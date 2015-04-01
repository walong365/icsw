#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2009 Andreas Lang, init.at
#
# Send feedback to: <lang@init.at>
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

import io_stream_helper
import sys

def main():
    io_target = "/var/lib/logging-server/py_err"
    if len(sys.argv) == 1:
        print "Need something to send, aborting..."
        sys.exit(-1)
    s_str = " ".join(sys.argv[1:])
    print "Sending '%s' to %s" % (s_str, io_target)
    err_h = io_stream_helper.io_stream(io_target)
    err_h.write(s_str)
    err_h.close()
    
if __name__ == "__main__":
    main()
    
