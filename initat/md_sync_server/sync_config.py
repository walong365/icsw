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

from __future__ import print_function, unicode_literals

import base64
import bz2
import json
import os
import signal
import stat
import time

from initat.host_monitoring.client_enums import icswServiceEnum
from initat.server_version import VERSION_MAJOR, VERSION_MINOR
from initat.tools import logging_tools, process_tools, server_command, config_store
from .base_config import RemoteServer, SlaveState
from .config import global_config, CS_MON_NAME

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
        # print "*", self.created, remote_result["version"], self.target_version
        if remote_result["version"] != self.target_version:
            self.created = False

    @property
    def is_pending(self):
        # print "ip", self.created, self.error, self.path
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
        # registered at master
        self.__registered_at_master = False
        if di_dict is None:
            # distribution slave on remote device
            self.name = None
            self.master = None
            self.master_config = None
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
            if "dir_offset" not in di_dict:
                self.log("old master data found", logging_tools.LOG_LEVEL_WARN)
                if self.name:
                    self.__dir_offset = os.path.join("slaves", self.name)
                else:
                    self.__dir_offset = ""
            else:
                self.__dir_offset = di_dict["dir_offset"]
            if self.name:
                # distribution slave structure on dist master
                self.struct = None
                # latest conact
                self.__latest_contact = None
                self.config_store = config_store.ConfigStore(CS_MON_NAME, log_com=self.__process.log, access_mode=config_store.AccessModeEnum.LOCAL, read=False)
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
                # distribution master structure
                self.__slave_configs, self.__slave_lut = ({}, {})
                # local master structure, is usually none due to delayed check of MD_TYPE in snycer.py
                self.struct = kwargs["local_master"]
                self.config_store = None
                self.master_ip = "127.0.0.1"
                self.master_port = di_dict["master_port"]
                self.pure_uuid = di_dict["pure_uuid"]
                self.master_uuid = di_dict["master_uuid"]
                self.slave_uuid = None
                self.log("master uuid is {}@{}, {:d}".format(self.master_uuid, self.master_ip, self.master_port))
            self.log("dir offset is {}".format(self.__dir_offset))
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

    def set_livestatus_version(self, ls_version):
        self.config_store["livestatus.version"] = ls_version
        self.config_store.write()

    def add_slaves(self, dist_info, inst_xml):
        # dict for all slaves
        self.__slave_configs, self.__slave_lut = ({}, {})
        for _di in dist_info:
            if not _di["master"]:
                self.log("found slave entry ({})".format(", ".join(sorted(_di.keys()))))
                _slave_c = SyncConfig(
                    self.__process,
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
                    self.__process.register_remote(
                        _slave_c.slave_ip,
                        _slave_c.slave_uuid,
                        inst_xml.get_port_dict(icswServiceEnum.monitor_slave, command=True)
                    )
        self.send_info_message()

    def get_slave(self, uuid):
        # for distribution master
        return self.__slave_configs[self.__slave_lut[uuid]]

    def send_register_msg(self, **kwargs):
        for _slave_struct in [self] + self.__slave_configs.values():
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

    def set_local_master(self, local_master):
        self.log("linking local_master with master_config")
        self.struct = local_master
        local_master.master_config = self

    def get_satellite_info(self):
        r_dict = {
            "config_store": {},
        }
        if self.config_store is not None:
            # may be none for local master
            for _key in ["md.version", "md.release", "icsw.version", "icsw.release", "livestatus.version"]:
                if _key in self.config_store:
                    r_dict["config_store"][_key] = self.config_store[_key]
        if self.master is None:
            r_dict["store_info"] = {
                _fi.path: _fi.get_info_dict() for _fi in self.__file_dict.itervalues()
            }
        return r_dict

    def store_satellite_info(self, si_info, dist_master):
        for _key in si_info.get("config_store", {}).keys():
            self.config_store[_key] = si_info["config_store"][_key]
        self.__latest_contact = time.time()
        if "store_info" in si_info:
            if self.__file_dict:
                for _key, _struct in si_info["store_info"].iteritems():
                    if _key not in self.__file_dict:
                        self.log("key '{}' not known in local file_dict".format(_key), logging_tools.LOG_LEVEL_ERROR)
                    else:
                        self.__file_dict[_key].store_result(_struct)
                self._show_pending_info(dist_master)

    def get_info_dict(self):
        r_dict = {
            "master": self.master,
            "slave_uuid": self.slave_uuid,
            "state": self.state.name,
            "latest_contact": self.__latest_contact,
        }
        if self.struct is not None:
            # local master
            r_dict.update(self.struct.get_satellite_info())
        else:
            r_dict.update(self.get_satellite_info())
        r_dict["sysinfo"] = self.__process.get_sys_dict()
        return r_dict

    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__process.log(
            u"[sc {}] {}".format(
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

    def send_slave_command(self, action_srvc, **kwargs):
        # send command from local master to remote slave
        if isinstance(action_srvc, basestring):
            srv_com = self._get_slave_srv_command(action_srvc, **kwargs)
        else:
            srv_com = action_srvc

        self.log(
            u"send {} to {} (UUID={}, {})".format(
                srv_com.get("action", srv_com["*command"]),
                unicode(self.name),
                self.slave_uuid,
                ", ".join(["{}='{}'".format(_key, str(_value)) for _key, _value in kwargs.iteritems()]),
            )
        )
        self.__process.send_command(
            self.slave_uuid,
            srv_com,
        )

    def _get_slave_srv_command(self, action, **kwargs):
        # server command from distribution master to remote slave
        return server_command.srv_command(
            command="slave_command",
            action=action,
            slave_uuid=self.slave_uuid,
            msg_src="D",
            master="1" if self.master else "0",
            **kwargs
        )

    def _get_config_srv_command(self, action, **kwargs):
        # server command to local md-config-server from distribution master
        # print "SI_COM", action
        return server_command.srv_command(
            command="slave_info",
            action=action,
            slave_uuid=self.slave_uuid,
            master="1" if self.master else "0",
            **kwargs
        )

    def send_info_message(self):
        # set latest contact for dist master
        self.__latest_contact = time.time()
        # send info to monitor daemon
        info_list = [
            _entry.get_info_dict() for _entry in [self] + self.__slave_configs.values()
        ]
        # print "ILIST", self.master_uuid, self.slave_uuid
        srv_com = self._get_config_srv_command(
            "info_list",
            slave_info=server_command.compress(info_list, json=True),
        )
        self.send_to_config_server(srv_com)

    def send_to_config_server(self, srv_com):
        self.__process.send_command(
            self.master_uuid,
            unicode(srv_com),
        )

    def _get_dist_master_srv_command(self, action, **kwargs):
        # server command from dist slave to dist master
        return server_command.srv_command(
            command="slave_command",
            action=action,
            slave_uuid=self.config_store["slave.uuid"],
            msg_src="S",
            master="1" if self.master else "0",
            **kwargs
        )

    def check_for_register_at_master(self):
        # is called with local_master on distribution master
        if not self.__registered_at_master and "master.uuid" in self.config_store:
            self.__registered_at_master = True
            # open connection to master server
            self.__process.register_remote(
                self.config_store["master.ip"],
                self.config_store["master.uuid"],
                self.config_store["master.port"],
            )
        # send satellite info
        self.send_satellite_info()

    def send_satellite_info(self):
        if self.master_config:
            # send full info when on distribution master
            self.master_config.send_info_message()
        else:
            if self.__registered_at_master:
                self.send_to_sync_master(
                    self._get_satellite_info()
                )

    def send_to_sync_master(self, srv_com):
        if self.__registered_at_master:
            self.__process.send_command(
                self.config_store["master.uuid"],
                unicode(srv_com),
            )
        else:
            self.log("slave not registered at master")

    def _get_satellite_info(self):
        return self._get_dist_master_srv_command(
            "satellite_info",
            satellite_info=server_command.compress(self.get_satellite_info(), json=True)
        )

    def _build_file_content(self, _send_list):
        srv_com = self._get_slave_srv_command(
            "file_content_bulk",
            config_version_send="{:d}".format(self.config_version_send),
            send_time="{:d}".format(int(self.send_time)),
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

    def _show_pending_info(self, dist_master):
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

            # this makes only sense on slave
            # self._check_for_ras()

            dist_master.send_to_config_server(
                self._get_config_srv_command(
                    "sync_end",
                )
            )
            # clear file_dict
            self.__file_dict = {}

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
    def forward_srv_com(self, srv_com):
        # forward srv com to other dist slaves
        self.log(
            "forwarding srv_com '{}' to {}...".format(
                srv_com["*command"],
                logging_tools.get_plural("slave", len(self.__slave_configs)),
            )
        )
        # set forward flag
        srv_com["forwarded"] = True
        for _slave in self.__slave_configs.itervalues():
            _slave.send_slave_command(srv_com)
        # always send info message
        self.send_info_message()

    def handle_remote_action(self, action, srv_com):
        _attr_name = "handle_remote_{}".format(action)
        try:
            remote_slave = self.get_slave(srv_com["*slave_uuid"])
        except:
            self.log("unable to get slave: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
        else:
            if not hasattr(self, _attr_name):
                self.log("unknown remote action '{}'".format(action), logging_tools.LOG_LEVEL_ERROR)
            else:
                getattr(remote_slave, _attr_name)(srv_com, self)

    def handle_remote_reload_after_sync(self, srv_com, dist_master):
        self.reload_after_sync_flag = True
        self.send_slave_command("reload_after_sync")

    def handle_remote_satellite_info(self, srv_com, dist_master):
        si_info = server_command.decompress(srv_com["*satellite_info"], json=True)
        self.store_satellite_info(si_info, dist_master)
        dist_master.send_info_message()

    def handle_remote_sync_slave(self, srv_com, dist_master):
        # max uncompressed send size
        self.config_version_build = int(srv_com["*config_version_build"])
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
            _to_send, _num_files, _size_data = self._get_send_commands(json.loads(srv_com["*file_tuples"]))
            self.num_send[self.config_version_send] = 0
            for _send_com in _to_send:
                self.send_slave_command(_send_com)
            dist_master.send_to_config_server(
                self._get_config_srv_command(
                    "sync_start",
                    num_files=_num_files,
                    size_data=_size_data,
                )
            )
            self._show_pending_info(dist_master)
        else:
            self.log("slave has no valid IP-address, skipping send", logging_tools.LOG_LEVEL_ERROR)

    def _get_send_commands(self, file_tuples):
        # file tuples are used for httpd-users syncs
        excl_file_dict = {src: dst for src, dst in file_tuples}
        # print("*", excl_file_dict)
        MAX_SEND_SIZE = 65536
        _to_send = []
        # number of atomic commands
        _num_files, _size_data = (0, 0)
        # send content of /etc
        dir_offset = len(self.__w_dir_dict["etc"])
        # generation 1 transfer
        del_dirs = []
        if not file_tuples:
            for cur_dir, _dir_names, file_names in os.walk(self.__w_dir_dict["etc"]):
                rel_dir = cur_dir[dir_offset + 1:]
                del_dirs.append(os.path.join(self.__r_dir_dict["etc"], rel_dir))
            if del_dirs:
                srv_com = self._get_slave_srv_command(
                    "clear_directories",
                    version="{:d}".format(int(self.send_time)),
                )
                _bld = srv_com.builder()
                srv_com["directories"] = _bld.directories(*[_bld.directory(del_dir) for del_dir in del_dirs])
                _to_send.append(srv_com)
        _send_list, _send_size = ([], 0)
        # clear file dict
        self.__file_dict = {}
        for cur_dir, _dir_names, file_names in os.walk(self.__w_dir_dict["etc"]):
            rel_dir = cur_dir[dir_offset + 1:]
            for cur_file in sorted(file_names):
                full_r_path = os.path.join(self.__w_dir_dict["etc"], rel_dir, cur_file)
                full_w_path = os.path.join(self.__r_dir_dict["etc"], rel_dir, cur_file)
                if os.path.isfile(full_r_path):
                    if excl_file_dict:
                        _take = full_r_path in excl_file_dict
                    else:
                        _take = True
                    if _take:
                        self.__file_dict[full_w_path] = FileInfo(full_w_path, self.config_version_send)
                        _content = file(full_r_path, "r").read()
                        _size_data += len(_content)
                        _num_files += 1
                        if _send_size + len(_content) > MAX_SEND_SIZE:
                            _to_send.append(self._build_file_content(_send_list))
                            _send_list, _send_size = ([], 0)
                        # format: uid, gid, path, content_len, content
                        _send_list.append((os.stat(full_r_path)[stat.ST_UID], os.stat(full_r_path)[stat.ST_GID], full_w_path, len(_content), _content))
        if _send_list:
            _to_send.append(self._build_file_content(_send_list))
        return _to_send, _num_files, _size_data

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

    def handle_local_sync_slave(self, srv_com):
        # copy config versions from srv_com (see handle_remote_sync_slave)
        self.config_version_build = int(srv_com["*config_version_build"])
        self.config_version_send = self.config_version_build
        # create send commands
        _to_send, _num_files, _size_data = self._get_send_commands(json.loads(srv_com["*file_tuples"]))
        self.log(
            "local sync, handling {} ({})".format(
                logging_tools.get_plural("file", _num_files),
                logging_tools.get_size_str(_size_data),
            )
        )
        # and process them
        for srv_com in _to_send:
            self.struct.handle_direct_action(srv_com["*action"], srv_com)

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
        self.send_satellite_info()

    def handle_direct_file_content_bulk(self, srv_com):
        new_vers = int(srv_com["*config_version_send"])
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
        self.send_satellite_info()

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
            self.__process.send_signal(signal.SIGHUP)
        else:
            self.log(
                "not sending reload: reload_after_sync_flag is {}, dist_ok is {}".format(
                    str(self.reload_after_sync_flag),
                    str(self.dist_ok),
                ),
                logging_tools.LOG_LEVEL_WARN
            )

    def handle_action(self, action, srv_com, src, dst):
        s_time = time.time()
        # signature
        _sig = "{}{}".format(src, dst)
        _type = {
            # slave to remote (dist slave to dist master)
            "SR": "remote",
            # mon server to remote
            "MR": "remote",
            # mon server to dist master
            "MD": "local",
            "DS": "direct",
        }[_sig]
        getattr(self, "handle_{}_action".format(_type))(action, srv_com)
        e_time = time.time()
        self.log(
            "{} action {} took {}".format(
                action,
                _type,
                logging_tools.get_diff_time_str(e_time - s_time),
            )
        )
