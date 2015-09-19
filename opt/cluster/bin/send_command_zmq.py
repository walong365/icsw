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

from initat.tools import net_tools


def _get_parser():
    parser = argparse.ArgumentParser("send command to servers of the init.at Clustersoftware")
    parser.add_argument("arguments", nargs="+", help="additional arguments, first one is command")
    parser.add_argument("-t", help="set timeout [%(default)d]", default=10, type=int, dest="timeout")
    parser.add_argument("-p", help="port [%(default)d]", default=2001, dest="port", type=int)
    parser.add_argument("-P", help="protocoll [%(default)s]", type=str, default="tcp", choices=["tcp", "ipc"], dest="protocoll")
    parser.add_argument("-S", help="servername [%(default)s]", type=str, default="collrelay", dest="server_name")
    parser.add_argument("-H", "--host", help="host [%(default)s] or server", default="localhost", dest="host")
    parser.add_argument("-v", help="verbose mode [%(default)s]", default=False, dest="verbose", action="store_true")
    parser.add_argument("-i", help="set identity substring [%(default)s]", type=str, default="sc", dest="identity_substring")
    parser.add_argument("-I", help="set identity string [%(default)s], has precedence over -i", type=str, default="", dest="identity_string")
    parser.add_argument("-n", help="set number of iterations [%(default)d]", type=int, default=1, dest="iterations")
    parser.add_argument("-q", help="be quiet [%(default)s], overrides verbose", default=False, action="store_true", dest="quiet")
    parser.add_argument("--raw", help="do not convert to server_command", default=False, action="store_true")
    parser.add_argument("--root", help="connect to root-socket [%(default)s]", default=False, action="store_true")
    parser.add_argument("--kv", help="key-value pair, colon-separated [key:value]", action="append")
    parser.add_argument("--kva", help="key-attribute pair, colon-separated [key:attribute:value]", action="append")
    parser.add_argument("--kv-path", help="path to store key-value pairs under", type=str, default="")
    parser.add_argument("--split", help="set read socket (for split-socket command), [%(default)s]", type=str, default="")
    parser.add_argument("--only-send", help="only send command, [%(default)s]", default=False, action="store_true")
    return parser


def main():
    my_com = net_tools.SendCommand(_get_parser().parse_args())
    my_com.init_connection()
    if my_com.connect():
        my_com.send_and_receive()
    my_com.close()
    sys.exit(my_com.ret_state)

if __name__ == "__main__":
    main()
