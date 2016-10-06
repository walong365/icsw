# Copyright (C) 2016 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-server
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" server process for md-sync-server """

import os
import time

import zmq

from initat.host_monitoring.client_enums import icswServiceEnum
from initat.host_monitoring.hm_classes import mvect_entry
from initat.host_monitoring.ipc_comtools import IPCCommandHandler
from initat.md_config_server import constants
from initat.md_sync_server.config import global_config, CS_NAME
from initat.md_sync_server.mixins import VersionCheckMixin
from initat.md_sync_server.process import ProcessControl
from initat.tools import configfile, logging_tools, process_tools, server_command, \
    threading_tools, server_mixins, config_store
from initat.tools.server_mixins import RemoteCall
from .status import StatusProcess, LiveSocket
from .sync_config import RemoteServer
from .syncer import SyncerHandler

DEFAULT_PROC_DICT = {
    "ignore_process": False,
    "start_process": True,
}


@server_mixins.RemoteCallProcess
class server_process(
    server_mixins.ICSWBasePoolClient,
    server_mixins.RemoteCallMixin,
    VersionCheckMixin,
):
    def __init__(self):
        process_tools.ALLOW_MULTIPLE_INSTANCES = False
        threading_tools.process_pool.__init__(self, "main", zmq=True)
        self.CC.init(icswServiceEnum.monitor_slave, global_config)
        self.CC.check_config()
        self.__verbose = global_config["VERBOSE"]
        self.read_config_store()
        # log config
        self.CC.log_config()
        self.ICH = IPCCommandHandler(self)
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("hup_error", self._hup_error)
        # from mixins
        self._icinga_pc = None
        self.register_timer(self._check_for_pc_control, 10, instant=True)
        self.VCM_check_md_version()
        self._init_network_sockets()
        self.add_process(StatusProcess("status"), start=True)
        self.register_func("send_command", self._send_command)
        self.__latest_status_query = None
        self.SH = SyncerHandler(self)
        if "distribute_info" in self.config_store:
            self.SH.distribute_info(server_command.decompress(self.config_store["distribute_info"], json=True))
        self.register_timer(self._update, 30, instant=True)
        # _srv_com = server_command.srv_command(command="status")
        # self.send_to_remote_server_ip("127.0.0.1", icswServiceEnum.cluster_server, unicode(_srv_com))

    def _check_for_pc_control(self):
        if self._icinga_pc is None:
            # check
            if "MD_TYPE" in global_config:
                _lock_file_name = os.path.join(
                    global_config["MD_BASEDIR"],
                    "var",
                    global_config["MD_LOCK_FILE"]
                )
                self._icinga_pc = ProcessControl(
                    self,
                    global_config["MD_TYPE"],
                    _lock_file_name,
                )
                if not self.config_store["ignore_process"]:
                    # go for a well-defined state
                    self._icinga_pc._kill_old_instances()
            else:
                self.log(
                    "MD_TYPE not found in global_config, packages missing",
                    logging_tools.LOG_LEVEL_WARN
                )
        self._check_mon_state()

    def _check_mon_state(self):
        if self._icinga_pc is not None:
            _is_running = self._icinga_pc.check_state()
            global_config["MON_CURRENT_STATE"] = _is_running
            if not self.config_store["ignore_process"]:
                if global_config["MON_TARGET_STATE"] != global_config["MON_CURRENT_STATE"]:
                    self.log(
                        "current state differs: {} (target) != {} (current)".format(
                            global_config["MON_TARGET_STATE"],
                            global_config["MON_CURRENT_STATE"],
                        )
                    )
                    if global_config["MON_TARGET_STATE"]:
                        self._icinga_pc.start()
                    else:
                        self._icinga_pc.stop()

    def _update(self):
        res_dict = {}
        if "MD_TYPE" in global_config and global_config["MON_CURRENT_STATE"]:
            _cur_time = time.time()
            cur_s = LiveSocket.get_mon_live_socket()
            if not self.__latest_status_query or abs(self.__latest_status_query - _cur_time) > 10 * 60:
                self.__latest_status_query = _cur_time
                try:
                    _stat_dict = cur_s.status.call()[0]
                except:
                    self.log("error getting status via livestatus: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                else:
                    self.SH.livestatus_info(_stat_dict)
            try:
                result = cur_s.hosts.columns("name", "state").call()
            except:
                self.log(
                    "cannot query socket {}: {}".format(cur_s.peer, process_tools.get_except_info()),
                    logging_tools.LOG_LEVEL_CRITICAL
                )
            else:
                q_list = [int(value["state"]) for value in result]
                res_dict = {
                    s_name: q_list.count(value) for s_name, value in [
                        ("unknown", constants.MON_HOST_UNKNOWN),
                        ("up", constants.MON_HOST_UP),
                        ("down", constants.MON_HOST_DOWN),
                    ]
                }
                res_dict["tot"] = sum(res_dict.values())
            # cur_s.peer.close()
            del cur_s
        else:
            self.log(
                "no MD_TYPE set or MON_CURRENT_STATE is False, skipping livecheck",
                logging_tools.LOG_LEVEL_WARN
            )
        if res_dict:
            self.log(
                "{} status is: {:d} up, {:d} down, {:d} unknown ({:d} total)".format(
                    global_config["MD_TYPE"],
                    res_dict["up"],
                    res_dict["down"],
                    res_dict["unknown"],
                    res_dict["tot"]
                )
            )
            drop_com = server_command.srv_command(command="set_vector")
            add_obj = drop_com.builder("values")
            mv_list = [
                mvect_entry("mon.devices.up", info="Devices up", default=0),
                mvect_entry("mon.devices.down", info="Devices down", default=0),
                mvect_entry("mon.devices.total", info="Devices total", default=0),
                mvect_entry("mon.devices.unknown", info="Devices unknown", default=0),
            ]
            cur_time = time.time()
            for mv_entry, key in zip(mv_list, ["up", "down", "tot", "unknown"]):
                mv_entry.update(res_dict[key])
                mv_entry.valid_until = cur_time + 120
                add_obj.append(mv_entry.build_xml(drop_com.builder))
            drop_com["vector_loadsensor"] = add_obj
            drop_com["vector_loadsensor"].attrib["type"] = "vector"
            send_str = unicode(drop_com)
            self.log("sending {:d} bytes to vector_socket".format(len(send_str)))
            self.vector_socket.send_unicode(send_str)
        else:
            self.log("empty result dict for _update()", logging_tools.LOG_LEVEL_WARN)

    def _check_for_redistribute(self):
        self.SH._check_for_redistribute()

    def read_config_store(self):
        self.config_store = config_store.ConfigStore(CS_NAME, log_com=self.log, access_mode=config_store.AccessModeEnum.LOCAL)
        for _key, _default in DEFAULT_PROC_DICT.iteritems():
            self.config_store[_key] = self.config_store.get(_key, _default)
        global_config.add_config_entries(
            [
                ("MON_TARGET_STATE", configfile.bool_c_var(self.config_store["start_process"])),
                # just a guess
                ("MON_CURRENT_STATE", configfile.bool_c_var(False)),
            ]
        )
        self.config_store.write()

    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True

    def _hup_error(self, err_cause):
        self.log("got sighup", logging_tools.LOG_LEVEL_WARN)
        self.send_to_process("build", "rebuild_config", cache_mode="DYNAMIC")

    def process_start(self, src_process, src_pid):
        self.CC.process_added(src_process, src_pid)

    def register_remote(self, remote_ip, remote_uuid, remote_port):
        if remote_uuid not in self.__slaves:
            rs = RemoteServer(remote_uuid, remote_ip, remote_port)
            self.log("connecting to {}".format(unicode(rs)))
            self.main_socket.connect(rs.conn_str)
            self.__slaves[remote_uuid] = rs

    def send_signal(self, sign):
        if self._icinga_pc is not None:
            self._icinga_pc.send_signal(sign)
        else:
            self.log("Processcontrol not defined", logging_tools.LOG_LEVEL_ERROR)

    def _send_command(self, *args, **kwargs):
        _src_proc, _src_id, full_uuid, srv_com = args
        self.send_command(full_uuid, srv_com)

    def send_command(self, full_uuid, srv_com):
        try:
            self.main_socket.send_unicode(full_uuid, zmq.SNDMORE)  # @UndefinedVariable
            self.main_socket.send_unicode(unicode(srv_com))
        except:
            self.log(
                "cannot send {:d} bytes to '{}': {}".format(
                    len(unicode(srv_com)),
                    full_uuid,
                    process_tools.get_except_info(),
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            if full_uuid in self.__slaves:
                self.log("target is {}".format(unicode(self.__slaves[full_uuid])))
        else:
            self.log("sent {:d} bytes to {}".format(len(srv_com), full_uuid))

    def handle_ocp_event(self, in_com):
        com_type = in_com["command"].text
        targ_list = [cur_arg.text for cur_arg in in_com.xpath(".//ns:arguments", smart_strings=False)[0]]
        target_com = {
            "ocsp-event": "PROCESS_SERVICE_CHECK_RESULT",
            "ochp-event": "PROCESS_HOST_CHECK_RESULT",
        }[com_type]
        # rewrite state information
        state_idx, error_state = (1, 1) if com_type == "ochp-event" else (2, 2)
        targ_list[state_idx] = "{:d}".format({
            "ok": 0,
            "up": 0,
            "warning": 1,
            "down": 1,
            "unreachable": 2,
            "critical": 2,
            "unknown": 3,
        }.get(targ_list[state_idx].lower(), error_state))
        if com_type == "ocsp-event":
            pass
        else:
            pass
        out_line = "[{:d}] {};{}".format(
            int(time.time()),
            target_com,
            ";".join(targ_list)
        )
        if self._icinga_pc:
            self._icinga_pc.write_external_cmd_file(out_line)

    def _init_network_sockets(self):
        self.network_bind(
            need_all_binds=False,
            bind_port=global_config["COMMAND_PORT"],
            bind_to_localhost=True,
            client_type=icswServiceEnum.monitor_slave,
            simple_server_bind=True,
            pollin=self.remote_call,
        )

        self.__slaves = {}

        conn_str = process_tools.get_zmq_ipc_name("vector", s_name="collserver", connect_to_root_instance=True)
        vector_socket = self.zmq_context.socket(zmq.PUSH)
        vector_socket.setsockopt(zmq.LINGER, 0)
        vector_socket.connect(conn_str)
        self.vector_socket = vector_socket

        # copy from relay, Refactor
        self.__nhm_connections = set()
        sock_list = [
            ("ipc", "receiver", zmq.PULL, 2),
        ]
        [setattr(self, "{}_socket".format(short_sock_name), None) for _sock_proto, short_sock_name, _a0, _b0 in sock_list]
        for _sock_proto, short_sock_name, sock_type, hwm_size in sock_list:
            sock_name = process_tools.get_zmq_ipc_name(short_sock_name, s_name="md-sync-server", connect_to_root_instance=True)
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
                    "error binding {}: {}".format(
                        short_sock_name,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_CRITICAL
                )
                raise
            else:
                setattr(self, "{}_socket".format(short_sock_name), cur_socket)
                os.chmod(file_name, 0777)
                cur_socket.setsockopt(zmq.LINGER, 0)
                cur_socket.setsockopt(zmq.SNDHWM, hwm_size)
                cur_socket.setsockopt(zmq.RCVHWM, hwm_size)
                if sock_type == zmq.PULL:
                    self.register_poller(cur_socket, zmq.POLLIN, self._recv_command_ipc)

    def _recv_command_ipc(self, *args, **kwargs):
        _data = self.receiver_socket.recv()
        src_id, srv_com = self.ICH.handle(_data)
        if srv_com is not None:
            self.SH.check_result(srv_com)
        else:
            self.log("cannot interpret {}".format(_data), logging_tools.LOG_LEVEL_ERROR)

    def _get_flag_info(self):
        return "process flags: {}".format(
            ", ".join(
                [
                    "{}={}".format(_key, self.config_store[_key]) for _key in DEFAULT_PROC_DICT.iterkeys()
                ]
            )
        )

    @RemoteCall()
    def mon_process_handling(self, srv_com, **kwargs):
        _dict = {}
        for _key, _default in DEFAULT_PROC_DICT.iteritems():
            if _key in srv_com:
                _dict[_key] = True if int(srv_com["*{}".format(_key)]) else False
            else:
                _dict[_key] = _default
            self.config_store[_key] = _dict[_key]
        self.log(self._get_flag_info())
        return self._start_stop_mon_process(srv_com)

    @RemoteCall()
    def distribute_info(self, srv_com, **kwargs):
        di_info = server_command.decompress(srv_com["*info"], marshal=True)
        self.config_store["distribute_info"] = server_command.compress(di_info, json=True)
        self.config_store.write()
        self.SH.distribute_info(di_info)
        return None

    def _start_stop_mon_process(self, srv_com):
        global_config["MON_TARGET_STATE"] = self.config_store["start_process"]
        self.config_store.write()
        if self._icinga_pc:
            self._icinga_pc._start_process = self.config_store["start_process"]
            self._icinga_pc._ignore_process = self.config_store["ignore_process"]
            self._check_mon_state()
        srv_com.set_result(self._get_flag_info())
        return srv_com

    @RemoteCall(target_process="KpiProcess")
    def calculate_kpi_preview(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall(target_process="KpiProcess")
    def calculate_kpi_db(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall(target_process="KpiProcess")
    def get_kpi_source_data(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall(target_process="status")
    def get_node_status(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall()
    def sync_http_users(self, srv_com, **kwargs):
        self.send_to_process("build", "sync_http_users")
        srv_com.set_result("ok processed command sync_http_users")
        return srv_com

    @RemoteCall()
    def ocsp_event(self, srv_com, **kwargs):
        self.handle_ocp_event(srv_com)
        return None

    @RemoteCall()
    def ochp_event(self, srv_com, **kwargs):
        self.handle_ocp_event(srv_com)
        return None

    @RemoteCall()
    def ocsp_lines(self, srv_com, **kwargs):
        # OCSP lines from md-config-server
        _ocsp_lines = server_command.decompress(srv_com["*ocsp_lines"], json=True)
        if self._icinga_pc:
            self._icinga_pc.write_external_cmd_file(_ocsp_lines)
        return None

    @RemoteCall()
    def slave_command(self, srv_com, **kwargs):
        # slave distribution commands, either
        # - from distribution slave to master or
        # - from master to distribution slave
        self.SH.slave_command(srv_com)
        return None

    @RemoteCall()
    def passive_check_result(self, srv_com, **kwargs):
        # from commandline
        # pretend to be synchronous call such that reply is sent right away
        self.SH.passive_check_handler(srv_com, "command")
        srv_com.set_result("ok processed command passive_check_result")
        return srv_com

    @RemoteCall()
    def passive_check_results(self, srv_com, **kwargs):
        self.SH.passive_check_handler(srv_com, "mult")
        return None

    @RemoteCall()
    def passive_check_results_as_chunk(self, srv_com, **kwargs):
        self.SH.passive_check_handler(srv_com, "chunk")
        return None

    @RemoteCall()
    def status(self, srv_com, **kwargs):
        return self.server_status(srv_com, self.CC.msi_block, global_config)

    def loop_end(self):
        if self._icinga_pc and not self.config_store["ignore_process"]:
            self._icinga_pc.stop()

    def loop_post(self):
        self.network_unbind()
        self.vector_socket.close()
        self.receiver_socket.close()
        self.CC.close()
