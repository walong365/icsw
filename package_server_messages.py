#!/opt/python-init/bin/python -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005 Andreas Lang, init.at
#
# Send feedback to: <lang@init.at>
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

import threading
import sys
import time

class message:
    type = ""
    thread = ""
    c_pid = None
    s_time = None
    arg = None
    def __init__(self, type="?", c_pid=None, s_time=None, arg=()):
        self.type = type
        self.thread = threading.currentThread().getName()
        self.c_pid = c_pid
        if s_time:
            self.s_time = s_time
        else:
            self.s_time = time.time()
        self.arg = arg

class internal_message(message):
    def __init__(self, arg=""):
        message.__init__(self, "I", arg=(arg))

class log_message(message):
    def __init__(self, arg="", level=0, machine=None):
        message.__init__(self, "L", arg=(arg, level, machine))

class write_file_message(message):
    def __init__(self, machine="", file_name="", arg=""):
        message.__init__(self, "F", arg=(machine, file_name, arg))

class node_message(message):
    def __init__(self, arg):
        message.__init__(self, "N", arg=arg)

class collect_message(message):
    def __init__(self, arg):
        message.__init__(self, "C", arg=arg)

class package_status_message(message):
    def __init__(self, arg):
        message.__init__(self, "PS", arg=arg)

if __name__ == "__main__":
    print "Loadable module, exiting..."
    sys.exit(0)
