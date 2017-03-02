# Copyright (C) 2008-2017 Andreas Lang-Nevyjel, init.at
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
""" cache of various settings and luts for md-config-server """

from collections import defaultdict
from enum import Enum
from django.db.models import Q
import attr
from initat.cluster.backbone.models import device, mon_check_command

__all__ = [
    "MonCheckEmitter",
    "MonCheckUsage",
]


class MonCheckEmitter(object):
    # holds the mon_checks to generate
    def __init__(
        self,
        master_build: bool,
        host_filter: object,
        monitor_server: int=0,
        single_build: bool=False,
    ):
        # filter for all configs, wider than the h_filter
        ac_filter = Q()
        if master_build:
            # need all devices for master
            pass
        else:
            host_filter &= Q(monitor_server=monitor_server)
            ac_filter &= Q(monitor_server=monitor_server)
        if not single_build:
            host_filter &= Q(enabled=True) & Q(device_group__enabled=True)
            ac_filter &= Q(enabled=True) & Q(device_group__enabled=True)
        self.host_pk_list = device.objects.exclude(
            Q(is_meta_device=True)
        ).filter(
            host_filter
        ).values_list(
            "pk", flat=True
        )
        import pprint
        # dict of all check_commands per device
        cc_per_dev = defaultdict(set)
        _DEBUG = False
        if _DEBUG:
            # debug: eddie == 3
            # uptime (uptime), check command (uptime) == 3, 79
            # ac_filter &= Q(name="eddie")
            print("Hosts: ", list(self.host_pk_list))

        # Step 1: meta devices, check_commands via config, resolve devices via device_group

        for _entry in device.objects.filter(
            Q(
                is_meta_device=True,
                device_config__config__mcc_rel__isnull=False,
                device_config__config__mcc_rel__enabled=True,
                # device_group__device_group__name="eddie",
            )
        ).values_list(
            # tuple format:
            # - device idx (from meta device)
            "device_group__device_group",
            # - mcc index via config
            "device_config__config__mcc_rel",
        ).order_by(
            "device_group__device_group",
            "device_config__config__mcc_rel",
        ).distinct():
            # distinct beacuse a config check can be referenced multiple times
            cc_per_dev[_entry[0]].add(_entry[1])
        if _DEBUG:
            print("s1")
            pprint.pprint(cc_per_dev)

        # Step 2: meta devices, check_commands via direct mon_check, resolve
        # devices via device_group
        for _entry in device.objects.filter(
            Q(
                is_meta_device=True,
                mcc_devices__isnull=False,
                mcc_devices__enabled=True,
            )
        ).values_list(
            # device idx
            "device_group__device_group",
            # direct devices
            "mcc_devices",
        ).distinct():
            if _entry[1] in cc_per_dev[_entry[0]]:
                # already set, interpret as exclusion
                cc_per_dev[_entry[0]].remove(_entry[1])
            else:
                cc_per_dev[_entry[0]].add(_entry[1])
        if _DEBUG:
            print("s2")
            pprint.pprint(cc_per_dev)

        # Step 3: check commands per device via configs

        for _entry in device.objects.filter(
            ac_filter
        ).filter(
            Q(
                device_config__config__mcc_rel__isnull=False,
                device_config__config__mcc_rel__enabled=True,
            )
        ).values_list(
            # device idx
            "idx",
            # mcc via config
            "device_config__config__mcc_rel",
        ).distinct():
            cc_per_dev[_entry[0]].add(_entry[1])

        if _DEBUG:
            print("s3")
            pprint.pprint(cc_per_dev)

        # Step 4: check commands per device direct via mcc

        for _entry in device.objects.filter(
            ac_filter
        ).filter(
            Q(
                mcc_devices__isnull=False,
                mcc_devices__enabled=True,
            )
        ).values_list(
            "idx",
            "mcc_devices",
        ).distinct():
            if _entry[1] in cc_per_dev[_entry[0]]:
                # interpret as exlcusion
                cc_per_dev[_entry[0]].remove(_entry[1])
            else:
                cc_per_dev[_entry[0]].add(_entry[1])
        if _DEBUG:
            print("s4")
            pprint.pprint(cc_per_dev)

        # final debug dump

        if _DEBUG:
            # dump result
            for _key, _values in cc_per_dev.items():
                _dev = device.objects.get(Q(idx=_key))
                if _values:
                    print(
                        "Checks for device {} ({:d}, count={:d})".format(
                            str(_dev),
                            _dev.idx,
                            len(_values)
                        )
                    )
                    for _val in _values:
                        print(
                            "   [{:d}] {}".format(
                                _val,
                                mon_check_command.objects.filter(Q(idx=_val))
                            )
                        )
        # result
        self._result = cc_per_dev

    def __getitem__(self, key):
        return self._result[key]


class MCUEnum(Enum):
    none = "none"
    # config (on group or device level)
    config = "config"
    # config inheritted from parent
    config_meta = "config_meta"
    # check (on group or device level)
    check = "check"
    # check inheritted from parent
    check_meta = "check_meta"


@attr.s
class MCUNode(object):

    value = attr.ib(default=attr.Factory(set))
    configs = attr.ib(default=attr.Factory(set))
    # for devices
    meta_configs = attr.ib(default=attr.Factory(set))
    idx = attr.ib(default=0)
    type = attr.ib(default="")

    def add(self, enum: enumerate, config_idx: int=None):
        self.value.add(enum)
        if config_idx:
            self.configs.add(config_idx)

    def inherit_from(self, parent: object):
        # inherit settings from parent
        for _enum in parent.value:
            self.value.add(
                {
                    MCUEnum.config: MCUEnum.config_meta,
                    MCUEnum.check: MCUEnum.check_meta,
                }[_enum]
            )
        for _config in parent.configs:
            self.meta_configs.add(_config)

    @property
    def node_id(self):
        return "{}{:d}".format(
            self.type,
            self.idx,
        )

    def prepare_json(self):
        # rewrites all enum in value to strings
        self.value = set(
            [
                _enum.value for _enum in self.value
            ]
        )
        return self


@attr.s
class MonCheckUsage(object):
    """
    helper object to determine which devices / groups use a certain
    moncheck
    """
    mc = attr.ib()
    groups = attr.ib(default=attr.Factory(dict))

    def feed_group(self, dev):
        if dev.device_group_id not in self.groups:
            self.groups[dev.device_group_id] = {
                "children": {},
                "node": MCUNode(idx=dev.device_group.device.idx, type="dg")
            }
        return self.groups[dev.device_group_id]["node"]

    def feed_device(self, dev):
        self.feed_group(dev)
        _group = self.groups[dev.device_group_id]
        if dev.idx not in _group["children"]:
            _group["children"][dev.idx] = MCUNode(idx=dev.idx, type="d")
        return _group["children"][dev.idx]

    def find_usage(self):
        # configs
        mc = self.mc
        # all configs
        configs = mc.config_rel.all().prefetch_related("device_config_set__device")
        for conf in configs:
            for dc in conf.device_config_set.all().select_related("device"):
                if dc.device.is_meta_device:
                    self.feed_group(dc.device).add(MCUEnum.config, dc.config_id)
                    # resolve devices
                    for dev in dc.device.get_group_devices():
                        self.feed_device(dev)
                else:
                    self.feed_device(dc.device).add(MCUEnum.config, dc.config_id)
        # direct devices
        for dev in mc.devices.all():
            if dev.is_meta_device:
                self.feed_group(dev).add(MCUEnum.check)
                for sub_dev in dev.get_group_devices():
                    self.feed_device(sub_dev)
            else:
                self.feed_device(dev).add(MCUEnum.check)
        for g_idx, g_stuff in self.groups.items():
            [
                dev_obj.inherit_from(g_stuff["node"]) for dev_obj in g_stuff["children"].values()
            ]
        # import pprint
        # pprint.pprint(self.groups)
        # for chaining
        return self

    def serialize(self):
        from initat.cluster.backbone.serializers import mon_check_command_serializer
        # flatten structure
        # top level
        top_level = {
            "data": mon_check_command_serializer(self.mc).data,
            "id": "root",
        }
        _result = [top_level]
        for g_idx, g_stuff in self.groups.items():
            if g_stuff["children"]:
                # only add non-empty groups
                g_level = {
                    "id": g_stuff["node"].node_id,
                    "data": attr.asdict(g_stuff["node"].prepare_json()),
                    "parent": top_level["id"],
                }
                _result.append(g_level)
                for d_idx, d_stuff in g_stuff["children"].items():
                    d_level = {
                        "id": d_stuff.node_id,
                        "data": attr.asdict(d_stuff.prepare_json()),
                        "parent": g_level["id"],
                    }
                    _result.append(d_level)
        return _result
