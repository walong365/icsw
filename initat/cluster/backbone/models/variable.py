# Copyright (C) 2001-2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
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
import logging
import uuid
import json

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models import signals
from enum import Enum
from django.dispatch import receiver

from initat.cluster.backbone.models.functions import check_empty_string, \
    check_integer, cluster_timezone

logger = logging.getLogger(__name__)

__all__ = [
    "device_variable",
    "device_variable_scope",
]


class DeviceVariableManager(models.Manager):

    def get_cluster_id(self):
        try:
            return self.get(name="CLUSTER_ID").val_str
        except device_variable.DoesNotExist:
            return None

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
    # variable prefix
    prefix = models.CharField(max_length=127, default="")
    # forced flags, json-encoded flags
    forced_flags = models.CharField(max_length=127, default="")
    date = models.DateTimeField(auto_now_add=True)


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
            ("t", "time"),
            ("b", "blob"),
            # only for posting a new dv
            ("?", "guess")
        ]
    )
    val_str = models.TextField(blank=True, null=True, default="")
    val_int = models.IntegerField(null=True, blank=True, default=0)
    # base64 encoded
    val_blob = models.TextField(blank=True, null=True, default="")
    val_date = models.DateTimeField(null=True, blank=True)
    val_time = models.TextField(blank=True, null=True)  # This field type is a guess.
    uuid = models.TextField(default="", max_length=64)
    date = models.DateTimeField(auto_now_add=True)

    def set_value(self, value):
        if type(value) == datetime.datetime:
            self.var_type = "d"
            self.val_date = cluster_timezone.localize(value)
        elif type(value) in [int, long] or (isinstance(value, basestring) and value.isdigit()):
            self.var_type = "i"
            self.val_int = int(value)
        else:
            self.var_type = "s"
            self.val_str = value
        self._clear()

    def get_value(self):
        if self.var_type == "i":
            return self.val_int
        elif self.var_type == "s":
            return self.val_str
        else:
            return "get_value for {}".format(self.var_type)

    def _clear(self):
        # clear all values which are not used
        for _short, _long in [
            ("i", "int"),
            ("s", "str"),
            ("b", "blob"),
            ("d", "date"),
            ("t", "time")
        ]:
            if self.var_type != _short:
                setattr(self, "val_{}".format(_long), None)
    value = property(get_value, set_value)

    def __unicode__(self):
        return "{}[{}] = {}".format(
            self.name,
            self.var_type,
            str(self.get_value())
        )

    def init_as_gauge(self, max_value, start=0):
        self.__max, self.__cur = (max_value, start)
        self._update_gauge()

    def count(self, num=1):
        self.__cur += num
        self._update_gauge()

    def _update_gauge(self):
        new_val = min(100, int(float(100 * self.__cur) / float(max(1, self.__max))))
        if self.pk:
            if self.val_int != new_val:
                self.val_int = new_val
                device_variable.objects.filter(Q(pk=self.pk)).update(val_int=new_val)
        else:
            self.val_int = new_val
            self.save()

    class Meta:
        db_table = u'device_variable'
        unique_together = ("name", "device", "device_variable_scope",)
        ordering = ("name",)
        verbose_name = "Device variable"


@receiver(signals.pre_save, sender=device_variable)
def device_variable_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if cur_inst.device_id:
            _dvt = cur_inst.device_variable_type
            if _dvt.forced_flags:
                # set flags
                for _f_name, _f_value in json.loads(_dvt.forced_flags):
                    setattr(cur_inst, _f_name, _f_value)
            check_empty_string(cur_inst, "name")
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
            all_var_names = device_variable.objects.exclude(Q(pk=cur_inst.pk)).filter(Q(device=cur_inst.device)).values_list("name", flat=True)
            if cur_inst.name in all_var_names:
                raise ValidationError(
                    "name '{}' already used for device '{}'".format(
                        cur_inst.name,
                        unicode(cur_inst.device)
                    )
                )
            cur_inst._clear()
            if not cur_inst.uuid:
                cur_inst.uuid = str(uuid.uuid4())
