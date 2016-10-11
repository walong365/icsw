# Copyright (C) 2008-2016 Andreas Lang-Nevyjel, init.at
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
""" syncer definition for md-config-server """

import datetime
import os
import time

from django.db.models import Q

from initat.cluster.backbone import routing
from initat.cluster.backbone.models import mon_dist_master, mon_dist_slave, cluster_timezone, \
    mon_build_unreachable
from initat.cluster.backbone.server_enums import icswServiceEnum
from initat.tools import config_tools, logging_tools, process_tools, server_command
from .global_config import global_config

__all__ = [
    "SyncConfig",
]


class SyncConfig(object):
    def __init__(self, proc, monitor_server, **kwargs):
        """
        holds information about remote monitoring satellites
        """
        self.__process = proc
        self.__slave_name = kwargs.get("slave_name", None)
        self.__main_dir = global_config["MD_BASEDIR"]
        self.distributed = kwargs.get("distributed", False)
        self.master = True if not self.__slave_name else False
        if self.__slave_name:
            self.__dir_offset = os.path.join("slaves", self.__slave_name)
            master_cfg = config_tools.device_with_config(service_type_enum=icswServiceEnum.monitor_server)
            self.master_uuid = routing.get_server_uuid(
                icswServiceEnum.monitor_slave,
                master_cfg[icswServiceEnum.monitor_server][0].effective_device.uuid,
            )
            slave_cfg = config_tools.server_check(
                host_name=monitor_server.full_name,
                service_type_enum=icswServiceEnum.monitor_slave,
                fetch_network_info=True
            )
            self.slave_uuid = routing.get_server_uuid(
                icswServiceEnum.monitor_slave,
                monitor_server.uuid,
            )
            route = master_cfg[icswServiceEnum.monitor_server][0].get_route_to_other_device(
                self.__process.router_obj,
                slave_cfg,
                allow_route_to_other_networks=True,
                global_sort_results=True,
            )
            if not route:
                self.slave_ip = None
                self.master_ip = None
                self.log(
                    "no route to slave {} found".format(unicode(monitor_server)),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                self.slave_ip = route[0][3][1][0]
                self.master_ip = route[0][2][1][0]
                self.log(
                    "IP-address of slave {} is {} (master ip: {})".format(
                        unicode(monitor_server),
                        self.slave_ip,
                        self.master_ip
                    )
                )
            # target config version directory for distribute
            self.__tcv_dict = {}
        else:
            # hm, for send_* commands
            self.slave_uuid = ""
            self.__dir_offset = "master"
        self.monitor_server = monitor_server
        self.__dict = {}
        self._create_directories()
        # flags
        # config state, one of
        # u .... unknown
        # b .... building
        # d .... done
        self.config_state = "u"
        # version of config build
        self.config_version_build = 0
        # version of config in send state
        self.config_version_send = 0
        # version of config installed
        self.config_version_installed = 0
        # start of send
        self.send_time = 0
        # lut: send_time -> config_version_send
        self.send_time_lut = {}
        # lut: config_version_send -> number transmitted
        self.num_send = {}
        # distribution state
        self.dist_ok = True
        # flag for reload after sync
        self.reload_after_sync_flag = False
        # relayer info (== icsw software version)
        # clear md_struct
        self.__md_struct = None
        # raw info
        self.__raw_info = {
            "version": {
                "relayer_version": "?.?-0",
                "mon_version": "?.?-0",
                "livestatus_version": "?.?",
            },
            # system falgs
            "sysinfo": {},
            "name": self.__slave_name,
            "master": self.master or "",
            "latest_contact": 0,
        }
        # try to get relayer / mon_version from latest build
        if self.master:
            _latest_build = mon_dist_master.objects.filter(Q(device=self.monitor_server)).order_by("-pk")
        else:
            _latest_build = mon_dist_slave.objects.filter(Q(device=self.monitor_server)).order_by("-pk")
        if len(_latest_build):
            _latest_build = _latest_build[0]
            for _attr in ["mon_version", "relayer_version", "livestatus_version"]:
                self.__raw_info["version"][_attr] = getattr(_latest_build, _attr)
            self.log(
                "recovered {} from DB".format(self.vers_info)
            )

    @property
    def vers_info(self):
        return "MonVer {} / RelVer {} / LiveVer {} from DB".format(
            self.__raw_info["version"]["mon_version"],
            self.__raw_info["version"]["relayer_version"],
            self.__raw_info["version"]["livestatus_version"],
        )

    @property
    def info(self):
        return self.__raw_info

    def set_info(self, info):
        for _copy_key in ["sysinfo", "latest_contact"]:
            if _copy_key in info:
                self.__raw_info[_copy_key] = info[_copy_key]
        _cs = info.get("config_store", {})
        if "icsw.version" in _cs:
            self.__raw_info["version"]["relayer_version"] = "{}-{}".format(
                _cs["icsw.version"],
                _cs["icsw.release"],
            )
        if "md.version" in _cs:
            self.__raw_info["version"]["mon_version"] = "{}-{}".format(
                _cs["md.version"],
                _cs["md.release"],
            )
        if "livestatus.version" in _cs:
            self.__raw_info["version"]["livestatus_version"] = _cs["livestatus.version"]
        if self.__md_struct:
            for _attr in ["relayer_version", "mon_version", "livestatus_version"]:
                setattr(self.__md_struct, _attr, self.__raw_info["version"][_attr])
            self.__md_struct.save()

    def handle_info_action(self, action, srv_com):
        if self.__md_struct:
            if action == "sync_start":
                self.__md_struct.sync_start = cluster_timezone.localize(datetime.datetime.now())
                self.__md_struct.num_files = int(srv_com["*num_files"])
                self.__md_struct.size_data = int(srv_com["*size_data"])
                self.__md_struct.num_transfers = 1
                self.__md_struct.num_runs += 1
                self.__md_struct.save(update_fields=["sync_start", "num_files", "size_data", "num_transfers", "num_runs"])
            elif action == "sync_end":
                self.__md_struct.sync_end = cluster_timezone.localize(datetime.datetime.now())
                self.__md_struct.save(update_fields=["sync_end"])
                self.__md_struct = None
            else:
                self.log("unknown action {} in handle_info_action()".format(action), logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("md_struct not set for action {}".format(action), logging_tools.LOG_LEVEL_WARN)

    def get_send_data(self):
        _r_dict = {
            "master": True if not self.__slave_name else False,
            "pk": self.monitor_server.idx,
            "pure_uuid": self.monitor_server.uuid,
            "dir_offset": self.__dir_offset,
            # todo, FIXME
            "master_port": 8010,
            "master_uuid": routing.get_server_uuid(
                icswServiceEnum.monitor_server,
                self.monitor_server.uuid,
            )
        }
        if self.__slave_name:
            _r_dict.update(
                {
                    "name": self.__slave_name,
                    "pk": self.monitor_server.pk,
                    "master_ip": self.master_ip,
                    "master_uuid": self.master_uuid,
                    "slave_ip": self.slave_ip,
                    "slave_uuid": self.slave_uuid,
                }
            )
        return _r_dict

    def send_slave_command(self, action, **kwargs):
        # sends slave command (==action) to local sync master
        self.__process.send_sync_command(
            server_command.srv_command(
                command="slave_command",
                action=action,
                master="1" if self.master else "0",
                msg_src="M",
                slave_uuid=self.slave_uuid,
                **kwargs
            )
        )

    def reload_after_sync(self):
        self.reload_after_sync_flag = True
        self._check_for_ras()

    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__process.log(
            "[sc {}] {}".format(
                self.__slave_name if self.__slave_name else "master",
                what
            ),
            level
        )

    def _create_directories(self):
        dir_names = [
            "",
            "etc",
            "var",
            "share",
            "var/archives",
            "ssl",
            "bin",
            "sbin",
            "lib",
            "var/spool",
            "var/spool/checkresults"
        ]
        if process_tools.get_sys_bits() == 64:
            dir_names.append("lib64")
        # dir dict for writing on disk
        self.__w_dir_dict = {dir_name: os.path.normpath(os.path.join(self.__main_dir, self.__dir_offset, dir_name)) for dir_name in dir_names}
        # dir dict for referencing
        self.__r_dir_dict = {dir_name: os.path.normpath(os.path.join(self.__main_dir, dir_name)) for dir_name in dir_names}

    def check_for_resend(self):
        if not self.dist_ok and self.config_version_build != self.config_version_installed and abs(self.send_time - time.time()) > 60:
            self.log("resending files")
            self.distribute()

    def config_ts(self, ts_type):
        if self.__md_struct:
            # set config timestamp
            setattr(self.__md_struct, "config_build_{}".format(ts_type), cluster_timezone.localize(datetime.datetime.now()))
            self.__md_struct.save()

    def device_count(self, _num):
        if self.__md_struct:
            self.__md_struct.num_devices = _num
            self.__md_struct.save(update_fields=["num_devices"])

    def unreachable_devices(self, num):
        # set number of unreachable devices
        if self.__md_struct:
            self.__md_struct.unreachable_devices = num
            self.__md_struct.save(update_fields=["unreachable_devices"])

    def unreachable_device(self, dev_pk, dev_name, devg_name):
        # add unreachable device
        if self.__md_struct:
            mon_build_unreachable.objects.create(
                mon_dist_master=self.__md_struct,
                device_pk=dev_pk,
                device_name=dev_name,
                devicegroup_name=devg_name,
            )

    def start_build(self, b_version, full_build, master=None):
        # generate datbase entry for build
        self.config_version_build = b_version
        if self.master:
            # re-check relayer version for master
            self.log("version for master is {}".format(self.vers_info))
            _md = mon_dist_master(
                device=self.monitor_server,
                version=self.config_version_build,
                full_build=full_build,
                build_start=cluster_timezone.localize(datetime.datetime.now()),
            )
        else:
            self.__md_master = master
            self.log("version for slave {} is {}".format(self.monitor_server.full_name, self.vers_info))
            _md = mon_dist_slave(
                device=self.monitor_server,
                full_build=full_build,
                mon_dist_master=self.__md_master,
            )
        # version info
        for _attr in ["relayer_version", "mon_version", "livestatus_version"]:
            setattr(_md, _attr, self.__raw_info["version"][_attr])
        _md.save()
        self.__md_struct = _md
        return self.__md_struct

    def end_build(self):
        if self.__md_struct:
            self.__md_struct.build_end = cluster_timezone.localize(datetime.datetime.now())
            self.__md_struct.save()

    def sync_slave(self):
        self.send_slave_command(
            "sync_slave",
            config_version_build="{:d}".format(self.config_version_build)
        )

    def _check_for_ras(self):
        if self.reload_after_sync_flag and self.dist_ok:
            self.reload_after_sync_flag = False
            self.log("sending reload")
            self.send_slave_command("reload_after_sync")

    def _parse_list(self, in_list):
        # return top_dir and simplified list
        if in_list:
            in_list = [os.path.normpath(_entry) for _entry in in_list]
            _parts = in_list[0].split("/")
            while _parts:
                _top = u"/".join(_parts)
                if all([_entry.startswith(_top) for _entry in in_list]):
                    break
                _parts.pop(-1)
            return (_top, [_entry[len(_top):] for _entry in in_list])
        else:
            return ("", [])
