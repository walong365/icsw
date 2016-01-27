# Copyright (C) 2009-2016 Andreas Lang-Nevyjel
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
""" SNMP relayer, server part """

import difflib
import os
import socket
import time

import zmq

from initat.host_monitoring import limits
from initat.snmp.process import snmp_process_container
from initat.snmp.sink import SNMPSink
from initat.snmp_relay.config import global_config, IPC_SOCK_SNMP
from initat.snmp_relay.schemes import SNMPNetObject, SNMPGeneralScheme, snmp_schemes, import_errors
from initat.tools import configfile, logging_tools, process_tools, \
    server_command, threading_tools


class server_process(threading_tools.process_pool):
    def __init__(self):
        self.__verbose = global_config["VERBOSE"]
        self.__log_cache, self.__log_template = ([], None)
        threading_tools.process_pool.__init__(
            self,
            "main",
            zmq=True,
        )
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self._init_msi_block()
        self._init_ipc_sockets()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("hup_error", self._hup_error)
        self.register_func("int_error", self._int_error)
        self.register_func("snmp_finished", self._snmp_finished)
        self.__verbose = global_config["VERBOSE"]
        self.__max_calls = global_config["MAX_CALLS"]
        self._log_config()
        # init luts
        self.__ip_lut, self.__forward_lut = ({}, {})
        self._check_schemes()
        self._init_host_objects()
        # dict to suppress too fast sending
        self.__ret_dict = {}
        self.__snmp_running = True
        self._init_processes()

    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))

    def _check_schemes(self):
        self.__local_schemes = {}
        if import_errors:
            self.log("{}:".format(logging_tools.get_plural("import error", len(import_errors))), logging_tools.LOG_LEVEL_ERROR)
            for _mod_name, _where, _line in import_errors:
                self.log("    {} ({}): {}".format(_mod_name, _where, _line), logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("no scheme import errors")
        self.log("found {}".format(logging_tools.get_plural("scheme", len(snmp_schemes))))
        for _name, _obj in snmp_schemes:
            self.__local_schemes[_name] = _obj
        # add snmp sink schemes
        self.snmp_sink = SNMPSink(self.log)
        _mon_handlers = [_handler for _handler in self.snmp_sink.handlers if _handler.Meta.mon_check]
        self.log("found {} with monitoring capability".format(logging_tools.get_plural("SNMP handler", len(_mon_handlers))))
        self.__gen_schemes = {}
        for _mh in _mon_handlers:
            for _mc in _mh.config_mon_check():
                self.__gen_schemes["SS:{}".format(_mc.Meta.name)] = _mc
                self.log("found gen scheme '{}' in handler {}".format(_mc.Meta.name, unicode(_mh)))

    def _init_host_objects(self):
        self.__host_objects = {}

    def _init_processes(self):
        self.spc = snmp_process_container(
            IPC_SOCK_SNMP,
            self.log,
            global_config["SNMP_PROCESSES"],
            self.__max_calls,
            {
                "VERBOSE": global_config["VERBOSE"],
                "LOG_NAME": global_config["LOG_NAME"],
                "LOG_DESTINATION": global_config["LOG_DESTINATION"],
            },
            {
                "process_start": self._snmp_process_start,
                "process_exit": self._snmp_process_exit,
                "all_stopped": self._all_snmps_stopped,
                "finished": self._snmp_finished,
            }
        )

        _snmp_sock = self.spc.create_ipc_socket(self.zmq_context, IPC_SOCK_SNMP)
        self.register_poller(_snmp_sock, zmq.POLLIN, self.spc.handle_with_socket)  # @UndefinedVariable
        # pending schemes
        self.__pending_schemes = {}
        self.spc.check()

    def _snmp_process_start(self, **kwargs):
        self.__msi_block.add_actual_pid(
            kwargs["pid"],
            mult=kwargs.get("mult", 3),
            process_name=kwargs["process_name"],
            fuzzy_ceiling=kwargs.get("fuzzy_ceiling", 3)
        )
        self.__msi_block.save_block()
        process_tools.append_pids(self.__pid_name, kwargs["pid"], mult=kwargs.get("mult", 3))

    def _snmp_process_exit(self, **kwargs):
        self.__msi_block.remove_actual_pid(kwargs["pid"], mult=kwargs.get("mult", 3))
        self.__msi_block.save_block()
        process_tools.remove_pids(self.__pid_name, kwargs["pid"], mult=kwargs.get("mult", 3))

    def _get_host_object(self, host_name, snmp_community, snmp_version):
        host_tuple = (host_name, snmp_community, snmp_version)
        if host_tuple not in self.__host_objects:
            self.__host_objects[host_tuple] = SNMPNetObject(self.log, self.__verbose, host_name, snmp_community, snmp_version)
        return self.__host_objects[host_tuple]

    def _log_config(self):
        self.log("Basic turnaround-time is %d seconds" % (global_config["MAIN_TIMER"]))
        self.log("basedir_name is '%s'" % (global_config["BASEDIR_NAME"]))
        self.log("manager PID is %d" % (configfile.get_manager_pid()))
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found %d valid config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))

    def _init_msi_block(self):
        self.__pid_name = global_config["PID_NAME"]
        process_tools.save_pids(global_config["PID_NAME"], mult=3)
        cf_pids = 2  # + global_config["SNMP_PROCESSES"]
        process_tools.append_pids(global_config["PID_NAME"], pid=configfile.get_manager_pid(), mult=cf_pids)
        self.log("Initialising meta-server-info block")
        msi_block = process_tools.meta_server_info("snmp-relay")
        msi_block.add_actual_pid(mult=3, fuzzy_ceiling=4, process_name="main")
        msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=cf_pids, process_name="manager")
        msi_block.kill_pids = True
        # msi_block.heartbeat_timeout = 120
        msi_block.save_block()
        self.__msi_block = msi_block

    def _int_error(self, err_cause):
        self.log("_int_error() called, cause %s" % (str(err_cause)), logging_tools.LOG_LEVEL_WARN)
        if not self.__snmp_running:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self.spc.stop()
            self.__snmp_running = False

    def _all_snmps_stopped(self):
        self["exit_requested"] = True

    def _init_ipc_sockets(self):
        self.__num_messages = 0
        sock_list = [
            ("receiver", zmq.PULL, 2),  # @UndefinedVariable
            ("sender", zmq.PUB, 1024),  # @UndefinedVariable
        ]
        [setattr(self, "{}_socket".format(short_sock_name), None) for short_sock_name, _a0, _b0 in sock_list]
        for short_sock_name, sock_type, hwm_size in sock_list:
            sock_name = process_tools.get_zmq_ipc_name(short_sock_name, s_name="snmp-relay")
            file_name = sock_name[5:]
            self.log(
                "init {} ipc_socket '{}' (HWM: {:d})".format(
                    short_sock_name,
                    sock_name,
                    hwm_size
                )
            )
            if os.path.exists(file_name):
                self.log("removing previous file")
                try:
                    os.unlink(file_name)
                except:
                    self.log("... %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            wait_iter = 0
            while os.path.exists(file_name) and wait_iter < 100:
                self.log("socket %s still exists, waiting" % (sock_name))
                time.sleep(0.1)
                wait_iter += 1
            cur_socket = self.zmq_context.socket(sock_type)
            try:
                process_tools.bind_zmq_socket(cur_socket, sock_name)
                # client.bind("tcp://*:8888")
            except zmq.ZMQError:
                self.log(
                    "error binding %s: %s" % (
                        short_sock_name,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_CRITICAL)
                raise
            else:
                setattr(self, "%s_socket" % (short_sock_name), cur_socket)
                os.chmod(file_name, 0777)
                self.receiver_socket.setsockopt(zmq.LINGER, 0)  # @UndefinedVariable
                self.receiver_socket.setsockopt(zmq.RCVHWM, hwm_size)  # @UndefinedVariable
                self.receiver_socket.setsockopt(zmq.SNDHWM, hwm_size)  # @UndefinedVariable
                if sock_type == zmq.PULL:  # @UndefinedVariable
                    self.register_poller(cur_socket, zmq.POLLIN, self._recv_command)  # @UndefinedVariable

    def _close_ipc_sockets(self):
        if self.receiver_socket is not None:
            self.unregister_poller(self.receiver_socket, zmq.POLLIN)  # @UndefinedVariable
            self.receiver_socket.close()
        if self.sender_socket is not None:
            self.sender_socket.close()
        self.spc.close()

    def _hup_error(self, err_cause):
        # no longer needed
        # self.__relay_thread_queue.put("reload")
        pass

    def _resolve_address(self, target):
        # to avoid loops in the 0MQ connection scheme (will result to nasty asserts)
        if target in self.__forward_lut:
            ip_addr = self.__forward_lut[target]
        else:
            orig_target = target
            if target.lower() in ["localhost", "127.0.0.1", "localhost.localdomain"]:
                target = process_tools.get_machine_name()
            # step 1: resolve to ip
            ip_addr = socket.gethostbyname(target)
            try:
                # step 2: try to get full name
                full_name, _aliases, _ip_addrs = socket.gethostbyaddr(ip_addr)
            except:
                # forget it
                pass
            else:
                # resolve full name
                try:
                    ip_addr = socket.gethostbyname(full_name)
                except:
                    self.log("error looking up {}: {}".format(full_name, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            if ip_addr not in self.__ip_lut:
                self.log("resolved %s to %s" % (target, ip_addr))
                self.__ip_lut[ip_addr] = target
            self.__forward_lut[target] = ip_addr
            self.log("ip resolving: %s -> %s" % (target, ip_addr))
            if orig_target != target:
                self.__forward_lut[orig_target] = ip_addr
                self.log("ip resolving: %s -> %s" % (orig_target, ip_addr))
        return ip_addr

    def _snmp_finished(self, data):  # src_proc, src_pid, *args, **kwargs):
        envelope, error_list, _received, snmp_dict = data["args"]
        cur_scheme = self.__pending_schemes[envelope]
        cur_scheme.snmp = snmp_dict
        for cur_error in error_list:
            cur_scheme.flag_error(cur_error)
        self._snmp_end(cur_scheme)
        del self.__pending_schemes[envelope]

    def _start_snmp_fetch(self, scheme):
        _cache_ok, num_cached, num_refresh, num_pending, num_hot_enough = scheme.pre_snmp_start(self.log)
        if self.__verbose:
            self.log("{}info for {}: {}".format(
                "[F] " if num_refresh else "[I] ",
                scheme.net_obj.name,
                ", ".join(["%d %s" % (cur_num, info_str) for cur_num, info_str in [
                    (num_cached, "cached"),
                    (num_refresh, "to refresh"),
                    (num_pending, "pending"),
                    (num_hot_enough, "hot enough")] if cur_num])))
        if num_refresh:
            self.__pending_schemes[scheme.envelope] = scheme
            self.spc.start_batch(*scheme.proc_data)
        else:
            self._snmp_end(scheme)

    def _snmp_end(self, scheme):
        if self.__verbose > 3:
            self.log(
                "snmp_end for %s, return_sent is %s, xml_input is %s" % (
                    scheme.net_obj.name,
                    scheme.return_sent,
                    scheme.xml_input,
                )
            )
        scheme.snmp_end(self.log)
        if scheme.return_sent:
            if scheme.xml_input:
                self._send_return_xml(scheme)
            else:
                ret_state, ret_str, _log_it = scheme.return_tuple
                self._send_return(scheme.envelope, ret_state, ret_str)

    def _recv_command(self, zmq_sock):
        body = zmq_sock.recv()
        if zmq_sock.getsockopt(zmq.RCVMORE):  # @UndefinedVariable
            _src_id = body
            body = zmq_sock.recv()
        parameter_ok = False
        xml_input = body.startswith("<")
        if self.__verbose > 3:
            self.log("received {:d} bytes, xml_input is {}".format(len(body), str(xml_input)))
        if xml_input:
            srv_com = server_command.srv_command(source=body)
            srv_com.set_result("no reply set", server_command.SRV_REPLY_STATE_UNSET)
            try:
                host = srv_com.xpath(".//ns:host", smart_strings=False)[0].text
                snmp_version = int(srv_com.xpath(".//ns:snmp_version", smart_strings=False)[0].text)
                snmp_community = srv_com.xpath(".//ns:snmp_community", smart_strings=False)[0].text
                comline = srv_com.xpath(".//ns:command", smart_strings=False)[0].text
                timeout = int(srv_com.get(".//ns:timeout", "10"))
            except:
                self._send_return(body, limits.nag_STATE_CRITICAL, "message format error: {}".format(process_tools.get_except_info()))
            else:
                envelope = srv_com["identity"].text
                parameter_ok = True
                if len(srv_com.xpath(".//ns:arg_list/text()", smart_strings=False)):
                    comline = " ".join([comline] + srv_com.xpath(".//ns:arg_list/text()", smart_strings=False)[0].strip().split())
        else:
            srv_com = None
            if body.count(";") >= 3:
                if body.startswith(";"):
                    # new format
                    proto_version, body = body[1:].split(";", 1)
                else:
                    proto_version, body = ("0", body)
                proto_version = int(proto_version)
                if proto_version == 0:
                    parts = body.split(";", 4)
                    parts.insert(4, "10")
                else:
                    parts = body.split(";", 5)
                envelope = parts.pop(0)
                # parse new format
                if parts[4].endswith(";"):
                    com_part = parts[4][:-1]
                else:
                    com_part = parts[4].split(";")
                # iterative parser
                try:
                    arg_list = []
                    while com_part.count(";"):
                        cur_size, cur_str = com_part.split(";", 1)
                        cur_size = int(cur_size)
                        com_part = cur_str[cur_size + 1:]
                        arg_list.append(cur_str[:cur_size].decode("utf-8"))
                    if com_part:
                        raise ValueError("not fully parsed ({})".format(com_part))
                except:
                    self.log("error parsing %s" % (body), logging_tools.LOG_LEVEL_ERROR)
                    arg_list = []
                host, snmp_version, snmp_community, timeout = parts[0:4]
                timeout = int(timeout)
                comline = " ".join(arg_list)
                # print host, snmp_version, snmp_community, timeout, arg_list
                parameter_ok = True
                # envelope, host, snmp_version, snmp_community, comline = body.split(";", 4)
        if parameter_ok:
            try:
                snmp_version = int(snmp_version)
                comline_split = comline.split()
                scheme = comline_split.pop(0)
            except:
                self._send_return(envelope, limits.nag_STATE_CRITICAL, "message format error: {}".format(process_tools.get_except_info()))
            else:
                self.__ret_dict[envelope] = time.time()
                if scheme in self.__local_schemes:
                    act_scheme, s_type = (self.__local_schemes[scheme], "L")
                elif scheme in self.__gen_schemes:
                    act_handler, s_type = (self.__gen_schemes[scheme], "G")
                elif scheme == "list_schemes":
                    _out_list = logging_tools.new_form_list()
                    for _s_name in sorted(self.__local_schemes):
                        try:
                            _scheme = self.__local_schemes[_s_name](dummy_init=True, options="")
                        except:
                            pass
                        else:
                            _out_list.append(
                                [
                                    logging_tools.form_entry("local", header="type"),
                                    logging_tools.form_entry(_s_name, header="name"),
                                    logging_tools.form_entry(len(_scheme.requests), header="#reqs"),
                                    logging_tools.form_entry(", ".join(sorted([repr(_req) for _req in _scheme.requests])), header="requests"),
                                ]
                            )
                    for _s_name in sorted(self.__gen_schemes):
                        _scheme = self.__gen_schemes[_s_name]
                        _out_list.append(
                            [
                                logging_tools.form_entry("generic", header="type"),
                                logging_tools.form_entry(_s_name, header="name"),
                            ]
                        )
                    self._send_return(envelope, limits.nag_STATE_OK, unicode(_out_list))
                    s_type = None
                else:
                    guess_list = ", ".join(difflib.get_close_matches(scheme, self.__local_schemes.keys() + self.__gen_schemes.keys()))
                    err_str = "got unknown scheme '{}'{}".format(
                        scheme,
                        ", maybe one of {}".format(guess_list) if guess_list else ", no similar scheme found"
                    )
                    self._send_return(envelope, limits.nag_STATE_CRITICAL, err_str)
                    s_type = None
                if s_type:
                    host = self._resolve_address(host)
                    host_obj = self._get_host_object(host, snmp_community, snmp_version)
                    if self.__verbose:
                        self.log(
                            "got request for scheme {} (host {}, community {}, version {:d}, envelope  {}, timeout {:d})".format(
                                scheme,
                                host,
                                snmp_community,
                                snmp_version,
                                envelope,
                                timeout,
                            )
                        )
                    try:
                        if s_type == "L":
                            act_scheme = act_scheme(
                                net_obj=host_obj,
                                envelope=envelope,
                                options=comline_split,
                                xml_input=xml_input,
                                srv_com=srv_com,
                                init_time=time.time(),
                                timeout=timeout,
                            )
                        else:
                            act_scheme = SNMPGeneralScheme(
                                net_obj=host_obj,
                                envelope=envelope,
                                options=comline_split,
                                xml_input=xml_input,
                                srv_com=srv_com,
                                init_time=time.time(),
                                timeout=timeout,
                                handler=act_handler,
                            )
                    except IOError:
                        err_str = "error while creating scheme {}: {}".format(
                            scheme,
                            process_tools.get_except_info()
                        )
                        self._send_return(envelope, limits.nag_STATE_CRITICAL, err_str)
                    else:
                        if act_scheme.get_errors():
                            err_str = "problem in creating scheme {}: {}".format(
                                scheme,
                                ", ".join(act_scheme.get_errors())
                            )
                            self._send_return(envelope, limits.nag_STATE_CRITICAL, err_str)
                        else:
                            self._start_snmp_fetch(act_scheme)

        elif not xml_input:
            self._send_return(envelope, limits.nag_STATE_CRITICAL, "message format error")
        self.__num_messages += 1
        if self.__verbose > 3:
            self.log("recv() done")
        if not self.__num_messages % 100:
            cur_mem = process_tools.get_mem_info(self.__msi_block.get_unique_pids() if self.__msi_block else 0)
            self.log(
                "memory usage is {} after {}".format(
                    logging_tools.get_size_str(cur_mem),
                    logging_tools.get_plural("message", self.__num_messages)
                )
            )
        if not self.__num_messages % 50:
            # log process usage
            self.log(self.spc.get_usage())

    def _send_return(self, envelope, ret_state, ret_str):
        if self.__verbose > 3:
            self.log(
                "_send_return, envelope is {} ({:d}, {})".format(
                    envelope,
                    ret_state,
                    ret_str,
                )
            )
        self._check_ret_dict(envelope)
        self.sender_socket.send(envelope, zmq.SNDMORE)  # @UndefinedVariable
        self.sender_socket.send_unicode(u"%d\0%s" % (ret_state, ret_str))

    def _send_return_xml(self, scheme):
        self._check_ret_dict(scheme.envelope)
        self.sender_socket.send(scheme.envelope, zmq.SNDMORE)  # @UndefinedVariable
        self.sender_socket.send_unicode(unicode(scheme.srv_com))

    def _check_ret_dict(self, env_str):
        max_sto = 0.001
        if env_str in self.__ret_dict:
            cur_time = time.time()
            if cur_time - self.__ret_dict[env_str] < max_sto:
                if self.__verbose > 2:
                    self.log(
                        "sleeping to avoid too fast resending (%.5f < %.5f) for %s" % (
                            cur_time - self.__ret_dict[env_str],
                            max_sto,
                            env_str
                        )
                    )
                time.sleep(max_sto)
            del_keys = [key for key, value in self.__ret_dict.iteritems() if abs(value - cur_time) > 60 and key != env_str]
            if del_keys:
                if self.__verbose > 2:
                    self.log(
                        "removing {}".format(
                            logging_tools.get_plural("timed-out key", len(del_keys))
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                for del_key in del_keys:
                    del self.__ret_dict[del_key]
            del self.__ret_dict[env_str]

    def loop_end(self):
        self._close_ipc_sockets()
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()

    def loop_post(self):
        self.__log_template.close()
