# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2008,2011-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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
""" logcheck-server (to be run on a syslog_server), server process """

import os

import zmq

from initat.cluster.backbone import db_tools
from initat.cluster.backbone.server_enums import icswServiceEnum
from initat.logcheck_server.config import global_config
from initat.logcheck_server.logcheck.scan import LogcheckScanner
from initat.logcheck_server.logcheck.struct import Machine
from initat.tools import server_mixins, configfile, logging_tools, \
    process_tools, threading_tools, service_tools, server_command


@server_mixins.RemoteCallProcess
class ServerProcess(server_mixins.ICSWBasePool, server_mixins.RemoteCallMixin, server_mixins.SendToRemoteServerMixin):
    def __init__(self):
        threading_tools.icswProcessPool.__init__(self, "main")
        self.CC.init(icswServiceEnum.logcheck_server, global_config)
        self.CC.check_config()
        self.CC.read_config_from_db(
            [
                ("SYSLOG_DIR", configfile.StringConfigVar("/var/log/hosts")),
                ("KEEP_LOGS_UNCOMPRESSED", configfile.IntegerConfigVar(2)),
                ("KEEP_LOGS_TOTAL", configfile.IntegerConfigVar(30)),
                ("KEEP_LOGS_TOTDDAL", configfile.IntegerConfigVar(30)),
                # maximum time in days to track logs
                ("LOGS_TRACKING_DAYS", configfile.IntegerConfigVar(4, help_string="time to track logs in days")),
                # cachesize for lineinfo (per file)
                ("LINECACHE_ENTRIES_PER_FILE", configfile.IntegerConfigVar(50, help_string="line cache per file")),
            ]
        )
        # close connection (daemonizing)
        db_tools.close_connection()
        self.srv_helper = service_tools.ServiceHelper(self.log)
        self.CC.re_insert_config()
        self.register_exception("hup_error", self._hup_error)
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        # log config
        self.CC.log_config()
        # prepare directories
        self._prepare_directories()
        # enable syslog_config
        self._enable_syslog_config()
        # network bind
        self._init_network_sockets()
        Machine.setup(self)
        self.my_scanner = LogcheckScanner(self)
        self.register_poller(Machine.get_watcher()._fd, zmq.POLLIN, Machine.inotify_event)
        self.register_timer(self.sync_machines, 3600, instant=True)
        self.register_timer(self.rotate_logs, 3600 * 12, instant=True)

    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True

    def _hup_error(self, err_cause):
        self.log("got SIGHUP")
        self.my_scanner.rescan()

    def _init_network_sockets(self):
        self.network_bind(
            need_all_binds=False,
            pollin=self.remote_call,
            service_type_enum=icswServiceEnum.logcheck_server,
        )
        return True

    def _prepare_directories(self):
        for cur_dir in [global_config["SYSLOG_DIR"]]:
            if not os.path.isdir(cur_dir):
                try:
                    os.mkdir(cur_dir)
                except:
                    self.log(
                        "error creating {}: {}".format(
                            cur_dir,
                            process_tools.get_except_info()
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )

    def sync_machines(self):
        db_tools.close_connection()
        Machine.db_sync()

    def rotate_logs(self):
        db_tools.close_connection()
        Machine.g_rotate_logs()

    def process_start(self, src_process, src_pid):
        self.CC.process_added(src_process, src_pid)

    def loop_end(self):
        self._disable_syslog_config()
        Machine.shutdown()

    def loop_post(self):
        self.network_unbind()
        self.CC.close()

    @server_mixins.RemoteCall()
    def get_syslog(self, srv_com, **kwargs):
        Machine.get_syslog(srv_com)
        return srv_com

    @server_mixins.RemoteCall()
    def syslog_rate_mon(self, srv_com, **kwargs):
        Machine.mon_command_class.g_run(srv_com)
        return srv_com

    @server_mixins.RemoteCall()
    def syslog_check_mon(self, srv_com, **kwargs):
        Machine.mon_command_class.g_run(srv_com)
        return srv_com

    @server_mixins.RemoteCall()
    def get_0mq_id(self, srv_com, **kwargs):
        srv_com["zmq_id"] = self.bind_id
        srv_com.set_result("0MQ_ID is {}".format(self.bind_id), server_command.SRV_REPLY_STATE_OK)
        return srv_com

    # syslog stuff
    def _enable_syslog_config(self):
        syslog_srvcs = self.srv_helper.find_services(".*syslog", active=True)
        if syslog_srvcs:
            self.__syslog_type = syslog_srvcs[0]
            self.log("syslog type found: {}".format(self.__syslog_type))
            if self.__syslog_type.count("rsys") or self.__syslog_type == "syslog":
                self._enable_rsyslog()
            elif self.__syslog_type.count("-ng"):
                self._enable_syslog_ng()
            else:
                self.log("dont know how to handle syslog_type '{}'".format(self.__syslog_type), logging_tools.LOG_LEVEL_ERROR)
        else:
            self.__syslog_type = None
            self.log("found no valid syslog service", logging_tools.LOG_LEVEL_ERROR)

    def _disable_syslog_config(self):
        if self.__syslog_type:
            if self.__syslog_type.count("rsys"):
                self._disable_rsyslog()
            elif self.__syslog_type.count("-ng"):
                self._disable_syslog_ng()

    def _enable_syslog_ng(self):
        self.log("not implemented", logging_tools.LOG_LEVEL_CRITICAL)

    def _disable_syslog_ng(self):
        self.log("not implemented", logging_tools.LOG_LEVEL_CRITICAL)

    def _enable_rsyslog(self):
        """ do not forget to enclose the local ruleset in $RuleSet local / $DefaultRuleset local """
        rsyslog_lines = [
            '# UDP Syslog Server:',
            '$ModLoad imudp.so         # provides UDP syslog reception',
            '',
            '$template precise,"%syslogpriority%|%syslogfacility%|%TIMESTAMP:::date-rfc3339%|%HOSTNAME%|%syslogtag%|%msg%\\n"',
            '',
            '$template prog_log,"{}/%FROMHOST-IP%/%$YEAR%/%$MONTH%/%$DAY%/%programname%"'.format(
                global_config["SYSLOG_DIR"],
            ),
            '$template full_log,"{}/%FROMHOST-IP%/%$YEAR%/%$MONTH%/%$DAY%/log"'.format(
                global_config["SYSLOG_DIR"],
            ),
            '',
            '$RuleSet remote',
            '$DirCreateMode 0755',
            '',
            '$FileCreateMode 0644',
            '*.* ?prog_log;precise',
            '',
            '$FileCreateMode 0644',
            '*.* ?full_log;precise',
            '',
            '$InputUDPServerBindRuleset remote',
            '$UDPServerRun 514         # start a UDP syslog server at standard port 514',
            '',
            '$RuleSet RSYSLOG_DefaultRuleset',
        ]
        self._slcn = "/etc/rsyslog.d/logcheck_server.conf"
        self.log("writing rsyslog-config to {}".format(self._slcn))
        open(self._slcn, "w").write("\n".join(rsyslog_lines))
        self._restart_syslog()

    def _disable_rsyslog(self):
        if os.path.isfile(self._slcn):
            os.unlink(self._slcn)
        self._restart_syslog()

    def _restart_syslog(self):
        self.srv_helper.service_command(self.__syslog_type, "restart")
