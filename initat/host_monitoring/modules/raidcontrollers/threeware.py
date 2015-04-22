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
""" checks for Threeware RAID controller """

import re

from initat.host_monitoring import limits, hm_classes

from initat.tools import logging_tools
from initat.tools import server_command

from initat.host_monitoring.modules.raidcontrollers.base import ctrl_type, ctrl_check_struct


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


class ctrl_type_tw(ctrl_type):
    class Meta:
        name = "tw"
        exec_name = "tw_cli"
        description = "Threeware RAID Controller"

    def get_exec_list(self, ctrl_list=[]):
        if ctrl_list == []:
            ctrl_list = self._dict.keys()
        return ["{} info {}".format(self._check_exec, ctrl_id) for ctrl_id in ctrl_list]

    def scan_ctrl(self):
        cur_stat, cur_lines = self.exec_command(" info", post="strip")
        if not cur_stat:
            mode = None
            for line in cur_lines:
                # print "*", line
                line_p = line.split()
                if mode is None:
                    if line_p[0].lower() == "list":
                        # old mode
                        mode = 1
                    elif line_p[0].lower() == "ctl":
                        # new mode
                        mode = 2
                elif mode:
                    if line_p[0].lower().startswith("controller") and mode == 1:
                        if ("{} {}".format(line_p[2], line_p[3])).lower() == "not compatible.":
                            self._dict["c%d" % (int(line_p[1][:-1]))] = {
                                "type": "not compatible",
                                "info": "error not compatible"
                            }
                        else:
                            self._dict["c%d" % (int(line_p[1][:-1]))] = {"type": line_p[2]}
                    elif line_p[0].startswith("c") and mode == 2:
                        self._dict[line_p[0]] = {"type": line_p[1]}

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
        unit_match = re.compile("^\s+Unit\s*(?P<num>\d+):\s*(?P<raid>.*)\s+(?P<size>\S+\s+\S+)\s+\(\s*(?P<blocks>\d+)\s+\S+\):\s*(?P<status>.*)$")
        port_match = re.compile("^\s+Port\s*(?P<num>\d+):\s*(?P<info>[^:]+):\s*(?P<status>.*)\(unit\s*(?P<unit>\d+)\)$")
        u2_0_match = re.compile("^u(?P<num>\d+)\s+(?P<raid>\S+)\s+(?P<status>\S+)\s+(?P<cmpl>\S+)\s+(?P<stripe>\S+)\s+(?P<size>\S+)\s+(?P<cache>\S+)\s+.*$")
        u2_1_match = re.compile(
            "^u(?P<num>\d+)\s+(?P<raid>\S+)\s+(?P<status>\S+)\s+(?P<rcmpl>\S+)\s+(?P<cmpl>\S+)\s+(?P<stripe>\S+)"
            "\s+(?P<size>\S+)\s+(?P<cache>\S+)\s+(?P<avrfy>\S+)$"
        )
        p2_match = re.compile("^p(?P<num>\d+)\s+(?P<status>\S+)\s+u(?P<unit>\d+)\s+(?P<size>\S+\s+\S+)\s+(?P<blocks>\d+)\s+.*$")
        bbu_match = re.compile("^bbu\s+(?P<onlinestate>\S+)\s+(?P<ready>\S+)\s+(?P<status>\S+)\s+(?P<volt>\S+)\s+(?P<temp>\S+)\s+.*$")
        _com_line, com_type, ctrl_id = ccs.run_info["command"].strip().split()
        if com_type == "info":
            ctrl_result = {
                "type": self._dict[ctrl_id]["type"],
                "units": {},
                "ports": {}
            }
            if ccs.run_info["result"]:
                ctrl_result["error"] = "{} gave {:d}".format(ccs.run_info["comline"], ccs.run_info["result"])
            else:
                ctrl_result["error"] = "ok"
                lines = [line.strip() for line in ccs.read().split("\n") if line.strip()]
                num_units, _num_ports = (0, 0)
                l_mode = "c"
                if lines:
                    if lines[0].lower().strip().startswith("unit"):
                        # new format
                        if lines[0].lower().count("rcmpl"):
                            # new tw_cli
                            u2_match = u2_1_match
                        else:
                            # old tw_cli
                            u2_match = u2_0_match
                        for line in lines:
                            um = u2_match.match(line)
                            pm = p2_match.match(line)
                            bm = bbu_match.match(line)
                            if um:
                                ctrl_result["units"][um.group("num")] = {
                                    "raid": um.group("raid").strip(),
                                    "size": "{} GB".format(um.group("size").strip()),
                                    "ports": [],
                                    "status": um.group("status").strip(),
                                    "cmpl": um.group("cmpl")
                                }
                            elif pm:
                                ctrl_result["ports"][pm.group("num")] = {
                                    "status": pm.group("status").strip(),
                                    "unit": pm.group("unit")}
                                if pm.group("unit") in ctrl_result["units"]:
                                    ctrl_result["units"][pm.group("unit")]["ports"].append(pm.group("num"))
                            elif bm:
                                ctrl_result["bbu"] = {
                                    key: bm.group(key) for key in [
                                        "onlinestate",
                                        "ready",
                                        "status",
                                        "volt",
                                        "temp"
                                    ]
                                }
                    else:
                        for line in lines:
                            if line.startswith("# of unit"):
                                uc_m = re.match("^# of units\s*:\s*(\d+).*$", line)
                                if uc_m:
                                    num_units = uc_m.group(1)
                                l_mode = "u"
                            elif line.startswith("# of port"):
                                l_mode = "p"
                                pc_m = re.match("^# of ports\s*:\s*(\d+).*$", line)
                                if num_units and pc_m:
                                    _num_ports = pc_m.group(1)
                            elif l_mode == "u":
                                um = unit_match.match(line)
                                if um:
                                    cmpl_str, stat_str = ("???",
                                                          um.group("status").strip())
                                    if stat_str.lower().startswith("rebuil"):
                                        # try to exctract rebuild_percentage
                                        pc_m = re.match("^(?P<stat>\S+)\s+\((?P<perc>\d+)%\)$", stat_str)
                                        if pc_m:
                                            stat_str = pc_m.group("stat")
                                            cmpl_str = pc_m.group("perc")
                                    ctrl_result["units"][um.group("num")] = {
                                        "raid": um.group("raid").strip(),
                                        "size": um.group("size").strip(),
                                        "blocks": um.group("blocks").strip(),
                                        "ports": [],
                                        "status": stat_str,
                                        "cmpl": cmpl_str
                                    }
                            elif l_mode == "p":
                                pm = port_match.match(line)
                                if pm:
                                    ctrl_result["ports"][pm.group("num")] = {"info": pm.group("info").strip(),
                                                                             "status": pm.group("status").strip()}
                                    if pm.group("unit") in ctrl_result["units"]:
                                        ctrl_result["units"][pm.group("unit")]["ports"].append(pm.group("num"))
            ccs.srv_com["result:ctrl_{}".format(ctrl_id)] = ctrl_result
        else:
            pass
# #    def server_call(self, cm):
# #        ret_str = self.module_info.check_exec()
# #        if ret_str.startswith("ok"):
# #            ret_str = self.module_info.update_ctrl_dict()
# #            if ret_str.startswith("ok"):
# #                if cm:
# #                    ctrl_list = [x for x in cm if x in self.module_info.ctrl_dict.keys()]
# #                else:
# #                    ctrl_list = self.module_info.ctrl_dict.keys()
# #                ret_dict = {}
# #                for ctrl_id in ctrl_list:
# #                    ret_dict[ctrl_id] = self.module_info.check_controller(ctrl_id)
# #                ret_str = "ok %s" % (hm_classes.sys_to_net(ret_dict))
# #        return ret_str

    def _interpret(self, tw_dict, cur_ns):
        # if tw_dict.has_key("units"):
        #    tw_dict = {parsed_coms[0] : tw_dict}
        num_warn, num_error = (0, 0)
        ret_list = []
        if tw_dict:
            for ctrl, ctrl_dict in tw_dict.iteritems():
                info = ctrl_dict.get("info", "")
                if info.startswith("error"):
                    num_error += 1
                    ret_list.append("{} ({}): {} ".format(ctrl, ctrl_dict.get("type", "???"), info))
                else:
                    num_units, num_ports = (len(ctrl_dict["units"]), len(ctrl_dict["ports"]))
                    unit_info, port_info = ([], [])
                    # check units
                    for u_num, u_stuff in ctrl_dict["units"].iteritems():
                        l_status = u_stuff["status"].lower()
                        if l_status in ["degraded"]:
                            num_error += 1
                        elif l_status != "ok":
                            num_warn += 1
                        if u_stuff["raid"].lower() in ["jbod"]:
                            num_error += 1
                        unit_info.append(
                            "unit {} ({}, {}, {}): {}{}".format(
                                u_num,
                                u_stuff["raid"],
                                u_stuff["size"],
                                "/".join(u_stuff["ports"]),
                                u_stuff["status"],
                                (
                                    l_status.startswith("verify") or l_status.startswith("initia") or l_status.startswith("rebuild")
                                ) and " ({} %)".format(u_stuff.get("cmpl", "???")) or ""
                            )
                        )
                    for p_num, p_stuff in ctrl_dict["ports"].iteritems():
                        if p_stuff["status"].lower() != "ok":
                            num_error += 1
                            port_info.append("port {} (u{}): {}".format(p_num, p_stuff.get("unit", "???"), p_stuff["status"]))
                    if "bbu" in ctrl_dict:
                        bbu_errors, bbu_ok = ([], 0)
                        for key in sorted(ctrl_dict["bbu"].iterkeys()):
                            value = ctrl_dict["bbu"][key]
                            if value.lower() not in ["on", "ok", "yes"]:
                                bbu_errors.append((key, value))
                                num_error += 1
                            else:
                                bbu_ok += 1
                        bbu_str = "{} ok".format(logging_tools.get_plural("attribute", bbu_ok))
                        if bbu_errors:
                            bbu_str = "{}, {}".format("; ".join(["error {}: {}".format(key, value) for key, value in bbu_errors]), bbu_str)
                    else:
                        bbu_str = ""
                    ret_list.append(
                        "{} ({}) {:d}u/{:d}p: {}{}{}".format(
                            ctrl,
                            ctrl_dict.get("type", "???"),
                            num_units,
                            num_ports,
                            ",".join(unit_info),
                            port_info and "; {}".format(",".join(port_info)) or "",
                            ", BBU: {}".format(bbu_str) if bbu_str else ""
                        )
                    )
        else:
            ret_list.append("no controller found")
            num_error = 1
        if num_error:
            ret_state = limits.nag_STATE_CRITICAL
        elif num_warn:
            ret_state = limits.nag_STATE_WARNING
        else:
            ret_state = limits.nag_STATE_OK
        return ret_state, ", ".join(ret_list)


class tw_status_command(hm_classes.hm_command):
    info_string = "3ware controller information"

    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)

    def __call__(self, srv_com, cur_ns):
        ctrl_type.update("tw")
        if "arguments:arg0" in srv_com:
            ctrl_list = [srv_com["arguments:arg0"].text]
        else:
            ctrl_list = []
        if ctrl_type.ctrl("tw").update_ok(srv_com):
            return ctrl_check_struct(self.log, srv_com, ctrl_type.ctrl("tw"), ctrl_list)

    def interpret(self, srv_com, cur_ns):
        return self._interpret({srv_com._interpret_tag(cur_el, cur_el.tag): srv_com._interpret_el(cur_el) for cur_el in srv_com["result"]}, cur_ns)

    def interpret_old(self, result, parsed_coms):
        tw_dict = hm_classes.net_to_sys(result[3:])
        return self._interpret(tw_dict, parsed_coms)

    def _interpret(self, tw_dict, cur_ns):
        return ctrl_type.ctrl("tw")._interpret(tw_dict, cur_ns)
