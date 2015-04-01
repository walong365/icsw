#!/usr/bin/python-init -Otu
#
# Copyright (C) 2001,2002,2003,2004,2005,2006 Andreas Lang, init.at
#
# Send feedback to: <lang@init.at>
#
# This file belongs to the rrd-server package
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

import sys
import os
import os.path
import time

# stop lock file name
LF_NAME = "/var/lock/rrd-server/rrd-server.lock"

def main():
    r_state = 1
    if len(sys.argv) < 2:
        print "No PIDfilename given, exiting",
    else:
        pf_name = sys.argv[1]
        try:
            pid = int(file(pf_name, "r").read().strip().split("\n")[0])
        except:
            print "Error reading pid",
        else:
            try:
                os.kill(pid, 15)
            except OSError:
                print "OSError killing %d: %s (%s)" % (pid,
                                                       str(sys.exc_info()[0]),
                                                       str(sys.exc_info()[1]))
            else:
                last_read = ""
                # wait loop
                while True:
                    if not os.path.isdir("/proc/%d" % (pid)):
                        print "done",
                        r_state = 0
                        break
                    if os.path.isfile(LF_NAME):
                        try:
                            new_read = file(LF_NAME, "r").read().strip()
                        except IOError:
                            pass
                        else:
                            pass
                    else:
                        new_read = last_read
                    if new_read != last_read:
                        last_read = new_read
                        print new_read,
                    else:
                        print ".",
                    time.sleep(1)
    return r_state
  
if __name__ == "__main__":
    sys.exit(main())
