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


class csw_object_permission(models.Model):
    """
    ClusterSoftware object permissions
    - local permissions
    - only allowed on the correct content_type
    """
    idx = models.AutoField(primary_key=True)
    csw_permission = models.ForeignKey(csw_permission)
    object_pk = models.IntegerField(default=0)

    class Meta:
        app_label = "backbone"


# permission intermediate models
class group_permission(models.Model):
    idx = models.AutoField(primary_key=True)
    group = models.ForeignKey("backbone.group")
    csw_permission = models.ForeignKey(csw_permission)
    level = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"


class group_object_permission(models.Model):
    idx = models.AutoField(primary_key=True)
    group = models.ForeignKey("backbone.group")
    csw_object_permission = models.ForeignKey(csw_object_permission)
    level = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"


class user_permission(models.Model):
    idx = models.AutoField(primary_key=True)
    user = models.ForeignKey("backbone.user")
    csw_permission = models.ForeignKey(csw_permission)
    level = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"


class user_object_permission(models.Model):
    idx = models.AutoField(primary_key=True)
    user = models.ForeignKey("backbone.user")
    csw_object_permission = models.ForeignKey(csw_object_permission)
    level = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"


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

    class Meta:
        db_table = u'user'
        ordering = ("login", "group__groupname")
        app_label = "backbone"


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

    class Meta:
        db_table = u'ggroup'
        ordering = ("groupname",)
        app_label = "backbone"


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
