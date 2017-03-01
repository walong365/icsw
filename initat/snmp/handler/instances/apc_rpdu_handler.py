# Copyright (C) 2014-2015,2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of icsw-server
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
""" SNMP handler for APC rack PDUs """

from lxml.builder import E

from ...snmp_struct import simple_snmp_oid
from ..base import SNMPHandler


class Handler(SNMPHandler):
    class Meta:
        description = "rackable power distribution unit"
        vendor_name = "apc"
        name = "rpdu"
        tl_oids = ["1.3.6.1.4.1.318.1.1.12"]

    def collect_fetch(self):
        return [
            (
                "V",
                [
                    simple_snmp_oid("1.3.6.1.4.1.318.1.1.12.2.3.1.1.2.1")
                ]
            )
        ]

    def collect_feed(self, result_dict, **kwargs):
        result_dict = self.filter_results(result_dict)
        if result_dict:
            mv_tree = kwargs["mv_tree"]
            _val = list(result_dict.values())[0]
            mv_tree.append(
                E.mve(
                    info="Ampere",
                    unit="A",
                    base="1",
                    v_type="f",
                    value="{:.1f}".format(float(_val) / 10.),
                    name="apc.ampere.used",
                )
            )

    def power_control(self, command, cd_obj):
        if cd_obj.parameter_i1 == 0:
            raise ValueError("parameter_i1 is 0")
        # delayed on : 5, delayed off : 6, delayed cycle : 7
        _com_value = {
            "on": 1,
            "cycle": 3,
            "off": 2,
        }[command]
        return [
            "S",
            [
                simple_snmp_oid((1, 3, 6, 1, 4, 1, 318, 1, 1, 12, 3, 3, 1, 1, 4, cd_obj.parameter_i1), target_value=_com_value),
            ]
        ]
