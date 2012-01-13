#!/usr/bin/python -Ot
#
# Copyright (C) 2007 Andreas Lang
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
import sys
import config_tools
import time
import os
import net_tools

class simple_tcp_obj(net_tools.buffer_object):
    # connects to a foreign cluster-server
    def __init__(self, stc, send_str):
        self.__stc = stc
        self.__send_str = send_str
        net_tools.buffer_object.__init__(self)
    def setup_done(self):
        self.add_to_out_buffer(net_tools.add_proto_1_header(self.__send_str, True))
    def out_buffer_sent(self, send_len):
        if send_len == len(self.__send_str) + 8:
            self.out_buffer = ""
            self.socket.send_done()
        else:
            self.out_buffer = self.out_buffer[send_len:]
            self.__send_len -= send_len
    def add_to_in_buffer(self, what):
        self.in_buffer += what
        p1_ok, p1_data = net_tools.check_for_proto_1_header(self.in_buffer)
        if p1_ok:
            self.__stc.set_result(p1_data)
            self.delete()
    def report_problem(self, flag, what):
        self.__stc.set_error("%s : %s" % (net_tools.net_flag_to_str(flag), what))
        self.delete()
        
class server_com(object):
    def __init__(self):
        cl_name = str(self.__class__).split(".")[-1]
        while True:
            if cl_name[-1] in [">", "'"]:
                cl_name = cl_name[:-1]
            else:
                break
        self.name = cl_name
        self.set_needed_option_keys()
        self.set_used_config_keys()
        self.set_act_config()
        self.set_showtime()
        self.set_write_log()
        self.set_config()
        self.set_blocking_mode()
        self.set_is_restartable()
        self.set_public_via_net()
        self.file_name = ""
    def set_public_via_net(self, pub=True):
        self.__public_via_net = pub
    def get_public_via_net(self):
        return self.__public_via_net
    def set_is_restartable(self, rs=0):
        self.is_restartable = rs
    def get_is_restartable(self):
        return self.is_restartable
    def get_name(self):
        return self.name
    def set_blocking_mode(self, block = 1):
        self.is_blocking = block
    def get_blocking_mode(self):
        return self.is_blocking
    def set_used_config_keys(self, keys=[]):
        self.used_config_keys = keys
    def get_used_config_keys(self):
        return self.used_config_keys and ", ".join(self.used_config_keys) or "<none>"
    def set_needed_option_keys(self, keys = []):
        self.needed_option_keys = keys
    def get_needed_option_keys(self):
        return self.needed_option_keys and ", ".join(self.needed_option_keys) or "<none>"
    def set_config(self, conf=[]):
        self.config = conf
    def get_config(self):
        if self.config:
            return ", ".join(self.config)
        else:
            return "<not set>"
    def get_config_list(self):
        return self.config
    #def set_config_type(self, conf_type=[]):
    #    self.config_type = conf_type
    def check_config(self, dc, loc_config, force=0):
        self.server_idx, self.act_config_name = (0, "")
        doit, srv_origin, err_str = (False, "---", "OK")
        if self.config:
            for act_c in self.config:
                sql_info = config_tools.server_check(dc=dc, server_type="%s%%" % (act_c))
                if sql_info.num_servers:
                    doit, srv_origin = (True, sql_info.server_origin)
                    if not self.server_idx:
                        self.server_device_name = sql_info.server_config_name
                        self.server_idx, self.act_config_name = (sql_info.server_config_idx, sql_info.real_server_name)
            if doit:
                self.set_act_config(self.config)
            else:
                if force:
                    doit = True
                else:
                    err_str = "Server %s has no %s attribute" % (loc_config["SERVER_SHORT_NAME"], " or ".join(self.config))
        else:
            doit = True
        if doit and srv_origin == "---":
            srv_origin = "yes"
        return (doit, srv_origin, err_str)
    def set_act_config(self, act_config=[]):
        self.act_config = act_config
    def set_write_log(self, wl=1):
        self.write_log = wl
    def get_write_log(self):
        return self.write_log
    def set_showtime(self, st=1):
        self.showtime = st
    def __call__(self, call_params):
        self.start_time = time.time()
        what = self.call_it(call_params.server_com.get_option_dict(), call_params)
        if not what:
            what = "<no return>"
        self.end_time = time.time()
        if self.showtime:
            if type(what) == type(""):
                # simple string
                what += " in %.2f seconds" % (self.end_time - self.start_time)
            else:
                # server reply
                what.set_result("%s in %.2f seconds" % (what.get_result(), self.end_time - self.start_time))
        return what
        
if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
    
