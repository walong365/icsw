# Copyright (C) 2014-2016 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
#
# Send feedback to: <lang-nevyjel@init.at>
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

"""

syncer process for md-config-server
keeps the monitoring-clients in sync and collects vital information about their installed
software and performance

"""

from django.db.models import Q

from initat.cluster.backbone import db_tools, routing
from initat.cluster.backbone.models import device
from initat.cluster.backbone.server_enums import icswServiceEnum
from initat.md_config_server.config import global_config, SyncConfig
from initat.md_sync_server.base_config import RemoteServer
from initat.tools import config_tools, logging_tools, server_command, threading_tools


__all__ = [
    "RemoteServer",
    "SyncerProcess",
]


class SyncerProcess(threading_tools.process_obj):
    def process_init(self):
        # global_config.close()
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True
        )
        db_tools.close_connection()
        self.router_obj = config_tools.RouterObject(self.log)
        self.register_func("file_content_result", self._file_content_result)
        self.register_func("file_content_bulk_result", self._file_content_result)
        self.register_func("check_for_slaves", self._check_for_slaves)
        self.register_func("check_for_redistribute", self._check_for_redistribute)
        self.register_func("build_info", self._build_info)
        self.register_func("slave_info", self._slave_info)
        self.__build_in_progress, self.__build_version = (False, 0)
        self.__master_config = None
        # this used to be just set in _check_for_slaves, but apparently check_for_redistribute can be called before that
        self.__slave_configs, self.__slave_lut = ({}, {})

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self.__log_template.close()

    def _check_for_slaves(self, **kwargs):
        master_server = device.objects.get(Q(pk=global_config["SERVER_IDX"]))
        slave_servers = device.objects.exclude(
            # exclude master server
            Q(pk=master_server.idx)
        ).filter(
            Q(device_config__config__config_service_enum__enum_name=icswServiceEnum.monitor_slave.name)
        ).select_related(
            "domain_tree_node"
        )
        # slave configs
        self.__master_config = SyncConfig(self, master_server, distributed=True if len(slave_servers) else False)
        self.__slave_configs, self.__slave_lut = ({}, {})
        # connect to local relayer
        self.__primary_slave_uuid = routing.get_server_uuid(icswServiceEnum.monitor_slave, master_server.uuid)
        self.log("  master {} (IP {}, {})".format(master_server.full_name, "127.0.0.1", self.__primary_slave_uuid))
        self.send_pool_message("register_remote", "127.0.0.1", self.__primary_slave_uuid, icswServiceEnum.monitor_slave.name)
        _send_data = [self.__master_config.get_send_data()]
        if len(slave_servers):
            self.log(
                "found {}: {}".format(
                    logging_tools.get_plural("slave_server", len(slave_servers)),
                    ", ".join(sorted([cur_dev.full_name for cur_dev in slave_servers]))
                )
            )
            for cur_dev in slave_servers:
                _slave_c = SyncConfig(
                    self,
                    cur_dev,
                    slave_name=cur_dev.full_name,
                    master_server=master_server,
                )
                self.__slave_configs[cur_dev.pk] = _slave_c
                self.__slave_lut[cur_dev.full_name] = cur_dev.pk
                self.__slave_lut[cur_dev.uuid] = cur_dev.pk
                self.log(
                    "  slave {} (IP {}, {})".format(
                        _slave_c.monitor_server.full_name,
                        _slave_c.slave_ip,
                        _slave_c.monitor_server.uuid
                    )
                )
                _send_data.append(_slave_c.get_send_data())
                # if _slave_c.slave_ip:
                #    self.send_pool_message("register_slave", _slave_c.slave_ip, _slave_c.monitor_server.uuid)
                # else:
                #    self.log("slave has an invalid IP", logging_tools.LOG_LEVEL_CRITICAL)
        else:
            self.log("no slave-servers found")
        # send distribution info to local syncer
        distr_info = server_command.srv_command(
            command="distribute_info",
            info=server_command.compress(_send_data, marshal=True),
        )
        self.send_sync_command(distr_info)

    def send_sync_command(self, srv_com):
        self.send_pool_message("send_command", self.__primary_slave_uuid, unicode(srv_com))

    def send_command(self, src_id, srv_com):
        self.send_pool_message("send_command", "urn:uuid:{}:relayer".format(src_id), unicode(srv_com))

    def _check_for_redistribute(self, *args, **kwargs):
        for slave_config in self.__slave_configs.itervalues():
            slave_config.check_for_resend()

    def _file_content_result(self, *args, **kwargs):
        srv_com = server_command.srv_command(source=args[0])
        slave_name = srv_com["slave_name"].text
        if slave_name in self.__slave_lut:
            self.__slave_configs[self.__slave_lut[slave_name]].file_content_info(srv_com)
        else:
            self.log("unknown slave_name '{}'".format(slave_name), logging_tools.LOG_LEVEL_ERROR)

    def _slave_info(self, *args, **kwargs):
        srv_com = server_command.srv_command(source=args[0])
        action = srv_com["*action"]
        if action == "info_list":
            info_list = server_command.decompress(srv_com["*slave_info"], json=True)
            for info in info_list:
                if info["master"]:
                    if self.__master_config is not None:
                        self.__master_config.set_info(info)
                    else:
                        self.log("not master config set", logging_tools.LOG_LEVEL_WARN)
                else:
                    _pure_uuid = routing.get_pure_uuid(info["slave_uuid"])
                    if _pure_uuid in self.__slave_lut:
                        _pk = self.__slave_lut[_pure_uuid]
                        self.__slave_configs[_pk].set_info(info)
                    else:
                        self.log("got unknown UUID '{}' ({})".format(info["slave_uuid"], _pure_uuid), logging_tools.LOG_LEVEL_ERROR)
        else:
            _pure_uuid = routing.get_pure_uuid(srv_com["*slave_uuid"])
            if _pure_uuid in self.__slave_lut:
                _pk = self.__slave_lut[_pure_uuid]
                self.__slave_configs[_pk].handle_info_action(action, srv_com)
            else:
                self.log("got unknown UUID '{}' ({})".format(srv_com["*slave_uuid"], _pure_uuid), logging_tools.LOG_LEVEL_ERROR)

    def _build_info(self, *args, **kwargs):
        # build info send from relayer
        _vals = list(args)
        _bi_type = _vals.pop(0)
        if _bi_type == "start_build":
            # config build started
            self.__build_in_progress, self.__build_version = (True, _vals.pop(0))
            self.log("build started ({:d})".format(self.__build_version))
            self._master_md = self.__master_config.start_build(self.__build_version)
            for _conf in self.__slave_configs.values():
                _conf.start_build(self.__build_version, master=self._master_md)
        elif _bi_type == "end_build":
            self.__build_in_progress = False
            self.log("build ended ({:d})".format(self.__build_version))
            self.__master_config.end_build()
            # trigger reload when sync is done
            for _slave in self.__slave_configs.itervalues():
                _slave.reload_after_sync()
            self.__master_config.reload_after_sync()
        elif _bi_type == "unreachable_devices":
            self.__master_config.unreachable_devices(_vals[0])
        elif _bi_type == "unreachable_device":
            self.__master_config.unreachable_device(_vals[0], _vals[1], _vals[2])
        elif _bi_type in ["start_config_build", "end_config_build"]:
            _srv_name = _vals.pop(0)
            if _srv_name in self.__slave_lut:
                # slave
                self.__slave_configs[self.__slave_lut[_srv_name]].config_ts(_bi_type.split("_")[0])
            else:
                # master
                self.__master_config.config_ts(_bi_type.split("_")[0])
        elif _bi_type == "device_count":
            _srv_name = _vals.pop(0)
            if _srv_name in self.__slave_lut:
                # slave
                self.__slave_configs[self.__slave_lut[_srv_name]].device_count(_vals[0])
            else:
                # master
                self.__master_config.device_count(_vals[0])
        elif _bi_type == "sync_slave":
            slave_name = _vals.pop(0)
            if slave_name in self.__slave_lut:
                _slave = self.__slave_configs[self.__slave_lut[slave_name]]
                # TODO, set sync_start
                # if not self.__md_struct.num_runs:
                #    self.__md_struct.sync_start = cluster_timezone.localize(datetime.datetime.now())
                # self.__md_struct.num_runs += 1

                _slave.send_slave_command("sync_slave")
            else:
                self.log("unknown slave '{}'".format(slave_name), logging_tools.LOG_LEVEL_CRITICAL)
        else:
            self.log("unknown build_info '{}'".format(str(args)), logging_tools.LOG_LEVEL_CRITICAL)
