# -*- coding: utf-8 -*-
#
# Copyright (c) 2001-2007,2009-2015 Andreas Lang-Nevyjel, init.at
#
# this file is part of python-modules-base
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License
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
""" usefull server mixins """

import time

from initat.tools import logging_tools
from initat.tools import process_tools
from initat.tools import threading_tools
from initat.tools import server_command, configfile
import zmq
import re
from enum import IntEnum


class ServerStatusMixin(object):
    # populates the srv_command with the current server stats
    def server_status(self, srv_com, msi_block, global_config=None, spc=None):
        # spc is an optional snmp_process_container
        _status = msi_block.check_block()
        _proc_info_dict = self.get_info_dict()
        # add configfile manager
        _mpid = configfile.get_manager_pid()
        if _mpid is not None:
            # salt proc_info_dict
            _proc_info_dict[_mpid] = {
                "name": "manager",
                "pid": _mpid,
                "alive": True
            }
        if spc is not None:
            spc.salt_proc_info_dict(_proc_info_dict)
        _pid_info = msi_block.pid_check_string(_proc_info_dict)
        if global_config is not None:
            try:
                _vers = global_config["VERSION"]
            except:
                pass
            else:
                _pid_info = "{}, Version: {}".format(
                    _pid_info,
                    _vers,
                )

        srv_com.set_result(
            _pid_info,
            server_command.SRV_REPLY_STATE_OK if _status else server_command.SRV_REPLY_STATE_ERROR,
        )
        return srv_com


# exception mixin
class OperationalErrorMixin(threading_tools.exception_handling_base):
    def __init__(self):
        # init by exception_handling_mxin
        self.register_exception("OperationalError", self._op_error)

    def _op_error(self, info):
        try:
            from django.db import connection
        except:
            pass
        else:
            self.log("operational error, closing db connection", logging_tools.LOG_LEVEL_ERROR)
            try:
                connection.close()
            except:
                pass


class NetworkBindMixin(object):
    def network_bind(self, **kwargs):
        _need_all_binds = kwargs.get("need_all_binds", False)
        pollin = kwargs.get("pollin", None)
        ext_call = kwargs.get("ext_call", False)
        immediate = kwargs.get("immediate", True)
        bind_port = kwargs["bind_port"]
        main_socket_name = kwargs.get("main_socket_name", "main_socket")
        virtual_sockets_name = kwargs.get("virtual_sockets_name", "virtual_sockets")
        bind_to_localhost = kwargs.get("bind_to_localhost", False)
        _sock_type = kwargs.get("socket_type", "ROUTER")
        if "client_type" in kwargs:
            self.bind_id = process_tools.get_client_uuid(kwargs["client_type"])
            dev_r = None
        else:
            from initat.tools import cluster_location
            from initat.cluster.backbone.routing import get_server_uuid
            self.bind_id = get_server_uuid(kwargs["server_type"])
            if kwargs.get("simple_server_bind", False):
                dev_r = None
            else:
                # device recognition
                dev_r = cluster_location.device_recognition()
        # virtual sockets
        if hasattr(self, virtual_sockets_name):
            _virtual_sockets = getattr(self, virtual_sockets_name)
        else:
            _virtual_sockets = []
        # main socket
        _main_socket = None
        # create bind list
        if dev_r and dev_r.device_dict:
            _bind_ips = set(list(dev_r.local_ips) + sum([_list for _dev, _list in dev_r.ip_r_lut.iteritems()], []))
            # complex bind
            master_bind_list = [
                (
                    True,
                    [
                        "tcp://{}:{:d}".format(_local_ip, bind_port) for _local_ip in dev_r.local_ips
                    ],
                    self.bind_id,
                    None,
                )
            ]
            _virt_list = []
            for _dev, _ip_list in dev_r.ip_r_lut.iteritems():
                if _dev.pk != dev_r.device.pk:
                    _virt_list.append(
                        (
                            False,
                            [
                                "tcp://{}:{:d}".format(_virtual_ip, bind_port) for _virtual_ip in _ip_list
                            ],
                            # ignore local device
                            get_server_uuid(kwargs["server_type"], _dev.uuid),
                            _dev,
                        )
                    )
                else:
                    self.log(
                        "ignoring virtual IP list ({}) (same device)".format(
                            ", ".join(sorted(_ip_list)),
                        )
                    )
            master_bind_list.extend(_virt_list)
            # we have to bind to localhost but localhost is not present in bind_list, add master_bind
            if bind_to_localhost and not any([_ip.startswith("127.") for _ip in _bind_ips]):
                self.log("bind_to_localhost is set but not IP in range 127.0.0.0/8 found in list, adding virtual_bind", logging_tools.LOG_LEVEL_WARN)
                master_bind_list.append(
                    (
                        False,
                        [
                            "tcp://127.0.0.1:{:d}".format(bind_port)
                        ],
                        self.bind_id,
                        None,
                    )
                )
        else:
            # simple bind
            master_bind_list = [
                (
                    True,
                    [
                        "tcp://*:{:d}".format(bind_port)
                    ],
                    self.bind_id,
                    None,
                )
            ]
        _errors = []
        # pprint.pprint(master_bind_list)
        bound_list = set()
        for master_bind, bind_list, bind_id, bind_dev in master_bind_list:
            client = process_tools.get_socket(
                self.zmq_context,
                _sock_type,
                identity=bind_id,
                immediate=immediate
            )
            for _bind_str in bind_list:
                if _bind_str in bound_list:
                    self.log(
                        "bind_str '{}' (for {}) already used, skipping ...".format(
                            _bind_str,
                            " device '{}'".format(bind_dev) if bind_dev is not None else " master device",
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                else:
                    bound_list.add(_bind_str)
                    try:
                        client.bind(_bind_str)
                    except zmq.ZMQError:
                        self.log(
                            "error binding to {}: {}".format(
                                _bind_str,
                                process_tools.get_except_info(),
                            ),
                            logging_tools.LOG_LEVEL_CRITICAL
                        )
                        _errors.append(_bind_str)
                    else:
                        self.log("bound {} to {} with id {}".format(_sock_type, _bind_str, bind_id))
                        if pollin:
                            self.register_poller(client, zmq.POLLIN, pollin, ext_call=ext_call, bind_id=bind_id)  # @UndefinedVariable
            if master_bind:
                _main_socket = client
            else:
                _virtual_sockets.append(client)
        setattr(self, main_socket_name, _main_socket)
        setattr(self, virtual_sockets_name, _virtual_sockets)
        if _errors and _need_all_binds:
            raise ValueError("{} went wrong: {}".format(logging_tools.get_plural("bind", len(_errors)), ", ".join(_errors)))

    def network_unbind(self, **kwargs):
        main_socket_name = kwargs.get("main_socket_name", "main_socket")
        virtual_sockets_name = kwargs.get("virtual_sockets_name", "virtual_sockets")
        _main_sock = getattr(self, main_socket_name, None)
        if _main_sock is not None:
            self.log("closing socket '{}'".format(main_socket_name))
            _main_sock.close()
            setattr(self, main_socket_name, None)
        _virt_socks = getattr(self, virtual_sockets_name, [])
        if _virt_socks:
            self.log("closing {}".format(logging_tools.get_plural("virtual socket", len(_virt_socks))))
            [_virt.close() for _virt in _virt_socks]
            setattr(self, virtual_sockets_name, [])


class RemoteAsyncHelper(object):
    def __init__(self, inst):
        self.__inst = inst
        self.log("init RemoteAsyncHelper")
        self.__async_id = 0
        self.__lut = {}

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__inst.log("[RAH] {}".format(what), log_level)

    def register(self, rcs, src_id, srv_com, zmq_sock):
        self.__async_id += 1
        srv_com["async_helper_id"] = self.__async_id
        self.__lut[self.__async_id] = (rcs.func_name, src_id, zmq_sock, time.time())

    def result(self, srv_com):
        if "async_helper_id" not in srv_com:
            self.log(
                "asnyc_helper_id  not found in srv_com, discarding message",
                logging_tools.LOG_LEVEL_ERROR
            )
            return None, None, None, None
        else:
            async_id = int(srv_com["*async_helper_id"])
            if async_id not in self.__lut:
                self.log(
                    "asnyc_id {:d} not defined in lut, discarding message".format(
                        asnyc_id
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
                return None, None, None, None
            else:
                func_name, src_id, zmq_sock, s_time = self.__lut[async_id]
                e_time = time.time()
                del self.__lut[async_id]
                del srv_com["async_helper_id"]
                _log_str = "finished async call {} ({:d}) in {}".format(
                    func_name,
                    async_id,
                    logging_tools.get_diff_time_str(e_time - s_time),
                )
                if zmq_sock is None:
                    self.log(_log_str)
                return zmq_sock, src_id, srv_com, _log_str


def RemoteCallProcess(klass):
    # print "*" * 20, klass
    # print dir(klass)
    # build list of lookup
    _lut_dict = {}
    _id_filter_dict = {}
    for _name in dir(klass):
        _obj = getattr(klass, _name)
        if isinstance(_obj, RemoteCallSignature):
            _obj.link(_lut_dict, _id_filter_dict)
    # print _lut_dict
    klass.remote_call_lut = _lut_dict
    klass.remote_call_id_filter_dict = _id_filter_dict
    # klass.remote_async_helper = RemoteAsyncHelper()
    return klass


class RemoteCallMixin(object):
    def remote_call(self, zmq_sock):
        in_data = []
        while True:
            in_data.append(zmq_sock.recv())
            if not zmq_sock.getsockopt(zmq.RCVMORE):  # @UndefinedVariable
                break
        com_type = "router" if len(in_data) == 2 else "pull"
        if com_type in self.remote_call_lut:
            if com_type == "router":
                src_id, data = in_data
            else:
                src_id, data = (None, in_data[0])
            msg_lut = self.remote_call_lut[com_type]
            if RemoteCallMessageType.xml in msg_lut:
                # try to interpret as server_command
                try:
                    srv_com = server_command.srv_command(source=data)
                except:
                    srv_com = None
                    msg_type = RemoteCallMessageType.flat
                else:
                    msg_type = RemoteCallMessageType.xml
            else:
                msg_type = RemoteCallMessageType.flat
            # set com_name to None
            com_name = None
            if self.remote_call_id_filter_dict and src_id is not None:
                _match = [_value for _key, _value in self.remote_call_id_filter_dict.iteritems() if _key.match(src_id)]
                if _match:
                    com_name = _match[0].func_name
            if com_name is None:
                # com name still none, parse data
                if msg_type == RemoteCallMessageType.flat:
                    com_name = data.strip().split()[0]
                else:
                    com_name = srv_com["*command"]

            com_name = com_name.replace("-", "_")  # can't have '-' in python method names
            # if msg_type in msg_lut:
            if com_name in msg_lut.get(msg_type, {}):
                if msg_type == RemoteCallMessageType.xml:
                    # set source
                    srv_com.update_source()
                rcs = msg_lut[msg_type][com_name]
                if rcs.sync:
                    if msg_type == RemoteCallMessageType.flat:
                        result = rcs.handle(self, src_id, data)
                    else:
                        result = rcs.handle(self, src_id, srv_com)
                    if com_type == "router" and result is not None:
                        # send reply
                        self._send_remote_call_reply(zmq_sock, src_id, result)
                else:
                    if rcs.send_async_return:
                        if not hasattr(self, "remote_async_helper"):
                            self.install_remote_call_handlers()
                        self.remote_async_helper.register(rcs, src_id, srv_com, zmq_sock)
                    if msg_type == RemoteCallMessageType.flat:
                        rcs.handle(self, src_id, data)
                    else:
                        rcs.handle(self, src_id, srv_com)
            else:
                self.log(
                    "no matching signature found for msg_type {} (command='{}')".format(
                        msg_type,
                        com_name,
                    ),
                    logging_tools.LOG_LEVEL_ERROR,
                )
                if com_type == "router":
                    if msg_type == RemoteCallMessageType.flat:
                        _reply = u"unknown command '{}'".format(com_name)
                    else:
                        srv_com.set_result(
                            "unknown command '{}'".format(com_name),
                            server_command.SRV_REPLY_STATE_ERROR
                        )
                        _reply = srv_com
                    self._send_remote_call_reply(zmq_sock, src_id, _reply)
        else:
            self.log(
                "unable to handle message type '{}' (# of data frames: {:d})".format(
                    com_type,
                    len(in_data),
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            if com_type == "router":
                _reply = server_command.srv_command()
                _reply.set_result(
                    "no remote_calls with com_type == 'router' defined",
                    server_command.SRV_REPLY_STATE_ERROR,
                )
                self._send_remote_call_reply(zmq_sock, in_data[0], _reply)

    def install_remote_call_handlers(self):
        if not hasattr(self, "remote_async_helper"):
            self.remote_async_helper = RemoteAsyncHelper(self)
            # callback to send result
            self.register_func("remote_call_async_result", self.remote_call_async_result)
            # callback to forget async helper entry
            self.register_func("remote_call_async_done", self.remote_call_async_done)

    def _send_remote_call_reply(self, zmq_sock, src_id, reply, add_log=None):
        add_log = " ({})".format(add_log) if add_log is not None else ""
        # send return
        _send_str = unicode(reply)
        try:
            zmq_sock.send_unicode(src_id, zmq.SNDMORE)
            zmq_sock.send_unicode(_send_str)
        except:
            self.log(
                "error sending reply to {} ({}): {}{}".format(
                    src_id,
                    logging_tools.get_size_str(len(_send_str)),
                    process_tools.get_except_info(),
                    add_log
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        else:
            self.log(
                "sent {} to {}{}".format(
                    logging_tools.get_size_str(len(_send_str)),
                    src_id,
                    add_log,
                )
            )

    def remote_call_async_result(self, *args, **kwargs):
        _src_proc, _src_pid, srv_com = args
        srv_com = server_command.srv_command(source=srv_com)
        _sock, _src_id, _reply, _log_str = self.remote_async_helper.result(srv_com)
        if _sock is not None:
            self._send_remote_call_reply(_sock, _src_id, _reply, _log_str)

    def remote_call_async_done(self, *args, **kwargs):
        _src_proc, _src_pid, srv_com = args
        srv_com = server_command.srv_command(source=srv_com)
        self.remote_async_helper.result(srv_com)


class RemoteCallMessageType(IntEnum):
    xml = 1
    flat = 2


class RemoteCallSignature(object):
    def __init__(self, *args, **kwargs):
        self.com_type = kwargs.get("com_type", "router")
        self.target_process = kwargs.get("target_process", None)
        self.target_process_func = kwargs.get("target_process_func", None)
        # only for async calls
        self.send_async_return = kwargs.get("send_async_return", True)
        self.msg_type = kwargs.get("msg_type", RemoteCallMessageType.xml)
        self.id_filter = kwargs.get("id_filter", None)
        self.debug = kwargs.get("debug", None)

        # sync should default to False when using a target process, else be True
        sync_default = not self.target_process

        self.sync = kwargs.get("sync", sync_default)

        if not self.sync and (self.com_type, self.msg_type, self.send_async_return) not in [
            ("router", RemoteCallMessageType.xml, True),
            ("router", RemoteCallMessageType.xml, False),
            ("router", RemoteCallMessageType.flat, False),
        ]:
            raise ValueError("async calls only possible for XML router calls or calls without return message")
        if not self.sync and not self.target_process:
            raise ValueError("need target process for async calls")
        if "sync" in kwargs and kwargs["sync"] and self.target_process:  # only check this if sync is set explicitly
            raise ValueError("call must by asynchronous when forwarding to target process")

    @property
    def func_name(self):
        return self.func.__name__

    def link(self, lut, id_filter_dict):
        lut.setdefault(self.com_type, {}).setdefault(self.msg_type, {})[self.func_name] = self
        if self.id_filter:
            id_filter_dict[re.compile(self.id_filter)] = self

    def handle(self, instance, src_id, srv_com):
        # print 'RemoteCall handle', self, instance, src_id, srv_com, 'target', self.target_process, self.func.__name__
        _result = self.func(instance, srv_com, src_id=src_id)
        if self.sync:
            return _result
        else:
            effective_target_func_name = self.target_process_func or self.func_name
            # print 'effective target name', effective_target_func_name
            instance.send_to_process(self.target_process, effective_target_func_name,  unicode(_result), src_id=src_id)


class RemoteCall(object):
    def __init__(self, *args, **kwargs):
        self.rc_signature = RemoteCallSignature(*args, **kwargs)

    def __call__(self, inst_method):
        self.rc_signature.func = inst_method
        return self.rc_signature
