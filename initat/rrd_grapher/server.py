# Copyright (C) 2007-2009,2013-2014 Andreas Lang-Nevyjel, init.at
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

from config_tools import router_object
from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models import device
from initat.cluster.backbone.routing import get_server_uuid
from initat.rrd_grapher.config import global_config, CD_COM_PORT
from initat.rrd_grapher.graph import graph_process
from initat.rrd_grapher.resize import resize_process
from initat.rrd_grapher.struct import data_store, var_cache
from lxml.builder import E  # @UnresolvedImport
import cluster_location
import config_tools
import configfile
import logging_tools
import os
import process_tools
import server_command
import stat
import threading_tools
import time
import uuid_tools
import zmq
try:
    import rrdtool  # @UnresolvedImport
except ImportError:
    rrdtool = None


class server_process(threading_tools.process_pool, threading_tools.operational_error_mixin):
    def __init__(self):
        self.__log_cache, self.__log_template = ([], None)
        self.__pid_name = global_config["PID_NAME"]
        self.__verbose = global_config["VERBOSE"]
        threading_tools.process_pool.__init__(self, "main", zmq=True, zmq_debug=global_config["ZMQ_DEBUG"])
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        if not global_config["DEBUG"]:
            process_tools.set_handles({
                "out": (1, "rrd-grapher.out"),
                "err": (0, "/var/lib/logging-server/py_err_zmq")},
                zmq_context=self.zmq_context
            )
        self.__msi_block = self._init_msi_block()
        # re-insert config
        self._re_insert_config()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("hup_error", self._hup_error)
        self._log_config()
        self._init_network_sockets()
        self.add_process(graph_process("graph"), start=True)
        self.add_process(resize_process("resize"), start=True)
        connection.close()
        self.register_func("send_command", self._send_command)
        self.register_timer(self._clear_old_graphs, 60, instant=True)
        self.register_timer(self._check_for_stale_rrds, 3600, instant=True)
        self.register_timer(self._connect_to_collectd, 300, instant=True)
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
        self._connect_to_collectd()

    def process_start(self, src_process, src_pid):
        mult = 3
        process_tools.append_pids(self.__pid_name, src_pid, mult=mult)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(src_pid, mult=mult, process_name=src_process)
            self.__msi_block.save_block()

    def _get_disabled_hosts(self):
        disabled_hosts = device.objects.filter(Q(store_rrd_data=False))
        num_dis = disabled_hosts.count()
        self.log(
            "{} with no_store flag, contacting {}".format(
                logging_tools.get_plural("device", num_dis),
                logging_tools.get_plural("collectd", len(self._collectd_sockets))
            )
        )
        dis_com = server_command.srv_command(command="disabled_hosts")
        _bld = dis_com.builder()
        dis_com["no_rrd_store"] = _bld.device_list(
            *[
                _bld.device(
                    pk="{:d}".format(cur_dev.pk),
                    short_name="{}".format(cur_dev.name),
                    full_name="{}".format(cur_dev.full_name),
                    uuid="{}".format(cur_dev.uuid)
                ) for cur_dev in disabled_hosts]
            )
        return dis_com

    def _check_reachability(self, devs, var_cache, _router, _type):
        _reachable, _unreachable = ([], [])
        _sc = config_tools.server_check(server_type="rrd_server")
        for dev in devs:
            _path = _sc.get_route_to_other_device(
                _router, config_tools.server_check(device=dev, config=None, server_type="node"), allow_route_to_other_networks=True
            )
            if not len(_path):
                _unreachable.append(dev)
            else:
                _ip = _path[0][3][1][0]
                # self.log("IPMI device {} is reachable via {}".format(unicode(ipmi_host), _ip))
                _reachable.append((dev, _ip, var_cache.get_vars(dev)[0]))
        if _unreachable:
            self.log(
                "{}: {}".format(
                    logging_tools.get_plural("unreachable {} device".format(_type), len(_unreachable)),
                    logging_tools.compress_list([unicode(_dev) for _dev in _unreachable])
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        if _reachable:
            self.log(
                "{}: {}".format(
                    logging_tools.get_plural("reachable {} device".format(_type), len(_reachable)),
                    logging_tools.compress_list([unicode(_dev) for _dev, _ip, _vars in _reachable])
                ),
            )
        return _reachable

    def _get_snmp_hosts(self, _router):
        # var cache
        _vc = var_cache(
            device.objects.get(
                Q(device_group__cluster_device_group=True)
            ), {"SNMP_VERSION": 1, "SNMP_READ_COMMUNITY": "public", "SNMP_SCHEME": "unknown"}
        )
        snmp_hosts = device.objects.filter(Q(enabled=True) & Q(device_group__enabled=True) & Q(curl__istartswith="snmp://") & Q(enable_perfdata=True))
        _reachable = self._check_reachability(snmp_hosts, _vc, _router, "SNMP")
        snmp_com = server_command.srv_command(command="snmp_hosts")
        _bld = snmp_com.builder()
        snmp_com["devices"] = _bld.device_list(
            *[
                _bld.device(
                    pk="{:d}".format(cur_dev.pk),
                    short_name="{}".format(cur_dev.name),
                    full_name="{}".format(cur_dev.full_name),
                    uuid="{}".format(cur_dev.uuid),
                    ip="{}".format(_ip),
                    snmp_version="{:d}".format(_vars["SNMP_VERSION"]),
                    snmp_read_community=_vars["SNMP_READ_COMMUNITY"],
                    snmp_scheme=_vars["SNMP_SCHEME"],
                ) for cur_dev, _ip, _vars in _reachable
            ]
        )
        return snmp_com

    def _get_ipmi_hosts(self, _router):
        # var cache
        _vc = var_cache(
            device.objects.get(
                Q(device_group__cluster_device_group=True)
            ), {"IPMI_USERNAME": "notset", "IPMI_PASSWORD": "notset", "IPMI_INTERFACE": ""}
        )
        ipmi_hosts = device.objects.filter(Q(enabled=True) & Q(device_group__enabled=True) & Q(curl__istartswith="ipmi://") & Q(enable_perfdata=True))
        _reachable = self._check_reachability(ipmi_hosts, _vc, _router, "IPMI")
        ipmi_com = server_command.srv_command(command="ipmi_hosts")
        _bld = ipmi_com.builder()
        ipmi_com["devices"] = _bld.device_list(
            *[
                _bld.device(
                    pk="{:d}".format(cur_dev.pk),
                    short_name="{}".format(cur_dev.name),
                    full_name="{}".format(cur_dev.full_name),
                    uuid="{}".format(cur_dev.uuid),
                    ip="{}".format(_ip),
                    ipmi_username=_vars["IPMI_USERNAME"],
                    ipmi_password=_vars["IPMI_PASSWORD"],
                    ipmi_interface=_vars["IPMI_INTERFACE"],
                ) for cur_dev, _ip, _vars in _reachable
            ]
        )
        return ipmi_com

    def _connect_to_collectd(self):
        _router = router_object(self.log)
        send_coms = [self._get_disabled_hosts(), self._get_ipmi_hosts(_router), self._get_snmp_hosts(_router)]
        snd_ok, snd_try = (0, 0)
        _error_keys = set()
        for send_com in send_coms:
            for key in sorted(self._collectd_sockets):
                snd_try += 1
                try:
                    self._collectd_sockets[key].send_unicode(unicode(send_com))
                except:
                    self.log("error sending to {}: {}".format(key, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                    _error_keys.add(key)
                else:
                    snd_ok += 1
        self.log(
            "sent {}, {:d} OK, {:d} with problems".format(
                logging_tools.get_plural("command", len(send_coms)),
                snd_ok,
                snd_try - snd_ok,
            )
        )
        if _error_keys:
            [self._open_collectd_socket(_host) for _host in _error_keys]

    def _check_for_stale_rrds(self):
        cur_time = time.time()
        # set stale after two hours
        MAX_DT = 3600 * 2
        num_changed = 0
        for pk in data_store.present_pks():
            _struct = data_store.get_instance(pk)
            enabled, disabled = (0, 0)
            num_active = 0
            for file_el in _struct.xml_vector.xpath(".//*[@file_name]", smart_strings=False):
                f_name = file_el.attrib["file_name"]
                if os.path.isfile(f_name):
                    c_time = os.stat(f_name)[stat.ST_MTIME]
                    stale = abs(cur_time - c_time) > MAX_DT
                    if stale and rrdtool:
                        # check via rrdtool
                        try:
                            rrd_info = rrdtool.info(f_name)
                        except:
                            self.log("cannot get info for {} via rrdtool: {}".format(
                                f_name,
                                process_tools.get_except_info()
                                ),
                                logging_tools.LOG_LEVEL_ERROR
                            )
                        else:
                            c_time = int(rrd_info["last_update"])
                            stale = abs(cur_time - c_time) > MAX_DT
                    is_active = True if int(file_el.attrib["active"]) else False
                    if is_active:
                        num_active += 1
                    if is_active and stale:
                        file_el.attrib["active"] = "0"
                        disabled += 1
                    elif not is_active and not stale:
                        file_el.attrib["active"] = "1"
                        enabled += 1
                else:
                    self.log("file '{}' missing, disabling".format(file_el.attrib["file_name"]), logging_tools.LOG_LEVEL_ERROR)
                    file_el.attrib["active"] = "0"
                    disabled += 1
            if enabled or disabled:
                num_changed += 1
                self.log("updated active info for {}: {:d} enabled, {:d} disabled".format(
                    _struct.name,
                    enabled,
                    disabled,
                    ))
                _struct.store()
            try:
                cur_dev = device.objects.get(Q(pk=pk))
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
        if not global_config["DEBUG"] or True:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("rrd-grapher")
            msi_block.add_actual_pid(mult=3, fuzzy_ceiling=3, process_name="main")
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=4, process_name="manager")
            msi_block.start_command = "/etc/init.d/rrd-grapher start"
            msi_block.stop_command = "/etc/init.d/rrd-grapher force-stop"
            msi_block.kill_pids = True
            msi_block.save_block()
        else:
            msi_block = None
        return msi_block

    def _send_command(self, *args, **kwargs):
        _src_proc, _src_id, full_uuid, srv_com = args
        self.log("init send of {:d} bytes to {}".format(len(srv_com), full_uuid))
        self.com_socket.send_unicode(full_uuid, zmq.SNDMORE)
        self.com_socket.send_unicode(srv_com)

    def _init_network_sockets(self):
        self.bind_id = get_server_uuid("grapher")
        client = process_tools.get_socket(self.zmq_context, "ROUTER", identity=self.bind_id)
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
            self.register_poller(client, zmq.POLLIN, self._recv_command)
            self.com_socket = client
        # connection to collectd clients
        self._collectd_sockets = {}
        collectd_hosts = ["127.0.0.1"]
        [self._open_collectd_socket(_host) for _host in collectd_hosts]

    def _open_collectd_socket(self, _ch):
        if _ch in self._collectd_sockets:
            self._collectd_sockets[_ch].close()
            del self._collectd_sockets[_ch]
        _id_str = "{}:{}:rrd_cs".format(uuid_tools.get_uuid().get_urn(), _ch)
        _cs = process_tools.get_socket(self.zmq_context, "DEALER", identity=self.bind_id)
        _conn_str = "tcp://{}:{:d}".format(_ch, CD_COM_PORT)
        self.log("connection string for collectd at {} is {}".format(_ch, _conn_str))
        _cs.connect(_conn_str)
        self._collectd_sockets[_ch] = _cs

    def _interpret_mv_info(self, in_vector):
        data_store.feed_vector(in_vector[0])

    def _interpret_perfdata_info(self, host_name, pd_type, pd_info):
        data_store.feed_perfdata(host_name, pd_type, pd_info)

    def _get_node_rrd(self, srv_com):
        node_results = E.node_results()
        dev_list = srv_com.xpath(".//device_list", smart_strings=False)[0]
        pk_list = [int(cur_pk) for cur_pk in dev_list.xpath(".//device/@pk", smart_strings=False)]
        for dev_pk in pk_list:
            cur_res = E.node_result(pk="{:d}".format(dev_pk))
            if data_store.has_rrd_xml(dev_pk):
                # web mode (sorts entries)
                cur_res.append(data_store.get_rrd_xml(dev_pk, mode="web"))
            else:
                self.log("no rrd_xml found for device {:d}".format(dev_pk), logging_tools.LOG_LEVEL_WARN)
            node_results.append(cur_res)
        if int(dev_list.get("merge_results", "0")):
            node_results = data_store.merge_node_results(node_results)
        srv_com["result"] = node_results

    def _recv_command(self, zmq_sock):
        in_data = []
        while True:
            in_data.append(zmq_sock.recv())
            if not zmq_sock.getsockopt(zmq.RCVMORE):
                break
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
                self.com_socket.send_unicode(src_id, zmq.SNDMORE)
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
                if cur_com in ["mv_info"]:
                    self._interpret_mv_info(srv_com["vector"])
                    send_return = False
                elif cur_com in ["perfdata_info"]:
                    self._interpret_perfdata_info(srv_com["hostname"].text, srv_com["pd_type"].text, srv_com["info"][0])
                    send_return = False
                elif cur_com == "get_node_rrd":
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
                    self.com_socket.send_unicode(src_id, zmq.SNDMORE)
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
        for _key, _sock in self._collectd_sockets.iteritems():
            _sock.close()
        self.__log_template.close()

    def thread_loop_post(self):
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
