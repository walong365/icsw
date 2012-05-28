#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2012 Andreas Lang-Nevyjel
#
# this file is part of package-server
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
""" package server """

import sys
import os
import re
try:
    import bz2
except:
    bz2 = None
import configfile_old as configfile
import time
import datetime
import configfile
import uuid_tools
import logging_tools
import process_tools
import mysql_tools
import MySQLdb
import server_command
import threading_tools
import net_tools
import pprint
from lxml import etree
from lxml.builder import E
import xml
import xml.dom.minidom
import xml_tools
import xml.parsers.expat
import inotify_tools
import stat
import config_tools
sys.path.append("/usr/local/sbin")
import insert_package_info
import zmq

try:
    from package_server_version import VERSION_STRING
except ImportError:
    VERSION_STRING = "unknown.unknown"

P_SERVER_PUB_PORT   = 8007
P_SERVER_PULL_PORT  = 8008
PACKAGE_CLIENT_PORT = 2003

ADD_PACK_PATH = "additional_packages"
DEL_PACK_PATH = "deleted_packages"

LAST_CONTACT_VAR_NAME    = "package_server_last_contact"
PACKAGE_VERSION_VAR_NAME = "package_client_version"
DIRECT_MODE_VAR_NAME     = "package_client_direct_mode"

SQL_ACCESS = "cluster_full_access"

CONFIG_NAME = "/etc/sysconfig/cluster/package_server_clients.xml"

### --------------------------------------------------------------------------------
##class connection_from_node(net_tools.buffer_object):
##    # receiving connection object for node connection
##    def __init__(self, sock, src, dest_queue):
##        self.__dest_queue = dest_queue
##        self.__src = src
##        net_tools.buffer_object.__init__(self)
##    def __del__(self):
##        #print "- del new_relay_con"
##        pass
##    def add_to_in_buffer(self, what):
##        self.in_buffer += what
##        is_p1, what = net_tools.check_for_proto_1_header(self.in_buffer)
##        if is_p1:
##            self.__dest_queue.put(("node_connection", (self, self.__src, what)))
##    def send_return(self, what):
##        self.lock()
##        if self.socket:
##            self.add_to_out_buffer(net_tools.add_proto_1_header(what))
##        else:
##            pass
##        self.unlock()
##    def out_buffer_sent(self, send_len):
##        if send_len == len(self.out_buffer):
##            self.out_buffer = ""
##            self.socket.send_done()
##            self.close()
##        else:
##            self.out_buffer = self.out_buffer[send_len:]
##    def report_problem(self, flag, what):
##        self.__dest_queue.put(("node_error", "%s : %s, src is %s" % (net_tools.net_flag_to_str(flag),
##                                                                     what,
##                                                                     str(self.__src))))
##        self.close()
##
##class connection_for_command(net_tools.buffer_object):
##    # receiving connection object for command connection
##    def __init__(self, sock, src, dest_queue):
##        self.__dest_queue = dest_queue
##        self.__src = src
##        net_tools.buffer_object.__init__(self)
##    def __del__(self):
##        #print "- del new_relay_con"
##        pass
##    def add_to_in_buffer(self, what):
##        self.in_buffer += what
##        is_p1, what = net_tools.check_for_proto_1_header(self.in_buffer)
##        if is_p1:
##            self.__dest_queue.put(("new_command", (self, self.__src, what)))
##    def send_return(self, what):
##        self.lock()
##        if self.socket:
##            self.add_to_out_buffer(net_tools.add_proto_1_header(what))
##        else:
##            pass
##        self.unlock()
##    def out_buffer_sent(self, send_len):
##        if send_len == len(self.out_buffer):
##            self.out_buffer = ""
##            self.socket.send_done()
##            self.close()
##        else:
##            self.out_buffer = self.out_buffer[send_len:]
##    def report_problem(self, flag, what):
##        self.__dest_queue.put(("command_error", (self, self.__src, "%s : %s" % (net_tools.net_flag_to_str(flag), what))))
##        self.close()
##
##class connection_to_node(net_tools.buffer_object):
##    # connects to a foreign package-client
##    def __init__(self, (act_dict, mach), ret_queue):
##        self.__act_dict = act_dict
##        self.__mach = mach
##        self.__ret_queue = ret_queue
##        net_tools.buffer_object.__init__(self)
##    def setup_done(self):
##        self.add_to_out_buffer(net_tools.add_proto_1_header(self.__act_dict["command"].get_command(), True))
##    def out_buffer_sent(self, send_len):
##        if send_len == len(self.out_buffer):
##            self.out_buffer = ""
##            self.socket.send_done()
##        else:
##            self.out_buffer = self.out_buffer[send_len:]
##    def add_to_in_buffer(self, what):
##        self.in_buffer += what
##        p1_ok, p1_data = net_tools.check_for_proto_1_header(self.in_buffer)
##        if p1_ok:
##            self.__ret_queue.put(("send_ok", ((self.__act_dict, self.__mach), p1_data)))
##            self.delete()
##    def report_problem(self, flag, what):
##        self.__ret_queue.put(("send_error", ((self.__act_dict, self.__mach), "%s : %s" % (net_tools.net_flag_to_str(flag), what))))
##        self.delete()
##
##class connection_to_cluster_server(net_tools.buffer_object):
##    # connects to a foreign package-client
##    def __init__(self, (srv_com, srv_name), ret_queue):
##        self.__srv_com = srv_com
##        self.__srv_name = srv_name
##        self.__ret_queue = ret_queue
##        net_tools.buffer_object.__init__(self)
##    def setup_done(self):
##        self.add_to_out_buffer(net_tools.add_proto_1_header(self.__srv_com, True))
##    def out_buffer_sent(self, send_len):
##        if send_len == len(self.out_buffer):
##            self.out_buffer = ""
##            self.socket.send_done()
##        else:
##            self.out_buffer = self.out_buffer[send_len:]
##    def add_to_in_buffer(self, what):
##        self.in_buffer += what
##        p1_ok, p1_data = net_tools.check_for_proto_1_header(self.in_buffer)
##        if p1_ok:
##            self.__ret_queue.put(("srv_send_ok", ((self.__srv_com, self.__srv_name), p1_data)))
##            self.delete()
##    def report_problem(self, flag, what):
##        self.__ret_queue.put(("srv_send_error", ((self.__srv_com, self.__srv_name), "%s : %s" % (net_tools.net_flag_to_str(flag), what))))
##        self.delete()
### --------------------------------------------------------------------------------

##class logging_thread(threading_tools.thread_obj):
##    def __init__(self, glob_config):
##        self.__glob_config = glob_config
##        self.__handles, self.__log_buffer, self.__global_log = ({}, [], None)
##        self.__sep_str = "-" * 50
##        threading_tools.thread_obj.__init__(self, "log", queue_size=100, priority=10)
##        self.register_func("log", self._log)
##        self.register_func("write_file", self._write_file)
##    def thread_running(self):
##        self.send_pool_message(("new_pid", self.pid))
##        self.__root = self.__glob_config["LOG_DIR"]
##        if not os.path.isdir(self.__root):
##            try:
##                os.makedirs(self.__root)
##            except OSError:
##                # we have to write to syslog
##                self.log("Unable to create '%s' directory" % (self.__root), logging_tools.LOG_LEVEL_ERROR)
##                self.__root = "/tmp"
##            else:
##                pass
##        glog_name = "%s/log" % (self.__root)
##        self.__global_log = logging_tools.logfile(glog_name)
##        self.__global_log.write(self.__sep_str, header = 0)
##        self.__global_log.write("(%s) Opening log" % (self.name))
##    def _get_handle(self, dev_name, file_name="log", register=True):
##        full_name = "%s/%s" % (dev_name, file_name)
##        if self.__handles.has_key(full_name):
##            handle = self.__handles[full_name]
##        else:
##            machdir = "%s/%s" % (self.__root, dev_name)
##            if not os.path.isdir(machdir):
##                self.__global_log.write("Creating dir %s for %s" % (machdir, dev_name))
##                os.makedirs(machdir)
##            if register:
##                handle = logging_tools.logfile("%s/%s" % (machdir, file_name))
##                self.__handles[full_name] = handle
##                handle.write(self.__sep_str)
##                handle.write("Opening log")
##            else:
##                handle = file("%s/%s" % (machdir, file_name), "w")
##        return handle
##    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
##        if self.__global_log:
##            if self.__log_buffer:
##                for b_what, b_line in self.__log_buffer:
##                    self._log((b_what, b_line))
##                self.__log_buffer = []
##            self._log((what, lev))
##        else:
##            self.__log_buffer.append((what, lev))
##    def _log(self, l_stuff):
##        if len(l_stuff) == 2:
##            what, lev = l_stuff
##            thread_name, node_name = (self.name, "")
##        elif len(l_stuff) == 3:
##            what, lev, thread_name = l_stuff
##            node_name = ""
##        else:
##            what, lev, thread_name, node_name = l_stuff
##        if node_name:
##            handle = self._get_handle(node_name)
##        else:
##            handle = self.__global_log
##        thread_pfix = "(%s)" % (thread_name.endswith("_thread") and thread_name[:-7] or thread_name)
##        handle.write("%-6s%s %s" % (logging_tools.get_log_level_str(lev), thread_pfix, what))
##    def _write_file(self, (dev_name, file_name, what)):
##        self._get_handle(dev_name, file_name, False).write(what)
##    def loop_end(self):
##        for mach in self.__handles.keys():
##            self.__handles[mach].write("Closing log")
##            self.__handles[mach].close()
##        self.__global_log.write("Closed %s" % (logging_tools.get_plural("machine log", len(self.__handles.keys()))))
##        self.__global_log.write("Closing log")
##        self.__global_log.close()
        
class command_thread(threading_tools.thread_obj):
    def __init__(self, log_queue, db_con, glob_config):
        self.__log_queue = log_queue
        self.__db_con = db_con
        self.__glob_config = glob_config
        threading_tools.thread_obj.__init__(self, "command", queue_size=100)
        self.register_func("set_queue"     , self._set_queue)
        self.register_func("update"        , self._update)
        self.register_func("srv_command"   , self._srv_command)
        self.register_func("set_net_server", self._set_net_server)
        self.register_func("send_error"    , self._send_error)
        self.register_func("srv_send_ok"   , self._srv_send_ok)
        self.register_func("srv_send_error", self._srv_send_error)
        self.register_func("send_ok"       , self._send_ok)
        self.register_func("new_command"   , self._new_command)
        self.register_func("command_error" , self._command_error)
        self.__queue_dict = {}
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK, node_name=""):
        self.__log_queue.put(("log", (what, lev, self.name, node_name)))
    def thread_running(self):
        self.send_pool_message(("new_pid", self.pid))
        self.__dev_conf_send_dict = {}
        self.__com_dict = {"new_config"       : self._new_config,
                           "new_rsync_config" : self._new_rsync_config,
                           "delete_packages"  : self._delete_packages}
        self.__ret_dict = {}
        self.__local_key = 0
        self.__last_update = time.time()
    def _set_net_server(self, ns):
        self.log("Netserver set")
        self.__net_server = ns
    def _set_queue(self, (q_name, q_addr)):
        self.log("Setting queue %s" % (q_name))
        self.__queue_dict[q_name] = q_addr
    def _update(self):
        act_time = time.time()
        if abs(act_time - self.__last_update) < 60 and False:
            pass
        else:
            self.__last_update = act_time
            dc = self.__db_con.get_connection(SQL_ACCESS)
            sql_str = "SELECT DISTINCT d.name FROM device d INNER JOIN device_group dg INNER JOIN new_config c INNER JOIN device_config dc INNER JOIN device_type dt LEFT JOIN device d2 ON d2.device_idx=dg.device WHERE " + \
                      "d.device_group=dg.device_group_idx AND (dc.device=d2.device_idx OR dc.device=d.device_idx) AND dc.new_config=c.new_config_idx AND dt.device_type_idx=d.device_type AND c.name='package_client' AND dt.identifier='H'"
            dc.execute(sql_str)
            add_names = [x["name"] for x in dc.fetchall() if x["name"] not in self.__dev_conf_send_dict.keys()]
            dc.release()
            for add_name in add_names:
                self.__dev_conf_send_dict[add_name] = {"num" : 0}
            machs_to_update = [k for k, v in self.__dev_conf_send_dict.iteritems() if abs(v.get("last_send", 0) - act_time) > self.__glob_config["RENOTIFY_CLIENTS_TIMEOUT"]]
            # don't send to already pending hosts
            machs_to_update = [x for x in machs_to_update if not len([True for pendings in self.__ret_dict.values() if x in pendings["command"].get_nodes()])]
            if machs_to_update:
                self.log("Sending new_config command to %s: %s" % (logging_tools.get_plural("device", len(machs_to_update)),
                                                                   logging_tools.compress_list(machs_to_update)))
                self._srv_command(server_command.server_command(command="new_config", nodes=machs_to_update))
    def _new_config(self, srv_com):
        # new config for nodes
        self._srv_command(srv_com)
    def _new_rsync_config(self, srv_com):
        # new rsync config for nodes
        self._srv_command(srv_com)
    def _srv_command(self, srv_com):
        self.__local_key += 1
        self.__ret_dict[self.__local_key] = {"key"        : self.__local_key,
                                             "command"    : srv_com,
                                             "open"       : len(srv_com.get_nodes()),
                                             "start_time" : time.time(),
                                             "results"    : dict([(k, "") for k in srv_com.get_nodes()])}
        self.log("got srv_command (command %s) for %s: %s" % (srv_com.get_command(),
                                                              logging_tools.get_plural("node", len(srv_com.get_nodes())),
                                                              logging_tools.compress_list(srv_com.get_nodes())))
        for mach in srv_com.get_nodes():
            self.__dev_conf_send_dict.setdefault(mach, {"num" : 0, "last_send" : time.time()})
            self.__dev_conf_send_dict[mach]["num"] += 1
            self.__dev_conf_send_dict[mach]["last_send"] = time.time()
            self.__net_server.add_object(net_tools.tcp_con_object(self._new_node_connection,
                                                                  connect_state_call=self._connect_state_call,
                                                                  connect_timeout_call=self._connect_timeout,
                                                                  timeout=8,
                                                                  bind_retries=1,
                                                                  rebind_wait_time=1,
                                                                  target_port=self.__glob_config["CLIENT_PORT"],
                                                                  target_host=mach,
                                                                  add_data=(self.__ret_dict[self.__local_key],
                                                                            mach)))
        if not self.__ret_dict[self.__local_key]["open"]:
            self._dict_changed(self.__ret_dict[self.__local_key])
    def _delete_packages(self, srv_com):
        res_com = server_command.server_reply(result="got command",
                                              state=server_command.SRV_REPLY_STATE_OK)
        p_idxs = srv_com.get_option_dict().get("package_idxs", [])
        if p_idxs:
            self.__queue_dict["watcher"].put(("delete_packages", p_idxs))
            # signal via file-creating
            try:
                file("%s/.queue_signal" % (self.__glob_config["ROOT_EXPORT_DIR"]), "w").write("-")
            except:
                self.log("cannot create file in %s: %s" % (self.__glob_config["ROOT_EXPORT_DIR"],
                                                           process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
        srv_com.get_key().send_return(res_com)
    def _send_error(self, ((act_dict, mach), why)):
        self.log("Error for device %s: %s" % (mach, why), logging_tools.LOG_LEVEL_ERROR)
        act_dict["results"][mach] = "error %s" % (why)
        act_dict["open"] -= 1
        self._dict_changed(act_dict)
    def _send_ok(self, ((act_dict, mach), result)):
        act_dict["results"][mach] = result
        act_dict["open"] -= 1
        self._dict_changed(act_dict)
    def _dict_changed(self, act_dict):
        if not act_dict["open"]:
            act_srv_command = act_dict["command"]
            ret_str = "ok got command #%s" % ("#".join([act_dict["results"][x] for x in act_srv_command.get_nodes()]))
            con_obj = act_srv_command.get_key()
            if con_obj:
                self.log("Returning str (took %s): %s" % (logging_tools.get_diff_time_str(time.time() - act_dict["start_time"]), ret_str))
                res_com = server_command.server_reply()
                res_com.set_ok_result("got command")
                res_com.set_node_results(act_dict["results"])
                con_obj.send_return(res_com)
            else:
                if act_srv_command.get_queue():
                    act_srv_command.get_queue().put(("status_result", act_dict["results"]))
                self.log("No need to return str (took %s): %s" % (logging_tools.get_diff_time_str(time.time() - act_dict["start_time"]), ret_str))
            del self.__ret_dict[act_dict["key"]]
            del act_dict
    def _connect_timeout(self, sock):
        self.get_thread_queue().put(("send_error", (sock.get_add_data(), "connect timeout")))
        sock.close()
    def _connect_state_call(self, **args):
        if args["state"] == "error":
            self.get_thread_queue().put(("send_error", (args["socket"].get_add_data(), "connection error")))
    def _new_node_connection(self, sock):
        return connection_to_node(sock.get_add_data(), self.get_thread_queue())
    def _command_error(self, (con_obj, (other_ip, other_addr), what)):
        self.log("Error for server_command: %s (%s, port %d)" % (what, other_ip, other_addr), logging_tools.LOG_LEVEL_ERROR)
    def _new_command(self, (con_obj, (other_ip, other_addr), what)):
        try:
            srv_com = server_command.server_command(what)
        except:
            srv_com = None
        else:
            if srv_com.get_command() == what:
                srv_com = None
        if srv_com:
            srv_com.set_key(con_obj)
            if srv_com.get_command() == "status":
                con_obj.send_return(self._status_com())
            elif srv_com.get_command() == "new_rsync_server_config":
                res_com = server_command.server_reply()
                res_com.set_state_and_result(server_command.SRV_REPLY_STATE_OK, "ok got it")
                con_obj.send_return(res_com)
                self.__net_server.add_object(net_tools.tcp_con_object(self._new_cluster_server_connection,
                                                                      connect_state_call=self._ncs_connect_state_call,
                                                                      connect_timeout_call=self._ncs_connect_timeout,
                                                                      timeout=10,
                                                                      bind_retries=1,
                                                                      rebind_wait_time=1,
                                                                      target_port=8004,
                                                                      target_host="localhost",
                                                                      add_data=(server_command.server_command(command="write_rsyncd_config"), "localhost")))
            elif srv_com.get_command() in self.__com_dict.keys():
                self.log("got command %s from %s (port %d)" % (srv_com.get_command(), other_ip, other_addr))
                self.__com_dict[srv_com.get_command()](srv_com)
            else:
                res_com = server_command.server_reply()
                res_com.set_error_result("unknown command %s" % (srv_com.get_command()))
                con_obj.send_return(res_com)
        else:
            con_obj.send_return("error unknown command %s (or missing server_command)" % (what))
    def _status_com(self):
        num_ok, num_threads = (self.get_thread_pool().num_threads_running(False),
                               self.get_thread_pool().num_threads(False))
        if num_ok == num_threads:
            ret_com = server_command.server_reply(state=server_command.SRV_REPLY_STATE_OK,
                                                  result="OK all %d threads running (version %s)" % (num_ok, VERSION_STRING))
        else:
            ret_com = server_command.server_reply(state=server_command.SRV_REPLY_STATE_ERROR,
                                                  result="ERROR only %d of %d threads running (version %s)" % (num_ok, num_threads, VERSION_STRING))
        return ret_com
    # connection to local cluster-server
    def _new_cluster_server_connection(self, sock):
        return connection_to_cluster_server(sock.get_add_data(), self.get_thread_queue())
    def _ncs_connect_timeout(self, sock):
        self.get_thread_queue().put(("srv_send_error", (sock.get_add_data(), "connect timeout")))
        sock.close()
    def _ncs_connect_state_call(self, **args):
        if args["state"] == "error":
            self.get_thread_queue().put(("srv_send_error", (args["socket"].get_add_data(), "connection error")))
    def _srv_send_error(self, ((srv_com, srv_name), why)):
        self.log("Error sending server_command %s to server %s: %s" % (srv_com.get_command(), srv_name, why), logging_tools.LOG_LEVEL_ERROR)
    def _srv_send_ok(self, ((srv_com, srv_name), result)):
        self.log("Sent server_command %s to server %s" % (srv_com.get_command(), srv_name))
        
class package_status_thread(threading_tools.thread_obj):
    def __init__(self, log_queue, db_con, glob_config):
        self.__log_queue = log_queue
        self.__db_con = db_con
        self.__glob_config = glob_config
        threading_tools.thread_obj.__init__(self, "package_status", queue_size=100)
        self.__queue_dict = {}
        self.register_func("set_queue", self._set_queue)
        self.register_func("package_status", self._package_status)
        self.register_func("rsync_object_status", self._rsync_object_status)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (what, lev, self.name, "")))
    def node_log(self, what, node_name, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (what, lev, self.name, node_name)))
    def thread_running(self):
        self.send_pool_message(("new_pid", self.pid))
        self.__dc = self.__db_con.get_connection(SQL_ACCESS)
    def _set_queue(self, (q_name, q_addr)):
        self.log("Setting queue %s" % (q_name))
        self.__queue_dict[q_name] = q_addr
    def _process_result_field(self, res_field, dev_idx, host_name, host_ip, error_dict):
        # package results
        sql_str = "SELECT ipd.instp_device_idx, CONCAT(p.name, '-', p.version, '-', p.release) AS pname, ipd.status, UNIX_TIMESTAMP(ipd.install_time) AS install_time, ipd.install, ipd.del, ipd.device, ipd.`upgrade`, ipd.error_lines FROM " + \
                  "instp_device ipd, inst_package ip, package p WHERE " + \
                  "p.package_idx=ip.package AND ip.inst_package_idx=ipd.inst_package AND (%s) AND ipd.device=%d" % (" OR ".join(["CONCAT(p.name,'-',p.version,'-',p.release)='%s'" % (p_name) for p_name, p_stat, p_time, status, extra_error_lines in res_field]), dev_idx)
        #print sql_str
        self.__dc.execute(sql_str)
        num_ok, act_stat_dict = (0, {})
        for db_rec in self.__dc.fetchall():
            act_stat_dict.setdefault(db_rec["device"], {}).setdefault(db_rec["pname"], []).append(db_rec)
        if act_stat_dict.has_key(dev_idx):
            dev_parts = act_stat_dict[dev_idx]
            for p_name, p_stat, p_time, status, extra_error_lines in res_field:
                ipd_stuff = dev_parts.get(p_name, [])
                if len(ipd_stuff) == 1:
                    ipd_stuff = ipd_stuff[0]
                    new_stat = "%s %s" % (p_stat, status)
                    update_ipd = False
                    if new_stat != ipd_stuff["status"] or p_time != ipd_stuff["install_time"] or extra_error_lines != ipd_stuff["error_lines"]:
                        update_ipd = True
                    if status.startswith("lost") and ((ipd_stuff["install"] or ipd_stuff["upgrade"]) or not ipd_stuff["del"]):
                        update_ipd = True
                    if update_ipd:
                        sql_set, sql_tuple = ("status=%%s, install_time=FROM_UNIXTIME(%d)%s, error_line_num=%d, error_lines=%%s" % (p_time,
                                                                                                                                    status.startswith("lost") and ", install=0, `upgrade`=0, del=1" or "",
                                                                                                                                    len(extra_error_lines.split("\n"))),
                                              (new_stat, extra_error_lines))
                        self.__dc.execute("UPDATE instp_device SET %s WHERE instp_device_idx=%d" % (sql_set, ipd_stuff["instp_device_idx"]), sql_tuple)
                        self.node_log(" - updating status for %s: %s" % (p_name, new_stat), host_name)
                    else:
                        self.node_log(" - status for %s still valid: %s" % (p_name, ipd_stuff["status"]), host_name)
                    num_ok += 1
                    db_err = None
                elif len(ipd_stuff) > 1:
                    db_err = "%d > 1" % (len(ipd_stuff))
                else:
                    db_err = "no match"
                if db_err:
                    self.log("Database error (%s) for rpm_info '%s' for package %s from host %s" % (db_err, status, p_name, host_name), logging_tools.LOG_LEVEL_ERROR)
                    self.node_log(" - Database error (%s) for %s: %s %s" % (db_err, p_name, p_stat, status), host_name, logging_tools.LOG_LEVEL_ERROR)
                    error_dict["db"] += 1
        else:
            self.log("Database error (?): found no packages named '%s' for device %s" % (",".join([p_name for p_name, p_stat, p_time, status, extra_error_field in res_field]), host_ip), logging_tools.LOG_LEVEL_ERROR)
            error_dict["db"] += 1
        return num_ok
    def _process_rso_result_field(self, res_field, dev_idx, host_name, host_ip, error_dict):
        # rsync_object results
        sql_str = "SELECT cs.value, rc.device_rsync_config_idx, rc.status, rc.device FROM device_rsync_config rc, config_str cs WHERE cs.new_config=rc.new_config AND " + \
                  "cs.name='rsync_name' AND (%s) AND rc.device=%d" % (" OR ".join(["cs.value='%s'" % (p_name) for p_name, p_state, p_status in res_field]),
                                                                      dev_idx)
        self.__dc.execute(sql_str)
        num_ok, act_stat_dict = (0, {})
        for db_rec in self.__dc.fetchall():
            act_stat_dict.setdefault(db_rec["device"], {}).setdefault(db_rec["value"], []).append(db_rec)
        if act_stat_dict.has_key(dev_idx):
            dev_parts = act_stat_dict[dev_idx]
            for r_name, r_stat, status in res_field:
                rso_stuff = dev_parts.get(r_name, [])
                if len(rso_stuff) == 1:
                    rso_stuff = rso_stuff[0]
                    new_stat = "%s %s" % (r_stat, status)
                    update_rso = False
                    if new_stat != rso_stuff["status"]:
                        update_rso = True
                    if update_rso:
                        self.__dc.execute("UPDATE device_rsync_config SET status=%s WHERE device_rsync_config_idx=%s", (new_stat, rso_stuff["device_rsync_config_idx"]))
                        self.node_log(" - updating status for %s: %s" % (r_name, new_stat), host_name)
                    else:
                        self.node_log(" - status for %s still valid: %s" % (r_name, new_stat), host_name)
                    num_ok += 1
                    db_err = None
                elif len(rso_stuff) > 1:
                    db_err = "%d > 1" % (len(rso_stuff))
                else:
                    db_err = "no match"
                if db_err:
                    self.log("Database error (%s) for rsync_object_info '%s' for rsync_object %s from host %s" % (db_err, status, r_name, host_name), logging_tools.LOG_LEVEL_ERROR)
                    self.node_log(" - Database error (%s) for %s: %s %s" % (db_err, r_name, r_stat, status), host_name, logging_tools.LOG_LEVEL_ERROR)
                    error_dict["db"] += 1
        else:
            self.log("Database error (?): found no rsync_objects named '%s' for device %s" % (",".join([r_name for r_name, r_stat, status in res_field]), host_ip), logging_tools.LOG_LEVEL_ERROR)
            error_dict["db"] += 1
        return num_ok
    def _package_status(self, (dev_idx, host_name, src_ip, pack_list)):
        error_dict = {"db" : 0}
        res_field = []
        for act_dict in [x for x in pack_list if x]:
            # correct install_time for clients with xml handler but without rpm-python
            if not act_dict.has_key("install_time"):
                self.log("got package_status without install_time from '%s'" % (host_name), logging_tools.LOG_LEVEL_ERROR)
            else:
                if type(act_dict["install_time"]) == type(""):
                    act_dict["install_time"] = int(act_dict["install_time"])
                if act_dict.has_key("extra_error_lines"):
                    extra_lines = [act_dict["error_line_%d" % (idx)] for idx in range(1, act_dict["extra_error_lines"] + 1)]
                else:
                    extra_lines = []
                try:
                    res_field.append(("%(name)s-%(version)s-%(release)s" % (act_dict), act_dict["act_state"], act_dict["install_time"] or 0, act_dict["status"], "\n".join(extra_lines)))
                except:
                    self.log("error adding to res_field: %s" % (process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
        if res_field:
            num_ok = self._process_result_field(res_field, dev_idx, host_name, src_ip, error_dict)
        else:
            num_ok = 0
        error_str = "%s, %s, %d (OK)" % (logging_tools.get_plural("package", len(res_field)), ", ".join(["%d (%s)" % (y, x) for x, y in error_dict.iteritems()]), num_ok)
        # sum errors, but ignore db-errors
        if sum([v for k, v in error_dict.iteritems() if k != "db"]):
            ret_str = "error for package_status: %s" % (error_str)
        else:
            ret_str = "ok for package_status: %s" % (error_str)
        self.node_log(ret_str, host_name)
        del res_field
    def _rsync_object_status(self, (dev_idx, host_name, src_ip, rsync_list)):
        error_dict = {"db" : 0}
        res_field = []
        for act_dict in [x for x in rsync_list if x]:
            # correct install_time for clients with xml handler but without rpm-python
            res_field.append((act_dict["name"], act_dict["act_state"], act_dict["status"]))
        if res_field:
            num_ok = self._process_rso_result_field(res_field, dev_idx, host_name, src_ip, error_dict)
        else:
            num_ok = 0
        error_str = "%s, %s, %d (OK)" % (logging_tools.get_plural("rsync", len(res_field)), ", ".join(["%d (%s)" % (y, x) for x, y in error_dict.iteritems()]), num_ok)
        # sum errors, but ignore db-errors
        if sum([v for k, v in error_dict.iteritems() if k != "db"]):
            ret_str = "error for rsync_object_status: %s" % (error_str)
        else:
            ret_str = "ok for rsync_object_status: %s" % (error_str)
        self.node_log(ret_str, host_name)
        del res_field
    def loop_end(self):
        self.__dc.release()

class watcher_process(threading_tools.process_obj):
    def __init__(self, name, db_con):
        self.__db_con = db_con
        threading_tools.process_obj.__init__(
            self,
            name,
            cb_func=self.call_watcher,
            loop_timer=1000)
        self.__export_dir = global_config["ROOT_EXPORT_DIR"]
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True)
        if inotify_tools.inotify_ok():
            self.log("watching via inotify")
            self.__my_watcher = inotify_tools.inotify_watcher()
            self.__my_watcher.add_watcher(
                "packageserver",
                self.__export_dir,
                inotify_tools.IN_MODIFY | inotify_tools.IN_CLOSE_WRITE | inotify_tools.IN_DELETE,
                self._process_event)
        else:
            self.log("watching via polling-loop", logging_tools.LOG_LEVEL_WARN)
            self.__my_watcher = None
        #self.register_func("update", self._update)
        self.register_func("delete_packages", self._delete_packages)
        self.__package_dict = {}
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def loop_post(self):
        self.__log_template.close()
    def call_watcher(self):
        self.__my_watcher.check(timeout=500)
    def _check(self):
        if self.__my_watcher:
            self.__my_watcher.check(5000)
        else:
            self._check_package_dir()
            time.sleep(self.__glob_config["WATCHER_TIMEOUT"])
    def _delete_packages(self, p_idxs):
        if p_idxs:
            self.log("removing %s from inst_package table" % (logging_tools.get_plural("package", len(p_idxs))))
            dc = self.__db_con.get_connection(SQL_ACCESS)
            dc.execute("SELECT p.name, i.* FROM package p, inst_package i WHERE (%s) AND i.package=p.package_idx" % (" OR ".join(["i.inst_package_idx=%d" % (idx) for idx in p_idxs])))
            del_p_idxs = []
            for db_rec in dc.fetchall():
                file_name = os.path.basename(db_rec["location"])
                full_path = os.path.normpath("%s/%s" % (self.__glob_config["ROOT_EXPORT_DIR"],
                                                        file_name))
                if os.path.isfile(full_path):
                    if self.__glob_config["REALLY_DELETE_PACKAGES"]:
                        self.log("deleting package %s" % (full_path))
                        try:
                            os.unlink(full_path)
                        except:
                            self.log("error deleting %s: %s" % (full_path,
                                                                process_tools.get_except_info()),
                                     logging_tools.LOG_LEVEL_ERROR)
                        else:
                            del_p_idxs.append(db_rec["package"])
                    else:
                        dest_path = "%s/%s/%s" % (self.__glob_config["ROOT_EXPORT_DIR"],
                                                  DEL_PACK_PATH,
                                                  file_name)
                        self.log("moving package %s to %s" % (full_path,
                                                              dest_path))
                        try:
                            os.rename(full_path, dest_path)
                        except:
                            self.log("error moving: %s" % (process_tools.get_except_info()),
                                     logging_tools.LOG_LEVEL_ERROR)
                        else:
                            del_p_idxs.append(db_rec["package"])
                else:
                    self.log("source path %s does not exist ..." % (full_path),
                             logging_tools.LOG_LEVEL_ERROR)
                    del_p_idxs.append(db_rec["package"])
            # remove from db
            dc.execute("DELETE FROM inst_package WHERE %s" % (" OR ".join(["inst_package_idx=%d" % (idx) for idx in p_idxs])))
            if del_p_idxs:
                self.log("deleting %s from package table" % (logging_tools.get_plural("entry", len(del_p_idxs))))
                dc.execute("DELETE FROM package WHERE %s" % (" OR ".join(["package_idx=%d" % (idx) for idx in del_p_idxs])))
            dc.release()
    def _process_event(self, event):
        name, mask = (event.name, event.mask)
        self.log("Got inotify_event for %s (mask %d [%s])" % (name,
                                                              mask,
                                                              inotify_tools.mask_to_str(mask)))
        # check dir
        self._check_package_dir()
    def _check_package_dir(self):
        if os.path.isdir(self.__export_dir):
            dc = None
            # step one: check packages on disk
            s_time = time.time()
            self.log("checking package_dir %s" % (self.__export_dir))
            num_packages, num_checked, num_ignored = (0, 0, 0)
            act_packs_found = []
            for ent in sorted(os.listdir(self.__export_dir)):
                if ent.endswith(".rpm") or ent.endswith(".deb"):
                    num_packages += 1
                    full_name = "%s/%s" % (self.__export_dir, ent)
                    act_packs_found.append(full_name)
                    act_mtime = os.stat(full_name)[stat.ST_MTIME]
                    check_file = True
                    if self.__package_dict.has_key(full_name):
                        if self.__package_dict[full_name] == act_mtime:
                            check_file = False
                    if check_file:
                        num_checked += 1
                        self.__package_dict[full_name] = act_mtime
                        self.log("checking file %s" % (full_name))
                        if not dc:
                            dc = self.__db_con.get_connection(SQL_ACCESS)
                        is_error, error_str, num_p, packages = insert_package_info.check_package(0, "/", full_name, dc)
                        if is_error:
                            self.log("*** %s" % (error_str), logging_tools.LOG_LEVEL_ERROR)
                        else:
                            exp_name = "%%{ROOT_IMPORT_DIR}/%s" % (ent)
                            if packages:
                                pack_struct = packages.values()[0][0]
                                p_idx = pack_struct["package_idx"]
                                pack_name = pack_struct["name"]
                                pack_version = pack_struct["version"]
                                pack_release = pack_struct["release"]
                                dc.execute("SELECT p.*, p.package_idx, ip.inst_package_idx FROM package p, inst_package ip WHERE ip.package=p.package_idx AND p.name=%s AND p.version=%s AND p.release=%s", (pack_name, pack_version, pack_release))
                                if not dc.rowcount:
                                    sql_str, sql_tuple = ("INSERT INTO inst_package SET package=%s, location=%s, native=1, last_build=%s, present_on_disk=1", (p_idx,
                                                                                                                                                               exp_name,
                                                                                                                                                               int(time.time())))
                                    ok = dc.execute(sql_str, sql_tuple)
                                    if ok:
                                        self.log("added package %s (version %s, release %s) to db" % (pack_name,
                                                                                                      pack_version,
                                                                                                      pack_release))
                                    else:
                                        self.log("cannot add packge %s (version %s, release %s) to db" % (pack_name,
                                                                                                          pack_version,
                                                                                                          pack_release), logging_tools.LOG_LEVEL_ERROR)
                            else:
                                self.log("No packages found for %s" % (full_name), logging_tools.LOG_LEVEL_WARN)
                    else:
                        num_ignored += 1
            self.log("checking took %s (%s found, %s checked, %s ignored)" % (logging_tools.get_diff_time_str(time.time() - s_time),
                                                                              logging_tools.get_plural("package", num_packages),
                                                                              logging_tools.get_plural("package", num_checked),
                                                                              logging_tools.get_plural("package", num_ignored)))
            del_packs = [key for key in self.__package_dict.keys() if key not in act_packs_found]
            if del_packs:
                self.log("%s vanished since last check: %s" % (logging_tools.get_plural("package", len(del_packs)),
                                                               ", ".join(sorted(del_packs))),
                         logging_tools.LOG_LEVEL_WARN)
                for del_pack in del_packs:
                    del self.__package_dict[del_pack]
            # step two: compare inst_package table with disk-packages
            if not dc:
                dc = self.__db_con.get_connection(SQL_ACCESS)
            dc.execute("SELECT p.name, i.* FROM package p, inst_package i WHERE i.package=p.package_idx")
            all_packs = dc.fetchall()
            for db_rec in all_packs:
                file_name = os.path.basename(db_rec["location"])
                full_path = os.path.normpath(os.path.join(self.__export_dir,
                                                          file_name))
                if not os.path.isfile(full_path):
                    self.log("package %s (path %s) no longer present on disk" % (db_rec["name"],
                                                                                 full_path),
                             logging_tools.LOG_LEVEL_ERROR)
                    dc.execute("UPDATE inst_package SET present_on_disk=0 WHERE inst_package_idx=%d" % (db_rec["inst_package_idx"]))
                    # check for device relations
                    dc.execute("SELECT * FROM instp_device WHERE inst_package=%d" % (db_rec["inst_package_idx"]))
                    if dc.rowcount:
                        self.log("  package has some device associations left, not removing from db",
                                 logging_tools.LOG_LEVEL_ERROR)
                    else:
                        self.log("  package has no device associations, removing from db",
                                 logging_tools.LOG_LEVEL_WARN)
                        dc.execute("DELETE FROM inst_package WHERE inst_package_idx=%d" % (db_rec["inst_package_idx"]))
                elif not db_rec["present_on_disk"]:
                    dc.execute("UPDATE inst_package SET present_on_disk=1 WHERE inst_package_idx=%d" % (db_rec["inst_package_idx"]))
            if dc:
                dc.release()
        else:
            self.log("package_dir %s not found" % (self.__export_dir), logging_tools.LOG_LEVEL_ERROR)

class node_thread(threading_tools.thread_obj):
    def __init__(self, log_queue, db_con, glob_config, loc_config):
        self.__log_queue = log_queue
        self.__db_con = db_con
        self.__glob_config = glob_config
        self.__loc_config = loc_config
        threading_tools.thread_obj.__init__(self, "node", queue_size=100)
        self.__vers_re = re.compile("^ok version (?P<versionstr>\S+)\s+.*$")
        self.__queue_dict = {}
        self.register_func("node_connection", self._node_connection)
        self.register_func("node_error", self._node_error)
        self.register_func("set_queue", self._set_queue)
        self.register_func("status_result", self._status_result)
        self.__file_idx = 0
    def _set_queue(self, (q_name, q_addr)):
        self.log("Setting queue %s" % (q_name))
        self.__queue_dict[q_name] = q_addr
    def write_file(self, node_name, file_name, what):
        self.__file_idx += 1
        self.__log_queue.put(("write_file", (node_name, "%s%s" % (file_name,
                                                                  self.__glob_config["VERBOSE"] and "_%s_%d" % (time.strftime("%Y%m%d", time.localtime(time.time())), self.__file_idx) or ""),
                                             what)))
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK, node_name=""):
        self.__log_queue.put(("log", (what, lev, self.name, node_name)))
    def node_log(self, what, node_name, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (what, lev, self.name, node_name)))
    def thread_running(self):
        self.send_pool_message(("new_pid", self.pid))
        # init db
        self.__dc = self.__db_con.get_connection(SQL_ACCESS)
        # get global netdevices for this machine
        self._get_glob_net_devices()
        # init xml parser
        self.__my_fast_parser = xml_tools.fast_xml_parser()
        # ip cache
        self.__ip_dict_cache = {}
        # last_received cache
        self.__last_received_cache = {}
        # act_version cache
        self.__act_version_cache = {}
    def _get_cached_ip_dict(self, host_ip):
        was_cached = False
        c_start = time.time()
        if not self.__ip_dict_cache.has_key(host_ip):
            pass
        elif abs(c_start - self.__ip_dict_cache[host_ip]["update_time"]) > self.__glob_config["CACHE_TIMEOUT"]:
            del self.__ip_dict_cache[host_ip]
        if not self.__ip_dict_cache.has_key(host_ip):
            dev_idx, host_name, bz2_flag = (None, None, None)
            sql_str = "SELECT DISTINCT n.netdevice_idx, n.device FROM netip i, netdevice n, hopcount h WHERE i.netdevice=n.netdevice_idx AND n.netdevice_idx=h.s_netdevice AND (%s) AND i.ip='%s' ORDER BY h.value" % (" OR ".join(["h.d_netdevice=%d" % (x) for x in self.__glob_net_devices]), host_ip)
            self.__dc.execute(sql_str)
            if self.__dc.rowcount:
                sql_str = "SELECT DISTINCT d.name, d.device_idx, d.bz2_capable, UNIX_TIMESTAMP(NOW()) AS update_time FROM device d INNER JOIN device_group dg INNER JOIN new_config c " + \
                          "INNER JOIN device_config dc LEFT JOIN device d2 ON d2.device_idx=dg.device WHERE d.device_group=dg.device_group_idx AND (dc.device=d2.device_idx OR dc.device=d.device_idx) AND " + \
                          "dc.new_config=c.new_config_idx AND c.name='package_client' AND d.device_idx=%d" % (self.__dc.fetchone()["device"])
                self.__dc.execute(sql_str)
                c_end = time.time()
                if self.__dc.rowcount:
                    act_dev = self.__dc.fetchone()
                    self.__ip_dict_cache[host_ip] = act_dev
                    dev_idx, host_name, bz2_flag = (act_dev["device_idx"],
                                                    act_dev["name"],
                                                    act_dev["bz2_capable"])
                    if self.__glob_config["SHOW_CACHE_LOG"]:
                        self.log("took %s, IP Info for %15s: devicename %s, device_idx %d, bz2_flag %d, caching for %s" % (logging_tools.get_diff_time_str(c_end - c_start),
                                                                                                                           host_ip,
                                                                                                                           host_name,
                                                                                                                           dev_idx,
                                                                                                                           bz2_flag,
                                                                                                                           logging_tools.get_plural("second", self.__glob_config["CACHE_TIMEOUT"])))
            if not dev_idx:
                c_end = time.time()
                self.log("took %s, unable to get IP Info for %s" % (logging_tools.get_diff_time_str(c_end - c_start), host_ip))
        else:
            was_cached = True
            act_dev = self.__ip_dict_cache[host_ip]
            dev_idx, host_name, bz2_flag = (act_dev["device_idx"],
                                            act_dev["name"],
                                            act_dev["bz2_capable"])
        return dev_idx, host_name, bz2_flag, was_cached
    def _parse_received_command(self, com):
        xml_doc, err_str = (None, "ok")
        if com.startswith("BZh"):
            # try to decompress BZ2-content
            try:
                com_dec = bz2.decompress(com)
            except:
                err_str = "bzip2-error: %s" % (process_tools.get_except_info())
            else:
                com = com_dec
        if com.startswith("<?xml"):
            try:
                xml_doc = self.__my_fast_parser.parse_it(com)
            except xml.parsers.expat.ExpatError:
                err_str = "xlm.parsers.expat.ExpatError: %s" % (process_tools.get_except_info())
                xml_doc = None
            else:
                com = xml_doc.get_command()
        return com, xml_doc, err_str
    def _node_error(self, what):
        self.log("Node error: %s" % (what), logging_tools.LOG_LEVEL_ERROR)
##    def _node_connection(self, (con_obj, src, what)):
##        src_ip, src_port = src
##        dev_idx, host_name, bz2_flag, was_cached = self._get_cached_ip_dict(src_ip)
##        if dev_idx:
##            self._handle_node_request(con_obj, dev_idx, src_ip, host_name, bz2_flag, what)
##        else:
##            ret_str = "error no package client at %s (com '%s' [first 20 bytes])" % (src_ip, what[:20])
##            self.log(ret_str, logging_tools.LOG_LEVEL_ERROR)
##            con_obj.send_return(ret_str)
    def _get_glob_net_devices(self):
        self.__dc.execute("SELECT i.ip, n.netdevice_idx FROM netdevice n, netip i, network nw WHERE n.device=%d AND i.netdevice=n.netdevice_idx AND i.network=nw.network_idx" % (self.__loc_config["SERVER_IDX"]))
        self.__glob_net_devices = {}
        for db_rec in self.__dc.fetchall():
            n_d, n_i = (db_rec["netdevice_idx"], db_rec["ip"])
            self.__glob_net_devices.setdefault(n_d, []).append(n_i)
        if self.__glob_net_devices:
            self.log("Found %s: %s" % (logging_tools.get_plural("global netdevice", len(self.__glob_net_devices.keys())),
                                       ",".join(["%d" % (x) for x in self.__glob_net_devices.keys()])))
        else:
            self.log("found no netdevices, please check config",
                     logging_tools.LOG_LEVEL_ERROR)
    def _mem_info(self):
        #print "%s: %s" % (w, commands.getoutput("ps auxw| grep pack| grep pyth | head -1 | tr -s ' ' | cut -d ' ' -f 5-6"))
        pass
    def _status_result(self, res_dict):
        for h_ip, h_vers_str in res_dict.iteritems():
            vers_m = self.__vers_re.match(h_vers_str)
            if vers_m:
                dev_idx, host_name, bz2_flag, was_cached = self._get_cached_ip_dict(h_ip)
                if dev_idx:
                    self._modify_device_variable(self.__act_version_cache, PACKAGE_VERSION_VAR_NAME, "actual version of the client", host_name, dev_idx, "s", "%s" % (vers_m.group("versionstr")))
    def _handle_node_request(self, con_obj, dev_idx, src_ip, host_name, bz2_flag, com):
        sr_time = time.time()
        start_time = time.time()
        command, xml_in_doc, err_str = self._parse_received_command(com)
        parse_time = time.time()
        # collect all request for package_list
        self.__package_list_requests, self.__rsync_list_requests, self.__com_dict = ({}, {}, {})
        # list of ips we want a status info from
        self.__status_req_ips = []
        # dummy, FIXME
        bp_time = time.time()
        mes_list_len = [1]
        num_cached = 0
        is_error, ret_str = (False, "")
        if err_str != "ok":
            ret_str = "error parsing command: %s" % (err_str)
            self.node_log(ret_str, host_name, logging_tools.LOG_LEVEL_ERROR)
        else:
            self._modify_device_variable(self.__last_received_cache, LAST_CONTACT_VAR_NAME, "last contact of the client", host_name, dev_idx, "d", datetime.datetime(*time.localtime()[0:6]))
            if xml_in_doc:
                r_com = command
            else:
                act_com = command.split()[0]
                ret_str = "error only XML-commands"
                r_com = act_com
            if xml_in_doc:
                self.node_log("got command %s (XML)" % (r_com), host_name)
                is_error, ret_str = self._handle_xml_in_doc(con_obj, dev_idx, src_ip, host_name, bz2_flag, command, xml_in_doc)
            else:
                self.node_log("got command %s (non-XML)" % (r_com), host_name)
            end_time = time.time()
            self.node_log("command %s took %s" % (r_com, logging_tools.get_diff_time_str(end_time - start_time)), host_name)
        if is_error and ret_str:
            self.log(ret_str, logging_tools.LOG_LEVEL_ERROR)
        if ret_str:
            con_obj.send_return(ret_str)
        if self.__status_req_ips:
            self.__queue_dict["command"].put(("srv_command", server_command.server_command(command="status", nodes=self.__status_req_ips, queue=self.get_thread_queue())))
        if self.__package_list_requests:
            self._handle_package_list_requests()
        if self.__rsync_list_requests:
            self._handle_rsync_list_requests()
        self.log("Processing of %s took %s (receiving %s, %s, %s)" % (logging_tools.get_plural("message", mes_list_len),
                                                                      logging_tools.get_diff_time_str(time.time() - bp_time),
                                                                      logging_tools.get_diff_time_str(bp_time - sr_time),
                                                                      "%d chached" % (num_cached),
                                                                      ", ".join(["%s: %d" % (k, v) for k, v in self.__com_dict.iteritems()])))
    def _handle_rsync_list_requests(self):
        for rs_val in self.__rsync_list_requests.values():
            rs_val["ret_com"].set_command("rsync_list")
            rs_val["rlist"] = rs_val["ret_com"].add_entity(xml_tools.xml_entity("rsyncs"))
            rs_val["ret_com"].add_flag("bz2compression", rs_val["flag_dict"].get("bz2compression", False))
        # get devices and rsync_device structs
        sql_str = "SELECT rc.device, rc.new_config, nc.name FROM device_rsync_config rc, new_config nc WHERE rc.new_config=nc.new_config_idx AND nc.name LIKE('%%rsync%%') AND (%s)" % (" OR ".join(["rc.device=%d" % (x) for x in self.__rsync_list_requests.keys()]))
        self.__dc.execute(sql_str)
        # dict new_config_idx -> stuff
        rsync_objects = {}
        for db_rec in self.__dc.fetchall():
            if not rsync_objects.has_key(db_rec["new_config"]):
                rsync_objects[db_rec["new_config"]] = {"name"        : db_rec["name"],
                                                       "vars"        : {},
                                                       "devices"     : [],
                                                       "server_name" : ""}
            rsync_objects[db_rec["new_config"]]["devices"].append(db_rec["device"])
        # fetch vars
        if rsync_objects:
            self.__dc.execute("SELECT cs.name, cs.value, cs.new_config FROM config_str cs WHERE (%s)" % (" OR ".join(["cs.new_config=%d" % (x) for x in rsync_objects.keys()])))
            for db_rec in self.__dc.fetchall():
                rsync_objects[db_rec["new_config"]]["vars"][db_rec["name"]] = db_rec["value"]
            # fetch servers
            self.__dc.execute("SELECT d.name, d.device_idx, c.new_config_idx FROM device d, device_config dc, new_config c WHERE dc.device=d.device_idx AND dc.new_config=c.new_config_idx AND (%s)" % (" OR ".join(["c.new_config_idx=%d" % (x) for x in rsync_objects.keys()])))
            for db_rec in self.__dc.fetchall():
                #if rsync_objects.has_key[x["new_config_idx"]]:
                #    if x["device_idx"]
                if db_rec["device_idx"] == self.__loc_config["SERVER_IDX"] and not rsync_objects[db_rec["new_config_idx"]]["server_name"]:
                    rsync_objects[db_rec["new_config_idx"]]["server_name"] = db_rec["name"]
        self.log("found %s: %s" % (logging_tools.get_plural("rsync_object", len(rsync_objects.keys())),
                                   ", ".join([v["name"] for v in rsync_objects.values()])))
        # check for invalid ones
        needed_keys = ["export_rsync", "import_rsync", "rsync_name"]
        invalid_keys = []
        for rso_idx, rso_stuff in rsync_objects.iteritems():
            if len(needed_keys) != len([True for x in needed_keys if rso_stuff["vars"].has_key(x)]):
                invalid_keys.append(rso_idx)
            elif not rso_stuff["server_name"]:
                invalid_keys.append(rso_idx)
        if invalid_keys:
            self.log("removing %s: %s" % (logging_tools.get_plural("rsync_object", len(invalid_keys)),
                                          ", ".join([v["name"] for v in rsync_objects.values()])), logging_tools.LOG_LEVEL_WARN)
            for inv_key in invalid_keys:
                del rsync_objects[inv_key]
        for rso_object in rsync_objects.itervalues():
            for dev_idx in rso_object["devices"]:
                act_r = self.__rsync_list_requests[dev_idx]["rlist"].add_entity(xml_tools.xml_entity("rsync"))
                act_r.add_entity(xml_tools.xml_entity_var("name", rso_object["vars"]["rsync_name"]))
                act_r.add_entity(xml_tools.xml_entity_var("source_server", rso_object["server_name"]))
                act_r.add_entity(xml_tools.xml_entity_var("target_dir", rso_object["vars"]["import_rsync"]))
        for rs_val in self.__rsync_list_requests.values():
            xml_info_str = logging_tools.get_plural("rsync", rs_val["num_r"])
            self.write_file(rs_val["host_name"], "%s_answer.xml" % ("get_rsync_list"), str(rs_val["ret_com"]))
            ret_str = rs_val["ret_com"].toxml()
            compress_return = rs_val["flag_dict"].get("bz2compression", False)
            if compress_return:
                ret_str = bz2.compress(ret_str)
            self.node_log("returning xml-struct (compression %s, %s), %s" % (compress_return and "enabled" or "disabled",
                                                                             logging_tools.get_plural("byte", len(ret_str)),
                                                                             xml_info_str),
                          rs_val["host_name"])
            rs_val["con_obj"].send_return(ret_str)
        self.__package_list_requests = {}
    def _expand_location(self, location):
        return location.replace("%{ROOT_IMPORT_DIR}", self.__glob_config["ROOT_IMPORT_DIR"])
    def _handle_package_list_requests(self):
        for pack_req in self.__package_list_requests.values():
            pack_req["ret_com"].set_command("package_list")
            pack_req["plist"] = pack_req["ret_com"].add_entity(xml_tools.xml_entity("packages"))
            pack_req["ret_com"].add_flag("bz2compression", pack_req["flag_dict"].get("bz2compression", False))
        self.__dc.execute("SELECT p.version, p.release, p.name, ip.location, ipd.install, ipd.upgrade, ipd.del, ipd.nodeps, ip.native, ipd.forceflag, ipd.device FROM package p, inst_package ip, instp_device ipd WHERE " + \
                          "ip.package=p.package_idx AND ipd.inst_package=ip.inst_package_idx AND (%s) ORDER BY p.name, p.version, p.release" % (" OR ".join(["ipd.device=%d" % (x) for x in self.__package_list_requests.keys()])))
        for db_rec in self.__dc.fetchall():
            act_p = self.__package_list_requests[db_rec["device"]]["plist"].add_entity(xml_tools.xml_entity("package"))
            self.__package_list_requests[db_rec["device"]]["num_p"] += 1
            if db_rec["install"]:
                db_rec["command"] = "install"
            elif db_rec["upgrade"]:
                db_rec["command"] = "upgrade"
            elif db_rec["del"]:
                db_rec["command"] = "delete"
            else:
                db_rec["command"] = "keep"
            for db_name, xml_name, xml_type in [("name"     , "name"    , "s"),
                                                ("version"  , "version" , "s"),
                                                ("release"  , "release" , "s"),
                                                ("command"  , "command" , "s"),
                                                ("location" , "location", "s"),
                                                ("nodeps"   , "nodeps"  , "b"),
                                                ("native"   , "native"  , "b"),
                                                ("forceflag", "force"   , "b")]:
                if xml_type == "s":
                    if db_name == "location":
                        act_p.add_entity(xml_tools.xml_entity_var(xml_name, self._expand_location(db_rec[db_name])))
                    else:
                        act_p.add_entity(xml_tools.xml_entity_var(xml_name, db_rec[db_name]))
                elif xml_type == "b":
                    act_p.add_entity(xml_tools.xml_entity_var(xml_name, db_rec[db_name] and True or False))
        for pack_val in self.__package_list_requests.values():
            xml_info_str = logging_tools.get_plural("package", pack_val["num_p"])
            self.write_file(pack_val["host_name"], "%s_answer.xml" % ("get_package_list"), str(pack_val["ret_com"]))
            ret_str = pack_val["ret_com"].toxml()
            compress_return = pack_val["flag_dict"].get("bz2compression", False)
            if compress_return:
                ret_str = bz2.compress(ret_str)
            self.node_log("returning xml-struct (compression %s, %s), %s" % (compress_return and "enabled" or "disabled",
                                                                             logging_tools.get_plural("byte", len(ret_str)),
                                                                             xml_info_str),
                          pack_val["host_name"])
            pack_val["con_obj"].send_return(ret_str)
        self.__package_list_requests = {}
    def _handle_xml_in_doc(self, con_obj, dev_idx, src_ip, host_name, bz2_flag, command, xml_in_doc):
        is_error = False
        self.write_file(host_name, "%s_request.xml" % (command), str(xml_in_doc))
        self.__com_dict.setdefault(command, 0)
        self.__com_dict[command] += 1
        flag_dict = xml_in_doc.get_flag_dict()
        if flag_dict.has_key("version"):
            self._modify_device_variable(self.__act_version_cache, PACKAGE_VERSION_VAR_NAME, "actual version of the client", host_name, dev_idx, "s", "%s" % (flag_dict["version"]))
        else:
            if src_ip not in self.__status_req_ips:
                self.__status_req_ips.append(src_ip)
        if flag_dict.has_key("rpm_direct"):
            self._modify_device_variable(self.__act_version_cache, DIRECT_MODE_VAR_NAME, "direct access to the rpm-database", host_name, dev_idx, "b", "%d" % (flag_dict["rpm_direct"] and 1 or 0))

        # parse xml-requests
        if command == "get_package_list":
            self.__package_list_requests[dev_idx] = {"con_obj"   : con_obj,
                                                     "host_name" : host_name,
                                                     "flag_dict" : flag_dict,
                                                     "num_p"     : 0,
                                                     "ret_com"   : xml_tools.xml_entity("content", top_node=1)}
            xml_info_str = None
        elif command == "get_rsync_list":
            self.__rsync_list_requests[dev_idx] = {"con_obj"   : con_obj,
                                                   "host_name" : host_name,
                                                   "flag_dict" : flag_dict,
                                                   "num_r"     : 0,
                                                   "ret_com"   : xml_tools.xml_entity("content", top_node=1)}
            xml_info_str = None
        elif command == "package_info":
            ret_com = xml_tools.xml_entity("content", top_node=1)
            ret_com.set_command("package_info_ok")
            ret_com.add_flag("bz2compression", flag_dict.get("bz2compression", False))
            self.node_log("sending to package_status thread", host_name)
            package_list = xml_in_doc["packages"][0]
            if package_list.has_sub_entity("package"):
                #print "***", host_name, len(package_list["package"])
                self.__queue_dict["package_status"].put(("package_status", (dev_idx, host_name, src_ip, [xml_tools.build_var_dict_fast(x.get_entity_list()) for x in package_list["package"]])))
            else:
                self.node_log("got empty package-list", logging_tools.LOG_LEVEL_WARN)
            xml_info_str = "no info"
        elif command == "rsync_object_info":
            ret_com = xml_tools.xml_entity("content", top_node=1)
            ret_com.set_command("rsync_object_info_ok")
            ret_com.add_flag("bz2compression", flag_dict.get("bz2compression", False))
            self.node_log("sending to package_status thread", host_name)
            rsync_list = xml_in_doc["packages"][0]
            if rsync_list.has_sub_entity("package"):
                self.__queue_dict["package_status"].put(("rsync_object_status", (dev_idx, host_name, src_ip, [xml_tools.build_var_dict_fast(x.get_entity_list()) for x in rsync_list["package"]])))
            else:
                self.node_log("got empty rsync-list", logging_tools.LOG_LEVEL_WARN)
            xml_info_str = "no info"
        else:
            ret_com = xml_tools.xml_entity("content", top_node=1)
            self.node_log("unknown command %s" % (command), host_name, logging_tools.LOG_LEVEL_WARN)
            is_error = True
            ret_com.add_flag("error", True)
            xml_info_str = "unknown command %s" % (command)
        if xml_info_str:
            self.write_file(host_name, "%s_answer.xml" % (command), str(ret_com))
            ret_str = ret_com.toxml()
            compress_return = not is_error and flag_dict.get("bz2compression", False)
            if compress_return:
                ret_str = bz2.compress(ret_str)
            self.node_log("returning xml-struct (%s, compression %s, %s), %s" % (is_error and "error" or "no error",
                                                                                 compress_return and "enabled" or "disabled",
                                                                                 logging_tools.get_plural("byte", len(ret_str)),
                                                                                 xml_info_str), host_name)
        else:
            ret_str = ""
        return is_error, ret_str
    def loop_end(self):
        self.__dc.release()

class client(object):
    all_clients = {}
    def __init__(self, c_uid, name):
        self.uid = c_uid
        self.name = name
        self.__version = ""
        self.__dev_idx = 0
        self.__log_template = None
    def create_logger(self):
        if self.__log_template is None:
            self.__log_template = logging_tools.get_logger(
                "%s.%s" % (global_config["LOG_NAME"],
                           self.name.replace(".", r"\.")),
                global_config["LOG_DESTINATION"],
                zmq=True,
                context=client.srv_process.zmq_context,
                init_logger=True)
            self.log("added client")
    @staticmethod
    def init(srv_process):
        client.srv_process = srv_process
        client.uid_set = set()
        client.name_set = set()
        client.lut = {}
        if not os.path.exists(CONFIG_NAME):
            file(CONFIG_NAME, "w").write(etree.tostring(E.package_clients(), pretty_print=True))
        client.xml = etree.fromstring(file(CONFIG_NAME, "r").read())
        for client_el in client.xml.xpath(".//package_client"):
            client.register(client_el.text, client_el.attrib["name"])
    @staticmethod
    def get(key):
        return client.lut[key]
    @staticmethod
    def register(uid, name):
        if uid not in client.uid_set:
            client.uid_set.add(uid)
            client.name_set.add(name)
            new_client = client(uid, name)
            client.lut[uid] = new_client
            client.lut[name] = new_client
            client.srv_process.log("added client %s (%s)" % (name, uid))
            cur_el = client.xml.xpath(".//package_client[@name='%s']" % (name))
            if not cur_el:
                client.xml.append(E.package_client(uid, name=name))
                file(CONFIG_NAME, "w").write(etree.tostring(client.xml, pretty_print=True))
    def close(self):
        if self.__log_template is not None:
            self.__log_template.close()
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.create_logger()
        self.__log_template.log(level, what)
    def send_reply(self, srv_com):
        self.srv_process.send_reply(self.uid, srv_com)
    def __unicode__(self):
        return u"%s (%s)" % (self.name,
                             self.uid)
    #def _modify_device_variable(self, c_dict, var_name, var_descr, h_name, dev_idx, var_type, var_value):
    def _get_dev_idx(self, dc):
        if not self.__dev_idx:
            dc.execute("SELECT d.device_idx FROM device d WHERE d.name=%s", (self.name))
            if dc.rowcount == 1:
                self.__dev_idx = dc.fetchone()["device_idx"]
                self.log("set device_idx to %d" % (self.__dev_idx))
            else:
                self.log("cannot determine device_idx", logging_tools.LOG_LEVEL_ERROR)
        return self.__dev_idx
    def _modify_device_variable(self, var_name, var_descr, var_type, var_value):
        var_type_name = "val_%s" % ({"s" : "str" ,
                                     "i" : "int" ,
                                     "b" : "blob",
                                     "t" : "time",
                                     "d" : "date"}[var_type])
        dc = client.srv_process.get_dc()
        if self._get_dev_idx(dc):
            dc.execute("SELECT dv.device_variable_idx, dv.%s FROM device_variable dv WHERE dv.device=%%s AND dv.name=%%s" % (var_type_name),
                       (self.__dev_idx,
                        var_name))
            if dc.rowcount:
                line = dc.fetchone()
                c_dict = {"idx"   : line["device_variable_idx"],
                          "value" : line[var_type_name]}
                self.log("Found device_variable named '%s' (idx %d)" % (var_name, c_dict["idx"]))
            else:
                dc.execute("INSERT INTO device_variable SET device=%s, name=%s, description=%s, var_type=%s", (
                    self.__dev_idx,
                    var_name,
                    var_descr,
                    var_type))
                c_dict = {"idx"   : dc.insert_id(),
                          "value" : None}
                self.log("Creating device_variable named '%s' (idx %d)" % (var_name, c_dict["idx"]))
            if c_dict["value"] != var_value:
                dc.execute("UPDATE device_variable SET %s=%%s, description=%%s WHERE device_variable_idx=%%s" % (var_type_name), (
                    var_value,
                    var_descr,
                    c_dict["idx"]))
                c_dict["value"] = var_value
                if not dc.rowcount:
                    self.log("UPDATE resulted in no rowchange, checking for device_variable '%s' ..." % (var_name))
                    dc.execute("SELECT dv.device_variable_idx FROM device_variable dv WHERE dv.device=%s AND dv.name=%s", (
                        dev_idx,
                        var_name))
                    if not dc.rowcount:
                        dc.execute("INSERT INTO device_variable SET device=%s, name=%s, description=%s, var_type=%s", (
                            dev_idx,
                            var_name,
                            var_descr,
                            var_type))
                        c_dict = {"idx"   : dc.insert_id(),
                                  "value" : None}
                        self.log("Creating device_variable named '%s' (idx %d)" % (var_name, c_dict["idx"]))
                    dc.execute("UPDATE device_variable SET %s=%%s WHERE device_variable_idx=%%s" % (var_type_name), (
                        var_value,
                        c_dict["idx"]))
                    c_dict["value"] = var_value
        dc.release()
    def _set_version(self, new_vers):
        if new_vers != self.__version:
            self.log("changed version from '%s' to '%s'" % (self.__version,
                                                            new_vers))
            self.__version = new_vers
            self._modify_device_variable(
                PACKAGE_VERSION_VAR_NAME,
                "actual version of the client",
                "s",
                self.__version)
    def _expand_var(self, var):
        return var.replace("%{ROOT_IMPORT_DIR}", global_config["ROOT_IMPORT_DIR"])
    def _get_package_list(self, srv_com):
        dc = client.srv_process.get_dc()
        if self._get_dev_idx(dc):
            dc.execute("SELECT p.version, p.release, p.name, ip.location, ipd.install, ipd.upgrade, ipd.del, ipd.nodeps, ip.native, ipd.forceflag, ipd.device, ipd.instp_device_idx FROM package p, inst_package ip, instp_device ipd WHERE " + \
                       "ip.package=p.package_idx AND ipd.inst_package=ip.inst_package_idx AND (%s) ORDER BY p.name, p.version, p.release" % (" OR ".join(["ipd.device=%d" % (cur_idx) for cur_idx in [self.__dev_idx]])))
            pack_list = srv_com.builder("packages")
            srv_com["result"] = pack_list
            for db_rec in dc.fetchall():
                new_p = srv_com.builder("package")
                if db_rec["install"]:
                    new_p.attrib["command"] = "install"
                elif db_rec["upgrade"]:
                    new_p.attrib["command"] = "upgrade"
                elif db_rec["del"]:
                    new_p.attrib["command"] = "delete"
                else:
                    new_p.attrib["command"] = "keep"
                new_p.attrib.update({
                    "instp_idx" : "%d" % (db_rec["instp_device_idx"]),
                    "nodeps" : "1" if db_rec["nodeps"] else "0",
                    "force"  : "1" if db_rec["forceflag"] else "0",
                    "native" : "1" if db_rec["native"] else "0"})
                for db_name, xml_name, xml_type in [("name"     , "name"    , "s"),
                                                    ("version"  , "version" , "s"),
                                                    ("release"  , "release" , "s"),
                                                    ("location" , "location", "s")]:
                    new_p.append(srv_com.builder(xml_name, self._expand_var(db_rec[db_name])))
                pack_list.append(new_p)
            self.log("package_list has %s" % (logging_tools.get_plural("entry", len(pack_list))))
        dc.release()
    def _get_package_info(self, srv_com):
        dc = client.srv_process.get_dc()
        if self._get_dev_idx(dc):
            p_el = srv_com["package_info:package"]
            instp_idx = int(p_el.attrib["instp_idx"])
            # get record
            dc.execute("SELECT * FROM instp_device WHERE instp_device_idx=%d" % (instp_idx))
            if dc.rowcount:
                db_rec = dc.fetchone()
                if "pending" in p_el.attrib:
                    res_str = "w waiting for action"
                else:
                    res_level = int(p_el.attrib["result_level"])
                    prefix = {logging_tools.LOG_LEVEL_OK : "ok",
                              logging_tools.LOG_LEVEL_WARN : "w",
                              logging_tools.LOG_LEVEL_ERROR : "error"}[res_level]
                    res_str = "%s %s" % (prefix, p_el.attrib["result_str"])
                #print p_el.attrib
                dc.execute("UPDATE instp_device SET status=%%s WHERE instp_device_idx=%d" % (instp_idx),
                           (res_str))
                if "install_time" in p_el.attrib:
                    dc.execute("UPDATE instp_device SET install_time=FROM_UNIXTIME(%s) WHERE instp_device_idx=%d" % (
                        p_el.attrib["install_time"],
                        instp_idx))
                elif p_el.attrib["command"] == "delete" and p_el.attrib["result_ok"] == "1":
                    # delete install time
                    dc.execute("UPDATE instp_device SET install_time=Null WHERE instp_device_idx=%d" % (
                        instp_idx))
                self.log("set status of %s to %s" % (p_el.xpath("ns:name/text()", namespaces={"ns" : server_command.XML_NS})[0],
                                                     res_str))
            else:
                self.log("no instp_device structure found with idx=%d" % (instp_idx),
                         logging_tools.LOG_LEVEL_ERROR)
        dc.release()
    def new_command(self, srv_com):
        s_time = time.time()
        cur_com = srv_com["command"].text
        if "package_client_version" in srv_com:
            self._set_version(srv_com["package_client_version"].text)
        self._modify_device_variable(LAST_CONTACT_VAR_NAME, "last contact of the client", "d", datetime.datetime(*time.localtime()[0:6]))
        srv_com.update_source()
        send_reply = False
        if cur_com == "get_package_list":
            srv_com["command"] = "package_list"
            self._get_package_list(srv_com)
            send_reply = True
        elif cur_com == "package_info":
            self._get_package_info(srv_com)
        else:
            self.log("unknown command '%s'" % (cur_com),
                     logging_tools.LOG_LEVEL_ERROR)
        if send_reply:
            self.send_reply(srv_com)
        e_time = time.time()
        self.log("handled command %s in %s" % (cur_com,
                                               logging_tools.get_diff_time_str(e_time - s_time)))

class server_process(threading_tools.process_pool):
    def __init__(self, db_con):
        self.__log_cache, self.__log_template = ([], None)
        self.__db_con = db_con
        self.__pid_name = global_config["PID_NAME"]
        self.__queue_file_name = "%s/.queue_signal" % (global_config["ROOT_EXPORT_DIR"])
        threading_tools.process_pool.__init__(self, "main", zmq=True)
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self._log_config()
        self.__msi_block = self._init_msi_block()
        self._init_clients()
        self._init_network_sockets()
        self._check_database()
        self.add_process(watcher_process("watcher", self.__db_con), start=True)
        #self.register_timer(self._send_update, global_config["RENOTIFY_CLIENTS_TIMEOUT"], instant=True)
        self.register_timer(self._send_update, 3600, instant=True)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            while self.__log_cache:
                self.__log_template.log(*self.__log_cache.pop(0))
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))
    def _init_clients(self):
        client.init(self)
    def _register_client(self, c_uid, srv_com):
        client.register(c_uid, srv_com["source"].attrib["host"])
    def get_dc(self):
        return self.__db_con.get_connection(SQL_ACCESS)
    def _init_msi_block(self):
        process_tools.save_pid(self.__pid_name, mult=3)
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=3)
        if not global_config["DEBUG"] or True:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("package-server")
            msi_block.add_actual_pid(mult=3)
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=3)
            msi_block.start_command = "/etc/init.d/package-server start"
            msi_block.stop_command = "/etc/init.d/package-server force-stop"
            msi_block.kill_pids = True
            msi_block.save_block()
        else:
            msi_block = None
        return msi_block
    def _log_config(self):
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found %d valid config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True
            # signal via file-creating
            try:
                file(self.__queue_file_name, "w").write("-")
            except:
                self.log("cannot create file in %s: %s" % (self.__queue_file_name,
                                                           process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
    def process_start(self, src_process, src_pid):
        # twisted needs 4 threads if connecting to TCP clients, 3 if not (???)
        mult = 3
        process_tools.append_pids(self.__pid_name, src_pid, mult=mult)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(src_pid, mult=mult)
            self.__msi_block.save_block()
    def loop_end(self):
        for c_name in client.name_set:
            client.get(c_name).close()
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
    def loop_post(self):
        for open_sock in self.socket_dict.itervalues():
            open_sock.close()
        self.__log_template.close()
    def _check_database(self):
        dc = self.__db_con.get_connection(SQL_ACCESS)
        # rewrite inst_package for expansion variable
        dc.execute("SELECT ip.inst_package_idx, ip.location FROM inst_package ip ORDER BY ip.location")
        all_recs = dc.fetchall()
        modified = 0
        for db_rec in all_recs:
            if db_rec["location"].startswith(global_config["ROOT_IMPORT_DIR"]):
                modified += 1
                dc.execute("UPDATE inst_package SET location=%s WHERE inst_package_idx=%s", (db_rec["location"].replace(global_config["ROOT_IMPORT_DIR"], "%{ROOT_IMPORT_DIR}"),
                                                                                             db_rec["inst_package_idx"]))
        self.log("modified %s in database" % (logging_tools.get_plural("package", modified)))
        dc.release()
    def _new_com(self, zmq_sock):
        data = [zmq_sock.recv_unicode()]
        while zmq_sock.getsockopt(zmq.RCVMORE):
            data.append(zmq_sock.recv_unicode())
        if len(data) == 2:
            c_uid, srv_com = (data[0], server_command.srv_command(source=data[1]))
            cur_com = srv_com["command"].text
            if cur_com == "register":
                self._register_client(c_uid, srv_com)
            else:
                if c_uid.endswith("webfrontend"):
                    self._handle_wfe_command(zmq_sock, c_uid, srv_com)
                else:
                    try:
                        cur_client = client.get(c_uid)
                    except KeyError:
                        self.log("unknown uid %s, not known" % (c_uid),
                                 logging_tools.LOG_LEVEL_CRITICAL)
                    else:
                        cur_client.new_command(srv_com)
        else:
            self.log("wrong number of data chunks (%d != 2)" % (len(data)),
                     logging_tools.LOG_LEVEL_ERROR)
    def _handle_wfe_command(self, zmq_sock, in_uid, srv_com):
        in_com = srv_com["command"].text
        self.log("got server_command %s from %s" % (in_com,
                                                    in_uid))
        srv_com.update_source()
        srv_com["result"] = None
        srv_com["result"].attrib.update({
            "reply" : "result not set",
            "state" : "%d" % (server_command.SRV_REPLY_STATE_UNSET)})
        if in_com == "new_config":
            all_devs = srv_com.xpath(None, ".//ns:device_command/@name")
            valid_devs = [name for name in all_devs if name in client.name_set]
            self.log("%s requested, %s found" % (logging_tools.get_plural("device", len(all_devs)),
                                                 logging_tools.get_plural("device" ,len(valid_devs))))
            for cur_dev in all_devs:
                srv_com.xpath(None, ".//ns:device_command[@name='%s']" % (cur_dev))[0].attrib["config_sent"] = "1" if cur_dev in valid_devs else "0"
            if valid_devs:
                self._send_update(command="new_config", dev_list=valid_devs)
            srv_com["result"].attrib.update({"reply" : "send update to %d of %d %s" % (len(valid_devs),
                                                                                       len(all_devs),
                                                                                       logging_tools.get_plural("device", len(all_devs))),
                                             "state" : "%d" % (server_command.SRV_REPLY_STATE_OK if len(valid_devs) == len(all_devs) else server_command.SRV_REPLY_STATE_WARN)})
        else:
            srv_com["result"].attrib.update({"reply" : "command %s not known" % (in_com),
                                             "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
        #print srv_com.pretty_print()
        zmq_sock.send_unicode(unicode(in_uid), zmq.SNDMORE)
        zmq_sock.send_unicode(unicode(srv_com))
    def _init_network_sockets(self):
        my_0mq_id = uuid_tools.get_uuid().get_urn()
        self.socket_dict = {}
        # get all ipv4 interfaces with their ip addresses, dict: interfacename -> IPv4
        for key, sock_type, bind_port, target_func in [
            ("router", zmq.ROUTER, global_config["SERVER_PUB_PORT"] , self._new_com),
            ("pull"  , zmq.PULL  , global_config["SERVER_PULL_PORT"], self._new_com),
            ]:
            client = self.zmq_context.socket(sock_type)
            client.setsockopt(zmq.IDENTITY, my_0mq_id)
            client.setsockopt(zmq.LINGER, 100)
            client.setsockopt(zmq.HWM, 256)
            client.setsockopt(zmq.BACKLOG, 1)
            conn_str = "tcp://*:%d" % (bind_port)
            try:
                client.bind(conn_str)
            except zmq.core.error.ZMQError:
                self.log("error binding to %s{%d}: %s" % (
                    conn_str,
                    sock_type, 
                    process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_CRITICAL)
                client.close()
            else:
                self.log("bind to port %s{%d}" % (conn_str,
                                                  sock_type))
                self.register_poller(client, zmq.POLLIN, target_func)
                self.socket_dict[key] = client
    def send_reply(self, t_uid, srv_com):
        send_sock = self.socket_dict["router"]
        send_sock.send_unicode(t_uid, zmq.SNDMORE|zmq.NOBLOCK)
        send_sock.send_unicode(unicode(srv_com), zmq.NOBLOCK)
    def _send_update(self, command="send_info", dev_list=[]):
        send_list = dev_list or client.name_set
        self.log("send command %s to %s" % (command,
                                            logging_tools.get_plural("client", len(send_list))))
        send_com = server_command.srv_command(command=command)
        for target_name in send_list:
            self.send_reply(client.get(target_name).uid, send_com)

class server_thread_pool(threading_tools.thread_pool):
    def __init__(self, n_retry, log_lines, daemon, db_con, glob_config, loc_config):
        # msi_block
        # log thread
        self.__log_queue = self.add_thread(logging_thread(self.__glob_config), start_thread=True).get_thread_queue()
        for what, lev in log_lines:
            self.log(what, lev)
        self._check_database(db_con)
        self.__ns = net_tools.network_server(timeout=1, log_hook=self.log, poll_verbose=False)
        self.__bind_states = {}
        self.__ns.add_object(net_tools.tcp_bind(self._new_command_con, port=self.__glob_config["COMMAND_PORT"], bind_retries=n_retry, bind_state_call=self._bind_state_call, timeout=60))
        self.__ns.add_object(net_tools.tcp_bind(self._new_node_con, port=self.__glob_config["NODE_PORT"], bind_retries=n_retry, bind_state_call=self._bind_state_call, timeout=60))
        self.__command_queue = self.add_thread(command_thread(self.__log_queue, db_con, self.__glob_config), start_thread=True).get_thread_queue()
        self.__package_status_queue = self.add_thread(package_status_thread(self.__log_queue, db_con, self.__glob_config), start_thread=True).get_thread_queue()
        self.__node_queue = self.add_thread(node_thread(self.__log_queue, db_con, self.__glob_config, self.__loc_config), start_thread=True).get_thread_queue()
        self.__watcher_queue = self.add_thread(watcher_thread(self.__log_queue, db_con, self.__glob_config), start_thread=True).get_thread_queue()
        self.__package_status_queue.put(("set_queue", ("node", self.__node_queue)))
        self.__node_queue.put(("set_queue", ("package_status", self.__package_status_queue)))
        self.__node_queue.put(("set_queue", ("command", self.__command_queue)))
        self.__command_queue.put(("set_queue", ("watcher", self.__watcher_queue)))
        self.__command_queue.put(("set_net_server", self.__ns))
    def loop_function(self):
        if not self["exit_requested"]:
            self.__command_queue.put("update")
            if self.__watcher_queue:
                self.__watcher_queue.put("update")
        self.__ns.step()
        self.log(", ".join(["%s: %d of %d used" % (name, act_used, max_size) for name, (max_size, act_used) in self.get_thread_queue_info().iteritems()]))
##    def _new_node_con(self, sock, src):
##        return connection_from_node(sock, src, self.__node_queue)
##    def _new_command_con(self, sock, src):
##        return connection_for_command(sock, src, self.__command_queue)

global_config = configfile.get_global_config(process_tools.get_programm_name())

def main():
    long_host_name, mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries([
        ("DEBUG"                    , configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("PID_NAME"                 , configfile.str_c_var(os.path.join(prog_name, prog_name))),
        ("KILL_RUNNING"             , configfile.bool_c_var(True, help_string="kill running instances [%(default)s]")),
        ("CHECK"                    , configfile.bool_c_var(False, short_options="C", help_string="only check for server status", action="store_true", only_commandline=True)),
        ("USER"                     , configfile.str_c_var("idpacks", help_string="user to run as [%(default)s")),
        ("GROUP"                    , configfile.str_c_var("idg", help_string="group to run as [%(default)s]")),
        ("GROUPS"                   , configfile.array_c_var(["idg"])),
        ("FORCE"                    , configfile.bool_c_var(False, help_string="force running ", action="store_true", only_commandline=True)),
        ("LOG_DESTINATION"          , configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME"                 , configfile.str_c_var(prog_name)),
        ("VERBOSE"                  , configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ("SERVER_PUB_PORT"          , configfile.int_c_var(P_SERVER_PUB_PORT, help_string="server publish port [%(default)d]")),
        ("SERVER_PULL_PORT"         , configfile.int_c_var(P_SERVER_PULL_PORT, help_string="server pull port [%(default)d]")),
        ("NODE_PORT"                , configfile.int_c_var(PACKAGE_CLIENT_PORT, help_string="port where the package-clients are listengin [%(default)d]")),
        ("ROOT_EXPORT_DIR"          , configfile.str_c_var("/usr/local/share/cluster/packages/RPMs")),
        ("ROOT_IMPORT_DIR"          , configfile.str_c_var("/packages/RPMs")),
        ("CACHE_TIMEOUT"            , configfile.int_c_var(15 * 60)),
        ("RENOTIFY_CLIENTS_TIMEOUT" , configfile.int_c_var(60 * 60 * 24)),
        ("SHOW_CACHE_LOG"           , configfile.int_c_var(0)),
        ("MAX_BLOCK_SIZE"           , configfile.int_c_var(50)),
        ("WATCHER_TIMEOUT"          , configfile.int_c_var(120)),
        ("REALLY_DELETE_PACKAGES"   , configfile.bool_c_var(False))
    ])
    global_config.parse_file()
    options = global_config.handle_commandline(description="%s, version is %s" % (prog_name,
                                                                                  VERSION_STRING),
                                               add_writeback_option=True,
                                               positional_arguments=False)
    global_config.write_file()
    db_con = mysql_tools.dbcon_container()
    try:
        dc = db_con.get_connection(SQL_ACCESS)
    except MySQLdb.OperationalError:
        sys.stderr.write(" Cannot connect to SQL-Server ")
        sys.exit(1)
    sql_info = config_tools.server_check(dc=dc, server_type="package_server")
    global_config.add_config_entries([("SERVER_IDX", configfile.int_c_var(sql_info.server_device_idx))])
    if sql_info.num_servers == 0 and not global_config["FORCE"]:
        sys.stderr.write(" Host %s is no package-server" % (long_host_name))
        sys.exit(5)
    if global_config["CHECK"]:
        sys.exit(0)
    if sql_info.num_servers > 1 and not global_config["FORCE"]:
        print "Database error for host %s (package_server): too many entries found (%d)" % (long_host_name, sql_info.num_servers)
        dc.release()
    else:
        if global_config["KILL_RUNNING"]:
            log_lines = process_tools.kill_running_processes(prog_name + ".py", exclude=configfile.get_manager_pid())
        log_source_idx = process_tools.create_log_source_entry(dc, sql_info.server_device_idx, "package_server", "Package Server")
        dir_list = [
            "%s" % (global_config["ROOT_EXPORT_DIR"]),
            "%s/%s" % (global_config["ROOT_EXPORT_DIR"], ADD_PACK_PATH),
            "%s/%s" % (global_config["ROOT_EXPORT_DIR"], DEL_PACK_PATH)]
        dir_fix_list = [
            "/var/run/package-server",
            "%s" % (global_config["ROOT_EXPORT_DIR"]),
            "%s/%s" % (global_config["ROOT_EXPORT_DIR"], ADD_PACK_PATH),
            "%s/%s" % (global_config["ROOT_EXPORT_DIR"], DEL_PACK_PATH)]
        log_lines = []
        for dir_val in dir_list:
            if not os.path.isdir(dir_val):
                try:
                    os.makedirs(dir_val)
                except OSError:
                    log_lines.append(("error creating directory %s" % (dir_val), logging_tools.LOG_LEVEL_ERROR))
                else:
                    log_lines.append(("Created directory %s" % (dir_val), logging_tools.LOG_LEVEL_OK))
                    dir_fix_list.append(dir_val)
        # not implemented, FIXME, AL 20120512
        #configfile.write_config(dc, "package_server", glob_config)
        dc.release()
        process_tools.renice()
        process_tools.fix_sysconfig_rights()
        process_tools.change_user_group_path(os.path.dirname(os.path.join(process_tools.RUN_DIR, global_config["PID_NAME"])), global_config["USER"], global_config["GROUP"])
        configfile.enable_config_access(global_config["USER"], global_config["GROUP"])
        process_tools.change_user_group(global_config["USER"], global_config["GROUP"])
        if not global_config["DEBUG"]:
            process_tools.become_daemon()
            process_tools.set_handles({"out" : (1, "package-server.out"),
                                       "err" : (0, "/var/lib/logging-server/py_err")})
        else:
            print "Debugging package-server on %s" % (long_host_name)
        ret_code = server_process(db_con).loop()
    db_con.close()
    del db_con
    sys.exit(ret_code)

if __name__ == "__main__":
    main()
