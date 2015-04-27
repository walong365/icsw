# Copyright (C) 2001-2009,2012-2015 Andreas Lang-Nevyjel
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

from initat.package_install.client.config import global_config
from initat.package_install.client.install_process import yum_install_process, zypper_install_process, \
    get_srv_command
from initat.tools import configfile
from initat.tools import logging_tools
import os
from initat.tools import process_tools
from initat.tools import server_command
from initat.tools import threading_tools
import time
from initat.tools import uuid_tools
import zmq


class server_process(threading_tools.process_pool):
    def __init__(self):
        self.global_config = global_config
        self.__log_cache, self.__log_template = ([], None)
        threading_tools.process_pool.__init__(
            self,
            "main",
            zmq=True,
            zmq_debug=global_config["ZMQ_DEBUG"]
        )
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        # self.renice(global_config["NICE_LEVEL"])
        self.install_signal_handlers()
        # init environment
        self._init_environment()
        self._init_msi_block()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("alarm_error", self._alarm_error)
        # log buffer
        self._show_config()
        # send buffer
        self.__send_buffer = []
        # log limits
        self._log_limits()
        self._set_resend_timeout(None)
        if self._get_package_server_id():
            self._init_network_sockets()
            self.register_func("send_to_server", self._send_to_server)
            if os.path.isfile("/etc/centos-release") or os.path.isfile("/etc/redhat-release"):
                self.add_process(yum_install_process("install"), start=True)
            else:
                self.add_process(zypper_install_process("install"), start=True)
        else:
            self.client_socket = None
            self._int_error("no package_server id")

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
        if True:  # not self.__options.DEBUG:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("package-client")
            msi_block.add_actual_pid(mult=3, fuzzy_ceiling=4, process_name="main")
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=3, process_name="manager")
            msi_block.kill_pids = True
            msi_block.save_block()
        else:
            msi_block = None
        self.__msi_block = msi_block

    def _show_config(self):
        for log_line, log_level in global_config.get_log():
            self.log("Config info : [{:d}] {}".format(log_level, log_line))
        conf_info = global_config.get_config_info()
        self.log("Found {}:".format(logging_tools.get_plural("valid configline", len(conf_info))))
        for conf in conf_info:
            self.log("Config : {}".format(conf))

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
                self.log("{} defined".format(logging_tools.get_plural("limit", len(res_keys))))
                res_list = logging_tools.new_form_list()
                for key in res_keys:
                    val = r_dict[key]
                    if isinstance(val, basestring):
                        info_str = val
                    elif type(val) is tuple:
                        info_str = "{:8d} (hard), {:8d} (soft)".format(*val)
                    else:
                        info_str = "None (error?)"
                    res_list.append([logging_tools.form_entry(key, header="key"),
                                     logging_tools.form_entry(info_str, header="value")])
                for line in str(res_list).split("\n"):
                    self.log(line)
            else:
                self.log("no limits found, strange ...", logging_tools.LOG_LEVEL_WARN)

    def _get_package_server_id(self):
        self.srv_conn_str = "tcp://{}:{:d}".format(
            global_config["PACKAGE_SERVER"],
            global_config["SERVER_COM_PORT"]
        )
        ps_id_file_name = global_config["PACKAGE_SERVER_ID_FILE"]
        if not os.path.exists(ps_id_file_name):
            _result = self._get_package_server_id_from_server()
            if _result is not None:
                _server_id = _result["*zmq_id"]
                self.log(
                    "got server_id {} from server, writing to {}".format(
                        _server_id,
                        ps_id_file_name,
                    )
                )
                file(ps_id_file_name, "w").write(_server_id)
        if os.path.exists(ps_id_file_name):
            self.__package_server_id = file(ps_id_file_name, "r").read().strip()
            return True
        else:
            return False

    def _get_package_server_id_from_server(self):
        check_sock = process_tools.get_socket(
            self.zmq_context,
            "DEALER",
            identity="{}:ptest:".format(uuid_tools.get_uuid().get_urn()),
        )
        check_sock.connect(self.srv_conn_str)
        self.log("fetch srv_id socket, connected to {}".format(self.srv_conn_str))
        check_sock.send_unicode(unicode(server_command.srv_command(command="get_0mq_id")))
        _timeout = 10
        my_poller = zmq.Poller()
        my_poller.register(check_sock, zmq.POLLIN)  # @UndefinedVariable
        s_time = time.time()
        _last_log = time.time()
        while True:
            _list = my_poller.poll(2)
            if _list:
                _result = server_command.srv_command(source=check_sock.recv_unicode())
                break
            cur_time = time.time()
            if cur_time > s_time + _timeout:
                self.log("timeout, exiting ...", logging_tools.LOG_LEVEL_ERROR)
                _result = None
                break
            else:
                if abs(cur_time - _last_log) > 0.5:
                    _last_log = cur_time
                    self.log(
                        "timeout, still waiting ({:.2f} of {:.2f})".format(
                            abs(cur_time - s_time),
                            _timeout,
                        ),
                        logging_tools.LOG_LEVEL_WARN
                    )
        my_poller.unregister(check_sock)
        del my_poller
        check_sock.close()
        del check_sock
        return _result

    def _init_network_sockets(self):
        # socket
        self.bind_id = "{}:pclient:".format(uuid_tools.get_uuid().get_urn())
        self.log("connected to {}".format(self.srv_conn_str))
        client_sock = process_tools.get_socket(
            self.zmq_context,
            "ROUTER",
            identity=self.bind_id,
        )
        bind_str = "tcp://0.0.0.0:{:d}".format(
            global_config["COM_PORT"]
        )
        client_sock.bind(bind_str)
        client_sock.connect(self.srv_conn_str)
        self.log("bound to {} (ID {})".format(bind_str, self.bind_id))
        self.client_socket = client_sock
        self.register_poller(client_sock, zmq.POLLIN, self._recv_client)  # @UndefinedVariable
        # send commands
        self._register()
        self._get_repos()
        self._get_new_config()

    def _check_send_buffer(self):
        new_buffer = []
        _send_ok = 0
        _success = True
        for _msg in self.__send_buffer:
            if _success:
                try:
                    self.client_socket.send_unicode(self.__package_server_id, zmq.SNDMORE)  # @UndefinedVariable
                    self.client_socket.send_unicode(_msg)
                except zmq.error.ZMQError:
                    _success = False
                    new_buffer.append(_msg)
                else:
                    _send_ok += 1
            else:
                new_buffer.append(_msg)
        self.__send_buffer = new_buffer
        self.log("trying to resend {}: {:d} ok, {:d} still pending".format(
            logging_tools.get_plural("message", len(self.__send_buffer)),
            _send_ok,
            len(self.__send_buffer),
            )
        )
        # print len(self.__send_buffer)
        if not self.__send_buffer:
            self._set_resend_timeout(300)

    def _set_resend_timeout(self, cur_to):
        if cur_to is None:
            self.__rst = 0
        else:
            if cur_to != self.__rst:
                if self.__rst:
                    self.log("changing check_send_buffer timeout from {:d} to {:d} secs".format(self.__rst, cur_to))
                    self.unregister_timer(self._check_send_buffer)
                else:
                    self.log("setting check_send_buffer timeout to {:d} secs".format(cur_to))
                self.register_timer(self._check_send_buffer, cur_to)
                self.__rst = cur_to

    def _send_to_server_int(self, xml_com):
        self._send_to_server("self", os.getpid(), xml_com["command"].text, unicode(xml_com), "server command")

    def _send_to_server(self, src_proc, *args, **kwargs):
        _src_pid, com_name, send_com, send_info = args
        self.log(
            "sending {} ({}) to server {}".format(
                com_name,
                send_info,
                self.srv_conn_str
            )
        )
        try:
            self.client_socket.send_unicode(self.__package_server_id, zmq.SNDMORE)  # @UndefinedVariable
            self.client_socket.send_unicode(send_com)
        except zmq.error.ZMQError:
            self.__send_buffer.append(send_com)
            self.log("error sending message to server, buffering ({:d})".format(len(self.__send_buffer)))
            self._set_resend_timeout(10)

    def _register(self):
        self._send_to_server_int(get_srv_command(command="register"))

    def _get_new_config(self):
        self._send_to_server_int(get_srv_command(command="get_package_list"))
        # self._send_to_server_int(get_srv_command(command="get_rsync_list"))

    def _get_repos(self):
        self._send_to_server_int(get_srv_command(command="get_repo_list"))

    def _recv_client(self, zmq_sock):
        data = [zmq_sock.recv()]
        while zmq_sock.getsockopt(zmq.RCVMORE):  # @UndefinedVariable
            data.append(zmq_sock.recv())
        batch_list = []
        if len(data) == 2:
            src_id = data.pop(0)
            data = data[0]
            try:
                srv_com = server_command.srv_command(source=data)
            except:
                self.log(
                    "error decoding command from {}: {}, '{}'".format(
                        src_id,
                        process_tools.get_except_info(),
                        data[:30],
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                send_reply = True
                srv_com.update_source()
                cur_com = srv_com["command"].text
                self.log("got {} (length: {:d}) from {}".format(cur_com, len(data), src_id))
                srv_com["result"] = None
                if cur_com == "get_0mq_id":
                    srv_com["zmq_id"] = self.bind_id
                    srv_com.set_result(
                        "0MQ_ID is {}".format(self.bind_id)
                    )
                elif cur_com == "status":
                    # FIXME, Todo
                    srv_com.set_result(
                        "everything OK :-)"
                    )
                elif cur_com == "new_config":
                    # no reply for this command
                    send_reply = False
                    self._get_new_config()
                elif cur_com == "sync_repos":
                    # no reply for this command
                    send_reply = False
                    self._get_repos()
                else:
                    # no reply for this command
                    send_reply = False
                    batch_list.append(srv_com)
                if send_reply:
                    self.log("send reply for command {}".format(cur_com))
                    zmq_sock.send_unicode(src_id, zmq.SNDMORE)  # @UndefinedVariable
                    zmq_sock.send_unicode(unicode(srv_com))
                del srv_com
        else:
            self.log(
                "cannot receive more data, already got '{}'".format(
                    ", ".join(data)
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        if batch_list:
            self.log("... batch list valid ({})".format(batch_list[0]["*command"]))
            self.send_to_process(
                "install",
                "command_batch",
                [
                    unicode(cur_com) for cur_com in batch_list
                ]
            )

    def _int_error(self, err_cause):
        self.__exit_cause = err_cause
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("got int_error, err_cause is '{}'".format(err_cause), logging_tools.LOG_LEVEL_WARN)
            self["exit_requested"] = True

    def _alarm_error(self, err_cause):
        self.__comsend_queue.put("reload")

    def loop_end(self):
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()

    def loop_post(self):
        if self.client_socket:
            self.client_socket.close()
        self.__log_template.close()
