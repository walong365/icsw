#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001-2009,2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of logging-server
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
""" logs an error """

import argparse
from initat.tools import io_stream_helper
import zmq

def main():
    my_parser = argparse.ArgumentParser()
    my_parser.add_argument("-n", dest="repeat", default=1, type=int, help="how often the error should by sent [%(default)s]")
    my_parser.add_argument(dest="args", nargs="+")
    my_parser.add_argument("--target", type=str, default="/var/lib/logging-server/py_err_zmq", help="0MQ target [%(default)s]")
    opts = my_parser.parse_args()
    s_str = " ".join(opts.args)
    print("Sending '{}' to {} (repeat: {:d})".format(s_str, opts.target, opts.repeat))
    _ctx = zmq.Context()
    for _rep in xrange(opts.repeat):
        err_h = io_stream_helper.io_stream(opts.target, zmq_context=_ctx)
        err_h.write(s_str)
        err_h.close()
    _ctx.term()

if __name__ == "__main__":
    main()

