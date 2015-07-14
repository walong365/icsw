#!/usr/bin/python-init -Ot
#
# Copyright (c) 2015 Andreas Lang-Nevyjel, lang-nevyjel@init.at
#
# this file is part of md-config-server
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
""" set the result of a passive checkcommand """

import argparse
import sys
import os

import zmq
from initat.tools import logging_tools, process_tools, server_command


def _get_parser():
    parser = argparse.ArgumentParser("set a passive check command")
    parser.add_argument("-p", type=int, default=8010, dest="port", help="target port [%(default)d]")
    parser.add_argument("-H", type=str, default="localhost", dest="host", help="target host [%(default)s]")
    parser.add_argument("--device", type=str, default="", help="device [%(default)s]", required=True)
    parser.add_argument("--check", type=str, default="", help="name of check [%(default)s]", required=True)
    parser.add_argument("--state", type=str, default="OK", choices=["OK", "WARN", "CRITICAL"], help="check state [%(default)s]")
    parser.add_argument("--output", type=str, default="", help="check output [%(default)s]", required=True)
    parser.add_argument("-v", help="verbose mode [%(default)s]", default=False, dest="verbose", action="store_true")
    parser.add_argument("-t", type=int, default=10, dest="timeout", help="set timeout [%(default)d]")
    return parser


def main():
    my_p = _get_parser()
    opts = my_p.parse_args()
    _context = zmq.Context()
    _sender = process_tools.get_socket(_context, "DEALER", identity="spcc_{:d}".format(os.getpid()))
    conn_str = "tcp://{}:{:d}".format(opts.host, opts.port)
    _com = server_command.srv_command(
        command="passive_check_result",
        device=opts.device,
        check=opts.check,
        state=opts.state,
        output=opts.output,
    )
    _sender.connect(conn_str)
    _sender.send_unicode(unicode(_com))
    if _sender.poll(opts.timeout * 1000):
        recv_str = server_command.srv_command(source=_sender.recv())
        _str, _ret = recv_str.get_log_tuple()
        print(_str)
    else:
        print(
            "error timeout in receive() from {} after {}".format(
                conn_str,
                logging_tools.get_plural("second", opts.timeout)
            )
        )
        _ret = 1
    _sender.close()
    _context.term()
    sys.exit(_ret)

if __name__ == "__main__":
    main()
