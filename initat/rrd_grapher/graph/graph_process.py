# Copyright (C) 2007-2009,2013-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file belongs to the rrd-server package
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
""" grapher part of rrd-grapher service """

import json
import select
import socket
import time

import dateutil.parser
from django.db.models import Q

from initat.cluster.backbone import db_tools
from initat.cluster.backbone.available_licenses import LicenseEnum
from initat.cluster.backbone.models import device, GraphSetting
from initat.cluster.backbone.models.license import LicenseLockListDeviceService, LicenseUsage, \
    LicenseParameterTypeEnum
from initat.tools import logging_tools, process_tools, server_mixins, server_command, threading_tools
from .graph_color import Colorizer
from .graph_graph import RRDGraph
from ..config import global_config

FLOAT_FMT = "{:.6f}"


class GraphProcess(threading_tools.process_obj, server_mixins.OperationalErrorMixin):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True,
        )
        db_tools.close_connection()
        self.register_func("graph_rrd", self._graph_rrd)
        self.graph_root = global_config["GRAPH_ROOT"]
        self.graph_root_debug = global_config["GRAPH_ROOT_DEBUG"]
        self.log("graphs go into {} for non-debug calls and into {} for debug calls".format(self.graph_root, self.graph_root_debug))
        self.colorizer = Colorizer(self.log)
        self.__rrdcached_socket = None

    def _open_rrdcached_socket(self):
        self._close_rrdcached_socket()
        try:
            self.__rrdcached_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.__rrdcached_socket.connect(global_config["RRD_CACHED_SOCKET"])
        except:
            self.log("error opening rrdcached socket: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            self.__rrdcached_socket = None
        else:
            self.log("connected to rrdcached socket {}".format(global_config["RRD_CACHED_SOCKET"]))
        self.__flush_cache = set()

    def _close_rrdcached_socket(self):
        if self.__rrdcached_socket:
            try:
                self.__rrdcached_socket.close()
            except:
                self.log("error closing rrdcached socket: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            else:
                self.log("closed rrdcached socket")
            self.__rrdcached_socket = None

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self._close()
        self.__log_template.close()

    def _close(self):
        pass

    def flush_rrdcached(self, f_names):
        if f_names:
            f_names -= self.__flush_cache
            if f_names:
                self.__flush_cache |= f_names
                if self.__rrdcached_socket:
                    _s_time = time.time()
                    self.log("sending flush() to rrdcached for {}".format(logging_tools.get_plural("file", len(f_names))))
                    _lines = [
                        "BATCH"
                    ] + [
                        "FLUSH {}".format(_f_name) for _f_name in f_names
                    ] + [
                        ".",
                        "",
                    ]
                    self.__rrdcached_socket.send("\n".join(_lines))
                    _read, _write, _exc = select.select([self.__rrdcached_socket.fileno()], [], [], 5000)
                    _e_time = time.time()
                    if not _read:
                        self.log("read list is empty after {}".format(logging_tools.get_diff_time_str(_e_time - _s_time)), logging_tools.LOG_LEVEL_ERROR)
                    else:
                        _recv = self.__rrdcached_socket.recv(16384)
                else:
                    self.log("no valid rrdcached_socket, skipping flush()", logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("no file names given, skipping flush()", logging_tools.LOG_LEVEL_WARN)

    def _graph_rrd(self, *args, **kwargs):
        srv_com = server_command.srv_command(source=args[0])
        orig_dev_pks = srv_com.xpath(".//device_list/device/@pk", smart_strings=False)
        orig_dev_pks = device.objects.filter(
            Q(pk__in=orig_dev_pks) & Q(machinevector__pk__gt=0)
        ).values_list("pk", flat=True)
        dev_pks = [
            dev_pk for dev_pk in orig_dev_pks
            if not LicenseLockListDeviceService.objects.is_device_locked(LicenseEnum.graphing, dev_pk)
        ]
        if len(orig_dev_pks) != len(dev_pks):
            self.log(
                "Access to device rrds denied to to locking: {}".format(set(orig_dev_pks).difference(dev_pks)),
                logging_tools.LOG_LEVEL_ERROR,
            )
        LicenseUsage.log_usage(LicenseEnum.graphing, LicenseParameterTypeEnum.device, dev_pks)
        graph_keys = json.loads(srv_com["*graph_key_list"])
        para_dict = {}
        for para in srv_com.xpath(".//parameters", smart_strings=False)[0]:
            para_dict[para.tag] = para.text
        # cast to integer
        para_dict = {key: int(value) if key in ["graph_setting"] else value for key, value in para_dict.iteritems()}
        for key in ["start_time", "end_time"]:
            # cast to datetime
            para_dict[key] = dateutil.parser.parse(para_dict[key])
        para_dict["graph_setting"] = GraphSetting.objects.get(Q(pk=para_dict["graph_setting"]))
        para_dict["graph_setting"].to_enum()
        for key, _default in [
            ("debug_mode", "0"),
        ]:
            para_dict[key] = True if int(para_dict.get(key, "0")) else False
        self._open_rrdcached_socket()
        try:
            graph_list = RRDGraph(
                self.graph_root_debug if para_dict.get("debug_mode", False) else self.graph_root,
                self.log,
                self.colorizer,
                para_dict,
                self
            ).graph(dev_pks, graph_keys)
        except:
            for _line in process_tools.exception_info().log_lines:
                self.log(_line, logging_tools.LOG_LEVEL_ERROR)
            srv_com["graphs"] = []
            srv_com.set_result(
                "error generating graphs: {}".format(process_tools.get_except_info()),
                server_command.SRV_REPLY_STATE_CRITICAL
            )
        else:
            srv_com["graphs"] = graph_list
            srv_com.set_result(
                "generated {}".format(logging_tools.get_plural("graph", len(graph_list))),
                server_command.SRV_REPLY_STATE_OK
            )
        self._close_rrdcached_socket()
        self.send_pool_message("remote_call_async_result", unicode(srv_com))
