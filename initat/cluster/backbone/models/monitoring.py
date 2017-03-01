# Copyright (C) 2014-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-server
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" database definitions for monitoring """

import enum
import json
import re
import uuid
from enum import Enum

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, signals
from django.dispatch import receiver

from initat.cluster.backbone.models.functions import check_empty_string, check_integer
from initat.md_config_server.base_config.mon_base_config import StructuredContentEmitter, \
    build_safe_name
from initat.tools import logging_tools

__all__ = [
    "mon_host_cluster",
    "mon_service_cluster",
    "host_check_command",
    "mon_check_command",
    "mon_contact",
    "mon_notification",
    "mon_contactgroup",
    "mon_device_templ",
    "mon_device_esc_templ",
    "mon_host_dependency_templ",
    "mon_host_dependency",
    "mon_service_dependency_templ",
    "mon_service_dependency",
    "mon_ext_host",
    "mon_period",
    "mon_service_templ",
    "mon_service_esc_templ",

    # distribution models

    "mon_dist_master",
    "mon_dist_slave",
    "monitoring_hint",
    # "mon_check_command_special",

    # trace

    "MonHostTrace",  # monitoring trace for speedup
    "MonHostTraceGeneration",   # monitoring trace generation

    # unreachable info

    "mon_build_unreachable",  # track unreachable devices
    "SpecialGroupsEnum",

    # syslog check object

    "SyslogCheck",

    # display pipes
    "MonDisplayPipeSpec",

    # Enum
    "MonCheckCommandSystemNames",
    "DBStructuredMonBaseConfig",
]


class SpecialGroupsEnum(enum.Enum):
    unspec = "Unspecified"
    hardware = "Hardware"
    hardware_disc = "Hardware / Disc"
    system = "System"
    system_disc = "System / Disc"
    system_net = "System / Network"


class MonHostTraceGeneration(models.Model):
    idx = models.AutoField(primary_key=True)
    fingerprint = models.CharField(max_length=255, default="")
    # number of edges
    edges = models.IntegerField(default=0)
    # number of nodes
    nodes = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)


class MonHostTrace(models.Model):
    idx = models.AutoField(primary_key=True)
    # generation
    generation = models.ForeignKey("backbone.MonHostTraceGeneration", null=True)
    device = models.ForeignKey("backbone.device")
    # fingerprint of device netdevices
    dev_netdevice_fp = models.CharField(max_length=128, default="", db_index=True)
    # fingerprint of server netdevices
    srv_netdevice_fp = models.CharField(max_length=128, default="", db_index=True)
    traces = models.TextField(default="")
    date = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def get_fingerprint(net_idxs):
        return ":".join(
            [
                "{:d}".format(_idx) for _idx in net_idxs
            ]
        )

    @staticmethod
    def create_trace(gen, dev, dev_fp, srv_fp, traces):
        new_tr = MonHostTrace(
            generation=gen,
            device=dev,
            dev_netdevice_fp=dev_fp,
            srv_netdevice_fp=srv_fp,
        )
        new_tr.set_trace(traces)
        new_tr.save()
        return new_tr

    @staticmethod
    def dump_trace(traces):
        return json.dumps(traces)

    @staticmethod
    def load_trace(traces):
        return json.loads(traces)

    def set_trace(self, traces):
        self.traces = MonHostTrace.dump_trace(traces)

    def get_trace(self):
        return MonHostTrace.load_trace(self.traces)

    def match(self, traces):
        return self.traces == MonHostTrace.dump_trace(traces)

    def __str__(self):
        return "MHT for {}".format(str(self.device))


class mon_dist_base(models.Model):
    # start of build
    config_build_start = models.DateTimeField(default=None, null=True)
    # end of build
    config_build_end = models.DateTimeField(default=None, null=True)
    # version of of relayer (== icsw)
    relayer_version = models.CharField(max_length=128, default="")
    # version of monitoring daemon (== icinga)
    mon_version = models.CharField(max_length=128, default="")
    # version of livestatus version
    livestatus_version = models.CharField(max_length=128, default="")
    # total build start
    build_start = models.DateTimeField(default=None, null=True)
    # total build end
    build_end = models.DateTimeField(default=None, null=True)
    # number of devices
    num_devices = models.IntegerField(default=0)
    # unroutable devices, always zero for slaves
    unreachable_devices = models.IntegerField(default=0)
    # full build, defaults to True
    full_build = models.BooleanField(default=True)
    # creation date
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


# distribution models, one per run
class mon_dist_slave(mon_dist_base):
    idx = models.AutoField(primary_key=True)
    mon_dist_master = models.ForeignKey("backbone.mon_dist_master")
    device = models.ForeignKey("backbone.device")
    # start of first sync
    sync_start = models.DateTimeField(default=None, null=True)
    # end of last sync
    sync_end = models.DateTimeField(default=None, null=True)
    # number of distribute runs (==sync)
    num_runs = models.IntegerField(default=0)
    # files transfered / number of transfered commands
    num_files = models.IntegerField(default=0)
    num_transfers = models.IntegerField(default=0)
    # pure data
    size_data = models.IntegerField(default=0)
    # with overhead
    size_raw = models.IntegerField(default=0)

    class Meta:
        verbose_name = "Config builds as slave"


class mon_dist_master(mon_dist_base):
    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey("backbone.device")
    version = models.IntegerField(default=0)

    class Meta:
        ordering = ("-idx",)
        verbose_name = "Config builds as master"


class mon_build_unreachable(models.Model):
    idx = models.AutoField(primary_key=True)
    mon_dist_master = models.ForeignKey("backbone.mon_dist_master")
    device_pk = models.IntegerField(default=0)
    device_name = models.CharField(max_length=256, default="")
    devicegroup_name = models.CharField(max_length=256, default="")
    date = models.DateTimeField(auto_now_add=True)

    class ICSW_Meta:
        backup = False


class mon_host_cluster(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(max_length=128, blank=False, null=False, unique=True)
    description = models.CharField(max_length=255, default="")
    main_device = models.ForeignKey("backbone.device", related_name="main_mon_host_cluster")
    mon_service_templ = models.ForeignKey("backbone.mon_service_templ")
    devices = models.ManyToManyField("backbone.device", related_name="devs_mon_host_cluster")
    warn_value = models.IntegerField(default=0)
    error_value = models.IntegerField(default=1)
    # True for user editable (user created) clusters
    user_editable = models.BooleanField(default=True)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Host Cluster"


@receiver(signals.pre_save, sender=mon_host_cluster)
def mon_host_cluster_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        check_empty_string(cur_inst, "name")
        for attr_name, min_val, max_val in [
            ("warn_value", 0, 128),
            ("error_value", 0, 128)
        ]:
            check_integer(cur_inst, attr_name, min_val=min_val, max_val=max_val)


class mon_service_cluster(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(max_length=128, blank=False, null=False, unique=True)
    description = models.CharField(max_length=255, default="")
    main_device = models.ForeignKey("backbone.device", related_name="main_mon_service_cluster")
    mon_service_templ = models.ForeignKey("backbone.mon_service_templ")
    devices = models.ManyToManyField("backbone.device", related_name="devs_mon_service_cluster")
    mon_check_command = models.ForeignKey("backbone.mon_check_command")
    warn_value = models.IntegerField(default=0)
    error_value = models.IntegerField(default=1)
    # True for user editable (user created) clusters
    user_editable = models.BooleanField(default=True)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Service Cluster"


@receiver(signals.pre_save, sender=mon_service_cluster)
def mon_service_cluster_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        check_empty_string(cur_inst, "name")
        for attr_name, min_val, max_val in [
            ("warn_value", 0, 128),
            ("error_value", 0, 128)
        ]:
            check_integer(cur_inst, attr_name, min_val=min_val, max_val=max_val)


class host_check_command(models.Model):
    idx = models.AutoField(db_column="ng_check_command_idx", primary_key=True)
    name = models.CharField(max_length=64, unique=True, blank=False, null=False)
    command_line = models.CharField(max_length=128, unique=True, blank=False, null=False)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return "hcc_{}".format(self.name)


class MonCheckCommandSystemNameDef(object):
    def __init__(self, name, uuid, description=""):
        self.name = name
        self.uuid = uuid
        self.description = description


class MonCheckCommandSystemNames(Enum):
    # process commands
    process_service_perfdata_file = MonCheckCommandSystemNameDef(
        'process-service-perfdata-file',
        '1a9ffb17-e7be-4146-b058-b9e2d1e6fb21'
    )
    process_host_perfdata_file = MonCheckCommandSystemNameDef(
        'process-host-perfdata-file',
        'f136418c-1875-4b62-a318-e24becd0dc0b'
    )
    # oc{h,s}p commands
    ochp_command = MonCheckCommandSystemNameDef(
        'ochp-command',
        'fc81e360-3a79-4651-b4b5-b4f9e591a2b3',
    )
    ocsp_command = MonCheckCommandSystemNameDef(
        'ocsp-command',
        '2fe49af7-d227-412e-8b22-9edc5c321690',
    )
    # cluster commands
    check_service_cluster = MonCheckCommandSystemNameDef(
        'check_service_cluster',
        'bfaf1ef9-1733-456f-a495-e64aa90bfd2a',
    )
    check_host_cluster = MonCheckCommandSystemNameDef(
        'check_host_cluster',
        'd4e32e3c-88ee-4a23-ae71-21de81e2bda1',
    )
    # notify commands
    dummy_notify = MonCheckCommandSystemNameDef(
        'dummy-notify',
        'd201b06f-a8ef-4096-a461-da35302e9c97',
        "Dummy notifier (does nothing)",
    )
    host_notify_by_mail = MonCheckCommandSystemNameDef(
        'host-notify-by-mail',
        '83512022-a558-4e50-9eb1-9224ae9a0379',
        "Notify users about Host issues via Mail",
    )
    host_notify_by_sms = MonCheckCommandSystemNameDef(
        'host-notify-by-sms',
        '72d86436-86fb-4157-a1f1-5fec91de102d',
        "Notify users about Host issues via SMS",
    )
    service_notify_by_mail = MonCheckCommandSystemNameDef(
        'service-notify-by-mail',
        '6a693498-4649-40e9-bb4c-159724b9ec49',
        "Notify users about Service issues via Mail",
    )
    service_notify_by_sms = MonCheckCommandSystemNameDef(
        'service-notify-by-sms',
        'b7a17953-de30-49a4-82ee-1d02f1158cb5',
        "Notify users about Serice issues via SMS",
    )


class mon_check_command(models.Model):
    idx = models.AutoField(db_column="ng_check_command_idx", primary_key=True)
    # must be empty for system-commands (also for shadow commands)
    config_rel = models.ManyToManyField("backbone.config", related_name="mcc_rel", blank=True)
    mon_service_templ = models.ForeignKey("backbone.mon_service_templ", null=True, blank=True)
    # UUID
    uuid = models.CharField(default="", max_length=64, blank=True)
    # parent UUID, value of the UUID this check_command was copied from
    parent_uuid = models.CharField(default="", max_length=64, blank=True)
    # only unique per config, shown on icinga page
    name = models.CharField(max_length=192)
    # unique name, this name is local to each installation and will be changed
    # on import if necessary
    unique_name = models.CharField(default="", max_length=255)
    # for mon_check_special_command this is empty
    command_line = models.CharField(max_length=765, default="")
    # description, only used for frontend (not for core monitoring)
    description = models.CharField(max_length=512, blank=True)
    # device = models.ForeignKey("backbone.device", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    enable_perfdata = models.BooleanField(default=False)
    volatile = models.BooleanField(default=False)
    # categories for this check
    categories = models.ManyToManyField("backbone.category", blank=True)
    # devices to assign directly
    devices = models.ManyToManyField("backbone.device", related_name="mcc_devices", blank=True)
    # handling of mcc selection with meta and config-related selection:
    # - options for meta devices:
    #   - via config_rel, devices
    #     - (0) - none set: not set
    #     - (1) - any config_rel set: use check downstream (towards devices)
    #     - (0) - any config_rel and via devices set: do not use check
    #     - (1) - no config_rel but via devices set: use check downstream (towards devices)
    # - options for real devices
    #   - via meta, config_rel, devices
    #     - if any meta config_rel is set no device-local config_rel should be set
    #     - if any meta devices rel is set no device-local devices rel should be set
    #     - the same rules apply as above but the meta settings are also taken into account
    # event handler settings
    is_event_handler = models.BooleanField(default=False)
    event_handler = models.ForeignKey("self", null=True, default=None, blank=True)
    event_handler_enabled = models.BooleanField(default=True)
    # internal (==system) command
    system_command = models.BooleanField(default=False)
    # is an active check
    is_active = models.BooleanField(default=True)
    # is enabled
    enabled = models.BooleanField(default=True)
    # fields for special commands
    is_special_command = models.BooleanField(default=False)
    # is container for other special commands (all SNMP checks for instance)
    is_special_meta = models.BooleanField(default=False)
    # comes from / is linked to a json definition
    json_linked = models.BooleanField(default=False)
    # for commands from a meta-command
    special_parent = models.ForeignKey("self", null=True, related_name="special_child")

    def get_configured_device_pks(self):
        if self.config_rel.all().count():
            return sum(
                [
                    [
                        dev_conf.device_id for dev_conf in _config.device_config_set.all()
                    ] for _config in self.config_rel.all()
                ],
                []
            ) + list(
                self.devices.all().values_list("idx", flat=True)
            )
        else:
            return []

    def get_object_type(self):
        return "mon"

    @property
    def command_type(self):
        if self.system_command:
            return "pure system"
        else:
            return "normal"

    class Meta:
        db_table = 'ng_check_command'
        # unique_together = (("name", "config"))
        verbose_name = "Check command"

    class ICSW_Meta:
        permissions = (
            ("setup_monitoring", "Change monitoring settings", False),
            ("show_monitoring_dashboard", "Show monitoring dashboard", False),
            ("create_config", "Create monitoring config", False),
            ("redirect_to_icinga", "Redirect to Icinga backend", False),
        )
        fk_ignore_list = [
            "mon_icinga_log_raw_service_alert_data",
            "mon_icinga_log_raw_service_flapping_data",
            "mon_icinga_log_raw_service_notification_data",
            "mon_icinga_log_aggregated_service_data",
            "mon_icinga_log_raw_service_downtime_data",
        ]

    @property
    def obj_type(self):
        return "command"

    def __str__(self):
        return "MonCheckCommand '{}'".format(self.name or "empty")


class DBStructuredMonBaseConfig(mon_check_command, StructuredContentEmitter):
    # proxy class to interface with md-config-server
    # every command like
    # - mon_check_command
    # - notificaton
    # has a mon_check_command entries, only the first type has system_command=False set

    @classmethod
    def get_system_check_command(cls, **kwargs):
        # some kind of simple factory ...
        _create = kwargs.pop("create")
        # _special = kwargs.pop("special_command", None)
        _changed = False
        try:
            # create a system command from the given (kw)args
            _obj = cls.objects.get(Q(system_command=True) & Q(name=kwargs["name"]))
        except cls.DoesNotExist:
            _obj = None
        if _obj is None:
            if _create:
                # simply a system-command from a non-special command
                _obj = cls(
                    name=kwargs["name"],
                    system_command=True,
                )
                _changed = True
                _obj.generate_md_com_line(None, False)
            else:
                # this should never happen, trigger an error
                _obj = None
        for key, value in kwargs.items():
            # set the values from the kwargs
            if getattr(_obj, key) != value:
                setattr(_obj, key, value)
                _changed = True
        if _obj:
            if not _obj.command_line.strip():
                # fix command line
                _obj.command_line = "/bin/true"
                _changed = True
        if _changed:
            # save obj if something has changed
            _obj.save()
        return _obj

    @classmethod
    def parse_commandline(cls, com_line):
        """
        parses command line, also builds argument lut
        lut format: commandline switch -> ARG#
        list format : ARG#, ARG#, ...
        """
        """
        handle the various input formats:

        ${ARG#:var_name:default}
        ${ARG#:var_name:default}$
        ${ARG#:*var_name}
        ${ARG#:*var_name}$
        ${ARG#:default}
        ${ARG#:default}$
        $ARG#$

        """
        _num_args, _default_values = (0, {})
        arg_lut, arg_list = ({}, [])
        log_lines = []
        if not com_line.strip():
            com_line = "/bin/true"
            log_lines.append(
                (
                    "commandline is empty, replacing with '{}'".format(com_line),
                    logging_tools.LOG_LEVEL_ERROR
                )
            )
        com_re = re.compile(
            "".join(
                [
                    "^(?P<pre_text>.*?)",
                    "((\${ARG(?P<arg_num_1>\d+):(((?P<var_name>[^:^}]+?)\:(?P<default_vn>[^}]+?)}\$*)|",
                    "(?P<default>[^}]+?)}\$*))|(\$ARG(?P<arg_num_2>\d+)\$))+",
                    "(?P<post_text>.*)$",
                ]
            )
        )
        cur_line = com_line
        # where to start the match to avoid infinite loop
        s_idx = 0
        while True:
            cur_m = com_re.match(cur_line[s_idx:])
            if cur_m:
                m_dict = cur_m.groupdict()
                # check for -X or --Y switch
                prev_part = m_dict["pre_text"].strip().split()
                if prev_part and prev_part[-1].startswith("-"):
                    prev_part = prev_part[-1]
                else:
                    prev_part = None
                if m_dict["arg_num_2"] is not None:
                    # short form
                    arg_name = "ARG{}".format(m_dict["arg_num_2"])
                else:
                    arg_name = "ARG{}".format(m_dict["arg_num_1"])
                    if m_dict["var_name"]:
                        _default_values[arg_name] = (m_dict["var_name"], m_dict["default_vn"])
                    elif m_dict["default"]:
                        _default_values[arg_name] = m_dict["default"]
                pre_text, post_text = (
                    m_dict["pre_text"] or "",
                    m_dict["post_text"] or ""
                )
                cur_line = "{}{}${}${}".format(
                    cur_line[:s_idx],
                    pre_text,
                    arg_name,
                    post_text
                )
                s_idx += len(pre_text) + len(arg_name) + 2
                if prev_part:
                    arg_lut[prev_part] = arg_name
                else:
                    arg_list.append(arg_name)
                _num_args += 1
            else:
                break
        _parsed_com_line = cur_line
        if not com_line.strip():
            log_lines.append("Empty commandline", logging_tools.LOG_LEVEL_CRITICAL)
        if com_line == _parsed_com_line:
            log_lines.append("commandline in/out is '{}'".format(com_line))
        else:
            log_lines.append("commandline in     is '{}'".format(com_line))
            log_lines.append("commandline out    is '{}'".format(_parsed_com_line))
        if arg_lut:
            log_lines.append(
                "lut : {}; {}".format(
                    logging_tools.get_plural("key", len(arg_lut)),
                    ", ".join(
                        ["'{}' => '{}'".format(key, value) for key, value in arg_lut.items()]
                    )
                )
            )
        if arg_list:
            log_lines.append(
                "list: {}; {}".format(
                    logging_tools.get_plural("item", len(arg_list)),
                    ", ".join(arg_list)
                )
            )
        return {
                   "arg_lut": arg_lut,
                   "arg_list": arg_list,
                   "parsed_com_line": _parsed_com_line,
                   "num_args": _num_args,
                   "default_values": _default_values,
               }, log_lines
        # self.__arg_lut, self.__arg_list = (arg_lut, arg_list)

    def keys(self):
        return ["command_line", "command_name"]

    def get(self, key, default=None):
        return getattr(self, key, default)

    def get_description(self):
        return self.name

    def __getitem__(self, key):
        # for config generation
        if key == "command_name":
            # print("G", self.idx, self.unique_name)
            return [self.unique_name]
        elif key == "command_line":
            return [self.__md_com_line]
        else:
            raise KeyError("key '{}' not supported for __getitem__".format(key))

    def generate_md_com_line(self, log_com: callable, safe_description: bool):
        if safe_description:
            self.__description = build_safe_name(self.name)
        else:
            self.__description = self.name
        # if self.mon_check_command_special_id:
        #    # is a user-specified link to a mon_check_command_special
        #    arg_info, log_lines = DBStructuredMonBaseConfig.parse_commandline(
        #        self.mon_check_command_special.command_line
        #    )
        # else:
        arg_info, log_lines = DBStructuredMonBaseConfig.parse_commandline(
            self.command_line
        )
        # print arg_info, log_lines
        self.__arg_lut = arg_info["arg_lut"]
        self.__arg_list = arg_info["arg_list"]
        self.__num_args = arg_info["num_args"]
        self.__default_values = arg_info["default_values"]
        self.__md_com_line = arg_info["parsed_com_line"]
        if log_com:
            log_com(
                "command '{}' maps to '{}'".format(
                    self.name,
                    self.unique_name,
                )
            )
            for _line in log_lines:
                if isinstance(_line, tuple):
                    _line, _level = _line
                else:
                    _level = logging_tools.LOG_LEVEL_OK
                log_com("[cc {}] {}".format(self.name, _line), _level)

    @property
    def arg_ll(self) -> tuple:
        """
        returns lut and list
        """
        return (self.__arg_lut, self.__arg_list)

    @property
    def servicegroup_names(self):
        return [cur_cat.full_name for cur_cat in self.categories.all()]

    @property
    def servicegroup_pks(self):
        return [cur_cat.pk for cur_cat in self.categories.all()]

    def get_template(self, default: str) -> str:
        if self.mon_service_templ_id:
            return self.mon_service_templ.name
        else:
            return default

    def correct_argument_list(self, arg_temp, dev_variables):
        out_list = []
        for arg_name in arg_temp.argument_names:
            value = arg_temp[arg_name]
            if arg_name in self.__default_values and not value:
                dv_value = self.__default_values[arg_name]
                if isinstance(dv_value, tuple):
                    # var_name and default_value
                    var_name = self.__default_values[arg_name][0]
                    if var_name in dev_variables:
                        value = dev_variables[var_name]
                    else:
                        value = self.__default_values[arg_name][1]
                else:
                    # only default_value
                    value = self.__default_values[arg_name]
            if isinstance(value, int):
                out_list.append("{:d}".format(value))
            else:
                out_list.append(value)
        return out_list

    class Meta:
        proxy = True


def _check_unique_name(cur_inst: object) -> bool:
    if not cur_inst.unique_name:
        unique_name = cur_inst.name
    else:
        unique_name = cur_inst.unique_name
    _other_uniques = mon_check_command.objects.all().exclude(Q(idx=cur_inst.idx)).values_list("unique_name", flat=True)
    if cur_inst.system_command:
        if cur_inst.idx and cur_inst.config_rel.all().count():
            raise ValidationError(
                "{} mon_check_command ({}) should not be linked to any config".format(
                    cur_inst.command_type,
                    cur_inst.name,
                )
            )
        # pure system commands need unique names and have no possibility to alter their names
        if unique_name in _other_uniques:
            # print("Q", cur_inst.idx)
            # print(list(_other_uniques))
            raise ValidationError(
                "MonCheckName for {} '{}' (pk={}) already used, please fix ...".format(
                    cur_inst.command_type,
                    cur_inst.name,
                    cur_inst.idx,
                )
            )
    while unique_name in _other_uniques:
        _parts = unique_name.split("_")
        if _parts[-1].isdigit():
            # increase unique counter
            unique_name = "_".join(_parts[:-1] + ["{:d}".format(int(_parts[-1]) + 1)])
        else:
            unique_name = "{}_1".format(unique_name)
    _changed = cur_inst.unique_name != unique_name
    cur_inst.unique_name = unique_name
    return _changed


# the receiver signals for mon_check_commands are a little complex because we
# have two Django-Models covering the same Databasemodel

@receiver(signals.post_init, sender=mon_check_command)
def mon_check_command_post_init(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        # only check uniqueness on save or for load of already defined checks without unique_name defined
        if cur_inst.idx and not cur_inst.unique_name and _check_unique_name(cur_inst):
            cur_inst.save()


@receiver(signals.post_init, sender=DBStructuredMonBaseConfig)
def dbstructuredmonbaseconfig_post_init(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        # only check uniqueness on save or for load of already defined checks without unique_name defined
        if cur_inst.idx and not cur_inst.unique_name and _check_unique_name(cur_inst):
            cur_inst.save()


def _mcc_pre_save(cur_inst):
    # cur_inst.is_special_command = True if special_re.match(cur_inst.name) else False
    if not cur_inst.uuid:
        cur_inst.uuid = str(uuid.uuid4())
    if not cur_inst.system_command:
        try:
            _ = MonCheckCommandSystemNames[cur_inst.name]
        except KeyError:
            pass
        else:
            raise ValidationError("'{}' is a reserved system command name".format(cur_inst.name))
    if not cur_inst.name:
        raise ValidationError("name is empty")
    # if not cur_inst.command_line:
    #     raise ValidationError("command_line is empty")
    if not cur_inst.is_event_handler:
        mc_refs = cur_inst.mon_check_command_set.all()
        if len(mc_refs):
            raise ValidationError("still referenced by {}".format(logging_tools.get_plural("check_command", len(mc_refs))))
    # specials can not be event_handlers
    if cur_inst.is_special_command and cur_inst.is_event_handler:
        raise ValidationError("special command not allowed as event handler")
    if cur_inst.is_event_handler and cur_inst.event_handler_id:
        raise ValidationError("cannot be an event handler and reference to another event handler")
    _check_unique_name(cur_inst)


@receiver(signals.pre_save, sender=mon_check_command)
def mon_check_command_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        _mcc_pre_save(kwargs["instance"])


@receiver(signals.pre_save, sender=DBStructuredMonBaseConfig)
def dbstructuredmonbaseconfig_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        _mcc_pre_save(kwargs["instance"])


def _mcc_post_save(cur_inst):
    # if cur_inst.idx
    if cur_inst.idx and cur_inst.config_rel.all().count() and not cur_inst.system_command:
        # remove all associated devices
        cur_inst.devices.clear()


@receiver(signals.pre_save, sender=mon_check_command)
def mon_check_command_post_save(sender, **kwargs):
    if "instance" in kwargs:
        _mcc_post_save(kwargs["instance"])


@receiver(signals.pre_save, sender=DBStructuredMonBaseConfig)
def dbstructuredmonbaseconfig_post_save(sender, **kwargs):
    if "instance" in kwargs:
        _mcc_post_save(kwargs["instance"])


class mon_contact(models.Model):
    idx = models.AutoField(db_column="ng_contact_idx", primary_key=True)
    user = models.ForeignKey("backbone.user")
    snperiod = models.ForeignKey("backbone.mon_period", related_name="service_n_period", verbose_name="service period")
    hnperiod = models.ForeignKey("backbone.mon_period", related_name="host_n_period", verbose_name="host period")
    snrecovery = models.BooleanField(default=False, verbose_name="Notify on service recovery")
    sncritical = models.BooleanField(default=False, verbose_name="Notify on service critical")
    snwarning = models.BooleanField(default=False, verbose_name="Notify on service warning")
    snunknown = models.BooleanField(default=False, verbose_name="Notify on service unknown")
    sflapping = models.BooleanField(default=False, verbose_name="Notify on service flapping")
    splanned_downtime = models.BooleanField(default=False, verbose_name="Notify on service planned downtime")
    hnrecovery = models.BooleanField(default=False, verbose_name="Notify on host recovery")
    hndown = models.BooleanField(default=False, verbose_name="Notify on host down")
    hnunreachable = models.BooleanField(default=False, verbose_name="Notify on host unreachable")
    hflapping = models.BooleanField(default=False, verbose_name="Notify on host flapping")
    hplanned_downtime = models.BooleanField(default=False, verbose_name="Notify on host planned downtime")
    date = models.DateTimeField(auto_now_add=True)
    notifications = models.ManyToManyField("backbone.mon_notification", blank=True)
    mon_alias = models.CharField(max_length=64, default="", verbose_name="alias", blank=True)

    def get_user_name(self):
        return "{} ({} {})".format(
            self.user.login,
            self.user.first_name,
            self.user.last_name,
        )

    def __str__(self):
        return str(self.user)

    class Meta:
        db_table = 'ng_contact'


@receiver(signals.pre_save, sender=mon_contact)
def mon_contact_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        used_user_ids = mon_contact.objects.exclude(Q(pk=cur_inst.pk)).values_list("user", flat=True)
        if cur_inst.user_id in used_user_ids:
            raise ValidationError("user already in used by mon_contact")


class mon_notification(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(max_length=128, blank=False, unique=True)
    channel = models.CharField(max_length=8, choices=[
        ("mail", "E-Mail"),
        ("sms", "SMS")], blank=False)
    not_type = models.CharField(
        max_length=8,
        choices=[
            ("host", "Host"),
            ("service", "Service")
        ],
        blank=False,
        verbose_name="Notification type"
    )
    subject = models.CharField(max_length=140, blank=True)
    content = models.TextField(default="", blank=False)
    enabled = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return "{} ({} via {})".format(
            self.name,
            self.not_type,
            self.channel,
        )


@receiver(signals.pre_save, sender=mon_notification)
def mon_notification_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]


"""
connection between the various nagios / icinage notification objects:

device -> mon_device_templ -> mon_service_templ
       -> mon_device_esc_templ -> mon_service_esc_templ

contactgroup -> mon_service_templ
             -> mon_service_esc_templ
             -> members
"""


class mon_contactgroup(models.Model):
    idx = models.AutoField(db_column="ng_contactgroup_idx", primary_key=True)
    name = models.CharField(max_length=192, unique=True)
    alias = models.CharField(max_length=255, blank=True, default="")
    date = models.DateTimeField(auto_now_add=True)
    device_groups = models.ManyToManyField("device_group", blank=True)
    members = models.ManyToManyField("backbone.mon_contact", blank=True)
    service_templates = models.ManyToManyField("backbone.mon_service_templ", blank=True)
    service_esc_templates = models.ManyToManyField("backbone.mon_service_esc_templ", blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'ng_contactgroup'


@receiver(signals.pre_save, sender=mon_contactgroup)
def mon_contactgroup_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        check_empty_string(cur_inst, "name")


class mon_device_templ(models.Model):
    idx = models.AutoField(db_column="ng_device_templ_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    mon_service_templ = models.ForeignKey("backbone.mon_service_templ")
    host_check_command = models.ForeignKey("backbone.host_check_command", null=True)
    # check interval
    check_interval = models.IntegerField(default=1)
    # retry interval
    retry_interval = models.IntegerField(default=1)
    # max_check_attempts
    max_attempts = models.IntegerField(null=True, blank=True, default=1)
    # notification interval
    ninterval = models.IntegerField(null=True, blank=True, default=1)
    not_period = models.ForeignKey("backbone.mon_period", related_name="dev_notify_period")
    # monitoring period
    mon_period = models.ForeignKey("backbone.mon_period", related_name="dev_check_period")
    # Notificiation Flags
    nrecovery = models.BooleanField(default=False, verbose_name="Notify on recovery")
    ndown = models.BooleanField(default=False, verbose_name="Notify when down")
    nunreachable = models.BooleanField(default=False, verbose_name="Notify when unreachable")
    nflapping = models.BooleanField(default=False, verbose_name="Notify when flapping")
    nplanned_downtime = models.BooleanField(default=False, verbose_name="Notify for planned downtime")
    is_default = models.BooleanField(default=False)
    low_flap_threshold = models.IntegerField(default=0)
    high_flap_threshold = models.IntegerField(default=0)
    flap_detection_enabled = models.BooleanField(default=False)
    flap_detect_up = models.BooleanField(default=True)
    flap_detect_down = models.BooleanField(default=False)
    flap_detect_unreachable = models.BooleanField(default=False)
    # freshness checks
    check_freshness = models.BooleanField(default=False)
    freshness_threshold = models.IntegerField(default=60)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'ng_device_templ'


@receiver(signals.pre_save, sender=mon_device_templ)
def mon_device_templ_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not cur_inst.name.strip():
            raise ValidationError("name must not be zero")
        for attr_name, min_val, max_val in [
            ("max_attempts", 1, 10),
            ("ninterval", 0, 60 * 24 * 7),
            ("low_flap_threshold", 0, 100),
            ("high_flap_threshold", 0, 100),
            ("check_interval", 1, 60),
            ("retry_interval", 1, 60),
            ("freshness_threshold", 10, 24 * 3600 * 365),
        ]:
            check_integer(cur_inst, attr_name, min_val=min_val, max_val=max_val)


class mon_device_esc_templ(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    first_notification = models.IntegerField(default=1)
    last_notification = models.IntegerField(default=1)
    mon_service_esc_templ = models.ForeignKey("backbone.mon_service_esc_templ")
    ninterval = models.IntegerField(default=1)
    esc_period = models.ForeignKey("backbone.mon_period")
    nrecovery = models.BooleanField(default=False, verbose_name="Notify on recovery")
    ndown = models.BooleanField(default=False, verbose_name="Notify when down")
    nunreachable = models.BooleanField(default=False, verbose_name="Notify when unreachable")
    nflapping = models.BooleanField(default=False, verbose_name="Notify when flapping")
    nplanned_downtime = models.BooleanField(default=False, verbose_name="Notify on planned downtime")
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


@receiver(signals.pre_save, sender=mon_device_esc_templ)
def mon_device_esc_templ_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not cur_inst.name.strip():
            raise ValidationError("name must not be empty")
        for attr_name, min_val, max_val in [
            ("first_notification", 1, 10),
            ("last_notification", 1, 10),
            ("ninterval", 0, 60 * 24 * 7)
        ]:
            check_integer(cur_inst, attr_name, min_val=min_val, max_val=max_val)


class mon_host_dependency_templ(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    inherits_parent = models.BooleanField(default=False)
    priority = models.IntegerField(default=0)
    efc_up = models.BooleanField(default=False)
    efc_down = models.BooleanField(default=True)
    efc_unreachable = models.BooleanField(default=True)
    efc_pending = models.BooleanField(default=False)
    nfc_up = models.BooleanField(default=False)
    nfc_down = models.BooleanField(default=True)
    nfc_unreachable = models.BooleanField(default=True)
    nfc_pending = models.BooleanField(default=False)
    dependency_period = models.ForeignKey("backbone.mon_period")
    date = models.DateTimeField(auto_now_add=True)

    @property
    def execution_failure_criteria(self):
        return ",".join(
            [
                short for short, _long in [
                    ("o", "up"), ("d", "down"), ("u", "unreachable"), ("p", "pending")
                ] if getattr(self, "efc_{}".format(_long))
            ]
        ) or "n"

    @property
    def notification_failure_criteria(self):
        return ",".join(
            [
                short for short, _long in [
                    ("o", "up"), ("d", "down"), ("u", "unreachable"), ("p", "pending")
                ] if getattr(self, "nfc_{}".format(_long))
            ]
        ) or "n"

    def __str__(self):
        return self.name

    class Meta:
        ordering = ("name",)


@receiver(signals.pre_save, sender=mon_host_dependency_templ)
def mon_host_dependency_templ_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        check_integer(cur_inst, "priority", min_val=-128, max_val=128)
        if not cur_inst.name.strip():
            raise ValidationError("name must not be empty")


class mon_host_dependency(models.Model):
    idx = models.AutoField(primary_key=True)
    devices = models.ManyToManyField("device", related_name="mhd_devices", blank=True)
    dependent_devices = models.ManyToManyField("device", related_name="mhd_dependent_devices")
    mon_host_dependency_templ = models.ForeignKey("backbone.mon_host_dependency_templ")
    mon_host_cluster = models.ForeignKey("backbone.mon_host_cluster", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        return True if (self.mon_host_dependency_templ_id) else False

    def get_id(self, devices=None, dependent_devices=None):
        # returns an unique ID
        return "{{{:d}:{:d}:[{}]:[{}]}}".format(
            self.mon_host_dependency_templ_id or 0,
            self.mon_host_cluster_id or 0,
            ",".join(["{:d}".format(val) for val in sorted(
                [
                    sub_dev.pk for sub_dev in (devices if devices is not None else self.devices.all())
                ]
            )]),
            ",".join(["{:d}".format(val) for val in sorted(
                [
                    sub_dev.pk for sub_dev in (dependent_devices if dependent_devices is not None else self.dependent_devices.all())
                ]
            )]),
        )

    def feed_config(self, conf):
        conf["inherits_parent"] = "1" if self.mon_host_dependency_templ.inherits_parent else "0"
        conf["execution_failure_criteria"] = self.mon_host_dependency_templ.execution_failure_criteria
        conf["notification_failure_criteria"] = self.mon_host_dependency_templ.notification_failure_criteria
        conf["dependency_period"] = self.mon_host_dependency_templ.dependency_period.name


class mon_service_dependency_templ(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    inherits_parent = models.BooleanField(default=False)
    priority = models.IntegerField(default=0)
    efc_ok = models.BooleanField(default=False)
    efc_warn = models.BooleanField(default=True)
    efc_unknown = models.BooleanField(default=True)
    efc_critical = models.BooleanField(default=False)
    efc_pending = models.BooleanField(default=False)
    nfc_ok = models.BooleanField(default=False)
    nfc_warn = models.BooleanField(default=True)
    nfc_unknown = models.BooleanField(default=True)
    nfc_critical = models.BooleanField(default=False)
    nfc_pending = models.BooleanField(default=False)
    dependency_period = models.ForeignKey("backbone.mon_period")
    date = models.DateTimeField(auto_now_add=True)

    @property
    def execution_failure_criteria(self):
        return ",".join(
            [
                short for short, _long in [
                    ("o", "ok"), ("w", "warn"), ("u", "unknown"), ("c", "critical"), ("p", "pending")
                ] if getattr(self, "efc_{}".format(_long))
            ]) or "n"

    @property
    def notification_failure_criteria(self):
        return ",".join(
            [
                short for short, _long in [
                    ("o", "ok"), ("w", "warn"), ("u", "unknown"), ("c", "critical"), ("p", "pending")
                ] if getattr(self, "nfc_{}".format(_long))
            ]
        ) or "n"

    def __str__(self):
        return self.name

    class Meta:
        ordering = ("name",)


@receiver(signals.pre_save, sender=mon_service_dependency_templ)
def mon_service_dependency_templ_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        check_integer(cur_inst, "priority", min_val=-128, max_val=128)
        if not cur_inst.name.strip():
            raise ValidationError("name must not be empty")


class mon_service_dependency(models.Model):
    idx = models.AutoField(primary_key=True)
    devices = models.ManyToManyField("backbone.device", related_name="msd_devices", blank=True)
    mon_check_command = models.ForeignKey("backbone.mon_check_command", related_name="msd_mcc")
    dependent_devices = models.ManyToManyField("backbone.device", related_name="msd_dependent_devices")
    dependent_mon_check_command = models.ForeignKey("backbone.mon_check_command", related_name="msd_dependent_mcc")
    mon_service_dependency_templ = models.ForeignKey("backbone.mon_service_dependency_templ")
    # overrides device and mon_check_command
    mon_service_cluster = models.ForeignKey("backbone.mon_service_cluster", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        return True if (self.mon_service_dependency_templ_id and self.mon_check_command_id and self.dependent_mon_check_command_id) else False

    def get_id(self, devices=None, dependent_devices=None):
        # returns an unique ID
        return "{{{:d}:{:d}:{:d}:{:d}:[{}]:[{}]}}".format(
            self.mon_check_command_id or 0,
            self.dependent_mon_check_command_id or 0,
            self.mon_service_dependency_templ_id or 0,
            self.mon_service_cluster_id or 0,
            ",".join(
                [
                    "{:d}".format(val) for val in sorted(
                        [
                            sub_dev.pk for sub_dev in (devices if devices is not None else self.devices.all())
                        ]
                    )
                ]
            ),
            ",".join(
                [
                    "{:d}".format(val) for val in sorted(
                        [
                            sub_dev.pk for sub_dev in (dependent_devices if dependent_devices is not None else self.dependent_devices.all())
                        ]
                    )
                ]
            ),
        )

    def feed_config(self, conf):
        conf["inherits_parent"] = "1" if self.mon_service_dependency_templ.inherits_parent else "0"
        conf["execution_failure_criteria"] = self.mon_service_dependency_templ.execution_failure_criteria
        conf["notification_failure_criteria"] = self.mon_service_dependency_templ.notification_failure_criteria
        conf["dependency_period"] = self.mon_service_dependency_templ.dependency_period.name


class mon_ext_host(models.Model):
    idx = models.AutoField(db_column="ng_ext_host_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    # png
    icon_image = models.CharField(max_length=192, blank=True)
    icon_image_alt = models.CharField(max_length=192, blank=True)
    vrml_image = models.CharField(max_length=192, blank=True)
    # gd2
    statusmap_image = models.CharField(max_length=192, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def data_image_field(self):
        _url = settings.STATIC_URL + "icinga/{}".format(self.icon_image)
        return _url

    class Meta:
        ordering = ("name",)
        db_table = 'ng_ext_host'


class mon_period(models.Model):
    idx = models.AutoField(db_column="ng_period_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192, default="")
    alias = models.CharField(max_length=255, blank=True, unique=True, default="")
    sun_range = models.CharField(max_length=48, blank=True, db_column="sunrange")
    mon_range = models.CharField(max_length=48, blank=True, db_column="monrange")
    tue_range = models.CharField(max_length=48, blank=True, db_column="tuerange")
    wed_range = models.CharField(max_length=48, blank=True, db_column="wedrange")
    thu_range = models.CharField(max_length=48, blank=True, db_column="thurange")
    fri_range = models.CharField(max_length=48, blank=True, db_column="frirange")
    sat_range = models.CharField(max_length=48, blank=True, db_column="satrange")
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'ng_period'


@receiver(signals.pre_save, sender=mon_period)
def mon_period_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not cur_inst.name.strip():
            raise ValidationError("name is empty")
        range_re1 = re.compile("^[0-9]{1,2}:[0-9]{1,2}-[0-9]{1,2}:[0-9]{1,2}$")
        range_re2 = re.compile("^[0-9]{1,2}-[0-9]{1,2}$")
        for day in ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]:
            r_name = "{}_range".format(day)
            cur_val = getattr(cur_inst, r_name)
            re_t1 = range_re1.match(cur_val)
            re_t2 = range_re2.match(cur_val)
            if not (re_t1 or re_t2):
                raise ValidationError("range for {} not correct".format(day))
            else:
                new_val = []
                for cur_time in cur_val.split("-"):
                    if re_t1:
                        hours, minutes = [int(val) for val in cur_time.split(":")]
                    else:
                        hours, minutes = (int(cur_time), 0)
                    if (hours, minutes) in [(24, 0)]:
                        pass
                    elif hours < 0 or hours > 23 or minutes < 0 or minutes > 60:
                        raise ValidationError("illegal time {} ({})".format(cur_time, day))
                    new_val.append("{:02d}:{:02d}".format(hours, minutes))
                setattr(cur_inst, r_name, "-".join(new_val))


class mon_service_templ(models.Model):
    idx = models.AutoField(db_column="ng_service_templ_idx", primary_key=True)
    name = models.CharField(max_length=192, unique=True)
    volatile = models.BooleanField(default=False)
    nsc_period = models.ForeignKey("backbone.mon_period", related_name="service_check_period")
    max_attempts = models.IntegerField(default=1)
    check_interval = models.IntegerField(default=5)
    retry_interval = models.IntegerField(default=10)
    ninterval = models.IntegerField(default=5)
    nsn_period = models.ForeignKey("backbone.mon_period", related_name="service_notify_period")
    nrecovery = models.BooleanField(default=False, verbose_name="Notify on recovery")
    ncritical = models.BooleanField(default=False, verbose_name="Notify when critical")
    nwarning = models.BooleanField(default=False, verbose_name="Notify when warning")
    nunknown = models.BooleanField(default=False, verbose_name="Notify when unknown")
    nflapping = models.BooleanField(default=False, verbose_name="Notify when flapping")
    nplanned_downtime = models.BooleanField(default=False, verbose_name="Notify when planned downtime")
    low_flap_threshold = models.IntegerField(default=0)
    high_flap_threshold = models.IntegerField(default=0)
    flap_detection_enabled = models.BooleanField(default=False)
    flap_detect_ok = models.BooleanField(default=True)
    flap_detect_warn = models.BooleanField(default=False)
    flap_detect_critical = models.BooleanField(default=False)
    flap_detect_unknown = models.BooleanField(default=False)
    # freshness checks
    check_freshness = models.BooleanField(default=False)
    freshness_threshold = models.IntegerField(default=60)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'ng_service_templ'

    def any_notification_enabled(self):
        return self.nrecovery or self.ncritical or self.nwarning or self.nunknown or self.nflapping or \
            self.nplanned_downtime


@receiver(signals.pre_save, sender=mon_service_templ)
def mon_service_templ_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not cur_inst.name.strip():
            raise ValidationError("name must not be zero")
        for attr_name, min_val, max_val in [
            ("max_attempts", 1, 10),
            ("check_interval", 1, 60),
            ("retry_interval", 1, 60),
            ("ninterval", 0, 60),
            ("low_flap_threshold", 0, 100),
            ("high_flap_threshold", 0, 100),
            ("freshness_threshold", 10, 24 * 3600 * 365),
        ]:
            _cur_val = check_integer(cur_inst, attr_name, min_val=min_val, max_val=max_val)


class mon_service_esc_templ(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    first_notification = models.IntegerField(default=1)
    last_notification = models.IntegerField(default=1)
    ninterval = models.IntegerField(default=1)
    esc_period = models.ForeignKey("backbone.mon_period")
    nrecovery = models.BooleanField(default=False)
    ncritical = models.BooleanField(default=False)
    nwarning = models.BooleanField(default=False)
    nunknown = models.BooleanField(default=False)
    nflapping = models.BooleanField(default=False)
    nplanned_downtime = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


@receiver(signals.pre_save, sender=mon_service_esc_templ)
def mon_service_esc_templ_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not cur_inst.name.strip():
            raise ValidationError("name must not be zero")
        for attr_name, min_val, max_val in [
            ("first_notification", 1, 10),
            ("last_notification", 1, 10),
            ("ninterval", 0, 60),
        ]:
            check_integer(cur_inst, attr_name, min_val=min_val, max_val=max_val)


class MonitoringHintEnabledManager(models.Manager):
    def get_queryset(self):
        return super(MonitoringHintEnabledManager, self).get_queryset().filter(enabled=True)


class monitoring_hint(models.Model):
    objects = models.Manager()
    all_enabled = MonitoringHintEnabledManager()
    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey("backbone.device")
    # call idx, for multi-server-call specials
    call_idx = models.IntegerField(default=0)
    # choices not needed, can be any value from special_*
    m_type = models.CharField(max_length=32)
    # key of vector or OID
    key = models.CharField(default="", max_length=255)
    # the tuple of m_type and and key is a unique key for monitoring-hints relative to a device
    # type of value
    v_type = models.CharField(
        default="f",
        choices=[
            ("f", "float"),
            ("i", "integer"),
            ("b", "boolean"),
            ("s", "string"),
            ("j", "json"),
        ],
        max_length=6
    )
    # current value
    value_float = models.FloatField(default=0.0)
    value_int = models.IntegerField(default=0)
    value_string = models.CharField(default="", max_length=256, blank=True)
    value_json = models.TextField(default="", blank=True)
    # limits
    lower_crit_float = models.FloatField(default=0.0)
    lower_warn_float = models.FloatField(default=0.0)
    upper_warn_float = models.FloatField(default=0.0)
    upper_crit_float = models.FloatField(default=0.0)
    lower_crit_int = models.IntegerField(default=0)
    lower_warn_int = models.IntegerField(default=0)
    upper_warn_int = models.IntegerField(default=0)
    upper_crit_int = models.IntegerField(default=0)
    lower_crit_float_source = models.CharField(default="n", choices=[("n", "not set"), ("s", "system"), ("u", "user")], max_length=4)
    lower_warn_float_source = models.CharField(default="n", choices=[("n", "not set"), ("s", "system"), ("u", "user")], max_length=4)
    upper_warn_float_source = models.CharField(default="n", choices=[("n", "not set"), ("s", "system"), ("u", "user")], max_length=4)
    upper_crit_float_source = models.CharField(default="n", choices=[("n", "not set"), ("s", "system"), ("u", "user")], max_length=4)
    lower_crit_int_source = models.CharField(default="n", choices=[("n", "not set"), ("s", "system"), ("u", "user")], max_length=4)
    lower_warn_int_source = models.CharField(default="n", choices=[("n", "not set"), ("s", "system"), ("u", "user")], max_length=4)
    upper_warn_int_source = models.CharField(default="n", choices=[("n", "not set"), ("s", "system"), ("u", "user")], max_length=4)
    upper_crit_int_source = models.CharField(default="n", choices=[("n", "not set"), ("s", "system"), ("u", "user")], max_length=4)
    # info string
    info = models.CharField(default="", max_length=255)
    # enabled
    enabled = models.BooleanField(default=True)
    # used in monitoring
    check_created = models.BooleanField(default=False)
    # persistent: do not remove even when missing from server (for instance openvpn)
    persistent = models.BooleanField(default=False)
    # is check active ?
    is_active = models.BooleanField(default=True)
    # datasource : (c)ache, (s)erver, (p)ersistent
    datasource = models.CharField(max_length=6, default="s", choices=[("c", "cache"), ("s", "server"), ("p", "persistent")])
    updated = models.DateTimeField(auto_now=True)
    date = models.DateTimeField(auto_now_add=True)

    def update(self, other_hint):
        # update hint with data from other_hint
        _l_names = [
            _name for _name in dir(self.__dict__) if _name.count("lower") or _name.count("upper")
        ]
        for _attr in [
            "info", "enabled", "check_created", "persistent", "is_active", "datasource",
            "v_type", "value_float", "value_int", "value_string", "value_json",
        ] + _l_names:
            # print("*", _attr)
            setattr(self, _attr, getattr(other_hint, _attr))
        self.save()

    def update_limits(self, m_value, limit_dict):
        if isinstance(m_value, int):
            v_type = "int"
        else:
            v_type = "float"
        changed = False
        for key, value in limit_dict.items():
            v_key = "{}_{}".format(key, v_type)
            s_key = "{}_{}".format(v_key, "source")
            if getattr(self, s_key) in ["n", "s"]:
                if getattr(self, s_key) == "n":
                    setattr(self, s_key, "s")
                    changed = True
                if getattr(self, v_key) != value:
                    changed = True
                    setattr(self, v_key, value)
        return changed

    def get_limit(self, name, default, ignore_zero=False):
        key = "{}_{}".format(name, self.get_v_type_display())
        if getattr(self, "{}_source".format(key)) == "n":
            return default
        else:
            _val = str(getattr(self, key))
            if _val == "0" and ignore_zero:
                return default
            else:
                return _val

    def set_value(self, value):
        if isinstance(value, int):
            v_type = "int"
        elif isinstance(value, str):
            v_type = "str"
        else:
            v_type = "float"
        v_key = "value_{}".format(v_type)
        setattr(self, v_key, value)
        self.save(update_fields=[v_key])

    def get_limit_list(self):
        v_type = {
            "f": "float",
            "i": "int"
        }[self.v_type]
        return [
            (
                s_key, getattr(self, "{}_{}".format(key, v_type))
            ) for s_key, key in [
                # ordering is important here to beautify the monitoring output
                ("lw", "lower_warn"),
                ("uw", "upper_warn"),
                ("lc", "lower_crit"),
                ("uc", "upper_crit"),
            ] if getattr(self, "{}_{}_source".format(key, v_type)) != "n"
        ]

    def __str__(self):
        return "{} ({}) for {}, ds {}, persistent {}".format(
            self.m_type,
            self.key,
            str(self.device) if self.device_id else "<unbound>",
            self.datasource,
            "true" if self.persistent else "false",
        )

    class Meta:
        ordering = ("m_type", "key",)
        verbose_name = "Monitoring hint"


class SyslogCheckEnabledManager(models.Manager):
    def get_queryset(self):
        return super(SyslogCheckEnabledManager, self).get_queryset().filter(enabled=True)


class SyslogCheck(models.Model):
    idx = models.AutoField(primary_key=True)
    objects = models.Manager()
    all_enabled = SyslogCheckEnabledManager()
    name = models.CharField(max_length=64, unique=True)
    # XML source
    xml_source = models.TextField(default="")
    # XML version
    version = models.IntegerField(default=1)
    # enabled ?
    enabled = models.BooleanField(default=True)
    # how many minutes to span
    minutes_to_consider = models.IntegerField(default=5)
    # expression-list as json-object
    expressions = models.TextField(default="")
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name", )


class MonDisplayPipeSpec(models.Model):
    idx = models.AutoField(primary_key=True)
    # name
    name = models.CharField(max_length=128, unique=True)
    # description
    description = models.CharField(max_length=255, default="", blank=True)
    # is a system Pipe (not user created)
    system_pipe = models.BooleanField(default=False)
    # public pipe, can be used by any user (is always true for system pipes)
    public_pipe = models.BooleanField(default=True)
    # create user
    create_user = models.ForeignKey("backbone.user", null=True)
    # default for the following user var
    def_user_var_name = models.CharField(default="", max_length=128, blank=True)
    # json spec
    json_spec = models.TextField(default="")
    date = models.DateTimeField(auto_now_add=True)

    def duplicate(self, user):
        _all_names = MonDisplayPipeSpec.objects.all().values_list("name", flat=True)
        _new_name = "Copy of {}".format(self.name)
        _idx = 0
        while True:
            _nn = "{}{}".format(
                _new_name,
                " #{:d}".format(_idx) if _idx else "",
            )
            if _nn in _all_names:
                _idx += 1
            else:
                break
        _spec = MonDisplayPipeSpec(
            name=_nn,
            description="{} (duplicate)".format(self.description),
            system_pipe=False,
            public_pipe=True,
            create_user=user,
            def_user_var_name="",
            json_spec=self.json_spec,
        )
        _spec.save()
        return _spec


@receiver(signals.pre_save, sender=MonDisplayPipeSpec)
def mon_display_pipe_spec_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if cur_inst.system_pipe:
            cur_inst.public_pipe = True
