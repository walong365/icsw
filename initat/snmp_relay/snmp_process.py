# Copyright (C) 2009-2014 Andreas Lang-Nevyjel
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
"""
SNMP relayer, SNMP process
used by
 o mother
 o collectd-init
 o discovery-server
"""

from pyasn1.codec.ber import encoder, decoder  # @UnresolvedImport
from pyasn1.type.error import ValueConstraintError  # @UnresolvedImport
from pysnmp.carrier.asynsock.dgram import udp  # @UnresolvedImport
from pysnmp.carrier.asynsock.dispatch import AsynsockDispatcher  # @UnresolvedImport
from pysnmp.proto import rfc1155, rfc1902, api  # @UnresolvedImport
from pysnmp.smi import exval  # @UnresolvedImport
import logging_tools
import os
import pprint  # @UnusedImport
import process_tools
import pyasn1  # @UnresolvedImport
import signal
import threading_tools
import time
import zmq

# --- hack Counter type, from http://pysnmp.sourceforge.net/faq.html


def counter_clone_hack(self, *args):
    if args and args[0] < 0:
        args = (0xffffffff + args[0] - 1,) + args[1:]

    return self.__class__(*args)

rfc1155.TimeTicks.clone = counter_clone_hack
rfc1902.TimeTicks.clone = counter_clone_hack
rfc1155.Counter.clone = counter_clone_hack
rfc1902.Counter32.clone = counter_clone_hack

DEFAULT_RETURN_NAME = "main"


def simplify_dict(in_dict, start_tuple):
    # check in_dict for all keys starting with start_tuple and return a reordered dict for faster
    # processing
    _slist = list(start_tuple)
    # get all valid keys
    _ref_keys = set([_key for _key in in_dict.iterkeys() if list(_key)[:len(start_tuple)] == _slist])
    # the last entry is the reference idx
    _result = {}
    for _key in _ref_keys:
        _s_key = _key[len(start_tuple):]
        if len(_s_key) == 2:
            # integer as key
            _result.setdefault(_s_key[1], {})[_s_key[0]] = in_dict[_key]
        elif _s_key:
            # tuple as key
            _result.setdefault(tuple(list(_s_key[1:])), {})[_s_key[0]] = in_dict[_key]
        else:
            _result[None] = in_dict[_key]
    return _result


def flatten_dict(in_dict):
    _changed = True
    while _changed:
        _changed = False
        if len(in_dict) == 1:
            in_dict = in_dict.values()[0]
        _r_dict = {}
        for _key, _value in in_dict.iteritems():
            if type(_value) == dict:
                _changed = True
                if type(_key) in [int, long]:
                    _key = [_key]
                else:
                    _key = list(_key)
                for _s_key, _s_value in _value.iteritems():
                    if type(_s_key) in [int, long]:
                        _s_key = _key + [_s_key]
                    else:
                        _s_key = _key + list(_s_key)
                    _r_dict[tuple(_s_key)] = _s_value
            else:
                _r_dict[_key] = _value
        in_dict = _r_dict
    return _r_dict


class snmp_process_container(object):
    def __init__(self, mq_name, log_com, max_procs, max_snmp_jobs, conf_dict, event_dict):
        # name of return queue
        self.mq_name = mq_name
        self.log_com = log_com
        self.max_procs = max_procs
        self.max_snmp_jobs = max_snmp_jobs
        self.conf_dict = conf_dict
        self.__event_dict = event_dict
        self.pid = os.getpid()
        self.__run_flag = True
        self.__snmp_dict = {}
        self.__used_proc_ids = set()
        self._socket = None
        self.log("init with a maximum of {:d} processes ({:d} jobs per process)".format(self.max_procs, self.max_snmp_jobs))
        self.log("{} in default config dict:".format(logging_tools.get_plural("key", len(self.conf_dict))))
        for _key in sorted(self.conf_dict):
            self.log("  {}={}".format(_key, self.conf_dict[_key]))

    def create_ipc_socket(self, zmq_context, socket_addr, socket_name=DEFAULT_RETURN_NAME):
        self._socket = zmq_context.socket(zmq.ROUTER)  # @UndefinedVariable
        self._socket.setsockopt(zmq.IDENTITY, socket_name)  # @UndefinedVariable
        self._socket.setsockopt(zmq.IMMEDIATE, True)  # @UndefinedVariable
        self._socket.setsockopt(zmq.ROUTER_MANDATORY, True)  # @UndefinedVariable
        self._socket.bind(socket_addr)
        return self._socket

    def close(self):
        self._socket.close()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.log_com(u"[spc] {}".format(what), log_level)

    def check(self):
        cur_running = self.__snmp_dict.keys()
        to_start = self.max_procs - len(cur_running)
        if to_start:
            min_idx = 1 if not self.__snmp_dict else max(self.__snmp_dict.keys()) + 1
            self.log(
                "starting {} (starting at {:d})".format(
                    logging_tools.get_plural("SNMP process", to_start),
                    min_idx,
                )
            )
            _npid = 1
            for new_idx in xrange(min_idx, min_idx + to_start):
                while _npid in self.__used_proc_ids:
                    _npid += 1
                self.__used_proc_ids.add(_npid)
                cur_struct = {
                    "npid": _npid,
                    "name": "snmp_{:d}".format(new_idx),
                    "msi_name": "snmp_{:d}".format(_npid),
                    "proc": snmp_process("snmp_{:d}".format(new_idx), self.conf_dict, ignore_signals=True),
                    "running": False,
                    "stopping": False,
                    "stopped": False,
                    "jobs": 0,
                    "pending": 0,
                    "done": 0,
                }
                cur_struct["proc"].main_queue_name = self.mq_name
                cur_struct["proc"].start()
                self.__snmp_dict[new_idx] = cur_struct

    def get_free_snmp_id(self):
        # code from old snmp-relay:
        # free_processes = sorted([(value["calls_init"], key) for key, value in self.__process_dict.iteritems() if value["state"] == "running"])
        idle_procs = sorted(
            [
                (value["jobs"], key) for key, value in self.__snmp_dict.iteritems() if not value["stopped"] and not value["pending"] and not value["stopping"]
            ]
        )
        running_procs = sorted(
            [
                (value["jobs"], key) for key, value in self.__snmp_dict.iteritems() if not value["stopped"] and value["pending"] and not value["stopping"]
            ]
        )
        if idle_procs:
            proc_id = idle_procs[0][1]
        else:
            proc_id = running_procs[0][1]
        return proc_id

    def stop(self):
        # stop all snmp process and stop spawning new ones
        self.__run_flag = False
        for _key, value in self.__snmp_dict.iteritems():
            if value["running"] and not value["stopped"]:
                self.send(value["name"], "exit")
        if not self.__snmp_dict:
            self._event("all_stopped")

    def get_usage(self):
        return "process usage (init/done): {}".format(
            ", ".join(
                [
                    "{:d}/{:d}".format(
                        self.__snmp_dict[key]["jobs"],
                        self.__snmp_dict[key]["done"],
                    ) for key in sorted(self.__snmp_dict.iterkeys())
                ]
            )
        )

    def start_batch(self, vers, ip, com, batch_id, single_key_transform, timeout, *oid_list, **kwargs):
        # see proc_data in snmp_relay_schemes
        snmp_id = self.get_free_snmp_id()
        self.__snmp_dict[snmp_id]["jobs"] += 1
        self.__snmp_dict[snmp_id]["pending"] += 1
        self.send("snmp_{:d}".format(snmp_id), "fetch_snmp", vers, ip, com, batch_id, single_key_transform, timeout, *oid_list, VERBOSE=0, **kwargs)

    def send(self, target, m_type, *args, **kwargs):
        _iter = 0
        while True:
            _iter += 1
            try:
                self._socket.send_unicode(target, zmq.SNDMORE)  # @UndefinedVariable
                self._socket.send_pyobj({
                    "pid": self.pid,
                    "type": m_type,
                    "args": args,
                    "kwargs": kwargs,
                })
            except zmq.error.ZMQError:
                _iter += 1
                time.sleep(0.1)
                if _iter > 10:
                    logging_tools.my_syslog("unable to send to {}".format(target))
            else:
                break

    def _event(self, ev_name, *args, **kwargs):
        if ev_name in self.__event_dict:
            self.__event_dict[ev_name](*args, **kwargs)
        else:
            self.log("no event with name {}".format(ev_name), logging_tools.LOG_LEVEL_ERROR)

    def handle_with_socket(self, _sock):
        self.handle()

    def handle(self):
        # handle results
        src_proc = self._socket.recv_unicode()
        snmp_idx = int(src_proc.split("_")[1])
        data = self._socket.recv_pyobj()
        if data["type"] == "process_start":
            self.__snmp_dict[snmp_idx]["running"] = True
            self._event(
                "process_start",
                pid=data["pid"],
                mult=3,
                process_name=self.__snmp_dict[snmp_idx]["msi_name"],
                fuzzy_ceiling=3
            )
        elif data["type"] == "process_exit":
            self.log("SNMP process {:d} stopped (PID={:d})".format(snmp_idx, data["pid"]), logging_tools.LOG_LEVEL_WARN)
            self.__snmp_dict[snmp_idx]["stopped"] = True
            self.__used_proc_ids.remove(self.__snmp_dict[snmp_idx]["npid"])
            # self.log(str(self.__used_proc_ids))
            self.__snmp_dict[snmp_idx]["proc"].join()
            del self.__snmp_dict[snmp_idx]
            self._event(
                "process_exit",
                pid=data["pid"],
                mult=3,
            )
            if self.__run_flag:
                # spawn new processes
                self.check()
            else:
                if not self.__snmp_dict:
                    self.log("all SNMP processes stopped")
                    self._event("all_stopped")
        elif data["type"] == "snmp_finished":
            self.__snmp_dict[snmp_idx]["pending"] -= 1
            self.__snmp_dict[snmp_idx]["done"] += 1
            self._event("finished", data)
            if self.__snmp_dict[snmp_idx]["jobs"] > self.max_snmp_jobs:
                self.__snmp_dict[snmp_idx]["stopping"] = True
                self.log(
                    "stopping SNMP process {:d} ({:d} > {:d})".format(
                        snmp_idx,
                        self.__snmp_dict[snmp_idx]["jobs"],
                        self.max_snmp_jobs,
                    )
                )
                self.send("snmp_{:d}".format(snmp_idx), "exit")
        else:
            self.log("unknown type {} from {}".format(data["type"], src_proc), logging_tools.LOG_LEVEL_ERROR)


class simple_snmp_oid(object):
    def __init__(self, *oid, **kwargs):
        self._target_value = kwargs.get("target_value", None)
        if type(oid[0]) in [tuple, list] and len(oid) == 1:
            oid = oid[0]
        if type(oid) == tuple and len(oid) == 1 and isinstance(oid[0], basestring):
            oid = oid[0]
        # store oid in tuple-form
        if isinstance(oid, basestring):
            self._oid = tuple([int(val) for val in oid.split(".")])
        else:
            self._oid = oid
        self._oid_len = len(self._oid)
        self._str_oid = ".".join(["{:d}".format(i_val) if type(i_val) in [int, long] else i_val for i_val in self._oid])

    def has_max_oid(self):
        return False

    def __str__(self):
        return self._str_oid

    def __repr__(self):
        return "OID {}".format(self._str_oid)

    def __iter__(self):
        # reset iteration idx
        self.__idx = -1
        return self

    def next(self):
        self.__idx += 1
        if self.__idx == self._oid_len:
            raise StopIteration
        else:
            return self._oid[self.__idx]

    def get_value(self, p_mod):
        if self._target_value is not None:
            if isinstance(self._target_value, basestring):
                return p_mod.OctetString(self._target_value)
            elif type(self._target_value) in [int, long]:
                return p_mod.Integer(self._target_value)
            else:
                return p_mod.Null("")
        else:
            return p_mod.Null("")

    def as_tuple(self):
        return self._oid


class snmp_batch(object):
    batch_key = 0

    def __init__(self, proc, *scheme_data, **kwargs):
        snmp_batch.batch_key += 1
        self.key = snmp_batch.batch_key
        self.proc = proc
        snmp_ver, snmp_host, snmp_community, self.envelope, self.transform_single_key, self.__timeout = scheme_data[0:6]
        self.__verbose = kwargs.pop("VERBOSE", False)
        self.__simplify_result = kwargs.get("simplify_result", False)
        self._clear_errors()
        self._set_target(snmp_ver, snmp_host, snmp_community)
        if self.__verbose > 2:
            self.log("init SNMP_batch for {} (V{:d})".format(snmp_host, snmp_ver))
        self.kh_list = scheme_data[6:]
        self.iterator = self.loop()
        self.proc.register_batch(self)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.proc.log("[b {:d}, {}] {}".format(self.key, self.__snmp_host, what), log_level)

    def _clear_errors(self):
        self.__received, self.__snmp_dict = (set(), {})
        self.__timed_out, self.__other_errors, self.__error_list = (False, False, [])

    def _set_target(self, snmp_ver, snmp_host, snmp_community):
        self.__snmp_ver, self.__snmp_host, self.__snmp_community = (snmp_ver, snmp_host, snmp_community)
        try:
            self.__p_mod = api.protoModules[
                {
                    1: api.protoVersion1,
                    2: api.protoVersion2c
                }[self.__snmp_ver]
            ]
        except KeyError:
            self.log("unknown snmp_version {:d}, using 1".format(self.__snmp_ver), logging_tools.LOG_LEVEL_ERROR)
            self.__p_mod = api.protoModules[api.protoVersion1]

    def run_ok(self):
        return not self.__timed_out and not self.__other_errors

    def oid_pretty_print(self, oids):
        return ";".join([unicode(oid) for oid in oids])

    def add_error(self, err_str):
        self.__error_list.append(err_str)

    def loop(self):
        for key, header_list in self.kh_list:
            if self.run_ok() and header_list:
                # header_list has to be a list
                if key == "T":
                    # get table (bulk)
                    if self.__verbose > 1:
                        self.log("bulk-walk tables ({}): {}".format(self.__snmp_host, self.oid_pretty_print(header_list)))
                    yield self.get_tables(header_list)
                    if self.__verbose > 1:
                        self.log("bulk-walk tables: done")
                elif key == "T*":
                    # get table (bulk)
                    if self.__verbose > 1:
                        self.log("bulk-walk tables test ({}): {}".format(self.__snmp_host, self.oid_pretty_print(header_list)))
                    yield self.get_tables(header_list, stop_after_first=True)
                    if self.__verbose > 1:
                        self.log("bulk-walk tables test: done")
                    for _head in header_list:
                        if _head.as_tuple() not in self.__snmp_dict:
                            self.add_error("oid {} gave no results".format(unicode(_head)))
                elif key == "S":
                    # set value, header_list is now a list of (mib, value) tuples
                    if self.__verbose > 1:
                        self.log("set mib ({}): {}".format(self.__snmp_host, self.oid_pretty_print(header_list)))
                    yield self.get_tables(header_list, set=True)
                    if self.__verbose > 1:
                        self.log("set mib: done")
                else:
                    # get table, single walk
                    if self.__verbose > 1:
                        self.log("get tables ({}): {}".format(self.__snmp_host, self.oid_pretty_print(header_list)))
                    yield self.get_tables(header_list, single_values=True)
                    if self.__verbose > 1:
                        self.log("get tables: done")
                if self.run_ok():
                    if self.__verbose > 1:
                        self.log(
                            "({}) for host {} ({}): {}".format(
                                key,
                                self.__snmp_host,
                                logging_tools.get_plural("table header", len(header_list)),
                                logging_tools.get_plural("result", self.num_result_values)
                            )
                        )
                else:
                    self.add_error(
                        "snmp timeout ({:d} secs, OID is {})".format(
                            self.__timeout,
                            self.oid_pretty_print(header_list)
                        )
                    )
                    self.log(
                        "({}) run not ok for host {} ({})".format(
                            key,
                            self.__snmp_host,
                            logging_tools.get_plural("table header", len(header_list))
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )

    def finish(self):
        if self.__verbose > 2:
            self.log("finish() called")
        # empty iterator to remove references
        for _v in self.iterator:
            pass
        self.proc.unregister_batch(self)
        _res = self.snmp
        if len(self.__received) == 1 and self.__received == set(self.snmp.keys()) and self.__simplify_result:
            _res = _res[list(self.__received)[0]]
        self.proc.send_return(self.envelope, self.__error_list, self.__received, _res)

    def __del__(self):
        if self.__verbose > 3:
            self.log("__del__")

    def get_tables(self, base_oids, **kwargs):
        self._set = kwargs.get("set", False)
        self._stop_after_first = kwargs.get("stop_after_first", False)
        # table header
        self.__head_vars = [self.__p_mod.ObjectIdentifier(base_oid) for base_oid in base_oids]
        self.__max_head_vars = [self.__p_mod.ObjectIdentifier(base_oid.get_max_oid()) if base_oid.has_max_oid() else None for base_oid in base_oids]
        # actual header vars
        self.__act_head_vars = [(header, max_header) for header, max_header in zip(self.__head_vars, self.__max_head_vars)]
        # numer of result values
        self.num_result_values = 0
        # timeout is being set by snmp_scheme.scheme_data
        # self.__timeout = kwargs.get("timeout", 30)
        # max items
        self.__max_items = kwargs.get("max_items", 0)
        self.__num_items = 0
        # who many times the timer_func was called
        self.__timer_count = 0
        self.__single_values = kwargs.get("single_values", False)
        if self._set:
            self.__req_pdu = self.__p_mod.SetRequestPDU()
        elif self.__single_values:
            # PDU for single values
            self.__req_pdu = self.__p_mod.GetRequestPDU()
        else:
            # PDU for multiple values
            self.__req_pdu = self.__p_mod.GetNextRequestPDU()
        self.__p_mod.apiPDU.setDefaults(self.__req_pdu)
        self.__next_names = [value for value, _max_value in self.__act_head_vars]
        self.__act_domain, self.__act_address = (udp.domainName, (self.__snmp_host, 161))
        if self._set:
            self.__p_mod.apiPDU.setVarBinds(
                self.__req_pdu,
                [
                    (head_var, base_oid.get_value(self.__p_mod)) for (head_var, _max_head_var), base_oid in zip(self.__act_head_vars, base_oids)
                ]
            )
        else:
            self.__p_mod.apiPDU.setVarBinds(
                self.__req_pdu,
                [
                    (head_var, self.__p_mod.Null("")) for head_var, _max_head_var in self.__act_head_vars
                ]
            )
        if self.__p_mod.apiPDU.getErrorStatus(self.__req_pdu):
            self.log(
                "Something went seriously wrong: {}".format(self.__p_mod.apiPDU.getErrorStatus(self.__req_pdu).prettyPrint()),
                logging_tools.LOG_LEVEL_CRITICAL
            )
        # message
        self.__req_msg = self.__p_mod.Message()
        self.__p_mod.apiMessage.setDefaults(self.__req_msg)
        self.__p_mod.apiMessage.setCommunity(self.__req_msg, self.__snmp_community)
        self.__p_mod.apiMessage.setPDU(self.__req_msg, self.__req_pdu)
        # anything got ?
        self.__data_got = False
        # init timer, start of action
        self.__start_time = time.time()
        # start of init get
        self.__start_get_time = time.time()
        # self.__single_value = self.__single_values
        # self.__act_scheme.set_single_value(self.__single_values)
        # self.__disp.sendMessage(encoder.encode(self.__req_msg), self.__act_domain, self.__act_address)
        self.request_id = self.__p_mod.apiPDU.getRequestID(self.__req_pdu)
        return encoder.encode(self.__req_msg), self.__act_domain, self.__act_address

    @property
    def snmp(self):
        return self.__snmp_dict

    @snmp.setter
    def snmp(self, in_value):
        header, key, value = in_value
        # if header in self.__waiting_for:
        self.__received.add(header)
        if self.__single_values:
            self.__snmp_dict[header] = value
        else:
            if self.transform_single_key and len(key) == 1:
                key = key[0]
            self.__snmp_dict.setdefault(header, {})[key] = value

    def feed_pdu(self, disp, domain, address, rsp_pdu):
        self.__data_got = True
        terminate = False
        next_headers, next_names = ([], [])
        # Check for SNMP errors reported
        error_status = self.__p_mod.apiPDU.getErrorStatus(rsp_pdu)
        if error_status:
            self.log("SNMP error_status: {}".format(self.__p_mod.apiPDU.getErrorStatus(rsp_pdu).prettyPrint()),
                     logging_tools.LOG_LEVEL_WARN)
            if error_status not in [2]:
                self.__other_errors = True
            terminate = True
        else:
            # Format var-binds table
            var_bind_table = self.__p_mod.apiPDU.getVarBindTable(self.__req_pdu, rsp_pdu)
            # Report SNMP table
            if len(var_bind_table) != 1:
                print("*** length of var_bind_table != 1 ***")
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
                        if isinstance(value, pyasn1.type.univ.Integer):  # @UndefinedVariable
                            self.snmp = (tuple(act_h), tuple(name), int(value))
                        # elif isinstance(value, pyasn1.type.univ.Real):
                        #    self.snmp = (tuple(act_h), tuple(name), float(value))
                        elif isinstance(value, pyasn1.type.univ.ObjectIdentifier):  # @UndefinedVariable
                            self.snmp = (tuple(act_h), tuple(name), tuple(value))
                        else:
                            self.snmp = (tuple(act_h), tuple(name), str(value))
                        if self._stop_after_first:
                            terminate = True
                        self.num_result_values += 1
                self.__num_items += 1
                if self.__max_items and self.__num_items > self.__max_items:
                    terminate = True
            # Stop on EOM
            if not terminate:
                for _oid, val in var_bind_table[-1]:
                    # continue when val is not None and mode==SET is active
                    if (val is not None) and not self._set:
                        terminate = False
                        break
                else:
                    terminate = True
        # Generate request for next row
        # print(self.__timed_out, next_names, terminate, self.__single_values)
        if abs(time.time() - self.__start_time) > self.__timeout:
            self.__timed_out = True
        else:
            self.__start_time = time.time()
        if not self.__timed_out and next_names and not terminate and not self.__single_values:
            self.__act_head_vars, self.__next_names = (next_headers, next_names)
            self.__act_domain, self.__act_address = (domain, address)
            self._next_send()
            # self.proc._inject(self)
        else:
            self.proc._inject(self)

    def _next_send(self):
        # not working for set-requests, FIXME
        self.__p_mod.apiPDU.setVarBinds(self.__req_pdu, [(var_x, self.__p_mod.Null("")) for var_x in self.__next_names])
        self.__p_mod.apiPDU.setRequestID(self.__req_pdu, self.__p_mod.getNextRequestID())
        self.request_id = self.__p_mod.apiPDU.getRequestID(self.__req_pdu)
        self.proc.send_next(self, (encoder.encode(self.__req_msg), self.__act_domain, self.__act_address))
        # self.__disp.sendMessage(encoder.encode(self.__req_msg), self.__act_domain, self.__act_address)

    def timer_func(self, act_time):
        diff_time = int(abs(act_time - self.__start_time))
        trigger_timeout = False
        if not self.__data_got and self.__timer_count:  # and diff_time > self.__timeout / 2:
            if not self.__num_items and diff_time > self.__timeout:
                self.log(
                    "giving up for {} after {:d} items ({:d} seconds, timer_count is {:d})".format(
                        self.__snmp_host,
                        self.__num_items,
                        diff_time,
                        self.__timer_count
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
                trigger_timeout = True
            elif abs(act_time - self.__start_get_time) > self.__timeout / 2:
                # trigger a re-get
                self.__start_get_time = act_time
                self.log(
                    "re-initiated get() for {} after {} ({:d} seconds, timer_count is {:d})".format(
                        self.__snmp_host,
                        logging_tools.get_plural("item", self.__num_items),
                        diff_time,
                        self.__timer_count
                    ),
                    logging_tools.LOG_LEVEL_WARN
                )
                self._next_send()
        self.__timer_count += 1
        # reset trigger
        self.__data_got = False
        if abs(diff_time) > self.__timeout or trigger_timeout:
            self.log("triggered timeout after {:d} seconds".format(diff_time), logging_tools.LOG_LEVEL_ERROR)
            self.__timed_out = True
            return True
        else:
            return False


class snmp_process(threading_tools.process_obj):
    def __init__(self, name, conf_dict, **kwargs):
        self.__snmp_name = name
        self.__log_name, self.__log_destination = (
            conf_dict["LOG_NAME"],
            conf_dict["LOG_DESTINATION"],
        )
        self.__verbose = conf_dict.get("VERBOSE", False)
        self.debug_zmq = conf_dict.get("DEBUG_ZMQ", False)
        threading_tools.process_obj.__init__(self, name, busy_loop=True)
        if kwargs.get("ignore_signals", False):
            signal.signal(signal.SIGTERM, signal.SIG_IGN)

    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            self.__log_name,
            self.__log_destination,
            zmq=True,
            context=self.zmq_context)
        self.__return_proc_name = None
        self.register_func("fetch_snmp", self._fetch_snmp)
        self.register_func("register_return", self._register_return)
        self._init_dispatcher()
        self.__job_dict = {}
        self.__req_id_lut = {}

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def _init_dispatcher(self):
        self.log("init snmp_session object")
        self.__disp = AsynsockDispatcher()
        self.__disp.registerTransport(udp.domainName, udp.UdpSocketTransport().openClientMode())
        self.__disp.registerRecvCbFun(self._recv_func)
        self.__disp.registerTimerCbFun(self._timer_func)
        self.v1_decoder = api.protoModules[api.protoVersion1]
        self.v2c_decoder = api.protoModules[api.protoVersion2c]

    def register_batch(self, cur_batch):
        if self.__verbose > 3:
            self.log("registered new batch {:d}".format(cur_batch.key))
        self.__job_dict[cur_batch.key] = cur_batch
        self.__disp.jobStarted(cur_batch.key)

    def unregister_batch(self, cur_batch):
        # ids we will no longer handle because of finish
        to_keys = [key for key, value in self.__req_id_lut.iteritems() if value == cur_batch]
        if to_keys:
            for to_key in to_keys:
                del self.__req_id_lut[to_key]
            if self.__verbose > 3:
                cur_batch.log(
                    "removed {} for batch {}".format(
                        logging_tools.get_plural("request ID", len(to_keys)),
                        cur_batch,
                    ),
                )
        del self.__job_dict[cur_batch.key]
        self.__disp.jobFinished(cur_batch.key)

    def loop(self):
        try:
            while self["run_flag"]:
                self.__disp.runDispatcher()
                self.step(blocking=self["run_flag"])
        except ValueConstraintError:
            self.log(
                "caught ValueConstraintError, terminating process",
                logging_tools.LOG_LEVEL_CRITICAL
            )
            _term_cause = "ValueConstraintError"
        except:
            exc_info = process_tools.exception_info()
            self.log("exception in dispatcher, terminating process",
                     logging_tools.LOG_LEVEL_CRITICAL)
            for log_line in exc_info.log_lines:
                self.log(" - {}".format(log_line), logging_tools.LOG_LEVEL_CRITICAL)
            _term_cause = "internal error"
        else:
            self.log("no more jobs running")
            _term_cause = ""
        self.log("jobs pending: {:d}".format(len(self.__job_dict)))
        # close all jobs
        if _term_cause:
            self._terminate_jobs(error="{}, check logs".format(_term_cause))
        else:
            self._terminate_jobs()
        self.__disp.closeDispatcher()

    def _inject(self, cur_batch):
        try:
            next_tuple = cur_batch.iterator.next()
        except StopIteration:
            cur_batch.finish()
        else:
            self.send_next(cur_batch, next_tuple)

    def send_next(self, cur_batch, next_tuple):
        self.__req_id_lut[cur_batch.request_id] = cur_batch
        self.__disp.sendMessage(*next_tuple)

    def _register_return(self, proc_name, **kwargs):
        self.__return_proc_name = proc_name
        self.send_pool_message("hellox", "hello2", "hello3", target=self.__return_proc_name)

    def _fetch_snmp(self, *scheme_data, **kwargs):
        self._inject(snmp_batch(self, *scheme_data, verbose=self.__verbose, **kwargs))

    def _timer_func(self, act_time):
        timed_out = [key for key, cur_job in self.__job_dict.iteritems() if cur_job.timer_func(act_time)]
        for to_key in timed_out:
            self.__job_dict[to_key].finish()
        self.step()
        if self["exit_requested"]:
            self._terminate_jobs(error="exit requested")

    def _terminate_jobs(self, **kwargs):
        _stop_keys = set(self.__job_dict.keys())
        for _key in _stop_keys:
            if "error" in kwargs:
                self.__job_dict[_key].add_error(kwargs["error"])
            self.__job_dict[_key].finish()

    def _recv_func(self, disp, domain, address, whole_msg):
        while whole_msg:
            # rsp_msg, whole_msg = decoder.decode(whole_msg, asn1Spec=self.__p_mod.Message())
            try:
                rsp_msg, whole_msg = decoder.decode(whole_msg, asn1Spec=self.v2c_decoder.Message())
            except:
                self.log("error decoding message from {}: {}".format(
                    address,
                    process_tools.get_except_info()), logging_tools.LOG_LEVEL_CRITICAL)
                # send meaningfull error message to client ? TODO, FIXME
                whole_msg = None
            else:
                # rsp_pdu = self.__p_mod.apiMessage.getPDU(rsp_msg)
                rsp_pdu = self.v2c_decoder.apiMessage.getPDU(rsp_msg)
                cur_id = self.v2c_decoder.apiPDU.getRequestID(rsp_pdu)
                if cur_id in self.__req_id_lut:
                    self.__req_id_lut[cur_id].feed_pdu(disp, domain, address, rsp_pdu)
                else:
                    self.log("id {} in response not known".format(cur_id))
                if cur_id in self.__req_id_lut:
                    del self.__req_id_lut[cur_id]
        return whole_msg

    def loop_post(self):
        self.__log_template.close()

    def send_return(self, envelope, error_list, received, snmp):
        self.send_pool_message("snmp_finished", envelope, error_list, received, snmp, target=self.__return_proc_name or DEFAULT_RETURN_NAME)
