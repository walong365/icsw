# Copyright (C) 2016 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-server
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
""" server process for md-sync-server """

import codecs
import os
import time

import zmq

from initat.host_monitoring.hm_classes import mvect_entry
from initat.md_sync_server.mixins import VersionCheckMixin
from initat.host_monitoring.client_enums import icswServiceEnum
from initat.md_sync_server.config import global_config, CS_NAME
from initat.md_sync_server.process import ProcessControl
from initat.tools import configfile, logging_tools, process_tools, server_command, \
    threading_tools, server_mixins, config_store
from initat.tools.server_mixins import RemoteCall
from .syncer import SyncerProcess
from .sync_config import RemoteServer


@server_mixins.RemoteCallProcess
class server_process(
    server_mixins.ICSWBasePoolClient,
    server_mixins.RemoteCallMixin,
    # server_mixins.SendToRemoteServerMixin,
    VersionCheckMixin,
):
    def __init__(self):
        threading_tools.process_pool.__init__(self, "main", zmq=True)
        self.CC.init(icswServiceEnum.monitor_slave, global_config)
        self.CC.check_config()
        self.__enable_livestatus = True  # global_config["ENABLE_LIVESTATUS"]
        self.__verbose = global_config["VERBOSE"]
        self.read_config_store()
        # log config
        self.CC.log_config()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("hup_error", self._hup_error)
        # from mixins
        self._icinga_pc = None
        self.register_timer(self._check_for_pc_control, 10, instant=True)
        self.VCM_check_md_version()
        self.VCM_check_relay_version()
        self._init_network_sockets()
        self.add_process(SyncerProcess("syncer"), start=True)
        self.register_func("send_command", self._send_command)
        self.register_func("register_remote", self._register_remote)
        _srv_com = server_command.srv_command(command="status")
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
                    target_state=self.config_store["mon_is_running"],
                )
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

    def _check_for_redistribute(self):
        self.send_to_process("syncer", "check_for_redistribute")

    def read_config_store(self):
        self.config_store = config_store.ConfigStore(CS_NAME, log_com=self.log, access_mode=config_store.AccessModeEnum.LOCAL)
        self.config_store["mon_is_running"] = self.config_store.get("mon_is_running", True)
        global_config.add_config_entries(
            [
                ("MON_TARGET_STATE", configfile.bool_c_var(self.config_store["mon_is_running"])),
                # just a guess
                ("MON_CURRENT_STATE", configfile.bool_c_var(False)),
            ]
        )
        self.config_store.write()
        # self.config_store

    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True

    def _hup_error(self, err_cause):
        self.log("got sighup", logging_tools.LOG_LEVEL_WARN)
        self.send_to_process("build", "rebuild_config", cache_mode="DYNAMIC")

    def process_start(self, src_process, src_pid):
        if src_process == "syncer" and "distribute_info" in self.config_store:
            self.send_to_process("syncer", "distribute_info", server_command.decompress(self.config_store["distribute_info"], json=True))
        self.CC.process_added(src_process, src_pid)

    def _register_remote(self, *args, **kwargs):
        _src_proc, _src_id, remote_ip, remote_uuid, remote_port = args
        if remote_uuid not in self.__slaves:
            rs = RemoteServer(remote_uuid, remote_ip, remote_port)
            self.log("connecting to {}".format(unicode(rs)))
            self.main_socket.connect(rs.conn_str)
            self.__slaves[remote_uuid] = rs

    def _send_command(self, *args, **kwargs):
        _src_proc, _src_id, full_uuid, srv_com = args
        try:
            self.main_socket.send_unicode(full_uuid, zmq.SNDMORE)  # @UndefinedVariable
            self.main_socket.send_unicode(srv_com)
        except:
            self.log(
                "cannot send {:d} bytes to {}: {}".format(
                    len(srv_com),
                    full_uuid,
                    process_tools.get_except_info(),
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            if full_uuid in self.__slaves:
                self.log("target is {}".format(unicode(self.__slaves[full_uuid])))
        else:
            self.log("sent {:d} bytes to {}".format(len(srv_com), full_uuid))

    def _ocsp_results(self, *args, **kwargs):
        _src_proc, _src_pid, lines = args
        self._write_external_cmd_file(lines)

    def _handle_ocp_event(self, in_com):
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
        self._write_external_cmd_file(out_line)

    def _write_external_cmd_file(self, lines):
        if type(lines) != list:
            lines = [lines]
        if self.__external_cmd_file:
            try:
                codecs.open(self.__external_cmd_file, "w", "utf-8").write("\n".join(lines + [""]))
            except:
                self.log(
                    "error writing to {}: {}".format(
                        self.__external_cmd_file,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
                raise
        else:
            self.log("no external cmd_file defined", logging_tools.LOG_LEVEL_ERROR)

    def _set_external_cmd_file(self, *args, **kwargs):
        _src_proc, _src_id, ext_name = args
        self.log("setting external cmd_file to '{}'".format(ext_name))
        self.__external_cmd_file = ext_name

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

    @RemoteCall()
    def stop_mon_process(self, srv_com, **kwargs):
        self.config_store["mon_is_running"] = False
        return self._start_stop_mon_process(srv_com)

    @RemoteCall()
    def start_mon_process(self, srv_com, **kwargs):
        self.config_store["mon_is_running"] = True
        return self._start_stop_mon_process(srv_com)

    @RemoteCall()
    def distribute_info(self, srv_com, **kwargs):
        di_info = server_command.decompress(srv_com["*info"], marshal=True)
        self.config_store["distribute_info"] = server_command.compress(di_info, json=True)
        self.config_store.write()
        self.send_to_process("syncer", "distribute_info", di_info)
        return None

    def _start_stop_mon_process(self, srv_com):
        global_config["MON_TARGET_STATE"] = self.config_store["mon_is_running"]
        self.config_store.write()
        if self._icinga_pc:
            self._icinga_pc._target_state = self.config_store["mon_is_running"]
            self._check_mon_state()
        srv_com.set_result("set mon_is_running to {}".format(self.config_store["mon_is_running"]))
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

    @RemoteCall(target_process="build", target_process_func="build_host_config")
    def get_host_config(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall()
    def rebuild_host_config(self, srv_com, **kwargs):
        # pretend to be synchronous call such that reply is sent right away
        self.send_to_process("build", "rebuild_config", cache_mode=srv_com.get("cache_mode", "DYNAMIC"))
        srv_com.set_result("ok processed command rebuild_host_config")
        return srv_com

    @RemoteCall()
    def sync_http_users(self, srv_com, **kwargs):
        self.send_to_process("build", "sync_http_users")
        srv_com.set_result("ok processed command sync_http_users")
        return srv_com

    @RemoteCall()
    def ocsp_event(self, srv_com, **kwargs):
        self._handle_ocp_event(srv_com)

    @RemoteCall()
    def ochp_event(self, srv_com, **kwargs):
        self._handle_ocp_event(srv_com)

    @RemoteCall(target_process="dynconfig")
    def monitoring_info(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall(target_process="syncer")
    def register_master(self, srv_com, **kwargs):
        # call from satellite master to register itself at this satellite
        return srv_com

    @RemoteCall(target_process="syncer")
    def satellite_info(self, srv_com, **kwargs):
        # call from pure slave (==satellite) to this satellite master
        return srv_com

    @RemoteCall(target_process="syncer")
    def file_content_result(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall(target_process="syncer")
    def file_content_bulk_result(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall()
    def relayer_info(self, srv_com, **kwargs):
        # pretend to be synchronous call such that reply is sent right away
        self.send_to_process("syncer", "relayer_info", unicode(srv_com))
        srv_com.set_result("ok processed command sync_http_users")
        return srv_com

    @RemoteCall()
    def passive_check_result(self, srv_com, **kwargs):
        # pretend to be synchronous call such that reply is sent right away
        self.send_to_process("dynconfig", "passive_check_result", unicode(srv_com))
        srv_com.set_result("ok processed command passive_check_result")
        return srv_com

    @RemoteCall(target_process="dynconfig")
    def passive_check_results(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall(target_process="dynconfig")
    def passive_check_results_as_chunk(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall()
    def status(self, srv_com, **kwargs):
        return self.server_status(srv_com, self.CC.msi_block, global_config)

    def loop_end(self):
        if self._icinga_pc:
            self._icinga_pc.stop()

    def loop_post(self):
        self.network_unbind()
        self.CC.close()
