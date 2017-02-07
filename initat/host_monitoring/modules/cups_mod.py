#
# Copyright (C) 2007,2012,2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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

import subprocess

from initat.constants import PlatformSystemTypeEnum
from initat.tools import server_command
from .. import limits, hm_classes
from ..constants import HMAccessClassEnum


class ModuleDefinition(hm_classes.MonitoringModule):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        required_access = HMAccessClassEnum.level0
        uuid = "3256c983-2fcf-4e0e-ada8-bf9b76c87e44"


class cups_status_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        required_access = HMAccessClassEnum.level0
        uuid = "48e18be1-c860-4368-b415-b7d6f9a2d4cd"
        description = "various status information about printers"

    def __call__(self, srv_com, cur_ns):
        lp_stat, lp_out = subprocess.getstatusoutput("lpstat -p")
        if lp_stat:
            srv_com.set_result(
                "error getting lpstat info ({:d}): {}".format(lp_stat, lp_out),
                server_command.SRV_REPLY_STATE_ERROR
            )
        else:
            printer_dict = {
                line_p[1]: line_p[2] for line_p in [line.strip().split(None, 2) for line in lp_out.split("\n") if line.startswith("printer")]
            }
            srv_com["printers"] = printer_dict

    def interpret(self, srv_com, cur_ns):
        return self._interpret(srv_com["printers"], cur_ns)

    def _interpret(self, print_dict, parsed_coms):
        if isinstance(print_dict, dict):
            multi_printer = True
        else:
            multi_printer = False
            print_dict = {print_dict[0]: print_dict[1]}
        print_res_dict = {}
        ret_state = limits.mon_STATE_OK
        for p_name, p_stuff in print_dict.items():
            since_idx = p_stuff.index("since")
            pre_time, post_time = (p_stuff[0: since_idx], p_stuff[since_idx + 6:])
            if pre_time.startswith("is "):
                pre_time = pre_time[3:]
            pre_time = pre_time.strip().replace("  ", " ").replace("  ", " ").replace(".", ",")
            post_time = post_time.strip().replace("  ", " ").replace("  ", " ")
            if not [True for pf in ["idle, enabled", "now printing"] if pre_time.lower().startswith(pf)]:
                ret_state = max(ret_state, limits.mon_STATE_CRITICAL)
            print_res_dict[p_name] = "{} (since {})".format(pre_time, post_time)
        return ret_state, ", ".join(
            [
                "{}{}".format(
                    multi_printer and "{}: ".format(p_name) or "",
                    print_res_dict[p_name]
                ) for p_name in sorted(print_res_dict.keys())
            ]
        )
