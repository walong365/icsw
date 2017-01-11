#
# Copyright (C) 2016 Gregor Kaufmann, Andreas Lang-Nevyjel init.at
#
# this file is part of icsw-server
#
# Send feedback to: <g.kaufmann@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA



import datetime
import logging

from django.db import models
from django.db.models import Q, signals
from django.dispatch import receiver
from django.utils import timezone
from enum import IntEnum

logger = logging.getLogger(__name__)

__all__ = [
    "StaticAssetTemplateFieldType",
    "StaticAssetTemplate",
    "StaticAssetTemplateField",
    "StaticAsset",
    "StaticAssetFieldValue",
]


class StaticAssetTemplateFieldType(IntEnum):
    INTEGER = 1
    # oneline
    STRING = 2
    # date
    DATE = 3
    # textarea
    TEXT = 4


# static assets
class StaticAssetTemplate(models.Model):
    # to be defined by administrator
    idx = models.AutoField(primary_key=True)
    # asset type
    type = models.CharField(max_length=256)
    # name of Template
    name = models.CharField(max_length=128, unique=True)
    # description
    description = models.TextField(default="", blank=True)
    # system template (not deleteable)
    system_template = models.BooleanField(default=False)
    # parent template (for copy operations)
    parent_template = models.ForeignKey("backbone.StaticAssetTemplate", null=True)
    # link to creation user
    user = models.ForeignKey("backbone.user", null=True)
    # enabled
    enabled = models.BooleanField(default=True)
    # allow multiple instances
    multi = models.BooleanField(default=False)
    # created
    date = models.DateTimeField(auto_now_add=True)

    def check_ordering(self):
        # check ordering of elements
        _dict = {}
        for entry in self.staticassettemplatefield_set.all():
            _dict.setdefault(entry.ordering, []).append(entry)
        if any([len(_value) > 1 for _value in _dict.values()]):
            # reorder
            for _idx, _entry in enumerate(self.staticassettemplatefield_set.all().order_by("ordering")):
                _entry.ordering = _idx
                _entry.save(update_fields=["ordering"])

    def copy(self, new_obj, create_user):
        nt = StaticAssetTemplate(
            type=self.type,
            name=new_obj["name"],
            description=new_obj["description"],
            system_template=False,
            parent_template=self,
            user=create_user,
            enabled=self.enabled,
        )
        nt.save()
        for _field in self.staticassettemplatefield_set.all():
            nt.staticassettemplatefield_set.add(_field.copy(nt, create_user))
        return nt

    class CSW_Meta:
        permissions = (
            ("setup", "Change StaticAsset templates", False),
        )


class StaticAssetTemplateField(models.Model):
    idx = models.AutoField(primary_key=True)
    # template
    static_asset_template = models.ForeignKey("backbone.StaticAssetTemplate")
    # name
    name = models.CharField(max_length=64, default="")
    # description
    field_description = models.TextField(default="", blank=True)
    field_type = models.IntegerField(choices=[(_type.value, _type.name) for _type in StaticAssetTemplateFieldType])
    # is optional
    optional = models.BooleanField(default=True)
    # is consumable (for integer fields)
    consumable = models.BooleanField(default=False)
    # consumable values, should be start > warn > critical
    consumable_start_value = models.IntegerField(default=0)
    consumable_warn_value = models.IntegerField(default=0)
    consumable_critical_value = models.IntegerField(default=0)
    # date check
    date_check = models.BooleanField(default=False)
    # date warning limits in days
    date_warn_value = models.IntegerField(default=60)
    date_critical_value = models.IntegerField(default=30)
    # field is fixed (cannot be altered)
    fixed = models.BooleanField(default=False)
    # default value
    default_value_str = models.CharField(default="", blank=True, max_length=255)
    default_value_int = models.IntegerField(default=0)
    default_value_date = models.DateField(default=timezone.now)
    default_value_text = models.TextField(default="", blank=True)
    # bounds, for input checking
    has_bounds = models.BooleanField(default=False)
    value_int_lower_bound = models.IntegerField(default=0)
    value_int_upper_bound = models.IntegerField(default=0)
    # monitor flag, only for datefields and / or consumable (...?)
    monitor = models.BooleanField(default=False)
    # hidden, used for linking (...?)
    hidden = models.BooleanField(default=False)
    # show_in_overview
    show_in_overview = models.BooleanField(default=False)
    # ordering, starting from 0 to #fields - 1
    ordering = models.IntegerField(default=0)
    # created
    date = models.DateTimeField(auto_now_add=True)

    def copy(self, new_template, create_user):
        nf = StaticAssetTemplateField(
            static_asset_template=new_template,
            name=self.name,
            field_description=self.field_description,
            field_type=self.field_type,
            optional=self.optional,
            consumable=self.consumable,
            default_value_str=self.default_value_str,
            default_value_int=self.default_value_int,
            default_value_date=self.default_value_date,
            default_value_text=self.default_value_text,
            has_bounds=self.has_bounds,
            value_int_lower_bound=self.value_int_lower_bound,
            value_int_upper_bound=self.value_int_upper_bound,
            monitor=self.monitor,
            fixed=self.fixed,
            hidden=self.hidden,
            show_in_overview=self.show_in_overview,
            consumable_start_value=self.consumable_start_value,
            consumable_warn_value=self.consumable_warn_value,
            consumable_critical_value=self.consumable_critical_value,
            date_warn_value=self.date_warn_value,
            date_critical_value=self.date_critical_value,
            date_check=self.date_check,
        )
        nf.save()
        return nf

    def get_attr_name(self):
        if self.field_type == StaticAssetTemplateFieldType.INTEGER.value:
            return ("value_int", "int")
        elif self.field_type == StaticAssetTemplateFieldType.STRING.value:
            return ("value_str", "str")
        elif self.field_type == StaticAssetTemplateFieldType.DATE.value:
            return ("value_date", "date")
        elif self.field_type == StaticAssetTemplateFieldType.TEXT.value:
            return ("value_text", "text")
        else:
            raise ValueError("wrong field type {}".format(self.field_type))

    def create_field_value(self, asset):
        new_f = StaticAssetFieldValue(
            static_asset=asset,
            static_asset_template_field=self,
            change_user=asset.create_user,
        )
        _local, _short = self.get_attr_name()
        setattr(new_f, _local, getattr(self, "default_{}".format(_local)))
        new_f.save()
        return new_f

    class Meta:
        unique_together = [
            ("static_asset_template", "name"),
        ]
        ordering = ["ordering"]


@receiver(signals.post_save, sender=StaticAssetTemplateField)
def StaticAssetTemplateField_post_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not cur_inst.optional:
            # get all staticassets where this field is not set
            _missing_assets = StaticAsset.objects.filter(
                Q(static_asset_template=cur_inst.static_asset_template)
            ).exclude(
                Q(staticassetfieldvalue__static_asset_template_field=cur_inst)
            )
            if _missing_assets.count():
                # add fields
                for _asset in _missing_assets:
                    cur_inst.create_field_value(_asset)


class StaticAsset(models.Model):
    # used for linking
    idx = models.AutoField(primary_key=True)
    # template
    static_asset_template = models.ForeignKey("backbone.StaticAssetTemplate")
    # create user
    create_user = models.ForeignKey("backbone.user", null=True)
    # device
    device = models.ForeignKey("backbone.device")
    date = models.DateTimeField(auto_now_add=True)

    def add_fields(self):
        for _f in self.static_asset_template.staticassettemplatefield_set.all():
            _f.create_field_value(self)


class StaticAssetFieldValue(models.Model):
    idx = models.AutoField(primary_key=True)
    # template
    static_asset = models.ForeignKey("backbone.StaticAsset")
    # field
    static_asset_template_field = models.ForeignKey("backbone.StaticAssetTemplateField")
    # change user
    change_user = models.ForeignKey("backbone.user")
    # value
    value_str = models.CharField(null=True, blank=True, max_length=255, default=None)
    value_int = models.IntegerField(null=True, blank=True, default=None)
    value_date = models.DateField(null=True, blank=True, default=None)
    value_text = models.TextField(null=True, blank=True, default=None)
    date = models.DateTimeField(auto_now_add=True)

    def check_new_value(self, in_dict, xml_response):
        _field = self.static_asset_template_field
        _local, _short = _field.get_attr_name()
        _value = in_dict[_short]
        _errors = []
        if not _field.fixed:
            if _short == "int":
                # check for lower / upper bounds
                if _field.has_bounds:
                    if _value < _field.value_int_lower_bound:
                        _errors.append(
                            "value {:d} is below lower bound {:d}".format(
                                _value,
                                _field.value_int_lower_bound,
                            )
                        )
                    if _value > _field.value_int_upper_bound:
                        _errors.append(
                            "value {:d} is above upper bound {:d}".format(
                                _value,
                                _field.value_int_upper_bound,
                            )
                        )
        if _errors:
            xml_response.error(
                "Field {}: {}".format(
                    _field.name,
                    ", ".join(_errors)
                )
            )
            return False
        else:
            return True

    def set_new_value(self, in_dict, user):
        _field = self.static_asset_template_field
        _local, _short = _field.get_attr_name()
        if not _field.fixed:
            # ignore changes to fixed values
            if _short == "date":
                # cast date
                setattr(self, _local, datetime.datetime.strptime(in_dict[_short], "%d.%m.%Y").date())
            else:
                setattr(self, _local, in_dict[_short])
            self.change_user = user
            self.save()
