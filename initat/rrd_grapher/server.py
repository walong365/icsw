# Copyright (C) 2007-2009,2013-2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file belongs to the rrd-server package
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
""" server-part of rrd-grapher """

import json
import os
import stat
import time

from django.conf import settings

from initat.cluster.backbone import db_tools
from initat.cluster.backbone.models import device, MachineVector
from initat.cluster.backbone.server_enums import icswServiceEnum
from initat.rrd_grapher.config import global_config
from initat.rrd_grapher.graph import GraphProcess
from initat.rrd_grapher.rrd_grapher_struct import DataStore
from initat.rrd_grapher.stale import GraphStaleProcess
from initat.tools import configfile, logging_tools, \
    server_mixins, threading_tools


@server_mixins.RemoteCallProcess
class ServerProcess(
    server_mixins.ICSWBasePool,
    server_mixins.RemoteCallMixin,
):
    def __init__(self):
        threading_tools.icswProcessPool.__init__(self, "main", zmq=True)
        self.CC.init(icswServiceEnum.grapher_server, global_config)
        self.CC.check_config()
        # close connection (daemonizing)
        db_tools.close_connection()
        self.CC.read_config_from_db(
            [
                (
                    "GRAPH_ROOT_DEBUG",
                    configfile.str_c_var(
                        os.path.abspath(
                            os.path.join(
                                settings.STATIC_ROOT_DEBUG,
                                "graphs"
                            )
                        ),
                        database=True
                    )
                ),
                (
                    "GRAPH_ROOT",
                    configfile.str_c_var(
                        os.path.abspath(
                            os.path.join(
                                settings.STATIC_ROOT_DEBUG if global_config["DEBUG"] else settings.STATIC_ROOT,
                                "graphs"
                            )
                        ),
                        database=True
                    )
                ),
            ]
        )
        if global_config["RRD_CACHED_SOCKET"] == "/var/run/rrdcached.sock":
            global_config["RRD_CACHED_SOCKET"] = os.path.join(global_config["RRD_CACHED_DIR"], "rrdcached.sock")
        self.CC.log_config()
        # re-insert config
        self.CC.re_insert_config()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("hup_error", self._hup_error)
        self.add_process(GraphProcess("graph"), start=True)
        self.add_process(GraphStaleProcess("stale"), start=True)
        db_tools.close_connection()
        self._init_network_sockets()
        DataStore.setup(self)
        self._db_debug = threading_tools.DBDebugBase(self.log, force_disable=False)
        # self.test("x")

    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True

    def _hup_error(self, err_cause):
        self.log("got sighup", logging_tools.LOG_LEVEL_WARN)

    def process_start(self, src_process, src_pid):
        self.CC.process_added(src_process, src_pid)

    def _init_network_sockets(self):
        self.network_bind(
            need_all_binds=False,
            bind_to_localhost=True,
            service_type_enum=icswServiceEnum.grapher_server,
            simple_server_bind=True,
            pollin=self.remote_call,
        )

    @server_mixins.RemoteCall()
    def get_node_rrd(self, srv_com, **kwargs):
        # print("got", unicode(srv_com))
        # database debug
        self._db_debug.start_call("node_rrd")
        node_results = []
        s_time = time.time()
        dev_list = srv_com.xpath(".//device_list", smart_strings=False)[0]
        pk_list = [int(cur_pk) for cur_pk in dev_list.xpath(".//device/@pk", smart_strings=False)]
        for dev_pk in pk_list:
            cur_res = {"pk": dev_pk}
            if DataStore.has_machine_vector(dev_pk):
                # web mode (sorts entries)
                _struct = DataStore.get_instance(dev_pk).vector_struct()
                _struct.extend(DataStore.compound_struct(_struct))
                cur_res["struct"] = _struct
            else:
                self.log("no MachineVector found for device {:d}".format(dev_pk), logging_tools.LOG_LEVEL_WARN)
            node_results.append(cur_res)
        e_time = time.time()
        self.log(
            "node_rrd for {} took {}".format(
                logging_tools.get_plural("device", len(pk_list)),
                logging_tools.get_diff_time_str(e_time - s_time),
            )
        )
        # _json = self._to_json(node_results, set(["info", "active", "key", "name", "part", "pk"]))
        # pprint.pprint(node_results, depth=5)
        self._db_debug.end_call()
        srv_com["result"] = json.dumps(node_results)
        srv_com.set_result("set results for {}".format(logging_tools.get_plural("node", len(node_results))))
        return srv_com

    @server_mixins.RemoteCall()
    def get_0mq_id(self, srv_com, **kwargs):
        srv_com["zmq_id"] = self.bind_id
        srv_com.set_result("0MQ_ID is {}".format(self.bind_id))
        return srv_com

    @server_mixins.RemoteCall()
    def status(self, srv_com, **kwargs):
        srv_com.set_result("status is up and running")
        return srv_com

    @server_mixins.RemoteCall(sync=False, target_process="graph")
    def graph_rrd(self, srv_com, **kwargs):
        # print("graph", unicode(srv_com))
        # here we have to possibility to modify srv_com before we send it to the remote process
        return srv_com

    @server_mixins.RemoteCall()
    def check_rrd_graph_freshness(self, srv_com, **kwargs):
        device_idx_list = []
        for child in srv_com.tree.getchildren():
            if "device_pks" in child.tag:
                for child in child.getchildren():
                    device_idx_list.append(int(child.text))

        devices = device.objects.filter(idx__in=device_idx_list)

        result_dict = {}

        for _device in devices:
            machine_vector = MachineVector.objects.filter(device=_device)
            newest_timestamp = 0

            if machine_vector:
                machine_vector = machine_vector[0]

                for entry in machine_vector.mvstructentry_set.all():
                    try:
                        newest_timestamp = max(newest_timestamp, os.stat(entry.file_name)[stat.ST_MTIME])
                    except:
                        pass

            result_dict[_device.idx] = newest_timestamp

        srv_com.set_result(result_dict)

        return srv_com

    def loop_end(self):
        pass

    def loop_post(self):
        self.network_unbind()
        self.CC.close()
