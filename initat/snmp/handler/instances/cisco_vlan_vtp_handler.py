# Copyright (C) 2016 Andreas Lang-Nevyjel, init.at
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
""" Cisco VLAN handler instance """

import pprint
from ..base import SNMPHandler
from ...snmp_struct import ResultNode
from ...functions import simplify_dict


VLAN_BASE = "1.3.6.1.4.1.9.9.46"

# todo: add port/ etherchannel stuff via 192.168.2.14 1.2.840.10006.300.43


class handler(SNMPHandler):
    class Meta:
        # oids = ["generic.netip"]
        description = "Cisco VLAN Information"
        vendor_name = "cisco"
        name = "ciscovlan"
        tl_oids = [VLAN_BASE]
        initial = True

    def update(self, dev, scheme, result_dict, oid_list, flags):
        _vlan_dict = simplify_dict(result_dict[VLAN_BASE], (1, 3, 1, 1))
        # rewrite (1, x) keys to x
        _vlan_dict = {key[1]: value for key, value in _vlan_dict.iteritems()}
        # pprint.pprint(_vlan_dict)
        _port_dict = simplify_dict(result_dict[VLAN_BASE], (1, 6, 1, 1))
        _vlan_ids = _vlan_dict.keys()
        # rewrite hexstrings
        for _port in sorted(_port_dict):
            _pd = _port_dict[_port]
            for _key, _value in _pd.iteritems():
                if _key in [4, 10, 17, 18, 19]:
                    if _key == 4:
                        allowed_vlans = [_id for _id in _vlan_ids if ord(_value[int(_id / 8)]) & (_id & 7)]
                        print(
                            "{:<6d} ts={:d} vlan={:d} {}".format(
                                _port,
                                _pd[14],
                                _pd[5],
                                allowed_vlans,
                            )
                        )
                        # print _port, _key, _port_dict[_port][5], allowed_vlans, "".join(["{:02x}".format(ord(_v)) for _v in _value[:4]])
        # pprint.pprint(_port_dict)
        # if _added:
        #    return ResultNode(ok="updated IPs (added: {:d})".format(_added))
        # else:
        return ResultNode()
