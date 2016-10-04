# Copyright (C) 2008-2015 Andreas Lang-Nevyjel, init.at
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

import base64
import bz2
import datetime
import marshal
import os
import stat
import time

from django.db.models import Q

from initat.cluster.backbone import routing
from initat.cluster.backbone.models import mon_dist_master, mon_dist_slave, cluster_timezone, \
    mon_build_unreachable
from initat.cluster.backbone.server_enums import icswServiceEnum
from initat.tools import config_tools, configfile, logging_tools, process_tools, server_command

global_config = configfile.get_global_config(process_tools.get_programm_name())


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
            self.__dir_offset = ""
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
        self.relayer_version = "?.?-0"
        self.mon_version = "?.?-0"
        # clear md_struct
        self.__md_struct = None
        # try to get relayer / mon_version from latest build
        if self.master:
            _latest_build = mon_dist_master.objects.filter(Q(device=self.monitor_server)).order_by("-pk")
        else:
            _latest_build = mon_dist_slave.objects.filter(Q(device=self.monitor_server)).order_by("-pk")
        if len(_latest_build):
            _latest_build = _latest_build[0]
            self.mon_version = _latest_build.mon_version
            self.relayer_version = _latest_build.relayer_version
            self.log("recovered MonVer {} / RelVer {} from DB".format(self.mon_version, self.relayer_version))

    def set_info(self, info):
        if "icsw.version" in info:
            self.relayer_version = "{}-{}".format(
                info["icsw.version"],
                info["icsw.release"],
            )
        if "md.version" in info:
            self.mon_version = "{}-{}".format(
                info["md.version"],
                info["md.release"],
            )
        # print "SI", info

    def handle_info_action(self, action, srv_com):
        print "**", action
        print srv_com.pretty_print()

    def get_send_data(self):
        _r_dict = {
            "master": True if not self.__slave_name else False,
            "pure_uuid": self.monitor_server.uuid,
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

    def start_build(self, b_version, master=None):
        # generate datbase entry for build
        self.config_version_build = b_version
        if self.master:
            # re-check relayer version for master
            self.log("mon / relayer version for master is {} / {}".format(self.mon_version, self.relayer_version))
            _md = mon_dist_master(
                device=self.monitor_server,
                version=self.config_version_build,
                build_start=cluster_timezone.localize(datetime.datetime.now()),
                relayer_version=self.relayer_version,
                # monitorig daemon
                mon_version=self.mon_version,
            )
        else:
            self.__md_master = master
            self.log("mon / relayer version for slave {} is {} / {}".format(self.monitor_server.full_name, self.mon_version, self.relayer_version))
            _md = mon_dist_slave(
                device=self.monitor_server,
                mon_dist_master=self.__md_master,
                relayer_version=self.relayer_version,
                mon_version=self.mon_version,
            )
        _md.save()
        self.__md_struct = _md
        return self.__md_struct

    def end_build(self):
        self.__md_struct.build_end = cluster_timezone.localize(datetime.datetime.now())
        self.__md_struct.save()

    def _send(self, srv_com):
        self.__process.send_command(self.monitor_server.uuid, unicode(srv_com))
        self.__size_raw += len(unicode(srv_com))
        self.__num_com += 1

    def _show_pending_info(self):
        cur_time = time.time()
        pend_keys = [key for key, value in self.__tcv_dict.iteritems() if type(value) != bool]
        error_keys = [key for key, value in self.__tcv_dict.iteritems() if value is False]
        self.log(
            "{:d} total, {} pending, {} error".format(
                len(self.__tcv_dict),
                logging_tools.get_plural("remote file", len(pend_keys)),
                logging_tools.get_plural("remote file", len(error_keys))
            ),
        )
        if not pend_keys and not error_keys:
            _dist_time = abs(cur_time - self.send_time)
            self.log(
                "actual distribution_set {:d} is OK (in {}, {:.2f} / sec)".format(
                    int(self.config_version_send),
                    logging_tools.get_diff_time_str(_dist_time),
                    self.num_send[self.config_version_send] / _dist_time,
                )
            )
            self.config_version_installed = self.config_version_send
            self.dist_ok = True
            self.__md_struct.sync_end = cluster_timezone.localize(datetime.datetime.now())
            self.__md_struct.save()
            self._check_for_ras()

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

    def file_content_info(self, srv_com):
        cmd = srv_com["command"].text
        version = int(srv_com["version"].text)
        file_reply, file_status = srv_com.get_log_tuple()
        self.log(
            "handling {} (version {:d}, reply is {})".format(
                cmd,
                version,
                file_reply,
            ),
            file_status
        )
        if cmd == "file_content_result":
            file_name = srv_com["file_name"].text
            # check return state for validity
            if not server_command.srv_reply_state_is_valid(file_status):
                self.log("file_state {:d} is not valid".format(file_status), logging_tools.LOG_LEVEL_CRITICAL)
            self.log(
                "file_content_status for {} is {} ({:d}), version {:d} (dist: {:d})".format(
                    file_name,
                    srv_com["result"].attrib["reply"],
                    file_status,
                    version,
                    self.send_time_lut.get(version, 0),
                ),
                file_status
            )
            file_names = [file_name]
        elif cmd == "file_content_bulk_result":
            num_ok, num_failed = (int(srv_com["num_ok"].text), int(srv_com["num_failed"].text))
            self.log("{:d} ok / {:d} failed".format(num_ok, num_failed))
            failed_list = marshal.loads(bz2.decompress(base64.b64decode(srv_com["failed_list"].text)))
            ok_list = marshal.loads(bz2.decompress(base64.b64decode(srv_com["ok_list"].text)))
            if ok_list:
                _ok_dir, _ok_list = self._parse_list(ok_list)
                self.log(
                    "ok list (beneath {}): {}".format(
                        _ok_dir,
                        ", ".join(
                            sorted(_ok_list)
                        ) if global_config["DEBUG"] else logging_tools.get_plural("entry", len(_ok_list))
                    )
                )
            if failed_list:
                _failed_dir, _failed_list = self._parse_list(failed_list)
                self.log(
                    "failed list (beneath {}): {}".format(
                        _failed_dir,
                        ", ".join(sorted(_failed_list))
                    )
                )
            file_names = ok_list
        err_dict = {}
        for file_name in file_names:
            err_str = None
            if version in self.send_time_lut:
                target_vers = self.send_time_lut[version]
                if version == self.send_time:
                    if type(self.__tcv_dict[file_name]) in [int, long]:
                        if self.__tcv_dict[file_name] == target_vers:
                            if file_status in [logging_tools.LOG_LEVEL_OK, logging_tools.LOG_LEVEL_WARN]:
                                self.__tcv_dict[file_name] = True
                            else:
                                self.__tcv_dict[file_name] = False
                        else:
                            err_str = "waits for different version: {:d} != {:d}".format(version, self.__tcv_dict[file_name])
                    else:
                        err_str = "already set to {}".format(str(self.__tcv_dict[file_name]))
                else:
                    err_str = "version is from an older distribution run ({:d} != {:d})".format(version, self.send_time)
            else:
                err_str = "version {:d} not known in send_time_lut".format(version)
            if err_str:
                err_dict.setdefault(err_str, []).append(file_name)
        for err_key in sorted(err_dict.keys()):
            self.log(
                "[{:4d}] {} : {}".format(
                    len(err_dict[err_key]),
                    err_key,
                    ", ".join(sorted(err_dict[err_key]))
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        self._show_pending_info()
