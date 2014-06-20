#
# this file is part of collectd-init
#
# Copyright (C) 2013-2014 Andreas Lang-Nevyjel init.at
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

""" net receiver process for collectd-init """

from initat.collectd.collectd_structs import host_info
from initat.collectd.collectd_types import * # @UnusedWildImport
from initat.collectd.config import global_config, IPC_SOCK, log_base
from lxml import etree # @UnresolvedImports
from lxml.builder import E # @UnresolvedImports
import logging_tools
import multiprocessing
import process_tools
import re
import threading
import server_command
import time
import uuid_tools
import signal
import zmq

class net_receiver(multiprocessing.Process, log_base):
    def __init__(self):
        multiprocessing.Process.__init__(self, target=self._code, name="0MQ_net_receiver")
        self.zmq_id = "{}:collserver_plugin".format(process_tools.get_machine_name())
        self.grapher_id = "{}:grapher:".format(uuid_tools.get_uuid().get_urn())
    def _init(self):
        threading.currentThread().name = "netrecv"
        # init zmq_context and logging
        self.zmq_context = zmq.Context()
        log_base.__init__(self)
        self.poller = zmq.Poller()
        self.log("net receiver started")
        # ignore signals
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        self._init_perfdata()
        self._init_vars()
        self._init_hosts()
        self._init_sockets()
    def _init_perfdata(self):
        re_list = []
        for key in globals().keys():
            obj = globals()[key]
            if type(obj) == type and obj != perfdata_object:
                if issubclass(obj, perfdata_object):
                    obj = obj()
                    re_list.append((obj.PD_RE, obj))
        self.__pd_re_list = re_list
    def _init_sockets(self):
        self.receiver = self.zmq_context.socket(zmq.PULL)
        self.com = self.zmq_context.socket(zmq.ROUTER)
        self.com.setsockopt(zmq.IDENTITY, "net")
        self.grapher = self.zmq_context.socket(zmq.ROUTER)
        self.command = self.zmq_context.socket(zmq.ROUTER)
        # set grapher flags
        for flag, value in [
            (zmq.IDENTITY, self.zmq_id),
            (zmq.SNDHWM, 256),
            (zmq.RCVHWM, 256),
            (zmq.TCP_KEEPALIVE, 1),
            (zmq.TCP_KEEPALIVE_IDLE, 300)]:
            self.grapher.setsockopt(flag, value)
            self.command.setsockopt(flag, value)
        self.com.connect(IPC_SOCK)
        listener_url = "tcp://*:{:d}".format(global_config["RECV_PORT"])
        command_url = "tcp://*:{:d}".format(global_config["COMMAND_PORT"])
        grapher_url = "tcp://localhost:{:d}".format(global_config["GRAPHER_PORT"])
        self.receiver.bind(listener_url)
        self.command.bind(command_url)
        self.grapher.connect(grapher_url)
        self.log("listening on {}, connected to grapher on {}, command_url is {}".format(
            listener_url,
            grapher_url,
            command_url,
            ))
        self.log("grapher_id is {}".format(self.grapher_id))
        self.__poller_dict = {
            self.receiver : self._recv_data,
            self.command : self._recv_command,
            self.com : self._recv_com,
            }
        self.__disabled_uuids = set()
        self.poller.register(self.receiver, zmq.POLLIN)
        self.poller.register(self.command, zmq.POLLIN)
        self.poller.register(self.com, zmq.POLLIN)
    def _init_hosts(self):
        # init host and perfdata structs
        host_info.setup()
        self.__hosts = {}
        # counter when to send data to rrd-grapher
        self.__perfdatas_cnt = {}
    def _init_vars(self):
        self.__start_time = time.time()
        self.__trees_read, self.__pds_read = (0, 0)
        self.__total_size_trees, self.__total_size_pds = (0, 0)
        self.__distinct_hosts_mv = set()
        self.__distinct_hosts_pd = set()
    def _close(self):
        self._log_stats()
        self._close_sockets()
    def _close_sockets(self):
        self.com.close()
        self.receiver.close()
        self.grapher.close()
        self.command.close()
        self.log("0MQ net receiver finished")
        self.close_log()
        self.zmq_context.term()
    def _code(self):
        self._init()
        try:
            self._loop()
        except:
            self.log("exception raised in loop, exiting", logging_tools.LOG_LEVEL_ERROR)
            exc_info = process_tools.exception_info()
            for line in exc_info.log_lines:
                self.log(line, logging_tools.LOG_LEVEL_ERROR)
            # self.com.send_unicode("main", zmq.SNDMORE)
            # self.com.send("stop")
            # self.com.send_unicode("bg", zmq.SNDMORE)
            # self.com.send("stop")
        self._close()
    def _log_stats(self):
        self.__end_time = time.time()
        diff_time = max(1, abs(self.__end_time - self.__start_time))
        bt_rate = self.__trees_read / diff_time
        st_rate = self.__total_size_trees / diff_time
        bp_rate = self.__pds_read / diff_time
        sp_rate = self.__total_size_pds / diff_time
        self.log("read {} ({}) from {} (rate [{:.2f}, {}] / sec), {} ({}) from {} (rate [{:.2f}, {}] / sec) in {}".format(
            logging_tools.get_plural("tree", self.__trees_read),
            logging_tools.get_size_str(self.__total_size_trees),
            logging_tools.get_plural("host", len(self.__distinct_hosts_mv)),
            bt_rate,
            logging_tools.get_size_str(st_rate),
            logging_tools.get_plural("perfdata", self.__pds_read),
            logging_tools.get_size_str(self.__total_size_pds),
            logging_tools.get_plural("host", len(self.__distinct_hosts_pd)),
            bp_rate,
            logging_tools.get_size_str(sp_rate),
            logging_tools.get_diff_time_str(self.__end_time - self.__start_time),
        ))
        self._init_vars()
    def _send_to_grapher(self, send_xml):
        self.grapher.send_unicode(self.grapher_id, zmq.SNDMORE)
        self.grapher.send_unicode(unicode(send_xml))
    def _send_to_main(self, send_obj):
        self.com.send_unicode("main", zmq.SNDMORE)
        self.com.send_pyobj(send_obj)
    def _loop(self):
        self.__run = True
        while self.__run:
            try:
                rcv_list = self.poller.poll(timeout=1000)
            except zmq.error.ZMQError:
                self.log("got ZMQError, exiting", logging_tools.LOG_LEVEL_ERROR)
                break
            else:
                for in_sock, in_type in rcv_list:
                    self.__poller_dict[in_sock](in_sock)
    def _recv_com(self, in_sock):
        _src_proc = in_sock.recv_unicode()
        _recv = in_sock.recv_pyobj()
        self.log(str(_recv))
        if _recv == "exit":
            self.__run = False
            _recv = None
        if _recv is not None:
            self.log("got unknown data {} {}".format(str(_recv), _src_proc), logging_tools.LOG_LEVEL_ERROR)
    def _recv_data(self, in_sock):
        in_data = in_sock.recv()
        self._process_data(in_data)
        if abs(time.time() - self.__start_time) > 300:
            # periodic log stats
            self._log_stats()
    def _recv_command(self, in_sock):
        in_uuid = in_sock.recv_unicode()
        in_xml = in_sock.recv_unicode()
        try:
            in_com = server_command.srv_command(source=in_xml)
        except:
            self.log("error decoding command {}: {}".format(in_xml, process_tools.get_except_info), logging_tools.LOG_LEVEL_ERROR)
        else:
            in_com.update_source()
            com_text = in_com["command"].text
            self.log("got command {} from {}".format(com_text, in_uuid))
            if com_text in ["host_list", "key_list"]:
                self._handle_hk_command(in_com, com_text)
            elif com_text == "disabled_hosts":
                self._handle_disabled_hosts(in_com, com_text)
            elif com_text in ["ipmi_hosts", "snmp_hosts"]:
                # send ipmi_hosts to main because currently there is no direct communication possible between net and background process
                self._send_to_main(("to_bg", unicode(in_com)))
            else:
                self.log("unknown command {}".format(com_text), logging_tools.LOG_LEVEL_ERROR)
                in_com.set_result(
                    "unknown command {}".format(com_text),
                    server_command.SRV_REPLY_STATE_ERROR
                    )
            in_sock.send_unicode(in_uuid, zmq.SNDMORE)
            in_sock.send_unicode(unicode(in_com))
    def _handle_disabled_hosts(self, in_com, com_text):
        uuids_to_disable = set(in_com.xpath(".//ns:device/@uuid")) & set(self.__hosts.keys())
        cur_disabled = set([key for key, value in self.__hosts.iteritems() if not value.store_to_disk])
        # to be used to disable hosts on first contact, FIXME
        self.__disabled_uuids = uuids_to_disable
        to_disable = uuids_to_disable - cur_disabled
        to_enable = cur_disabled - uuids_to_disable
        if to_disable or to_enable:
            self.log(
                "{} to disable, {} to enable".format(
                    logging_tools.get_plural("UUID", len(to_disable)),
                    logging_tools.get_plural("UUID", len(to_enable)),
                ),
                logging_tools.LOG_LEVEL_WARN
            )
            for _to_dis in to_disable:
                _host = self.__hosts[_to_dis]
                _host.store_to_disk = False
                self.log("disabled {}".format(unicode(_host)), logging_tools.LOG_LEVEL_WARN)
            for _to_en in to_enable:
                _host = self.__hosts[_to_en]
                _host.store_to_disk = True
                self.log("enabled {}".format(unicode(_host)), logging_tools.LOG_LEVEL_WARN)
    def _handle_hk_command(self, in_com, com_text):
        h_filter, k_filter = (
            in_com.get("host_filter", ".*"),
            in_com.get("key_filter", ".*")
        )
        self.log(
            "host_filter: {}, key_filter: {}".format(
                h_filter,
                k_filter,
            )
        )
        try:
            host_filter = re.compile(h_filter)
        except:
            host_filter = re.compile(".*")
            self.log(
                "error interpreting '{}' as host re: {}".format(
                    h_filter,
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        try:
            key_filter = re.compile(k_filter)
        except:
            key_filter = re.compile(".*")
            self.log(
                "error interpreting '{}' as key re: {}".format(
                    k_filter,
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        match_uuids = [_value[1] for _value in sorted([(self.__hosts[cur_uuid].name, cur_uuid) for cur_uuid in self.__hosts.keys() if host_filter.match(self.__hosts[cur_uuid].name)])]
        if com_text == "host_list":
            result = E.host_list(entries="{:d}".format(len(match_uuids)))
            for cur_uuid in match_uuids:
                result.append(self.__hosts[cur_uuid].get_host_info())
            in_com["result"] = result
        elif com_text == "key_list":
            result = E.host_list(entries="{:d}".format(len(match_uuids)))
            for cur_uuid in match_uuids:
                result.append(self.__hosts[cur_uuid].get_key_list(key_filter))
            in_com["result"] = result
        in_com.set_result("got command {}".format(com_text))
    def _feed_host_info(self, host_uuid, host_name, _xml):
        if host_uuid not in self.__hosts:
            self.__hosts[host_uuid] = host_info(self.log_template, host_uuid, host_name)
        if self.__hosts[host_uuid].update(_xml):
            # something changed
            new_com = server_command.srv_command(command="mv_info")
            new_com["vector"] = _xml
            self._send_to_grapher(new_com)
    def _feed_host_info_ov(self, host_uuid, host_name, _xml):
        # update only values
        self.__hosts[host_uuid].update_ov(_xml)
    def _process_data(self, in_tree):
        # adopt tree format for faster handling in collectd loop
        try:
            _xml = etree.fromstring(in_tree)
        except:
            self.log("cannot parse tree: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
        else:
            xml_tag = _xml.tag.split("}")[-1]
            handle_name = "_handle_{}".format(xml_tag)
            if hasattr(self, handle_name):
                try:
                    # loop
                    for p_data in getattr(self, handle_name)(_xml, len(in_tree)):
                        self._send_to_main(p_data)
                except:
                    self.log(process_tools.get_except_info(), logging_tools.LOG_LEVEL_ERROR)
            else:
                self.log("unknown handle_name '{}'".format(handle_name), logging_tools.LOG_LEVEL_ERROR)
    def _check_for_ext_perfdata(self, mach_values):
        # unique tuple
        pd_tuple = (mach_values[0], mach_values[1])
        # init counter
        if pd_tuple not in self.__perfdatas_cnt:
            self.__perfdatas_cnt[pd_tuple] = 1
        # reduce by one
        self.__perfdatas_cnt[pd_tuple] -= 1
        if not self.__perfdatas_cnt[pd_tuple]:
            # zero reached, reset counter to 10 and send info to local rrd-grapher
            self.__perfdatas_cnt[pd_tuple] = 10
            pd_obj = globals()["{}_pdata".format(mach_values[0])]()
            self._send_to_grapher(pd_obj.build_perfdata_info(mach_values))
    def _handle_machine_vector(self, _xml, data_len):
        self.__trees_read += 1
        self.__total_size_trees += data_len
        simple, host_name, host_uuid, recv_time = (
            _xml.attrib["simple"] == "1",
            _xml.attrib["name"],
            # if uuid is not set use name as uuid (will not be sent to the grapher)
            _xml.attrib.get("uuid", _xml.attrib.get("name")),
            float(_xml.attrib["time"]),
        )
        self.__distinct_hosts_mv.add(host_uuid)
        if simple and host_uuid not in self.__hosts:
            self.log(
                "no full info for host {} ({}) received, discarding data".format(
                    host_name,
                    host_uuid,
                ),
                logging_tools.LOG_LEVEL_WARN
            )
            raise StopIteration
        else:
            # store values in host_info (and memcached)
            if simple:
                # only values
                self._feed_host_info_ov(host_uuid, host_name, _xml)
            else:
                self._feed_host_info(host_uuid, host_name, _xml)
            if not self.__hosts[host_uuid].store_to_disk:
                # writing to disk not allowed
                raise StopIteration
            values = self.__hosts[host_uuid].get_values(_xml, simple)
            r_data = ("mvector", host_name, recv_time, values)
            yield r_data
    def _handle_perf_data(self, _xml, data_len):
        self.__total_size_pds += data_len
        # iterate over lines
        for p_data in _xml:
            self.__pds_read += 1
            perf_value = p_data.get("perfdata", "").strip()
            if perf_value:
                self.__distinct_hosts_pd.add(p_data.attrib["host"])
                mach_values = self._find_matching_pd_handler(p_data, perf_value)
                if len(mach_values):
                    self._check_for_ext_perfdata(mach_values)
                    yield ("pdata", mach_values)
        raise StopIteration
    def _find_matching_pd_handler(self, p_data, perf_value):
        values = []
        for cur_re, re_obj in self.__pd_re_list:
            cur_m = cur_re.match(perf_value)
            if cur_m:
                values.extend(re_obj.build_values(p_data, cur_m.groupdict()))
                # stop loop
                break
        if not values:
            self.log(
                "unparsed perfdata '{}' from {}".format(
                    perf_value,
                    p_data.get("host")
                ),
                logging_tools.LOG_LEVEL_WARN
            )
        return values
