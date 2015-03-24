# -*- coding: utf-8 -*-
#
# Copyright (C) 2014-2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of cluster-backbone-sql
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
""" NOCTUA / CORUVS models, user part """

import base64
import crypt
import hashlib
import inspect
import os
import random
import string
import smbpasswd
import datetime

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.db import models
from django.apps import apps
from django.db.models import Q, signals
from django.dispatch import receiver
from initat.cluster.backbone.models.functions import _check_empty_string, _check_integer, \
    get_vnc_enc
from initat.cluster.backbone.signals import user_changed, group_changed, \
    virtual_desktop_user_setting_changed
import django.core.serializers


__all__ = [
    "csw_permission",
    "csw_object_permission",
    "user",
    "group",
    "user_device_login",
    "user_variable",
    "group_permission",
    "group_object_permission",
    "user_permission",
    "user_object_permission",
    "user_quota_setting",
    "group_quota_setting",
    "AC_MASK_READ", "AC_MASK_MODIFY",
    "AC_MASK_DELETE", "AC_MASK_CREATE",
    "AC_MASK_DICT",
    "user_scan_run",
    "user_scan_result",
    "virtual_desktop_protocol",
    "virtual_desktop_user_setting",
    "window_manager",
    "login_history",
]


def _csw_key(perm):
    return "{}.{}.{}".format(
        perm.content_type.app_label,
        perm.content_type.name,
        perm.codename,
    )


# auth_cache structure
class auth_cache(object):
    def __init__(self, auth_obj):
        self.auth_obj = auth_obj
        self.model_name = self.auth_obj._meta.model_name
        self.cache_key = u"auth_{}_{:d}".format(
            auth_obj._meta.object_name,
            auth_obj.pk,
            )
        self.__perms, self.__obj_perms = ({}, {})
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
        self.__perm_dict = {_csw_key(cur_perm): cur_perm for cur_perm in csw_permission.objects.all().select_related("content_type")}
        # pprint.pprint(self.__perm_dict)
        # print self.__perm_dict.keys()
        if self.has_all_perms:
            # set all perms
            for perm in csw_permission.objects.all().select_related("content_type"):
                self.__perms[_csw_key(perm)] = AC_FULL
        else:
            for perm in getattr(self.auth_obj, "{}_permission_set".format(self.model_name)).select_related("csw_permission__content_type"):
                self.__perms[_csw_key(perm.csw_permission)] = perm.level
        for perm in getattr(
            self.auth_obj,
            "{}_object_permission_set".format(
                self.model_name
            )
        ).select_related("csw_object_permission__csw_permission__content_type"):
            self.__obj_perms.setdefault(_csw_key(perm.csw_object_permission.csw_permission), {})[perm.csw_object_permission.object_pk] = perm.level
        # pprint.pprint(self.__perms)
        # pprint.pprint(self.__obj_perms)

    def _get_code_key(self, app_label, content_name, code_name):
        code_key = "{}.{}.{}".format(app_label, content_name, code_name)
        if code_key not in self.__perm_dict:
            raise ImproperlyConfigured("wrong permission name {}".format(code_key))
        return code_key

    def has_permission(self, app_label, content_name, code_name):
        code_key = self._get_code_key(app_label, content_name, code_name)
        return code_key in self.__perms

    def get_object_permission_level(self, app_label, content_name, code_name, obj=None):
        code_key = self._get_code_key(app_label, content_name, code_name)
        _level = self.__perms.get(code_key, -1)
        if obj is not None:
            if code_key in self.__obj_perms:
                _level = self.__obj_perms[code_key].get(obj.pk, _level)
        return _level

    def has_object_permission(self, app_label, content_name, code_name, obj=None):
        code_key = self._get_code_key(app_label, content_name, code_name)
        if self.has_permission(app_label, content_name, code_name):
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
        if self.has_permission(app_label, content_name, code_name) or getattr(self.auth_obj, "is_superuser", False):
            # at fist check global permission, return all devices
            return set(apps.get_model(app_label, self.__perm_dict[code_key].content_type.name).objects.all().values_list("pk", flat=True))
        elif code_key in self.__obj_perms:
            # only return devices where the code_key is set
            return set(self.__obj_perms[code_key].keys())
        else:
            return set()

    def get_all_object_perms(self, obj):
        if obj:
            obj_ct = ContentType.objects.get_for_model(obj)
            # which permissions are valid for this object ?
            obj_perms = set([key for key, value in self.__perm_dict.iteritems() if value.content_type == obj_ct])
        else:
            # copy
            obj_perms = set(self.__perm_dict.keys())
        if self.has_all_perms:
            # return all permissions
            return {key: AC_FULL for key in obj_perms}
        else:
            # which permissions are globaly set ?
            global_perms = {key: value for key, value in self.__perms.iteritems() if key in obj_perms}
            # obj_perms = {key: self.__perms[key] for key in obj_perms.iterkeys()}
            if obj:
                # local permissions
                local_perms = {key: max(obj_list.values()) for key, obj_list in self.__obj_perms.iteritems() if key in obj_perms and obj.pk in obj_list}
            else:
                local_perms = {key: max(obj_list.values()) for key, obj_list in self.__obj_perms.iteritems() if key in obj_perms}
            # merge to result permissions
            result_perms = {key: max(global_perms.get(key, -1), local_perms.get(key, -1)) for key in set(global_perms.keys()) | set(local_perms.keys())}
            # only use values with at least level 0
            result_perms = {_key: _value for _key, _value in result_perms.iteritems() if _value >= 0}
            return result_perms

    def get_object_access_levels(self, obj, is_superuser):
        obj_type = obj._meta.model_name
        # returns a dict with all access levels for the given object
        obj_perms = [key for key, value in self.__perm_dict.iteritems() if value.content_type.name == obj_type]
        if is_superuser:
            ac_dict = {key: AC_FULL for key in obj_perms}
        else:
            ac_dict = {key: self.__obj_perms.get(key, {}).get(obj.pk, self.__perms.get(key, -1)) for key in obj_perms}
            # filter values
            ac_dict = {key: value for key, value in ac_dict.iteritems() if value >= 0}
            if obj_type == "device":
                # for devices we assume that the minimum access level is 0 (pre-filtered by the access_to_devicegroup feature)
                self._fill_dg_lut(obj)
                # get permissions dict for meta device
                meta_dict = {key: self.__obj_perms.get(key, {}).get(self.__dg_lut[obj.pk], self.__perms.get(key, -1)) for key in obj_perms}
                # copy to device permdict
                for key, value in meta_dict.iteritems():
                    # only use values with at least level 0
                    if value >= 0 or key in ac_dict:
                        ac_dict[key] = max(ac_dict.get(key, 0), value)
        return ac_dict

    def _fill_dg_lut(self, dev):
        if dev.pk not in self.__dg_lut:
            for dev_pk, md_pk in dev._default_manager.filter(Q(device_group=dev.device_group_id)).values_list("pk", "device_group__device"):
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

    class Meta:
        unique_together = (("content_type", "codename"),)
        ordering = ("content_type__app_label", "content_type__name", "name",)
        app_label = "backbone"
        verbose_name = "Global permission"

    @staticmethod
    def get_permission(in_object, code_name):
        ct = ContentType.objects.get_for_model(in_object)
        cur_pk = in_object.pk
        return csw_object_permission.objects.create(
            csw_permission=csw_permission.objects.get(Q(content_type=ct) & Q(codename=code_name)),
            object_pk=cur_pk
            )

    def __unicode__(self):
        return u"{} | {} | {} | {}".format(
            self.content_type.app_label,
            self.content_type,
            self.name,
            "G/O" if self.valid_for_object_level else "G",
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

    def __unicode__(self):
        obj = self.csw_permission.content_type.model_class().objects.get(pk=self.object_pk)
        return "{} on {}".format(unicode(self.csw_permission), obj)

    class Meta:
        app_label = "backbone"
        verbose_name = "Object permission"


# permission intermediate models
class group_permission(models.Model):
    idx = models.AutoField(primary_key=True)
    group = models.ForeignKey("backbone.group")
    csw_permission = models.ForeignKey(csw_permission)
    level = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"


@receiver(signals.post_save, sender=group_permission)
def group_permission_save(sender, **kwargs):
    if not kwargs["raw"] and "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        group_changed.send(sender=_cur_inst, group=_cur_inst.group, cause="global_permission_create")


@receiver(signals.post_delete, sender=group_permission)
def group_permission_delete(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        group_changed.send(sender=_cur_inst, group=_cur_inst.group, cause="global_permission_delete")


class group_object_permission(models.Model):
    idx = models.AutoField(primary_key=True)
    group = models.ForeignKey("backbone.group")
    csw_object_permission = models.ForeignKey(csw_object_permission)
    level = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"


@receiver(signals.post_save, sender=group_object_permission)
def group_object_permission_save(sender, **kwargs):
    if not kwargs["raw"] and "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        group_changed.send(sender=_cur_inst, group=_cur_inst.group, cause="object_permission_create")


@receiver(signals.post_delete, sender=group_object_permission)
def group_object_permission_delete(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        group_changed.send(sender=_cur_inst, group=_cur_inst.group, cause="object_permission_delete")


class user_permission(models.Model):
    idx = models.AutoField(primary_key=True)
    user = models.ForeignKey("backbone.user")
    csw_permission = models.ForeignKey(csw_permission)
    level = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"
        verbose_name = "Global permissions of users"

    def __unicode__(self):
        return "Permission {} for user {}".format(self.csw_permission, self.user)


@receiver(signals.post_save, sender=user_permission)
def user_permission_save(sender, **kwargs):
    if not kwargs["raw"] and "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        user_changed.send(sender=_cur_inst, user=_cur_inst.user, cause="global_permission_create")


@receiver(signals.post_delete, sender=user_permission)
def user_permission_delete(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        user_changed.send(sender=_cur_inst, user=_cur_inst.user, cause="global_permission_delete")

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


class user_object_permission(models.Model):
    idx = models.AutoField(primary_key=True)
    user = models.ForeignKey("backbone.user")
    csw_object_permission = models.ForeignKey(csw_object_permission)
    level = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "Permission {} for user {}".format(self.csw_object_permission, self.user)

    class Meta:
        app_label = "backbone"
        verbose_name = "Object permissions of users"


@receiver(signals.post_save, sender=user_object_permission)
def user_object_permission_save(sender, **kwargs):
    if not kwargs["raw"] and "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        user_changed.send(sender=_cur_inst, user=_cur_inst.user, cause="object_permission_create")


@receiver(signals.post_delete, sender=user_object_permission)
def user_object_permission_delete(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        user_changed.send(sender=_cur_inst, user=_cur_inst.user, cause="object_permission_delete")


def get_label_codename(perm):
    app_label, codename = (None, None)
    if isinstance(perm, basestring):
        if perm.count(".") == 2:
            app_label, content_name, codename = perm.split(".")
        elif perm.count(".") == 1:
            raise ImproperlyConfigured("old permission format '{}'".format(perm))
        else:
            raise ImproperlyConfigured("Unknown permission format '{}'".format(perm))
    elif isinstance(perm, csw_permission):
        app_label, content_name, codename = (perm.content_type.app_label, perm.content_type.name, perm.codename)
    elif isinstance(perm, csw_object_permission):
        app_label, content_name, codename = (perm.csw_permission.content_type.app_label, perm.csw_permission.content_type.name, perm.csw_permission.codename)
    else:
        raise ImproperlyConfigured("Unknown perm '{}'".format(unicode(perm)))
    return (app_label, content_name, codename)


def check_app_permission(auth_obj, app_label):
    if auth_obj.perms.filter(Q(content_type__app_label=app_label)).count():
        return True
    elif auth_obj.object_perms.filter(Q(csw_permission__content_type__app_label=app_label)).count():
        return True
    else:
        return False


def check_content_permission(auth_obj, app_label, content_name):
    print "ccp", app_label, content_name
    if auth_obj.perms.filter(Q(content_type__app_label=app_label) & Q(content_type__name=content_name)).count():
        return True
    elif auth_obj.object_perms.filter(Q(csw_permission__content_type__app_label=app_label) & Q(csw_permission__content_type__name=content_name)).count():
        return True
    else:
        # check for valiid app_label / content_name
        if csw_permission.objects.filter(Q(content_type__app_label=app_label) & Q(content_type__name=content_name)).count():
            return False
        else:
            raise ImproperlyConfigured("unknown app_label / content_name combination '{}.{}".format(app_label, content_name))


def check_permission(auth_obj, perm):
    if not hasattr(auth_obj, "_auth_cache"):
        auth_obj._auth_cache = auth_cache(auth_obj)
    app_label, content_name, codename = get_label_codename(perm)
    if app_label and content_name and codename:
        # caching code
        return auth_obj._auth_cache.has_permission(app_label, content_name, codename)
    else:
        return False


def check_object_permission(auth_obj, perm, obj):
    if not hasattr(auth_obj, "_auth_cache"):
        auth_obj._auth_cache = auth_cache(auth_obj)
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
        auth_obj._auth_cache = auth_cache(auth_obj)
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
        auth_obj._auth_cache = auth_cache(auth_obj)
    return auth_obj._auth_cache.get_object_access_levels(obj, is_superuser)


def get_all_object_perms(auth_obj, obj):
    # return all allowed permissions for a given object
    if not hasattr(auth_obj, "_auth_cache"):
        auth_obj._auth_cache = auth_cache(auth_obj)
    return auth_obj._auth_cache.get_all_object_perms(obj)


def get_allowed_object_list(auth_obj, perm):
    # return all allowed objects for a given permissions
    if not hasattr(auth_obj, "_auth_cache"):
        auth_obj._auth_cache = auth_cache(auth_obj)
    app_label, content_name, code_name = get_label_codename(perm)
    return auth_obj._auth_cache.get_allowed_object_list(app_label, content_name, code_name)


def get_global_permissions(auth_obj):
    # return all global permissions with levels (as dict)
    if not hasattr(auth_obj, "_auth_cache"):
        auth_obj._auth_cache = auth_cache(auth_obj)
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

    def create_superuser(self, login, email, password):
        if not password:
            if "DJANGO_SUPERUSER_PASSWORD" in os.environ:
                # hack for setup_cluster.py
                password = os.environ["DJANGO_SUPERUSER_PASSWORD"]
        # create group
        user_group = group.objects.create(
            groupname="{}grp".format(login),
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
            is_superuser=True)
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
    # login count
    login_count = models.IntegerField(default=0)
    # deprecated
    permissions = models.ManyToManyField(csw_permission, related_name="db_user_permissions", blank=True)
    object_permissions = models.ManyToManyField(csw_object_permission, related_name="db_user_permissions", blank=True)
    # new model
    perms = models.ManyToManyField(csw_permission, related_name="db_user_perms", blank=True, through=user_permission)
    object_perms = models.ManyToManyField(csw_object_permission, related_name="db_user_perms", blank=True, through=user_object_permission)
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
        if key == "export" and isinstance(value, basestring):
            value = None
        super(user, self).__setattr__(key, value)

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
                for key, value in get_all_object_perms(self.group, obj).iteritems():
                    r_val[key] = max(value, r_val.get(key, 0))
        return r_val

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

    class CSW_Meta:
        permissions = (
            ("admin", "Administrator", True),
            ("server_control", "start and stop server processes", True),
            ("modify_tree", "modify device tree", False),
            ("modify_domain_name_tree", "modify domain name tree", False),
            ("modify_category_tree", "modify category tree", False),
            ("rms_operator", "change RMS settings", True),
        )
        # foreign keys to ignore
        fk_ignore_list = ["user_variable", "user_permission", "user_object_permission", "login_history", "user_quota_setting"]

    class Meta:
        db_table = u'user'
        ordering = ("login", "group__groupname")
        app_label = "backbone"
        verbose_name = "User"

    def get_info(self):
        return unicode(self)

    def __unicode__(self):
        _add_fields = [
            _entry for _entry in [
                self.first_name or "",
                self.last_name or "",
                "[{}]".format("{:d}".format(self.pk) if type(self.pk) in [int, long] else "???"),
            ] if _entry
        ]
        return u"{} ({})".format(
            self.login,
            " ".join(_add_fields),
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
        _check_integer(cur_inst, "uid", min_val=100, max_val=65535)
        _check_empty_string(cur_inst, "login", strip=True)
        _check_empty_string(cur_inst, "password")
        if not cur_inst.home:
            cur_inst.home = cur_inst.login
        _check_empty_string(cur_inst, "home", strip=True)
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
            cur_inst.lm_password = smbpasswd.lmhash(passwd)
            cur_inst.nt_password = smbpasswd.nthash(passwd)
            pw_gen_1 = settings.PASSWORD_HASH_FUNCTION
            if pw_gen_1 == "CRYPT":
                salt = "".join(random.choice(string.ascii_uppercase + string.digits) for _x in xrange(4))
                cur_pw = "{}:{}".format(pw_gen_1, crypt.crypt(passwd, salt))
                cur_inst.password = cur_pw
                cur_inst.password_ssha = ""
            else:
                salt = os.urandom(4)
                new_sh = hashlib.new(pw_gen_1)
                new_sh.update(passwd)
                cur_pw = "{}:{}".format(pw_gen_1, base64.b64encode(new_sh.digest()))
                cur_inst.password = cur_pw
                # ssha1
                new_sh.update(salt)
                # print base64.b64encode(new_sh.digest() +  salt)
                cur_inst.password_ssha = "{}:{}".format("SSHA", base64.b64encode(new_sh.digest() + salt))


@receiver(signals.post_save, sender=user)
def user_post_save(sender, **kwargs):
    if not kwargs["raw"] and "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        user_changed.send(sender=_cur_inst, user=_cur_inst, cause="save")


@receiver(signals.post_delete, sender=user)
def user_post_delete(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        user_changed.send(sender=_cur_inst, user=_cur_inst, cause="delete")


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
    # deprecated
    permissions = models.ManyToManyField(csw_permission, related_name="db_group_permissions", blank=True)
    object_permissions = models.ManyToManyField(csw_object_permission, related_name="db_group_permissions")
    # new model
    perms = models.ManyToManyField(csw_permission, related_name="db_group_perms", blank=True, through=group_permission)
    object_perms = models.ManyToManyField(csw_object_permission, related_name="db_group_perms", blank=True, through=group_object_permission)

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

    def get_allowed_object_list(self, perm, ask_parent=True):
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

    class CSW_Meta:
        permissions = (
            ("group_admin", "Group administrator", True),
        )
        fk_ignore_list = ["group_quota_setting"]

    class Meta:
        db_table = u'ggroup'
        ordering = ("groupname",)
        app_label = "backbone"
        verbose_name = u"Group"

    def __unicode__(self):
        return u"{} (gid={:d})".format(
            self.groupname,
            self.gid)


@receiver(signals.pre_save, sender=group)
def group_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_empty_string(cur_inst, "groupname")
        _check_integer(cur_inst, "gid", min_val=100, max_val=65535)
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
        group_changed.send(sender=_cur_inst, group=_cur_inst, cause="save")


@receiver(signals.post_delete, sender=group)
def group_post_delete(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        group_changed.send(sender=_cur_inst, group=_cur_inst, cause="delete")


@receiver(signals.m2m_changed, sender=group.perms.through)
def group_perms_changed(sender, *args, **kwargs):
    if kwargs.get("action") == "pre_add" and "instance" in kwargs:
        print "***", kwargs.get("pk_set")
        for add_pk in kwargs.get("pk_set"):
            if csw_permission.objects.get(Q(pk=add_pk)).codename in ["admin", "group_admin"]:
                raise ValidationError("right not allowed for group")


class user_device_login(models.Model):
    idx = models.AutoField(db_column="user_device_login_idx", primary_key=True)
    user = models.ForeignKey("backbone.user")
    device = models.ForeignKey("backbone.device")
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'user_device_login'
        app_label = "backbone"


class user_variable(models.Model):
    idx = models.AutoField(primary_key=True)
    user = models.ForeignKey("backbone.user")
    var_type = models.CharField(max_length=2, choices=[
        ("s", "string"),
        ("i", "integer"),
        ("b", "boolean"),
        ("n", "none")])
    name = models.CharField(max_length=189)
    value = models.CharField(max_length=512, default="")
    date = models.DateTimeField(auto_now_add=True)

    def to_db_format(self):
        cur_val = self.value
        if isinstance(cur_val, basestring):
            self.var_type = "s"
        elif type(cur_val) in [int, long]:
            self.var_type = "i"
            self.value = "{:d}".format(self.value)
        elif type(cur_val) in [bool]:
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

    class Meta:
        unique_together = [("name", "user"), ]
        app_label = "backbone"


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


@receiver(signals.pre_save, sender=user_variable)
def user_variable_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_empty_string(cur_inst, "name")
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

    class Meta:
        app_label = "backbone"


class group_quota_setting(quota_setting):
    group = models.ForeignKey("backbone.group")

    class Meta:
        app_label = "backbone"


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

    class Meta:
        app_label = "backbone"


class user_scan_result(models.Model):
    idx = models.AutoField(primary_key=True)
    user_scan_run = models.ForeignKey("backbone.user_scan_run")
    # parent dir (or empty if top level dir)
    parent_dir = models.ForeignKey("self", null=True)
    full_name = models.CharField(max_length=2048, default="")
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
        app_label = "backbone"
        ordering = ("idx",)


class virtual_desktop_user_setting(models.Model):

    class State(object):
        # NOTE: keep in sync with code in user.cs
        DISABLED = 1
        STARTING = 2
        RUNNING = 3

        @classmethod
        def get_state_description(cls, state):
            return {1: "Disabled", 2: "Starting", 3: "Running"}.get(state, "Undefined")

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

    # set when this is about to be deleted (this is necessary as only cluster-server may do it as soon as session is shut down)
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


@receiver(signals.post_save, sender=virtual_desktop_user_setting)
def virtual_desktop_user_setting_save(sender, **kwargs):
    if not kwargs["raw"] and "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        if _cur_inst._send_signals:
            virtual_desktop_user_setting_changed.send(sender=_cur_inst, vdus=_cur_inst, cause="vdus_save")


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

