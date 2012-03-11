#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2012 Andreas Lang-Nevyjel, init.at
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

import sys
import re
import commands
from host_monitoring import limits, hm_classes
import os
import os.path
import time
import logging_tools
import server_command

TW_EXEC = "/sbin/tw_cli"
ARCCONF_BIN = "/usr/sbin/arcconf"

CTRL_TYPES = ["tw"]

class ctrl_type(object):
    def __init__(self, module_struct):
        self.name = self.Meta.name
        # last scan date
        self.scanned = None
        # last check date
        self.checked = None
        self._dict = {}
        self._module = module_struct
        self._check_exec = None
        self.log("init")
    @staticmethod
    def init(module_struct):
        ctrl_type._all_types = {}
        for ctrl_struct in [glob_struct for glob_struct in globals().itervalues() if type(glob_struct) == type and issubclass(glob_struct, ctrl_type) and not glob_struct == ctrl_type]:
            ctrl_type._all_types[ctrl_struct.Meta.name] = ctrl_struct(module_struct)
        #for sub_class in globals()#
        #for type_name, exec_name in 
    @staticmethod
    def update(c_type, ctrl_ids=[]):
        if c_type is None:
            c_type = self._all_types.keys()
        elif type(c_type) != list:
            c_type = [c_type]
        for cur_type in c_type:
            ctrl_type._all_types[cur_type]._update(ctrl_ids)
    @staticmethod
    def ctrl(key):
        return ctrl_type._all_types[key]
    def exec_command(self, com_line, **kwargs):
        if com_line.startswith(" "):
            com_line = "%s%s" % (self._check_exec, com_line)
        cur_stat, cur_out = commands.getstatusoutput(com_line)
        lines = cur_out.split("\n")
        if cur_stat:
            self.log("%s gave %d:" % (com_line, cur_stat), logging_tools.LOG_LEVEL_ERROR)
            for line_num, cur_line in enumerate(lines):
                self.log("  %3d %s" % (line_num + 1, cur_line), logging_tools.LOG_LEVEL_ERROR)
        if "post" in kwargs:
            lines = [getattr(cur_line, kwargs["post"])() for cur_line in lines]
        if not kwargs.get("empty_ok", False):
            lines = [cur_line for cur_line in lines if cur_line.strip()]
        print cur_stat, lines
        return cur_stat, lines
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self._module.log("[ct %s] %s" % (self.name, what), log_level)
    def _scan(self):
        self.scanned = time.time()
        self.log("scanning for %s controller" % (self.name))
        self.check_for_exec()
        if self._check_exec:
            self.scan_ctrl()
    def _update(self, ctrl_ids):
        if not self.scanned:
            self._scan()
        self.update_ctrl(ctrl_ids)
    def check_for_exec(self):
        if self._check_exec is None:
            for s_path in ["/sbin", "/usr/sbin", "/bin", "/usr/bin"]:
                cur_path = os.path.join(s_path, self.Meta.exec_name)
                if os.path.isfile(cur_path):
                    self._check_exec = cur_path
                    break
        if self._check_exec:
            self.log("found check binary at '%s'" % (self._check_exec))
        else:
            self.log("no check binary '%s' found" % (self.Meta.exec_name),
                     logging_tools.LOG_LEVEL_ERROR)
    def controller_list(self):
        return self._dict.keys()
    def scan_ctrl(self):
        pass
    def update_ctrl(self):
        pass
    def update_ok(self, srv_com):
        if self._check_exec:
            return True
        else:
            srv_com["result"].attrib.update({"reply" : "monitoring tool '%s' missing" % (self.Meta.exec_name),
                                             "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
            return False

class ctrl_check_struct(hm_classes.subprocess_struct):
    def __init__(self, srv_com, ct_struct, ctrl_list=[]):
        hm_classes.subprocess_struct.__init__(self, srv_com, ct_struct.get_exec_list(), ct_struct.process)
        
class ctrl_type_tw(ctrl_type):
    class Meta:
        name = "tw"
        exec_name = "tw_cli"
        description = "Threeware RAID Controller"
    def get_exec_list(self, ctrl_list=[]):
        if ctrl_list == []:
            ctrl_list = self._dict.keys()
        return ["%s info %s" % (self._check_exec, ctr_id) for ctrl_id in ctrl_list]
    def scan_ctrl(self):
        cur_stat, cur_lines = self.exec_command(" info", post="strip")
        if not cur_stat:
            mode = None
            for line in cur_lines:
                print "*", line
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
                            self._dict["c%d" % (int(line_p[1][:-1]))] = {"type" : "not compatible",
                                                                         "info" : "error not compatible"}
                        else:
                            self._dict["c%d" % (int(line_p[1][:-1]))] = {"type"  : line_p[2]}
                    elif line_p[0].startswith("c") and mode == 2:
                        self._dict[line_p[0]] = {"type" : line_p[1]}
    def update_ctrl(self, ctrl_ids):
        print ctrl_ids
    def update_ok(self, srv_com):
        if self._dict:
            return ctrl_type.update_ok(self, srv_com)
        else:
            srv_com["result"].attrib.update({"reply" : "no controller found",
                                             "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
            return False
    def process(self, ccs, x):
        ccs.srv_com["result"] = "OK"
        
class _general(hm_classes.hm_module):
    def init_module(self):
        ctrl_type.init(self)
    def check_exec(self):
        if os.path.isfile(TW_EXEC):
            return "ok"
        else:
            return "error no %s found" % (TW_EXEC)
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
            return ctrl_check_struct(srv_com, ctrl_type.ctrl("tw"), ctrl_list)
    def _cb_func(self, sps_struct, cur_num=None):
        if cur_num is not None:
            ctrl_result = {}
            ctrl_id = sps_struct.cur_comline.split()[-1]
            if sps_struct.cur_result:
                ctrl_result["error"] = "%s gave %d" % (sps_struct.cur_comline, sps_struct.cur_result)
            else:
                ctrl_result["error"] = "ok"
                lines = [line.strip() for line in sps_struct.read().split("\n") if line.strip()]
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
                                ctrl_result["units"][um.group("num")] = {
                                    "raid"   : um.group("raid").strip(),
                                    "size"   : "%s GB" % (um.group("size").strip()),
                                    "ports"  : [],
                                    "status" : um.group("status").strip(),
                                    "cmpl"   : um.group("cmpl")}
                            elif pm:
                                ctrl_result["ports"][pm.group("num")] = {
                                    "status" : pm.group("status").strip(),
                                    "unit"   : pm.group("unit")}
                                if ctrl_result["units"].has_key(pm.group("unit")):
                                    ctrl_result["units"][pm.group("unit")]["ports"].append(pm.group("num"))
                            elif bm:
                                ctrl_result["bbu"] = dict([(key, bm.group(key)) for key in [
                                    "onlinestate",
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
                                    ctrl_result["units"][um.group("num")] = {
                                        "raid"   : um.group("raid").strip(),
                                        "size"   : um.group("size").strip(),
                                        "blocks" : um.group("blocks").strip(),
                                        "ports"  : [],
                                        "status" : stat_str,
                                        "cmpl"   : cmpl_str}
                            elif l_mode == "p":
                                pm = port_match.match(line)
                                if pm:
                                    ctrl_result["ports"][pm.group("num")] = {"info"   : pm.group("info").strip(),
                                                                             "status" : pm.group("status").strip()}
                                    if ctrl_result["units"].has_key(pm.group("unit")):
                                        ctrl_result["units"][pm.group("unit")]["ports"].append(pm.group("num"))
            sps_struct.srv_com.set_dictionary("result:ctrl_%s" % (ctrl_id), ctrl_result)
        else:
            pass
##    def server_call(self, cm):
##        ret_str = self.module_info.check_exec()
##        if ret_str.startswith("ok"):
##            ret_str = self.module_info.update_ctrl_dict()
##            if ret_str.startswith("ok"):
##                if cm:
##                    ctrl_list = [x for x in cm if x in self.module_info.ctrl_dict.keys()]
##                else:
##                    ctrl_list = self.module_info.ctrl_dict.keys()
##                ret_dict = {}
##                for ctrl_id in ctrl_list:
##                    ret_dict[ctrl_id] = self.module_info.check_controller(ctrl_id)
##                ret_str = "ok %s" % (hm_classes.sys_to_net(ret_dict))
##        return ret_str
    def interpret(self, srv_com, cur_ns):
        print unicode(srv_com)
        print cur_ns
    def interpret_old(self, result, parsed_coms):
        tw_dict = hm_classes.net_to_sys(result[3:])
        return self._interpret(tw_dict, parsed_coms)
    def _interpret(self, tw_dict, cur_ns):
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
            ret_state = limits.nag_STATE_CRITICAL
        elif num_warn:
            ret_state = limits.nag_STATE_WARNING
        else:
            ret_state = limits.nag_STATE_OK
        return ret_state, ", ".join(ret_list)

if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)
