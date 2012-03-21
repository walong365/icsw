#!/usr/bin/python-init -Otu
#
# Copyright (C) 2009,2010,2011,2012 Andreas Lang-Nevyjel
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
import struct
import socket
import threading_tools
import logging_tools
import process_tools
import configfile
import difflib
from host_monitoring import limits
import pprint
import optparse
import threading
# SNMP related imports
import pkg_resources
pkg_resources.require("pyasn1")
from pysnmp.carrier.asynsock.dispatch import AsynsockDispatcher
from pysnmp.carrier.asynsock.dgram import udp
from pyasn1.codec.ber import encoder, decoder
import pyasn1
from pysnmp.smi import exval
from pysnmp.proto import api
import snmp_relay_schemes
import gc
import server_command
#import ipc_comtools

# non-critical imports
try:
    from snmp_relay_version import VERSION_STRING
except ImportError:
    VERSION_STRING = "unknown-unknown"

STR_LEN = 256
DEBUG_LOG_TIME = 15

class snmp_process(threading_tools.process_obj):
    def process_init(self):
        self.__thread_num = 0#thread_num
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        #self.__mother_thread_queue = mother_thread_queue
        #threading_tools.thread_obj.__init__(self, thread_name, queue_size=500)
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
    #def thread_running(self):
    #    self.__mother_thread_queue.put(("new_pid", self.pid))
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
                        self.log("(%s) for host %s (%s): %s" % (key,
                                                                self.__snmp_host,
                                                                logging_tools.get_plural("table header", len(header_list)),
                                                                logging_tools.get_plural("result", self.num_result_values)))
                else:
                    self.__error_list.append("snmp timeout (OID is %s)" % (self.oid_pretty_print(header_list)))
                    self.log("(%s) run not ok for host %s (%s)" % (key,
                                                                   self.__snmp_host,
                                                                   logging_tools.get_plural("table header", len(header_list))),
                             logging_tools.LOG_LEVEL_ERROR)
        # signal scheme that we are done
        #pprint.pprint(self.snmp)
        #act_scheme.snmp_end(self.log)
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
        except:
            self.log("cannot run Dispatcher (host %s): %s" % (self.__snmp_host,
                                                              process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_CRITICAL)
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
                self.log("giving up for %s after %d items (timer_idx is %d)" % (self.__snmp_host,
                                                                                self.__num_items,
                                                                                self.__timer_idx),
                         logging_tools.LOG_LEVEL_ERROR)
                trigger_timeout = True
            else:
                self.log("re-initiated get() for %s after %d items (timer_idx is %d)" % (self.__snmp_host,
                                                                                         self.__num_items,
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

##class timer_thread(threading_tools.thread_obj):
##    def __init__(self, msi_block, logger):
##        self.__logger       = logger
##        self.__msi_block    = msi_block
##        threading_tools.thread_obj.__init__(self, "timer", queue_size=100, loop_function=self._run)
##        self._event = threading.Event()
##    def thread_running(self):
##        self.send_pool_message(("new_pid", self.pid))
##    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
##        self.__logger.log(lev, what)
##    def _run(self):
##        self.log("init timer loop")
##        while not self._event.is_set():
##            # heartbeat
##            self.__msi_block.heartbeat()
##            # test message
##            r_state, r_out = ipc_comtools.send_and_receive("<INTERNAL>", "test-connection", ipc_key=101, mode="snmp-relay")
##            self.log("test-connection gave (%d): %s" % (r_state,
##                                                        r_out),
##                     limits.nag_state_to_log_level(r_state))
##            self._event.wait(30)
        
##class flush_thread(threading_tools.thread_obj):
##    def __init__(self, message_q, logger):
##        self.__logger       = logger
##        self.__message_queue = message_q
##        threading_tools.thread_obj.__init__(self, "flush", queue_size=100)
##        self.register_func("finished", self._finished)
##        self.__finish_list = []
##        self.__flush_counter = 0
##    def thread_running(self):
##        self.send_pool_message(("new_pid", self.pid))
##    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
##        self.__logger.log(lev, what)
##    def _finished(self, (pid, init_time)):
##        self.__finish_list.append((pid, init_time))
##        self.__flush_counter = (self.__flush_counter - 1) % 10
##        if not self.__flush_counter:
##            act_plist = process_tools.get_process_id_list()
##            act_time = time.time()
##            new_flist = []
##            for c_pid, init_time in self.__finish_list:
##                # check if initial call is old enough (say 60 seconds)
##                tdiff = act_time - init_time
##                # fragment to old, clock skewed or calling process dead:
##                if abs(tdiff) > 60 or c_pid not in act_plist:
##                    # delete pending requests
##                    num, b_len = (0, 0)
##                    data = True
##                    while data:
##                        data = self.__message_queue.receive(type = c_pid)
##                        if data:
##                            b_len += len(data)
##                            num += 1
##                    if num:
##                        self.log("flushed %s (%d bytes) for pid %d" % (logging_tools.get_plural("message fragment", num),
##                                                                       b_len,
##                                                                       c_pid))
##                else:
##                    new_flist.append((c_pid, init_time))
##            self.__finish_list = new_flist

##class relay_process_x(threading_tools.process_pool):
##    def __init__(self):
##        self.__verbose = global_config["VERBOSE"]
##        self.__log_cache, self.__log_template = ([], None)
##        threading_tools.process_pool.__init__(self, "main", zmq=True)
##        self.renice()
##        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
##        #self.__message_queue  = mes_queue
##        #self.__flush_queue    = flush_queue
##        self.register_func("new_ipc_request", self._new_ipc_request)
##        self.register_func("new_pid", self._new_pid)
##        self.register_func("exiting", self._helper_thread_exiting)
##        self.register_func("spawn_thread", self._spawn_thread)
##        self.register_func("snmp_result", self._snmp_result)
##        self.register_func("snmp_finished", self._snmp_finished)
##        self._check_schemes()
##        self._init_host_objects()
##        self.__requests_served = 0
##        self.__requests_pending = 0
##        self.__start_time = time.time()
##        self.__last_log_time = time.time() - 3600
##    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
##        if self.__log_template:
##            self.__log_template.log(lev, what)
##        else:
##            self.__log_cache.append((lev, what))
##    def thread_running(self):
##        self.__net_server, self.__ping_object = (None, None)
##        self.send_pool_message(("new_pid", self.pid))
##        #self.__glob_config.add_config_dict({"LONG_LEN" : configfile.int_c_var(struct.calcsize("@l")),
##        #                                    "INT_LEN"  : configfile.int_c_var(struct.calcsize("@i"))})
##        self._init_threads(12)
##    def _new_pid(self, what):
##        self.send_pool_message(("new_pid", what))
##        self._send_wakeup()
##    def _helper_thread_exiting(self, stuff):
##        self.send_pool_message(("exiting", stuff))
##        self._send_wakeup()
##    def _send_wakeup(self):
##        send_str = "wakeup"
##        self.__message_queue.send(struct.pack("@l%ds" % (len(send_str)), 1, send_str))
##    def _check_schemes(self):
##        self.__all_schemes = {}
##        glob_keys = dir(snmp_relay_schemes)
##        for glob_key in sorted(glob_keys):
##            if glob_key.endswith("_scheme") and glob_key != "snmp_scheme":
##                glob_val = getattr(snmp_relay_schemes, glob_key)
##                if issubclass(glob_val, snmp_relay_schemes.snmp_scheme):
##                    self.__all_schemes[glob_key[:-7]] = glob_val
##    def _init_host_objects(self):
##        self.__host_objects = {}
##    def _get_host_object(self, host_name, snmp_community, snmp_version):
##        host_tuple = (host_name, snmp_community, snmp_version)
##        if not self.__host_objects.has_key(host_tuple):
##            self.__host_objects[host_tuple] = snmp_relay_schemes.net_object(self.log, global_config["VERBOSE"], host_name, snmp_community, snmp_version)
##        return self.__host_objects[host_tuple]
##    def _init_threads(self, num_threads):
##        self.log("Spawning %s" % (logging_tools.get_plural("parser_thread", num_threads)))
##        # buffer for queued_requests
##        self.__queued_requests = []
##        # helper threads
##        self.__snmp_queues = {}
##        for idx in range(num_threads):
##            self._spawn_thread(idx)
##    def _spawn_thread(self, idx):
##        pt_name = "snmp_%d" % (idx)
##        self.log("starting helper thread %s" % (pt_name))
##        self.__snmp_queues[pt_name] = {"queue"      : self.get_thread_pool().add_thread(snmp_helper_thread(idx, pt_name, self.get_thread_queue()), start_thread=True).get_thread_queue(),
##                                       "used"       : 0,
##                                       "call_count" : 0,
##                                       # flag if thread is running
##                                       "running"    : True}
##    def _parse_packed_data(self, data, (other_long_len, other_int_len, long_len, int_len)):
##        header_len = other_long_len + 5 * other_int_len
##        data_len = len(data)
##        if data_len < header_len:
##            raise ValueError, "received message with only %s (need at least %s)" % (logging_tools.get_plural("byte", data_len),
##                                                                                    logging_tools.get_plural("byte", header_len))
##        else:
##            # not really needed any more ...
##            if other_long_len == long_len:
##                form_str = "@l5i"
##            elif long_len == 4:
##                # i am 32 bit, foreign host is 64 bit
##                form_str = "@q5i"
##            else:
##                # i am 64 bit, foreign host is 32 bit
##                form_str = "@i5i"
##            datatype, pid, snmp_version, dhost_len, command_len, snmp_community_len = struct.unpack(form_str, data[0:header_len])
##            host           = data[header_len             : header_len + dhost_len              ]
##            full_comline   = data[header_len + dhost_len : header_len + dhost_len + command_len].strip()
##            snmp_community = data[header_len + dhost_len + command_len : header_len + dhost_len + command_len + snmp_community_len].strip()
##            return pid, host, snmp_version, snmp_community, full_comline
##    def _snmp_finished(self, thread_name):
##        ht_struct = self.__snmp_queues[thread_name]
##        #self.__requests_pending -= 1
##        #self.log("pending-: %d" % (self.__requests_pending))
##        ht_struct["used"] -= 1
##        ht_struct["call_count"] += 1
##        if ht_struct["call_count"] > 100:
##            self.log("removing helper_thread %s" % (thread_name))
##            # flag queue as not running
##            ht_struct["running"] = False
##            ht_struct["queue"].put(("exit", self.get_thread_queue()))
##        if self.__queued_requests:
##            self.log("sending request from buffer")
##            self._start_snmp_fetch(self.__queued_requests.pop(0))
##    def _start_snmp_fetch(self, scheme):
##        free_threads = sorted([key for key, value in self.__snmp_queues.iteritems() if not value["used"] and value["running"]])
##        cache_ok, num_cached, num_refresh, num_pending, num_hot_enough = scheme.pre_snmp_start(self.log)
##        if global_config["VERBOSE"] > 1:
##            self.log("%sinfo for %s: %s" % ("[F] " if num_refresh else "[I] ",
##                                            scheme.net_obj.name,
##                                            ", ".join(["%d %s" % (cur_num, info_str) for cur_num, info_str in [(num_cached, "cached"),
##                                                                                                               (num_refresh, "to refresh"),
##                                                                                                               (num_pending, "pending"),
##                                                                                                               (num_hot_enough, "hot enough")] if cur_num])))
##        if num_refresh:
##            if free_threads:
##                ht_struct = self.__snmp_queues[free_threads[0]]
##                ht_struct["used"] += 1
##                #self.__requests_pending += 1
##                #self.log("pending+: %d" % (self.__requests_pending))
##                ht_struct["queue"].put(("fetch_snmp", scheme))
##            else:
##                self.__queued_requests.append(scheme)
##                self.log("no free threads, buffering request (%d in buffer)" % (len(self.__queued_requests)),
##                         logging_tools.LOG_LEVEL_WARN)
##        else:
##            scheme.snmp_end(self.log)
##    def _new_ipc_request(self, (data, init_time)):
##        act_time = time.time()
##        if global_config["VERBOSE"] > 0 and abs(act_time - self.__last_log_time) > DEBUG_LOG_TIME:
##            self.__last_log_time = act_time
##            self.log("queue statistics : %s" % (", ".join(["%s: %d of %d" % (q_name, q_struct["queue"].qsize(), q_struct["queue"].maxsize) for q_name, q_struct in
##                                                           self.__snmp_queues.iteritems() if q_struct["queue"].qsize()]) or "all empty"))
##        try:
##            pid, host, snmp_version, snmp_community, comline = self._parse_packed_data(data, (self.__glob_config["LONG_LEN"], self.__glob_config["INT_LEN"], self.__glob_config["LONG_LEN"], self.__glob_config["INT_LEN"]))
##        except:
##            self.log("error decoding ipc_request: %s" % (process_tools.get_except_info()),
##                     logging_tools.LOG_LEVEL_ERROR)
##        else:
##            if host == "<INTERNAL>":
##                self._snmp_result((pid, init_time, limits.nag_STATE_OK, "ok checked", False))
##            else:
##                host_obj = self._get_host_object(host, snmp_community, snmp_version)
##                comline_split = comline.split()
##                scheme = comline_split.pop(0)
##                if scheme.count("/"):
##                    scheme = os.path.basename(scheme)
##                act_scheme = self.__all_schemes.get(scheme, None)
##                if act_scheme:
##                    if global_config["VERBOSE"] > 1:
##                        self.log("got request for scheme %s (host %s, community %s, version %d, pid %d)" % (scheme,
##                                                                                                            host,
##                                                                                                            snmp_community,
##                                                                                                            snmp_version,
##                                                                                                            pid))
##                    try:
##                        act_scheme = act_scheme(net_obj=host_obj,
##                                                ret_queue=self.get_thread_queue(),
##                                                pid=pid,
##                                                options=comline_split,
##                                                init_time=init_time)
##                    except IOError:
##                        err_str = "error while creating scheme %s: %s" % (scheme,
##                                                                          process_tools.get_except_info()) 
##                        self._snmp_result((pid, init_time, limits.nag_STATE_CRITICAL, err_str, True))
##                    else:
##                        if act_scheme.get_errors():
##                            err_str = "problem in creating scheme %s: %s" % (scheme,
##                                                                             ", ".join(act_scheme.get_errors()))
##                            self._snmp_result((pid, init_time, limits.nag_STATE_CRITICAL, err_str, True))
##                        else:
##                            self._start_snmp_fetch(act_scheme)
##                else:
##                    guess_list = ", ".join(difflib.get_close_matches(scheme, self.__all_schemes.keys()))
##                    err_str = "got unknown scheme '%s'%s" % (scheme,
##                                                             ", maybe one of %s" % (guess_list) if guess_list else ", no similar scheme found")
##                    self._snmp_result((pid, init_time, limits.nag_STATE_CRITICAL, err_str, True))
##    def _snmp_result(self, (pid, init_time, ret_state, ret_str, log_it)):
##        self.__requests_served += 1
##        if not self.__requests_served % 100:
##            self.log("requests served: %d (%.2f / sec)" % (self.__requests_served,
##                                                           self.__requests_served/(time.time() - self.__start_time)))
##        if gc.garbage:
##            self.log("garbage-collecting %s (memory_usage is %s)" % (logging_tools.get_plural("object", len(gc.garbage)),
##                                                                     process_tools.beautify_mem_info()),
##                     logging_tools.LOG_LEVEL_WARN)
##            for obj in gc.garbage:
##                del obj
##            del gc.garbage[:]
##        if log_it:
##            self.log("(%d) %s" % (ret_state,
##                                  ret_str.replace("\n", "<NL>")),
##                     logging_tools.LOG_LEVEL_ERROR)
##        self._send_return_message(pid, init_time, ret_state, ret_str)
##        #new_actc = act_con(message_queue=self.__message_queue, in_data=data, init_time=init_time, size_info=(self.__glob_config["LONG_LEN"], self.__glob_config["INT_LEN"], self.__g#lob_config["LONG_LEN"], self.__glob_config["INT_LEN"]), rreq_header=self.__rreq_header, flush_queue=self.__flush_queue)#
##        #if new_actc.error:
##        #    new_actc.send_return_message(self.__logger)
##        #else:
##        #    # get and install parser
##        #    self._request_ok(new_actc)
##    def _send_return_message(self, pid, init_time, ret_state, ret_str):
##        #print "shm", self.__ret_str, self.__ret_code
##        #print "Sending ipc_return to pid %d (code %d)" % (return_pid, ret_code)
##        if global_config["VERBOSE"] > 1:
##            self.log("sending return for pid %d (state %d, %s, %s)" % (pid,
##                                                                       ret_state,
##                                                                       logging_tools.get_plural("byte", len(ret_str)),
##                                                                       logging_tools.get_diff_time_str(time.time() - init_time)))
##        idx, t_idx = (0, len(ret_str))
##        while idx <= t_idx:
##            n_idx = idx + STR_LEN - 1
##            e_idx = min(n_idx, t_idx)
##            try:
##                msg_str = struct.pack("@l3i%ds" % (e_idx - idx),
##                                      pid,
##                                      ret_state,
##                                      1 if n_idx < t_idx else 0,
##                                      e_idx - idx,
##                                      ret_str[idx : e_idx])
##            except:
##                self.log("Cannot pack ipc_return (ret_str %s, ret_code %d, pid %d, %s)" % (ret_str,
##                                                                                           ret_state,
##                                                                                           pid,
##                                                                                           process_tools.get_except_info()),
##                         logging_tools.LOG_LEVEL_ERROR)
##                break
##            else:
##                idx = n_idx
##                self.__message_queue.send(msg_str)
##        if self.__flush_queue:
##            self.__flush_queue.put(("finished", (pid, init_time)))
        
class relay_process(threading_tools.process_pool):
    def __init__(self):
        self.__verbose = global_config["VERBOSE"]
        self.__log_cache, self.__log_template = ([], None)
        threading_tools.process_pool.__init__(self, "main", zmq=True)
        self.renice()
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self.install_signal_handlers()
        self._init_msi_block()
        self._init_ipc_sockets(close_socket=True)
        self.register_exception("int_error" , self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("hup_error" , self._hup_error)
        self.register_exception("term_error", self._sigint)
        self.register_func("int_error", self._int_error)
        self.register_func("snmp_finished", self._snmp_finished)
        self.__verbose = global_config["VERBOSE"]
        self._check_msg_settings()
        self._log_config()
        self.__last_log_time = time.time() - 3600
        self._check_schemes()
        self._init_host_objects()
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
        self.log("Spawning %s" % (logging_tools.get_plural("SNMP_process", num_processes)))
        # buffer for queued_requests
        self.__queued_requests = []
        # pending schemes
        self.__pending_schemes = {}
        self.__process_dict = {}
        for idx in xrange(num_processes):
            proc_name = "SNMP_%d" % (idx)
            new_proc = snmp_process(proc_name)
            proc_socket = self.add_process(new_proc, start=True)
            self.__process_dict[proc_name] = {
                "socket"     : proc_socket,
                "call_count" : 0,
                "in_use"     : False,
                "running"    : True,
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
    def thread_exited(self, t_name, t_pid):
        process_tools.remove_pids(self.__pid_name, t_pid)
        if self.__msi_block:
            self.__msi_block.remove_actual_pid(t_pid)
            self.__msi_block.save_block()
        if t_name.startswith("snmp_"):
            self.__relay_thread_queue.put(("spawn_thread", int(t_name.split("_")[1])))
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
    def _init_ipc_sockets(self, close_socket=False):
        sock_name = process_tools.get_zmq_ipc_name("receiver")
        file_name = sock_name[5:]
        self.log("init ipc_socket '%s'" % (sock_name))
        if os.path.exists(file_name) and close_socket:
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
        client = self.zmq_context.socket(zmq.ROUTER)
        try:
            process_tools.bind_zmq_socket(client, sock_name)
            #client.bind("tcp://*:8888")
        except zmq.core.error.ZMQError:
            self.log("error binding %s: %s" % (sock_name,
                                               process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_CRITICAL)
            raise
        else:
            self.relayer_socket = client
            backlog_size = global_config["BACKLOG_SIZE"]
            os.chmod(file_name, 0777)
            self.relayer_socket.setsockopt(zmq.LINGER, 0)
            #self.relayer_socket.setsockopt(zmq.HWM, backlog_size)
            self.register_poller(client, zmq.POLLIN, self._recv_command)
        self.__num_messages = 0
    def _close_ipc_sockets(self):
        self.unregister_poller(self.relayer_socket, zmq.POLLIN)
        self.relayer_socket.close()
    def _hup_error(self, err_cause):
        # no longer needed
        #self.__relay_thread_queue.put("reload")
        pass
    def _snmp_finished(self, src_proc, src_pid, *args, **kwargs):
        proc_struct = self.__process_dict[src_proc]
        proc_struct["in_use"] = False
        envelope, error_list, received, snmp_dict = args
        cur_scheme = self.__pending_schemes[envelope]
        cur_scheme.snmp = snmp_dict
        for cur_error in error_list:
            cur_scheme.flag_error(cur_error)
        cur_scheme.snmp_end(self.log)
        if cur_scheme.return_sent:
            if cur_scheme.xml_input:
                self._send_return_xml(cur_scheme)
            else:
                ret_state, ret_str, log_it = cur_scheme.return_tuple
                self._send_return(cur_scheme.envelope, ret_state, ret_str)
        del self.__pending_schemes[envelope]
        if self.__queued_requests:
            self.log("sending request from buffer (size: %d)" % (len(self.__queued_requests)))
            self._start_snmp_fetch(self.__queued_requests.pop(0))
    def _start_snmp_fetch(self, scheme):
        free_processes = sorted([key for key, value in self.__process_dict.iteritems() if not value["in_use"] and value["running"]])
        cache_ok, num_cached, num_refresh, num_pending, num_hot_enough = scheme.pre_snmp_start(self.log)
        if self.__verbose:
            self.log("%sinfo for %s: %s" % ("[F] " if num_refresh else "[I] ",
                                            scheme.net_obj.name,
                                            ", ".join(["%d %s" % (cur_num, info_str) for cur_num, info_str in [(num_cached, "cached"),
                                                                                                               (num_refresh, "to refresh"),
                                                                                                               (num_pending, "pending"),
                                                                                                               (num_hot_enough, "hot enough")] if cur_num])))
        if num_refresh:
            if free_processes:
                proc_struct = self.__process_dict[free_processes[0]]
                proc_struct["in_use"] = True
                self.send_to_process(proc_struct["proc_name"], "fetch_snmp", *scheme.proc_data())
                self.__pending_schemes[scheme.envelope] = scheme
            else:
                self.__queued_requests.append(scheme)
                self.log("no free threads, buffering request (%d in buffer)" % (len(self.__queued_requests)),
                         logging_tools.LOG_LEVEL_WARN)
        else:
            scheme.snmp_end(self.log)
            if scheme.return_sent:
                if scheme.xml_input:
                    self._send_return_xml(scheme)
                else:
                    ret_state, ret_str, log_it = scheme.return_tuple
                    self._send_return(scheme.envelope, ret_state, ret_str)
    def _recv_command(self, zmq_sock):
        in_data = []
        while True:
            in_data.append(zmq_sock.recv())
            if not zmq_sock.getsockopt(zmq.RCVMORE):
                break
        if len(in_data) == 2:
            envelope, body = in_data
            xml_input = body.startswith("<")
            parameter_ok = False
            if xml_input:
                srv_com = server_command.srv_command(source=body)
                srv_com["result"] = {"reply" : "no reply set",
                                     "state" : server_command.SRV_REPLY_STATE_UNSET}
                try:
                    host = srv_com.xpath(None, ".//ns:host")[0].text
                    snmp_version = int(srv_com.xpath(None, ".//ns:snmp_version")[0].text)
                    snmp_community = srv_com.xpath(None, ".//ns:snmp_community")[0].text
                    comline = srv_com.xpath(None, ".//ns:command")[0].text
                except:
                    self._send_return(envelope, limits.nag_STATE_CRITICAL, "message format error: %s" % (process_tools.get_except_info()))
                else:
                    parameter_ok = True
                    if len(srv_com.xpath(None, ".//ns:arg_list/text()")):
                        comline = " ".join([comline] + srv_com.xpath(None, ".//ns:arg_list/text()")[0].strip().split())
            else:
                srv_com = None
                if body.count(";") >= 3:
                    host, snmp_version, snmp_community, comline = body.split(";", 3)
                    parameter_ok = True
            if parameter_ok:
                try:
                    snmp_version = int(snmp_version)
                    comline_split = comline.split()
                    scheme = comline_split.pop(0)
                except:
                    self._send_return(envelope, limits.nag_STATE_CRITICAL, "message format error: %s" % (process_tools.get_except_info()))
                else:
                    act_scheme = self.__all_schemes.get(scheme, None)
                    if act_scheme:
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
                        err_str = "got unknown scheme '%s'%s" % (scheme,
                                                                 ", maybe one of %s" % (guess_list) if guess_list else ", no similar scheme found")
                        self._send_return(envelope, limits.nag_STATE_CRITICAL, err_str)
            else:
                self._send_return(envelope, limits.nag_STATE_CRITICAL, "message format error")
        else:
            self.log("wrong count of input data frames: %d, first one is %s" % (len(in_data),
                                                                                in_data[0]),
                      logging_tools.LOG_LEVEL_ERROR)
    def _send_return(self, envelope, ret_state, ret_str):
        self.relayer_socket.send(envelope, zmq.SNDMORE)
        self.relayer_socket.send_unicode(u"%d\0%s" % (ret_state, ret_str))
    def _send_return_xml(self, scheme):
        self.relayer_socket.send(scheme.envelope, zmq.SNDMORE)
        self.relayer_socket.send_unicode(unicode(scheme.srv_com))
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
##    def loop_function(self):
##        if self["exit_requested"]:
##            if self.__timer_thread:
##                self.__timer_thread._event.set()
##        if self.__message_queue:
##            recv_flag = self["exit_requested"] and self.__pyipc_mod.IPC_NOWAIT or 0
##            data = self.__message_queue.receive(type=1, flags=recv_flag)
##            if not data:
##                time.sleep(0.1)
##            elif data.endswith("wakeup"):
##                pass
##            else:
##                act_time = time.time()
##                if global_config["VERBOSE"] > 0 and abs(act_time - self.__last_log_time) > DEBUG_LOG_TIME:
##                    self.__last_log_time = act_time
##                    self.log("queue statistics : %s" % (", ".join(["%s: %d of %d" % (q_name, q_struct.qsize(), q_struct.maxsize) for q_name, q_struct in
##                                                                   [("flush"  , self.__flush_queue),
##                                                                    ("relay"  , self.__relay_thread_queue)]])))
##                self.__relay_thread_queue.put(("new_ipc_request", (data, time.time())))
##        else:
##            # wait for exit
##            time.sleep(1)
##    def _force_flush_queue(self):
##        num = 0
##        if self.__message_queue:
##            while True:
##                data = self.__message_queue.receive()
##                if data:
##                    num += 1
##                else:
##                    break
##        return num
##    def thread_loop_post(self):
##        # femove message-queue
##        nflush = self._force_flush_queue()
##        try:
##            self.__pyipc_mod.removeIPC(self.__message_queue)
##        except:
##            self.log("unable to destroy the message-queue with MessageKey %d (after flushing %d messages): %s" % (global_config["IPC_SNMP_KEY"],
##                                                                                                                  nflush,
##                                                                                                                  process_tools.get_except_info()),
##                     logging_tools.LOG_LEVEL_WARN)
##        else:
##            self.log("destroyed the message-queue with MessageKey %d (%d messages flushed)" % (global_config["IPC_SNMP_KEY"], nflush))
##        try:
##            os.unlink(self.__message_key_file_name)
##        except:
##            pass
##        process_tools.delete_pid("snmp-relay/snmp-relay")
##        if self.__msi_block:
##            self.__msi_block.remove_meta_block()
    def loop_end(self):
        self._close_ipc_sockets()
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
    
class my_options(optparse.OptionParser):
    def __init__(self, glob_config):
        self.__glob_config = glob_config
        optparse.OptionParser.__init__(self,
                                       usage="%prog [GENERAL OPTIONS] [SERVER/RELAY OPTIONS] command [CLIENT OPTIONS]",
                                       add_help_option=False)
        self.add_option("-h", "--help", help="help", action="callback", callback=self.show_help)
        self.add_option("--longhelp", help="this help (long version)", action="callback", callback=self.show_help)
        self.add_option("--options", help="show internal options and flags (for dev)", action="callback", callback=self.show_help)
        self.add_option("-d", dest="daemonize", default=True, action="store_false", help="do not run in debug mode (no forking)") 
        self.add_option("-k", dest="kill_running", default=True, action="store_false", help="do not kill running instances")
        self.add_option("-v", dest="verbose", default=0, action="count", help="increase verbosity [%default]")
        self.add_option("-V", action="callback", callback=self.show_version, help="show Version")
        self.add_option("-l", dest="show_log_queue", default=False, action="store_true", help="show logging output [%default]")
        #self.add_option("-b", dest="basedir_name", type="str", default="/etc/sysconfig/snmp-relay.d", help="base name for various config files [%default]")
        self.add_option("-t", dest="main_timer", type="int", default=60, help="set main timer [%default]")
        # relayer options
        relayer_group = optparse.OptionGroup(self, "relayer options")
        relayer_group.add_option("-n", dest="ipc_key", default=0, type="int", help="key of the IPC Messagequeue (default is [%default], autoseek)")
        relayer_group.add_option("-f", dest="flood_mode", default=False, action="store_true", help="enable flood mode (faster pings, [%default])")
        self.add_option_group(relayer_group)
    def show_help(self, option, opt_str, value, *args, **kwargs):
        self.print_help()
        sys.exit(-0)
    def show_version(self, option, opt_str, value, *args, **kwargs):
        print "Version %s" % (VERSION_STRING)
        sys.exit(-0)
    def parse(self):
        options, args = self.parse_args()
        # copy options
        self.__glob_config["DAEMONIZE"]      = options.daemonize
        self.__glob_config["VERBOSE"]        = options.verbose
        self.__glob_config["IPC_SNMP_KEY"]   = int(options.ipc_key)
        self.__glob_config["MAIN_TIMER"]     = int(options.main_timer)
        self.__glob_config["BASEDIR_NAME"]   = options.basedir_name
        return options, args

global_config = configfile.get_global_config(process_tools.get_programm_name())
        
def main():
    # read global configfile
    prog_name = global_config.name()
    global_config.add_config_entries([
        ("BASEDIR_NAME"    , configfile.str_c_var("/etc/sysconfig/snmp-relay.d")),
        ("DEBUG"           , configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("VERBOSE"         , configfile.int_c_var(0)),
        ("DAEMONIZE"       , configfile.bool_c_var(True)),
        ("SNMP_PROCESSES"  , configfile.int_c_var(4, help_string="number of SNMP processes [%(default)d]", short_options="n")),
        ("MAIN_TIMER"      , configfile.int_c_var(60, help_string="main timer [%(default)d]")),
        #("IPC_SNMP_KEY"    , configfile.int_c_var(0)),
        ("KILL_RUNNING"    , configfile.bool_c_var(True)),
        ("BACKLOG_SIZE"    , configfile.int_c_var(5, help_string="backlog size for 0MQ sockets [%(default)d]")),
        ("LOG_NAME"        , configfile.str_c_var("snmp-relay")),
        ("LOG_DESTINATION" , configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("VERBOSE"         , configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ("PID_NAME"        , configfile.str_c_var("%s/%s" % (prog_name,
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
