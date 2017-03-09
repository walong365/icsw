#
# this file is part of icsw-server
#
# Copyright (C) 2013-2017 Andreas Lang-Nevyjel init.at
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
""" helper structures for weathermap """

import json
import os
import rrdtool
import shutil
import subprocess
import time
import re
from enum import Enum
import attr

from django.db.models import Q
from lxml.builder import E

from initat.cluster.backbone.models import device, netdevice
from initat.tools import logging_tools, process_tools, rrd_tools, server_mixins
from .collectd_types.base import collectdMVValue, PerfdataObject
from .config import global_config

_WM_LIST = [
    "net\.(?P<netdevice>.*)\.(?P<ndspec>.*)",
    "load\.(?P<loadval>\d+)",
    "mem\.(avail|free|used)\.(?P<memspec>.*)",
]

WM_KEYS = re.compile(
    "^({})$".format(
        "|".join(_WM_LIST)
    )
)


class WMTypeEnum(Enum):
    network = "network"
    load = "load"
    memory = "memory"


@attr.s(slots=True)
class WMValue(object):
    """
    this is in fact similiar to the MachinVectorEntries
    notable differences:
    - no detailed info about description, base, type
    + preparsed weathermap info (base type, detailed spec)
    """
    key = attr.ib()
    # type enum
    wm_type = attr.ib()
    # database index of object (netdevice for example)
    db_idx = attr.ib(default=0)
    # detailed spec (tail of network info, load timeframe [1, 5, 15])
    spec = attr.ib(default="")
    # latest update
    feed_time = attr.ib(default=0.0)
    # value
    value = attr.ib(default=0.0)

    def feed_value(self, value, cur_time):
        self.feed_time = cur_time
        self.value = value.real_value
        # print("*", self)

    def is_valid(self, cur_time):
        return True if abs(self.feed_time - cur_time) < 120 else False

    def get_json_dump(self):
        return {
            "key": self.key,
            "wm_type": self.wm_type.value,
            "db_idx": self.db_idx,
            "spec": self.spec,
            "value": self.value,
        }

    def get_wm_info(self):
        return E.key(
            key=self.key,
            value=str(self.value),
            wm_type=str(self.wm_type.value),
            db_idx="{:d}".format(self.db_idx),
            spec=self.spec,
        )

    @classmethod
    def interpret_wm_info(cls, wm_el):
        return cls(
            key=wm_el.attrib["key"],
            wm_type=WMTypeEnum(wm_el.attrib["wm_type"]),
            db_idx=int(wm_el.attrib["db_idx"]),
            spec=wm_el.attrib["spec"],
            value=float(wm_el.attrib["value"])
        )

    def get_form_entry(self, idx, max_num_keys):
        act_line = [
            logging_tools.form_entry(self.wm_type.value, header="Type"),
            logging_tools.form_entry(self.db_idx, header="db_idx"),
            logging_tools.form_entry(self.spec, header="Spec"),
        ]
        sub_keys = (self.key.split(".") + [""] * max_num_keys)[0:max_num_keys]
        for key_idx, sub_key in zip(range(max_num_keys), sub_keys):
            act_line.append(
                logging_tools.form_entry(
                    "{}{}".format(
                        "" if (key_idx == 0 or sub_key == "") else ".", sub_key
                    ),
                    header="key{:d}".format(key_idx)
                )
            )
        # check for unknow
        if self.value is None:
            # unknown value
            act_pf, val_str = ("", "<unknown>")
        else:
            act_pf, val_str = self._get_val_str(self.value)
        act_line.extend(
            [
                logging_tools.form_entry_right(val_str, header="value"),
                logging_tools.form_entry_right(act_pf, header=" "),
                logging_tools.form_entry("({:3d})".format(idx), header="idx"),
            ]
        )
        return act_line

    def _get_val_str(self, val):
        act_pf = ""
        pf_list = ["k", "M", "G", "T", "E", "P"]
        while val > 100:
            act_pf = pf_list.pop(0)
            val = float(val) / 1000.
        val_str = "{:>14.3f}".format(val)
        return act_pf, val_str


class WMMatcher(object):
    def __init__(self, chi: object):
        # one structure per collectdhostinfo
        self.chi = chi
        self._wm_keys = set()
        self._wm_dict = {}
        self._ignore_dict = {}

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.chi.log("[WM] {}".format(what), log_level)

    def feed_vector(self, in_dict: dict) -> list:
        cur_time = time.time()
        # print("*", self.chi.mc_key, in_dict)
        for key, value in in_dict.items():
            if key in self._wm_keys:
                # match
                self._wm_dict[key].feed_value(value, cur_time)
            elif key in self._ignore_dict and abs(cur_time - self._ignore_dict[key]) < 60:
                pass
            else:
                match_obj = WM_KEYS.match(key)
                if match_obj:
                    # new match
                    gd = match_obj.groupdict()
                    if gd["netdevice"]:
                        wmt = WMTypeEnum.network
                        # find netdevice
                        try:
                            db_idx = netdevice.objects.values_list(
                                "idx", flat=True
                            ).get(
                                Q(device=self.chi.device.idx) &
                                Q(devname=gd["netdevice"])
                            )
                        except netdevice.DoesNotExist:
                            wmt = None
                        else:
                            spec = gd["ndspec"]
                    elif gd["loadval"]:
                        wmt = WMTypeEnum.load
                        db_idx = 0
                        spec = gd["loadval"]
                    elif gd["memspec"]:
                        wmt = WMTypeEnum.memory
                        db_idx = 0
                        spec = gd["memspec"]
                    else:
                        wmt = None
                    if wmt:
                        self._wm_keys.add(key)
                        self._wm_dict[key] = WMValue(key, wmt, db_idx=db_idx, spec=spec)
                        self._wm_dict[key].feed_value(value, cur_time)
                    else:
                        self._ignore_dict[key] = cur_time
        return [
            _value.get_json_dump() for key, _value in self._wm_dict.items() if _value.is_valid(cur_time)
        ]

    def append_to_host_info(self, host_info: object, key_filter: object):
        """
        Append WM-Info Structures to host-info
        :param host_info:
        :param key_filter:
        :return:
        """
        for key in sorted(self._wm_dict.keys()):
            if key_filter.match(key):
                host_info.append(
                    self._wm_dict[key].get_wm_info()
                )