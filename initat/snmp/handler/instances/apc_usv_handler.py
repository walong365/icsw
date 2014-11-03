# Copyright (C) 2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of init-snmp-libs
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
""" SNMP handler for APC USVs """

from ..base import SNMPHandler
from ...struct import simple_snmp_oid
from ...functions import simplify_dict, flatten_dict
from lxml.builder import E


class handler(SNMPHandler):
    class Meta:
        description = "USV"
        vendor_name = "apc"
        name = "usv"
        tl_oids = ["1.3.6.1.4.1.318.1.1.1"]

    def collect_fetch(self):
        return [
            (
                "T",
                [
                    simple_snmp_oid("1.3.6.1.4.1.318.1.1.1.3"),
                    simple_snmp_oid("1.3.6.1.4.1.318.1.1.1.4"),
                ]
            )
        ]

    def collect_feed(self, result_dict, **kwargs):
        res_dict = flatten_dict(simplify_dict(self.filter_results(result_dict, keys_are_strings=False), (1, 3, 6, 1, 4, 1, 318, 1, 1, 1)))
        mv_tree = kwargs["mv_tree"]
        mv_tree.extend([
            E.mve(
                info="Input frequency",
                unit="1/s",
                base="1",
                v_type="i",
                value="{:d}".format(res_dict[(3, 2, 4, 0)]),
                name="usv.frequency.in",
            ),
            E.mve(
                info="Output frequency",
                unit="1/s",
                base="1",
                v_type="i",
                value="{:d}".format(res_dict[(4, 2, 2, 0)]),
                name="usv.frequency.out",
            ),
            E.mve(
                info="Input line voltage",
                unit="V",
                base="1",
                v_type="i",
                value="{:d}".format(res_dict[(3, 2, 1, 0)]),
                name="usv.voltage.in.line",
            ),
            E.mve(
                info="Input line voltage max",
                unit="V",
                base="1",
                v_type="i",
                value="{:d}".format(res_dict[(3, 2, 2, 0)]),
                name="usv.voltage.in.line_max",
            ),
            E.mve(
                info="Input line voltage min",
                unit="V",
                base="1",
                v_type="i",
                value="{:d}".format(res_dict[(3, 2, 3, 0)]),
                name="usv.voltage.in.line_min",
            ),
            E.mve(
                info="Output voltage",
                unit="V",
                base="1",
                v_type="i",
                value="{:d}".format(res_dict[(4, 2, 1, 0)]),
                name="usv.voltage.out",
            ),
            E.mve(
                info="Output load",
                unit="%",
                base="1",
                v_type="i",
                value="{:d}".format(res_dict[(4, 2, 3, 0)]),
                name="usv.load.out",
            ),
            E.mve(
                info="Output current",
                unit="A",
                base="1",
                v_type="i",
                value="{:d}".format(res_dict[(4, 2, 4, 0)]),
                name="usv.ampere.out",
            ),
        ])

