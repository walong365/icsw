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


class FileInfo(object):
    def __init__(self, path, target_version):
        self.path = path
        self.target_version = target_version
        self.created = False
        # not used right now
        self.error = ""

    def compare(self, new_version):
        if new_version == self.target_version:
            return False, "version is not newer ({:d})".format(self.target_version)
        else:
            _log = "newer version ({:d} -> {:d})".format(self.target_version, new_version)
            self.target_version = new_version
            self.created = False
            return True, _log

    def get_info_dict(self):
        return {
            "version": self.target_version,
            "created": self.created,
            "error": self.error,
        }

    def log_error(self, err_str):
        self.created = False
        self.error = err_str

    def log_success(self):
        self.created = True

    def store_result(self, remote_result):
        self.created = remote_result["created"]
        print "*", self.created, remote_result["version"], self.target_version
        if remote_result["version"] != self.target_version:
            self.created = False

    @property
    def is_pending(self):
        return True if (not self.created and not self.error) else False

    @property
    def is_error(self):
        return True if self.error else False


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
            # path -> FileInfo
            self.__file_dict = {}
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
                # file dict to check distribution state
                self.__file_dict = {}
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

    def get_satellite_info(self):
        r_dict = {
            "config_store": {}
        }
        if self.config_store is not None:
            # may be none for local master
            for _key in ["md.version", "md.release", "icsw.version", "icsw.release"]:
                if _key in self.config_store:
                    r_dict["config_store"][_key] = self.config_store[_key]
        if self.master is None:
            r_dict["store_info"] = {
                _fi.path: _fi.get_info_dict() for _fi in self.__file_dict.itervalues()
            }
        return r_dict

    def store_satellite_info(self, si_info):
        import pprint
        pprint.pprint(si_info)
        for _key in si_info.get("config_store", {}).keys():
            self.config_store[_key] = si_info["config_store"][_key]
        if "store_info" in si_info:
            for _key, _struct in si_info["store_info"].iteritems():
                if _key not in self.__file_dict:
                    self.log("key '{}' not known in local file_dict".format(_key), logging_tools.LOG_LEVEL_ERROR)
                else:
                    self.__file_dict[_key].store_result(_struct)
            self._show_pending_info()

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

    def end_build(self):
        self.__md_struct.build_end = cluster_timezone.localize(datetime.datetime.now())
        self.__md_struct.save()

    def send_slave_command(self, action_srvc, **kwargs):
        # send command from local master to remote slave
        if isinstance(action_srvc, basestring):
            srv_com = self._get_slave_srv_command(action_srvc, **kwargs)
        else:
            srv_com = action_srvc

        self.log(
            u"send {} to {} (UUID={}, {})".format(
                srv_com["*action"],
                unicode(self.name),
                self.slave_uuid,
                ", ".join(["{}='{}'".format(_key, str(_value)) for _key, _value in kwargs.iteritems()]),
            )
        )
        self.__process.send_command(
            self.slave_uuid,
            unicode(srv_com),
        )

    def _get_slave_srv_command(self, action, **kwargs):
        return server_command.srv_command(
            command="slave_command",
            action=action,
            slave_uuid=self.slave_uuid,
            master="1" if self.master else "0",
            **kwargs
        )

    def _get_config_srv_command(self, action, **kwargs):
        # server command to local md-config-server from distribution master
        return server_command.srv_command(
            command="slave_info",
            action=action,
            slave_uuid=self.slave_uuid,
            master="1" if self.master else "0",
            **kwargs
        )

    def _build_file_content(self, _send_list):
        srv_com = self._get_slave_srv_command(
            "file_content_bulk",
            version="{:d}".format(int(self.send_time)),
        )
        _bld = srv_com.builder()

        srv_com["file_list"] = _bld.file_list(
            *[
                _bld.file(
                    _path,
                    size="{:d}".format(_size)
                ) for _uid, _gid, _path, _size, _content in _send_list
            ]
        )
        srv_com["bulk"] = base64.b64encode(bz2.compress("".join([_parts[-1] for _parts in _send_list])))
        return srv_com

    def _show_pending_info(self):
        if self.__file_dict:
            cur_time = time.time()
            pend_keys = [key for key, value in self.__file_dict.iteritems() if value.is_pending]
            error_keys = [key for key, value in self.__file_dict.iteritems() if value.is_error]
            self.log(
                "{:d} total, {} pending, {} error".format(
                    len(self.__file_dict),
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
                # self.__md_struct.sync_end = cluster_timezone.localize(datetime.datetime.now())
                # self.__md_struct.save()
                self._check_for_ras()

                self.__process.send_to_config_server(
                    self._get_config_srv_command(
                        "sync_end",
                    )
                )

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

    # remote actions
    def handle_remote_action(self, action, srv_com):
        _attr_name = "handle_remote_{}".format(action)
        if not hasattr(self, _attr_name):
            self.log("unknown remote action '{}'".format(action), logging_tools.LOG_LEVEL_ERROR)
        else:
            getattr(self, _attr_name)(srv_com)

    def handle_remote_reload_after_sync(self, srv_com):
        self.reload_after_sync_flag = True
        self.send_slave_command("reload_after_sync")

    def handle_remote_sync_slave(self, srv_com):
        # max uncompressed send size
        MAX_SEND_SIZE = 65536
        cur_time = time.time()
        if self.slave_ip:
            self.config_version_send = self.config_version_build
            self.send_time = int(cur_time)
            # to distinguish between iterations during a single build
            self.send_time_lut[self.send_time] = self.config_version_send
            self.dist_ok = False
            self.log(
                "start send to slave (version {:d} [{:d}])".format(
                    self.config_version_send,
                    self.send_time,
                )
            )
            # number of atomic commands
            _num_files, _size_data = (0, 0)
            # send content of /etc
            dir_offset = len(self.__w_dir_dict["etc"])
            # generation 1 transfer
            del_dirs = []
            for cur_dir, _dir_names, file_names in os.walk(self.__w_dir_dict["etc"]):
                rel_dir = cur_dir[dir_offset + 1:]
                del_dirs.append(os.path.join(self.__r_dir_dict["etc"], rel_dir))
            if del_dirs:
                srv_com = self._get_slave_srv_command(
                    "clear_directories",
                    version="{:d}".format(int(self.send_time)),
                )
                _bld = srv_com.builder()
                srv_com["directories"] = _bld.directories(*[_bld.directory(del_dir) for del_dir in del_dirs]),
                self.send_slave_command(srv_com)
            _send_list, _send_size = ([], 0)
            # clear file dict
            self.__file_dict = {}
            for cur_dir, _dir_names, file_names in os.walk(self.__w_dir_dict["etc"]):
                rel_dir = cur_dir[dir_offset + 1:]
                for cur_file in sorted(file_names):
                    full_r_path = os.path.join(self.__w_dir_dict["etc"], rel_dir, cur_file)
                    full_w_path = os.path.join(self.__r_dir_dict["etc"], rel_dir, cur_file)
                    if os.path.isfile(full_r_path):
                        self.__file_dict[full_w_path] = FileInfo(full_w_path, self.config_version_send)
                        _content = file(full_r_path, "r").read()
                        _size_data += len(_content)
                        _num_files += 1
                        if _send_size + len(_content) > MAX_SEND_SIZE:
                            self._send(self._build_file_content(_send_list))
                            _send_list, _send_size = ([], 0)
                        # format: uid, gid, path, content_len, content
                        _send_list.append((os.stat(full_r_path)[stat.ST_UID], os.stat(full_r_path)[stat.ST_GID], full_w_path, len(_content), _content))
            if _send_list:
                self.send_slave_command(self._build_file_content(_send_list))
                _send_list, _send_size = ([], 0)
            self.num_send[self.config_version_send] = 0
            self.__process.send_to_config_server(
                self._get_config_srv_command(
                    "sync_start",
                    num_files=_num_files,
                    size_data=_size_data,
                )
            )
            # self.__md_struct.num_files = self.__num_com
            # self.__md_struct.num_transfers = self.__num_com
            # self.__md_struct.size_raw = self.__size_raw
            # self.__md_struct.size_data = size_data
            # self.__md_struct.save()
            self._show_pending_info()
        else:
            self.log("slave has no valid IP-address, skipping send", logging_tools.LOG_LEVEL_ERROR)

    # local actions
    def handle_local_action(self, action, srv_com):
        _attr_name = "handle_local_{}".format(action)
        if not hasattr(self, _attr_name):
            self.log("unknown local action '{}'".format(action), logging_tools.LOG_LEVEL_ERROR)
        else:
            getattr(self, _attr_name)(srv_com)

    def handle_local_reload_after_sync(self, srv_com):
        self.reload_after_sync_flag = True
        self._check_for_ras()

    # direct actions
    def handle_direct_action(self, action, srv_com):
        _attr_name = "handle_direct_{}".format(action)
        if not hasattr(self, _attr_name):
            self.log("unknown direct action '{}'".format(action), logging_tools.LOG_LEVEL_ERROR)
        else:
            getattr(self, _attr_name)(srv_com)

    def handle_direct_clear_directories(self, srv_com):
        # print srv_com.pretty_print()
        for dir_name in srv_com.xpath(".//ns:directories/ns:directory/text()"):
            self._clear_dir(dir_name)

    def handle_direct_file_content_bulk(self, srv_com):
        new_vers = int(srv_com["*version"])
        _file_list = srv_com["file_list"][0]
        _bulk = bz2.decompress(base64.b64decode(srv_com["*bulk"]))
        cur_offset = 0
        self.log(
            "got {} (version {:d})".format(
                logging_tools.get_plural("bulk file", len(srv_com.xpath(".//ns:file_list/ns:file"))),
                new_vers,
            )
        )
        for _entry in srv_com.xpath(".//ns:file_list/ns:file"):
            _size = int(_entry.get("size"))
            self._store_file(_entry.text, new_vers, _bulk[cur_offset:cur_offset + _size])
            cur_offset += _size
        self.__process._send_satellite_info()

    def _store_file(self, t_file, new_vers, content):
        MON_TOP_DIR = global_config["MD_BASEDIR"]
        if not t_file.startswith(MON_TOP_DIR):
            self.log(
                "refuse to operate outside '{}'".format(
                    MON_TOP_DIR,
                ),
                logging_tools.LOG_LEVEL_CRITICAL
            )
        else:
            renew, log_str, file_info = self._check_version(t_file, new_vers)
            if renew:
                t_dir = os.path.dirname(t_file)
                if not os.path.exists(t_dir):
                    try:
                        os.makedirs(t_dir)
                    except:
                        self.log(
                            "error creating directory {}: {}".format(
                                t_dir,
                                process_tools.get_except_info()
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                    else:
                        self.log("created directory {}".format(t_dir))
                if os.path.exists(t_dir):
                    try:
                        file(t_file, "w").write(content)
                        # we no longer chown because we are not running as root
                    except:
                        self.log(
                            "error creating file {}: {}".format(
                                t_file,
                                process_tools.get_except_info()
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                        file_info.log_error(process_tools.get_except_info())
                    else:
                        self.log(
                            "created {} [{}, {}]".format(
                                t_file,
                                logging_tools.get_size_str(len(content)).strip(),
                                log_str,
                            )
                        )
                        file_info.log_success()
            else:
                self.log("file {} not newer [{}]".format(t_file, log_str), logging_tools.LOG_LEVEL_WARN)

    def _check_version(self, key, new_vers):
        if key in self.__file_dict:
            _renew, _log = self.__file_dict[key].compare(new_vers)
        else:
            self.__file_dict[key] = FileInfo(key, new_vers)
            _renew, _log = (True, "new version ({:d})".format(new_vers))
        return _renew, _log, self.__file_dict[key]

    def _clear_file_info(self, key):
        if key in self.__file_dict:
            del self.__file_dict[key]

    def _clear_dir(self, t_dir):
        MON_TOP_DIR = global_config["MD_BASEDIR"]
        if not t_dir.startswith(MON_TOP_DIR):
            self.log(
                "refuse to operate outside '{}'".format(
                    MON_TOP_DIR,
                ),
                logging_tools.LOG_LEVEL_CRITICAL
            )
        else:
            self.log("clearing directory {}".format(t_dir))
            num_rem = 0
            if os.path.isdir(t_dir):
                for entry in os.listdir(t_dir):
                    f_path = os.path.join(t_dir, entry)
                    # remove from file_dict
                    self._clear_file_info(f_path)
                    if os.path.isfile(f_path):
                        try:
                            os.unlink(f_path)
                        except:
                            self.log(
                                "cannot remove {}: {}".format(
                                    f_path,
                                    process_tools.get_except_info()
                                ),
                                logging_tools.LOG_LEVEL_ERROR
                            )
                        else:
                            num_rem += 1
            else:
                self.log("directory '{}' does not exist".format(t_dir), logging_tools.LOG_LEVEL_ERROR)
            self.log("removed {} in {}".format(logging_tools.get_plural("file", num_rem), t_dir))

    def handle_direct_reload_after_sync(self, srv_com):
        self.reload_after_sync_flag = True
        self._check_for_ras()

    def handle_direct_register_master(self, srv_com):
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

    def _check_for_ras(self):
        if self.reload_after_sync_flag and self.dist_ok:
            self.reload_after_sync_flag = False
            self.log("sending reload")
            self.__process.send_pool_message(
                "send_signal",
                signal.SIGHUP,
            )

    def handle_action(self, action, srv_com):
        s_time = time.time()
        if self.master is None:
            # direct local action
            _type = "direct"
            self.handle_direct_action(action, srv_com)
        elif self.master:
            # local action on sync master
            _type = "local"
            self.handle_local_action(action, srv_com)
        else:
            # remote action
            _type = "remote"
            self.handle_remote_action(action, srv_com)
        e_time = time.time()
        self.log(
            "{} action {} took {}".format(
                action,
                _type,
                logging_tools.get_diff_time_str(e_time - s_time),
            )
        )
