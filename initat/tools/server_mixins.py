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

from initat.tools import logging_tools
from initat.tools import process_tools
from initat.tools import threading_tools
from initat.tools import server_command
import zmq
import time

# exception mixin
class OperationalErrorMixin(threading_tools.exception_handling_base):
    def __init__(self):
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
        bind_to_localhost = kwargs.get("bind_to_localhost", False)
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
        self.virtual_sockets = []
        # main sockets
        self.main_socket = None
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
                        ["tcp://127.0.0.1:{:d}".format(bind_port)],
                        self.bind_id,
                        None,
                    )
                )
        else:
            # simple bind
            master_bind_list = [
                (
                    True,
                    ["tcp://*:{:d}".format(bind_port)],
                    self.bind_id,
                    None,
                )
            ]
        _errors = []
        # pprint.pprint(master_bind_list)
        bound_list = set()
        for master_bind, bind_list, bind_id, bind_dev in master_bind_list:
            client = process_tools.get_socket(self.zmq_context, "ROUTER", identity=bind_id, immediate=immediate)
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
                        self.log("bound to {} with id {}".format(_bind_str, bind_id))
                        if pollin:
                            self.register_poller(client, zmq.POLLIN, pollin, ext_call=ext_call, bind_id=bind_id)  # @UndefinedVariable
            if master_bind:
                self.main_socket = client
            else:
                self.virtual_sockets.append(client)
        if _errors and _need_all_binds:
            raise ValueError("{} went wrong: {}".format(logging_tools.get_plural("bind", len(_errors)), ", ".join(_errors)))

    def network_unbind(self):
        if self.main_socket:
            self.log("closing socket")
            self.main_socket.close()
        for _virt in self.virtual_sockets:
            self.log("closing virtual socket")
            _virt.close()
        self.virtual_sockets = []


class RemoteAsyncHelper(object):
    def __init__(self, inst):
        self.__inst = inst
        self.log("init RemoteAsyncHelper")
        self.__async_id = 0
        self.__lut = {}

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__inst.log("[RAH] {}".format(what), log_level)

    def register(self, src_id, srv_com, zmq_sock):
        self.__async_id += 1
        srv_com["async_helper_id"] = self.__async_id
        self.__lut[self.__async_id] = (src_id, zmq_sock, time.time())

    def result(self, srv_com):
        async_id = int(srv_com["*async_helper_id"])
        if async_id not in self.__lut:
            self.log(
                "asnyc_id {:d} not defined in lut, discarding message".format(
                    asnyc_id
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            return None, None, None
        else:
            src_id, zmq_sock, s_time = self.__lut[async_id]
            e_time = time.time()
            del self.__lut[async_id]
            del srv_com["async_helper_id"]
            self.log(
                "finished async call {:d} in {}".format(
                    async_id,
                    logging_tools.get_diff_time_str(e_time - s_time),
                )
            )
            return zmq_sock, src_id, srv_com


def RemoteCallProcess(klass):
    # print "*" * 20, klass
    # print dir(klass)
    # build list of lookup
    _lut_dict = {}
    for _name in dir(klass):
        _obj = getattr(klass, _name)
        if isinstance(_obj, RemoteCallSignature):
            _obj.link(_lut_dict)
    # print _lut_dict
    klass.remote_call_lut = _lut_dict
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
            if "xml" in msg_lut:
                # try to interpret as server_command
                try:
                    srv_com = server_command.srv_command(source=data)
                except:
                    srv_com = None
                    msg_type = "flat"
                else:
                    msg_type = "xml"
            else:
                msg_type = "flat"
            if msg_type == "flat":
                com_name = data.strip().split()[0]
            else:
                com_name = srv_com["*command"]
            # if msg_type in msg_lut:
            if com_name in msg_lut.get(msg_type, {}):
                if msg_type == "xml":
                    # set source
                    srv_com.update_source()
                rcs = msg_lut[msg_type][com_name]
                if rcs.sync:
                    result = rcs.handle(self, src_id, srv_com)
                    if com_type == "router":
                        # send reply
                        self._send_remote_call_reply(zmq_sock, src_id, result)
                else:
                    if not hasattr(self, "remote_async_helper"):
                        self.remote_async_helper = RemoteAsyncHelper(self)
                        self.register_func("remote_call_async_result", self.remote_call_async_result)
                    self.remote_async_helper.register(src_id, srv_com, zmq_sock)
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
                    if msg_type == "flat":
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

    def _send_remote_call_reply(self, zmq_sock, src_id, reply):
        # send return
        _send_str = unicode(reply)
        try:
            zmq_sock.send_unicode(src_id, zmq.SNDMORE)
            zmq_sock.send_unicode(_send_str)
        except:
            self.log(
                "error sending reply to {} ({}): {}".format(
                    src_id,
                    logging_tools.get_size_str(len(_send_str)),
                    process_tools.get_except_info(),
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        else:
            self.log(
                "sent {} to {}".format(
                    logging_tools.get_size_str(len(_send_str)),
                    src_id,
                )
            )

    def remote_call_async_result(self, *args, **kwargs):
        _src_proc, _src_pid, srv_com = args
        srv_com = server_command.srv_command(source=srv_com)
        _sock, _src_id, _reply = self.remote_async_helper.result(srv_com)
        if _sock is not None:
            self._send_remote_call_reply(_sock, _src_id, _reply)


class RemoteCallSignature(object):
    def __init__(self, *args, **kwargs):
        self.com_type = kwargs.get("com_type", "router")
        self.sync = kwargs.get("sync", True)
        self.msg_type = kwargs.get("msg_type", "xml")
        self.target_process = kwargs.get("target_process", None)
        self.debug = kwargs.get("debug", None)
        if not self.sync and (self.com_type, self.msg_type) not in [("router", "xml")]:
            raise ValueError("asnyc calls only possible for XML router calls")
        if not self.sync and not self.target_process:
            raise ValueError("need target process for async calls")

    def link(self, lut):
        lut.setdefault(self.com_type, {}).setdefault(self.msg_type, {})[self.func.__name__] = self

    def handle(self, instance, src_id, srv_com):
        _result = self.func(instance, srv_com, src_id=src_id)
        if self.sync:
            return _result
        else:
            instance.send_to_process(self.target_process, self.func.__name__, unicode(_result))


class RemoteCall(object):
    def __init__(self, *args, **kwargs):
        self.rc_signature = RemoteCallSignature(*args, **kwargs)

    def __call__(self, inst_method):
        self.rc_signature.func = inst_method
        return self.rc_signature
