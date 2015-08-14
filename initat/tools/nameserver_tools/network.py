#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2007-2009,2012-2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" generates zonefiles for nsX.init.at """

from .functions import make_qualified, to_idna


PTR_RECORD = "{:<24s} IN PTR {}"


class Network(object):
    networks = []

    def __init__(self, name, network, netmask, **kwargs):
        self.name = name
        self.network = network
        self.netmask = netmask
        # is a private network
        self.private = kwargs.get("private", False)
        self.records = []
        self.used_ips = set()

    @staticmethod
    def setup(*networks):
        Network.networks = networks

    @staticmethod
    def get_network(ip):
        _res = []
        for _nw in Network.networks:
            if ip & _nw.netmask == _nw.network:
                _res.append(_nw)
        if len(_res) > 1:
            raise ValueError(
                "found {:d} matching networks for {}: {}".format(
                    len(_res),
                    str(ip),
                    ", ".join([unicode(_nw) for _new in _res])
                )
            )
        return _res[0] if _res else None

    def feed_host(self, host, zone):
        if host.ip:
            _src = [(host.network, host.ip)]
        else:
            _src = [
                (host.private_network, host.private_ip),
                (host.public_network, host.public_ip),
            ]
        for _nw, _ip in _src:
            if _nw == self:
                if _ip not in self.used_ips and host.create_record:
                    self.used_ips.add(_ip)
                    add_host = host.copy()
                    add_host.fix_names(zone)
                    self.records.append(add_host)

    def is_in_net(self, host):
        if host.ip:
            _src_ips = [host.ip]
        else:
            _src_ips = [
                host.private_ip,
                host.public_ip,
            ]
        return any([_ip & self.netmask == self.network for _ip in _src_ips])

    def create_zone(self):
        # late import to break loop
        from .zone import Zone
        zone = Zone(str(self.network))
        self.set_zone_content(zone, True)
        self.set_zone_content(zone, False)
        zone.create_master_slave_content()
        return zone

    def get_src_mask(self):
        return "{}/{:d}".format(str(self.network), self.netmask.netmask_bits())

    def set_zone_content(self, zone, private):
        rev_parts = str(self.network).split(".")
        rev_parts.reverse()
        rev_parts.pop(0)
        zone.origin = "{}.in-addr.arpa".format(".".join(rev_parts))
        content = zone.get_header()
        _records = zone.filter(self.records, private)
        if _records:
            setattr(zone, "{}_empty".format("private" if private else "public"), False)
            content.extend(
                [
                    PTR_RECORD.format(
                        str(_host.get_ip(private)).split(".")[-1],
                        make_qualified(to_idna(_host.long_name)),
                    ) for _host in sorted(_records, key=lambda entry: entry.get_ip(private))
                ]
            )
        _target = "{}_content".format("private" if private else "public")
        setattr(zone, _target, content)
