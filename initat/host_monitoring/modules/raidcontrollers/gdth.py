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
""" checks for GDTH / ICP RAID controller """

import datetime
import os
import time

from initat.host_monitoring import limits, hm_classes
from initat.host_monitoring.modules.raidcontrollers.base import ctrl_type, ctrl_check_struct
from initat.tools import logging_tools, server_command


class ctrl_type_gdth(ctrl_type):
    class Meta:
        name = "gdth"
        exec_name = "true"
        description = "GDTH"

    def get_exec_list(self, ctrl_list=[]):
        if ctrl_list == []:
            ctrl_list = self._dict.keys()
        return ["/bin/true {}".format(ctrl_id) for ctrl_id in ctrl_list]

    def scan_ctrl(self):
        gdth_dir = "/proc/scsi/gdth"
        if os.path.isdir(gdth_dir):
            for entry in os.listdir(gdth_dir):
                self._dict[entry] = {}

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
        _com_line, ctrl_id = ccs.run_info["command"].strip().split()
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
                # print "%s %s" % (act_mode, line)
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
                            if "status" in act_ld_dict:
                                ld_dict[len(ld_dict)] = act_ld_dict
                            act_ld_dict = {}
                elif act_mode == "ad":
                    if len(line.strip()) > 10:
                        left_str, right_str = (line[0:27].strip(), line[27:].strip())
                        for act_str in [x for x in [left_str, right_str] if x]:
                            key, value = [x.strip() for x in act_str.split(":", 1)]
                            act_ad_dict[key.lower()] = value
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
            "pd": pd_dict,
            "ld": ld_dict,
            "ad": ad_dict,
            "hd": hd_dict,
            "log": (last_log_time, last_log_line)
        }
        ccs.srv_com["result:ctrl_%s" % (ctrl_id)] = ret_dict

    def _interpret(self, ctrl_dict, cur_ns):
        if ctrl_dict.keys()[0].startswith("ctrl_"):
            ctrl_dict = ctrl_dict.values()[0]
        pd_list, ld_list, ad_list, hd_list = (ctrl_dict["pd"], ctrl_dict["ld"], ctrl_dict["ad"], ctrl_dict["hd"])
        if type(pd_list) == dict:
            # rewrite dict to list
            pd_list = [pd_list[key] for key in sorted(pd_list.keys())]
            ld_list = [ld_list[key] for key in sorted(ld_list.keys())]
            ad_list = [ad_list[key] for key in sorted(ad_list.keys())]
            hd_list = [hd_list[key] for key in sorted(hd_list.keys())]
        _last_log_time, last_log_line = ctrl_dict.get("log", (None, ""))
        out_f, num_w, num_e = ([], 0, 0)
        for _l_type, what, lst in [
            ("p", "physical disc", pd_list),
            ("l", "logical drive", ld_list),
            ("a", "array drive", ad_list),
            ("h", "host drive", hd_list)
        ]:
            if lst:
                num = len(lst)
                cap = reduce(lambda x, y: x + y, [int(x["capacity [mb]"]) for x in lst if "capacity [mb]" in x])
                loc_out = [
                    "%s (%s)" % (
                        logging_tools.get_plural(what, num),
                        ", ".join(
                            [
                                entry for entry in [
                                    "%.2f GB" % (float(cap) / 1024) if cap else "",
                                    ", ".join([x["type"] for x in lst if "type" in x]) if "type" in lst[0] else ""
                                ] if entry])
                    )
                ]
                if "status" in lst[0]:
                    loc_warn = [x for x in lst if x["status"].lower() in ["rebuild", "build", "rebuild/patch"]]
                    loc_err = [x for x in lst if x["status"].lower() not in ["ok", "ready", "rebuild", "build", "rebuild/patch", "ready/patch"]]
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
        return ret_state, "{}: {}".format(ret_str, ", ".join(out_f))


class gdth_status_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        ctrl_type.update("gdth")
        if "arguments:arg0" in srv_com:
            ctrl_list = [srv_com["arguments:arg0"].text]
        else:
            ctrl_list = []
        if ctrl_type.ctrl("gdth").update_ok(srv_com):
            return ctrl_check_struct(self.log, srv_com, ctrl_type.ctrl("gdth"), ctrl_list)

    def _interpret(self, ctrl_dict, cur_ns):
        return ctrl_type.ctrl("gdth")._interpret(ctrl_dict, cur_ns)

    def interpret(self, srv_com, cur_ns):
        return self._interpret({srv_com._interpret_tag(cur_el, cur_el.tag): srv_com._interpret_el(cur_el) for cur_el in srv_com["result"]}, cur_ns)

    def interpret_old(self, result, cur_ns):
        ctrl_dict = hm_classes.net_to_sys(result[3:])
        return self._interpret(ctrl_dict, cur_ns)
