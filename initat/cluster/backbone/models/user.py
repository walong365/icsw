# -*- coding: utf-8 -*-
#
# Copyright (C) 2014-2017 Andreas Lang-Nevyjel
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
""" NOCTUA / CORUVS models, user part """

import base64
import crypt
import datetime
import hashlib
import inspect
import os
import random
import string

import django.core.serializers
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.db import models
from django.db.models import Q, signals
from django.dispatch import receiver
from django.utils import timezone
from django.utils.encoding import force_text
from enum import Enum

from initat.cluster.backbone.models.functions import check_empty_string, check_integer, \
    get_vnc_enc
from initat.cluster.backbone.signals import UserChanged, GroupChanged, RoleChanged
from initat.constants import GEN_CS_NAME
from initat.tools import config_store

__all__ = [
    "csw_permission",
    "csw_object_permission",
    "user",
    "group",
    "Role",
    "RolePermission",
    "RoleObjectPermission",
    "user_device_login",
    "user_variable",
    "group_permission",
    "group_object_permission",
    "user_permission",
    "user_object_permission",
    "user_quota_setting",
    "group_quota_setting",
    "AC_MASK_READ",
    "AC_MASK_MODIFY",
    "AC_MASK_DELETE",
    "AC_MASK_CREATE",
    "AC_MASK_DICT",
    "user_scan_run",
    "user_scan_result",
    "virtual_desktop_protocol",
    "virtual_desktop_user_setting",
    "window_manager",
    "login_history",
    "UserLogEntry",
    "RouteTrace",
    # special var names
    "SPECIAL_USER_VAR_NAMES",
]


AC_MASK_READ = 0
AC_MASK_MODIFY = 1
AC_MASK_CREATE = 2
AC_MASK_DELETE = 4

AC_MASK_DICT = {
    "AC_MASK_READ": AC_MASK_READ,
    "AC_MASK_MODIFY": AC_MASK_MODIFY,
    "AC_MASK_CREATE": AC_MASK_CREATE,
    "AC_MASK_DELETE": AC_MASK_DELETE,
}

AC_READONLY = AC_MASK_READ
AC_MODIFY = AC_MASK_READ | AC_MASK_MODIFY
AC_CREATE = AC_MASK_READ | AC_MASK_MODIFY | AC_MASK_CREATE
AC_FULL = AC_MASK_READ | AC_MASK_MODIFY | AC_MASK_CREATE | AC_MASK_DELETE


# special user var names
class SPECIAL_USER_VAR_NAMES(Enum):
    network_topology_pipe = "$$network_topology_pipe"
    livestatus_dashboard_pipe = "$$livestatus_dashboard_pipe"
    device_location_pipe = "$$device_location_pipe"


# RouteChanges
class RouteTrace(models.Model):
    idx = models.AutoField(primary_key=True)
    session_id = models.CharField(max_length=64, default="")
    user_id = models.IntegerField(default=0)
    from_name = models.CharField(max_length=64)
    to_name = models.CharField(max_length=64)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return "RouteTrace, session {} ({:d}) from {} to {}".format(
            self.session_id,
            self.user_id,
            self.from_name,
            self.to_name,
        )


# icswAuthCache structure
class icswAuthCache(object):
    def __init__(self, auth_obj):
        # auth_obj is a user or a group
        self.auth_obj = auth_obj
        self.model_name = self.auth_obj._meta.model_name
        self.cache_key = "auth_{}_{:d}".format(
            auth_obj._meta.object_name,
            auth_obj.pk,
        )
        # permissions with code_name
        self.__perms, self.__obj_perms = ({}, {})
        # permissions on modellevel
        self.__model_perms, self.__model_obj_perms = ({}, {})
        if self.auth_obj.__class__.__name__ == "user":
            self.has_all_perms = self.auth_obj.is_superuser
        else:
            self.has_all_perms = False
        # print self.cache_key
        self._from_db()
        # init device <-> device group luts
        # maps from device to the respective meta-device
        self.__dg_lut = {}

    def _from_db(self):
        def icsw_key(perm):
            return "{}.{}.{}".format(
                perm.content_type.app_label,
                perm.content_type.model_class().__name__.lower(),
                perm.codename,
            )

        def model_key(perm_key):
            return ".".join(perm_key.split(".")[:2])

        # dict, icsw_perm_key -> icsw_perm
        self.__perm_dict = {
            icsw_key(cur_perm): cur_perm for cur_perm in csw_permission.objects.all().select_related("content_type")
        }
        # dict, content label -> list of perms
        self.__model_perm_dict = {}
        for _key, _value in self.__perm_dict.items():
            self.__model_perm_dict.setdefault(model_key(_key), {})[_key] = _value
        # pprint.pprint(self.__model_perm_dict)
        # pprint.pprint(self.__perm_dict)
        # print self.__perm_dict.keys()
        _q = RolePermission.objects
        _q_obj = RoleObjectPermission.objects
        if self.model_name == "user":
            _q = _q.filter(Q(role__role_users=self.auth_obj))
            _q_obj = _q_obj.filter(Q(role__role_users=self.auth_obj))
        else:
            _q = _q.filter(Q(role__role_groups=self.auth_obj))
            _q_obj = _q_obj.filter(Q(role__role_groups=self.auth_obj))
        if self.has_all_perms:
            # set all perms
            for perm in csw_permission.objects.all().select_related("content_type"):
                self.__perms[icsw_key(perm)] = AC_FULL
                self.__model_perms[model_key(icsw_key(perm))] = AC_FULL
        else:
            for perm in _q.select_related("csw_permission__content_type"):
                _icsw_key = icsw_key(perm.csw_permission)
                _model_key = model_key(_icsw_key)
                self.__perms[_icsw_key] = perm.level
                if _model_key not in self.__model_perms:
                    self.__model_perms[_model_key] = 0
                self.__model_perms[_model_key] |= perm.level
        for perm in _q_obj.select_related("csw_object_permission__csw_permission__content_type"):
            _icsw_key = icsw_key(perm.csw_object_permission.csw_permission)
            _model_key = model_key(_icsw_key)
            self.__obj_perms.setdefault(_icsw_key, {})[perm.csw_object_permission.object_pk] = perm.level
            self.__model_obj_perms.setdefault(
                _model_key,
                {}
            ).setdefault(perm.csw_object_permission.object_pk, 0)
            self.__model_obj_perms[_model_key][perm.csw_object_permission.object_pk] |= perm.level
        # pprint.pprint(self.__perms)
        # pprint.pprint(self.__obj_perms)

    def _get_code_key(self, app_label, content_name, code_name=None):
        if code_name is None:
            code_key = "{}.{}".format(app_label, content_name)
            if code_key not in self.__model_perm_dict:
                raise ImproperlyConfigured("wrong content_type {}".format(code_key))
        else:
            code_key = "{}.{}.{}".format(app_label, content_name, code_name)
            if code_key not in self.__perm_dict:
                raise ImproperlyConfigured("wrong permission name {}".format(code_key))
        return code_key

    def has_global_permission(self, app_label, content_name, code_name):
        code_key = self._get_code_key(app_label, content_name, code_name)
        return code_key in self.__perms

    def has_global_model_permission(self, app_label, content_name):
        code_key = self._get_code_key(app_label, content_name)
        return code_key in self.__model_perms

    def get_object_permission_level(self, app_label, content_name, code_name, obj=None):
        code_key = self._get_code_key(app_label, content_name, code_name)
        _level = self.__perms.get(code_key, -1)
        if obj is not None:
            if code_key in self.__obj_perms:
                _level = self.__obj_perms[code_key].get(obj.pk, _level)
        return _level

    def has_object_permission(self, app_label, content_name, code_name, obj=None):
        code_key = self._get_code_key(app_label, content_name, code_name)
        if self.has_global_permission(app_label, content_name, code_name):
            # at fist check global permission
            return True
        elif code_key in self.__obj_perms:
            if obj:
                if app_label == obj._meta.app_label:
                    return obj.pk in self.__obj_perms.get(code_key, [])
                else:
                    return False
            else:
                # no obj given so if the key is found in obj_perms it means that at least we have one object set
                return True
        else:
            return False

    def get_allowed_object_list(self, app_label, content_name, code_name):
        code_key = self._get_code_key(app_label, content_name, code_name)
        if self.has_global_permission(app_label, content_name, code_name) or getattr(self.auth_obj, "is_superuser", False):
            # at fist check global permission, return all devices
            return set(
                apps.get_model(
                    app_label,
                    self.__perm_dict[code_key].content_type.model_class().__name__
                ).objects.all().values_list("pk", flat=True)
            )
        elif code_key in self.__obj_perms:
            # only return devices where the code_key is set
            return set(self.__obj_perms[code_key].keys())
        else:
            return set()

    def get_allowed_object_list_model(self, app_label, content_name):
        # return all objects defined by app_label and content name where the auth_object has any rights for
        code_key = self._get_code_key(app_label, content_name)
        if self.has_global_model_permission(app_label, content_name) or getattr(self.auth_obj, "is_superuser", False):
            # at fist check global permission, return all devices
            return set(
                apps.get_model(
                    app_label,
                    list(self.__model_perm_dict[code_key].values())[0].content_type.model_class().__name__
                ).objects.all().values_list("pk", flat=True)
            )
        elif code_key in self.__model_obj_perms:
            # only return devices where the code_key is set
            return set(self.__model_obj_perms[code_key].keys())
        else:
            return set()

    def get_all_object_perms(self, obj):
        if obj:
            obj_ct = ContentType.objects.get_for_model(obj)
            # which permissions are valid for this object ?
            obj_perms = set([key for key, value in self.__perm_dict.items() if value.content_type == obj_ct])
        else:
            # copy
            obj_perms = set(self.__perm_dict.keys())
        if self.has_all_perms:
            # return all permissions
            return {key: AC_FULL for key in obj_perms}
        else:
            # which permissions are globaly set ?
            global_perms = {key: value for key, value in self.__perms.items() if key in obj_perms}
            # obj_perms = {key: self.__perms[key] for key in obj_perms.iterkeys()}
            if obj:
                # local permissions
                local_perms = {key: max(obj_list.values()) for key, obj_list in self.__obj_perms.items() if key in obj_perms and obj.pk in obj_list}
            else:
                local_perms = {key: max(obj_list.values()) for key, obj_list in self.__obj_perms.items() if key in obj_perms}
            # merge to result permissions
            result_perms = {key: max(global_perms.get(key, -1), local_perms.get(key, -1)) for key in set(global_perms.keys()) | set(local_perms.keys())}
            # only use values with at least level 0
            result_perms = {_key: _value for _key, _value in result_perms.items() if _value >= 0}
            return result_perms

    def get_object_access_levels(self, obj, is_superuser):
        obj_type = obj._meta.model_name
        # returns a dict with all access levels for the given object
        obj_perms = [
            key for key, value in self.__perm_dict.items() if value.content_type.model_class().__name__ == obj_type
        ]
        if is_superuser:
            ac_dict = {key: AC_FULL for key in obj_perms}
        else:
            ac_dict = {key: self.__obj_perms.get(key, {}).get(obj.pk, self.__perms.get(key, -1)) for key in obj_perms}
            # filter values
            ac_dict = {key: value for key, value in ac_dict.items() if value >= 0}
            if obj_type == "device":
                # for devices we assume that the minimum access level is 0 (pre-filtered by the access_to_devicegroup feature)
                self._fill_dg_lut(obj)
                # get permissions dict for meta device
                meta_dict = {key: self.__obj_perms.get(key, {}).get(self.__dg_lut[obj.pk], self.__perms.get(key, -1)) for key in obj_perms}
                # copy to device permdict
                for key, value in meta_dict.items():
                    # only use values with at least level 0
                    if value >= 0 or key in ac_dict:
                        ac_dict[key] = max(ac_dict.get(key, 0), value)
        return ac_dict

    def _fill_dg_lut(self, dev):
        if dev.pk not in self.__dg_lut:
            from django.apps import apps
            device = apps.get_model("backbone", "device")
            for dev_pk, md_pk in device._default_manager.filter(Q(device_group=dev.device_group_id)).values_list("pk", "device_group__device"):
                self.__dg_lut[dev_pk] = md_pk

    def get_global_permissions(self):
        return self.__perms


class csw_permission(models.Model):
    """
    ClusterSoftware permissions
    - global permissions
    """
    idx = models.AutoField(primary_key=True)
    name = models.CharField(max_length=150)
    codename = models.CharField(max_length=150)
    content_type = models.ForeignKey(ContentType)
    # true if this right can be used for object-level permissions
    valid_for_object_level = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("content_type", "codename"),)
        ordering = ("content_type__app_label", "content_type__model", "name",)
        verbose_name = "Global permission"

    @property
    def perm_name(self):
        return "{}.{}.{}".format(
            self.content_type.app_label,
            self.content_type.model,
            self.codename,
            )

    @staticmethod
    def get_permission(in_object, code_name):
        ct = ContentType.objects.get_for_model(in_object)
        cur_pk = in_object.pk
        return csw_object_permission.objects.create(
            csw_permission=csw_permission.objects.get(
                Q(content_type=ct) & Q(codename=code_name)
            ),
            object_pk=cur_pk,
        )

    @property
    def scope(self):
        return "G/O" if self.valid_for_object_level else "G"

    def __str__(self):
        return "{} | {} | {} | {}".format(
            self.content_type.app_label or "backbone",
            self.content_type.model,
            self.name,
            self.scope,
        )


class csw_object_permission(models.Model):
    """
    ClusterSoftware object permissions
    - local permissions
    - only allowed on the correct content_type
    """
    idx = models.AutoField(primary_key=True)
    csw_permission = models.ForeignKey(csw_permission)
    object_pk = models.IntegerField(default=0)

    def __str__(self):
        model_class = self.csw_permission.content_type.model_class()
        try:
            obj = model_class.objects.get(pk=self.object_pk)
        except model_class.DoesNotExist:
            obj = "deleted object (pk: {})".format(self.object_pk)
        return "{} on {}".format(str(self.csw_permission), str(obj))

    class Meta:
        verbose_name = "Object permission"


# permission intermediate models
class group_permission(models.Model):
    idx = models.AutoField(primary_key=True)
    group = models.ForeignKey("backbone.group")
    csw_permission = models.ForeignKey(csw_permission)
    level = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)


@receiver(signals.post_save, sender=group_permission)
def group_permission_save(sender, **kwargs):
    if not kwargs["raw"] and "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        GroupChanged.send(sender=_cur_inst, group=_cur_inst.group, cause="global_permission_create")


@receiver(signals.post_delete, sender=group_permission)
def group_permission_delete(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        GroupChanged.send(sender=_cur_inst, group=_cur_inst.group, cause="global_permission_delete")


class group_object_permission(models.Model):
    idx = models.AutoField(primary_key=True)
    group = models.ForeignKey("backbone.group")
    csw_object_permission = models.ForeignKey(csw_object_permission)
    level = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)


@receiver(signals.post_save, sender=group_object_permission)
def group_object_permission_save(sender, **kwargs):
    if not kwargs["raw"] and "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        GroupChanged.send(sender=_cur_inst, group=_cur_inst.group, cause="object_permission_create")


@receiver(signals.post_delete, sender=group_object_permission)
def group_object_permission_delete(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        GroupChanged.send(sender=_cur_inst, group=_cur_inst.group, cause="object_permission_delete")


class user_permission(models.Model):
    idx = models.AutoField(primary_key=True)
    user = models.ForeignKey("backbone.user")
    csw_permission = models.ForeignKey(csw_permission)
    level = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Global permissions of users"

    def __str__(self):
        return "Permission {} for user {}".format(
            str(self.csw_permission),
            str(self.user),
        )


@receiver(signals.post_save, sender=user_permission)
def user_permission_save(sender, **kwargs):
    if not kwargs["raw"] and "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        UserChanged.send(sender=_cur_inst, user=_cur_inst.user, cause="global_permission_create")


@receiver(signals.post_delete, sender=user_permission)
def user_permission_delete(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        UserChanged.send(sender=_cur_inst, user=_cur_inst.user, cause="global_permission_delete")


class RolePermission(models.Model):
    idx = models.AutoField(primary_key=True)
    role = models.ForeignKey("backbone.role")
    csw_permission = models.ForeignKey(csw_permission)
    level = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Global permissions of Role"

    def __str__(self):
        return "Permission {} for role {}".format(
            str(self.csw_permission),
            str(self.role),
        )


@receiver(signals.post_save, sender=RolePermission)
def RolePermission_save(sender, **kwargs):
    if not kwargs["raw"] and "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        RoleChanged.send(sender=_cur_inst, role=_cur_inst.role, cause="global_permission_create")


@receiver(signals.post_delete, sender=user_permission)
def RolePermission_delete(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        RoleChanged.send(sender=_cur_inst, role=_cur_inst.role, cause="global_permission_delete")


class RoleObjectPermission(models.Model):
    idx = models.AutoField(primary_key=True)
    role = models.ForeignKey("backbone.role")
    csw_object_permission = models.ForeignKey(csw_object_permission)
    level = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Global Object permissions of Role"

    def __str__(self):
        return "Object permission {} for role {}".format(
            str(self.csw_object_permission),
            str(self.role),
        )


@receiver(signals.post_save, sender=RoleObjectPermission)
def RoleObjectPermission_save(sender, **kwargs):
    if not kwargs["raw"] and "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        RoleChanged.send(sender=_cur_inst, role=_cur_inst.role, cause="object_permission_create")


@receiver(signals.post_delete, sender=user_permission)
def RoleObjectPermission_delete(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        RoleChanged.send(sender=_cur_inst, role=_cur_inst.role, cause="object_permission_delete")


class user_object_permission(models.Model):
    idx = models.AutoField(primary_key=True)
    user = models.ForeignKey("backbone.user")
    csw_object_permission = models.ForeignKey(csw_object_permission)
    level = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return "Permission {} for user {}".format(
            str(self.csw_object_permission),
            str(self.user),
        )

    class Meta:
        verbose_name = "Object permissions of users"


@receiver(signals.post_save, sender=user_object_permission)
def user_object_permission_save(sender, **kwargs):
    if not kwargs["raw"] and "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        UserChanged.send(sender=_cur_inst, user=_cur_inst.user, cause="object_permission_create")


@receiver(signals.post_delete, sender=user_object_permission)
def user_object_permission_delete(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        UserChanged.send(sender=_cur_inst, user=_cur_inst.user, cause="object_permission_delete")


def get_label_codename(perm):
    app_label, codename = (None, None)
    if isinstance(perm, str):
        if perm.count(".") == 2:
            app_label, content_name, codename = perm.split(".")
        elif perm.count(".") == 1:
            raise ImproperlyConfigured("old permission format '{}'".format(perm))
        else:
            raise ImproperlyConfigured("Unknown permission format '{}'".format(perm))
    elif isinstance(perm, csw_permission):
        app_label, content_name, codename = (
            perm.content_type.app_label,
            perm.content_type.model_class().__name__,
            perm.codename
        )
    elif isinstance(perm, csw_object_permission):
        app_label, content_name, codename = (
            perm.csw_permission.content_type.app_label,
            perm.csw_permission.content_type.model_class().__name__,
            perm.csw_permission.codename
        )
    else:
        raise ImproperlyConfigured("Unknown perm '{}'".format(str(perm)))
    return (app_label, content_name, codename)


def check_app_permission(auth_obj, app_label):
    if auth_obj.perms.filter(Q(content_type__app_label=app_label)).count():
        return True
    elif auth_obj.object_perms.filter(Q(csw_permission__content_type__app_label=app_label)).count():
        return True
    else:
        return False


def check_content_permission(auth_obj, app_label, content_name):
    def name_found(content_type_objects):
        names = [
            force_text(i.model_class()._meta.verbose_name) for i in content_type_objects
        ]
        return content_name in names

    objects = auth_obj.perms.filter(content_type__app_label=app_label)
    content_types = [i.content_type for i in objects]

    objects_csw = auth_obj.object_perms.filter(
        csw_permission__content_type__app_label=app_label
    )
    content_types_csw = [i.csw_permission.content_type for i in objects_csw]

    if objects and name_found(content_types):
        return True
    elif objects_csw and name_found(content_types_csw):
        return True
    else:
        # check for valid app_label / content_name
        objects = csw_permission.objects.filter(content_type__app_label=app_label)
        content_types = [i.content_type for i in objects]
        if objects and name_found(content_types):
            return False
        else:
            raise ImproperlyConfigured("unknown app_label / content_name combination '{}.{}".format(app_label, content_name))


def check_permission(auth_obj, perm):
    if not hasattr(auth_obj, "_auth_cache"):
        auth_obj._auth_cache = icswAuthCache(auth_obj)
    app_label, content_name, codename = get_label_codename(perm)
    if app_label and content_name and codename:
        # caching code
        return auth_obj._auth_cache.has_global_permission(app_label, content_name, codename)
    else:
        return False


def check_object_permission(auth_obj, perm, obj):
    if not hasattr(auth_obj, "_auth_cache"):
        auth_obj._auth_cache = icswAuthCache(auth_obj)
    app_label, content_name, code_name = get_label_codename(perm)
    # print "* cop", auth_obj, perm, obj, app_label, codename
    if app_label and content_name and code_name:
        if obj is None:
            # caching code
            return auth_obj._auth_cache.has_object_permission(app_label, content_name, code_name)
        else:
            if app_label == obj._meta.app_label:
                # caching code
                return auth_obj._auth_cache.has_object_permission(app_label, content_name, code_name, obj)
            else:
                return False
    else:
        return False


def get_object_permission_level(auth_obj, perm, obj):
    if not hasattr(auth_obj, "_auth_cache"):
        auth_obj._auth_cache = icswAuthCache(auth_obj)
    app_label, content_name, code_name = get_label_codename(perm)
    # print "* cop", auth_obj, perm, obj, app_label, codename
    if app_label and content_name and code_name:
        if obj is None:
            # caching code
            return auth_obj._auth_cache.get_object_permission_level(app_label, content_name, code_name)
        else:
            if app_label == obj._meta.app_label:
                # caching code
                return auth_obj._auth_cache.get_object_permission_level(app_label, content_name, code_name, obj)
            else:
                return -1
    else:
        return -1


def get_object_access_levels(auth_obj, obj, is_superuser=False):
    if not hasattr(auth_obj, "_auth_cache"):
        auth_obj._auth_cache = icswAuthCache(auth_obj)
    return auth_obj._auth_cache.get_object_access_levels(obj, is_superuser)


def get_all_object_perms(auth_obj, obj):
    # return all allowed permissions for a given object
    if not hasattr(auth_obj, "_auth_cache"):
        auth_obj._auth_cache = icswAuthCache(auth_obj)
    return auth_obj._auth_cache.get_all_object_perms(obj)


def get_allowed_object_list(auth_obj, perm):
    # return all allowed objects for a given permissions
    if not hasattr(auth_obj, "_auth_cache"):
        auth_obj._auth_cache = icswAuthCache(auth_obj)
    app_label, content_name, code_name = get_label_codename(perm)
    return auth_obj._auth_cache.get_allowed_object_list(app_label, content_name, code_name)


def get_allowed_object_list_model(auth_obj, content_type):
    # return all allowed objects for all local permissions
    if not hasattr(auth_obj, "_auth_cache"):
        auth_obj._auth_cache = icswAuthCache(auth_obj)
    # add dummy codename
    app_label, content_name, code_name = get_label_codename("{}.*".format(content_type))
    return auth_obj._auth_cache.get_allowed_object_list_model(app_label, content_name)


def get_global_permissions(auth_obj):
    # return all global permissions with levels (as dict)
    if not hasattr(auth_obj, "_auth_cache"):
        auth_obj._auth_cache = icswAuthCache(auth_obj)
    return auth_obj._auth_cache.get_global_permissions()


class user_manager(models.Manager):
    def get_by_natural_key(self, login):
        return super(user_manager, self).get(Q(login=login))

    def get_do_not_use(self, *args, **kwargs):
        # could be used to avoid loading from database, not used right now because of problems
        # with serialization (cost is too high)
        if args and type(args[0]) == Q:
            _q = args[0].children
            if len(_q) == 1 and len(_q[0]) == 2:
                if _q[0][0] == "pdk":
                    _val = _q[0][1]
                    # get from memcached
                    _mc_key = "icsw_user_pk_{:d}".format(int(_val))
                    _mc_content = cache.get(_mc_key)
                    if _mc_content:
                        for _obj in django.core.serializers.deserialize("json", _mc_content):
                            # the query will still be logged but not executed
                            return _obj.object
        _user = super(user_manager, self).get(*args, **kwargs)
        # store in memcached
        cache.set(_user.mc_key(), django.core.serializers.serialize("json", [_user]))
        return _user

    def ensure_default_variables(self, user_obj):
        for _var_name, _var_value in [
            ("$$ICSW_THEME_SELECTION$$", "default"),
            ("$$ICSW_MENU_LAYOUT_SELECTION$$", "normal"),
        ]:
            try:
                cur_var = user_obj.user_variable_set.get(Q(name=_var_name))
            except user_variable.DoesNotExist:
                user_variable.create_system_variable(user_obj, _var_name, _var_value)

    def cleanup_before_login(self, user_obj):
        # cleans user vars no longer needed
        user_obj.user_variable_set.filter(
            Q(name__startswith="$$saved_selection_") &
            Q(date__lte=timezone.now() - datetime.timedelta(days=1))
        ).delete()

    def create_superuser(self, login, email, password):
        if not password:
            if "ICSW_DJANGO_SUPERUSER_PASSWORD" in os.environ:
                # hack for setup_cluster.py
                password = os.environ["ICSW_DJANGO_SUPERUSER_PASSWORD"]
        try:
            new_admin = user.objects.get(Q(login=login))
        except user.DoesNotExist:
            # create group
            _grpname = "{}grp".format(login)
            try:
                user_group = group.objects.get(Q(groupname=_grpname))
            except group.DoesNotExist:
                user_group = group.objects.create(
                    groupname=_grpname,
                    gid=max(list(group.objects.all().values_list("gid", flat=True)) + [665]) + 1,
                    group_comment="auto created group for admin {}".format(login),
                    homestart="/",
                )
            new_admin = self.create(
                login=login,
                email=email,
                uid=max(list(user.objects.all().values_list("uid", flat=True)) + [665]) + 1,
                group=user_group,
                comment="admin created by createsuperuser",
                password=password,
                is_superuser=True
            )
        else:
            # overwrite password
            if "ICSW_DJANGO_SUPERUSER_PASSWORD" in os.environ:
                # hack for setup_cluster.py
                password = os.environ["ICSW_DJANGO_SUPERUSER_PASSWORD"]
                new_admin.password = password
                new_admin.save()
        return new_admin


class user(models.Model):
    objects = user_manager()
    USERNAME_FIELD = "login"
    REQUIRED_FIELDS = ["email", ]
    idx = models.AutoField(db_column="user_idx", primary_key=True)
    active = models.BooleanField(default=True)
    login = models.CharField(unique=True, max_length=255)
    uid = models.IntegerField(unique=True)
    group = models.ForeignKey("group")
    aliases = models.TextField(blank=True, null=True, default="")
    export = models.ForeignKey("device_config", null=True, related_name="export", blank=True)
    home = models.CharField(default="", blank=True, max_length=128)
    shell = models.CharField(max_length=765, blank=True, default="/bin/bash")
    # SHA encrypted
    password = models.CharField(max_length=128, blank=True)
    password_ssha = models.CharField(max_length=128, blank=True, default="")
    # nt and lm hashes of passwords
    nt_password = models.CharField(max_length=255, blank=True, default="")
    lm_password = models.CharField(max_length=255, blank=True, default="")
    # cluster_contact = models.BooleanField()
    first_name = models.CharField(max_length=765, blank=True, default="")
    last_name = models.CharField(max_length=765, blank=True, default="")
    title = models.CharField(max_length=765, blank=True, default="")
    email = models.CharField(max_length=765, blank=True, default="")
    pager = models.CharField(max_length=765, blank=True, default="", verbose_name="mobile")
    tel = models.CharField(max_length=765, blank=True, default="")
    comment = models.CharField(max_length=765, blank=True, default="")
    date = models.DateTimeField(auto_now_add=True)
    allowed_device_groups = models.ManyToManyField("device_group", blank=True)
    home_dir_created = models.BooleanField(default=False)
    secondary_groups = models.ManyToManyField("group", related_name="secondary", blank=True)
    last_login = models.DateTimeField(null=True)
    # login count (ok)
    login_count = models.IntegerField(default=0)
    # login count (failed)
    login_fail_count = models.IntegerField(default=0)
    # old model
    perms = models.ManyToManyField(csw_permission, related_name="db_user_perms", blank=True, through=user_permission)
    object_perms = models.ManyToManyField(csw_object_permission, related_name="db_user_perms", blank=True, through=user_object_permission)
    # new model, roles
    roles = models.ManyToManyField("backbone.role", blank=True, related_name="role_users")
    is_superuser = models.BooleanField(default=False)
    db_is_auth_for_password = models.BooleanField(default=False)
    only_webfrontend = models.BooleanField(default=False)
    # create rms user ?
    create_rms_user = models.BooleanField(default=False)
    # rms user created ?
    rms_user_created = models.BooleanField(default=False)
    # scan files in home dir ?
    scan_user_home = models.BooleanField(default=False)
    # scan depth
    scan_depth = models.IntegerField(default=2)

    @property
    def is_anonymous(self):
        return False

    def mc_key(self):
        if self.pk:
            return "icsw_user_pk_{:d}".format(self.pk)
        else:
            return "icsw_user_pk_none"

    def __setattr__(self, key, value):
        # catch clearing of export entry via empty ("" or '') key
        if key == "export" and isinstance(value, str):
            value = None
        super(user, self).__setattr__(key, value)

    # @property
    def is_authenticated(self):
        return True

    def has_perms(self, perms):
        # check if user has all of the perms
        return all([self.has_perm(perm) for perm in perms])

    def has_any_perms(self, perms):
        # check if user has any of the perms
        return any([self.has_perm(perm) for perm in perms])

    def has_perm(self, perm, ask_parent=True):
        # only check global permissions
        if not (self.active and self.group.active):
            return False
        elif self.is_superuser:
            return True
        res = check_permission(self, perm)
        if not res and ask_parent:
            res = check_permission(self.group, perm)
        return res

    @property
    def is_staff(self):
        return self.is_superuser

    @property
    def id(self):
        return self.pk

    def has_object_perm(self, perm, obj=None, ask_parent=True):
        if not (self.active and self.group.active):
            return False
        elif self.is_superuser:
            return True
        res = check_object_permission(self, perm, obj)
        if not res and ask_parent:
            res = check_object_permission(self.group, perm, obj)
        return res

    def get_object_perm_level(self, perm, obj=None, ask_parent=True):
        # returns -1 if no level is given
        if not (self.active and self.group.active):
            return -1
        elif self.is_superuser:
            return AC_FULL
        res = get_object_permission_level(self, perm, obj)
        if res == -1 and ask_parent:
            res = get_object_permission_level(self.group, perm, obj)
        return res

    def get_object_access_levels(self, obj):
        # always as parent
        if not (self.active and self.group.active):
            return {}
        elif self.is_superuser:
            return get_object_access_levels(self, obj, is_superuser=True)
        else:
            acc_dict = get_object_access_levels(self.group, obj)
            acc_dict.update(get_object_access_levels(self, obj))
            return acc_dict

    def get_all_object_perms(self, obj, ask_parent=True):
        # return all permissions we have for a given object
        if not (self.active and self.group.active):
            r_val = {}
        else:
            r_val = get_all_object_perms(self, obj)
            if ask_parent:
                for key, value in get_all_object_perms(self.group, obj).items():
                    r_val[key] = max(value, r_val.get(key, 0))
        return r_val

    def get_allowed_object_list_model(self, content_type, ask_parent=True):
        # get all object pks we have any permission for
        if ask_parent:
            return get_allowed_object_list_model(self, content_type) | get_allowed_object_list_model(self.group, content_type)
        else:
            return get_allowed_object_list_model(self, content_type)

    def get_allowed_object_list(self, perm, ask_parent=True):
        # get all object pks we have an object permission for
        if ask_parent:
            return get_allowed_object_list(self, perm) | get_allowed_object_list(self.group, perm)
        else:
            return get_allowed_object_list(self, perm)

    def has_object_perms(self, perms, obj=None, ask_parent=True):
        # check if user has all of the object perms
        return all([self.has_object_perm(perm, obj, ask_parent=ask_parent) for perm in perms])

    def has_any_object_perms(self, perms, obj=None, ask_parent=True):
        # check if user has any of the object perms
        return any([self.has_object_perm(perm, obj, ask_parent=ask_parent) for perm in perms])

    def get_global_permissions(self):
        if not (self.active and self.group.active):
            return {}
        group_perms = get_global_permissions(self.group)
        group_perms.update(get_global_permissions(self))
        return group_perms

    def has_content_perms(self, module_name, content_name, ask_parent=True):
        if not (self.active and self.group.active):
            return False
        elif self.is_superuser:
            return True
        res = check_content_permission(self, module_name, content_name)
        if not res and ask_parent:
            res = self.group.has_content_perms(module_name, content_name)
        return res

    def has_module_perms(self, module_name, ask_parent=True):
        if not (self.active and self.group.active):
            return False
        elif self.is_superuser:
            return True
        res = check_app_permission(self, module_name)
        if not res and ask_parent:
            res = self.group.has_module_perms(module_name)
        return res

    def get_is_active(self):
        return self.active

    is_active = property(get_is_active)

    class ICSW_Meta:
        permissions = (
            ("admin", "Administrator", True),
            ("server_control", "start and stop server processes", True),
            ("modify_tree", "modify device tree", False),
            ("modify_domain_name_tree", "modify domain name tree", False),
            ("modify_category_tree", "modify category tree", False),
            ("rms_operator", "change RMS settings", True),
            ("snapshots", "Show database history (snapshots)", False),
            ("rms_show", "Show RMS info", False),
            ("license_liveview", "Show LiveView of Licenses", False),
        )
        # foreign keys to ignore
        fk_ignore_list = [
            "user_variable", "user_permission", "user_object_permission", "login_history", "user_quota_setting",
            "virtual_desktop_user_setting", "user_scan_run",

        ]

    class Meta:
        db_table = 'user'
        ordering = ("login", "group__groupname")
        verbose_name = "User"

    def get_info(self):
        return str(self)

    def __str__(self):
        _add_fields = [
            _entry for _entry in [
                str(self.first_name) or "",
                str(self.last_name) or "",
                "[{}]".format(
                    "{:d}".format(self.pk) if isinstance(self.pk, int) else "???"
                ),
            ] if _entry
        ]
        return "{}{}".format(
            self.login,
            " ({})".format(
                " ".join(_add_fields)
            ) if _add_fields else "",
        )


@receiver(signals.m2m_changed, sender=user.perms.through)
def user_perms_changed(sender, *args, **kwargs):
    if kwargs.get("action") == "pre_add" and "instance" in kwargs:
        cur_user = None
        try:
            # hack to get the current logged in user
            for frame_record in inspect.stack():
                if frame_record[3] == "get_response":
                    request = frame_record[0].f_locals["request"]
                    cur_user = request.user
        except:
            cur_user = None
        if cur_user:
            is_admin = cur_user.has_perm("backbone.admin")
            for add_pk in kwargs.get("pk_set"):
                # only admins can grant admin or group_admin rights
                if csw_permission.objects.get(Q(pk=add_pk)).codename in ["admin", "group_admin"] and not is_admin:
                    raise ValidationError("not enough rights")


@receiver(signals.pre_save, sender=user)
def user_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        check_integer(cur_inst, "uid", min_val=100, max_val=2147483647)
        check_empty_string(cur_inst, "login", strip=True)
        check_empty_string(cur_inst, "password")
        if not cur_inst.home:
            cur_inst.home = cur_inst.login
        check_empty_string(cur_inst, "home", strip=True)
        if cur_inst.aliases is None:
            cur_inst.aliases = ""
        elif cur_inst.aliases in ["None"]:
            cur_inst.aliases = ""
        cur_pw = cur_inst.password
        if cur_pw.count(":"):
            cur_method, passwd = cur_pw.split(":", 1)
        else:
            cur_method, passwd = ("", cur_pw)
        if cur_method in ["SHA1", "CRYPT"]:
            # known hash, pass
            pass
        else:
            import passlib.hash
            cur_inst.lm_password = passlib.hash.lmhash.encrypt(passwd).upper()
            cur_inst.nt_password = passlib.hash.nthash.encrypt(passwd).upper()
            pw_gen_1 = config_store.ConfigStore(GEN_CS_NAME, quiet=True)["password.hash.function"]
            if pw_gen_1 == "CRYPT":
                salt = "".join(random.choice(string.ascii_uppercase + string.digits) for _x in range(4))
                cur_pw = "{}:{}".format(pw_gen_1, crypt.crypt(passwd, salt).decode("utf-8"))
                cur_inst.password = cur_pw
                cur_inst.password_ssha = ""
            else:
                salt = os.urandom(4)
                new_sh = hashlib.new(pw_gen_1)
                new_sh.update(passwd.encode("utf-8"))
                cur_pw = "{}:{}".format(pw_gen_1, base64.b64encode(new_sh.digest()).decode("utf-8"))
                cur_inst.password = cur_pw
                # ssha1
                new_sh.update(salt)
                # print base64.b64encode(new_sh.digest() +  salt)
                cur_inst.password_ssha = "{}:{}".format("SSHA", base64.b64encode(new_sh.digest() + salt).decode("utf-8"))


@receiver(signals.post_save, sender=user)
def user_post_save(sender, **kwargs):
    if not kwargs["raw"] and "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        UserChanged.send(sender=_cur_inst, user=_cur_inst, cause="save")


@receiver(signals.post_delete, sender=user)
def user_post_delete(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        UserChanged.send(sender=_cur_inst, user=_cur_inst, cause="delete")


class group(models.Model):
    idx = models.AutoField(db_column="ggroup_idx", primary_key=True)
    active = models.BooleanField(default=True)
    groupname = models.CharField(db_column="ggroupname", unique=True, max_length=48, blank=False)
    gid = models.IntegerField(unique=True)
    homestart = models.TextField(blank=True)
    group_comment = models.CharField(max_length=765, blank=True)
    first_name = models.CharField(max_length=765, blank=True)
    last_name = models.CharField(max_length=765, blank=True)
    title = models.CharField(max_length=765, blank=True)
    email = models.CharField(max_length=765, blank=True, default="")
    pager = models.CharField(max_length=765, blank=True, default="", verbose_name="mobile")
    tel = models.CharField(max_length=765, blank=True, default="")
    comment = models.CharField(max_length=765, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    # not implemented right now in md-config-server
    allowed_device_groups = models.ManyToManyField("device_group", blank=True)
    # parent group
    parent_group = models.ForeignKey("self", null=True, blank=True)
    # old code
    perms = models.ManyToManyField(csw_permission, related_name="db_group_perms", blank=True, through=group_permission)
    object_perms = models.ManyToManyField(csw_object_permission, related_name="db_group_perms", blank=True, through=group_object_permission)
    # new model, roles
    roles = models.ManyToManyField("backbone.role", blank=True, related_name="role_groups")

    def has_perms(self, perms):
        # check if group has all of the perms
        return all([self.has_perm(perm) for perm in perms])

    def has_any_perms(self, perms):
        # check if group has any of the perms
        return any([self.has_perm(perm) for perm in perms])

    def has_perm(self, perm):
        if not self.active:
            return False
        return check_permission(self, perm)

    def has_object_perm(self, perm, obj=None, ask_parent=True):
        if not self.active:
            return False
        return check_object_permission(self, perm, obj)

    def has_object_perms(self, perms, obj=None, ask_parent=True):
        # check if group has all of the object perms
        return all([self.has_object_perm(perm, obj) for perm in perms])

    def has_any_object_perms(self, perms, obj=None, ask_parent=True):
        # check if group has any of the object perms
        return any([self.has_object_perm(perm, obj) for perm in perms])

    def get_allowed_object_list_model(self, content_type):
        # get all object pks we have any permission for
        return get_allowed_object_list_model(self, content_type)

    def get_allowed_object_list(self, perm):
        # get all object pks we have an object permission for
        return get_allowed_object_list(self, perm)

    def has_content_perms(self, module_name, content_name):
        if not (self.active):
            return False
        return check_content_permission(self, module_name, content_name)

    def has_module_perms(self, module_name):
        if not (self.active):
            return False
        return check_app_permission(self, module_name)

    def get_is_active(self):
        return self.active
    is_active = property(get_is_active)

    class ICSW_Meta:
        permissions = (
            ("group_admin", "Group administrator", True),
        )
        fk_ignore_list = ["group_quota_setting"]

    class Meta:
        db_table = 'ggroup'
        ordering = ("groupname",)
        verbose_name = "Group"

    def __str__(self):
        return "{} (gid={:d})".format(
            self.groupname,
            self.gid)


@receiver(signals.pre_save, sender=group)
def group_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        check_empty_string(cur_inst, "groupname")
        check_integer(cur_inst, "gid", min_val=100, max_val=2147483647)
        if cur_inst.homestart and not cur_inst.homestart.startswith("/"):
            raise ValidationError("homestart has to start with '/'")
        my_pk = cur_inst.pk
        if cur_inst.parent_group_id:
            # while true
            if cur_inst.parent_group_id == my_pk:
                raise ValidationError("cannot be own parentgroup")
            # check for ring dependency
            cur_parent = cur_inst.parent_group
            while cur_parent is not None:
                if cur_parent.pk == my_pk:
                    raise ValidationError("ring dependency detected in groups")
                cur_parent = cur_parent.parent_group


@receiver(signals.post_save, sender=group)
def group_post_save(sender, **kwargs):
    if not kwargs["raw"] and "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        GroupChanged.send(sender=_cur_inst, group=_cur_inst, cause="save")


@receiver(signals.post_delete, sender=group)
def group_post_delete(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        GroupChanged.send(sender=_cur_inst, group=_cur_inst, cause="delete")


@receiver(signals.m2m_changed, sender=group.perms.through)
def group_perms_changed(sender, *args, **kwargs):
    if kwargs.get("action") == "pre_add" and "instance" in kwargs:
        for add_pk in kwargs.get("pk_set"):
            if csw_permission.objects.get(Q(pk=add_pk)).codename in ["admin", "group_admin"]:
                raise ValidationError("right not allowed for group")


class user_device_login(models.Model):
    idx = models.AutoField(db_column="user_device_login_idx", primary_key=True)
    user = models.ForeignKey("backbone.user")
    device = models.ForeignKey("backbone.device")
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'user_device_login'


class login_history(models.Model):
    idx = models.AutoField(primary_key=True)
    user = models.ForeignKey("backbone.user")
    success = models.BooleanField(default=False)
    remote_addr = models.CharField(default="", max_length=128)
    remote_host = models.CharField(default="", max_length=128)
    http_user_agent = models.CharField(default="", max_length=256)
    date = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def login_attempt(_user, request, success):
        entry = login_history.objects.create(
            user=_user,
            success=success,
            remote_addr=request.META["REMOTE_ADDR"],
            remote_host=request.META.get("REMOTE_HOST", request.META["REMOTE_ADDR"]),
            http_user_agent=request.META["HTTP_USER_AGENT"],
        )
        return entry


class user_variable(models.Model):
    idx = models.AutoField(primary_key=True)
    user = models.ForeignKey("backbone.user")
    description = models.CharField(default="", blank=True, max_length=255)
    var_type = models.CharField(
        max_length=2,
        choices=[
            ("s", "string"),
            ("i", "integer"),
            ("b", "boolean"),
            ("j", "json-encoded"),
            ("n", "none"),
        ]
    )
    name = models.CharField(max_length=189)
    value = models.CharField(max_length=512, default="", blank=True)
    json_value = models.TextField(default="", blank=True)
    # can be edited
    editable = models.BooleanField(default=False)
    # is hidden
    hidden = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)

    def to_db_format(self):
        if self.json_value:
            self.var_type = "j"
        else:
            cur_val = self.value
            if isinstance(cur_val, str):
                self.var_type = "s"
            elif isinstance(cur_val, int):
                self.var_type = "i"
                self.value = "{:d}".format(self.value)
            elif isinstance(cur_val, bool):
                self.var_type = "b"
                self.value = "1" if cur_val else "0"
            elif cur_val is None:
                self.var_type = "n"
                self.value = "None"

    def from_db_format(self):
        if self.var_type == "b":
            if self.value.lower() in ["true", "t"]:
                self.value = True
            elif self.value.lower() in ["false", "f"]:
                self.value = False
            else:
                self.value = True if int(self.value) else False
        elif self.var_type == "i":
            self.value = int(self.value)
        elif self.var_type == "n":
            self.value = None

    @classmethod
    def create_system_variable(cls, user_obj, name, value):
        _new_var = user_variable(
            user=user_obj,
            name=name,
            description="System variable '{}'".format(name),
            value=value,
            editable=False,
            hidden=True,
        )
        _new_var.save()

    def __str__(self):
        return "UserVar {} type {}, {}, {}".format(
            self.name,
            self.var_type,
            "hidden" if self.hidden else "not hidden",
            "editable" if self.editable else "not editable",
        )

    class Meta:
        unique_together = [("name", "user"), ]


@receiver(signals.pre_save, sender=user_variable)
def user_variable_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        check_empty_string(cur_inst, "name")
        cur_inst.to_db_format()


@receiver(signals.post_init, sender=user_variable)
def user_variable_post_init(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        cur_inst.from_db_format()


@receiver(signals.post_save, sender=user_variable)
def user_variable_post_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        cur_inst.from_db_format()


class quota_setting(models.Model):
    idx = models.AutoField(primary_key=True)
    quota_capable_blockdevice = models.ForeignKey("backbone.quota_capable_blockdevice")
    date = models.DateTimeField(auto_now_add=True)
    # in Bytes
    bytes_used = models.BigIntegerField(default=0)
    bytes_soft = models.BigIntegerField(default=0)
    bytes_hard = models.BigIntegerField(default=0)
    # bytes_grace = models.CharField(max_length=128, default="")
    bytes_gracetime = models.IntegerField(default=0)
    bytes_soft_target = models.BigIntegerField(default=0)
    bytes_hard_target = models.BigIntegerField(default=0)
    # simple count
    files_used = models.BigIntegerField(default=0)
    files_soft = models.BigIntegerField(default=0)
    files_hard = models.BigIntegerField(default=0)
    # files_grace = models.CharField(max_length=128, default="")
    files_gracetime = models.IntegerField(default=0)
    files_soft_target = models.BigIntegerField(default=0)
    files_hard_target = models.BigIntegerField(default=0)
    # flags, 2 character field
    quota_flags = models.CharField(max_length=4, default="--")

    class Meta:
        abstract = True


class user_quota_setting(quota_setting):
    user = models.ForeignKey("backbone.user")


class group_quota_setting(quota_setting):
    group = models.ForeignKey("backbone.group")


class user_scan_run(models.Model):
    # user scan run, at most one scan run should be current
    idx = models.AutoField(primary_key=True)
    user = models.ForeignKey("backbone.user")
    date = models.DateTimeField(auto_now_add=True)
    # start with False, switch to True when this one becomes active
    current = models.BooleanField(default=False)
    running = models.BooleanField(default=False)
    # run_time in milliseconds
    run_time = models.IntegerField(default=0)
    # depth
    scan_depth = models.IntegerField(default=1)


class user_scan_result(models.Model):
    idx = models.AutoField(primary_key=True)
    user_scan_run = models.ForeignKey("backbone.user_scan_run")
    # parent dir (or empty if top level dir)
    parent_dir = models.ForeignKey("self", null=True)
    full_name = models.TextField(default="")
    # name of dir (relative to parent dir)
    name = models.CharField(max_length=384, default="")
    # size of current dir
    size = models.BigIntegerField(default=0)
    # size of current dir and all subdirs
    size_total = models.BigIntegerField(default=0)
    # number of files in directory
    num_files = models.BigIntegerField(default=0)
    num_dirs = models.BigIntegerField(default=0)
    # number of files in all directory starting from this one
    num_files_total = models.BigIntegerField(default=0)
    num_dirs_total = models.BigIntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("idx",)


class virtual_desktop_user_setting(models.Model):

    class State(object):
        # NOTE: keep in sync with code in user.cs
        DISABLED = 1
        STARTING = 2
        RUNNING = 3

        @classmethod
        def get_state_description(cls, state):
            return {
                1: "Disabled",
                2: "Starting",
                3: "Running",
            }.get(state, "Undefined")

    idx = models.AutoField(primary_key=True)
    virtual_desktop_protocol = models.ForeignKey("backbone.virtual_desktop_protocol")
    window_manager = models.ForeignKey("backbone.window_manager")
    screen_size = models.CharField(max_length=256)

    device = models.ForeignKey("backbone.device")
    user = models.ForeignKey("user")
    # 0 means autoselect
    port = models.IntegerField(default=0)
    # port actually used
    effective_port = models.IntegerField(default=0)

    # port set in settings
    websockify_port = models.IntegerField(default=0)
    # port actually used (different from one above if set to 0)
    websockify_effective_port = models.IntegerField(default=0)
    websockify_pid = models.IntegerField(default=0)
    websockify_process_name = models.CharField(max_length=256, default="", blank=True)

    # temporary password for vnc session
    password = models.CharField(max_length=256, default="", blank=True)

    # whether this session should be running
    # TODO: rename this as soon as we have a proper way of doing manual migrations
    # in the gui, this can be called "enabled"
    is_running = models.BooleanField(default=False)

    # data of running process
    pid = models.IntegerField(default=0)
    process_name = models.CharField(max_length=256, default="", blank=True)

    last_start_attempt = models.DateTimeField(default=datetime.datetime.fromtimestamp(0), blank=True)

    # set when this is about to be deleted
    # (this is necessary as only cluster-server may do it as soon as session is shut down)
    to_delete = models.BooleanField(default=False, blank=True)

    state = models.IntegerField(default=State.DISABLED)

    def __init__(self, *args, **kwargs):
        super(virtual_desktop_user_setting, self).__init__(*args, **kwargs)
        self._send_signals = True  # query this is handlers

    def save_without_signals(self):
        self._send_signals = False
        self.save()
        self._send_signals = True

    def get_vnc_obfuscated_password(self):
        return get_vnc_enc(self.password)

    def get_state_description(self):
        return self.State.get_state_description(self.state)

    def update_state(self, state):
        if self.state != state:
            self.state = state
            self.save_without_signals()


@receiver(signals.pre_save, sender=virtual_desktop_user_setting)
def virtual_desktop_user_setting_pre_save(sender, instance, raw, **kwargs):
    pass
    # if not raw:
    #     if LicenseLockListUser.objects.is_user_locked(LicenseEnum.virtual_desktop, instance.user):
    #        raise ValidationError(u"User {} is locked from accessing virtual desktops".format(unicode(instance.user)))


@receiver(signals.post_save, sender=virtual_desktop_user_setting)
def virtual_desktop_user_setting_post_save(sender, **kwargs):
    pass
    # if not kwargs["raw"] and "instance" in kwargs:
    #    _cur_inst = kwargs["instance"]
    #    if _cur_inst._send_signals:
    #        VirtualDesktopUserSettingChanged.send(sender=_cur_inst, vdus=_cur_inst, cause="vdus_save")

    #    # if _cur_inst.is_running and not _cur_inst.to_delete:
    #    #    LicenseUsage.log_usage(LicenseEnum.virtual_desktop, LicenseParameterTypeEnum.user, _cur_inst.user)


class virtual_desktop_protocol(models.Model):
    idx = models.AutoField(primary_key=True)
    # name of protocol to display to user
    name = models.CharField(max_length=256, unique=True)
    # binary to start protocol server
    binary = models.CharField(max_length=256, default="")
    # description of protocol for user
    description = models.TextField()
    # devices where this is available
    devices = models.ManyToManyField("backbone.device")
    date = models.DateTimeField(auto_now_add=True)


class window_manager(models.Model):
    idx = models.AutoField(primary_key=True)
    # name of window manager to display to user
    name = models.CharField(max_length=256, unique=True)
    # binary to start window manager
    binary = models.CharField(max_length=256, default="")
    # description of window manager for user
    description = models.TextField()
    # devices where this is available
    devices = models.ManyToManyField("backbone.device")
    date = models.DateTimeField(auto_now_add=True)


class UserLogEntry(models.Model):
    idx = models.AutoField(primary_key=True)
    user = models.ForeignKey("backbone.user")
    devices = models.ManyToManyField("backbone.device")
    sent_via_digest = models.BooleanField(default=False)
    viewed_via_webfrontend = models.BooleanField(default=False)
    level = models.ForeignKey("LogLevel")
    source = models.ForeignKey("LogSource")
    text = models.CharField(max_length=765, default="")
    date = models.DateTimeField(auto_now_add=True)


class Role(models.Model):
    idx = models.AutoField(primary_key=True)
    # active
    active = models.BooleanField(default=True)
    # creation user
    create_user = models.ForeignKey("backbone.user", null=True)
    # name
    name = models.CharField(max_length=64, default="", unique=True)
    # description
    description = models.TextField(default="", blank=True)
    # permissions
    perms = models.ManyToManyField(csw_permission, related_name="role_perms", blank=True, through=RolePermission)
    # object permissions
    object_perms = models.ManyToManyField(csw_object_permission, related_name="role_perms", blank=True, through=RoleObjectPermission)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ("name",)

    class ICSW_Meta:
        fk_ignore_list = [
            "RolePermission", "RoleObjectPermission",
        ]


@receiver(signals.post_save, sender=Role)
def Role_post_save(sender, **kwargs):
    if not kwargs["raw"] and "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        RoleChanged.send(sender=_cur_inst, role=_cur_inst, cause="save")


@receiver(signals.post_delete, sender=group)
def Role_post_delete(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        RoleChanged.send(sender=_cur_inst, role=_cur_inst, cause="delete")
