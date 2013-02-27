#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007 Andreas Lang-Nevyjel, init.at
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
from initat.host_monitoring import limits
from initat.host_monitoring import hm_classes
import os
import os.path
import logging_tools
import datetime
import time

class my_modclass(hm_classes.hm_fileinfo):
    def __init__(self, **args):
        hm_classes.hm_fileinfo.__init__(self,
                                        "gdth",
                                        "provides a interface to check the status of gdth RAID-cards",
                                        **args)

class gdth_status_OLD_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "gdth_status", **args)
        self.help_str = "returns the status of the given controller"
        self.cache_timeout = 600
        self.is_immediate = False
    def server_call(self, cm):
        gdth_dir = "/proc/scsi/gdth"
        if os.path.isdir(gdth_dir):
            ctrls_found = os.listdir(gdth_dir)
            if cm:
                ctrls = [y for y in [x.strip() for x in cm[0].strip().split(",")] if y in ctrls_found]
            else:
                ctrls = ctrls_found
            if ctrls:
                last_log_line, last_log_time = ("", None)
                act_time = datetime.datetime(*time.localtime()[0:6])
                for ctrl in ctrls:
                    lines = [x.rstrip() for x in file("%s/%s" % (gdth_dir, ctrl), "r").read().split("\n")]
                    act_mode = "?"
                    pd_list, ld_list, ad_list, hd_list = ([], [], [], [])
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
                                        pd_list.append(act_dp_dict)
                                        act_dp_dict = {}
                            elif act_mode == "ld":
                                left_str, right_str = (line[0:27].strip(), line[27:].strip())
                                for act_str in [x for x in [left_str, right_str] if x]:
                                    key, value = [x.strip() for x in act_str.split(":", 1)]
                                    act_ld_dict[key.lower()] = value
                                    if key.lower().startswith("to array dr"):
                                        if act_ld_dict.has_key("status"):
                                            ld_list.append(act_ld_dict)
                                        act_ld_dict = {}
                            elif act_mode == "ad":
                                if len(line.strip()) > 10:
                                    left_str, right_str = (line[0:27].strip(), line[27:].strip())
                                    for act_str in [x for x in [left_str, right_str] if x]:
                                        key, value = [x.strip() for x in act_str.split(":", 1)]
                                        act_ad_dict[key.lower()]=value
                                        if key.lower().startswith("type"):
                                            ad_list.append(act_ad_dict)
                                            act_ad_dict = {}
                            elif act_mode == "hd":
                                left_str, right_str = (line[0:27].strip(), line[27:].strip())
                                for act_str in [x for x in [left_str, right_str] if x]:
                                    key, value = [x.strip() for x in act_str.split(":", 1)]
                                    act_hd_dict[key.lower()] = value
                                    if key.lower().startswith("start secto"):
                                        hd_list.append(act_hd_dict)
                                        act_hd_dict = {}
                            elif act_mode == "ce":
                                if line.strip().startswith("date-"):
                                    line_p = line.strip().split(None, 2)
                                    line_d, last_log_line = ([int(x) for x in line_p[1].split(":")], line_p[2])
                                    time_t = datetime.timedelta(0, line_d[0] * 3600 + line_d[1] * 60 + line_d[2])
                                    last_log_time = act_time - time_t
                ret_dict = {"pd" : pd_list, "ld" : ld_list, "ad" : ad_list, "hd" : hd_list, "log" : (last_log_time, last_log_line)}
                return "ok %s" % (hm_classes.sys_to_net(ret_dict))
            else:
                return "error no controller found"
        else:
            return "error no gdth-controllers found"
    def client_call(self, result, parsed_coms):
        if result.startswith("ok "):
            ret_dict = hm_classes.net_to_sys(result[3:])
            pd_list, ld_list, ad_list, hd_list = (ret_dict["pd"], ret_dict["ld"], ret_dict["ad"], ret_dict["hd"])
            last_log_time, last_log_line = ret_dict.get("log", (None, ""))
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
        else:
            return limits.nag_STATE_CRITICAL, "error %s" % (result)

if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)

