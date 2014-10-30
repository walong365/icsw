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
""" SNMP handler for basic network stuff (netdevices) """

from ...struct import ResultNode, snmp_if, simple_snmp_oid
from ..base import SNMPHandler
from ...functions import simplify_dict
from initat.cluster.backbone.models import snmp_network_type, netdevice, netdevice_speed, \
    peer_information
from django.db.models import Q


class handler(SNMPHandler):
    class Meta:
        description = "network settings (devices)"
        vendor_name = "generic"
        name = "net"
        version = 1
        tl_oids = ["1.3.6.1.2.1.2"]
        priority = 64
        initial = True

    def update(self, dev, scheme, result_dict, oid_list, flags):
        _if_dict = {key: snmp_if(value) for key, value in simplify_dict(result_dict["1.3.6.1.2.1.2"], (2, 1)).iteritems()}
        snmp_type_dict = {_value.if_type: _value for _value in snmp_network_type.objects.all()}
        speed_dict = {}
        for _entry in netdevice_speed.objects.all().order_by("-check_via_ethtool", "-full_duplex"):
            if _entry.speed_bps not in speed_dict:
                speed_dict[_entry.speed_bps] = _entry
        _added, _updated, _removed = (0, 0, 0)
        # found and used database ids (for deletion)
        _found_nd_ids = set()
        # all present netdevices
        present_nds = netdevice.objects.filter(Q(device=dev))
        # lut
        pnd_lut = {}
        for entry in present_nds:
            pnd_lut[entry.devname] = entry
            if entry.snmp_idx:
                pnd_lut[entry.snmp_idx] = entry
        # pprint.pprint(pnd_lut)
        # lookup dict for snmp_if -> dev_nd
        for if_idx, if_struct in _if_dict.iteritems():
            _created = False
            _dev_nd = pnd_lut.get(if_idx, pnd_lut.get(if_struct.name, None))
            if _dev_nd is None:
                _created = True
                _added += 1
                # create new entry, will be updated later with more values
                _dev_nd = netdevice(
                    device=dev,
                    snmp_idx=if_idx,
                    force_network_device_type_match=False,
                )
                # update lut
                pnd_lut[if_idx] = _dev_nd
                pnd_lut[if_struct.name] = _dev_nd
            if _dev_nd is not None:
                if not _created:
                    _updated += 1
                if if_struct.name in pnd_lut and pnd_lut[if_struct.name].snmp_idx != _dev_nd.snmp_idx:
                    self.log(
                        "namechange detected for SNMP interfaces, deleting previous interface ({}, {:d})".format(
                            if_struct.name,
                            if_idx,
                        )
                    )
                    pnd_lut[if_struct.name].delete()
                _dev_nd.devname = if_struct.name
                _dev_nd.netdevice_speed = speed_dict.get(if_struct.speed, speed_dict[0])
                _dev_nd.snmp_network_type = snmp_type_dict[if_struct.if_type]
                _dev_nd.mtu = if_struct.mtu
                _dev_nd.macaddr = if_struct.macaddr
                _dev_nd.snmp_admin_status = if_struct.admin_status
                _dev_nd.snmp_oper_status = if_struct.oper_status
                _dev_nd.save()
                _found_nd_ids.add(_dev_nd.idx)
        if flags["strict"]:
            stale_nds = netdevice.objects.exclude(Q(pk__in=_found_nd_ids)).filter(Q(device=dev))
            if stale_nds.count():
                _remove = True
                _stale_ids = [_nd.idx for _nd in stale_nds]
                # check peers
                stale_peers = peer_information.objects.filter(Q(s_netdevice__in=_stale_ids) | Q(d_netdevice__in=_stale_ids))
                if stale_peers.count():
                    # relink stale peers to first new netdevice
                    if _found_nd_ids:
                        # nds without loopback devices
                        relink_nds = netdevice.objects.exclude(Q(snmp_network_type__if_type__in=[24])).filter(Q(pk__in=_found_nd_ids))
                        if relink_nds.count():
                            # ok, take first one
                            relink_nd = relink_nds[0]
                        else:
                            # take first one without software loopback filter
                            relink_nd = netdevice.objects.get(Q(pk=list(_found_nd_ids)[0]))
                        for stale_peer in stale_peers:
                            if stale_peer.s_netdevice_id in _stale_ids and stale_peer.d_netdevice_id in _stale_ids:
                                # source and dest will be delete, delete this peer
                                pass
                            elif stale_peer.s_netdevice_id in _stale_ids:
                                stale_peer.s_netdevice = relink_nd
                                stale_peer.save()
                            else:
                                stale_peer.d_netdevice = relink_nd
                                stale_peer.save()
                    else:
                        # no netdevices found, skip removing stale nds
                        _remove = False
                if _remove:
                    _removed += stale_nds.count()
                    stale_nds.delete()
        return ResultNode(
            ok="updated interfaces (added {:d}, updated {:d}, removed {:d})".format(
                _added,
                _updated,
                _removed,
            )
        )
