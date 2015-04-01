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
import commands
from initat.host_monitoring import limits
from initat.host_monitoring import hm_classes
import os
import os.path
import logging_tools

class my_modclass(hm_classes.hm_fileinfo):
    def __init__(self, **args):
        hm_classes.hm_fileinfo.__init__(self,
                                        "hpacu",
                                        "provides a interface to check the status via Compaq hpacu-tools",
                                        **args)
    def init(self, mode, logger, basedir_name, **args):
        if mode == "i":
            self.controllers = []

def call_command(bin, what):
    stat, out = commands.getstatusoutput("%s %s" % (bin, what))
    if not stat:
        out = [y for y in [x.strip() for x in out.split("\n")] if y]
    return stat, out

def check_for_controller_ids(logger, exec_name):
    stat, out = commands.getstatusoutput("echo 'controller all show' | %s" % (exec_name))
    if stat:
        return False, "error calling %s (%d): %s" % (exec_name, stat, out)
    else:
        out_lines = [x.strip() for x in out.split("\n") if x.lower().count("in slot")]
        if out_lines:
            c_ids = [int(x.split()[5].replace("(", " ").replace(")", " ")) for x in out_lines]
        else:
            c_ids = []
        return True, c_ids
   
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

class hpacu_status_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "hpacu_status", **args)
        self.help_str = "returns the status of the Compaq Raid-Controllersgiven controller"
        self.cache_timeout = 600
        self.is_immediate = False
    def server_call(self, cm):
        hpacucli_bin = "/usr/sbin/hpacucli"
        if os.path.isfile(hpacucli_bin):
            if not self.module_info.controllers:
                c_ok, id_list = check_for_controller_ids(self.logger, hpacucli_bin)
                if not c_ok:
                    # id_list is the error strings
                    return id_list
                else:
                    self.module_info.controllers = id_list
            if self.module_info.controllers:
                c_stat, c_out = commands.getstatusoutput("echo -ne '%s' | %s" % ("\n".join(["controller slot=%d show status\ncontroller slot=%d logicaldrive all show\ncontroller slot=%d physicaldrive all show\n" % (x, x, x) for x in self.module_info.controllers]), hpacucli_bin))
                if c_stat:
                    return "error getting status (%d): %s" % (c_stat, c_out)
                c_lines = [x.strip() for x in c_out.split("\n") if x.strip() and not x.startswith("=>")]
                c_dict = {}
                act_ctrl, act_array = (None, None)
                for c_line in c_lines:
                    l_line = c_line.lower()
                    if l_line.count("in slot"):
                        is_idx = l_line.index("in slot")
                        c_info = int(l_line[is_idx + len("in slot"):].strip().split()[0])
                        if act_ctrl != c_info:
                            act_ctrl = c_info
                            c_dict[act_ctrl] = {"info"   : c_line[0:is_idx].strip(),
                                                "arrays" : {},
                                                "status" : {}}
                        act_array = None
                    if act_ctrl is not None:
                        if l_line.startswith("array"):
                            act_array = " ".join(c_line.split()[1:])
                            if not c_dict[act_ctrl]["arrays"].has_key(act_array):
                                c_dict[act_ctrl]["arrays"][act_array] = {"logicals"  : {},
                                                                         "physicals" : {}}
                    if act_array is not None:
                        if l_line.startswith("logicaldrive"):
                            l_num = int(l_line.split()[1])
                            l_info = [x.strip() for x in (" ".join(c_line.split()[2:]))[1:-1].split(",")]
                            c_dict[act_ctrl]["arrays"][act_array]["logicals"][l_num] = {"size_info"   : l_info[0],
                                                                                        "raid_info"   : l_info[1],
                                                                                        "status_info" : l_info[2]}
                            if len(l_info) > 3:
                                c_dict[act_ctrl]["arrays"][act_array]["logicals"][l_num]["recovery_info"] = l_info[3]
                        elif l_line.startswith("physicaldrive"):
                            pos_info = tuple(c_line.split()[1].split(":"))
                            p_info = [x.strip() for x in (" ".join(c_line.split()[2:]))[1:-1].split(",")]
                            c_dict[act_ctrl]["arrays"][act_array]["physicals"][pos_info] = {"type_info"   : p_info[1],
                                                                                            "size_info"   : p_info[2],
                                                                                            "status_info" : p_info[3]}
                    else:
                        if l_line.count("status"):
                            c_dict[act_ctrl]["status"][l_line.split()[0]] = " ".join(l_line.split()[2:])
                return "ok %s" % (hm_classes.sys_to_net(c_dict))
            else:
                return "error not controllers found"
        else:
            return "error %s not found" % (hpacucli_bin)
    def client_call(self, result, parsed_coms):
        if result.startswith("ok "):
            c_dict = hm_classes.net_to_sys(result[3:])
            num_cont, num_array, num_log, num_phys = (0, 0, 0, 0)
            array_names, size_log, size_phys = ([], [], 0)
            #pprint.pprint(c_dict)
            error_f, warn_f = ([], [])
            for c_name, c_stuff in c_dict.iteritems():
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
        else:
            return limits.nag_STATE_CRITICAL, "error %s" % (result)

if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)

