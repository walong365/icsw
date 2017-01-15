# Copyright (C) 2014-2015,2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of init-snmp-libs
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
""" SNMP handler for IBM rack PDUs, old version """

from lxml.builder import E

from ...snmp_struct import simple_snmp_oid
from ..base import SNMPHandler


APC_OID = "1.3.6.1.4.1.5528.100.4.1.1"


class handler(SNMPHandler):
    class Meta:
        description = "APC Netbotz, new version, only temperature"
        vendor_name = "apc"
        name = "netbv1"
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
            for _key, _value in result_dict.items():
                if _key[:2] == (1, 7):
                    mv_tree = kwargs["mv_tree"]
                    mv_tree.append(
                        E.mve(
                            info="Temperature",
                            unit="C",
                            base="1",
                            v_type="f",
                            value="{:.3f}".format(float(_value)),
                            name="apc.sensor.temperature1",
                        )
                    )
                    break
