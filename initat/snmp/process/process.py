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
""" SNMP process definition """

from .batch import snmp_batch
from .config import DEFAULT_RETURN_NAME
from pyasn1.codec.ber import decoder  # @UnresolvedImport
from pyasn1.type.error import ValueConstraintError  # @UnresolvedImport
from pysnmp.carrier.asynsock.dgram import udp  # @UnresolvedImport
from pysnmp.carrier.asynsock.dispatch import AsynsockDispatcher  # @UnresolvedImport
from pysnmp.proto import api  # @UnresolvedImport
import logging_tools
import pprint  # @UnusedImport
import process_tools
import signal
import threading_tools


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
