#!/usr/bin/python-init -Ot
#
# Copyright (c) 2012-2015 Andreas Lang-Nevyjel, lang-nevyjel@init.at
#
# this file is part of python-modules-base
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License
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

""" sends a command to one of the python-servers, 0MQ version"""

import argparse
import sys

from initat.icsw.service.instance import InstanceXML
from initat.tools import net_tools


class LocalParser(argparse.ArgumentParser):
    def __init__(self):
        argparse.ArgumentParser.__init__(self, "send command to servers of the init.at Clustersoftware")
        self.inst_xml = InstanceXML(quiet=True)
        inst_list = []
        for inst in self.inst_xml.get_all_instances():
            if len(inst.xpath(".//network/ports/port[@type='command']")):
                inst_list.append(inst.get("name"))
        self.add_argument("arguments", nargs="+", help="additional arguments, first one is command")
        self.add_argument("-t", help="set timeout [%(default)d]", default=10, type=int, dest="timeout")
        self.add_argument(
            "-p",
            help="port or instance/service [%(default)d]",
            default=self.inst_xml.get_port_dict("host-monitoring", command=True),
            dest="port",
            type=str
        )
        self.add_argument("-P", help="protocoll [%(default)s]", type=str, default="tcp", choices=["tcp", "ipc"], dest="protocoll")
        self.add_argument("-S", help="servername [%(default)s]", type=str, default="collrelay", dest="server_name")
        self.add_argument("-H", "--host", help="host [%(default)s] or server", default="localhost", dest="host")
        self.add_argument("-v", help="verbose mode [%(default)s]", default=False, dest="verbose", action="store_true")
        self.add_argument("-i", help="set identity substring [%(default)s]", type=str, default="sc", dest="identity_substring")
        self.add_argument("-I", help="set identity string [%(default)s], has precedence over -i", type=str, default="", dest="identity_string")
        self.add_argument("-n", help="set number of iterations [%(default)d]", type=int, default=1, dest="iterations")
        self.add_argument("-q", help="be quiet [%(default)s], overrides verbose", default=False, action="store_true", dest="quiet")
        self.add_argument("--raw", help="do not convert to server_command", default=False, action="store_true")
        self.add_argument("--root", help="connect to root-socket [%(default)s]", default=False, action="store_true")
        self.add_argument("--kv", help="key-value pair, colon-separated [key:value]", action="append")
        self.add_argument("--kva", help="key-attribute pair, colon-separated [key:attribute:value]", action="append")
        self.add_argument("--kv-path", help="path to store key-value pairs under", type=str, default="")
        self.add_argument("--split", help="set read socket (for split-socket command), [%(default)s]", type=str, default="")
        self.add_argument("--only-send", help="only send command, [%(default)s]", default=False, action="store_true")

    def parse(self):
        opts = self.parse_args()
        if isinstance(opts.port, basestring) and opts.port.isdigit():
            opts.port = int(opts.port)
        else:
            opts.port = self.inst_xml.get_port_dict(opts.port, command=True)
        return opts


def main():
    my_com = net_tools.SendCommand(LocalParser().parse())
    my_com.init_connection()
    if my_com.connect():
        my_com.send_and_receive()
    my_com.close()
    sys.exit(my_com.ret_state)

if __name__ == "__main__":
    main()
