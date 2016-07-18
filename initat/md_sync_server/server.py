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
from initat.md_sync_server.mixins import version_check_mixin
from initat.md_sync_server.config import global_config
from initat.md_sync_server.process import ProcessControl
from initat.tools import configfile, logging_tools, process_tools, server_command, \
    threading_tools, server_mixins
from initat.tools.server_mixins import RemoteCall


@server_mixins.RemoteCallProcess
class server_process(
    server_mixins.ICSWBasePool,
    server_mixins.RemoteCallMixin,
    server_mixins.SendToRemoteServerMixin,
    version_check_mixin,
):
    def __init__(self):
        threading_tools.process_pool.__init__(self, "main", zmq=True)
        self.CC.init("md-sync-server", global_config)
        self.CC.check_config(client=True)
        self.__enable_livestatus = True  # global_config["ENABLE_LIVESTATUS"]
        self.__pid_name = global_config["PID_NAME"]
        self.__verbose = global_config["VERBOSE"]
        self._init_msi_block()
        # log config
        self.CC.log_config()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("hup_error", self._hup_error)
        # from mixins
        self._icinga_pc = None
        self.register_timer(self._check_for_pc_control, 10, instant=True)
        self._check_md_version()
        self._check_relay_version()
        self._init_network_sockets()
        _srv_com = server_command.srv_command(command="status")
        self.send_to_remote_server_ip("127.0.0.1", "cluster-server", unicode(_srv_com))

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
            else:
                self.log(
                    "MD_TYPE not found in global_config, packages missing",
                    logging_tools.LOG_LEVEL_WARN
                )
        else:
            self._icinga_pc.check_state()

    def _check_for_redistribute(self):
        self.send_to_process("syncer", "check_for_redistribute")

    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True

    def _hup_error(self, err_cause):
        self.log("got sighup", logging_tools.LOG_LEVEL_WARN)
        self.send_to_process("build", "rebuild_config", cache_mode="DYNAMIC")

    def process_start(self, src_process, src_pid):
        # if src_process == "syncer":
        #    self.send_to_process("syncer", "check_for_slaves")
        #    self.add_process(build_process("build"), start=True)
        # elif src_process == "build":
        #    self.send_to_process("build", "check_for_slaves")
        #    if global_config["RELOAD_ON_STARTUP"]:
        #        self.send_to_process("build", "reload_md_daemon")
        #    if global_config["BUILD_CONFIG_ON_STARTUP"] or global_config["INITIAL_CONFIG_RUN"]:
        #        self.send_to_process("build", "rebuild_config", cache_mode=global_config["INITIAL_CONFIG_CACHE_MODE"])
        mult = 3
        process_tools.append_pids(self.__pid_name, src_pid, mult=mult)
        self.__msi_block.add_actual_pid(src_pid, mult=mult, fuzzy_ceiling=3, process_name=src_process)
        self.__msi_block.save_block()

    def _init_msi_block(self):
        process_tools.save_pid(self.__pid_name, mult=3)
        self.log("Initialising meta-server-info block")
        msi_block = process_tools.meta_server_info("md-sync-server")
        msi_block.add_actual_pid(mult=3, fuzzy_ceiling=4, process_name="main")
        msi_block.kill_pids = True
        msi_block.save_block()
        self.__msi_block = msi_block

    def _register_slave(self, *args, **kwargs):
        _src_proc, _src_id, slave_ip, slave_uuid = args
        if slave_uuid not in self.__slaves:
            rs = RemoteSlave(slave_uuid, slave_ip, 2004)
            self.log("connecting to {}".format(unicode(rs)))
            self.main_socket.connect(rs.conn_str)
            self.__slaves[slave_uuid] = rs

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

    def _set_external_cmd_file(self, *args, **kwargs):
        _src_proc, _src_id, ext_name = args
        self.log("setting external cmd_file to '{}'".format(ext_name))
        self.__external_cmd_file = ext_name

    def _init_network_sockets(self):
        self.network_bind(
            need_all_binds=False,
            bind_port=global_config["COMMAND_PORT"],
            bind_to_localhost=True,
            client_type="md-sync-server",
            simple_server_bind=True,
            pollin=self.remote_call,
        )

        self.__slaves = {}

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
        return self.server_status(srv_com, self.__msi_block, global_config)

    def loop_end(self):
        if self._icinga_pc:
            self._icinga_pc.stop()
        process_tools.delete_pid(self.__pid_name)
        self.__msi_block.remove_meta_block()

    def loop_post(self):
        self.network_unbind()
        self.CC.close()