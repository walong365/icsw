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

from initat.tools import ipvx_tools

from .network import Network


class Host(object):
    all_ips = {}
    mult_ips = []

    @staticmethod
    def setup(**kwargs):
        Host.all_ips = {}
        Host.mult_ips = kwargs.get("mult_ips", [])
        Host.init = 0
        Host.copied = 0
        Host.monitor = 0
        Host.monitor_records = []

    @staticmethod
    def feed(new_ip, name):
        if new_ip not in Host.mult_ips:
            if new_ip in Host.all_ips:
                raise ValueError("IP {}@{} already used by {}".format(new_ip, name, Host.all_ips[new_ip]))
            Host.all_ips[new_ip] = name

    def __init__(self, name, ip=None, **kwargs):
        Host.init += 1
        register = kwargs.get("register", True)
        self.monitor = kwargs.get("monitor", False)
        if self.monitor:
            Host.monitor += 1
            Host.monitor_records.append(self)
        self.force_create_private = kwargs.get("force_create_private", False)
        self.forward_domain = kwargs.get("forward_domain", None)
        if ip is None:
            if name.count(":"):
                self.name = name.strip().split(":")[0]
                self.ip = ipvx_tools.ipv4(name.strip().split(":")[1])
                if register:
                    Host.feed(self.ip, self.name)
                self.public_ip, self.private_ip = (None, None)
            else:
                self.name = name
                self.ip = None
                self.public_ip = kwargs.get("public_ip")
                self.private_ip = kwargs.get("private_ip")
                if not isinstance(self.public_ip, ipvx_tools.ipv4):
                    self.public_ip = ipvx_tools.ipv4(self.public_ip)
                if not isinstance(self.private_ip, ipvx_tools.ipv4):
                    self.private_ip = ipvx_tools.ipv4(self.private_ip)
                if register:
                    Host.feed(self.public_ip, self.name)
                    Host.feed(self.private_ip, self.name)
        else:
            self.name = name
            if isinstance(ip, ipvx_tools.ipv4):
                self.ip = ip
            else:
                self.ip = ipvx_tools.ipv4(ip)
            if register:
                Host.feed(self.ip, self.name)
            self.public_ip, self.private_ip = (None, None)
        # set networks
        if self.ip:
            _ips = [self.ip]
            self.network = Network.get_network(self.ip)
            _cnws = [self.network]
            self.private = self.network.private if self.network else False
        else:
            _ips = [self.public_ip, self.private_ip]
            self.public_network = Network.get_network(self.public_ip)
            self.private_network = Network.get_network(self.private_ip)
            _cnws = [self.public_network, self.private_network]
        if kwargs.get("multiple", False):
            Host.mult_ips.extend(_ips)
        self.private = False
        for _cnw in _cnws:
            if _cnw:
                if _cnw.private:
                    self.private = True

    def get_ip(self, private):
        if self.ip:
            return self.ip
        else:
            if private:
                return self.private_ip
            else:
                return self.public_ip

    def copy(self):
        Host.copied += 1
        return Host(
            self.name,
            self.ip,
            # no monitoring for copied records
            monitor=False,
            public_ip=self.public_ip,
            private_ip=self.private_ip,
            force_create_private=self.force_create_private,
            register=False,
        )

    def __unicode__(self):
        if hasattr(self, "deploy_ip"):
            return "{}@{}(-> {})".format(
                self.name,
                self.ip,
                self.deploy_ip,
            )
        else:
            return "{}@{}".format(
                self.name,
                self.ip if self.ip else "{}/{}".format(
                    self.public_ip,
                    self.private_ip
                )
            )

    @property
    def is_special(self):
        return True if self.name.strip() in ["*", ""] else False
    
    @property
    def create_record(self):
        return self.force_create_private or self.name.strip() not in ["*"]

    def fix_names(self, zone):
        self.short_name = self.name
        self.long_name = self.name
        if not self.long_name.endswith(zone.origin):
            self.long_name = u"{}.{}".format(self.name, zone.origin)
        if self.short_name.endswith(zone.origin):
            self.short_name = make_unqualified(self.short_name[:-len(zone.origin)])
