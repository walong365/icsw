# Copyright (C) 2013-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-server-server
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
""" server process for md-config-server """

import json
import time

import zmq
from django.db.models import Q

from initat.cluster.backbone import db_tools
from initat.cluster.backbone.icinga_commands_enum import IcingaCommandEnum
from initat.cluster.backbone.models import mon_notification, config_str, config_int, \
    device, user
from initat.cluster.backbone.server_enums import icswServiceEnum
from initat.md_sync_server.mixins import VersionCheckMixin
from initat.tools import logging_tools, process_tools, threading_tools, server_mixins, configfile, server_command
from initat.tools.server_mixins import RemoteCall
from .build import BuildControl
from .config import global_config
from .dynconfig import DynConfigProcess
from .icinga_log_reader.log_reader import IcingaLogReader
from .kpi import KpiProcess
from .syncer import SyncerProcess, RemoteServer


@server_mixins.RemoteCallProcess
class ServerProcess(
    server_mixins.ICSWBasePool,
    VersionCheckMixin,
    server_mixins.RemoteCallMixin,
    server_mixins.SendToRemoteServerMixin,
):
    def __init__(self):
        long_host_name, mach_name = process_tools.get_fqdn()
        threading_tools.icswProcessPool.__init__(self, "main")
        self.CC.init(icswServiceEnum.monitor_server, global_config)
        self.CC.check_config()
        db_tools.close_connection()
        self.CC.read_config_from_db(
            [
                ("NETSPEED_WARN_MULT", configfile.FloatConfigVar(0.85)),
                ("NETSPEED_CRITICAL_MULT", configfile.FloatConfigVar(0.95)),
                ("NETSPEED_DEFAULT_VALUE", configfile.IntegerConfigVar(10000000)),
                ("CHECK_HOST_ALIVE_PINGS", configfile.IntegerConfigVar(5)),
                ("CHECK_HOST_ALIVE_TIMEOUT", configfile.FloatConfigVar(5.0)),
                ("ENABLE_COLLECTD", configfile.BoolConfigVar(False)),
                ("ENABLE_NAGVIS", configfile.BoolConfigVar(False)),
                ("ENABLE_FLAP_DETECTION", configfile.BoolConfigVar(False)),
                ("NAGVIS_DIR", configfile.StringConfigVar("/opt/nagvis4icinga")),
                ("NAGVIS_URL", configfile.StringConfigVar("/nagvis")),
                ("NONE_CONTACT_GROUP", configfile.StringConfigVar("none_group")),
                ("FROM_ADDR", configfile.StringConfigVar(long_host_name)),
                ("LOG_EXTERNAL_COMMANDS", configfile.BoolConfigVar(False)),
                ("LOG_PASSIVE_CHECKS", configfile.BoolConfigVar(False)),
                ("BUILD_CONFIG_ON_STARTUP", configfile.BoolConfigVar(True)),
                ("RELOAD_ON_STARTUP", configfile.BoolConfigVar(True)),
                ("RETAIN_HOST_STATUS", configfile.BoolConfigVar(True)),
                ("RETAIN_SERVICE_STATUS", configfile.BoolConfigVar(True)),
                ("PASSIVE_HOST_CHECKS_ARE_SOFT", configfile.BoolConfigVar(True)),
                ("RETAIN_PROGRAM_STATE", configfile.BoolConfigVar(False)),
                ("USE_HOST_DEPENDENCIES", configfile.BoolConfigVar(False)),
                ("USE_SERVICE_DEPENDENCIES", configfile.BoolConfigVar(False)),
                ("TRANSLATE_PASSIVE_HOST_CHECKS", configfile.BoolConfigVar(True)),
                ("USE_ONLY_ALIAS_FOR_ALIAS", configfile.BoolConfigVar(False)),
                ("HOST_DEPENDENCIES_FROM_TOPOLOGY", configfile.BoolConfigVar(False)),
                ("CCOLLCLIENT_TIMEOUT", configfile.IntegerConfigVar(10)),
                ("CSNMPCLIENT_TIMEOUT", configfile.IntegerConfigVar(20)),
                ("MAX_SERVICE_CHECK_SPREAD", configfile.IntegerConfigVar(5)),
                ("MAX_HOST_CHECK_SPREAD", configfile.IntegerConfigVar(5)),
                ("MAX_CONCURRENT_CHECKS", configfile.IntegerConfigVar(500)),
                ("CHECK_SERVICE_FRESHNESS", configfile.BoolConfigVar(True, help_string="enable service freshness checking")),
                ("CHECK_HOST_FRESHNESS", configfile.BoolConfigVar(True, help_string="enable host freshness checking")),
                ("SAFE_CC_NAME", configfile.BoolConfigVar(False)),
                ("SERVICE_FRESHNESS_CHECK_INTERVAL", configfile.IntegerConfigVar(60)),
                ("HOST_FRESHNESS_CHECK_INTERVAL", configfile.IntegerConfigVar(60)),
                (
                    "SAFE_NAMES", configfile.BoolConfigVar(False, help_string="convert all command descriptions to safe names (without spaces), [%(default)s]")
                ),
                (
                    "ENABLE_ICINGA_LOG_PARSING",
                    configfile.BoolConfigVar(True, help_string="collect icinga logs in the database (required for status history and kpis)")
                ),
            ]
        )
        # copy flags
        self.__verbose = global_config["VERBOSE"]
        # log config
        self.CC.log_config()
        # re-insert config
        self.CC.re_insert_config()
        # init build control
        self.BC = BuildControl(self)
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("hup_error", self._hup_error)
        self._check_notification()
        # sync master uuid
        self.__sync_master_uuid = None
        # from mixins
        self.VCM_check_md_version(global_config)
        self._init_network_sockets()

        if "MD_TYPE" in global_config:
            self.register_func("register_remote", self._register_remote)
            self.register_func("send_command", self._send_command)
            self.register_func("ocsp_results", self._ocsp_results)
            self.register_func("set_sync_master_uuid", self._set_sync_master_uuid)
            self.register_func("distribution_info", self._distribution_info)
            self.register_func("build_step", self.BC.build_step)

            self.add_process(SyncerProcess("syncer"), start=True)
            self.add_process(DynConfigProcess("dynconfig"), start=True)
            self.add_process(IcingaLogReader("IcingaLogReader"), start=True)
            self.add_process(KpiProcess("KpiProcess"), start=True)
            # wait for the processes to start
            time.sleep(0.5)
            self.register_timer(self._check_for_redistribute, 60 if global_config["DEBUG"] else 300)
            # only test code
            # self.send_to_remote_server(
            #    "cluster-server",
            #    unicode(server_command.srv_command(command="statusd")),
            # )
        else:
            self.log("MD_TYPE not defined in global_config, exiting...", logging_tools.LOG_LEVEL_ERROR)
            self._int_error("no MD found")

    def _distribution_info(self, *args, **kwarg):
        dist_info = args[2]
        self.BC.distribution_info(dist_info)

    def _check_for_redistribute(self):
        self.send_to_process("syncer", "check_for_redistribute")

    def _set_sync_master_uuid(self, src_proc, src_id, master_uuid, **kwargs):
        self.log("set sync_master uuid to {}".format(master_uuid))
        self.__sync_master_uuid = master_uuid

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
                            [global_config["HOST_NOTIFY_BY_EMAIL_LINE{:02d}".format(idx)] for idx in range(1, 16)],
                        ),
                        "service": (
                            global_config["NOTIFY_BY_EMAIL_SUBJECT"],
                            [global_config["NOTIFY_BY_EMAIL_LINE{:02d}".format(idx)] for idx in range(1, 16)],
                        ),
                    }
                }
                for key in list(global_config.keys()):
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
                            'Host $HOSTSTATE$ alert for $HOSTNAME$@$INIT_CLUSTER_NAME$',
                            [
                                '***** $INIT_MONITOR_INFO$ *****',
                                '',
                                'Notification Type: $NOTIFICATIONTYPE$',
                                '',
                                'Cluster: $INIT_CLUSTER_NAME$',
                                'Host   : $HOSTNAME$',
                                'State  : $HOSTSTATE$',
                                'Address: $HOSTADDRESS$',
                                'Info   : $HOSTOUTPUT$',
                                '',
                                'Date/Time: $LONGDATETIME$',
                                '',
                                '',
                                '',
                                ''
                            ]
                        ),
                        'service': (
                            '$NOTIFICATIONTYPE$ alert - $HOSTNAME$@$INIT_CLUSTER_NAME$ ($HOSTALIAS$)/$SERVICEDESC$ is $SERVICESTATE$',
                            [
                                '***** $INIT_MONITOR_INFO$ *****',
                                '',
                                'Notification Type: $NOTIFICATIONTYPE$',
                                '',
                                'Cluster: $INIT_CLUSTER_NAME$',
                                'Service: $SERVICEDESC$',
                                'Host   : $HOSTALIAS$',
                                'Address: $HOSTADDRESS$',
                                'State  : $SERVICESTATE$',
                                '',
                                'Date/Time: $LONGDATETIME$',
                                '',
                                'Additional Info:',
                                '',
                                '$SERVICEOUTPUT$'
                            ]
                        )
                    },
                    'sms': {
                        'host': (
                            '',
                            [
                                '$HOSTSTATE$ alert for $HOSTNAME$ ($HOSTADDRESS$)'
                            ]
                        ),
                        'service': (
                            '',
                            [
                                '$NOTIFICATIONTYPE$ alert - $SERVICEDESC$ is $SERVICESTATE$ on $HOSTNAME$'
                            ]
                        )
                    }
                }
            for channel, s_dict in str_dict.items():
                for not_type, (subject, content) in s_dict.items():
                    mon_notification.objects.create(
                        name="{}-notify-by-{}".format(not_type, channel),
                        channel=channel,
                        not_type=not_type,
                        subject=subject,
                        content="\n".join(content)
                    )

    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True

    def _hup_error(self, err_cause):
        self.log("got sighup", logging_tools.LOG_LEVEL_WARN)
        srv_com = server_command.srv_command(
            command="build_host_config",
        )
        self.BC.handle_command(srv_com)

    def process_start(self, src_process, src_pid):
        db_tools.close_connection()
        if src_process == "syncer":
            self.send_to_process("syncer", "check_for_slaves")
        self.BC.process_action(src_process, True)
        self.CC.process_added(src_process, src_pid)

    def process_exit(self, src_process, src_pid):
        self.BC.process_action(src_process, False)
        self.CC.process_removed(src_pid)

    def handle_mon_command(self, srv_com):
        data = json.loads(srv_com["*data"])
        _enum = getattr(IcingaCommandEnum, data["action"].lower())
        _val_dict = {key: {"raw": value} for key, value in data["arguments"].items()}
        _val_dict = _enum.value.resolve_args(_val_dict)
        # add user
        _val_dict["author"] = {"value": str(user.objects.get(Q(pk=data["user_idx"])))}
        # unroll keys
        host_idxs = set([entry["host_idx"] for entry in data["key_list"]])
        name_dict = {dev.idx: dev.full_name for dev in device.objects.filter(Q(idx__in=host_idxs))}
        cmd_lines = _enum.value.create_commands(data["type"], data["key_list"], _val_dict, name_dict)
        # pprint.pprint(cmd_lines)
        srv_com.set_result(
            "processed command {} (generated {})".format(
                data["action"],
                logging_tools.get_plural("line", len(cmd_lines)),
            )
        )
        if cmd_lines:
            self.log("created {}".format(logging_tools.get_plural("line", len(cmd_lines))))
            ext_com = server_command.srv_command(
                command="ext_command",
                lines=cmd_lines,
            )
            self.send_to_process("syncer", "ext_command", str(ext_com))
        else:
            self.log("created no external commands", logging_tools.LOG_LEVEL_ERROR)

    def _register_remote(self, *args, **kwargs):
        _src_proc, _src_id, remote_ip, remote_uuid, remote_enum_name = args
        if remote_uuid not in self.__remotes:
            # in fact only one primary remote is handled
            rs = RemoteServer(remote_uuid, remote_ip, self.CC.Instance.get_port_dict(getattr(icswServiceEnum, remote_enum_name), command=True))
            self.log("connecting to {}".format(str(rs)))
            self.main_socket.connect(rs.conn_str)
            self.__remotes[remote_uuid] = rs

    def _ocsp_results(self, *args, **kwargs):
        _src_proc, _src_pid, lines = args
        # print "* OCSP", lines
        if self.__sync_master_uuid:
            self.send_command(
                self.__sync_master_uuid,
                server_command.srv_command(
                    command="ocsp_lines",
                    ocsp_lines=server_command.compress(lines, json=True),
                )
            )
        else:
            self.log(
                "no sync_master_uuid set ({})".format(
                    logging_tools.get_plural("OCSP line", len(lines))
                ),
                logging_tools.LOG_LEVEL_ERROR
            )

    def _send_command(self, *args, **kwargs):
        _src_proc, _src_id, full_uuid, srv_com = args
        self.send_command(full_uuid, srv_com)

    def send_command(self, full_uuid, srv_com):
        _srv_com = str(srv_com)
        try:
            self.main_socket.send_unicode(full_uuid, zmq.SNDMORE)
            self.main_socket.send_unicode(_srv_com)
        except:
            self.log(
                "cannot send {:d} bytes to {}: {}".format(
                    len(_srv_com),
                    full_uuid,
                    process_tools.get_except_info(),
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            if full_uuid in self.__remotes:
                self.log("target is {}".format(str(self.__remotes[full_uuid])))
        else:
            self.log("sent {:d} bytes to {}".format(len(srv_com), full_uuid))

    def _init_network_sockets(self):
        self.network_bind(
            need_all_binds=False,
            bind_to_localhost=True,
            service_type_enum=icswServiceEnum.monitor_server,
            simple_server_bind=True,
            pollin=self.remote_call,
        )

        self.__remotes = {}

    @RemoteCall(target_process="KpiProcess")
    def calculate_kpi_preview(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall(target_process="KpiProcess")
    def calculate_kpi_db(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall(target_process="KpiProcess")
    def get_kpi_source_data(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall(send_async_return=True, sync=False)
    def get_host_config(self, srv_com, **kwargs):
        self.BC.handle_command(srv_com)
        return None

    @RemoteCall()
    def build_host_config(self, srv_com, **kwargs):
        # pretend to be synchronous call such that reply is sent right away
        self.BC.handle_command(srv_com)
        srv_com.set_result("ok processed command build_host_config")
        return srv_com

    @RemoteCall()
    def fetch_dyn_config(self, srv_com, **kwargs):
        # pretend to be synchronous call such that reply is sent right away
        self.BC.handle_command(srv_com)
        srv_com.set_result("ok started fetching of dynamic configs")
        return srv_com

    @RemoteCall()
    def sync_http_users(self, srv_com, **kwargs):
        # self.send_to_process("build", "sync_http_users")
        self.BC.handle_command(srv_com)
        srv_com.set_result("ok processed command sync_http_users")
        return srv_com

    @RemoteCall(target_process="dynconfig")
    def monitoring_info(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall()
    def mon_process_handling(self, srv_com, **kwargs):
        self.send_to_process("syncer", "mon_process_handling", str(srv_com))
        srv_com.set_result("ok set new flags")
        return srv_com

    @RemoteCall()
    def mon_command(self, srv_com, **kwargs):
        self.handle_mon_command(srv_com)
        return srv_com

    @RemoteCall(target_process="syncer")
    def slave_info(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall(target_process="syncer")
    def get_sys_info(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall()
    def passive_check_result(self, srv_com, **kwargs):
        # pretend to be synchronous call such that reply is sent right away
        self.send_to_process("dynconfig", "passive_check_result", str(srv_com))
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
        return self.server_status(srv_com, self.CC.msi_block, global_config)

    def loop_end(self):
        pass

    def loop_post(self):
        self.network_unbind()
        self.CC.close()
