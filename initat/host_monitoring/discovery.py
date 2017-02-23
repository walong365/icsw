# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server-client
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

""" host-monitoring, with 0MQ and direct socket support, relay part """

import os
import re
import time
import pprint

import zmq
from lxml import etree

from initat.icsw.service.instance import InstanceXML
from initat.tools import logging_tools, process_tools, server_command, config_store
from . import limits
from .constants import MAPPING_FILE_IDS
from .host_monitoring_struct import HostMessage
from .zmq_mapping import MappingDB

CS_NAME = "hr.0mq-mapping"

CS_RE = re.compile("tcp://(?P<address>[^:]+):(?P<port>\d+).*$")


class ZMQMapping(object):
    def __init__(self, conn_str):
        # stores the ID per connection string
        # conn_str -> (conn_id, mach_id, dyn_id)
        self._conn_str = conn_str
        for attr_name in {"conn", "mach", "dyn"}:
            setattr(self, "_{}_id".format(attr_name), "")
        # parse connection string
        _csm = CS_RE.match(self._conn_str)
        if _csm is None:
            raise SyntaxError(
                "connection_string '{}' does not match RE {}".format(
                    self._conn_str,
                    str(CS_RE),
                )
            )
        self.address = _csm.group("address")
        self.port = int(_csm.group("port"))
        self.clear_reuse()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        ZMQMapping.discovery_class.relayer_process.log(
            "[ZM {}] {}".format(
                self._conn_str,
                what,
            ),
            log_level,
        )

    def clear_reuse(self):
        self.reuse_detected = False
        self.reuse_info = "no reuse"

    @classmethod
    def init(cls, discovery_class):
        # recorded values of dyn_ids
        cls.conn_id_stream = {}
        cls.discovery_class = discovery_class

    @classmethod
    def feed_dynamic_id(cls, map_obj):
        conn_id, dyn_id = (map_obj.connection_uuid, map_obj.dynamic_uuid)
        pprint.pprint(cls.conn_id_stream)
        if conn_id not in cls.conn_id_stream:
            cls.conn_id_stream[conn_id] = [dyn_id]
            _reuse = False
        else:
            if dyn_id == cls.conn_id_stream[conn_id][-1]:
                # same id, no change
                _reuse = False
            elif dyn_id in cls.conn_id_stream[conn_id]:
                # id was recorded bevore, signal
                _reuse = True
            else:
                # add to stream
                if len(cls.conn_id_stream[conn_id]) > 10:
                    cls.conn_id_stream[conn_id].pop(0)
                cls.conn_id_stream[conn_id].append(dyn_id)
                _reuse = True
        map_obj.reuse_detected = _reuse

    @property
    def connection_uuid(self):
        return self._conn_id

    @property
    def machine_uuid(self):
        return self._mach_id

    @property
    def dynamic_uuid(self):
        return self._dyn_id

    def update(self, conn_id, mach_id, dyn_id):
        change_list = set()
        for (new_val, attr_name, full_name) in [
            (conn_id, "_conn_id", "connection id"),
            (mach_id, "_mach_id", "machine id"),
            (dyn_id, "_dyn_id", "dynamic id"),
        ]:
            old_val = getattr(self, attr_name)
            if new_val != old_val:
                change_list.add(full_name[0])
                self.log(
                    "{} has changed from '{}' to '{}'".format(
                        full_name,
                        old_val,
                        new_val,
                    ),
                    logging_tools.LOG_LEVEL_WARN
                )
                setattr(self, attr_name, new_val)
        if self.dynamic_uuid:
            # check for dyn_id changes
            ZMQMapping.feed_dynamic_id(self)
        else:
            self.reuse_detected = False
        self._changes = change_list
        return True if (change_list or self.reuse_detected) else False


class ZMQDiscovery(object):
    # discover 0mq ids
    __slots__ = [
        "port", "host", "raw_connect", "conn_str", "init_time",
        "srv_com", "src_id", "xml_input", "socket", "hm_port",
    ]

    def __init__(self, srv_com, src_id, xml_input):
        if "conn_str" in srv_com:
            _conn_str = srv_com["*conn_str"]
            _parts = _conn_str.split(":")
            if len(_parts) == 3:
                _parts.pop(0)
            self.host = _parts.pop(0).split("/")[-1]
            self.port = int(_parts.pop(0))
        else:
            self.port = int(srv_com["port"].text)
            self.host = srv_com["host"].text
        self.raw_connect = True if int(srv_com.get("raw_connect", "0")) else False
        self.conn_str = "tcp://{}:{:d}".format(
            self.host,
            self.port
        )
        self.init_time = time.time()
        self.srv_com = srv_com
        self.src_id = src_id
        self.xml_input = xml_input
        cur_time = time.time()
        if self.conn_str in ZMQDiscovery.last_try and abs(ZMQDiscovery.last_try[self.conn_str] - cur_time) < 60:
            # need 60 seconds between tries
            self.socket = None
            self.send_return("last 0MQ discovery less than 60 seconds ago")
        else:
            ZMQDiscovery._pending[self.conn_str] = self
            new_sock = ZMQDiscovery.relayer_process.zmq_context.socket(zmq.DEALER)
            id_str = "relayer_dlr_{}_{}".format(
                process_tools.get_machine_name(),
                self.src_id
            )
            new_sock.setsockopt_string(zmq.IDENTITY, id_str)
            new_sock.setsockopt(zmq.LINGER, 0)
            new_sock.setsockopt(zmq.SNDHWM, ZMQDiscovery.backlog_size)
            new_sock.setsockopt(zmq.RCVHWM, ZMQDiscovery.backlog_size)
            new_sock.setsockopt(zmq.BACKLOG, ZMQDiscovery.backlog_size)
            new_sock.setsockopt(zmq.TCP_KEEPALIVE, 1)
            new_sock.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 300)
            self.socket = new_sock
            ZMQDiscovery.relayer_process.register_poller(new_sock, zmq.POLLIN, self.get_result)
            # ZMQDiscovery.relayer_process.register_poller(new_sock, zmq.POLLIN, self.error)
            self.socket.connect(self.conn_str)
            if self.raw_connect:
                self.log("send raw discovery message")
                self.socket.send_unicode("get_0mq_id")
            else:
                self.log("send discovery message")
                dealer_message = server_command.srv_command(command="get_0mq_id")
                dealer_message["target_ip"] = self.host
                self.socket.send_unicode(str(dealer_message))

    def send_return(self, error_msg):
        self.log(error_msg, logging_tools.LOG_LEVEL_ERROR)
        if self.src_id:
            dummy_mes = HostMessage(self.srv_com["command"].text, self.src_id, self.srv_com, self.xml_input)
            dummy_mes.set_result(limits.mon_STATE_CRITICAL, error_msg)
            self.send_result(dummy_mes)
        else:
            self.close()

    def send_result(self, host_mes, result=None):
        ZMQDiscovery.relayer_process.sender_socket.send_unicode(host_mes.src_id, zmq.SNDMORE)
        ZMQDiscovery.relayer_process.sender_socket.send_unicode(host_mes.get_result(result)[0])
        self.close()

    def error(self, zmq_sock):
        self.log(
            "got error for socket {}".format(
                str(zmq_sock)
            ),
            logging_tools.LOG_LEVEL_ERROR
        )
        time.sleep(1)

    def get_result(self, zmq_sock):
        if self.conn_str in ZMQDiscovery.last_try:
            del ZMQDiscovery.last_try[self.conn_str]
        try:
            _res = zmq_sock.recv()
            # print("*", _res)
            if self.raw_connect:
                # only valid for hoststatus, FIXME
                zmq_id = etree.fromstring(_res).findtext("nodestatus")
                cur_reply = None
            else:
                cur_reply = server_command.srv_command(source=_res)
                zmq_id = cur_reply["zmq_id"].text
        except:
            self.send_return(
                "error extracting 0MQ id (discovery): {}".format(
                    process_tools.get_except_info(),
                )
            )
        else:
            # old code, never really used in production
            # if zmq_id in ZMQDiscovery.reverse_mapping and (
            #     self.host not in ZMQDiscovery.reverse_mapping[zmq_id]
            # ) and ZMQDiscovery.force_resolve:
            #     self.log(
            #         "0MQ is {} but already used by {}: {}".format(
            #             zmq_id,
            #             logging_tools.get_plural(
            #                 "host", len(ZMQDiscovery.reverse_mapping[zmq_id])
            #             ),
            #             ", ".join(
            #                 sorted(
            #                     ZMQDiscovery.reverse_mapping[zmq_id]
            #                 )
            #             )
            #         ),
            #         logging_tools.LOG_LEVEL_ERROR
            #     )
            #     self.send_return("0MQ id not unique, virtual host setup found ?")
            if zmq_id.lower().count("unknown command"):
                self.log(
                    "received illegal zmq_id '{}'".format(
                        zmq_id
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                self.log("0MQ id is {}".format(zmq_id))
                if cur_reply is not None and "machine_uuid" in cur_reply:
                    mach_uuid, dyn_uuid = (
                        cur_reply["*machine_uuid"],
                        cur_reply["*dynamic_uuid"],
                    )
                else:
                    mach_uuid, dyn_uuid = (
                        "", "",
                    )
                ZMQDiscovery.update_mapping(self.conn_str, zmq_id, mach_uuid, dyn_uuid)
                # ZMQDiscovery.db_map.add_mapping(
                #    self.host,
                #    self.port,
                #    zmq_id,
                # )
                if self.src_id:
                    # reinject
                    if self.port == self.hm_port:
                        ZMQDiscovery.relayer_process._send_to_client(self.src_id, self.srv_com, self.xml_input)
                    else:
                        ZMQDiscovery.relayer_process._send_to_nhm_service(self.src_id, self.srv_com, self.xml_input)
                else:
                    self.log("no src_id set, was internal ID check", logging_tools.LOG_LEVEL_WARN)
            self.close()

    def close(self):
        del self.srv_com
        if self.socket:
            self.socket.close()
            ZMQDiscovery.relayer_process.unregister_poller(self.socket, zmq.POLLIN)
            del self.socket
        if self.conn_str in ZMQDiscovery._pending:
            # remove from pending dict
            del ZMQDiscovery._pending[self.conn_str]
        self.log("closing")
        del self

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        ZMQDiscovery.relayer_process.log("[idd, {}] {}".format(self.conn_str, what), log_level)

    @classmethod
    def reload_mapping(cls):
        tm = logging_tools.MeasureTime(log_com=cls.relayer_process.log)
        _log = cls.relayer_process.log
        # illegal server names
        ISN_SET = {
            "clusterserver",
            "ccserver",
            "sgeserver",
            "rrd_grapher",
            "pclient",
        }
        # mapping connection string -> current mapping
        cls._mapping = {}
        cls.CS = config_store.ConfigStore(
            CS_NAME,
            log_com=_log
        )
        cls.db_map.clear()
        #
        if config_store.ConfigStore.exists(CS_NAME):
            _log("read mapping from CStore")
            key_re = re.compile("^(?P<proto>\S+)@(?P<addr>[^:]+):(?P<port>\d+)$")
            for key in list(cls.CS.keys()):
                _km = key_re.match(key)
                if _km:
                    _gd = _km.groupdict()
                    conn_str = "{}://{}:{:d}".format(
                        _gd["proto"],
                        _gd["addr"],
                        int(_gd["port"]),
                    )
                    # cls._mapping[conn_str] = ZMQMapping(conn_str, cls.CS[key], None, None)
                    # cls.db_map.add_mapping(
                    #    _gd["addr"],
                    #    int(_gd["port"]),
                    #    cls.CS[key],
                    # )
                else:
                    _log("error interpreting key {}".format(key))
        elif os.path.isfile(MAPPING_FILE_IDS):
            map_content = open(MAPPING_FILE_IDS, "r").read()
            if map_content.startswith("<"):
                # new format
                mapping_xml = etree.fromstring(map_content)
                for host_el in mapping_xml.findall(".//host"):
                    for uuid_el in host_el.findall(".//uuid"):
                        if any([uuid_el.text.count(_isn) for _isn in ISN_SET]):
                            pass
                        else:
                            conn_str = "{}://{}:{}".format(
                                uuid_el.get("proto"),
                                host_el.get("address"),
                                uuid_el.get("port"),
                            )
                            # cls._mapping[conn_str] = ZMQMapping(conn_str, uuid_el.text, None, None)
                            # cls.db_map.add_mapping(
                            #    host_el.get("address"),
                            #    int(uuid_el.get("port")),
                            #    uuid_el.text,
                            # )
            else:
                # old format
                map_lines = [
                    line.strip().split("=", 1) for line in map_content.split("\n") if line.strip() and line.count("=")
                ]
                for key, value in map_lines:
                    cls._mapping[key] = ZMQMapping(key, value, None, None)
                cls.CS.save()  # save_mapping
            _log(
                "read {} from {} (in file: {:d})".format(
                    logging_tools.get_plural(
                        "mapping",
                        len(list(cls.CS.keys())),
                    ),
                    MAPPING_FILE_IDS,
                    len(map_content.split("\n")),
                )
            )
        cls.db_map.dump()
        _prev_maps = cls.__cur_maps
        cls.__cur_maps = set(cls._mapping.keys())
        cls.vanished = _prev_maps - cls.__cur_maps
        if cls.vanished:
            _log(
                "{} vanished: {}".format(
                    logging_tools.get_plural("address", len(cls.vanished)),
                    ", ".join(sorted(list(cls.vanished))),
                )
            )
        tm.step("reload mapping")

    @classmethod
    def init(cls, r_process, backlog_size, timeout, verbose):
        ZMQMapping.init(cls)
        cls.db_map = MappingDB(
            os.path.join(r_process.state_directory, "mapping.sqlite"),
            r_process.log,
        )
        cls.relayer_process = r_process
        cls.backlog_size = backlog_size
        cls.timeout = timeout
        cls.verbose = verbose
        # requests pending
        cls._pending = {}
        # last discovery try
        cls.last_try = {}
        cls.__cur_maps = set()
        cls.vanished = set()
        cls.hm_port = InstanceXML(quiet=True).get_port_dict(
            "host-monitoring",
            command=True
        )
        cls.reload_mapping()

    @classmethod
    def destroy(cls):
        for value in list(cls._pending.values()):
            value.close()

    @classmethod
    def get_hm_0mq_addrs(cls):
        return cls.db_map.get_0mq_addrs(cls.hm_port)

    @classmethod
    def get_mapping(cls, conn_str):
        return cls._mapping[conn_str]

    @classmethod
    def update_mapping(cls, conn_str, conn_id, machine_id, dynamic_id):
        if conn_str not in cls._mapping:
            cls._mapping[conn_str] = ZMQMapping(conn_str)
        map_obj = cls._mapping[conn_str]
        if map_obj.update(conn_id, machine_id, dynamic_id):
            # something has changed, force update to database
            cls.db_map.update_mapping(map_obj)
        return map_obj.reuse_detected
        # print("+", conn_str, conn_id, machine_id, dynamic_id)

    @classmethod
    def set_initial_mapping(cls, conn_str, con_uuid, mach_uuid, dyn_uuid):
        # only called during setup
        if con_uuid.lower().count("unknown command"):
            return
        cls._mapping[conn_str] = ZMQMapping(conn_str, con_uuid, mach_uuid, dyn_uuid)
        return

        proto, addr, port = conn_str.split(":")
        addr = addr[2:]
        _key = "{}@{}:{}".format(
            proto,
            addr,
            port,
        )
        if _key not in cls.CS or cls.CS[_key] != uuid:
            cls.CS[_key] = uuid
            # cls.CS.write()

    @classmethod
    def is_pending(cls, conn_str):
        return conn_str in cls._pending

    @classmethod
    def has_mapping(cls, conn_str):
        return conn_str in cls._mapping

    @classmethod
    def get_connection_uuid(cls, conn_str):
        return cls._mapping[conn_str].connection_uuid

    @classmethod
    def get_machine_uuid(cls, conn_str):
        return cls._mapping[conn_str].machine_uuid

    @classmethod
    def check_timeout(cls, cur_time):
        del_list = []
        for _conn_str, cur_ids in cls._pending.items():
            diff_time = abs(cur_ids.init_time - cur_time)
            if diff_time > cls.timeout:
                del_list.append(cur_ids)
        for cur_ids in del_list:
            # set last try flag
            cls.last_try[cur_ids.conn_str] = cur_time
            cur_ids.send_return("timeout triggered, closing")
