#!/usr/bin/python3-init -Otu
#
# Copyright (C) 2012,2014-2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server-server
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FTNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" simple command snippet for rsyslog """

import sys

import zmq

from initat.logging_server.constants import icswLogHandleTypes, get_log_path
from initat.tools import logging_tools, process_tools


def open_socket(zmq_context):
    send_sock = zmq_context.socket(zmq.DEALER)
    send_sock.setsockopt_string(zmq.IDENTITY, "{}:syslog_scan".format(process_tools.get_machine_name()))
    send_sock.setsockopt(zmq.LINGER, 0)
    send_sock.connect("tcp://localhost:8000")
    return send_sock


def main():
    zmq_context = zmq.Context()
    log_template = logging_tools.get_logger(
        "syslog_scan",
        get_log_path(icswLogHandleTypes.log_py),
        zmq=True,
        context=zmq_context
    )
    send_sock = None
    log_template.log(logging_tools.LOG_LEVEL_OK, "starting syslog_scan")
    while True:
        line = sys.stdin.readline().strip()
        if not line:
            break
        try:
            _timestamp, host, msg = line.split(None, 2)
        except:
            log_template.log(
                logging_tools.LOG_LEVEL_ERROR,
                "error parsing line {}: {}".format(line, process_tools.get_except_info())
            )
        else:
            log_template.log("got line from {}: {}".format(host, msg))
            if not send_sock:
                send_sock = open_socket(zmq_context)
            send_sock.send_unicode(msg)
    if send_sock:
        send_sock.close()
    log_template.log(logging_tools.LOG_LEVEL_OK, "received empty line, exiting")
    log_template.close()
    zmq_context.term()

if __name__ == "__main__":
    main()
