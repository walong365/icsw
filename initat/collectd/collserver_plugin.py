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

from initat.collectd.collectd_types import * # @UnusedWildImport
from initat.collectd.collectd_structs import host_info
from initat.collectd.config import COMMAND_PORT, GRAPHER_PORT, RECV_PORT, IPC_SOCK
from lxml import etree # @UnresolvedImports
from lxml.builder import E # @UnresolvedImports
import collectd # @UnresolvedImport
import logging_tools
import multiprocessing
import os
import process_tools
import re
import server_command
import signal
import threading
import time
import uuid_tools
import zmq

class net_receiver(multiprocessing.Process):
    def __init__(self):
        multiprocessing.Process.__init__(self, target=self._code, name="0MQ_net_receiver")
        self.zmq_id = "{}:collserver_plugin".format(process_tools.get_machine_name())
        self.grapher_id = "{}:rrd_grapher".format(uuid_tools.get_uuid().get_urn())
        self.poller = zmq.Poller()
    def _init(self):
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
        self.context = zmq.Context()
        self.receiver = self.context.socket(zmq.PULL)
        self.sender = self.context.socket(zmq.PUSH)
        self.grapher = self.context.socket(zmq.ROUTER)
        self.command = self.context.socket(zmq.ROUTER)
        # set grapher flags
        for flag, value in [
            (zmq.IDENTITY, self.zmq_id),
            (zmq.SNDHWM, 256),
            (zmq.RCVHWM, 256),
            (zmq.TCP_KEEPALIVE, 1),
            (zmq.TCP_KEEPALIVE_IDLE, 300)]:
            self.grapher.setsockopt(flag, value)
            self.command.setsockopt(flag, value)
        self.sender.connect(IPC_SOCK)
        listener_url = "tcp://*:{:d}".format(RECV_PORT)
        command_url = "tcp://*:{:d}".format(COMMAND_PORT)
        grapher_url = "tcp://localhost:{:d}".format(GRAPHER_PORT)
        self.receiver.bind(listener_url)
        self.command.bind(command_url)
        self.grapher.connect(grapher_url)
        collectd.notice("listening on {}, connected to grapher on {}, command_url is {}".format(
            listener_url,
            grapher_url,
            command_url,
            ))
        self.__poller_dict = {
            self.receiver : self._recv_data,
            self.command : self._recv_command,
            }
        self.__disabled_uuids = set()
        self.poller.register(self.receiver, zmq.POLLIN)
        self.poller.register(self.command, zmq.POLLIN)
    def _init_hosts(self):
        # init host and perfdata structs
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
        self.sender.close()
        self.receiver.close()
        self.grapher.close()
        self.command.close()
        self.context.term()
        collectd.notice("0MQ process finished")
    def _code(self):
        self._init()
        try:
            self._loop()
        except:
            collectd.error("exception raised in loop, exiting")
            exc_info = process_tools.exception_info()
            for line in exc_info.log_lines:
                collectd.error(line)
            self.sender.send("stop")
        self._close()
    def _log_stats(self):
        self.__end_time = time.time()
        diff_time = max(1, abs(self.__end_time - self.__start_time))
        bt_rate = self.__trees_read / diff_time
        st_rate = self.__total_size_trees / diff_time
        bp_rate = self.__pds_read / diff_time
        sp_rate = self.__total_size_pds / diff_time
        collectd.notice("read {} ({}) from {} (rate [{:.2f}, {}] / sec), {} ({}) from {} (rate [{:.2f}, {}] / sec) in {}".format(
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
    def _loop(self):
        while True:
            try:
                rcv_list = self.poller.poll(timeout=1000)
            except zmq.error.ZMQError:
                collectd.error("got ZMQError, exiting")
                break
            else:
                for in_sock, in_type in rcv_list:
                    self.__poller_dict[in_sock](in_sock)
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
            collectd.error("error decoding command {}: {}".format(in_xml, process_tools.get_except_info))
        else:
            in_com.update_source()
            com_text = in_com["command"].text
            collectd.info("got command {} from {}".format(com_text, in_uuid))
            if com_text in ["host_list", "key_list"]:
                self._handle_hk_command(in_com, com_text)
            elif com_text == "disabled_hosts":
                self._handle_disabled_hosts(in_com, com_text)
            else:
                collectd.error("unknown command {}".format(com_text))
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
            collectd.warning(
                "{} to disable, {} to enable".format(
                    logging_tools.get_plural("UUID", len(to_disable)),
                    logging_tools.get_plural("UUID", len(to_enable)),
                )
            )
            for _to_dis in to_disable:
                _host = self.__hosts[_to_dis]
                _host.store_to_disk = False
                collectd.warning("disabled {}".format(unicode(_host)))
            for _to_en in to_enable:
                _host = self.__hosts[_to_en]
                _host.store_to_disk = True
                collectd.warning("enabled {}".format(unicode(_host)))
    def _handle_hk_command(self, in_com, com_text):
        h_filter, k_filter = (
            in_com.get("host_filter", ".*"),
            in_com.get("key_filter", ".*")
        )
        collectd.info(
            "host_filter: {}, key_filter: {}".format(
                h_filter,
                k_filter,
            )
        )
        try:
            host_filter = re.compile(h_filter)
        except:
            host_filter = re.compile(".*")
            collectd.error(
                "error interpreting '{}' as host re: {}".format(
                    h_filter,
                    process_tools.get_except_info()
                )
            )
        try:
            key_filter = re.compile(k_filter)
        except:
            key_filter = re.compile(".*")
            collectd.error(
                "error interpreting '{}' as key re: {}".format(
                    k_filter,
                    process_tools.get_except_info()
                )
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
            self.__hosts[host_uuid] = host_info(host_uuid, host_name)
        if self.__hosts[host_uuid].update(_xml):
            # something changed
            new_com = server_command.srv_command(command="mv_info")
            new_com["vector"] = _xml
            self._send_to_grapher(new_com)
    def _process_data(self, in_tree):
        # adopt tree format for faster handling in collectd loop
        try:
            _xml = etree.fromstring(in_tree)
        except:
            collectd.error("cannot parse tree: {}".format(process_tools.get_except_info()))
        else:
            xml_tag = _xml.tag.split("}")[-1]
            # collectd.error(xml_tag)
            handle_name = "_handle_{}".format(xml_tag)
            if hasattr(self, handle_name):
                try:
                    # loop
                    for p_data in getattr(self, handle_name)(_xml, len(in_tree)):
                        # collectd.info(str(p_data))
                        self.sender.send_pyobj(p_data)
                except:
                    collectd.error(process_tools.get_except_info())
            else:
                collectd.error("unknown handle_name '{}'".format(handle_name))
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
            collectd.warning(
                "no full info for host {} ({}) received, discarding data".format(
                    host_name,
                    host_uuid,
                )
            )
            raise StopIteration
        else:
            if not simple:
                self._feed_host_info(host_uuid, host_name, _xml)
            if not self.__hosts[host_uuid].store_to_disk:
                # writing to disk not allowed
                raise StopIteration
            values = self.__hosts[host_uuid].get_values(_xml, simple)
            r_data = (host_name, recv_time, values)
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
            collectd.warning(
                "unparsed perfdata '{}' from {}".format(
                    perf_value,
                    p_data.get("host")
                )
            )
        return values

class receiver(object):
    def __init__(self):
        self.context = zmq.Context()
        self.recv_sock = None
        self.__last_sent = {}
        self.lock = threading.Lock()
    def start_sub_proc(self):
        collectd.notice("start 0MQ process")
        self.sub_proc = net_receiver()
        self.sub_proc.start()
        collectd.info("adding receiver pid {:d}".format(self.sub_proc.pid))
        self.__msi_block.add_actual_pid(self.sub_proc.pid, mult=3, process_name="receiver", fuzzy_ceiling=3)
        self.__msi_block.save_block()
    def init_receiver(self):
        self._init_msi_block()
        collectd.notice("init 0MQ IPC receiver at {}".format(IPC_SOCK))
        self.recv_sock = self.context.socket(zmq.PULL)
        sock_dir = os.path.dirname(IPC_SOCK[6:])
        if not os.path.isdir(sock_dir):
            collectd.notice("creating directory {}".format(sock_dir))
            os.mkdir(sock_dir)
        self.recv_sock.bind(IPC_SOCK)
    def _init_msi_block(self):
        collectd.info("init meta-server-info block")
        msi_block = process_tools.meta_server_info("collectd")
        msi_block.add_actual_pid(mult=10, fuzzy_ceiling=10, process_name="main")
        msi_block.start_command = "/etc/init.d/collectd start"
        msi_block.stop_command = "/etc/init.d/collectd force-stop"
        msi_block.kill_pids = True
        msi_block.save_block()
        self.__msi_block = msi_block
    def recv(self):
        self.lock.acquire()
        if self.recv_sock:
            while True:
                try:
                    data = self.recv_sock.recv_pyobj(zmq.DONTWAIT)
                except:
                    break
                else:
                    if data == "stop":
                        collectd.notice("0MQ process exited, closing sockets")
                        self.sub_proc.join()
                        self.recv_sock.close()
                        self.context.term()
                        self.recv_sock = None
                        self.__msi_block.remove_meta_block()
                        break
                    else:
                        if len(data) == 3:
                            self._handle_tree(data)
                        else:
                            self._handle_perfdata(data)
        self.lock.release()
    def get_time(self, h_tuple, cur_time):
        cur_time = int(cur_time)
        if h_tuple in self.__last_sent:
            if cur_time <= self.__last_sent[h_tuple]:
                diff_time = self.__last_sent[h_tuple] + 1 - cur_time
                cur_time += diff_time
                collectd.notice("correcting time for {} (+{:d}s to {:d})".format(str(h_tuple), diff_time, int(cur_time)))
        self.__last_sent[h_tuple] = cur_time
        return self.__last_sent[h_tuple]
    def _handle_perfdata(self, data):
        # print "***", data
        _type, type_instance, host_name, time_recv, rsi, v_list = data[1]
        s_time = self.get_time((host_name, "ipd_{}".format(_type)), time_recv)
        collectd.Values(plugin="perfdata", type_instance=type_instance, host=host_name, time=s_time, type="ipd_{}".format(_type), interval=5 * 60).dispatch(values=v_list[rsi:])
    def _handle_tree(self, data):
        host_name, time_recv, values = data
        # print host_name, time_recv
        s_time = self.get_time((host_name, "icval"), time_recv)
        for name, value in values:
            # name can be none for values with transform problems
            if name:
                collectd.Values(plugin="collserver", host=host_name, time=s_time, type="icval", type_instance=name).dispatch(values=[value])

def main_for_collectd():
    # our own functions go here
    def configer(ObjConfiguration):
        pass
    def initer(my_recv):
        signal.signal(signal.SIGCHLD, signal.SIG_DFL)
        my_recv.init_receiver()
        my_recv.start_sub_proc()

    my_recv = receiver()

    collectd.register_config(configer)
    collectd.register_init(initer, my_recv)
    # call every 15 seconds
    collectd.register_read(my_recv.recv, 15.0)

def main_for_direct():
    out_list = logging_tools.new_form_list()
    out_list.append([
        logging_tools.form_entry("icval"),
        logging_tools.form_entry("v:GAUGE:U:U"),
        ])
    for key in sorted(globals().keys()):
        obj = globals()[key]
        if type(obj) == type and obj != perfdata_object:
            if issubclass(obj, perfdata_object):
                obj = obj()
                out_list.append(
                    [
                        logging_tools.form_entry(
                            "ipd_{}".format(obj.PD_NAME)
                        ),
                        logging_tools.form_entry(
                            " ".join(
                                [
                                    "{}:{}".format(
                                        _e.get("name"),
                                        _e.get("rrd_spec")
                                    ) for _e in obj.default_xml_info.xpath(
                                        ".//value[@rrd_spec]", smart_strings=False
                                    )
                                ]
                            )
                        ),
                    ]
                )
    print(unicode(out_list))

if __name__ != "__main__":
    main_for_collectd()
else:
    main_for_direct()
