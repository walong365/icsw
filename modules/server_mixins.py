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

from initat.cluster.backbone.routing import get_server_uuid
import cluster_location
import logging_tools
import pprint  # @UnusedImport
import process_tools
import threading_tools
import zmq


# exception mixin
class operational_error_mixin(threading_tools.exception_handling_base):
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


class network_bind_mixin(object):
    def network_bind(self, **kwargs):
        _need_all_binds = kwargs.get("need_all_binds", False)
        pollin = kwargs.get("pollin", None)
        ext_call = kwargs.get("ext_call", False)
        immediate = kwargs.get("immediate", True)
        bind_port = kwargs["bind_port"]
        bind_to_localhost = kwargs.get("bind_to_localhost", False)
        self.bind_id = get_server_uuid(kwargs["server_type"])
        # device recognition
        dev_r = cluster_location.device_recognition()
        # virtual sockets
        self.virtual_sockets = []
        # main sockets
        self.main_socket = None
        # create bind list
        if dev_r.device_dict:
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
            ] + [
                (
                    False,
                    [
                        "tcp://{}:{:d}".format(_virtual_ip, bind_port) for _virtual_ip in _ip_list
                    ],
                    # ignore local device
                    get_server_uuid(kwargs["server_type"], _dev.uuid),
                    _dev,
                ) for _dev, _ip_list in dev_r.ip_r_lut.iteritems() if _dev.pk != dev_r.device.pk
            ]
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
