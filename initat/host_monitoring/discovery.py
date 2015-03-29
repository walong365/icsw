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

from initat.host_monitoring import limits
from initat.host_monitoring.constants import MAPPING_FILE_IDS
from initat.host_monitoring.struct import host_message
from lxml import etree  # @UnresolvedImport
from lxml.builder import E  # @UnresolvedImport
import logging_tools
import os
import process_tools
import server_command
import time
import zmq


class id_discovery(object):
    # discover 0mq ids
    __slots__ = [
        "port", "host", "raw_connect", "conn_str", "init_time", "srv_com", "src_id", "xml_input", "socket"
    ]

    def __init__(self, srv_com, src_id, xml_input):
        self.port = int(srv_com["port"].text)
        self.host = srv_com["host"].text
        self.raw_connect = True if int(srv_com.get("raw_connect", "0")) else False
        self.conn_str = "tcp://%s:%d" % (
            self.host,
            self.port)
        self.init_time = time.time()
        self.srv_com = srv_com
        self.src_id = src_id
        self.xml_input = xml_input
        cur_time = time.time()
        if self.conn_str in id_discovery.last_try and abs(id_discovery.last_try[self.conn_str] - cur_time) < 60:
            # need 60 seconds between tries
            self.socket = None
            self.send_return("last 0MQ discovery less than 60 seconds ago")
        else:
            id_discovery.pending[self.conn_str] = self
            new_sock = id_discovery.relayer_process.zmq_context.socket(zmq.DEALER)  # @UndefinedVariable
            id_str = "relayer_dlr_%s_%s" % (
                process_tools.get_machine_name(),
                self.src_id)
            new_sock.setsockopt(zmq.IDENTITY, id_str)  # @UndefinedVariable
            new_sock.setsockopt(zmq.LINGER, 0)  # @UndefinedVariable
            new_sock.setsockopt(zmq.SNDHWM, id_discovery.backlog_size)  # @UndefinedVariable
            new_sock.setsockopt(zmq.RCVHWM, id_discovery.backlog_size)  # @UndefinedVariable
            new_sock.setsockopt(zmq.BACKLOG, id_discovery.backlog_size)  # @UndefinedVariable
            new_sock.setsockopt(zmq.TCP_KEEPALIVE, 1)  # @UndefinedVariable
            new_sock.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 300)  # @UndefinedVariable
            self.socket = new_sock
            id_discovery.relayer_process.register_poller(new_sock, zmq.POLLIN, self.get_result)  # @UndefinedVariable
            # id_discovery.relayer_process.register_poller(new_sock, zmq.POLLIN, self.error)
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
        id_discovery.relayer_process.sender_socket.send_unicode(host_mes.src_id, zmq.SNDMORE)  # @UndefinedVariable
        id_discovery.relayer_process.sender_socket.send_unicode(host_mes.get_result(result)[0])
        self.close()

    def error(self, zmq_sock):
        self.log("got error for socket", logging_tools.LOG_LEVEL_ERROR)
        time.sleep(1)

    def get_result(self, zmq_sock):
        if self.conn_str in id_discovery.last_try:
            del id_discovery.last_try[self.conn_str]
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
            if zmq_id in id_discovery.reverse_mapping and (self.host not in id_discovery.reverse_mapping[zmq_id]) and id_discovery.force_resolve:
                self.log("0MQ is {} but already used by {}: {}".format(
                    zmq_id,
                    logging_tools.get_plural(
                        "host", len(id_discovery.reverse_mapping[zmq_id])
                    ),
                    ", ".join(
                        sorted(
                            id_discovery.reverse_mapping[zmq_id])
                        )
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
                self.send_return("0MQ id not unique, virtual host setup found ?")
            else:
                if zmq_id.lower().count("unknown command"):
                    self.log("received illegal zmq_id '{}'".format(zmq_id), logging_tools.LOG_LEVEL_ERROR)
                else:
                    self.log("0MQ id is {}".format(zmq_id))
                    id_discovery.set_mapping(self.conn_str, zmq_id)  # mapping[self.conn_str] = zmq_id
                    # reinject
                    if self.port == 2001:
                        id_discovery.relayer_process._send_to_client(self.src_id, self.srv_com, self.xml_input)
                    else:
                        id_discovery.relayer_process._send_to_nhm_service(self.src_id, self.srv_com, self.xml_input)
                self.close()

    @staticmethod
    def save_mapping():
        if id_discovery.save_file:
            id_discovery.relayer_process.log("saving mapping file")
            file(MAPPING_FILE_IDS, "w").write(etree.tostring(id_discovery.mapping_xml, pretty_print=True))  # @UndefinedVariable

    def close(self):
        del self.srv_com
        if self.socket:
            self.socket.close()
            id_discovery.relayer_process.unregister_poller(self.socket, zmq.POLLIN)  # @UndefinedVariable
            del self.socket
        if self.conn_str in id_discovery.pending:
            # remove from pending dict
            del id_discovery.pending[self.conn_str]
        self.log("closing")
        del self

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        id_discovery.relayer_process.log("[idd, %s] %s" % (self.conn_str, what), log_level)

    @staticmethod
    def reload_mapping():
        id_discovery.reverse_mapping = {}
        # mapping connection string -> 0MQ id
        id_discovery.save_file = True
        if os.path.isfile(MAPPING_FILE_IDS):
            map_content = file(MAPPING_FILE_IDS, "r").read()
            if map_content.startswith("<"):
                # new format
                id_discovery.mapping = {}
                id_discovery.mapping_xml = etree.fromstring(map_content)  # @UndefinedVariable
                for host_el in id_discovery.mapping_xml.findall(".//host"):
                    for uuid_el in host_el.findall(".//uuid"):
                        conn_str = "{}://{}:{}".format(
                            uuid_el.get("proto"),
                            host_el.get("address"),
                            uuid_el.get("port"),
                            )
                        id_discovery.set_mapping(conn_str, uuid_el.text)
            else:
                # old format
                map_lines = [line.strip().split("=", 1) for line in map_content.split("\n") if line.strip() and line.count("=")]
                id_discovery.mapping = {}
                id_discovery.mapping_xml = E.zmq_mapping()
                id_discovery.save_file = False
                for key, value in map_lines:
                    id_discovery.set_mapping(key, value)
                id_discovery.save_file = True
                id_discovery.save_mapping()
            id_discovery.relayer_process.log(
                "read %s from %s (in file: %d)" % (
                    logging_tools.get_plural("mapping", len(id_discovery.mapping_xml.findall(".//uuid"))),
                    MAPPING_FILE_IDS,
                    len(map_content.split("\n")),
                    ))
            for key, value in id_discovery.mapping.iteritems():
                # only use ip-address / hostname from key
                id_discovery.reverse_mapping.setdefault(value, []).append(key[6:].split(":")[0])
            # pprint.pprint(id_discovery.reverse_mapping)
        else:
            id_discovery.mapping = {}
            id_discovery.mapping_xml = E.zmq_mapping()

    @staticmethod
    def init(r_process, backlog_size, timeout, verbose, force_resolve):
        id_discovery.relayer_process = r_process
        id_discovery.backlog_size = backlog_size
        id_discovery.timeout = timeout
        id_discovery.verbose = verbose
        id_discovery.force_resolve = force_resolve
        id_discovery.pending = {}
        # last discovery try
        id_discovery.last_try = {}
        id_discovery.reload_mapping()

    @staticmethod
    def destroy():
        for value in list(id_discovery.pending.values()):
            value.close()

    @staticmethod
    def set_mapping(conn_str, uuid):
        if uuid.lower().count("unknown command"):
            return
        id_discovery.mapping[conn_str] = uuid
        proto, addr, port = conn_str.split(":")
        addr = addr[2:]
        map_xml = id_discovery.mapping_xml
        addr_el = map_xml.find(".//host[@address='%s']" % (addr))
        if addr_el is None:
            addr_el = E.host(address=addr)
            map_xml.append(addr_el)
        uuid_el = addr_el.xpath("uuid[@proto='%s' and @port='%s']" % (proto, port), smart_strings=False)
        if not len(uuid_el):
            uuid_el = E.uuid("", proto=proto, port=port)
            addr_el.append(uuid_el)
        else:
            uuid_el = uuid_el[0]
        if uuid_el.text != uuid:
            uuid_el.text = uuid
            id_discovery.save_mapping()

    @staticmethod
    def is_pending(conn_str):
        return conn_str in id_discovery.pending

    @staticmethod
    def has_mapping(conn_str):
        return conn_str in id_discovery.mapping

    @staticmethod
    def get_mapping(conn_str):
        return id_discovery.mapping[conn_str]

    @staticmethod
    def check_timeout(cur_time):
        del_list = []
        for _conn_str, cur_ids in id_discovery.pending.iteritems():
            diff_time = abs(cur_ids.init_time - cur_time)
            if diff_time > id_discovery.timeout:
                del_list.append(cur_ids)
        for cur_ids in del_list:
            # set last try flag
            id_discovery.last_try[cur_ids.conn_str] = cur_time
            cur_ids.send_return("timeout triggered, closing")
