#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006 Andreas Lang, init.at
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
    def __init__(self, m_type="?", c_pid=None, s_time=None, arg=()):
        self.m_type = m_type
        self.thread = threading.currentThread().getName()
        self.c_pid = c_pid
        self.arg = arg

class ps_message(message):
    def __init__(self, com, ret_queue=None):
        message.__init__(self, "PS", arg=(com, ret_queue))
        
class internal_message(message):
    def __init__(self, arg):
        message.__init__(self, "I", arg=arg)

class register_queue_message(message):
    def __init__(self, arg):
        message.__init__(self, "RQ", arg=arg)

if __name__ == "__main__":
    print "Loadable module, exiting..."
    sys.exit(0)
