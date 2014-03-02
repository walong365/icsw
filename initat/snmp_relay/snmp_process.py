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
"""
SNMP relayer, SNMP process
also used by the control process of mother
"""

from pyasn1.codec.ber import encoder, decoder # @UnresolvedImport
from pyasn1.type.error import ValueConstraintError # @UnresolvedImport
from pysnmp.carrier.asynsock.dgram import udp # @UnresolvedImport
from pysnmp.carrier.asynsock.dispatch import AsynsockDispatcher # @UnresolvedImport
from pysnmp.proto import api # @UnresolvedImport
from pysnmp.smi import exval # @UnresolvedImport
import logging_tools
import process_tools
import pyasn1 # @UnresolvedImport
import threading_tools
import time

class snmp_batch(object):
    batch_key = 0
    def __init__(self, proc, *scheme_data, **kwargs):
        snmp_batch.batch_key += 1
        self.key = snmp_batch.batch_key
        self.proc = proc
        snmp_ver, snmp_host, snmp_community, self.envelope, self.transform_single_key, self.__timeout = scheme_data[0:6]
        self.__verbose = kwargs.pop("VERBOSE", False)
        self._clear_errors()
        self._set_target(snmp_ver, snmp_host, snmp_community)
        if self.__verbose > 2:
            self.log("init SNMP_batch for %s (V%d)" % (snmp_host, snmp_ver))
        self.kh_list = scheme_data[6:]
        self.iterator = self.loop()
        self.proc.register_batch(self)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.proc.log("[b %d] %s" % (self.key, what), log_level)
    def _clear_errors(self):
        self.__received, self.__snmp_dict = (set(), {})
        self.__timed_out, self.__other_errors, self.__error_list = (False, False, [])
    def _set_target(self, snmp_ver, snmp_host, snmp_community):
        self.__snmp_ver, self.__snmp_host, self.__snmp_community = (snmp_ver, snmp_host, snmp_community)
        try:
            self.__p_mod = api.protoModules[
                {
                    1 : api.protoVersion1,
                    2 : api.protoVersion2c
                }[self.__snmp_ver]
            ]
        except KeyError:
            self.log("unknown snmp_version %d, using 1" % (self.__snmp_ver), logging_tools.LOG_LEVEL_ERROR)
            self.__p_mod = api.protoModules[api.protoVersion1]
    def run_ok(self):
        return not self.__timed_out and not self.__other_errors
    def oid_pretty_print(self, oids):
        return ";".join(["%s" % (".".join(["%d" % (oidp) for oidp in oid])) for oid in oids])
    def loop(self):
        # print self.kh_list
        for key, header_list in self.kh_list:
            if self.run_ok() and header_list:
                if key == "T":
                    if self.__verbose > 1:
                        self.log("bulk-walk tables (%s): %s" % (self.__snmp_host, self.oid_pretty_print(header_list)))
                    yield self.get_tables(header_list)
                    if self.__verbose > 1:
                        self.log("bulk-walk tables: done")
                else:
                    if self.__verbose > 1:
                        self.log("get tables (%s): %s" % (self.__snmp_host, self.oid_pretty_print(header_list)))
                    yield self.get_tables(header_list, single_values=True)
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
                    self.__error_list.append(
                        "snmp timeout (%d secs, OID is %s)" % (
                            self.__timeout,
                            self.oid_pretty_print(header_list)))
                    self.log("(%s) run not ok for host %s (%s)" % (
                        key,
                        self.__snmp_host,
                        logging_tools.get_plural("table header", len(header_list))),
                             logging_tools.LOG_LEVEL_ERROR)
    def finish(self):
        if self.__verbose > 2:
            self.log("finish() called")
        # empty iterator to remove references
        for _v in self.iterator:
            pass
        self.proc.unregister_batch(self)
        self.proc.send_pool_message("snmp_finished", self.envelope, self.__error_list, self.__received, self.snmp)
    def __del__(self):
        if self.__verbose > 3:
            self.log("__del__")
    def get_tables(self, base_oids, **kwargs):
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
        if self.__single_values:
            # PDU for single values
            self.__req_pdu = self.__p_mod.GetRequestPDU()
        else:
            # PDU for multiple values
            self.__req_pdu = self.__p_mod.GetNextRequestPDU()
        self.__p_mod.apiPDU.setDefaults(self.__req_pdu)
        self.__next_names = [value for value, _max_value in self.__act_head_vars]
        self.__act_domain, self.__act_address = (udp.domainName, (self.__snmp_host, 161))
        self.__p_mod.apiPDU.setVarBinds(self.__req_pdu, [(head_var, self.__p_mod.Null("")) for head_var, _max_head_var in self.__act_head_vars])
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
        # init timer, start of action
        self.__start_time = time.time()
        # start of init get
        self.__start_get_time = time.time()
        self.__single_value = self.__single_values
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
        if self.__single_value:
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
                        # elif isinstance(value, pyasn1.type.univ.Real):
                        #    self.snmp = (tuple(act_h), tuple(name), float(value))
                        elif isinstance(value, pyasn1.type.univ.ObjectIdentifier):
                            self.snmp = (tuple(act_h), tuple(name), tuple(value))
                        else:
                            self.snmp = (tuple(act_h), tuple(name), str(value))
                        self.num_result_values += 1
                self.__num_items += 1
                if self.__max_items and self.__num_items > self.__max_items:
                    terminate = True
                    # print "from: %s, %s = %s" % (address, name.prettyPrint(), value.prettyPrint())
            # Stop on EOM
            if not terminate:
                for _oid, val in var_bind_table[-1]:
                    if val is not None:
                        terminate = False
                        break
                else:
                    terminate = True
        # Generate request for next row
        # print self.__timed_out, next_names, terminate, self.__single_values
        if abs(time.time() - self.__start_time) > self.__timeout:
            self.__timed_out = True
        else:
            self.__start_time = time.time()
        if not self.__timed_out and next_names and not terminate and not self.__single_values:
            self.__act_head_vars, self.__next_names = (next_headers, next_names)
            self.__act_domain, self.__act_address = (domain, address)
            self._next_send()
            # print var_bind_table
            # self.proc._inject(self)
        else:
            # print "done"
            self.proc._inject(self)
    def _next_send(self):
        self.__p_mod.apiPDU.setVarBinds(self.__req_pdu, [(var_x, self.__p_mod.Null("")) for var_x in self.__next_names])
        self.__p_mod.apiPDU.setRequestID(self.__req_pdu, self.__p_mod.getNextRequestID())
        self.request_id = self.__p_mod.apiPDU.getRequestID(self.__req_pdu)
        # print "***", self.request_id
        self.proc.send_next(self, (encoder.encode(self.__req_msg), self.__act_domain, self.__act_address))
        # self.__disp.sendMessage(encoder.encode(self.__req_msg), self.__act_domain, self.__act_address)
    def timer_func(self, act_time):
        diff_time = act_time - self.__start_time
        trigger_timeout = False
        if not self.__data_got and self.__timer_count: # and diff_time > self.__timeout / 2:
            if not self.__num_items and diff_time > self.__timeout:
                self.log("giving up for %s after %d items (%d seconds, timer_count is %d)" % (
                    self.__snmp_host,
                    self.__num_items,
                    act_time - self.__start_time,
                    self.__timer_count),
                         logging_tools.LOG_LEVEL_ERROR)
                trigger_timeout = True
            elif abs(act_time - self.__start_get_time) > self.__timeout / 2:
                # trigger a re-get
                self.__start_get_time = act_time
                self.log("re-initiated get() for %s after %s (%d seconds, timer_count is %d)" % (
                    self.__snmp_host,
                    logging_tools.get_plural("item", self.__num_items),
                    act_time - self.__start_time,
                    self.__timer_count),
                         logging_tools.LOG_LEVEL_WARN)
                self._next_send()
        # print self.__timer_count
        self.__timer_count += 1
        # reset trigger
        self.__data_got = False
        if abs(diff_time) > self.__timeout or trigger_timeout:
            self.__timed_out = True
            return True
        else:
            return False

class snmp_process(threading_tools.process_obj):
    def __init__(self, name, global_config):
        self.__log_name, self.__log_destination = (
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
        )
        self.__verbose = global_config["VERBOSE"]
        threading_tools.process_obj.__init__(self, name, busy_loop=True)
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            self.__log_name,
            self.__log_destination,
            zmq=True,
            context=self.zmq_context)
        self.register_func("fetch_snmp", self._fetch_snmp)
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
            self.log("registered new batch %d" % (cur_batch.key))
        self.__job_dict[cur_batch.key] = cur_batch
        self.__disp.jobStarted(cur_batch.key)
    def unregister_batch(self, cur_batch):
        # ids we will no longer handle because of finish
        to_keys = [key for key, value in self.__req_id_lut.iteritems() if value == cur_batch]
        if to_keys:
            for to_key in to_keys:
                del self.__req_id_lut[to_key]
            cur_batch.log("deleted %s" % (logging_tools.get_plural("request ID", len(to_keys))))
        del self.__job_dict[cur_batch.key]
        self.__disp.jobFinished(cur_batch.key)
    def loop(self):
        try:
            while self["run_flag"]:
                self.__disp.runDispatcher()
                self.step(blocking=self["run_flag"])
        except ValueConstraintError:
            self.log("caught ValueConstraintError, terminating process",
                     logging_tools.LOG_LEVEL_CRITICAL)
        except:
            exc_info = process_tools.exception_info()
            self.log("exception in dispatcher, terminating process",
                     logging_tools.LOG_LEVEL_CRITICAL)
            for log_line in exc_info.log_lines:
                self.log(" - %s" % (log_line), logging_tools.LOG_LEVEL_CRITICAL)
        else:
            self.log("no more jobs running")
        self.log("jobs pending: %d" % (len(self.__job_dict)))
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
        # print "send_msg"
        self.__disp.sendMessage(*next_tuple)
    def _fetch_snmp(self, *scheme_data, **kwargs):
        self._inject(snmp_batch(self, *scheme_data, verbose=self.__verbose, **kwargs))
    def _timer_func(self, act_time):
        timed_out = [key for key, cur_job in self.__job_dict.iteritems() if cur_job.timer_func(act_time)]
        for to_key in timed_out:
            self.__job_dict[to_key].finish()
        self.step()
    def _recv_func(self, disp, domain, address, whole_msg):
        while whole_msg:
            # rsp_msg, whole_msg = decoder.decode(whole_msg, asn1Spec=self.__p_mod.Message())
            rsp_msg, whole_msg = decoder.decode(whole_msg, asn1Spec=self.v2c_decoder.Message())
            # rsp_pdu = self.__p_mod.apiMessage.getPDU(rsp_msg)
            rsp_pdu = self.v2c_decoder.apiMessage.getPDU(rsp_msg)
            cur_id = self.v2c_decoder.apiPDU.getRequestID(rsp_pdu)
            if cur_id in self.__req_id_lut:
                self.__req_id_lut[cur_id].feed_pdu(disp, domain, address, rsp_pdu)
            else:
                self.log("id %s in response not known" % (cur_id))
            if cur_id in self.__req_id_lut:
                del self.__req_id_lut[cur_id]
        return whole_msg
    def loop_post(self):
        self.__log_template.close()

