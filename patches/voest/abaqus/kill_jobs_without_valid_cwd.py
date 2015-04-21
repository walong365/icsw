#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006 Andreas Lang, init.at
#
# Send feedback to: <lang@init.at>
#
# This file is part of rms-tools
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
from initat.tools import logging_tools

WORK_DIR = "/work"

def main():
    kill_pids = []
    kill_signal = 9
    p_dir = "/proc"
    for p_id in os.listdir(p_dir):
        if p_id.isdigit():
            full_path = "%s/%s" % (p_dir, p_id)
            cwd_file = "%s/cwd" % (full_path)
            cwd_path = os.readlink(cwd_file)
            if cwd_path.startswith(WORK_DIR) and not os.path.exists(cwd_path):
                kill_pids.append(int(p_id))
    if kill_pids:
        kill_pids.sort()
        logging_tools.my_syslog("sending signal %d to %s: %s" % (kill_signal,
                                                                 logging_tools.get_plural("PID", len(kill_pids)),
                                                                 ", ".join(["%d" % (x) for x in kill_pids])))
        for kill_pid in kill_pids:
            try:
                os.kill(kill_pid, kill_signal)
            except:
                pass
    sys.exit(0)
    
if __name__ == "__main__":
    main()
    
