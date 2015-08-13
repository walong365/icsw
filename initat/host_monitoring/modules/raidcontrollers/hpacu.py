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
""" checks for HPACU Controllers """

import re

from initat.host_monitoring import limits, hm_classes
from initat.tools import logging_tools, server_command
from initat.host_monitoring.modules.raidcontrollers.base import ctrl_type, ctrl_check_struct


def get_size(in_str):
    try:
        s_p, p_p = in_str.split()
        return float(s_p) * {
            "k": 1000,
            "m": 1000 * 1000,
            "g": 1000 * 1000 * 1000,
            "t": 1000 * 1000 * 1000 * 1000
        }.get(p_p[0].lower(), 1)
    except:
        return 0


def _split_config_line(line):
    key, val = line.split(":", 1)
    key = key.lower().strip().replace(" ", "_")
    val = val.strip()
    if val.isdigit():
        val = int(val)
    elif val.lower() == "enabled":
        val = True
    elif val.lower() == "disabled":
        val = False
    return key, val


class ctrl_type_hpacu(ctrl_type):
    class Meta:
        name = "hpacu"
        exec_name = ["hpssacli", "hpacucli"]
        description = "HP Acu controller"

    def get_exec_list(self, ctrl_list=[]):
        if ctrl_list == []:
            ctrl_list = self._dict.keys()
        return ["%s ctrl slot=%d show config detail" % (self._check_exec, self._dict[ctrl_id]["config"]["slot"]) for ctrl_id in ctrl_list]

    def scan_ctrl(self):
        slot_re = re.compile(".*in\s+slot\s+(?P<slot>\d+)\s+.*", re.IGNORECASE)
        cur_stat, cur_lines = self.exec_command(" ctrl all show", post="strip")
        if not cur_stat:
            num_ctrl = len([True for line in cur_lines if line.lower().count("smart array")])
            if num_ctrl:
                for ctrl_num, _line in enumerate(cur_lines, 1):
                    _slot_m = slot_re.match(_line)
                    if _slot_m:
                        slot_num = int(_slot_m.group("slot"))
                    else:
                        _parts = cur_lines[ctrl_num - 1].strip().split()
                        try:
                            slot_num = int(_parts[-2])
                        except:
                            slot_num = int(_parts[-4])
                    _c_stat, c_result = self.exec_command(" ctrl slot={:d} show status".format(slot_num))
                    ctrl_stuff = {}
                    ctrl_stuff["config"] = {"slot": slot_num}
                    for key, val in [_split_config_line(line) for line in c_result if line.count(":")]:
                        ctrl_stuff["config"][key] = val
                    self._dict[ctrl_num] = ctrl_stuff

    def update_ctrl(self, ctrl_ids):
        pass
        # print ctrl_ids

    def update_ok(self, srv_com):
        if self._dict:
            return ctrl_type.update_ok(self, srv_com)
        else:
            srv_com.set_result(
                "no controller found",
                server_command.SRV_REPLY_STATE_ERROR
            )
            return False

    def process(self, ccs):
        c_dict = {}
        act_ctrl, act_array, act_log, act_phys, act_obj, act_pmgroup = (
            None, None, None, None, None, None)
        for c_line in ccs.read().split("\n"):
            l_line = c_line.lower().strip()
            if l_line.count("in slot"):
                is_idx = l_line.index("in slot")
                c_num = int(l_line[is_idx + len("in slot"):].strip().split()[0])
                act_ctrl = {
                    "info": c_line[0:is_idx].strip(),
                    "arrays": {},
                    "config": {}
                }
                c_dict[c_num] = act_ctrl
                act_array, act_log, act_phys, act_pmgroup = (
                    None, None, None, None)
                act_obj = act_ctrl
                continue
            if act_ctrl is not None:
                if l_line.startswith("array:"):
                    act_array = {
                        "logicals": {},
                        "physicals": {},
                        "config": {},
                    }
                    array_num = " ".join(c_line.split()[1:])
                    if array_num not in act_ctrl["arrays"]:
                        act_ctrl["arrays"][array_num] = act_array
                    act_phys, act_log, act_pmgroup = (None, None, None)
                    act_obj = act_array
                    continue
                if act_array is not None:
                    if l_line.startswith("logical drive:"):
                        l_num = int(l_line.split()[-1])
                        act_log = {
                            "config": {},
                            "parity_groups": {},
                            "mirror_groups": {},
                        }
                        act_array["logicals"][l_num] = act_log
                        act_phys = None
                        act_obj = act_log
                        continue
                    elif l_line.startswith("physicaldrive"):
                        if act_pmgroup:
                            act_pmgroup["drives"].append(l_line.strip())
                        else:
                            pos_info = c_line.split()[-1].replace(":", "_")
                            act_phys = {
                                "config": {},
                            }
                            act_array["physicals"][pos_info] = act_phys
                            act_log = None
                            act_obj = act_phys
                        continue
                    elif l_line.startswith("parity group"):
                        # parity and mirror groups are below logical drive, take care
                        pos_info = c_line.split()[-1].replace(":", "")
                        act_pmgroup = {"drives": []}
                        act_log["parity_groups"][pos_info] = act_pmgroup
                        act_obj = act_pmgroup
                        continue
                    elif l_line.startswith("mirror group"):
                        pos_info = c_line.split()[-1].replace(":", "")
                        act_pmgroup = {"drives": []}
                        act_log["mirror_groups"][pos_info] = act_pmgroup
                        act_obj = act_pmgroup
                        continue
            if not l_line.strip():
                if act_pmgroup:
                    # clear parity group
                    act_pmgroup = None
            if l_line.count(":") and act_obj:
                key, value = self._interpret_line(l_line)
                if "config" not in act_obj and act_pmgroup:
                    # data type tag after mirror / parity groups
                    act_pmgroup = None
                    act_obj = act_log
                act_obj["config"][key] = value
            # else:
            #    if l_line.count("status"):
            #        c_dict[act_ctrl]["status"][l_line.split()[0]] = " ".join(l_line.split()[2:])
        ccs.srv_com["result:ctrl"] = c_dict

    def _interpret_line(self, in_line):
        key, value = in_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        key = key.replace(" ", "_")
        if key.endswith("_status"):
            pass
        elif key.count("temperature"):
            value = float(value)
        elif key == "logical_drive_label":
            # remove binary values from label, stupid HP
            value = "".join([cur_c for cur_c in value if ord(cur_c) > 32 and ord(cur_c) < 80])
        elif value.isdigit():
            value = int(value)
        if key.endswith("temperature_(c)"):
            key = key[:-4]
        key = key.replace("(", "").replace(")", "")
        return key, value

    def _interpret(self, ctrl_dict, cur_ns):
        num_cont, num_array, num_log, num_phys = (0, 0, 0, 0)
        array_names, size_log, size_phys = ([], [], 0)
        # pprint.pprint(c_dict)
        error_f, _warn_f = ([], [])
        if "ctrl" not in ctrl_dict and len(ctrl_dict):
            ctrl_dict = {"ctrl": ctrl_dict}
            new_style = False
        else:
            new_style = True
        for slot_num, c_stuff in ctrl_dict.get("ctrl", {}).iteritems():
            num_cont += 1
            # new code
            if new_style:
                status_dict = {
                    key: value for key, value in c_stuff.get("config", {}).iteritems() if key.count("status") and not key.count("6_adg")
                }
            else:
                status_dict = {
                    key: value for key, value in c_stuff.get("status", {}).iteritems()
                }
            if set(status_dict.values()) != set(["ok", "not redundant"]):
                error_f.append(
                    "status of controller {} (slot {:d}): {}".format(
                        c_stuff["info"],
                        slot_num,
                        ", ".join(
                            [
                                "{}: {}".format(key, value) for key, value in status_dict.iteritems() if value != "ok"
                            ]
                        )
                    )
                )
            for array_name, array_stuff in c_stuff["arrays"].iteritems():
                array_names.append("{} in slot {:d}".format(array_name, slot_num))
                num_array += 1
                for log_num, log_stuff in array_stuff["logicals"].iteritems():
                    num_log += 1
                    if "config" in log_stuff:
                        # new format
                        _lc = log_stuff["config"]
                        size_log.append(get_size(_lc["size"]))
                        if _lc["status"].lower() != "ok":
                            error_f.append(
                                "status of log.drive %d (array {}) is {} ({}{})".format(
                                    log_num,
                                    array_name,
                                    _lc["status"],
                                    _lc["fault_tolerance"],
                                    ", {}".format(_lc.get("parity_initialization_status", ""))
                                )
                            )
                    else:
                        size_log.append(get_size(log_stuff["size_info"]))
                        if log_stuff["status_info"].lower() != "okx":
                            error_f.append(
                                "status of log.drive {:d} (array {}) is {} ({})".format(
                                    log_num,
                                    array_name,
                                    log_stuff["status_info"],
                                    log_stuff["raid_info"],
                                )
                            )
                for _phys_num, phys_stuff in array_stuff["physicals"].iteritems():
                    num_phys += 1
                    _pc = phys_stuff["config"]
                    size_phys += get_size(_pc["size"])
                    if _pc["status"].lower() != "ok":
                        pos_info = "port {}, box {}, bay {}".format(_pc["port"], _pc["box"], _pc["bay"])
                        error_f.append(
                            "status of phys.drive {} (array {}) is {} ({})".format(
                                pos_info,
                                array_name,
                                _pc["status"],
                                _pc["drive_type"]
                            )
                        )
        if error_f:
            ret_state, ret_str = (limits.nag_STATE_CRITICAL, "Error")
            error_str = ", {}: {}".format(logging_tools.get_plural("error", len(error_f)), ", ".join(error_f))
        else:
            ret_state, ret_str = (limits.nag_STATE_OK, "OK")
            error_str = ""
        if num_array:
            return ret_state, "{}: {}, {} ({}), {} ({}), {} ({}){}".format(
                ret_str,
                logging_tools.get_plural("controller", num_cont),
                logging_tools.get_plural("array", num_array),
                ", ".join(array_names),
                logging_tools.get_plural("log.drive", num_log),
                "+".join([logging_tools.get_size_str(act_size_log) for act_size_log in size_log]),
                logging_tools.get_plural("phys.drive", num_phys),
                logging_tools.get_size_str(size_phys),
                error_str
            )
        else:
            return ret_state, "{}: {}, {} ({}), {} ({}){}".format(
                ret_str,
                logging_tools.get_plural("controller", num_cont),
                logging_tools.get_plural("log.drive", num_log),
                "+".join([logging_tools.get_size_str(act_size_log) for act_size_log in size_log]),
                logging_tools.get_plural("phys.drive", num_phys),
                logging_tools.get_size_str(size_phys),
                error_str
            )


class hpacu_status_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        ctrl_type.update("hpacu")
        ctrl_list = []
        return ctrl_check_struct(self.log, srv_com, ctrl_type.ctrl("hpacu"), ctrl_list)

    def interpret_old(self, result, cur_ns):
        ctrl_dict = hm_classes.net_to_sys(result[3:])
        return self._interpret(ctrl_dict, cur_ns)

    def interpret(self, srv_com, cur_ns):
        return self._interpret({srv_com._interpret_tag(cur_el, cur_el.tag): srv_com._interpret_el(cur_el) for cur_el in srv_com["result"]}, cur_ns)

    def _interpret(self, ctrl_dict, cur_ns):
        return ctrl_type.ctrl("hpacu")._interpret(ctrl_dict, cur_ns)
