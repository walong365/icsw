#!/usr/bin/python-init -OtW default
#
# Copyright (C) 2001-2014 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
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
""" status process """

from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models import device
from initat.md_config_server.config import global_config
from lxml.builder import E # @UnresolvedImport
import csv
import socket
import logging_tools
import os
import process_tools
import server_command
import threading_tools

try:
    from md_config_server.version import VERSION_STRING
except ImportError:
    VERSION_STRING = "?.?"

class live_query(object):
    def __init__(self, conn, resource):
        self._conn = conn
        self._resource = resource
        self._columns = []
        self._filters = []
    def call(self):
        if self._columns:
            return self._conn.call(str(self), self._columns)
        else:
            return self._conn.call(str(self))
    def __str__(self):
        r_field = ["GET %s" % (self._resource)]
        if self._columns:
            r_field.append("Columns: %s" % (" ".join(self._columns)))
        r_field.extend(self._filters)
        return "\n".join(r_field + ["", ""])
    def columns(self, *args):
        self._columns = args
        return self
    def filter(self, key, op, value):
        if type(value) == list:
            for entry in value:
                self._filters.append("Filter: %s %s %s" % (key, op, entry))
            if len(value) > 1:
                self._filters.append("Or: %d" % (len(value)))
        else:
            self._filters.append("Filter: %s %s %s" % (key, op, value))
        return self

class live_socket(object):
    def __init__(self, peer_name):
        self.peer = peer_name
    def __getattr__(self, name):
        return live_query(self, name)
    def call(self, request, columns=None):
        try:
            if len(self.peer) == 2:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            else:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(self.peer)
            s.send(request)
            s.shutdown(socket.SHUT_WR)
            csv_lines = csv.DictReader(s.makefile(), columns, delimiter=';')
            return list(csv_lines)
        finally:
            s.close()

class status_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context, init_logger=True)
        connection.close()
        self.register_func("get_node_status", self._get_node_status)
        self.__socket = None
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def loop_post(self):
        self._close()
        self.__log_template.close()
    def _close(self):
        if self.__socket:
            del self.__socket
            self.__socket = None
    def _open(self):
        if self.__socket is None:
            sock_name = "/opt/%s/var/live" % (global_config["MD_TYPE"])
            if os.path.exists(sock_name):
                self.__socket = live_socket(sock_name)
            else:
                self.log("socket '%s' does not exist" % (sock_name), logging_tools.LOG_LEVEL_ERROR)
        return self.__socket
    def _get_node_status(self, *args, **kwargs):
        src_id, srv_com = (args[0], server_command.srv_command(source=args[1]))
        pk_list = srv_com.xpath(".//device_list/device/@pk", smart_strings=False)
        dev_names = sorted([cur_dev.full_name for cur_dev in device.objects.filter(Q(pk__in=pk_list))])
        self.log("querying %s: %s" % (logging_tools.get_plural("device", len(dev_names)), ", ".join(sorted(dev_names))))
        try:
            cur_sock = self._open()
            if cur_sock:
                query = cur_sock.services.columns("host_name", "description", "state", "plugin_output", "last_check").filter("host_name", "=", dev_names)
                result = query.call()
                node_results = {}
                for entry in result:
                    try:
                        # cleanup entry
                        entry = {key: value for key, value in entry.iteritems() if value != None}
                        host_name = entry.pop("host_name")
                        output = entry["plugin_output"]
                        if type(output) == list:
                            entry["plugin_output"] = ",".join(output)
                        if host_name:
                            node_results.setdefault(host_name, []).append((entry["description"], entry))
                    except:
                        self.log("error processing livestatus entry '%s': %s" % (str(entry), process_tools.get_except_info()),
                            logging_tools.LOG_LEVEL_CRITICAL)
                if len(node_results) == len(dev_names):
                    srv_com.set_result("status for %s" % (logging_tools.get_plural("device", len(dev_names))))
                else:
                    srv_com.set_result("status for %s (%d requested)" % (logging_tools.get_plural("device", len(node_results.keys())), len(dev_names)), server_command.SRV_REPLY_STATE_WARN)
                srv_com["result"] = E.node_results(
                    *[E.node_result(
                        *[E.result(**entry) for _sort_val, entry in sorted(value)],
                        name=key) for key, value in node_results.iteritems()]
                )
                # print srv_com.pretty_print()
            else:
                srv_com.set_result("cannot connect to socket", server_command.SRV_REPLY_STATE_CRITICAL)
        except:
            self.log("fetch exception: %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            exc_info = process_tools.exception_info()
            for line in exc_info.log_lines:
                self.log(" - %s" % (line), logging_tools.LOG_LEVEL_ERROR)
            self._close()
            srv_com.set_result("exception during fetch", server_command.SRV_REPLY_STATE_CRITICAL)
        self.send_pool_message("send_command", src_id, unicode(srv_com))

