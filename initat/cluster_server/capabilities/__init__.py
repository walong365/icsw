# Copyright (C) 2001-2008,2012-2014 Andreas Lang-Nevyjel
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
""" cluster-server, capability process """

from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models import device, user, user_scan_result, user_scan_run
from initat.cluster.backbone.routing import get_server_uuid
from initat.cluster_server.capabilities import usv_server, quota, virtual_desktop, user_scan
from initat.cluster_server.config import global_config
from initat.cluster_server.notify import notify_mixin
import cluster_location
import config_tools
import configfile
import datetime
import initat.cluster_server.modules
import logging_tools
import os
import stat
import pprint
import process_tools
import server_command
import threading_tools
import time
import uuid_tools
import zmq


class capability_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context
        )
        connection.close()
        self._init_network()
        self._init_capabilities()
        self.__last_user_scan = None
        self.__scan_running = False
        self.register_timer(self._update, 2 if global_config["DEBUG"] else 30, instant=True)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self.vector_socket.close()
        self.__log_template.close()

    def _init_network(self):
        # connection to local collserver socket
        conn_str = process_tools.get_zmq_ipc_name("vector", s_name="collserver", connect_to_root_instance=True)
        vector_socket = self.zmq_context.socket(zmq.PUSH)  # @UndefinedVariable
        vector_socket.setsockopt(zmq.LINGER, 0)  # @UndefinedVariable
        vector_socket.connect(conn_str)
        self.vector_socket = vector_socket
        self.log("connected vector_socket to {}".format(conn_str))

    def _init_capabilities(self):
        self.log("init server capabilities")
        self.__server_cap_dict = {
            "usv_server": usv_server.usv_server_stuff(self),
            "quota_scan": quota.quota_stuff(self),
            "virtual_desktop": virtual_desktop.virtual_desktop_stuff(self),
            "user_scan": user_scan.user_scan_stuff(self),
            # "dummy"      : dummy_stuff(self),
            }
        self.__cap_list = []
        for key, _value in self.__server_cap_dict.iteritems():
            _sql_info = config_tools.server_check(server_type=key)
            if _sql_info.effective_device:
                self.__cap_list.append(key)
            self.log("capability {}: {}".format(key, "enabled" if key in self.__cap_list else "disabled"))

    def _update(self):
        cur_time = time.time()
        drop_com = server_command.srv_command(command="set_vector")
        for cap_name in self.__cap_list:
            self.__server_cap_dict[cap_name](cur_time, drop_com)
        self.vector_socket.send_unicode(unicode(drop_com))
