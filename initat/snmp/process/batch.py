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
""" SNMP batch definition """

from pyasn1.codec.ber import encoder, decoder  # @UnresolvedImport
from pyasn1.type.error import ValueConstraintError  # @UnresolvedImport
from pysnmp.carrier.asynsock.dgram import udp  # @UnresolvedImport
from pysnmp.carrier.asynsock.dispatch import AsynsockDispatcher  # @UnresolvedImport
from pysnmp.proto import rfc1155, rfc1902, api  # @UnresolvedImport
from pysnmp.smi import exval  # @UnresolvedImport
from pysnmp.smi.exval import noSuchInstance
from initat.tools import logging_tools
import pprint  # @UnusedImport
import pyasn1  # @UnresolvedImport
import time


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
                        elif value == noSuchInstance:
                            pass
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
