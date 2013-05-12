#!/usr/bin/python-init -Otu
#
# Copyright (C) 2009,2010,2011,2012,2013 Andreas Lang-Nevyjel
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
""" SNMP relayer """

import zmq
import time
import sys
import os
import threading_tools
import logging_tools
import process_tools
import configfile
import difflib
import socket
from initat.host_monitoring import limits
from pysnmp.carrier.asynsock.dispatch import AsynsockDispatcher
from pysnmp.carrier.asynsock.dgram import udp
from pyasn1.codec.ber import encoder, decoder
import pyasn1
from pyasn1.type.error import ValueConstraintError
from pysnmp.smi import exval
from pysnmp.proto import api
from initat.snmp_relay import snmp_relay_schemes
import server_command

import pprint

# non-critical imports
try:
    from snmp_relay_version import VERSION_STRING
except ImportError:
    VERSION_STRING = "unknown-unknown"

STR_LEN = 256
DEBUG_LOG_TIME = 15

class snmp_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context)
        self.register_func("fetch_snmp", self._fetch_snmp)
        self._init_dispatcher()
        self.__verbose = global_config["VERBOSE"]
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def oid_pretty_print(self, oids):
        return ";".join(["%s" % (".".join(["%d" % (oidp) for oidp in oid])) for oid in oids])
    def _init_dispatcher(self):
        self.log("init snmp_session object")
        self.__disp = AsynsockDispatcher()
        self.__disp.registerTransport(udp.domainName, udp.UdpSocketTransport().openClientMode())
        self.__disp.registerRecvCbFun(self._recv_func)
        self.__disp.registerTimerCbFun(self._timer_func)
    def _fetch_snmp(self, *scheme_data, **kwargs):
        snmp_ver, snmp_host, snmp_community, self.envelope, self.transform_single_key = scheme_data[0:5]
        self._set_target(snmp_ver, snmp_host, snmp_community)
        self._clear_errors()
        # header value mapping mapping
        for key, header_list in scheme_data[5:]:
            if self.run_ok() and header_list:
                if key == "T":
                    if self.__verbose > 1:
                        self.log("bulk-walk tables (%s): %s" % (self.__snmp_host, self.oid_pretty_print(header_list)))
                    self.get_tables(header_list)
                    if self.__verbose > 1:
                        self.log("bulk-walk tables: done")
                else:
                    if self.__verbose > 1:
                        self.log("get tables (%s): %s" % (self.__snmp_host, self.oid_pretty_print(header_list)))
                    self.get_tables(header_list, single_values=True)
                    if self.__verbose > 1:
                        self.log("get tables: done")
                if self.run_ok():
                    if self.__verbose > 1:
                        self.log("(%s) for host %s (%s): %s" % (
                            key,
                            self.__snmp_host,
                            logging_tools.get_plural("table header", len(header_list)),
                            logging_tools.get_plural("result", self.num_result_values)))
                else:
                    self.__error_list.append("snmp timeout (OID is %s)" % (self.oid_pretty_print(header_list)))
                    self.log("(%s) run not ok for host %s (%s)" % (
                        key,
                        self.__snmp_host,
                        logging_tools.get_plural("table header", len(header_list))),
                             logging_tools.LOG_LEVEL_ERROR)
        # signal scheme that we are done
        #pprint.pprint(self.snmp)
        self._unlink()
        self.send_pool_message("snmp_finished", self.envelope, self.__error_list, self.__received, self.snmp)
    @property
    def snmp(self):
        return self.__snmp_dict
    @snmp.setter
    def snmp(self, in_value):
        header, key, value = in_value
        #if header in self.__waiting_for:
        self.__received.add(header)
        if self.__single_value:
            self.__snmp_dict[header] = value
        else:
            if self.transform_single_key and len(key) == 1:
                key = key[0]
            self.__snmp_dict.setdefault(header, {})[key] = value
    def _clear_errors(self):
        self.__received, self.__snmp_dict = (set(), {})
        self.__timed_out, self.__other_errors, self.__error_list = (False, False, [])
    def _set_target(self, snmp_ver, snmp_host, snmp_community):
        self.__snmp_ver, self.__snmp_host, self.__snmp_community = (snmp_ver, snmp_host, snmp_community)
        try:
            self.__p_mod = api.protoModules[{1 : api.protoVersion1,
                                             2 : api.protoVersion2c}[self.__snmp_ver]]
        except KeyError:
            self.log("unknown snmp_version %d, using 1" % (self.__snmp_ver), logging_tools.LOG_LEVEL_ERROR)
            self.__p_mod = api.protoModules[api.protoVersion1]
    def _unlink(self):
        # remove links
        pass
    def get_tables(self, base_oids, **args):
        # table header
        self.__head_vars = [self.__p_mod.ObjectIdentifier(base_oid) for base_oid in base_oids]
        self.__max_head_vars = [self.__p_mod.ObjectIdentifier(base_oid.get_max_oid()) if base_oid.has_max_oid() else None for base_oid in base_oids]
        # actual header vars
        self.__act_head_vars = [(header, max_header) for header, max_header in zip(self.__head_vars, self.__max_head_vars)]
        # numer of result values
        self.num_result_values = 0
        # 5 seconds default timeout
        self.__timeout = args.get("timeout", 30)
        # max items
        self.__max_items = args.get("max_items", 0)
        self.__num_items = 0
        # who many times the timer_func was called
        self.__timer_idx = 0
        self.__single_values = args.get("single_values", False)
        if self.__single_values:
            # PDU for single values
            self.__req_pdu =  self.__p_mod.GetRequestPDU()
        else:
            # PDU for multiple values
            self.__req_pdu =  self.__p_mod.GetNextRequestPDU()
        self.__p_mod.apiPDU.setDefaults(self.__req_pdu)
        self.__next_names = [value for value, max_value in self.__act_head_vars]
        self.__act_domain, self.__act_address = (udp.domainName, (self.__snmp_host, 161))
        self.__p_mod.apiPDU.setVarBinds(self.__req_pdu, [(head_var, self.__p_mod.Null("")) for head_var, max_head_var in self.__act_head_vars])
        if self.__p_mod.apiPDU.getErrorStatus(self.__req_pdu):
            self.log("Something went seriously wrong: %s" % (self.__p_mod.apiPDU.getErrorStatus(self.__req_pdu).prettyPrint()),
                    logging_tools.LOG_LEVEL_CRITICAL)
        # message
        self.__req_msg = self.__p_mod.Message()
        self.__p_mod.apiMessage.setDefaults(self.__req_msg)
        self.__p_mod.apiMessage.setCommunity(self.__req_msg, self.__snmp_community)
        self.__p_mod.apiMessage.setPDU(self.__req_msg, self.__req_pdu)
        # anything got ?
        self.__data_got = False
        # init timer
        self.__start_time = time.time()
        self.__single_value = self.__single_values
        #self.__act_scheme.set_single_value(self.__single_values)
        self.__disp.sendMessage(encoder.encode(self.__req_msg), self.__act_domain, self.__act_address)
        self.__disp.jobStarted(True)
        try:
            self.__disp.runDispatcher()
        except ValueConstraintError:
            self.log("caught ValueConstraintError for host %s" % (
                self.__snmp_host),
                     logging_tools.LOG_LEVEL_CRITICAL)
            self.__other_errors = True
        except:
            exc_info = process_tools.exception_info()
            self.log("cannot run Dispatcher (host %s):" % (
                self.__snmp_host),
                     logging_tools.LOG_LEVEL_CRITICAL)
            for log_line in exc_info.log_lines:
                self.log(" - %s" % (log_line), logging_tools.LOG_LEVEL_CRITICAL)
            self.__other_errors = True
    def run_ok(self):
        return not self.__timed_out and not self.__other_errors
    def __del__(self):
        self.__disp.closeDispatcher()
    def _timer_func(self, act_time):
        diff_time = act_time - self.__start_time
        trigger_timeout = False
        # no data received for a certain time (wait at least 3 seconds)
        if not self.__data_got and self.__timer_idx and diff_time > 3:
            if self.__timer_idx > 3 and not self.__num_items:
                self.log("giving up for %s after %d items (%d seconds, timer_idx is %d)" % (
                    self.__snmp_host,
                    self.__num_items,
                    act_time - self.__start_time,
                    self.__timer_idx),
                         logging_tools.LOG_LEVEL_ERROR)
                trigger_timeout = True
            else:
                self.log("re-initiated get() for %s after %s (%d seconds, timer_idx is %d)" % (
                    self.__snmp_host,
                    logging_tools.get_plural("item", self.__num_items),
                    act_time - self.__start_time,
                    self.__timer_idx),
                         logging_tools.LOG_LEVEL_WARN)
                self._next_send()
        self.__timer_idx += 1
        # reset trigger
        self.__data_got = False
        if abs(diff_time) > self.__timeout or trigger_timeout:
            self.__timed_out = True
            self.__disp.jobFinished(True)
    def _recv_func(self, disp, domain, address, whole_msg):
        self.__data_got = True
        while whole_msg:
            rsp_msg, whole_msg = decoder.decode(whole_msg, asn1Spec=self.__p_mod.Message())
            rsp_pdu = self.__p_mod.apiMessage.getPDU(rsp_msg)
            # Match response to request
            if self.__p_mod.apiPDU.getRequestID(self.__req_pdu) == self.__p_mod.apiPDU.getRequestID(rsp_pdu):
                terminate = False
                next_headers, next_names = ([], [])
                # Check for SNMP errors reported
                error_status = self.__p_mod.apiPDU.getErrorStatus(rsp_pdu)
                if error_status:
                    self.log("SNMP error_status: %s" % (self.__p_mod.apiPDU.getErrorStatus(rsp_pdu).prettyPrint()),
                             logging_tools.LOG_LEVEL_WARN)
                    if error_status not in [2]:
                        self.__other_errors = True
                    terminate = True
                else:
                    # Format var-binds table
                    var_bind_table = self.__p_mod.apiPDU.getVarBindTable(self.__req_pdu, rsp_pdu)
                    # Report SNMP table
                    if len(var_bind_table) != 1:
                        print "*** length of var_bind_table != 1 ***"
                    for (act_h, max_h), (name, value) in zip(self.__act_head_vars, var_bind_table[0]):
                        if value is None:
                            continue
                        elif exval.endOfMib.isSameTypeWith(value):
                            terminate = True
                            break
                        if act_h.isPrefixOf(name):
                            if max_h and max_h.isPrefixOf(name):
                                # max_oid reached
                                pass
                            else:
                                next_headers.append((act_h, max_h))
                                next_names.append(name)
                                name = name[len(act_h):]
                                if isinstance(value, pyasn1.type.univ.Integer):
                                    self.snmp = (tuple(act_h), tuple(name), int(value))
                                #elif isinstance(value, pyasn1.type.univ.Real):
                                #    self.snmp = (tuple(act_h), tuple(name), float(value))
                                elif isinstance(value, pyasn1.type.univ.ObjectIdentifier):
                                    self.snmp = (tuple(act_h), tuple(name), tuple(value))
                                else:
                                    self.snmp = (tuple(act_h), tuple(name), str(value))
                                self.num_result_values += 1
                        self.__num_items += 1
                        if self.__max_items and self.__num_items > self.__max_items:
                            terminate = True
                            #print "from: %s, %s = %s" % (address, name.prettyPrint(), value.prettyPrint())
                    # Stop on EOM
                    if not terminate:
                        for oid, val in var_bind_table[-1]:
                            if val is not None:
                                terminate = False
                                break
                        else:
                            terminate = True
                # Generate request for next row
                if abs(time.time() - self.__start_time) > self.__timeout:
                    self.__timed_out = True
                else:
                    self.__start_time = time.time()
                if not self.__timed_out and next_names and not terminate and not self.__single_values:
                    self.__act_head_vars, self.__next_names = (next_headers, next_names)
                    self.__act_domain, self.__act_address = (domain, address)
                    #print var_bind_table
                    self._next_send()
                else:
                    self.__disp.jobFinished(1)
        return whole_msg
    def _next_send(self):
        self.__p_mod.apiPDU.setVarBinds(self.__req_pdu, [(var_x, self.__p_mod.Null("")) for var_x in self.__next_names])
        self.__p_mod.apiPDU.setRequestID(self.__req_pdu, self.__p_mod.getNextRequestID())
        self.__disp.sendMessage(encoder.encode(self.__req_msg), self.__act_domain, self.__act_address)
    def loop_post(self):
        self.__log_template.close()

class relay_process(threading_tools.process_pool):
    def __init__(self):
        self.__verbose = global_config["VERBOSE"]
        self.__log_cache, self.__log_template = ([], None)
        threading_tools.process_pool.__init__(
            self,
            "main",
            zmq=True,
            zmq_debug=global_config["ZMQ_DEBUG"]
        )
        self.renice()
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self.install_signal_handlers()
        self._init_msi_block()
        self._init_ipc_sockets()
        self.register_exception("int_error" , self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("hup_error" , self._hup_error)
        self.register_exception("term_error", self._sigint)
        self.register_func("int_error", self._int_error)
        self.register_func("snmp_finished", self._snmp_finished)
        self.__verbose = global_config["VERBOSE"]
        self._check_msg_settings()
        self._log_config()
        # init luts
        self.__ip_lut, self.__forward_lut = ({}, {})
        self.__last_log_time = time.time() - 3600
        self._check_schemes()
        self._init_host_objects()
        # dict to suppress too fast sending
        self.__ret_dict = {}
        self._init_processes(global_config["SNMP_PROCESSES"])
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))
    def _sigint(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True
    def _check_schemes(self):
        self.__all_schemes = {}
        glob_keys = dir(snmp_relay_schemes)
        for glob_key in sorted(glob_keys):
            if glob_key.endswith("_scheme") and glob_key != "snmp_scheme":
                glob_val = getattr(snmp_relay_schemes, glob_key)
                if issubclass(glob_val, snmp_relay_schemes.snmp_scheme):
                    self.__all_schemes[glob_key[:-7]] = glob_val
    def _init_host_objects(self):
        self.__host_objects = {}
    def _init_processes(self, num_processes):
        self.log("Spawning %s" % (logging_tools.get_plural("snmp_process", num_processes)))
        # buffer for queued_requests
        self.__queued_requests = []
        # pending schemes
        self.__pending_schemes = {}
        self.__process_dict = {}
        for idx in xrange(num_processes):
            proc_name = "snmp_%d" % (idx)
            new_proc = snmp_process(proc_name)
            proc_socket = self.add_process(new_proc, start=True)
            self.__process_dict[proc_name] = {
                "socket"     : proc_socket,
                "call_count" : 0,
                "in_use"     : False,
                "state"      : "running",
                "proc_name"  : proc_name}
    def _get_host_object(self, host_name, snmp_community, snmp_version):
        host_tuple = (host_name, snmp_community, snmp_version)
        if not self.__host_objects.has_key(host_tuple):
            self.__host_objects[host_tuple] = snmp_relay_schemes.net_object(self.log, self.__verbose, host_name, snmp_community, snmp_version)
        return self.__host_objects[host_tuple]
    def _log_config(self):
        self.log("Basic turnaround-time is %d seconds" % (global_config["MAIN_TIMER"]))
        self.log("basedir_name is '%s'" % (global_config["BASEDIR_NAME"]))
        self.log("manager PID is %d" % (configfile.get_manager_pid()))
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found %d valid config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def _init_msi_block(self):
        self.__pid_name = global_config["PID_NAME"]
        process_tools.save_pids(global_config["PID_NAME"], mult=3)
        cf_pids = 2 + global_config["SNMP_PROCESSES"]
        process_tools.append_pids(global_config["PID_NAME"], pid=configfile.get_manager_pid(), mult=cf_pids)
        if global_config["DAEMONIZE"]:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("snmp-relay")
            msi_block.add_actual_pid(mult=3)
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=cf_pids)
            msi_block.start_command = "/etc/init.d/snmp-relay start"
            msi_block.stop_command ="/etc/init.d/snmp-relay force-stop"
            msi_block.kill_pids = True
            #msi_block.heartbeat_timeout = 120
            msi_block.save_block()
        else:
            msi_block = None
        self.__msi_block = msi_block
    def process_start(self, src_process, src_pid):
        process_tools.append_pids(self.__pid_name, src_pid, mult=3)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(src_pid, mult=3)
            self.__msi_block.save_block()
    def _int_error(self, err_cause):
        self.log("_int_error() called, cause %s" % (str(err_cause)), logging_tools.LOG_LEVEL_WARN)
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True
    def _init_ipc_sockets(self):
        self.__num_messages = 0
        sock_list = [("receiver", zmq.PULL, 2   ),
                     ("sender"  , zmq.PUB , 1024)]
        [setattr(self, "%s_socket" % (short_sock_name), None) for short_sock_name, a0, b0 in sock_list]
        for short_sock_name, sock_type, hwm_size in sock_list:
            sock_name = process_tools.get_zmq_ipc_name(short_sock_name)
            file_name = sock_name[5:]
            self.log("init %s ipc_socket '%s' (HWM: %d)" % (short_sock_name, sock_name,
                                                            hwm_size))
            if os.path.exists(file_name):
                self.log("removing previous file")
                try:
                    os.unlink(file_name)
                except:
                    self.log("... %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            wait_iter = 0
            while os.path.exists(file_name) and wait_iter < 100:
                self.log("socket %s still exists, waiting" % (sock_name))
                time.sleep(0.1)
                wait_iter += 1
            cur_socket = self.zmq_context.socket(sock_type)
            try:
                process_tools.bind_zmq_socket(cur_socket, sock_name)
                #client.bind("tcp://*:8888")
            except zmq.core.error.ZMQError:
                self.log("error binding %s: %s" % (short_sock_name,
                                                   process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_CRITICAL)
                raise
            else:
                setattr(self, "%s_socket" % (short_sock_name), cur_socket)
                backlog_size = global_config["BACKLOG_SIZE"]
                os.chmod(file_name, 0777)
                self.receiver_socket.setsockopt(zmq.LINGER, 0)
                self.receiver_socket.setsockopt(zmq.RCVHWM, hwm_size)
                self.receiver_socket.setsockopt(zmq.SNDHWM, hwm_size)
                if sock_type == zmq.PULL:
                    self.register_poller(cur_socket, zmq.POLLIN, self._recv_command)
    def _close_ipc_sockets(self):
        if self.receiver_socket is not None:
            self.unregister_poller(self.receiver_socket, zmq.POLLIN)
            self.receiver_socket.close()
        if self.sender_socket is not None:
            self.sender_socket.close()
    def _hup_error(self, err_cause):
        # no longer needed
        #self.__relay_thread_queue.put("reload")
        pass
    def _resolve_address(self, target):
        # to avoid loops in the 0MQ connection scheme (will result to nasty asserts)
        if target in self.__forward_lut:
            ip_addr = self.__forward_lut[target]
        else:
            orig_target = target
            if target.lower() in ["localhost", "127.0.0.1", "localhost.localdomain"]:
                target = process_tools.get_machine_name()
            # step 1: resolve to ip
            ip_addr = socket.gethostbyname(target)
            try:
                # step 2: try to get full name
                full_name, aliases, ip_addrs = socket.gethostbyaddr(ip_addr)
            except:
                # forget it
                pass
            else:
                # resolve full name
                ip_addr = socket.gethostbyname(full_name)
            if ip_addr not in self.__ip_lut:
                self.log("resolved %s to %s" % (target, ip_addr))
                self.__ip_lut[ip_addr] = target
            self.__forward_lut[target] = ip_addr
            self.log("ip resolving: %s -> %s" % (target, ip_addr))
            if orig_target != target:
                self.__forward_lut[orig_target] = ip_addr
                self.log("ip resolving: %s -> %s" % (orig_target, ip_addr))
        return ip_addr
    def process_exit(self, p_name, p_pid):
        if not self["exit_requested"]:
            if global_config["DAEMONIZE"]:
                process_tools.remove_pids(self.__pid_name, pid=p_pid)
                self.__msi_block.remove_actual_pid(p_pid)
                self.__msi_block.save_block()
            self.log("helper process %s stopped, restarting" % (p_name))
            proc_struct = self.__process_dict[p_name]
            proc_struct["call_count"] = 0
            proc_struct["state"] = "running"
            proc_struct["socket"] = self.add_process(snmp_process(p_name), start=True)
    def _snmp_finished(self, src_proc, src_pid, *args, **kwargs):
        proc_struct = self.__process_dict[src_proc]
        proc_struct["in_use"] = False
        proc_struct["call_count"] += 1
        envelope, error_list, received, snmp_dict = args
        cur_scheme = self.__pending_schemes[envelope]
        cur_scheme.snmp = snmp_dict
        for cur_error in error_list:
            cur_scheme.flag_error(cur_error)
        self._snmp_end(cur_scheme)
        del self.__pending_schemes[envelope]
        if self.__queued_requests:
            self.log("sending request from buffer (size: %d)" % (len(self.__queued_requests)))
            self._start_snmp_fetch(self.__queued_requests.pop(0))
        if proc_struct["call_count"] == global_config["MAX_CALLS"]:
            self.log("recycling helper process %s after %d calls" % (
                src_proc,
                proc_struct["call_count"],
            ))
            self.stop_process(src_proc)
            proc_struct["state"] = "stopping"
    def _start_snmp_fetch(self, scheme):
        free_processes = sorted([key for key, value in self.__process_dict.iteritems() if not value["in_use"] and value["state"] == "running"])
        cache_ok, num_cached, num_refresh, num_pending, num_hot_enough = scheme.pre_snmp_start(self.log)
        if self.__verbose:
            self.log("%sinfo for %s: %s" % (
                "[F] " if num_refresh else "[I] ",
                scheme.net_obj.name,
                ", ".join(["%d %s" % (cur_num, info_str) for cur_num, info_str in [
                    (num_cached    , "cached"),
                    (num_refresh   , "to refresh"),
                    (num_pending   , "pending"),
                    (num_hot_enough, "hot enough")] if cur_num])))
        if num_refresh:
            if free_processes:
                proc_struct = self.__process_dict[free_processes[0]]
                proc_struct["in_use"] = True
                self.send_to_process(proc_struct["proc_name"], "fetch_snmp", *scheme.proc_data())
                self.__pending_schemes[scheme.envelope] = scheme
            else:
                self.__queued_requests.append(scheme)
                self.log(
                    "no free threads, buffering request (%d in buffer)" % (
                        len(self.__queued_requests)),
                    logging_tools.LOG_LEVEL_WARN)
        else:
            self._snmp_end(scheme)
    def _snmp_end(self, scheme):
        if self.__verbose > 3:
            self.log(
                "snmp_end for %s, return_sent is %s, xml_input is %s" % (
                    scheme.net_obj.name,
                    scheme.return_sent,
                    scheme.xml_input,
                )
            )
        scheme.snmp_end(self.log)
        if scheme.return_sent:
            if scheme.xml_input:
                self._send_return_xml(scheme)
            else:
                ret_state, ret_str, log_it = scheme.return_tuple
                self._send_return(scheme.envelope, ret_state, ret_str)
    def _recv_command(self, zmq_sock):
        body = zmq_sock.recv()
        if zmq_sock.getsockopt(zmq.RCVMORE):
            src_id = body
            body = zmq_sock.recv()
        parameter_ok = False
        xml_input = body.startswith("<")
        if self.__verbose > 3:
            self.log("received %d bytes, xml_input is %s" % (len(body), str(xml_input)))
        if xml_input:
            srv_com = server_command.srv_command(source=body)
            srv_com["result"] = None
            srv_com["result"].attrib.update({"reply" : "no reply set",
                                             "state" : "%d" % (server_command.SRV_REPLY_STATE_UNSET)})
            try:
                host = srv_com.xpath(None, ".//ns:host")[0].text
                snmp_version = int(srv_com.xpath(None, ".//ns:snmp_version")[0].text)
                snmp_community = srv_com.xpath(None, ".//ns:snmp_community")[0].text
                comline = srv_com.xpath(None, ".//ns:command")[0].text
            except:
                self._send_return(body, limits.nag_STATE_CRITICAL, "message format error: %s" % (process_tools.get_except_info()))
            else:
                envelope = srv_com["identity"].text
                parameter_ok = True
                if len(srv_com.xpath(None, ".//ns:arg_list/text()")):
                    comline = " ".join([comline] + srv_com.xpath(None, ".//ns:arg_list/text()")[0].strip().split())
        else:
            srv_com = None
            if body.count(";") >= 3:
                parts = body.split(";", 4)
                envelope = parts.pop(0)
                # parse new format
                if parts[3].endswith(";"):
                    com_part = parts[3][:-1].split(";")
                else:
                    com_part = parts[3].split(";")
                if all([com_part[idx].isdigit() and (len(com_part[idx + 1]) == int(com_part[idx])) for idx in xrange(0, len(com_part), 2)]):
                    arg_list = [com_part[idx + 1] for idx in xrange(0, len(com_part), 2)]
                elif len(com_part):
                    self.log("cannot parse %s" % (body), logging_tools.LOG_LEVEL_ERROR)
                    arg_list = []
                else:
                    arg_list = []
                host, snmp_version, snmp_community = parts[0:3]
                comline = " ".join(arg_list)
                parameter_ok = True
                #envelope, host, snmp_version, snmp_community, comline = body.split(";", 4)
        if parameter_ok:
            try:
                snmp_version = int(snmp_version)
                comline_split = comline.split()
                scheme = comline_split.pop(0)
            except:
                self._send_return(envelope, limits.nag_STATE_CRITICAL, "message format error: %s" % (process_tools.get_except_info()))
            else:
                self.__ret_dict[envelope] = time.time()
                act_scheme = self.__all_schemes.get(scheme, None)
                if act_scheme:
                    host = self._resolve_address(host)
                    host_obj = self._get_host_object(host, snmp_community, snmp_version)
                    if self.__verbose:
                        self.log("got request for scheme %s (host %s, community %s, version %d, envelope %s)" % (
                            scheme,
                            host,
                            snmp_community,
                            snmp_version,
                            envelope))
                    try:
                        act_scheme = act_scheme(net_obj=host_obj,
                                                #ret_queue=self.get_thread_queue(),
                                                #pid=pid,
                                                envelope=envelope,
                                                options=comline_split,
                                                xml_input=xml_input,
                                                srv_com=srv_com,
                                                init_time=time.time())
                    except IOError:
                        err_str = "error while creating scheme %s: %s" % (scheme,
                                                                          process_tools.get_except_info()) 
                        self._send_return(envelope, limits.nag_STATE_CRITICAL, err_str)
                    else:
                        if act_scheme.get_errors():
                            err_str = "problem in creating scheme %s: %s" % (scheme,
                                                                             ", ".join(act_scheme.get_errors()))
                            self._send_return(envelope, limits.nag_STATE_CRITICAL, err_str)
                        else:
                            self._start_snmp_fetch(act_scheme)
                else:
                    guess_list = ", ".join(difflib.get_close_matches(scheme, self.__all_schemes.keys()))
                    err_str = "got unknown scheme '%s'%s" % (
                        scheme,
                        ", maybe one of %s" % (guess_list) if guess_list else ", no similar scheme found")
                    self._send_return(envelope, limits.nag_STATE_CRITICAL, err_str)
        elif not xml_input:
            self._send_return(envelope, limits.nag_STATE_CRITICAL, "message format error")
        self.__num_messages += 1
        if self.__verbose > 3:
            self.log("recv() done")
        if self.__num_messages % 100 == 0:
            cur_mem = process_tools.get_mem_info(self.__msi_block.get_unique_pids() if self.__msi_block else 0)
            self.log("memory usage is %s after %s" % (
                logging_tools.get_size_str(cur_mem),
                logging_tools.get_plural("message", self.__num_messages)))
    def _send_return(self, envelope, ret_state, ret_str):
        if self.__verbose > 3:
            self.log("_send_return, envelope is %s (%d, %s)" % (
                envelope,
                ret_state,
                ret_str,
            ))
        self._check_ret_dict(envelope)
        self.sender_socket.send(envelope, zmq.SNDMORE)
        self.sender_socket.send_unicode(u"%d\0%s" % (ret_state, ret_str))
    def _send_return_xml(self, scheme):
        self._check_ret_dict(scheme.envelope)
        self.sender_socket.send(scheme.envelope, zmq.SNDMORE)
        self.sender_socket.send_unicode(unicode(scheme.srv_com))
    def _check_ret_dict(self, env_str):
        max_sto = 0.001
        if env_str in self.__ret_dict:
            cur_time = time.time()
            if cur_time - self.__ret_dict[env_str] < max_sto:
                if self.__verbose > 2:
                    self.log("sleeping to avoid too fast resending (%.5f < %.5f) for %s" % (
                        cur_time - self.__ret_dict[env_str],
                        max_sto,
                        env_str))
                time.sleep(max_sto)
            del_keys = [key for key, value in self.__ret_dict.iteritems() if abs(value - cur_time) > 60 and key != env_str]
            if del_keys:
                if self.__verbose > 2:
                    self.log("removing %s" % (logging_tools.get_plural("timed-out key", len(del_keys))), logging_tools.LOG_LEVEL_ERROR)
                for del_key in del_keys:
                    del self.__ret_dict[del_key]
            del self.__ret_dict[env_str]
    def _check_msg_settings(self):
        msg_dir = "/proc/sys/kernel/"
        t_dict = {"max" : {"info"  : "maximum number of bytes in a message"},
                  "mni" : {"info"  : "number of message-queue identifiers"},
                  "mnb" : {"info"  : "initial value for msg_qbytes",
                           "value" : 655360}}
        for key, ipc_s in t_dict.iteritems():
            r_name = "msg%s" % (key)
            f_name = "%s%s" % (msg_dir, r_name)
            if os.path.isfile(f_name):
                value = int(file(f_name, "r").read().strip())
                self.log("value of %s (%s) is %d" % (r_name, ipc_s["info"], value))
                if ipc_s.has_key("value") and ipc_s["value"] != value:
                    try:
                        file(f_name, "w").write("%d\n" % (ipc_s["value"]))
                    except:
                        self.log("Cannot alter value of %s (%s) to %d: %s" % (f_name,
                                                                              ipc_s["info"],
                                                                              ipc_s["value"],
                                                                              process_tools.get_except_info()),
                                 logging_tools.LOG_LEVEL_WARN)
                    else:
                        self.log("Altered value of %s (%s) from %d to %d" % (f_name,
                                                                             ipc_s["info"],
                                                                             value,
                                                                             ipc_s["value"]))
                                                                             
            else:
                self.log("file %s not readable" % (f_name), logging_tools.LOG_LEVEL_WARN)
    def loop_end(self):
        self._close_ipc_sockets()
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
    def loop_post(self):
        self.__log_template.close()
    
global_config = configfile.get_global_config(process_tools.get_programm_name())
        
def main():
    # read global configfile
    prog_name = global_config.name()
    global_config.add_config_entries([
        ("BASEDIR_NAME"    , configfile.str_c_var("/etc/sysconfig/snmp-relay.d")),
        ("DEBUG"           , configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("ZMQ_DEBUG"       , configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
        ("VERBOSE"         , configfile.int_c_var(0)),
        ("DAEMONIZE"       , configfile.bool_c_var(True)),
        ("SNMP_PROCESSES"  , configfile.int_c_var(4, help_string="number of SNMP processes [%(default)d]", short_options="n")),
        ("MAIN_TIMER"      , configfile.int_c_var(60, help_string="main timer [%(default)d]")),
        ("KILL_RUNNING"    , configfile.bool_c_var(True)),
        ("BACKLOG_SIZE"    , configfile.int_c_var(5, help_string="backlog size for 0MQ sockets [%(default)d]")),
        ("LOG_NAME"        , configfile.str_c_var("snmp-relay")),
        ("LOG_DESTINATION" , configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("MAX_CALLS"       , configfile.int_c_var(100, help_string="number of calls per helper process [%(default)d]")),
        ("VERBOSE"         , configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ("PID_NAME"        , configfile.str_c_var("%s/%s" % (
            prog_name,
            prog_name)))])
    global_config.parse_file()
    options = global_config.handle_commandline(positional_arguments=False,
                                               partial=False,
                                               add_writeback_option=True)
    global_config.write_file()
    if global_config["KILL_RUNNING"]:
        process_tools.kill_running_processes(exclude=configfile.get_manager_pid())
    handledict = {"out"    : (1, "snmp-relay.out"),
                  "err"    : (0, "/var/lib/logging-server/py_err"),
                  "strict" : 0}
    process_tools.ALLOW_MULTIPLE_INSTANCES = False
    process_tools.renice()
    if global_config["DAEMONIZE"] and not global_config["DEBUG"]:
        process_tools.become_daemon()
        #hc_ok = process_tools.set_handles(handledict)
    else:
        print "Debugging snmp-relayer"
    ret_code = relay_process().loop()
    sys.exit(ret_code)

if __name__ == "__main__":
    main()
