#!/usr/bin/python-init -Ot
#
# Copyright (C) 2016 Gregor Kaufmann, init.at
#
# this file is part of icsw-server
#
# Send feedback to: <g.kaufmann@init.at>
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

import argparse
import subprocess
import base64
import bz2

NRPE_BIN_LOCATION = "/opt/cluster/sbin/check_nrpe"

def get_args():
    parser = argparse.ArgumentParser(
        description='Process args for retrieving all the Virtual Machines')
    parser.add_argument('-H', '--host', required=True, action='store',
                        help='Remote host to connect to')
    parser.add_argument('-n', '--port', type=int, default=5666, action='store',
                        help='remote port to connect to')
    parser.add_argument('-t', '--timeout', default=120, action='store',
                        help='Timeout')
    parser.add_argument('-c', '--command', required=True, action='store',
                        help='Command to execute')
    args = parser.parse_args()
    return args

def main():
    args = get_args()

    nrpe_cmd = [NRPE_BIN_LOCATION,
                "-H", str(args.host),
                "-p", str(args.port),
                "-n",
                "-c", str(args.command),
                "-t", str(args.timeout)]

    proc = subprocess.Popen(nrpe_cmd, stdout=subprocess.PIPE)
    output = proc.stdout.read()

    if output.startswith("b'"):
        output = output[2:-2]

    print bz2.decompress(base64.b64decode(output))

if __name__ == "__main__":
   main()
