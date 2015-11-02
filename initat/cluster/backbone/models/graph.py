# Copyright (C) 2015 Andreas Lang-Nevyjel, init.at
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
""" graph models for NOCTUA, CORVUS and NESTOR """

from django.db import models
from django.db.models import signals, Q
from django.dispatch import receiver
from enum import Enum

from initat.cluster.backbone.signals import SensorThresholdChanged

__all__ = [
    "MachineVector",
    "MVStructEntry",
    "MVValueEntry",
    "SensorAction",
    "SensorThreshold",
    "SensorThresholdAction",
    "GraphSetting",
    "GraphScaleModeEnum",
    "GraphLegendModeEnum",
    "GraphForecastModeEnum",
    "GraphCFEnum",
    "GraphSettingSize",
    "GraphSettingTimeshift",
    "GraphSettingForecast",
    "GraphTimeFrame",
]


"""
XML structure on icinga.init.at (27.2.2015):

top levels: ['machine_vector']
[machine_vector (store_name) ->
    [pde (active, file_name, host, init_time, last_update, name, type_instance) ->
        [value (base, factor, index, info, key, name, unit, v_type) ->
        ]
    ]
    [mvl (active, file_name, info, init_time, last_update, name, sane_name) ->
        [value (base, factor, index, info, key, name, unit, v_type) ->
        ]
    ]
    [mve (active, base, factor, file_name, full, info, init_time, last_update, name, sane_name, unit, v_type) ->
    ]
]

"""


class MachineVector(models.Model):
    idx = models.AutoField(primary_key=True)
    # link to device
    device = models.ForeignKey("backbone.device")
    # src_file name, for later reference
    src_file_name = models.CharField(max_length=256, default="", blank=True)
    # directory under cache_dir, in most cases the UUID
    dir_name = models.CharField(max_length=128, default="")
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return u"MachineVector for device {}".format(unicode(self.device))


class MVStructEntry(models.Model):
    # structural entry for machine_vector, references an RRD-file on disk
    idx = models.AutoField(primary_key=True)
    machine_vector = models.ForeignKey("MachineVector")
    file_name = models.CharField(max_length=256, default="")
    # needed ?
    se_type = models.CharField(
        max_length=6,
        choices=[
            # performance data entry
            ("pde", "pde"),
            # machine vector list (multi-value)
            ("mvl", "mvl"),
            # machine vector entry (single value)
            ("mve", "mve"),
        ],
    )
    # type instance is set for certains PDEs (for instance windows disk [C,D,E,...], SNMP netifaces [eth0,eth1,...])
    type_instance = models.CharField(max_length=255, default="")
    # position in RRD-tree this nodes resides in, was name
    key = models.CharField(max_length=256)
    # is active
    is_active = models.BooleanField(default=True)
    # last update
    last_update = models.DateTimeField(auto_now=True)
    # was init_time
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return u"MVStructEntry ({}, {}{}), file is {}".format(
            self.se_type,
            self.key,
            ", ti={}".format(self.type_instance) if self.type_instance else "",
            self.file_name,
        )

    class Meta:
        ordering = ("key",)


class MVValueEntry(models.Model):
    # value entry for machine_vector
    idx = models.AutoField(primary_key=True)
    mv_struct_entry = models.ForeignKey("MVStructEntry")
    # base for generating {k,M,G,T} values, in most cases 1000 or 1024
    base = models.IntegerField(default=1024)
    # factor, a simple multiplicator to get to a sane value (in most cases 1)
    factor = models.IntegerField(default=1)
    # unit
    unit = models.CharField(max_length=16, default="")
    # variable type
    v_type = models.CharField(max_length=3, choices=[("i", "int"), ("f", "float")], default="f")
    # info string
    info = models.CharField(max_length=256, default="")
    # key, string describing the last part of the position (was also called name), not necessarily a single value
    # (for instance request.time.connect for HTTP perfdata)
    # the full key is mv_struct_entry.key + "." + mv_value.key
    # may be empty in case of mve entries (full key is stored in mv_struct_entry)
    key = models.CharField(max_length=128, default="")
    # rra_index, index in RRA-file (zero in most cases except for PDEs and MVEs
    rra_idx = models.IntegerField(default=0)
    # full key for this value, stored for faster reference
    full_key = models.CharField(max_length=128, default="")
    # name, required to look up the correct row in the RRD in case of perfdata
    # otherwise this entry is forced to be empty (otherwise we have problems in rrd-grapher)
    # (no longer valid: we don't store the name which was the last part of key)
    name = models.CharField(max_length=64, default="")
    # we also don't store the index because this fields was omitted some time ago (still present in some XMLs)
    # full is also not stored because full is always equal to name
    # sane_name is also ignored because this is handled by collectd to generate filesystem-safe filenames ('/' -> '_sl_')
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return u"MVValueEntry ({}{}, '{}'), '{}' b/f={:d}/{:d} ({})".format(
            self.key or "NONE",
            ", name={}@{:d}".format(self.name, self.rra_idx) if (self.name or self.rra_idx) else "",
            self.info,
            self.unit,
            self.base,
            self.factor,
            self.v_type,
        )

    def copy_and_modify(self, mod_dict):
        # return a copy of the current MVValueEntry and set the attributes according to mod_dict
        new_mv = MVValueEntry(
            mv_struct_entry=self.mv_struct_entry,
            base=self.base,
            factor=self.factor,
            unit=self.unit,
            v_type=self.v_type,
            info=self.info,
            key=self.key,
            full_key=self.full_key,
            rra_idx=self.rra_idx,
            date=self.date
        )
        for _key, _value in mod_dict.iteritems():
            if _key not in {"key", "full_key"}:
                setattr(new_mv, _key, _value)
        return new_mv

    class Meta:
        ordering = ("key",)


class SensorAction(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(max_length=64, unique=True)
    description = models.CharField(max_length=256, default="")
    action = models.CharField(
        max_length=64,
        default="none",
        choices=[
            ("none", "do nothing"),
            ("reboot", "restart device"),
            ("halt", "halt device"),
            ("poweron", "turn on device"),
        ]
    )
    # action on device via soft- or hardware
    hard_control = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)

    def get_mother_command(self):
        if self.action == "none":
            _cmd = None
        else:
            if self.hard_control:
                # map to IPMI command, see command.py:163
                _cmd = {
                    "reboot": "cycle",
                    "halt": "off",
                    "poweron": "on",
                }[self.action]
                _cmd = ("hard_control", _cmd)
            else:
                # map to hoststatus command, see hoststatus_zmq.c:266
                _cmd = {
                    "reboot": "reboot",
                    "halt": "poweroff",
                    "poweron": None
                }[self.action]
                if _cmd is not None:
                    _cmd = ("soft_control", _cmd)
        return _cmd

    def build_mother_element(self, _bldr, dev):
        from initat.cluster.backbone.models import cd_connection
        if self.hard_control:
            cd_cons = cd_connection.objects.filter(Q(child=dev))
            return [
                _bldr(
                    "device",
                    name=dev.name,
                    pk="{:d}".format(dev.pk),
                    command=self.get_mother_command()[1],
                    cd_con="{:d}".format(cd_con.pk),
                ) for cd_con in cd_cons
            ]
        else:
            return [
                _bldr(
                    "device",
                    name=dev.name,
                    pk="{:d}".format(dev.pk),
                    soft_command=self.get_mother_command()[1]
                )
            ]

    def __unicode__(self):
        return "SensorAction {}".format(self.name)


class SensorThreshold(models.Model):
    idx = models.AutoField(primary_key=True)
    # name of Threshold
    name = models.CharField(max_length=64, default="")
    mv_value_entry = models.ForeignKey("MVValueEntry")
    lower_value = models.FloatField(default=0.0)
    upper_value = models.FloatField(default=0.0)
    lower_sensor_action = models.ForeignKey("SensorAction", related_name="lower_sensor_action", null=True, blank=True)
    upper_sensor_action = models.ForeignKey("SensorAction", related_name="upper_sensor_action", null=True, blank=True)
    lower_mail = models.BooleanField(default=False)
    upper_mail = models.BooleanField(default=False)
    lower_enabled = models.BooleanField(default=True)
    upper_enabled = models.BooleanField(default=True)
    # which users to notify
    notify_users = models.ManyToManyField("user")
    # creating user
    create_user = models.ForeignKey("user", null=True, blank=True, related_name="sensor_threshold_create_user")
    # device selection
    device_selection = models.ForeignKey("backbone.DeviceSelection", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "SensorThreshold '{}' [{}@{:.4f}({}), {}@{:.4f}({})] for {}".format(
            self.name,
            unicode(self.lower_sensor_action),
            self.lower_value,
            "enabled" if self.lower_enabled else "disabled",
            unicode(self.upper_sensor_action),
            self.upper_value,
            "enabled" if self.upper_enabled else "disabled",
            unicode(self.mv_value_entry),
        )

    class CSW_Meta:
        fk_ignore_list = [
            "SensorThresholdAction",
        ]


class SensorThresholdAction(models.Model):
    # log
    idx = models.AutoField(primary_key=True)
    sensor_threshold = models.ForeignKey("SensorThreshold")
    sensor_action = models.ForeignKey("SensorAction")
    action_type = models.CharField(
        max_length=12,
        choices=[
            ("lower", "lower"),
            ("upper", "upper"),
        ]
    )
    # copy of current values
    # upper or lower
    mail = models.BooleanField(default=False)
    value = models.FloatField(default=0.0)
    notify_users = models.ManyToManyField("user")
    create_user = models.ForeignKey("user", null=True, blank=True, related_name="sensor_threshold_action_create_user")
    device_selection = models.ForeignKey("backbone.DeviceSelection", null=True, blank=True)
    # was triggered via webfrontend ?
    triggered = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)


@receiver(signals.pre_save, sender=SensorThreshold)
def SensorThresholdPreSave(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        _lower = min(_cur_inst.lower_value, _cur_inst.upper_value)
        _upper = max(_cur_inst.lower_value, _cur_inst.upper_value)
        _cur_inst.lower_value = _lower
        _cur_inst.upper_value = _upper


@receiver(signals.post_save, sender=SensorThreshold)
def SensorThresholdPostSave(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        SensorThresholdChanged.send(sender=_cur_inst, sensor_threshold=_cur_inst, cause="SensorThreshold saved")


@receiver(signals.post_delete, sender=SensorThreshold)
def SensorThresholdPostDelete(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        SensorThresholdChanged.send(sender=_cur_inst, sensor_threshold=_cur_inst, cause="SensorThreshold deleted")


class GraphScaleModeEnum(Enum):
    level = "l"
    none = "n"
    to100 = "t"


class GraphLegendModeEnum(Enum):
    full_with_values = "f"
    only_text = "t"
    nothing = "n"


class GraphForecastModeEnum(Enum):
    simple_linear = "sl"


class GraphCFEnum(Enum):
    minimum = "MIN"
    average = "AVERAGE"
    maximum = "MAX"


class GraphSettingSize(models.Model):
    # sizes
    idx = models.AutoField(primary_key=True)
    name = models.CharField(max_length=64, default="", unique=True)
    default = models.BooleanField(default=False)
    width = models.IntegerField(default=0)
    height = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("width", "height")]
        ordering = ("width", "height",)


class GraphSettingTimeshift(models.Model):
    # sizes
    idx = models.AutoField(primary_key=True)
    name = models.CharField(max_length=64, default="", unique=True)
    seconds = models.IntegerField(default=0, unique=True)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "GraphSettingTimeshift {}".format(self.name)


class GraphSettingForecast(models.Model):
    # sizes
    idx = models.AutoField(primary_key=True)
    name = models.CharField(max_length=64, default="", unique=True)
    seconds = models.IntegerField(default=0, unique=True)
    mode = models.CharField(
        max_length=4,
        default=GraphForecastModeEnum.simple_linear.value,
        choices=[(_en.value, _en.name.replace("_", " ")) for _en in GraphForecastModeEnum],
    )
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "GraphSettingForecast {}".format(self.name)


class GraphSetting(models.Model):
    idx = models.AutoField(primary_key=True)
    user = models.ForeignKey("backbone.user")
    name = models.CharField(max_length=128, default="")
    # hide empty (all zero) RRDs
    hide_empty = models.BooleanField(default=True)
    # include y=0
    include_zero = models.BooleanField(default=True)
    # scale mode
    # ... (l)evel : all graphs have the same max-value
    # ... (n)one  : no scaling
    # ... (t)o100 : all graphs max out at 100
    scale_mode = models.CharField(
        max_length=4,
        default=GraphScaleModeEnum.level.value,
        choices=[(_en.value, _en.name.replace("_", " ")) for _en in GraphScaleModeEnum],
    )
    legend_mode = models.CharField(
        max_length=4,
        default=GraphLegendModeEnum.full_with_values.value,
        choices=[(_en.value, _en.name.replace("_", " ")) for _en in GraphLegendModeEnum],
    )
    cf = models.CharField(
        max_length=16,
        default=GraphCFEnum.average.value,
        choices=[(_en.value, _en.name) for _en in GraphCFEnum],
    )
    # merge all devices together
    merge_devices = models.BooleanField(default=False)
    # merge all graphs into one
    merge_graphs = models.BooleanField(default=False)
    # merge controlling devices, only meaningfull when used with pks
    merge_controlling_devices = models.BooleanField(default=False)
    # size
    graph_setting_size = models.ForeignKey("backbone.GraphSettingSize")
    graph_setting_timeshift = models.ForeignKey("backbone.GraphSettingTimeshift", null=True, blank=True)
    graph_setting_forecast = models.ForeignKey("backbone.GraphSettingForecast", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def to_enum(self):
        # rewrite scale and legend mode to full enum
        self.scale_mode = [_entry for _entry in GraphScaleModeEnum if _entry.value == self.scale_mode][0]
        self.legend_mode = [_entry for _entry in GraphLegendModeEnum if _entry.value == self.legend_mode][0]
        self.cf = [_entry for _entry in GraphCFEnum if _entry.value == self.cf][0]
        if self.graph_setting_forecast_id:
            self.graph_setting_forecast.mode = [
                _entry for _entry in GraphForecastModeEnum if _entry.value == self.graph_setting_forecast.mode
            ][0]

    class Meta:
        unique_together = [("user", "name")]

    def __unicode__(self):
        return "GraphSetting '{}'".format(self.name)


class GraphTimeFrame(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(max_length=64, default="", unique=True)
    # relative to now (for last X hours)
    relative_to_now = models.BooleanField(default=False)
    # auto_refresh flag
    auto_refresh = models.BooleanField(default=False)
    # lenght of timespan in seconds
    seconds = models.IntegerField(default=0)
    # base timeframe
    base_timeframe = models.CharField(
        max_length=4,
        default="d",
        choices=[
            ("h", "hour"),
            ("d", "day"),
            ("w", "week"),
            ("m", "month"),
            ("y", "year"),
            ("D", "decade"),
        ]
    )
    # timeframe offset, 0 means current <timeframe>, -1 means previous <timeframe> and so on
    timeframe_offset = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "GraphTimeFrame '{}'".format(self.name)

    class Meta:
        ordering = ("-relative_to_now", "timeframe_offset", "seconds",)
