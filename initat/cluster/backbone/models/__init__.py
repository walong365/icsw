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
""" models for NOCTUA and CORVUS, master file """

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.signals import request_finished, request_started
from django.db import models
from django.db.models import Q, signals, CASCADE
from django.dispatch import receiver
from django.utils.lru_cache import lru_cache
from django.utils.crypto import get_random_string
from initat.tools.bgnotify.create import create_bg_job, notify_command
from initat.cluster.backbone.middleware import thread_local_middleware, \
    thread_local_obj
from initat.tools import config_store, logging_tools, net_tools, process_tools
from initat.constants import GEN_CS_NAME
from initat.cluster.backbone.models.functions import check_empty_string, \
    check_float, check_integer, check_non_empty_string, to_system_tz, \
    get_change_reset_list, get_related_models, cluster_timezone, duration, \
    system_timezone, db_limit_1
from django.conf import settings
from lxml.builder import E
import crypt
import datetime
import json
import logging
import random
import time
import uuid

from initat.cluster.backbone.models.internal import *
from initat.cluster.backbone.models.variable import *
from initat.cluster.backbone.models.device import *
from initat.cluster.backbone.models.capability import *
from initat.cluster.backbone.models.domain import *
from initat.cluster.backbone.models.config import *
from initat.cluster.backbone.models.monitoring import *
from initat.cluster.backbone.models.network import *
from initat.cluster.backbone.models.package import *
from initat.cluster.backbone.models.asset import *
from initat.cluster.backbone.models.user import *
from initat.cluster.backbone.models.background import *
from initat.cluster.backbone.models.hints import *
from initat.cluster.backbone.models.rms import *
from initat.cluster.backbone.models.partition import *
from initat.cluster.backbone.models.setup import *
from initat.cluster.backbone.models.graph import *
from initat.cluster.backbone.models.selection import *
from initat.cluster.backbone.models.kpi import *
from initat.cluster.backbone.models.license import *
from initat.cluster.backbone.models.status_history import *
from initat.cluster.backbone.models.dispatch import *
from initat.cluster.backbone.signals import UserChanged, GroupChanged, \
    BootsettingsChanged, VirtualDesktopUserSettingChanged, SensorThresholdChanged, \
    RoleChanged
from initat.cluster.backbone.models.asset import *
from initat.cluster.backbone.models.report import *
import initat.cluster.backbone.models.model_history


logger = logging.getLogger(__name__)


@receiver(request_started)
def bg_req_started(*args, **kwargs):
    # init number of background jobs created
    thread_local_obj.num_bg_jobs = 0


@receiver(request_finished)
def bg_req_finished(*args, **kwargs):
    # check number of background jobs and signal localhost
    if getattr(thread_local_obj, "num_bg_jobs", 0):
        thread_local_obj.num_bg_jobs = 0
        signal_localhost()


@receiver(UserChanged)
def user_changed(*args, **kwargs):
    _insert_bg_job("sync_users", kwargs["cause"], kwargs["user"])


@receiver(GroupChanged)
def group_changed(*args, **kwargs):
    _insert_bg_job("sync_users", kwargs["cause"], kwargs["group"])


@receiver(RoleChanged)
def role_changed(*args, **kwargs):
    _insert_bg_job("sync_users", kwargs["cause"], kwargs["role"])


@receiver(VirtualDesktopUserSettingChanged)
def vdus_changed(*args, **kwargs):
    _insert_bg_job("reload_virtual_desktop_dispatcher", kwargs["cause"], kwargs["vdus"])


@receiver(SensorThresholdChanged)
def sensor_threshold_changed(*args, **kwargs):
    _insert_bg_job("sync_sensor_threshold", kwargs["cause"], kwargs["sensor_threshold"])


@receiver(BootsettingsChanged)
def rcv_bootsettings_changed(*args, **kwargs):
    # not signal when bootserver is not set
    if kwargs["device"].bootserver_id:
        _insert_bg_job("change_bootsetting", kwargs["cause"], kwargs["device"])


def _insert_bg_job(cmd, cause, obj):
    if getattr(obj, "_no_bg_job", False):
        # used in boot_views
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
    if _local_pk and thread_local_middleware().user and isinstance(thread_local_middleware().user, user):
        create_bg_job(_local_pk, thread_local_middleware().user, cmd, cause, obj)
        # init if not already done
        if not hasattr(thread_local_obj, "num_bg_jobs"):
            thread_local_obj.num_bg_jobs = 1
        else:
            thread_local_obj.num_bg_jobs += 1
    else:
        if not _local_pk:
            logger.error("cannot identify local device")


def signal_localhost():
    # signal clusterserver running on localhost
    _sender = net_tools.zmq_connection("wf_server_notify")
    # only send no receive
    _sender.add_connection("tcp://localhost:8004", notify_command(), multi=True)
    # close connection / terminate context
    _sender.close()


class home_export_list(object):
    """ build home_export_list (dict) from DB, used in forms.py and ldap_modules.py """
    def __init__(self):
        exp_entries = device_config.objects.filter(
            Q(config__name__icontains="homedir") &
            Q(config__name__icontains="export") &
            Q(device__is_meta_device=False)
        ).prefetch_related(
            "config__config_str_set"
        ).select_related(
            "device",
            "device__domain_tree_node"
        )
        home_exp_dict = {}
        for entry in exp_entries:
            dev_name, dev_name_full, act_pk = (
                entry.device.name,
                entry.device.full_name,
                entry.pk,
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
                "create_automount_entries": True,
            }
            for c_str in entry.config.config_str_set.all():
                if c_str.name in home_exp_dict[act_pk]:
                    home_exp_dict[act_pk][c_str.name] = c_str.value
            for c_bool in entry.config.config_bool_set.all():
                if c_bool.name in home_exp_dict[act_pk]:
                    home_exp_dict[act_pk][c_bool.name] = c_bool.value
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


class device_rsync_config(models.Model):
    idx = models.AutoField(db_column="device_rsync_config_idx", primary_key=True)
    config = models.ForeignKey("config", db_column="new_config_id")
    device = models.ForeignKey("device")
    last_rsync_time = models.DateTimeField(null=True, blank=True)
    status = models.TextField()
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'device_rsync_config'


class log_status(models.Model):
    idx = models.AutoField(db_column="log_status_idx", primary_key=True)
    identifier = models.CharField(max_length=12, blank=True)
    log_level = models.IntegerField(null=True, blank=True)
    name = models.CharField(max_length=192, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'log_status'


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
            ",".join(
                [
                    short for short, attr_name in [
                        ("link", "prod_link"),
                        ("mem", "memory_test"),
                        ("loc", "boot_local"),
                        ("ins", "do_install"),
                        ("iso", "boot_iso"),
                        ("retain", "is_clean")
                    ] if getattr(self, attr_name)
                ]
            ),
            "(*)" if self.allow_boolean_modify else ""
        )

    class Meta:
        db_table = u'status'


class ConfigTreeNode(models.Model):
    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey("device", default=None)
    is_dir = models.BooleanField(default=False)
    is_link = models.BooleanField(default=False)
    parent = models.ForeignKey("ConfigTreeNode", null=True, default=None)
    # is an intermediate node is has not to be created
    intermediate = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)

    def __cmp__(self, other):
        if self.is_dir == other.is_dir:
            if self.writtenconfigfile.dest < other.writtenconfigfile.dest:
                return -1
            elif self.writtenconfigfile.dest > other.writtenconfigfile.dest:
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
        return "ConfigTreNode, {}".format(self.get_type_str())


class WrittenConfigFile(models.Model):
    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey("device")
    config_tree_node = models.OneToOneField("ConfigTreeNode", null=True, default=None)
    run_number = models.IntegerField(default=0)
    config = models.ManyToManyField("backbone.config")
    # config = models.CharField(max_length=255, blank=True)
    uid = models.IntegerField(default=0, blank=True)
    gid = models.IntegerField(default=0, blank=True)
    mode = models.IntegerField(default=0755, blank=True)
    dest_type = models.CharField(
        max_length=8,
        choices=(
            ("f", "file"),
            ("l", "link"),
            ("d", "directory"),
            ("e", "erase"),
            ("c", "copy"),
            ("i", "internal"),
        )
    )
    # source path
    source = models.TextField(default="")
    # destination path, relative to tree_node
    dest = models.TextField(default="")
    # error
    error_flag = models.BooleanField(default=False)
    # content, defaults to the empty string, base64-encoded for binary data
    content = models.TextField(blank=True, default="")
    binary = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)


class quota_capable_blockdevice(models.Model):
    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey("device")
    block_device_path = models.CharField(max_length=256, default="")
    # mount path, empty for not mounted
    mount_path = models.CharField(max_length=512, default="")
    # filesystemtype, link to partition_fs
    fs_type = models.ForeignKey("backbone.partition_fs")
    # size in Bytes
    size = models.BigIntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "qcb {} ({})".format(self.block_device_path, self.mount_path)


class DeleteRequest(models.Model):
    idx = models.AutoField(primary_key=True)
    obj_pk = models.IntegerField()
    model = models.TextField()
    delete_strategies = models.TextField(null=True, blank=True)

    class Meta:
        if db_limit_1():
            pass
        else:
            unique_together = ("obj_pk", "model")


# register models in history
def _register_models():
    models = (
        # user
        group, csw_permission, csw_object_permission, user, user_permission, user_object_permission,
        # net
        netdevice, net_ip, peer_information,
        # device
        device, device_group, device_config, device_variable, ComCapability, domain_tree_node,
        # config
        config, config_catalog, config_script, config_int, config_bool, config_str, config_blob,
        # category
        category,
        # mon
        mon_check_command, mon_check_command_special,
        # kpi
        Kpi, KpiDataSourceTuple,
        # lic
        License,
        # setup
        architecture, image, kernel,
        partition, partition_disc, partition_fs, partition_table, sys_partition,
    )
    for model in models:
        model_history.icsw_register(model)

_register_models()
