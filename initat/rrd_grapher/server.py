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

from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models import device, MVStructEntry, MachineVector
from initat.cluster.backbone.routing import get_server_uuid
from initat.rrd_grapher.config import global_config
from initat.rrd_grapher.graph import graph_process
from initat.rrd_grapher.struct import data_store
from lxml.builder import E  # @UnresolvedImport
import cluster_location
import configfile
import json
import logging_tools
import os
import process_tools
import server_command
import server_mixins
import pprint
import stat
import threading_tools
import time
import zmq
import rrdtool  # @UnresolvedImport


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
        connection.close()
        self._init_network_sockets()
        self.register_func("send_command", self._send_command)
        self.register_timer(self._clear_old_graphs, 60, instant=True)
        self.register_timer(self._check_for_stale_rrds, 3600, instant=True)
        data_store.setup(self)

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

    def _check_for_stale_rrds(self):
        cur_time = time.time()
        # set stale after two hours
        MAX_DT = 3600 * 2
        num_changed = 0
        for mv in MachineVector.objects.all().prefetch_related("mvstructentry_set"):
            enabled, disabled = (0, 0)
            num_active = 0
            for mvs in mv.mvstructentry_set.all():
                f_name = mvs.file_name
                is_active = True if mvs.is_active else False
                if os.path.isfile(f_name):
                    _stat = os.stat(f_name)
                    if _stat[stat.ST_SIZE] < 1024:
                        self.log("file {} is too small, deleting and disabling...".format(f_name), logging_tools.LOG_LEVEL_ERROR)
                        try:
                            os.unlink(f_name)
                        except:
                            self.log("error deleting {}: {}".format(f_name, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                        is_active, stale = (False, True)
                    else:
                        c_time = os.stat(f_name)[stat.ST_MTIME]
                        stale = abs(cur_time - c_time) > MAX_DT
                        if stale:
                            # check via rrdtool
                            try:
                                # important: cast to str
                                rrd_info = rrdtool.info(str(f_name))
                            except:
                                raise
                                self.log(
                                    "cannot get info for {} via rrdtool: {}".format(
                                        f_name,
                                        process_tools.get_except_info()
                                    ),
                                    logging_tools.LOG_LEVEL_ERROR
                                )
                            else:
                                c_time = int(rrd_info["last_update"])
                                stale = abs(cur_time - c_time) > MAX_DT
                    if is_active:
                        num_active += 1
                    if is_active and stale:
                        mvs.is_active = False
                        mvs.save(update_fields=["is_active"])
                        disabled += 1
                    elif not is_active and not stale:
                        mvs_active = True
                        mvs.save(update_fields=["is_active"])
                        enabled += 1
                else:
                    if is_active:
                        self.log("file '{}' missing, disabling".format(mvs.file_name, logging_tools.LOG_LEVEL_ERROR))
                        mvs.is_active = False
                        mvs.save(update_fields=["is_active"])
                        disabled += 1
            if enabled or disabled:
                num_changed += 1
                self.log("updated active info for {}: {:d} enabled, {:d} disabled".format(
                    _struct.name,
                    enabled,
                    disabled,
                    ))
            try:
                cur_dev = mv.device
            except device.DoesNotExist:
                self.log("device with pk no longer present", logging_tools.LOG_LEVEL_WARN)
            else:
                is_active = num_active > 0
                if is_active != cur_dev.has_active_rrds:
                    cur_dev.has_active_rrds = is_active
                    cur_dev.save(update_fields=["has_active_rrds"])
        self.log("checked for stale entries, modified {}".format(logging_tools.get_plural("device", num_changed)))

    def _clear_old_graphs(self):
        cur_time = time.time()
        graph_root = global_config["GRAPH_ROOT"]
        del_list = []
        if os.path.isdir(graph_root):
            for entry in os.listdir(graph_root):
                if entry.endswith(".png"):
                    full_name = os.path.join(graph_root, entry)
                    c_time = os.stat(full_name)[stat.ST_CTIME]
                    diff_time = abs(c_time - cur_time)
                    if diff_time > 5 * 60:
                        del_list.append(full_name)
        else:
            self.log("graph_root '{}' not found, strange".format(graph_root), logging_tools.LOG_LEVEL_ERROR)
        if del_list:
            self.log("clearing {} in {}".format(
                logging_tools.get_plural("old graph", len(del_list)),
                graph_root))
            for del_entry in del_list:
                try:
                    os.unlink(del_entry)
                except:
                    pass

    def _init_msi_block(self):
        process_tools.save_pid(self.__pid_name, mult=3)
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=3)
        self.log("Initialising meta-server-info block")
        msi_block = process_tools.meta_server_info("rrd-grapher")
        msi_block.add_actual_pid(mult=3, fuzzy_ceiling=4, process_name="main")
        msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=3, process_name="manager")
        msi_block.start_command = "/etc/init.d/rrd-grapher start"
        msi_block.stop_command = "/etc/init.d/rrd-grapher force-stop"
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
            if data_store.has_machine_vector(dev_pk):
                # web mode (sorts entries)
                _struct = data_store.get_instance(dev_pk).vector_struct()
                _struct.extend(data_store.compound_struct(_struct))
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
                # if cur_com in ["mv_info"]:
                #    self.log("got mv_info")
                #    self._interpret_mv_info(srv_com["vector"])
                #    send_return = False
                # elif cur_com in ["perfdata_info"]:
                #    self._interpret_perfdata_info(
                #        srv_com["hostname"].text,
                #        srv_com["pd_type"].text,
                #        srv_com["info"][0],
                #        srv_com["file_name"].text
                #    )
                #    send_return = False
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
                    self.com_socket.send_unicode(src_id, zmq.SNDMORE)  # @UndefinedVariable
                    self.com_socket.send_unicode(unicode(srv_com))
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
