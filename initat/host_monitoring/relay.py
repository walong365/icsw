# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of host-monitoring
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

""" host-monitoring, with 0MQ and direct socket support, relay part """

from initat.host_monitoring import limits, hm_classes
from initat.host_monitoring.config import global_config
from initat.host_monitoring.constants import MAPPING_FILE_TYPES, MASTER_FILE_NAME, ICINGA_TOP_DIR
from initat.host_monitoring.discovery import id_discovery
from initat.host_monitoring.hm_direct import socket_process
from initat.host_monitoring.struct import host_connection, host_message
from initat.host_monitoring.tools import my_cached_file
from initat.host_monitoring.version import VERSION_STRING
from lxml import etree  # @UnresolvedImport
from lxml.builder import E  # @UnresolvedImport
import StringIO
import base64
import bz2
import commands
import configfile
import logging_tools
import marshal
import os
import process_tools
import resource
import server_command
import socket
import sys
import threading_tools
import time
import uuid_tools
import zmq


class relay_code(threading_tools.process_pool):
    def __init__(self):
        # monkey path process tools to allow consistent access
        process_tools.ALLOW_MULTIPLE_INSTANCES = False
        self.objgraph = None
        if global_config["OBJGRAPH"]:
            try:
                import objgraph
            except ImportError:
                pass
            else:
                self.objgraph = objgraph
        # copy to access from modules
        from initat.host_monitoring import modules
        self.modules = modules
        self.global_config = global_config
        self.__verbose = global_config["VERBOSE"]
        self.__autosense = global_config["AUTOSENSE"]
        self.__force_resolve = global_config["FORCERESOLVE"]
        self.__log_cache, self.__log_template = ([], None)
        threading_tools.process_pool.__init__(self, "main", zmq=True, zmq_debug=global_config["ZMQ_DEBUG"])
        self.renice(global_config["NICE_LEVEL"])
        # ip resolving
        if self.__force_resolve:
            self.log("automatic resolving is enabled", logging_tools.LOG_LEVEL_WARN)
            self._resolve_address = self._resolve_address_resolve
        else:
            self.log("automatic resolving is disabled")
            self._resolve_address = self._resolve_address_noresolve
        # pending_connection.init(self)
        # global timeout value for host connections
        self.__global_timeout = global_config["TIMEOUT"]
        self._show_config()
        self._get_mon_version()
        host_connection.init(self, global_config["BACKLOG_SIZE"], self.__global_timeout, self.__verbose)
        # init lut
        self.__old_send_lut = {}
        # we need no icmp capability in relaying
        self.add_process(socket_process("socket", icmp=False), start=True)
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self.install_signal_handlers()
        id_discovery.init(self, global_config["BACKLOG_SIZE"], global_config["TIMEOUT"], self.__verbose, self.__force_resolve)
        self._init_filecache()
        self._init_msi_block()
        self._change_rlimits()
        self._init_network_sockets()
        self._init_ipc_sockets()
        self.register_exception("int_error", self._sigint)
        self.register_exception("term_error", self._sigint)
        self.register_exception("hup_error", self._hup_error)
        self.__delayed = []
        self.register_timer(self._check_timeout, 2)
        self.__last_master_contact = None
        self.register_func("socket_result", self._socket_result)
        self.version_dict = {}
        self._init_master()
        if self.objgraph:
            self.register_timer(self._objgraph_run, 30, instant=True)
        if not self._init_commands():
            self._sigint("error init")

    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            while self.__log_cache:
                self.__log_template.log(*self.__log_cache.pop(0))
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))

    def _sigint(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True

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

    def _get_mon_version(self):
        _icinga_bin = "/opt/icinga/bin/icinga"
        self.__mon_version = "N/A"
        if os.path.isfile(_icinga_bin):
            cur_stat, cur_out = commands.getstatusoutput("{} -v".format(_icinga_bin))
            lines = cur_out.split("\n")
            self.log("'{} -v' gave {:d}, first 5 lines:".format(_icinga_bin, cur_stat))
            for _line in lines[:5]:
                self.log("  {}".format(_line))
            lines = [line.lower() for line in lines if line.lower().startswith("icinga")]
            if lines:
                self.__mon_version = lines.pop(0).strip().split()[-1]
        self.log("mon_version is '{}'".format(self.__mon_version))

    def _hup_error(self, err_cause):
        self.log("got SIGHUP ({})".format(err_cause), logging_tools.LOG_LEVEL_WARN)
        self.log(" - setting all clients with connmode TCP to unknown", logging_tools.LOG_LEVEL_WARN)
        self.log(" - reloading 0MQ mappings", logging_tools.LOG_LEVEL_WARN)
        num_c = 0
        for t_host, c_state in self.__client_dict.iteritems():
            if c_state == "T":
                self.__client_dict[t_host] = None
                num_c += 1
        self.log("cleared {}".format(logging_tools.get_plural("state", num_c)))
        id_discovery.reload_mapping()

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
        # try:
        #    resource.setrlimit(resource.RLIMIT_OFILE, 4069)

    def _init_master(self):
        self.__master_sync_id = None
        # register_to_master_timer set ?
        self.__rmt_set = False
        self.master_ip = None
        self.master_port = None
        self.master_uuid = None
        if os.path.isfile(MASTER_FILE_NAME):
            try:
                master_xml = etree.fromstring(file(MASTER_FILE_NAME, "r").read())  # @UndefinedVariable
            except:
                self.log("error interpreting master_file '{}': {}".format(MASTER_FILE_NAME, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            else:
                self._register_master(master_xml.attrib["ip"], master_xml.attrib["uuid"], int(master_xml.attrib["port"]), write=False)
        else:
            self.log("no master_file found", logging_tools.LOG_LEVEL_WARN)

    def _handle_relayer_info_result(self, srv_com):
        sync_id = int(srv_com["*sync_id"])
        ok = sync_id == self.__master_sync_id
        self.log(
            "got ack for syncer_id {:d} (sent: {})".format(
                sync_id,
                self.__master_sync_id,
            ),
            logging_tools.LOG_LEVEL_OK if ok else logging_tools.LOG_LEVEL_ERROR,
        )
        if ok:
            self.__master_sync_id = None

    def _contact_master(self):
        if self.master_ip:
            # updated monitoring version
            self._get_mon_version()
            if self.__master_sync_id:
                self.log("master_sync_id still set, closing connection and retrying", logging_tools.LOG_LEVEL_ERROR)
                self.__master_sync_id = False

            self.__master_sync_id = int(time.time())
            srv_com = server_command.srv_command(
                command="relayer_info",
                host=self.master_ip,
                port="{:d}".format(self.master_port),
                relayer_version=VERSION_STRING,
                uuid=uuid_tools.get_uuid().get_urn(),
                mon_version=self.__mon_version,
                sync_id="{:d}".format(self.__master_sync_id),
            )
            self.log(
                u"send master info (Rel {}, Mon {})".format(
                    VERSION_STRING,
                    self.__mon_version
                )
            )
            self._send_to_nhm_service(None, srv_com, None, register=False)

    def _register_master(self, master_ip, master_uuid, master_port, write=True):
        self.master_ip = master_ip
        self.master_uuid = master_uuid
        self.master_port = master_port
        _ets = etree.tostring  # @UndefinedVariable
        if write:
            file(MASTER_FILE_NAME, "w").write(_ets(
                E.master_data(
                    ip=self.master_ip,
                    uuid=self.master_uuid,
                    port="{:d}".format(self.master_port)
                ),
                pretty_print=True
            ))
        conn_str = u"tcp://{}:{:d}".format(self.master_ip, self.master_port)
        self.log(u"registered master at {} ({})".format(conn_str, self.master_uuid))
        id_discovery.set_mapping(conn_str, self.master_uuid)
        if not self.__rmt_set:
            self.__rmt_set = True
            # force connection
            self._contact_master()
            # report to master after 5 seconds
            self.register_timer(self._contact_master, 5, instant=False, oneshot=True)
            # report to master every 10 minutes
            self.register_timer(self._contact_master, 600, instant=False)

    def _init_filecache(self):
        self.__client_dict = {}
        self.__last_tried = {}
        if not self.__autosense:
            self.__new_clients, self.__old_clients = (
                my_cached_file("/tmp/.new_clients", log_handle=self.log),
                my_cached_file("/tmp/.old_clients", log_handle=self.log)
            )
        else:
            if os.path.isfile(MAPPING_FILE_TYPES):
                self.__client_dict.update(dict([(key, "0") for key in file(MAPPING_FILE_TYPES, "r").read().split("\n") if key.strip()]))
        self.__default_0mq = False

    def _new_client(self, c_ip, c_port):
        self._set_client_state(c_ip, c_port, "0")

    def _old_client(self, c_ip, c_port):
        self._set_client_state(c_ip, c_port, "T")

    def _set_client_state(self, c_ip, c_port, c_type):
        write_file = False
        if self.__autosense:
            check_names = [c_ip]
            if self.__force_resolve:
                if c_ip in self.__ip_lut:
                    real_name = self.__ip_lut[c_ip]
                    if real_name != c_ip:
                        check_names.append(real_name)
            for c_name in check_names:
                if self.__client_dict.get(c_name, None) != c_type and c_port == 2001:
                    self.log("setting client '{}:{:d}' to '{}'".format(c_name, c_port, c_type))
                    self.__client_dict[c_name] = c_type
                    write_file = True
        if write_file:
            file(MAPPING_FILE_TYPES, "w").write("\n".join([key for key, value in self.__client_dict.iteritems() if value == "0"]))

    def _init_msi_block(self):
        # store pid name because global_config becomes unavailable after SIGTERM
        self.__pid_name = global_config["PID_NAME"]
        process_tools.save_pids(global_config["PID_NAME"], mult=3)
        process_tools.append_pids(global_config["PID_NAME"], pid=configfile.get_manager_pid(), mult=3)
        if True:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("collrelay")
            msi_block.add_actual_pid(mult=3, fuzzy_ceiling=4, process_name="main")
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=3, process_name="manager")
            msi_block.start_command = "/etc/init.d/host-relay start"
            msi_block.stop_command = "/etc/init.d/host-relay force-stop"
            msi_block.kill_pids = True
            # msi_block.heartbeat_timeout = 60
            msi_block.save_block()
        else:
            msi_block = None
        self.__msi_block = msi_block

    def process_start(self, src_process, src_pid):
        # twisted needs 4 threads if connecting to TCP clients, 3 if not (???)
        if src_process == "socket":
            if src_pid in self.__msi_block.get_pids():
                # add one extra thread
                mult = 1
            else:
                mult = 3
        else:
            mult = 3
        process_tools.append_pids(self.__pid_name, src_pid, mult=mult)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(src_pid, mult=mult, process_name=src_process)
            self.__msi_block.save_block()

    def _check_timeout(self):
        host_connection.check_timeout_global(id_discovery)
        cur_time = time.time()
        # check nhm timeouts
        del_list = []
        for key, value in self.__nhm_dict.iteritems():
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
        for key, value in self.__raw_nhm_dict.iteritems():
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
            self.log("{} in delayed queue".format(logging_tools.get_plural("object", len(self.__delayed))))
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
            self.__old_send_lut.pop(src_id)._handle_old_result(src_id, data_str, is_error)
        else:
            self.log(
                "result for non-existing id '{}' received, discarding".format(src_id),
                logging_tools.LOG_LEVEL_ERROR)

    def send_result(self, src_id, ret_str):
        self.sender_socket.send_unicode(src_id, zmq.SNDMORE)  # @UndefinedVariable
        self.sender_socket.send_unicode(ret_str)

    def _init_ipc_sockets(self):
        # init IP lookup table
        if self.__force_resolve:
            self.__ip_lut = {}
            self.__forward_lut = {}
        self.__num_messages = 0
        # nhm (not host monitoring) dictionary for timeout
        self.__nhm_dict = {}
        # raw_nhm (not host monitoring) dictionary for timeout, raw connections (no XML)
        self.__raw_nhm_dict = {}
        self.__nhm_connections = set()
        sock_list = [
            ("ipc", "receiver", zmq.PULL, 2),  # @UndefinedVariable
            ("ipc", "sender", zmq.PUB, 1024),  # @UndefinedVariable
        ]
        [setattr(self, "{}_socket".format(short_sock_name), None) for _sock_proto, short_sock_name, _a0, _b0 in sock_list]
        for _sock_proto, short_sock_name, sock_type, hwm_size in sock_list:
            sock_name = process_tools.get_zmq_ipc_name(short_sock_name)
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
            try:
                process_tools.bind_zmq_socket(cur_socket, sock_name)
                # client.bind("tcp://*:8888")
            except zmq.ZMQError:
                self.log(
                    "error binding {}: {}" .format(
                        short_sock_name,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_CRITICAL
                )
                raise
            else:
                setattr(self, "{}_socket".format(short_sock_name), cur_socket)
                _backlog_size = global_config["BACKLOG_SIZE"]
                os.chmod(file_name, 0777)
                cur_socket.setsockopt(zmq.LINGER, 0)  # @UndefinedVariable
                cur_socket.setsockopt(zmq.SNDHWM, hwm_size)  # @UndefinedVariable
                cur_socket.setsockopt(zmq.RCVHWM, hwm_size)  # @UndefinedVariable
                if sock_type == zmq.PULL:  # @UndefinedVariable
                    self.register_poller(cur_socket, zmq.POLLIN, self._recv_command_ipc)  # @UndefinedVariable
        self.client_socket = process_tools.get_socket(
            self.zmq_context,
            "ROUTER",
            identity="ccollclient:{}".format(process_tools.get_machine_name()),
            linger=0,
            sndhwm=2,
            rcvhwm=2,
            immediate=True,
        )
        self.register_poller(self.client_socket, zmq.POLLIN, self._recv_nhm_result)  # @UndefinedVariable

    def _init_network_sockets(self):
        client = self.zmq_context.socket(zmq.ROUTER)  # @UndefinedVariable
        uuid = "{}:relayer".format(uuid_tools.get_uuid().get_urn())
        client.setsockopt(zmq.IDENTITY, uuid)  # @UndefinedVariable
        # AL 2014-02-13, increased SNDHWM / RCVHWM from 10 to 128
        client.setsockopt(zmq.SNDHWM, 128)  # @UndefinedVariable
        client.setsockopt(zmq.RCVHWM, 128)  # @UndefinedVariable
        client.setsockopt(zmq.RECONNECT_IVL_MAX, 500)  # @UndefinedVariable
        client.setsockopt(zmq.RECONNECT_IVL, 200)  # @UndefinedVariable
        client.setsockopt(zmq.TCP_KEEPALIVE, 1)  # @UndefinedVariable
        client.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 300)  # @UndefinedVariable
        conn_str = "tcp://*:{:d}".format(
            global_config["COM_PORT"])
        try:
            client.bind(conn_str)
        except zmq.ZMQError:
            self.log(
                "error binding to *:{:d}: {}".format(
                    global_config["COM_PORT"],
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_CRITICAL
            )
            client.close()
            self.network_socket = None
        else:
            self.log(
                "bound to {} (ID {})".format(
                    conn_str,
                    uuid
                )
            )
            self.register_poller(client, zmq.POLLIN, self._recv_command_net)  # @UndefinedVariable
            self.network_socket = client

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
        if zmq_sock.getsockopt(zmq.RCVMORE):  # @UndefinedVariable
            src_id = data
            data = zmq_sock.recv()
        else:
            src_id = None
        xml_input = data.startswith("<")
        srv_com = None
        if xml_input:
            srv_com = server_command.srv_command(source=data)
            srv_com["source_socket"] = src
            if src_id is None:
                src_id = srv_com["identity"].text
            else:
                srv_com["identity"] = src_id
        else:
            if data.count(";") > 1:
                if data.startswith(";"):
                    # new format
                    proto_version, data = data[1:].split(";", 1)
                else:
                    proto_version, data = ("0", data)
                proto_version = int(proto_version)
                if proto_version == 0:
                    parts = data.split(";", 3)
                    # insert default timeout of 10 seconds
                    parts.insert(3, "10")
                    parts.insert(4, "0")
                elif proto_version == 1:
                    parts = data.split(";", 4)
                    parts.insert(4, "0")
                else:
                    parts = data.split(";", 5)
                src_id = parts.pop(0)
                # parse new format
                if parts[4].endswith(";"):
                    com_part = parts[4][:-1]
                else:
                    com_part = parts[4]
                # iterative parser
                try:
                    arg_list = []
                    while com_part.count(";"):
                        cur_size, cur_str = com_part.split(";", 1)
                        cur_size = int(cur_size)
                        com_part = cur_str[cur_size + 1:]
                        arg_list.append(cur_str[:cur_size].decode("utf-8"))
                    if com_part:
                        raise ValueError("not fully parsed ({})".format(com_part))
                    else:
                        cur_com = arg_list.pop(0) if arg_list else ""
                        srv_com = server_command.srv_command(command=cur_com, identity=src_id)
                        _e = srv_com.builder()
                        srv_com[""].extend(
                            [
                                _e.host(parts[0]),
                                _e.port(parts[1]),
                                _e.timeout(parts[2]),
                                _e.raw_connect(parts[3]),
                                _e.arguments(
                                    *[getattr(_e, "arg{:d}".format(arg_idx))(arg) for arg_idx, arg in enumerate(arg_list)]
                                ),
                                _e.arg_list(" ".join(arg_list)),
                            ]
                    )
                except:
                    self.log("error parsing {}: {}".format(data, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                    srv_com = None
        if srv_com is not None:
            if self.__verbose:
                self.log("got command '{}' for '{}' (XML: {})".format(
                    srv_com["command"].text,
                    srv_com["host"].text,
                    str(xml_input)))
            if "host" in srv_com and "port" in srv_com:
                # check target host, rewrite to ip
                t_host = srv_com["host"].text
                if t_host == "DIRECT":
                    self._handle_direct_command(src_id, srv_com)
                else:
                    try:
                        ip_addr = self._resolve_address(t_host)
                    except socket.gaierror:
                        self.log("resolve error for '{}'".format(t_host),
                                 logging_tools.LOG_LEVEL_ERROR)
                        self.sender_socket.send_unicode(src_id, zmq.SNDMORE)  # @UndefinedVariable
                        self.sender_socket.send_unicode("{:d}\0resolve error".format(limits.nag_STATE_CRITICAL))
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
                        if self.__autosense:
                            # try to get the state of both addresses
                            c_state = self.__client_dict.get(t_host, self.__client_dict.get(ip_addr, None))
                            # just for debug runs
                            # c_state = "T"
                            if c_state is None:
                                # not needed
                                # host_connection.delete_hc(srv_com)
                                if t_host not in self.__last_tried:
                                    self.__last_tried[t_host] = "T" if self.__default_0mq else "0"
                                self.__last_tried[t_host] = {
                                    "T": "0",
                                    "0": "T",
                                }[self.__last_tried[t_host]]
                                c_state = self.__last_tried[t_host]
                            con_mode = c_state
                            # con_mode = "0"
                        else:
                            self.__old_clients.update()
                            self.__new_clients.update()
                            if t_host in self.__new_clients:
                                con_mode = "0"
                            elif t_host in self.__old_clients:
                                con_mode = "T"
                            elif self.__default_0mq:
                                con_mode = "0"
                            else:
                                con_mode = "T"
                        # decide which code to use
                        if self.__verbose:
                            self.log(
                                "connection to '{}:{:d}' via {}".format(
                                    t_host,
                                    int(srv_com["port"].text),
                                    con_mode
                                )
                            )
                        if int(srv_com["port"].text) != 2001:
                            # connect to non-host-monitoring service
                            if con_mode == "0":
                                self._send_to_nhm_service(src_id, srv_com, xml_input)
                            else:
                                self._send_to_old_nhm_service(src_id, srv_com, xml_input)
                        elif con_mode == "0":
                            self._send_to_client(src_id, srv_com, xml_input)
                        elif con_mode == "T":
                            self._send_to_old_client(src_id, srv_com, xml_input)
                        else:
                            self.log(
                                "unknown con_mode '{}', error".format(con_mode),
                                logging_tools.LOG_LEVEL_CRITICAL
                            )
                        if self.__verbose:
                            self.log("send done")
            else:
                self.log("some keys missing (host and / or port)",
                         logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log(
                "cannot interpret input data '{}' as srv_command".format(data),
                logging_tools.LOG_LEVEL_ERROR
            )
            # return a dummy message
            self._send_result(src_id, "cannot interpret", limits.nag_STATE_CRITICAL)
        self.__num_messages += 1
        if self.__num_messages % 1000 == 0:
            pid_list = sorted(list(set(self.__msi_block.pids)))
            self.log("memory usage is {} after {}".format(
                ", ".join(["{:d}={:s}".format(cur_pid, logging_tools.get_size_str(process_tools.get_mem_info(cur_pid))) for cur_pid in pid_list]),
                logging_tools.get_plural("message", self.__num_messages))
            )

    def _check_version(self, key, new_vers):
        if new_vers == self.version_dict.get(key):
            renew, log_str = (False, "no newer version ({:d})".format(new_vers))
        else:
            renew = True
            if key in self.version_dict:
                log_str = "newer version ({:d} -> {:d})".format(self.version_dict.get(key, 0), new_vers)
            else:
                log_str = "new version ({:d})".format(new_vers)
            self.version_dict[key] = new_vers
        return renew, log_str

    def _clear_version(self, key):
        if key in self.version_dict:
            del self.version_dict[key]

    def _handle_direct_command(self, src_id, srv_com):
        # only DIRECT command from ccollclientzmq
        # print "*", src_id
        cur_com = srv_com["command"].text
        if self.__verbose:
            self.log("got DIRECT command {}".format(cur_com))
        if cur_com in ["file_content", "file_content_bulk"]:
            if cur_com == "file_content":
                ret_com = self._file_content(srv_com)
            else:
                ret_com = self._file_content_bulk(srv_com)
            # set values
            self._send_to_master(ret_com)
        elif cur_com == "clear_directory":
            self._clear_directory(srv_com)
        elif cur_com == "clear_directories":
            self._clear_directories(srv_com)
        elif cur_com == "call_command":
            # also check for version ? compare with file versions ? deleted files ? FIXME
            cmdline = srv_com["cmdline"].text
            self.log("got command '{}'".format(cmdline))
            new_ss = hm_classes.subprocess_struct(
                server_command.srv_command(command=cmdline, result="0"),
                cmdline,
                cb_func=self._ext_com_result
            )
            new_ss.run()
            self.__delayed.append(new_ss)
        elif cur_com == "register_master":
            self._register_master(
                srv_com["master_ip"].text,
                srv_com["identity"].text,
                int(srv_com["master_port"].text)
            )
        else:
            # add to cache ?
            self._send_to_master(srv_com)

    def send_passive_results_to_master(self, result_list):
        self.log("sending {} to master".format(logging_tools.get_plural("passive result", len(result_list))))
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
        self._send_to_master(srv_com)

    def send_passive_results_as_chunk_to_master(self, ascii_chunk):
        self.log("sending passive chunk (size {:d}) to master".format(len(ascii_chunk)))
        srv_com = server_command.srv_command(
            command="passive_check_results_as_chunk",
            ascii_chunk=ascii_chunk,
        )
        self._send_to_master(srv_com)

    def _send_to_master(self, srv_com):
        if self.master_ip:
            srv_com["host"] = self.master_ip
            srv_com["port"] = "{:d}".format(self.master_port)
            self._send_to_nhm_service(None, srv_com, None, register=False)
        else:
            self.log("no master-ip set, discarding message", logging_tools.LOG_LEVEL_WARN)

    def _ext_com_result(self, sub_s):
        self.log("external command gave:")
        for line_num, line in enumerate(sub_s.read().split("\n")):
            self.log(" {:2d} {}".format(line_num + 1, line))

    def _send_to_client(self, src_id, srv_com, xml_input):
        # generate new xml from srv_com
        conn_str = "tcp://{}:{:d}".format(
            srv_com["host"].text,
            int(srv_com["port"].text)
        )
        if id_discovery.has_mapping(conn_str):
            id_str = id_discovery.get_mapping(conn_str)
            cur_hc = host_connection.get_hc_0mq(conn_str, id_str)
            com_name = srv_com["command"].text
            cur_mes = cur_hc.add_message(host_message(com_name, src_id, srv_com, xml_input))
            if com_name in self.modules.command_dict:
                com_struct = self.modules.command_dict[srv_com["command"].text]
                # handle commandline
                cur_hc.send(cur_mes, com_struct)
            else:
                cur_hc.return_error(cur_mes, "command '{}' not defined on relayer".format(com_name))
        elif id_discovery.is_pending(conn_str):
            cur_hc = host_connection.get_hc_0mq(conn_str)
            com_name = srv_com["command"].text
            cur_mes = cur_hc.add_message(host_message(com_name, src_id, srv_com, xml_input))
            cur_hc.return_error(cur_mes, "0mq discovery in progress")
        else:
            id_discovery(srv_com, src_id, xml_input)

    def _disconnect(self, conn_str):
        if conn_str in self.__nhm_connections:
            self.__nhm_connections.remove(conn_str)
            try:
                self.client.disconnect(conn_str)
            except:
                self.log(u"error disconnecting {}: {}".format(conn_str, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            else:
                self.log("disconnected {}".format(conn_str))
        else:
            self.log(u"connection {} not present in __nhm_connections, ignoring disconnect".format(conn_str), logging_tools.LOG_LEVEL_WARN)

    def _send_to_nhm_service(self, src_id, srv_com, xml_input, **kwargs):
        conn_str = "tcp://{}:{:d}".format(
            srv_com["host"].text,
            int(srv_com["port"].text)
        )
        if id_discovery.has_mapping(conn_str):
            connected = conn_str in self.__nhm_connections
            # trigger id discovery
            if not connected:
                try:
                    self.client_socket.connect(conn_str)
                except:
                    self._send_result(src_id, "error connecting: {}".format(process_tools.get_except_info()), server_command.SRV_REPLY_STATE_CRITICAL)
                else:
                    self.log("connected ROUTER client to {}".format(conn_str))
                    connected = True
                    self.__nhm_connections.add(conn_str)
            if connected:
                try:
                    if int(srv_com.get("raw_connect", "0")):
                        self.client_socket.send_unicode(id_discovery.get_mapping(conn_str), zmq.SNDMORE | zmq.DONTWAIT)  # @UndefinedVariable
                        self.client_socket.send_unicode(srv_com["command"].text, zmq.DONTWAIT)  # @UndefinedVariable
                    else:
                        self.client_socket.send_unicode(id_discovery.get_mapping(conn_str), zmq.SNDMORE | zmq.DONTWAIT)  # @UndefinedVariable
                        self.client_socket.send_unicode(unicode(srv_com), zmq.DONTWAIT)  # @UndefinedVariable
                except:
                    self._send_result(
                        src_id,
                        "error sending to {}: {}".format(
                            conn_str,
                            process_tools.get_except_info(),
                        ),
                        server_command.SRV_REPLY_STATE_CRITICAL
                    )
                else:
                    if int(srv_com.get("raw_connect", "0")):
                        self.__raw_nhm_dict[id_discovery.get_mapping(conn_str)] = (time.time(), srv_com)
                    elif kwargs.get("register", True):
                        self.__nhm_dict[srv_com["identity"].text] = (time.time(), srv_com)
        elif id_discovery.is_pending(conn_str):
            self._send_result(src_id, "0mq discovery in progress", server_command.SRV_REPLY_STATE_CRITICAL)
        else:
            id_discovery(srv_com, src_id, xml_input)

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
            self.sender_socket.send_unicode(identity, zmq.SNDMORE)  # @UndefinedVariable
            self.sender_socket.send_unicode(
                "{:d}\0{}".format(
                    reply_state,
                    reply_str
                )
            )

    def _recv_nhm_result(self, zmq_sock):
        data = []
        while True:
            data.append(zmq_sock.recv())
            if not zmq_sock.getsockopt(zmq.RCVMORE):  # @UndefinedVariable
                break
        if len(data) == 2:
            if data[0] in self.__raw_nhm_dict:
                srv_result = etree.fromstring(data[1])  # @UndefinedVariable
                srv_com = self.__raw_nhm_dict[data[0]][1]
                cur_id = srv_com["identity"].text
                self._send_result(cur_id, srv_result.findtext("nodestatus"), limits.nag_STATE_OK)
                del self.__raw_nhm_dict[data[0]]
            else:
                srv_result = server_command.srv_command(source=data[1])
                if "command" in srv_result and srv_result["*command"] in ["relayer_info"]:
                    self._handle_relayer_info_result(srv_result)
                elif "identity" in srv_result:
                    cur_id = srv_result["identity"].text
                    if cur_id in self.__nhm_dict:
                        del self.__nhm_dict[cur_id]
                        self._send_result(
                            cur_id,
                            srv_result["result"].attrib["reply"],
                            int(srv_result["result"].attrib["state"]))
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
        cur_hc = host_connection.get_hc_tcp(conn_str, dummy_connection=True)
        com_name = srv_com["command"].text
        cur_mes = cur_hc.add_message(host_message(com_name, src_id, srv_com, xml_input))
        if com_name in self.modules.command_dict:
            com_struct = self.modules.command_dict[com_name]
            cur_hc.send(cur_mes, com_struct)
            self.__old_send_lut[cur_mes.src_id] = cur_hc
        else:
            cur_hc.return_error(cur_mes, "command '{}' not defined on relayer".format(com_name))

    def _send_to_old_nhm_service(self, src_id, srv_com, xml_input):
        conn_str = "tcp://{}:{:d}".format(
            srv_com["host"].text,
            int(srv_com["port"].text)
        )
        cur_hc = host_connection.get_hc_tcp(conn_str, dummy_connection=True)
        com_name = srv_com["command"].text
        cur_mes = cur_hc.add_message(host_message(com_name, src_id, srv_com, xml_input))
        cur_hc.send(cur_mes, None)
        self.__old_send_lut[cur_mes.src_id] = cur_hc

    def _handle_module_command(self, srv_com):
        try:
            self.commands[srv_com["command"].text](srv_com)
        except:
            for log_line in process_tools.exception_info().log_lines:
                self.log(log_line, logging_tools.LOG_LEVEL_ERROR)
                srv_com.set_result(
                    "caught server exception '{}'".format(process_tools.get_except_info()),
                    server_command.SRV_REPLY_STATE_CRITICAL,
                    )

    def _show_config(self):
        try:
            for log_line, log_level in global_config.get_log():
                self.log("Config info : [{:d}] {}".format(log_level, log_line))
        except:
            self.log(
                "error showing configfile log, old configfile ? ({})".format(process_tools.get_except_info()),
                logging_tools.LOG_LEVEL_ERROR
            )
        conf_info = global_config.get_config_info()
        self.log("Found {}:".format(logging_tools.get_plural("valid configline", len(conf_info))))
        for conf in conf_info:
            self.log("Config : {}".format(conf))

    def _close_ipc_sockets(self):
        if self.receiver_socket is not None:
            self.unregister_poller(self.receiver_socket, zmq.POLLIN)  # @UndefinedVariable
            self.receiver_socket.close()
        if self.sender_socket is not None:
            self.sender_socket.close()
        if self.client_socket is not None:
            self.unregister_poller(self.client_socket, zmq.POLLIN)  # @UndefinedVariable
            self.client_socket.close()
        host_connection.global_close()

    def _close_io_sockets(self):
        if self.network_socket:
            self.network_socket.close()

    def loop_end(self):
        self._close_ipc_sockets()
        self._close_io_sockets()
        id_discovery.destroy()
        from initat.host_monitoring import modules
        for cur_mod in modules.module_list:
            cur_mod.close_module()
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()

    def loop_post(self):
        self.__log_template.close()

    def _init_commands(self):
        self.log("init commands")
        self.module_list = self.modules.module_list
        self.commands = self.modules.command_dict
        self.log("modules import errors:", logging_tools.LOG_LEVEL_ERROR)
        for mod_name, com_name, error_str in self.modules.IMPORT_ERRORS:
            self.log("{:<24s} {:<32s} {}".format(mod_name.split(".")[-1], com_name, error_str), logging_tools.LOG_LEVEL_ERROR)
        _init_ok = True
        for call_name, add_self in [
            ("register_server", True),
            ("init_module", False)
        ]:
            for cur_mod in self.modules.module_list:
                if self.__verbose:
                    self.log(
                        "calling {} for module '{}'".format(
                            call_name,
                            cur_mod.name
                        )
                    )
                try:
                    if add_self:
                        getattr(cur_mod, call_name)(self)
                    else:
                        getattr(cur_mod, call_name)()
                except:
                    exc_info = process_tools.exception_info()
                    for log_line in exc_info.log_lines:
                        self.log(log_line, logging_tools.LOG_LEVEL_CRITICAL)
                    _init_ok = False
                    break
            if not _init_ok:
                break
        return _init_ok
    # file handling commands

    def _clear_directory(self, srv_com):
        t_dir = srv_com["directory"].text
        self._clear_dir(t_dir)

    def _clear_directories(self, srv_com):
        # print srv_com.pretty_print()
        for dir_name in srv_com.xpath(".//ns:directories/ns:directory/text()"):
            self._clear_dir(dir_name)

    def _clear_dir(self, t_dir):
        if not t_dir.startswith(ICINGA_TOP_DIR):
            self.log("refuse to operate outside '{}'".format(ICINGA_TOP_DIR), logging_tools.LOG_LEVEL_CRITICAL)
        else:
            self.log("clearing directory {}".format(t_dir))
            num_rem = 0
            if os.path.isdir(t_dir):
                for entry in os.listdir(t_dir):
                    f_path = os.path.join(t_dir, entry)
                    # remove from version_dict
                    self._clear_version(f_path)
                    if os.path.isfile(f_path):
                        try:
                            os.unlink(f_path)
                        except:
                            self.log(
                                "cannot remove {}: {}".format(
                                    f_path,
                                    process_tools.get_except_info()
                                ),
                                logging_tools.LOG_LEVEL_ERROR
                            )
                        else:
                            num_rem += 1
            else:
                self.log("directory '{}' does not exist".format(t_dir), logging_tools.LOG_LEVEL_ERROR)
            self.log("removed {} in {}".format(logging_tools.get_plural("file", num_rem), t_dir))

    def _file_content(self, srv_com):
        t_file = srv_com["file_name"].text
        new_vers = int(srv_com["version"].text)
        ret_com = server_command.srv_command(
            command="file_content_result",
            version="{:d}".format(new_vers),
            slave_name=srv_com["slave_name"].text,
            file_name=t_file,
        )
        success = self._store_file(
            t_file,
            new_vers,
            int(srv_com["uid"].text),
            int(srv_com["gid"].text),
            base64.b64decode(srv_com["content"].text),
        )
        if success:
            ret_com.set_result("stored content")
        else:
            ret_com.set_result("cannot create file (please check logs on relayer)", server_command.SRV_REPLY_STATE_ERROR)
        return ret_com

    def _file_content_bulk(self, srv_com):
        new_vers = int(srv_com["version"].text)
        _file_list = srv_com["file_list"][0]
        _bulk = bz2.decompress(base64.b64decode(srv_com["bulk"].text))
        cur_offset = 0
        num_ok, num_failed = (0, 0)
        ok_list, failed_list = ([], [])
        self.log(
            "got {} (version {:d})".format(
                logging_tools.get_plural("bulk file", len(srv_com.xpath(".//ns:file_list/ns:file"))),
                new_vers,
            )
        )
        for _entry in srv_com.xpath(".//ns:file_list/ns:file"):
            _uid, _gid = (int(_entry.get("uid")), int(_entry.get("gid")))
            _size = int(_entry.get("size"))
            path = _entry.text
            content = _bulk[cur_offset:cur_offset + _size]
            _success = self._store_file(path, new_vers, _uid, _gid, content)
            if _success:
                num_ok += 1
                ok_list.append(path)
            else:
                num_failed += 1
                failed_list.append(path)
            cur_offset += _size
        # print etree.tostring(_file_list), len(_bulk)
        ret_com = server_command.srv_command(
            command="file_content_bulk_result",
            version="{:d}".format(new_vers),
            slave_name=srv_com["slave_name"].text,
            num_ok="{:d}".format(num_ok),
            num_failed="{:d}".format(num_failed),
            ok_list=base64.b64encode(bz2.compress(marshal.dumps(ok_list))),
            failed_list=base64.b64encode(bz2.compress(marshal.dumps(failed_list))),
        )
        if num_failed:
            log_str, log_state = ("cannot create all files ({:d}, please check logs on relayer)".format(num_failed), server_command.SRV_REPLY_STATE_ERROR)
        else:
            log_str, log_state = ("all {:d} files created".format(num_ok), server_command.SRV_REPLY_STATE_OK)
        ret_com.set_result(log_str, log_state)
        self.log(log_str, server_command.srv_reply_to_log_level(log_state))
        return ret_com

    def _store_file(self, t_file, new_vers, uid, gid, content):
        success = False
        if not t_file.startswith(ICINGA_TOP_DIR):
            self.log("refuse to operate outside '{}'".format(ICINGA_TOP_DIR), logging_tools.LOG_LEVEL_CRITICAL)
        else:
            renew, log_str = self._check_version(t_file, new_vers)
            if renew:
                t_dir = os.path.dirname(t_file)
                if not os.path.exists(t_dir):
                    try:
                        os.makedirs(t_dir)
                    except:
                        self.log("error creating directory {}: {}".format(t_dir, process_tools.get_except_info()),
                                 logging_tools.LOG_LEVEL_ERROR)
                    else:
                        self.log("created directory {}".format(t_dir))
                try:
                    file(t_file, "w").write(content)
                    os.chown(t_file, uid, gid)
                except:
                    self.log(
                        "error creating file {}: {}".format(
                            t_file,
                            process_tools.get_except_info()
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                else:
                    self.log(
                        "created {} [{}, {}]".format(
                            t_file,
                            logging_tools.get_size_str(len(content)).strip(),
                            log_str,
                        )
                    )
                    success = True
            else:
                success = True
                self.log("file {} not newer [{}]".format(t_file, log_str), server_command.SRV_REPLY_STATE_WARN)
        return success
