# Copyright (C) 2008-2014 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
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
""" special for network monitoring """

from django.db.models import Q
from initat.cluster.backbone.models import netdevice
from initat.md_config_server.special_commands.base import SpecialBase
import logging_tools
import re


class special_net(SpecialBase):
    class Meta:
        info = "configured netdevices via collserver"
        command_line = "$USER2$ -m $HOSTADDRESS$ net --duplex $ARG1$ -s $ARG2$ -w $ARG3$ -c $ARG4$ $ARG5$"
        description = "queries all configured network devices"

    def _call(self):
        sc_array = []
        virt_check = re.compile("^.*:\S+$")
        # never check duplex and stuff for a loopback-device
        nd_list = netdevice.objects.filter(
            Q(device=self.host) &
            Q(enabled=True)
        ).select_related("netdevice_speed")
        for net_dev in nd_list:
            if not virt_check.match(net_dev.devname):
                name_with_descr = "{}{}".format(
                    net_dev.devname,
                    " ({})".format(net_dev.description) if net_dev.description else "")
                _bps = net_dev.netdevice_speed.speed_bps
                cur_temp = self.get_arg_template(
                    "{} [HM]".format(name_with_descr),
                    w="{:.0f}".format(_bps * 0.9) if _bps else "-",
                    c="{:.0f}".format(_bps * 0.95) if _bps else "-",
                    arg_1=net_dev.devname,
                )
                if net_dev.netdevice_speed.check_via_ethtool and net_dev.devname != "lo":
                    cur_temp["duplex"] = net_dev.netdevice_speed.full_duplex and "full" or "half"
                    cur_temp["s"] = "{:d}".format(_bps)
                else:
                    cur_temp["duplex"] = "-"
                    cur_temp["s"] = "-"
                self.log(" - netdevice {} with {}: {}".format(
                    name_with_descr,
                    logging_tools.get_plural("option", len(cur_temp.argument_names)),
                    ", ".join(cur_temp.argument_names))
                )
                sc_array.append(cur_temp)
                # sc_array.append((name_with_descr, eth_opts))
        return sc_array
