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

import time

from django.db.models import Q

from .process import BuildProcess
from initat.cluster.backbone.models import device
from initat.icsw.service.instance import InstanceXML
from initat.md_config_server.config import MainConfigContainer, global_config
from initat.tools import logging_tools, server_command
from ..constants import BuildModes


class BuildControl(object):
    def __init__(self, process):
        self.__process = process
        self.log("init BuildControl")
        # store pending commands
        self.__pending_commands = []
        self.__hm_port = InstanceXML(quiet=True).get_port_dict("host-monitoring", command=True)
        # ready (check_for_slaves called)
        self.__ready = False
        self.version = int(time.time())
        self.__initial_reload_checked = False
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
                    cache_mode=global_config["INITIAL_CONFIG_CACHE_MODE"],
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
        if self.__ready:
            _func_name = srv_com["*command"]
            if hasattr(self, _func_name):
                getattr(self, _func_name)(srv_com)
            else:
                self.log("unknown function '{}'".format(_func_name), logging_tools.LOG_LEVEL_CRITICAL)
        else:
            self.log("buffering command {}".format(srv_com["*command"]), logging_tools.LOG_LEVEL_WARN)
            self.__pending_commands.append(unicode(srv_com))

    def get_host_config(self, srv_com):
        # dummy call, should be build_host_config, name needed
        # to distinguish call in server.py
        return self.build_host_config(srv_com)

    def _sync_http_users(self, *args, **kwargs):
        self.log("syncing http-users")
        print "not handled correctly right now, triggering error"
        self.__gen_config._create_access_entries()

    def build_host_config(self, srv_com):
        # all builds are handled via this call
        dev_pks = srv_com.xpath(".//device_list/device/@pk", smart_strings=False)
        dev_cache_modes = list(set(srv_com.xpath(".//device_list/device/@mode", smart_strings=False)))
        if dev_cache_modes:
            dev_cache_mode = dev_cache_modes[0]
            dev_names = [cur_dev.full_name for cur_dev in device.objects.filter(Q(pk__in=dev_pks)).select_related("domain_tree_node")]
            self.log(
                "starting single build with {}, cache mode is {}: {}".format(
                    logging_tools.get_plural("device", len(dev_names)),
                    dev_cache_mode,
                    ", ".join(sorted(dev_names))
                )
            )
            srv_com.set_result(
                "rebuilt config for {}".format(
                    ", ".join(dev_names)
                ),
                server_command.SRV_REPLY_STATE_OK
            )
            self._rebuild_config(srv_com, *dev_names, cache_mode=dev_cache_mode)
        else:
            cache_mode = srv_com["*cache_mode"]
            self.log("rebuild config for all hosts with cache_mode '{}'".format(cache_mode))
            srv_com.set_result("rebuild config for all hosts")
            self._rebuild_config(srv_com, cache_mode=cache_mode)

    def _rebuild_config(self, srv_com, *args, **kwargs):
        # how many processes to add
        _b_list = [self.__master_config.serialize()]
        if len(args):
            _mode = BuildModes.some_master  # some_check
        else:
            _mode = BuildModes.all_master
        if _mode not in [BuildModes.some_check]:
            # build config for all hosts, one process per slave
            _b_list.extend(
                [_slave.serialize() for _slave in self.__slave_configs.itervalues()]
            )

        for _build_id, _ser_info in enumerate(_b_list, 1):
            _p_name = "build{:d}".format(_build_id)
            self.__process.add_process(BuildProcess(_p_name), start=True)
            self.__process.send_to_process(
                _p_name,
                "start_build",
                _mode,
                _ser_info,
                self.version,
                unicode(srv_com),
                *args
            )
            # advance mode
            _mode = {
                BuildModes.some_master: BuildModes.some_slave,
                BuildModes.all_master: BuildModes.all_slave,
            }.get(_mode, _mode)
