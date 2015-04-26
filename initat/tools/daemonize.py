#!/usr/bin/python-init -Otu
# Copyright (C) 2015 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-client
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

""" daemonizes a given server """

import setproctitle
import sys
import importlib

import daemon
from initat.tools.io_stream_helper import io_stream


def main():
    prog_name, module_name, prog_title = sys.argv[1:4]
    with daemon.DaemonContext(detach_process=True):
        sys.argv = [prog_name]
        setproctitle.setproctitle(prog_title)
        main_module = importlib.import_module(module_name)
        sys.stdout = io_stream("/var/lib/logging-server/py_log_zmq")
        sys.stderr = io_stream("/var/lib/logging-server/py_err_zmq")
        main_module.main()


if __name__ == "__main__":
    main()
