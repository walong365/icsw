# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server-client
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

""" host-monitoring, with 0MQ and direct socket support, relay part """

import os
import resource
import socket
import time
from enum import Enum

import zmq
from lxml import etree

from initat.icsw.service.instance import InstanceXML
from initat.tools import logging_tools, process_tools, server_command, threading_tools, uuid_tools
from initat.tools.server_mixins import ICSWBasePool
from initat.debug import ICSW_DEBUG_MODE
from . import limits
from .client_enums import icswServiceEnum
from .discovery import ZMQDiscovery
from .hm_direct import SocketProcess
from .hm_mixins import HMHRMixin
from .hm_resolve import ResolveProcess
from .host_monitoring_struct import HostConnection, HostMessage, DUMMY_0MQ_ID
from .ipc_comtools import IPCCommandHandler


class ConnectionType(Enum):
    zmq = "zmq"
    tcp = "tcp"


class RelayCode(ICSWBasePool, HMHRMixin):
    def __init__(self, global_config):
        # monkey path process tools to allow consistent access
        process_tools.ALLOW_MULTIPLE_INSTANCES = False
        # copy to access from modules
        threading_tools.icswProcessPool.__init__(
            self,
            "main",
            global_config=global_config,
        )
        from initat.host_monitoring.modules import local_mc
        self.__hm_port = InstanceXML(quiet=True).get_port_dict("host-monitoring", command=True)
        self.CC.init(icswServiceEnum.host_relay, self.global_config)
        self.CC.check_config()
        self.__verbose = self.global_config["VERBOSE"]
        _cs_changed = False
        if "hr.state.directory" not in self.CC.CS:
            self.CC.CS["hr.state.directory"] = "/var/lib/host-relay"
            _cs_changed = True
        self.state_directory = self.CC.CS["hr.state.directory"]
        if "hr.force.name.resolve" in self.CC.CS:
            del self.CC.CS["hr.force.name.resolve"]
            _cs_changed = True
        if _cs_changed:
            self.CC.CS.write()
        # ip resolving
        self._resolve_address = self._resolve_address_noresolve
        self.log("state directory is {}".format(self.state_directory))
        # pending_connection.init(self)
        # global timeout value for host connections
        self.__global_timeout = self.CC.CS["hr.connection.timeout"]
        self.ICH = IPCCommandHandler(self)
        self.CC.log_config()
        # init lut
        self.__old_send_lut = {}
        # we need no icmp capability in relaying
        self.add_process(SocketProcess("socket"), start=True)
        self.add_process(ResolveProcess("resolve"), start=True)
        self.install_signal_handlers()
        ZMQDiscovery.init(
            self,
            self.CC.CS["hm.socket.backlog.size"],
            self.__global_timeout,
            self.__verbose,
        )
        HostConnection.init(
            self,
            self.CC.CS["hm.socket.backlog.size"],
            self.__global_timeout,
            ZMQDiscovery,
        )
        self._init_filecache()
        self._change_rlimits()
        self._init_network_sockets()
        self._init_ipc_sockets()
        self.register_exception("int_error", self._sigint)
        self.register_exception("term_error", self._sigint)
        self.register_exception("hup_error", self._hup_error)
        self.__delayed = []
        self.__local_pings = {}
        self.__local_ping = None
        if not self.COM_open(local_mc, global_config["VERBOSE"]):
            self._sigint("error init")
        else:
            self.__local_ping = self.local_mc["ping"]
            self.register_timer(self._check_timeout, 2)
            self.register_func("socket_result", self._socket_result)
            self.register_func("socket_ping_result", self._socket_ping_result)

    def _sigint(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True

    def _hup_error(self, err_cause):
        self.log("got SIGHUP ({})".format(err_cause), logging_tools.LOG_LEVEL_WARN)
        self.log(" - setting all clients with connmode TCP to unknown", logging_tools.LOG_LEVEL_WARN)
        self.log(" - reloading 0MQ mappings", logging_tools.LOG_LEVEL_WARN)
        num_c = 0
        for t_host, c_state in self.__client_dict.items():
            if c_state == ConnectionType.tcp:
                self.__client_dict[t_host] = None
                num_c += 1
        self.log("cleared {}".format(logging_tools.get_plural("state", num_c)))
        ZMQDiscovery.reload_mapping()

    def _change_rlimits(self):
        for limit_name in ["OFILE"]:
            res = getattr(resource, "RLIMIT_{}".format(limit_name))
            soft, hard = resource.getrlimit(res)
            if soft < hard:
                self.log(
                    "changing ulimit of {} from {:d} to {:d}".format(
                        limit_name,
                        soft,
                        hard,
                    )
                )
                try:
                    resource.setrlimit(res, (hard, hard))
                except:
                    self.log(
                        "cannot alter ulimit: {}".format(
                            process_tools.get_except_info()
                        ),
                        logging_tools.LOG_LEVEL_CRITICAL,
                    )

    def _init_filecache(self):
        self.__client_dict = {
            _key: ConnectionType.zmq for _key in ZMQDiscovery.get_hm_0mq_addrs()
        }
        # print("*", self.__client_dict.keys())

    def _new_client(self, c_ip, c_port):
        self._set_client_state(c_ip, c_port, ConnectionType.zmq)

    def _old_client(self, c_ip, c_port):
        self._set_client_state(c_ip, c_port, ConnectionType.tcp)

    def _set_client_state(self, c_ip, c_port, c_type):
        check_names = [c_ip]
        # if self.__force_resolve:
        #    # try to map IPs and names to devices
        #    if c_ip in self.__ip_lut:
        #        real_name = self.__ip_lut[c_ip]
        #        if real_name != c_ip:
        #            check_names.append(real_name)
        for c_name in check_names:
            if self.__client_dict.get(c_name, None) != c_type and c_port == self.__hm_port:
                self.log(
                    "setting client '{}:{:d}' to '{}'".format(
                        c_name,
                        c_port,
                        c_type
                    )
                )
                self.__client_dict[c_name] = c_type

    def process_start(self, src_process, src_pid):
        self.CC.process_added(src_process, src_pid)

    def _check_timeout(self):
        HostConnection.check_timeout_global(ZMQDiscovery)
        cur_time = time.time()
        # check nhm timeouts
        del_list = []
        for key, value in self.__nhm_dict.items():
            if abs(value[0] - cur_time) > self.__global_timeout:
                del_list.append(key)
                self._send_result(
                    value[1]["identity"].text,
                    "error timeout (cto)",
                    server_command.SRV_REPLY_STATE_ERROR
                )
        if del_list:
            self.log(
                "removing {}: {}".format(
                    logging_tools.get_plural("nhm key", len(del_list)),
                    ", ".join(sorted(del_list))
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            for key in del_list:
                del self.__nhm_dict[key]
        # check raw_nhm timeouts
        del_list = []
        for key, value in self.__raw_nhm_dict.items():
            if abs(value[0] - cur_time) > self.__global_timeout:
                del_list.append(key)
                self._send_result(
                    value[1]["identity"].text,
                    "error timeout (rcto)",
                    server_command.SRV_REPLY_STATE_ERROR
                )
        if del_list:
            self.log(
                "removing {}: {}".format(
                    logging_tools.get_plural("raw nhm key", len(del_list)),
                    ", ".join(sorted(del_list))
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            for key in del_list:
                del self.__raw_nhm_dict[key]
        # check delayed
        cur_time = time.time()
        new_list = []
        if self.__delayed:
            self.log(
                "{} in delayed queue".format(
                    logging_tools.get_plural("object", len(self.__delayed))
                )
            )
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

    def _socket_result(self, src_proc, proc_id, src_id, srv_com, data_str, is_error):
        if src_id in self.__old_send_lut:
            self.__old_send_lut.pop(src_id)._handle_old_result(
                src_id,
                data_str,
                is_error
            )
        else:
            self.log(
                "result for non-existing id '{}' received, discarding".format(
                    src_id
                ),
                logging_tools.LOG_LEVEL_ERROR
            )

    def send_to_syncer(self, srv_com):
        try:
            self.main_socket.send_unicode(self.__local_syncer_uuid, zmq.SNDMORE)
            self.main_socket.send_unicode(str(srv_com))
        except:
            self.log(
                "cannot send to local syncer: {}".format(
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )

    def send_result(self, src_id, ret_str):
        self.sender_socket.send_unicode(src_id, zmq.SNDMORE)
        self.sender_socket.send_unicode(ret_str)

    def _init_ipc_sockets(self):
        # init IP lookup table
        # if self.__force_resolve:
        #    self.__ip_lut = {}
        #    self.__forward_lut = {}
        self.__num_messages = 0
        # nhm (not host monitoring) dictionary for timeout
        self.__nhm_dict = {}
        # raw_nhm (not host monitoring) dictionary for timeout, raw connections (no XML)
        self.__raw_nhm_dict = {}
        self.__nhm_connections = set()
        # also used in md-sync-server/server, ToDo: Refactor
        sock_list = [
            {
                "proto": "ipc",
                "name": "receiver",
                "type": zmq.PULL,
                "hwm_size": 2,
            },
            {
                "proto": "ipc",
                "name": "sender",
                "type": zmq.PUB,
                "hwm_size": 1024,
            },
        ]
        [
            setattr(self, "{}_socket".format(_sock["name"]), None) for _sock in sock_list
        ]
        for _sock in sock_list:
            sock_name = process_tools.get_zmq_ipc_name(_sock["name"], s_name="collrelay")
            file_name = sock_name[5:]
            self.log(
                "init {} ipc_socket '{}' (HWM: {:d})".format(
                    _sock["name"],
                    sock_name,
                    _sock["hwm_size"],
                )
            )
            if os.path.exists(file_name):
                self.log("removing previous file")
                try:
                    os.unlink(file_name)
                except:
                    self.log(
                        "... {}".format(process_tools.get_except_info()),
                        logging_tools.LOG_LEVEL_ERROR
                    )
            wait_iter = 0
            while os.path.exists(file_name) and wait_iter < 100:
                self.log("socket {} still exists, waiting".format(sock_name))
                time.sleep(0.1)
                wait_iter += 1
            cur_socket = self.zmq_context.socket(_sock["type"])
            try:
                process_tools.bind_zmq_socket(cur_socket, sock_name)
                # client.bind("tcp://*:8888")
            except zmq.ZMQError:
                self.log(
                    "error binding {}: {}" .format(
                        _sock["name"],
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_CRITICAL
                )
                raise
            else:
                setattr(self, "{}_socket".format(_sock["name"]), cur_socket)
                os.chmod(file_name, 0o777)
                cur_socket.setsockopt(zmq.LINGER, 0)
                cur_socket.setsockopt(zmq.SNDHWM, _sock["hwm_size"])
                cur_socket.setsockopt(zmq.RCVHWM, _sock["hwm_size"])
                if _sock["type"] == zmq.PULL:
                    self.register_poller(cur_socket, zmq.POLLIN, self._recv_command_ipc)
        self.client_socket = process_tools.get_socket(
            self.zmq_context,
            "ROUTER",
            identity="ccollclient:{}".format(process_tools.get_machine_name()),
            linger=0,
            sndhwm=2,
            rcvhwm=2,
            immediate=True,
        )
        self.register_poller(self.client_socket, zmq.POLLIN, self._recv_nhm_result)

    def _register_local_syncer(self):
        _inst_xml = InstanceXML(log_com=self.log)
        self.__local_syncer_uuid = "urn:uuid:{}:{}:".format(
            uuid_tools.get_uuid(),
            _inst_xml.get_uuid_postfix(icswServiceEnum.monitor_slave)
        )
        self.__local_syncer_addr = "tcp://127.0.0.1:{:d}".format(
            _inst_xml.get_port_dict(icswServiceEnum.monitor_slave, command=True)
        )
        self.log(
            "connecting to local syncer {} (uuid={})".format(
                self.__local_syncer_addr,
                self.__local_syncer_uuid,
            )
        )
        self.main_socket.connect(self.__local_syncer_addr)

    def _init_network_sockets(self):
        self.network_bind(
            service_type_enum=icswServiceEnum.host_relay,
            client_type=icswServiceEnum.host_relay,
            pollin=self._recv_command_net,
        )
        self._register_local_syncer()

    def _resolve_address_noresolve(self, target):
        return target

    def _resolve_address_resolve(self, target):
        # to avoid loops in the 0MQ connection scheme (will result to nasty asserts)
        if target in self.__forward_lut:
            ip_addr = self.__forward_lut[target]
        else:
            orig_target = target
            if target.lower().startswith("localhost") or target.lower().startswith("127.0.0."):
                # map localhost to something 0MQ can handle
                target = process_tools.get_machine_name()
            # step 1: resolve to ip
            try:
                ip_addr = socket.gethostbyname(target)
            except:
                self.log(
                    "cannot resolve target '{}': {}".format(
                        target,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_CRITICAL
                )
                raise
            try:
                # step 2: try to get full name
                full_name, aliases, ip_addrs = socket.gethostbyaddr(ip_addr)
            except:
                # forget it
                pass
            else:
                # resolve full name
                self.log(
                    "ip_addr {} resolved to '{}' ({}), {}".format(
                        ip_addr,
                        full_name,
                        ", ".join(aliases) or "N/A",
                        ", ".join(ip_addrs) or "N/A"
                    )
                )
                try:
                    new_ip_addr = socket.gethostbyname(full_name)
                except:
                    self.log(
                        "cannot resolve full_name '{}': {}".format(
                            full_name,
                            process_tools.get_except_info()
                        ),
                        logging_tools.LOG_LEVEL_CRITICAL
                    )
                    raise
                else:
                    self.log(
                        "full_name {} resolves back to {} (was: {})".format(
                            full_name,
                            new_ip_addr,
                            ip_addr
                        ),
                        logging_tools.LOG_LEVEL_OK if new_ip_addr == ip_addr else logging_tools.LOG_LEVEL_ERROR
                    )
                    # should we use the new ip_addr ? dangerous, FIXME
                    # ip_addr = new_ip_addr
            if ip_addr not in self.__ip_lut:
                self.log("resolved {} to {}".format(target, ip_addr))
                self.__ip_lut[ip_addr] = target
            self.__forward_lut[target] = ip_addr
            self.log("ip resolving: {} -> {}".format(target, ip_addr))
            if orig_target != target:
                self.__forward_lut[orig_target] = ip_addr
                self.log("ip resolving: {} -> {}".format(orig_target, ip_addr))
        return ip_addr

    def _recv_command_ipc(self, zmq_sock):
        # to be improved via network_mixins, TODO
        return self._recv_command(zmq_sock, "ipc")

    def _recv_command_net(self, zmq_sock):
        return self._recv_command(zmq_sock, "net")

    def _recv_command(self, zmq_sock, src):
        data = zmq_sock.recv()
        if zmq_sock.getsockopt(zmq.RCVMORE):
            src_id = data
            data = zmq_sock.recv_unicode()
        else:
            src_id = None
        data = data.decode("ascii")
        # print("*", type(data), data)
        xml_input = data.startswith("<")
        # print(xml_input)
        if xml_input:
            srv_com = server_command.srv_command(source=data)
            srv_com["source_socket"] = src
            if src_id is None:
                src_id = srv_com["identity"].text
            else:
                srv_com["identity"] = src_id
            # print("src_id=", src_id)
        else:
            src_id, srv_com = self.ICH.handle(data)
        if srv_com is not None:
            if self.__verbose:
                self.log(
                    "got command '{}' for '{}' (XML: {})".format(
                        srv_com["command"].text,
                        srv_com["host"].text,
                        str(xml_input)
                    )
                )
            if "host" in srv_com and "port" in srv_com:
                # check target host, rewrite to ip
                t_host = srv_com["host"].text
                try:
                    ip_addr = self._resolve_address(t_host)
                except socket.gaierror:
                    self.log(
                        "resolve error for '{}'".format(t_host),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                    self.sender_socket.send_unicode(src_id, zmq.SNDMORE)
                    self.sender_socket.send_unicode(
                        "{:d}\0resolve error".format(limits.mon_STATE_CRITICAL)
                    )
                else:
                    _e = srv_com.builder()
                    srv_com[""].append(_e.host_unresolved(t_host))
                    cur_host = srv_com.xpath(".//ns:host", smart_strings=False)
                    if len(cur_host) == 1:
                        cur_host[0].text = ip_addr
                    else:
                        srv_com[""].append(_e.host(ip_addr))
                    # , _e.host(ip_addr)])
                    # srv_com["host_unresolved"] = t_host
                    # srv_com["host"] = ip_addr
                    # try to get the state of both addresses
                    if int(srv_com["*port"]) == self.__hm_port:
                        c_state = self.__client_dict.get(t_host, self.__client_dict.get(ip_addr, None))
                        # just for debug runs
                        if c_state is None:
                            # not needed
                            # HostConnection.delete_hc(srv_com)
                            con_modes = [ConnectionType.zmq, ConnectionType.tcp]
                        else:
                            con_modes = [c_state]
                    else:
                        con_modes = [ConnectionType.zmq]
                    full_con_mode = {
                        ConnectionType.zmq: "zeroMQ",
                        ConnectionType.tcp: "TCP",
                    }
                    # con_mode = "0"
                    # decide which code to use
                    if self.__verbose:
                        self.log(
                            "connection to '{}:{:d}' via {}".format(
                                t_host,
                                int(srv_com["port"].text),
                                ", ".join(
                                    [
                                        full_con_mode[_mode] for _mode in con_modes
                                    ]
                                ),
                            )
                        )
                    _host = srv_com["*host"]
                    com_name = srv_com["*command"]
                    if com_name == "ping" and _host in ["127.0.0.1", "localhost"]:
                        # special handling of local pings
                        self._handle_local_ping(src_id, srv_com)
                    elif int(srv_com["port"].text) != self.__hm_port:
                        # connect to non-host-monitoring service
                        for con_mode in con_modes:
                            if con_mode == ConnectionType.zmq:
                                self._send_to_nhm_service(src_id, srv_com, xml_input)
                            else:
                                self._send_to_old_nhm_service(src_id, srv_com, xml_input)
                    elif con_modes[0] == ConnectionType.zmq:
                        self._send_to_client(src_id, srv_com, xml_input)
                    elif con_modes[0] == ConnectionType.tcp:
                        self._send_to_old_client(src_id, srv_com, xml_input)
                    else:
                        self.log(
                            "unknown con_modes '{}', error".format(str(con_modes)),
                            logging_tools.LOG_LEVEL_CRITICAL
                        )
                    if self.__verbose:
                        self.log("send done")
            else:
                self.log(
                    "some keys missing (host and / or port)",
                    logging_tools.LOG_LEVEL_ERROR
                )
        else:
            self.log(
                "cannot interpret input data '{}' as srv_command".format(data),
                logging_tools.LOG_LEVEL_ERROR
            )
            # return a dummy message
            self._send_result(src_id, "cannot interpret", limits.mon_STATE_CRITICAL)
        self.__num_messages += 1
        if self.__num_messages % 1000 == 0:
            pid_list = sorted(list(set(self.CC.msi_block.pids)))
            self.log(
                "memory usage is {} after {}".format(
                    ", ".join(
                        [
                            "{:d}={:s}".format(
                                cur_pid,
                                logging_tools.get_size_str(process_tools.get_mem_info(cur_pid))
                            ) for cur_pid in pid_list
                        ]
                    ),
                    logging_tools.get_plural("message", self.__num_messages)
                )
            )

    def _ext_com_result(self, sub_s):
        self.log("external command gave:")
        for line_num, line in enumerate(sub_s.read().split("\n")):
            self.log(" {:2d} {}".format(line_num + 1, line))

    def _send_to_client(self, src_id, srv_com, xml_input):
        # send to host-monitor
        _host = srv_com["*host"]
        com_name = srv_com["*command"]
        # generate new xml from srv_com
        conn_str = "tcp://{}:{:d}".format(
            _host,
            int(srv_com["*port"])
        )
        # has connection_string vanished ?
        if conn_str in ZMQDiscovery.vanished:
            self.log(
                "{} has vanished, closing connection".format(conn_str),
                logging_tools.LOG_LEVEL_ERROR,
            )
            ZMQDiscovery.vanished.remove(conn_str)
            # get current connection
            cur_hc = HostConnection.get_hc_0mq(conn_str, DUMMY_0MQ_ID)
            cur_hc._close()
        if ZMQDiscovery.has_mapping(conn_str):
            id_str = ZMQDiscovery.get_connection_uuid(conn_str)
            if ICSW_DEBUG_MODE:
                self.log("conn_str {} has the cUUID {}".format(conn_str, id_str))
            cur_hc = HostConnection.get_hc_0mq(conn_str, id_str)
            cur_mes = cur_hc.add_message(
                HostMessage(com_name, src_id, srv_com, xml_input)
            )
            if com_name in self.local_mc:
                com_struct = self.local_mc[srv_com["command"].text]
                # handle commandline
                cur_hc.send(cur_mes, com_struct)
            else:
                cur_hc.return_error(
                    cur_mes,
                    "command '{}' not defined on relayer".format(com_name)
                )
        elif ZMQDiscovery.is_pending(conn_str):
            # discovery pending ?
            cur_hc = HostConnection.get_hc_0mq(conn_str)
            com_name = srv_com["command"].text
            cur_mes = cur_hc.add_message(HostMessage(com_name, src_id, srv_com, xml_input))
            cur_hc.return_error(cur_mes, "0MQ discovery in progress")
        else:
            ZMQDiscovery(srv_com, src_id, xml_input)

    def _handle_local_ping(self, src_id, srv_com):
        args = srv_com["*arg_list"].strip().split()
        cur_ns, _rest = self.__local_ping.handle_commandline(args)
        _struct = self.__local_ping(srv_com, cur_ns)
        if _struct is not None:
            # _args = NameSpace()
            self.__local_pings[_struct.seq_str] = (_struct, src_id, cur_ns)
            self.send_to_process(
                "socket",
                *_struct.run()
            )
        else:
            self._send_result(
                src_id,
                "wrong number of arguments ({:d})".format(len(args)),
                limits.mon_STATE_CRITICAL
            )

    def _socket_ping_result(self, src_proc, src_id, *args):
        ping_id = args[0]
        _stuff, _src_id, cur_ns = self.__local_pings[ping_id]
        del self.__local_pings[ping_id]
        _stuff.process(send_return=False, *args)
        _ret_state, _ret_str = self.__local_ping.interpret(_stuff.srv_com, cur_ns)
        self._send_result(
            _src_id,
            _ret_str,
            _ret_state,
        )
        del _stuff

    def _disconnect(self, conn_str):
        if conn_str in self.__nhm_connections:
            self.__nhm_connections.remove(conn_str)
            try:
                self.client.disconnect(conn_str)
            except:
                self.log(
                    "error disconnecting {}: {}".format(
                        conn_str,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                self.log("disconnected {}".format(conn_str))
        else:
            self.log(
                "connection {} not present in __nhm_connections, ignoring disconnect".format(
                    conn_str
                ),
                logging_tools.LOG_LEVEL_WARN
            )

    def _send_to_nhm_service(self, src_id, srv_com, xml_input, **kwargs):
        conn_str = "tcp://{}:{:d}".format(
            srv_com["host"].text,
            int(srv_com["port"].text),
        )
        if ZMQDiscovery.has_mapping(conn_str):
            connected = conn_str in self.__nhm_connections
            # trigger id discovery
            if not connected:
                try:
                    self.client_socket.connect(conn_str)
                except:
                    self._send_result(
                        src_id,
                        "error connecting: {}".format(process_tools.get_except_info()),
                        server_command.SRV_REPLY_STATE_CRITICAL
                    )
                else:
                    self.log(
                        "connected ROUTER client to {} (id={})".format(
                            conn_str,
                            ZMQDiscovery.get_connection_uuid(conn_str),
                        )
                    )
                    connected = True
                    self.__nhm_connections.add(conn_str)
            if connected:
                try:
                    if int(srv_com.get("raw_connect", "0")):
                        self.client_socket.send_unicode(
                            ZMQDiscovery.get_connection_uuid(conn_str),
                            zmq.SNDMORE | zmq.DONTWAIT
                        )
                        self.client_socket.send_unicode(
                            srv_com["command"].text,
                            zmq.DONTWAIT
                        )
                    else:
                        self.client_socket.send_unicode(
                            ZMQDiscovery.get_connection_uuid(conn_str),
                            zmq.SNDMORE | zmq.DONTWAIT
                        )
                        self.client_socket.send_unicode(
                            str(srv_com),
                            zmq.DONTWAIT
                        )
                except:
                    self._send_result(
                        src_id,
                        "error sending to {}: {}".format(
                            conn_str,
                            process_tools.get_except_info(),
                        ),
                        server_command.SRV_REPLY_STATE_ERROR
                    )
                else:
                    if int(srv_com.get("raw_connect", "0")):
                        self.__raw_nhm_dict[
                            ZMQDiscovery.get_connection_uuid(conn_str)
                        ] = (time.time(), srv_com)
                    elif kwargs.get("register", True):
                        self.__nhm_dict[srv_com["identity"].text] = (time.time(), srv_com)
        elif ZMQDiscovery.is_pending(conn_str):
            self._send_result(
                src_id,
                "0MQ discovery in progress",
                server_command.SRV_REPLY_STATE_CRITICAL
            )
        else:
            ZMQDiscovery(srv_com, src_id, xml_input)

    def _send_result(self, identity, reply_str, reply_state):
        if identity is None:
            self.log(
                "refuse to use identity==None, reply_str is [{:d}]: {}".format(
                    reply_state,
                    reply_str
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        else:
            self.sender_socket.send_unicode(identity, zmq.SNDMORE)
            self.sender_socket.send_unicode(
                "{:d}\0{}".format(
                    reply_state,
                    reply_str
                )
            )

    def _recv_nhm_result(self, zmq_sock):
        # receive result from non-host-monitor target
        data = []
        while True:
            data.append(zmq_sock.recv())
            if not zmq_sock.getsockopt(zmq.RCVMORE):
                break
        if len(data) == 2:
            src_id = data[0].decode("utf-8")
            if src_id in self.__raw_nhm_dict:
                srv_result = etree.fromstring(data[1])
                srv_com = self.__raw_nhm_dict[src_id][1]
                cur_id = srv_com["identity"].text
                self._send_result(cur_id, srv_result.findtext("nodestatus"), limits.mon_STATE_OK)
                del self.__raw_nhm_dict[src_id]
            else:
                srv_result = server_command.srv_command(source=data[1])
                if "command" in srv_result and srv_result["*command"] in ["relayer_info"]:
                    self.log(
                        "relayer_info command no longer supported",
                        logging_tools.LOG_LEVEL_ERROR
                    )
                elif "identity" in srv_result:
                    cur_id = srv_result["identity"].text
                    if cur_id in self.__nhm_dict:
                        del self.__nhm_dict[cur_id]
                        if "result" in srv_result:
                            self._send_result(
                                cur_id,
                                srv_result["result"].attrib["reply"],
                                server_command.srv_reply_to_nag_state(
                                    int(srv_result["result"].attrib["state"])
                                )
                            )
                        else:
                            self._send_result(
                                cur_id,
                                "no result tag found",
                                limits.mon_STATE_CRITICAL,
                            )
                    else:
                        self.log(
                            "received nhm-result for unknown id '{}', ignoring".format(cur_id),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                else:
                    self.log(
                        "no identity-tag found in result",
                        logging_tools.LOG_LEVEL_ERROR
                    )

    def _send_to_old_client(self, src_id, srv_com, xml_input):
        conn_str = "tcp://{}:{:d}".format(
            srv_com["host"].text,
            int(srv_com["port"].text)
        )
        cur_hc = HostConnection.get_hc_tcp(conn_str, dummy_connection=True)
        com_name = srv_com["command"].text
        cur_mes = cur_hc.add_message(HostMessage(com_name, src_id, srv_com, xml_input))
        if com_name in self.local_mc:
            com_struct = self.local_mc[com_name]
            cur_hc.send(cur_mes, com_struct)
            self.__old_send_lut[cur_mes.src_id] = cur_hc
        else:
            cur_hc.return_error(cur_mes, "command '{}' not defined on relayer".format(com_name))

    def _send_to_old_nhm_service(self, src_id, srv_com, xml_input):
        conn_str = "tcp://{}:{:d}".format(
            srv_com["host"].text,
            int(srv_com["port"].text)
        )
        cur_hc = HostConnection.get_hc_tcp(conn_str, dummy_connection=True)
        com_name = srv_com["command"].text
        cur_mes = cur_hc.add_message(HostMessage(com_name, src_id, srv_com, xml_input))
        cur_hc.send(cur_mes, None)
        self.__old_send_lut[cur_mes.src_id] = cur_hc

    def _handle_module_command(self, srv_com):
        try:
            self.local_mc[srv_com["command"].text](srv_com)
        except:
            for log_line in process_tools.icswExceptionInfo().log_lines:
                self.log(log_line, logging_tools.LOG_LEVEL_ERROR)
                srv_com.set_result(
                    "caught server exception '{}'".format(process_tools.get_except_info()),
                    server_command.SRV_REPLY_STATE_CRITICAL,
                )

    def send_passive_results_to_master(self, result_list):
        self.log(
            "sending {} to master".format(
                logging_tools.get_plural("passive result", len(result_list))
            )
        )
        srv_com = server_command.srv_command(
            command="passive_check_results"
        )
        _bldr = srv_com.builder()
        srv_com["results"] = _bldr.passive_results(
            *[
                # FIXME, TODO
                _bldr.passive_result("d")
            ]
        )
        self.send_to_syncer(srv_com)

    def send_passive_results_as_chunk_to_master(self, ascii_chunk):
        self.log("sending passive chunk (size {:d}) to master".format(len(ascii_chunk)))
        srv_com = server_command.srv_command(
            command="passive_check_results_as_chunk",
            ascii_chunk=ascii_chunk,
        )
        self.send_to_syncer(srv_com)

    def _close_ipc_sockets(self):
        if self.receiver_socket is not None:
            self.unregister_poller(self.receiver_socket, zmq.POLLIN)
            self.receiver_socket.close()
        if self.sender_socket is not None:
            self.sender_socket.close()
        if self.client_socket is not None:
            self.unregister_poller(self.client_socket, zmq.POLLIN)
            self.client_socket.close()
        HostConnection.global_close()

    def _close_io_sockets(self):
        self.network_unbind()

    def loop_end(self):
        self.COM_close()
        self._close_ipc_sockets()
        self._close_io_sockets()
        ZMQDiscovery.destroy()

    def loop_post(self):
        self.CC.close()
