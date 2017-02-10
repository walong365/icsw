# Copyright (C) 2001-2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server-server
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
""" models for NOCTUA and CORVUS, device variable definition file """

import datetime
import json
import logging
import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models import signals
from django.dispatch import receiver

from initat.cluster.backbone.models.functions import check_empty_string, \
    check_integer, cluster_timezone, memoize_with_expiry

logger = logging.getLogger(__name__)

__all__ = [
    "device_variable",
    "device_variable_scope",
    "dvs_allowed_name",
]


class DeviceVariableManager(models.Manager):

    @memoize_with_expiry(10)
    def get_cluster_id(self, default=None):
        try:
            return self.get(
                Q(name="CLUSTER_ID") &
                Q(device__device_group__cluster_device_group=True)
            ).val_str
        except device_variable.DoesNotExist:
            return default

    @memoize_with_expiry(10)
    def get_cluster_name(self, default=None):
        try:
            return self.get(
                Q(name="CLUSTER_NAME") &
                Q(device__device_group__cluster_device_group=True)
            ).val_str
        except device_variable.DoesNotExist:
            return default

    def get_device_variable_value(self, device, var_name, default_val=None):
        """ Returns variable considering inheritance. """
        var_value = default_val
        try:
            cur_var = device.device_variable_set.get(Q(name=var_name))
        except device_variable.DoesNotExist:
            try:
                cur_var = device.device_group.device.device_variable_set.get(
                    Q(name=var_name)
                )
            except device_variable.DoesNotExist:
                try:
                    cur_var = device_variable.objects.get(
                        Q(device__device_group__cluster_device_group=True) &
                        Q(name=var_name)
                    )
                except device_variable.DoesNotExist:
                    cur_var = None
        if cur_var:
            var_value = cur_var.value
        return var_value


# class DeviceVariableTypeManager(models.Manager):
#     def get_by_natural_key(self, name):
#        return self.get(name=name)


class device_variable_scope(models.Model):
    # objects = DeviceVariableTypeManager()
    idx = models.AutoField(primary_key=True)
    name = models.CharField(
        max_length=32,
        unique=True,
    )
    # priority (for ordering)
    priority = models.IntegerField(default=0)
    # description
    description = models.TextField(default="", blank=True)
    # variable prefix
    prefix = models.CharField(max_length=127, default="", blank=True)
    # is fixed
    fixed = models.BooleanField(default=False)
    # system scope, not editable
    system_scope = models.BooleanField(default=False)
    # forced flags, json-encoded flags
    forced_flags = models.CharField(max_length=127, default="", blank=True)
    # is default scope
    default_scope = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return "device_variable_scope '{}'".format(
            self.name,
        )


class dvs_allowed_name(models.Model):
    idx = models.AutoField(primary_key=True)
    device_variable_scope = models.ForeignKey("backbone.device_variable_scope")
    name = models.CharField(
        max_length=127,
        default="",
    )
    # globally unique
    unique = models.BooleanField(default=False)
    # editable (on frontend)
    editable = models.BooleanField(default=False)
    # forced type
    forced_type = models.CharField(
        max_length=3,
        choices=[
            ("", "ignore"),
            ("i", "integer"),
            ("s", "string"),
            ("d", "datetime"),
            ("D", "date"),
            ("t", "time"),
            ("b", "blob"),
        ],
        default="",
    )
    # group, for grouping :-)
    group = models.CharField(max_length=127, default="", blank=True)
    description = models.TextField(default="", blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return "Allowed for scope {}: '{}', forced_type='{}', group='{}'".format(
            self.device_variable_scope.name,
            self.name,
            self.forced_type,
            self.group,
        )

    class Meta:
        unique_together = ("name", "device_variable_scope")


@receiver(signals.pre_save, sender=dvs_allowed_name)
def dvs_allowed_name__pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not cur_inst.device_variable_scope.fixed:
            raise ValidationError(
                "Scope {} is not fixed".format(
                    str(cur_inst.device_variable_scope)
                )
            )


class device_variable(models.Model):
    objects = DeviceVariableManager()

    idx = models.AutoField(db_column="device_variable_idx", primary_key=True)
    device = models.ForeignKey("device")
    is_public = models.BooleanField(default=True)
    name = models.CharField(max_length=765)
    device_variable_scope = models.ForeignKey("backbone.device_variable_scope")
    description = models.CharField(max_length=765, default="", blank=True)
    # can be copied to a group or device ? There is no sense in making the cluster_name a local instance
    local_copy_ok = models.BooleanField(default=True)
    # will the variable be inerited by lower levels (CDG -> DG -> D) ?
    inherit = models.BooleanField(default=True)
    # protected, not deletable by frontend
    protected = models.BooleanField(default=False)
    var_type = models.CharField(
        max_length=3,
        choices=[
            ("i", "integer"),
            ("s", "string"),
            ("d", "datetime"),
            ("D", "date"),
            ("t", "time"),
            ("b", "blob"),
            # only for posting a new dv
            ("?", "guess")
        ]
    )
    val_str = models.TextField(blank=True, null=True, default="")
    val_int = models.IntegerField(null=True, blank=True, default=0)
    # boolean value
    val_bool = models.NullBooleanField(null=True, blank=True, default=False)
    # base64 encoded
    val_blob = models.TextField(blank=True, null=True, default="")
    val_date = models.DateTimeField(null=True, blank=True)
    val_time = models.TextField(blank=True, null=True)  # This field type is a guess.
    # link to dvs_allowed_name entry
    dvs_allowed_name = models.ForeignKey("backbone.dvs_allowed_name", null=True, blank=True)
    uuid = models.TextField(default="", max_length=64, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def get_private_variable(**kwargs):
        return device_variable(
            is_public=False,
            local_copy_ok=False,
            inherit=False,
            protected=True,
            **kwargs
        )

    def set_value(self, value):
        if isinstance(value, datetime.datetime):
            self.var_type = "d"
            self.val_date = cluster_timezone.localize(value)
        elif isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
            self.var_type = "i"
            self.val_int = int(value)
        elif isinstance(value, bool):
            self.var_type = "B"
            self.val_bool = value
        else:
            self.var_type = "s"
            self.val_str = value
        self._clear()

    def get_value(self):
        if self.var_type == "i":
            return self.val_int
        elif self.var_type == "s":
            return self.val_str
        elif self.var_type == "B":
            return self.val_bool
        else:
            return "get_value for {}".format(self.var_type)

    def _clear(self):
        # clear all values which are not used
        for _short_list, _long in [
            (["i"], "int"),
            (["s"], "str"),
            (["b"], "blob"),
            (["d", "D"], "date"),
            (["t"], "time"),
            (["B"], "bool"),
        ]:
            if self.var_type not in _short_list:
                setattr(self, "val_{}".format(_long), None)
    value = property(get_value, set_value)

    def __str__(self):
        return "{}[{}] = {}".format(
            self.name,
            self.var_type,
            str(self.get_value())
        )

    class Meta:
        db_table = 'device_variable'
        unique_together = ("name", "device", "device_variable_scope",)
        ordering = ("name",)
        verbose_name = "Device variable"


@receiver(signals.pre_save, sender=device_variable)
def device_variable_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if cur_inst.device_id:
            if not cur_inst.device_variable_scope_id:
                cur_inst.device_variable_scope = device_variable_scope.objects.get(Q(default_scope=True))
            _dvs = cur_inst.device_variable_scope
            if _dvs.forced_flags:
                # set flags
                for _f_name, _f_value in json.loads(_dvs.forced_flags).items():
                    setattr(cur_inst, _f_name, _f_value)
            # check values
            if cur_inst.var_type == "?":
                # guess type
                _val = cur_inst.val_str
                cur_inst.val_str = ""
                if len(_val.strip()) and _val.strip().isdigit():
                    cur_inst.var_type = "i"
                    cur_inst.val_int = int(_val.strip())
                else:
                    cur_inst.var_type = "s"
                    cur_inst.val_str = _val
            if cur_inst.var_type == "s":
                check_empty_string(cur_inst, "val_str")
            if cur_inst.var_type == "i":
                check_integer(cur_inst, "val_int")
            check_empty_string(cur_inst, "var_type")
            if _dvs.dvs_allowed_name_set.all().count():
                _allowed = _dvs.dvs_allowed_name_set.all()
                if cur_inst.name not in [entry.name for entry in _allowed]:
                    raise ValidationError(
                        "Name '{}' not allowed in scope '{}'".format(
                            cur_inst.name,
                            _dvs.name,
                        )
                    )
                _allowed_struct = [entry for entry in _allowed if entry.name == cur_inst.name][0]
                cur_inst.dvs_allowed_name = _allowed_struct
                if _allowed_struct.unique:
                    _found = device_variable.objects.exclude(
                        Q(pk=cur_inst.idx)
                    ).filter(
                        Q(name=cur_inst.name) & Q(device_variable_scope=_dvs)
                    ).count()
                    print("Fg", _found)
                if _allowed_struct.forced_type:
                    # print(cur_inst.var_type, _allowed_struct.forced_type)
                    if cur_inst.var_type != _allowed_struct.forced_type:
                        raise ValidationError("Type is not allowed (VariableScope issue)")
            check_empty_string(cur_inst, "name")
            all_var_names = device_variable.objects.exclude(Q(pk=cur_inst.pk)).filter(Q(device=cur_inst.device)).values_list("name", flat=True)
            if cur_inst.name in all_var_names:
                raise ValidationError(
                    "name '{}' already used for device '{}'".format(
                        cur_inst.name,
                        str(cur_inst.device)
                    )
                )
            cur_inst._clear()
            if not cur_inst.uuid:
                cur_inst.uuid = str(uuid.uuid4())
