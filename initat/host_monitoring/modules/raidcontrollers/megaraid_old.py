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
""" checks for old MegaRAID controllers """

from initat.host_monitoring import limits, hm_classes
from initat.tools import logging_tools
from initat.tools import server_command

from initat.host_monitoring.modules.raidcontrollers.base import ctrl_type, ctrl_check_struct


class ctrl_type_megaraid(ctrl_type):
    class Meta:
        name = "megaraid"
        exec_name = "megarc"
        description = "MegaRAID"

    def get_exec_list(self, ctrl_list=[]):
        if ctrl_list == []:
            ctrl_list = self._dict.keys()
        return ["%s info %s" % (self._check_exec, ctrl_id) for ctrl_id in ctrl_list]

    def scan_ctrl(self):
        _cur_stat, _cur_lines = self.exec_command(" info", post="strip")

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
