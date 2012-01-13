#!/usr/bin/python-init -Ot
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

import time
import threading

class message:
    def __init__(self, type="?", arg=()):
        self.type = type
        self.arg = arg
        self.thread = threading.currentThread().getName()
        self.time = time.time()
    
# internal message (for thread communication)
# defined arg values:
# exit ...... request for exit
# exiting ... reply (yes, i'm exiting ;-) )
class internal_message(message):
    def __init__(self, arg=""):
        message.__init__(self, "I", arg=arg)
    
# log message
class log_message(message):
    def __init__(self, arg="", machine=None, header=1):
        message.__init__(self, "L", arg=(arg, machine, header))
    
# collect message
class collector_message(message):
    def __init__(self, arg):
        message.__init__(self, "M", arg=arg)
    
# snmp mesage
class snmp_message(message):
    def __init__(self, arg):
        message.__init__(self, "SM", arg=arg)
        
# snmp_result message (defines return from snmp_thread)
class snmp_result(message):
    def __init__(self, arg=()):
        message.__init__(self, "SR", arg=arg)
        
if __name__ == "__main__":
    print "Loadable module, not directly callable !"
    sys.exit(-1)
    
