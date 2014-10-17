#
# this file is part of collectd-init
#
# Copyright (C) 2013-2014 Andreas Lang-Nevyjel init.at
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
""" collectd-init, server part """

from django.conf import settings
from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models import device
from initat.cluster.backbone.routing import get_server_uuid
from initat.collectd.background import snmp_job, bg_job, ipmi_builder
from initat.collectd.resize import resize_process
from initat.collectd.aggregate import aggregate_process
from initat.collectd.collectd_types import *  # @UnusedWildImport
from initat.collectd.config import global_config, IPC_SOCK_SNMP, MD_SERVER_UUID
from initat.collectd.struct import host_info, var_cache, ext_com, host_matcher, file_creator
from initat.snmp_relay.snmp_process import snmp_process_container
from lxml import etree
from lxml.builder import E  # @UnresolvedImports
import cluster_location
import config_tools
import configfile
import logging_tools
import pprint
import process_tools
import re
import server_command
import socket
import threading_tools
import time
import uuid_tools
import zmq


class server_process(threading_tools.process_pool, threading_tools.operational_error_mixin):
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
        self._init_network_sockets()
        self.register_func("disable_rrd_cached", self.disable_rrd_cached)
        self.register_func("enable_rrd_cached", self.enable_rrd_cached)
        self.hm = host_matcher(self.log)
        self.fc = file_creator(self.log)
        self.__last_sent = {}
        self.__snmp_running = True
        self._init_snmp()
        self._init_perfdata()
        self._init_vars()
        self._init_hosts()
        self._init_rrd_cached()
        self.__ipmi_list = []
        bg_job.setup(self)
        snmp_job.setup(self)
        self.register_timer(self._check_database, 300, instant=True)
        self.register_timer(self._check_background, 2, instant=True)
        self.__cached_stats, self.__cached_time = (None, time.time())
        self.register_timer(self._check_cached_stats, 30, first_timeout=5)
        self.add_process(resize_process("resize"), start=True)
        self.add_process(aggregate_process("aggregate"), start=True)
        connection.close()
        # self.register_func("send_command", self._send_command)
        # self.register_timer(self._clear_old_graphs, 60, instant=True)
        # self.register_timer(self._check_for_stale_rrds, 3600, instant=True)
        # self.register_timer(self._connect_to_collectd, 300, instant=True)
        # data_store.setup(self)

    def _init_perfdata(self):
        re_list = []
        for key in globals().keys():
            obj = globals()[key]
            if type(obj) == type and obj != perfdata_object:
                if issubclass(obj, perfdata_object):
                    obj = obj()
                    re_list.append((obj.PD_RE, obj))
        self.__pd_re_list = re_list

    def _init_vars(self):
        self.__start_time = time.time()
        self.__trees_read, self.__pds_read = (0, 0)
        self.__total_size_trees, self.__total_size_pds = (0, 0)
        self.__distinct_hosts_mv = set()
        self.__distinct_hosts_pd = set()

    def _init_hosts(self):
        # init host and perfdata structs
        host_info.setup(self.fc)
        self.__hosts = {}

    def _log_config(self):
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [{:d}] {}".format(log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found {:d} valid global config-lines:".format(len(conf_info)))
        for conf in conf_info:
            self.log("Config : {}".format(conf))

    def _re_insert_config(self):
        cluster_location.write_config("rrd_collector", global_config)

    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            while self.__log_cache:
                self.__log_template.log(*self.__log_cache.pop(0))
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))

    def _int_error(self, err_cause):
        if not self.__snmp_running:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self.spc.stop()
            self.__snmp_running = False

    def _hup_error(self, err_cause):
        self.log("got sighup", logging_tools.LOG_LEVEL_WARN)
        self._check_database()

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
        msi_block = process_tools.meta_server_info("collectd-init")
        msi_block.add_actual_pid(mult=3, fuzzy_ceiling=4, process_name="main")
        msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=4, process_name="manager")
        msi_block.start_command = "/etc/init.d/collectd-init start"
        msi_block.stop_command = "/etc/init.d/collectd-init force-stop"
        msi_block.kill_pids = True
        msi_block.save_block()
        return msi_block

    def _init_network_sockets(self):
        self.bind_id = get_server_uuid("collectd-init")
        client = process_tools.get_socket(self.zmq_context, "ROUTER", identity=self.bind_id, immediate=True)
        bind_str = "tcp://*:{:d}".format(global_config["COMMAND_PORT"])
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
            # self.md_target = self.zmq_context.socket(zmq.DEALER)  # @UndefinedVariable
            self.__last_md_send_error = None
            # for flag, value in [
            #    (zmq.IDENTITY, get_self.zmq_id),  # @UndefinedVariable
            #    (zmq.SNDHWM, 4),  # @UndefinedVariable
            #    (zmq.RCVHWM, 4),  # @UndefinedVariable
            #    (zmq.TCP_KEEPALIVE, 1),  # @UndefinedVariable
            #    (zmq.IMMEDIATE, 1),  # @UndefinedVariable
            #    (zmq.TCP_KEEPALIVE_IDLE, 300),  # @UndefinedVariable
            # ]:
            #    self.md_target.setsockopt(flag, value)
            self.grapher_id = "{}:grapher:".format(uuid_tools.get_uuid().get_urn())
            self.__grapher_url = "tcp://localhost:{:d}".format(global_config["GRAPHER_PORT"])
            self.md_target_addr = "tcp://{}:{:d}".format(
                global_config["MD_SERVER_HOST"],
                global_config["MD_SERVER_PORT"],
            )
            # self.md_target.connect(self.md_target_addr)
            self.md_target_id = "{}:{}:".format(
                MD_SERVER_UUID,
                "md-config-server",
            )
            self.com_socket.connect(self.md_target_addr)
            self.log("connection to md-config-server at {}".format(self.md_target_addr))  # , self.md_target_id))
            self.__grapher_connected = False
            # receiver socket
            self.receiver = self.zmq_context.socket(zmq.PULL)  # @UndefinedVariable
            listener_url = "tcp://*:{:d}".format(global_config["RECV_PORT"])
            self.receiver.bind(listener_url)
            self._reconnect_to_grapher()
            self.register_poller(self.receiver, zmq.POLLIN, self._recv_data)  # @UndefinedVariable

    def _reconnect_to_grapher(self):
        if self.__grapher_connected:
            try:
                self.com_socket.disconnect(self.__grapher_url)
            except:
                self.log(
                    "error disconnecting grapher {}: {}".format(
                        self.__grapher_url,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                self.log("closed grapher connection", logging_tools.LOG_LEVEL_WARN)
            self.__grapher_connected = False
        try:
            self.com_socket.connect(self.__grapher_url)
        except:
            self.log(
                "error connecting grapher {}: {}".format(
                    self.__grapher_url,
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        else:
            self.log("connected to grapher at {}".format(self.__grapher_url))
            self.__grapher_connected = True

    def _init_rrd_cached(self):
        self.log("init rrd cached process")
        _comline = "/opt/cluster/bin/rrdcached -m0777 -l {} -s idg -w 60 -t {:d} -F -g -b {} -p /var/run/rrdcached/rrdcached.pid".format(
            global_config["RRD_CACHED_SOCKET"],
            global_config["RRD_CACHED_WRITETHREADS"],
            global_config["RRD_DIR"],
        )
        self.log("comline is {}".format(_comline))
        self.__rrd_com = ext_com(self.log, _comline, name="rrdcached")
        self.__rrdcached_socket = None
        # flag for enabled / disabled
        self.__rrdcached_enabled = True
        # flag for should run / should not run
        self.__rrdcached_run = True
        # flag for actually running
        self.__rrdcached_running = False
        self.start_rrd_cached()
        self.register_timer(self._check_for_rrdcached_socket, timeout=30, first_timeout=1)

    def disable_rrd_cached(self, *args, **kwargs):
        # stop rrd_cached if running and disable further starts
        self.__rrdcached_enabled = False
        self._check_rrd_cached_state()

    def enable_rrd_cached(self, *args, **kwargs):
        # enable rrd_cached and start if requested
        self.__rrdcached_enabled = True
        self._check_rrd_cached_state()

    def start_rrd_cached(self):
        self.__rrdcached_run = True
        self._check_rrd_cached_state()

    def stop_rrd_cached(self):
        self.__rrdcached_run = False
        self._check_rrd_cached_state()

    def _check_rrd_cached_state(self):
        def _log():
            self.log(
                "_run={}, _enabled={}, _running={}, target_state={}".format(
                    self.__rrdcached_run,
                    self.__rrdcached_enabled,
                    self.__rrdcached_running,
                    _target_state,
                )
            )
        _target_state = True if (self.__rrdcached_run and self.__rrdcached_enabled) else False
        if self.__rrdcached_running and not _target_state:
            _log()
            self.__rrdcached_running = False
            self._close_rrdcached_socket()
            self.log("stopping rrd_cached process")
            self.__rrd_com.terminate()
            _result = self.__rrd_com.finished()
            if _result is not None:
                _stdout, _stderr = self.__rrd_com.communicate()
                self.log("stopped with result {:d}".format(_result))
                for _name, _stream in [("stdout", _stdout), ("stderr", _stderr)]:
                    if _stream:
                        for _line in _stream.split("\n"):
                            self.log("{}: {}".format(_name, _line))
        elif not self.__rrdcached_running and _target_state:
            _log()
            self.log("starting rrd_cached process")
            self.__rrd_com.run()
            self.__rrdcached_running = True

    def _check_for_rrdcached_socket(self):
        if not self.__rrdcached_socket and self.__rrdcached_running:
            self._open_rrdcached_socket()

    def _open_rrdcached_socket(self):
        self._close_rrdcached_socket()
        try:
            self.__rrdcached_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.__rrdcached_socket.connect(global_config["RRD_CACHED_SOCKET"])
        except:
            self.log("error opening rrdcached socket: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            self.__rrdcached_socket = None
        else:
            self.log("connected to rrdcached socket {}".format(global_config["RRD_CACHED_SOCKET"]))

    def _close_rrdcached_socket(self):
        if self.__rrdcached_socket:
            try:
                self.__rrdcached_socket.close()
            except:
                self.log("error closing rrdcached socket: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            else:
                self.log("closed rrdcached socket")
            self.__rrdcached_socket = None

    def send_to_grapher(self, send_xml):
        try:
            self.com_socket.send_unicode(self.grapher_id, zmq.DONTWAIT | zmq.SNDMORE)  # @UndefinedVariable
            self.com_socket.send_unicode(unicode(send_xml), zmq.DONTWAIT)  # @UndefinedVariable
        except zmq.error.ZMQError:
            # this will never happen because we are using a REQ socket
            self.log(
                "cannot send to grapher: {}".format(
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_CRITICAL
            )
            self._reconnect_to_grapher()
        else:
            # print "sent", unicode(send_xml)
            pass

    def send_to_md(self, send_str):
        cur_time = time.time()
        if self.__last_md_send_error and abs(self.__last_md_send_error - cur_time) < 10:
            # silently fail
            pass
        else:
            try:
                self.com_socket.send_unicode(self.md_target_id, zmq.DONTWAIT | zmq.SNDMORE)  # @UndefinedVariable
                self.com_socket.send_unicode(send_str, zmq.DONTWAIT)  # @UndefinedVariable
            except zmq.error.ZMQError:
                # this will never happen because we are using a REQ socket
                self.log(
                    "cannot send to md: {}".format(
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_CRITICAL
                )
                self.__last_md_send_error = cur_time
            else:
                pass

    def loop_end(self):
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()

    def loop_post(self):
        self.stop_rrd_cached()
        self._log_stats()
        self.com_socket.close()
        self.receiver.close()
        self.spc.close()
        self.__log_template.close()

    def thread_loop_post(self):
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()

    def _check_database(self):
        self._handle_disabled_hosts()
        _router = config_tools.router_object(self.log)
        for _send_com in [self._get_ipmi_hosts(_router), self._get_snmp_hosts(_router)]:
            self._handle_xml(_send_com)

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

    def _send_command(self, *args, **kwargs):
        _src_proc, _src_id, full_uuid, srv_com = args
        self.log("init send of {:d} bytes to {}".format(len(srv_com), full_uuid))
        self.com_socket.send_unicode(full_uuid, zmq.SNDMORE)  # @UndefinedVariable
        self.com_socket.send_unicode(srv_com)

    def _recv_command(self, zmq_sock):
        in_data = []
        while True:
            in_data.append(zmq_sock.recv())
            if not zmq_sock.getsockopt(zmq.RCVMORE):  # @UndefinedVariable
                break
        if len(in_data) == 2:
            in_uuid, in_xml = in_data
            try:
                in_com = server_command.srv_command(source=in_xml)
            except:
                self.log("error decoding command {}: {}".format(in_xml, process_tools.get_except_info), logging_tools.LOG_LEVEL_ERROR)
            else:
                com_text = in_com["command"].text
                self.log("got command {} from {}".format(com_text, in_uuid))
                if com_text in ["host_list", "key_list"]:
                    self._handle_hk_command(in_com, com_text)
                else:
                    self.log("unknown command {}".format(com_text), logging_tools.LOG_LEVEL_ERROR)
                    in_com.set_result(
                        "unknown command {}".format(com_text),
                        server_command.SRV_REPLY_STATE_ERROR
                        )
                zmq_sock.send_unicode(in_uuid, zmq.SNDMORE)  # @UndefinedVariable
                zmq_sock.send_unicode(unicode(in_com))

    def _init_snmp(self):
        self.spc = snmp_process_container(
            IPC_SOCK_SNMP,
            self.log,
            global_config["SNMP_PROCS"],
            global_config["MAX_SNMP_JOBS"],
            {
                "VERBOSE": True,
                "LOG_NAME": global_config["LOG_NAME"],
                "LOG_DESTINATION": global_config["LOG_DESTINATION"],
            },
            {
                "process_start": self._snmp_process_start,
                "process_exit": self._snmp_process_exit,
                "all_stopped": self._snmp_all_stopped,
                "finished": self._snmp_finished,
            }
        )
        _snmp_sock = self.spc.create_ipc_socket(self.zmq_context, IPC_SOCK_SNMP)
        self.register_poller(_snmp_sock, zmq.POLLIN, self.spc.handle_with_socket)  # @UndefinedVariable
        self.spc.check()

    def _snmp_process_start(self, **kwargs):
        self.__msi_block.add_actual_pid(
            kwargs["pid"],
            mult=kwargs.get("mult", 3),
            process_name=kwargs["process_name"],
            fuzzy_ceiling=kwargs.get("fuzzy_ceiling", 3)
        )
        self.__msi_block.save_block()

    def _snmp_process_exit(self, **kwargs):
        self.__msi_block.remove_actual_pid(kwargs["pid"], mult=kwargs.get("mult", 3))
        self.__msi_block.save_block()

    def _snmp_all_stopped(self):
        self["exit_requested"] = True

    def _snmp_finished(self, data):
        snmp_job.feed_result(data["args"])

    def _log_stats(self):
        self.__end_time = time.time()
        diff_time = max(1, abs(self.__end_time - self.__start_time))
        bt_rate = self.__trees_read / diff_time
        st_rate = self.__total_size_trees / diff_time
        bp_rate = self.__pds_read / diff_time
        sp_rate = self.__total_size_pds / diff_time
        self.log("read {} ({}) from {} (rate [{:.2f}, {}] / sec), {} ({}) from {} (rate [{:.2f}, {}] / sec) in {}".format(
            logging_tools.get_plural("tree", self.__trees_read),
            logging_tools.get_size_str(self.__total_size_trees),
            logging_tools.get_plural("host", len(self.__distinct_hosts_mv)),
            bt_rate,
            logging_tools.get_size_str(st_rate),
            logging_tools.get_plural("perfdata", self.__pds_read),
            logging_tools.get_size_str(self.__total_size_pds),
            logging_tools.get_plural("host", len(self.__distinct_hosts_pd)),
            bp_rate,
            logging_tools.get_size_str(sp_rate),
            logging_tools.get_diff_time_str(self.__end_time - self.__start_time),
        ))
        self._init_vars()

    def _create_host_info(self, _dev):
        if _dev.uuid not in self.__hosts:
            self.__hosts[_dev.uuid] = host_info(self.log, _dev)
        return self.__hosts[_dev.uuid]

    def _feed_host_info(self, _dev, _xml):
        _host_info = self._create_host_info(_dev)
        if _host_info.update(_xml, self.fc):
            # something changed
            new_com = server_command.srv_command(command="mv_info")
            new_com["vector"] = _xml
            self.send_to_grapher(new_com)
        return _host_info

    def _feed_host_info_ov(self, _dev, _xml):
        # update only values
        self.__hosts[_dev.uuid].update_ov(_xml)
        return self.__hosts[_dev.uuid]

    def feed_data(self, data):
        self._process_data(data)

    def _recv_data(self, in_sock):
        in_data = in_sock.recv()
        self._process_data(in_data)
        if abs(time.time() - self.__start_time) > 300:
            # periodic log stats
            self._log_stats()

    def _process_data(self, in_tree):
        # adopt tree format for faster handling in collectd loop
        try:
            _xml = etree.fromstring(in_tree)  # @UndefinedVariable
        except:
            self.log(
                "cannot parse tree: {}".format(
                    process_tools.get_except_info()
                ), logging_tools.LOG_LEVEL_ERROR
            )
        else:
            xml_tag = _xml.tag.split("}")[-1]
            handle_name = "_handle_{}".format(xml_tag)
            if hasattr(self, handle_name):
                try:
                    # loop
                    for p_data in getattr(self, handle_name)(_xml, len(in_tree)):
                        self.handle_raw_data(p_data)
                except:
                    exc_info = process_tools.exception_info()
                    for _line in exc_info.log_lines:
                        self.log(
                            _line,
                            logging_tools.LOG_LEVEL_ERROR
                        )
            else:
                self.log("unknown handle_name '{}'".format(handle_name), logging_tools.LOG_LEVEL_ERROR)

    def _handle_machine_vector(self, _xml, data_len):
        self.__trees_read += 1
        self.__total_size_trees += data_len
        simple, host_name, host_uuid, recv_time = (
            _xml.attrib["simple"] == "1",
            _xml.attrib["name"],
            # if uuid is not set use name as uuid (will not be sent to the grapher)
            _xml.attrib.get("uuid", _xml.attrib.get("name")),
            float(_xml.attrib["time"]),
        )
        self.__distinct_hosts_mv.add(host_uuid)
        _dev = self.hm.update(host_uuid, host_name)
        if _dev is None:
            self.log("no device found for host {} ({})".format(host_name, host_uuid))
            raise StopIteration
        else:
            if simple and _dev.uuid not in self.__hosts:
                self.log(
                    "no full info for host {} ({}) received, discarding data".format(
                        host_name,
                        host_uuid,
                    ),
                    logging_tools.LOG_LEVEL_WARN
                )
                raise StopIteration
            else:
                # store values in host_info (and memcached)
                # host_uuid is uuid or name
                if simple:
                    # only values
                    _host_info = self._feed_host_info_ov(_dev, _xml)
                else:
                    _host_info = self._feed_host_info(_dev, _xml)
                if not _host_info.store_to_disk:
                    # writing to disk not allowed
                    raise StopIteration
                values = _host_info.get_values(_xml, simple)
                r_data = ("mvector", _host_info, recv_time, values)
                yield r_data

    def _handle_perf_data(self, _xml, data_len):
        self.__total_size_pds += data_len
        # iterate over lines
        for p_data in _xml:
            _uuid = p_data.get("uuid", "")
            _name = p_data.get("host", "")
            _dev = self.hm.update(_uuid, _name)
            if _dev is None:
                self.log("no device found for host {} ({})".format(p_data.get("host"), _uuid))
            else:
                _host_info = self._create_host_info(_dev)
                self.__pds_read += 1
                perf_value = p_data.get("perfdata", "").strip()
                if perf_value:
                    self.__distinct_hosts_pd.add(p_data.attrib["host"])
                    mach_values = self._find_matching_pd_handler(_host_info, p_data, perf_value)
                    for pd_vec in mach_values:
                        if pd_vec[2] is not None:
                            self.send_to_grapher(pd_vec[2])
                        yield ("pdata", pd_vec)
        raise StopIteration

    def _find_matching_pd_handler(self, _host_info, p_data, perf_value):
        values = []
        for cur_re, re_obj in self.__pd_re_list:
            cur_m = cur_re.match(perf_value)
            if cur_m:
                values.append(re_obj.build_values(_host_info, p_data, cur_m.groupdict()))
                # stop loop
                break
        if not values:
            self.log(
                "unparsed perfdata '{}' from {} ({})".format(
                    perf_value,
                    _host_info.name,
                    _host_info.uuid,
                ),
                logging_tools.LOG_LEVEL_WARN
            )
        return values

    def handle_raw_data(self, data):
        _com = data[0]
        if _com == "mvector":
            self._handle_mvector_tree(data[1:])
        elif _com == "pdata":
            # always take the first value of data
            self._handle_perfdata(data[1])
        else:
            self.log("unknown data: {}".format(_com), logging_tools.LOG_LEVEL_ERROR)

    def get_time(self, h_tuple, cur_time):
        cur_time = int(cur_time)
        pprint.pprint(self.__last_sent)
        if h_tuple in self.__last_sent:
            if cur_time <= self.__last_sent[h_tuple]:
                diff_time = self.__last_sent[h_tuple] + 1 - cur_time
                cur_time += diff_time
                self.log("correcting time for {} (+{:d}s to {:d})".format(str(h_tuple), diff_time, int(cur_time)))
        self.__last_sent[h_tuple] = cur_time
        return self.__last_sent[h_tuple]

    def _handle_perfdata(self, data):
        pd_tuple, _host_info, _send_xml, time_recv, rsi, v_list = data
        # s_time = self.get_time((_host_info.name, "ipd_{}_{}".format(pd_tuple[0], pd_tuple[1])), time_recv)
        s_time = int(time_recv)
        if self.__rrdcached_socket:
            _tf = _host_info.target_file(pd_tuple, step=5 * 60, v_type="ipd_{}".format(pd_tuple[0]))
            if _tf:
                cache_lines = [
                    "UPDATE {} {:d}:{}".format(
                        _tf,  # self.fc.get_target_file(_target_dir, "perfdata", type_instance, "ipd_{}".format(_type), step=5 * 60),
                        s_time,
                        ":".join([str(_val) for _val in v_list[rsi:]]),
                    )
                ]
                self.do_rrdcc(_host_info, cache_lines)

    def _handle_mvector_tree(self, data):
        _host_info, time_recv, values = data
        # print host_name, time_recv
        # s_time = self.get_time((_host_info.name, "icval"), time_recv)
        s_time = int(time_recv)
        cache_lines = []
        if self.__rrdcached_socket:
            for name, value in values:
                # name can be none for values with transform problems
                if name:
                    try:
                        _tf = _host_info.target_file(name)
                    except:
                        self.log("cannot get target file name for {}: {}".format(name, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                    else:
                        if _tf:
                            cache_lines.append(
                                "UPDATE {} {:d}:{}".format(
                                    _tf,
                                    s_time,
                                    str(value),
                                )
                            )
            if cache_lines:
                self.do_rrdcc(_host_info, cache_lines)

    def do_rrdcc(self, host_info, cache_lines):
        # end rrd-cached communication
        self.__rrdcached_socket.send("BATCH\n")
        for _line in cache_lines:
            self.__rrdcached_socket.send("{}\n".format(_line))
        self.__rrdcached_socket.send(".\n")
        _skip_lines = 0
        _read = True
        s_time = time.time()
        _content = ""
        while _read:
            if settings.DEBUG:
                self.log("read...")
            _content = "{}{}".format(_content, self.__rrdcached_socket.recv(4096))
            if settings.DEBUG:
                self.log("...done, content has {:d} bytes".format(len(_content)))
            if _content.endswith("\n"):
                for _line in _content.split("\n"):
                    if not _line.strip():
                        # empty line
                        continue
                    if _skip_lines:
                        _skip_lines -= 1
                        _idx = int(_line.split()[0])
                        self.log(
                            u"error: {} for {}".format(
                                _line,
                                cache_lines[_idx - 1]
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                        if not _skip_lines:
                            _read = False
                    else:
                        if _line.startswith("0 Go"):
                            # ignore first line
                            pass
                        elif _line.endswith("errors"):
                            _errcount = int(_line.split()[0])
                            _skip_lines = _errcount
                            if _errcount:
                                self.log(
                                    "errors from RRDcached for {}: {:d}".format(
                                        host_info.name,
                                        _errcount,
                                    ),
                                    logging_tools.LOG_LEVEL_ERROR
                                )
                            else:
                                _read = False
                        else:
                            self.log("unparsed line: '{}'".format(_line), logging_tools.LOG_LEVEL_WARN)
                _content = ""
        e_time = time.time()
        if _errcount:
            self.log("parsing took {}".format(logging_tools.get_diff_time_str(e_time - s_time)))

    def _check_cached_stats(self):
        if self.__rrdcached_socket:
            try:
                self.__rrdcached_socket.send("STATS\n")
                _lines = self.__rrdcached_socket.recv(16384).split("\n")
            except:
                self.log("error communicating with rrdcached: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            else:
                _first_line_parts = _lines[0].strip().split()
                _dict = None
                if _first_line_parts and _first_line_parts[0].isdigit():
                    if int(_first_line_parts[0]) + 2 == len(_lines):
                        cur_time = time.time()
                        _dict = {_line.split(":")[0]: int(_line.split(":")[1].strip()) for _line in _lines[1:-1]}
                        if self.__cached_stats is not None:
                            _tree = E.machine_vector(
                                simple="0",
                                name=process_tools.get_fqdn()[0],
                                uuid=str(uuid_tools.get_uuid()),
                                time="{:d}".format(int(time.time())),
                            )
                            diff_time = max(1, abs(cur_time - self.__cached_time))
                            for _key in sorted(_dict.iterkeys()):
                                _value = abs(self.__cached_stats[_key] - _dict[_key]) / diff_time
                                _tree.append(
                                    E.mve(
                                        info="RRD {}".format(_key),
                                        unit="1/s",
                                        base="1",
                                        v_type="f",
                                        factor="1",
                                        value="{:.2f}".format(_value),
                                        name="rrd.operations.{}".format(_key),
                                    ),
                                )
                            self._process_data(etree.tostring(_tree))
                        self.__cached_stats, self.__cached_time = (_dict, cur_time)
                if _dict is None:
                    self.log("error parsing stats {}".format("; ".join(_lines)), logging_tools.LOG_LEVEL_ERROR)

    def _handle_disabled_hosts(self):
        disabled_hosts = device.objects.filter(Q(store_rrd_data=False))
        num_dis = disabled_hosts.count()
        self.log(
            "{} with no_store flag".format(
                logging_tools.get_plural("device", num_dis),
            )
        )
        uuids_to_disable = set([_dev.uuid for _dev in disabled_hosts])
        cur_disabled = set([key for key, value in self.__hosts.iteritems() if not value.store_to_disk])
        # to be used to disable hosts on first contact, FIXME
        self.__disabled_uuids = uuids_to_disable
        to_disable = uuids_to_disable - cur_disabled
        to_enable = cur_disabled - uuids_to_disable
        if to_disable or to_enable:
            self.log(
                "{} to disable, {} to enable".format(
                    logging_tools.get_plural("UUID", len(to_disable)),
                    logging_tools.get_plural("UUID", len(to_enable)),
                ),
                logging_tools.LOG_LEVEL_WARN
            )
            for _to_dis in to_disable:
                _host = self.__hosts[_to_dis]
                _host.store_to_disk = False
                self.log("disabled {}".format(unicode(_host)), logging_tools.LOG_LEVEL_WARN)
            for _to_en in to_enable:
                _host = self.__hosts[_to_en]
                _host.store_to_disk = True
                self.log("enabled {}".format(unicode(_host)), logging_tools.LOG_LEVEL_WARN)

    def _handle_xml(self, in_com):
        com_text = in_com["*command"]
        if com_text in ["ipmi_hosts", "snmp_hosts"]:
            j_type = com_text.split("_")[0]
            t_obj = {
                "ipmi": bg_job,
                "snmp": snmp_job
            }[j_type]
            # create ids
            _id_dict = {
                "{}:{}".format(_dev.attrib["uuid"], j_type): _dev for _dev in in_com.xpath(".//ns:device_list/ns:device")
            }
            _new_list, _remove_list, _same_list = t_obj.sync_jobs_with_id_list(_id_dict.keys())
            for new_id in _new_list:
                _dev = _id_dict[new_id]
                if j_type == "ipmi":
                    t_obj(
                        new_id,
                        ipmi_builder().get_comline(_dev),
                        ipmi_builder(),
                        device_name=_dev.get("full_name"),
                        uuid=_dev.get("uuid"),
                    )
                else:
                    t_obj(
                        new_id,
                        _dev.get("ip"),
                        _dev.get("snmp_scheme"),
                        int(_dev.get("snmp_version")),
                        _dev.get("snmp_read_community"),
                        device_name=_dev.get("full_name"),
                        uuid=_dev.get("uuid"),
                    )
            for same_id in _same_list:
                _dev = _id_dict[same_id]
                _job = t_obj.get_job(same_id)
                if j_type == "ipmi":
                    for attr_name, attr_value in [
                        ("comline", ipmi_builder().get_comline(_dev)),
                        ("device_name", _dev.get("full_name")),
                        ("uuid", _dev.get("uuid")),
                    ]:
                        _job.update_attribute(attr_name, attr_value)
                else:
                    for attr_name, attr_value in [
                        ("ip", _dev.get("ip")),
                        ("snmp_scheme", _dev.get("snmp_scheme")),
                        ("snmp_version", int(_dev.get("snmp_version"))),
                        ("snmp_read_community", _dev.get("snmp_read_community")),
                    ]:
                        _job.update_attribute(attr_name, attr_value)
        else:
            self.log("got server_command with unknown command {}".format(com_text), logging_tools.LOG_LEVEL_ERROR)

    def _check_background(self):
        bg_job.check_jobs()
        snmp_job.check_jobs()

    def _handle_hk_command(self, in_com, com_text):
        h_filter, k_filter = (
            in_com.get("host_filter", ".*"),
            in_com.get("key_filter", ".*")
        )
        self.log(
            "host_filter: {}, key_filter: {}".format(
                h_filter,
                k_filter,
            )
        )
        try:
            host_filter = re.compile(h_filter)
        except:
            host_filter = re.compile(".*")
            self.log(
                "error interpreting '{}' as host re: {}".format(
                    h_filter,
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        try:
            key_filter = re.compile(k_filter)
        except:
            key_filter = re.compile(".*")
            self.log(
                "error interpreting '{}' as key re: {}".format(
                    k_filter,
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        match_uuids = [
            _value[1] for _value in sorted(
                [
                    (self.__hosts[cur_uuid].name, cur_uuid) for cur_uuid in self.__hosts.keys() if host_filter.match(self.__hosts[cur_uuid].name)
                ]
            )
        ]
        if com_text == "host_list":
            result = E.host_list(entries="{:d}".format(len(match_uuids)))
            for cur_uuid in match_uuids:
                result.append(self.__hosts[cur_uuid].get_host_info())
            in_com["result"] = result
        elif com_text == "key_list":
            result = E.host_list(entries="{:d}".format(len(match_uuids)))
            for cur_uuid in match_uuids:
                result.append(self.__hosts[cur_uuid].get_key_list(key_filter))
            in_com["result"] = result
        in_com.set_result("got command {}".format(com_text))
