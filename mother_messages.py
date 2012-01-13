#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004 Andreas Lang, init.at
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

import time
import threading
import Queue

class message:
    def __init__(self,type="?",arg=()):
        self.type=type
        self.arg=arg
        self.thread=threading.currentThread().getName()
        self.time=time.time()
    
# internal message (for thread communication)
# defined arg values:
# exit ...... request for exit
# exiting ... reply (yes, i'm exiting ;-) )
class internal_message(message):
    def __init__(self,arg=""):
        message.__init__(self,"I",arg=arg)
    
class snmp_message(message):
    def __init__(self,arg):
        message.__init__(self,"SM",arg=arg)
    
# log message
class log_message(message):
    def __init__(self,str="",machname=None):
        message.__init__(self,"L",arg=(str,machname))

# node message
class node_message(message):
    def __init__(self,arg=()):
        message.__init__(self,"N",arg=arg)

# node_request message
class node_request(message):
    def __init__(self,arg=()):
        message.__init__(self,"R",arg=arg)
    
# config message
class config_request(message):
    def __init__(self,arg=()):
        message.__init__(self,"C",arg=arg)

# dhcpd-message (general type)
class dhcpd_message(message):
    def __init__(self,arg=()):
        message.__init__(self,"D",arg=arg)
        
# throttle-message
class throttle_message(message):
    def __init__(self,arg=()):
        message.__init__(self,"T",arg=arg)
        
# sql-message
class sql_message(message):
    def __init__(self,arg=()):
        message.__init__(self,"S",arg=arg)
        
# external_result message (defines return from external command)
# arg from message holds the command
class ext_result(message):
    def __init__(self,arg=()):
        message.__init__(self,"ER",arg=arg)

# delay-message
class delay_request(message):
    def __init__(self,ret_queue,ret_obj,delay=30):
        message.__init__(self,"DL",arg=(ret_queue,ret_obj,delay))
        
