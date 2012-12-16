#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2012 Andreas Lang-Nevyjel
#
# this file is part of package-client
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
""" daemon to automatically install packages (.rpm, .deb) """

import sys
import os
import configfile
import zmq
import uuid_tools
import server_command
import pprint
import time
import logging_tools
import process_tools
import threading_tools
import subprocess
from lxml import etree
from lxml.builder import E

try:
    from package_client_version import *
except ImportError:
    # instead of unknown-unknown
    VERSION_STRING = "0.0-0"

P_SERVER_COM_PORT   = 8007
PACKAGE_CLIENT_PORT = 2003

LF_NAME = "/var/lock/package_client.lock"

def get_srv_command(**kwargs):
    return server_command.srv_command(
        package_client_version=VERSION_STRING,
        debian="1" if global_config["DEBIAN"] else "0",
        **kwargs)

# copy from command_tools.py (package mother)
class simple_command(object):
    sc_idx = 0
    com_list = []
    stream_dict = {}
    def __init__(self, com_str, **kwargs):
        simple_command.sc_idx += 1
        self.idx = simple_command.sc_idx
        self.com_str = com_str
        # stream_id, None for unsorted
        # streams with the same id are processed strictly in order
        # (for example to feed the DHCP-server)
        self.stream_id, self.stream = (kwargs.get("stream_id", None), None)
        self.__log_com = kwargs.get("log_com", None)
        self.delay_time = kwargs.get("delay_time", 0)
        self.done_func = kwargs.get("done_func", None)
        self.start_time, self.popen = (None, None)
        self.info = kwargs.get("info", None)
        self.max_run_time = kwargs.get("max_run_time", 600)
        self.log("init command %s%s, delay is %s" % (
            "with %s" % (logging_tools.get_plural("line", len(self.com_str.split("\n")))) if kwargs.get("short_info", True) else "'%s'" % (self.com_str),
            " (%s)" % (kwargs.get("add_info", "")) if "add_info" in kwargs else "",
            logging_tools.get_plural("second", self.delay_time)))
        if self.delay_time:
            simple_command.process.register_timer(self.call, self.delay_time, oneshot=True)
        else:
            self.call()
        if "data" in kwargs:
            self.data = kwargs["data"]
        simple_command.com_list.append(self)
    @staticmethod
    def setup(process):
        simple_command.process = process
        simple_command.process.log("init simple_command metastructure")
    @staticmethod
    def check():
        cur_time = time.time()
        new_list = []
        for com in simple_command.com_list:
            keep = True
            if com.start_time:
                if com.finished():
                    com.done()
                    keep = False
                elif abs(cur_time - com.start_time) > com.max_run_time:
                    com.log("maximum runtime exceeded, killing", logging_tools.LOG_LEVEL_ERROR)
                    keep = False
                    com.terminate()
            if keep:
                new_list.append(com)
        simple_command.com_list = new_list
    @staticmethod
    def idle():
        return True if not simple_command.com_list else False
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        if self.__log_com:
            self.__log_com("[sc %d] %s" % (self.idx, what), log_level)
        else:
            simple_command.process.log("[sc %d] %s" % (self.idx, what), log_level)
    def terminate(self):
        if self.popen:
            del self.popen
    def finished(self):
        self.result = self.popen.poll()
        return self.result != None
    def read(self):
        if self.popen:
            return self.popen.stdout.read()
        else:
            return None
    def done(self):
        self.end_time = time.time()
        if self.done_func:
            self.done_func(self)
        else:
            simple_command.process.sc_finished(self)
        if self.stream:
            self.stream.done()
    def call(self):
        self.start_time = time.time()
        self.popen = subprocess.Popen(self.com_str, shell=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
            
class install_process(threading_tools.process_obj):
    """ handles all install and external command stuff """
    def __init__(self, name):
        threading_tools.process_obj.__init__(
            self,
            name,
            loop_timer=1000.0)
        self.commands = []
        self.register_func("command_batch", self._command_batch)
        # commands pending becaus of missing package list
        self.pending_commands = []
        # list of pending package commands
        self.package_commands = []
        self.register_timer(self._check_commands, 10)
    @property
    def packages(self):
        return self._packages
    @packages.setter
    def packages(self, in_list):
        self._packages = in_list
        self.packages_valid = True
        self.handle_pending_commands()
    @packages.deleter
    def packages(self):
        if self.packages_valid:
            self.packages_valid = False
            del self._packages
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            zmq_debug=global_config["ZMQ_DEBUG"],
            context=self.zmq_context,
            init_logger=True)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def loop_post(self):
        self.__log_template.close()
    def _command_batch(self, com_list, *args, **kwargs):
        com_list = [server_command.srv_command(source=cur_com) for cur_com in com_list]
        self.pending_commands.extend(com_list)
        self.handle_pending_commands()
    def send_to_server(self, send_xml, info_str="no info"):
        self.send_pool_message("send_to_server", send_xml["command"].text, unicode(send_xml), info_str)
    def package_command_done(self, t_com):
        self.package_commands.remove(t_com)
        self.handle_pending_commands()
    def _check_commands(self):
        simple_command.check()
        if simple_command.idle():
            self.set_loop_timer(1000)
    def _process_commands(self):
        if simple_command.idle():
            self.register_timer(self._check_commands, 1)
        # check if any commands are pending
        not_init = [cur_com for cur_com in self.package_commands if not int(cur_com.get("init"))]
        if not_init:
            cur_init = not_init[0]
            cur_init.attrib["init"] = "1"
            cur_com_str = self.build_command(cur_init)
            if cur_com_str is not None:
                simple_command(
                    cur_com_str,
                    short_info="package",
                    done_func=self._command_done,
                    log_com=self.log,
                    info="install package",
                    data=cur_init)
            else:
                self.pdc_done(cur_init, E.info("nothing to do"))
    def build_command(self, cur_pdc):
        #print etree.tostring(cur_pdc, pretty_print=True)
        if cur_pdc.attrib["target_state"] == "keep":
            # nothing to do
            zypper_com = None
        else:
            pack_xml = cur_pdc[0]
            zypper_com = {"install" : "in",
                          "upgrade" : "up",
                          "erase"   : "rm"}.get(cur_pdc.attrib["target_state"])
            zypper_com = "/usr/bin/zypper -q -x -n --no-refresh %s %s-%s" % (
                zypper_com,
                pack_xml.attrib["name"],
                pack_xml.attrib["version"],
            )
            self.log("transformed pdc to '%s'" % (zypper_com))
        return zypper_com
    def _command_done(self, hc_sc):
        cur_out = hc_sc.read()
        if cur_out.startswith("<?xml"):
            xml_out = etree.fromstring(cur_out)
        else:
            # todo: transform output to XML for sending back to server
            xml_out = None
        self.log("hc_com finished with stat %d (%d bytes)" % (
            hc_sc.result,
            len(cur_out)))
        for line_num, line in enumerate(cur_out.split("\n")):
            self.log(" %3d %s" % (line_num + 1, line))
        hc_sc.terminate()
        # remove from package_commands
        self.pdc_done(hc_sc.data, xml_out)
        del hc_sc
    def pdc_done(self, cur_pdc, xml_info):
        self.log("pdc done")
        if xml_info is not None:
            cur_pdc.append(E.result(xml_info))
            cur_pdc.attrib["response_type"] = "zypper_xml"
        else:
            cur_pdc.attrib["response_type"] = "unknown"
        srv_com = server_command.srv_command(
            command="package_info",
            info=cur_pdc)
        self.send_to_server(srv_com)
        new_list = [cur_com for cur_com in self.package_commands if cur_com != cur_pdc]
        self.package_commands = new_list
        self._process_commands()
    def handle_pending_commands(self):
        while self.pending_commands and not self.package_commands:
            # now the fun starts, we have a list of commands and a valid local package list
            first_com = self.pending_commands.pop(0)
            cur_com = first_com["command"].text
            self.log("try to handle %s" % (cur_com))
            if cur_com in ["send_info"]:
                self.log("... ignoring", logging_tools.LOG_LEVEL_WARN)
            elif cur_com in ["package_list"]:
                if len(first_com.xpath(None, ".//ns:packages/package_device_connection")):
                    # clever enqueue ? FIXME
                    for cur_pdc in first_com.xpath(None, ".//ns:packages/package_device_connection"):
                        # set flag to not init
                        cur_pdc.attrib["init"] = "0"
                        self.package_commands.append(cur_pdc)
                    self.log(logging_tools.get_plural("package command", len(self.package_commands)))
                    self._process_commands()
                else:
                    self.log("empty package_list, removing")
    
class server_process(threading_tools.process_pool):
    def __init__(self):
        self.global_config = global_config
        self.__log_cache, self.__log_template = ([], None)
        threading_tools.process_pool.__init__(self, "main", zmq=True,
            zmq_debug=global_config["ZMQ_DEBUG"]
            )
        if not global_config["DEBUG"]:
            process_tools.set_handles({"out" : (1, "package_client.out"),
                                       "err" : (0, "/var/lib/logging-server/py_err")},
                                       zmq_context=self.zmq_context)
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self.install_signal_handlers()
        # init environment
        self._init_environment()
        self._init_msi_block()
        self.register_exception("int_error"  , self._int_error)
        self.register_exception("term_error" , self._int_error)
        self.register_exception("alarm_error", self._alarm_error)
        # set lockfile
        process_tools.set_lockfile_msg(LF_NAME, "connect...")
        # log buffer
        self._show_config()
        # log limits
        self._log_limits()
        self._init_network_sockets()
        self.register_func("send_to_server", self._send_to_server)
        self.add_process(install_process("install"), start=True)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            while self.__log_cache:
                cur_lev, cur_what = self.__log_cache.pop(0)
                self.__log_template.log(cur_lev, cur_what)
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))
    def _init_environment(self):
        # Debian fix to get full package names, sigh ...
        os.environ["COLUMNS"] = "2000"
    def _init_msi_block(self):
        # store pid name because global_config becomes unavailable after SIGTERM
        self.__pid_name = global_config["PID_NAME"]
        process_tools.save_pids(global_config["PID_NAME"], mult=3)
        process_tools.append_pids(global_config["PID_NAME"], pid=configfile.get_manager_pid(), mult=3)
        if True:#not self.__options.DEBUG:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("package-client")
            msi_block.add_actual_pid(mult=3)
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=3)
            msi_block.start_command = "/etc/init.d/package-client start"
            msi_block.stop_command = "/etc/init.d/package-client force-stop"
            msi_block.kill_pids = True
            #msi_block.heartbeat_timeout = 60
            msi_block.save_block()
        else:
            msi_block = None
        self.__msi_block = msi_block
    def _show_config(self):
        try:
            for log_line, log_level in global_config.get_log():
                self.log("Config info : [%d] %s" % (log_level, log_line))
        except:
            self.log("error showing configfile log, old configfile ? (%s)" % (process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
        conf_info = global_config.get_config_info()
        self.log("Found %s:" % (logging_tools.get_plural("valid configline", len(conf_info))))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def _log_limits(self):
        # read limits
        r_dict = {}
        try:
            import resource
        except ImportError:
            self.log("cannot import resource", logging_tools.LOG_LEVEL_CRITICAL)
        else:
            available_resources = [key for key in dir(resource) if key.startswith("RLIMIT")]
            for av_r in available_resources:
                try:
                    r_dict[av_r] = resource.getrlimit(getattr(resource, av_r))
                except ValueError:
                    r_dict[av_r] = "invalid resource"
                except:
                    r_dict[av_r] = None
            if r_dict:
                res_keys = sorted(r_dict.keys())
                self.log("%s defined" % (logging_tools.get_plural("limit", len(res_keys))))
                res_list = logging_tools.new_form_list()
                for key in res_keys:
                    val = r_dict[key]
                    if type(val) == type(""):
                        info_str = val
                    elif type(val) == type(()):
                        info_str = "%8d (hard), %8d (soft)" % val
                    else:
                        info_str = "None (error?)"
                    res_list.append([logging_tools.form_entry(key, header="key"),
                                     logging_tools.form_entry(info_str, header="value")])
                for line in str(res_list).split("\n"):
                    self.log(line)
            else:
                self.log("no limits found, strange ...", logging_tools.LOG_LEVEL_WARN)
    def _init_network_sockets(self):
        # connect to server
        srv_port = self.zmq_context.socket(zmq.DEALER)
        srv_port.setsockopt(zmq.LINGER, 1000)
        srv_port.setsockopt(zmq.IDENTITY, uuid_tools.get_uuid().get_urn())
        #srv_port.setsockopt(zmq.SUBSCRIBE, "")
        self.conn_str = "tcp://%s:%d" % (
            global_config["PACKAGE_SERVER"],
            global_config["SERVER_COM_PORT"])
        srv_port.connect(self.conn_str)
        #pull_port = self.zmq_context.socket(zmq.PUSH)
        #pull_port.setsockopt(zmq.IDENTITY, uuid_tools.get_uuid().get_urn())
        self.register_poller(srv_port, zmq.POLLIN, self._recv)
        self.log("connected to %s" % (self.conn_str))
        self.srv_port = srv_port
        self._send_to_server_int(get_srv_command(command="register"))
        self._get_new_config()
    def _send_to_server_int(self, xml_com):
        self._send_to_server("self", os.getpid(), xml_com["command"].text, unicode(xml_com), "server command")
    def _send_to_server(self, src_proc, *args, **kwargs):
        src_pid, com_name, send_com, send_info = args
        self.log("sending %s (%s) to server %s" % (com_name, send_info, self.conn_str))
        self.srv_port.send_unicode(send_com)
    def _get_new_config(self):
        self._send_to_server_int(get_srv_command(command="get_package_list"))
        self._send_to_server_int(get_srv_command(command="get_rsync_list"))
    def _recv(self, zmq_sock):
        batch_list = []
        while True:
            data = []
            while True:
                try:
                    in_com = server_command.srv_command(source=zmq_sock.recv_unicode())
                except:
                    self.log("error decoding command: %s" % (process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                else:
                    rcv_com = in_com["command"].text
                    self.log("got command %s" % (rcv_com))
                    if rcv_com == "new_config":
                        self._get_new_config()
                    else:
                        data.append(in_com)
                if not zmq_sock.getsockopt(zmq.RCVMORE):
                    break
            batch_list.extend(data)
            if not zmq_sock.poll(zmq.POLLIN):
                break
        #batch_list = self._optimize_list(batch_list)
        self.send_to_process("install",
                             "command_batch",
                             [unicode(cur_com) for cur_com in batch_list])
    #def _optimize_list(self, in_list):
    #    return in_list
    def _int_error(self, err_cause):
        self.__exit_cause = err_cause
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("got int_error, err_cause is '%s'" % (err_cause), logging_tools.LOG_LEVEL_WARN)
            self["exit_requested"] = True
    def _alarm_error(self, err_cause):
        self.__comsend_queue.put("reload")
    def loop_end(self):
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
    def loop_post(self):
        self.srv_port.close()
        self.__log_template.close()
    
global_config = configfile.get_global_config(process_tools.get_programm_name())

def main():
    process_tools.delete_lockfile(LF_NAME, None, 0)
    prog_name = global_config.name()
    global_config.add_config_entries([
        ("PID_NAME"               , configfile.str_c_var("%s/%s" % (prog_name, prog_name))),
        ("DEBUG"                  , configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("ZMQ_DEBUG"              , configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
        ("VERBOSE"                , configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ("KILL_RUNNING"           , configfile.bool_c_var(True)),
        ("POLL_INTERVALL"         , configfile.int_c_var(5, help_string="poll intervall")),
        ("EXIT_ON_FAIL"           , configfile.bool_c_var(False, help_string="exit on fail [%(default)s]")),
        ("COM_PORT"               , configfile.int_c_var(PACKAGE_CLIENT_PORT, help_string="node to bind to [%(default)d]")),
        ("SERVER_COM_PORT"          , configfile.int_c_var(P_SERVER_COM_PORT, help_string="server com port [%(default)d]")),
        ("LOG_DESTINATION"        , configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME"               , configfile.str_c_var(prog_name)),
        ("VAR_DIR"                , configfile.str_c_var("/var/lib/cluster/package-client", help_string="location of var-directory [%(default)s]")),
        ("PACKAGE_SERVER_FILE"    , configfile.str_c_var("/etc/packageserver", help_string="filename where packageserver location is stored [%(default)s]"))
    ])
    global_config.parse_file()
    options = global_config.handle_commandline(description="%s, version is %s" % (prog_name,
                                                                                  VERSION_STRING),
                                               add_writeback_option=True,
                                               positional_arguments=False,
                                               partial=False)
    ps_file_name = global_config["PACKAGE_SERVER_FILE"]
    if not os.path.isfile(ps_file_name):
        try:
            file(ps_file_name, "w").write("localhost\n")
        except:
            print "error writing to %s: %s" % (ps_file_name, process_tools.get_except_info())
            sys.exit(5)
        else:
            pass
    try:
        global_config.add_config_entries([
            ("PACKAGE_SERVER", configfile.str_c_var(file(ps_file_name, "r").read().strip().split("\n")[0].strip()))
        ])
    except:
        print "error reading from %s: %s" % (ps_file_name, process_tools.get_except_info())
        sys.exit(5)
    global_config.add_config_entries([("DEBIAN", configfile.bool_c_var(os.path.isfile("/etc/debian_version")))])
    if global_config["KILL_RUNNING"]:
        process_tools.kill_running_processes(exclude=configfile.get_manager_pid())
    process_tools.fix_directories(0, 0, [global_config["VAR_DIR"]])
    process_tools.renice()
    if not global_config["DEBUG"]:
        process_tools.become_daemon(mother_hook = process_tools.wait_for_lockfile, mother_hook_args = (LF_NAME, 5, 200))
    else:
        print "Debugging %s on %s" % (prog_name, process_tools.get_machine_name())
        # no longer needed
        #global_config["LOG_DESTINATION"] = "stdout"
    ret_code = server_process().loop()
    process_tools.delete_lockfile(LF_NAME, None, 0)
    sys.exit(ret_code)

if __name__ == "__main__":
    main()
