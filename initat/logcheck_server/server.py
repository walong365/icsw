# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2008,2011-2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of logcheck-server
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
""" logcheck-server (to be run on a syslog_server), server process """

import os

from initat.cluster.backbone import db_tools
from initat.logcheck_server.config import global_config
from initat.logcheck_server.logcheck_struct import Machine
from initat.tools import server_mixins, configfile, logging_tools, \
    process_tools, threading_tools, service_tools


class server_process(server_mixins.ICSWBasePool):
    def __init__(self, options):
        threading_tools.process_pool.__init__(self, "main", zmq=True)
        self.CC.init("logcheck-server", global_config)
        self.CC.check_config()
        self.__pid_name = global_config["PID_NAME"]
        # close connection (daemonizing)
        db_tools.close_connection()
        self.__msi_block = self._init_msi_block()
        self.srv_helper = service_tools.ServiceHelper(self.log)
        self.CC.re_insert_config()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        # log config
        self.CC.log_config()
        # prepare directories
        self._prepare_directories()
        # enable syslog_config
        self._enable_syslog_config()
        self.__options = options
        Machine.setup(self)
        self.register_timer(self._sync_machines, 3600, instant=True)
        self.register_timer(self._rotate_logs, 3600 * 12, instant=True)

    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True

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

    def _sync_machines(self):
        db_tools.close_connection()
        Machine.db_sync()

    def _rotate_logs(self):
        db_tools.close_connection()
        Machine.rotate_logs()

    def process_start(self, src_process, src_pid):
        mult = 2
        process_tools.append_pids(self.__pid_name, src_pid, mult=mult)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(src_pid, mult=mult)
            self.__msi_block.save_block()

    def _init_msi_block(self):
        process_tools.save_pid(self.__pid_name, mult=3)
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=2)
        self.log("Initialising meta-server-info block")
        msi_block = process_tools.meta_server_info("logcheck-server")
        msi_block.add_actual_pid(mult=3, fuzzy_ceiling=4, process_name="main")
        msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=2, process_name="manager")
        msi_block.kill_pids = True
        msi_block.save_block()
        return msi_block

    def loop_end(self):
        self._disable_syslog_config()
        Machine.shutdown()
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()

    def loop_post(self):
        self.CC.close()

    # syslog stuff
    def _enable_syslog_config(self):
        syslog_srvcs = self.srv_helper.find_services(".*syslog", active=True)
        if syslog_srvcs:
            self.__syslog_type = syslog_srvcs[0]
            self.log("syslog type found: {}".format(self.__syslog_type))
            if self.__syslog_type.count("rsys"):
                self._enable_rsyslog()
            elif self.__syslog_type.count("-ng"):
                self._enable_syslog_ng()
            else:
                self.log("dont know how to handle syslog_type '{}'".format(self.__syslog_type), logging_tools.LOG_LEVEL_ERROR)
        else:
            self.__syslog_type = None
            self.log("found no valid syslog service", logging_tools.LOG_LEVEL_ERROR)

    def _disable_syslog_config(self):
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
            '*.* ?prog_log',
            '',
            '$FileCreateMode 0644',
            '*.* ?full_log',
            '',
            '$InputUDPServerBindRuleset remote',
            '$UDPServerRun 514         # start a UDP syslog server at standard port 514',
            '',
            '$RuleSet RSYSLOG_DefaultRuleset',
        ]
        self._slcn = "/etc/rsyslog.d/logcheck_server.conf"
        self.log("writing rsyslog-config to {}".format(self._slcn))
        file(self._slcn, "w").write("\n".join(rsyslog_lines))
        self._restart_syslog()

    def _disable_rsyslog(self):
        if os.path.isfile(self._slcn):
            os.unlink(self._slcn)
        self._restart_syslog()

    def _restart_syslog(self):
        self.srv_helper.service_command(self.__syslog_type, "restart")
