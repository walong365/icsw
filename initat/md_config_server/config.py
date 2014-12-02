# Copyright (C) 2008-2014 Andreas Lang-Nevyjel, init.at
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
""" config part of md-config-server """

from django.conf import settings
from django.db.models import Q
from initat.cluster.backbone.models import device, device_group, device_variable, mon_device_templ, \
    mon_check_command, mon_period, mon_contact, mon_contactgroup, mon_service_templ, \
    user, category_tree, TOP_MONITORING_CATEGORY, mon_notification, host_check_command, \
    mon_dist_master, mon_dist_slave, cluster_timezone, mon_check_command_special, \
    mon_host_cluster, mon_service_cluster, mon_trace, mon_host_dependency, mon_service_dependency, \
    mon_build_unreachable, parse_commandline
from initat.md_config_server.version import VERSION_STRING
from initat.snmp.sink import SNMPSink
from lxml.builder import E  # @UnresolvedImport
import ConfigParser
import base64
import binascii
import bz2
import cluster_location
import codecs
import config_tools
import configfile
import datetime
import json
import logging_tools
import marshal
import os
import process_tools
import server_command
import shutil
import sqlite3
import stat
import sys
import time

global_config = configfile.get_global_config(process_tools.get_programm_name())


# also used in parse_anovis
def build_safe_name(in_str):
    in_str = in_str.replace("/", "_").replace(" ", "_").replace("(", "[").replace(")", "]")
    while in_str.count("__"):
        in_str = in_str.replace("__", "_")
    return in_str


# a similiar structure is used in the server process of rrd-grapher
class var_cache(dict):
    def __init__(self, cdg, prefill=False):
        super(var_cache, self).__init__(self)
        self.__cdg = cdg
        self.__prefill = prefill
        if prefill:
            self._prefill()

    def get_global_def_dict(self):
        return {
            "SNMP_VERSION": 2,
            "SNMP_READ_COMMUNITY": "public",
            "SNMP_WRITE_COMMUNITY": "private",
        }

    def _prefill(self):
        for _var in device_variable.objects.all().select_related("device__device_type"):
            if _var.device.device_type.identifier == "MD":
                if _var.device.device_group_id == self.__cdg.pk:
                    _key = "GLOBAL"
                    if _key not in self:
                        self[_key] = {g_key: g_value for g_key, g_value in self.get_global_def_dict().iteritems()}
                else:
                    _key = "dg__{:d}".format(_var.device.device_group_id)
            else:
                _key = "dev__{:d}".format(_var.device_id)
            self.setdefault(_key, {})[_var.name] = _var.value

    def get_vars(self, cur_dev):
        global_key, dg_key, dev_key = (
            "GLOBAL",
            "dg__{:d}".format(cur_dev.device_group_id),
            "dev__{:d}".format(cur_dev.pk))
        if global_key not in self:
            def_dict = self.get_global_def_dict()
            # read global configs
            self[global_key] = dict([(cur_var.name, cur_var.get_value()) for cur_var in device_variable.objects.filter(Q(device=self.__cdg))])
            # update with def_dict
            for key, value in def_dict.iteritems():
                if key not in self[global_key]:
                    self[global_key][key] = value
        if not self.__prefill:
            # do not query the devices
            if dg_key not in self:
                # read device_group configs
                self[dg_key] = dict([(cur_var.name, cur_var.get_value()) for cur_var in device_variable.objects.filter(Q(device=cur_dev.device_group.device))])
            if dev_key not in self:
                # read device configs
                self[dev_key] = dict([(cur_var.name, cur_var.get_value()) for cur_var in device_variable.objects.filter(Q(device=cur_dev))])
        ret_dict, info_dict = ({}, {})
        # for s_key in ret_dict.iterkeys():
        for key, key_n in [(dev_key, "d"), (dg_key, "g"), (global_key, "c")]:
            info_dict[key_n] = 0
            for s_key, s_value in self.get(key, {}).iteritems():
                if s_key not in ret_dict:
                    ret_dict[s_key] = s_value
                    info_dict[key_n] += 1
        # print cur_dev, ret_dict, info_dict
        return ret_dict, info_dict


class sync_config(object):
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
            master_cfg = config_tools.device_with_config("monitor_server")
            slave_cfg = config_tools.server_check(
                short_host_name=monitor_server.name,
                server_type="monitor_slave",
                fetch_network_info=True)
            self.slave_uuid = monitor_server.uuid
            route = master_cfg["monitor_server"][0].get_route_to_other_device(
                self.__process.router_obj,
                slave_cfg,
                allow_route_to_other_networks=True,
                global_sort_results=True,
                )
            if not route:
                self.slave_ip = None
                self.master_ip = None
                self.log("no route to slave %s found" % (unicode(monitor_server)), logging_tools.LOG_LEVEL_ERROR)
            else:
                self.slave_ip = route[0][3][1][0]
                self.master_ip = route[0][2][1][0]
                self.log("IP-address of slave %s is %s (master: %s)" % (
                    unicode(monitor_server),
                    self.slave_ip,
                    self.master_ip
                ))
            # target config version directory for distribute
            self.__tcv_dict = {}
        else:
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
        # relayer info
        self.relayer_version = "?.?-0"
        self.mon_version = "?.?-0"
        # clear md_struct
        self.__md_struct = None
        if not self.master:
            # try to get relayer / mon_version from latest build
            _latest_build = mon_dist_slave.objects.filter(Q(device=self.monitor_server)).order_by("-pk")
            if len(_latest_build):
                _latest_build = _latest_build[0]
                self.mon_version = _latest_build.mon_version
                self.relayer_version = _latest_build.relayer_version
                self.log("recovered MonVer %s / RelVer %s from DB" % (self.mon_version, self.relayer_version))

    def _relayer_gen(self):
        # return the relayer generation
        # 0 ... old one, no bulk transfers
        # 1 ... supports bulk transfer (file_content_bulk and clear_directories)
        _r_gen = 0
        _r_vers = self.relayer_version
        if _r_vers.count("-"):
            _r_vers = _r_vers.split("-")[0]
            if _r_vers.count(".") == 1:
                _r_vers = [int(_part.strip()) for _part in _r_vers.split(".") if _part.strip() and _part.strip().isdigit()]
                if len(_r_vers) == 2:
                    major, minor = _r_vers
                    if major < 5:
                        pass
                    elif major > 5:
                        _r_gen = 1
                    else:
                        if minor > 1:
                            _r_gen = 1
        return _r_gen

    def reload_after_sync(self):
        self.reload_after_sync_flag = True
        self._check_for_ras()

    def set_relayer_info(self, srv_com):
        for key in ["relayer_version", "mon_version"]:
            if key in srv_com:
                _new_vers = srv_com[key].text
                if _new_vers != getattr(self, key):
                    self.log("changing %s from '%s' to '%s'" % (
                        key,
                        getattr(self, key),
                        _new_vers))
                    setattr(self, key, _new_vers)

    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__process.log("[sc %s] %s" % (
            self.__slave_name if self.__slave_name else "master",
            what), level)

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
            "var/spool/checkresults"]
        if process_tools.get_sys_bits() == 64:
            dir_names.append("lib64")
        # dir dict for writing on disk
        self.__w_dir_dict = dict([(dir_name, os.path.normpath(os.path.join(self.__main_dir, self.__dir_offset, dir_name))) for dir_name in dir_names])
        # dir dict for referencing
        self.__r_dir_dict = dict([(dir_name, os.path.normpath(os.path.join(self.__main_dir, dir_name))) for dir_name in dir_names])

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
            from initat.host_monitoring.version import VERSION_STRING as RELAYER_VERSION_STRING
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
            _r_gen = self._relayer_gen()
            self.log("start send to slave (version {:d} [{:d}], generation is {:d})".format(
                self.config_version_send,
                self.send_time,
                _r_gen,
                ))
            # number of atomic commands
            self.__num_com = 0
            self.__size_raw, size_data = (0, 0)
            # send content of /etc
            dir_offset = len(self.__w_dir_dict["etc"])
            if _r_gen == 0:
                # generation 0 transfer
                for cur_dir, _dir_names, file_names in os.walk(self.__w_dir_dict["etc"]):
                    rel_dir = cur_dir[dir_offset + 1:]
                    # send a clear_directory message
                    srv_com = server_command.srv_command(
                        command="clear_directory",
                        host="DIRECT",
                        slave_name=self.__slave_name,
                        port="0",
                        version="%d" % (self.send_time),
                        directory=os.path.join(self.__r_dir_dict["etc"], rel_dir),
                        )
                    self._send(srv_com)
                    for cur_file in sorted(file_names):
                        full_r_path = os.path.join(self.__w_dir_dict["etc"], rel_dir, cur_file)
                        full_w_path = os.path.join(self.__r_dir_dict["etc"], rel_dir, cur_file)
                        if os.path.isfile(full_r_path):
                            self.__tcv_dict[full_w_path] = self.config_version_send
                            _content = file(full_r_path, "r").read()
                            size_data += len(_content)
                            srv_com = server_command.srv_command(
                                command="file_content",
                                host="DIRECT",
                                slave_name=self.__slave_name,
                                port="0",
                                uid="{:d}".format(os.stat(full_r_path)[stat.ST_UID]),
                                gid="{:d}".format(os.stat(full_r_path)[stat.ST_GID]),
                                version="{:d}".format(self.send_time),
                                file_name="{}".format(full_w_path),
                                content=base64.b64encode(_content)
                            )
                            self._send(srv_com)
            else:
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
                        version="%d" % (self.send_time),
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
            version="%d" % (self.send_time),
        )
        _bld = srv_com.builder()

        srv_com["file_list"] = _bld.file_list(
            *[_bld.file(_path, uid="%d" % (_uid), gid="%d" % (_gid), size="%d" % (_size)) for _uid, _gid, _path, _size, _content in _send_list]
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
            self.log("actual distribution_set %d is OK (in %s, %.2f / sec)" % (
                self.config_version_send,
                logging_tools.get_diff_time_str(_dist_time),
                self.num_send[self.config_version_send] / _dist_time,
                ))
            self.config_version_installed = self.config_version_send
            self.dist_ok = True
            self.__md_struct.sync_end = cluster_timezone.localize(datetime.datetime.now())
            self.__md_struct.save()
            self._check_for_ras()

    def _check_for_ras(self):
        if self.reload_after_sync_flag and self.dist_ok:
            self.reload_after_sync_flag = False
            self.log("sending reload")
            srv_com = server_command.srv_command(
                command="call_command",
                host="DIRECT",
                port="0",
                version="%d" % (self.config_version_send),
                cmdline="/etc/init.d/icinga reload")
            self.__process.send_command(self.monitor_server.uuid, unicode(srv_com))

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
                self.log("file_state %d is not valid" % (file_status), logging_tools.LOG_LEVEL_CRITICAL)
            self.log("file_content_status for %s is %s (%d), version %d (dist: %d)" % (
                file_name,
                srv_com["result"].attrib["reply"],
                file_status,
                version,
                self.send_time_lut.get(version, 0),
                ), file_status)
            file_names = [file_name]
        elif cmd == "file_content_bulk_result":
            num_ok, num_failed = (int(srv_com["num_ok"].text), int(srv_com["num_failed"].text))
            self.log("%d ok / %d failed" % (num_ok, num_failed))
            failed_list = marshal.loads(bz2.decompress(base64.b64decode(srv_com["failed_list"].text)))
            ok_list = marshal.loads(bz2.decompress(base64.b64decode(srv_com["ok_list"].text)))
            if ok_list:
                _ok_dir, _ok_list = self._parse_list(ok_list)
                self.log("ok list (beneath {}): {}".format(
                    _ok_dir,
                    ", ".join(sorted(_ok_list)) if global_config["DEBUG"] else logging_tools.get_plural("entry", len(_ok_list))))
            if failed_list:
                _failed_dir, _failed_list = self._parse_list(failed_list)
                self.log("failed list (beneath %s): %s" % (
                    _failed_dir,
                    ", ".join(sorted(_failed_list))))
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


class main_config(object):
    def __init__(self, proc, monitor_server, **kwargs):
        self.__process = proc
        self.__slave_name = kwargs.get("slave_name", None)
        self.__main_dir = global_config["MD_BASEDIR"]
        self.distributed = kwargs.get("distributed", False)
        if self.__slave_name:
            self.__dir_offset = os.path.join("slaves", self.__slave_name)
            master_cfg = config_tools.device_with_config("monitor_server")
            slave_cfg = config_tools.server_check(
                short_host_name=monitor_server.name,
                server_type="monitor_slave",
                fetch_network_info=True)
            self.slave_uuid = monitor_server.uuid
            route = master_cfg["monitor_server"][0].get_route_to_other_device(self.__process.router_obj, slave_cfg, allow_route_to_other_networks=True)
            if not route:
                self.slave_ip = None
                self.master_ip = None
                self.log("no route to slave %s found" % (unicode(monitor_server)), logging_tools.LOG_LEVEL_ERROR)
            else:
                self.slave_ip = route[0][3][1][0]
                self.master_ip = route[0][2][1][0]
                self.log("IP-address of slave %s is %s (master: %s)" % (
                    unicode(monitor_server),
                    self.slave_ip,
                    self.master_ip
                ))
        else:
            self.__dir_offset = ""
            # self.__min_dir = os.path.join(self.__main_dir, "slaves", self.__slave_name)
        self.monitor_server = monitor_server
        self.master = True if not self.__slave_name else False
        self.__dict = {}
        self._create_directories()
        self._clear_etc_dir()
        self.allow_write_entries = global_config["BUILD_CONFIG_ON_STARTUP"] or global_config["INITIAL_CONFIG_RUN"]
        self._create_base_config_entries()
        self._write_entries()
        self.allow_write_entries = True

    @property
    def allow_write_entries(self):
        return self.__allow_write_entries

    @allow_write_entries.setter
    def allow_write_entries(self, val):
        self.__allow_write_entries = val

    @property
    def slave_name(self):
        return self.__slave_name

    @property
    def var_dir(self):
        return self.__r_dir_dict["var"]

    def is_valid(self):
        ht_conf_names = [key for key, value in self.__dict.iteritems() if isinstance(value, host_type_config)]
        invalid = sorted([key for key in ht_conf_names if not self[key].is_valid()])
        if invalid:
            self.log(
                "{} invalid: {}".format(
                    logging_tools.get_plural("host_type config", len(invalid)),
                    ", ".join(invalid)
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            return False
        else:
            return True

    def refresh(self):
        # refreshes host- and contactgroup definition
        self["contactgroup"].refresh(self)
        self["hostgroup"].refresh(self)

    def has_key(self, key):
        return key in self.__dict

    def keys(self):
        return self.__dict.keys()

    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__process.log("[mc%s] %s" % (
            " %s" % (self.__slave_name) if self.__slave_name else "",
            what), level)

    def get_command_name(self):
        return os.path.join(self.__r_dir_dict["var"], "icinga.cmd")

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
            "var/spool/checkresults"]
        if process_tools.get_sys_bits() == 64:
            dir_names.append("lib64")
        # dir dict for writing on disk
        self.__w_dir_dict = dict([(dir_name, os.path.normpath(os.path.join(self.__main_dir, self.__dir_offset, dir_name))) for dir_name in dir_names])
        # dir dict for referencing
        self.__r_dir_dict = dict([(dir_name, os.path.normpath(os.path.join(self.__main_dir, dir_name))) for dir_name in dir_names])
        for dir_name, full_path in self.__w_dir_dict.iteritems():
            if not os.path.exists(full_path):
                self.log("Creating directory %s" % (full_path))
                os.makedirs(full_path)
            else:
                self.log("already exists : %s" % (full_path))

    def _clear_etc_dir(self):
        if self.master:
            self.log("not clearing %s dir (master)" % (self.__w_dir_dict["etc"]))
        else:
            self.log("clearing %s dir (slave)" % (self.__w_dir_dict["etc"]))
            for dir_e in os.listdir(self.__w_dir_dict["etc"]):
                full_path = "%s/%s" % (self.__w_dir_dict["etc"], dir_e)
                if os.path.isfile(full_path):
                    try:
                        os.unlink(full_path)
                    except:
                        self.log("Cannot delete file %s: %s" % (full_path, process_tools.get_except_info()),
                                 logging_tools.LOG_LEVEL_ERROR)

    def _create_nagvis_base_entries(self):
        if os.path.isdir(global_config["NAGVIS_DIR"]):
            self.log("creating base entries for nagvis (under %s)" % (global_config["NAGVIS_DIR"]))
            #
            nagvis_main_cfg = ConfigParser.RawConfigParser(allow_no_value=True)
            for sect_name, var_list in [
                ("global", [
                    ("audit_log", 1),
                    ("authmodule", "CoreAuthModSQLite"),
                    ("authorisationmodule", "CoreAuthorisationModSQLite"),
                    ("controls_size", 10),
                    ("dateformat", "Y-m-d H:i:s"),
                    ("dialog_ack_sticky", 1),
                    ("dialog_ack_notify", 1),
                    ("dialog_ack_persist", 0),
                    # ("file_group", ""),
                    ("file_mode", "660"),
                    # ("http_proxy", ""),
                    ("http_timeout", 10),
                    ("language_detection", "user,session,browser,config"),
                    ("language", "en_US"),
                    ("logonmodule", "LogonMixed"),
                    ("logonenvvar", "REMOTE_USER"),
                    ("logonenvcreateuser", 1),
                    ("logonenvcreaterole", "Guests"),
                    ("refreshtime", 60),
                    ("sesscookiedomain", "auto-detect"),
                    ("sesscookiepath", "/nagvis"),
                    ("sesscookieduration", "86400"),
                    ("startmodule", "Overview"),
                    ("startaction", "view"),
                    ("startshow", ""),
                    ]),
                ("paths", [
                    ("base", "%s/" % (os.path.normpath(global_config["NAGVIS_DIR"]))),
                    ("htmlbase", global_config["NAGVIS_URL"]),
                    ("htmlcgi", "/icinga/cgi-bin"),
                    ]),
                ("defaults", [
                    ("backend", "live_1"),
                    ("backgroundcolor", "#ffffff"),
                    ("contextmenu", 1),
                    ("contexttemplate", "default"),
                    ("event_on_load", 0),
                    ("event_repeat_interval", 0),
                    ("event_repeat_duration", -1),
                    ("eventbackground", 0),
                    ("eventhighlight", 1),
                    ("eventhighlightduration", 10000),
                    ("eventhighlightinterval", 500),
                    ("eventlog", 0),
                    ("eventloglevel", "info"),
                    ("eventlogevents", 24),
                    ("eventlogheight", 75),
                    ("eventloghidden", 1),
                    ("eventscroll", 1),
                    ("eventsound", 1),
                    ("headermenu", 1),
                    ("headertemplate", "default"),
                    ("headerfade", 1),
                    ("hovermenu", 1),
                    ("hovertemplate", "default"),
                    ("hoverdelay", 0),
                    ("hoverchildsshow", 0),
                    ("hoverchildslimit", 100),
                    ("hoverchildsorder", "asc"),
                    ("hoverchildssort", "s"),
                    ("icons", "std_medium"),
                    ("onlyhardstates", 0),
                    ("recognizeservices", 1),
                    ("showinlists", 1),
                    ("showinmultisite", 1),
                    # ("stylesheet", ""),
                    ("urltarget", "_self"),
                    ("hosturl", "[htmlcgi]/status.cgi?host=[host_name]"),
                    ("hostgroupurl", "[htmlcgi]/status.cgi?hostgroup=[hostgroup_name]"),
                    ("serviceurl", "[htmlcgi]/extinfo.cgi?type=2&host=[host_name]&service=[service_description]"),
                    ("servicegroupurl", "[htmlcgi]/status.cgi?servicegroup=[servicegroup_name]&style=detail"),
                    ("mapurl", "[htmlbase]/index.php?mod=Map&act=view&show=[map_name]"),
                    ("view_template", "default"),
                    ("label_show", 0),
                    ("line_weather_colors", "10:#8c00ff,25:#2020ff,40:#00c0ff,55:#00f000,70:#f0f000,85:#ffc000,100:#ff0000"),
                    ]),
                ("index", [
                    ("backgroundcolor", "#ffffff"),
                    ("cellsperrow", 4),
                    ("headermenu", 1),
                    ("headertemplate", "default"),
                    ("showmaps", 1),
                    ("showgeomap", 0),
                    ("showrotations", 1),
                    ("showmapthumbs", 0),
                    ]),
                ("automap", [
                    ("defaultparams", "&childLayers=2"),
                    ("defaultroot", ""),
                    ("graphvizpath", "/opt/cluster/bin/"),
                    ]),
                ("wui", [
                    ("maplocktime", 5),
                    ("grid_show", 0),
                    ("grid_color", "#D5DCEF"),
                    ("grid_steps", 32),
                    ]),
                ("worker", [
                    ("interval", "10"),
                    ("requestmaxparams", 0),
                    ("requestmaxlength", 1900),
                    ("updateobjectstates", 30),
                    ]),
                ("backend_live_1", [
                    ("backendtype", "mklivestatus"),
                    ("statushost", ""),
                    ("socket", "unix:/opt/icinga/var/live"),
                    ]),
                ("backend_ndomy_1", [
                    ("backendtype", "ndomy"),
                    ("statushost", ""),
                    ("dbhost", "localhost"),
                    ("dbport", 3306),
                    ("dbname", "nagios"),
                    ("dbuser", "root"),
                    ("dbpass", ""),
                    ("dbprefix", "nagios_"),
                    ("dbinstancename", "default"),
                    ("maxtimewithoutupdate", 180),
                    ("htmlcgi", "/nagios/cgi-bin"),
                    ]),
                # ("backend_merlinmy_1", [
                #    ("backendtype", "merlinmy"),
                #    ("dbhost", "localhost"),
                #    ("dbport", 3306),
                #    ("dbname", "merlin"),
                #    ("dbuser", "merlin"),
                #    ("dbpass", "merlin"),
                #    ("maxtimewithoutupdate", 180),
                #    ("htmlcgi", "/nagios/cgi-bin"),
                #    ]),
                # ("rotation_demo", [
                #    ("maps", "demo-germany,demo-ham-racks,demo-load,demo-muc-srv1,demo-geomap,demo-automap"),
                #    ("interval", 15),
                #    ]),
                ("states", [
                    ("down", 10),
                    ("down_ack", 6),
                    ("down_downtime", 6),
                    ("unreachable", 9),
                    ("unreachable_ack", 6),
                    ("unreachable_downtime", 6),
                    ("critical", 8),
                    ("critical_ack", 6),
                    ("critical_downtime", 6),
                    ("warning", 7),
                    ("warning_ack", 5),
                    ("warning_downtime", 5),
                    ("unknown", 4),
                    ("unknown_ack", 3),
                    ("unknown_downtime", 3),
                    ("error", 4),
                    ("error_ack", 3),
                    ("error_downtime", 3),
                    ("up", 2),
                    ("ok", 1),
                    ("unchecked", 0),
                    ("pending", 0),
                    ("unreachable_bgcolor", "#F1811B"),
                    ("unreachable_color", "#F1811B"),
                    # ("unreachable_ack_bgcolor", ""),
                    # ("unreachable_downtime_bgcolor", ""),
                    ("down_bgcolor", "#FF0000"),
                    ("down_color", "#FF0000"),
                    # ("down_ack_bgcolor", ""),
                    # ("down_downtime_bgcolor", ""),
                    ("critical_bgcolor", "#FF0000"),
                    ("critical_color", "#FF0000"),
                    # ("critical_ack_bgcolor", ""),
                    # ("critical_downtime_bgcolor", ""),
                    ("warning_bgcolor", "#FFFF00"),
                    ("warning_color", "#FFFF00"),
                    # ("warning_ack_bgcolor", ""),
                    # ("warning_downtime_bgcolor", ""),
                    ("unknown_bgcolor", "#FFCC66"),
                    ("unknown_color", "#FFCC66"),
                    # ("unknown_ack_bgcolor", ""),
                    # ("unknown_downtime_bgcolor", ""),
                    ("error_bgcolor", "#0000FF"),
                    ("error_color", "#0000FF"),
                    ("up_bgcolor", "#00FF00"),
                    ("up_color", "#00FF00"),
                    ("ok_bgcolor", "#00FF00"),
                    ("ok_color", "#00FF00"),
                    ("unchecked_bgcolor", "#C0C0C0"),
                    ("unchecked_color", "#C0C0C0"),
                    ("pending_bgcolor", "#C0C0C0"),
                    ("pending_color", "#C0C0C0"),
                    ("unreachable_sound", "std_unreachable.mp3"),
                    ("down_sound", "std_down.mp3"),
                    ("critical_sound", "std_critical.mp3"),
                    ("warning_sound", "std_warning.mp3"),
                    # ("unknown_sound", ""),
                    # ("error_sound", ""),
                    # ("up_sound", ""),
                    # ("ok_sound", ""),
                    # ("unchecked_sound", ""),
                    # ("pending_sound", ""),

                ])
            ]:
                nagvis_main_cfg.add_section(sect_name)
                for key, value in var_list:
                    nagvis_main_cfg.set(sect_name, key, unicode(value))
            try:
                nv_target = os.path.join(global_config["NAGVIS_DIR"], "etc", "nagvis.ini.php")
                with open(nv_target, "wb") as nvm_file:
                    nvm_file.write("; <?php return 1; ?>\n")
                    nagvis_main_cfg.write(nvm_file)
            except IOError:
                self.log("error creating %s: %s" % (
                    nv_target,
                    process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            # clear SALT
            config_php = os.path.join(global_config["NAGVIS_DIR"], "share", "server", "core", "defines", "global.php")
            if os.path.exists(config_php):
                lines = file(config_php, "r").read().split("\n")
                new_lines, save = ([], False)
                for cur_line in lines:
                    if cur_line.lower().count("auth_password_salt") and len(cur_line) > 60:
                        # remove salt
                        cur_line = "define('AUTH_PASSWORD_SALT', '');"
                        save = True
                    new_lines.append(cur_line)
                if save:
                    self.log("saving %s" % (config_php))
                    file(config_php, "w").write("\n".join(new_lines))
            else:
                self.log("config.php '%s' does not exist" % (config_php), logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("no nagvis_directory '%s' found" % (global_config["NAGVIS_DIR"]), logging_tools.LOG_LEVEL_ERROR)

    def _create_base_config_entries(self):
        # read sql info
        sql_file = "/etc/sysconfig/cluster/mysql.cf"
        sql_suc, sql_dict = configfile.readconfig(sql_file, 1)
        resource_cfg = base_config("resource", is_host_file=True)
        if os.path.isfile("/opt/%s/libexec/check_dns" % (global_config["MD_TYPE"])):
            resource_cfg["$USER1$"] = "/opt/%s/libexec" % (global_config["MD_TYPE"])
        else:
            resource_cfg["$USER1$"] = "/opt/%s/lib" % (global_config["MD_TYPE"])
        resource_cfg["$USER2$"] = "/opt/cluster/sbin/ccollclientzmq -t %d" % (global_config["CCOLLCLIENT_TIMEOUT"])
        resource_cfg["$USER3$"] = "/opt/cluster/sbin/csnmpclientzmq -t %d" % (global_config["CSNMPCLIENT_TIMEOUT"])
        NDOMOD_NAME, NDO2DB_NAME = ("ndomod",
                                    "ndo2db")
        ndomod_cfg = base_config(
            NDOMOD_NAME,
            belongs_to_ndo=True,
            values=[
                ("instance_name", "clusternagios"),
                ("output_type", "unixsocket"),
                ("output", "%s/ido.sock" % (self.__r_dir_dict["var"])),
                ("tcp_port", 5668),
                ("output_buffer_items", 5000),
                ("buffer_file", "%s/ndomod.tmp" % (self.__r_dir_dict["var"])),
                ("file_rotation_interval", 14400),
                ("file_rotation_timeout", 60),
                ("reconnect_interval", 15),
                ("reconnect_warning_interval", 15),
                ("debug_level", 0),
                ("debug_verbosity", 0),
                ("debug_file", os.path.join(self.__r_dir_dict["var"], "ndomod.debug")),
                ("data_processing_options", global_config["NDO_DATA_PROCESSING_OPTIONS"]),
                ("config_output_options", 2)])
        if not sql_suc:
            self.log("error reading sql_file '%s', no ndo2b_cfg to write" % (sql_file),
                     logging_tools.LOG_LEVEL_ERROR)
            ndo2db_cfg = None
        elif "monitor" not in settings.DATABASES:
            self.log("no 'monitor' database defined in settings.py",
                     logging_tools.LOG_LEVEL_ERROR)
            ndo2db_cfg = None
        else:
            nag_engine = settings.DATABASES["monitor"]["ENGINE"]
            db_server = "pgsql" if nag_engine.count("psycopg") else "mysql"
            if db_server == "mysql":
                sql_dict["PORT"] = 3306
            else:
                sql_dict["PORT"] = 5432
            ndo2db_cfg = base_config(
                NDO2DB_NAME,
                belongs_to_ndo=True,
                values=[
                    ("ndo2db_user", "idnagios"),
                    ("ndo2db_group", "idg"),
                    ("socket_type", "unix"),
                    ("socket_name", "%s/ido.sock" % (self.__r_dir_dict["var"])),
                    ("tcp_port", 5668),
                    ("db_servertype", db_server),
                    ("db_host", sql_dict["MYSQL_HOST"]),
                    ("db_port", sql_dict["PORT"]),
                    ("db_name", sql_dict["NAGIOS_DATABASE"]),
                    ("db_prefix", "%s_" % (global_config["MD_TYPE"])),
                    ("db_user", sql_dict["MYSQL_USER"]),
                    ("db_pass", sql_dict["MYSQL_PASSWD"]),
                    # time limits one week
                    ("max_timedevents_age", 1440),
                    ("max_systemcommands_age", 1440),
                    ("max_servicechecks_age", 1440),
                    ("max_hostchecks_age", 1440),
                    ("max_eventhandlers_age", 1440),
                    ("debug_level", 0),
                    ("debug_verbosity", 1),
                    ("debug_file", "%s/ndo2db.debug" % (self.__r_dir_dict["var"])),
                    ("max_debug_file_size", 1000000)])
        main_values = [
            ("log_file", "{}/{}.log".format(
                self.__r_dir_dict["var"],
                global_config["MD_TYPE"]
            )),
            ("cfg_file", []),
            ("resource_file", "%s/%s.cfg" % (
                self.__r_dir_dict["etc"],
                resource_cfg.get_name())),
            ("%s_user" % (global_config["MD_TYPE"]), "idnagios"),
            ("%s_group" % (global_config["MD_TYPE"]), "idg"),
            ("check_external_commands", 1),
            ("command_check_interval", 1),
            ("command_file", self.get_command_name()),
            ("command_check_interval", "5s"),
            ("lock_file", "%s/%s" % (self.__r_dir_dict["var"], global_config["MD_LOCK_FILE"])),
            ("temp_file", "%s/temp.tmp" % (self.__r_dir_dict["var"])),
            ("log_rotation_method", "d"),
            ("log_archive_path", self.__r_dir_dict["var/archives"]),
            ("use_syslog", 0),
            ("host_inter_check_delay_method", "s"),
            ("service_inter_check_delay_method", "s"),
            ("service_interleave_factor", "s"),
            # ("enable_predictive_service_dependency_checks", 1 if global_config["USE_HOST_DEPENDENCIES"] else 0),
            ("enable_predictive_host_dependency_checks", 1 if global_config["USE_HOST_DEPENDENCIES"] else 0),
            ("translate_passive_host_checks", 1 if global_config["TRANSLATE_PASSIVE_HOST_CHECKS"] else 0),
            ("max_concurrent_checks", global_config["MAX_CONCURRENT_CHECKS"]),
            ("passive_host_checks_are_soft", 1 if global_config["PASSIVE_HOST_CHECKS_ARE_SOFT"] else 0),
            ("service_reaper_frequency", 12),
            ("sleep_time", 1),
            ("retain_state_information", 1 if global_config["RETAIN_SERVICE_STATUS"] else 0),  # if self.master else 0),
            ("state_retention_file", "%s/retention.dat" % (self.__r_dir_dict["var"])),
            ("retention_update_interval", 60),
            ("use_retained_program_state", 1 if global_config["RETAIN_PROGRAM_STATE"] else 0),
            ("use_retained_scheduling_info", 0),
            ("interval_length", 60 if not self.master else 60),
            ("use_aggressive_host_checking", 0),
            ("execute_service_checks", 1),
            ("accept_passive_host_checks", 1),
            ("accept_passive_service_checks", 1),
            ("enable_notifications", 1 if self.master else 0),
            ("enable_event_handlers", 1),
            ("process_performance_data", (1 if global_config["ENABLE_COLLECTD"] else 0) if self.master else 0),
            ("obsess_over_services", 1 if not self.master else 0),
            ("obsess_over_hosts", 1 if not self.master else 0),
            ("check_for_orphaned_services", 0),
            ("check_service_freshness", 1 if global_config["CHECK_SERVICE_FRESHNESS"] else 0),
            ("service_freshness_check_interval", global_config["SERVICE_FRESHNESS_CHECK_INTERVAL"]),
            ("check_host_freshness", 1 if global_config["CHECK_HOST_FRESHNESS"] else 0),
            ("host_freshness_check_interval", global_config["HOST_FRESHNESS_CHECK_INTERVAL"]),
            ("freshness_check_interval", 15),
            ("enable_flap_detection", 1 if global_config["ENABLE_FLAP_DETECTION"] else 0),
            ("low_service_flap_threshold", 25),
            ("high_service_flap_threshold", 50),
            ("low_host_flap_threshold", 25),
            ("high_host_flap_threshold", 50),
            ("date_format", "euro"),
            ("illegal_object_name_chars", r"~!$%^&*|'\"<>?),()"),
            ("illegal_macro_output_chars", r"~$&|'\"<>"),
            ("admin_email", "lang-nevyjel@init.at"),
            ("admin_pager", "????"),
            # ("debug_file"      , os.path.join(self.__r_dir_dict["var"], "icinga.dbg")),
            # ("debug_level"     , -1),
            # ("debug_verbosity" , 2),
            # NDO stuff
        ]
        lib_dir_name = "lib64" if process_tools.get_sys_bits() == 64 else "lib"
        for sub_dir_name in ["device.d"]:
            sub_dir = os.path.join(self.__w_dir_dict["etc"], sub_dir_name)
            if not os.path.isdir(sub_dir):
                os.mkdir(sub_dir)
        for sub_dir_name in ["df_settings", "manual"]:
            sub_dir = os.path.join(self.__w_dir_dict["etc"], sub_dir_name)
            if os.path.isdir(sub_dir):
                shutil.rmtree(sub_dir)
        if self.master:
            main_values.append(
                ("cfg_dir", os.path.join(self.__r_dir_dict["etc"], "manual")),
            )
            if global_config["ENABLE_LIVESTATUS"]:
                main_values.extend([
                    ("*broker_module", "%s/mk-livestatus/livestatus.o %s/live" % (
                        self.__r_dir_dict[lib_dir_name],
                        self.__r_dir_dict["var"]))
                ])
            if global_config["ENABLE_COLLECTD"]:
                # setup perf
                # collectd data:
                main_values.extend(
                    [
                        (
                            "service_perfdata_file",
                            os.path.join(self.__r_dir_dict["var"], "service-perfdata")
                        ),
                        (
                            "host_perfdata_file",
                            os.path.join(self.__r_dir_dict["var"], "host-perfdata")
                        ),
                        (
                            "service_perfdata_file_template",
                            "<rec type='service' uuid='$_HOSTUUID$' time='$TIMET$' host='$HOSTNAME$' sdesc='$SERVICEDESC$' "
                            "perfdata='$SERVICEPERFDATA$' com='$SERVICECHECKCOMMAND$' hs='$HOSTSTATE$' hstype='$HOSTSTATETYPE$' "
                            "ss='$SERVICESTATE$' sstype='$SERVICESTATETYPE$'/>"
                        ),
                        (
                            "host_perfdata_file_template",
                            "<rec type='host' uuid='$_HOSTUUID$' time='$TIMET$' host='$HOSTNAME$' perfdata='$HOSTPERFDATA$' "
                            "com='$HOSTCHECKCOMMAND$' hs='$HOSTSTATE$' hstype='$HOSTSTATETYPE$'/>"
                        ),
                    ]
                )
                # general data:
                main_values.extend(
                    [
                        # ("host_perfdata_command"   , "process-host-perfdata"),
                        # ("service_perfdata_command", "process-service-perfdata"),
                        ("service_perfdata_file_mode", "a"),
                        ("service_perfdata_file_processing_interval", "15"),
                        ("service_perfdata_file_processing_command", "process-service-perfdata-file"),
                        ("host_perfdata_file_mode", "a"),
                        ("host_perfdata_file_processing_interval", "15"),
                        ("host_perfdata_file_processing_command", "process-host-perfdata-file"),
                    ]
                )
            if global_config["ENABLE_NDO"]:
                if os.path.exists(os.path.join(self.__r_dir_dict[lib_dir_name], "idomod.so")):
                    main_values.append(
                        ("*broker_module", "%s/idomod.so config_file=%s/%s.cfg" % (
                            self.__r_dir_dict[lib_dir_name],
                            self.__r_dir_dict["etc"],
                            NDOMOD_NAME)))
                else:
                    main_values.append(
                        (
                            "*broker_module", "%s/idomod.so config_file=%s/%s.cfg" % (
                                self.__r_dir_dict["lib"],
                                self.__r_dir_dict["etc"],
                                NDOMOD_NAME
                            )
                        )
                    )
            main_values.append(
                ("event_broker_options", -1 if global_config["ENABLE_LIVESTATUS"] else global_config["EVENT_BROKER_OPTIONS"])
            )
        else:
            # add global event handlers
            main_values.extend([
                ("cfg_dir", []),
                ("ochp_command", "ochp-command"),
                ("ocsp_command", "ocsp-command"),
                ("stalking_event_handlers_for_hosts", 1),
                ("stalking_event_handlers_for_services", 1),
            ])
        main_values.extend(
            [
                ("object_cache_file", "%s/object.cache" % (self.__r_dir_dict["var"])),
                ("use_large_installation_tweaks", "1"),
                ("enable_environment_macros", "0"),
                ("max_service_check_spread", global_config["MAX_SERVICE_CHECK_SPREAD"]),
                ("max_host_check_spread", global_config["MAX_HOST_CHECK_SPREAD"]),
            ])
        main_cfg = base_config(global_config["MAIN_CONFIG_NAME"],
                               is_host_file=True,
                               values=main_values)
        for log_descr, en in [
            ("notifications", 1),
            ("service_retries", 1),
            ("host_retries", 1),
            ("event_handlers", 1),
            ("initial_states", 1 if global_config["LOG_INITIAL_STATES"] else 0),
            ("external_commands", 1 if global_config["LOG_EXTERNAL_COMMANDS"] else 0),
            ("passive_checks", 1 if global_config["LOG_PASSIVE_CHECKS"] else 0)
        ]:
            main_cfg["log_%s" % (log_descr)] = en
        for to_descr, to in [
            ("service_check", 60),
            ("host_check", 30),
            ("event_handler", 30),
            ("notification", 30),
            ("ocsp", 5),
            ("perfdata", 5)
        ]:
            main_cfg["%s_timeout" % (to_descr)] = to
        for th_descr, th in [
            ("low_service", 5.0),
            ("high_service", 20.0),
            ("low_host", 5.0),
            ("high_host", 20.0)
        ]:
            main_cfg["%s_flap_threshold" % (th_descr)] = th
        _uo = user.objects  # @UndefinedVariable
        admin_list = list(
            [
                cur_u.login for cur_u in _uo.filter(
                    Q(active=True) & Q(group__active=True) & Q(mon_contact__pk__gt=0)
                ) if cur_u.has_perm("backbone.device.all_devices")
            ]
        )
        if admin_list:
            def_user = ",".join(admin_list)
        else:
            def_user = "%sadmin" % (global_config["MD_TYPE"])
        cgi_config = base_config(
            "cgi",
            is_host_file=True,
            values=[
                (
                    "main_config_file", "%s/%s.cfg" % (
                        self.__r_dir_dict["etc"], global_config["MAIN_CONFIG_NAME"]
                    )
                ),
                ("physical_html_path", "%s" % (self.__r_dir_dict["share"])),
                ("url_html_path", "/%s" % (global_config["MD_TYPE"])),
                ("show_context_help", 0),
                ("use_authentication", 1),
                # ("default_user_name"        , def_user),
                ("default_statusmap_layout", 5),
                ("default_statuswrl_layout", 4),
                ("refresh_rate", 60),
                ("lock_author_name", 1),
                ("authorized_for_system_information", def_user),
                ("authorized_for_system_commands", def_user),
                ("authorized_for_configuration_information", def_user),
                ("authorized_for_all_hosts", def_user),
                ("authorized_for_all_host_commands", def_user),
                ("authorized_for_all_services", def_user),
                ("authorized_for_all_service_commands", def_user)] +
            [("tac_show_only_hard_state", 1)] if (global_config["MD_TYPE"] == "icinga" and global_config["MD_RELEASE"] >= 6) else [])
        if sql_suc:
            pass
        else:
            self.log("Error reading SQL-config %s" % (sql_file), logging_tools.LOG_LEVEL_ERROR)
        self[main_cfg.get_name()] = main_cfg
        self[ndomod_cfg.get_name()] = ndomod_cfg
        if ndo2db_cfg:
            self[ndo2db_cfg.get_name()] = ndo2db_cfg
        self[cgi_config.get_name()] = cgi_config
        self[resource_cfg.get_name()] = resource_cfg
        if self.master:
            # wsgi config
            if os.path.isfile("/etc/debian_version"):
                www_user, www_group = ("www-data", "www-data")
            elif os.path.isfile("/etc/redhat-release") or os.path.islink("/etc/redhat-release"):
                www_user, www_group = ("apache", "apache")
            else:
                www_user, www_group = ("wwwrun", "www")
            wsgi_config = base_config(
                "uwsgi",
                is_host_file=True,
                headers=["[uwsgi]"],
                values=[
                    ("chdir", self.__r_dir_dict[""]),
                    ("plugin-dir", "/opt/cluster/%s" % (lib_dir_name)),
                    ("cgi-mode", "true"),
                    ("master", "true"),
                    # set vacuum to false because of problems with uwsgi 1.9
                    ("vacuum", "false"),
                    ("workers", 4),
                    ("harakiri-verbose", 1),
                    ("plugins", "cgi"),
                    ("socket", os.path.join(self.__r_dir_dict["var"], "uwsgi.sock")),
                    ("uid", www_user),
                    ("gid", www_group),
                    ("cgi", self.__r_dir_dict["sbin"]),
                    ("no-default-app", "true"),
                    ("cgi-timeout", 3600),
                    ("pidfile", os.path.join(self.__r_dir_dict["var"], "wsgi.pid")),
                    ("daemonize", os.path.join(self.__r_dir_dict["var"], "wsgi.log")),
                    ("chown-socket", www_user),
                    ("no-site", "true"),
                    # ("route"           , "^/icinga/cgi-bin basicauth:Monitor,init:init"),
                ])
            self[wsgi_config.get_name()] = wsgi_config
        if global_config["ENABLE_NAGVIS"] and self.master:
            self._create_nagvis_base_entries()

    def _create_access_entries(self):
        if self.master:
            self.log("creating http_users.cfg file")
            # create htpasswd
            htp_file = os.path.join(self.__r_dir_dict["etc"], "http_users.cfg")
            file(htp_file, "w").write(
                "\n".join(
                    ["{}:{{SSHA}}{}".format(
                        cur_u.login,
                        cur_u.password_ssha.split(":", 1)[1]
                    ) for cur_u in user.objects.filter(Q(active=True)) if cur_u.password_ssha.count(":")] + [""]  # @UndefinedVariable
                )
            )
            if global_config["ENABLE_NAGVIS"]:
                # modify auth.db
                auth_db = os.path.join(global_config["NAGVIS_DIR"], "etc", "auth.db")
                self.log("modifying authentication info in %s" % (auth_db))
                try:
                    conn = sqlite3.connect(auth_db)
                except:
                    self.log("cannot create connection: %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_CRITICAL)
                else:
                    cur_c = conn.cursor()
                    cur_c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                    # tables
                    all_tables = [value[0] for value in cur_c.fetchall()]
                    self.log(
                        "found {}: {}".format(
                            logging_tools.get_plural("table", len(all_tables)),
                            ", ".join(sorted(all_tables))
                        )
                    )
                    # delete previous users
                    cur_c.execute("DELETE FROM users2roles")
                    cur_c.execute("DELETE FROM users")
                    cur_c.execute("DELETE FROM roles")
                    cur_c.execute("DELETE FROM roles2perms")
                    admin_role_id = cur_c.execute("INSERT INTO roles VALUES(Null, 'admins')").lastrowid
                    perms_dict = dict([("%s.%s.%s" % (
                        cur_perm[1].lower(),
                        cur_perm[2].lower(),
                        cur_perm[3].lower()), cur_perm[0]) for cur_perm in cur_c.execute("SELECT * FROM perms")])
                    # pprint.pprint(perms_dict)
                    cur_c.execute("INSERT INTO roles2perms VALUES(%d, %d)" % (
                        admin_role_id,
                        perms_dict["*.*.*"]))
                    role_dict = dict([(cur_role[1].lower().split()[0], cur_role[0]) for cur_role in cur_c.execute("SELECT * FROM roles")])
                    self.log("role dict: %s" % (", ".join(["%s=%d" % (key, value) for key, value in role_dict.iteritems()])))
                    # get nagivs root points
                    nagvis_rds = device.objects.filter(Q(automap_root_nagvis=True)).select_related("domain_tree_node", "device_group")
                    self.log(
                        "{}: {}".format(
                            logging_tools.get_plural("NagVIS root device", len(nagvis_rds)),
                            ", ".join([unicode(cur_dev) for cur_dev in nagvis_rds])
                        )
                    )
                    devg_lut = {}
                    for cur_dev in nagvis_rds:
                        devg_lut.setdefault(cur_dev.device_group.pk, []).append(cur_dev.full_name)
                    for cur_u in user.objects.filter(Q(active=True) & Q(mon_contact__pk__gt=0)).prefetch_related("allowed_device_groups"):  # @UndefinedVariable
                        # check for admin
                        if cur_u.has_perm("backbone.device.all_devices"):
                            target_role = "admins"
                        else:
                            # create special role
                            target_role = cur_u.login
                            role_dict[target_role] = cur_c.execute("INSERT INTO roles VALUES(Null, '%s')" % (cur_u.login)).lastrowid
                            add_perms = ["auth.logout.*", "overview.view.*", "general.*.*", "user.setoption.*"]
                            perm_names = []
                            for cur_devg in cur_u.allowed_device_groups.values_list("pk", flat=True):
                                for dev_name in devg_lut.get(cur_devg, []):
                                    perm_names.extend(
                                        [
                                            "map.view.{}".format(dev_name),
                                            "automap.view.{}".format(dev_name),
                                        ]
                                    )
                            for perm_name in perm_names:
                                if perm_name not in perms_dict:
                                    try:
                                        perms_dict[perm_name] = cur_c.execute(
                                            "INSERT INTO perms VALUES(Null, '%s', '%s', '%s')" % (
                                                perm_name.split(".")[0].title(),
                                                perm_name.split(".")[1],
                                                perm_name.split(".")[2]
                                            )
                                        ).lastrowid
                                        self.log("permission '%s' has id %d" % (perm_name, perms_dict[perm_name]))
                                    except:
                                        self.log(
                                            "cannot create permission '{}': {}".format(
                                                perm_name,
                                                process_tools.get_except_info()
                                            ),
                                            logging_tools.LOG_LEVEL_ERROR
                                        )
                                add_perms.append(perm_name)
                            # add perms
                            for new_perm in add_perms:
                                if new_perm in perms_dict:
                                    cur_c.execute("INSERT INTO roles2perms VALUES(%d, %d)" % (
                                        role_dict[target_role],
                                        perms_dict[new_perm]))
                            self.log("creating new role '%s' with perms %s" % (
                                target_role,
                                ", ".join(add_perms)
                            ))
                        self.log("creating user '%s' with role %s" % (
                            unicode(cur_u),
                            target_role,
                        ))
                        new_userid = cur_c.execute("INSERT INTO users VALUES(Null, '%s', '%s')" % (
                            cur_u.login,
                            binascii.hexlify(base64.b64decode(cur_u.password.split(":", 1)[1])),
                            )).lastrowid
                        cur_c.execute("INSERT INTO users2roles VALUES(%d, %d)" % (
                            new_userid,
                            role_dict[target_role],
                        ))
                    conn.commit()
                    conn.close()

    def _write_entries(self):
        if not self.__allow_write_entries:
            self.log("writing entries not allowed", logging_tools.LOG_LEVEL_WARN)
            return 0
        cfg_written, empty_cfg_written = ([], [])
        start_time = time.time()
        for key, stuff in self.__dict.iteritems():
            if isinstance(stuff, base_config) or isinstance(stuff, host_type_config) or isinstance(stuff, config_dir):
                if isinstance(stuff, config_dir):
                    cfg_written.extend(stuff.create_content(self.__w_dir_dict["etc"]))
                else:
                    if isinstance(stuff, base_config):
                        act_cfg_name = stuff.get_file_name(self.__w_dir_dict["etc"])
                    else:
                        act_cfg_name = os.path.normpath(os.path.join(
                            self.__w_dir_dict["etc"],
                            "%s.cfg" % (key)))
                    # print "*", key, act_cfg_name
                    stuff.create_content()
                    if stuff.act_content != stuff.old_content:
                        try:
                            codecs.open(act_cfg_name, "w", "utf-8").write(u"\n".join(stuff.act_content + [u""]))
                        except IOError:
                            self.log(
                                "Error writing content of %s to %s: %s" % (
                                    key,
                                    act_cfg_name,
                                    process_tools.get_except_info()),
                                logging_tools.LOG_LEVEL_CRITICAL)
                            stuff.act_content = []
                        else:
                            os.chmod(act_cfg_name, 0644)
                            cfg_written.append(key)
                    elif not stuff.act_content:
                        # crate empty config file
                        empty_cfg_written.append(act_cfg_name)
                        self.log("creating empty file %s" % (act_cfg_name),
                                 logging_tools.LOG_LEVEL_WARN)
                        open(act_cfg_name, "w").write("\n")
                    else:
                        # no change
                        pass
        end_time = time.time()
        if cfg_written:
            if global_config["DEBUG"]:
                self.log(
                    "wrote {} ({}) in {}".format(
                        logging_tools.get_plural("config_file", len(cfg_written)),
                        ", ".join(cfg_written),
                        logging_tools.get_diff_time_str(end_time - start_time)
                    )
                )
            else:
                self.log(
                    "wrote {} in {}".format(
                        logging_tools.get_plural("config_file", len(cfg_written)),
                        logging_tools.get_diff_time_str(end_time - start_time)
                    )
                )
        else:
            self.log("no config files written")
        return len(cfg_written) + len(empty_cfg_written)

    def has_config(self, config_name):
        return config_name in self

    def get_config(self, config_name):
        return self[config_name]

    def add_config(self, config):
        if self.has_config(config.get_name()):
            config.set_previous_config(self.get_config(config.get_name()))
        self[config.get_name()] = config

    def add_config_dir(self, config_dir):
        self[config_dir.get_name()] = config_dir

    def __setitem__(self, key, value):
        self.__dict[key] = value
        new_file_keys = sorted([
            "%s/%s.cfg" % (self.__r_dir_dict["etc"], key) for key, value in self.__dict.iteritems() if
            (not isinstance(value, base_config) or not (value.is_host_file or value.belongs_to_ndo)) and (not isinstance(value, config_dir))
        ])
        old_file_keys = self[global_config["MAIN_CONFIG_NAME"]]["cfg_file"]
        new_dir_keys = sorted(["%s/%s" % (self.__r_dir_dict["etc"], key) for key, value in self.__dict.iteritems() if isinstance(value, config_dir)])
        old_dir_keys = self[global_config["MAIN_CONFIG_NAME"]]["cfg_dir"]
        write_cfg = False
        if old_file_keys != new_file_keys:
            self[global_config["MAIN_CONFIG_NAME"]]["cfg_file"] = new_file_keys
            write_cfg = True
        if old_dir_keys != new_dir_keys:
            self[global_config["MAIN_CONFIG_NAME"]]["cfg_dir"] = new_dir_keys
            write_cfg = True
        if write_cfg:
            self._write_entries()

    def __contains__(self, key):
        return key in self.__dict

    def __getitem__(self, key):
        return self.__dict[key]


class base_config(object):
    def __init__(self, name, **kwargs):
        self.__name = name
        self.__dict, self.__key_list = ({}, [])
        self.is_host_file = kwargs.get("is_host_file", False)
        self.belongs_to_ndo = kwargs.get("belongs_to_ndo", False)
        self.headers = kwargs.get("headers", [])
        for key, value in kwargs.get("values", []):
            self[key] = value
        self.act_content = []

    def get_name(self):
        return self.__name

    def get_file_name(self, etc_dir):
        if self.__name in ["uwsgi"]:
            return "/opt/cluster/etc/uwsgi/icinga.wsgi.ini"
        else:
            return os.path.normpath(os.path.join(etc_dir, "{}.cfg".format(self.__name)))

    def __setitem__(self, key, value):
        if key.startswith("*"):
            key, multiple = (key[1:], True)
        else:
            multiple = False
        if key not in self.__key_list:
            self.__key_list.append(key)
        if multiple:
            self.__dict.setdefault(key, []).append(value)
        else:
            self.__dict[key] = value

    def __getitem__(self, key):
        return self.__dict[key]

    def create_content(self):
        self.old_content = self.act_content
        c_lines = []
        last_key = None
        for key in self.__key_list:
            if last_key:
                if last_key[0] != key[0]:
                    c_lines.append("")
            last_key = key
            value = self.__dict[key]
            if type(value) == list:
                pass
            elif type(value) in [int, long]:
                value = [str(value)]
            else:
                value = [value]
            for act_v in value:
                c_lines.append("%s=%s" % (key, act_v))
        self.act_content = self.headers + c_lines


class mon_config(dict):
    def __init__(self, obj_type, name, **kwargs):
        # dict-like object, uses {key, list} as storage
        self.obj_type = obj_type
        self.name = name
        super(mon_config, self).__init__()
        for _key, _value in kwargs.iteritems():
            self[_key] = _value

    def __setitem__(self, key, value):
        if type(value) == list:
            if key in self:
                super(mon_config, self).__getitem__(key).extend(value)
            else:
                # important: create a new list
                super(mon_config, self).__setitem__(key, [_val for _val in value])
        else:
            if key in self:
                super(mon_config, self).__getitem__(key).append(value)
            else:
                super(mon_config, self).__setitem__(key, [value])

    def __getitem__(self, key):
        if key == "name":
            return self.name
        else:
            return super(mon_config, self).__getitem__(key)


class content_emitter(object):
    def ignore_content(self, in_dict):
        return False

    def _emit_content(self, dest_type, in_dict):
        if self.ignore_content(in_dict):
            return []
        _content = [
            "define {} {{".format(dest_type)
        ] + [
            "  {} {}".format(
                act_key,
                self._build_value_string(act_key, in_dict[act_key])
            ) for act_key in sorted(in_dict.iterkeys())
        ] + [
            "}", ""
        ]
        return _content

    def _build_value_string(self, _key, in_list):
        if in_list:
            # check for unique types
            if len(set([type(_val) for _val in in_list])) != 1:
                raise ValueError("values in list {} for key {} have different types".format(str(in_list), _key))
            else:
                _first_val = in_list[0]
                if type(_first_val) in [int, long]:
                    return ",".join(["{:d}".format(_val) for _val in in_list])
                else:
                    if "" in in_list:
                        raise ValueError("empty string found in list {} for key {}".format(str(in_list), _key))
                    return u",".join([unicode(_val) for _val in in_list])
        else:
            return "-"


class build_cache(object):
    def __init__(self, log_com, cdg, full_build, unreachable_pks=[]):
        self.log_com = log_com
        # build cache to speed up config generation
        # stores various cached objects
        # global luts
        # lookup table for host_check_commands
        self.unreachable_pks = set(unreachable_pks or [])
        s_time = time.time()
        self.mcc_lut = {key: (v0, v1, v2) for key, v0, v1, v2 in mon_check_command.objects.all().values_list("pk", "name", "description", "config__name")}
        # lookup table for config -> mon_check_commands
        self.mcc_lut_2 = {}
        for v_list in mon_check_command.objects.all().values_list("name", "config__name"):
            self.mcc_lut_2.setdefault(v_list[1], []).append(v_list[0])
        # host list, set from caller
        self.host_list = []
        self.dev_templates = None
        self.serv_templates = None
        self.cache_mode = "???"
        self.single_build = False
        self.debug = False
        self.__var_cache = var_cache(cdg, prefill=full_build)
        self.join_char = "_" if global_config["SAFE_NAMES"] else " "
        # device_group user access
        self.dg_user_access = {}
        mon_user_pks = list(user.objects.filter(Q(mon_contact__pk__gt=0)).values_list("pk", flat=True))  # @UndefinedVariable
        for _dg in device_group.objects.all().prefetch_related("user_set"):
            self.dg_user_access[_dg.pk] = list([_user for _user in _dg.user_set.all() if _user.pk in mon_user_pks])
        # all hosts dict
        self.all_hosts_dict = {
            cur_dev.pk: cur_dev for cur_dev in device.objects.filter(
                Q(device_group__enabled=True) & Q(enabled=True)
            ).select_related(
                "device_type",
                "domain_tree_node",
                "device_group"
            ).prefetch_related("mon_trace_set")
        }
        # set reachable flag
        for key, value in self.all_hosts_dict.iteritems():
            value.reachable = value.pk not in self.unreachable_pks
        # traces
        self.__host_traces = {host.pk: list(host.mon_trace_set.all()) for host in self.all_hosts_dict.itervalues()}
        # host / service clusters
        clusters = {}
        for _obj, _name in [(mon_host_cluster, "hc"), (mon_service_cluster, "sc")]:
            _lut = {}
            _query = _obj.objects.all()
            if _name == "sc":
                _query = _query.select_related("mon_check_command")
            for _co in _query:
                _lut[_co.pk] = _co.main_device_id
                _co.devices_list = []
                clusters.setdefault(_name, {}).setdefault(_co.main_device_id, []).append(_co)
            for _entry in _obj.devices.through.objects.all():
                if _name == "hc":
                    _pk = _entry.mon_host_cluster_id
                else:
                    _pk = _entry.mon_service_cluster_id
                _tco = [_co for _co in clusters[_name][_lut[_pk]] if _co.pk == _pk][0]
                _tco.devices_list.append(_entry.device_id)
                # clusters[_name][_entry.]
        self.__clusters = clusters
        # host / service dependencies
        deps = {}
        for _obj, _name in [(mon_host_dependency, "hd"), (mon_service_dependency, "sd")]:
            _lut = {}
            _query = _obj.objects.all().prefetch_related("devices", "dependent_devices")
            if _name == "hd":
                _query = _query.select_related(
                    "mon_host_dependency_templ",
                    "mon_host_dependency_templ__dependency_period",
                )
            else:
                _query = _query.select_related(
                    "mon_service_cluster",
                    "mon_check_command",
                    "dependent_mon_check_command",
                    "mon_service_dependency_templ",
                    "mon_service_dependency_templ__dependency_period",
                )
            for _do in _query:
                # == slaves
                _do.devices_list = []
                # == dependent devices
                _do.master_list = []
                _lut[_do.pk] = []
                for _dd in _do.dependent_devices.all():
                    _lut[_do.pk].append(_dd.pk)
                    deps.setdefault(_name, {}).setdefault(_dd.pk, []).append(_do)
            for _entry in _obj.devices.through.objects.all():
                if _name == "hd":
                    _pk = _entry.mon_host_dependency_id
                else:
                    _pk = _entry.mon_service_dependency_id
                for _devpk in _lut[_pk]:
                    _tdo = [_do for _do in deps[_name][_devpk] if _do.pk == _pk][0]
                    _tdo.devices_list.append(_entry.device_id)
            for _entry in _obj.dependent_devices.through.objects.all():
                if _name == "hd":
                    _pk = _entry.mon_host_dependency_id
                else:
                    _pk = _entry.mon_service_dependency_id
                for _devpk in _lut[_pk]:
                    _tdo = [_do for _do in deps[_name][_devpk] if _do.pk == _pk][0]
                    _tdo.master_list.append(_entry.device_id)
        self.__dependencies = deps
        # init snmp sink
        self.snmp_sink = SNMPSink(log_com)
        e_time = time.time()
        self.log("init build_cache in {}".format(logging_tools.get_diff_time_str(e_time - s_time)))

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.log_com("[bc] {}".format(what), log_level)

    def get_device_group_users(self, dg_pk):
        return [_user.login for _user in self.dg_user_access[dg_pk]]

    def get_host(self, pk):
        return self.all_hosts_dict[pk]

    def get_vars(self, host):
        return self.__var_cache.get_vars(host)

    def get_cluster(self, c_type, main_device_id):
        if main_device_id in self.__clusters.get(c_type, {}):
            return self.__clusters[c_type][main_device_id]
        else:
            return []

    def get_dependencies(self, s_type, main_device_id):
        if main_device_id in self.__dependencies.get(s_type, {}):
            return self.__dependencies[s_type][main_device_id]
        else:
            return []

    def get_mon_trace(self, host, dev_net_idxs, srv_net_idxs):
        _traces = self.__host_traces.get(host.pk, [])
        if _traces:
            _dev_fp, _srv_fp = (
                mon_trace.get_fp(dev_net_idxs),
                mon_trace.get_fp(srv_net_idxs),
            )
            _traces = [_tr for _tr in _traces if _tr.dev_netdevice_fp == _dev_fp and _tr.srv_netdevice_fp == _srv_fp]
            if _traces:
                return _traces[0].get_trace()
            else:
                return []
        else:
            return []

    def set_mon_trace(self, host, dev_net_idxs, srv_net_idxs, traces):
        _dev_fp, _srv_fp = (
            mon_trace.get_fp(dev_net_idxs),
            mon_trace.get_fp(srv_net_idxs),
        )
        # check for update
        _match_traces = [_tr for _tr in self.__host_traces.get(host.pk, []) if _tr.dev_netdevice_fp == _dev_fp and _tr.srv_netdevice_fp == _srv_fp]
        if _match_traces:
            _match_trace = _match_traces[0]
            if json.loads(_match_trace.traces) != traces:
                _match_trace.set_trace(traces)
                try:
                    _match_trace.save()
                except:
                    self.log(
                        "error saving trace {}: {}".format(
                            str(traces),
                            process_tools.get_except_info(),
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
        else:
            _new_trace = mon_trace.create_trace(host, _dev_fp, _srv_fp, json.dumps(traces))
            self.__host_traces.setdefault(host.pk, []).append(_new_trace)

    def set_host_list(self, host_pks):
        self.host_pks = set(list(host_pks))
        for _pk in host_pks:
            self.all_hosts_dict[_pk].valid_ips = {}
            self.all_hosts_dict[_pk].invalid_ips = {}
        # print host_pks


class host_type_config(content_emitter):
    def __init__(self, build_process):
        self.__build_proc = build_process
        self.act_content, self.prev_content = ([], [])

    def clear(self):
        self.__obj_list, self.__dict = ([], {})

    def is_valid(self):
        return True

    def create_content(self):
        # if self.act_content:
        self.old_content = self.act_content
        self.act_content = self.get_content()

    def set_previous_config(self, prev_conf):
        self.act_content = prev_conf.act_content

    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__build_proc.log(what, level)

    def get_content(self):
        act_list = self.get_object_list()
        dest_type = self.get_name()
        content = []
        if act_list:
            for act_le in act_list:
                content.extend(self._emit_content(dest_type, act_le))
            self.log("created {} for {}".format(
                logging_tools.get_plural("entry", len(act_list)),
                dest_type))
        return content

    def get_xml(self):
        res_xml = getattr(E, "{}_list".format(self.get_name()))()
        for act_le in self.get_object_list():
            if self.ignore_content(act_le):
                continue
            new_node = getattr(
                E, self.get_name()
            )(
                **dict(
                    [
                        (
                            key,
                            self._build_value_string(key, act_le[key])
                        ) for key in sorted(act_le.iterkeys())
                    ]
                )
            )
            res_xml.append(new_node)
        return [res_xml]


class all_host_dependencies(host_type_config):
    def __init__(self, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.__obj_list = []

    def get_name(self):
        return "hostdependency"

    def add_host_dependency(self, new_hd):
        self.__obj_list.append(new_hd)

    def get_object_list(self):
        return self.__obj_list


class time_periods(host_type_config):
    def __init__(self, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.__obj_list, self.__dict = ([], {})
        self._add_time_periods_from_db()

    def get_name(self):
        return "timeperiod"

    def _add_time_periods_from_db(self):
        for cur_per in mon_period.objects.all():
            nag_conf = mon_config(
                "timeperiod",
                cur_per.name,
                timeperiod_name=cur_per.name,
                alias=cur_per.alias.strip() if cur_per.alias.strip() else []
            )
            for short_s, long_s in [
                ("mon", "monday"), ("tue", "tuesday"), ("wed", "wednesday"), ("thu", "thursday"),
                ("fri", "friday"), ("sat", "saturday"), ("sun", "sunday")
            ]:
                nag_conf[long_s] = getattr(cur_per, "%s_range" % (short_s))
            self.__dict[cur_per.pk] = nag_conf
            self.__obj_list.append(nag_conf)

    def __getitem__(self, key):
        return self.__dict[key]

    def get_object_list(self):
        return self.__obj_list

    def values(self):
        return self.__dict.values()


class all_service_groups(host_type_config):
    def __init__(self, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.__obj_list, self.__dict = ([], {})
        # dict : which host has which service_group defined
        self.__host_srv_lut = {}
        self.cat_tree = category_tree()
        self._add_servicegroups_from_db()

    def get_name(self):
        return "servicegroup"

    def _add_servicegroups_from_db(self):
        for cat_pk in self.cat_tree.get_sorted_pks():
            cur_cat = self.cat_tree[cat_pk]
            nag_conf = mon_config(
                "servicegroup",
                cur_cat.full_name,
                servicegroup_name=cur_cat.full_name,
                alias="{} group".format(cur_cat.full_name))
            self.__host_srv_lut[cur_cat.full_name] = set()
            self.__dict[cur_cat.pk] = nag_conf
            self.__obj_list.append(nag_conf)

    def clear_host(self, host_name):
        for _key, value in self.__host_srv_lut.iteritems():
            if host_name in value:
                value.remove(host_name)

    def add_host(self, host_name, srv_groups):
        for srv_group in srv_groups:
            self.__host_srv_lut[srv_group].add(host_name)

    def get_object_list(self):
        return [obj for obj in self.__obj_list if self.__host_srv_lut[obj.name]]

    def values(self):
        return self.__dict.values()


class unique_list(object):
    def __init__(self):
        self._list = set()

    def add(self, name):
        if name not in self._list:
            self._list.add(name)
            return name
        else:
            add_idx = 1
            while True:
                _name = "{}_{:d}".format(name, add_idx)
                if _name not in self._list:
                    break
                else:
                    add_idx += 1
            self._list.add(_name)
            return _name


class all_commands(host_type_config):
    def __init__(self, gen_conf, build_proc):
        check_command.gen_conf = gen_conf
        host_type_config.__init__(self, build_proc)
        self.refresh(gen_conf)

    def refresh(self, gen_conf):
        self.__obj_list, self.__dict = ([], {})
        self._add_notify_commands()
        self._add_commands_from_db(gen_conf)

    def ignore_content(self, in_dict):
        # ignore commands with empty command line (== meta commands)
        return ("".join(in_dict.get("command_line", [""]))).strip() == ""

    def get_name(self):
        return "command"

    def _expand_str(self, in_str):
        for key, value in self._str_repl_dict.iteritems():
            in_str = in_str.replace(key, value)
        return in_str

    def _add_notify_commands(self):
        try:
            cdg = device.objects.get(Q(device_group__cluster_device_group=True))
        except device.DoesNotExist:
            cluster_name = "N/A"
        else:
            # cluster_name has to be set, otherwise something went seriously wrong while setting up the cluster
            cluster_name = cluster_location.db_device_variable(cdg, "CLUSTER_NAME", description="name of the cluster").get_value()
        md_vers = global_config["MD_VERSION_STRING"]
        md_type = global_config["MD_TYPE"]
        if os.path.isfile("/opt/cluster/bin/send_mail.py"):
            send_mail_prog = "/opt/cluster/bin/send_mail.py"
        elif os.path.isfile("/usr/local/sbin/send_mail.py"):
            send_mail_prog = "/usr/local/sbin/send_mail.py"
        else:
            send_mail_prog = "/usr/local/bin/send_mail.py"
        send_sms_prog = "/opt/icinga/bin/sendsms"
        from_addr = "{}@{}".format(
            global_config["MD_TYPE"],
            global_config["FROM_ADDR"]
        )

        self._str_repl_dict = {
            "$INIT_MONITOR_INFO$": "{} {}".format(md_type, md_vers),
            "$INIT_CLUSTER_NAME$": "{}".format(cluster_name),
        }

        self.__obj_list.append(
            mon_config(
                "command",
                "dummy-notify",
                command_name="dummy-notify",
                command_line="/usr/bin/true",
            )
        )
        for cur_not in mon_notification.objects.filter(Q(enabled=True)):
            if cur_not.channel == "mail":
                command_line = r"{} -f '{}' -s '{}' -t $CONTACTEMAIL$ -- '{}'".format(
                    send_mail_prog,
                    from_addr,
                    self._expand_str(cur_not.subject),
                    self._expand_str(cur_not.content),
                )
            else:
                command_line = r"{} $CONTACTPAGER$ '{}'".format(
                    send_sms_prog,
                    self._expand_str(cur_not.content),
                )
            nag_conf = mon_config(
                "command",
                cur_not.name,
                command_name=cur_not.name,
                command_line=command_line.replace("\n", "\\n"),
            )
            self.__obj_list.append(nag_conf)

    def _add_commands_from_db(self, gen_conf):
        # set of names of configs which point to a full check_config
        cc_command_names = unique_list()
        # set of all names
        command_names = unique_list()
        for hc_com in host_check_command.objects.all():
            cur_nc = mon_config(
                "command",
                hc_com.name,
                command_name=hc_com.name,
                command_line=hc_com.command_line,
            )
            self.__obj_list.append(cur_nc)
            # simple mon_config, we do not add this to the command dict
            # self.__dict[cur_nc["command_name"]] = cur_nc
            command_names.add(hc_com.name)
        check_coms = list(
            mon_check_command.objects.all().prefetch_related(
                "categories",
                "exclude_devices"
            ).select_related(
                "mon_service_templ",
                "config",
                "event_handler"
            ).order_by("name")
        )
        enable_perfd = global_config["ENABLE_COLLECTD"]
        if enable_perfd and gen_conf.master:
            check_coms += [
                mon_check_command(
                    name="process-service-perfdata-file",
                    command_line="/opt/cluster/sbin/send_collectd_zmq {}/service-perfdata".format(
                        gen_conf.var_dir
                    ),
                    description="Process service performance data",
                ),
                mon_check_command(
                    name="process-host-perfdata-file",
                    command_line="/opt/cluster/sbin/send_collectd_zmq {}/host-perfdata".format(
                        gen_conf.var_dir
                    ),
                    description="Process host performance data",
                ),
            ]
        all_mccs = mon_check_command_special.objects.all()
        check_coms += [
            mon_check_command(
                name=ccs.md_name,
                command_line=ccs.command_line or "/bin/true",
                description=ccs.description,
            ) for ccs in all_mccs
        ]
        check_coms += [
            mon_check_command(
                name="ochp-command",
                command_line="$USER2$ -m DIRECT -s ochp-event \"$HOSTNAME$\" \"$HOSTSTATE$\" \"{}\"".format(
                    "$HOSTOUTPUT$|$HOSTPERFDATA$" if enable_perfd else "$HOSTOUTPUT$"
                ),
                description="OCHP Command"
            ),
            mon_check_command(
                name="ocsp-command",
                command_line="$USER2$ -m DIRECT -s ocsp-event \"$HOSTNAME$\" \"$SERVICEDESC$\" \"$SERVICESTATE$\" \"{}\" ".format(
                    "$SERVICEOUTPUT$|$SERVICEPERFDATA$" if enable_perfd else "$SERVICEOUTPUT$"
                ),
                description="OCSP Command"
            ),
            mon_check_command(
                name="check_service_cluster",
                command_line="/opt/cluster/bin/check_icinga_cluster.py --service -l \"$ARG1$\" -w \"$ARG2$\" -c \"$ARG3$\" -d \"$ARG4$\" -n \"$ARG5$\"",
                description="Check Service Cluster"
            ),
            mon_check_command(
                name="check_host_cluster",
                command_line="/opt/cluster/bin/check_icinga_cluster.py --host -l \"$ARG1$\" -w \"$ARG2$\" -c \"$ARG3$\" -d \"$ARG4$\" -n \"$ARG5$\"",
                description="Check Host Cluster"
            ),
        ]
        safe_names = global_config["SAFE_NAMES"]
        mccs_dict = {mccs.pk: mccs for mccs in mon_check_command_special.objects.all()}
        for ngc in check_coms:
            # pprint.pprint(ngc)
            # build / extract ngc_name
            ngc_name = ngc.name
            _ngc_name = cc_command_names.add(ngc_name)
            if _ngc_name != ngc_name:
                self.log(
                    "rewrite {} to {}".format(
                        ngc_name,
                        _ngc_name
                    ),
                    logging_tools.LOG_LEVEL_WARN
                )
                ngc_name = _ngc_name
            _nag_name = command_names.add(ngc_name)
            if ngc.pk:
                # print ngc.categories.all()
                cats = [cur_cat.full_name for cur_cat in ngc.categories.all()]  # .values_list("full_name", flat=True)
                cat_pks = [cur_cat.pk for cur_cat in ngc.categories.all()]
            else:
                cats = [TOP_MONITORING_CATEGORY]
                cat_pks = []
            if ngc.mon_check_command_special_id:
                com_line = mccs_dict[ngc.mon_check_command_special_id].command_line
            else:
                com_line = ngc.command_line
            cc_s = check_command(
                ngc_name,
                com_line,
                ngc.config.name if ngc.config_id else None,
                ngc.mon_service_templ.name if ngc.mon_service_templ_id else None,
                build_safe_name(ngc.description) if safe_names else ngc.description,
                exclude_devices=ngc.exclude_devices.all() if ngc.pk else [],
                icinga_name=_nag_name,
                mccs_id=ngc.mon_check_command_special_id,
                servicegroup_names=cats,
                servicegroup_pks=cat_pks,
                enable_perfdata=ngc.enable_perfdata,
                is_event_handler=ngc.is_event_handler,
                event_handler=ngc.event_handler,
                event_handler_enabled=ngc.event_handler_enabled,
                check_command_pk=ngc.pk,
                db_entry=ngc,
                volatile=ngc.volatile,
            )
            nag_conf = cc_s.get_mon_config()
            self.__obj_list.append(nag_conf)
            self.__dict[ngc_name] = cc_s  # ag_conf["command_name"]] = cc_s

    def get_object_list(self):
        return self.__obj_list

    def values(self):
        return self.__dict.values()

    def __getitem__(self, key):
        return self.__dict[key]

    def __contains__(self, key):
        return key in self.__dict

    def keys(self):
        return self.__dict.keys()


class all_contacts(host_type_config):
    def __init__(self, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.__obj_list, self.__dict = ([], {})
        self._add_contacts_from_db(gen_conf)

    def get_name(self):
        return "contact"

    def _add_contacts_from_db(self, gen_conf):
        all_nots = mon_notification.objects.all()
        for contact in mon_contact.objects.all().prefetch_related("notifications").select_related("user"):
            full_name = (u"{} {}".format(contact.user.first_name, contact.user.last_name)).strip().replace(" ", "_")
            if not full_name:
                full_name = contact.user.login
            not_h_list = [entry for entry in all_nots if entry.channel == "mail" and entry.not_type == "host" and entry.enabled]
            # not_s_list = list(contact.notifications.filter(Q(channel="mail") & Q(not_type="service") & Q(enabled=True)))
            not_s_list = [entry for entry in all_nots if entry.channel == "mail" and entry.not_type == "service" and entry.enabled]
            not_pks = [_not.pk for _not in contact.notifications.all()]
            if len(contact.user.pager) > 5:
                # check for pager number
                not_h_list.extend([entry for entry in all_nots if entry.channel == "sms" and entry.not_type == "host" and entry.enabled])
                not_s_list.extend([entry for entry in all_nots if entry.channel == "sms" and entry.not_type == "service" and entry.enabled])
            # filter
            not_h_list = [entry for entry in not_h_list if entry.pk in not_pks]
            not_s_list = [entry for entry in not_s_list if entry.pk in not_pks]
            if contact.mon_alias:
                alias = contact.mon_alias
            elif contact.user.comment:
                alias = contact.user.comment
            else:
                alias = full_name
            nag_conf = mon_config(
                "contact",
                full_name,
                contact_name=contact.user.login,
                host_notification_period=gen_conf["timeperiod"][contact.hnperiod_id].name,
                service_notification_period=gen_conf["timeperiod"][contact.snperiod_id].name,
                alias=alias.strip() if alias.strip() else [],
            )
            if not_h_list:
                nag_conf["host_notification_commands"] = [entry.name for entry in not_h_list]
            else:
                nag_conf["host_notification_commands"] = "dummy-notify"
            if not_s_list:
                nag_conf["service_notification_commands"] = [entry.name for entry in not_s_list]
            else:
                nag_conf["service_notification_commands"] = "dummy-notify"
            for targ_opt, pairs in [
                (
                    "host_notification_options", [
                        ("hnrecovery", "r"), ("hndown", "d"), ("hnunreachable", "u"), ("hflapping", "f"), ("hplanned_downtime", "s")
                    ]
                ),
                (
                    "service_notification_options", [
                        ("snrecovery", "r"), ("sncritical", "c"), ("snwarning", "w"), ("snunknown", "u"), ("sflapping", "f"), ("splanned_downtime", "s")
                    ]
                )
            ]:
                act_a = []
                for long_s, short_s in pairs:
                    if getattr(contact, long_s):
                        act_a.append(short_s)
                if not act_a:
                    act_a = ["n"]
                nag_conf[targ_opt] = act_a
            u_mail = contact.user.email or "root@localhost"
            nag_conf["email"] = u_mail
            nag_conf["pager"] = contact.user.pager or "----"
            self.__obj_list.append(nag_conf)
            self.__dict[contact.pk] = nag_conf

    def __getitem__(self, key):
        return self.__dict[key]

    def get_object_list(self):
        return self.__obj_list

    def values(self):
        return self.__dict.values()


class all_contact_groups(host_type_config):
    def __init__(self, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.refresh(gen_conf)

    def refresh(self, gen_conf):
        self.__obj_list, self.__dict = ([], {})
        self._add_contact_groups_from_db(gen_conf)

    def get_name(self):
        return "contactgroup"

    def _add_contact_groups_from_db(self, gen_conf):
        # none group
        self.__dict[0] = mon_config(
            "contactgroup",
            global_config["NONE_CONTACT_GROUP"],
            contactgroup_name=global_config["NONE_CONTACT_GROUP"],
            alias="None group")
        for cg_group in mon_contactgroup.objects.all().prefetch_related("members"):
            nag_conf = mon_config(
                "contactgroup",
                cg_group.name,
                contactgroup_name=cg_group.name,
                alias=cg_group.alias.strip() if cg_group.alias.strip() else [])
            self.__dict[cg_group.pk] = nag_conf
            for member in cg_group.members.all():
                try:
                    nag_conf["members"] = gen_conf["contact"][member.pk]["contact_name"]
                except:
                    pass
        self.__obj_list = self.__dict.values()

    def has_key(self, key):
        return key in self.__dict

    def keys(self):
        return self.__dict.keys()

    def __getitem__(self, key):
        return self.__dict[key]

    def __contains__(self, key):
        return key in self.__dict__

    def get_object_list(self):
        return self.__obj_list

    def values(self):
        return self.__dict.values()


class all_host_groups(host_type_config):
    def __init__(self, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)
        self.refresh(gen_conf)

    def refresh(self, gen_conf):
        self.__obj_list, self.__dict = ([], {})
        self.cat_tree = category_tree()
        self._add_host_groups_from_db(gen_conf)

    def get_name(self):
        return "hostgroup"

    def _add_host_groups_from_db(self, gen_conf):
        if "device.d" in gen_conf:
            host_pks = gen_conf["device.d"].host_pks
            hostg_filter = Q(enabled=True) & Q(device_group__enabled=True) & Q(device_group__pk__in=host_pks)
            host_filter = Q(enabled=True) & Q(device_group__enabled=True) & Q(pk__in=host_pks)
            if host_pks:
                # hostgroups by devicegroups
                # distinct is important here
                for h_group in device_group.objects.filter(hostg_filter).prefetch_related("device_group").distinct():
                    nag_conf = mon_config(
                        "hostgroup",
                        h_group.name,
                        hostgroup_name=h_group.name,
                        alias=h_group.description or h_group.name,
                        members=[])
                    self.__dict[h_group.pk] = nag_conf
                    self.__obj_list.append(nag_conf)
                    nag_conf["members"] = [cur_dev.full_name for cur_dev in h_group.device_group.filter(Q(pk__in=host_pks)).select_related("domain_tree_node")]
                # hostgroups by categories
                for cat_pk in self.cat_tree.get_sorted_pks():
                    cur_cat = self.cat_tree[cat_pk]
                    nag_conf = mon_config(
                        "hostgroup",
                        cur_cat.full_name,
                        hostgroup_name=cur_cat.full_name,
                        alias=cur_cat.comment or cur_cat.full_name,
                        members=[])
                    nag_conf["members"] = [cur_dev.full_name for cur_dev in cur_cat.device_set.filter(host_filter).select_related("domain_tree_node")]
                    if nag_conf["members"]:
                        self.__obj_list.append(nag_conf)
            else:
                self.log("empty SQL-Str for in _add_host_groups_from_db()",
                         logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("no host-dict found in gen_dict",
                     logging_tools.LOG_LEVEL_WARN)

    def __getitem__(self, key):
        return self.__dict[key]

    def get_object_list(self):
        return self.__obj_list

    def values(self):
        return self.__dict.values()


class config_dir(content_emitter):
    def __init__(self, name, gen_conf, build_proc):
        self.name = "%s.d" % (name)
        self.__build_proc = build_proc
        self.host_pks = set()
        self.refresh(gen_conf)
        self.act_content, self.prev_content = ([], [])

    def clear(self):
        self.__dict = {}

    def refresh(self, gen_conf):
        # ???
        self.clear()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__build_proc.log(what, log_level)

    def get_name(self):
        return self.name

    def add_device(self, c_list, host):
        host_conf = c_list[0]
        self.host_pks.add(host.pk)
        self[host_conf.name] = c_list

    def values(self):
        return self.__dict.values()

    def __contains__(self, key):
        return key in self.__dict

    def __getitem__(self, key):
        return self.__dict[key]

    def __setitem__(self, key, value):
        self.__dict[key] = value

    def __delitem__(self, key):
        del self.__dict[key]

    def has_key(self, key):
        return key in self.__dict

    def keys(self):
        return self.__dict.keys()

    def create_content(self, etc_dir):
        cfg_written = []
        # check for missing files, FIXME
        cfg_dir = os.path.join(etc_dir, self.name)
        self.log("creating entries in %s" % (cfg_dir))
        new_entries = set()
        for key in sorted(self.keys()):
            new_entries.add("%s.cfg" % (key))
            cfg_name = os.path.join(cfg_dir, "%s.cfg" % (key))
            # check for changed content, FIXME
            content = self._create_sub_content(key)
            try:
                codecs.open(cfg_name, "w", "utf-8").write(u"\n".join(content + [u""]))
            except IOError:
                self.log(
                    "Error writing content of %s to %s: %s" % (
                        key,
                        cfg_name,
                        process_tools.get_except_info()),
                    logging_tools.LOG_LEVEL_CRITICAL)
            else:
                os.chmod(cfg_name, 0644)
                cfg_written.append(key)
        present_entries = set(os.listdir(cfg_dir))
        del_entries = present_entries - new_entries
        _dbg = global_config["DEBUG"]
        if del_entries:
            self.log(
                "removing {} from {}".format(
                    logging_tools.get_plural("entry", len(del_entries)),
                    cfg_dir,
                ),
                logging_tools.LOG_LEVEL_WARN
            )
            for del_entry in del_entries:
                full_name = os.path.join(cfg_dir, del_entry)
                try:
                    os.unlink(full_name)
                except:
                    self.log(
                        "cannot remove {}: {}".format(
                            full_name,
                            process_tools.get_except_info(),
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                else:
                    if _dbg:
                        self.log("removed {}".format(full_name), logging_tools.LOG_LEVEL_WARN)
        return cfg_written

    def _create_sub_content(self, key):
        content = []
        for entry in self[key]:
            content.extend(self._emit_content(entry.obj_type, entry))
        return content

    def get_xml(self):
        res_dict = {}
        for key, value in self.__dict.iteritems():
            prev_tag = None
            for entry in value:
                if entry.obj_type != prev_tag:
                    if entry.obj_type not in res_dict:
                        res_xml = getattr(E, "%s_list" % (entry.obj_type))()
                        res_dict[entry.obj_type] = res_xml
                    else:
                        res_xml = res_dict[entry.obj_type]
                    prev_tag = entry.obj_type
                res_xml.append(getattr(E, entry.obj_type)(**dict([(key, self._build_value_string(key, entry[key])) for key in sorted(entry.iterkeys())])))
        return list(res_dict.itervalues())


class all_hosts(host_type_config):
    """ only a dummy, now via device.d """
    def __init__(self, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)

    def refresh(self, gen_conf):
        pass

    def get_name(self):
        return "host"

    def get_object_list(self):
        return []


class all_services(host_type_config):
    """ only a dummy, now via device.d """
    def __init__(self, gen_conf, build_proc):
        host_type_config.__init__(self, build_proc)

    def refresh(self, gen_conf):
        pass

    def get_name(self):
        return "service"

    def get_object_list(self):
        return []


class check_command(object):
    def __init__(self, name, com_line, config, template, descr, exclude_devices=None, **kwargs):
        self.__name = name
        self.__nag_name = kwargs.pop("icinga_name", self.__name)
        # print self.__name, self.__nag_name
        self.__com_line = com_line
        self.config = config
        self.mccs_id = kwargs.pop("mccs_id", 0)
        self.template = template
        self.exclude_devices = [cur_dev.pk for cur_dev in exclude_devices] or []
        self.servicegroup_names = kwargs.get("servicegroup_names", [TOP_MONITORING_CATEGORY])
        self.servicegroup_pks = kwargs.get("servicegroup_pks", [])
        self.check_command_pk = kwargs.get("check_command_pk", None)
        self.is_event_handler = kwargs.get("is_event_handler", False)
        self.event_handler = kwargs.get("event_handler", None)
        self.event_handler_enabled = kwargs.get("event_handler_enabled", True)
        self.__descr = descr.replace(",", ".")
        self.enable_perfdata = kwargs.get("enable_perfdata", False)
        self.volatile = kwargs.get("volatile", False)
        self.mon_check_command = None
        if "db_entry" in kwargs:
            if kwargs["db_entry"].pk:
                self.mon_check_command = kwargs["db_entry"]
        self._generate_md_com_line()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        check_command.gen_conf.log("[cc %s] %s" % (self.__name, what), log_level)

    @property
    def command_line(self):
        return self.__com_line

    @property
    def md_command_line(self):
        return self.__md_com_line

    def get_num_args(self):
        return self.__num_args

    def get_default_value(self, arg_name, def_value):
        return self.__default_values.get(arg_name, def_value)

    def _generate_md_com_line(self):
        arg_info, log_lines = parse_commandline(self.command_line)
        # print arg_info, log_lines
        self.__arg_lut = arg_info["arg_lut"]
        self.__arg_list = arg_info["arg_list"]
        self.__num_args = arg_info["num_args"]
        self.__default_values = arg_info["default_values"]
        self.__md_com_line = arg_info["parsed_com_line"]
        if global_config["DEBUG"]:
            for _line in log_lines:
                self.log(_line)

    def correct_argument_list(self, arg_temp, dev_variables):
        out_list = []
        for arg_name in arg_temp.argument_names:
            value = arg_temp[arg_name]
            if arg_name in self.__default_values and not value:
                dv_value = self.__default_values[arg_name]
                if type(dv_value) == tuple:
                    # var_name and default_value
                    var_name = self.__default_values[arg_name][0]
                    if var_name in dev_variables:
                        value = dev_variables[var_name]
                    else:
                        value = self.__default_values[arg_name][1]
                else:
                    # only default_value
                    value = self.__default_values[arg_name]
            if type(value) in [int, long]:
                out_list.append("{:d}".format(value))
            else:
                out_list.append(value)
        return out_list

    def get_mon_config(self):
        return mon_config(
            "command",
            self.__nag_name,
            command_name=self.__nag_name,
            command_line=self.md_command_line
        )

    def __getitem__(self, key):
        if key == "command_name":
            return self.__nag_name
        else:
            raise SyntaxError("illegal call to __getitem__ of check_command (key='{}')".format(key))

    def __setitem__(self, key, value):
        if key == "command_name":
            self.__nag_name = value
        else:
            raise SyntaxError("illegal call to __setitem__ of check_command (key='{}')".format(key))

    def get_config(self):
        return self.config

    def get_template(self, default):
        if self.template:
            return self.template
        else:
            return default

    def get_description(self):
        if self.__descr:
            return self.__descr
        else:
            return self.__name

    @property
    def name(self):
        # returns config name for icinga config
        return self.__nag_name

    @property
    def arg_ll(self):
        """
        returns lut and list
        """
        return (self.__arg_lut, self.__arg_list)

    def __repr__(self):
        return "%s [%s]" % (self.__name, self.command_line)


class device_templates(dict):
    def __init__(self, build_proc):
        dict.__init__(self)
        self.__build_proc = build_proc
        self.__default = None
        for dev_templ in mon_device_templ.objects.all().select_related("host_check_command"):
            self[dev_templ.pk] = dev_templ
            if dev_templ.is_default:
                self.__default = dev_templ
        self.log(
            "Found {} ({})".format(
                logging_tools.get_plural("device_template", len(self.keys())),
                ", ".join([cur_dt.name for cur_dt in self.itervalues()])
            )
        )
        if self.__default:
            self.log(
                "Found default device_template named '%s'" % (self.__default.name)
            )
        else:
            if self.keys():
                self.__default = self.values()[0]
                self.log(
                    "No default device_template found, using '%s'" % (self.__default.name),
                    logging_tools.LOG_LEVEL_WARN
                )
            else:
                self.log(
                    "No device_template founds, skipping configuration....",
                    logging_tools.LOG_LEVEL_ERROR
                )

    def is_valid(self):
        return self.__default and True or False

    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__build_proc.log("[device_templates] %s" % (what), level)

    def __getitem__(self, key):
        act_key = key or self.__default.pk
        if act_key not in self:
            self.log(
                "key {} not known, using default {} ({:d})".format(
                    str(act_key),
                    unicode(self.__default),
                    self.__default.pk,
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            act_key = self.__default.pk
        return super(device_templates, self).__getitem__(act_key)


class service_templates(dict):
    def __init__(self, build_proc):
        dict.__init__(self)
        self.__build_proc = build_proc
        self.__default = 0
        for srv_templ in mon_service_templ.objects.all().prefetch_related(
            "mon_device_templ_set",
            "mon_contactgroup_set"
        ):
            # db_rec["contact_groups"] = set()
            # generate notification options
            not_options = []
            for long_name, short_name in [
                ("nrecovery", "r"), ("ncritical", "c"), ("nwarning", "w"), ("nunknown", "u"), ("nflapping", "f"), ("nplanned_downtime", "s")
            ]:
                if getattr(srv_templ, long_name):
                    not_options.append(short_name)
            if not not_options:
                not_options.append("n")
            srv_templ.notification_options = not_options
            self[srv_templ.pk] = srv_templ
            self[srv_templ.name] = srv_templ
            srv_templ.contact_groups = list(set(srv_templ.mon_contactgroup_set.all().values_list("name", flat=True)))
        if self.keys():
            self.__default = self.keys()[0]
        self.log("Found %s (%s)" % (
            logging_tools.get_plural("device_template", len(self.keys())),
            ", ".join([cur_v.name for cur_v in self.values()])))

    def is_valid(self):
        return True

    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__build_proc.log("[service_templates] %s" % (what), level)

    def __getitem__(self, key):
        act_key = key or self.__default.pk
        if act_key not in self:
            self.log(
                "key {} not known, using default {} ({:d})".format(
                    str(act_key),
                    unicode(self.__default),
                    self.__default.pk,
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            act_key = self.__default.pk
        return super(service_templates, self).__getitem__(act_key)


class SimpleCounter(object):
    def __init__(self):
        self.num_ok = 0
        self.num_warning = 0
        self.num_error = 0

    def error(self, num=1):
        self.num_error += num

    def warning(self, num=1):
        self.num_warning += num

    def ok(self, num=1):
        self.num_ok += num
