# Copyright (C) 2001-2016 Andreas Lang-Nevyjel, init.at
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
""" build control structure for md-config-server """

from __future__ import unicode_literals, print_function

import time

from django.db.models import Q

from initat.cluster.backbone.models import device
from initat.md_config_server.config import MainConfigContainer, global_config
from initat.tools import logging_tools, server_command
from .process import BuildProcess
from ..constants import BuildModesEnum


class BuildControl(object):
    def __init__(self, process):
        self.__process = process
        self.log("init BuildControl")
        # store pending commands
        self.__pending_commands = []
        # ready (check_for_slaves called)
        self.__ready = False
        self.version = int(time.time())
        self.__initial_reload_checked = False
        # dyn process is running
        self.__dc_running = False
        # dyn run is requested
        self.__dc_run_queue = []
        self.log("initial config_version is {:d}".format(self.version))

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__process.log(u"[BC] {}".format(what), log_level)

    def distribution_info(self, dist_info):
        # dist gets called as soon as the syncer process is up and running
        for _entry in dist_info:
            # add device entries
            _entry["device"] = device.objects.get(Q(pk=_entry["pk"]))
        self.log(
            "got distribution info, found {}: {}".format(
                logging_tools.get_plural("slave server", len(dist_info) - 1),
                ", ".join(
                    [
                        _entry["device"].full_name for _entry in dist_info if not _entry["master"]
                    ]
                )
            )
        )
        # create MonConfigContainer instances
        for entry in dist_info:
            cur_dev = entry["device"]
            if entry["master"]:
                self.__master_config = MainConfigContainer(
                    self,
                    cur_dev,
                )
                self.__slave_configs = {}
            else:
                _slave_c = MainConfigContainer(
                    self,
                    cur_dev,
                    slave_name=cur_dev.full_name,
                )
                self.__slave_configs[cur_dev.pk] = _slave_c
        self.__ready = True
        if not self.__initial_reload_checked:
            self.__initial_reload_checked = True
            if global_config["BUILD_CONFIG_ON_STARTUP"] or global_config["INITIAL_CONFIG_RUN"]:
                srv_com = server_command.srv_command(
                    command="build_host_config",
                )
                self.handle_command(srv_com)
        if self.__pending_commands:
            self.log(
                "processing {}".format(
                    logging_tools.get_plural("pending command", len(self.__pending_commands))
                )
            )
            while self.__pending_commands:
                self.handle_command(server_command.srv_command(source=self.__pending_commands.pop(0)))

    def handle_command(self, srv_com):
        _func_name = srv_com["*command"]
        if _func_name in {"sync_http_users", "build_host_config", "fetch_dyn_config", "get_host_config"}:
            if self.__ready:
                getattr(self, _func_name)(srv_com)
            else:
                self.log("buffering command {}".format(srv_com["*command"]), logging_tools.LOG_LEVEL_WARN)
                self.__pending_commands.append(unicode(srv_com))
        else:
            self.log("unknown function '{}'".format(_func_name), logging_tools.LOG_LEVEL_CRITICAL)

    def get_host_config(self, srv_com):
        # dummy call, should be build_host_config, name needed
        # to distinguish call in server.py
        if srv_com["*mode"] == "config":
            # get config
            return self.build_host_config(srv_com)
        else:
            # call dynconfig fetch
            return self.fetch_dyn_config(srv_com)

    def sync_http_users(self, srv_com):
        srv_com.set_result("syncing httpd-users")
        # bump version
        self.version += 1
        self._rebuild_config(srv_com)

    def build_step(self, *args, **kwargs):
        _action = args[2]
        if _action == "routing_ok":
            _fp = args[3]
            self.log("master setup routing with fp {}".format(_fp))
            for _p_name in self._build_slave_names:
                self.__process.send_to_process(
                    _p_name,
                    "routing_fingerprint",
                    _fp,
                )
        else:
            self.log("Unknown build_step action '{}'".format(_action), logging_tools.LOG_LEVEL_ERROR)

    def build_host_config(self, srv_com):
        # all builds are handled via this call
        dev_pks = srv_com.xpath(".//device_list/device/@pk", smart_strings=False)
        new_version = int(time.time())
        while new_version < self.version:
            new_version += 1
        self.version = new_version
        if dev_pks:
            dev_names = [
                cur_dev.full_name for cur_dev in device.objects.filter(Q(pk__in=dev_pks)).select_related("domain_tree_node")
            ]
            # check if only the config should be built
            only_build = True if len(srv_com.xpath(".//device_list/device/@only_build")) else False
            self.log(
                "starting single build with {} ({}): {}".format(
                    logging_tools.get_plural("device", len(dev_names)),
                    "only build config" if only_build else "build config and redistribute",
                    ", ".join(sorted(dev_names))
                )
            )
            srv_com.set_result(
                "rebuilt config for {}".format(
                    ", ".join(dev_names)
                ),
                server_command.SRV_REPLY_STATE_OK
            )
            self._rebuild_config(srv_com, *dev_names)
        else:
            self.log("rebuild config for all hosts")
            srv_com.set_result("rebuild config for all hosts")
            self._rebuild_config(srv_com)

    def _rebuild_config(self, srv_com, *args, **kwargs):
        # how many processes to add
        _b_list = [self.__master_config.serialize()]
        if len(args):
            if kwargs.get("only_build", False):
                _mode = BuildModesEnum.some_master
            else:
                _mode = BuildModesEnum.some_check
        elif srv_com["*command"] == "sync_http_users":
            _mode = BuildModesEnum.sync_users_master
        else:
            _mode = BuildModesEnum.all_master
        if _mode not in [BuildModesEnum.some_check]:
            # build config for all hosts, one process per slave
            _b_list.extend(
                [_slave.serialize() for _slave in self.__slave_configs.itervalues()]
            )

        self._build_slave_names = []
        # print("*", self.version, _mode)
        for _build_id, _ser_info in enumerate(_b_list, 1):
            _p_name = "build{:d}".format(_build_id)
            self.__process.add_process(BuildProcess(_p_name), start=True)
            self.__process.send_to_process(
                _p_name,
                "start_build",
                _mode.name,
                _ser_info,
                self.version,
                unicode(srv_com),
                *args
            )
            if _mode in [BuildModesEnum.some_slave, BuildModesEnum.all_slave, BuildModesEnum.sync_users_slave]:
                self._build_slave_names.append(_p_name)
            # advance mode
            _mode = {
                BuildModesEnum.some_master: BuildModesEnum.some_slave,
                BuildModesEnum.all_master: BuildModesEnum.all_slave,
                BuildModesEnum.sync_users_master: BuildModesEnum.sync_users_slave,
            }.get(_mode, _mode)

    def process_action(self, proc_name, ss_flag):
        if proc_name in {"DynConfig"}:
            self.__dc_running = ss_flag
            if not self.__dc_running and len(self.__dc_run_queue):
                self.log("fetching srv_com from dc_run_queue")
                srv_com = self.__dc_run_queue.pop(0)
                self.fetch_dyn_config(self, srv_com)

    def fetch_dyn_config(self, srv_com, *args, **kwargs):
        if self.__dc_running:
            self.log("DynConfigProcess is already running, registering re-run")
            self.__dc_run_queue.append(srv_com)
        else:
            dev_pks = [
                int(_pk) for _pk in srv_com.xpath(".//device_list/device/@pk", smart_strings=False)
            ]
            _p_name = "DynConfig"
            self.__process.add_process(BuildProcess(_p_name), start=True)
            self.__process.send_to_process(
                _p_name,
                "fetch_dyn_config",
                BuildModesEnum.dyn_master.name,
                self.__master_config.serialize(),
                unicode(srv_com),
                *dev_pks
            )
            self.__dc_running = True
