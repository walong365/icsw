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
""" SNMP handler for IBM rack PDUs """

from lxml.builder import E

from ...snmp_struct import simple_snmp_oid
from ..base import SNMPHandler


AMP_OID = "1.3.6.1.4.1.2.6.223.8.2.2.1.9"
WATT_OID = "1.3.6.1.4.1.2.6.223.8.2.2.1.15"


class handler(SNMPHandler):
    class Meta:
        description = "rackable power distribution unit (IBM)"
        vendor_name = "ibm"
        name = "pdu"
        tl_oids = [AMP_OID, WATT_OID]

    def collect_fetch(self):
        return [
            (
                "T",
                [
                    # milliamperes
                    simple_snmp_oid(AMP_OID),
                    # watts
                    simple_snmp_oid(WATT_OID),
                ]
            ),
        ]

    def collect_feed(self, result_dict, **kwargs):
        result_dict = self.filter_results(result_dict)
        if result_dict:
            mv_tree = kwargs["mv_tree"]
            for _tk, _info, _unit, _div in [
                (AMP_OID, "Ampere", "A", 1000.),
                (WATT_OID, "Watt", "W", 1.),
            ]:
                _total = 0.
                for _num, _val in result_dict.get(_tk, {}).iteritems():
                    _total += float(_val)
                    mv_tree.append(
                        E.mve(
                            info="{} of outlet {:d}".format(_info, _num),
                            unit=_unit,
                            base="1",
                            v_type="f",
                            value="{:.3f}".format(float(_val) / _div),
                            name="pdu.{}.outlet{:d}.used".format(_info.lower(), _num),
                        )
                    )
                mv_tree.append(
                    E.mve(
                        info="{} total".format(_info),
                        unit=_unit,
                        base="1",
                        v_type="f",
                        value="{:.3f}".format(float(_total) / _div),
                        name="pdu.{}.total.used".format(_info.lower()),
                    )
                )
