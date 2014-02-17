#!/usr/bin/python-init -Otu
# -*- coding: utf-8 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2011,2012,2013 Andreas Lang-Nevyjel
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

from initat.cluster.backbone.models import device
from initat.logcheck_server.config import global_config
import logging_tools
import os
import process_tools
import shutil
import time

SCAN_TEXT_PREFIX = ".scan"

class machine(object):
    # def __init__(self, name, idx, ips={}, log_queue=None):
    @staticmethod
    def g_log(what, log_level=logging_tools.LOG_LEVEL_OK):
        machine.srv_proc.log("[m] %s" % (what), log_level)
    @staticmethod
    def setup(srv_proc):
        machine.srv_proc = srv_proc
        machine.g_log("init")
        machine.dev_dict = {}
    @staticmethod
    def rotate_logs():
        machine.g_log("starting log rotation")
        s_time = time.time()
        ext_coms = []
        for dev in machine.dev_dict.itervalues():
            ext_coms.extend(dev._rotate_logs())
        machine.g_log("rotatet in %s, %s" % (
            logging_tools.get_diff_time_str(time.time() - s_time),
            logging_tools.get_plural("external command", len(ext_coms))))
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
        machine.g_log("synced in %s" % (logging_tools.get_diff_time_str(time.time() - s_time)))
    def __init__(self, cur_dev):
        self.device = cur_dev
        self.name = cur_dev.name
        machine.dev_dict[self.name] = self
        self.log("Added to dict")
        self.__ip_dict = {}
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        machine.srv_proc.log("[%s] %s" % (self.name,
                                          what), log_level)
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
                if type(ps) in [str, unicode]:
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
                                self.log("  ...something went wrong for unlink(): %s" % (
                                    process_tools.get_except_info()),
                                         logging_tools.LOG_LEVEL_ERROR)
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
        ext_coms = []
        dirs_found, dirs_proc, files_proc, files_error, files_del, dirs_del = (0, 0, 0, 0, 0, 0)
        start_time = time.time()
        log_start_dir = os.path.join(global_config["SYSLOG_DIR"], self.name)
        if os.path.isdir(log_start_dir):
            lsd_len = len(log_start_dir)
            self.log("starting walk for rotate_logs() in %s" % (log_start_dir))
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
                                host_info_str = "(dir %04d)" % (root_dir_p[0])
                            else:
                                host_info_str = "(dir %04d/%02d)" % (root_dir_p[0],
                                                                     root_dir_p[1])
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
                                self.log("Had problems deleting %s %s: %s" % (
                                    logging_tools.get_plural("file", len(err_files)),
                                    host_info_str,
                                    ", ".join(err_files)))
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
                                self.log("Deleted %s %s: %s" % (
                                    logging_tools.get_plural("file", len(ok_files)),
                                    host_info_str,
                                    ", ".join(ok_files)))
                                files_del += len(ok_files)
                    elif len(root_dir_p) == 3:
                        dir_time = time.mktime([
                            root_dir_p[0],
                            root_dir_p[1],
                            root_dir_p[2],
                            0,
                            0,
                            0,
                            0,
                            0,
                            0])
                        day_diff = int((start_time - dir_time) / (3600 * 24))
                        host_info_str = "(dir %04d/%02d/%02d)" % (
                            root_dir_p[0],
                            root_dir_p[1],
                            root_dir_p[2])
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
                                self.log("Had problems deleting %s %s: %s" % (
                                    logging_tools.get_plural(
                                        "file",
                                        len(err_files)),
                                    host_info_str,
                                    ", ".join(err_files)))
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
                                self.log("Deleted %s %s: %s" % (
                                    logging_tools.get_plural("file", len(ok_files)),
                                    host_info_str,
                                    ", ".join(ok_files)))
                                files_del += len(ok_files)
                        elif day_diff > max(1, global_config["KEEP_LOGS_UNCOMPRESSED"]):
                            dirs_proc += 1
                            err_files, ok_files = ([], [])
                            old_size, new_size = (0, 0)
                            for file_name in [entry for entry in files if not entry.endswith(".gz") and not entry.startswith(SCAN_TEXT_PREFIX)]:
                                old_file = os.path.join(root_dir, file_name)
                                new_file = os.path.join(root_dir, "%s.gz" % (file_name))
                                ext_coms.append("compress %s %s")
                                # try:
                                    # old_f_size = os.stat(old_file)[stat.ST_SIZE]
                                    # new_fh = gzip.open(new_file, "wb", 4)
                                    # new_fh.write(file(old_file, "r").read())
                                    # new_fh.close()
                                    # new_f_size = os.stat(new_file)[stat.ST_SIZE]
                                # except:
                                    # err_files.append(file_name)
                                # else:
                                    # old_size += old_f_size
                                    # new_size += new_f_size
                                    # ok_files.append(file_name)
                                    # os.unlink(old_file)
                            # if err_files:
                                # self.log("Had problems compressing %s %s: %s" % (logging_tools.get_plural("file", len(err_files)), host_info_str, ", ".join(err_files)))
                                # files_error += len(err_files)
                            # if ok_files:
                                # self.log("Compressed %s %s: %s" % (logging_tools.get_plural("file", len(ok_files)), host_info_str, ", ".join(ok_files)))
                                # files_proc += len(ok_files)
                            # if err_files or ok_files:
                                # self.log("Stats for directory %s: Saved %s (%.2f %%, new size: %s, orig size: %s)" % (root_dir,
                                                                                                                      # logging_tools.get_size_str(old_size - new_size),
                                                                                                                      # 100. * (float(old_size - new_size) / float(max(1, old_size))),
                                                                                                                      # logging_tools.get_size_str(new_size),
                                                                                                                      # logging_tools.get_size_str(old_size)))
            self.log("Found %s, checked %s in %.2f seconds (%s ok, %s error)" % (
                logging_tools.get_plural("directory", dirs_found),
                logging_tools.get_plural("directory", dirs_proc),
                time.time() - start_time,
                logging_tools.get_plural("file", files_proc),
                logging_tools.get_plural("file", files_error)))
            self.log("finished walk for rotate_logs(), found %s, checked %s, deleted %s in %.2f seconds (%s ok, deleted %s, %s error)" % (
                logging_tools.get_plural("directory", dirs_found),
                logging_tools.get_plural("directory", dirs_proc),
                logging_tools.get_plural("directory", dirs_del),
                time.time() - start_time,
                logging_tools.get_plural("file", files_proc),
                logging_tools.get_plural("file", files_del),
                logging_tools.get_plural("file", files_error)))
        else:
            self.log("log_start_dir %s not found, no log-rotate ..." % (log_start_dir))
        return ext_coms

