# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2008,2011-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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
""" base objects for logcheck-server """

import datetime
import os
import stat
import time

from initat.tools import logging_tools, process_tools, inotify_tools
from ..config import global_config


class LogLine(object):
    DT_FORMAT = "%Y-%m-%dT%H:%M:%S"

    def __init__(self, line, prefix="", offset=0, dev_pk=0):
        self.dev_pk = dev_pk
        num_pipes = line.strip().count("|")
        if num_pipes > 2:
            _parts = line.strip().split("|")
            _priority = int(_parts.pop(0))
            _facility = int(_parts.pop(0))
            _datetime = _parts.pop(0)
            _hostname = _parts.pop(0)
            _tag = _parts.pop(0)
            _rest = _parts[0].strip()
        else:
            _datetime, _rest = line.strip().split(None, 1)
            _priority, _facility = (1, 1)
            _hostname = "unknown"
            _tag = "unknown"
        try:
            _pd = datetime.datetime.strptime(
                _datetime.split("+")[0],
                LogLine.DT_FORMAT,
            )
        except ValueError:
            raise ValueError(
                "cannot parse '{}' from line '{}' via {}".format(
                    _datetime.split("+")[0],
                    line,
                    LogLine.DT_FORMAT,
                )
            )
        # format idx, datetime, parsed_datetime, line
        self.id = "{}{:06d}".format(prefix, offset)
        self.pd = _pd
        self.pd_parsed = (
            _pd.year, _pd.month, _pd.day, _pd.hour, _pd.minute, _pd.second
        )
        self.priority = _priority
        self.facility = _facility
        self.hostname = _hostname
        self.tag = _tag
        self.text = _rest

    def get_xml_format(self, format="flat"):
        # for XML
        # flat format, also support structured (i.E. full XML) format ?
        _dict = self.get_mongo_db_entry()
        _dict.pop("line_datetime")
        return _dict

    def get_mongo_db_entry(self):
        # for mongo insert
        return {
            "line_id": self.id,
            "line_datetime": self.pd,
            "line_datetime_parsed": self.pd_parsed,
            "text": self.text,
            "device_pk": self.dev_pk,
            "priority": self.priority,
            "facility": self.facility,
            "hostname": self.hostname,
            "tag": self.tag,
        }


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
        return list(self.info_dict.keys())

    def feed(self, other):
        for _key in list(self.info_dict.keys()):
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
        return str(self)

    def __str__(self):
        return "Filebatch at {:d} ({:d} [{:d}] lines @{:d})".format(
            self.time,
            self.diff_lines,
            self.tot_lines,
            self.offset,
        )


class FileWriteRater(object):
    MAX_STREAM_TIME = 15 * 60

    def __init__(self):
        # simple format, tuples with (time, diff_lines)
        self.stream = []

    def trim_stream(self, trim_time):
        self.stream = [_entry for _entry in self.stream if abs(_entry[0] - trim_time) < FileWriteRater.MAX_STREAM_TIME]

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

    @staticmethod
    def get_stream_info(in_dict):
        return ", ".join(
            [
                "{:.2f} lines/s [{}]".format(
                    in_dict[_key],
                    logging_tools.get_diff_time_str(_key, int=False),
                ) for _key in sorted(in_dict.keys())
            ]
        )

    def __unicode__(self):
        return FileWriteRater.get_stream_info(self.get_stream_dict())


class FileSize(object):
    # hm, really needed ?
    def __init__(self, in_file):
        self.in_file = in_file
        # offset / diff_lines / tot_lines
        self.slices = [
            FileBatch(0, 0, 0)
        ]

    def feed(self, size, first=False):
        _file = open(self.in_file.f_name, "r")
        _num_slices = len(self.slices)
        _size = self.slices[_num_slices - 1].offset
        _start_line = self.slices[_num_slices - 1].tot_lines
        _file.seek(_size)
        _num = 0
        for _line in _file:
            if not _line.endswith("\n"):
                self.in_file.log("incomplete line, ignoring", logging_tools.LOG_LEVEL_WARN)
                # ignore incomplete lines
                break
            if not first:
                # not first call (find first line of file)
                try:
                    self.in_file.line_to_mongo(_line, _start_line + 1 + _num)
                except ValueError:
                    # ignore
                    self.in_file.log(
                        "Got ValueError: {}".format(
                            process_tools.get_except_info()
                        ),
                        logging_tools.LOG_LEVEL_CRITICAL
                    )
                except:
                    raise
            _size += len(_line)
            _num += 1
            if _size == size:
                break
        # todo: create a new batch only every 10 minute
        new_batch = FileBatch(
            _size,
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
        self.prefix = "{:04d}{:02d}{:02d}".format(
            self.year,
            self.month,
            self.day,
        )
        # record last sizes with timestamps
        self.sizes = FileSize(self)
        self.stat = None
        self.rater = FileWriteRater()
        # read filesize, skip lineparsing when opening for the first time
        self._update(first=True)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.in_root.log("[IF] {}".format(what), log_level)

    def __repr__(self):
        return "InotifyFile for {}".format(self.f_name)

    def line_to_mongo(self, line, line_idx):
        _dev_pk = self.in_root.fw_obj.machine.device.pk
        self.in_root.mach_class.feed_mongo_line(
            LogLine(
                line,
                prefix=self.prefix,
                offset=line_idx,
                dev_pk=_dev_pk
            )
        )

    def _update(self, first=False):
        # invalidate cache
        # self.cache_valid = False
        # if self.stat is not None:
        #    prev_size = self.stat[stat.ST_SIZE]
        #    _handle = open(self.f_name, "r")
        #    # _handle.seek(prev_size)
        #    # print _handle.read()
        self.stat = os.stat(self.f_name)
        # each size tuple
        _batch = self.sizes.feed(self.stat[stat.ST_SIZE], first)
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

    def read_chunks(self, lines, to_read_total, first_log_time):
        _file = open(self.f_name, "r")
        _tot_lines = self.sizes.slices[-1].tot_lines
        lines_to_read = to_read_total - len(lines)
        if first_log_time:
            # calculate skip by iterating over file
            _to_skip_time = _tot_lines
            for _idx, line in enumerate(_file):
                _parsed = LogLine(line).pd
                if _parsed > first_log_time:
                    # read everything starting from now
                    _to_skip_time = _idx
                    break
            _file.seek(0)
        else:
            _to_skip_time = None
        if to_read_total:
            if lines_to_read < _tot_lines:
                _to_skip_size = _tot_lines - lines_to_read
            else:
                _to_skip_size = 0
        else:
            _to_skip_size = None
        # compare _to_skip_time with _to_skip_size
        if _to_skip_size is None:
            _to_skip = _to_skip_time
        elif _to_skip_time is None:
            _to_skip = _to_skip_size
        else:
            _to_skip = min(_to_skip_size, _to_skip_time)
        # print _to_skip_time, _to_skip_size, _to_skip
        _read, _skipped = (0, 0)
        _read_sthg = False
        cur_ls = len(lines)
        for line in _file:
            if _to_skip > _skipped:
                _skipped += 1
            else:
                _read += 1
                _read_sthg = True
                lines.insert(
                    cur_ls,
                    LogLine(line, prefix=self.prefix, offset=_skipped + _read),
                )
        return _read_sthg


class InotifyRoot(object):
    watch_id = 0
    FILES_TO_SCAN = {"log"}

    def __init__(self, mach_class, root_dir, fw_obj):
        InotifyRoot.watch_id += 1
        self.mach_class = mach_class
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

    def get_stream_info(self, in_dict):
        return FileWriteRater.get_stream_info(in_dict)

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
            self.mach_class.inotify_watcher.add_watcher(
                self.watch_name,
                in_dir,
                reg_mask,
                self.process_event,
            )
            self.log("added dir {} (watching: {:d})".format(in_dir, len(list(self._dir_dict.keys()))))
            if recursive:
                if os.path.isdir(in_dir):
                    try:
                        for sub_dir, _dirs, _files in os.walk(str(in_dir)):
                            if sub_dir != in_dir:
                                self.register_dir(sub_dir, recursive=False)
                            _found_files = InotifyRoot.FILES_TO_SCAN & set(_files)
                            if _found_files:
                                [
                                    self.register_file(os.path.join(sub_dir, _file)) for _file in _found_files
                                ]
                    except UnicodeDecodeError:
                        self.log("got a UnicodeDecodeError for dir {}".format(in_dir), logging_tools.LOG_LEVEL_CRITICAL)
                        raise
                else:
                    self.log("dir {} does not exist".format(in_dir), logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("dir {} already in watch_dict".format(in_dir), logging_tools.LOG_LEVEL_ERROR)

    def remove_dir(self, in_path):
        if in_path in self._dir_dict:
            del self._dir_dict[in_path]
            self.mach_class.inotify_watcher.remove_watcher(
                self.watch_name,
                in_path,
            )
            self.log("removed dir {} (watching: {:d})".format(in_path, len(list(self._dir_dict.keys()))))
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
                    (_f_obj.stat[stat.ST_MTIME], _f_obj) for _f_obj in self._file_dict.values()
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
                    logging_tools.get_plural("file", len(list(self._file_dict.keys()))),
                    ", latest: {}".format(_latest.f_name) if _latest else "",
                )
            )

    def check_for_stale_files(self):
        self.log("checking for stale files")
        cur_time = time.time()
        _cur_num = len(self._file_dict)
        _stale = [f_name for f_name, f_obj in self._file_dict.items() if f_obj.is_stale(cur_time)]
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
                    (_f_obj.stat[stat.ST_MTIME], _f_obj) for _f_obj in self._file_dict.values()
                ],
                reverse=True
            )
        ]


class FileWatcher(object):
    def __init__(self, mach_class, machine):
        self.machine = machine
        self.__root_dir = os.path.join(
            global_config["SYSLOG_DIR"],
            format(self.machine.device.full_name),
        )
        self.log("init filewatcher at {}".format(self.__root_dir))
        self.__inotify_root = mach_class.register_root(self.__root_dir, self)

    def get_logs(self, to_read=0, minutes=0):
        lines = []
        if minutes:
            first_time = datetime.datetime.now() - datetime.timedelta(minutes=minutes)
        else:
            first_time = None
        if to_read or first_time:
            _logs = self.__inotify_root.get_logs()
            for _log in _logs:
                sthg_read = _log.read_chunks(lines, to_read, first_time)
                if not sthg_read:
                    break
        return lines

    def get_rates(self):
        return self.__inotify_root.get_latest_stream_dict()

    def get_rate_info(self, in_dict):
        return self.__inotify_root.get_stream_info(in_dict)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.machine.log("[fw] {}".format(what), log_level)
