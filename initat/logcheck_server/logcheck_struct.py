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
import stat
import datetime
import fileinput
import subprocess
import marshal
import time

from initat.cluster.backbone.models import device
from initat.tools import logging_tools, process_tools, inotify_tools
from .config import global_config


class LogRotateResult(object):
    def __init__(self):
        self.info_dict = {
            key: 0 for key in[
                "dirs_found",
                "dirs_proc",
                "dirs_del",
                "files_proc",
                "files_del",
                "files_error",
            ]
        }
        self.compress_list = []
        self.start_time = time.time()

    def stop(self):
        self.end_time = time.time()

    def __setitem__(self, key, value):
        self.info_dict[key] = value

    def __getitem__(self, key):
        return self.info_dict[key]

    def keys(self):
        return self.info_dict.keys()

    def feed(self, other):
        for _key in self.info_dict.keys():
            self[_key] += other[_key]
        self.compress_list.extend(other.compress_list)

    def info_str(self):
        return "finished walk for rotate_logs(), dirs: {} in {} (files: {})".format(
            ", ".join(
                [
                    "{}: {:d}".format(
                        _key.split("_")[1],
                        self[_key]
                    ) for _key in sorted(self.keys()) if _key.startswith("dirs") and self[_key]
                ]
            ) or "no info",
            logging_tools.get_diff_time_str(self.end_time - self.start_time),
            ", ".join(
                [
                    "{}: {:d}".format(
                        _key.split("_")[1],
                        self[_key]
                    ) for _key in sorted(self.keys()) if _key.startswith("files") and self[_key]
                ]
            ) or "no info",
        )


class FileBatch(object):
    def __init__(self, offset, diff, tot):
        self.time = int(time.time())
        self.offset = offset
        self.diff_lines = diff
        self.tot_lines = tot

    def __repr__(self):
        return unicode(self)

    def __unicode__(self):
        return "Filebatch at {:d} ({:d} [{:d}] lines @ {:d})".format(
            self.time,
            self.diff_lines,
            self.tot_lines,
            self.offset,
        )


class FileWiteRater(object):
    MAX_STREAM_TIME = 15 * 60

    def __init__(self):
        # simple format, tuples with (time, diff_lines)
        self.stream = []

    def trim_stream(self, trim_time):
        self.stream = [_entry for _entry in self.stream if abs(_entry[0] - trim_time) < FileWiteRater.MAX_STREAM_TIME]

    def feed(self, fb):
        # fb ... filebatch
        _feed_time = fb.time
        self.trim_stream(_feed_time)
        self.stream.append((_feed_time, fb.diff_lines))

    def get_stream_dict(self):
        cur_time = int(time.time())
        # monitoring times in seconds
        mon_times = [_v * 60 for _v in {1, 5, 15}]
        info_dict = {
            _time: float(
                sum([_entry[1] for _entry in self.stream if abs(_entry[0] - cur_time) <= _time])
            ) / _time for _time in mon_times
        }
        return info_dict

    def __unicode__(self):
        _dict = self.get_stream_dict()
        return ", ".join(
            [
                "{:.2f} lines/sec [{:d}]".format(_dict[_key], _key) for _key in sorted(_dict.iterkeys())
            ]
        )


class FileSize(object):
    # hm, really needed ?
    def __init__(self, in_file):
        self.in_file = in_file
        # offset / diff_lines / tot_lines
        self.slices = [
            FileBatch(0, 0, 0)
        ]

    def feed(self, size):
        _file = file(self.in_file.f_name, "r")
        _num_slices = len(self.slices)
        _size = self.slices[_num_slices - 1].offset
        _file.seek(_size)
        _num = 0
        for _line in _file:
            _size += len(_line)
            _num += 1
            if _size == size:
                break
        # todo: create a new batch only every 10 minute
        new_batch = FileBatch(
            size,
            _num,
            _num + self.slices[_num_slices - 1].tot_lines
        )
        self.slices.append(new_batch)
        return new_batch


class InotifyFile(object):
    # simple cache for os.stat info
    def __init__(self, f_name, in_root):
        self.in_root = in_root
        self.f_name = f_name
        _parts = self.f_name.split(os.sep)
        _year, _month, _day = _parts[5:8]
        self.year = int(_year)
        self.month = int(_month)
        self.day = int(_day)
        self.DT_FORMAT = "%Y-%m-%dT%H:%M:%S"
        self.prefix = "{:04d}{:02d}{:02d}".format(
            self.year,
            self.month,
            self.day,
        )
        # record last sizes with timestamps
        self.sizes = FileSize(self)
        self.stat = None
        self.rater = FileWiteRater()
        # read filesize
        self._update()

    def _update(self):
        # invalidate cache
        # self.cache_valid = False
        # if self.stat is not None:
        #    prev_size = self.stat[stat.ST_SIZE]
        #    _handle = file(self.f_name, "r")
        #    # _handle.seek(prev_size)
        #    # print _handle.read()
        self.stat = os.stat(self.f_name)
        # each size tuple
        _batch = self.sizes.feed(self.stat[stat.ST_SIZE])
        return _batch
        # if len(self.sizes) > self.in_root.linecache_size:
        #    todo: shorten list of batches
        #    self.sizes.remove(0)

    def update(self):
        _new_batch = self._update()
        self.rater.feed(_new_batch)

    def is_stale(self, cur_time):
        return abs(cur_time - self.stat[stat.ST_MTIME]) > self.in_root.track_seconds

    def close(self):
        pass

    def get_line(self, line, idx):
        _datetime, _rest = line.strip().split(None, 1)
        _pd = datetime.datetime.strptime(
            _datetime.split("+")[0],
            self.DT_FORMAT,
        )
        return (
            "{}{:06d}".format(self.prefix, idx),
            (
                _pd.year, _pd.month, _pd.day, _pd.hour, _pd.minute, _pd.second
            ),
            _rest
        )

    def read_chunks(self, lines, lines_to_read):
        _file = open(self.f_name, "r")
        _tot_lines = self.sizes.slices[-1].tot_lines
        if lines_to_read < _tot_lines:
            _to_skip = _tot_lines - lines_to_read
        else:
            _to_skip = 0
        _read, _skipped = (0, 0)
        cur_ls = len(lines)
        for line in _file:
            if _to_skip > _skipped:
                _skipped += 1
            else:
                _read += 1
                lines.insert(
                    cur_ls,
                    self.get_line(line, _skipped + _read),
                )
        return _read


class InotifyRoot(object):
    watch_id = 0
    FILES_TO_SCAN = {"log"}

    def __init__(self, root_dir, fw_obj):
        InotifyRoot.watch_id += 1
        self.track_seconds = 24 * 3600 * global_config["LOGS_TRACKING_DAYS"]
        self.linecache_size = global_config["LINECACHE_ENTRIES_PER_FILE"]
        self.watch_name = "irw_{:04d}".format(InotifyRoot.watch_id)
        self.root_dir = root_dir
        self.fw_obj = fw_obj
        self.log(
            "init IR at {} ({}), tracking names {} for {}".format(
                self.root_dir,
                self.watch_name,
                ", ".join(InotifyRoot.FILES_TO_SCAN),
                logging_tools.get_diff_time_str(self.track_seconds),
            )
        )
        self._dir_dict = {}
        self._file_dict = {}
        self.register_dir(self.root_dir)

    def get_latest_stream_dict(self):
        # return stream dict of latest written file
        _latest = self.latest_log
        if _latest is not None:
            return _latest.rater.get_stream_dict()
        else:
            return {}

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.fw_obj.log("[IR] {}".format(what), log_level)

    def register_dir(self, in_dir, recursive=True):
        if in_dir not in self._dir_dict:
            self._dir_dict[in_dir] = True
            reg_mask = inotify_tools.IN_MODIFY | inotify_tools.IN_CLOSE_WRITE | \
                inotify_tools.IN_DELETE | inotify_tools.IN_DELETE_SELF | inotify_tools.IN_CREATE
            Machine.inotify_watcher.add_watcher(
                self.watch_name,
                in_dir,
                reg_mask,
                self.process_event,
            )
            self.log("added dir {} (watching: {:d})".format(in_dir, len(self._dir_dict.keys())))
            if recursive:
                for sub_dir, _dirs, _files in os.walk(in_dir):
                    if sub_dir != in_dir:
                        self.register_dir(sub_dir, recursive=False)
                    _found_files = InotifyRoot.FILES_TO_SCAN & set(_files)
                    if _found_files:
                        [
                            self.register_file(os.path.join(sub_dir, _file)) for _file in _found_files
                        ]
        else:
            self.log("dir {} already in watch_dict".format(in_dir), logging_tools.LOG_LEVEL_ERROR)

    def remove_dir(self, in_path):
        if in_path in self._dir_dict:
            del self._dir_dict[in_path]
            Machine.inotify_watcher.remove_watcher(
                self.watch_name,
                in_path,
            )
            self.log("removed dir {} (watching: {:d})".format(in_path, len(self._dir_dict.keys())))
        else:
            self.log(
                "trying to remove non-watched dir '{}' from watcher_dict".format(
                    in_path,
                ),
                logging_tools.LOG_LEVEL_ERROR
            )

    def update_file(self, f_name):
        if f_name not in self._file_dict:
            self.register_file(f_name)
        self._file_dict[f_name].update()

    def register_file(self, f_name):
        cur_time = time.time()
        _stat = os.stat(f_name)
        if f_name not in self._file_dict:
            if abs(max(_stat[stat.ST_MTIME], _stat[stat.ST_CTIME]) - cur_time) < self.track_seconds:
                try:
                    self._file_dict[f_name] = InotifyFile(f_name, self)
                    self.log_file_info()
                except:
                    self.log(
                        "unable to add file {}: {}".format(
                            f_name,
                            process_tools.get_except_info(),
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )

    def remove_file(self, f_name):
        if f_name in self._file_dict:
            self._file_dict[f_name].close()
            del self._file_dict[f_name]
            self.log_file_info()
        else:
            self.log("trying to remove non-tracked file {}".format(f_name), logging_tools.LOG_LEVEL_ERROR)

    @property
    def latest_log(self):
        if self._file_dict:
            _latest = sorted(
                [
                    (_f_obj.stat[stat.ST_MTIME], _f_obj) for _f_obj in self._file_dict.itervalues()
                ],
                reverse=True
            )[0][1]
        else:
            _latest = None
        return _latest

    def log_file_info(self):
        _latest = self.latest_log
        if _latest is not None:
            self.log(
                "tracking {}{}".format(
                    logging_tools.get_plural("file", len(self._file_dict.keys())),
                    ", latest: {}".format(_latest.f_name) if _latest else "",
                )
            )

    def check_for_stale_files(self):
        self.log("checking for stale files")
        cur_time = time.time()
        _cur_num = len(self._file_dict)
        _stale = [f_name for f_name, f_obj in self._file_dict.iteritems() if f_obj.is_stale(cur_time)]
        if _stale:
            self.log(
                "{} stale: {}".format(logging_tools.get_plural("file")),
                ", ".join(sorted(_stale))
            )
            for _df in _stale:
                self.remove_file(_df)

    def process_event(self, event):
        if event.dir:
            if event.mask & inotify_tools.IN_DELETE:
                self.remove_dir(os.path.join(event.path, event.name))
            elif event.mask & inotify_tools.IN_CREATE:
                self.register_dir(os.path.join(event.path, event.name))
            else:
                pass
        else:
            if event.name in InotifyRoot.FILES_TO_SCAN:
                _path = os.path.join(event.path, event.name)
                if event.mask & inotify_tools.IN_CREATE:
                    self.register_file(_path)
                    self.check_for_stale_files()
                elif event.mask & inotify_tools.IN_MODIFY:
                    self.update_file(_path)
                elif event.mask & inotify_tools.IN_CLOSE_WRITE:
                    self.update_file(_path)
                if event.mask & inotify_tools.IN_DELETE:
                    self.remove_file(_path)

    def get_logs(self):
        return [
            _v[1] for _v in sorted(
                [
                    (_f_obj.stat[stat.ST_MTIME], _f_obj) for _f_obj in self._file_dict.itervalues()
                ],
                reverse=True
            )
        ]


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
            Machine.in_root_dict[root_dir] = InotifyRoot(root_dir, fw_obj)
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
                lines, rates = dev.filewatcher.get_logs(_to_read)
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
        self.__fw = FileWatcher(self)

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


class FileWatcher(object):
    def __init__(self, machine):
        self.machine = machine
        self.__root_dir = os.path.join(
            global_config["SYSLOG_DIR"],
            format(self.machine.device.name),
        )
        self.log("init filewatcher at {}".format(self.__root_dir))
        self.__inotify_root = Machine.register_root(self.__root_dir, self)

    def get_logs(self, to_read):
        lines = []
        if to_read:
            _logs = self.__inotify_root.get_logs()
            for _log in _logs:
                to_read -= _log.read_chunks(lines, to_read)
                if not to_read:
                    break
        return lines, self.__inotify_root.get_latest_stream_dict()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.machine.log("[fw] {}".format(what), log_level)
