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
    # config via meta device
    meta_config = "meta_config"
    # config directly
    config = "config"
    # check via meta device
    meta_check = "meta_check"
    # check directly
    check = "check"


@attr.s
class MonCheckUsage(object):
    """
    helper object to determine which devices / groups use a certain
    moncheck
    """
    mc = attr.ib()
    devices = attr.ib(default=defaultdict(set))

    def find_usage(self):
        # configs
        mc = self.mc
        # all configs
        configs = mc.config_rel.all().prefetch_related("device_config_set__device")
        for conf in configs:
            for dc in conf.device_config_set.all().select_related("device"):
                if dc.device.is_meta_device:
                    # resolve devices
                    for dev in dc.device.get_group_devices():
                        self.devices[dev.idx].add(MCUEnum.meta_config)
                else:
                    self.devices[dc.device.idx].add(MCUEnum.config)
        # direct devices
        for dev in mc.devices.all():
            if dev.is_meta_device:
                for sub_dev in dev.get_group_devices():
                    self.devices[sub_dev.idx].add(MCUEnum.meta_check)
            else:
                self.devices[dev.idx].add(MCUEnum.check)
        # import pprint
        # pprint.pprint(self.devices)
        # for chaining
        return self

    def serialize(self):
        return {
            idx: [_enum.value for _enum in enum_list] for idx, enum_list in self.devices.items()
        }
