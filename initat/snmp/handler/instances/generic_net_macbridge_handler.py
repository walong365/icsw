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
""" SNMP handler for MAC bridge info (basic routing info) """

from initat.tools import logging_tools

from ...functions import reorder_dict
from ...snmp_struct import ResultNode
from ..base import SNMPHandler

try:
    from django.db.models import Q
    from initat.cluster.backbone.models import netdevice, peer_information
except:
    pass

# bi base
BI_BASE = "1.3.6.1.2.1.17.4.3.1"


class handler(SNMPHandler):
    class Meta:
        description = "MAC bridge info"
        vendor_name = "generic"
        name = "macbridge"
        version = 1
        tl_oids = [BI_BASE]
        initial = True

    def update(self, dev, scheme, result_dict, oid_list, flags):
        _added = 0
        if result_dict:
            my_nds = dev.netdevice_set.all()
            my_nd_pks = set([_nd.pk for _nd in my_nds])
            my_nd_dict = {_nd.snmp_idx: _nd for _nd in my_nds if _nd.snmp_idx}
            self.log("found {}".format(logging_tools.get_plural("netdevice", len(my_nds))))
            # reorder dict
            _mac_dict = reorder_dict(result_dict.values()[0])
            # rewrite dict, only use entries where status == 3 (== learned)
            _mac_dict = {":".join(["{:02x}".format(_val) for _val in _key]): _value[2] for _key, _value in _mac_dict.iteritems() if _value[3] == 3}
            # dict now has the form MAC Adress -> snmp idx
            self.log("MAC forward dict has {}".format(logging_tools.get_plural("entry", len(_mac_dict.keys()))))
            _nd_dict = {
                _nd.macaddr: _nd for _nd in netdevice.objects.filter(
                    Q(macaddr__in=_mac_dict.keys())
                ).select_related(
                    "device"
                ).prefetch_related(
                    "peer_s_netdevice",
                    "peer_d_netdevice",
                )
            }
            for _mac in sorted(_mac_dict):
                if _mac in _nd_dict:
                    _snmp_idx = _mac_dict[_mac]
                    _nd = _nd_dict[_mac]
                    s_peers, d_peers = (_nd.peer_s_netdevice.all(), _nd.peer_d_netdevice.all())
                    self.log(
                        "MAC {} (snmp_idx {:d}) -> netdevice '{}' on device '{}', current: {}".format(
                            _mac,
                            _snmp_idx,
                            unicode(_nd),
                            unicode(_nd.device),
                            logging_tools.get_plural("peer", len(s_peers) + len(d_peers)),
                        )
                    )
                    other_pks = set([_p.d_netdevice_id for _p in s_peers]) | set([_p.s_netdevice_id for _p in d_peers])
                    if not other_pks & my_nd_pks:
                        if _snmp_idx in my_nd_dict:
                            self.log(
                                "creating new peer from '{}' to '{}'".format(
                                    unicode(my_nd_dict[_snmp_idx]),
                                    unicode(_nd),
                                )
                            )
                            _added += 1
                            peer_information.objects.create(
                                s_netdevice=my_nd_dict[_snmp_idx],
                                d_netdevice=_nd,
                                penalty=1,
                                autocreated=True,
                            )
                        else:
                            self.log("snmp_idx {:d} not found in local network dict".format(_snmp_idx), logging_tools.LOG_LEVEL_WARN)
        if _added:
            return ResultNode(
                ok="added {}".format(logging_tools.get_plural("peer information", _added))
            )
        else:
            return ResultNode()
