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


APC_OID = "1.3.6.1.4.1.1909.31.4"


class handler(SNMPHandler):
    class Meta:
        description = "APC Netbotz, old version, only temperature"
        vendor_name = "apc"
        name = "netbv0"
        tl_oids = [APC_OID]

    def collect_fetch(self):
        return [
            (
                "T",
                [
                    # general
                    simple_snmp_oid(APC_OID),
                ]
            ),
        ]

    def collect_feed(self, result_dict, **kwargs):
        result_dict = self.filter_results(result_dict).get(APC_OID, {})
        if result_dict:
            mv_tree = kwargs["mv_tree"]
            mv_tree.append(
                E.mve(
                    info="Temperature 1",
                    unit="C",
                    base="1",
                    v_type="f",
                    value="{:.3f}".format(float(result_dict[(1, 1, 3, 1)])),
                    name="apc.sensor.temperature1",
                )
            )
            mv_tree.append(
                E.mve(
                    info="Temperature 2",
                    unit="C",
                    base="1",
                    v_type="f",
                    value="{:.3f}".format(float(result_dict[(1, 1, 3, 2)])),
                    name="apc.sensor.temperature2",
                )
            )
