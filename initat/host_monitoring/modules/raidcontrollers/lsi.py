# Copyright (C) 2001-2008,2012-2015 Andreas Lang-Nevyjel, init.at
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
""" checks for various RAID controllers """

import re

from initat.host_monitoring import limits, hm_classes
import logging_tools

from initat.host_monitoring.modules.raidcontrollers.base import ctrl_type, ctrl_check_struct


class ctrl_type_lsi(ctrl_type):
    class Meta:
        name = "lsi"
        exec_name = "cfggen"
        description = "LSI 1030 RAID Controller"

    def get_exec_list(self, ctrl_list=[]):
        if ctrl_list == []:
            ctrl_list = self._dict.keys()
        return ["{} {} DISPLAY".format(self._check_exec, ctrl_id[3:]) for ctrl_id in ctrl_list]

    def scan_ctrl(self):
        cur_stat, cur_lines = self.exec_command(" LIST", super_strip=True)
        if not cur_stat:
            c_ids = set()
            for line in cur_lines:
                if line.split()[0].isdigit():
                    c_ids.add("ioc{}".format(line.split()[0]))
            self._dict = {key: {} for key in c_ids}

    def update_ctrl(self, ctrl_ids):
        pass
        # print ctrl_ids

    def process(self, ccs):
        ctrl_id = "ioc{}".format(ccs.run_info["command"].split()[1])
        ctrl_dict = self._dict[ctrl_id]
        cur_mode = None
        # pacify checker
        vol_dict, phys_dict = ({}, {})
        to_int = set(["device", "function", "maximum_physical_devices", "size", "slot", "enclosure"])
        for line in ccs.read().split("\n"):
            if line.strip():
                space_line = line[0] == " "
                if line.count("information") and not space_line:
                    cur_mode = {
                        "con": "c",
                        "ir ": "v",
                        "phy": "p",
                        "enc": "e"
                    }.get(line.lower()[0:3], None)
                elif line.startswith("---"):
                    pass
                else:
                    if cur_mode:
                        if space_line:
                            # print cur_mode, "s", line
                            if line.count(":"):
                                key, value = line.strip().split(":", 1)
                                key = (" ".join(key.strip().lower().split("(")[0].split()))
                                if key.endswith("#"):
                                    key = key[:-1].strip()
                                key = key.replace(" ", "_")
                                value = value.strip()
                                if key in to_int or key.endswith("_id"):
                                    try:
                                        value = int(value.split("/")[0])
                                    except:
                                        pass
                                if cur_mode == "c":
                                    ctrl_dict[key] = value
                                elif cur_mode == "v":
                                    vol_dict[key] = value
                                elif cur_mode == "p":
                                    phys_dict[key] = value
                        else:
                            # print cur_mode, line
                            if cur_mode == "v":
                                vol_dict = {}
                                ctrl_dict.setdefault("volumes", {})[line.split()[-1]] = vol_dict
                            if cur_mode == "p":
                                phys_dict = {}
                                if "volumes" in ctrl_dict:
                                    vol_dict.setdefault("disks", {})[line.split()[-1].replace("#", "")] = phys_dict
        ccs.srv_com["result:ctrls"] = self._dict
        return
        # code mpt-status, not used any more
        ctrl_re = re.compile(
            "^(?P<c_name>\S+) vol_id (?P<vol_id>\d+) type (?P<c_type>\S+), (?P<num_discs>\d+) "
            "phy, (?P<size>\S+) (?P<size_pfix>\S+), state (?P<state>\S+), flags (?P<flags>\S+)"
        )
        disk_re = re.compile(
            "^(?P<c_name>\S+) phy (?P<phy_id>\d+) scsi_id (?P<scsi_id>\d+) (?P<disk_info>.*), "
            "(?P<size>\S+) (?P<size_pfix>\S+), state (?P<state>\S+), flags (?P<flags>\S+)$"
        )
        to_int = ["num_discs", "vol_id", "phy_id", "scsi_id"]
        to_float = ["size"]
        for line in ccs.read().split("\n"):
            if line.strip():
                line = " ".join(line.split())
                for re_type, cur_re in [("c", ctrl_re), ("d", disk_re)]:
                    cur_m = cur_re.match(line)
                    if cur_m:
                        break
                if cur_m:
                    cur_dict = cur_m.groupdict()
                    for key, value in cur_dict.iteritems():
                        if key in to_int:
                            cur_dict[key] = int(value)
                        elif key in to_float:
                            cur_dict[key] = float(value)
                    if re_type == "c":
                        self._dict[cur_dict["c_name"]] = cur_dict
                        self._dict[cur_dict["c_name"]]["disks"] = []
                    elif cur_m:
                        self._dict[cur_dict["c_name"]]["disks"].append(cur_dict)
        ccs.srv_com["result:ctrls"] = self._dict

    def _interpret(self, in_dict, cur_ns):
        if "ctrls" in in_dict and in_dict["ctrls"]:
            ret_state = limits.nag_STATE_OK
            c_array = []
            for c_name in sorted(in_dict["ctrls"]):
                ctrl_dict = in_dict["ctrls"][c_name]
                vol_list = []
                for vol_key in sorted(ctrl_dict.get("volumes", {})):
                    vol_dict = ctrl_dict["volumes"][vol_key]
                    vol_stat = vol_dict["status_of_volume"].split()[0]
                    vol_list.append(
                        "vol{}, RAID{}, {}, {}".format(
                            vol_key,
                            vol_dict["raid_level"],
                            logging_tools.get_size_str(vol_dict["size"] * 1024 * 1024),
                            vol_stat,
                        )
                    )
                    if vol_stat.lower() != "okay":
                        ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                c_array.append("{} ({}{}){}".format(
                    c_name,
                    ctrl_dict["controller_type"],
                    ", {}".format(logging_tools.get_plural("volume", len(ctrl_dict.get("volumes", {})))) if vol_list else "",
                    ": {}".format(", ".join(vol_list)) if vol_list else "",
                ))
            return ret_state, "; ".join(c_array)
        else:
            return limits.nag_STATE_WARNING, "no controller found"


class lsi_status_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)

    def __call__(self, srv_com, cur_ns):
        ctrl_type.update("lsi")
        if "arguments:arg0" in srv_com:
            ctrl_list = [srv_com["arguments:arg0"].text]
        else:
            ctrl_list = []
        return ctrl_check_struct(self.log, srv_com, ctrl_type.ctrl("lsi"), ctrl_list)

    def interpret(self, srv_com, cur_ns):
        return self._interpret({srv_com._interpret_tag(cur_el, cur_el.tag): srv_com._interpret_el(cur_el) for cur_el in srv_com["result"]}, cur_ns)

    def _interpret(self, ctrl_dict, cur_ns):
        return ctrl_type.ctrl("lsi")._interpret(ctrl_dict, cur_ns)

