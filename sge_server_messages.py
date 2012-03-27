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

import threading
import sys
import time
import logging_tools

class message:
    def __init__(self, m_type="?", c_pid=None, s_time=None, arg=()):
        self.m_type = m_type
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
    def __init__(self, arg, level, logs=["n"]):
        message.__init__(self, "L", arg=(arg, level, logs))

class log_ok_message(message):
    def __init__(self, arg, logs=["n"]):
        message.__init__(self, "L", arg=(arg, logging_tools.LOG_LEVEL_OK, logs))

class log_warn_message(message):
    def __init__(self, arg, logs=["n"]):
        message.__init__(self, "L", arg=(arg, logging_tools.LOG_LEVEL_WARN, logs))

class log_error_message(message):
    def __init__(self, arg, logs=["n"]):
        message.__init__(self, "L", arg=(arg, logging_tools.LOG_LEVEL_ERROR, logs))

class log_critical_message(message):
    def __init__(self, arg, logs=["n"]):
        message.__init__(self, "L", arg=(arg, logging_tools.LOG_LEVEL_CRITICAL, logs))

class log_command(message):
    def __init__(self, arg="", logs=["n"]):
        message.__init__(self, "LC", arg=(arg, logs))

class monitor_message(message):
    def __init__(self, arg):
        message.__init__(self, "MM", arg=arg)
        
## class job_monitor_message(message):
##     def __init__(self, arg):
##         message.__init__(self, "JM", arg=arg)
        
## class remove_job_message(message):
##     def __init__(self, arg):
##         message.__init__(self, "RM", arg=arg)
        
class job_log_message(message):
    def __init__(self, arg):
        message.__init__(self, "JL", arg=arg)

class check_job_message(message):
    def __init__(self, arg):
        message.__init__(self, "CJ", arg=arg)

class queue_log_message(message):
    def __init__(self, arg):
        message.__init__(self, "QL", arg=arg)
        
class monitor_reply(message):
    def __init__(self, arg):
        message.__init__(self, "MR", arg=arg)
        
class read_accounting_message(message):
    def __init__(self, arg):
        message.__init__(self, "RA", arg=arg)
        
class sql_thread_message(message):
    def __init__(self, arg):
        message.__init__(self, "ST", arg=arg)
        
if __name__ == "__main__":
    print "Loadable module, exiting..."
    sys.exit(0)
