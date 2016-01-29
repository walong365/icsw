# Copyright (C) 2001-2008,2012-2016 Andreas Lang-Nevyjel, init.at
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
""" checks for IBM Bladecenter RAID controllers """

import base64
import marshal
import os
import stat
import time

from initat.constants import INITAT_BASE_DEBUG
from initat.host_monitoring import limits, hm_classes
from initat.host_monitoring.modules.raidcontrollers.base import ctrl_type, ctrl_check_struct
from initat.tools import logging_tools, server_command


class ctrl_type_ibmbcraid(ctrl_type):
    class Meta:
        name = "ibmbcraid"
        exec_name = "true"
        description = "IBM Raidcontroller for Bladecenter S"

    def get_exec_list(self, ctrl_list=[]):
        if ctrl_list == []:
            ctrl_list = self._dict.keys()

        _list = [
            (
                "{}/host_monitoring/exe/check_ibmbcraid.py --host {} --user {} --passwd {} --target {}".format(
                    INITAT_BASE_DEBUG,
                    ctrl_id,
                    self.cur_ns.user,
                    self.cur_ns.passwd,
                    self._get_target_file(ctrl_id),
                ),
                ctrl_id,
                self._get_target_file(ctrl_id)
            ) for ctrl_id in ctrl_list
        ]
        return _list

    def _get_target_file(self, ctrl_id):
        return "/tmp/.bcraidctrl_{}".format(ctrl_id)

    def scan_ctrl(self):
        _cur_stat, _cur_lines = self.exec_command(" info", post="strip")

    def update_ctrl(self, ctrl_ids):
        pass

    def update_ok(self, srv_com):
        if self._dict:
            return ctrl_type.update_ok(self, srv_com)
        else:
            srv_com.set_result(
                "no controller found",
                server_command.SRV_REPLY_STATE_ERROR
            )
            return False

    def started(self, ccs):
        _com_line, ctrl_id, s_file = ccs.run_info["command"]
        if os.path.isfile(s_file):
            f_dt = os.stat(s_file)[stat.ST_CTIME]
            file_age = abs(time.time() - f_dt)
            if file_age > 60 * 15:
                ccs.srv_com.set_result(
                    "controller information for {} is too old: {}".format(
                        ctrl_id,
                        logging_tools.get_diff_time_str(file_age)
                    ),
                    server_command.SRV_REPLY_STATE_ERROR
                )
            else:
                # content of s_file is already marshalled
                ccs.srv_com["result:ctrl_{}".format(ctrl_id)] = base64.b64encode(file(s_file, "r").read())
        else:
            ccs.srv_com.set_result(
                "no controller information found for {} (file {})".format(ctrl_id, s_file),
                server_command.SRV_REPLY_STATE_ERROR
            )

    def process(self, ccs):
        pass

    def _interpret(self, ctrl_dict, cur_ns):
        ctrl_dict = {key.split("_")[1]: marshal.loads(base64.b64decode(value)) for key, value in ctrl_dict.iteritems()}
        ctrl_keys = set(ctrl_dict.keys())
        if cur_ns.arguments:
            match_keys = set(cur_ns.arguments) & ctrl_keys
        else:
            match_keys = ctrl_keys
        if match_keys:
            for cur_key in sorted(match_keys):
                ctrl_dict = ctrl_dict[cur_key]
                ret_state = limits.nag_STATE_OK
                ret_f = ["Info from {}".format(cur_key)]
                for ctrl_info in ctrl_dict["ctrl_list"]:
                    ret_f.append(
                        "{} ({})".format(
                            ctrl_info["name"],
                            ctrl_info["status"]
                        )
                    )
                    if ctrl_info["status"].lower() not in ["primary", "secondary"]:
                        ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                for ctrl_key in [key for key in ctrl_dict.keys() if key.split("_")[1].isdigit()]:
                    cur_dict = ctrl_dict[ctrl_key]
                    # pprint.pprint(cur_dict)
                    ctrl_f = [
                        "C{:d}: {}".format(
                            int(ctrl_key.split("_")[1]),
                            cur_dict["Current Status"],
                        )
                    ]
                    if "BBU Charging" in cur_dict:
                        if cur_dict["BBU Charging"]:
                            ctrl_f.append("BBU Charging")
                            ret_state = max(ret_state, limits.nag_STATE_WARNING)
                    else:
                        ctrl_f.append("no BBU Charge info")
                        ret_state = max(ret_state, limits.nag_STATE_WARNING)
                    if "BBU State" in cur_dict:
                        if cur_dict["BBU State"].split()[0] != "1" or cur_dict["BBU Fault Code"].split()[0] != "0":
                            ctrl_f.append(
                                "BBU State/Fault Code: '{}/{}'".format(
                                    cur_dict["BBU State"],
                                    cur_dict["BBU Fault Code"]
                                )
                            )
                            ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                    else:
                        ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                        ctrl_f.append("BBU State missing")
                    if cur_dict["Current Status"].lower() not in ["primary", "secondary"]:
                        ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                    vol_info = [logging_tools.get_plural("volume", len(cur_dict["volumes"]))]
                    for cur_vol in cur_dict["volumes"]:
                        if cur_vol["status"] != "VBL INI":
                            vol_info.append(
                                "{} ({:d}, {:d}): {}".format(
                                    cur_vol["name"],
                                    cur_vol["raidlevel"],
                                    cur_vol["capacity"],
                                    cur_vol["status"]
                                )
                            )
                        pass
                    ctrl_f.append(",".join(vol_info))
                    ret_f.append(", ".join(ctrl_f))
                if "drive_dict" in ctrl_dict:
                    _drives = ctrl_dict["drive_dict"]
                    ret_f.append(logging_tools.get_plural("drive", len(_drives)))
                    spares, problems = ([], [])
                    for _id in sorted(_drives.keys()):
                        _drive = _drives[_id]
                        if _drive["state"] in ["OK"]:
                            pass
                        else:
                            problems.append(_drive)
                        if _drive["usage"] in ["GRP"]:
                            pass
                        elif _drive["usage"] in ["GLS"]:
                            spares.append(_drive)
                        else:
                            pass
                    if spares:
                        ret_f.append(logging_tools.get_plural("spare", len(spares)))
                    else:
                        ret_f.append("No spares found")
                        ret_state = max(ret_state, limits.nag_STATE_WARNING)
                    if problems:
                        ret_f.append(
                            "{} found: {}".format(
                                logging_tools.get_plural("problem disk", len(problems)),
                                ", ".join(
                                    [
                                        "{} has state {} ({}, {}, {})".format(
                                            _drv["E:T"],
                                            _drv["state"],
                                            _drv["usage"],
                                            _drv["mount state"],
                                            _drv["cap"],
                                        ) for _drv in problems
                                    ]
                                )
                            )
                        )
                        ret_state = max(ret_state, limits.nag_STATE_WARNING)
                else:
                    ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                    ret_f.append("missing drive info")
            return ret_state, "; ".join(ret_f)
        else:
            return limits.nag_STATE_CRITICAL, "no controller found"


class ibmbcraid_status_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
        self.parser.add_argument("--user", dest="user", type=str)
        self.parser.add_argument("--pass", dest="passwd", type=str)

    def __call__(self, srv_com, cur_ns):
        ctrl_type.update("ibmbcraid")
        ctrl_type.cur_ns = cur_ns
        if "arguments:arg0" in srv_com:
            ctrl_list = [srv_com["arguments:arg0"].text]
        else:
            ctrl_list = []
        return ctrl_check_struct(self.log, srv_com, ctrl_type.ctrl("ibmbcraid"), ctrl_list)

    def interpret(self, srv_com, cur_ns):
        return self._interpret(
            {
                srv_com._interpret_tag(cur_el, cur_el.tag): srv_com._interpret_el(cur_el) for cur_el in srv_com["result"]
            },
            cur_ns
        )

    def _interpret(self, ctrl_dict, cur_ns):
        return ctrl_type.ctrl("ibmbcraid")._interpret(ctrl_dict, cur_ns)
