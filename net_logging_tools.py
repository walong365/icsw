#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009 Andreas Lang-Nevyjel
#
# this file is part of python-modules-base
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
""" tools to log via network """

import sys
import time
import os
import os.path
import cPickle
import socket
import net_tools
import logging_tools
import threading
import threading_tools
import struct
import process_tools
try:
    import stackless
    import stackless_tools
except:
    stackless, stackless_tools = (None, None)

LOG_DEST_STDOUT  = 0
LOG_DEST_UDS     = 1
LOG_DEST_UDP     = 2
LOG_DEST_FILE    = 3
LOG_DEST_SYSLOG  = 4
LOG_DEST_TCP     = 5
LOG_DEST_UNKNOWN = -1

class dummy_ios(object):
    def __init__(self):
        self.out_buffer = []
    def write(self, what):
        self.out_buffer.append(what)
    def close(self):
        pass
    def __del__(self):
        pass
    
class dummy_ios_low(object):
    def __init__(self, save_fd):
        self.orig_fd = save_fd
        self.save_fd = os.dup(self.orig_fd)
        self.tmp_fo = os.tmpfile()
        self.new_fd = self.tmp_fo.fileno()
        os.dup2(self.new_fd, self.orig_fd)
    def close(self):
        self.tmp_fo.seek(0)
        self.data = self.tmp_fo.read()
        os.dup2(self.save_fd, self.orig_fd)
        del self.orig_fd
        del self.tmp_fo
        os.close(self.save_fd)
    
class uds_send_struct(net_tools.buffer_object):
    def __init__(self, log_com):
        net_tools.buffer_object.__init__(self)
        self.__state, self.__state_str = (0, "ok")
    def error_set(self):
        return self.__state and True or False
    def set_send_str(self, what):
        self.__send_str = what
    def setup_done(self):
        self.socket.set_init_time()
        self.add_to_out_buffer(self.__send_str)
    def out_buffer_sent(self, s_len):
        self.out_buffer = self.out_buffer[s_len:]
        if self.out_buffer:
            pass
        else:
            self.socket.send_done()
            self.call_exit()
    def bind_state_call(self, **args):
        if args["state"] == "ok":
            self.__state, self.__state_str = (0, "ok")
        elif args["state"] == "error":
            self.__state, self.__state_str = (1, "bind error")
    def call_exit(self):
        self.socket.get_server().request_exit()
    def get_state(self):
        return self.__state, self.__state_str
    def report_problem(self, flag, what):
        self.__state, self.__state_str = (1, "%s: %s" % (net_tools.net_flag_to_str(flag), what))
        self.call_exit()
        
class log_command(object):
    def __init__(self, name, command="log", log_str=None, level=logging_tools.LOG_LEVEL_OK, host=None, log_time=None, thread=None, thread_safe=False, **args):
        if thread:
            self.__thread_name = thread
        else:
            self.__thread_name = threading_tools.get_act_thread_name()
        if stackless:
            # use stackles processing
            self.__stackless = True
            if "tasklet" in args:
                self.__tasklet_name = args["tasklet"]
            else:
                self.__tasklet_name = stackless_tools.get_act_tasklet_name()
        else:
            self.__tasklet_name = ""
            self.__stackless = False
        # thread safety
        self.__thread_safe = thread_safe
        if self.__thread_safe:
            self.__lock = threading.Lock()
        else:
            self.__lock = None
        # name of calling instance (f.e. package-client)
        self.set_name(name)
        # log command (log, open_log, close_log)
        self.__command = command
        # log_str can also be a list (maybe in future versions)
        self.__log_str, self.__log_level = (log_str, level)
        if log_time:
            self.__log_time = log_time
        else:
            self.__log_time = time.time()
        if host:
            self.__host = host
        else:
            self.__host = socket.gethostname()
        self.__net_send_obj = None
        self.__timeout = args.get("timeout", 10)
        # pre_struct is invalid
        self.__pre_struct_valid = False
        self.set_destination()
        self.set_prefix()
        self._generate_line()
        self.set_log_dest_type()
        self.init_errors()
        self.__use_count = 0
    def init_errors(self):
        self.__error_count = 0
        self.__err_dict = {}
    def error(self, r_state, r_str):
        self.__error_count += 1
        self.__err_dict.setdefault(r_state, 0)
        self.__err_dict[r_state] += 1
        logging_tools.my_syslog("error in thread %s%s sending logstr '%s' (%d, %s): %s (raw)" % (self.__thread_name,
                                                                                                 " (tasklet %s)" % (self.__tasklet_name) if self.__tasklet_name else "",
                                                                                                 self.get_raw_line(),
                                                                                                 r_state,
                                                                                                 r_str,
                                                                                                 ", ".join(["%d: %d" % (x, y) for x, y in self.__err_dict.iteritems()])))
    def set_log_dest_type(self, dt=LOG_DEST_UNKNOWN):
        self.__log_dest = dt
    def get_log_dest_type(self):
        return self.__log_dest
    def set_name(self, name="unknown"):
        parts = name.split("/")
        #print parts
        self.__name = parts.pop(0)
        self.set_sub_names(parts)
        self.__pre_struct_valid = False
    def set_sub_names(self, sn=""):
        if type(sn) == type(""):
            sn = sn.split("/")
        self.__sub_names = sn
        self.__pre_struct_valid = False
    def set_prefix(self, pf=""):
        self.__prefix = pf
        self.__pre_struct_valid = False
    def set_command(self, command):
        self.__command = command
        self.__pre_struct_valid = False
    def set_destination(self, dest_str=None):
        if not self.__net_send_obj:
            self.__net_send_obj = net_tools.network_send(timeout=self.__timeout)
        self.__dest_str = dest_str
        if not self.__dest_str:
            self.send_line_to_dest = self.send_line_to_syslog
            self.set_log_dest_type(LOG_DEST_SYSLOG)
        elif self.__dest_str == "stdout":
            self.send_line_to_dest = self.send_line_to_stdout
            self.set_log_dest_type(LOG_DEST_STDOUT)
        elif self.__dest_str.startswith("uds:"):
            self.__dest_addr = self.__dest_str.split(":")[1]
            self.__uds_blocking = True
            self.init_uds_object()
            self.send_line_to_dest = self.send_line_to_uds
            self.set_log_dest_type(LOG_DEST_UDS)
        elif self.__dest_str.startswith("uds_nb:"):
            self.__dest_addr = self.__dest_str.split(":")[1]
            self.__uds_blocking = False
            self.init_uds_object()
            self.send_line_to_dest = self.send_line_to_uds
            self.set_log_dest_type(LOG_DEST_UDS)
        elif self.__dest_str.startswith("udp:"):
            self.__dest_addr = self.__dest_str.split(":")[1]
            self.__dest_port = int(self.__dest_str.split(":")[2])
            self.send_line_to_dest = self.send_line_to_udp
            self.set_log_dest_type(LOG_DEST_UDP)
        elif self.__dest_str.startswith("tcp:"):
            self.__dest_addr = self.__dest_str.split(":")[1]
            self.__dest_port = int(self.__dest_str.split(":")[2])
            self.send_line_to_dest = self.send_line_to_tcp
            self.set_log_dest_type(LOG_DEST_TCP)
        elif self.__dest_str.startswith("file:"):
            self.__dest_addr = self.__dest_str.split(":")[1]
            self.send_line_to_dest = self.send_line_to_file
            self.set_log_dest_type(LOG_DEST_FILE)
        else:
            self.send_line_to_dest = self.send_line_to_syslog
    def generate_pre_struct(self):
        if not self.__pre_struct_valid:
            self.__pre_struct_valid = True
            if self.__tasklet_name:
                str_field = ["/".join([self.__name] + self.__sub_names),
                             self.__command,
                             self.__host,
                             self.__thread_name,
                             self.__tasklet_name]
            else:
                str_field = ["/".join([self.__name] + self.__sub_names),
                             self.__command,
                             self.__host,
                             self.__thread_name]
            self.__pre_struct_1 = struct.pack("=%di" % (len(str_field) + 1), self.__log_level, *[len(x) for x in str_field])
            self.__pre_struct_2 = struct.pack("".join(["="] + ["%ds" % (len(x)) for x in str_field]), *str_field)
    def _generate_line(self):
        # pre-pack str with str_lens
        if True:
            self.generate_pre_struct()
            r_log_line = "%s%s" % (self.__prefix, self.__log_str)
            # bpd1 : first version, timestamp was only a float -> error
            # bpd2 : timestamp as double (correct resolution)
            # bpd3 : as bpd2 with tasklet info
            if self.__tasklet_name:
                self.__line = "bpd3%s%s%s%s" % (self.__pre_struct_1,
                                                struct.pack("=id", len(r_log_line), self.__log_time),
                                                self.__pre_struct_2,
                                                struct.pack("=%ds" % (len(r_log_line)), r_log_line))
            else:
                self.__line = "bpd2%s%s%s%s" % (self.__pre_struct_1,
                                                struct.pack("=id", len(r_log_line), self.__log_time),
                                                self.__pre_struct_2,
                                                struct.pack("=%ds" % (len(r_log_line)), r_log_line))
        else:
            self.__line = cPickle.dumps(("/".join([self.__name] + self.__sub_names),
                                         self.__command,
                                         "%s%s" % (self.__prefix, self.__log_str),
                                         self.__log_level,
                                         self.__host,
                                         self.__log_time,
                                         self.__thread_name,
                                         self.__tasklet_name))
    def get_raw_line(self):
        return ";".join(["/".join([self.__name] + self.__sub_names),
                         self.__command,
                         "%s%s" % (self.__prefix, self.__log_str),
                         str(self.__log_level),
                         self.__host,
                         str(self.__log_time),
                         str(self.__thread_name),
                         str(self.__tasklet_name)])
    def _send_line(self):
        self._generate_line()
        return self.send_line_to_dest()
    def close(self):
        if self.__dest_str:
            if self.__dest_str.startswith("uds"):
                self.__uds_socket.close()
                self.__uds_socket.delete()
                del self.__uds_socket
                del self.__uds_send_obj
        if self.__net_send_obj:
            self.__net_send_obj.close()
            self.__net_send_obj = None
    # send_line_to_DEST
    def send_line_to_stdout(self):
        print self.get_log_line()
    def _uds_send_ok(self, sock):
        return self.__uds_send_obj
    def init_uds_object(self):
        # uds send_object
        self.__uds_send_obj = uds_send_struct(self)
        # uds socket
        self.__uds_socket = net_tools.uds_con_object(self._uds_send_ok, socket=self.__dest_addr, bind_retries=0, rebind_wait_time=0.01, connect_state_call=self.__uds_send_obj.bind_state_call)
        self.__net_send_obj.add_object(self.__uds_socket)
    def send_line_to_uds(self):
        if self.__use_count:
            print "%s: ERROR, log_command already in use from thread %s (calling thread: %s [tasklet %s]), log_line is %s" % (time.ctime(),
                                                                                                                              self.__thread_name,
                                                                                                                              self.__tasklet_name,
                                                                                                                              threading_tools.get_act_thread_name(),
                                                                                                                              self.__line)
        self.__use_count += 1
        # set content
        self.__uds_send_obj.set_send_str(self.__line)
        # error last time ?
        if self.__uds_send_obj.error_set():
            # try to reopen 
            self.__uds_socket.try_to_reopen(self.__net_send_obj)
        if self.__uds_send_obj.socket:
            # socket set, set init_time and add to string to out_buffer
            self.__uds_send_obj.setup_done()
        self.__net_send_obj.step()
        while not self.__net_send_obj.exit_requested() and self.__net_send_obj.get_num_objects():
            self.__net_send_obj.step()
        self.__net_send_obj.request_exit(False)
        ret_state, ret_str = self.__uds_send_obj.get_state()
        self.__use_count -= 1
        if ret_state:
            self.error(ret_state, ret_str)
        return (ret_state, ret_str)
    def send_line_to_udp(self):
        ret_state, ret_str = net_tools.single_connection(mode="udp",
                                                         host=self.__dest_addr,
                                                         port=self.__dest_port,
                                                         command=self.__line,
                                                         protocoll=0).iterate()
        if ret_state:
            self.error(ret_state, ret_str)
        return (ret_state, ret_str)
    def send_line_to_tcp(self):
        ret_state, ret_str = net_tools.single_connection(mode="tcp",
                                                         host=self.__dest_addr,
                                                         port=self.__dest_port,
                                                         command=self.__line,
                                                         protocoll=1).iterate()
        if ret_state:
            self.error(ret_state, ret_str)
        return (ret_state, ret_str)
    def send_line_to_file(self):
        try:
            file(self.__dest_addr, "a").write("%s\n" % (self.get_log_line()))
        except:
            logging_tools.my_syslog("error write to file %s: %s" % (self.__dest_addr, process_tools.get_except_info()))
    def send_line_to_syslog(self):
        logging_tools.my_syslog("Unknown log_destination '%s', name %s, string %s, thread %s" % (self.__dest_str, self.__name, self.__log_str, self.__thread_name))
    def get_thread(self):
        return self.__thread_name
    def get_tasklet(self):
        return self.__tasklet_name
    def get_name(self, with_sub_names=0):
        if with_sub_names:
            return "/".join([self.__name] + self.__sub_names)
        else:
            return self.__name
    def get_host(self):
        return self.__host
    def get_command(self):
        return self.__command
    def set_command_and_send(self, command):
        self.set_command(command)
        self._send_line()
    def set_log_str(self, log_str, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_time = time.time()
        self.__log_str = log_str
        if log_level is not None:
            if log_level != self.__log_level:
                self.__pre_struct_valid = False
                self.__log_level = log_level
    def log(self, log_str, log_level=logging_tools.LOG_LEVEL_OK):
        if self.__lock:
            # at first lock thread
            self.__lock.acquire()
            if self.__stackless:
                # then tasklet
                act_tl = stackless.getcurrent()
                was_atomic = act_tl.set_atomic(True)
        self.set_log_str(log_str, log_level)
        try:
            log_result = self._send_line()
        except:
            exc_info = process_tools.get_except_info()
            logging_tools.my_syslog("error logging %s (%d): %s" % (log_str, log_level, exc_info))
            log_result = (666, "internal error: %s" % (exc_info))
        if self.__lock:
            if self.__stackless:
                # release tasklet
                act_tl.set_atomic(was_atomic)
            # and thread
            self.__lock.release()
        return log_result
    def get_log_str(self):
        return self.__log_str
    def get_log_level(self):
        return self.__log_level
    def get_log_time(self):
        return self.__log_time
    def get_log_line(self):
        # beautify (what, level tuple)
        h_info = "host %s, %s" % (self.__host,
                                  "file %s" % ("/".join(self.__sub_names)) if self.__sub_names else "<TOP LEVEL>")
        if self.__command == "log":
            return "%-4s %-14s%s" % (logging_tools.get_log_level_str(self.__log_level),
                                     "[%s%s]" % (self.__thread_name,
                                                 ".%s" % (self.__tasklet_name) if self.__tasklet_name else ""),
                                     self.__log_str)
        elif self.__command == "open_log":
            return "------- opening log for %s (%s) --------------------------" % (self.__name, h_info)
        elif self.__command == "close_log":
            return "------- closing log for %s (%s) --------------------------" % (self.__name, h_info)
        else:
            return "*** unknown command %s for %s (%s) ***" % (self.__command, self.__name, h_info)
    def __len__(self):
        return len(self.__line)
    def __str__(self):
        return self.__line
    
if __name__ == "__main__":
    print "Loadable module, exiting..."
    sys.exit(0)
