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
""" SNMP handler for IBM rack PDUs, old version """

from lxml.builder import E

from ...snmp_struct import simple_snmp_oid
from ..base import SNMPHandler


PDU_OID = "1.3.6.1.4.1.534.6.6.2.1.3.2.7.1"


class handler(SNMPHandler):
    class Meta:
        description = "rackable power distribution unit, old MIB (IBM)"
        vendor_name = "ibm"
        name = "pduv0"
        tl_oids = [PDU_OID]

    def collect_fetch(self):
        return [
            (
                "T",
                [
                    # general
                    simple_snmp_oid(PDU_OID),
                ]
            ),
        ]

    def collect_feed(self, result_dict, **kwargs):
        result_dict = self.filter_results(result_dict).get(PDU_OID, {})
        if result_dict:
            mv_tree = kwargs["mv_tree"]
            mv_tree.append(
                E.mve(
                    info="Ampere total",
                    unit="A",
                    base="1",
                    v_type="f",
                    value="{:.3f}".format(float(result_dict[(49, 0)]) / 10.),
                    name="pdu.ampere.total.used",
                )
            )
            mv_tree.append(
                E.mve(
                    info="output frequency",
                    unit="1/s",
                    base="1",
                    v_type="f",
                    value="{:.3f}".format(float(result_dict[(10, 0)]) / 10.),
                    name="pdu.output.frequence",
                )
            )
            mv_tree.append(
                E.mve(
                    info="total output (VA)",
                    unit="VA",
                    base="1",
                    v_type="f",
                    value="{:.3f}".format(float(result_dict[(46, 0)])),
                    name="pdu.output.va",
                )
            )
            mv_tree.append(
                E.mve(
                    info="total output (W)",
                    unit="W",
                    base="1",
                    v_type="f",
                    value="{:.3f}".format(float(result_dict[(43, 0)])),
                    name="pdu.output.power",
                )
            )
            mv_tree.append(
                E.mve(
                    info="Ambient temperature",
                    unit="C",
                    base="1",
                    v_type="f",
                    value="{:.3f}".format(float(result_dict[(34, 0)])),
                    name="pdu.ambient.temp",
                )
            )
