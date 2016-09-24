# Copyright (C) 2008-2016 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
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
""" syncer definition for md-sync-server """

import base64
import bz2
import datetime
import marshal
import os
import signal
import stat
import sys
import time

from initat.server_version import VERSION_STRING
from initat.tools import logging_tools, process_tools, server_command, config_store
from .base_config import RemoteServer, SlaveState
from .config import global_config, CS_MON_NAME
from initat.server_version import VERSION_MAJOR, VERSION_MINOR

__all__ = [
    "SyncConfig",
    "RemoteServer",
]


class SyncConfig(object):
    def __init__(self, proc, di_dict, **kwargs):
        """
        holds information about remote monitoring satellites
        """
        # TreeState, di_dict set with master=True|False or di_dict not set (simple config)
        self.__process = proc
        self.__main_dir = global_config["MD_BASEDIR"]
        self.distributed = kwargs.get("distributed", False)
        if di_dict is None:
            self.name = None
            self.master = None
            self.log("init local structure")
            self.__dir_offset = ""
            self.config_store = config_store.ConfigStore(CS_MON_NAME, log_com=self.__process.log, access_mode=config_store.AccessModeEnum.LOCAL)
            self.config_store["md.version"] = global_config["MD_VERSION"]
            self.config_store["md.release"] = global_config["MD_RELEASE"]
            self.config_store["icsw.version"] = VERSION_MAJOR
            self.config_store["icsw.release"] = VERSION_MINOR
            self.config_store.write()
        else:
            self.name = di_dict.get("name", None)
            self.master = di_dict["master"]
            if self.name:
                self.struct = None
                self.config_store = config_store.ConfigStore(CS_MON_NAME, log_com=self.__process.log, access_mode=config_store.AccessModeEnum.LOCAL, read=False)
                self.__dir_offset = os.path.join("slaves", self.name)
                for _attr_name in ["slave_ip", "master_ip", "pk", "slave_uuid", "master_uuid"]:
                    setattr(self, _attr_name, di_dict[_attr_name])
                if not self.master_ip:
                    self.slave_ip = None
                    self.master_ip = None
                    self.log("no route to slave {} found".format(self.name), logging_tools.LOG_LEVEL_ERROR)
                else:
                    self.log(
                        "IP-address of slave {} is {} [{}] (master ip: {} [{}])".format(
                            self.name,
                            self.slave_ip,
                            self.slave_uuid,
                            self.master_ip,
                            self.master_uuid,
                        )
                    )
                # target config version directory for distribute
                self.__tcv_dict = {}
            else:
                # local master structure, is usually none due to delayed check of MD_TYPE in snycer.py
                self.struct = kwargs["local_master"]
                self.config_store = None
                self.master_ip = "127.0.0.1"
                self.master_port = di_dict["master_port"]
                self.pure_uuid = di_dict["pure_uuid"]
                self.master_uuid = di_dict["master_uuid"]
                self.slave_uuid = None
                self.log("master uuid is {}@{}, {:d}".format(self.master_uuid, self.master_ip, self.master_port))
                self.__dir_offset = ""
        self.state = SlaveState.init
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
        # distribution state, always True for master
        self.dist_ok = True
        # flag for reload after sync
        self.reload_after_sync_flag = False
        # clear md_struct
        self.__md_struct = None

    def set_local_master(self, local_master):
        self.struct = local_master

    def register_master(self, srv_com):
        master_ip, master_uuid, master_port, slave_uuid = (
            srv_com["*master_ip"],
            srv_com["*master_uuid"],
            int(srv_com["*master_port"]),
            srv_com["*slave_uuid"],
        )
        self.log(
            "registering master at {} ({}@{:d}) for local slave".format(
                master_uuid,
                master_ip,
                master_port,
                slave_uuid,
            )
        )
        self.config_store["master.uuid"] = master_uuid
        self.config_store["master.ip"] = master_ip
        self.config_store["master.port"] = master_port
        self.config_store["slave.uuid"] = slave_uuid
        self.config_store.write()

    def get_satellite_info(self):
        r_dict = {}
        if self.config_store is not None:
            # may be none for local master
            for _key in ["md.version", "md.release", "icsw.version", "icsw.release"]:
                if _key in self.config_store:
                    r_dict[_key] = self.config_store[_key]
        return r_dict

    def store_satellite_info(self, si_info):
        for _key in si_info.keys():
            self.config_store[_key] = si_info[_key]

    def get_info_dict(self):
        r_dict = {
            "master": self.master,
            "slave_uuid": self.slave_uuid,
            "state": self.state.name,
        }
        if self.struct is not None:
            # local master
            r_dict.update(self.struct.get_satellite_info())
        else:
            r_dict.update(self.get_satellite_info())
        return r_dict

    def reload_after_sync(self):
        self.reload_after_sync_flag = True
        self._check_for_ras()

    def set_relayer_info(self, srv_com):
        for key in ["relayer_version", "mon_version"]:
            if key in srv_com:
                _new_vers = srv_com[key].text
                if _new_vers != getattr(self, key):
                    self.log("changing {} from '{}' to '{}'".format(
                        key,
                        getattr(self, key),
                        _new_vers)
                    )
                    setattr(self, key, _new_vers)

    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__process.log(
            "[sc {}] {}".format(
                self.name if self.name else "master",
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
        self.log("create directores called, main_dir={}, dir_offset={}".format(self.__main_dir, self.__dir_offset or "<EMPTY>"))
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
            if "initat.host_monitoring.version" in sys.modules:
                del sys.modules["initat.host_monitoring.version"]
            from initat.client_version import VERSION_STRING as RELAYER_VERSION_STRING
            self.relayer_version = RELAYER_VERSION_STRING
            _mon_version = global_config["MD_VERSION_STRING"]
            if _mon_version.split(".")[-1] in ["x86_64", "i586", "i686"]:
                _mon_version = ".".join(_mon_version.split(".")[:-1])
            self.mon_version = _mon_version
            self.log("mon / relayer version for master is {} / {}".format(self.mon_version, self.relayer_version))
            _md = mon_dist_master(
                device=self.monitor_server,
                version=self.config_version_build,
                build_start=cluster_timezone.localize(datetime.datetime.now()),
                relayer_version=self.relayer_version,
                # monitorig daemon
                md_version=VERSION_STRING,
                mon_version=self.mon_version,
            )
        else:
            self.__md_master = master
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

    def distribute(self):
        # max uncompressed send size
        MAX_SEND_SIZE = 65536
        cur_time = time.time()
        if self.slave_ip:
            self.config_version_send = self.config_version_build
            if not self.__md_struct.num_runs:
                self.__md_struct.sync_start = cluster_timezone.localize(datetime.datetime.now())
            self.__md_struct.num_runs += 1
            self.send_time = int(cur_time)
            # to distinguish between iterations during a single build
            self.send_time_lut[self.send_time] = self.config_version_send
            self.dist_ok = False
            self.log(
                "start send to slave (version {:d} [{:d}], generation is {:d})".format(
                    self.config_version_send,
                    self.send_time,
                    _r_gen,
                )
            )
            # number of atomic commands
            self.__num_com = 0
            self.__size_raw, size_data = (0, 0)
            # send content of /etc
            dir_offset = len(self.__w_dir_dict["etc"])
            # generation 1 transfer
            del_dirs = []
            for cur_dir, _dir_names, file_names in os.walk(self.__w_dir_dict["etc"]):
                rel_dir = cur_dir[dir_offset + 1:]
                del_dirs.append(os.path.join(self.__r_dir_dict["etc"], rel_dir))
            if del_dirs:
                srv_com = server_command.srv_command(
                    command="clear_directories",
                    host="DIRECT",
                    slave_name=self.__slave_name,
                    port="0",
                    version="{:d}".format(int(self.send_time)),
                )
                _bld = srv_com.builder()
                srv_com["directories"] = _bld.directories(*[_bld.directory(del_dir) for del_dir in del_dirs])
                self._send(srv_com)
            _send_list, _send_size = ([], 0)
            for cur_dir, _dir_names, file_names in os.walk(self.__w_dir_dict["etc"]):
                rel_dir = cur_dir[dir_offset + 1:]
                for cur_file in sorted(file_names):
                    full_r_path = os.path.join(self.__w_dir_dict["etc"], rel_dir, cur_file)
                    full_w_path = os.path.join(self.__r_dir_dict["etc"], rel_dir, cur_file)
                    if os.path.isfile(full_r_path):
                        self.__tcv_dict[full_w_path] = self.config_version_send
                        _content = file(full_r_path, "r").read()
                        size_data += len(_content)
                        if _send_size + len(_content) > MAX_SEND_SIZE:
                            self._send(self._build_file_content(_send_list))
                            _send_list, _send_size = ([], 0)
                        # format: uid, gid, path, content_len, content
                        _send_list.append((os.stat(full_r_path)[stat.ST_UID], os.stat(full_r_path)[stat.ST_GID], full_w_path, len(_content), _content))
            if _send_list:
                self._send(self._build_file_content(_send_list))
                _send_list, _send_size = ([], 0)
            self.num_send[self.config_version_send] = self.__num_com
            self.__md_struct.num_files = self.__num_com
            self.__md_struct.num_transfers = self.__num_com
            self.__md_struct.size_raw = self.__size_raw
            self.__md_struct.size_data = size_data
            self.__md_struct.save()
            self._show_pending_info()
        else:
            self.log("slave has no valid IP-address, skipping send", logging_tools.LOG_LEVEL_ERROR)

    def _build_file_content(self, _send_list):
        srv_com = server_command.srv_command(
            command="file_content_bulk",
            host="DIRECT",
            slave_name=self.__slave_name,
            port="0",
            version="{:d}".format(int(self.send_time)),
        )
        _bld = srv_com.builder()

        srv_com["file_list"] = _bld.file_list(
            *[
                _bld.file(
                    _path,
                    uid="{:d}".format(_uid),
                    gid="{:d}".format(_gid),
                    size="{:d}".format(_size)
                ) for _uid, _gid, _path, _size, _content in _send_list
            ]
        )
        srv_com["bulk"] = base64.b64encode(bz2.compress("".join([_parts[-1] for _parts in _send_list])))
        return srv_com

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
            self.log("[{:4d}] {} : {}".format(
                len(err_dict[err_key]),
                err_key,
                ", ".join(sorted(err_dict[err_key]))), logging_tools.LOG_LEVEL_ERROR)
        self._show_pending_info()

    # local actions
    def handle_reload_after_sync(self, srv_com):
        self.reload_after_sync_flag = True
        self._check_for_ras()

    def _check_for_ras(self):
        if self.reload_after_sync_flag and self.dist_ok:
            self.reload_after_sync_flag = False
            self.log("sending reload")
            self.__process.send_pool_message(
                "send_signal",
                signal.SIGHUP,
            )

    def handle_local_action(self, action, srv_com):
        _attr_name = "handle_{}".format(action)
        if not hasattr(self, _attr_name):
            self.log("unknown local action '{}'".format(action), logging_tools.LOG_LEVEL_ERROR)
        else:
            getattr(self, _attr_name)(srv_com)

    def handle_action(self, action, srv_com):
        if self.master:
            # local action
            self.handle_local_action(action, srv_com)
        else:
            # remote action
            pass
            # print action, self.name
