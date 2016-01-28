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
""" SNMP handler instances """

from ...functions import simplify_dict
from ...snmp_struct import ResultNode, ifSNMPIP
from initat.tools import process_tools, logging_tools, ipvx_tools
from ..base import SNMPHandler

try:
    from django.db.models import Q
    from initat.cluster.backbone.models import network, netdevice, domain_tree_node, \
        network_type, net_ip
except:
    pass


class handler(SNMPHandler):
    class Meta:
        # oids = ["generic.netip"]
        description = "network settings (IP addresses)"
        vendor_name = "generic"
        name = "netip"
        tl_oids = ["1.3.6.1.2.1.4.20", "1.3.6.1.2.1.4.22"]
        initial = True

    def update(self, dev, scheme, result_dict, oid_list, flags):
        # ip dict
        _ip_dict = {}
        # import pprint
        # pprint.pprint(result_dict)
        # pprint.pprint(simplify_dict(result_dict["1.3.6.1.2.1.4.22"], (1,)))
        for key, struct in simplify_dict(result_dict["1.3.6.1.2.1.4.22"], (1,)).iteritems():
            # check for static entries
            if 4 in struct and struct[4] == 4:
                # build snmp_ip struct
                _ip = ipvx_tools.ipv4(".".join(["{:d}".format(_entry) for _entry in key[1:]]))
                _networks = _ip.find_matching_network(network.objects.all())
                if _networks:
                    self.log(
                        "found {} for {}: {}".format(
                            logging_tools.get_plural("matching network", len(_networks)),
                            unicode(_ip),
                            ", ".join([unicode(_net) for _net in _networks]),
                        )
                    )
                    _nw = _networks[0]
                    _dict = {
                        2: key[0],
                        1: struct[3],
                        3: "".join([chr(int(_value)) for _value in _nw[1].netmask.split(".")]),
                    }
                    try:
                        _ip = ifSNMPIP(_dict)
                    except:
                        self.log(
                            "error interpreting {} as IP: {}".format(
                                str(value),
                                process_tools.get_except_info()
                            ),
                            logging_tools.LOG_LEVEL_ERROR,
                        )
                    else:
                        _ip_dict[key[0]] = _ip
                else:
                    self.log("found no matching network for IP {}".format(unicode(_ip)), logging_tools.LOG_LEVEL_ERROR)
        for key, value in simplify_dict(result_dict["1.3.6.1.2.1.4.20"], (1,)).iteritems():
            try:
                _ip = ifSNMPIP(value)
            except:
                self.log(
                    "error interpreting {} as IP: {}".format(
                        str(value),
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR,
                )
            else:
                _ip_dict[key] = _ip
        if any([unicode(_value.address_ipv4) == "0.0.0.0" for _value in _ip_dict.itervalues()]):
            self.log("ignoring zero IP address", logging_tools.LOG_LEVEL_WARN)
            _ip_dict = {key: value for key, value in _ip_dict.iteritems() if unicode(value.address_ipv4) != "0.0.0.0"}
        if dev.domain_tree_node_id:
            _tln = dev.domain_tree_node
        else:
            _tln = domain_tree_node.objects.get(Q(depth=0))
        if_lut = {_dev_nd.snmp_idx: _dev_nd for _dev_nd in netdevice.objects.filter(Q(snmp_idx__gt=0) & Q(device=dev))}
        # handle IPs
        _found_ip_ids = set()
        _added = 0
        for ip_struct in _ip_dict.itervalues():
            if ip_struct.if_idx in if_lut:
                _dev_nd = if_lut[ip_struct.if_idx]
                # check for network
                _network_addr = ip_struct.address_ipv4 & ip_struct.netmask_ipv4

                cur_nw = network.objects.get_or_create_network(
                    network_addr=_network_addr,
                    netmask=ip_struct.netmask_ipv4,
                    context="SNMP",
                )
                # check for existing IP
                try:
                    _ip = net_ip.objects.get(Q(netdevice__device=dev) & Q(ip=ip_struct.address))
                except net_ip.DoesNotExist:
                    _added += 1
                    _ip = net_ip(
                        ip=ip_struct.address,
                    )
                _ip.domain_tree_node = _tln
                _ip.network = cur_nw
                _ip.netdevice = _dev_nd
                _ip.save()
                _found_ip_ids.add(_ip.idx)
        if flags["strict"]:
            stale_ips = net_ip.objects.exclude(Q(pk__in=_found_ip_ids)).filter(Q(netdevice__device=dev))
            if stale_ips.count():
                stale_ips.delete()
        if _added:
            return ResultNode(ok="updated IPs (added: {:d})".format(_added))
        else:
            return ResultNode()
