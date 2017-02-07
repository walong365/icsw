# Copyright (C) 2014-2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of discovery-server
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
""" discovery-server, server part """

import zmq
from django.db.models import Q

from initat.cluster.backbone import db_tools
from initat.cluster.backbone.models import device, DeviceScanLock
from initat.cluster.backbone.server_enums import icswServiceEnum
from initat.discovery_server.event_log.event_log_poller import \
    EventLogPollerProcess
from initat.snmp.process import SNMPProcessContainer
from initat.tools import configfile, logging_tools, process_tools, \
    server_command, server_mixins, threading_tools, net_tools
from initat.tools.server_mixins import RemoteCall
from .config import global_config, IPC_SOCK_SNMP
from .discovery import DiscoveryProcess


@server_mixins.RemoteCallProcess
class server_process(server_mixins.ICSWBasePool, server_mixins.RemoteCallMixin):
    def __init__(self):
        threading_tools.icswProcessPool.__init__(self, "main", zmq=True)
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.CC.init(icswServiceEnum.discovery_server, global_config)
        self.CC.check_config()
        # close connection (daemonize)
        db_tools.close_connection()
        self.CC.read_config_from_db(
            [
                ("SNMP_PROCESSES", configfile.int_c_var(4, help_string="number of SNMP processes [%(default)d]")),
                ("MAX_CALLS", configfile.int_c_var(100, help_string="number of calls per helper process [%(default)d]")),
            ]
        )
        self.CC.re_insert_config()
        self.CC.log_config()
        self.add_process(DiscoveryProcess("discovery"), start=True)
        self.add_process(EventLogPollerProcess(EventLogPollerProcess.PROCESS_NAME), start=True)
        self._init_network_sockets()
        self.register_func("snmp_run", self._snmp_run)
        self.register_func("send_host_monitor_command", self.send_host_monitor_command)
        self.register_func("host_monitoring_command_timeout_handler", self.host_monitoring_command_timeout_handler)
        db_tools.close_connection()
        self.__max_calls = global_config["MAX_CALLS"] if not global_config["DEBUG"] else 5
        self.__snmp_running = True
        self._init_processes()
        # not really necessary
        self.install_remote_call_handlers()
        # clear pending scans
        self.clear_pending_scans()
        self.__run_idx = 0
        self.__pending_commands = {}
        if process_tools.get_machine_name() == "eddiex" and global_config["DEBUG"]:
            self._test()

        self.__pending_host_monitoring_commands = {}

    def clear_pending_scans(self):
        pending_locks = DeviceScanLock.objects.filter(Q(server=global_config["SERVER_IDX"]) & Q(active=True))
        if pending_locks.count():
            self.log("clearing {}".format(logging_tools.get_plural("active scan", pending_locks.count())))
            for _lock in pending_locks:
                [self.log(_what, _level) for _what, _level in _lock.close()]

    def _int_error(self, err_cause):
        if not self.__snmp_running:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self.spc.stop()
            self.__snmp_running = False
            self["exit_requested"] = True

    def _all_snmps_stopped(self):
        self["exit_requested"] = True

    def _snmp_process_start(self, **kwargs):
        self.CC.process_added(kwargs["process_name"], kwargs["pid"])

    def _snmp_process_exit(self, **kwargs):
        self.CC.process_removed(kwargs["pid"])

    def _init_processes(self):
        self.spc = SNMPProcessContainer(
            IPC_SOCK_SNMP,
            self.log,
            global_config["SNMP_PROCESSES"],
            self.__max_calls,
            {
                "VERBOSE": global_config["VERBOSE"],
                "LOG_NAME": global_config["LOG_NAME"],
                "LOG_DESTINATION": global_config["LOG_DESTINATION"],
            },
            {
                "process_start": self._snmp_process_start,
                "process_exit": self._snmp_process_exit,
                "all_stopped": self._all_snmps_stopped,
                "finished": self._snmp_finished,
            }
        )

        _snmp_sock = self.spc.create_ipc_socket(self.zmq_context, IPC_SOCK_SNMP)
        self.register_poller(_snmp_sock, zmq.POLLIN, self.spc.handle_with_socket)
        self.spc.check()

    def process_start(self, src_process, src_pid):
        self.CC.process_added(src_process, src_pid)

    def loop_end(self):
        self.spc.close()

    def loop_post(self):
        self.network_unbind()
        self.CC.close()

    def _init_network_sockets(self):
        self.network_bind(
            need_all_binds=False,
            bind_to_localhost=True,
            service_type_enum=icswServiceEnum.discovery_server,
            simple_server_bind=True,
            pollin=self.remote_call,
        )
        # dict for external connections

    def host_monitoring_command_timeout_handler(self, *args, **kwargs):
        _from_name, _from_pid, run_index = args

        if run_index in self.__pending_host_monitoring_commands:
            self.__pending_host_monitoring_commands[run_index].close()
            del self.__pending_host_monitoring_commands[run_index]

    def send_host_monitor_command(self, *args, **kwargs):
        _from_name, _from_pid, run_index, conn_str, srv_com = args
        srv_com = server_command.srv_command(source=srv_com)
        srv_com["run_index"] = "{:d}".format(run_index)
        _new_con = net_tools.ZMQConnection(
            "host_monitor_command_{:d}".format(run_index),
            context=self.zmq_context,
            poller_base=self,
            callback=self.__send_host_monitor_command_callback,
        )

        self.__pending_host_monitoring_commands[run_index] = _new_con

        _new_con.add_connection(conn_str, srv_com)

    def __send_host_monitor_command_callback(self, *args):
        srv_reply = args[0]
        run_index = None
        if srv_reply:
            run_index = int(srv_reply["*run_index"])

        if run_index:
            self.send_to_process("discovery", "host_monitor_result", run_index, str(srv_reply))
            self.__pending_host_monitoring_commands[run_index].close()
            del self.__pending_host_monitoring_commands[run_index]

    @RemoteCall()
    def status(self, srv_com, **kwargs):
        return self.server_status(srv_com, self.CC.msi_block, global_config, spc=self.spc)

    @RemoteCall(target_process="discovery")
    def scan_system_info(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall(target_process="discovery")
    def scan_network_info(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall(target_process="discovery")
    def snmp_basic_scan(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall(target_process="discovery")
    def base_scan(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall(target_process="discovery")
    def wmi_scan(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall(target_process="discovery")
    def nrpe_scan(self, srv_com, **kwargs):
        return srv_com

    def _snmp_finished(self, args):
        self.send_to_process("discovery", "snmp_result", *args["args"])

    def _test(self):
        _srv_com = server_command.srv_command(command="snmp_basic_scan")
        _srv_com["devices"] = _srv_com.builder(
            "device",
            snmp_version="1",
            pk="{:d}".format(device.objects.get(Q(name='eddie')).pk),
            snmp_community="public",
            snmp_address="127.0.0.1",
            # snmp_address="192.168.1.50",
            # snmp_address="192.168.2.12",
        )
        self.send_to_process("discovery", _srv_com["*command"], str(_srv_com))

    def _snmp_run(self, *args, **kwargs):
        # ignore src specs
        _src_proc, _src_pid = args[0:2]
        self.spc.start_batch(*args[2:], **kwargs)

