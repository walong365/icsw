#!/usr/bin/python-init -OtW default
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2010,2011,2012,2013 Andreas Lang-Nevyjel, init.at
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

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import logging_tools
import process_tools
import server_command
import threading_tools
from lxml.builder import E # @UnresolvedImport

from initat.md_config_server.config import global_config

try:
    from md_config_server.version import VERSION_STRING
except ImportError:
    VERSION_STRING = "?.?"

from django.db.models import Q
from django.db import connection
from initat.cluster.backbone.models import device

try:
    import mk_livestatus
except ImportError:
    mk_livestatus = None

class status_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context, init_logger=True)
        self.register_func("get_node_status", self._get_node_status)
        connection.close()
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
            try:
                self.__socket = mk_livestatus.Socket(sock_name)
            except:
                self.log("cannot open livestatus socket %s : %s" % (sock_name, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                self.__socket = None
            else:
                self.log("reopened livestatus socket %s" % (sock_name))
        return self.__socket
    def _get_node_status(self, *args, **kwargs):
        src_id, srv_com = (args[0], server_command.srv_command(source=args[1]))
        if mk_livestatus:
            pk_list = srv_com.xpath(None, ".//device_list/device/@pk")
            dev_names = sorted([cur_dev.full_name for cur_dev in device.objects.filter(Q(pk__in=pk_list))])
            try:
                cur_sock = self._open()
                if cur_sock:
                    srv_com.set_result("status for %s" % (logging_tools.get_plural("device", len(dev_names))))
                    query_field = [
                            "GET services",
                            "Columns: host_name description state plugin_output last_check",
                    ]
                    query_field.append("Filter: host_name = %s" % (dev_names[0]))
                    if len(dev_names) > 1:
                        query_field.extend([
                                          "Filter: host_name = %s" % (dev_n) for dev_n in dev_names[1:]])
                        query_field.append("Or: %d" % (len(dev_names)))
                    query_field.append("")
                    query_str = "\n".join(query_field)
                    cur_query = cur_sock.query(query_str)
                    result = cur_query.get_list()
                    node_results = {}
                    for entry in result:
                        host_name = entry.pop("host_name")
                        output = entry["plugin_output"]
                        if type(output) == list:
                            entry["plugin_output"] = ",".join(output)
                        node_results.setdefault(host_name, []).append((entry["description"], entry))
                    # rewrite to xml
                    srv_com["result"] = E.node_results(
                        *[E.node_result(
                            *[E.result(**entry) for sort_val, entry in sorted(value)],
                            name=key) for key, value in node_results.iteritems()]
                    )
                    # print srv_com.pretty_print()
                else:
                    srv_com.set_result("cannot connect", server_command.SRV_REPLY_STATE_CRITICAL)
            except:
                self._close()
                self.log("fetch exception: %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                srv_com.set_result("exception during fetch", server_command.SRV_REPLY_STATE_CRITICAL)
        else:
            srv_com.set_result("no mk_livestatus found", server_command.SRV_REPLY_STATE_CRITICAL)
        self.send_pool_message("send_command", src_id, unicode(srv_com))

