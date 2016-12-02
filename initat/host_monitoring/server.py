# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2016 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of host-monitoring
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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

""" host-monitoring, with 0MQ and direct socket support, server code """

from __future__ import unicode_literals, print_function

import StringIO
import argparse
import difflib
import netifaces
import os
import sys
import time
from Queue import Empty
from multiprocessing import Queue

import zmq
from lxml import etree

from initat.client_version import VERSION_STRING
from initat.host_monitoring.client_enums import icswServiceEnum
from initat.host_monitoring.hm_mixins import HMHRMixin
from initat.tools import logging_tools, process_tools, \
    server_command, threading_tools, uuid_tools, config_store
from initat.tools.server_mixins import ICSWBasePool
from .config import global_config
from .constants import TIME_FORMAT, ZMQ_ID_MAP_STORE
from .hm_direct import SocketProcess
from .hm_inotify import HMInotifyProcess
from .hm_resolve import ResolveProcess
from .long_running_checks import LongRunningCheck, LONG_RUNNING_CHECK_RESULT_KEY

# defaults to 10 seconds
IDLE_LOOP_GRANULARITY = 10000.0


class ServerCode(ICSWBasePool, HMHRMixin):
    def __init__(self):
        # monkey path process tools to allow consistent access
        process_tools.ALLOW_MULTIPLE_INSTANCES = False
        # copy to access from modules
        self.global_config = global_config
        self.objgraph = None
        threading_tools.process_pool.__init__(
            self,
            "main",
            zmq=True,
            zmq_contexts=1,
            loop_granularity=IDLE_LOOP_GRANULARITY,
        )
        self.CC.init(icswServiceEnum.host_monitoring, global_config)
        self.CC.check_config()
        if self.CC.CS["hm.enable.objgraph"]:
            try:
                import objgraph
            except ImportError:
                pass
            else:
                self.objgraph = objgraph
        self.add_process(SocketProcess("socket"), start=True)
        self.add_process(ResolveProcess("resolve"), start=True)
        self.install_signal_handlers()
        self._check_ksm()
        self._check_huge()
        self._change_socket_settings()
        self._init_network_sockets()
        self.register_exception("int_error", self._sigint)
        self.register_exception("term_error", self._sigint)
        self.register_exception("hup_error", self._sighup)
        self.register_func("socket_ping_result", self._socket_ping_result)
        self.__callbacks, self.__callback_queue = ({}, {})
        self.register_func("register_callback", self._register_callback)
        self.register_func("callback_result", self._callback_result)
        if not self.CC.CS["hm.disable.inotify.process"]:
            self.add_process(HMInotifyProcess("inotify", busy_loop=True, kill_myself=True), start=True)
        self._show_config()
        self.__debug = global_config["DEBUG"]
        if self.objgraph:
            self.register_timer(self._objgraph_run, 30, instant=True)
        from initat.host_monitoring import modules
        self.modules = modules
        self.__delayed = []
        # Datastructure for managing long running checks:
        # A tuple of (Process, queue, zmq_socket, src_id, srv_com)
        self.long_running_checks = []
        if not self._init_commands():
            self._sigint("error init")
        self.register_timer(self._check_cpu_usage, 30, instant=True)
        # self["exit_requested"] = True

    def long_running_checks_timer(self):
        new_checks = []
        for _idx, _stuff in enumerate(self.long_running_checks):
            process, queue, zmq_sock, src_id, srv_com, c_buffer, long_running_check_obj = _stuff
            if process.is_alive():
                try:
                    _queue_get = queue.get(False)
                except Empty:
                    pass
                else:
                    c_buffer = "{}{}".format(c_buffer, _queue_get)
            if not process.is_alive():
                # check again in case the queue.get triggered a process.exit()
                if process.exitcode == 0:
                    try:
                        _result = queue.get(False)
                    except Empty:
                        _result = c_buffer
                    else:
                        _result = "{}{}".format(c_buffer, _result)
                    try:
                        srv_com = server_command.srv_command(source=_result)
                    except:
                        srv_com[LONG_RUNNING_CHECK_RESULT_KEY] = _result
                    self._send_return(zmq_sock, src_id, srv_com)
                    self.log("Long running check {!r} finished".format(process.name))
                else:
                    srv_com.set_result(
                        "Long running check {!r} failed".format(process.name),
                        server_command.SRV_REPLY_STATE_ERROR
                    )
                    self._send_return(zmq_sock, src_id, srv_com)
                    self.log(
                        "Long running check {!r} failed".format(process.name),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                try:
                    long_running_check_obj.post_perform_check()
                except NotImplementedError:
                    pass
            else:
                new_checks.append((process, queue, zmq_sock, src_id, srv_com, c_buffer, long_running_check_obj))
        self.long_running_checks = new_checks
        if not self.long_running_checks:
            self.unregister_timer(self.long_running_checks_timer)
            self.set_loop_granularity()

    def _sigint(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True

    def _sighup(self, err_cause):
        self.log("got sighup")
        for cur_mod in self.module_list:
            try:
                _ret_val = cur_mod.reload()
            except:
                self.log("error calling reload() for {}: {}".format(cur_mod.name, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            else:
                if _ret_val != "N/A":
                    self.log("called reload() for {}".format(cur_mod.name))

    def _objgraph_run(self):
        # lines = unicode(self.hpy.heap().byrcs[0].byid).split("\n")
        cur_stdout = sys.stdout
        my_io = StringIO.StringIO()
        sys.stdout = my_io
        self.objgraph.show_growth()
        lines = [line.rstrip() for line in unicode(my_io.getvalue()).split("\n") if line.strip()]
        self.log("objgraph show_growth ({})".format(logging_tools.get_plural("line", len(lines)) if lines else "no output"))
        if lines:
            for line in lines:
                self.log(u" - {}".format(line))
        sys.stdout = cur_stdout

    def _check_ksm(self):
        if self.CC.CS["hm.enable.ksm"]:
            ksm_dir = "/sys/kernel/mm/ksm/"
            if os.path.isdir(ksm_dir):
                try:
                    file(os.path.join(ksm_dir, "run"), "w").write("1\n")
                except:
                    self.log(
                        "error enabling KSM: {}".format(
                            process_tools.get_except_info()
                        ),
                        logging_tools.LOG_LEVEL_ERROR)
                else:
                    self.log("enabled KSM")
            else:
                self.log("ksm_dir '{}' not found".format(ksm_dir), logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("KSM not touched")

    def _register_callback(self, *args, **kwargs):
        call_proc, _call_pid, com_name, func_name = args
        self.__callbacks[com_name] = (call_proc, func_name)
        self.log(
            "registered callback '{}' from process {} (func: {})".format(
                com_name,
                call_proc,
                func_name
            )
        )

    def _check_huge(self):
        if self.CC.CS["hm.enable.hugepages"]:
            huge_dir = "/sys/kernel/mm/hugepages/"
            mem_total = int(
                [
                    line for line in file("/proc/meminfo", "r").read().lower().split("\n") if line.startswith("memtotal")
                ][0].split()[1]
            ) * 1024
            mem_to_map = mem_total * self.CC.CS["hm.hugepage.percentage"] / 100
            self.log(
                "memory to use for hugepages ({:d} %): {} (of {})".format(
                    self.CC.CS["hm.hugepage.percentage"],
                    logging_tools.get_size_str(mem_to_map),
                    logging_tools.get_size_str(mem_total),
                )
            )
            if os.path.isdir(huge_dir):
                for sub_dir in os.listdir(huge_dir):
                    if sub_dir.startswith("hugepages"):
                        full_subdir = os.path.join(huge_dir, sub_dir)
                        local_size = sub_dir.split("-")[1].lower()
                        if local_size.endswith("kb"):
                            local_size = int(local_size[:-2]) * 1024
                        elif local_size.endswith("mb"):
                            local_size = int(local_size[:-2]) * 1024 * 1024
                        elif local_size.endswith("gb"):
                            local_size = int(local_size[:-2]) * 1024 * 1024 * 1024
                        else:
                            self.log(
                                "cannot interpret {} ({})".format(
                                    local_size,
                                    full_subdir
                                ),
                                logging_tools.LOG_LEVEL_ERROR
                            )
                            local_size = None
                        if local_size:
                            num_pages = int(mem_to_map / local_size)
                            self.log("size of {} is {}, resulting in {}".format(
                                sub_dir,
                                logging_tools.get_size_str(local_size),
                                logging_tools.get_plural("page", num_pages)
                            ))
                            if num_pages:
                                pages_file = os.path.join(full_subdir, "nr_hugepages")
                                try:
                                    cur_pages = int(file(pages_file, "r").read().strip())
                                except:
                                    self.log(
                                        "cannot read pages from {}: {}".format(
                                            pages_file,
                                            process_tools.get_except_info()
                                        ),
                                        logging_tools.LOG_LEVEL_ERROR
                                    )
                                else:
                                    if cur_pages:
                                        self.log(
                                            "current pages set to {:d}, skipping set to {:d}".format(
                                                cur_pages, num_pages
                                            ),
                                            logging_tools.LOG_LEVEL_WARN
                                        )
                                    else:
                                        try:
                                            file(pages_file, "w").write("{:d}\n".format(num_pages))
                                        except:
                                            self.log(
                                                "cannot write {:d} to {}: {}".format(
                                                    num_pages,
                                                    pages_file,
                                                    process_tools.get_except_info()
                                                ),
                                                logging_tools.LOG_LEVEL_ERROR
                                            )
                                        else:
                                            self.log("wrote {:d} to {}".format(num_pages, pages_file))
            else:
                self.log("huge_dir '{}' not found".format(huge_dir), logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("hugepages not touched")

    def _change_socket_settings(self):
        # hm, really needed ?
        for sys_name, sys_value in [
            ("net.core.rmem_default", 524288),
            ("net.core.rmem_max", 5242880),
            ("net.core.wmem_default", 524288),
            ("net.core.wmem_max", 5242880)
        ]:
            f_path = "/proc/sys/{}".format(sys_name.replace(".", "/"))
            if os.path.isfile(f_path):
                cur_value = int(open(f_path, "r").read().strip())
                if cur_value < sys_value:
                    try:
                        file(f_path, "w").write("%d" % (sys_value))
                    except:
                        self.log(
                            "cannot change value of {} from {:d} to {:d}: {}".format(
                                f_path,
                                cur_value,
                                sys_value,
                                process_tools.get_except_info()
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                    else:
                        self.log(
                            "changed {} from {:d} to {:d}".format(
                                f_path,
                                cur_value,
                                sys_value
                            )
                        )
                else:
                    self.log(
                        "{} is now {:d} (needed: {:d}), OK".format(
                            f_path,
                            cur_value,
                            sys_value
                        )
                    )

    def process_start(self, src_process, src_pid):
        self.CC.process_added(src_process, src_pid)

    def _init_network_sockets(self):
        zmq_id_name = "/etc/sysconfig/host-monitoring.d/0mq_id"
        my_0mq_id = uuid_tools.get_uuid().get_urn()
        if not config_store.ConfigStore.exists(ZMQ_ID_MAP_STORE):
            create_0mq_cs = True
            if os.path.exists(zmq_id_name):
                try:
                    zmq_id_dict = {
                        cur_el.attrib["bind_address"]: (
                            cur_el.text, True if "virtual" in cur_el.attrib else False
                        ) for cur_el in etree.fromstring(
                            file(zmq_id_name, "r").read()
                        ).xpath(".//zmq_id[@bind_address]", smart_strings=False)
                    }
                except:
                    self.log(
                        "error reading from  {}: {}".format(
                            zmq_id_name,
                            process_tools.get_except_info()
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                    zmq_id_dict = {}
            else:
                zmq_id_dict = {}
            if "*" not in zmq_id_dict:
                zmq_id_dict["*"] = (my_0mq_id, False)
            _cs = config_store.ConfigStore(
                ZMQ_ID_MAP_STORE,
                log_com=self.log,
                read=False,
                prefix="bind",
                access_mode=config_store.AccessModeEnum.LOCAL,
                fix_access_mode=True,
            )
            for _idx, _key in enumerate(["*"] + sorted([_key for _key in zmq_id_dict.keys() if _key not in ["*"]])):
                _cs["{:d}".format(_idx)] = {
                    "address": _key,
                    "uuid": zmq_id_dict[_key][0],
                    "virtual": zmq_id_dict[_key][1]
                }
        else:
            # read from cs
            _cs = config_store.ConfigStore(
                ZMQ_ID_MAP_STORE,
                log_com=self.log,
                prefix="bind",
                access_mode=config_store.AccessModeEnum.LOCAL,
                fix_access_mode=True,
            )
            create_0mq_cs = False

        if "0" not in _cs:
            _cs["0"] = {
                "address": "*",
                "virtual": False,
                "uuid": my_0mq_id,
            }
        if _cs["0"]["uuid"] != my_0mq_id:
            self.log(
                "0MQ id from cluster ({}) differs from host-monitoring 0MQ id ({})".format(
                    my_0mq_id,
                    _cs["bind_0_uuid"],
                )
            )
            # code snippet to update value
            _cur = _cs["0"]
            _cur["uuid"] = my_0mq_id
            _cs["0"] = _cur
            create_0mq_cs = True
        if create_0mq_cs:
            _cs.write()
        # get all ipv4 interfaces with their ip addresses, dict: interfacename -> IPv4
        zmq_id_dict = {}
        for _idx in _cs.keys():
            _bind = _cs[_idx]
            zmq_id_dict[_bind["address"]] = (
                _bind["uuid"],
                _bind["virtual"],
            )
        ipv4_dict = {
            cur_if_name: [
                ip_tuple["addr"] for ip_tuple in value[2]
            ][0] for cur_if_name, value in [
                (if_name, netifaces.ifaddresses(if_name)) for if_name in netifaces.interfaces()
            ] if 2 in value
        }
        # ipv4_lut = dict([(value, key) for key, value in ipv4_dict.iteritems()])
        ipv4_addresses = ipv4_dict.values()
        if zmq_id_dict.keys() == ["*"]:
            # wildcard bind
            pass
        else:
            if "*" in zmq_id_dict:
                wc_urn, wc_virtual = zmq_id_dict.pop("*")
                for target_ip in ipv4_addresses:
                    if target_ip not in zmq_id_dict:
                        zmq_id_dict[target_ip] = (wc_urn, wc_virtual)
        ref_id = "*" if "*" in zmq_id_dict else "127.0.0.1"
        self.zeromq_id = zmq_id_dict[ref_id][0].split(":")[-1]
        self.log("0MQ bind info (global 0MQ id is {})".format(self.zeromq_id))
        for key in sorted(zmq_id_dict.iterkeys()):
            self.log(
                "bind address {:<15s}: {}{}".format(
                    key,
                    zmq_id_dict[key][0],
                    " is virtual" if zmq_id_dict[key][1] else ""
                )
            )
        self.zmq_id_dict = zmq_id_dict
        self._bind_external()
        sock_list = [
            ("ipc", "vector", zmq.PULL, 512, None, ""),  # @UndefinedVariable
            ("ipc", "command", zmq.PULL, 512, self._recv_ext_command, ""),  # @UndefinedVariable
            ("ipc", "result", zmq.ROUTER, 512, None, process_tools.zmq_identity_str("host_monitor"))  # @UndefinedVariable
        ]
        for _sock_proto, short_sock_name, sock_type, hwm_size, dst_func, zmq_id in sock_list:
            sock_name = process_tools.get_zmq_ipc_name(short_sock_name, s_name="collserver")
            file_name = sock_name[5:]
            self.log(
                "init {} ipc_socket '{}' (HWM: {:d})".format(
                    short_sock_name,
                    sock_name,
                    hwm_size
                )
            )
            if os.path.exists(file_name):
                self.log("removing previous file")
                try:
                    os.unlink(file_name)
                except:
                    self.log("... {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            wait_iter = 0
            while os.path.exists(file_name) and wait_iter < 100:
                self.log("socket {} still exists, waiting".format(sock_name))
                time.sleep(0.1)
                wait_iter += 1
            cur_socket = self.zmq_context.socket(sock_type)
            if zmq_id:
                cur_socket.setsockopt_string(zmq.IDENTITY, zmq_id)  # @UndefinedVariable
            try:
                process_tools.bind_zmq_socket(cur_socket, sock_name)
                # client.bind("tcp://*:8888")
            except zmq.ZMQError:
                self.log(
                    "error binding {}: {}".format(
                        short_sock_name,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_CRITICAL
                )
                raise
            else:
                setattr(self, "{}_socket".format(short_sock_name), cur_socket)
                _backlog_size = self.CC.CS["hm.socket.backlog.size"]
                os.chmod(file_name, 0777)
                cur_socket.setsockopt(zmq.LINGER, 0)  # @UndefinedVariable
                cur_socket.setsockopt(zmq.SNDHWM, hwm_size)  # @UndefinedVariable
                cur_socket.setsockopt(zmq.RCVHWM, hwm_size)  # @UndefinedVariable
                if dst_func:
                    self.register_poller(cur_socket, zmq.POLLIN, dst_func)  # @UndefinedVariable

    def _unbind_external(self):
        # experimental code, not used right now
        for bind_ip, sock in zip(sorted(self.zmq_id_dict.keys()), self.socket_list):
            # print "unbind", bind_ip
            sock.unbind(
                "tcp://{}:{:d}".format(
                    bind_ip,
                    global_config["COMMAND_PORT"]
                )
            )
            sock.close()
            del sock
            # print "done"
            # time.sleep(1)

    def _bind_external(self):
        self.socket_list = []
        for bind_ip in sorted(self.zmq_id_dict.keys()):
            bind_0mq_id, is_virtual = self.zmq_id_dict[bind_ip]
            client = self.zmq_context.socket(zmq.ROUTER)  # @UndefinedVariable
            client.setsockopt(zmq.LINGER, 0)  # @UndefinedVariable
            client.setsockopt(zmq.IDENTITY, bind_0mq_id)  # @UndefinedVariable
            client.setsockopt(zmq.SNDHWM, 16)  # @UndefinedVariable
            client.setsockopt(zmq.RCVHWM, 16)  # @UndefinedVariable
            client.setsockopt(zmq.RECONNECT_IVL_MAX, 500)  # @UndefinedVariable
            client.setsockopt(zmq.RECONNECT_IVL, 200)  # @UndefinedVariable
            client.setsockopt(zmq.TCP_KEEPALIVE, 1)  # @UndefinedVariable
            client.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 300)  # @UndefinedVariable
            _conn_str = "tcp://{}:{:d}".format(
                bind_ip,
                global_config["COMMAND_PORT"]
            )
            try:
                client.bind(_conn_str)
            except zmq.ZMQError:
                self.log(
                    "error binding to {}{}: {}".format(
                        "virtual " if is_virtual else "",
                        _conn_str,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_CRITICAL
                )
                if not is_virtual:
                    raise
                client.close()
            else:
                self.register_poller(client, zmq.POLLIN, self._recv_command)
                self.socket_list.append(client)

    def register_vector_receiver(self, t_func):
        self.register_poller(self.vector_socket, zmq.POLLIN, t_func)

    def _recv_ext_command(self, zmq_sock):
        data = zmq_sock.recv()
        if data.startswith("<"):
            srv_com = server_command.srv_command(source=data)
            src_id = srv_com["identity"].text
        else:
            src_id = data.split(";")[0]
        cur_com = srv_com["command"].text
        srv_com["client_version"] = VERSION_STRING
        srv_com.update_source()
        if cur_com in self.__callbacks.keys():
            call_proc, func_name = self.__callbacks[cur_com]
            self.send_to_process(
                call_proc,
                func_name,
                src_id,
                unicode(srv_com)
            )
        else:
            srv_com.set_result(
                "got unknown command {}".format(srv_com["command"].text),
                server_command.SRV_REPLY_STATE_ERROR
            )
            self.result_socket.send_unicode(src_id, zmq.SNDMORE)
            self.result_socket.send_unicode(unicode(srv_com))
        # print "."

    def _callback_result(self, *args, **kwargs):
        _call_proc, _proc_pid, src_id, srv_com = args
        self.result_socket.send_unicode(src_id, zmq.SNDMORE)
        self.result_socket.send_unicode(unicode(srv_com))

    def _check_cpu_usage(self):
        if self.check_cpu_usage():
            self.log("excess cpu usage detected", logging_tools.LOG_LEVEL_CRITICAL)
            self.log("shooting myself in the head ...", logging_tools.LOG_LEVEL_CRITICAL)
            os.kill(self.pid, 9)

    def _recv_command(self, zmq_sock):
        # print [(key, value.pid) for key, value in self.processes.iteritems()]
        data = [zmq_sock.recv()]
        while zmq_sock.getsockopt(zmq.RCVMORE):
            data.append(zmq_sock.recv())
        if len(data) == 2:
            src_id = data.pop(0)
            data = data[0]
            srv_com = server_command.srv_command(source=data)
            srv_com["client_version"] = VERSION_STRING
            if "namespace" in srv_com:
                # namespace given, parse and use it
                cur_ns = argparse.Namespace()
                for _entry in srv_com.xpath(".//ns:namespace/ns:*", smart_strings=False):
                    ns_key = _entry.tag.split("}", 1)[-1]
                    setattr(cur_ns, ns_key, srv_com["*namespace:{}".format(ns_key)])
                rest_str = u""
            else:
                # no namespace given, parse what we got form server
                cur_ns = None
                rest_el = srv_com.xpath(".//ns:arguments/ns:rest", smart_strings=False)
                if rest_el:
                    rest_str = rest_el[0].text or u""
                elif len(srv_com.xpath(".//ns:arguments/ns:arg0")):
                    # no rest given but there are arguments
                    rest_str = u" ".join([_el.text for _el in srv_com.xpath(".//ns:arguments")[0]])
                else:
                    rest_str = u""
            # is a delayed command
            delayed = False
            cur_com = srv_com["command"].text
            srv_com.set_result("ok")
            srv_com["result"].attrib.update(
                {
                    "start_time": TIME_FORMAT.format(time.time())
                }
            )
            if cur_com in self.commands:
                delayed = self._handle_module_command(srv_com, cur_ns, rest_str)
            else:
                c_matches = difflib.get_close_matches(cur_com, self.commands.keys())
                if c_matches:
                    cm_str = "close matches: {}".format(", ".join(c_matches))
                else:
                    cm_str = "no matches found"
                srv_com.set_result(
                    "unknown command '{}', {}".format(cur_com, cm_str),
                    server_command.SRV_REPLY_STATE_ERROR
                )
            if isinstance(delayed, LongRunningCheck):
                queue = Queue()
                process = delayed.start(queue)
                if not self.long_running_checks:
                    self.register_timer(self.long_running_checks_timer, 1.0)
                self.long_running_checks.append(
                    (process, queue, zmq_sock, src_id, srv_com, "", delayed)
                )
            elif delayed:
                # delayed is a subprocess_struct
                delayed.set_send_stuff(self, src_id, zmq_sock)
                com_usage = len([True for cur_del in self.__delayed if cur_del.command == cur_com])
                # print "CU", com_usage, [cur_del.target_host for cur_del in self.__delayed]
                if com_usage > delayed.Meta.max_usage:
                    srv_com.set_result(
                        "delay limit {:d} reached for '{}'".format(
                            delayed.Meta.max_usage,
                            cur_com
                        ),
                        server_command.SRV_REPLY_STATE_ERROR
                    )
                    delayed = None
                else:
                    if not self.__delayed:
                        self.register_timer(self._check_delayed, 0.1)
                    if delayed.Meta.direct:
                        if not self["exit_requested"]:
                            self.send_to_process(
                                "socket",
                                *delayed.run()
                            )
                    else:
                        delayed.run()
                    self.__delayed.append(delayed)
            self.set_loop_granularity()
            if not delayed:
                self._send_return(zmq_sock, src_id, srv_com)
        else:
            self.log(
                "cannot receive more data, already got '{}'".format(", ".join(data)),
                logging_tools.LOG_LEVEL_ERROR
            )

    def set_loop_granularity(self):
        _cur_lg = self.loop_granularity
        if self.__delayed or self.long_running_checks:
            _new_lg = 50
        else:
            _new_lg = IDLE_LOOP_GRANULARITY
        if _new_lg != _cur_lg:
            self.log("changing loop-granularity from {:.2f} to {:.2f} msecs".format(_cur_lg, _new_lg))
            self.loop_granularity = _new_lg

    def _send_return(self, zmq_sock, src_id, srv_com):
        c_time = time.time()
        srv_com["result"].attrib["end_time"] = TIME_FORMAT.format(c_time)
        info_str = "got command '{}' from '{}', took {}".format(
            srv_com["command"].text,
            srv_com["source"].attrib["host"],
            logging_tools.get_diff_time_str(abs(c_time - float(srv_com["result"].attrib["start_time"])))
        )
        if int(srv_com["result"].attrib["state"]) != server_command.SRV_REPLY_STATE_OK:
            info_str = "{}, result is {} ({})".format(
                info_str,
                srv_com["result"].attrib["reply"],
                srv_com["result"].attrib["state"]
            )
            log_level = logging_tools.LOG_LEVEL_WARN
        else:
            log_level = logging_tools.LOG_LEVEL_OK
        if self.__debug:
            self.log(info_str, log_level)
        srv_com.update_source()
        zmq_sock.send_unicode(src_id, zmq.SNDMORE)  # @UndefinedVariable
        zmq_sock.send_unicode(unicode(srv_com))
        del srv_com

    def _check_delayed(self):
        cur_time = time.time()
        new_list = []
        for cur_del in self.__delayed:
            if cur_del.Meta.use_popen:
                if cur_del.finished():
                    # print "finished delayed"
                    cur_del.send_return()
                elif abs(cur_time - cur_del._init_time) > cur_del.Meta.max_runtime:
                    self.log("delay_object runtime exceeded, stopping")
                    cur_del.terminate()
                    cur_del.send_return()
                else:
                    new_list.append(cur_del)
            else:
                if not cur_del.terminated:
                    new_list.append(cur_del)
        self.__delayed = new_list
        if not self.__delayed:
            self.unregister_timer(self._check_delayed)
            self.set_loop_granularity()

    def _handle_module_command(self, srv_com, cur_ns, rest_str):
        cur_com = self.commands[srv_com["command"].text]
        sp_struct = None
        try:
            if cur_ns is None:
                cur_ns, _rest = cur_com.handle_commandline(rest_str.strip().split())
            sp_struct = cur_com(srv_com, cur_ns)
        except:
            exc_info = process_tools.exception_info()
            for log_line in exc_info.log_lines:
                self.log(log_line, logging_tools.LOG_LEVEL_ERROR)
            srv_com.set_result(
                "caught server exception '{}'".format(process_tools.get_except_info()),
                server_command.SRV_REPLY_STATE_CRITICAL
            )
        return sp_struct

    def _socket_ping_result(self, src_proc, src_id, *args):
        ping_id = args[0]
        found = False
        for cur_del in self.__delayed:
            if cur_del.Meta.id_str == "ping" and cur_del.seq_str == ping_id:
                cur_del.process(*args)
                found = True
        if not found:
            self.log(
                "got ping_reply with unknown id '{}'".format(ping_id),
                logging_tools.LOG_LEVEL_WARN
            )

    def _show_config(self):
        try:
            for log_line, log_level in global_config.get_log():
                self.log("Config info : [%d] %s" % (log_level, log_line))
        except:
            self.log(
                "error showing configfile log, old configfile ? ({})".format(process_tools.get_except_info()),
                logging_tools.LOG_LEVEL_ERROR
            )
        conf_info = global_config.get_config_info()
        self.log("Found {}:".format(logging_tools.get_plural("valid configline", len(conf_info))))
        for conf in conf_info:
            self.log("Config : {}".format(conf))

    def loop_end(self):
        for cur_mod in self.modules.module_list:
            cur_mod.close_module()

    def _close_modules(self):
        for cur_mod in self.module_list:
            if hasattr(cur_mod, "stop_module"):
                self.log("calling stop_module() for {}".format(cur_mod.name))
                try:
                    cur_mod.stop_module()
                except:
                    exc_info = process_tools.exception_info()
                    for log_line in exc_info.log_lines:
                        self.log(log_line, logging_tools.LOG_LEVEL_CRITICAL)
                    _init_ok = False

    def loop_post(self):
        self._close_modules()
        for cur_sock in self.socket_list:
            cur_sock.close()
        self.vector_socket.close()
        self.command_socket.close()
        self.result_socket.close()
        self.CC.close()
