# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2008,2011-2014 Andreas Lang-Nevyjel
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

from django.db import connection
from initat.logcheck_server.config import global_config
from initat.logcheck_server.struct import machine
import cluster_location
import configfile
import logging_tools
import os
import process_tools
import psutil
import threading_tools


class server_process(threading_tools.process_pool):
    def __init__(self, options):
        self.__log_cache, self.__log_template = ([], None)
        threading_tools.process_pool.__init__(self, "main", zmq=True, zmq_debug=global_config["ZMQ_DEBUG"])
        self.__pid_name = global_config["PID_NAME"]
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        # close connection (daemonizing)
        connection.close()
        self.__msi_block = self._init_msi_block()
        self._re_insert_config()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        # log config
        self._log_config()
        # prepare directories
        self._prepare_directories()
        # enable syslog_config
        self._enable_syslog_config()
        self.__options = options
        machine.setup(self)
        self.register_timer(self._sync_machines, 3600, instant=True)
        self.register_timer(self._rotate_logs, 3600 * 12, instant=True)

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

    def _log_config(self):
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found %d valid config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))

    def _re_insert_config(self):
        self.log("re-insert config")
        cluster_location.write_config("syslog_server", global_config)

    def _sync_machines(self):
        connection.close()
        machine.db_sync()

    def _rotate_logs(self):
        connection.close()
        machine.rotate_logs()

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
        msi_block = process_tools.meta_server_info("logcheck")
        msi_block.add_actual_pid(mult=3, fuzzy_ceiling=4, process_name="main")
        msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=2, process_name="manager")
        msi_block.start_command = "/etc/init.d/logcheck-server start"
        msi_block.stop_command = "/etc/init.d/logcheck-server force-stop"
        msi_block.kill_pids = True
        msi_block.save_block()
        return msi_block

    def loop_end(self):
        self._disable_syslog_config()
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()

    def loop_post(self):
        self.__log_template.close()

    # syslog stuff
    def _enable_syslog_config(self):
        syslog_exe_dict = {value.pid: value.exe() for value in psutil.process_iter() if value.is_running() and value.exe().count("syslog")}
        syslog_type = None
        for key, value in syslog_exe_dict.iteritems():
            self.log("syslog process found: {}".format(key))
            if value.endswith("rsyslogd"):
                syslog_type = "rsyslogd"
            elif value.endswith("syslog-ng"):
                syslog_type = "syslog-ng"
        self.log("syslog type found: {}".format(syslog_type or "none"))
        self.__syslog_type = syslog_type
        if self.__syslog_type == "rsyslogd":
            self._enable_rsyslog()
        elif self.__syslog_type == "syslog-ng":
            self._enable_syslog_ng()

    def _disable_syslog_config(self):
        if self.__syslog_type == "rsyslogd":
            self._disable_rsyslog()
        elif self.__syslog_type == "syslog-ng":
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
            '$template prog_log,"%s/%%FROMHOST-IP%%/%%$YEAR%%/%%$MONTH%%/%%$DAY%%/%%programname%%"' % (global_config["SYSLOG_DIR"]),
            '$template full_log,"%s/%%FROMHOST-IP%%/%%$YEAR%%/%%$MONTH%%/%%$DAY%%/log"' % (global_config["SYSLOG_DIR"]),
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
        slcn = "/etc/rsyslog.d/logcheck_server.conf"
        file(slcn, "w").write("\n".join(rsyslog_lines))
        self._restart_syslog()

    def _disable_rsyslog(self):
        slcn = "/etc/rsyslog.d/logcheck_server.conf"
        if os.path.isfile(slcn):
            os.unlink(slcn)
        self._restart_syslog()

    def _restart_syslog(self):
        syslog_found = False
        for syslog_rc in ["/etc/init.d/syslog", "/etc/init.d/syslog-ng", "/etc/init.d/rsyslog"]:
            if os.path.isfile(syslog_rc):
                syslog_found = True
                break
        if syslog_found:
            c_stat, out_f = process_tools.submit_at_command("%s restart" % (syslog_rc), 0)
            self.log(u"restarting {} gave {:d}:".format(syslog_rc, c_stat))
            for line in out_f:
                self.log(line)
        else:
            self.log("no syslog rc-script found", logging_tools.LOG_LEVEL_ERROR)
