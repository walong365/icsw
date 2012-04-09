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
import datetime
import logging_tools
import server_command
import pprint
import base64
import marshal
import bz2

TW_EXEC = "/sbin/tw_cli"
ARCCONF_BIN = "/usr/sbin/arcconf"

# WTF ?
def get_short_state(in_state):
    return in_state.lower()

def get_size(in_str):
    try:
        s_p, p_p = in_str.split()
        return float(s_p) * {"k" : 1000,
                             "m" : 1000 * 1000,
                             "g" : 1000 * 1000 * 1000,
                             "t" : 1000 * 1000 * 1000 * 1000}.get(p_p[0].lower(), 1)
    except:
        return 0

def to_size_str(in_size):
    rst, idx = (in_size, 0)
    while rst > 1000:
        rst /= 1000
        idx += 1
    return "%.2f %sB" % (rst, {0 : "",
                               1 : "k",
                               2 : "M",
                               3 : "G",
                               4 : "T"}[idx])

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

class dummy_mod(object):
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        print "[%d] %s" % (log_level, what)
        
class ctrl_type(object):
    _all_types = None
    def __init__(self, module_struct, **kwargs):
        self.name = self.Meta.name
        # last scan date
        self.scanned = None
        # last check date
        self.checked = None
        self._dict = {}
        self._module = module_struct
        self._check_exec = None
        if not kwargs.get("quiet", False):
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
        if ctrl_type._all_types:
            return ctrl_type._all_types[key]
        else:
            return globals()["ctrl_type_%s" % (key)](dummy_mod(), quiet=True)
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
        #print cur_stat, lines
        return cur_stat, lines
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self._module.log("[ct %s] %s" % (self.name, what), log_level)
    def _scan(self):
        self.scanned = time.time()
        self.log("scanning for %s controller" % (self.name))
        self.check_for_exec()
        if self._check_exec:
            self.log("scanning for %s" % (self.Meta.description))
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
        # override to scan for controllers
        pass
    def update_ctrl(self, *args):
        # override to update controllers, args optional
        pass
    def update_ok(self, srv_com):
        # return True if update is OK, can be overrided to add more checks (maybe arguments)
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
        return ["%s info %s" % (self._check_exec, ctrl_id) for ctrl_id in ctrl_list]
    def scan_ctrl(self):
        cur_stat, cur_lines = self.exec_command(" info", post="strip")
        if not cur_stat:
            mode = None
            for line in cur_lines:
                #print "*", line
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
    def process(self, ccs):
        unit_match = re.compile("^\s+Unit\s*(?P<num>\d+):\s*(?P<raid>.*)\s+(?P<size>\S+\s+\S+)\s+\(\s*(?P<blocks>\d+)\s+\S+\):\s*(?P<status>.*)$")
        port_match = re.compile("^\s+Port\s*(?P<num>\d+):\s*(?P<info>[^:]+):\s*(?P<status>.*)\(unit\s*(?P<unit>\d+)\)$")
        u2_0_match = re.compile("^u(?P<num>\d+)\s+(?P<raid>\S+)\s+(?P<status>\S+)\s+(?P<cmpl>\S+)\s+(?P<stripe>\S+)\s+(?P<size>\S+)\s+(?P<cache>\S+)\s+.*$")
        u2_1_match = re.compile("^u(?P<num>\d+)\s+(?P<raid>\S+)\s+(?P<status>\S+)\s+(?P<rcmpl>\S+)\s+(?P<cmpl>\S+)\s+(?P<stripe>\S+)\s+(?P<size>\S+)\s+(?P<cache>\S+)\s+(?P<avrfy>\S+)$")
        p2_match   = re.compile("^p(?P<num>\d+)\s+(?P<status>\S+)\s+u(?P<unit>\d+)\s+(?P<size>\S+\s+\S+)\s+(?P<blocks>\d+)\s+.*$")
        bbu_match  = re.compile("^bbu\s+(?P<onlinestate>\S+)\s+(?P<ready>\S+)\s+(?P<status>\S+)\s+(?P<volt>\S+)\s+(?P<temp>\S+)\s+.*$")
        com_line, com_type, ctrl_id = ccs.run_info["command"].strip().split()
        if com_type == "info":
            ctrl_result = {
                "type"  : self._dict[ctrl_id]["type"],
                "units" : {},
                "ports" : {}}
            if ccs.run_info["result"]:
                ctrl_result["error"] = "%s gave %d" % (ccs.run_info["comline"], ccs.run_info["result"])
            else:
                ctrl_result["error"] = "ok"
                lines = [line.strip() for line in ccs.read().split("\n") if line.strip()]
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
            ccs.srv_com.set_dictionary("result:ctrl_%s" % (ctrl_id), ctrl_result)
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
    def _interpret(self, tw_dict, cur_ns):
        if tw_dict.has_key("units"):
            tw_dict = {parsed_coms[0] : tw_dict}
        num_warn, num_error = (0, 0)
        ret_list = []
        if tw_dict:
            for ctrl, ctrl_dict in tw_dict.iteritems():
                info = ctrl_dict.get("info", "")
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
        
class ctrl_type_ips(ctrl_type):
    class Meta:
        name = "ips"
        exec_name = "arcconf"
        description = "Adapatec AAC RAID Controller"
    def get_exec_list(self, ctrl_ids=[]):
        ctrl_ids = ctrl_ids or self._dict.keys()
        return [("%s getconfig %d AL" % (self._check_exec, ctrl_id),
                 "config", ctrl_id) for ctrl_id in ctrl_ids] + \
               [("%s getstatus %d" % (self._check_exec, ctrl_id),
                 "status", ctrl_id) for ctrl_id in ctrl_ids]               
    def scan_ctrl(self):
        cur_stat, cur_lines = self.exec_command(" getversion", post="strip")
        if not cur_stat:
            num_ctrl = len([True for line in cur_lines if line.lower().count("controller #")])
            if num_ctrl:
                for ctrl_num in range(1, num_ctrl + 1):
                    ctrl_stuff = {"last_al_lines" : []}
                    # get config for every controller
                    c_stat, c_result = self.exec_command(" getconfig %d AD" % (ctrl_num))
                    ctrl_stuff["config"] = {}
                    for key, val in [_split_config_line(line) for line in c_result if line.count(":")]:
                        ctrl_stuff["config"][key] = val
                    self._dict[ctrl_num] = ctrl_stuff
    def update_ok(self, srv_com):
        if self._dict:
            return ctrl_type.update_ok(self, srv_com)
        else:
            srv_com["result"].attrib.update({"reply" : "no controller found",
                                             "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
            return False
    def process(self, ccs):
        com_line, com_type, ctrl_num = ccs.run_info["command"].strip().split()
        if com_type == "config":
            ctrl_config = {"logical"    : {},
                           "array"      : {},
                           "channel"    : {},
                           "physical"   : [],
                           "controller" : {}}
            act_part, prev_line = ("", "")
            for line in ccs.read().split("\n"):
                ls = line.strip()
                lsl = ls.lower()
                if prev_line.startswith("-" * 10) and line.endswith("information"):
                    act_part = " ".join(line.split()[0:2]).lower().replace(" ", "_").replace("drive", "device")
                elif line.lower().startswith("command complet") or line.startswith("-" * 10):
                    pass
                else:
                    if act_part == "logical_device":
                        if line.lower().count("logical device number") or line.lower().count("logical drive number"):
                            act_log_drv_num = int(line.split()[-1])
                            ctrl_config["logical"][act_log_drv_num] = {}
                        elif line.lower().strip().startswith("logical device name"):
                            array_name = ls.split()[1]
                            ctrl_config["array"][array_name] = " ".join(line.lower().strip().split()[2:])
                        elif line.count(":"):
                            key, val = _split_config_line(line)
                            ctrl_config["logical"][act_log_drv_num][key] = val
                    elif act_part == "physical_device":
                        if lsl.startswith("channel #"):
                            act_channel_num = int(lsl[-2])
                            ctrl_config["channel"][act_channel_num] = {}
                            act_scsi_stuff = None
                        elif lsl.startswith("device #"):
                            act_scsi_id = int(lsl[-1])
                            act_channel_num = -1
                            act_scsi_stuff = {}
                        elif lsl.startswith("reported channel,device"):
                            act_scsi_id = int(lsl.split(",")[-1])
                            if act_channel_num == -1:
                                act_channel_num = int(lsl.split(",")[-2].split()[-1])
                                ctrl_config["channel"][act_channel_num] = {}
                            ctrl_config["channel"][act_channel_num][act_scsi_id] = " ".join(lsl.split()[:-4])
                            act_scsi_stuff["channel"] = act_channel_num
                            act_scsi_stuff["scsi_id"] = act_scsi_id
                            ctrl_config["channel"][act_channel_num][act_scsi_id] = act_scsi_stuff
                            ctrl_config["physical"].append(act_scsi_stuff)
                        elif line.count(":"):
                            if act_scsi_stuff is not None:
                                key, val = _split_config_line(line)
                                act_scsi_stuff[key] = val
                    elif act_part == "controller_information":
                        if lsl.count(":"):
                            key, value = [entry.strip() for entry in lsl.split(":", 1)]
                            ctrl_config["controller"][key] = value
                    #print act_part, linea
                prev_line = line
            self._dict[ctrl_num].update(ctrl_config)
        elif com_type == "status":
            task_list = []
            act_task = None
            for line in ccs.read().split("\n"):
                lline = line.lower()
                if lline.startswith("logical device task"):
                    act_task = {"header" : lline}
                elif act_task:
                    if lline.count(":"):
                        key, value = [part.strip().lower() for part in lline.split(":", 1)]
                        act_task[key] = value
                if not lline.strip():
                    if act_task:
                        task_list.append(act_task)
                        act_task = None
            self._dict[ctrl_num]["config"]["task_list"] = task_list
        if ctrl_num == max(self._dict.keys()) and com_type == "status":
            ccs.srv_com["ips_dict_base64"] = base64.b64encode(bz2.compress(marshal.dumps(self._dict)))
    def _interpret(self, aac_dict, cur_ns):
        num_warn, num_error = (0, 0)
        ret_f = []
        for c_num, c_stuff in aac_dict.iteritems():
            #pprint.pprint(c_stuff)
            act_field = []
            if c_stuff["logical"]:
                log_field = []
                for l_num, l_stuff in c_stuff["logical"].iteritems():
                    sold_name = "status_of_logical_device" if l_stuff.has_key("status_of_logical_device") else "status_of_logical_drive"
                    log_field.append("ld%d: %s (%s, %s)" % (l_num,
                                                            logging_tools.get_size_str(int(l_stuff["size"].split()[0]) * 1000000, divider=1000).strip(),
                                                            "RAID%s" % (l_stuff["raid_level"]) if l_stuff.has_key("raid_level") else "RAID?",
                                                            get_short_state(l_stuff[sold_name])))
                    if l_stuff[sold_name].lower() in ["degraded"]:
                        num_error += 1
                    elif l_stuff[sold_name].lower() not in ["optimal", "okay"]:
                        num_warn += 1
                act_field.extend(log_field)
            if c_stuff["physical"]:
                phys_dict = {}
                for phys in c_stuff["physical"]:
                    if phys.has_key("size"):
                        s_state = get_short_state(phys["state"])
                        if s_state == "sby":
                            # ignore empty standby bays
                            pass
                        else:
                            if s_state not in ["onl", "hsp", "optimal", "online"]:
                                num_error += 1
                            con_info = ""
                            if phys.has_key("reported_location"):
                                cd_info = phys["reported_location"].split(",")
                                if len(cd_info) == 2:
                                    try:
                                        con_info = "c%d.%d" % (int(cd_info[0].split()[-1]),
                                                               int(cd_info[1].split()[-1]))
                                    except:
                                        con_info = "error parsing con_info %s" % (phys["reported_location"])
                            phys_dict.setdefault(s_state, []).append("c%d/id%d%s" % (phys["channel"],
                                                                                     phys["scsi_id"],
                                                                                     " (%s)" % (con_info) if con_info else ""))
                act_field.extend(["%s: %s" % (key, ",".join(phys_dict[key])) for key in sorted(phys_dict.keys())])
            if "task_list" in c_stuff:
                for act_task in c_stuff["task_list"]:
                    act_field.append("%s on logical device %s: %s, %d %%" % (act_task.get("header", "unknown task"),
                                                                             act_task.get("logical device", "?"),
                                                                             act_task.get("current operation", "unknown op"),
                                                                             int(act_task.get("percentage complete", "0"))))
            # check controller warnings
            ctrl_field = []
            if c_stuff["controller"]:
                ctrl_dict = c_stuff["controller"]
                c_stat = ctrl_dict.get("controller status", "")
                if c_stat:
                    ctrl_field.append("status %s" % (c_stat))
                    if c_stat.lower() not in ["optimal", "okay"]:
                        num_error += 1
                ov_temp = ctrl_dict.get("over temperature", "")
                if ov_temp:
                    if ov_temp == "yes":
                        num_error += 1
                        ctrl_field.append("over temperature")
            ret_f.append("c%d (%s): %s" % (c_num,
                                           ", ".join(ctrl_field) or "---",
                                           ", ".join(act_field)))
            if num_error:
                ret_state = limits.nag_STATE_CRITICAL
            elif num_warn:
                ret_state = limits.nag_STATE_WARNING
            else:
                ret_state = limits.nag_STATE_OK
        if not ret_f:
            return limits.nag_STATE_WARNING, "no controller information found"
        else:
            return ret_state, "; ".join(ret_f)
            
class ctrl_type_megaraid_sas(ctrl_type):
    class Meta:
        name = "megaraid_sas"
        exec_name = "megarc"
        description = "MegaRAID SAS"
    def get_exec_list(self, ctrl_list=[]):
        if ctrl_list == []:
            ctrl_list = self._dict.keys()
        return ["%s info %s" % (self._check_exec, ctr_id) for ctrl_id in ctrl_list]
    def scan_ctrl(self):
        cur_stat, cur_lines = self.exec_command(" info", post="strip")
    def update_ctrl(self, ctrl_ids):
        print ctrl_ids
    def update_ok(self, srv_com):
        if self._dict:
            return ctrl_type.update_ok(self, srv_com)
        else:
            srv_com["result"].attrib.update({"reply" : "no controller found",
                                             "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
            return False
    def process(self, ccs):
        ccs.srv_com["result"] = "OK"
    def _interpret(self, ctrl_dict, cur_ns):
        num_c, num_d, num_e = (len(ctrl_dict.keys()), 0, 0)
        ret_state = limits.nag_STATE_OK
        drive_stats = []
        for ctrl_num, ctrl_stuff in ctrl_dict.iteritems():
            for log_num, log_stuff in ctrl_stuff.get("logical_lines", {}).iteritems():
                log_dict = dict([(key.lower(), value) for key, value in log_stuff])
                num_d += 1
                if "state" in log_dict:
                    status = log_dict["state"]
                    if status.lower() != "optimal":
                        num_e += 1
                    drive_stats.append("ld %d (ctrl %d, %s): %s" % (log_num,
                                                                    ctrl_num,
                                                                    log_dict.get("size", "???"),
                                                                    status))
        if num_e:
            ret_state = limits.nag_STATE_CRITICAL
        return ret_state, "%s: %s on %s, %s" % (limits.get_state_str(ret_state),
                                                logging_tools.get_plural("logical drive", num_d),
                                                logging_tools.get_plural("controller", num_c),
                                                ", ".join(drive_stats))
        
class ctrl_type_megaraid(ctrl_type):
    class Meta:
        name = "megaraid"
        exec_name = "megarc"
        description = "MegaRAID"
    def get_exec_list(self, ctrl_list=[]):
        if ctrl_list == []:
            ctrl_list = self._dict.keys()
        return ["%s info %s" % (self._check_exec, ctr_id) for ctrl_id in ctrl_list]
    def scan_ctrl(self):
        cur_stat, cur_lines = self.exec_command(" info", post="strip")
    def update_ctrl(self, ctrl_ids):
        print ctrl_ids
    def update_ok(self, srv_com):
        if self._dict:
            return ctrl_type.update_ok(self, srv_com)
        else:
            srv_com["result"].attrib.update({"reply" : "no controller found",
                                             "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
            return False
    def process(self, ccs):
        ccs.srv_com["result"] = "OK"
    def _interpret(self, ctrl_dict, cur_ns):
        num_c, num_d, num_e = (len(ctrl_dict.keys()), 0, 0)
        ret_state, ret_str = (limits.nag_STATE_OK, "OK")
        drive_stats = []
        for ctrl_num, ctrl_stuff in ctrl_dict.iteritems():
            for log_num, log_stuff in ctrl_stuff.get("logical_lines", {}).iteritems():
                num_d += 1
                for line in log_stuff:
                    if line.lower().startswith("logical drive") and line.lower().count("status"):
                        status = line.split()[-1]
                        if status.lower() != "optimal":
                            num_e += 1
                        drive_stats.append("ld %d (ctrl %d): %s" % (log_num,
                                                                    ctrl_num,
                                                                    status))
        if num_e:
            ret_state, ret_str = (limits.nag_STATE_CRITICAL, "Error")
        return ret_state, "%s: %s on %s, %s" % (ret_str,
                                                logging_tools.get_plural("logical drive", num_d),
                                                logging_tools.get_plural("controller", num_c),
                                                ", ".join(drive_stats))
 
class ctrl_type_gdth(ctrl_type):
    class Meta:
        name = "gdth"
        exec_name = "true"
        description = "GDTH"
    def get_exec_list(self, ctrl_list=[]):
        if ctrl_list == []:
            ctrl_list = self._dict.keys()
        return ["/bin/true %s" % (ctrl_id) for ctrl_id in ctrl_list]
    def scan_ctrl(self):
        gdth_dir = "/proc/scsi/gdth"
        if os.path.isdir(gdth_dir):
            for entry in os.listdir(gdth_dir):
                self._dict[entry] = {}
    def update_ctrl(self, ctrl_ids):
        print ctrl_ids
    def update_ok(self, srv_com):
        if self._dict:
            return ctrl_type.update_ok(self, srv_com)
        else:
            srv_com["result"].attrib.update({"reply" : "no controller found",
                                             "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
            return False
    def process(self, ccs):
        com_line, ctrl_id = ccs.run_info["command"].strip().split()
        ctrl_file = "/proc/scsi/gdth/%s" % (ctrl_id)
        last_log_line, last_log_time = ("", None)
        act_time = datetime.datetime(*time.localtime()[0:6])
        lines = [line.rstrip() for line in file(ctrl_file, "r").read().split("\n")]
        act_mode = "?"
        pd_dict, ld_dict, ad_dict, hd_dict = ({}, {}, {}, {})
        for line in lines:
            if line.lower().startswith("driver parameter"):
                act_mode = "dp"
                act_dp_dict = {}
            elif line.lower().startswith("disk array control"):
                act_mode = "ci"
            elif line.lower().startswith("physical devices"):
                act_mode = "pd"
            elif line.lower().startswith("logical drives"):
                act_mode = "ld"
                act_ld_dict = {}
            elif line.lower().startswith("array drives"):
                act_mode = "ad"
                act_ad_dict = {}
            elif line.lower().startswith("host drives"):
                act_mode = "hd"
                act_hd_dict = {}
            elif line.lower().startswith("controller even"):
                act_mode = "ce"
            elif line.strip():
                #print "%s %s" % (act_mode, line)
                if act_mode == "pd":
                    left_str, right_str = (line[0:27].strip(), line[27:].strip())
                    for act_str in [x for x in [left_str, right_str] if x]:
                        key, value = [x.strip() for x in act_str.split(":", 1)]
                        act_dp_dict[key.lower()] = value
                        if key.lower() == "grown defects":
                            pd_dict[len(pd_dict)] = act_dp_dict
                            act_dp_dict = {}
                elif act_mode == "ld":
                    left_str, right_str = (line[0:27].strip(), line[27:].strip())
                    for act_str in [x for x in [left_str, right_str] if x]:
                        key, value = [x.strip() for x in act_str.split(":", 1)]
                        act_ld_dict[key.lower()] = value
                        if key.lower().startswith("to array dr"):
                            if act_ld_dict.has_key("status"):
                                ld_dict[len(ld_dict)] = act_ld_dict
                            act_ld_dict = {}
                elif act_mode == "ad":
                    if len(line.strip()) > 10:
                        left_str, right_str = (line[0:27].strip(), line[27:].strip())
                        for act_str in [x for x in [left_str, right_str] if x]:
                            key, value = [x.strip() for x in act_str.split(":", 1)]
                            act_ad_dict[key.lower()]=value
                            if key.lower().startswith("type"):
                                ad_dict[len(ad_dict)] = act_ad_dict
                                act_ad_dict = {}
                elif act_mode == "hd":
                    left_str, right_str = (line[0:27].strip(), line[27:].strip())
                    for act_str in [x for x in [left_str, right_str] if x]:
                        key, value = [x.strip() for x in act_str.split(":", 1)]
                        act_hd_dict[key.lower()] = value
                        if key.lower().startswith("start secto"):
                            hd_dict[len(hd_dict)] = act_hd_dict
                            act_hd_dict = {}
                elif act_mode == "ce":
                    if line.strip().startswith("date-"):
                        line_p = line.strip().split(None, 2)
                        line_d, last_log_line = ([int(x) for x in line_p[1].split(":")], line_p[2])
                        time_t = datetime.timedelta(0, line_d[0] * 3600 + line_d[1] * 60 + line_d[2])
                        last_log_time = act_time - time_t
        ret_dict = {
            "pd" : pd_dict,
            "ld" : ld_dict,
            "ad" : ad_dict,
            "hd" : hd_dict,
            "log" : (last_log_time, last_log_line)}
        ccs.srv_com.set_dictionary("result:ctrl_%s" % (ctrl_id), ret_dict)
    def _interpret(self, ctrl_dict, cur_ns):
        if ctrl_dict.keys()[0].startswith("ctrl_"):
            ctrl_dict = ctrl_dict.values()[0]
        pd_list, ld_list, ad_list, hd_list = (ctrl_dict["pd"], ctrl_dict["ld"], ctrl_dict["ad"], ctrl_dict["hd"])
        if type(pd_list) == type({}):
            # rewrite dict to list
            pd_list = [pd_list[key] for key in sorted(pd_list.keys())]
            ld_list = [ld_list[key] for key in sorted(ld_list.keys())]
            ad_list = [ad_list[key] for key in sorted(ad_list.keys())]
            hd_list = [hd_list[key] for key in sorted(hd_list.keys())]
        last_log_time, last_log_line = ctrl_dict.get("log", (None, ""))
        out_f, num_w, num_e = ([], 0, 0)
        for l_type, what, lst in [("p", "physical disc", pd_list),
                                  ("l", "logical drive", ld_list),
                                  ("a", "array drive"  , ad_list),
                                  ("h", "host drive"   , hd_list)]:
            if lst:
                num = len(lst)
                cap = reduce(lambda x, y : x+y, [int(x["capacity [mb]"]) for x in lst if x.has_key("capacity [mb]")])
                loc_out = ["%s (%s)" % (logging_tools.get_plural(what, num),
                                        ", ".join([entry for entry in ["%.2f GB" % (float(cap)/1024) if cap else "",
                                                                       ", ".join([x["type"] for x in lst if x.has_key("type")]) if lst[0].has_key("type") else ""] if entry]))]
                if lst[0].has_key("status"):
                    loc_warn = [x for x in lst if x["status"].lower() in ["rebuild", "build", "rebuild/patch"]]
                    loc_err  = [x for x in lst if x["status"].lower() not in ["ok", "ready", "rebuild", "build", "rebuild/patch", "ready/patch"]]
                    if loc_warn:
                        num_w += 1
                        loc_out.append(", ".join(["%s %s: %s" % (what, x["number"], x["status"]) for x in loc_warn]))
                    if loc_err:
                        num_e += 1
                        loc_out.append(", ".join(["%s %s: %s" % (what, x["number"], x["status"]) for x in loc_err]))
                out_f.append(";".join(loc_out))
            else:
                out_f.append("no %ss" % (what))
        if num_e:
            ret_state, ret_str = (limits.nag_STATE_CRITICAL, "Error")
        elif num_w:
            ret_state, ret_str = (limits.nag_STATE_WARNING, "Warning")
        else:
            ret_state, ret_str = (limits.nag_STATE_OK, "OK")
        if last_log_line:
            # change ret_state if ret_state == STATE_OK:
            if ret_state == limits.nag_STATE_OK:
                lll = last_log_line.lower().strip()
                if lll.endswith("started"):
                    ret_state, ret_str = (limits.nag_STATE_WARNING, "Warning")
            out_f.append(last_log_line)
        return ret_state, "%s: %s" % (ret_str, ", ".join(out_f))

class ctrl_type_hpacu(ctrl_type):
    class Meta:
        name = "hpacu"
        exec_name = "true"
        description = "HP Acu controller"
    def get_exec_list(self, ctrl_list=[]):
        if ctrl_list == []:
            ctrl_list = self._dict.keys()
        return ["%s info %s" % (self._check_exec, ctr_id) for ctrl_id in ctrl_list]
    def scan_ctrl(self):
        cur_stat, cur_lines = self.exec_command(" info", post="strip")
    def update_ctrl(self, ctrl_ids):
        print ctrl_ids
    def update_ok(self, srv_com):
        if self._dict:
            return ctrl_type.update_ok(self, srv_com)
        else:
            srv_com["result"].attrib.update({"reply" : "no controller found",
                                             "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
            return False
    def process(self, ccs):
        ccs.srv_com["result"] = "OK"
    def _interpret(self, ctrl_dict, cur_ns):
        num_cont, num_array, num_log, num_phys = (0, 0, 0, 0)
        array_names, size_log, size_phys = ([], [], 0)
        #pprint.pprint(c_dict)
        error_f, warn_f = ([], [])
        for c_name, c_stuff in ctrl_dict.iteritems():
            num_cont += 1
            if c_stuff.has_key("arrays"):
                # new code
                if len([True for v in c_stuff["status"].itervalues() if v.lower() not in ["ok"]]):
                    error_f.append("status of controller %s (slot %d): %s" % (c_stuff["info"], c_name, ", ".join(["%s: %s" % (k, v) for k, v in c_stuff["status"].iteritems() if v.lower() != "ok"])))
                for array_name, array_stuff in c_stuff["arrays"].iteritems():
                    array_names.append("%s in slot %d" % (array_name, c_name))
                    num_array += 1
                    for log_num, log_stuff in array_stuff["logicals"].iteritems():
                        num_log += 1
                        size_log.append(get_size(log_stuff["size_info"]))
                        if log_stuff["status_info"].lower() != "ok":
                            error_f.append("status of log.drive %d (array %s) is %s (%s%s)" % (log_num, array_name, log_stuff["status_info"], log_stuff["raid_info"], ", %s" % (log_stuff["recovery_info"]) if "recovery_info" in log_stuff else ""))
                    for phys_num, phys_stuff in array_stuff["physicals"].iteritems():
                        num_phys += 1
                        size_phys += get_size(phys_stuff["size_info"])
                        if phys_stuff["status_info"].lower() != "ok":
                            if len(phys_num) == 3:
                                pos_info = "port %s, box %s, bay %s" % (phys_num[0], phys_num[1], phys_num[2])
                            else:
                                pos_info = "port %s, id %s" % (phys_num[0], phys_num[1])
                            error_f.append("status of phys.drive %s (array %s) is %s (%s)" % (pos_info, array_name, phys_stuff["status_info"], phys_stuff["type_info"]))
            else:
                # old code (SRO3)
                if c_stuff["status"] != "ok":
                    error_f.append("status of controller %s (slot %d): %s" % (c_name, c_stuff["slot"], c_stuff["status"]))
                if type(c_stuff["logicaldrives"]) == type("a"):
                    error_f.append("logical drives on controller %s (slot %d): %s" % (c_name, c_stuff["slot"], c_stuff["logicaldrives"]))
                else:
                    for l_num, l_stuff in c_stuff["logicaldrives"].iteritems():
                        num_log += 1
                        size_log.append(get_size(l_stuff["size"]))
                        if l_stuff["status"] != "ok":
                            error_f.append("logical drive %d on controller %s (slot %d): %s%s" % (l_num, c_name, c_stuff["slot"], l_stuff["status"], ", %s" % (l_stuff["recovery_info"]) if "recovery_info" in l_stuff else ""))
                if type(c_stuff["physicaldrives"]) == type("a"):
                    error_f.append("physical drives on controller %s (slot %d): %s" % (c_name, c_stuff["slot"], c_stuff["physicaldrives"]))
                else:
                    for port_num, port_stuff in c_stuff["physicaldrives"].iteritems():
                        for id_num, phys_stuff in port_stuff.iteritems():
                            num_phys += 1
                            size_phys += get_size(phys_stuff["size"])
                            if phys_stuff["status"] != "ok":
                                error_f.append("physical drive on controller %s (slot %d), port %d, id %d: %s" % (c_name, c_stuff["slot"], port_num, id_num, phys_stuff["status"]))
        if error_f:
            ret_state, ret_str = (limits.nag_STATE_CRITICAL, "Error")
            error_str = ", %s: %s" % (logging_tools.get_plural("error", len(error_f)), ", ".join(error_f))
        else:
            ret_state, ret_str = (limits.nag_STATE_OK, "OK")
            error_str = ""
        if num_array:
            return ret_state, "%s: %s, %s (%s), %s (%s), %s (%s)%s" % (ret_str,
                                                                       logging_tools.get_plural("controller", num_cont),
                                                                       logging_tools.get_plural("array", num_array),
                                                                       ", ".join(array_names),
                                                                       logging_tools.get_plural("log.drive", num_log),
                                                                       "+".join([to_size_str(act_size_log) for act_size_log in size_log]),
                                                                       logging_tools.get_plural("phys.drive", num_phys),
                                                                       to_size_str(size_phys),
                                                                       error_str)
        else:
            return ret_state, "%s: %s, %s (%s), %s (%s)%s" % (ret_str,
                                                              logging_tools.get_plural("controller", num_cont),
                                                              logging_tools.get_plural("log.drive", num_log),
                                                              to_size_str(size_log),
                                                              logging_tools.get_plural("phys.drive", num_phys),
                                                              to_size_str(size_phys),
                                                              error_str)

class ctrl_type_ibmraid(ctrl_type):
    class Meta:
        name = "ibmraid"
        exec_name = "true"
        description = "IBM Raidcontroller for Bladecenter S"
    def get_exec_list(self, ctrl_list=[]):
        if ctrl_list == []:
            ctrl_list = self._dict.keys()
        return ["%s info %s" % (self._check_exec, ctr_id) for ctrl_id in ctrl_list]
    def scan_ctrl(self):
        cur_stat, cur_lines = self.exec_command(" info", post="strip")
    def update_ctrl(self, ctrl_ids):
        print ctrl_ids
    def update_ok(self, srv_com):
        if self._dict:
            return ctrl_type.update_ok(self, srv_com)
        else:
            srv_com["result"].attrib.update({"reply" : "no controller found",
                                             "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
            return False
    def process(self, ccs):
        ccs.srv_com["result"] = "OK"
    def _interpret(self, ctrl_dict, cur_ns):
        ret_state = limits.nag_STATE_OK
        ret_f = []
        for ctrl_info in ctrl_dict["ctrl_list"]:
            ret_f.append("%s (%s)" % (ctrl_info["name"],
                                      ctrl_info["status"]))
            if ctrl_info["status"].lower() not in ["primary", "secondary"]:
                ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
        for ctrl_key in [key for key in ctrl_dict.keys() if key.split("_")[1].isdigit()]:
            cur_dict = ctrl_dict[ctrl_key]
            #pprint.pprint(cur_dict)
            ctrl_f = []
            ctrl_f.append("C%d: %s" % (int(ctrl_key.split("_")[1]),
                                       cur_dict["Current Status"]))
            if cur_dict["BBU Charging"]:
                ctrl_f.append("BBU Charging")
                ret_state = max(ret_state, limits.nag_STATE_WARNING)
            if cur_dict["BBU State"].split()[0] != "1" or cur_dict["BBU Fault Code"].split()[0] != "0":
                ctrl_f.append("BBU State/Fault Code: '%s/%s'" % (cur_dict["BBU State"],
                                                                 cur_dict["BBU Fault Code"]))
                ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
            if cur_dict["Current Status"].lower() not in ["primary", "secondary"]:
                ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
            vol_info = [logging_tools.get_plural("volume", len(cur_dict["volumes"]))]
            for cur_vol in cur_dict["volumes"]:
                if cur_vol["status"] != "VBL INI":
                    vol_info.append("%s (%d, %s): %s" % (cur_vol["name"],
                                                         cur_vol["raidlevel"],
                                                         cur_vol["capacity"],
                                                         cur_vol["status"]))
                pass
            ctrl_f.append(",".join(vol_info))
            ret_f.append(", ".join(ctrl_f))
        return ret_state, "; ".join(ret_f)

class _general(hm_classes.hm_module):
    def init_module(self):
        ctrl_type.init(self)
##    def check_exec(self):
##        if os.path.isfile(TW_EXEC):
##            return "ok"
##        else:
##            return "error no %s found" % (TW_EXEC)
    def check_controller(self, ctrl_id):
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
    def _interpret(self, ctrl_dict, cur_ns):
        return ctrl_type.ctrl("tw")._interpret(ctrl_dict, cur_ns)
    def interpret(self, srv_com, cur_ns):
        return self._interpret(server_command.srv_command.tree_to_dict(srv_com["result"]), cur_ns)
    def interpret_old(self, result, parsed_coms):
        tw_dict = hm_classes.net_to_sys(result[3:])
        return self._interpret(tw_dict, parsed_coms)
    def _interpret(self, tw_dict, cur_ns):
        return ctrl_type.ctrl("tw")._interpret(tw_dict, cur_ns)

class aac_status_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=False)
    def __call__(self, srv_com, cur_ns):
        ctrl_type.update("ips")
        if "arguments:arg0" in srv_com:
            ctrl_list = [srv_com["arguments:arg0"].text]
        else:
            ctrl_list = []
        if ctrl_type.ctrl("ips").update_ok(srv_com):
            return ctrl_check_struct(srv_com, ctrl_type.ctrl("ips"), ctrl_list)
    def interpret(self, srv_com, cur_ns):
        return self._interpret(marshal.loads(bz2.decompress(base64.b64decode(srv_com["ips_dict_base64"].text))), cur_ns)
    def interpret_old(self, result, cur_ns):
        aac_dict = hm_classes.net_to_sys(result[3:])
        return self._interpret(aac_dict, cur_ns)
    def _interpret(self, aac_dict, cur_ns):
        return ctrl_type.ctrl("ips")._interpret(aac_dict, cur_ns)

class megaraid_sas_status_command(hm_classes.hm_command):
    def server_call(self, cm):
        self.module_info.init_ctrl_dict(self.logger)
        self.module_info.update_ctrl_dict(self.logger)
        return "ok %s" % (hm_classes.sys_to_net(self.module_info.get_ctrl_config()))
    def interpret_old(self, result, cur_ns):
        ctrl_dict = hm_classes.net_to_sys(result[3:])
        return self._interpret(ctrl_dict, cur_ns)
    def _interpret(self, ctrl_dict, cur_ns):
        return ctrl_type.ctrl("megaraid_sas")._interpret(ctrl_dict, cur_ns)

class megaraid_status_command(hm_classes.hm_command):
    def server_call(self, cm):
        self.module_info.init_ctrl_dict(self.logger)
        self.module_info.update_ctrl_dict(self.logger)
        return "ok %s" % (hm_classes.sys_to_net(self.module_info.get_ctrl_config()))
    def interpret_old(self, result, cur_ns):
        ctrl_dict = hm_classes.net_to_sys(result[3:])
        return self._interpret(ctrl_dict, cur_ns)
    def _interpret(self, ctrl_dict, cur_ns):
        return ctrl_type.ctrl("megaraid")._interpret(ctrl_dict, cur_ns)

class gdth_status_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        ctrl_type.update("gdth")
        if "arguments:arg0" in srv_com:
            ctrl_list = [srv_com["arguments:arg0"].text]
        else:
            ctrl_list = []
        if ctrl_type.ctrl("gdth").update_ok(srv_com):
            return ctrl_check_struct(srv_com, ctrl_type.ctrl("gdth"), ctrl_list)
    def _interpret(self, ctrl_dict, cur_ns):
        return ctrl_type.ctrl("gdth")._interpret(ctrl_dict, cur_ns)
    def interpret(self, srv_com, cur_ns):
        return self._interpret(server_command.srv_command.tree_to_dict(srv_com["result"]), cur_ns)
    def interpret_old(self, result, cur_ns):
        ctrl_dict = hm_classes.net_to_sys(result[3:])
        return self._interpret(ctrl_dict, cur_ns)
    def _interpret(self, ctrl_dict, cur_ns):
        return ctrl_type.ctrl("gdth")._interpret(ctrl_dict, cur_ns)

class hpacu_status_command(hm_classes.hm_command):
    def interpret_old(self, result, cur_ns):
        ctrl_dict = hm_classes.net_to_sys(result[3:])
        return self._interpret(ctrl_dict, cur_ns)
    def _interpret(self, ctrl_dict, cur_ns):
        return ctrl_type.ctrl("hpacu")._interpret(ctrl_dict, cur_ns)

class ibmraid_status_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
    def interpret_old(self, result, cur_ns):
        ctrl_dict = hm_classes.net_to_sys(result[3:])
        return self._interpret(ctrl_dict, cur_ns)
    def _interpret(self, ctrl_dict, cur_ns):
        return ctrl_type.ctrl("ibmraid")._interpret(ctrl_dict, cur_ns)

if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)
