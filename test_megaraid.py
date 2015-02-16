#!/usr/bin/python-init -Ot
# Copyright (C) 2015 Andreas Lang-Nevyjel, init.at
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
""" test the functionality of the megaraid SAS controller check """

import argparse
import pprint  # @UnusedImport
import sys

from initat.host_monitoring.modules.raidcontrollers.all import dummy_mod
from initat.host_monitoring.modules.raidcontrollers.megaraid import ctrl_type_megaraid_sas
import server_command


class dummy_ccs(object):
    def __init__(self, srv_com, _type, _content):
        self.run_info = {
            "command": ["_bla", 0, _type]
        }
        self._content = _content
        self.srv_com = srv_com

    def read(self):
        return self._content


if __name__ == "__main__":
    # example:
    # ./test_megaraid.py initat/host_monitoring/modules/raidinfos/v20_ldpdinfo initat/host_monitoring/modules/raidinfos/v20_bbustatus initat/host_monitoring/modules/raidinfos/v20_encstatus

    print("debugging")
    _sas = ctrl_type_megaraid_sas(dummy_mod(), None)
    srv_com = server_command.srv_command(command="result")
    _sas.process(dummy_ccs(srv_com, "ld", file(sys.argv[1], "r").read() + file(sys.argv[2], "r").read() + file(sys.argv[3], "r").read()))
    # _sas.process(dummy_ccs(srv_com, "bbu", file(sys.argv[2], "r").read()))
    # _sas.process(dummy_ccs(srv_com, "enc", file(sys.argv[3], "r").read()))
    _sas.process(dummy_ccs(srv_com, "done", ""))

    # print srv_com.pretty_print()

    get_hints = False
    short_output = "0"
    cur_ns = argparse.Namespace(
        get_hints=get_hints,
        passive_check_postfix="xxx",
        key="c01",
        short_output=short_output,
        ignore_missing_bbu=False,
        check="all"
    )
    ctrl_dict = {}
    for res in srv_com["result"]:
        ctrl_dict[int(res.tag.split("}")[1].split("_")[-1])] = srv_com._interpret_el(res)
    # pprint.pprint(ctrl_dict)
    _res = ctrl_type_megaraid_sas._interpret(ctrl_dict, cur_ns)
    if get_hints:
        pprint.pprint(_res)
    else:
        print _res.ret_str
