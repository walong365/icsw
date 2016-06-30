# Copyright (C) 2013-2016 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
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
""" server process for md-config-server """

import zmq

from initat.laser_server.config import global_config
from initat.tools import configfile, logging_tools, process_tools, threading_tools, server_mixins
from initat.tools.server_mixins import RemoteCall


@server_mixins.RemoteCallProcess
class server_process(
    server_mixins.ICSWBasePool,
    server_mixins.RemoteCallMixin,
    server_mixins.SendToRemoteServerMixin,
):
    def __init__(self):
        threading_tools.process_pool.__init__(self, "main", zmq=True)
        self.CC.init("laser-server", global_config)
        self.CC.check_config(client=True)
        self.__pid_name = global_config["PID_NAME"]
        self._init_msi_block()
        # re-insert config
        # log config
        self.CC.log_config()
        #self.CC.re_insert_config()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("hup_error", self._hup_error)
        # from mixins
        self._init_network_sockets()

    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True

    def _hup_error(self, err_cause):
        self.log("got sighup", logging_tools.LOG_LEVEL_WARN)
        self.send_to_process("build", "rebuild_config", cache_mode="DYNAMIC")

    def _init_msi_block(self):
        process_tools.save_pid(self.__pid_name, mult=3)
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=5)
        self.log("Initialising meta-server-info block")
        msi_block = process_tools.meta_server_info("laser-server")
        msi_block.add_actual_pid(mult=3, fuzzy_ceiling=4, process_name="main")
        msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=2, process_name="manager")
        msi_block.start_command = "/etc/init.d/laser-server start"
        msi_block.stop_command = "/etc/init.d/laser-server force-stop"
        msi_block.kill_pids = True
        msi_block.save_block()
        self.__msi_block = msi_block

    def _init_network_sockets(self):
        self.network_bind(
            need_all_binds=False,
            bind_port=global_config["COM_PORT"],
            bind_to_localhost=True,
            client_type="laser-server",
            simple_server_bind=True,
            pollin=self.remote_call,
        )

        self.__slaves = {}

        conn_str = process_tools.get_zmq_ipc_name("vector", s_name="collserver", connect_to_root_instance=True)
        vector_socket = self.zmq_context.socket(zmq.PUSH)
        vector_socket.setsockopt(zmq.LINGER, 0)
        vector_socket.connect(conn_str)
        self.vector_socket = vector_socket

    @RemoteCall()
    def status(self, srv_com, **kwargs):
        return self.server_status(srv_com, self.__msi_block, global_config)

    @RemoteCall()
    def rebuild_host_config(self, srv_com, **kwargs):
        print "pew pew"
        # pretend to be synchronous call such that reply is sent right away
        #self.send_to_process("build", "rebuild_config", cache_mode=srv_com.get("cache_mode", "DYNAMIC"))
        srv_com.set_result("pew pew")
        return srv_com

    def loop_end(self):
        process_tools.delete_pid(self.__pid_name)
        self.__msi_block.remove_meta_block()

    def loop_post(self):
        self.network_unbind()
        self.vector_socket.close()
        self.CC.close()