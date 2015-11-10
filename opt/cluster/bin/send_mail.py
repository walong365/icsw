#!/usr/bin/python-init -Ot
#
# -*- encoding: utf-8 -*-
#
# Copyright (c) 2015 Andreas Lang-Nevyjel, init.at
#
# this file is part of python-modules-base
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" thin wrapper for old send_mail.py, calls icsw user mail """

import argparse
import subprocess
import sys


def main():
    my_parser = argparse.ArgumentParser()
    my_parser.add_argument("-f", "--from", type=str, help="from address [%(default)s]", default="root@localhost")
    my_parser.add_argument("-s", "--subject", type=str, help="subject [%(default)s]", default="mailsubject")
    my_parser.add_argument("-m", "--server", type=str, help="mailserver to connect [%(default)s]", default="localhost")
    my_parser.add_argument("-t", "--to", type=str, nargs="*", help="to address [%(default)s]", default="root@localhost")
    my_parser.add_argument("message", nargs="+", help="message to send")
    cur_opts = my_parser.parse_args()
    print cur_opts
    # build commandline
    cmd_line = [
        "/opt/cluster/sbin/icsw",
        "--logger",
        "logserver",
        "user",
        "--mode",
        "mail",
        "-f",
        getattr(cur_opts, "from"),
        "-s",
        cur_opts.subject,
    ]
    # rewrite to from single-key-multi-value to multi-(key,value)
    for _to in cur_opts.to:
        cmd_line.extend(
            [
                "-t",
                _to,
            ]
        )
    cmd_line.extend(
        [
            "--message"
        ] + cur_opts.message
    )
    ret_code = subprocess.call(cmd_line)
    sys.exit(ret_code)

if __name__ == "__main__":
    main()
