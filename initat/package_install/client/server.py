# Copyright (C) 2001-2009,2012-2017 Andreas Lang-Nevyjel
#
# this file is part of package-client
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
""" daemon to automatically install packages (.rpm, .deb) """

import os
import time

import zmq

from initat.client_version import VERSION_STRING
from initat.host_monitoring.client_enums import icswServiceEnum
from initat.tools import logging_tools, process_tools, server_command, \
    threading_tools, uuid_tools, server_mixins
from initat.tools.server_mixins import RemoteCall
from .installprocess import YumInstallProcess, ZypperInstallProcess, DebianInstallProcess


@server_mixins.RemoteCallProcess
class server_process(server_mixins.ICSWBasePool, server_mixins.RemoteCallMixin):
    def __init__(self, global_config):
        threading_tools.icswProcessPool.__init__(
            self,
            "main",
            zmq=True,
            global_config=global_config,
        )
        self.CC.init(icswServiceEnum.package_client, self.global_config)
        self.CC.check_config(client=True)
        self.install_signal_handlers()
        # init environment
        self._init_environment()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("alarm_error", self._alarm_error)
        # log buffer
        self.CC.log_config()
        # log limits
        self._log_limits()
        self._set_resend_timeout(None)
        if self._get_package_server_id():
            self.register_func("send_to_server", self._send_to_server)
            if os.path.isfile("/etc/centos-release") or os.path.isfile("/etc/redhat-release"):
                self.add_process(YumInstallProcess("install"), start=True)
            elif os.path.isfile("/etc/debian_version"):
                self.add_process(DebianInstallProcess("install"), start=True)
            else:
                self.add_process(ZypperInstallProcess("install"), start=True)
            self.register_timer(self.connection_ok_test, 10)
            self.init_network_sockets()
        else:
            self.main_socket = None
            self._int_error("no package_server id")

    def get_srv_command(self, **kwargs):
        return server_command.srv_command(
            package_client_version=VERSION_STRING,
            debian="1" if self.global_config["DEBIAN"] else "0",
            **kwargs
        )

    def _init_environment(self):
        # Debian fix to get full package names, sigh ...
        os.environ["COLUMNS"] = "2000"

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
                res_list = logging_tools.NewFormList()
                for key in res_keys:
                    val = r_dict[key]
                    if isinstance(val, str):
                        info_str = val
                    elif isinstance(val, tuple):
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
            self.global_config["PACKAGE_SERVER"],
            self.CC.CS["pc.server.com.port"],
        )
        ps_id_file_name = "/etc/packageserver_id"
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
                open(ps_id_file_name, "w").write(_server_id)
        if os.path.exists(ps_id_file_name):
            self.__package_server_id = open(ps_id_file_name, "r").read().strip()
            return True
        else:
            return False

    def _get_package_server_id_from_server(self):
        check_sock = process_tools.get_socket(
            self.zmq_context,
            "DEALER",
            identity="{}:ptest:".format(uuid_tools.get_uuid().urn),
        )
        check_sock.connect(self.srv_conn_str)
        self.log("fetch srv_id socket, connected to {}".format(self.srv_conn_str))
        check_sock.send_unicode(str(server_command.srv_command(command="get_0mq_id")))
        _timeout = 10
        my_poller = zmq.Poller()
        my_poller.register(check_sock, zmq.POLLIN)
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

    def init_network_sockets(self):
        # send buffer
        self.__send_buffer = []
        # socket
        self.network_bind(
            bind_port=self.global_config["COMMAND_PORT"],
            bind_to_localhost=True,
            pollin=self.remote_call,
            client_type=icswServiceEnum.package_client,
        )
        self.main_socket.connect(self.srv_conn_str)
        self.network_info = {"ok": 0, "error": 0, "total": 0}
        self.__got_response_from_server = False
        # send commands
        self._register()
        self._get_repos()
        self._get_new_config()

    def connection_ok_test(self):
        self.unregister_timer(self.connection_ok_test)
        if not self.__got_response_from_server:
            self.log("got no response from server, exiting...")
            self._int_error("no server response")

    def _send_to_server_ll(self, send_com):
        self.network_info["total"] += 1
        try:
            self.main_socket.send_unicode(self.__package_server_id, zmq.SNDMORE)
            self.main_socket.send_unicode(send_com)
        except zmq.error.ZMQError:
            self.network_info["error"] += 1
            self.log(
                "error sending message to server {}, buffering ({:d} bytes, {})".format(
                    self.__package_server_id,
                    len(str(send_com)),
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            _success = False
            self._show_network_info()
        else:
            self.network_info["ok"] += 1
            _success = True
        return _success

    def _send_to_server(self, src_proc, *args, **kwargs):
        _src_pid, com_name, send_com, send_info = args
        self.log(
            "sending {} ({}) to server {}".format(
                com_name,
                send_info,
                self.srv_conn_str
            )
        )
        if not self._send_to_server_ll(send_com):
            self.__send_buffer.append(send_com)
            self._set_resend_timeout(10)

    def _show_network_info(self):
        self.log(
            "send info: {}".format(
                ", ".join(
                    [
                        "{}={:d}".format(
                            _key,
                            _value
                        ) for _key, _value in self.network_info.items()
                    ]
                )
            )
        )

    def _check_send_buffer(self):
        if not self.network_info["ok"] and False:
            self.log(
                "no sends were ok, exiting ...",
                logging_tools.LOG_LEVEL_ERROR
            )
            self._int_error("network send error")
        new_buffer = []
        _send_ok = 0
        _success = True
        _num_to_send = len(self.__send_buffer)
        self._show_network_info()
        for _msg in self.__send_buffer:
            if _success:
                if self._send_to_server_ll(_msg):
                    _send_ok += 1
                else:
                    _success = False
                    new_buffer.append(_msg)
            else:
                new_buffer.append(_msg)
        self.__send_buffer = new_buffer
        self.log(
            "info after resending {} from buffer: {:d} sent, {:d} still pending".format(
                logging_tools.get_plural("message", _num_to_send),
                _send_ok,
                len(self.__send_buffer),
            )
        )
        # print len(self.__send_buffer)
        if not self.__send_buffer:
            self._set_resend_timeout(0)

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
                if cur_to:
                    self.register_timer(self._check_send_buffer, cur_to)
                self.__rst = cur_to

    def _send_to_server_int(self, xml_com):
        self._send_to_server("self", os.getpid(), xml_com["command"].text, str(xml_com), "server command")

    def _register(self):
        self._send_to_server_int(self.get_srv_command(command="register"))

    def _get_new_config(self):
        self._send_to_server_int(self.get_srv_command(command="get_package_list"))
        # self._send_to_server_int(self.get_srv_command(command="get_rsync_list"))

    def _get_repos(self):
        self._send_to_server_int(self.get_srv_command(command="get_repo_list"))

    @RemoteCall()
    def status(self, srv_com, **kwargs):
        return self.server_status(srv_com, self.CC.msi_block, self.global_config)

    @RemoteCall()
    def get_0mq_id(self, srv_com, **kwargs):
        srv_com["zmq_id"] = self.bind_id
        srv_com.set_result("0MQ_ID is {}".format(self.bind_id))
        return srv_com

    @RemoteCall()
    def get_package_list(self, srv_com, **kwargs):
        self.__got_response_from_server = True
        self._new_batch_list(srv_com)
        return None

    @RemoteCall()
    def package_list(self, srv_com, **kwargs):
        self.__got_response_from_server = True
        self._new_batch_list(srv_com)
        return None

    @RemoteCall()
    def clear_cache(self, srv_com, **kwargs):
        self.__got_response_from_server = True
        self._new_batch_list(srv_com)
        return None

    @RemoteCall()
    def get_repo_list(self, srv_com, **kwargs):
        self.__got_response_from_server = True
        self._new_batch_list(srv_com)
        return None

    @RemoteCall()
    def repo_list(self, srv_com, **kwargs):
        self.__got_response_from_server = True
        self._new_batch_list(srv_com)
        return None

    def _new_batch_list(self, srv_com):
        self.log("... batch list valid ({})".format(srv_com["*command"]))
        self.send_to_process(
            "install",
            "command_batch",
            [
                str(srv_com)
            ]
        )

    @RemoteCall()
    def sync_repos(self, srv_com, **kwargs):
        self.__got_response_from_server = True
        self._get_repos()
        return None

    @RemoteCall()
    def new_config(self, srv_com, **kwargs):
        self.__got_response_from_server = True
        self._get_new_config()
        return None

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
        pass

    def loop_post(self):
        if self.main_socket:
            self.network_unbind()
        self.CC.close()
