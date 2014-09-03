# Copyright (C) 2001-2014 Andreas Lang-Nevyjel, init.at
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
# -*- coding: utf-8 -*-
#

from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.core.signals import request_finished, request_started
from django.db import models
from django.db.models import Q, signals
from django.dispatch import receiver
from django.utils.functional import memoize
from initat.cluster.backbone.middleware import thread_local_middleware, \
    _thread_local
from initat.cluster.backbone.models.functions import _check_empty_string, \
    _check_float, _check_integer, _check_non_empty_string, to_system_tz, \
    get_change_reset_list, get_related_models, cluster_timezone
from lxml import etree  # @UnresolvedImport
from lxml.builder import E  # @UnresolvedImport
import crypt
import datetime
import ipvx_tools
import json
import logging
import logging_tools
import marshal
import net_tools
import process_tools
import pytz
import random
import re
import server_command
import time
import uuid

from initat.cluster.backbone.models.domain import *  # @UnusedWildImport
from initat.cluster.backbone.models.monitoring import *  # @UnusedWildImport
from initat.cluster.backbone.models.network import *  # @UnusedWildImport
from initat.cluster.backbone.models.package import *  # @UnusedWildImport
from initat.cluster.backbone.models.user import *  # @UnusedWildImport
from initat.cluster.backbone.models.background import *  # @UnusedWildImport
from initat.cluster.backbone.models.hints import *  # @UnusedWildImport
from initat.cluster.backbone.models.rms import *  # @UnusedWildImport
from initat.cluster.backbone.signals import user_changed, group_changed, \
    bootsettings_changed


# do not use, problems with import
# from initat.cluster.backbone.models.partition import * # @UnusedWildImport

# attention: this list is used in create_fixtures.py
LICENSE_CAPS = [
    ("monitor", "Monitoring services", ["md-config"]),
    ("monext", "Extended monitoring services", ["md-config"]),
    ("boot", "boot/config facility for nodes", ["mother"]),
    ("package", "Package installation", ["package"]),
    ("rms", "Resource Management system", ["rms"]),
    ("docu", "show documentation", []),
]

ALL_LICENSES = [name for name, _descr, _srv in LICENSE_CAPS]


def get_license_descr(name):
    return [_descr for _name, _descr, _srv in LICENSE_CAPS if name == _name][0]

ALLOWED_CFS = ["MAX", "MIN", "AVERAGE"]

logger = logging.getLogger(__name__)


class cs_timer(object):
    def __init__(self):
        self.start_time = time.time()

    def __call__(self, what):
        cur_time = time.time()
        log_str = "{} in {}".format(
            what,
            logging_tools.get_diff_time_str(cur_time - self.start_time)
        )
        self.start_time = cur_time
        return log_str

# cluster_log_source
cluster_log_source = None


@receiver(request_started)
def bg_req_started(*args, **kwargs):
    # init number of background jobs created
    _thread_local.num_bg_jobs = 0


@receiver(request_finished)
def bg_req_finished(*args, **kwargs):
    # check number of background jobs and signal localhost
    if getattr(_thread_local, "num_bg_jobs", 0):
        _thread_local.num_bg_jobs = 0
        _signal_localhost()


@receiver(user_changed)
def user_changed(*args, **kwargs):
    _insert_bg_job("sync_users", kwargs["cause"], kwargs["user"])


@receiver(group_changed)
def group_changed(*args, **kwargs):
    _insert_bg_job("sync_users", kwargs["cause"], kwargs["group"])


@receiver(bootsettings_changed)
def rcv_bootsettings_changed(*args, **kwargs):
    # not signal when bootserver is not set
    if kwargs["device"].bootserver_id:
        _insert_bg_job("change_bootsetting", kwargs["cause"], kwargs["device"])


def _insert_bg_job(cmd, cause, obj):
    if getattr(obj, "_no_bg_job", False):
        return
    # create entry to be handled by the cluster-server
    # get local device, key is defined in routing.py
    _routing_key = "_WF_ROUTING"
    _resolv_dict = cache.get(_routing_key)
    if _resolv_dict:
        _r_dict = json.loads(_resolv_dict)
        if "_local_device" in _r_dict:
            _local_pk = _r_dict["_local_device"][0]
        else:
            _local_pk = 0
    else:
        try:
            _local_pk = device.objects.get(Q(name=process_tools.get_machine_name())).pk
        except device.DoesNotExist:
            _local_pk = 0
    # we need local_pk and a valid user (so we have to be called via webfrontend)
    if _local_pk and thread_local_middleware().user:
        srv_com = server_command.srv_command(
            command=cmd,
        )
        _bld = srv_com.builder()
        srv_com["object"] = _bld.object(
            unicode(obj),
            model=obj._meta.model_name,
            app=obj._meta.app_label,
            pk="{:d}".format(obj.pk)
        )
        background_job.objects.create(
            command=cmd,
            cause=u"{} of '{}'".format(cause, unicode(obj)),
            state="pre-init",
            initiator=device.objects.get(Q(pk=_local_pk)),
            user=thread_local_middleware().user,
            command_xml=unicode(srv_com),
            # valid for 4 hours
            valid_until=cluster_timezone.localize(datetime.datetime.now() + datetime.timedelta(seconds=60 * 5)),  # 3600 * 4)),
        )
        # init if not already done
        if not hasattr(_thread_local, "num_bg_jobs"):
            _thread_local.num_bg_jobs = 1
        else:
            _thread_local.num_bg_jobs += 1
    else:
        if not _local_pk:
            logger.error("cannot identify local device")


def _signal_localhost():
    # signal clusterserver running on localhost
    _sender = net_tools.zmq_connection("wf_server_notify")
    _sender.add_connection("tcp://localhost:8004", server_command.srv_command(command="wf_notify"), multi=True)
    _sender.close()


def boot_uuid(cur_uuid):
    return "{}-boot".format(cur_uuid[:-5])


class home_export_list(object):
    """ build home_export_list (dict) from DB, used in forms.py and ldap_modules.py """
    def __init__(self):
        exp_entries = device_config.objects.filter(
            Q(config__name__icontains="homedir") &
            Q(config__name__icontains="export") &
            Q(device__device_type__identifier="H")).prefetch_related("config__config_str_set").select_related("device", "device__domain_tree_node")
        home_exp_dict = {}
        for entry in exp_entries:
            dev_name, dev_name_full, act_pk = (
                entry.device.name,
                entry.device.full_name,
                entry.pk
            )
            home_exp_dict[act_pk] = {
                "key": act_pk,
                "entry": entry,
                "name": dev_name,
                "full_name": dev_name_full,
                "homeexport": "",
                "node_postfix": "",
                "createdir": "",
                "options": "-soft",
            }
            for c_str in entry.config.config_str_set.all():
                if c_str.name in home_exp_dict[act_pk]:
                    home_exp_dict[act_pk][c_str.name] = c_str.value
        # remove invalid exports (with no homeexport-entry)
        invalid_home_keys = [key for key, value in home_exp_dict.iteritems() if not value["homeexport"]]
        for ihk in invalid_home_keys:
            del home_exp_dict[ihk]
        for key, value in home_exp_dict.iteritems():
            value["info"] = u"{} on {}".format(value["homeexport"], value["name"])
            value["entry"].info_str = value["info"]
            value["entry"].info_dict = value
        self.exp_dict = home_exp_dict

    def get(self, *args, **kwargs):
        # hacky
        return self.exp_dict[int(kwargs["pk"])]["entry"]

    def all(self):
        for pk in [s_pk for _s_info, s_pk in sorted([(value["info"], key) for key, value in self.exp_dict.iteritems()])]:
            yield self.exp_dict[pk]["entry"]


class architecture(models.Model):
    idx = models.AutoField(db_column="architecture_idx", primary_key=True)
    architecture = models.CharField(default="", unique=True, max_length=128)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'architecture'

    def __unicode__(self):
        return self.architecture


class config_catalog(models.Model):
    idx = models.AutoField(primary_key=True)
    # MySQL restriction
    name = models.CharField(max_length=254, unique=True, blank=False, null=False)
    url = models.URLField(max_length=256, default="", blank=True)
    author = models.CharField(max_length=256, default="", blank=True)
    # gets increased by one on every download
    version = models.IntegerField(default=1)
    # extraction time
    extraction_time = models.DateTimeField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def create_local_catalog():
        def_cc = config_catalog.objects.create(
            name="local",
            url="http://www.initat.org/",
            author="Andreas Lang-Nevyjel",
        )
        return def_cc

    def __unicode__(self):
        return self.name


class config(models.Model):
    idx = models.AutoField(db_column="new_config_idx", primary_key=True)
    name = models.CharField(max_length=192, blank=False)
    config_catalog = models.ForeignKey(config_catalog, null=True)
    description = models.CharField(max_length=765, default="", blank=True)
    priority = models.IntegerField(null=True, default=0)
    # valid for servers (activate special functionalities)
    server_config = models.BooleanField(default=False)
    # system config, not user generated
    system_config = models.BooleanField(default=False)
    # config_type = models.ForeignKey("config_type", db_column="new_config_type_id")
    # can not be used for server configs
    parent_config = models.ForeignKey("config", null=True, blank=True)
    enabled = models.BooleanField(default=True)
    date = models.DateTimeField(auto_now_add=True)
    # categories for this config
    categories = models.ManyToManyField("backbone.category")

    def get_use_count(self):
        return self.device_config_set.all().count()

    def __unicode__(self):
        return self.name

    def show_variables(self, log_com, detail=False):
        log_com(" - config {} (pri {:d})".format(
            self.name,
            self.priority))
        if detail:
            for var_type in ["str", "int", "bool"]:
                for cur_var in getattr(self, "config_{}_set".format(var_type)).all():
                    log_com("    {:<20s} : {}".format(cur_var.name, unicode(cur_var)))

    def natural_key(self):
        return self.name

    class Meta:
        db_table = u'new_config'
        ordering = ["name", "config_catalog__name"]
        unique_together = (("name", "config_catalog"),)

    class CSW_Meta:
        permissions = (
            ("modify_config", "modify global configurations", False),
        )
        fk_ignore_list = ["config_str", "config_int", "config_script", "config_bool", "config_blob", "mon_check_command"]


@receiver(signals.pre_save, sender=config)
def config_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        cur_inst.description = cur_inst.description or ""
        _check_empty_string(cur_inst, "name")
        if cur_inst.server_config:
            cur_inst.parent_config = None
        # priority
        _check_integer(cur_inst, "priority", min_val=-9999, max_val=9999)


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
        parent_list = []
        cur_parent = cur_inst
        while True:
            if cur_parent.pk in parent_list:
                raise ValidationError("Loop in config parent setup detected")
            parent_list.append(cur_parent.pk)
            if cur_parent.parent_config_id:
                cur_parent = cur_parent.parent_config
            else:
                break
        if not cur_inst.config_catalog_id:
            if not config_catalog.objects.all().count():
                config_catalog.create_local_catalog()
            cur_inst.config_catalog = config_catalog.objects.all()[0]


class config_str(models.Model):
    idx = models.AutoField(db_column="config_str_idx", primary_key=True)
    name = models.CharField(max_length=192)
    description = models.CharField(db_column="descr", max_length=765)
    config_old = models.IntegerField(null=True, blank=True, db_column="config")
    config = models.ForeignKey("config", db_column="new_config_id")
    value = models.TextField(blank=True)
    device = models.ForeignKey("device", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def get_object_type(self):
        return "str"

    def __unicode__(self):
        return self.value or u""

    class Meta:
        db_table = u'config_str'
        ordering = ("name",)


@receiver(signals.pre_save, sender=config_str)
def config_str_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_empty_string(cur_inst, "name")
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
    config_old = models.IntegerField(null=True, blank=True, db_column="config")
    config = models.ForeignKey("config", db_column="new_config_id")
    value = models.TextField(blank=True)
    device = models.ForeignKey("device", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def get_object_type(self):
        return "blob"

    class Meta:
        db_table = u'config_blob'


@receiver(signals.pre_save, sender=config_blob)
def config_blob_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_empty_string(cur_inst, "name")
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
    config_old = models.IntegerField(null=True, blank=True, db_column="config")
    config = models.ForeignKey("config", db_column="new_config_id")
    value = models.IntegerField(null=True, blank=True)
    device = models.ForeignKey("device", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def get_object_type(self):
        return "bool"

    def __unicode__(self):
        return "True" if self.value else "False"

    class Meta:
        db_table = u'config_bool'


@receiver(signals.pre_save, sender=config_bool)
def config_bool_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_empty_string(cur_inst, "name")
        all_var_names = list(cur_inst.config.config_str_set.all().values_list("name", flat=True)) + \
            list(cur_inst.config.config_int_set.all().values_list("name", flat=True)) + \
            list(cur_inst.config.config_bool_set.exclude(Q(pk=cur_inst.pk)).values_list("name", flat=True)) + \
            list(cur_inst.config.config_blob_set.all().values_list("name", flat=True))
        if cur_inst.name in all_var_names:
            raise ValidationError("name '{}' already used".format(cur_inst.name))
        try:
            if type(cur_inst.value) == bool:
                pass
            else:
                if type(cur_inst.value) in [int, long]:
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
    config_old = models.IntegerField(null=True, blank=True, db_column="config")
    config = models.ForeignKey("config", db_column="new_config_id")
    value = models.IntegerField(null=True, blank=True)
    device = models.ForeignKey("device", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def get_object_type(self):
        return "int"

    def __unicode__(self):
        if type(self.value) in [str, unicode]:
            self.value = int(self.value)
        return "{:d}".format(self.value or 0)

    class Meta:
        db_table = u'config_int'


@receiver(signals.pre_save, sender=config_int)
def config_int_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_empty_string(cur_inst, "name")
        all_var_names = list(cur_inst.config.config_str_set.all().values_list("name", flat=True)) + \
            list(cur_inst.config.config_int_set.exclude(Q(pk=cur_inst.pk)).values_list("name", flat=True)) + \
            list(cur_inst.config.config_bool_set.all().values_list("name", flat=True)) + \
            list(cur_inst.config.config_blob_set.all().values_list("name", flat=True))
        if cur_inst.name in all_var_names:
            raise ValidationError("name '{}' already used".format(cur_inst.name))
        _check_integer(cur_inst, "value")


class config_script(models.Model):
    idx = models.AutoField(db_column="config_script_idx", primary_key=True)
    name = models.CharField(max_length=192)
    description = models.CharField(max_length=765, db_column="descr")
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
        db_table = u'config_script'
        ordering = ("priority", "name",)


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
        _check_integer(cur_inst, "priority")
        cur_inst.error_text = cur_inst.error_text or ""


class device_variable(models.Model):
    idx = models.AutoField(db_column="device_variable_idx", primary_key=True)
    device = models.ForeignKey("device")
    is_public = models.BooleanField(default=True)
    name = models.CharField(max_length=765)
    description = models.CharField(max_length=765, default="", blank=True)
    # can be copied to a group or device ? There is no sense in making the cluster_name a local instance
    local_copy_ok = models.BooleanField(default=True)
    var_type = models.CharField(max_length=3, choices=[
        ("i", "integer"),
        ("s", "string"),
        ("d", "datetime"),
        ("t", "time"),
        ("b", "blob"),
        # only for posting a new dv
        ("?", "guess")])
    val_str = models.TextField(blank=True, null=True, default="")
    val_int = models.IntegerField(null=True, blank=True, default=0)
    # base64 encoded
    val_blob = models.TextField(blank=True, null=True, default="")
    val_date = models.DateTimeField(null=True, blank=True)
    val_time = models.TextField(blank=True, null=True)  # This field type is a guess.
    date = models.DateTimeField(auto_now_add=True)

    def set_value(self, value):
        if type(value) == datetime.datetime:
            self.var_type = "d"
            self.val_date = cluster_timezone.localize(value)
        elif type(value) in [int, long] or (type(value) in [str, unicode] and value.isdigit()):
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
            str(self.get_value()))

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
        unique_together = ("name", "device",)
        ordering = ("name",)


@receiver(signals.pre_save, sender=device_variable)
def device_variable_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if cur_inst.device_id:
            _check_empty_string(cur_inst, "name")
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
                _check_empty_string(cur_inst, "val_str")
            if cur_inst.var_type == "i":
                _check_integer(cur_inst, "val_int")
            _check_empty_string(cur_inst, "var_type")
            all_var_names = device_variable.objects.exclude(Q(pk=cur_inst.pk)).filter(Q(device=cur_inst.device)).values_list("name", flat=True)
            if cur_inst.name in all_var_names:
                raise ValidationError(
                    "name '{}' already used for device '{}'".format(
                        cur_inst.name,
                        unicode(cur_inst.device)
                    )
                )
            cur_inst._clear()


class device_config(models.Model):
    idx = models.AutoField(db_column="device_config_idx", primary_key=True)
    device = models.ForeignKey("device")
    config = models.ForeignKey("backbone.config", db_column="new_config_id")
    date = models.DateTimeField(auto_now_add=True)

    def home_info(self):
        return self.info_str

    class Meta:
        db_table = u'device_config'


class partition_fs(models.Model):
    # mix of partition and fs info, not perfect ...
    idx = models.AutoField(db_column="partition_fs_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=48)
    identifier = models.CharField(max_length=3)
    descr = models.CharField(max_length=765, blank=True)
    hexid = models.CharField(max_length=6)
    # none, one or more (space sepearted) kernel modules needed for ths fs
    kernel_module = models.CharField(max_length=128, default="")
    # flags
    date = models.DateTimeField(auto_now_add=True)

    def need_mountpoint(self):
        return True if self.hexid in ["83"] else False

    def __unicode__(self):
        return self.descr

    class Meta:
        db_table = u'partition_fs'
        ordering = ("name",)


class sys_partition(models.Model):
    idx = models.AutoField(db_column="sys_partition_idx", primary_key=True)
    partition_table = models.ForeignKey("backbone.partition_table")
    name = models.CharField(max_length=192)
    mountpoint = models.CharField(max_length=192, default="/")
    mount_options = models.CharField(max_length=255, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'sys_partition'


class lvm_lv(models.Model):
    idx = models.AutoField(db_column="lvm_lv_idx", primary_key=True)
    partition_table = models.ForeignKey("backbone.partition_table")
    lvm_vg = models.ForeignKey("backbone.lvm_vg")
    size = models.BigIntegerField(null=True, blank=True)
    mountpoint = models.CharField(max_length=192, default="/")
    mount_options = models.CharField(max_length=384, blank=True)
    fs_freq = models.IntegerField(null=True, blank=True)
    fs_passno = models.IntegerField(null=True, blank=True)
    name = models.CharField(max_length=192)
    partition_fs = models.ForeignKey("backbone.partition_fs")
    warn_threshold = models.IntegerField(null=True, blank=True, default=85)
    crit_threshold = models.IntegerField(null=True, blank=True, default=95)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'lvm_lv'
        ordering = ("name",)


@receiver(signals.pre_save, sender=lvm_lv)
def lvm_lv_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_integer(cur_inst, "warn_threshold", none_to_zero=True, min_val=0, max_val=100)
        _check_integer(cur_inst, "crit_threshold", none_to_zero=True, min_val=0, max_val=100)
        # fs_freq
        _check_integer(cur_inst, "fs_freq", min_val=0, max_val=1)
        # fs_passno
        _check_integer(cur_inst, "fs_passno", min_val=0, max_val=2)


class lvm_vg(models.Model):
    idx = models.AutoField(db_column="lvm_vg_idx", primary_key=True)
    partition_table = models.ForeignKey("backbone.partition_table")
    name = models.CharField(max_length=192)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'lvm_vg'
        ordering = ("name",)


class partition(models.Model):
    idx = models.AutoField(db_column="partition_idx", primary_key=True)
    partition_disc = models.ForeignKey("backbone.partition_disc")
    mountpoint = models.CharField(max_length=192, default="/", blank=True)
    partition_hex = models.CharField(max_length=6, blank=True)
    size = models.IntegerField(null=True, blank=True, default=100)
    mount_options = models.CharField(max_length=255, blank=True, default="defaults")
    pnum = models.IntegerField()
    bootable = models.BooleanField(default=False)
    fs_freq = models.IntegerField(null=True, blank=True, default=0)
    fs_passno = models.IntegerField(null=True, blank=True, default=0)
    partition_fs = models.ForeignKey("backbone.partition_fs")
    # lut_blob = models.TextField(blank=True, null=True)
    # comma-delimited list of /dev/disk/by-* entries
    disk_by_info = models.TextField(default="", blank=True)
    warn_threshold = models.IntegerField(null=True, blank=True, default=85)
    crit_threshold = models.IntegerField(null=True, blank=True, default=95)
    date = models.DateTimeField(auto_now_add=True)

    def _validate(self, p_disc):
        p_list = []
        p_name = "{}{:d}".format(p_disc, self.pnum)
        if not self.partition_fs_id:
            p_list.append((logging_tools.LOG_LEVEL_ERROR, "no partition_fs set ({})".format(p_name), False))
        else:
            if self.partition_fs.hexid == "0" and self.partition_fs.name == "empty":
                p_list.append((logging_tools.LOG_LEVEL_ERROR, "empty partitionf_fs ({})".format(p_name), False))
            if self.partition_fs.need_mountpoint():
                if not self.mountpoint.startswith("/"):
                    p_list.append((logging_tools.LOG_LEVEL_ERROR, "no mountpoint defined for {}".format(p_name), False))
                if not self.mount_options.strip():
                    p_list.append((logging_tools.LOG_LEVEL_ERROR, "no mount_options given for {}".format(p_name), False))
        return p_list

    class Meta:
        db_table = u'partition'
        ordering = ("pnum",)


@receiver(signals.pre_save, sender=partition)
def partition_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        p_num = cur_inst.pnum
        if type(p_num) in [str, unicode]:
            if not p_num.strip():
                p_num = "0"
        try:
            p_num = int(p_num)
        except:
            raise ValidationError("partition number '{}' not parseable".format(p_num))
        if p_num == 0:
            if partition.objects.filter(Q(partition_disc=cur_inst.partition_disc)).count() > 1:
                raise ValidationError("for pnum==0 only one partition is allowed")
        elif p_num < 1 or p_num > 32:
            raise ValidationError("partition number {:d} out of bounds [1, 32]".format(p_num))
        all_part_nums = partition.objects.exclude(Q(pk=cur_inst.pk)).filter(Q(partition_disc=cur_inst.partition_disc)).values_list("pnum", flat=True)
        if p_num in all_part_nums:
            raise ValidationError("partition number already used")
        cur_inst.pnum = p_num
        # size
        _check_integer(cur_inst, "size", min_val=0)
        _check_integer(cur_inst, "warn_threshold", none_to_zero=True, min_val=0, max_val=100)
        _check_integer(cur_inst, "crit_threshold", none_to_zero=True, min_val=0, max_val=100)
        # mountpoint
        if cur_inst.partition_fs.need_mountpoint():
            if cur_inst.mountpoint.strip() and not cur_inst.mountpoint.startswith("/"):
                raise ValidationError("mountpoint must start with '/'")
        # fs_freq
        _check_integer(cur_inst, "fs_freq", min_val=0, max_val=1)
        # fs_passno
        _check_integer(cur_inst, "fs_passno", min_val=0, max_val=2)
        if cur_inst.partition_fs_id:
            if cur_inst.partition_fs.name == "swap":
                cur_inst.mountpoint = "swap"
            if not cur_inst.partition_fs.need_mountpoint():
                cur_inst.mountpoint = ""
            cur_inst.partition_hex = cur_inst.partition_fs.hexid


class partition_disc(models.Model):
    idx = models.AutoField(db_column="partition_disc_idx", primary_key=True)
    partition_table = models.ForeignKey("backbone.partition_table")
    disc = models.CharField(max_length=192)
    label_type = models.CharField(max_length=128, default="gpt", choices=[("gpt", "GPT"), ("msdos", "MSDOS")])
    priority = models.IntegerField(null=True, default=0)
    date = models.DateTimeField(auto_now_add=True)

    def _validate(self):
        my_parts = self.partition_set.all()
        p_list = sum([[(cur_lev, "*{:d} : {}".format(part.pnum, msg), flag) for cur_lev, msg, flag in part._validate(self)] for part in my_parts], [])
        all_mps = [cur_mp.mountpoint for cur_mp in my_parts if cur_mp.mountpoint.strip() and cur_mp.mountpoint.strip() != "swap"]
        if len(all_mps) != len(set(all_mps)):
            p_list.append((logging_tools.LOG_LEVEL_ERROR, "mountpoints not unque", False))
        if all_mps:
            if "/usr" in all_mps:
                p_list.append((logging_tools.LOG_LEVEL_ERROR, "cannot boot when /usr is on a separate partition", False))
        ext_parts = [cur_p for cur_p in my_parts if cur_p.partition_fs_id and cur_p.partition_fs.name == "ext"]
        if my_parts:
            max_pnum = max([cur_p.pnum for cur_p in my_parts])
            if self.label_type == "msdos":
                # msdos label validation path
                if len(ext_parts) == 0:
                    if max_pnum > 4:
                        p_list.append((logging_tools.LOG_LEVEL_ERROR, "too many partitions ({:d}), only 4 without ext allowed".format(max_pnum), False))
                elif len(ext_parts) > 1:
                    p_list.append((logging_tools.LOG_LEVEL_ERROR, "too many ext partitions ({:d}) defined".format(len(ext_parts)), False))
                else:
                    ext_part = ext_parts[0]
                    if ext_part.pnum != 4:
                        p_list.append((logging_tools.LOG_LEVEL_ERROR, "extended partition must have pnum 4", False))
            else:
                # gpt label validation path
                if len(ext_parts):
                    p_list.append((logging_tools.LOG_LEVEL_ERROR, "no extended partitions allowed for GPT label", False))
        return p_list

    class Meta:
        db_table = u'partition_disc'
        ordering = ("priority", "disc",)

    def __unicode__(self):
        return self.disc


@receiver(signals.pre_save, sender=partition_disc)
def partition_disc_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        disc_re = re.compile("^/dev/([shv]d[a-z]|dm-(\d+)|mapper/.*|ida/(.*)|cciss/(.*))$")
        cur_inst = kwargs["instance"]
        d_name = cur_inst.disc.strip().lower()
        if not d_name:
            raise ValidationError("name must not be zero")
        if not disc_re.match(d_name):
            raise ValidationError("illegal name '{}'".format(d_name))
        all_discs = partition_disc.objects.exclude(Q(pk=cur_inst.pk)).filter(Q(partition_table=cur_inst.partition_table)).values_list("disc", flat=True)
        if d_name in all_discs:
            raise ValidationError("disc name '{}' already used".format(d_name))
        cur_inst.disc = d_name


class partition_table(models.Model):
    idx = models.AutoField(db_column="partition_table_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    description = models.CharField(max_length=255, blank=True, default="")
    enabled = models.BooleanField(default=True)
    valid = models.BooleanField(default=False)
    modify_bootloader = models.IntegerField(default=0)
    nodeboot = models.BooleanField(default=False)
    # non users-created partition tables can be deleted automatically
    user_created = models.BooleanField(default=True)
    date = models.DateTimeField(auto_now_add=True)

    def _msg_merge(self, parent, msg):
        if msg.startswith("*"):
            return "{}{}".format(parent, msg[1:])
        else:
            return "{}: {}".format(parent, msg)

    def validate(self):
        # problem list, format is level, problem, global (always True for partition_table)
        prob_list = []
        if not self.partition_disc_set.all():
            prob_list.append((logging_tools.LOG_LEVEL_ERROR, "no discs defined", True))
        prob_list.extend(
            sum([
                [
                    (cur_lev, self._msg_merge(p_disc.disc, msg), flag) for cur_lev, msg, flag in p_disc._validate()
                ] for p_disc in self.partition_disc_set.all()
            ], [])
        )
        all_mps = sum(
            [
                [
                    cur_p.mountpoint for cur_p in p_disc.partition_set.all() if cur_p.mountpoint.strip() and (
                        cur_p.partition_fs_id and cur_p.partition_fs.need_mountpoint()
                    )
                ] for p_disc in self.partition_disc_set.all()
            ],
            []
        )
        all_mps.extend([sys_p.mountpoint for sys_p in self.sys_partition_set.all()])
        unique_mps = set(all_mps)
        for non_unique_mp in sorted([name for name in unique_mps if all_mps.count(name) > 1]):
            prob_list.append(
                (logging_tools.LOG_LEVEL_ERROR, "mountpoint '{}' is not unique ({:d})".format(
                    non_unique_mp,
                    all_mps.count(name),
                ), True)
                )
        if u"/" not in all_mps:
            prob_list.append(
                (logging_tools.LOG_LEVEL_ERROR, "no '/' mountpoint defined", True)
                )
        new_valid = not any([log_level in [
            logging_tools.LOG_LEVEL_ERROR,
            logging_tools.LOG_LEVEL_CRITICAL] for log_level, _what, _is_global in prob_list])
        # validate
        if new_valid != self.valid:
            self.valid = new_valid
            self.save()
        return prob_list

    def __unicode__(self):
        return self.name

    class Meta:
        db_table = u'partition_table'

    class CSW_Meta:
        fk_ignore_list = ["partition_disc", "sys_partition", "lvm_lv", "lvm_vg"]


@receiver(signals.pre_save, sender=partition_table)
def partition_table_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not cur_inst.name.strip():
            raise ValidationError("name must not be zero")


class device(models.Model):
    idx = models.AutoField(db_column="device_idx", primary_key=True)
    # no longer unique as of 20130531 (ALN)
    # no dots allowed (these parts are now in domain_tree_node)
    name = models.CharField(max_length=192)
    # FIXME
    device_group = models.ForeignKey("device_group", related_name="device_group")
    device_type = models.ForeignKey("device_type")
    alias = models.CharField(max_length=384, blank=True)
    comment = models.CharField(max_length=384, blank=True)
    mon_device_templ = models.ForeignKey("backbone.mon_device_templ", null=True, blank=True)
    mon_device_esc_templ = models.ForeignKey("backbone.mon_device_esc_templ", null=True, blank=True)
    mon_ext_host = models.ForeignKey("backbone.mon_ext_host", null=True, blank=True)
    etherboot_valid = models.BooleanField(default=False)
    kernel_append = models.CharField(max_length=384, blank=True)
    newkernel = models.CharField(max_length=192, blank=True)
    new_kernel = models.ForeignKey("kernel", null=True, related_name="new_kernel")
    actkernel = models.CharField(max_length=192, blank=True)
    act_kernel = models.ForeignKey("kernel", null=True, related_name="act_kernel")
    act_kernel_build = models.IntegerField(null=True, blank=True)
    kernelversion = models.CharField(max_length=192, blank=True)
    stage1_flavour = models.CharField(max_length=48, blank=True, default="CPIO")
    newimage = models.CharField(max_length=765, blank=True)
    new_image = models.ForeignKey("image", null=True, related_name="new_image")
    actimage = models.CharField(max_length=765, blank=True)
    act_image = models.ForeignKey("image", null=True, related_name="act_image")
    imageversion = models.CharField(max_length=192, blank=True)
    # new partition table
    partition_table = models.ForeignKey("backbone.partition_table", null=True, related_name="new_partition_table")
    # current partition table
    act_partition_table = models.ForeignKey("backbone.partition_table", null=True, related_name="act_partition_table", blank=True)
    partdev = models.CharField(max_length=192, blank=True)
    fixed_partdev = models.IntegerField(null=True, blank=True)
    bz2_capable = models.IntegerField(null=True, blank=True)
    new_state = models.ForeignKey("backbone.status", null=True, db_column="newstate_id", blank=True)
    rsync = models.BooleanField(default=False)
    rsync_compressed = models.BooleanField(default=False)
    prod_link = models.ForeignKey("backbone.network", db_column="prod_link", null=True, blank=True)
    # states (with timestamp)
    recvstate = models.TextField(blank=True, default="not set")
    recvstate_timestamp = models.DateTimeField(null=True)
    reqstate = models.TextField(blank=True, default="not set")
    reqstate_timestamp = models.DateTimeField(null=True)
    # uptime (with timestamp)
    uptime = models.IntegerField(default=0)
    uptime_timestamp = models.DateTimeField(null=True, default=None)
    bootnetdevice = models.ForeignKey("backbone.netdevice", null=True, related_name="boot_net_device", on_delete=models.SET_NULL)
    bootserver = models.ForeignKey("device", null=True, related_name="boot_server", blank=True)
    reachable_via_bootserver = models.BooleanField(default=False)
    dhcp_mac = models.NullBooleanField(null=True, blank=True, default=False)
    dhcp_write = models.NullBooleanField(default=False)
    dhcp_written = models.NullBooleanField(default=False)
    dhcp_error = models.CharField(max_length=765, blank=True)
    propagation_level = models.IntegerField(default=0, blank=True)
    last_install = models.CharField(max_length=192, blank=True)
    last_boot = models.CharField(max_length=192, blank=True)
    last_kernel = models.CharField(max_length=192, blank=True)
    root_passwd = models.CharField(max_length=192, blank=True)
    # link to monitor_server (or null for master)
    monitor_server = models.ForeignKey("device", null=True, blank=True)
    monitor_checks = models.BooleanField(default=True, db_column="nagios_checks", verbose_name="Checks enabled")
    # performance data tracking, also needed for IPMI and SNMP active monitoring
    enable_perfdata = models.BooleanField(default=False, verbose_name="enable perfdata, check IPMI and SNMP")
    flap_detection_enabled = models.BooleanField(default=False)
    show_in_bootcontrol = models.BooleanField(default=True)
    # not so clever here, better in extra table, FIXME
    # cpu_info = models.TextField(blank=True, null=True)
    # machine uuid, cannot be unique due to MySQL problems with unique TextFields
    uuid = models.TextField(default="", max_length=64)  # , unique=True)
    # cluster url
    curl = models.CharField(default="ssh://", max_length=512, verbose_name="cURL")
    # , choices=[
    #    ("ssh://", "ssh://"),
    #    ("snmp://", "snmp://"),
    #    ("ipmi://", "ipmi://"),
    #    ("ilo4://", "ilo4://"), # no longer used ?
    #    ]
    # )
    date = models.DateTimeField(auto_now_add=True)
    # slaves
    master_connections = models.ManyToManyField("self", through="cd_connection", symmetrical=False, related_name="slave_connections")
    # automap root for nagvis
    automap_root_nagvis = models.BooleanField(default=False)
    # parent nagvis
    nagvis_parent = models.ForeignKey("device", null=True, related_name="nagvis_childs", blank=True)
    # enabled ?
    enabled = models.BooleanField(default=True)
    # try to read relevant data from device via md-config-server
    md_cache_mode = models.IntegerField(choices=[
        (1, "automatic (server)"),
        (2, "never use cache"),
        (3, "once (until successfull)"),
        ], default=1)
    # system name
    domain_tree_node = models.ForeignKey("backbone.domain_tree_node", null=True, default=None)
    # resolve name for monitoring (i.e. use IP for monitoring)
    mon_resolve_name = models.BooleanField(default=True, verbose_name="Resolve to IP for monitoring")
    # categories for this device
    categories = models.ManyToManyField("backbone.category")
    # store rrd data to disk
    store_rrd_data = models.BooleanField(default=True)
    # has active RRDs
    has_active_rrds = models.BooleanField(default=False)

    @property
    def full_name(self):
        if not self.domain_tree_node_id:
            self.domain_tree_node = domain_tree_node.objects.get(Q(depth=0))
            self.save()
        if self.domain_tree_node.full_name:
            return ".".join([self.name, self.domain_tree_node.full_name])
        else:
            return self.name

    def crypt(self, in_pwd):
        if in_pwd:
            salt = "".join([chr(random.randint(65, 90)) for _idx in xrange(4)])
            _crypted = crypt.crypt(in_pwd, salt)
            if _crypted == "*0":
                _crypted = ""
        else:
            _crypted = ""
        return _crypted

    def root_passwd_set(self):
        return True if self.root_passwd else False

    def is_meta_device(self):
        return self.device_type.identifier == "MD"

    def device_type_identifier(self):
        return self.device_type.identifier

    def device_group_name(self):
        return self.device_group.name

    def is_cluster_device_group(self):
        return self.device_group.cluster_device_group

    def get_monitor_type(self):
        sel_configs = set(self.device_config_set.filter(
            Q(config__name__in=["monitor_server", "monitor_master", "monitor_slave"])).values_list("config__name", flat=True)
        )
        if set(["monitor_master", "monitor_server"]) & sel_configs:
            return "master"
        elif sel_configs:
            return "slave"
        else:
            return "---"

    def get_boot_uuid(self):
        return boot_uuid(self.uuid)

    def add_log(self, log_src, log_stat, text, **kwargs):
        return devicelog.new_log(self, log_src, log_stat, text, **kwargs)

    def get_simple_xml(self):
        return E.device(
            unicode(self),
            pk="%d" % (self.pk),
            key="dev__%d" % (self.pk),
            name=self.name
        )

    def all_ips(self):
        # return all IPs
        return list(set(self.netdevice_set.all().values_list("net_ip__ip", flat=True)))

    def all_dns(self):
        # return all names, including short ones
        _list = [self.name, self.full_name]
        for _domain, _alias, _excl in self.netdevice_set.all().values_list("net_ip__domain_tree_node__full_name", "net_ip__alias", "net_ip__alias_excl"):
            if _alias:
                _add_names = _alias.strip().split()
                if not _excl:
                    _add_names.append(self.name)
            else:
                _add_names = [self.name]
            _list.extend(["{}.{}".format(_name, _domain) for _name in _add_names])
        return list(set(_list))

    def get_master_cons(self):
        return [entry for entry in self.cd_cons if entry.parent_id == self.pk]

    def get_slave_cons(self):
        return [entry for entry in self.cd_cons if entry.child_id == self.pk]

    def valid_state(self):
        _rs = ""
        if self.mother_xml is not None:
            if int(self.mother_xml.get("ok", "0")):
                now, recv_ts, req_ts = (
                    cluster_timezone.localize(datetime.datetime.now()).astimezone(pytz.UTC),
                    self.recvstate_timestamp,
                    self.reqstate_timestamp,
                )
                if recv_ts is not None:
                    recv_timeout = (now - recv_ts).seconds
                else:
                    recv_timeout = 3600
                if req_ts is not None:
                    req_timeout = (now - req_ts).seconds
                else:
                    req_timeout = 3600
                if req_timeout > recv_timeout:
                    # recv_state is newer
                    _rs = "recv"
                else:
                    # req_state is newer
                    _rs = "req"
        return _rs

    def net_state(self):
        _rs = "down"
        if self.mother_xml is not None:
            if int(self.mother_xml.get("ok", "0")):
                now, recv_ts, req_ts = (
                    cluster_timezone.localize(datetime.datetime.now()).astimezone(pytz.UTC),
                    self.recvstate_timestamp,
                    self.reqstate_timestamp,
                )
                if recv_ts is not None:
                    recv_timeout = (now - recv_ts).seconds
                else:
                    recv_timeout = 3600
                if req_ts is not None:
                    req_timeout = (now - req_ts).seconds
                else:
                    req_timeout = 3600
                if min(req_timeout, recv_timeout) > 20:
                    # too long ago, deem as outdated (not reachable by mother)
                    _rs = "ping"
                else:
                    _rs = "up"
        return _rs

    def network(self):
        _rs = "unknown"
        if self.mother_xml is not None:
            if int(self.mother_xml.get("ok", "0")):
                _rs = self.mother_xml.attrib["network"]
        return _rs

    def get_uptime(self):
        _rs = 0
        if self.mother_xml is not None:
            if int(self.mother_xml.get("ok", "0")):
                now, uptime_ts = (
                    cluster_timezone.localize(datetime.datetime.now()).astimezone(pytz.UTC),
                    self.uptime_timestamp,
                )
                if uptime_ts is not None:
                    uptime_timeout = (now - uptime_ts).seconds
                else:
                    uptime_timeout = 3600
                if uptime_timeout > 30:
                    # too long ago, outdated
                    _rs = 0
                else:
                    _rs = self.uptime
        return _rs

    def uptime_valid(self):
        _rs = False
        if self.mother_xml is not None:
            if int(self.mother_xml.get("ok", "0")):
                now, uptime_ts = (
                    cluster_timezone.localize(datetime.datetime.now()).astimezone(pytz.UTC),
                    self.uptime_timestamp,
                )
                if uptime_ts is not None:
                    uptime_timeout = (now - uptime_ts).seconds
                else:
                    uptime_timeout = 3600
                if uptime_timeout > 30:
                    # too long ago, outdated
                    _rs = False
                else:
                    _rs = True
        return _rs

    def latest_contact(self):
        lc_obj = [obj for obj in self.device_variable_set.all() if obj.name == "package_server_last_contact"]
        if lc_obj:
            return int(time.mktime(to_system_tz(lc_obj[0].val_date).timetuple()))
        else:
            return 0

    def client_version(self):
        vers_obj = [obj for obj in self.device_variable_set.all() if obj.name == "package_client_version"]
        if vers_obj:
            return vers_obj[0].val_str
        else:
            return "?.?"

    def __unicode__(self):
        return u"{}{}".format(
            self.name,
            u" ({})".format(self.comment) if self.comment else "")

    class CSW_Meta:
        permissions = (
            ("all_devices", "access all devices", False),
            ("show_graphs", "Access to device graphs", True),
            ("change_basic", "Change basic settings", True),
            ("change_network", "Change network", True),
            ("change_config", "Change configuration", True),
            ("change_boot", "Change boot settings", True),
            ("change_variables", "Change variables", True),
            ("change_connection", "Change device connection", True),
            ("change_monitoring", "Change device monitoring config", True),
            ("change_location", "Change device location", True),
            ("change_category", "Change device category", True),
        )
        fk_ignore_list = ["mon_trace", "netdevice", "device_variable", "device_config"]

    class Meta:
        db_table = u'device'
        ordering = ("name",)
        unique_together = [("name", "domain_tree_node"), ]


class device_selection(object):
    def __init__(self, sel_str):
        parts = sel_str.split("__")
        self.idx = int(parts[1])
        self.sel_type = {"dev": "d", "devg": "g"}[parts[0]]


@receiver(signals.post_save, sender=device)
def device_post_save(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        if _cur_inst.bootserver_id:
            bootsettings_changed.send(sender=_cur_inst, device=_cur_inst, cause="device_changed")
        if _cur_inst.device_type.identifier in ["MD"]:
            _stripped = strip_metadevice_name(_cur_inst.name)
            if _stripped != _cur_inst.device_group.name:
                _cur_inst.device_group.name = _stripped
                _cur_inst.device_group.save()


def _get_top_level_dtn():
    try:
        top_level_dn = domain_tree_node.objects.get(Q(depth=0))
    except domain_tree_node.DoesNotExist:
        top_level_dn = None
    return top_level_dn


@receiver(signals.pre_save, sender=device)
def device_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_empty_string(cur_inst, "name")
        if cur_inst.name.count("."):
            short_name, dom_name = cur_inst.name.split(".", 1)
            try:
                cur_dnt = domain_tree_node.objects.get(Q(full_name=dom_name))
            except domain_tree_node.DoesNotExist:
                # create new domain
                if settings.AUTO_CREATE_NEW_DOMAINS:
                    cur_inst.domain_tree_node = domain_name_tree().add_domain(dom_name)
                    cur_inst.name = short_name
                else:
                    raise ValidationError("domain '{}' not defined".format(dom_name))
            else:
                cur_inst.domain_tree_node = cur_dnt
                cur_inst.name = short_name
        else:
            if not cur_inst.domain_tree_node_id:
                cur_inst.domain_tree_node = _get_top_level_dtn()
            if not cur_inst.pk:
                top_level_dn = _get_top_level_dtn()
                if top_level_dn is not None:
                    if cur_inst.domain_tree_node_id == top_level_dn.pk:
                        if cur_inst.device_group.device_id:
                            # set domain_node to domain_node of meta_device
                            cur_inst.domain_tree_node = cur_inst.device_group.device.domain_tree_node
                        else:
                            # no meta device (i am the new meta device, ignore)
                            pass
            # raise ValidationError("no dots allowed in device name '%s'" % (cur_inst.name))
        if not valid_domain_re.match(cur_inst.name):
            # check if we can simple fix it
            if not valid_domain_re.match(cur_inst.name.replace(" ", "_")):
                raise ValidationError("illegal characters in name '{}'".format(cur_inst.name))
            else:
                cur_inst.name = cur_inst.name.replace(" ", "_")
        if int(cur_inst.md_cache_mode) == 0:
            cur_inst.md_cache_mode = 1
        _check_integer(cur_inst, "md_cache_mode", min_val=1, max_val=3)
        if not cur_inst.uuid:
            cur_inst.uuid = str(uuid.uuid4())
        # check for uniqueness of UUID
        try:
            present_dev = device.objects.get(Q(uuid=cur_inst.uuid))
        except device.DoesNotExist:
            pass
        else:
            if present_dev.pk != cur_inst.pk:
                raise ValidationError("UUID clash (={} for {} and {})".format(
                    cur_inst.uuid,
                    unicode(cur_inst),
                    unicode(present_dev),
                    ))
        # check for device group
        if cur_inst.device_group.cluster_device_group and cur_inst.device_type.identifier not in ["MD"]:
            raise ValidationError("no devices allowed in cluster_device_group")
        # Check if the device limit is reached, disabled as of 2013-10-14 (AL)
        if False:
            dev_count = settings.CLUSTER_LICENSE["device_count"]

            # Exclude special meta devices
            md_type = device_type.objects.get(identifier="MD")
            current_count = device.objects.exclude(device_type=md_type).count()

            if dev_count > 0 and current_count >= dev_count:
                logger.warning("Device limit {:d} reached".format(dev_count))
                raise ValidationError("Device limit reached!")


class cd_connection(models.Model):
    # controlling_device connection
    idx = models.AutoField(primary_key=True)
    parent = models.ForeignKey("device", related_name="parent_device")
    child = models.ForeignKey("device", related_name="child_device")
    created_by = models.ForeignKey("user", null=True)
    connection_info = models.CharField(max_length=256, default="not set")
    parameter_i1 = models.IntegerField(default=0)
    parameter_i2 = models.IntegerField(default=0)
    parameter_i3 = models.IntegerField(default=0)
    parameter_i4 = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "{} (via {}) {}".format(
            unicode(self.parent),
            self.connection_info,
            unicode(self.child))

    class Meta:
        ordering = ("parent__name", "child__name",)


@receiver(signals.pre_save, sender=cd_connection)
def cd_connection_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        for par_idx in xrange(1, 5):
            _check_integer(cur_inst, "parameter_i{:d}".format(par_idx), min_val=0, max_val=256)
        try:
            cd_connection.objects.get(Q(parent=cur_inst.parent_id) & Q(child=cur_inst.child_id))
        except cd_connection.DoesNotExist:
            pass
        except cd_connection.MultipleObjectsReturned:
            raise ValidationError("connections already exist")
        else:
            if cur_inst.pk is None:
                raise ValidationError("connection already exists")


class device_group(models.Model):
    idx = models.AutoField(db_column="device_group_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192, blank=False)
    description = models.CharField(max_length=384, default="")
    # device = models.ForeignKey("device", null=True, blank=True, related_name="group_device")
    # must be an IntegerField, otherwise we have a cycle reference
    # device = models.IntegerField(null=True, blank=True)
    device = models.ForeignKey("device", db_column="device", null=True, blank=True, related_name="group_device")
    # flag
    cluster_device_group = models.BooleanField(default=False)
    # enabled flag, ident to the enabled flag of the corresponding meta-device
    enabled = models.BooleanField(default=True)
    # domain tree node, see enabled flag
    domain_tree_node = models.ForeignKey("domain_tree_node", null=True, default=None)
    date = models.DateTimeField(auto_now_add=True)

    def _add_meta_device(self):
        new_md = device(name=self.get_metadevice_name(),
                        device_group=self,
                        domain_tree_node=self.domain_tree_node,
                        enabled=self.enabled,
                        # device_class=device_class.objects.get(Q(pk=1)),
                        device_type=device_type.objects.get(Q(identifier="MD")))
        new_md.save()
        self.device = new_md
        self.save()
        return new_md

    def get_metadevice_name(self, name=None):
        return "METADEV_{}".format(name if name else self.name)

    class Meta:
        db_table = u'device_group'
        ordering = ("-cluster_device_group", "name",)

    def __unicode__(self):
        return u"{}{}{}".format(
            self.name,
            " ({})".format(self.description) if self.description else "",
            "[*]" if self.cluster_device_group else ""
        )


def strip_metadevice_name(name):
    if name.startswith("METADEV_"):
        return name[8:]
    else:
        return name


@receiver(signals.pre_save, sender=device_group)
def device_group_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not cur_inst.name:
            raise ValidationError("name can not be zero")
        if not valid_domain_re.match(cur_inst.name):
            raise ValidationError("invalid characters in '{}'".format(cur_inst.name))


@receiver(signals.post_save, sender=device_group)
def device_group_post_save(sender, **kwargs):
    cur_inst = kwargs["instance"]
    if kwargs["created"] and not kwargs["raw"]:
        # first is always cdg
        if device_group.objects.count() == 1 and not cur_inst.cluster_device_group:
            cur_inst.cluster_device_group = True
            cur_inst.save()
    if not kwargs["raw"]:
        # meta_device is always created
        if not cur_inst.device_id:
            cur_inst._add_meta_device()
        if cur_inst.device_id:
            save_meta = False
            if cur_inst.device.name != cur_inst.get_metadevice_name():
                cur_inst.device.name = cur_inst.get_metadevice_name()
                save_meta = True
            for c_field in ["enabled", "domain_tree_node"]:
                if getattr(cur_inst.device, c_field) != getattr(cur_inst, c_field):
                    setattr(cur_inst.device, c_field, getattr(cur_inst, c_field))
                    save_meta = True
            if save_meta:
                cur_inst.device.save()
        if cur_inst.cluster_device_group and not cur_inst.enabled:
            # always enable cluster device group
            cur_inst.enabled = True
            cur_inst.save()


class cluster_setting(models.Model):
    idx = models.AutoField(db_column="device_rsync_config_idx", primary_key=True)
    name = models.CharField(max_length=64, default="GLOBAL", unique=True)
    login_screen_type = models.CharField(max_length=64, default="big", choices=[
        ("big", "big (full screen)"),
        ("medium", "medium (side by side)"),
        ])
    # also present in /etc/sysconfig/cluster/local_settings.py
    secret_key = models.CharField(max_length=64, default="")
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "cs {}, login_screen_type is {}, secret_key is '{}'".format(
            self.name,
            self.login_screen_type,
            self.secret_key,
        )


# license related
class cluster_license(models.Model):
    idx = models.AutoField(db_column="device_rsync_config_idx", primary_key=True)
    cluster_setting = models.ForeignKey("cluster_setting")
    name = models.CharField(max_length=64, default="", unique=True)
    enabled = models.BooleanField(default=False)
    description = models.CharField(max_length=256, default="")
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "clic {} (is {})".format(
            self.name,
            "enabled" if self.enabled else "disabled",
        )

    class Meta:
        ordering = ("name",)


@receiver(signals.post_save, sender=cluster_license)
def cluster_license_post_save(sender, **kwargs):
    cluster_license_cache(force=True)


class cluster_license_cache(object):
    def __init__(self, force=False):
        self.__CLC_NAME = "__ICSW_CLCV2"
        _cur_c = cache.get(self.__CLC_NAME)
        _lic_dict = {
            _name: {
                "enabled": False,
                "services": _srvs,
                "description": _descr,
            } for _name, _descr, _srvs in LICENSE_CAPS
        }
        if not _cur_c or force:
            for cur_lic in cluster_license.objects.filter(Q(cluster_setting__name="GLOBAL")):
                _lic_dict[cur_lic.name]["enabled"] = cur_lic.enabled
            cache.set(self.__CLC_NAME, marshal.dumps(_lic_dict), 300)
        else:
            _lic_dict.update(marshal.loads(_cur_c))
        self._lic_dict = _lic_dict

    @property
    def licenses(self):
        return self._lic_dict


class device_rsync_config(models.Model):
    idx = models.AutoField(db_column="device_rsync_config_idx", primary_key=True)
    config = models.ForeignKey("config", db_column="new_config_id")
    device = models.ForeignKey("device")
    last_rsync_time = models.DateTimeField(null=True, blank=True)
    status = models.TextField()
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'device_rsync_config'


class device_type(models.Model):
    idx = models.AutoField(db_column="device_type_idx", primary_key=True)
    identifier = models.CharField(unique=True, max_length=24)
    # for ordering
    priority = models.IntegerField(default=0)
    description = models.CharField(unique=True, max_length=192)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.description

    class Meta:
        db_table = u'device_type'


class devicelog(models.Model):
    idx = models.AutoField(db_column="devicelog_idx", primary_key=True)
    device = models.ForeignKey("device", null=True, blank=True)
    log_source = models.ForeignKey("log_source", null=True)
    user = models.ForeignKey("user", null=True)
    log_status = models.ForeignKey("log_status", null=True)
    text = models.CharField(max_length=765, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def new_log(cur_dev, log_src, log_stat, text, **kwargs):
        if log_src and type(log_src) in [int, long]:
            log_src = cached_short_log_source(log_src)
        if log_stat and type(log_stat) in [int, long]:
            log_stat = cached_log_status(log_stat)
        cur_log = devicelog.objects.create(
            device=cur_dev,
            log_source=log_src or cluster_log_source,
            user=kwargs.get("user", None),
            log_status=log_stat,
            text=text,
        )
        return cur_log

    def __unicode__(self):
        return u"{} ({}, {}:{:d})".format(
            self.text,
            self.log_source.name,
            self.log_status.identifier,
            self.log_status.log_level)

    class Meta:
        db_table = u'devicelog'
        ordering = ("date",)


class image(models.Model):
    idx = models.AutoField(db_column="image_idx", primary_key=True)
    name = models.CharField(max_length=192, blank=True, unique=True)
    source = models.CharField(max_length=384, blank=True)
    version = models.IntegerField(null=True, blank=True, default=1)
    release = models.IntegerField(null=True, blank=True, default=0)
    builds = models.IntegerField(null=True, blank=True, default=0)
    build_machine = models.CharField(max_length=192, blank=True, default="")
    # not a foreign key to break cyclic dependencies
    # device = models.ForeignKey("device", null=True)
    device = models.IntegerField(null=True)
    build_lock = models.BooleanField(default=False)
    # size in Byte
    size = models.BigIntegerField(default=0)
    size_string = models.TextField(blank=True, default="")
    sys_vendor = models.CharField(max_length=192, blank=True)
    sys_version = models.CharField(max_length=192, blank=True)
    sys_release = models.CharField(max_length=192, blank=True)
    bitcount = models.IntegerField(null=True, blank=True)
    architecture = models.ForeignKey("architecture")
    full_build = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)
    enabled = models.BooleanField(default=True)

    def __unicode__(self):
        return "{} (arch {})".format(
            self.name,
            unicode(self.architecture))

    class Meta:
        db_table = u'image'
        ordering = ("name",)


@receiver(signals.pre_save, sender=image)
def image_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        cur_inst.size_string = logging_tools.get_size_str(cur_inst.size)


class kernel(models.Model):
    idx = models.AutoField(db_column="kernel_idx", primary_key=True)
    name = models.CharField(max_length=384)
    kernel_version = models.CharField(max_length=384)
    major = models.CharField(max_length=192, blank=True)
    minor = models.CharField(max_length=192, blank=True)
    patchlevel = models.CharField(max_length=192, blank=True)
    version = models.IntegerField(null=True, blank=True, default=1)
    release = models.IntegerField(null=True, blank=True, default=1)
    builds = models.IntegerField(null=True, blank=True, default=0)
    build_machine = models.CharField(max_length=192, blank=True)
    # not a foreignkey to break cyclic dependencies
    # master_server = models.ForeignKey("device", null=True, related_name="master_server")
    master_server = models.IntegerField(null=True)
    master_role = models.CharField(max_length=192, blank=True)
    # not a foreignkey to break cyclic dependencies
    # device = models.ForeignKey("device", null=True)
    device = models.IntegerField(null=True)
    build_lock = models.BooleanField(default=False)
    config_name = models.CharField(max_length=192, blank=True)
    cpu_arch = models.CharField(max_length=192, blank=True)
    sub_cpu_arch = models.CharField(max_length=192, blank=True)
    target_dir = models.CharField(max_length=765, blank=True)
    comment = models.TextField(blank=True, default="")
    enabled = models.BooleanField(default=False)
    initrd_version = models.IntegerField(null=True, blank=True)
    initrd_built = models.DateTimeField(null=True, blank=True)
    # which modules are actually built into initrd
    module_list = models.TextField(blank=True)
    # which modules are requested
    target_module_list = models.TextField(blank=True, default="")
    xen_host_kernel = models.NullBooleanField(default=False)
    xen_guest_kernel = models.NullBooleanField(default=False)
    bitcount = models.IntegerField(null=True, blank=True)
    stage1_lo_present = models.BooleanField(default=False)
    stage1_cpio_present = models.BooleanField(default=False)
    stage1_cramfs_present = models.BooleanField(default=False)
    stage2_present = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)

    def get_usecount(self):
        return 5

    def __unicode__(self):
        return self.name

    class Meta:
        db_table = u'kernel'

    class CSW_Meta:
        fk_ignore_list = ["initrd_build", "kernel_build"]


class initrd_build(models.Model):
    idx = models.AutoField(primary_key=True)
    kernel = models.ForeignKey("kernel")
    user_name = models.CharField(max_length=128, default="root")
    # run_time in seconds
    run_time = models.IntegerField(default=0)
    success = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)


class kernel_build(models.Model):
    idx = models.AutoField(db_column="kernel_build_idx", primary_key=True)
    kernel = models.ForeignKey("kernel")
    build_machine = models.CharField(max_length=192, blank=True)
    device = models.ForeignKey("device", null=True)
    version = models.IntegerField(null=True, blank=True)
    release = models.IntegerField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'kernel_build'


class kernel_local_info(models.Model):
    idx = models.AutoField(db_column="kernel_local_info_idx", primary_key=True)
    kernel = models.ForeignKey("kernel")
    device = models.ForeignKey("device")
    syncer_role = models.CharField(max_length=192, blank=True)
    info_blob = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'kernel_local_info'


class kernel_log(models.Model):
    idx = models.AutoField(db_column="kernel_log_idx", primary_key=True)
    kernel = models.ForeignKey("kernel")
    device = models.ForeignKey("device")
    syncer_role = models.CharField(max_length=192, blank=True)
    log_level = models.IntegerField(null=True, blank=True)
    log_str = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'kernel_log'


class log_source(models.Model):
    idx = models.AutoField(db_column="log_source_idx", primary_key=True)
    # server_type or user
    identifier = models.CharField(max_length=192)
    # name (Cluster Server, webfrontend, ...)
    name = models.CharField(max_length=192)
    # link to device or None
    device = models.ForeignKey("device", null=True)
    # long description
    description = models.CharField(max_length=765, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def create_log_source_entry(identifier, name, **kwargs):
        ls_dev = kwargs.get("device", None)
        sources = log_source.objects.filter(Q(identifier=identifier) & Q(device=ls_dev))
        if len(sources) > 1:
            print "Too many log_source_entries present ({}), exiting".format(", ".join([identifier, name]))
            cur_source = None
        elif not len(sources):
            if ls_dev is not None:
                new_source = log_source(
                    identifier=identifier,
                    name=name,
                    description=u"{} on {}".format(name, unicode(ls_dev)),
                    device=kwargs["device"]
                )
                new_source.save()
            else:
                new_source = log_source(
                    identifier=identifier,
                    name=name,
                    description=kwargs.get("description", "{} (id {})".format(name, identifier))
                )
                new_source.save()
            cur_source = new_source
        else:
            cur_source = sources[0]
        return cur_source

    def __unicode__(self):
        return "ls {} ({}), {}".format(
            self.name,
            self.identifier,
            self.description)

    class Meta:
        db_table = u'log_source'


def log_source_lookup(identifier, log_dev):
    return log_source.objects.get(Q(identifier=identifier) & Q(device=log_dev))


def short_log_source_lookup(idx):
    return log_source.objects.get(Q(pk=idx))

cached_log_source = memoize(log_source_lookup, {}, 2)
cached_short_log_source = memoize(short_log_source_lookup, {}, 2)


class log_status(models.Model):
    idx = models.AutoField(db_column="log_status_idx", primary_key=True)
    identifier = models.CharField(max_length=12, blank=True)
    log_level = models.IntegerField(null=True, blank=True)
    name = models.CharField(max_length=192, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'log_status'


def log_status_lookup(key):
    if type(key) in [str, unicode]:
        return log_status.objects.get(Q(identifier=key))
    else:
        return log_status.objects.get(Q(log_level={
            logging_tools.LOG_LEVEL_OK: 0,
            logging_tools.LOG_LEVEL_WARN: 50,
            logging_tools.LOG_LEVEL_ERROR: 100,
            logging_tools.LOG_LEVEL_CRITICAL: 200}[key]))

cached_log_status = memoize(log_status_lookup, {}, 1)


class mac_ignore(models.Model):
    idx = models.AutoField(db_column="mac_ignore_idx", primary_key=True)
    macaddr = models.CharField(max_length=192, db_column="macadr", default="00:00:00:00:00:00")
    user = models.ForeignKey("backbone.user", null=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'mac_ignore'


class macbootlog(models.Model):
    idx = models.AutoField(db_column="macbootlog_idx", primary_key=True)
    device = models.ForeignKey("device", null=True)
    entry_type = models.CharField(max_length=96, db_column="type", default="???")
    ip_action = models.CharField(max_length=96, db_column="ip", default="0.0.0.0")
    macaddr = models.CharField(max_length=192, db_column="macadr", default="00:00:00:00:00:00")
    log_source = models.ForeignKey("log_source", null=True)
    date = models.DateTimeField(auto_now_add=True)

    def get_created(self):
        return time.mktime(cluster_timezone.normalize(self.date).timetuple())

    def get_device_name(self):
        if self.device_id:
            return self.device.full_name
        else:
            return ""

    class Meta:
        db_table = u'macbootlog'


class status(models.Model):
    idx = models.AutoField(db_column="status_idx", primary_key=True)
    status = models.CharField(unique=True, max_length=255)
    prod_link = models.BooleanField(default=True)
    memory_test = models.BooleanField(default=False)
    boot_iso = models.BooleanField(default=False)
    boot_local = models.BooleanField(default=False)
    do_install = models.BooleanField(default=False)
    is_clean = models.BooleanField(default=False)
    # allow mother to set bools according to status
    allow_boolean_modify = models.BooleanField(default=True)
    date = models.DateTimeField(auto_now_add=True)

    def info_string(self):
        return unicode(self)

    def __unicode__(self):
        # print ".", self.status
        return u"{} ({}){}".format(
            self.status,
            ",".join([short for short, attr_name in [
                ("link", "prod_link"),
                ("mem", "memory_test"),
                ("loc", "boot_local"),
                ("ins", "do_install"),
                ("iso", "boot_iso"),
                ("retain", "is_clean")] if getattr(self, attr_name)]),
            "(*)" if self.allow_boolean_modify else "")

    class Meta:
        db_table = u'status'


class tree_node(models.Model):
    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey("device", default=None)
    is_dir = models.BooleanField(default=False)
    is_link = models.BooleanField(default=False)
    parent = models.ForeignKey("tree_node", null=True, default=None)
    # is an intermediate node is has not to be created
    intermediate = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)

    def __cmp__(self, other):
        if self.is_dir == other.is_dir:
            if self.wc_files.dest < other.wc_files.dest:
                return -1
            elif self.wc_files.dest > other.wc_files.dest:
                return 1
            else:
                return 0
        elif self.is_dir:
            return -1
        else:
            return +1

    def get_type_str(self):
        return "dir" if self.is_dir else ("link" if self.is_link else "file")

    def __unicode__(self):
        return "tree_node, {}".format(self.get_type_str())


class wc_files(models.Model):
    idx = models.AutoField(db_column="wc_files_idx", primary_key=True)
    device = models.ForeignKey("device")
    tree_node = models.OneToOneField("tree_node", null=True, default=None)
    run_number = models.IntegerField(default=0)
    config = models.ManyToManyField("backbone.config")
    # config = models.CharField(max_length=255, blank=True)
    uid = models.IntegerField(default=0, blank=True)
    gid = models.IntegerField(default=0, blank=True)
    mode = models.IntegerField(default=0755, blank=True)
    dest_type = models.CharField(max_length=8, choices=(
        ("f", "file"),
        ("l", "link"),
        ("d", "directory"),
        ("e", "erase"),
        ("c", "copy"),
        ("i", "internal"),
    ))
    # source path
    source = models.CharField(max_length=1024)
    # destination path, relative to tree_node
    dest = models.CharField(max_length=1024)
    # error
    error_flag = models.BooleanField(default=False)
    # content, defaults to the empty string, base64-encoded for binary data
    content = models.TextField(blank=True, default="")
    binary = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'wc_files'
