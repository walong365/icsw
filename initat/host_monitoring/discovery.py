# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of host-monitoring
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

""" host-monitoring, with 0MQ and direct socket support, relay part """

from lxml import etree  # @UnresolvedImport
import os
import re
import time

from initat.host_monitoring import limits
from initat.host_monitoring.constants import MAPPING_FILE_IDS
from initat.host_monitoring.host_monitoring_struct import host_message
from lxml.builder import E  # @UnresolvedImport
from initat.icsw.service.instance import InstanceXML
from initat.tools import logging_tools, process_tools, server_command, config_store
import zmq

CS_NAME = "hr.0mq-mapping"


class ZMQDiscovery(object):
    # discover 0mq ids
    __slots__ = [
        "port", "host", "raw_connect", "conn_str", "init_time",
        "srv_com", "src_id", "xml_input", "socket", "hm_port",
    ]

    def __init__(self, srv_com, src_id, xml_input):
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
            ZMQDiscovery.pending[self.conn_str] = self
            new_sock = ZMQDiscovery.relayer_process.zmq_context.socket(zmq.DEALER)  # @UndefinedVariable
            id_str = "relayer_dlr_{}_{}".format(
                process_tools.get_machine_name(),
                self.src_id
            )
            new_sock.setsockopt(zmq.IDENTITY, id_str)  # @UndefinedVariable
            new_sock.setsockopt(zmq.LINGER, 0)  # @UndefinedVariable
            new_sock.setsockopt(zmq.SNDHWM, ZMQDiscovery.backlog_size)  # @UndefinedVariable
            new_sock.setsockopt(zmq.RCVHWM, ZMQDiscovery.backlog_size)  # @UndefinedVariable
            new_sock.setsockopt(zmq.BACKLOG, ZMQDiscovery.backlog_size)  # @UndefinedVariable
            new_sock.setsockopt(zmq.TCP_KEEPALIVE, 1)  # @UndefinedVariable
            new_sock.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 300)  # @UndefinedVariable
            self.socket = new_sock
            ZMQDiscovery.relayer_process.register_poller(new_sock, zmq.POLLIN, self.get_result)  # @UndefinedVariable
            # ZMQDiscovery.relayer_process.register_poller(new_sock, zmq.POLLIN, self.error)
            self.socket.connect(self.conn_str)
            if self.raw_connect:
                self.log("send raw discovery message")
                self.socket.send_unicode("get_0mq_id")
            else:
                self.log("send discovery message")
                dealer_message = server_command.srv_command(command="get_0mq_id")
                dealer_message["target_ip"] = self.host
                self.socket.send_unicode(unicode(dealer_message))

    def send_return(self, error_msg):
        self.log(error_msg, logging_tools.LOG_LEVEL_ERROR)
        dummy_mes = host_message(self.srv_com["command"].text, self.src_id, self.srv_com, self.xml_input)
        dummy_mes.set_result(limits.nag_STATE_CRITICAL, error_msg)
        self.send_result(dummy_mes)

    def send_result(self, host_mes, result=None):
        ZMQDiscovery.relayer_process.sender_socket.send_unicode(host_mes.src_id, zmq.SNDMORE)  # @UndefinedVariable
        ZMQDiscovery.relayer_process.sender_socket.send_unicode(host_mes.get_result(result)[0])
        self.close()

    def error(self, zmq_sock):
        self.log("got error for socket", logging_tools.LOG_LEVEL_ERROR)
        time.sleep(1)

    def get_result(self, zmq_sock):
        if self.conn_str in ZMQDiscovery.last_try:
            del ZMQDiscovery.last_try[self.conn_str]
        try:
            if self.raw_connect:
                # only valid for hoststatus, FIXME
                zmq_id = etree.fromstring(zmq_sock.recv()).findtext("nodestatus")  # @UndefinedVariable
            else:
                cur_reply = server_command.srv_command(source=zmq_sock.recv())
                zmq_id = cur_reply["zmq_id"].text
        except:
            self.send_return("error extracting 0MQ id (discovery): {}".format(process_tools.get_except_info()))
        else:
            if zmq_id in ZMQDiscovery.reverse_mapping and (self.host not in ZMQDiscovery.reverse_mapping[zmq_id]) and ZMQDiscovery.force_resolve:
                self.log(
                    "0MQ is {} but already used by {}: {}".format(
                        zmq_id,
                        logging_tools.get_plural(
                            "host", len(ZMQDiscovery.reverse_mapping[zmq_id])
                        ),
                        ", ".join(
                            sorted(
                                ZMQDiscovery.reverse_mapping[zmq_id]
                            )
                        )
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
                self.send_return("0MQ id not unique, virtual host setup found ?")
            else:
                if zmq_id.lower().count("unknown command"):
                    self.log(
                        "received illegal zmq_id '{}'".format(
                            zmq_id
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                else:
                    self.log("0MQ id is {}".format(zmq_id))
                    ZMQDiscovery.set_mapping(self.conn_str, zmq_id)  # mapping[self.conn_str] = zmq_id
                    # reinject
                    if self.port == self.hm_port:
                        ZMQDiscovery.relayer_process._send_to_client(self.src_id, self.srv_com, self.xml_input)
                    else:
                        ZMQDiscovery.relayer_process._send_to_nhm_service(self.src_id, self.srv_com, self.xml_input)
                self.close()

    def close(self):
        del self.srv_com
        if self.socket:
            self.socket.close()
            ZMQDiscovery.relayer_process.unregister_poller(self.socket, zmq.POLLIN)  # @UndefinedVariable
            del self.socket
        if self.conn_str in ZMQDiscovery.pending:
            # remove from pending dict
            del ZMQDiscovery.pending[self.conn_str]
        self.log("closing")
        del self

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        ZMQDiscovery.relayer_process.log("[idd, {}] {}".format(self.conn_str, what), log_level)

    @staticmethod
    def reload_mapping():
        _log = ZMQDiscovery.relayer_process.log
        # illegal server names
        ISN_SET = {
            "clusterserver",
            "ccserver",
            "sgeserver",
            "rrd_grapher",
            "pclient",
        }
        ZMQDiscovery.mapping = {}
        ZMQDiscovery.reverse_mapping = {}
        # mapping connection string -> 0MQ id
        ZMQDiscovery.save_file = True
        ZMQDiscovery.CS = config_store.ConfigStore(
            CS_NAME,
            log_com=_log
        )
        #
        if config_store.ConfigStore.exists(CS_NAME):
            _log("read mapping from CStore")
            key_re = re.compile("^(?P<proto>\S+)@(?P<addr>[^:]+):(?P<port>\d+)$")
            for key in ZMQDiscovery.CS.keys():
                _km = key_re.match(key)
                if _km:
                    _gd = _km.groupdict()
                    conn_str = "{}://{}:{:d}".format(
                        _gd["proto"],
                        _gd["addr"],
                        int(_gd["port"]),
                    )
                    ZMQDiscovery.mapping[conn_str] = ZMQDiscovery.CS[key]
                else:
                    _log("error interpreting key {}".format(key))
        else:
            if os.path.isfile(MAPPING_FILE_IDS):
                map_content = file(MAPPING_FILE_IDS, "r").read()
                if map_content.startswith("<"):
                    # new format
                    mapping_xml = etree.fromstring(map_content)  # @UndefinedVariable
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
                                ZMQDiscovery.set_mapping(conn_str, uuid_el.text)
                else:
                    # old format
                    map_lines = [
                        line.strip().split("=", 1) for line in map_content.split("\n") if line.strip() and line.count("=")
                    ]
                    ZMQDiscovery.save_file = False
                    for key, value in map_lines:
                        ZMQDiscovery.set_mapping(key, value)
                    ZMQDiscovery.save_file = True
                    ZMQDiscovery.CS.save()  # save_mapping()
                _log(
                    "read {} from {} (in file: {:d})".format(
                        logging_tools.get_plural(
                            "mapping",
                            len(ZMQDiscovery.CS.keys()),
                        ),
                        MAPPING_FILE_IDS,
                        len(map_content.split("\n")),
                    )
                )
            # pprint.pprint(ZMQDiscovery.reverse_mapping)
            else:
                ZMQDiscovery.mapping = {}
        _prev_maps = ZMQDiscovery.__cur_maps
        ZMQDiscovery.__cur_maps = set(ZMQDiscovery.mapping.keys())
        ZMQDiscovery.vanished = _prev_maps - ZMQDiscovery.__cur_maps
        if ZMQDiscovery.vanished:
            _log(
                "{} vanished: {}".format(
                    logging_tools.get_plural("address", len(ZMQDiscovery.vanished)),
                    ", ".join(sorted(list(ZMQDiscovery.vanished))),
                )
            )
        for key, value in ZMQDiscovery.mapping.iteritems():
            # only use ip-address / hostname from key
            ZMQDiscovery.reverse_mapping.setdefault(value, []).append(key[6:].split(":")[0])

    @staticmethod
    def init(r_process, backlog_size, timeout, verbose, force_resolve):
        ZMQDiscovery.relayer_process = r_process
        ZMQDiscovery.backlog_size = backlog_size
        ZMQDiscovery.timeout = timeout
        ZMQDiscovery.verbose = verbose
        ZMQDiscovery.force_resolve = force_resolve
        ZMQDiscovery.pending = {}
        # last discovery try
        ZMQDiscovery.last_try = {}
        ZMQDiscovery.__cur_maps = set()
        ZMQDiscovery.vanished = set()
        ZMQDiscovery.hm_port = InstanceXML(quiet=True).get_port_dict("host-monitoring", command=True)
        ZMQDiscovery.reload_mapping()

    @staticmethod
    def destroy():
        for value in list(ZMQDiscovery.pending.values()):
            value.close()

    @staticmethod
    def get_hm_0mq_addrs():
        return [
            _key.split("/")[-1].split(":")[0] for _key in ZMQDiscovery.mapping.iterkeys() if _key.endswith(":{:d}".format(ZMQDiscovery.hm_port))
        ]

    @staticmethod
    def set_mapping(conn_str, uuid):
        if uuid.lower().count("unknown command"):
            return
        ZMQDiscovery.mapping[conn_str] = uuid
        proto, addr, port = conn_str.split(":")
        addr = addr[2:]
        _key = "{}@{}:{}".format(
            proto,
            addr,
            port,
        )
        if _key not in ZMQDiscovery.CS or ZMQDiscovery.CS[_key] != uuid:
            ZMQDiscovery.CS[_key] = uuid
            ZMQDiscovery.CS.write()

    @staticmethod
    def is_pending(conn_str):
        return conn_str in ZMQDiscovery.pending

    @staticmethod
    def has_mapping(conn_str):
        return conn_str in ZMQDiscovery.mapping

    @staticmethod
    def get_mapping(conn_str):
        return ZMQDiscovery.mapping[conn_str]

    @staticmethod
    def check_timeout(cur_time):
        del_list = []
        for _conn_str, cur_ids in ZMQDiscovery.pending.iteritems():
            diff_time = abs(cur_ids.init_time - cur_time)
            if diff_time > ZMQDiscovery.timeout:
                del_list.append(cur_ids)
        for cur_ids in del_list:
            # set last try flag
            ZMQDiscovery.last_try[cur_ids.conn_str] = cur_time
            cur_ids.send_return("timeout triggered, closing")
