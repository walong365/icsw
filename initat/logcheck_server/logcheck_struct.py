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
import time
import subprocess

from initat.cluster.backbone.models import device
from initat.logcheck_server.config import global_config

from initat.tools import logging_tools, process_tools


class machine(object):
    # def __init__(self, name, idx, ips={}, log_queue=None):
    @staticmethod
    def g_log(what, log_level=logging_tools.LOG_LEVEL_OK):
        machine.srv_proc.log("[m] %s" % (what), log_level)

    @staticmethod
    def setup(srv_proc):
        machine.c_binary = process_tools.find_file(global_config["COMPRESS_BINARY"])
        machine.srv_proc = srv_proc
        machine.g_log("init")
        if machine.c_binary:
            machine.g_log("compression binary to use: {}".format(machine.c_binary))
        else:
            machine.g_log("no compression binary found ({})".format(global_config["COMPRESS_BINARY"]), logging_tools.LOG_LEVEL_ERROR)
        machine.dev_dict = {}

    @staticmethod
    def rotate_logs():
        machine.g_log("starting log rotation")
        s_time = time.time()
        compress_list = []
        for dev in machine.dev_dict.itervalues():
            compress_list.extend(dev._rotate_logs())
        machine.g_log(
            "rotated in {}, {} to compress".format(
                logging_tools.get_diff_time_str(time.time() - s_time),
                logging_tools.get_plural("file", len(compress_list)),
            )
        )
        if compress_list and machine.c_binary:
            start_time = time.time()
            for _c_file in compress_list:
                _bin = "{} {}".format(machine.c_binary, _c_file)
                retcode = subprocess.call(_bin, shell=True)
                if retcode:
                    machine.g_log("'{}' returned {:d}".format(_bin, retcode), logging_tools.LOG_LEVEL_WARN)
            end_time = time.time()
            machine.g_log(
                "compressed {} in {} (per item: {})".format(
                    logging_tools.get_plural("file", len(compress_list)),
                    logging_tools.get_diff_time_str(end_time - start_time),
                    logging_tools.get_diff_time_str((end_time - start_time) / len(compress_list)),
                )
            )

    @staticmethod
    def db_sync():
        machine.g_log("start sync")
        s_time = time.time()
        all_devs = device.objects.all().prefetch_related(
            "netdevice_set",
            "netdevice_set__net_ip_set",
            "netdevice_set__net_ip_set__network",
            "netdevice_set__net_ip_set__network__network_type",
        )
        for cur_dev in all_devs:
            if cur_dev.name in machine.dev_dict:
                cur_mach = machine.dev_dict[cur_dev.name]
            else:
                cur_mach = machine(cur_dev)
            cur_mach.add_ips(cur_dev)
        machine.g_log("synced in {}".format(logging_tools.get_diff_time_str(time.time() - s_time)))

    def __init__(self, cur_dev):
        self.device = cur_dev
        self.name = cur_dev.name
        machine.dev_dict[self.name] = self
        self.log("Added to dict")
        self.__ip_dict = {}

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        machine.srv_proc.log(
            "[{}] {}".format(
                self.name,
                what
            ),
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
                self.log(" IP %15s, postfix %-5s (type %-5s), full name is %s%s" % (
                    ip,
                    nw_postfix and "'%s'" % (nw_postfix) or "''",
                    net_type == "p" and "%s [*]" % (net_type) or net_type,
                    self.name,
                    nw_postfix))
        else:
            self.log("No IPs set")

    def generate_syslog_dirs(self):
        link_array = [("d", "%s/%s" % (global_config["SYSLOG_DIR"], self.name))]
        for ip, (nw_postfix, net_type) in self.__ip_dict.iteritems():
            if nw_postfix:
                link_array.append(("l", "%s/%s%s" % (global_config["SYSLOG_DIR"], self.name, nw_postfix)))
            if net_type != "l" or (net_type == "l" and self.name == global_config["SERVER_SHORT_NAME"]):
                link_array.append(("l", "%s/%s" % (global_config["SYSLOG_DIR"], ip)))
        self.process_link_array(link_array)

    def process_link_array(self, l_array):
        for pt, ps in l_array:
            if pt == "d":
                if not os.path.isdir(ps):
                    self.log("pla(): Creating directory %s" % (ps))
                    try:
                        os.mkdir(ps)
                    except:
                        self.log("  ...something went wrong for mkdir(): %s" % (process_tools.get_except_info()),
                                 logging_tools.LOG_LEVEL_ERROR)
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
                                self.log(" removed wrong link (%s pointed to %s instead of %s)" % (ps, old_dest, dest))
                                create_link = True
                    else:
                        pass
                if create_link:
                    if os.path.exists(ps):
                        try:
                            self.log("pla(): Unlink %s" % (ps))
                            os.unlink(ps)
                        except:
                            self.log("  ...something went wrong for unlink(): %s" % (process_tools.get_except_info()),
                                     logging_tools.LOG_LEVEL_ERROR)
                        try:
                            self.log("pla(): rmtree %s" % (ps))
                            shutil.rmtree(ps, 1)
                        except:
                            self.log("  ...something went wrong for rmtree(): %s" % (process_tools.get_except_info()),
                                     logging_tools.LOG_LEVEL_ERROR)
                    try:
                        self.log("pla(): symlink from %s to %s" % (ps, dest))
                        os.symlink(dest, ps)
                    except:
                        self.log("  ...something went wrong for symlink(): %s" % (process_tools.get_except_info()),
                                 logging_tools.LOG_LEVEL_ERROR)

    def _rotate_logs(self):
        compress_list = []
        dirs_found, dirs_proc, files_proc, files_error, files_del, dirs_del = (0, 0, 0, 0, 0, 0)
        start_time = time.time()
        log_start_dir = os.path.join(global_config["SYSLOG_DIR"], self.name)
        if os.path.isdir(log_start_dir):
            lsd_len = len(log_start_dir)
            self.log("starting walk for rotate_logs() in {}".format(log_start_dir))
            # directories processeds
            start_time = time.time()
            for root_dir, sub_dirs, files in os.walk(log_start_dir):
                dirs_found += 1
                if root_dir.startswith(log_start_dir):
                    root_dir_p = [int(entry) for entry in root_dir[lsd_len:].split("/") if entry.isdigit()]
                    if len(root_dir_p) in [1, 2]:
                        # check for deletion of empty month-dirs
                        if not sub_dirs:
                            if len(root_dir_p) == 1:
                                host_info_str = "(dir %04d)" % (
                                    root_dir_p[0]
                                )
                            else:
                                host_info_str = "(dir %04d/%02d)" % (
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
                                files_error += len(err_files)
                            else:
                                # try to delete directory
                                try:
                                    os.rmdir(root_dir)
                                except:
                                    pass
                                else:
                                    dirs_del += 1
                            if ok_files:
                                self.log(
                                    "Deleted {} {}: {}".format(
                                        logging_tools.get_plural("file", len(ok_files)),
                                        host_info_str,
                                        ", ".join(ok_files)
                                    )
                                )
                                files_del += len(ok_files)
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
                        host_info_str = "(dir %04d/%02d/%02d)" % (
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
                                files_error += len(err_files)
                            else:
                                # try to delete directory
                                try:
                                    os.rmdir(root_dir)
                                except:
                                    pass
                                else:
                                    dirs_del += 1
                            if ok_files:
                                self.log(
                                    "Deleted {} {}: {}".format(
                                        logging_tools.get_plural("file", len(ok_files)),
                                        host_info_str,
                                        ", ".join(ok_files)
                                    )
                                )
                                files_del += len(ok_files)
                        elif day_diff > max(1, global_config["KEEP_LOGS_UNCOMPRESSED"]):
                            dirs_proc += 1
                            err_files, ok_files = ([], [])
                            old_size, new_size = (0, 0)
                            for file_name in [entry for entry in files if entry.split(".")[-1] not in ["gz", "bz2", "xz"]]:
                                old_file = os.path.join(root_dir, file_name)
                                compress_list.append(old_file)
            _info_dict = {
                "dirs_found": dirs_found,
                "dirs_proc": dirs_proc,
                "dirs_del": dirs_del,
                "files_proc": files_proc,
                "files_del": files_del,
                "files_error": files_error,
            }
            self.log(
                "finished walk for rotate_logs(), dirs: {} in {:.2f} seconds (files: {})".format(
                    ", ".join(
                        [
                            "{}: {:d}".format(
                                _key.split("_")[1],
                                _info_dict[_key]
                            ) for _key in sorted(_info_dict.keys()) if _key.startswith("dirs") and _info_dict[_key]
                        ]
                    ) or "no info",
                    time.time() - start_time,
                    ", ".join(
                        [
                            "{}: {:d}".format(
                                _key.split("_")[1],
                                _info_dict[_key]
                            ) for _key in sorted(_info_dict.keys()) if _key.startswith("files") and _info_dict[_key]
                        ]
                    ) or "no info",
                )
            )
        else:
            self.log("log_start_dir {} not found, no log-rotate ...".format(log_start_dir))
        return compress_list
