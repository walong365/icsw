#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2010,2011 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of meta-server
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
""" meta-server """

import sys
import os
import os.path
import socket
import time
import optparse
import logging_tools
import process_tools
import mail_tools
import net_tools
import threading_tools
import configfile
import server_command
import stat
from twisted.python import log
from twisted.internet import reactor, task
from twisted.internet.protocol import ConnectedDatagramProtocol, Factory, Protocol

try:
    from meta_server_version import VERSION_STRING
except ImportError:
    VERSION_STRING = "?.?"

class simple_protocol(Protocol):
    def dataReceived(self, data):
        p1_header, data = net_tools.check_for_proto_1_header(data)
        try:
            server_com = server_command.server_command(data)
        except:
            log.msg("error decoding in_str (len %d)" % (len(what)),
                    log_level=logging_tools.LOG_LEVEL_CRITICAL)
            self.transport.loseConnection()
        else:
            server_reply = server_command.server_reply()
            log.msg("got command %s from %s" % (server_com.get_command(),
                                                "?"))
            if server_com.get_command() == "status":
                server_reply.set_ok_result("ok thread is running")
            elif server_com.get_command() == "version":
                server_reply.set_ok_result("version %s" % (VERSION_STRING))
            else:
                server_reply.set_error_result("unknown comand %s" % (server_com.get_command()))
            self.transport.write(net_tools.add_proto_1_header(server_reply, p1_header))
    
class simple_factory(Factory):
    protocol = simple_protocol
    
class check_protocol(ConnectedDatagramProtocol):
    def doStart(self):
        self.sendDatagram()
    def sendDatagram(self):
        self.is_ok = True
        self.transport.write("meta-server-test")
    def connectionFailed(self, why):
        self.is_ok = False

class main_thread(threading_tools.twisted_main_thread):
    def __init__(self, glob_config):
        self.__glob_config = glob_config
        my_observer = logging_tools.twisted_log_observer(self.__glob_config["LOG_NAME"],
                                                         self.__glob_config["LOG_DESTINATION"])
        log.startLoggingWithObserver(my_observer, setStdout=False)
        threading_tools.twisted_main_thread.__init__(self, "main")
        self.install_signal_handlers()
        process_tools.save_pid(self.__glob_config["PID_NAME"])
        # init stuff for mailing
        self.__new_mail = mail_tools.mail(None, "%s@%s" % (self.__glob_config["FROM_NAME"], self.__glob_config["FROM_ADDR"]), self.__glob_config["TO_ADDR"])
        self.__new_mail.set_server(self.__glob_config["MAILSERVER"], self.__glob_config["MAILSERVER"])
        # check
        self.__check_dict = {}
        self.__last_update_time = time.time() - 2 * self.__glob_config["MIN_CHECK_TIME"]
        self.__problem_list = []
        act_commands = self._check_for_new_info([])
        self._do_commands(act_commands)
        self._init_meminfo()
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        log.msg(what, log_level=lev)
    def _sigint(self):
        log.msg("got sigint")
        reactor.stop()
    def _sigterm(self):
        log.msg("got sigterm")
        reactor.stop()
    def run(self):
        self._show_config()
        self.log("starting mainloop")
        try:
            reactor.listenTCP(self.__glob_config["COM_PORT"], simple_factory())
        except:
            self.log("error listening to port %d: %s" % (self.__glob_config["COM_PORT"],
                                                         process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_CRITICAL)
        else:
            loop_task = task.LoopingCall(self._check)
            loop_task.start(60)
            reactor.run()
        self.loop_end()
    def _show_config(self):
        try:
            for log_line, log_level in self.__glob_config.get_log():
                self.log("Config info : [%d] %s" % (log_line, log_level))
        except:
            self.log("error showing configfile log, old configfile ? (%s)" % (process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
        conf_info = self.__glob_config.get_config_info()
        self.log("Found %s:" % (logging_tools.get_plural("valid configline", len(conf_info))))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def loop_end(self):
        process_tools.delete_pid(self.__glob_config["PID_NAME"])
    def loop_function(self):
        self.__check_queue.put("update")
        self.__ns.step()
    def _new_tcp_con(self, sock, src):
        return tcp_receive(self)
    def _do_commands(self, act_commands):
        for act_command in act_commands:
            self._submit_at_command(act_command, 1)
    def _submit_at_command(self, com, when):
        c_stat, log_lines = process_tools.submit_at_command(com, when)
        for line in log_lines:
            self.log(line)
    def _init_meminfo(self):
        self.__last_meminfo_keys, self.__act_meminfo_line = ([], 0)
    def _check_for_new_info(self, problem_list):
        # problem_list: list of problematic blocks we have to check
        change, act_commands = (False, [])
        if os.path.isdir(self.__glob_config["MAIN_DIR"]):
            for fname in os.listdir(self.__glob_config["MAIN_DIR"]):
                full_name = "%s/%s" % (self.__glob_config["MAIN_DIR"], fname)
                if fname == ".command":
                    try:
                        act_commands = [y for y in [x.strip() for x in file(full_name, "r").read().split("\n")] if not y.startswith("#") and y]
                    except:
                        self.log("error reading %s file %s: %s" % (fname, full_name, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                        act_commands = []
                    else:
                        act_time = time.localtime()
                        new_name = "%s_%04d%02d%02d_%02d:%02d:%02d" % (fname, act_time[0], act_time[1], act_time[2], act_time[3], act_time[4], act_time[5])
                        self.log("read %s from %s file %s, renaming to %s" % (logging_tools.get_plural("command", len(act_commands)), fname, full_name, new_name))
                        try:
                            os.rename(full_name, "%s/%s" % (self.__glob_config["MAIN_DIR"], new_name))
                        except:
                            self.log("error renaming %s to %s: %s" % (fname, new_name, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                        else:
                            pass
                elif fname.startswith(".command_"):
                    pass
                elif fname.endswith(".hb"):
                    # ignore heartbeat files
                    pass
                else:
                    fn_dict = dict([(m_block.get_file_name(), m_block) for m_block in self.__check_dict.itervalues()])
                    if not full_name in fn_dict:
                        new_meta_info = process_tools.meta_server_info(full_name)
                        nm_name = new_meta_info.get_name()
                        if nm_name:
                            self.__check_dict[nm_name] = new_meta_info
                            self.log("discovered new meta_info_block for %s (file %s, info: %s)" % (new_meta_info.get_name(), full_name, new_meta_info.get_info()))
                            change = True
                        else:
                            self.log("error reading meta_info_block %s (get_name() returned none)" % (fname),
                                     logging_tools.LOG_LEVEL_ERROR)
                    else:
                        file_time = os.stat(full_name)[stat.ST_MTIME]
                        if file_time > fn_dict[full_name].file_init_time or fname in problem_list:
                            new_meta_info = process_tools.meta_server_info(full_name)
                            nm_name = new_meta_info.get_name()
                            if nm_name:
                                # copy checks_failed info
                                new_meta_info.set_last_check_ok_time(self.__check_dict[nm_name].get_last_check_ok_time())
                                new_meta_info.checks_failed = self.__check_dict[nm_name].checks_failed
                                self.__check_dict[nm_name] = new_meta_info
                                self.log("updated meta_info_block for %s (from file %s, info: %s)" % (new_meta_info.get_name(), full_name, new_meta_info.get_info()))
                                change = True
        del_list = []
        for cname in self.__check_dict.keys():
            full_name = "%s/%s" % (self.__glob_config["MAIN_DIR"], cname)
            if not os.path.isfile(full_name):
                self.log("removed meta_info_block for %s (file %s no longer present)" % (cname, full_name))
                del_list.append(cname)
                change = True
        for d_p in del_list:
            del self.__check_dict[d_p]
        if change:
            all_names = sorted(self.__check_dict.keys())
            self.log("%s present: %s" % (logging_tools.get_plural("meta_info_block", len(all_names)), ", ".join(all_names)))
        return act_commands
    def _check_logging_server(self):
        act_cp = check_protocol()
        # not working correctly, FIXME
        #reactor.connectUNIXDatagram(self.__glob_config["LOG_DESTINATION"].split(":")[1], act_cp)
        #if not act_cp.is_ok and os.path.isfile(self.__glob_config["LOGGING_SERVER_PID"]):
        #    c_stat, log_lines = process_tools.submit_at_command("/etc/init.d/logging-server force-restart")
        #    self.log("Restarting logging-server", logging_tools.LOG_LEVEL_ERROR)
        del act_cp
    def _check(self):
        self._check_logging_server()
        act_time = time.time()
        if abs(act_time - self.__last_update_time) < self.__glob_config["MIN_CHECK_TIME"]:
            self.log("last check only %s ago (%.2f needed), skipping..." % (logging_tools.get_diff_time_str(abs(act_time - self.__last_update_time)),
                                                                            self.__glob_config["MIN_CHECK_TIME"]),
                     logging_tools.LOG_LEVEL_WARN)
        else:
            self.__last_update_time = act_time
            act_commands = self._check_for_new_info(self.__problem_list)
            self._do_commands(act_commands)
            del_list = []
            mem_info_dict = {}
            act_pid_list = process_tools.get_process_id_list(True, True)
            act_pid_dict = process_tools.get_proc_list()
            problem_list = []
            for key, struct in self.__check_dict.iteritems():
                struct.check_block(act_pid_list, act_pid_dict)
                if struct.checks_failed or struct.heartbeat_checks_failed:
                    problem_list.append(key)
                    pids_failed_time      = abs(struct.get_last_check_ok_time() - act_time)
                    heartbeat_failed_time = abs(struct.get_last_heartbeat_check_ok_time() - act_time)
                    do_sthg_pids = (struct.checks_failed           >= 2 and pids_failed_time      > self.__glob_config["FAILED_CHECK_TIME"])
                    do_sthg_hb   = (struct.heartbeat_checks_failed >= 2 and heartbeat_failed_time > self.__glob_config["FAILED_CHECK_TIME"])
                    do_sthg = do_sthg_pids or do_sthg_hb
                    if do_sthg_pids:
                        self.log("*** check failed for %s: %s" % (key, struct.get_problem_str_pids()),
                                 logging_tools.LOG_LEVEL_WARN)
                    if do_sthg_hb:
                        self.log("*** check failed for %s: %s" % (key, struct.get_problem_str_hb()),
                                 logging_tools.LOG_LEVEL_WARN)
                    self.log("*** %s (%d, %d): %s remaining, grace time %s, %s" % (
                        key,
                        struct.checks_failed,
                        struct.heartbeat_checks_failed,
                        logging_tools.get_plural("grace_period", max(0, 2 - max(struct.checks_failed, struct.heartbeat_checks_failed))),
                        logging_tools.get_plural("second", self.__glob_config["FAILED_CHECK_TIME"] - max(pids_failed_time, heartbeat_failed_time)),
                        do_sthg and "starting countermeasures" or "still waiting..."),
                             logging_tools.LOG_LEVEL_WARN)
                    if do_sthg:
                        # first submit the at-commands 
                        if struct.stop_command:
                            self._submit_at_command(struct.stop_command, 1)
                        if struct.start_command:
                            self._submit_at_command(struct.start_command, 2)
                        self.__new_mail.init_text()
                        self.__new_mail.set_subject("problem with %s on %s (meta-server)" % (key, self.__glob_config["SERVER_FULL_NAME"]))
                        self.__new_mail.append_text(["check failed for %s: %s, %s" % (
                            key,
                            struct.get_problem_str_pids() if do_sthg_pids else "pids OK",
                            struct.get_problem_str_hb() if do_sthg_hb else "HB ok"),
                                                     "starting repair sequence",
                                                     ""])
                        self.log("*** starting repair sequence",
                             logging_tools.LOG_LEVEL_WARN)
                        if struct.kill_pids:
                            kill_info = struct.kill_all_found_pids()
                            self.log("  *** kill info: %s" % (kill_info),
                                     logging_tools.LOG_LEVEL_WARN)
                            self.__new_mail.append_text(["trying to kill the remaining pids, kill info : %s" % (kill_info),
                                                         ""])
                        if struct.stop_command:
                            self.__new_mail.append_text(["issued the stop command : %s" % (struct.stop_command),
                                                         ""])
                        if struct.start_command:
                            self.__new_mail.append_text(["issued the start command : %s" % (struct.start_command),
                                                         ""])
                        struct.remove_meta_block()
                        sm_stat, log_lines = self.__new_mail.send_mail()
                        for line in log_lines:
                            self.log(line)
                        del_list.append(key)
                else:
                    # check memory consumption if everything is ok
                    if struct.check_memory:
                        pids = struct.get_unique_pids()
                        if pids:
                            # only count memory for one pid
                            mem_info_dict[key] = process_tools.get_mem_info(pids[0])
                        else:
                            mem_info_dict[key] = 0
            if mem_info_dict:
                self.__act_meminfo_line += 1
                act_meminfo_keys = sorted(mem_info_dict.keys())
                if act_meminfo_keys != self.__last_meminfo_keys or self.__act_meminfo_line > 100:
                    self.__act_meminfo_line = 0
                    self.__last_meminfo_keys = act_meminfo_keys
                    self.log("Memory info mapping: %s" % (", ".join(["%d: %s" % (act_meminfo_keys.index(k) + 1, k) for k in act_meminfo_keys])))
                self.log("Memory info: %s" % (" / ".join([process_tools.beautify_mem_info(mem_info_dict[k], 1) for k in act_meminfo_keys])))

            if del_list:
                del_list.sort()
                self.log("removed %s: %s" % (logging_tools.get_plural("block", len(del_list)), ", ".join(del_list)))
                for d_p in del_list:
                    del self.__check_dict[d_p]

class my_options(optparse.OptionParser):
    def __init__(self, glob_config):
        optparse.OptionParser.__init__(self, version=VERSION_STRING)
        self.__glob_config = glob_config
        self.add_option("-d", action="store_true", dest="debug_mode", default=False, help="run in debug mode (no daemonizing) [%default]")
        self.add_option("-k", action="store_false", dest="kill_running", default=self.__glob_config["KILL_RUNNING"], help="disables killing of already running meta-server [%default]")
        self.add_option("-t", type="str", dest="to_addr", default=self.__glob_config["TO_ADDR"], help="mail address to send error-mails [%default]")
        self.add_option("-p", type="int", dest="com_port", default=self.__glob_config["COM_PORT"], help="port to comunicate [%default]")
    def parse(self):
        options, args = self.parse_args()
        if args:
            print "Additional arguments found, exiting"
            sys.exit(0)
        self.__glob_config["KILL_RUNNING"] = options.kill_running
        self.__glob_config["TO_ADDR"] = options.to_addr
        self.__glob_config["COM_PORT"] = options.com_port
        return options

def main():
    long_host_name = socket.getfqdn(socket.gethostname())
    glob_config = configfile.configuration("meta-server", {"MAILSERVER"         : configfile.str_c_var("localhost", info="Mail Server"),
                                                           "COM_PORT"           : configfile.int_c_var(8012, info="listening Port"),
                                                           "LOG_DESTINATION"    : configfile.str_c_var("uds:/var/lib/logging-server/py_log"),
                                                           "LOG_NAME"           : configfile.str_c_var("meta-server"),
                                                           "MAIN_DIR"           : configfile.str_c_var("/var/lib/meta-server"),
                                                           "FROM_NAME"          : configfile.str_c_var("meta-server"),
                                                           "FROM_ADDR"          : configfile.str_c_var(socket.getfqdn()),
                                                           "TO_ADDR"            : configfile.str_c_var("lang-nevyjel@init.at"),
                                                           "FAILED_CHECK_TIME"  : configfile.int_c_var(120, info="time in seconds to wait befor we do something"),
                                                           "MIN_CHECK_TIME"     : configfile.int_c_var(6, info="minimum time between two checks"),
                                                           "KILL_RUNNING"       : configfile.bool_c_var(True),
                                                           "SERVER_FULL_NAME"   : configfile.str_c_var(long_host_name),
                                                           "PID_NAME"           : configfile.str_c_var("meta-server"),
                                                           "LOGGING_SERVER_PID" : configfile.str_c_var("/var/run/logserver/logserver.pid")})
    pname = os.path.basename(sys.argv[0])
    cf_name = "/etc/sysconfig/meta-server"
    glob_config.parse_file(cf_name)
    # always set FROM_ADDR
    glob_config["FROM_ADDR"] = socket.getfqdn()
    my_parser = my_options(glob_config)
    options = my_parser.parse()
    glob_config.write_file(cf_name, 1)
    if glob_config["KILL_RUNNING"]:
        process_tools.kill_running_processes(pname)
    if glob_config["FROM_ADDR"] in ["linux.site", "localhost", "localhost.localdomain"]:
        glob_config["FROM_ADDR"] = socket.getfqdn()
    process_tools.renice()
    process_tools.fix_directories("root", "root", [(glob_config["MAIN_DIR"], 0777)])
    if not options.debug_mode:
        process_tools.become_daemon()
        process_tools.set_handles({"out" : (1, "meta-server.out"),
                                   "err" : (0, "/var/lib/logging-server/py_err")})
    else:
        print "Debugging meta-server on %s" % (glob_config["SERVER_FULL_NAME"])
    main_thread(glob_config).run()
    sys.exit(0)

if __name__ == "__main__":
    main()
