# Copyright (C) 2001-2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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
#
# -*- coding: utf-8 -*-
#
""" model definitions, configuration """

import logging

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, signals
from django.dispatch import receiver

from initat.cluster.backbone.models.functions import check_integer, check_empty_string

__all__ = [
    "config_catalog",
    "config",
    "ConfigServiceEnum",
    "config_str",
    "config_int",
    "config_blob",
    "config_bool",
    "config_script",
    "device_config",
]


logger = logging.getLogger(__name__)


class config_catalog(models.Model):
    idx = models.AutoField(primary_key=True)
    # MySQL restriction
    name = models.CharField(max_length=254, unique=True, blank=False, null=False)
    url = models.URLField(max_length=256, default="", blank=True)
    author = models.CharField(max_length=256, default="", blank=True)
    # gets increased by one on every download
    version = models.IntegerField(default=1)
    # is system catalog
    system_catalog = models.BooleanField(default=False)
    # priority
    priority = models.IntegerField(default=0)
    # extraction time
    extraction_time = models.DateTimeField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def create_local_catalog():
        def_cc = config_catalog.objects.create(
            name="local",
            system_catalog=True,
            url="http://www.initat.org/",
            author="Andreas Lang-Nevyjel",
        )
        return def_cc

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Configuration catalog'


@receiver(signals.pre_save, sender=config_catalog)
def config_catalog_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if cur_inst.system_catalog:
            _all_c = config_catalog.objects.exclude(Q(idx=cur_inst.idx)).filter(Q(system_catalog=True))
            if len(_all_c):
                raise ValidationError("Only one config_catalog with system_catalog=True allowed")


class ConfigServiceEnum(models.Model):
    # mirrors icswServiceEnumBase
    idx = models.AutoField(primary_key=True)
    enum_name = models.CharField(max_length=255, default="", unique=True)
    name = models.CharField(max_length=255, default="", unique=True)
    info = models.TextField(default="", blank=True)
    # is a root service and not a subservice (like image or kernel server)
    root_service = models.BooleanField(default=True)
    # single instance, only allowed once
    date = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def create_db_entry(srv_enum):
        _new_entry = ConfigServiceEnum.objects.create(
            enum_name=srv_enum.name,
            name=srv_enum.value.name,
            info=srv_enum.value.info,
            root_service=srv_enum.value.root_service,
        )
        return _new_entry

    def update_values(self, srv_enum):
        _changed = False
        for _attr_name in ["name", "info", "root_service"]:
            if getattr(self, _attr_name) != getattr(srv_enum.value, _attr_name):
                _changed = True
                setattr(self, _attr_name, getattr(srv_enum.value, _attr_name))
        if _changed:
            self.save()

    def __str__(self):
        return "ConfigServerEnum {}".format(self.name)


class config(models.Model):
    idx = models.AutoField(db_column="new_config_idx", primary_key=True)
    name = models.CharField(max_length=192, blank=False)
    config_catalog = models.ForeignKey(config_catalog, null=True)
    description = models.CharField(max_length=765, default="", blank=True)
    priority = models.IntegerField(null=True, default=0)
    # valid for servers (activate special functionalities)
    server_config = models.BooleanField(default=False)
    # system config, not user generated, now deprecated
    # system_config = models.BooleanField(default=False)
    # link to ConfigServerEnum to activate server services
    config_service_enum = models.ForeignKey("backbone.configserviceenum", null=True)
    enabled = models.BooleanField(default=True)
    date = models.DateTimeField(auto_now_add=True)
    # categories for this config
    categories = models.ManyToManyField("backbone.category", blank=True)

    def __str__(self):
        return self.name

    def show_variables(self, log_com, detail=False):
        log_com(" - config {} (pri {:d})".format(
            self.name,
            self.priority))
        if detail:
            for var_type in ["str", "int", "bool"]:
                for cur_var in getattr(self, "config_{}_set".format(var_type)).all():
                    log_com("    {:<20s} : {}".format(cur_var.name, str(cur_var)))

    def natural_key(self):
        return self.name

    class Meta:
        db_table = 'new_config'
        ordering = ["name", "config_catalog__name"]
        unique_together = (("name", "config_catalog"),)
        verbose_name = "Configuration"

    class ICSW_Meta:
        permissions = (
            ("modify_config", "modify global configurations", False),
        )
        fk_ignore_list = [
            "config_str", "config_int", "config_script",
            "config_bool", "config_blob", "mon_check_command"
        ]


@receiver(signals.pre_save, sender=config)
def config_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        cur_inst.description = cur_inst.description or ""
        check_empty_string(cur_inst, "name")
        # priority
        check_integer(cur_inst, "priority", min_val=-9999, max_val=9999)
        # if cur_inst.system_config:
        #    if cur_inst.config_catalog is None:
        #        try:
        #            sys_cc = config_catalog.objects.get(Q(system_catalog=True))
        #        except config_catalog.DoesNotExist:
        #            raise ValidationError("no System catalog available")
        #        else:
        #            cur_inst.config_catalog = sys_cc
        #    if not cur_inst.config_catalog.system_catalog:
        #        raise ValidationError(
        #            "System config '{}' has to reside inside the system config_catalog".format(
        #                cur_inst.name,
        #            )
        #        )


@receiver(signals.post_save, sender=config)
def config_post_save(sender, **kwargs):
    if not kwargs["raw"] and "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if kwargs["created"] and getattr(cur_inst, "create_default_entries", True):
            # list of vars to create
            var_add_list, script_add_list = ([], [])
            ch_model = apps.get_model("backbone", "config_hint")
            try:
                my_hint = ch_model.objects.get(Q(config_name=cur_inst.name))
            except ch_model.DoesNotExist:
                # soft search
                nem_names = ch_model.objects.filter(Q(exact_match=False)).values_list("config_name", flat=True)
                m_list = [_entry for _entry in nem_names if cur_inst.name.count(_entry)]
                if m_list:
                    m_list = [_name for _len, _name in sorted([(-len(_entry), _entry) for _entry in m_list])]
                    my_hint = ch_model.objects.get(Q(config_name=m_list[0]))
                else:
                    my_hint = None
            if my_hint is not None:
                ac_vars = my_hint.config_var_hint_set.filter(ac_flag=True)
                for ac_var in ac_vars:
                    if ac_var.ac_type == "str":
                        new_var = config_str(
                            value=ac_var.ac_value,
                        )
                    elif ac_var.ac_type == "int":
                        new_var = config_int(
                            value=int(ac_var.ac_value),
                        )
                    elif ac_var.ac_type == "bool":
                        new_var = config_bool(
                            value=True if ac_var.ac_value.lower() in ["1", "t", "yes", "true"] else False,
                        )
                    new_var.description = ac_var.ac_description
                    new_var.name = ac_var.var_name
                    var_add_list.append(new_var)
                ac_scripts = my_hint.config_script_hint_set.filter(ac_flag=True)
                for ac_script in ac_scripts:
                    script_add_list.append(
                        config_script(
                            name=ac_script.script_name,
                            description=ac_script.ac_description,
                            value=ac_script.ac_value,
                        )
                    )
            for _cvs in var_add_list + script_add_list:
                _cvs.config = cur_inst
                _cvs.save()
        if not cur_inst.config_catalog_id:
            if not config_catalog.objects.all().count():
                config_catalog.create_local_catalog()
            cur_inst.config_catalog = config_catalog.objects.all()[0]


class device_config(models.Model):
    idx = models.AutoField(db_column="device_config_idx", primary_key=True)
    device = models.ForeignKey("device")
    config = models.ForeignKey("backbone.config", db_column="new_config_id")
    date = models.DateTimeField(auto_now_add=True)

    def home_info(self):
        return self.info_str

    class Meta:
        db_table = 'device_config'
        verbose_name = "Device configuration"


@receiver(signals.post_save, sender=device_config)
def device_config_post_save(sender, instance, raw, **kwargs):
    pass
    # if not raw:
    #    log_usage_data = collections.defaultdict(lambda: [])
    #
    #    for mcc in instance.config.mon_check_command_set.all().select_related("mon_service_templ"):
    #        if mcc.mon_service_templ is not None and mcc.mon_service_templ.any_notification_enabled():
    #            log_usage_data[instance.device_id].append(mcc)
    #    LicenseUsage.log_usage(LicenseEnum.notification, LicenseParameterTypeEnum.service, log_usage_data)


class config_str(models.Model):
    idx = models.AutoField(db_column="config_str_idx", primary_key=True)
    name = models.CharField(max_length=192)
    description = models.CharField(db_column="descr", max_length=765)
    config = models.ForeignKey("config", db_column="new_config_id")
    value = models.TextField(blank=True)
    device = models.ForeignKey("device", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def get_object_type(self):
        return "str"

    def __str__(self):
        return self.value or ""

    class Meta:
        db_table = 'config_str'
        ordering = ("name",)
        verbose_name = "Configuration variable (string)"


@receiver(signals.pre_save, sender=config_str)
def config_str_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        check_empty_string(cur_inst, "name")
        all_var_names = list(cur_inst.config.config_str_set.exclude(Q(pk=cur_inst.pk)).values_list("name", flat=True)) + \
            list(cur_inst.config.config_int_set.all().values_list("name", flat=True)) + \
            list(cur_inst.config.config_bool_set.all().values_list("name", flat=True)) + \
            list(cur_inst.config.config_blob_set.all().values_list("name", flat=True))
        if cur_inst.name in all_var_names:
            raise ValidationError("name '{}' already used".format(cur_inst.name))
        cur_inst.value = cur_inst.value or ""


class config_blob(models.Model):
    idx = models.AutoField(db_column="config_blob_idx", primary_key=True)
    name = models.CharField(max_length=192)
    description = models.CharField(max_length=765, db_column="descr")
    # deprecated
    config = models.ForeignKey("config", db_column="new_config_id")
    value = models.TextField(blank=True)
    device = models.ForeignKey("device", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def get_object_type(self):
        return "blob"

    class Meta:
        db_table = 'config_blob'
        verbose_name = "Configuration variable (blob)"


@receiver(signals.pre_save, sender=config_blob)
def config_blob_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        check_empty_string(cur_inst, "name")
        all_var_names = list(cur_inst.config.config_str_set.all().values_list("name", flat=True)) + \
            list(cur_inst.config.config_int_set.all().values_list("name", flat=True)) + \
            list(cur_inst.config.config_bool_set.all().values_list("name", flat=True)) + \
            list(cur_inst.config.config_blob_set.exclude(Q(pk=cur_inst.pk)).values_list("name", flat=True))
        if cur_inst.name in all_var_names:
            raise ValidationError("name '{}' already used".format(cur_inst.name))


class config_bool(models.Model):
    idx = models.AutoField(db_column="config_bool_idx", primary_key=True)
    name = models.CharField(max_length=192)
    description = models.CharField(max_length=765, db_column="descr")
    # deprecated
    config = models.ForeignKey("config", db_column="new_config_id")
    value = models.IntegerField(null=True, blank=True)
    device = models.ForeignKey("device", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def get_object_type(self):
        return "bool"

    def __str__(self):
        return "True" if self.value else "False"

    class Meta:
        db_table = 'config_bool'
        verbose_name = "Configuration variable (boolean)"


@receiver(signals.pre_save, sender=config_bool)
def config_bool_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        check_empty_string(cur_inst, "name")
        all_var_names = list(
            cur_inst.config.config_str_set.all().values_list("name", flat=True)
        ) + list(
            cur_inst.config.config_int_set.all().values_list("name", flat=True)
        ) + list(
            cur_inst.config.config_bool_set.exclude(Q(pk=cur_inst.pk)).values_list("name", flat=True)
        ) + list(
            cur_inst.config.config_blob_set.all().values_list("name", flat=True)
        )
        if cur_inst.name in all_var_names:
            raise ValidationError("name '{}' already used".format(cur_inst.name))
        try:
            if isinstance(cur_inst.value, bool):
                pass
            else:
                if isinstance(cur_inst.value, int):
                    cur_inst.value = True if cur_inst.value else False
                else:
                    cur_inst.value = True if (cur_inst.value or "").lower() in ["1", "true", "yes"] else False
        except ValueError:
            raise ValidationError("value cannot be interpret as bool")


class config_int(models.Model):
    idx = models.AutoField(db_column="config_int_idx", primary_key=True)
    name = models.CharField(max_length=192)
    description = models.CharField(max_length=765, db_column="descr")
    # deprecated
    config = models.ForeignKey("config", db_column="new_config_id")
    value = models.IntegerField(null=True, blank=True)
    device = models.ForeignKey("device", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def get_object_type(self):
        return "int"

    def __str__(self):
        if isinstance(self.value, str):
            self.value = int(self.value)
        return "{:d}".format(self.value or 0)

    class Meta:
        db_table = 'config_int'
        verbose_name = "Configuration variable (integer)"


@receiver(signals.pre_save, sender=config_int)
def config_int_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        check_empty_string(cur_inst, "name")
        all_var_names = list(cur_inst.config.config_str_set.all().values_list("name", flat=True)) + \
            list(cur_inst.config.config_int_set.exclude(Q(pk=cur_inst.pk)).values_list("name", flat=True)) + \
            list(cur_inst.config.config_bool_set.all().values_list("name", flat=True)) + \
            list(cur_inst.config.config_blob_set.all().values_list("name", flat=True))
        if cur_inst.name in all_var_names:
            raise ValidationError("name '{}' already used".format(cur_inst.name))
        check_integer(cur_inst, "value")


class config_script(models.Model):
    idx = models.AutoField(db_column="config_script_idx", primary_key=True)
    name = models.CharField(max_length=192)
    description = models.CharField(max_length=765, db_column="descr", blank=True)
    enabled = models.BooleanField(default=True)
    priority = models.IntegerField(null=True, blank=True, default=0)
    config = models.ForeignKey("config", db_column="new_config_id")
    value = models.TextField(blank=True)
    # to be removed
    error_text = models.TextField(blank=True, default="")
    device = models.ForeignKey("device", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def get_object_type(self):
        return "script"

    class Meta:
        db_table = 'config_script'
        ordering = ("priority", "name",)
        verbose_name = "Configuration script"


@receiver(signals.pre_save, sender=config_script)
def config_script_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not cur_inst.name:
            raise ValidationError("name is empty")
        if not cur_inst.value:
            raise ValidationError("value is empty")
        if cur_inst.name in cur_inst.config.config_script_set.exclude(Q(pk=cur_inst.pk)).values_list("name", flat=True):
            raise ValidationError("name '{}' already used".format(cur_inst.name))
        check_integer(cur_inst, "priority")
        cur_inst.error_text = cur_inst.error_text or ""
