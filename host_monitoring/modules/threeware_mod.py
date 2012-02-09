#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008 Andreas Lang-Nevyjel, init.at
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

import sys
import re
import commands
from host_monitoring import limits
from host_monitoring import hm_classes
import os
import os.path
import time
import logging_tools

TW_EXEC = "/sbin/tw_cli"

class my_modclass(hm_classes.hm_fileinfo):
    def __init__(self, **args):
        hm_classes.hm_fileinfo.__init__(self,
                                        "threeware",
                                        "provides a interface to check the status of threeware-cards",
                                        **args)
    def init(self, mode, logger, basedir_name, **args):
        self.__last_ctrl_check = (-1, -1)
        if mode == "i":
            self.ctrl_dict = None
    def needs_hourly_wakeup_call(self):
        return True
    def hourly_wakeup_call(self, logger):
        act_hour, act_day = (time.localtime()[3],
                             time.localtime()[6])
        # check every Friday at 02:00
        if (act_day == 4 and act_hour == 2):
            if self.__last_ctrl_check != (act_day, act_hour):
                ret_str = self.check_exec()
                if ret_str.startswith("ok"):
                    self.__last_ctrl_check = (act_day, act_hour)
                    ctrl_list = self.ctrl_dict.keys()
                    to_check = []
                    for c_name in ctrl_list:
                        c_stuff = self.check_controller(c_name)
                        c_type = c_stuff.get("type", "6200")
                        if c_type.startswith("6"):
                            logger.warning("skipping verify for 6xxx (local is a %s) - version controllers" % (c_type))
                        else:
                            for u_name, u_stuff in c_stuff["units"].iteritems():
                                if u_stuff["status"].lower() == "ok":
                                    to_check.append((c_type, c_name, u_name))
                                else:
                                    logger.warning("skipping verify for unit u%s on %s (%s, status is %s)" % (u_name, c_name, c_type, u_stuff["status"]))
                    if to_check:
                        logger.info("checking %s: %s" % (logging_tools.get_plural("unit", len(to_check)),
                                                         ", ".join(["u%s on %s (type %s)" % (u, c, t) for t, c, u in to_check])))
                        for c_type, c_name, u_name in to_check:
                            com_str = "%s maint verify %s u%s" % (TW_EXEC, c_name, u_name)
                            stat, out = commands.getstatusoutput(com_str)
                            if stat:
                                logger.error("'%s' gave (%d) %s" % (com_str, stat, out))
                            else:
                                logger.info("'%s' gave %s" % (com_str, out))
                else:
                    logger.error(ret_str)
    def check_exec(self):
        if os.path.isfile(TW_EXEC):
            return "ok"
        else:
            return "error no %s found" % (TW_EXEC)
    def update_ctrl_dict(self):
        ret_str = "ok"
        if self.ctrl_dict is None:
            self.ctrl_dict = {}
            stat, out = commands.getstatusoutput("%s info" % (TW_EXEC))
            if stat:
                ret_str = "error calling %s (%d): %s" % (TW_EXEC, stat, str(out))
            else:
                mode = None
                for line in [y for y in [x.strip() for x in out.split("\n")] if y]:
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
                            if ("%s %s" % (line_p[2], line_p[3])).lower() == "not compatible.":
                                self.ctrl_dict["c%d" % (int(line_p[1][:-1]))] = {"type" : "not compatible",
                                                                                 "info" : "error not compatible"}
                            else:
                                self.ctrl_dict["c%d" % (int(line_p[1][:-1]))] = {"type"  : line_p[2]}
                        elif line_p[0].startswith("c") and mode == 2:
                            self.ctrl_dict[line_p[0]] = {"type" : line_p[1]}
        return ret_str
    def check_controller(self, ctrl_id):
        unit_match = re.compile("^\s+Unit\s*(?P<num>\d+):\s*(?P<raid>.*)\s+(?P<size>\S+\s+\S+)\s+\(\s*(?P<blocks>\d+)\s+\S+\):\s*(?P<status>.*)$")
        port_match = re.compile("^\s+Port\s*(?P<num>\d+):\s*(?P<info>[^:]+):\s*(?P<status>.*)\(unit\s*(?P<unit>\d+)\)$")
        u2_0_match = re.compile("^u(?P<num>\d+)\s+(?P<raid>\S+)\s+(?P<status>\S+)\s+(?P<cmpl>\S+)\s+(?P<stripe>\S+)\s+(?P<size>\S+)\s+(?P<cache>\S+)\s+.*$")
        u2_1_match = re.compile("^u(?P<num>\d+)\s+(?P<raid>\S+)\s+(?P<status>\S+)\s+(?P<rcmpl>\S+)\s+(?P<cmpl>\S+)\s+(?P<stripe>\S+)\s+(?P<size>\S+)\s+(?P<cache>\S+)\s+(?P<avrfy>\S+)$")
        p2_match   = re.compile("^p(?P<num>\d+)\s+(?P<status>\S+)\s+u(?P<unit>\d+)\s+(?P<size>\S+\s+\S+)\s+(?P<blocks>\d+)\s+.*$")
        bbu_match  = re.compile("^bbu\s+(?P<onlinestate>\S+)\s+(?P<ready>\S+)\s+(?P<status>\S+)\s+(?P<volt>\S+)\s+(?P<temp>\S+)\s+.*$")
        ctrl_dict = {"type"  : self.ctrl_dict[ctrl_id]["type"],
                     "units" : {},
                     "ports" : {}}
        if self.ctrl_dict[ctrl_id].has_key("info"):
            ctrl_dict["info"] = self.ctrl_dict[ctrl_id]["info"]
        else:
            stat, out = commands.getstatusoutput("%s info %s" % (TW_EXEC, ctrl_id))
            if stat:
                ctrl_dict["info"] = "error calling %s (%d): %s" % (TW_EXEC, stat, str(out))
            else:
                ctrl_dict["info"] = "ok"
                lines = [y for y in [x.rstrip() for x in out.strip().split("\n")] if y]
                num_units, num_ports = (0, 0)
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
                                ctrl_dict["units"][um.group("num")] = {"raid"   : um.group("raid").strip(),
                                                                       "size"   : "%s GB" % (um.group("size").strip()),
                                                                       "ports"  : [],
                                                                       "status" : um.group("status").strip(),
                                                                       "cmpl"   : um.group("cmpl")}
                            elif pm:
                                ctrl_dict["ports"][pm.group("num")] = {"status" : pm.group("status").strip(),
                                                                       "unit"   : pm.group("unit")}
                                if ctrl_dict["units"].has_key(pm.group("unit")):
                                    ctrl_dict["units"][pm.group("unit")]["ports"].append(pm.group("num"))
                            elif bm:
                                ctrl_dict["bbu"] = dict([(key, bm.group(key)) for key in ["onlinestate",
                                                                                          "ready",
                                                                                          "status",
                                                                                          "volt",
                                                                                          "temp"]])
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
                                    num_ports = pc_m.group(1)
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
                                    ctrl_dict["units"][um.group("num")] = {"raid"   : um.group("raid").strip(),
                                                                           "size"   : um.group("size").strip(),
                                                                           "blocks" : um.group("blocks").strip(),
                                                                           "ports"  : [],
                                                                           "status" : stat_str,
                                                                           "cmpl"   : cmpl_str}
                            elif l_mode == "p":
                                pm = port_match.match(line)
                                if pm:
                                    ctrl_dict["ports"][pm.group("num")] = {"info"   : pm.group("info").strip(),
                                                                           "status" : pm.group("status").strip()}
                                    if ctrl_dict["units"].has_key(pm.group("unit")):
                                        ctrl_dict["units"][pm.group("unit")]["ports"].append(pm.group("num"))
        return ctrl_dict

class tw_status_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "tw_status", **args)
        self.help_str = "returns the status of installed threeware-controllers"
        self.is_immediate = False
        self.cache_timeout = 60
    def server_call(self, cm):
        ret_str = self.module_info.check_exec()
        if ret_str.startswith("ok"):
            ret_str = self.module_info.update_ctrl_dict()
            if ret_str.startswith("ok"):
                if cm:
                    ctrl_list = [x for x in cm if x in self.module_info.ctrl_dict.keys()]
                else:
                    ctrl_list = self.module_info.ctrl_dict.keys()
                ret_dict = {}
                for ctrl_id in ctrl_list:
                    ret_dict[ctrl_id] = self.module_info.check_controller(ctrl_id)
                ret_str = "ok %s" % (hm_classes.sys_to_net(ret_dict))
        return ret_str
    def client_call(self, result, parsed_coms):
        if result.startswith("ok "):
            tw_dict = hm_classes.net_to_sys(result[3:])
            if tw_dict.has_key("units"):
                tw_dict = {parsed_coms[0] : tw_dict}
            num_warn, num_error = (0, 0)
            ret_list = []
            if tw_dict:
                for ctrl, ctrl_dict in tw_dict.iteritems():
                    info = ctrl_dict["info"]
                    if info.startswith("error"):
                        num_error += 1
                        ret_list.append("%s (%s): %s " % (ctrl, ctrl_dict.get("type", "???"), info))
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
                            unit_info.append("unit %s (%s, %s, %s): %s%s" % (u_num,
                                                                             u_stuff["raid"],
                                                                             u_stuff["size"],
                                                                             "/".join(u_stuff["ports"]),
                                                                             u_stuff["status"],
                                                                             (l_status.startswith("verify") or l_status.startswith("initia") or l_status.startswith("rebuild")) and " (%s %%)" % (u_stuff.get("cmpl", "???")) or ""))
                        for p_num, p_stuff in ctrl_dict["ports"].iteritems():
                            if p_stuff["status"].lower() != "ok":
                                num_error += 1
                                port_info.append("port %s (u%s): %s" % (p_num, p_stuff.get("unit", "???"), p_stuff["status"]))
                        if ctrl_dict.has_key("bbu"):
                            bbu_errors, bbu_ok = ([], 0)
                            for key in sorted(ctrl_dict["bbu"].iterkeys()):
                                value = ctrl_dict["bbu"][key]
                                if value.lower() not in ["on", "ok", "yes"]:
                                    bbu_errors.append((key, value))
                                    num_error += 1
                                else:
                                    bbu_ok += 1
                            bbu_str = "%s ok" % (logging_tools.get_plural("attribute", bbu_ok))
                            if bbu_errors:
                                bbu_str = "%s, %s" % ("; ".join(["error %s: %s" % (key, value) for key, value in bbu_errors]), bbu_str)
                        else:
                            bbu_str = ""
                        ret_list.append("%s (%s) %du/%dp: %s%s%s" % (ctrl,
                                                                     ctrl_dict.get("type", "???"),
                                                                     num_units,
                                                                     num_ports,
                                                                     ",".join(unit_info),
                                                                     port_info and "; %s" % (",".join(port_info)) or "",
                                                                     ", BBU: %s" % (bbu_str) if bbu_str else ""))
            else:
                ret_list.append("no controller found")
                num_error = 1
            if num_error:
                ret_state, ret_str = (limits.nag_STATE_CRITICAL, "ERROR")
            elif num_warn:
                ret_state, ret_str = (limits.nag_STATE_WARNING, "WARNING")
            else:
                ret_state, ret_str = (limits.nag_STATE_OK, "OK")
            return ret_state, "%s: %s" % (ret_str, ", ".join(ret_list))
        else:
            return limits.nag_STATE_CRITICAL, "error %s" % (resulto)

if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)
