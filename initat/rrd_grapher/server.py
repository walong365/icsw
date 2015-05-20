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
from initat.cluster.backbone.routing import get_server_uuid
from initat.rrd_grapher.config import global_config
from initat.rrd_grapher.struct import DataStore
from initat.rrd_grapher.graph import graph_process
from initat.rrd_grapher.stale import stale_process
from initat.tools import cluster_location
from initat.tools import configfile
from initat.tools import logging_tools
from initat.tools import process_tools
from initat.tools import server_command
from initat.tools import server_mixins
from initat.tools import threading_tools
import zmq


class server_process(threading_tools.process_pool, server_mixins.operational_error_mixin):
    def __init__(self):
        self.__log_cache, self.__log_template = ([], None)
        self.__pid_name = global_config["PID_NAME"]
        self.__verbose = global_config["VERBOSE"]
        threading_tools.process_pool.__init__(self, "main", zmq=True, zmq_debug=global_config["ZMQ_DEBUG"])
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        # close connection (daemonizing)
        connection.close()
        self.__msi_block = self._init_msi_block()
        # re-insert config
        self._re_insert_config()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("hup_error", self._hup_error)
        self._log_config()
        self.add_process(graph_process("graph"), start=True)
        self.add_process(stale_process("stale"), start=True)
        connection.close()
        self._init_network_sockets()
        self.register_func("send_command", self._send_command)
        DataStore.setup(self)

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

    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            while self.__log_cache:
                self.__log_template.log(*self.__log_cache.pop(0))
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))

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

    def _send_command(self, *args, **kwargs):
        _src_proc, _src_id, full_uuid, srv_com = args
        self.log("init send of {:d} bytes to {}".format(len(srv_com), full_uuid))
        self.com_socket.send_unicode(full_uuid, zmq.SNDMORE)  # @UndefinedVariable
        self.com_socket.send_unicode(srv_com)

    def _init_network_sockets(self):
        self.bind_id = get_server_uuid("grapher")
        client = process_tools.get_socket(self.zmq_context, "ROUTER", identity=self.bind_id, immediate=True)
        bind_str = "tcp://*:{:d}".format(global_config["COM_PORT"])
        try:
            client.bind(bind_str)
        except zmq.ZMQError:
            self.log(
                "error binding to {:d}: {}".format(
                    global_config["COM_PORT"],
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_CRITICAL
            )
            raise
        else:
            self.log("bound to {} (id {})".format(bind_str, self.bind_id))
            self.register_poller(client, zmq.POLLIN, self._recv_command)  # @UndefinedVariable
            self.com_socket = client
        # connection to collectd clients
        # self._collectd_sockets = {}
        # collectd_hosts = ["127.0.0.1"]
        # [self._open_collectd_socket(_host) for _host in collectd_hosts]

    def _get_node_rrd(self, srv_com):
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

    # def _iter_level(self, start_el, _dict):
    #    for node in
    def _recv_command(self, zmq_sock):
        in_data = []
        while True:
            in_data.append(zmq_sock.recv())
            if not zmq_sock.getsockopt(zmq.RCVMORE):  # @UndefinedVariable
                break
        # self.log("{:d}".format(len(in_data)))
        if len(in_data) == 2:
            src_id, data = in_data
            try:
                srv_com = server_command.srv_command(source=data)
            except:
                self.log(
                    "error interpreting command: {}".format(process_tools.get_except_info()),
                    logging_tools.LOG_LEVEL_ERROR
                )
                # send something back
                self.com_socket.send_unicode(src_id, zmq.SNDMORE)  # @UndefinedVariable
                self.com_socket.send_unicode("internal error")
            else:
                cur_com = srv_com["command"].text
                if self.__verbose or cur_com not in ["ocsp-event", "ochp-event" "vector", "perfdata_info"]:
                    self.log("got command '{}' from '{}'".format(
                        cur_com,
                        srv_com["source"].attrib["host"])
                    )
                srv_com.update_source()
                send_return = True
                srv_reply, srv_state = (
                    "ok processed command {}".format(cur_com),
                    server_command.SRV_REPLY_STATE_OK
                )
                if cur_com == "get_node_rrd":
                    self._get_node_rrd(srv_com)
                elif cur_com == "graph_rrd":
                    send_return = False
                    self.send_to_process("graph", "graph_rrd", src_id, unicode(srv_com))
                elif cur_com == "get_0mq_id":
                    srv_com["zmq_id"] = self.bind_id
                    srv_reply = "0MQ_ID is {}".format(self.bind_id)
                elif cur_com == "status":
                    srv_reply = "up and running"
                else:
                    self.log("got unknown command '{}'".format(cur_com), logging_tools.LOG_LEVEL_ERROR)
                    srv_reply, srv_state = (
                        "unknown command '{}'".format(cur_com),
                        server_command.SRV_REPLY_STATE_ERROR,
                    )
                if send_return:
                    srv_com.set_result(srv_reply, srv_state)
                    try:
                        self.com_socket.send_unicode(src_id, zmq.SNDMORE)  # @UndefinedVariable
                        self.com_socket.send_unicode(unicode(srv_com))
                    except:
                        self.log(
                            "error sending return to {}".format(src_id),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                else:
                    del cur_com
        else:
            self.log(
                "wrong count of input data frames: {:d}, first one is {}".format(
                    len(in_data),
                    in_data[0]),
                logging_tools.LOG_LEVEL_ERROR)

    def loop_end(self):
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()

    def loop_post(self):
        self.com_socket.close()
        # for _key, _sock in self._collectd_sockets.iteritems():
        #    _sock.close()
        self.__log_template.close()

    def thread_loop_post(self):
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
