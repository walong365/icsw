# Copyright (C) 2007-2009,2013-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file belongs to the rrd-server package
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
""" server-part of rrd-grapher """

import json

from django.db import connection
from initat.rrd_grapher.config import global_config
from initat.rrd_grapher.rrd_grapher_struct import DataStore
from initat.rrd_grapher.graph import GraphProcess
from initat.rrd_grapher.stale import GraphStaleProcess
from initat.tools import cluster_location, configfile, logging_tools, \
    process_tools, server_mixins, threading_tools


@server_mixins.RemoteCallProcess
class server_process(
    server_mixins.ICSWBasePool,
    server_mixins.RemoteCallMixin,
):
    def __init__(self):
        threading_tools.process_pool.__init__(self, "main", zmq=True)
        self.CC.init("rrd-grapher", global_config)
        self.CC.check_config()
        self.__pid_name = global_config["PID_NAME"]
        self.__verbose = global_config["VERBOSE"]
        # close connection (daemonizing)
        connection.close()
        self.__msi_block = self._init_msi_block()
        # re-insert config
        self._re_insert_config()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("hup_error", self._hup_error)
        self._log_config()
        self.add_process(GraphProcess("graph"), start=True)
        self.add_process(GraphStaleProcess("stale"), start=True)
        connection.close()
        self._init_network_sockets()
        DataStore.setup(self)
        # self.test("x")

    def _log_config(self):
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [{:d}] {}".format(log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found {:d} valid global config-lines:".format(len(conf_info)))
        for conf in conf_info:
            self.log("Config : {}".format(conf))

    def _re_insert_config(self):
        cluster_location.write_config("rrd_server", global_config)

    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True

    def _hup_error(self, err_cause):
        self.log("got sighup", logging_tools.LOG_LEVEL_WARN)

    def process_start(self, src_process, src_pid):
        mult = 3
        process_tools.append_pids(self.__pid_name, src_pid, mult=mult)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(src_pid, mult=mult, process_name=src_process)
            self.__msi_block.save_block()

    def _init_msi_block(self):
        process_tools.save_pid(self.__pid_name, mult=3)
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=4)
        self.log("Initialising meta-server-info block")
        msi_block = process_tools.meta_server_info("rrd-grapher")
        msi_block.add_actual_pid(mult=3, fuzzy_ceiling=4, process_name="main")
        msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=4, process_name="manager")
        msi_block.kill_pids = True
        msi_block.save_block()
        return msi_block

    def _init_network_sockets(self):
        self.network_bind(
            need_all_binds=False,
            bind_port=global_config["COMMAND_PORT"],
            bind_to_localhost=True,
            server_type="grapher",
            simple_server_bind=True,
            pollin=self.remote_call,
        )

    @server_mixins.RemoteCall()
    def get_node_rrd(self, srv_com, **kwargs):
        node_results = []
        dev_list = srv_com.xpath(".//device_list", smart_strings=False)[0]
        pk_list = [int(cur_pk) for cur_pk in dev_list.xpath(".//device/@pk", smart_strings=False)]
        for dev_pk in pk_list:
            cur_res = {"pk": dev_pk}
            if DataStore.has_machine_vector(dev_pk):
                # web mode (sorts entries)
                _struct = DataStore.get_instance(dev_pk).vector_struct()
                _struct.extend(DataStore.compound_struct(_struct))
                cur_res["struct"] = _struct
            else:
                self.log("no machine_vector found for device {:d}".format(dev_pk), logging_tools.LOG_LEVEL_WARN)
            node_results.append(cur_res)
        # _json = self._to_json(node_results, set(["info", "active", "key", "name", "part", "pk"]))
        # pprint.pprint(node_results, depth=5)
        srv_com["result"] = json.dumps(node_results)
        srv_com.set_result("set results for {}".format(logging_tools.get_plural("node", len(node_results))))
        return srv_com

    @server_mixins.RemoteCall()
    def get_0mq_id(self, srv_com, **kwargs):
        srv_com["zmq_id"] = self.bind_id
        srv_com.set_result("0MQ_ID is {}".format(self.bind_id))
        return srv_com

    @server_mixins.RemoteCall()
    def status(self, srv_com, **kwargs):
        srv_com.set_result("status is up and running")
        return srv_com

    @server_mixins.RemoteCall(sync=False, target_process="graph")
    def graph_rrd(self, srv_com, **kwargs):
        # here we have to possibility to modify srv_com before we send it to the remote process
        return srv_com

    def loop_end(self):
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()

    def loop_post(self):
        self.network_unbind()
        self.CC.close()
