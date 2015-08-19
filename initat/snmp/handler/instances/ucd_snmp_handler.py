# Copyright (C) 2014-2015 Andreas Lang-Nevyjel, init.at
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
""" SNMP handler for UCD-SNMP """

from lxml.builder import E

from ...snmp_struct import simple_snmp_oid
from ..base import SNMPHandler

from initat.tools import logging_tools

UCD_OID = "1.3.6.1.4.1.2021"


class handler(SNMPHandler):
    class Meta:
        description = "UCD-SNMP generic info"
        vendor_name = "UCD"
        name = "ucd-snmp"
        initial = True
        tl_oids = [UCD_OID]

    def collect_fetch(self):
        return [
            (
                "T",
                [
                    simple_snmp_oid(UCD_OID),
                ]
            ),
        ]

    def _add_memory(self, mem_dict, mv_tree):
        swap_total, swap_avail = (
            mem_dict[3],
            mem_dict[4],
        )
        phys_total, phys_avail = (
            mem_dict[5],
            mem_dict[6],
        )
        for _name, _info, _value in [
            ("mem.swap.used", "Swap memory in use", swap_total - swap_avail),
            ("mem.swap.free", "Swap memory free", swap_avail),
            ("mem.swap.total", "Swap memory total", swap_total),
            ("mem.phys.used", "Physical memory in use", phys_total - phys_avail),
            ("mem.phys.free", "Physical memory free", phys_avail),
            ("mem.phys.total", "Physical memory total", phys_total),
        ]:
            mv_tree.append(
                E.mve(
                    info=_info,
                    unit="B",
                    base="1",
                    v_type="f",
                    value="{:.3f}".format(_value * 1024),
                    name=_name,
                )
            )

    def _add_load(self, load_dict, mv_tree):
        for _num, _load in [
            (1, float(load_dict[1])),
            (5, float(load_dict[2])),
            (15, float(load_dict[3])),
        ]:
            mv_tree.append(
                E.mve(
                    info="Mean load in last {}".format(logging_tools.get_plural("minute", _num)),
                    unit="1",
                    base="1",
                    v_type="f",
                    value="{:.3f}".format(_load),
                    name="load.{:d}".format(_num),
                )
            )

    def _add_system(self, sys_dict, mv_tree):
        if 7 in sys_dict:
            mv_tree.append(
                E.mve(
                    info="number of interrupts",
                    unit="1/s",
                    base="1",
                    v_type="f",
                    value="{:.3f}".format(float(sys_dict[7])),
                    name="num.interrupts",
                )
            )
        if 8 in sys_dict:
            mv_tree.append(
                E.mve(
                    info="number of context switches",
                    unit="1/s",
                    base="1",
                    v_type="f",
                    value="{:.3f}".format(float(sys_dict[8])),
                    name="num.context",
                )
            )

    def collect_feed(self, result_dict, **kwargs):
        result_dict = self.reorganize(self.filter_results(result_dict))
        if result_dict:
            _dict = result_dict.values()[0]
            mv_tree = kwargs["mv_tree"]
            # import pprint
            # pprint.pprint(_dict)
            # FIXME, we can graph a lot more from this dict ...
            if 4 in _dict:
                self._add_memory(_dict[4], mv_tree)
            if 10 in _dict and 1 in _dict[10] and 3 in _dict[10][1]:
                self._add_load(_dict[10][1][3], mv_tree)
            if 11 in _dict:
                self._add_system(_dict[11], mv_tree)
