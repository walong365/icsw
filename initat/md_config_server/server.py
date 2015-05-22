# Copyright (C) 2013-2015 Andreas Lang-Nevyjel, init.at
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
import json

import os
from initat.tools.server_mixins import RemoteCallMessageType, RemoteCall

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models import mon_notification, config_str, config_int, \
    mon_check_command_special, mon_check_command
from initat.cluster.backbone.models.functions import get_related_models
from initat.cluster.backbone.routing import get_server_uuid
from initat.host_monitoring.hm_classes import mvect_entry
from initat.md_config_server import constants
from initat.md_config_server.build import build_process
from initat.md_config_server.config import global_config
from initat.md_config_server.mixins import version_check_mixin
from initat.md_config_server.status import status_process, live_socket
from initat.md_config_server.syncer import syncer_process
from initat.md_config_server.dynconfig import dynconfig_process
from initat.md_config_server.kpi import KpiProcess, KpiData
from initat.md_config_server.icinga_log_reader.log_reader import icinga_log_reader
from initat.tools import cluster_location
import codecs
import inspect
from initat.tools import configfile
from initat.tools import logging_tools
from initat.tools import process_tools
from initat.tools import server_command
from initat.tools import threading_tools
from initat.tools import server_mixins
import time
import zmq


@server_mixins.RemoteCallProcess
class server_process(threading_tools.process_pool, version_check_mixin, server_mixins.RemoteCallMixin,
                     server_mixins.OperationalErrorMixin, server_mixins.NetworkBindMixin):
    def __init__(self):
        self.__log_cache, self.__log_template = ([], None)
        self.__pid_name = global_config["PID_NAME"]
        self.__verbose = global_config["VERBOSE"]
        self.__enable_livestatus = global_config["ENABLE_LIVESTATUS"]
        threading_tools.process_pool.__init__(self, "main", zmq=True, zmq_debug=global_config["ZMQ_DEBUG"])
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self._init_msi_block()
        connection.close()
        # re-insert config
        self._re_insert_config()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("hup_error", self._hup_error)
        self._check_notification()
        self._check_special_commands()
        # from mixins
        self._check_md_version()
        self._check_relay_version()
        self._log_config()
        self._init_network_sockets()

        if "MD_TYPE" in global_config:
            self.__external_cmd_file = None
            self.add_process(status_process("status"), start=True)
            self.add_process(syncer_process("syncer"), start=True)
            self.add_process(dynconfig_process("dynconfig"), start=True)
            self.add_process(icinga_log_reader("icinga_log_reader"), start=True)
            self.add_process(KpiProcess("KpiProcess"), start=True)
            # wait for the processes to start
            time.sleep(0.5)
            self.register_timer(self._check_for_redistribute, 60 if global_config["DEBUG"] else 300)
            self.register_timer(self._update, 30, instant=True)
        else:
            self._int_error("no MD found")

    def _check_for_redistribute(self):
        self.send_to_process("syncer", "check_for_redistribute")

    def _update(self):
        res_dict = {}
        if self.__enable_livestatus:
            if "MD_TYPE" in global_config:
                sock_name = os.path.join("/opt", global_config["MD_TYPE"], "var", "live")
                cur_s = live_socket(sock_name)
                try:
                    result = cur_s.hosts.columns("name", "state").call()
                except:
                    self.log("cannot query socket {}: {}".format(sock_name, process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_CRITICAL)
                else:
                    q_list = [int(value["state"]) for value in result]
                    res_dict = dict([(s_name, q_list.count(value)) for s_name, value in [
                        ("unknown", constants.NAG_HOST_UNKNOWN),
                        ("up", constants.NAG_HOST_UP),
                        ("down", constants.NAG_HOST_DOWN)]])
                    res_dict["tot"] = sum(res_dict.values())
                # cur_s.peer.close()
                del cur_s
            else:
                self.log("no MD_TYPE set, skipping livecheck", logging_tools.LOG_LEVEL_WARN)
        if res_dict:
            self.log("{} status is: {:d} up, {:d} down, {:d} unknown ({:d} total)".format(
                global_config["MD_TYPE"],
                res_dict["up"],
                res_dict["down"],
                res_dict["unknown"],
                res_dict["tot"]))
            drop_com = server_command.srv_command(command="set_vector")
            add_obj = drop_com.builder("values")
            mv_list = [
                mvect_entry("mon.devices.up", info="Devices up", default=0),
                mvect_entry("mon.devices.down", info="Devices down", default=0),
                mvect_entry("mon.devices.total", info="Devices total", default=0),
                mvect_entry("mon.devices.unknown", info="Devices unknown", default=0),
            ]
            cur_time = time.time()
            for mv_entry, key in zip(mv_list, ["up", "down", "tot", "unknown"]):
                mv_entry.update(res_dict[key])
                mv_entry.valid_until = cur_time + 120
                add_obj.append(mv_entry.build_xml(drop_com.builder))
            drop_com["vector_loadsensor"] = add_obj
            drop_com["vector_loadsensor"].attrib["type"] = "vector"
            send_str = unicode(drop_com)
            self.log("sending {:d} bytes to vector_socket".format(len(send_str)))
            self.vector_socket.send_unicode(send_str)
        else:
            self.log("empty result dict for _update()", logging_tools.LOG_LEVEL_WARN)

    def _log_config(self):
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [{:d}] {}".format(log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found {:d} valid global config-lines:".format(len(conf_info)))
        for conf in conf_info:
            self.log("Config : {}".format(conf))

    def _re_insert_config(self):
        cluster_location.write_config("monitor_server", global_config)

    def _check_special_commands(self):
        from initat.md_config_server.special_commands import SPECIAL_DICT
        pks_found = set()
        mccs_dict = {}
        for _name, _entry in SPECIAL_DICT.iteritems():
            _inst = _entry(self.log)
            if "special_{}".format(_inst.Meta.name) != _name:
                self.log("special {} has illegal name {}".format(_name, _inst.Meta.name), logging_tools.LOG_LEVEL_CRITICAL)
            else:
                self.log("found special {}".format(_name))
                cur_mccs = self._check_mccs(_inst.Meta)
                mccs_dict[cur_mccs.name] = cur_mccs
                pks_found.add(cur_mccs.pk)
                if cur_mccs.meta:
                    for _sub_com in _inst.get_commands():
                        sub_mccs = self._check_mccs(_sub_com.Meta, parent=cur_mccs)
                        mccs_dict[sub_mccs.name] = sub_mccs
                        pks_found.add(sub_mccs.pk)
        # delete stale
        del_mccs = mon_check_command_special.objects.exclude(pk__in=pks_found)
        if del_mccs:
            for _del_mcc in del_mccs:
                self.log(
                    "trying to removing stale {}...".format(
                        unicode(_del_mcc),
                    )
                )
                _refs = get_related_models(_del_mcc)
                if _refs:
                    self.log("  unable to remove because referenced {}".format(logging_tools.get_plural("time", _refs)), logging_tools.LOG_LEVEL_ERROR)
                else:
                    _del_mcc.delete()
                    self.log("  ...done")
        # rewrite
        for to_rewrite in mon_check_command.objects.filter(Q(name__startswith="@")):
            self.log("rewriting {} to new format... ".format(unicode(to_rewrite)))
            _key = to_rewrite.name.split("@")[1].lower()
            if _key in mccs_dict:
                to_rewrite.name = to_rewrite.name.split("@")[2]
                to_rewrite.mon_check_command_special = mccs_dict[_key]
                to_rewrite.save()
            else:
                self.log("key {} not found in dict".format(_key), logging_tools.LOG_LEVEL_ERROR)

    def _check_mccs(self, mdef, parent=None):
        try:
            cur_mccs = mon_check_command_special.objects.get(Q(name=mdef.name))
        except mon_check_command_special.DoesNotExist:
            cur_mccs = mon_check_command_special(name=mdef.name)
        # also used in snmp/struct.py and generic_net_handler.py
        for attr_name in ["command_line", "info", "description", "is_active", "meta", "identifier"]:
            setattr(cur_mccs, attr_name, getattr(mdef, attr_name))
        cur_mccs.parent = parent
        cur_mccs.save()
        return cur_mccs

    def _check_notification(self):
        cur_not = mon_notification.objects.all().count()
        if cur_not:
            self.log("{} defined, skipping check".format(logging_tools.get_plural("notification", cur_not)))
        else:
            if "NOTIFY_BY_EMAIL_LINE01" in global_config:
                self.log("rewriting notifications from global_config")
                str_dict = {
                    "sms": {
                        "host": ("", [global_config["HOST_NOTIFY_BY_SMS_LINE01"]]),
                        "service": ("", [global_config["NOTIFY_BY_SMS_LINE01"]]),
                        },
                    "mail": {
                        "host": (
                            global_config["HOST_NOTIFY_BY_EMAIL_SUBJECT"],
                            [global_config["HOST_NOTIFY_BY_EMAIL_LINE{:02d}".format(idx)] for idx in xrange(1, 16)],
                            ),
                        "service": (
                            global_config["NOTIFY_BY_EMAIL_SUBJECT"],
                            [global_config["NOTIFY_BY_EMAIL_LINE{:02d}".format(idx)] for idx in xrange(1, 16)],
                        ),
                    }
                }
                for key in global_config.keys():
                    if key.count("NOTIFY_BY") and (key.count("LINE") or key.count("SUBJECT")):
                        src = global_config.get_source(key)
                        if src.count("::"):
                            t_type, pk = src.split("::")
                            var_obj = {
                                "str_table": config_str,
                                "int_table": config_int
                            }.get(t_type, None)
                            if var_obj:
                                try:
                                    var_obj.objects.get(Q(pk=pk)).delete()
                                except:
                                    self.log("cannot delete var {}: {}".format(key, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                                else:
                                    self.log("deleted variable {}".format(key))
                                    del global_config[key]
                            else:
                                self.log("unknown source_table {} for {}".format(t_type, key), logging_tools.LOG_LEVEL_ERROR)
                        else:
                            self.log("cannot parse source {} of {}".format(src, key), logging_tools.LOG_LEVEL_ERROR)
            else:
                # default dict
                str_dict = {
                    'mail': {
                        'host': (
                            u'Host $HOSTSTATE$ alert for $HOSTNAME$@$INIT_CLUSTER_NAME$',
                            [
                                u'***** $INIT_MONITOR_INFO$ *****',
                                u'',
                                u'Notification Type: $NOTIFICATIONTYPE$',
                                u'',
                                u'Cluster: $INIT_CLUSTER_NAME$',
                                u'Host   : $HOSTNAME$',
                                u'State  : $HOSTSTATE$',
                                u'Address: $HOSTADDRESS$',
                                u'Info   : $HOSTOUTPUT$',
                                u'',
                                u'Date/Time: $LONGDATETIME$',
                                u'',
                                u'',
                                u'',
                                u''
                                ]
                        ),
                        'service': (
                            u'$NOTIFICATIONTYPE$ alert - $HOSTNAME$@$INIT_CLUSTER_NAME$ ($HOSTALIAS$)/$SERVICEDESC$ is $SERVICESTATE$',
                            [
                                u'***** $INIT_MONITOR_INFO$ *****',
                                u'',
                                u'Notification Type: $NOTIFICATIONTYPE$',
                                u'',
                                u'Cluster: $INIT_CLUSTER_NAME$',
                                u'Service: $SERVICEDESC$',
                                u'Host   : $HOSTALIAS$',
                                u'Address: $HOSTADDRESS$',
                                u'State  : $SERVICESTATE$',
                                u'',
                                u'Date/Time: $LONGDATETIME$',
                                u'',
                                u'Additional Info:',
                                u'',
                                u'$SERVICEOUTPUT$'
                                ]
                            )
                        },
                    'sms': {
                        'host': (
                            '', [
                                u'$HOSTSTATE$ alert for $HOSTNAME$ ($HOSTADDRESS$)'
                                ]
                            ),
                        'service': (
                            '',
                            [
                                u'$NOTIFICATIONTYPE$ alert - $SERVICEDESC$ is $SERVICESTATE$ on $HOSTNAME$'
                            ]
                        )
                    }
                }
            for channel, s_dict in str_dict.iteritems():
                for not_type, (subject, content) in s_dict.iteritems():
                    mon_notification.objects.create(
                        name="{}-notify-by-{}".format(not_type, channel),
                        channel=channel,
                        not_type=not_type,
                        subject=subject,
                        content="\n".join(content)
                    )

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
        self.send_to_process("build", "rebuild_config", cache_mode="DYNAMIC")

    def process_start(self, src_process, src_pid):
        if src_process == "syncer":
            self.send_to_process("syncer", "check_for_slaves")
            self.add_process(build_process("build"), start=True)
        elif src_process == "build":
            self.send_to_process("build", "check_for_slaves")
            if global_config["RELOAD_ON_STARTUP"]:
                self.send_to_process("build", "reload_md_daemon")
            if global_config["BUILD_CONFIG_ON_STARTUP"] or global_config["INITIAL_CONFIG_RUN"]:
                self.send_to_process("build", "rebuild_config", cache_mode=global_config["INITIAL_CONFIG_CACHE_MODE"])
        mult = 3
        process_tools.append_pids(self.__pid_name, src_pid, mult=mult)
        self.__msi_block.add_actual_pid(src_pid, mult=mult, fuzzy_ceiling=3, process_name=src_process)
        self.__msi_block.save_block()

    def _init_msi_block(self):
        process_tools.save_pid(self.__pid_name, mult=3)
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=5)
        self.log("Initialising meta-server-info block")
        msi_block = process_tools.meta_server_info("md-config-server")
        msi_block.add_actual_pid(mult=3, fuzzy_ceiling=4, process_name="main")
        msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=8, process_name="manager")
        msi_block.start_command = "/etc/init.d/md-config-server start"
        msi_block.stop_command = "/etc/init.d/md-config-server force-stop"
        msi_block.kill_pids = True
        msi_block.save_block()
        self.__msi_block = msi_block

    @server_mixins.RemoteCall(target_process="KpiProcess")
    def calculate_kpi(self, srv_com, **kwargs):
        return srv_com

    @server_mixins.RemoteCall(target_process="KpiProcess")
    def get_kpi_source_data(self, srv_com, **kwargs):
        return srv_com

    @server_mixins.RemoteCall(msg_type=RemoteCallMessageType.flat)
    def register_slave(self, *args, **kwargs):
        _src_proc, _src_id, slave_ip, slave_uuid = args
        conn_str = "tcp://{}:{:d}".format(
            slave_ip,
            2004)
        if conn_str not in self.__slaves:
            self.log("connecting to slave on {} ({})".format(conn_str, slave_uuid))
            self.main_socket.connect(conn_str)
            self.__slaves[conn_str] = slave_uuid

    @server_mixins.RemoteCall(msg_type=RemoteCallMessageType.flat)
    def ocsp_results(self, *args, **kwargs):
        _src_proc, _src_pid, lines = args
        self._write_external_cmd_file(lines)

    def _handle_ocp_event(self, in_com):
        com_type = in_com["command"].text
        targ_list = [cur_arg.text for cur_arg in in_com.xpath(".//ns:arguments", smart_strings=False)[0]]
        target_com = {
            "ocsp_event": "PROCESS_SERVICE_CHECK_RESULT",
            "ochp_event": "PROCESS_HOST_CHECK_RESULT",
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
        if com_type == "ocsp_event":
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
                self.log("error writing to {}: {}".format(
                    self.__external_cmd_file,
                    process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                raise
        else:
            self.log("no external cmd_file defined", logging_tools.LOG_LEVEL_ERROR)

    def _send_command(self, *args, **kwargs):
        _src_proc, _src_id, full_uuid, srv_com = args
        self.log("init send of {:d} bytes to {}".format(len(srv_com), full_uuid))
        self.main_socket.send_unicode(full_uuid, zmq.SNDMORE)  # @UndefinedVariable
        self.main_socket.send_unicode(srv_com)

    def _init_network_sockets(self):
        self.network_bind(
            need_all_binds=False,
            bind_port=global_config["COM_PORT"],
            bind_to_localhost=True,
            server_type="md-config",
            simple_server_bind=True,
            pollin=self.remote_call,
        )

        #client = self.zmq_context.socket(zmq.ROUTER)  # @UndefinedVariable
        #client.setsockopt(zmq.IDENTITY, get_server_uuid("md-config"))  # @UndefinedVariable
        #client.setsockopt(zmq.SNDHWM, 1024)  # @UndefinedVariable
        #client.setsockopt(zmq.RCVHWM, 1024)  # @UndefinedVariable
        #client.setsockopt(zmq.LINGER, 0)  # @UndefinedVariable
        #client.setsockopt(zmq.TCP_KEEPALIVE, 1)  # @UndefinedVariable
        #client.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 300)  # @UndefinedVariable
        #try:
        #    client.bind("tcp://*:{:d}".format(global_config["COM_PORT"]))
        #except zmq.ZMQError:
        #    self.log(
        #        "error binding to {:d}: {}".format(
        #            global_config["COM_PORT"],
        #            process_tools.get_except_info()),
        #        logging_tools.LOG_LEVEL_CRITICAL)
        #    raise
        #else:
        #    self.register_poller(client, zmq.POLLIN, self._recv_command)  # @UndefinedVariable
        #    self.com_socket = client

        self.__slaves = {}

        conn_str = process_tools.get_zmq_ipc_name("vector", s_name="collserver", connect_to_root_instance=True)
        vector_socket = self.zmq_context.socket(zmq.PUSH)  # @UndefinedVariable
        vector_socket.setsockopt(zmq.LINGER, 0)  # @UndefinedVariable
        vector_socket.connect(conn_str)
        self.vector_socket = vector_socket

    @server_mixins.RemoteCall(msg_type=RemoteCallMessageType.flat)
    def set_external_cmd_file(self, *args, **kwargs):
        _src_proc, _src_id, ext_name = args
        self.log("setting external cmd_file to '{}'".format(ext_name))
        self.__external_cmd_file = ext_name

    @RemoteCall(target_process="status")
    def get_node_status(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall(target_process="build", target_process_func="build_host_config")
    def get_host_config(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall()
    def rebuild_host_config(self, srv_com, **kwargs):
        # TODO: make parameters work with remote call forwarding
        # TODO: make async execution work with remote call forwarding
        self.send_to_process("build", "rebuild_config", cache_mode=srv_com.get("cache_mode", "DYNAMIC"))
        srv_com.set_result("ok processed command rebuild_host_config")
        return srv_com

    @RemoteCall()
    def sync_http_users(self, srv_com, **kwargs):
        # TODO: make async execution work with remote call forwarding
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
        # TODO: test
        return srv_com

    def _handle_sync_command(self, srv_com):
        self.send_to_process("syncer", srv_com, unicode(srv_com))
        if "sync_id" in srv_com:
            self.log("return with sync_id {:d}".format(int(srv_com["*sync_id"])))
            return srv_com

    @RemoteCall(target_process="syncer")
    def file_content_result(self, srv_com, **kwargs):
        # TODO: test
        return srv_com

    @RemoteCall(target_process="syncer")
    def file_content_bulk_result(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall(target_process="syncer")
    def relayer_info(self, srv_com, **kwargs):
        self.send_to_process("syncer", "relayer_info", unicode(srv_com))
        self.log("return with sync_id {:d}".format(int(srv_com["*sync_id"])))
        srv_com.set_result("ok processed command sync_http_users")
        return srv_com


    TODO:
    transform rest from _recv_command to new structure
    check if other methods are deprecated now
    test startup/teardown of md-config-server


    def _recv_command(self, zmq_sock):
        in_data = []
        while True:
            in_data.append(zmq_sock.recv())
            if not zmq_sock.getsockopt(zmq.RCVMORE):  # @UndefinedVariable
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
                self.main_socket.send_unicode(src_id, zmq.SNDMORE)  # @UndefinedVariable
                self.main_socket.send_unicode("internal error")
            else:
                cur_com = srv_com["command"].text
                if self.__verbose or cur_com not in ["ocsp-event", "ochp-event", "file_content_result", "monitoring_info"]:
                    self.log("got command '{}' from '{}'".format(
                        cur_com,
                        srv_com["source"].attrib["host"]))
                srv_com.update_source()
                send_return = False
                if False:
                    pass

                elif cur_com in ["passive_check_results", "passive_check_results_as_chunk", "passive_check_result"]:
                    self.send_to_process("dynconfig", cur_com, unicode(srv_com))
                    if cur_com == "passive_check_result":
                        send_return = True
                else:
                    self.log("got unknown command '{}' from '{}'".format(cur_com, srv_com["source"].attrib["host"]), logging_tools.LOG_LEVEL_ERROR)
                if send_return:
                    srv_com.set_result("ok processed command {}".format(cur_com))
                    self.main_socket.send_unicode(src_id, zmq.SNDMORE)  # @UndefinedVariable
                    self.main_socket.send_unicode(unicode(srv_com))
                else:
                    del cur_com
        else:
            self.log(
                "wrong count of input data frames: {:d}, first one is {}".format(
                    len(in_data),
                    in_data[0]
                ),
                logging_tools.LOG_LEVEL_ERROR
            )

    def loop_end(self):
        process_tools.delete_pid(self.__pid_name)
        self.__msi_block.remove_meta_block()

    def loop_post(self):
        self.network_unbind()
        self.vector_socket.close()
        self.__log_template.close()
