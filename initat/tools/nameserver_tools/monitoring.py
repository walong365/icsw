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
""" monitoring for nsX.init.at """

import os
from .zone import Zone
from .host import Host


class Monitoring(object):
    def __init__(self, opts):
        self.opts = opts
        print("Init monitoring")
        # init django and get nameserver devices
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

        import django
        django.setup()

        from initat.cluster.backbone.models import device
        self.device = device

        self._resolve_ns()

    def _resolve_ns(self):
        from django.db.models import Q
        self.ns = []
        for _ns in Zone.Meta.nameservers:
            self.ns.append(
                self.device.objects.get(
                    Q(name=_ns.name.split(".")[0]) &
                    Q(domain_tree_node__full_name=_ns.name.split(".", 1)[1])
                )
            )
        print("Nameservers: {}".format(", ".join([unicode(_ns) for _ns in self.ns])))

    def run(self):
        from initat.cluster.backbone.models import config, device_config, mon_check_command
        from django.db.models import Q
        try:
            _conf = config.objects.get(Q(name=self.opts.mon_config_name))
        except config.DoesNotExist:
            _conf = config(name=self.opts.mon_config_name)
            _conf.save()
        # add config to nameserver
        for _ns in self.ns:
            if _conf not in [_dc.config for _dc in _ns.device_config_set.all()]:
                # attach device_config to device if not present
                _ns.device_config_set.add(device_config(device=_ns, config=_conf))
        # check all mon_check_commands
        for mon_host in Host.monitor_records:
            _mc_name = "{}.{}".format(self.opts.mon_config_name, mon_host.long_name).replace(" ", "").replace("..", ".")
            try:
                _mc = mon_check_command.objects.get(Q(name=_mc_name))
            except mon_check_command.DoesNotExist:
                _mc = mon_check_command(
                    config=_conf,
                    name=_mc_name,
                )
            _ln = mon_host.long_name.strip()
            if _ln.startswith("."):
                _ln = _ln[1:]
            _mc.command_line = "$USER1$/check_dns -s $HOSTADDRESS$ -H {} -a {}".format(
                _ln,
                mon_host.get_ip(False),
            )
            _mc.description = "DNS {} ({})".format(_ln, mon_host.get_ip(False))
            _mc.save()
            print("  added record {}".format(_mc.description))
