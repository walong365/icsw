#!/usr/bin/python-init -Otu
# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2008,2011-2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of logcheck-server
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
""" logcheck-server (to be run on a syslog_server) """

import os
import shutil
import subprocess
import time

from initat.cluster.backbone.models import device
from initat.host_monitoring import limits
from initat.tools import logging_tools, process_tools, inotify_tools
from .config import global_config
from .objects import LogRotateResult, InotifyRoot, FileWatcher
from .commands import MonCommand, LogRateCommand


class Machine(object):
    @staticmethod
    def g_log(what, log_level=logging_tools.LOG_LEVEL_OK):
        Machine.srv_proc.log("[m] {}".format(what), log_level)

    @staticmethod
    def setup(srv_proc):
        Machine.c_binary = "/opt/cluster/bin/lbzip2"
        Machine.srv_proc = srv_proc
        Machine.g_log("init, compression binary to use: {}".format(Machine.c_binary))
        Machine.devname_dict = {}
        Machine.devpk_dict = {}
        # Inotify root dict
        Machine.in_root_dict = {}
        Machine.inotify_watcher = inotify_tools.InotifyWatcher()
        Machine.mon_command_class = MonCommand
        MonCommand.setup(srv_proc.log, Machine)
        # add commands
        LogRateCommand()

    @staticmethod
    def get_watcher():
        return Machine.inotify_watcher

    @staticmethod
    def inotify_event(*args, **kgwargs):
        try:
            Machine.inotify_watcher.process()
        except:
            Machine.g_log(
                "exception occured in Machine.inotify_event(): {}".format(
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        else:
            pass

    @staticmethod
    def shutdown():
        Machine.g_log("shutting down")
        for dev in Machine.devname_dict.itervalues():
            dev.close()

    @staticmethod
    def register_root(root_dir, fw_obj):
        #
        if root_dir in Machine.in_root_dict:
            Machine.g_log("root_dir '{}' already registered".format(root_dir), logging_tools.LOG_LEVEL_ERROR)
        else:
            Machine.in_root_dict[root_dir] = InotifyRoot(Machine, root_dir, fw_obj)
        return Machine.in_root_dict[root_dir]

    @staticmethod
    def g_rotate_logs():
        Machine.g_log("starting log rotation")
        s_time = time.time()
        g_res = LogRotateResult()
        for dev in Machine.devname_dict.itervalues():
            g_res.feed(dev.rotate_logs())
        Machine.g_log(
            "rotated in {}, {} to compress".format(
                logging_tools.get_diff_time_str(time.time() - s_time),
                logging_tools.get_plural("file", len(g_res.compress_list)),
            )
        )
        g_res.stop()
        Machine.g_log(g_res.info_str())
        if g_res.compress_list and Machine.c_binary:
            start_time = time.time()
            for _c_file in g_res.compress_list:
                _bin = "{} {}".format(Machine.c_binary, _c_file)
                retcode = subprocess.call(_bin, shell=True)
                if retcode:
                    Machine.g_log("'{}' returned {:d}".format(_bin, retcode), logging_tools.LOG_LEVEL_WARN)
            end_time = time.time()
            Machine.g_log(
                "compressed {} in {} (per item: {})".format(
                    logging_tools.get_plural("file", len(g_res.compress_list)),
                    logging_tools.get_diff_time_str(end_time - start_time),
                    logging_tools.get_diff_time_str((end_time - start_time) / len(g_res.compress_list)),
                )
            )

    @staticmethod
    def get_syslog(srv_com):
        # print srv_com.pretty_print()
        for _dev in srv_com.xpath(".//ns:devices/ns:device"):
            _dev.attrib.update(
                {
                    "state": "{:d}".format(logging_tools.LOG_LEVEL_ERROR),
                    "result": "Device not found",
                }
            )
            _pk = int(_dev.attrib["pk"])
            if Machine.has_device(_pk):
                dev = Machine.get_device(_pk)
                _to_read = int(_dev.attrib.get("lines", "0"))
                lines = dev.filewatcher.get_logs(_to_read)
                dev.log(
                    "lines found: {:d} (of {:d})".format(
                        len(lines),
                        _to_read,
                    )
                )
                _dev.attrib.update(
                    {
                        "read": "{:d}".format(len(lines)),
                        # for line version
                        "version": "1",
                    }
                )
                rates = dev.filewatcher.get_rates()
                if rates:
                    _dev.append(
                        srv_com.builder(
                            "rates",
                            *[
                                srv_com.builder(
                                    "rate",
                                    timeframe="{:d}".format(_seconds),
                                    rate="{:.4f}".format(_rate)
                                ) for _seconds, _rate in rates.iteritems()
                            ]
                        )
                    )
                _dev.append(
                    srv_com.builder(
                        "lines",
                        process_tools.compress_struct(lines)
                    )
                )

    @staticmethod
    def db_sync():
        Machine.g_log("start sync")
        s_time = time.time()
        all_devs = device.objects.all().prefetch_related(
            "netdevice_set",
            "netdevice_set__net_ip_set",
            "netdevice_set__net_ip_set__network",
            "netdevice_set__net_ip_set__network__network_type",
        )
        for cur_dev in all_devs:
            if cur_dev.name in Machine.devname_dict:
                cur_mach = Machine.devname_dict[cur_dev.name]
            else:
                cur_mach = Machine(cur_dev)
            cur_mach.add_ips(cur_dev)
        Machine.g_log("synced in {}".format(logging_tools.get_diff_time_str(time.time() - s_time)))

    def __init__(self, cur_dev):
        self.__log_template = logging_tools.get_logger(
            "{}.{}".format(
                global_config["LOG_NAME"],
                cur_dev.full_name.replace(".", r"\.")
            ),
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=Machine.srv_proc.zmq_context,
            init_logger=True,
        )
        self.device = cur_dev
        self.name = cur_dev.name
        self.pk = cur_dev.pk
        Machine.devname_dict[self.name] = self
        Machine.devpk_dict[self.pk] = self
        self.log("Added to dict")
        self.__fw = None
        self.__ip_dict = {}
        # if self.device.name == "a":
        self.__fw = FileWatcher(Machine, self)

    @property
    def filewatcher(self):
        return self.__fw

    @staticmethod
    def has_device(key):
        if type(key) in [int, long]:
            return key in Machine.devpk_dict
        else:
            return key in Machine.devname_dict

    @staticmethod
    def get_device(key):
        if type(key) in [int, long]:
            return Machine.devpk_dict[key]
        else:
            return Machine.devname_dict[key]

    def close(self):
        self.__log_template.close()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(
            what,
            log_level
        )

    def add_ips(self, cur_dev):
        any_changes = False
        for cur_nd in cur_dev.netdevice_set.all():
            for cur_ip in cur_nd.net_ip_set.all():
                if cur_ip.ip not in self.__ip_dict:
                    any_changes = True
                    if cur_ip.domain_tree_node:
                        self.__ip_dict[cur_ip.ip] = (cur_ip.domain_tree_node.node_postfix, cur_ip.network.network_type.identifier)
                    else:
                        self.__ip_dict[cur_ip.ip] = ("", cur_ip.network.network_type.identifier)
        if any_changes:
            self.log_ip_info()
            self.generate_syslog_dirs()

    def log_ip_info(self):
        if self.__ip_dict:
            self.log("IP information:")
            for ip in sorted(self.__ip_dict.keys()):
                nw_postfix, net_type = self.__ip_dict[ip]
                self.log(
                    " IP {:<15s}, postfix {:<5s} (type {:<5s}), full name is {}{}".format(
                        ip,
                        nw_postfix and "'{}'".format(nw_postfix) or "''",
                        net_type == "p" and "{} [*]".format(net_type) or net_type,
                        self.name,
                        nw_postfix,
                    )
                )
        else:
            self.log("No IPs set")

    def generate_syslog_dirs(self):
        link_array = [("d", os.path.join(global_config["SYSLOG_DIR"], self.name))]
        for ip, (nw_postfix, net_type) in self.__ip_dict.iteritems():
            if nw_postfix:
                link_array.append(
                    (
                        "l",
                        os.path.join(
                            global_config["SYSLOG_DIR"],
                            "{}{}".format(self.name, nw_postfix)
                        )
                    )
                )
            if net_type != "l" or (net_type == "l" and self.name == global_config["SERVER_SHORT_NAME"]):
                link_array.append(("l", os.path.join(global_config["SYSLOG_DIR"], ip)))
        self.process_link_array(link_array)

    def process_link_array(self, l_array):
        for pt, ps in l_array:
            if pt == "d":
                if not os.path.isdir(ps):
                    self.log("pla(): Creating directory {}".format(ps))
                    try:
                        os.mkdir(ps)
                    except:
                        self.log(
                            "  ...something went wrong for mkdir(): {}".format(process_tools.get_except_info()),
                            logging_tools.LOG_LEVEL_ERROR
                        )
            elif pt == "l":
                if isinstance(ps, basestring):
                    dest = self.name
                else:
                    ps, dest = ps
                create_link = False
                if not os.path.islink(ps):
                    create_link = True
                else:
                    if os.path.exists(ps):
                        old_dest = os.readlink(ps)
                        if old_dest != dest:
                            try:
                                os.unlink(ps)
                            except OSError:
                                self.log(
                                    "  ...something went wrong for unlink(): {}".format(
                                        process_tools.get_except_info()
                                    ),
                                    logging_tools.LOG_LEVEL_ERROR
                                )
                            else:
                                self.log(
                                    " removed wrong link ({} pointed to {} instead of {})".format(
                                        ps,
                                        old_dest,
                                        dest
                                    )
                                )
                                create_link = True
                    else:
                        pass
                if create_link:
                    if os.path.exists(ps):
                        try:
                            self.log("pla(): Unlink {}".format(ps))
                            os.unlink(ps)
                        except:
                            self.log(
                                "  ...something went wrong for unlink(): {}".format(process_tools.get_except_info()),
                                logging_tools.LOG_LEVEL_ERROR
                            )
                        try:
                            self.log("pla(): rmtree {}".format(ps))
                            shutil.rmtree(ps, 1)
                        except:
                            self.log(
                                "  ...something went wrong for rmtree(): {}".format(process_tools.get_except_info()),
                                logging_tools.LOG_LEVEL_ERROR
                            )
                    try:
                        self.log("pla(): symlink from {} to {}".format(ps, dest))
                        os.symlink(dest, ps)
                    except:
                        self.log(
                            "  ...something went wrong for symlink(): {}".format(process_tools.get_except_info()),
                            logging_tools.LOG_LEVEL_ERROR
                        )

    def rotate_logs(self):
        _res = LogRotateResult()
        start_time = time.time()
        log_start_dir = os.path.join(global_config["SYSLOG_DIR"], self.name)
        if os.path.isdir(log_start_dir):
            lsd_len = len(log_start_dir)
            self.log("starting walk for rotate_logs() in {}".format(log_start_dir))
            # directories processed
            for root_dir, sub_dirs, files in os.walk(log_start_dir):
                _res["dirs_found"] += 1
                if root_dir.startswith(log_start_dir):
                    root_dir_p = [int(entry) for entry in root_dir[lsd_len:].split("/") if entry.isdigit()]
                    if len(root_dir_p) in [1, 2]:
                        # check for deletion of empty month-dirs
                        if not sub_dirs:
                            if len(root_dir_p) == 1:
                                host_info_str = "(dir {:04d})".format(
                                    root_dir_p[0]
                                )
                            else:
                                host_info_str = "(dir {:04d}/{:02d})".format(
                                    root_dir_p[0],
                                    root_dir_p[1]
                                )
                            err_files, ok_files = ([], [])
                            for file_name in files:
                                old_file = os.path.join(root_dir, file_name)
                                try:
                                    os.unlink(old_file)
                                except IOError:
                                    err_files.append(old_file)
                                else:
                                    ok_files.append(old_file)
                            if err_files:
                                self.log(
                                    "had problems deleting {} {}: {}".format(
                                        logging_tools.get_plural("file", len(err_files)),
                                        host_info_str,
                                        ", ".join(err_files)
                                    )
                                )
                                _res["files_error"] += len(err_files)
                            else:
                                # try to delete directory
                                try:
                                    os.rmdir(root_dir)
                                except:
                                    pass
                                else:
                                    _res["dirs_del"] += 1
                            if ok_files:
                                self.log(
                                    "Deleted {} {}: {}".format(
                                        logging_tools.get_plural("file", len(ok_files)),
                                        host_info_str,
                                        ", ".join(ok_files)
                                    )
                                )
                                _res["files_del"] += len(ok_files)
                    elif len(root_dir_p) == 3:
                        dir_time = time.mktime(
                            [
                                root_dir_p[0],
                                root_dir_p[1],
                                root_dir_p[2],
                                0,
                                0,
                                0,
                                0,
                                0,
                                0
                            ]
                        )
                        day_diff = int((start_time - dir_time) / (3600 * 24))
                        host_info_str = "(dir {:04d}/{:02d}/{:02d})".format(
                            root_dir_p[0],
                            root_dir_p[1],
                            root_dir_p[2]
                        )
                        if day_diff > max(1, global_config["KEEP_LOGS_TOTAL"]):
                            err_files, ok_files = ([], [])
                            for file_name in [x for x in files]:
                                old_file = os.path.join(root_dir, file_name)
                                try:
                                    os.unlink(old_file)
                                except IOError:
                                    err_files.append(old_file)
                                else:
                                    ok_files.append(old_file)
                            if err_files:
                                self.log(
                                    "had problems deleting {} {}: {}".format(
                                        logging_tools.get_plural(
                                            "file",
                                            len(err_files)
                                        ),
                                        host_info_str,
                                        ", ".join(err_files)
                                    )
                                )
                                _res["files_error"] += len(err_files)
                            else:
                                # try to delete directory
                                try:
                                    os.rmdir(root_dir)
                                except:
                                    pass
                                else:
                                    _res["dirs_del"] += 1
                            if ok_files:
                                self.log(
                                    "Deleted {} {}: {}".format(
                                        logging_tools.get_plural("file", len(ok_files)),
                                        host_info_str,
                                        ", ".join(ok_files)
                                    )
                                )
                                _res["files_del"] += len(ok_files)
                        elif day_diff > max(1, global_config["KEEP_LOGS_UNCOMPRESSED"]):
                            _res["dirs_proc"] += 1
                            err_files, ok_files = ([], [])
                            old_size, new_size = (0, 0)
                            for file_name in [entry for entry in files if entry.split(".")[-1] not in ["gz", "bz2", "xz"]]:
                                old_file = os.path.join(root_dir, file_name)
                                _res.compress_list.append(old_file)
            _res.stop()
            self.log(_res.info_str())
        else:
            _res.stop()
            self.log("log_start_dir {} not found, no log-rotate ...".format(log_start_dir))
        return _res
