# Copyright (C) 2001-2014 Andreas Lang-Nevyjel, init.at
#
# this file is part of cluster-backbone-sql
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" database definitions for monitoring """

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, signals
from django.dispatch import receiver
from initat.cluster.backbone.models.functions import _check_empty_string, _check_integer
import datetime
import json
import logging_tools
import re

__all__ = [
    "mon_host_cluster",
    "mon_service_cluster",
    "host_check_command",
    "mon_check_command",
    "mon_check_command_type",
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
    "mon_dist_master",  # "mon_dist_master_serializer",
    "mon_dist_slave",  # "mon_dist_slave_serializer",
    "monitoring_hint",
    "mon_check_command_special",
    # trace
    "mon_trace",  # monitoring trace for speedup
    # unreachable info
    "mon_build_unreachable",  # track unreachable devices
    "parse_commandline",  # commandline parsing
    "snmp_scheme_vendor",
    "snmp_scheme",
    "snmp_scheme_tl_oid",
    "mon_icinga_log_raw_host_alert_data",
    "mon_icinga_log_raw_service_alert_data",
    "mon_icinga_log_file",
    "mon_icinga_log_last_read",
]


class snmp_scheme_vendor(models.Model):
    idx = models.AutoField(primary_key=True)
    # name
    name = models.CharField(max_length=128, unique=True)
    # info (full name of company)
    company_info = models.CharField(max_length=256, default="")
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "snmp_scheme_vendor {}".format(self.name)

    class Meta:
        app_label = "backbone"


class snmp_scheme(models.Model):
    idx = models.AutoField(primary_key=True)
    # vendor
    snmp_scheme_vendor = models.ForeignKey("backbone.snmp_scheme_vendor")
    # name
    name = models.CharField(max_length=128, unique=True)
    # description
    description = models.CharField(max_length=128, default="")
    # version
    version = models.IntegerField(default=1)
    # used for collectd calls
    collect = models.BooleanField(default=False)
    # when found make an initial lookup call
    initial = models.BooleanField(default=False)
    # moncheck
    mon_check = models.BooleanField(default=False)
    # priority for handling, schemes with higher priority will be handled first
    priority = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "snmp_scheme {}".format(self.name)

    @property
    def full_name(self):
        return "{}.{}".format(
            self.snmp_scheme_vendor.name,
            self.name,
        )

    @property
    def full_name_version(self):
        return "{}_v{:d}".format(
            self.full_name,
            self.version,
        )

    class Meta:
        app_label = "backbone"


class snmp_scheme_tl_oid(models.Model):
    idx = models.AutoField(primary_key=True)
    snmp_scheme = models.ForeignKey("backbone.snmp_scheme")
    oid = models.CharField(default="", max_length=255)
    # is this oid optional ?
    optional = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"


class mon_trace(models.Model):
    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey("backbone.device")
    # fingerprint of device netdevices
    dev_netdevice_fp = models.CharField(max_length=128, default="", db_index=True)
    # fingerprint of server netdevices
    srv_netdevice_fp = models.CharField(max_length=128, default="", db_index=True)
    traces = models.TextField(default="")
    date = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def get_fp(net_idxs):
        return ":".join(["{:d}".format(_idx) for _idx in net_idxs])

    @staticmethod
    def create_trace(dev, dev_fp, srv_fp, traces):
        new_tr = mon_trace.objects.create(
            device=dev,
            dev_netdevice_fp=dev_fp,
            srv_netdevice_fp=srv_fp,
            traces=traces,
        )
        return new_tr

    def set_trace(self, traces):
        self.traces = json.dumps(traces)

    def get_trace(self):
        return json.loads(self.traces)

    class Meta:
        app_label = "backbone"


class mon_dist_base(models.Model):
    # start of build
    config_build_start = models.DateTimeField(default=None, null=True)
    # end of build
    config_build_end = models.DateTimeField(default=None, null=True)
    # version of of relayer / icinga
    relayer_version = models.CharField(max_length=128, default="")
    mon_version = models.CharField(max_length=128, default="")
    # total build start
    build_start = models.DateTimeField(default=None, null=True)
    # total build end
    build_end = models.DateTimeField(default=None, null=True)
    # number of devices
    num_devices = models.IntegerField(default=0)
    # unroutable devices, always zero for slaves
    unreachable_devices = models.IntegerField(default=0)
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
        app_label = "backbone"


class mon_dist_master(mon_dist_base):
    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey("backbone.device")
    version = models.IntegerField(default=0)
    # version of of md-config-server
    md_version = models.CharField(max_length=128, default="")

    class Meta:
        app_label = "backbone"
        ordering = ("-idx",)


class mon_build_unreachable(models.Model):
    idx = models.AutoField(primary_key=True)
    mon_dist_master = models.ForeignKey("backbone.mon_dist_master")
    device_pk = models.IntegerField(default=0)
    device_name = models.CharField(max_length=256, default="")
    devicegroup_name = models.CharField(max_length=256, default="")
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"

    class CSW_Meta:
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

    def __unicode__(self):
        return self.name

    class Meta:
        app_label = "backbone"


@receiver(signals.pre_save, sender=mon_host_cluster)
def mon_host_cluster_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_empty_string(cur_inst, "name")
        for attr_name, min_val, max_val in [
            ("warn_value", 0, 128),
            ("error_value", 0, 128)
        ]:
            _check_integer(cur_inst, attr_name, min_val=min_val, max_val=max_val)


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

    def __unicode__(self):
        return self.name

    class Meta:
        app_label = "backbone"


@receiver(signals.pre_save, sender=mon_service_cluster)
def mon_service_cluster_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_empty_string(cur_inst, "name")
        for attr_name, min_val, max_val in [
            ("warn_value", 0, 128),
            ("error_value", 0, 128)
        ]:
            _check_integer(cur_inst, attr_name, min_val=min_val, max_val=max_val)


class host_check_command(models.Model):
    idx = models.AutoField(db_column="ng_check_command_idx", primary_key=True)
    name = models.CharField(max_length=64, unique=True, blank=False, null=False)
    command_line = models.CharField(max_length=128, unique=True, blank=False, null=False)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "hcc_{}".format(self.name)

    class Meta:
        app_label = "backbone"


class mon_check_command_special(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(max_length=64, unique=True)
    info = models.CharField(max_length=64, default="")
    command_line = models.CharField(max_length=256, default="")
    description = models.CharField(max_length=256, default="")
    is_active = models.BooleanField(default=True)
    date = models.DateTimeField(auto_now_add=True)
    # triggers other commands
    meta = models.BooleanField(default=False)
    # for commands from a meta-command
    parent = models.ForeignKey("self", null=True)

    @property
    def md_name(self):
        return "special_{:d}_{}".format(self.idx, self.name)

    class Meta:
        app_label = "backbone"

    def __unicode__(self):
        return "mccs_{}".format(self.name)


def parse_commandline(com_line):
    """
    parses command line, also builds argument lut
    lut format: commandline switch -> ARG#
    list format : ARG#, ARG#, ...
    """
    _num_args, _default_values = (0, {})
    arg_lut, arg_list = ({}, [])
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
    com_re = re.compile(
        "^(?P<pre_text>.*?)((\${ARG(?P<arg_num_1>\d+):(((?P<var_name>[^:^}]+?)\:(?P<default_vn>[^}]+?)}\$*)"
        "|(?P<default>[^}]+?)}\$*))|(\$ARG(?P<arg_num_2>\d+)\$))+(?P<post_text>.*)$"
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
    log_lines = []
    if com_line == _parsed_com_line:
        log_lines.append("command_line in/out is '{}'".format(com_line))
    else:
        log_lines.append("command_line in     is '{}'".format(com_line))
        log_lines.append("command_line out    is '{}'".format(_parsed_com_line))
    if arg_lut:
        log_lines.append("lut : %s; %s" % (
            logging_tools.get_plural("key", len(arg_lut)),
            ", ".join(["'%s' => '%s'" % (key, value) for key, value in arg_lut.iteritems()])
        ))
    if arg_list:
        log_lines.append("list: %s; %s" % (
            logging_tools.get_plural("item", len(arg_list)),
            ", ".join(arg_list)
        ))
    return {
        "arg_lut": arg_lut,
        "arg_list": arg_list,
        "parsed_com_line": _parsed_com_line,
        "num_args": _num_args,
        "default_values": _default_values,
    }, log_lines
    # self.__arg_lut, self.__arg_list = (arg_lut, arg_list)


class mon_check_command(models.Model):
    idx = models.AutoField(db_column="ng_check_command_idx", primary_key=True)
    config_old = models.IntegerField(null=True, blank=True, db_column="config")
    config = models.ForeignKey("backbone.config", db_column="new_config_id")
    # deprecated, now references category tree
    mon_check_command_type = models.ForeignKey("backbone.mon_check_command_type", null=True, default=None, blank=True)
    mon_service_templ = models.ForeignKey("backbone.mon_service_templ", null=True, blank=True)
    # only unique per config
    name = models.CharField(max_length=192)  # , unique=True)
    # flag for special commands (@<SREF>@command)
    mon_check_command_special = models.ForeignKey("backbone.mon_check_command_special", null=True, blank=True)
    # for mon_check_special_command this is empty
    command_line = models.CharField(max_length=765, default="")
    description = models.CharField(max_length=192, blank=True)
    # device = models.ForeignKey("backbone.device", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    enable_perfdata = models.BooleanField(default=False)
    volatile = models.BooleanField(default=False)
    # categories for this device
    categories = models.ManyToManyField("backbone.category", blank=True)
    # device to exclude
    exclude_devices = models.ManyToManyField("backbone.device", related_name="mcc_exclude_devices", blank=True)
    # event handler settings
    is_event_handler = models.BooleanField(default=False)
    event_handler = models.ForeignKey("self", null=True, default=None, blank=True)
    event_handler_enabled = models.BooleanField(default=True)
    # which tcp port(s) cover this check
    tcp_coverage = models.CharField(default="", max_length=256, blank=True)

    def get_object_type(self):
        return "mon"

    class Meta:
        db_table = u'ng_check_command'
        unique_together = (("name", "config"))
        app_label = "backbone"

    class CSW_Meta:
        permissions = (
            ("setup_monitoring", "Change monitoring settings", False),
        )

    def __unicode__(self):
        return "mcc_{}".format(self.name)


@receiver(signals.pre_save, sender=mon_check_command)
def mon_check_command_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        # cur_inst.is_special_command = True if special_re.match(cur_inst.name) else False
        if not cur_inst.name:
            raise ValidationError("name is empty")
        if not cur_inst.command_line:
            raise ValidationError("command_line is empty")
        if cur_inst.name in cur_inst.config.mon_check_command_set.exclude(Q(pk=cur_inst.pk)).values_list("name", flat=True):
            raise ValidationError("name already used")
        if not cur_inst.is_event_handler:
            mc_refs = cur_inst.mon_check_command_set.all()
            if len(mc_refs):
                raise ValidationError("still referenced by {}".format(logging_tools.get_plural("check_command", len(mc_refs))))
        if cur_inst.mon_check_command_special_id and cur_inst.is_event_handler:
            cur_inst.is_event_handler = False
            cur_inst.save()
            raise ValidationError("special command not allowed as event handler")
        if cur_inst.is_event_handler and cur_inst.event_handler_id:
            cur_inst.event_handler = None
            cur_inst.save()
            raise ValidationError("cannot be an event handler and reference to another event handler")


class mon_check_command_type(models.Model):
    idx = models.AutoField(db_column="ng_check_command_type_idx", primary_key=True)
    name = models.CharField(unique=True, max_length=192)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.name

    class Meta:
        db_table = u'ng_check_command_type'
        app_label = "backbone"


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
        return u"{} ({} {})".format(
            self.user.login,
            self.user.first_name,
            self.user.last_name,
            )

    def __unicode__(self):
        return unicode(self.user)

    class Meta:
        db_table = u'ng_contact'
        app_label = "backbone"


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
    content = models.CharField(max_length=4096, blank=False)
    enabled = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "{} ({} via {})".format(
            self.name,
            self.not_type,
            self.channel,
        )

    class Meta:
        app_label = "backbone"


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

    def __unicode__(self):
        return self.name

    class Meta:
        db_table = u'ng_contactgroup'
        app_label = "backbone"


@receiver(signals.pre_save, sender=mon_contactgroup)
def mon_contactgroup_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_empty_string(cur_inst, "name")


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

    def __unicode__(self):
        return self.name

    class Meta:
        db_table = u'ng_device_templ'
        app_label = "backbone"


@receiver(signals.pre_save, sender=mon_device_templ)
def mon_device_templ_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not cur_inst.name.strip():
            raise ValidationError("name must not be zero")
        for attr_name, min_val, max_val in [
            ("max_attempts", 1, 10),
            ("ninterval", 0, 60 * 24),
            ("low_flap_threshold", 0, 100),
            ("high_flap_threshold", 0, 100),
            ("check_interval", 1, 60),
            ("retry_interval", 1, 60),
            ("freshness_threshold", 10, 24 * 3600 * 365),
        ]:
            _check_integer(cur_inst, attr_name, min_val=min_val, max_val=max_val)


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

    def __unicode__(self):
        return self.name

    class Meta:
        app_label = "backbone"


@receiver(signals.pre_save, sender=mon_device_esc_templ)
def mon_device_esc_templ_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not cur_inst.name.strip():
            raise ValidationError("name must not be empty")
        for attr_name, min_val, max_val in [
            ("first_notification", 1, 10),
            ("last_notification", 1, 10),
            ("ninterval", 0, 60 * 24)
        ]:
            _check_integer(cur_inst, attr_name, min_val=min_val, max_val=max_val)


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

    def __unicode__(self):
        return self.name

    class Meta:
        ordering = ("name",)
        app_label = "backbone"


@receiver(signals.pre_save, sender=mon_host_dependency_templ)
def mon_host_dependency_templ_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_integer(cur_inst, "priority", min_val=-128, max_val=128)
        if not cur_inst.name.strip():
            raise ValidationError("name must not be empty")


class mon_host_dependency(models.Model):
    idx = models.AutoField(primary_key=True)
    devices = models.ManyToManyField("device", related_name="mhd_devices", null=True, blank=True)
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

    class Meta:
        app_label = "backbone"


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

    def __unicode__(self):
        return self.name

    class Meta:
        ordering = ("name",)
        app_label = "backbone"


@receiver(signals.pre_save, sender=mon_service_dependency_templ)
def mon_service_dependency_templ_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_integer(cur_inst, "priority", min_val=-128, max_val=128)
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

    class Meta:
        app_label = "backbone"


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

    def __unicode__(self):
        return self.name

    def data_image_field(self):
        _url = settings.STATIC_URL + "icinga/{}".format(self.icon_image)
        return _url

    class Meta:
        ordering = ("name",)
        db_table = u'ng_ext_host'
        app_label = "backbone"


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

    def __unicode__(self):
        return self.name

    class Meta:
        db_table = u'ng_period'
        app_label = "backbone"


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

    def __unicode__(self):
        return self.name

    class Meta:
        db_table = u'ng_service_templ'
        app_label = "backbone"


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
            _cur_val = _check_integer(cur_inst, attr_name, min_val=min_val, max_val=max_val)


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

    def __unicode__(self):
        return self.name

    class Meta:
        app_label = "backbone"


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
            _check_integer(cur_inst, attr_name, min_val=min_val, max_val=max_val)



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
    m_type = models.CharField(max_length=32)  # , choices=[("ipmi", "IPMI"), ("snmp", "SNMP"), ])
    # key of vector or OID
    key = models.CharField(default="", max_length=255)
    # type of value
    v_type = models.CharField(
        default="f",
        choices=[
            ("f", "float"),
            ("i", "integer"),
            ("b", "boolean"),
            ("s", "string"),
        ],
        max_length=6
    )
    # current value
    value_float = models.FloatField(default=0.0)
    value_int = models.IntegerField(default=0)
    value_string = models.CharField(default="", max_length=256, blank=True)
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
    changed = models.DateTimeField(auto_now_add=True, auto_now=True)  # , default=datetime.datetime.now())
    # persistent: do not remove even when missing from server (for instance openvpn)
    persistent = models.BooleanField(default=False)
    # datasource : (c)ache, (s)erver, (p)ersistent
    datasource = models.CharField(max_length=6, default="s", choices=[("c", "cache"), ("s", "server"), ("p", "persistent")])
    date = models.DateTimeField(auto_now_add=True)

    def update_limits(self, m_value, limit_dict):
        if type(m_value) in [int, long]:
            v_type = "int"
        else:
            v_type = "float"
        changed = False
        for key, value in limit_dict.iteritems():
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
        if type(value) in [int, long]:
            v_type = "int"
        elif isinstance(value, basestring):
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

    def __unicode__(self):
        return u"{} ({}) for {}, ds {}, persistent {}".format(
            self.m_type,
            self.key,
            unicode(self.device),
            self.datasource,
            "true" if self.persistent else "false",
        )

    class Meta:
        app_label = "backbone"
        ordering = ("m_type", "key",)


########################################
# models for direct data from icinga logs
class mon_icinga_log_raw_base(models.Model):
    idx = models.AutoField(primary_key=True)
    date = models.DateTimeField(db_index=True)
    device = models.ForeignKey("backbone.device", db_index=True, null=True)  # only null for device_independent
    device_independent = models.BooleanField(default=False)  # events which apply to all devices such as icinga shutdown
    # text from log entry
    msg = models.TextField()
    # entry originates from this logfile
    logfile = models.ForeignKey("backbone.mon_icinga_log_file", blank=True, null=True)

    STATE_TYPE_HARD = "H"
    STATE_TYPE_SOFT = "S"
    STATE_UNDETERMINED = "UD"  # state as well as state type
    STATE_UNDETERMINED_LONG = "UNDETERMINED"
    STATE_TYPES = [(STATE_TYPE_HARD, "HARD"), (STATE_TYPE_SOFT, "SOFT"), (STATE_UNDETERMINED, STATE_UNDETERMINED)]

    FLAPPING_START = "START"
    FLAPPING_STOP = "STOP"

    class Meta:
        app_label = "backbone"
        abstract = True


class mon_icinga_log_raw_host_alert_data(mon_icinga_log_raw_base):
    STATE_UP = "UP"
    STATE_DOWN = "D"
    STATE_UNREACHABLE = "UR"
    STATE_CHOICES = [(STATE_UP, "UP"), (STATE_DOWN, "DOWN"), (STATE_UNREACHABLE, "UNREACHABLE"),
                     (mon_icinga_log_raw_base.STATE_UNDETERMINED, mon_icinga_log_raw_base.STATE_UNDETERMINED_LONG)]
    STATE_CHOICES_REVERSE_MAP = {val: key for (key, val) in STATE_CHOICES}
    state_type = models.CharField(max_length=2, choices=mon_icinga_log_raw_base.STATE_TYPES)
    state = models.CharField(max_length=2, choices=STATE_CHOICES)
    log_rotation_state = models.BooleanField(default=False)  # whether this is an entry at the beginning of a fresh archive file.
    initial_state = models.BooleanField(default=False)  # whether this is an entry after icinga restart

    class CSW_Meta:
        backup = False


class mon_icinga_log_raw_service_alert_data(mon_icinga_log_raw_base):
    STATE_UNDETERMINED = "UD"
    STATE_CHOICES = [("O", "OK"), ("W", "WARNING"), ("U", "UNKNOWN"), ("C", "CRITICAL"),
                     (mon_icinga_log_raw_base.STATE_UNDETERMINED, mon_icinga_log_raw_base.STATE_UNDETERMINED_LONG)]
    STATE_CHOICES_REVERSE_MAP = {val: key for (key, val) in STATE_CHOICES}

    # NOTE: there are different setup, at this time only regular check_commands are supported
    # they are identified by the mon_check_command.pk and their name, hence the fields here
    # the layout of this table probably has to change in order to accommodate for further services
    # I however can't do that now as I don't know how what to change it to
    service = models.ForeignKey(mon_check_command, null=True, db_index=True)  # null for device_independent events
    service_info = models.TextField(blank=True, null=True, db_index=True)

    state_type = models.CharField(max_length=2, choices=mon_icinga_log_raw_base.STATE_TYPES)
    state = models.CharField(max_length=2, choices=STATE_CHOICES)

    log_rotation_state = models.BooleanField(default=False)  # whether this is an entry at the beginning of a fresh archive file.
    initial_state = models.BooleanField(default=False)  # whether this is an entry after icinga restart

    class CSW_Meta:
        backup = False


class mon_icinga_log_raw_service_flapping_data(mon_icinga_log_raw_base):
    # see comment in mon_icinga_log_raw_service_alert_data
    service = models.ForeignKey(mon_check_command, null=True)  # null for device_independent events
    service_info = models.TextField(blank=True, null=True)

    flapping_state = models.CharField(max_length=5, choices=[(mon_icinga_log_raw_base.FLAPPING_START, mon_icinga_log_raw_base.FLAPPING_START),
                                                             (mon_icinga_log_raw_base.FLAPPING_STOP, mon_icinga_log_raw_base.FLAPPING_STOP)])

    class CSW_Meta:
        backup = False


class mon_icinga_log_raw_host_flapping_data(mon_icinga_log_raw_base):
    flapping_state = models.CharField(max_length=5, choices=[(mon_icinga_log_raw_base.FLAPPING_START, mon_icinga_log_raw_base.FLAPPING_START),
                                                             (mon_icinga_log_raw_base.FLAPPING_STOP, mon_icinga_log_raw_base.FLAPPING_STOP)])

    class CSW_Meta:
        backup = False


class mon_icinga_log_raw_service_notification_data(mon_icinga_log_raw_base):
    # see comment in mon_icinga_log_raw_service_alert_data
    service = models.ForeignKey(mon_check_command, null=True)
    service_info = models.TextField(blank=True, null=True)

    state = models.CharField(max_length=2, choices=mon_icinga_log_raw_service_alert_data.STATE_CHOICES)
    user = models.TextField()
    notification_type = models.TextField()

    class CSW_Meta:
        backup = False


class mon_icinga_log_raw_host_notification_data(mon_icinga_log_raw_base):
    state = models.CharField(max_length=2, choices=mon_icinga_log_raw_host_alert_data.STATE_CHOICES)
    user = models.TextField()
    notification_type = models.TextField()

    class CSW_Meta:
        backup = False


class mon_icinga_log_file(models.Model):
    idx = models.AutoField(primary_key=True)
    filepath = models.TextField()

    class Meta:
        app_label = "backbone"

    class CSW_Meta:
        backup = False


class _last_read_manager(models.Manager):
    def get_last_read(self):
        """
        @return int timestamp
        """
        if self.all():
            return self.all()[0]
        else:
            return None


class mon_icinga_log_last_read(models.Model):
    # this table contains only one row
    idx = models.AutoField(primary_key=True)
    position = models.BigIntegerField()  # position of start of last line read
    timestamp = models.IntegerField()  # time of last line read

    objects = _last_read_manager()

    class Meta:
        app_label = "backbone"

    class CSW_Meta:
        backup = False


########################################
# models for aggregated data from icinga


class mon_icinga_log_aggregated_timespan(models.Model):

    idx = models.AutoField(primary_key=True)
    end_date = models.DateTimeField()
    start_date = models.DateTimeField(db_index=True)
    duration = models.IntegerField()  # seconds
    duration_type = models.IntegerField(db_index=True)  # durations pseudo enum from functions


class mon_icinga_log_aggregated_host_data(models.Model):
    STATE_FLAPPING = "FL"  # this is also a state type
    STATE_CHOICES = mon_icinga_log_raw_host_alert_data.STATE_CHOICES + [(STATE_FLAPPING, "FLAPPING")]
    STATE_CHOICES_REVERSE_MAP = {val: key for (key, val) in STATE_CHOICES}

    STATE_TYPES = mon_icinga_log_raw_base.STATE_TYPES + [(STATE_FLAPPING, STATE_FLAPPING)]

    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey("backbone.device")
    timespan = models.ForeignKey(mon_icinga_log_aggregated_timespan)

    state_type = models.CharField(max_length=2, choices=STATE_TYPES)
    state = models.CharField(max_length=2, choices=STATE_CHOICES)

    # ratio of time span spent in this (state_type, state)
    value = models.FloatField()


class mon_icinga_log_aggregated_service_data(models.Model):
    STATE_FLAPPING = "FL"
    STATE_CHOICES = mon_icinga_log_raw_service_alert_data.STATE_CHOICES + [(STATE_FLAPPING, "FLAPPING")]
    STATE_CHOICES_REVERSE_MAP = {val: key for (key, val) in STATE_CHOICES}

    idx = models.AutoField(primary_key=True)
    timespan = models.ForeignKey(mon_icinga_log_aggregated_timespan)

    STATE_TYPES = mon_icinga_log_raw_base.STATE_TYPES + [(STATE_FLAPPING, STATE_FLAPPING)]

    device = models.ForeignKey("backbone.device")
    state_type = models.CharField(max_length=2, choices=STATE_TYPES)
    state = models.CharField(max_length=2, choices=STATE_CHOICES)

    # see comment in mon_icinga_log_raw_service_alert_data
    service = models.ForeignKey(mon_check_command, null=True)  # null for old entries for special check commands
    service_info = models.TextField(blank=True, null=True)

    # ratio of time span spent in this (state_type, state)
    value = models.FloatField()
