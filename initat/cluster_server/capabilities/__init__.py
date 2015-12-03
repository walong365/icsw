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

import importlib
import inspect
import os
import time

import zmq
from lxml import etree

from initat.cluster.backbone import db_tools
from initat.cluster.backbone import factories
from initat.cluster_server.capabilities import base
from initat.cluster_server.config import global_config
from initat.tools import config_tools, logging_tools, process_tools, server_command, threading_tools


class capability_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context
        )
        db_tools.close_connection()
        self._init_network()
        self._init_capabilities()
        self.__last_user_scan = None
        self.__scan_running = False
        self.register_timer(self._update, 2 if global_config["DEBUG"] else 30, instant=True)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self.collectd_socket.close()
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
        # connection to local collectd server
        _cc_str = "tcp://localhost:8002"
        collectd_socket = self.zmq_context.socket(zmq.PUSH)
        collectd_socket.setsockopt(zmq.LINGER, 0)
        collectd_socket.connect(_cc_str)
        self.log("connected collectd_socket to {}".format(_cc_str))
        self.collectd_socket = collectd_socket

    def _init_capabilities(self):
        self.__cap_list = []
        if global_config["BACKUP_DATABASE"]:
            self.log("doing database backup, ignoring capabilities", logging_tools.LOG_LEVEL_WARN)
        else:
            # read caps
            _dir = os.path.dirname(__file__)
            self.log("init server capabilities from directory {}".format(_dir))
            SRV_CAPS = []
            for entry in os.listdir(_dir):
                if entry.endswith(".py") and entry not in ["__init__.py"]:
                    _imp_name = "initat.cluster_server.capabilities.{}".format(entry.split(".")[0])
                    _mod = importlib.import_module(_imp_name)
                    for _key in dir(_mod):
                        _value = getattr(_mod, _key)
                        if inspect.isclass(_value) and issubclass(_value, base.bg_stuff) and _value != base.bg_stuff:
                            SRV_CAPS.append(_value)
            self.log("checking {}".format(logging_tools.get_plural("capability", len(SRV_CAPS))))
            self.__server_cap_dict = {}
            self.__cap_list = []
            sys_cc = factories.ConfigCatalog(name="local", system_catalog=True)
            for _srv_cap in SRV_CAPS:
                cap_name = _srv_cap.Meta.name
                try:
                    cap_descr = _srv_cap.Meta.description,
                except:
                    self.log("capability {} has no description set, ignoring...".format(cap_name), logging_tools.LOG_LEVEL_ERROR)
                else:
                    _new_c = factories.Config(
                        name=cap_name,
                        description=cap_descr,
                        config_catalog=sys_cc,
                        server_config=True,
                        system_config=True,
                    )
                    _sql_info = config_tools.server_check(server_type=cap_name)
                    if _sql_info.effective_device:
                        self.__cap_list.append(cap_name)
                        self.__server_cap_dict[cap_name] = _srv_cap(self, _sql_info)
                        self.log(
                            "capability {} is enabled on {}".format(
                                cap_name,
                                unicode(_sql_info.effective_device),
                            )
                        )
                    else:
                        self.log("capability {} is disabled".format(cap_name))

    def _update(self):
        cur_time = time.time()
        drop_com = server_command.srv_command(command="set_vector")
        mach_vectors = []
        for cap_name in self.__cap_list:
            self.__server_cap_dict[cap_name](cur_time, drop_com, mach_vectors)
        self.vector_socket.send_unicode(unicode(drop_com))
        for _mv in mach_vectors:
            try:
                self.collectd_socket.send_unicode(etree.tostring(_mv))
            except:
                self.log(
                    "unable to send machvector to collectd: {}".format(
                        process_tools.get_except_info(),
                    ),
                    logging_tools.LOG_LEVEL_ERROR,
                )
