#
# this file is part of collectd
#
# Copyright (C) 2013-2017 Andreas Lang-Nevyjel init.at
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
""" collectd, server part """

import datetime
import os
import psutil
import re
import socket
import time

import pytz
import zmq
from django.conf import settings
from django.db.models import Q
from initat.tools import config_tools, configfile, logging_tools, process_tools, \
    server_command, threading_tools, uuid_tools, net_tools
from initat.tools.server_mixins import GetRouteToDevicesMixin, ICSWBasePool, \
    SendToRemoteServerMixin

from lxml import etree
from lxml.builder import E

from initat.cluster.backbone import db_tools
from initat.cluster.backbone.models import device, snmp_scheme, DeviceFlagsAndSettings
from initat.cluster.backbone.routing import get_server_uuid
from initat.cluster.backbone.server_enums import icswServiceEnum
from initat.cluster.backbone.var_cache import VarCache
from initat.icsw.service.instance import InstanceXML
from initat.snmp.process import SNMPProcessContainer
from .aggregate import aggregate_process
from .background import SNMPJob, BackgroundJob, IPMIBuilder
from .collectd_struct import CollectdHostInfo, ext_com, HostMatcher, FileCreator
from .config import global_config, IPC_SOCK_SNMP
from .dbsync import SyncProcess
from .resize import resize_process
from .rsync import RSyncMixin
from .sensor_threshold import ThresholdContainer

RRD_CACHED_PID = "/var/run/rrdcached/rrdcached.pid"


class server_process(GetRouteToDevicesMixin, ICSWBasePool, RSyncMixin, SendToRemoteServerMixin):
    def __init__(self):
        self.__verbose = global_config["VERBOSE"]
        long_host_name, _mach_name = process_tools.get_fqdn()
        threading_tools.process_pool.__init__(self, "main", zmq=True)
        self.CC.init(icswServiceEnum.collectd_server, global_config)
        self.CC.check_config()
        # override default
        self.STRS_SOCKET_NAME = "com_socket"
        global_config.add_config_entries(
            [
                ("MEMCACHE_PORT", configfile.int_c_var(self.CC.Instance.get_port_dict("memcached", command=True))),
            ]
        )
        # close connection (daemonizing)
        # db_tools.close_connection()
        self.CC.read_config_from_db(
            [
                (
                    "RRD_DISK_CACHE",
                    configfile.str_c_var(
                        "/opt/cluster/system/rrd",
                        help_string="persistent directory to use when /var/cache/rrd is a RAM-disk",
                        database=True
                    )
                ),
                ("RRD_DISK_CACHE_SYNC", configfile.int_c_var(3600, help_string="seconds between syncs from RAM to disk", database=True)),
                ("RRD_COVERAGE_1", configfile.str_c_var("1min for 2days", database=True)),
                ("RRD_COVERAGE_2", configfile.str_c_var("5min for 2 week", database=True)),
                ("RRD_COVERAGE_3", configfile.str_c_var("15mins for 1month", database=True)),
                ("RRD_COVERAGE_4", configfile.str_c_var("4 hours for 1 year", database=True)),
                ("RRD_COVERAGE_5", configfile.str_c_var("1day for 5 years", database=True)),
                (
                    "MODIFY_RRD_COVERAGE",
                    configfile.bool_c_var(False, help_string="alter RRD files on disk when coverage differs from configured one", database=True)
                ),
                ("ENABLE_SENSOR_THRESHOLDS", configfile.bool_c_var(True, help_string="globaly enable sensor thresholds [%(default)s]")),
                ("SERVER_FULL_NAME", configfile.str_c_var(long_host_name)),
                ("FROM_NAME", configfile.str_c_var("collectd", help_string="from address for event (threshold) mails [%(default)s]")),
                ("FROM_ADDRESS", configfile.str_c_var(long_host_name)),
                ("MEMCACHE_ADDRESS", configfile.str_c_var("127.0.0.1", help_string="memcache address")),
                ("SNMP_PROCS", configfile.int_c_var(4, help_string="number of SNMP processes to use [%(default)s]")),
                ("MAX_SNMP_JOBS", configfile.int_c_var(40, help_string="maximum number of jobs a SNMP process shall handle [%(default)s]")),
                # ("RECV_PORT", configfile.int_c_var(8002, help_string="receive port, do not change [%(default)s]")),
                ("MD_SERVER_HOST", configfile.str_c_var("127.0.0.1", help_string="md-config-server host [%(default)s]")),
                # ("MD_SERVER_PORT", configfile.int_c_var(8010, help_string="md-config-server port, do not change [%(default)s]")),
                ("MEMCACHE_HOST", configfile.str_c_var("127.0.0.1", help_string="host where memcache resides [%(default)s]")),
                ("MEMCACHE_TIMEOUT", configfile.int_c_var(2 * 60, help_string="timeout in seconds for values stored in memcache [%(default)s]")),
                ("RRD_CACHED_WRITETHREADS", configfile.int_c_var(4, help_string="number of write threads for RRD-cached")),
                ("AGGREGATE_STRUCT_UPDATE", configfile.int_c_var(600, help_string="timer for aggregate struct updates")),
            ]
        )
        if global_config["RRD_CACHED_SOCKET"] == "/var/run/rrdcached.sock":
            global_config["RRD_CACHED_SOCKET"] = os.path.join(global_config["RRD_CACHED_DIR"], "rrdcached.sock")
        # re-insert config
        self.CC.re_insert_config()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("hup_error", self._hup_error)
        self.CC.log_config()
        self._init_network_sockets()
        self.register_func("disable_rrd_cached", self.disable_rrd_cached)
        self.register_func("enable_rrd_cached", self.enable_rrd_cached)
        self.sync_from_disk_to_ram()
        self.hm = HostMatcher(self.log)
        self.fc = FileCreator(self.log)
        self.__last_sent = {}
        self.__snmp_running = True
        self._init_perfdata()
        self._init_vars()
        self._init_hosts()
        self._init_rrd_cached()
        self.__ipmi_list = []
        BackgroundJob.setup(self)
        SNMPJob.setup(self)
        self.tc = ThresholdContainer(self)
        self.register_timer(self._check_database, 300, instant=True)
        self.register_timer(self._check_background, 2, instant=True)
        self.__cached_stats, self.__cached_time = (None, time.time())
        self.register_timer(self._check_cached_stats, 30, first_timeout=5)
        db_tools.close_connection()
        self.log("starting processes")
        self._init_snmp()
        # stop resize-process at the end
        self.add_process(resize_process("resize", priority=20), start=True)
        self.add_process(aggregate_process("aggregate"), start=True)
        self.add_process(SyncProcess("dbsync"), start=True)
        # self.init_notify_framework(global_config)
        self.__hm_port = InstanceXML(quiet=True).get_port_dict("host-monitoring", command=True)

    def _init_perfdata(self):
        from initat.collectd.collectd_types import IMPORT_ERRORS, ALL_PERFDATA
        if IMPORT_ERRORS:
            self.log(
                "errors while importing perfdata structures: {:d}".format(
                    len(IMPORT_ERRORS)
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            for _num, _line in enumerate(IMPORT_ERRORS):
                self.log("    {}".format(_line), logging_tools.LOG_LEVEL_ERROR)
        self.log("valid perfdata structures: {:d}".format(len(list(ALL_PERFDATA.keys()))))
        for _key in sorted(ALL_PERFDATA.keys()):
            self.log(" - {}: '{}'".format(_key, ALL_PERFDATA[_key][1].PD_RE.pattern))
        self.__pd_re_list = list(ALL_PERFDATA.values())

    def _init_vars(self):
        self.__start_time = time.time()
        self.__trees_read, self.__pds_read = (0, 0)
        self.__total_size_trees, self.__total_size_pds = (0, 0)
        self.__distinct_hosts_mv = set()
        self.__distinct_hosts_pd = set()

    def _init_hosts(self):
        # init host and perfdata structs
        CollectdHostInfo.setup(self.fc)
        self.__hosts = {}

    def _int_error(self, err_cause):
        if not self.__snmp_running:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("stopping SNMP-container")
            self.spc.stop()
            self.__snmp_running = False
            self.__shutdown_msg_time = None

    def _hup_error(self, err_cause):
        self.log("got sighup", logging_tools.LOG_LEVEL_WARN)
        self._check_database()

    def process_start(self, src_process, src_pid):
        self.CC.process_added(src_process, src_pid)

    def _init_network_sockets(self):
        self.bind_id = get_server_uuid("collectd")
        client = process_tools.get_socket(self.zmq_context, "ROUTER", identity=self.bind_id, immediate=True)
        bind_str = "tcp://*:{:d}".format(global_config["COMMAND_PORT"])
        try:
            client.bind(bind_str)
        except zmq.ZMQError:
            self.log(
                "error binding to {:d}: {}".format(
                    global_config["COMMAND_PORT"],
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
            # receiver socket
            self.receiver = self.zmq_context.socket(zmq.PULL)  # @UndefinedVariable
            listener_url = "tcp://*:{:d}".format(global_config["RECEIVE_PORT"])
            self.receiver.bind(listener_url)
            self.register_poller(self.receiver, zmq.POLLIN, self._recv_data)  # @UndefinedVariable

    def _init_rrd_cached(self):
        self.log("init rrd cached process")
        # FIXME, improve
        _dir = os.path.realpath(global_config["RRD_DIR"])
        if _dir != global_config["RRD_DIR"]:
            self.log("RRD_DIR '{}' resolved to '{}'".format(global_config["RRD_DIR"], _dir))
        _comline = "/opt/cluster/bin/rrdcached -m0777 -l {} -s idg -w 60 -t {:d} -F -b {} -p {} > /tmp/.rrdcached_output 2>&1".format(
            global_config["RRD_CACHED_SOCKET"],
            global_config["RRD_CACHED_WRITETHREADS"],
            _dir,
            RRD_CACHED_PID,
        )
        self.log("comline is {}".format(_comline))
        # rrd_com is only used for starting
        self.__rrd_com = ext_com(self.log, _comline, name="rrdcached", detach=True)
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
            try:
                _pid = int(open(RRD_CACHED_PID, "r").read().strip())
            except:
                self.log(
                    "error reading pid of rrdcached: {}".format(
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                try:
                    os.kill(_pid, 15)
                except:
                    self.log("cannot kill pid {:d}".format(_pid))
                else:
                    self.log("killed rrdcached at {:d}".format(_pid))
            self.__rrd_com.terminate()
            _result = self.__rrd_com.finished()
            if _result is not None:
                _stdout, _stderr = self.__rrd_com.communicate()
                self.log("stopped rrd_cached process with result {:d}".format(_result))
                for _name, _stream in [("stdout", _stdout), ("stderr", _stderr)]:
                    if _stream:
                        for _line in _stream.split("\n"):
                            self.log("{}: {}".format(_name, _line))
            else:
                self.log("stopped rrd_cached process")
        elif not self.__rrdcached_running and _target_state:
            _log()
            # check for stale pid file
            if os.path.exists(RRD_CACHED_PID):
                self.log("removing (stale) PID {}".format(RRD_CACHED_PID))
                os.unlink(RRD_CACHED_PID)
            self.log("starting rrd_cached process")
            self.__rrd_com.run()
            _result = self.__rrd_com.finished()
            self.__rrdcached_running = True

    def _check_for_rrdcached_socket(self):
        if not self.__rrdcached_socket and self.__rrdcached_running:
            self._open_rrdcached_socket()

    def _open_rrdcached_socket(self):
        self._close_rrdcached_socket()
        # check if rrdcached is running
        if self.__rrdcached_running:
            try:
                _pid = open(RRD_CACHED_PID, "r").read().strip()
                _proc = psutil.Process(pid=int(_pid))
            except:
                self.log(
                    "RRDCached-Process is not running ... ?: {}".format(
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
                self.__rrdcached_running = False
            else:
                T_NAME = "rrdcached"
                if _proc.name() != T_NAME:
                    self.log(
                        "Process {:d} has the wrong name ({} != {}), trying to restart".format(
                            _pid,
                            T_NAME,
                            _proc.name(),
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                    self.__rrdcached_running = False
        if not self.__rrdcached_running:
            self._check_rrd_cached_state()
        try:
            self.__rrdcached_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.__rrdcached_socket.connect(global_config["RRD_CACHED_SOCKET"])
        except:
            self.log("error opening rrdcached socket: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            self.__rrdcached_socket = None
        else:
            self.log("connected to rrdcached socket {}".format(global_config["RRD_CACHED_SOCKET"]))
            self.__rrdcached_socket.settimeout(10.0)

    def _close_rrdcached_socket(self):
        if self.__rrdcached_socket:
            try:
                self.__rrdcached_socket.close()
            except:
                self.log("error closing rrdcached socket: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            else:
                self.log("closed rrdcached socket")
            self.__rrdcached_socket = None

    def loop_post(self):
        self.CC.close()

    def loop_end(self):
        self.stop_rrd_cached()
        self.sync_from_ram_to_disk()
        self._log_stats()
        self.com_socket.close()
        self.receiver.close()
        self.spc.close()

    def _check_database(self):
        if self._still_active("check database"):
            self._handle_disabled_hosts()
            _router = config_tools.RouterObject(self.log)
            for _send_com in [self._get_ipmi_hosts(_router), self._get_snmp_hosts(_router)]:
                self._handle_xml(_send_com)

    def _check_reachability(self, devs, var_cache, _router, _type):
        _srv_type = icswServiceEnum.collectd_server
        self.log(
            "Start reachability check for {} (srv {}, type {})".format(
                logging_tools.get_plural("device", len(devs)),
                _srv_type.name,
                _type,
            )
        )
        s_time = time.time()
        _sc = config_tools.server_check(service_type_enum=_srv_type)
        res_dict = _sc.get_route_to_other_devices(_router, devs, allow_route_to_other_networks=True)
        _reachable, _unreachable = ([], [])
        for dev in devs:
            if res_dict[dev.idx]:
                _ip = res_dict[dev.idx][0][3][1][0]
                _reachable.append((dev, _ip, var_cache.get_vars(dev)[0]))
            else:
                _unreachable.append(dev)
        e_time = time.time()
        self.log(
            "Reachability check for {} (srv {}, type {}) took {}".format(
                logging_tools.get_plural("device", len(devs)),
                _srv_type.name,
                _type,
                logging_tools.get_diff_time_str(e_time - s_time),
            )
        )
        if _unreachable:
            self.log(
                "{}: {}".format(
                    logging_tools.get_plural("unreachable {} device".format(_type), len(_unreachable)),
                    logging_tools.compress_list([str(_dev) for _dev in _unreachable])
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        if _reachable:
            _reach = sorted(list(set([str(_dev) for _dev, _ip, _vars in _reachable])))
            self.log(
                "{}: {}".format(
                    logging_tools.get_plural("reachable {} device".format(_type), len(_reach)),
                    logging_tools.reduce_list(_reach, top_join_str=", ")
                ),
            )
        return _reachable

    def _get_snmp_hosts(self, _router):
        def _cast_snmp_version(_vers):
            if isinstance(_vers, int):
                return _vers
            elif _vers.isdigit():
                return int(_vers)
            else:
                return {"2c": 2}.get(_vers, 1)
        # var cache
        _vc = VarCache(
            def_dict={
                "SNMP_VERSION": 1,
                "SNMP_READ_COMMUNITY": "public",
                "SNMP_READ_TIMEOUT": 10,
            }
        )
        snmp_hosts = device.all_enabled.exclude(
            Q(snmp_schemes=None)
        ).filter(
            Q(enable_perfdata=True) &
            Q(snmp_schemes__collect=True)
        ).prefetch_related(
            "snmp_schemes__snmp_scheme_vendor"
        )
        _reachable = self._check_reachability(snmp_hosts, _vc, _router, "SNMP")
        snmp_com = server_command.srv_command(command="snmp_hosts")
        _bld = snmp_com.builder()
        snmp_com["devices"] = _bld.device_list(
            *[
                _bld.device(
                    _bld.schemes(
                        *[
                            _bld.scheme(
                                _scheme.full_name_version,
                                pk="{:d}".format(_scheme.pk)
                            ) for _scheme in cur_dev.snmp_schemes.all() if _scheme.collect
                        ]
                    ),
                    pk="{:d}".format(cur_dev.pk),
                    short_name="{}".format(cur_dev.name),
                    full_name="{}".format(cur_dev.full_name),
                    uuid="{}".format(cur_dev.uuid),
                    ip="{}".format(_ip),
                    snmp_version="{:d}".format(_cast_snmp_version(_vars["SNMP_VERSION"])),
                    snmp_read_community=_vars["SNMP_READ_COMMUNITY"],
                    snmp_read_timeout="{:d}".format(_vars["SNMP_READ_TIMEOUT"]),
                ) for cur_dev, _ip, _vars in _reachable
            ]
        )
        return snmp_com

    def _get_ipmi_hosts(self, _router):
        # var cache
        _vc = VarCache(
            def_dict={"IPMI_USERNAME": "notset", "IPMI_PASSWORD": "notset", "IPMI_INTERFACE": ""}
        )
        ipmi_hosts = device.all_enabled.filter(Q(enable_perfdata=True) & Q(com_capability_list__matchcode="ipmi"))
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
        if self._still_active("received XML data"):
            if len(in_data) == 2:
                in_uuid, in_xml = in_data
                try:
                    in_com = server_command.srv_command(source=in_xml)
                except:
                    self.log("error decoding command {}: {}".format(in_xml, process_tools.get_except_info), logging_tools.LOG_LEVEL_ERROR)
                else:
                    _send_result = True
                    com_text = in_com["command"].text
                    self.log("got command {} from {}".format(com_text, in_uuid))
                    if com_text in ["host_list", "key_list"]:
                        self._handle_hk_command(in_com, com_text)
                    elif com_text in ["sync_sensor_threshold"]:
                        self._sync_sensor_threshold(in_com)
                    elif com_text == "trigger_sensor_threshold":
                        self._trigger_sensor_threshold(in_com)
                    elif com_text == "add_rrd_target":
                        self._add_rrd_target(in_com)
                    # background notify glue
                    # elif com_text in ["wf_notify"]:
                    #    _send_result = False
                    #    self.bg_check_notify()
                    # elif self.bg_notify_waiting_for_job(in_com):
                    #    self.bg_notify_handle_result(in_com)
                    #    _send_result = False
                    else:
                        self.log("unknown command {}".format(com_text), logging_tools.LOG_LEVEL_ERROR)
                        in_com.set_result(
                            "unknown command {}".format(com_text),
                            server_command.SRV_REPLY_STATE_ERROR
                        )
                    if _send_result:
                        try:
                            zmq_sock.send_unicode(in_uuid, zmq.SNDMORE)  # @UndefinedVariable
                            zmq_sock.send_unicode(str(in_com))
                        except:
                            self.log(
                                "error sending to {}: {}".format(
                                    in_uuid,
                                    process_tools.get_except_info()
                                ),
                                logging_tools.LOG_LEVEL_ERROR
                            )
            else:
                self.log("short data received", logging_tools.LOG_LEVEL_ERROR)

    def _still_active(self, msg):
        # return true if process is not shuting down
        if self.__snmp_running:
            return True
        else:
            self._show_shutdown_msg(msg)
            return False

    def _show_shutdown_msg(self, msg):
        cur_time = int(time.time())
        if cur_time != self.__shutdown_msg_time:
            self.__shutdown_msg_time = cur_time
            self.log(
                "shutting down, ignore {}".format(
                    msg,
                ),
                logging_tools.LOG_LEVEL_WARN
            )

    def _init_snmp(self):
        self.spc = SNMPProcessContainer(
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
                "process_pre_start": self._snmp_process_pre_start,
                "process_start": self._snmp_process_start,
                "process_exit": self._snmp_process_exit,
                "all_stopped": self._snmp_all_stopped,
                "finished": self._snmp_finished,
            }
        )
        _snmp_sock = self.spc.create_ipc_socket(self.zmq_context, IPC_SOCK_SNMP)
        self.register_poller(_snmp_sock, zmq.POLLIN, self.spc.handle_with_socket)
        self.spc.check()

    def _snmp_process_pre_start(self, snmp_proc):
        from initat.cluster.backbone import db_tools
        db_tools.close_connection()

    def _snmp_process_start(self, **kwargs):
        self.CC.process_added(kwargs["process_name"], kwargs["pid"])

    def _snmp_process_exit(self, **kwargs):
        self.CC.process_removed(kwargs["pid"])

    def process_exit(self, p_name, pid):
        self.CC.process_removed(pid)

    def _snmp_all_stopped(self):
        self.log("all SNMP-processes stopped, setting exit_requested flag")
        self["exit_requested"] = True

    def _snmp_finished(self, data):
        SNMPJob.feed_result(data["args"])

    def _log_stats(self):
        self.__end_time = time.time()
        diff_time = max(1, abs(self.__end_time - self.__start_time))
        bt_rate = self.__trees_read / diff_time
        st_rate = self.__total_size_trees / diff_time
        bp_rate = self.__pds_read / diff_time
        sp_rate = self.__total_size_pds / diff_time
        self.log(
            "read {} ({}) from {} (rate [{:.2f}, {}] / sec), {} ({}) from {} (rate [{:.2f}, {}] / sec) in {}".format(
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
            )
        )
        self._init_vars()

    def _create_host_info(self, _dev):
        if _dev.uuid not in self.__hosts:
            self.__hosts[_dev.uuid] = CollectdHostInfo(self.log, _dev)
        return self.__hosts[_dev.uuid]

    def _feed_host_info(self, _dev, _xml):
        _host_info = self._create_host_info(_dev)
        if _host_info.update(_xml, self.fc):
            # something changed
            # new_com = server_command.srv_command(command="mv_info")
            # new_com["vector"] = _xml
            self.send_to_process("dbsync", "mvector", etree.tostring(_xml))
        return _host_info

    def _feed_host_info_ov(self, _dev, _xml):
        # update only values
        self.__hosts[_dev.uuid].update_ov(_xml)
        return self.__hosts[_dev.uuid]

    def _recv_data(self, in_sock):
        in_data = in_sock.recv_unicode()
        if self._still_active("received data"):
            # adopt tree format for faster handling in collectd loop
            try:
                _xml = etree.fromstring(in_data)
            except etree.XMLSyntaxError:
                self.log(
                    "cannot parse tree: {}, first 48 bytes: '{}'".format(
                        process_tools.get_except_info(),
                        in_data[:48],
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                self.process_data_xml(_xml, len(in_data))
        if abs(time.time() - self.__start_time) > 300:
            # periodic log stats
            self._log_stats()

    def process_data_xml(self, _xml, data_len):
        xml_tag = _xml.tag.split("}")[-1]
        handle_name = "_handle_{}".format(xml_tag)
        if hasattr(self, handle_name):
            # loop
            for p_data in getattr(self, handle_name)(_xml, data_len):
                _com = p_data[0]
                if _com == "mvector":
                    self._handle_mvector_tree(p_data[1:])
                elif _com == "pdata":
                    # always take the first value of data
                    self._handle_perfdata(p_data[1])
                else:
                    self.log("unknown data: {}".format(_com), logging_tools.LOG_LEVEL_ERROR)
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
                _xml.attrib["uuid"] = _dev.uuid
                if not simple:
                    # add rra_idx entries for mvls
                    for _mvl in _xml.findall(".//mvl"):
                        for _num, _entry in enumerate(_mvl.findall(".//value")):
                            # set rra_idx and name to ease mapping for sensor thresholds
                            _entry.attrib["rra_idx"] = "{:d}".format(_num)
                            _entry.attrib["name"] = _entry.get("key")
                # create values
                if simple:
                    # only values
                    _host_info = self._feed_host_info_ov(_dev, _xml)
                else:
                    _host_info = self._feed_host_info(_dev, _xml)
                values = _host_info.get_values(_xml, simple)
                # store values in host_info (and memcached)
                # host_uuid is uuid or name
                if not _host_info.store_to_disk:
                    # writing to disk not allowed
                    raise StopIteration
                # print "+", values
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
                            self.send_to_process("dbsync", "perfdata", etree.tostring(pd_vec[2]))
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

    def get_time(self, h_tuple, cur_time):
        cur_time = int(cur_time)
        # pprint.pprint(self.__last_sent)
        if h_tuple in self.__last_sent:
            if cur_time <= self.__last_sent[h_tuple]:
                diff_time = self.__last_sent[h_tuple] + 1 - cur_time
                cur_time += diff_time
                self.log(
                    "correcting time for {} (+{:d}s to {:d})".format(
                        str(h_tuple),
                        diff_time,
                        int(cur_time)
                    )
                )
        self.__last_sent[h_tuple] = cur_time
        return self.__last_sent[h_tuple]

    def _handle_perfdata(self, data):
        pd_tuple, _host_info, _send_xml, time_recv, rsi, v_list, key_list = data
        s_time = int(time_recv)
        if self.tc.device_has_thresholds(_host_info.device.idx):
            for name, value in zip(key_list, v_list):
                self.tc.feed(_host_info.device.idx, name, value, False)
        if self.__rrdcached_socket:
            _tf = _host_info.target_file(pd_tuple, step=5 * 60, v_type=pd_tuple[0])
            if _tf:
                cache_lines = [
                    "UPDATE {} {:d}:{}".format(
                        _tf,
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
        if self.tc.device_has_thresholds(_host_info.device.idx):
            for name, value, mv_flag in values:
                # name can be none for values with transform problems
                if name:
                    self.tc.feed(_host_info.device.idx, name, value, mv_flag)
        if self.__rrdcached_socket:
            for name, value, mv_flag in values:
                # name can be none for values with transform problems
                if name:
                    try:
                        _tf = _host_info.target_file(name)
                    except ValueError:
                        self.log(
                            "cannot get target file name for {}: {}".format(
                                name,
                                process_tools.get_except_info()
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
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
        _com_error = False
        # end rrd-cached communication
        try:
            _num_sent = self.__rrdcached_socket.send(b"BATCH\n")
        except BrokenPipeError:
            self.log(
                "error communicating with rrd-cached: {}".format(
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            _com_error = True
        else:
            for _line in cache_lines:
                _num_sent += self.__rrdcached_socket.send(("{}\n".format(_line)).encode("utf-8"))
            _num_sent += self.__rrdcached_socket.send(b".\n")
            _skip_lines = 0
            _read = True
            s_time = time.time()
            _content = ""
            _errcount = 0
            while _read:
                if settings.DEBUG:
                    self.log("send {:d} bytes, reading from rrdcached socket...".format(_num_sent))
                try:
                    _content = "{}{}".format(_content, self.__rrdcached_socket.recv(4096).decode("utf-8"))
                except IOError:
                    _com_error = True
                    self.log(
                        "error communicating with rrdcached ({}), forcing reopening".format(
                            process_tools.get_except_info()
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                    _read = False
                else:
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
                                    "error: {} for {}".format(
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
        if _com_error:
            self._open_rrdcached_socket()

    def _check_cached_stats(self):
        if self.__rrdcached_socket:
            try:
                self.__rrdcached_socket.send(b"STATS\n")
                _lines = self.__rrdcached_socket.recv(16384).decode("utf-8").split("\n")
            except IOError:
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
                            for _key in sorted(_dict.keys()):
                                if _key not in self.__cached_stats:
                                    self.log("key {} missing in previous run, ignoring ...".format(_key), logging_tools.LOG_LEVEL_WARN)
                                else:
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
                            self.process_data_xml(_tree, len(etree.tostring(_tree)))  # @UndefinedVariable
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
        cur_disabled = set([key for key, value in self.__hosts.items() if not value.store_to_disk])
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
                if _to_dis in self.__hosts:
                    _host = self.__hosts[_to_dis]
                    _host.store_to_disk = False
                    self.log("disabled {}".format(str(_host)), logging_tools.LOG_LEVEL_WARN)
            for _to_en in to_enable:
                if _to_en in self.__hosts:
                    _host = self.__hosts[_to_en]
                    _host.store_to_disk = True
                    self.log("enabled {}".format(str(_host)), logging_tools.LOG_LEVEL_WARN)

    def _handle_xml(self, in_com):
        com_text = in_com["*command"]
        if com_text in ["ipmi_hosts", "snmp_hosts"]:
            j_type = com_text.split("_")[0]
            t_obj = {
                "ipmi": BackgroundJob,
                "snmp": SNMPJob
            }[j_type]
            # create ids
            _id_dict = {
                "{}:{}".format(_dev.attrib["uuid"], j_type): _dev for _dev in in_com.xpath(".//ns:device_list/ns:device")
            }
            _new_list, _remove_list, _same_list = t_obj.sync_jobs_with_id_list(list(_id_dict.keys()))
            for new_id in _new_list:
                _dev = _id_dict[new_id]
                _dev_obj = device.objects.get(Q(uuid=_dev.get("uuid")))
                if j_type == "ipmi":
                    BackgroundJob(
                        new_id,
                        _dev_obj,
                        IPMIBuilder().get_comline(_dev),
                        IPMIBuilder(),
                        device_name=_dev.get("full_name"),
                        uuid=_dev.get("uuid"),
                    )
                else:
                    _schemes = snmp_scheme.objects.filter(Q(pk__in=in_com.xpath(".//ns:schemes/ns:scheme/@pk", start_el=_dev)))
                    SNMPJob(
                        new_id,
                        _dev_obj,
                        _dev.get("ip"),
                        _schemes,
                        int(_dev.get("snmp_version")),
                        _dev.get("snmp_read_community"),
                        device_name=_dev.get("full_name"),
                        uuid=_dev.get("uuid"),
                        snmp_read_timeout=int(_dev.get("snmp_read_timeout", "10")),
                    )
            for same_id in _same_list:
                # update attributes for jobs already present
                _dev = _id_dict[same_id]
                _job = t_obj.get_job(same_id)
                if j_type == "ipmi":
                    for attr_name, attr_value in [
                        ("comline", IPMIBuilder().get_comline(_dev)),
                        ("device_name", _dev.get("full_name")),
                        ("uuid", _dev.get("uuid")),
                    ]:
                        _job.update_attribute(attr_name, attr_value)
                else:
                    _schemes = snmp_scheme.objects.filter(Q(pk__in=in_com.xpath(".//ns:schemes/ns:scheme/@pk", start_el=_dev)))
                    for attr_name, attr_value in [
                        ("ip", _dev.get("ip")),
                        ("snmp_schemes", _schemes),
                        ("snmp_version", int(_dev.get("snmp_version"))),
                        ("snmp_read_community", _dev.get("snmp_read_community")),
                        ("snmp_read_timeout", int(_dev.get("snmp_read_timeout", "10"))),
                    ]:
                        _job.update_attribute(attr_name, attr_value)
        else:
            self.log(
                "got server_command with unknown command {}".format(
                    com_text,
                ),
                logging_tools.LOG_LEVEL_ERROR
            )

    def _check_background(self):
        BackgroundJob.check_jobs(start=self.__snmp_running)
        SNMPJob.check_jobs(start=self.__snmp_running)

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
        except re.error:
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
        except re.error:
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
                    (self.__hosts[cur_uuid].name, cur_uuid) for cur_uuid in list(self.__hosts.keys()) if host_filter.match(self.__hosts[cur_uuid].name)
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

    def _sync_sensor_threshold(self, in_com):
        in_com.set_result("ok syncing thresholds")
        self.tc.sync()

    def _trigger_sensor_threshold(self, in_com):
        in_com.set_result("triggered sensor_threshold")
        self.tc.trigger(in_com)

    def _add_rrd_target(self, srv_com):
        device_pk = int(srv_com["device_pk"].text)

        target_dev = device.objects.get(idx=device_pk)
        collectd_dev = device.objects.get(pk=global_config["SERVER_IDX"])

        self.get_route_to_devices([collectd_dev, target_dev])

        if target_dev.target_ip and collectd_dev.target_ip:
            device_flags = DeviceFlagsAndSettings.objects.filter(device=target_dev)

            new_con = net_tools.ZMQConnection(
                "graph_setup_{:d}".format(target_dev.idx),
            )

            conn_str = "tcp://{}:{:d}".format(target_dev.target_ip, self.__hm_port)

            if not device_flags:
                obj = DeviceFlagsAndSettings.objects.create(
                    device=target_dev,
                    graph_enslavement_start=datetime.datetime.now(tz=pytz.utc)
                )
                obj.save()
            else:
                device_flags[0].graph_enslavement_start = datetime.datetime.now(tz=pytz.utc)
                device_flags[0].save()

            new_srv_com = server_command.srv_command(command="graph_setup", send_name=target_dev.full_name, target_ip=collectd_dev.target_ip)
            new_con.add_connection(conn_str, new_srv_com)
            result = new_con.loop()[0]

            if result:
                srv_com.set_result(1)
            else:
                srv_com.set_result(0)
        else:
            srv_com.set_result(0)

        return srv_com
