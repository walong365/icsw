# Copyright (C) 2014-2016 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-sync-server
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

"""

syncer process for md-config-server
keeps the monitoring-clients in sync and collects vital information about their installed
software and performance

"""

from django.db.models import Q

from initat.host_monitoring.client_enums import icswServiceEnum
from initat.tools import logging_tools, server_command, threading_tools
from initat.icsw.service.instance import InstanceXML
from .config import global_config
from .sync_config import SyncConfig


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
        self.inst_xml = InstanceXML(self.log)
        self.__register_timer = False
        self.register_func("file_content_result", self._file_content_result)
        self.register_func("file_content_bulk_result", self._file_content_result)
        self.register_func("check_for_redistribute", self._check_for_redistribute)
        self.register_func("build_info", self._build_info)
        self.register_func("distribute_info", self._distribute_info)
        self.register_func("satellite_info", self._satellite_info)
        self.register_func("slave_command", self._slave_command)
        self.__build_in_progress, self.__build_version = (False, 0)
        # setup local master, always set (also on satellite nodes)
        self.__local_master = None
        # master config for distribution master (only set on distribution master)
        self.__master_config = None
        # registered at master
        self.__registered_at_master = False
        self.register_timer(self._init_local_master, 60, first_timeout=2)
        # this used to be just set in _check_for_slaves, but apparently check_for_redistribute can be called before that
        self.__slave_configs, self.__slave_lut = ({}, {})

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self.__log_template.close()

    def _init_local_master(self):
        if not self.__local_master and "MD_TYPE" in global_config:
            self.__local_master = SyncConfig(self, None, distributed=False)
            if self.__master_config:
                self.__master_config.set_local_master(self.__local_master)
            self._check_for_register_at_master()
        self._send_satellite_info()

    def _send_satellite_info(self):
        if self.__registered_at_master and self.__local_master:
            self.send_to_config_server(
                server_command.srv_command(
                    command="satellite_info",
                    uuid=self.__local_master.config_store["slave.uuid"],
                    satellite_info=server_command.compress(self.__local_master.get_satellite_info(), json=True)
                )
            )

    def send_to_config_server(self, srv_com):
        self.send_command(
            self.__master_config.master_uuid,
            unicode(srv_com),
        )

    def _distribute_info(self, dist_info, **kwargs):
        self.log("distribution info has {}".format(logging_tools.get_plural("entry", len(dist_info))))
        self.__slave_configs, self.__slave_lut = ({}, {})
        for _di in dist_info:
            if _di["master"]:
                self.log("found master entry")
                self.__master_config = SyncConfig(self, _di, distributed=True if len(dist_info) > 1 else False, local_master=self.__local_master)
                # register md-config-server
                self.send_pool_message(
                    "register_remote",
                    self.__master_config.master_ip,
                    self.__master_config.master_uuid,
                    _di["master_port"],
                )
            else:
                self.log("found slave entry ({})".format(", ".join(sorted(_di.keys()))))
                _slave_c = SyncConfig(
                    self,
                    _di,
                )
                self.__slave_configs[_slave_c.pk] = _slave_c
                self.__slave_lut[_slave_c.name] = _slave_c.pk
                self.__slave_lut[_slave_c.slave_uuid] = _slave_c.pk
                self.log(
                    "  slave {} (IP {}, {})".format(
                        _slave_c.name,
                        _slave_c.slave_ip,
                        _slave_c.slave_uuid,
                    )
                )
                if _slave_c.slave_ip:
                    self.send_pool_message(
                        "register_remote",
                        _slave_c.slave_ip,
                        _slave_c.slave_uuid,
                        self.inst_xml.get_port_dict(icswServiceEnum.monitor_slave, command=True)
                    )
        if not self.__register_timer:
            self.__register_timer = True
            _reg_timeout, _first_timeout = (600, 2)  # (600, 15)
            self.log("will send register_msg in {:d} (then {:d}) seconds".format(_first_timeout, _reg_timeout))
            self.register_timer(self._send_register_msg, _reg_timeout, instant=global_config["DEBUG"], first_timeout=_first_timeout)
        self.send_info_message()

    def _send_register_msg(self, **kwargs):
        for _slave_struct in [self.__master_config] + self.__slave_configs.values():
            if _slave_struct.master:
                self.log("register_master not necessary for master")
            else:
                master_ip = _slave_struct.master_ip
                master_uuid = _slave_struct.master_uuid
                _slave_struct.send_slave_command(
                    "register_master",
                    master_ip=master_ip,
                    master_uuid=master_uuid,
                    master_port="{:d}".format(global_config["COMMAND_PORT"]),
                )
        self.send_info_message()

    def send_info_message(self):
        info_list = [
            _entry.get_info_dict() for _entry in [self.__master_config] + self.__slave_configs.values()
        ]
        srv_com = server_command.srv_command(
            command="slave_info",
            action="info_list",
            slave_info=server_command.compress(info_list, json=True)
        )
        self.send_command(self.__master_config.master_uuid, unicode(srv_com))

    def send_command(self, src_id, srv_com):
        self.send_pool_message("send_command", src_id, srv_com)

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

    def _satellite_info(self, *args, **kwargs):
        srv_com = server_command.srv_command(source=args[0])
        uuid = srv_com["*uuid"]
        si_info = server_command.decompress(srv_com["*satellite_info"], json=True)
        if uuid in self.__slave_lut:
            _pk = self.__slave_lut[uuid]
            self.__slave_configs[_pk].store_satellite_info(si_info)
            self.send_info_message()
        else:
            self.log("Unknown uuid for satellite_info: {}".format(uuid), logging_tools.LOG_LEVEL_ERROR)

    # pure slave (==satellite) methods

    def _check_for_register_at_master(self):
        if not self.__registered_at_master and "master.uuid" in self.__local_master.config_store:
            self.__registered_at_master = True
            self.send_pool_message(
                "register_remote",
                self.__local_master.config_store["master.ip"],
                self.__local_master.config_store["master.uuid"],
                self.__local_master.config_store["master.port"],
            )
        # send satellite info
        self._send_satellite_info()

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
                self.log("syncing config to slave '{}'".format(slave_name))
                slave_pk = self.__slave_lut[slave_name]
                self.__slave_configs[slave_pk].distribute()
            else:
                self.log("unknown slave '{}'".format(slave_name), logging_tools.LOG_LEVEL_CRITICAL)
        else:
            self.log("unknown build_info '{}'".format(str(args)), logging_tools.LOG_LEVEL_CRITICAL)

    def _slave_command(self, *args, **kwargs):
        # generic slave command
        srv_com = server_command.srv_command(source=args[0])
        _action = srv_com["*action"]
        # find target
        _master = True if int(srv_com["*master"]) else False
        _slave_uuid = srv_com["*slave_uuid"]
        if self.__master_config:
            if _master:
                _config = self.__master_config
            else:
                _config = self.__slave_configs[self.__slave_lut[_slave_uuid]]
        else:
            _config = self.__local_master
        if _config is not None:
            self.log(
                "got action {} for {}".format(
                    _action,
                    "master" if _master else "slave {}".format(_config.name),
                )
            )
            _config.handle_action(_action, srv_com)
        else:
            self.log("_config is None, local_master still unset ?", logging_tools.LOG_LEVEL_ERROR)
