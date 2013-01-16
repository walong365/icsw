#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2011,2012,2013 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of rms-tools
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

import sys
import process_tools
import commands
import os
import configfile
import os.path
import time
import logging_tools
import pprint
import server_command
import threading_tools
import sge_tools
import config_tools
try:
    import cluster_location
except ImportError:
    cluster_location = None
try:
    from sge_server_version import VERSION_STRING
except ImportError:
    VERSION_STRING = "?.?"
import zmq

#from sge_server_messages import *

# old
SERVER_CHECK_PORT = 8009
# new 
COM_PORT = 8009
SQL_ACCESS = "cluster_full_access"

def call_command(command, log_com=None):
    start_time = time.time()
    stat, out = commands.getstatusoutput(command)
    end_time = time.time()
    log_lines = ["calling '%s' took %s, result (stat %d) is %s (%s)" % (command,
                                                                        logging_tools.get_diff_time_str(end_time - start_time),
                                                                        stat,
                                                                        logging_tools.get_plural("byte", len(out)),
                                                                        logging_tools.get_plural("line", len(out.split("\n"))))]
    if log_com:
        for log_line in log_lines:
            log_com(" - %s" % (log_line))
        if stat:
            for log_line in out.split("\n"):
                log_com(" - %s" % (log_line))
        return stat, out
    else:
        if stat:
            # append output to log_lines if error
            log_lines.extend([" - %s" % (line) for line in out.split("\n")])
        return stat, out, log_lines

class rms_mon_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context, init_logger=True)
        self.__main_socket = self.connect_to_socket("internal")
        self._init_sge_info()
        self.register_func("get_config", self._get_config)
        self.register_func("full_reload", self._full_reload)
    def _init_sge_info(self):
        self.log("init sge_info")
        self.__sge_info = sge_tools.sge_info(log_command=self.log,
                                             run_initial_update=False,
                                             verbose=True if global_config["DEBUG"] else False,
                                             is_active=True,
                                             sge_dict=dict([(key, global_config[key]) for key in ["SGE_ARCH", "SGE_ROOT", "SGE_CELL"]]))
        self._update()
    def _update(self):
        self.__sge_info.update(no_file_cache=True, force_update=True)
    def _full_reload(self, *args, **kwargs):
        self.log("doing a full_reload")
        self._update()
    def _get_config(self, *args, **kwargs):
        src_id, srv_com_str = args
        srv_com = server_command.srv_command(source=srv_com_str)
        #needed_dicts = opt_dict.get("needed_dicts", ["hostgroup", "queueconf", "qhost", "complexes"])
        #update_list = opt_dict.get("update_list", [])
        self.__sge_info.update()
        srv_com["sge"] = self.__sge_info.get_tree()
        #needed_dicts = ["hostgroup", "queueconf", "qhost"]#, "complexes"]
        #update_list = []
        #for key in needed_dicts:
        #    if key == "qhost":
        #        srv_com["sge:%s" % (key)] = dict([(sub_key, self.__sge_info[key][sub_key].get_value_dict()) for sub_key in self.__sge_info[key]])
        #    else:
        #        srv_com["sge:%s" % (key)] = self.__sge_info[key]
        self.send_to_socket(self.__main_socket, ["command_result", src_id, unicode(srv_com)])
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def loop_post(self):
        self.__main_socket.close()
        self.__log_template.close()

class server_process(threading_tools.process_pool):
    def __init__(self):
        self.__log_cache, self.__log_template = ([], None)
        self.__pid_name = global_config["PID_NAME"]
        threading_tools.process_pool.__init__(self, "main", zmq=True,
                                              zmq_debug=global_config["ZMQ_DEBUG"])
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self.__msi_block = self._init_msi_block()
        # re-insert config
        self._re_insert_config()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("hup_error", self._hup_error)
        self._log_config()
        #dc.release()
        self._init_network_sockets()
        #self.add_process(db_verify_process("db_verify"), start=True)
        self.add_process(rms_mon_process("rms_mon"), start=True)
        self.register_func("command_result", self._com_result)
        #self._init_em()
        #self.register_timer(self._check_db, 3600, instant=True)
        #self.register_timer(self._update, 30, instant=True)
        #self.__last_update = time.time() - self.__glob_config["MAIN_LOOP_TIMEOUT"]
        #self.send_to_process("build", "rebuild_config", global_config["ALL_HOSTS_NAME"])
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            while self.__log_cache:
                self.__log_template.log(*self.__log_cache.pop(0))
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))
    def _log_config(self):
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found %d valid global config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True
    def _hup_error(self, err_cause):
        self.log("got sighup", logging_tools.LOG_LEVEL_WARN)
        self.send_to_process("rms_mon", "full_reload")
    def _re_insert_config(self):
        self.log("re-insert config")
        cluster_location.write_config("sge_server", global_config)
    def process_start(self, src_process, src_pid):
        mult = 3
        process_tools.append_pids(self.__pid_name, src_pid, mult=mult)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(src_pid, mult=mult)
            self.__msi_block.save_block()
    def _init_msi_block(self):
        process_tools.save_pid(self.__pid_name, mult=3)
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=3)
        if not global_config["DEBUG"] or True:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("sge_server")
            msi_block.add_actual_pid(mult=3)
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=3)
            msi_block.start_command = "/etc/init.d/sge-server start"
            msi_block.stop_command = "/etc/init.d/sge-server force-stop"
            msi_block.kill_pids = True
            msi_block.save_block()
        else:
            msi_block = None
        return msi_block
    def _init_network_sockets(self):
        client = self.zmq_context.socket(zmq.ROUTER)
        client.setsockopt(zmq.IDENTITY, "sgeserver")
        client.setsockopt(zmq.RCVHWM, 256)
        client.setsockopt(zmq.SNDHWM, 256)
        try:
            client.bind("tcp://*:%d" % (global_config["COM_PORT"]))
        except zmq.core.error.ZMQError:
            self.log("error binding to %d: %s" % (global_config["COM_PORT"],
                                                  process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_CRITICAL)
            raise
        else:
            self.log("connected to tcp://*:%d" % (global_config["COM_PORT"]))
            self.register_poller(client, zmq.POLLIN, self._recv_command)
            self.com_socket = client
    def _recv_command(self, zmq_sock):
        data = []
        while True:
            data.append(zmq_sock.recv_unicode())
            more = zmq_sock.getsockopt(zmq.RCVMORE)
            if not more:
                break
        if len(data) == 2:
            src_id, xml_input = data
            srv_com = server_command.srv_command(source=xml_input)
            self.log("got command '%s' from %s" % (srv_com["command"].text, src_id))
            srv_com.update_source()
            cur_com = srv_com["command"].text
            if cur_com == "get_config":
                self.send_to_process("rms_mon", "get_config", src_id, unicode(srv_com))
            else:
                srv_com["result"] = {"state" : server_command.SRV_REPLY_STATE_ERROR,
                                     "reply" : "unknown command %s" % (cur_com)}
                self._send_result(src_id, srv_com)
        else:
            self.log("received wrong data (len() = %d != 2)" % (len(data)),
                     logging_tools.LOG_LEVEL_ERROR)
    def _send_result(self, src_id, srv_com):
        self.com_socket.send_unicode(src_id, zmq.SNDMORE)
        self.com_socket.send_unicode(unicode(srv_com))
    def _com_result(self, src_proc, proc_id, src_id, srv_com):
        self._send_result(src_id, srv_com)
    def loop_post(self):
        if self.com_socket:
            self.log("closing socket")
            self.com_socket.close()
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
        self.__log_template.close()
        
global_config = configfile.get_global_config(process_tools.get_programm_name())

def main():
    long_host_name, mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries([
        ("DEBUG"               , configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("ZMQ_DEBUG"           , configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
        ("PID_NAME"            , configfile.str_c_var(os.path.join(prog_name, prog_name))),
        ("KILL_RUNNING"        , configfile.bool_c_var(True, help_string="kill running instances [%(default)s]")),
        ("CHECK"               , configfile.bool_c_var(False, short_options="C", help_string="only check for server status", action="store_true", writeback=False)),
        ("USER"                , configfile.str_c_var("sge", help_string="user to run as [%(default)s")),
        ("GROUP"               , configfile.str_c_var("sge", help_string="group to run as [%(default)s]")),
        ("GROUPS"              , configfile.array_c_var(["idg"])),
        ("FORCE"               , configfile.bool_c_var(False, help_string="force running ", action="store_true", only_commandline=True)),
        ("LOG_DESTINATION"     , configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME"            , configfile.str_c_var(prog_name)),
        ("VERBOSE"             , configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
    ])
    global_config.parse_file()
    options = global_config.handle_commandline(description="%s, version is %s" % (prog_name,
                                                                                  VERSION_STRING),
                                               add_writeback_option=True,
                                               positional_arguments=False)
    global_config.write_file()
    sql_s_info = config_tools.server_check(server_type="sge_server")
    if not sql_s_info.effective_device:
        if global_config["FORCE"]:
            global_config.add_config_entries([("DUMMY_RUN", configfile.bool_c_var(True))])
        else:
            sys.stderr.write(" %s is no sge-server, exiting..." % (long_host_name))
            sys.exit(5)
    else:
        global_config.add_config_entries([("DUMMY_RUN", configfile.bool_c_var(False))])
    if global_config["CHECK"]:
        sys.exit(0)
    if not global_config["DUMMY_RUN"]:
        global_config.add_config_entries([("SERVER_IDX", configfile.int_c_var(sql_s_info.effective_device.pk, database=False))])
        # FIXME
        #global_config.add_config_entries([("LOG_SOURCE_IDX", configfile.int_c_var(process_tools.create_log_source_entry(dc, global_config["SERVER_IDX"], "sge_server", "RMS Server")))])
    if global_config["KILL_RUNNING"]:
        log_lines = process_tools.kill_running_processes(prog_name + ".py", exclude=configfile.get_manager_pid())
    sge_dict = {}
    for v_name, v_src, v_default in [("SGE_ROOT", "/etc/sge_root", "/opt/sge"),
                                     ("SGE_CELL", "/etc/sge_cell", "default" )]:
        if os.path.isfile(v_src):
            sge_dict[v_name] = file(v_src, "r").read().strip()
        else:
            if global_config["FORCE"]:
                sge_dict[v_name] = v_default
            else:
                print "error: Cannot read %s from file %s, exiting..." % (v_name, v_src)
                sys.exit(2)
    stat, sge_dict["SGE_ARCH"], log_lines = call_command("/%s/util/arch" % (sge_dict["SGE_ROOT"]))
    if stat:
        if global_config["FORCE"]:
            sge_dict["SGE_ARCH"] = "lx26_amd64"
        else:
            print "error Cannot evaluate SGE_ARCH"
            sys.exit(1)
    if cluster_location:
        cluster_location.read_config_from_db(global_config, "sge_server", [
            ("CHECK_ITERATIONS"               , configfile.int_c_var(3)),
            ("COM_PORT"                       , configfile.int_c_var(COM_PORT)),
            ("RETRY_AFTER_CONNECTION_PROBLEMS", configfile.int_c_var(0)),
            ("FROM_ADDR"                      , configfile.str_c_var("sge_server")),
            ("TO_ADDR"                        , configfile.str_c_var("lang-nevyjel@init.at")),
            ("SGE_ARCH"                       , configfile.str_c_var(sge_dict["SGE_ARCH"])),#, fixed=True)),
            ("SGE_ROOT"                       , configfile.str_c_var(sge_dict["SGE_ROOT"])),#, fixed=True)),
            ("SGE_CELL"                       , configfile.str_c_var(sge_dict["SGE_CELL"])),#, fixed=True)),
            ("MONITOR_JOBS"                   , configfile.bool_c_var(True)),
            ("TRACE_FAIRSHARE"                , configfile.bool_c_var(False)),
            ("STRICT_MODE"                    , configfile.bool_c_var(False)),
            ("APPEND_SERIAL_COMPLEX"          , configfile.bool_c_var(True)),
            ("CLEAR_ITERATIONS"               , configfile.int_c_var(1)),
            ("CHECK_ACCOUNTING_TIMEOUT"       , configfile.int_c_var(300))],
                                             dummy_run=global_config["DUMMY_RUN"])
    else:
        configfile.read_config_from_db(global_config, None, "sge_server", [
            ("CHECK_ITERATIONS"               , configfile.int_c_var(3)),
            ("COM_PORT"                       , configfile.int_c_var(COM_PORT)),
            ("RETRY_AFTER_CONNECTION_PROBLEMS", configfile.int_c_var(0)),
            ("FROM_ADDR"                      , configfile.str_c_var("sge_server")),
            ("TO_ADDR"                        , configfile.str_c_var("lang-nevyjel@init.at")),
            ("SGE_ARCH"                       , configfile.str_c_var(sge_dict["SGE_ARCH"])),#, fixed=True)),
            ("SGE_ROOT"                       , configfile.str_c_var(sge_dict["SGE_ROOT"])),#, fixed=True)),
            ("SGE_CELL"                       , configfile.str_c_var(sge_dict["SGE_CELL"])),#, fixed=True)),
            ("MONITOR_JOBS"                   , configfile.bool_c_var(True)),
            ("TRACE_FAIRSHARE"                , configfile.bool_c_var(False)),
            ("STRICT_MODE"                    , configfile.bool_c_var(False)),
            ("APPEND_SERIAL_COMPLEX"          , configfile.bool_c_var(True)),
            ("CLEAR_ITERATIONS"               , configfile.int_c_var(1)),
            ("CHECK_ACCOUNTING_TIMEOUT"       , configfile.int_c_var(300))],
                                       dummy_run=global_config["DUMMY_RUN"])
##    if os.path.isfile("/%s/%s/common/product_mode" % (g_config["SGE_ROOT"], g_config["SGE_CELL"])):
##        g_config.add_config_dict({"SGE_VERSION"    : configfile.int_c_var(5),
##                                  "SGE_RELEASE"    : configfile.int_c_var(3),
##                                  "SGE_PATCHLEVEL" : configfile.int_c_var(0)})
##    else:
##        # try to get the actual version
##        qs_com = "/%s/bin/%s/qconf" % (g_config["SGE_ROOT"],
##                                       g_config["SGE_ARCH"])
##        stat, vers_string, log_lines = call_command(qs_com)
##        vers_line = vers_string.split("\n")[0].lower()
##        if vers_line.startswith("ge") or vers_line.startswith("sge"):
##            vers_part = vers_line.split()[1]
##            major, minor = vers_part.split(".")
##            minor, patchlevel = minor.split("u")
##            patchlevel = patchlevel.split("_")[0]
##            g_config.add_config_dict({"SGE_VERSION"    : configfile.int_c_var(int(major)),
##                                      "SGE_RELEASE"    : configfile.int_c_var(int(minor)),
##                                      "SGE_PATCHLEVEL" : configfile.int_c_var(int(patchlevel))})
##        else:
##            if g_config.has_key("SGE_VERSION") and g_config.has_key("SGE_RELEASE") and g_config.has_key("SGE_PATCHLEVEL"):
##                pass
##            else:
##                print "Cannot determine GE Version via %s" % (qs_com)
##                dc.release()
##                sys.exit(-1)

        #log_sources = process_tools.get_all_log_sources(dc)
        #log_status = process_tools.get_all_log_status(dc)
        #process_tools.create_log_source_entry(dc, 0, "sgeflat", "SGE Message (unparsed)", "Info from the SunGridEngine")
    pid_dir = "/var/run/%s" % (os.path.dirname(global_config["PID_NAME"]))
    if pid_dir not in ["/var/run", "/var/run/"]:
        process_tools.fix_directories(global_config["USER"], global_config["GROUP"], [pid_dir])
    process_tools.change_user_group(global_config["USER"], global_config["GROUP"], global_config["GROUPS"], global_config=global_config)
    if not global_config["DEBUG"]:
        process_tools.become_daemon()
        process_tools.set_handles({"out" : (1, "sge-server.out"),
                                   "err" : (0, "/var/lib/logging-server/py_err")})
    else:
        print "Debugging SGE-server"
    ret_state = server_process().loop()
    sys.exit(ret_state)

if __name__ == "__main__":
    main()
