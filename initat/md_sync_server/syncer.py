# Copyright (C) 2014-2016 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-sync-server
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

from initat.icsw.service.instance import InstanceXML
from initat.tools import logging_tools, server_command, threading_tools
from .config import global_config
from .sync_config import SyncConfig


class SyncerHandler(object):
    def __init__(self, process):
        self.__process = process
        self.inst_xml = InstanceXML(self.log)
        self.__register_timer = False
        self.__build_in_progress, self.__build_version = (False, 0)
        # setup local master, always set (also on satellite nodes)
        self.__local_master = None
        # master config for distribution master (only set on distribution master)
        self.__master_config = None
        self.__process.register_timer(self._init_local_master, 60, first_timeout=2)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__process.log(log_level, what)

    def loop_post(self):
        pass

    def _init_local_master(self):
        # init local master as soon as MD_TYPE is set / known
        if not self.__local_master and "MD_TYPE" in global_config:
            # this is called on all devices with a mon instance
            self.log("init local master")
            self.__local_master = SyncConfig(self.__process, None, distributed=False)
            if self.__master_config:
                # only on distribution master
                self.__master_config.set_local_master(self.__local_master)
            # register at distribution master
            self.__local_master.check_for_register_at_master()
        if self.__local_master and self.__master_config:
            self.__local_master.send_satellite_info()

    def distribute_info(self, dist_info):
        self.log("distribution info has {}".format(logging_tools.get_plural("entry", len(dist_info))))
        for _di in dist_info:
            if _di["master"]:
                self.log("found master entry")
                self.__master_config = SyncConfig(self.__process, _di, distributed=True if len(dist_info) > 1 else False, local_master=self.__local_master)
                # register md-config-server
                self.__process.register_remote(
                    self.__master_config.master_ip,
                    self.__master_config.master_uuid,
                    _di["master_port"],
                )
                self.__master_config.add_slaves(dist_info, self.inst_xml)
        if not self.__register_timer:
            self.__register_timer = True
            _reg_timeout, _first_timeout = (600, 2)  # (600, 15)
            self.log("will send register_msg in {:d} (then {:d}) seconds".format(_first_timeout, _reg_timeout))
            self.__process.register_timer(self.__master_config.send_register_msg, _reg_timeout, instant=global_config["DEBUG"], first_timeout=_first_timeout)

    def send_command(self, src_id, srv_com):
        self.__process.send_command(src_id, srv_com)

    def check_for_redistribute(self):
        for slave_config in self.__slave_configs.itervalues():
            slave_config.check_for_resend()

    # pure slave (==satellite) methods

    def check_result(self, srv_com):
        if self.__master_config:
            # distribution master, forward to ocsp / ochp process
            self.__process.handle_ocp_event(srv_com)
        else:
            if self.__local_master:
                # distribution slave, send to sync-master
                self.__local_master.send_to_sync_master(srv_com)
            else:
                self.log("local master not set", logging_tools.LOG_LEVEL_ERROR)

    def passive_check_handler(self, srv_com, source):
        self.log("got passive check result via {}".format(source))
        if self.__master_config:
            # distribution master, send to mon master
            self.__master_config.send_to_config_server(srv_com)
        else:
            if self.__local_master:
                self.__local_master.send_to_sync_master(srv_com)
            else:
                self.log("local master not set", logging_tools.LOG_LEVEL_ERROR)
        print srv_com.pretty_print()

    def livestatus_info(self, arg_dict):
        self.log("got livestatus dict with {:d} keys".format(len(arg_dict.keys())))
        if self.__local_master:
            self.__local_master.set_livestatus_version(arg_dict["livestatus_version"])

    def slave_command(self, srv_com):
        # generic slave command
        _action = srv_com["*action"]
        # find target
        _master = True if int(srv_com["*master"]) else False
        _msg_src = srv_com["*msg_src"]
        _slave_uuid = srv_com["*slave_uuid"]
        # msg_dst: message destination
        # D: Distribution Master
        # R: Remote Slave (handled by dist master)
        # S: Local Slave (on remote device)
        # msg_src: message source
        # M: Monitoring daemon
        # D: Distribution Master
        # S: Distribution Slave
        if self.__master_config:
            if _master:
                _config = self.__master_config
                _slave = None
                _msg_dst = "D"
            else:
                _config = self.__master_config
                _slave = _config.get_slave(_slave_uuid)
                _msg_dst = "R"
        else:
            _config = self.__local_master
            _slave = _config
            _msg_dst = "S"
        if _config is not None:
            self.log(
                "[{}->{}] got action {} for {}".format(
                    _msg_src,
                    _msg_dst,
                    _action,
                    "master" if _master else "slave {}".format(_slave.name),
                )
            )
            _config.handle_action(_action, srv_com, _msg_src, _msg_dst)
        else:
            self.log("_config is None, local_master still unset ?", logging_tools.LOG_LEVEL_ERROR)
