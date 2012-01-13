#!/usr/bin/python-init -Otu
#
# Copyright (C) 2009,2010,2011 Andreas Lang-Nevyjel
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
import limits
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
import ipc_comtools

# non-critical imports
try:
    from snmp_relay_version import VERSION_STRING
except ImportError:
    VERSION_STRING = "unknown-unknown"

STR_LEN = 256
DEBUG_LOG_TIME = 15

class snmp_helper_thread(threading_tools.thread_obj):
    def __init__(self, thread_num, g_config, logger, thread_name, mother_thread_queue):
        self.__thread_num = thread_num
        self.__glob_config = g_config
        self.__logger = logger
        self.__mother_thread_queue = mother_thread_queue
        threading_tools.thread_obj.__init__(self, thread_name, queue_size=500)
        self.register_func("fetch_snmp", self._fetch_snmp)
        self._init_dispatcher()
    def oid_pretty_print(self, oids):
        return ";".join(["%s" % (".".join(["%d" % (oidp) for oidp in oid])) for oid in oids])
    def _init_dispatcher(self):
        self.log("init snmp_session object")
        self.__disp = AsynsockDispatcher()
        self.__disp.registerTransport(udp.domainName, udp.UdpSocketTransport().openClientMode())
        self.__disp.registerRecvCbFun(self._recv_func)
        self.__disp.registerTimerCbFun(self._timer_func)
    def thread_running(self):
        self.__mother_thread_queue.put(("new_pid", self.pid))
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(lev, what)
    def _fetch_snmp(self, act_scheme):
        self._set_target(act_scheme)
        self._clear_errors()
        # header value mapping mapping
        kh_list = act_scheme.snmp_start()
        for key, header_list in kh_list:
            if self.run_ok() and header_list:
                if key == "T":
                    if self.__glob_config["VERBOSE"] > 1:
                        self.log("bulk-walk tables (%s): %s" % (self.__net_obj.name, self.oid_pretty_print(header_list)))
                    self.get_tables(header_list)
                    if self.__glob_config["VERBOSE"] > 1:
                        self.log("bulk-walk tables: done")
                else:
                    if self.__glob_config["VERBOSE"] > 1:
                        self.log("get tables (%s): %s" % (self.__net_obj.name, self.oid_pretty_print(header_list)))
                    self.get_tables(header_list, single_values=True)
                    if self.__glob_config["VERBOSE"] > 1:
                        self.log("get tables: done")
                if self.run_ok():
                    if self.__glob_config["VERBOSE"] > 1:
                        self.log("(%s) for host %s (%s): %s" % (key,
                                                                self.__net_obj.name,
                                                                logging_tools.get_plural("table header", len(header_list)),
                                                                logging_tools.get_plural("result", self.num_result_values)))
                else:
                    act_scheme.flag_error("snmp timeout (OID is %s)" % (self.oid_pretty_print(header_list)))
                    self.log("(%s) run not ok for host %s (%s)" % (key,
                                                                   self.__net_obj.name,
                                                                   logging_tools.get_plural("table header", len(header_list))),
                             logging_tools.LOG_LEVEL_ERROR)
        ret_queue = self.__act_scheme.ret_queue
        # signal scheme that we are done
        act_scheme.snmp_end(self.log)
        self._unlink()
        ret_queue.put(("snmp_finished", self.name))
    def _clear_errors(self):
        self.__timed_out, self.__other_errors = (False, False)
    def _set_target(self, act_scheme):
        self.__act_scheme = act_scheme
        self.__net_obj = act_scheme.net_obj
        try:
            self.__p_mod = api.protoModules[{1 : api.protoVersion1,
                                             2 : api.protoVersion2c}[self.__net_obj.snmp_version]]
        except KeyError:
            self.log("unknown snmp_version %d, using 1" % (self.__net_obj.snmp_version), logging_tools.LOG_LEVEL_ERROR)
            self.__p_mod = api.protoModules[api.protoVersion1]
    def _unlink(self):
        # remove links
        self.__act_scheme = None
        self.__net_obj = None
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
        self.__act_domain, self.__act_address = (udp.domainName, (self.__net_obj.name, 161))
        self.__p_mod.apiPDU.setVarBinds(self.__req_pdu, [(head_var, self.__p_mod.Null("")) for head_var, max_head_var in self.__act_head_vars])
        if self.__p_mod.apiPDU.getErrorStatus(self.__req_pdu):
            self.log("Something went seriously wrong: %s" % (self.__p_mod.apiPDU.getErrorStatus(self.__req_pdu).prettyPrint()),
                    logging_tools.LOG_LEVEL_CRITICAL)
        # message
        self.__req_msg = self.__p_mod.Message()
        self.__p_mod.apiMessage.setDefaults(self.__req_msg)
        self.__p_mod.apiMessage.setCommunity(self.__req_msg, self.__net_obj.snmp_community)
        self.__p_mod.apiMessage.setPDU(self.__req_msg, self.__req_pdu)
        # anything got ?
        self.__data_got = False
        # init timer
        self.__start_time = time.time()
        self.__act_scheme.set_single_value(self.__single_values)
        self.__disp.sendMessage(encoder.encode(self.__req_msg), self.__act_domain, self.__act_address)
        self.__disp.jobStarted(True)
        try:
            self.__disp.runDispatcher()
        except:
            self.log("cannot run Dispatcher (host %s): %s" % (self.__net_obj.name,
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
                self.log("giving up for %s after %d items (timer_idx is %d)" % (self.__net_obj.name,
                                                                                self.__num_items,
                                                                                self.__timer_idx),
                         logging_tools.LOG_LEVEL_ERROR)
                trigger_timeout = True
            else:
                self.log("re-initiated get() for %s after %d items (timer_idx is %d)" % (self.__net_obj.name,
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
                                    self.__act_scheme.snmp = (tuple(act_h), tuple(name), int(value))
                                #elif isinstance(value, pyasn1.type.univ.Real):
                                #    self.__act_scheme.snmp = (tuple(act_h), tuple(name), float(value))
                                elif isinstance(value, pyasn1.type.univ.ObjectIdentifier):
                                    self.__act_scheme.snmp = (tuple(act_h), tuple(name), tuple(value))
                                else:
                                    self.__act_scheme.snmp = (tuple(act_h), tuple(name), str(value))
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


class timer_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, msi_block, logger):
        self.__glob_config  = glob_config
        self.__logger       = logger
        self.__msi_block    = msi_block
        threading_tools.thread_obj.__init__(self, "timer", queue_size=100, loop_function=self._run)
        self._event = threading.Event()
    def thread_running(self):
        self.send_pool_message(("new_pid", self.pid))
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(lev, what)
    def _run(self):
        self.log("init timer loop")
        while not self._event.is_set():
            # heartbeat
            self.__msi_block.heartbeat()
            # test message
            r_state, r_out = ipc_comtools.send_and_receive("<INTERNAL>", "test-connection", ipc_key=101, mode="snmp-relay")
            self.log("test-connection gave (%d): %s" % (r_state,
                                                        r_out),
                     limits.nag_state_to_log_level(r_state))
            self._event.wait(30)
        
    
class flush_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, message_q, logger):
        self.__glob_config  = glob_config
        self.__logger       = logger
        self.__message_queue = message_q
        threading_tools.thread_obj.__init__(self, "flush", queue_size=100)
        self.register_func("finished", self._finished)
        self.__finish_list = []
        self.__flush_counter = 0
    def thread_running(self):
        self.send_pool_message(("new_pid", self.pid))
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(lev, what)
    def _finished(self, (pid, init_time)):
        self.__finish_list.append((pid, init_time))
        self.__flush_counter = (self.__flush_counter - 1) % 10
        if not self.__flush_counter:
            act_plist = process_tools.get_process_id_list()
            act_time = time.time()
            new_flist = []
            for c_pid, init_time in self.__finish_list:
                # check if initial call is old enough (say 60 seconds)
                tdiff = act_time - init_time
                # fragment to old, clock skewed or calling process dead:
                if abs(tdiff) > 60 or c_pid not in act_plist:
                    # delete pending requests
                    num, b_len = (0, 0)
                    data = True
                    while data:
                        data = self.__message_queue.receive(type = c_pid)
                        if data:
                            b_len += len(data)
                            num += 1
                    if num:
                        self.log("flushed %s (%d bytes) for pid %d" % (logging_tools.get_plural("message fragment", num),
                                                                       b_len,
                                                                       c_pid))
                else:
                    new_flist.append((c_pid, init_time))
            self.__finish_list = new_flist

class relay_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, flush_queue, mes_queue, logger):
        self.__glob_config = glob_config
        self.__logger      = logger
        threading_tools.thread_obj.__init__(self, "relay", queue_size=100)
        self.__message_queue  = mes_queue
        self.__flush_queue    = flush_queue
        self.register_func("new_ipc_request", self._new_ipc_request)
        self.register_func("new_pid", self._new_pid)
        self.register_func("exiting", self._helper_thread_exiting)
        self.register_func("spawn_thread", self._spawn_thread)
        self.register_func("snmp_result", self._snmp_result)
        self.register_func("snmp_finished", self._snmp_finished)
        self._check_schemes()
        self._init_host_objects()
        self.__requests_served = 0
        self.__requests_pending = 0
        self.__start_time = time.time()
        self.__last_log_time = time.time() - 3600
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(lev, what)
    def thread_running(self):
        self.__net_server, self.__ping_object = (None, None)
        self.send_pool_message(("new_pid", self.pid))
        self.__glob_config.add_config_dict({"LONG_LEN" : configfile.int_c_var(struct.calcsize("@l")),
                                            "INT_LEN"  : configfile.int_c_var(struct.calcsize("@i"))})
        self._init_threads(12)
    def _new_pid(self, what):
        self.send_pool_message(("new_pid", what))
        self._send_wakeup()
    def _helper_thread_exiting(self, stuff):
        self.send_pool_message(("exiting", stuff))
        self._send_wakeup()
    def _send_wakeup(self):
        send_str = "wakeup"
        self.__message_queue.send(struct.pack("@l%ds" % (len(send_str)), 1, send_str))
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
    def _get_host_object(self, host_name, snmp_community, snmp_version):
        host_tuple = (host_name, snmp_community, snmp_version)
        if not self.__host_objects.has_key(host_tuple):
            self.__host_objects[host_tuple] = snmp_relay_schemes.net_object(self.log, self.__glob_config["VERBOSE"], host_name, snmp_community, snmp_version)
        return self.__host_objects[host_tuple]
    def _init_threads(self, num_threads):
        self.log("Spawning %s" % (logging_tools.get_plural("parser_thread", num_threads)))
        # buffer for queued_requests
        self.__queued_requests = []
        # helper threads
        self.__snmp_queues = {}
        for idx in range(num_threads):
            self._spawn_thread(idx)
    def _spawn_thread(self, idx):
        pt_name = "snmp_%d" % (idx)
        self.log("starting helper thread %s" % (pt_name))
        self.__snmp_queues[pt_name] = {"queue"      : self.get_thread_pool().add_thread(snmp_helper_thread(idx, self.__glob_config, self.__logger, pt_name, self.get_thread_queue()), start_thread=True).get_thread_queue(),
                                       "used"       : 0,
                                       "call_count" : 0,
                                       # flag if thread is running
                                       "running"    : True}
    def _parse_packed_data(self, data, (other_long_len, other_int_len, long_len, int_len)):
        header_len = other_long_len + 5 * other_int_len
        data_len = len(data)
        if data_len < header_len:
            raise ValueError, "received message with only %s (need at least %s)" % (logging_tools.get_plural("byte", data_len),
                                                                                    logging_tools.get_plural("byte", header_len))
        else:
            # not really needed any more ...
            if other_long_len == long_len:
                form_str = "@l5i"
            elif long_len == 4:
                # i am 32 bit, foreign host is 64 bit
                form_str = "@q5i"
            else:
                # i am 64 bit, foreign host is 32 bit
                form_str = "@i5i"
            datatype, pid, snmp_version, dhost_len, command_len, snmp_community_len = struct.unpack(form_str, data[0:header_len])
            host           = data[header_len             : header_len + dhost_len              ]
            full_comline   = data[header_len + dhost_len : header_len + dhost_len + command_len].strip()
            snmp_community = data[header_len + dhost_len + command_len : header_len + dhost_len + command_len + snmp_community_len].strip()
            return pid, host, snmp_version, snmp_community, full_comline
    def _snmp_finished(self, thread_name):
        ht_struct = self.__snmp_queues[thread_name]
        #self.__requests_pending -= 1
        #self.log("pending-: %d" % (self.__requests_pending))
        ht_struct["used"] -= 1
        ht_struct["call_count"] += 1
        if ht_struct["call_count"] > 100:
            self.log("removing helper_thread %s" % (thread_name))
            # flag queue as not running
            ht_struct["running"] = False
            ht_struct["queue"].put(("exit", self.get_thread_queue()))
        if self.__queued_requests:
            self.log("sending request from buffer")
            self._start_snmp_fetch(self.__queued_requests.pop(0))
    def _start_snmp_fetch(self, scheme):
        free_threads = sorted([key for key, value in self.__snmp_queues.iteritems() if not value["used"] and value["running"]])
        cache_ok, num_cached, num_refresh, num_pending, num_hot_enough = scheme.pre_snmp_start(self.log)
        if self.__glob_config["VERBOSE"] > 1:
            self.log("%sinfo for %s: %s" % ("[F] " if num_refresh else "[I] ",
                                            scheme.net_obj.name,
                                            ", ".join(["%d %s" % (cur_num, info_str) for cur_num, info_str in [(num_cached, "cached"),
                                                                                                               (num_refresh, "to refresh"),
                                                                                                               (num_pending, "pending"),
                                                                                                               (num_hot_enough, "hot enough")] if cur_num])))
        if num_refresh:
            if free_threads:
                ht_struct = self.__snmp_queues[free_threads[0]]
                ht_struct["used"] += 1
                #self.__requests_pending += 1
                #self.log("pending+: %d" % (self.__requests_pending))
                ht_struct["queue"].put(("fetch_snmp", scheme))
            else:
                self.__queued_requests.append(scheme)
                self.log("no free threads, buffering request (%d in buffer)" % (len(self.__queued_requests)),
                         logging_tools.LOG_LEVEL_WARN)
        else:
            scheme.snmp_end(self.log)
    def _new_ipc_request(self, (data, init_time)):
        act_time = time.time()
        if self.__glob_config["VERBOSE"] > 0 and abs(act_time - self.__last_log_time) > DEBUG_LOG_TIME:
            self.__last_log_time = act_time
            self.log("queue statistics : %s" % (", ".join(["%s: %d of %d" % (q_name, q_struct["queue"].qsize(), q_struct["queue"].maxsize) for q_name, q_struct in
                                                           self.__snmp_queues.iteritems() if q_struct["queue"].qsize()]) or "all empty"))
        try:
            pid, host, snmp_version, snmp_community, comline = self._parse_packed_data(data, (self.__glob_config["LONG_LEN"], self.__glob_config["INT_LEN"], self.__glob_config["LONG_LEN"], self.__glob_config["INT_LEN"]))
        except:
            self.log("error decoding ipc_request: %s" % (process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
        else:
            if host == "<INTERNAL>":
                self._snmp_result((pid, init_time, limits.nag_STATE_OK, "ok checked", False))
            else:
                host_obj = self._get_host_object(host, snmp_community, snmp_version)
                comline_split = comline.split()
                scheme = comline_split.pop(0)
                if scheme.count("/"):
                    scheme = os.path.basename(scheme)
                act_scheme = self.__all_schemes.get(scheme, None)
                if act_scheme:
                    if self.__glob_config["VERBOSE"] > 1:
                        self.log("got request for scheme %s (host %s, community %s, version %d, pid %d)" % (scheme,
                                                                                                            host,
                                                                                                            snmp_community,
                                                                                                            snmp_version,
                                                                                                            pid))
                    try:
                        act_scheme = act_scheme(net_obj=host_obj,
                                                ret_queue=self.get_thread_queue(),
                                                pid=pid,
                                                options=comline_split,
                                                init_time=init_time)
                    except IOError:
                        err_str = "error while creating scheme %s: %s" % (scheme,
                                                                          process_tools.get_except_info()) 
                        self._snmp_result((pid, init_time, limits.nag_STATE_CRITICAL, err_str, True))
                    else:
                        if act_scheme.get_errors():
                            err_str = "problem in creating scheme %s: %s" % (scheme,
                                                                             ", ".join(act_scheme.get_errors()))
                            self._snmp_result((pid, init_time, limits.nag_STATE_CRITICAL, err_str, True))
                        else:
                            self._start_snmp_fetch(act_scheme)
                else:
                    guess_list = ", ".join(difflib.get_close_matches(scheme, self.__all_schemes.keys()))
                    err_str = "got unknown scheme '%s'%s" % (scheme,
                                                             ", maybe one of %s" % (guess_list) if guess_list else ", no similar scheme found")
                    self._snmp_result((pid, init_time, limits.nag_STATE_CRITICAL, err_str, True))
    def _snmp_result(self, (pid, init_time, ret_state, ret_str, log_it)):
        self.__requests_served += 1
        if not self.__requests_served % 100:
            self.log("requests served: %d (%.2f / sec)" % (self.__requests_served,
                                                           self.__requests_served/(time.time() - self.__start_time)))
        if gc.garbage:
            self.log("garbage-collecting %s (memory_usage is %s)" % (logging_tools.get_plural("object", len(gc.garbage)),
                                                                     process_tools.beautify_mem_info()),
                     logging_tools.LOG_LEVEL_WARN)
            for obj in gc.garbage:
                del obj
            del gc.garbage[:]
        if log_it:
            self.log("(%d) %s" % (ret_state,
                                  ret_str.replace("\n", "<NL>")),
                     logging_tools.LOG_LEVEL_ERROR)
        self._send_return_message(pid, init_time, ret_state, ret_str)
        #new_actc = act_con(message_queue=self.__message_queue, in_data=data, init_time=init_time, size_info=(self.__glob_config["LONG_LEN"], self.__glob_config["INT_LEN"], self.__g#lob_config["LONG_LEN"], self.__glob_config["INT_LEN"]), rreq_header=self.__rreq_header, flush_queue=self.__flush_queue)#
        #if new_actc.error:
        #    new_actc.send_return_message(self.__logger)
        #else:
        #    # get and install parser
        #    self._request_ok(new_actc)
    def _send_return_message(self, pid, init_time, ret_state, ret_str):
        #print "shm", self.__ret_str, self.__ret_code
        #print "Sending ipc_return to pid %d (code %d)" % (return_pid, ret_code)
        if self.__glob_config["VERBOSE"] > 1:
            self.log("sending return for pid %d (state %d, %s, %s)" % (pid,
                                                                       ret_state,
                                                                       logging_tools.get_plural("byte", len(ret_str)),
                                                                       logging_tools.get_diff_time_str(time.time() - init_time)))
        idx, t_idx = (0, len(ret_str))
        while idx <= t_idx:
            n_idx = idx + STR_LEN - 1
            e_idx = min(n_idx, t_idx)
            try:
                msg_str = struct.pack("@l3i%ds" % (e_idx - idx),
                                      pid,
                                      ret_state,
                                      1 if n_idx < t_idx else 0,
                                      e_idx - idx,
                                      ret_str[idx : e_idx])
            except:
                self.log("Cannot pack ipc_return (ret_str %s, ret_code %d, pid %d, %s)" % (ret_str,
                                                                                           ret_state,
                                                                                           pid,
                                                                                           process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
                break
            else:
                idx = n_idx
                self.__message_queue.send(msg_str)
        if self.__flush_queue:
            self.__flush_queue.put(("finished", (pid, init_time)))
        
class relay_thread_pool(threading_tools.thread_pool):
    def __init__(self, glob_config, logger):
        self.__glob_config = glob_config
        self.__logger      = logger
        threading_tools.thread_pool.__init__(self, "main", blocking_loop=False)
        process_tools.save_pid("snmp-relay/snmp-relay")
        self._init_msi_block()
        self.register_exception("int_error" , self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("hup_error" , self._hup_error)
        self.register_func("new_pid", self._new_pid)
        self.register_func("int_error", self._int_error)
        self._check_msg_settings()
        self._log_config()
        self.__last_log_time = time.time() - 3600
        if not self._init_relay_key("/var/run/snmp_relay_key.ipc"):
            self._int_error("unable to create msgqueue")
        elif not api:
            self._int_error("api (SNMP) not defined (unable to create my_asynsock_dispatcher)")
        else:
            self.__flush_queue        = self.add_thread(flush_thread(self.__glob_config, self.__message_queue, self.__logger),
                                                        start_thread=True).get_thread_queue()
            self.__relay_thread_queue = self.add_thread(relay_thread(self.__glob_config, self.__flush_queue, self.__message_queue, self.__logger),
                                                        start_thread=True).get_thread_queue()
            if self.__msi_block:
                self.__timer_thread = timer_thread(self.__glob_config, self.__msi_block, self.__logger)
                self.add_thread(self.__timer_thread, start_thread=True)
            else:
                self.__timer_thread = None
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(lev, what)
    def _log_config(self):
        self.log("Basic turnaround-time is %d seconds" % (self.__glob_config["MAIN_TIMER"]))
        self.log("basedir_name is '%s'" % (self.__glob_config["BASEDIR_NAME"]))
        self.log("Config info:")
        for line, log_level in self.__glob_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = self.__glob_config.get_config_info()
        self.log("Found %d valid config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def _init_msi_block(self):
        if self.__glob_config["DAEMONIZE"]:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("snmp-relay")
            msi_block.add_actual_pid()
            msi_block.start_command = "/etc/init.d/snmp-relay start"
            msi_block.stop_command ="/etc/init.d/snmp-relay force-stop"
            msi_block.kill_pids = True
            msi_block.heartbeat_timeout = 120
            msi_block.save_block()
        else:
            msi_block = None
        self.__msi_block = msi_block
    def thread_exited(self, t_name, t_pid):
        process_tools.remove_pids("snmp-relay/snmp-relay", t_pid)
        if self.__msi_block:
            self.__msi_block.remove_actual_pid(t_pid)
            self.__msi_block.save_block()
        if t_name.startswith("snmp_"):
            self.__relay_thread_queue.put(("spawn_thread", int(t_name.split("_")[1])))
    def _new_pid(self, new_pid):
        self.log("received new_pid message")
        process_tools.append_pids("snmp-relay/snmp-relay", new_pid)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(new_pid)
            self.__msi_block.save_block()
    def _int_error(self, err_cause):
        self.log("_int_error() called, cause %s" % (str(err_cause)), logging_tools.LOG_LEVEL_WARN)
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True
    def _hup_error(self, err_cause):
        # no longer needed
        #self.__relay_thread_queue.put("reload")
        pass
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
    def _init_relay_key(self, key_f_name):
        self.__message_key_file_name = key_f_name
        success = False
        self.__message_queue = None
        try:
            import pyipc
        except:
            self.log("Cannot load pyipc-module: %s" % (process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_CRITICAL)
            return success
        else:
            self.__pyipc_mod = pyipc
        try:
            old_key = int(file(key_f_name, "r").read().split("\n")[0].strip())
        except:
            pass
        else:
            try:
                message_q = pyipc.MessageQueue(old_key)
            except:
                self.log("Can't create MessageQueue with with old key %d" % (old_key),
                         logging_tools.LOG_LEVEL_WARN)
            else:
                pyipc.removeIPC(message_q)
        if self.__glob_config["IPC_SNMP_KEY"] > 0:
            try:
                message_q = pyipc.MessageQueue(self.__glob_config["IPC_SNMP_KEY"], pyipc.IPC_CREAT | 0666)
            except:
                self.log("Can't allocate given IPC MessageKey %d" % (self.__glob_config["IPC_SNMP_KEY"]),
                         logging_tools.LOG_LEVEL_CRITICAL)
                ret_code = limits.nag_STATE_CRITICAL
            else:
                self.__message_queue = message_q
                success = True
        else:
            # auto-allocate message-queue
            first_key = 101
            last_key = 2000
            for act_key in xrange(first_key, last_key):
                try:
                    message_q = pyipc.MessageQueue(act_key, 0666)
                except:
                    try:
                        message_q = pyipc.MessageQueue(act_key, pyipc.IPC_CREAT | 0666)
                    except:
                        try:
                            pyipc.removeIPC(message_q)
                        except:
                            pass
                    else:
                        self.__glob_config["IPC_SNMP_KEY"] = act_key
                else:
                    self.__glob_config["IPC_SNMP_KEY"] = act_key
                if self.__glob_config["IPC_SNMP_KEY"] > 0:
                    success = True
                    self.__message_queue = message_q
                    break
            if not self.__glob_config["IPC_SNMP_KEY"]:
                self.log("Can't allocate an IPC MessageQueue in the key range [ %d : %d ]" % (first_key, last_key), logging_tools.LOG_LEVEL_CRITICAL)
        if success:
            # write relay-key
            # at first, delete it if possible
            if os.path.isfile(key_f_name):
                try:
                    os.unlink(key_f_name)
                except:
                    self.log("Error unlinking %s: %s" % (key_f_name,
                                                         process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
            # now (re-)create it
            try:
                file(key_f_name, "w").write("%d\n" % (self.__glob_config["IPC_SNMP_KEY"]))
            except:
                self.log("Can't write IPC MessageQueue-key %d to file %s: %s" % (self.__glob_config["IPC_SNMP_KEY"],
                                                                                 key_f_name,
                                                                                 process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                self.log("wrote IPC MessageQueue-key %d to file %s" % (self.__glob_config["IPC_SNMP_KEY"], key_f_name))
            if self.__glob_config["VERBOSE"]:
                self.log("allocated IPC MessageQueue with key %d" % (self.__glob_config["IPC_SNMP_KEY"]))
        return success
    def loop_function(self):
        if self["exit_requested"]:
            if self.__timer_thread:
                self.__timer_thread._event.set()
        if self.__message_queue:
            recv_flag = self["exit_requested"] and self.__pyipc_mod.IPC_NOWAIT or 0
            data = self.__message_queue.receive(type=1, flags=recv_flag)
            if not data:
                time.sleep(0.1)
            elif data.endswith("wakeup"):
                pass
            else:
                act_time = time.time()
                if self.__glob_config["VERBOSE"] > 0 and abs(act_time - self.__last_log_time) > DEBUG_LOG_TIME:
                    self.__last_log_time = act_time
                    self.log("queue statistics : %s" % (", ".join(["%s: %d of %d" % (q_name, q_struct.qsize(), q_struct.maxsize) for q_name, q_struct in
                                                                   [("flush"  , self.__flush_queue),
                                                                    ("relay"  , self.__relay_thread_queue)]])))
                self.__relay_thread_queue.put(("new_ipc_request", (data, time.time())))
        else:
            # wait for exit
            time.sleep(1)
    def _force_flush_queue(self):
        num = 0
        if self.__message_queue:
            while True:
                data = self.__message_queue.receive()
                if data:
                    num += 1
                else:
                    break
        return num
    def thread_loop_post(self):
        # femove message-queue
        nflush = self._force_flush_queue()
        try:
            self.__pyipc_mod.removeIPC(self.__message_queue)
        except:
            self.log("unable to destroy the message-queue with MessageKey %d (after flushing %d messages): %s" % (self.__glob_config["IPC_SNMP_KEY"],
                                                                                                                  nflush,
                                                                                                                  process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("destroyed the message-queue with MessageKey %d (%d messages flushed)" % (self.__glob_config["IPC_SNMP_KEY"], nflush))
        try:
            os.unlink(self.__message_key_file_name)
        except:
            pass
        process_tools.delete_pid("snmp-relay/snmp-relay")
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
        self.add_option("-b", dest="basedir_name", type="str", default="/etc/sysconfig/snmp-relay.d", help="base name for various config files [%default]")
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
        
def main():
    # read global configfile
    glob_config = configfile.configuration("snmprelay", {"BASEDIR_NAME"    : configfile.str_c_var("/etc/sysconfig/snmp-relay.d"),
                                                         "VERBOSE"         : configfile.int_c_var(0),
                                                         "DAEMONIZE"       : configfile.bool_c_var(True),
                                                         "MAIN_TIMER"      : configfile.int_c_var(60),
                                                         "IPC_SNMP_KEY"    : configfile.int_c_var(0),
                                                         "PROGRAM_NAME"    : configfile.str_c_var("not set"),
                                                         "LONG_HOST_NAME"  : configfile.str_c_var("not set"),
                                                         "LOG_NAME"        : configfile.str_c_var("snmp-relay"),
                                                         "LOG_DESTINATION" : configfile.str_c_var("uds:/var/lib/logging-server/py_log")})
    glob_config.parse_file("/etc/sysconfig/snmp-relay")
    glob_config["LONG_HOST_NAME"] = socket.getfqdn(socket.gethostname())
    glob_config["PROGRAM_NAME"] = os.path.basename(sys.argv[0])
    loc_options, loc_args = my_options(glob_config).parse()
    # determine module_path
    logger = logging_tools.get_logger(glob_config["LOG_NAME"],
                                      glob_config["LOG_DESTINATION"],
                                      init_logger=True)
    if loc_options.kill_running:
        process_tools.kill_running_processes(glob_config["PROGRAM_NAME"])
    handledict = {"out"    : (1, "snmp-relay.out"),
                  "err"    : (0, "/var/lib/logging-server/py_err"),
                  "strict" : 0}
    process_tools.renice()
    if glob_config["DAEMONIZE"]:
        process_tools.become_daemon()
        hc_ok = process_tools.set_handles(handledict)
    else:
        hc_ok = 1
        print "Debugging snmp-relayer"
    if hc_ok:
        thread_pool = relay_thread_pool(glob_config, logger)
        thread_pool.thread_loop()
        ret_code = limits.nag_STATE_OK
    else:
        print "Cannot modify handles, exiting..."
        ret_code = limits.nag_STATE_CRITICAL
    if glob_config["DAEMONIZE"] and hc_ok != 2:
        process_tools.handles_write_endline()
    logger.info("CLOSE")
    sys.exit(ret_code)

if __name__ == "__main__":
    main()
