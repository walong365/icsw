# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2014 Andreas Lang-Nevyjel
#
# this file is part of python-modules-base
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
""" logging tools """

import bz2
import datetime
import gzip
import inspect
import logging
import logging.handlers
import os
import pickle
import pprint
import re
import stat
import sys
import threading
import time
import traceback

if sys.platform in ["linux2", "linux3", "linux"]:
    import syslog

if sys.version_info[0] == 3:
    unicode = str
    long = int

try:
    import zmq
except ImportError:
    zmq = None

LOG_LEVEL_OK = 20
LOG_LEVEL_WARN = 30
LOG_LEVEL_ERROR = 40
LOG_LEVEL_CRITICAL = 50

# add the levels to the logging dict
logging.addLevelName(LOG_LEVEL_OK      , "ok")
logging.addLevelName(LOG_LEVEL_WARN    , "warn")
logging.addLevelName(LOG_LEVEL_ERROR   , "err")
logging.addLevelName(LOG_LEVEL_CRITICAL, "crit")

# default unified name
UNIFIED_NAME = "unified"

def rewrite_log_destination(log_dest):
    if log_dest.startswith("uds:"):
        log_dest = log_dest.replace("uds:", "ipc://")
    return log_dest

def map_old_to_new_level(in_level):
    return {
        0  : LOG_LEVEL_OK,
        5  : LOG_LEVEL_WARN,
        10 : LOG_LEVEL_ERROR,
        20 : LOG_LEVEL_CRITICAL,
        }.get(in_level, in_level)

def map_log_level_to_log_status(log_lev):
    return {
        LOG_LEVEL_OK       : "i",
        LOG_LEVEL_WARN     : "w",
        LOG_LEVEL_ERROR    : "e",
        LOG_LEVEL_CRITICAL : "c",
        }.get(log_lev, "c")

def get_relative_dt(dt_struct):
    act_time = datetime.datetime.now()
    diff_days = (datetime.date(act_time.year, act_time.month, act_time.day) -
                 datetime.date(dt_struct.year, dt_struct.month, dt_struct.day)).days
    if diff_days < 2:
        if diff_days == 1:
            return dt_struct.strftime("yesterday %H:%M:%S")
        elif diff_days == 0:
            return dt_struct.strftime("today %H:%M:%S")
        else:
            return dt_struct.strftime("%%a, %d days ago %%H:%%M:%%S" % (diff_days))
    else:
        return dt_struct.strftime("%a, %d. %b %Y %H:%M:%S")

def get_plural(in_str, num, show_int=1, fstr_len=0, **kwargs):
    if type(num) in [list, set]:
        r_num = len(num)
    else:
        r_num = num
    end_idx = len(in_str)
    if r_num != 1:
        if in_str and in_str[-1].lower() in ["s", "x", "h"]:
            p_str = "es"
        elif in_str and in_str[-1].lower() in ["y"]:
            if len(in_str) >= 2 and in_str[-2].lower() in ["a", "e", "i", "o", "u"]:
                p_str = "s"
            else:
                p_str = "ies"
                end_idx = -1
        else:
            p_str = "s"
    else:
        p_str = ""
    if fstr_len > 0:
        f_str = "%%%dd " % (fstr_len)
    elif fstr_len < 0:
        f_str = "%%0%dd " % (abs(fstr_len))
    else:
        f_str = "%d "
    return "%s%s%s" % ((show_int and f_str % (r_num)) or "",
                       in_str[0 : end_idx],
                       p_str)

def get_size_str(in_s, long_version=False, divider=1024, strip_spaces=False):
    if type(in_s) in [str, unicode]:
        _len_in_s = len(in_s)
    else:
        _len_in_s = in_s
    b_str = long_version and "Byte" or "B"
    pf_f, pf_str = (["k", "M", "G", "T", "P", "E"], "")
    while in_s > divider:
        in_s = in_s / float(divider)
        pf_str = pf_f.pop(0)
    ret_str = "{} {}{}".format(
        pf_str and "{:6.2f}".format(float(in_s)) or "{:4d}".format(int(in_s)),
        pf_str,
        b_str)
    if strip_spaces:
        ret_str = " ".join(ret_str.split())
    return ret_str

def interpret_size_str(in_str, **kwargs):
    size_re = re.compile("^(?P<value>\d+(\.\d+)*)\s*(?P<pfix>.*?)b*(yte)*s*$", re.IGNORECASE)
    size_m = size_re.match(in_str)
    if size_m:
        value = float(size_m.group("value"))
        pfix = size_m.group("pfix").lower()
        value = int(value * {
            "m"  : 1024 * 1024,
            "mi" : 1000 * 1000,
            "g"  : 1024 * 1024 * 1024,
            "gi" : 1000 * 1000 * 1000,
            "t"  : 1024 * 1024 * 1024 * 1024,
            "ti" : 1000 * 1000 * 1000 * 1000,
            }.get(pfix, 1))
        return value
    else:
        return 0

def get_diff_time_str(diff_secs):
    if type(diff_secs) == datetime.timedelta:
        diff_secs = diff_secs.total_seconds()
    abs_diffs = abs(diff_secs)
    is_int = type(abs_diffs) in [int, long]
    if abs_diffs < 0.1:
        diff_str = "%.2f mseconds" % (abs_diffs * 1000)
    else:
        abs_mins, abs_hours = (0, 0)
        if abs_diffs > 60:
            abs_mins = int(abs_diffs / 60)
            abs_secs = abs_diffs - 60 * abs_mins
            if abs_mins > 60:
                abs_hours = int(abs_mins / 60)
                abs_mins -= 60 * abs_hours
            if abs_hours:
                if abs_hours > 24:
                    abs_days = int(abs_hours / 24)
                    abs_hours -= 24 * abs_days
                    if abs_days > 365:
                        abs_years = int(abs_days / 365)
                        abs_days -= 365 * abs_years
                        diff_str = "%dy %3dd %02d:%02d:%02d" % (abs_years, abs_days, abs_hours, abs_mins, abs_secs)
                    else:
                        diff_str = "%dd %02d:%02d:%02d" % (abs_days, abs_hours, abs_mins, abs_secs)
                else:
                    diff_str = "%d:%02d:%02d" % (abs_hours, abs_mins, abs_secs)
            else:
                diff_str = "%d:%02d" % (abs_mins, abs_secs)
        else:
            diff_str = "%s seconds" % ("%d" if is_int else "%.2f") % (abs_diffs)
    if diff_secs < 0:
        diff_str = "%s [NEGATIVE TIME]" % (diff_str)
    return diff_str

def get_time_str(secs):
    parts, left = ([], secs)
    for div in [3600 * 24, 3600, 60]:
        parts.append(int(left / div))
        left -= div * parts[-1]
    parts.append(left)
    days = parts.pop(0)
    out_f = []
    if days:
        out_f.append(get_plural("day", days))
    hms_f, any_written = ([], False)
    for hms in parts:
        if hms:
            if any_written:
                hms_f.append("%02d" % (hms))
            else:
                hms_f.append("%d" % (hms))
            any_written = True
        else:
            if any_written:
                hms_f.append("%02d" % (hms))
    out_f.append(":".join(hms_f))
    return " ".join(out_f)

class twisted_log_observer(object):
    def __init__(self, name, destination, **kwargs):
        kwargs.update({"init_logger" : True})
        self.__logger = get_logger(name,
                                   destination,
                                   **kwargs)
        self.__last_cinfo = 0.0
    def __call__(self, in_dict):
        for line in in_dict["message"]:
            self.__logger.log(in_dict.get("log_level", LOG_LEVEL_OK), line)
        if in_dict["isError"]:
            if in_dict.get("why", None):
                self.__logger.log(LOG_LEVEL_CRITICAL, in_dict["why"])
            act_time = time.time()
            if abs(act_time - self.__last_cinfo) > 1:
                self.__last_cinfo = act_time
            for line in in_dict["failure"].getTraceback().split("\n"):
                self.__logger.log(LOG_LEVEL_CRITICAL, line)
    def close(self):
        for handle in self.__logger.logger.handlers:
            handle.close()

def get_logger(name, destination, **kwargs):
    """ specify init_logger=True to prepend init.at to the logname """
    is_linux, cur_pid = (
        sys.platform in ["linux2", "linux3", "linux"],
        os.getpid())
    if kwargs.get("init_logger", False) and is_linux:
        # force init.at logger
        if not name.startswith("init.at."):
            name = "init.at.{}".format(name)
    # get unique logger for 0MQ send
    act_logger = logging.getLogger("{}.{:d}".format(name, cur_pid))
    act_logger.name = name
    act_logger.propagate = 0
    if not hasattr(act_logger, "handler_strings"):
        # only initiate once
        act_logger.handler_strings = []
    act_logger.setLevel(kwargs.get("base_log_level", logging.DEBUG))
    if type(destination) != list:
        destination = [destination]
    # hack to make destination unique with respect to pid
    destination = [(cur_pid, cur_dest) for cur_dest in destination]
    for act_dest in destination:
        # print name, act_dest
        if (cur_pid, act_dest) not in act_logger.handler_strings:
            act_dest = act_dest[1]
            act_logger.handler_strings.append((cur_pid, act_dest))
            if "context" not in kwargs:
                cur_context = zmq.Context()
            else:
                cur_context = kwargs["context"]

            pub = cur_context.socket(zmq.PUSH)
            pub.setsockopt(zmq.LINGER, 0)
            pub.connect(rewrite_log_destination(act_dest if act_dest.endswith("_zmq") else "{}_zmq".format(act_dest)))
            act_logger.addHandler(zmq_handler(pub, act_logger))
    if log_adapter:
        # by using the log_adapter we also add thread-safety to the logger
        act_adapter = log_adapter(act_logger, {})
    else:
        act_adapter = act_logger
    return act_adapter

class log_adapter(logging.LoggerAdapter):
    """ small adapater which adds host information to logRecords """
    def __init__(self, logger, extra):
        self.__lock = threading.Lock()
        self.set_prefix()
        logging.LoggerAdapter.__init__(self, logger, extra)
    def process(self, msg, kwargs):
        # add hostname and parent process id (to handle multiprocessing logging)
        if sys.platform in ["linux2", "linux3", "linux"]:
            kwargs.setdefault("extra", {})
            kwargs["extra"].setdefault("host", os.uname()[1].split(".")[0])
            kwargs["extra"].setdefault("ppid", os.getppid())
        elif sys.platform in ["win32"]:
            kwargs.setdefault("extra", {})
            kwargs["extra"].setdefault("host", os.getenv("COMPUTERNAME").lower())
            kwargs["extra"].setdefault("ppid", os.getppid())
        return msg, kwargs
    def set_prefix(self, pfix=""):
        self.__prefix = pfix
    def log_command(self, what):
        self.log("<LCH>{}</LCH>".format(what))
    def log(self, level, what=LOG_LEVEL_OK, *args, **kwargs):
        self.__lock.acquire()
        if type(level) in [str, unicode]:
            if self.__prefix:
                level = "{}{}".format(self.__prefix, level)
            try:
                logging.LoggerAdapter.log(self, what, level, *args, **kwargs)
            except:
                my_syslog(what)
                print(what, self)
                raise
        else:
            if self.__prefix:
                what = "{}{}".format(self.__prefix, what)
            try:
                logging.LoggerAdapter.log(self, level, what, *args, **kwargs)
            except:
                my_syslog(what)
                print(what, self)
                raise
        self.__lock.release()
    def close(self):
        self.log_command("close")
        for handle in self.logger.handlers:
            if hasattr(handle, "close"):
                handle.close()

class zmq_handler(logging.Handler):
    def __init__(self, t_sock, logger_struct, **kwargs):
        self.__target = t_sock
        self._open = True
        logging.Handler.__init__(self)
        self.__logger = logger_struct
    def makePickle(self, record):
        """
        Pickles the record in binary format with a length prefix, and
        returns it ready for transmission across the socket.
        """
        ei = record.exc_info
        if ei:
            dummy = self.format(record) # just to get traceback text into record.exc_text
            record.exc_info = None # to avoid Unpickleable error
        _d = dict(record.__dict__)
        _d["msg"] = record.getMessage()
        _d["args"] = None
        p_str = pickle.dumps(_d, 1)
        if ei:
            record.exc_info = ei # for next handler
        return p_str
    def emit(self, record):
        self.__target.send(self.makePickle(record))
    def close(self):
        if self._open:
            self._open = False
            # set linger to zero to speed up close process
            self.__target.setsockopt(zmq.LINGER, 0)
            self.__target.close()
            del self.__target
            if self.__logger:
                # remove from handler
                self.__logger.removeHandler(self)

class initat_formatter(object):
    # in fact a dummy formatter
    def format(self, record):
        record.message = record.getMessage()
        if getattr(record, "exc_info", None):
            tb_object = record.exc_info[2]
            frame_info = []
            for file_name, line_no, name, line in traceback.extract_tb(tb_object):
                frame_info.append("File '{}', line {:d}, in {}".format(file_name, line_no, name))
                if line:
                    frame_info.append(u" - {:d} : {}".format(line_no, line))
            frame_info.append(u"{} ({})".format(
                unicode(record.exc_info[0]),
                unicode(record.exc_info[1])))
            record.error_str = record.message + "\n" + "\n".join(frame_info)
            var_list, info_lines = ([], [])
            request = inspect.trace()[-1][0].f_locals.get("request", None)
            if request:
                info_lines.extend([
                    "",
                    "method is {}".format(request.method),
                    "",
                ])
                # print get / post variables
                v_dict = getattr(request, request.method, None)
                if v_dict:
                    var_list.extend([
                        "",
                        "{}:".format(get_plural("variable", len(v_dict))),
                        "",
                    ])
                    for s_num, s_key in enumerate(sorted(v_dict.keys())):
                        var_list.append(
                            "  {:3d} {}: {}".format(
                                s_num + 1,
                                s_key,
                                v_dict[s_key]
                            )
                        )
            # print frame_info, var_list
            record.exc_text = "\n".join(frame_info + var_list + info_lines)
        if hasattr(record, "request"):
            delattr(record, "request")

class init_handler(zmq_handler):
    zmq_context = None
    def __init__(self, filename=None):
        if not init_handler.zmq_context:
            init_handler.zmq_context = zmq.Context()
        cur_context = init_handler.zmq_context
        pub = cur_context.socket(zmq.PUSH)
        pub.connect(rewrite_log_destination("uds:/var/lib/logging-server/py_log_zmq"))
        zmq_handler.__init__(self, pub, None)
    def emit(self, record):
        if not record.name.startswith("init.at."):
            record.name = "init.at.{}".format(record.name)
        self.format(record)
        zmq_handler.emit(self, record)

class init_email_handler(zmq_handler):
    zmq_context = None
    def __init__(self, filename=None, *args, **kwargs):
        if not init_handler.zmq_context:
            init_handler.zmq_context = zmq.Context()
        cur_context = init_handler.zmq_context
        pub = cur_context.socket(zmq.PUSH)
        pub.connect(rewrite_log_destination("uds:/var/lib/logging-server/py_err_zmq"))
        zmq_handler.__init__(self, pub, None)
        self.__lens = {"name"       : 1,
                       "threadName" : 1,
                       "lineno"     : 1}
    def emit(self, record):
        record.IOS_type = "error"
        self.format(record)
        record.uid = os.getuid()
        record.gid = os.getgid()
        record.pid = os.getpid()
        record.ppid = os.getppid()
        zmq_handler.emit(self, record)

class init_handler_unified(zmq_handler):
    zmq_context = None
    def __init__(self, filename=None, *args, **kwargs):
        if not init_handler.zmq_context:
            init_handler.zmq_context = zmq.Context()
        cur_context = init_handler.zmq_context
        pub = cur_context.socket(zmq.PUSH)
        pub.connect(rewrite_log_destination("uds:/var/lib/logging-server/py_log_zmq"))
        zmq_handler.__init__(self, pub, None)
    def emit(self, record):
        if record.name.startswith("init.at."):
            record.name = record.name[8:]
        self.format(record)
        form_str = "%-s/%s[%d]"
        record.threadName = form_str % (record.name, record.threadName, record.lineno)
        record.name = "init.at.{}".format(UNIFIED_NAME)
        zmq_handler.emit(self, record)

class queue_handler(logging.Handler):
    """ sends log requests to other queues """
    def __init__(self, t_queue, **kwargs):
        self.__target_queue = t_queue
        self.__pre_tuple = kwargs.get("pre_tuple", "int_log")
        logging.Handler.__init__(self)
    def emit(self, record):
        try:
            self.__target_queue.put((self.__pre_tuple, record))
        except:
            self.handleError(record)

class progress_counter(object):
    def __init__(self, action, total_count, **kwargs):
        self.__act_cs_time = time.time()
        self.__action = action
        self.__total_count = total_count
        self.__start_count = total_count
        self.__lc, self.__sum_lc, self.__print_every = (0, 0, kwargs.get("print_every", 1))
        self.__log_command = kwargs.get("log_command", None)
    def _log(self, log_str, **kwargs):
        l_com = kwargs.get("log_command", self.__log_command)
        if l_com and log_str:
            l_com(log_str)
    def overview(self, **kwargs):
        if self.__total_count:
            diff_time = time.time() - self.__act_cs_time
            log_str = "{} {:d} ({} announced), {} total, {} per entity".format(
                self.__action,
                self.__sum_lc,
                self.__total_count,
                get_diff_time_str(diff_time),
                get_diff_time_str(diff_time / self.__sum_lc if self.__sum_lc else 0))
        else:
            log_str = "no entities to work with ({})".format(self.__action)
        self._log(log_str, **kwargs)
        return log_str
    def count(self, **kwargs):
        self.__lc += 1
        self.__sum_lc += 1
        self.__start_count -= 1
        if self.__lc == self.__print_every:
            act_time = time.time()
            time_spent = act_time - self.__act_cs_time
            time_to_go = time_spent / (self.__sum_lc) * (self.__start_count)
            if kwargs.get("show_rate", False):
                info_str = " (rate: %.2f / sec)" % (self.__sum_lc / time_spent)
            else:
                info_str = ""
            if kwargs.get("info_str", ""):
                info_str = "{}, {}".format(info_str, kwargs["info_str"])
            log_str = "%s %d, %5.2f %%, %d (%s) to go%s" % (
                self.__action,
                self.__lc,
                100. * (self.__sum_lc / float(max(1, self.__total_count))),
                self.__start_count,
                get_diff_time_str(time_to_go),
                info_str)
            self.__lc = 0
        else:
            log_str = ""
        self._log(log_str, **kwargs)
        return log_str
    def finished(self):
        return True if not self.__start_count else False

class dummy_ios(object):
    """
    dummy container for I/O redirection
    used for example in cluster-config-server.py
    """
    def __init__(self):
        self.out_buffer = []
    def write(self, what):
        self.out_buffer.append(what)
    def close(self):
        pass
    def __del__(self):
        pass
    def get_content(self):
        return "".join(self.out_buffer)

class dummy_ios_low(object):
    def __init__(self, save_fd):
        self.orig_fd = save_fd
        self.save_fd = os.dup(self.orig_fd)
        self.tmp_fo = os.tmpfile()
        self.new_fd = self.tmp_fo.fileno()
        os.dup2(self.new_fd, self.orig_fd)
    def close(self):
        self.tmp_fo.seek(0)
        self.data = self.tmp_fo.read()
        os.dup2(self.save_fd, self.orig_fd)
        del self.orig_fd
        del self.tmp_fo
        os.close(self.save_fd)

class form_list(object):
    def __init__(self):
        self.lines = []
        self.form_dict = {}
        self.header_dict = {}
        self.set_column_separator()
        self.act_row_idx = 0
        self.set_raw_mode()
    def set_raw_mode(self, raw_mode=False):
        self.raw_mode = raw_mode
    def add_line(self, l_p):
        if type(l_p) in [int, long]:
            l_p = str(l_p)
        if type(l_p) in [str, unicode]:
            l_p = [l_p]
        self.lines.append(tuple(l_p))
    def set_column_separator(self, def_val=" "):
        self.col_separator = def_val
    def set_format_string(self, row_idx, r_t="s", left="-", pre_string="", post_string="", min_size=0):
        if type(row_idx) in [str, unicode]:
            row_idx = dict([(v, k) for k, v in self.header_dict.iteritems()])[row_idx]
        if row_idx == -1:
            act_row_idx = self.act_row_idx + 1
        else:
            act_row_idx = row_idx
        self.form_dict[act_row_idx] = (r_t, left, pre_string, post_string, 0)
        self.act_row_idx = act_row_idx
    def set_header_string(self, row_idx, header):
        if type(header) == list:
            for idx in range(len(header)):
                self.header_dict[row_idx + idx] = header[idx]
        else:
            self.header_dict[row_idx] = header
    def __str__(self):
        if self.raw_mode:
            out_lines = [";".join([self.header_dict.get(idx, "").strip() for idx in range(len(self.header_dict.keys()))])]
            for l_p in self.lines:
                out_lines.append(";".join([str(x).strip() for x in l_p]))
        else:
            if not self.lines:
                raise ValueError("empty list (no lines)")
            # count number of rows
            num_rows = max([len(x) for x in self.lines])
            _min_rows = min([len(x) for x in self.lines])
            # if num_rows != min_rows:
            #    print "Number of rows differ"
            row_lens = [0] * num_rows
            for l_p in self.lines:
                l_p_l = len(l_p)
                if l_p_l < num_rows:
                    if l_p_l > 1:
                        row_lens = [max(x, y) for x, y in zip(row_lens[:l_p_l - 1], [len(str(y)) for y in list(l_p[:-1])])] + row_lens[l_p_l - 1:]
                else:
                    row_lens = [max(x, y) for x, y in zip(row_lens, [len(str(y)) for y in list(l_p)])]
            # body format parts, header format parts
            b_f_parts, h_f_parts = ([], [])
            for idx in range(num_rows):
                tp_str, lf_str, pre_str, post_str, min_len = self.form_dict.get(idx, ("s", "-", "", "", 0))
                act_len = max(row_lens[idx], min_len, len(self.header_dict.get(idx, "")))
                if tp_str.endswith("f") and tp_str.startswith("."):
                    b_f_parts.append(("%s%%%s%d%s%s" % (pre_str, lf_str, act_len, tp_str, post_str)))
                else:
                    b_f_parts.append(("%s%%%s%d%s%s" % (pre_str, lf_str, act_len, tp_str, post_str)))
                h_f_parts.append(("%s%%%s%ds%s" % (pre_str, lf_str, act_len, post_str)))
            b_form_str_dict = {num_rows : self.col_separator.join(b_f_parts)}
            h_form_str_dict = {num_rows : self.col_separator.join(h_f_parts)}
            for idx in range(1, len(b_f_parts)):
                b_form_str_dict[idx] = self.col_separator.join(b_f_parts[0:idx - 1] + ["%s"])
                h_form_str_dict[idx] = self.col_separator.join(h_f_parts[0:idx - 1] + ["%s"])
            out_lines = []
            if self.header_dict:
                headers = [self.header_dict.get(idx, "") for idx in range(len(self.header_dict.keys()))]
                out_lines.append((h_form_str_dict[len(headers)] % tuple(headers)).rstrip())
                out_lines.append("-" * len(out_lines[-1]))
            for l_p in self.lines:
                out_lines.append((b_form_str_dict[len(l_p)] % tuple(list(l_p))).rstrip())
        return "\n".join(out_lines)
    def __len__(self):
        return len(self.lines)
    def __unicode__(self):
        return str(self)

class form_entry(object):
    def __init__(self, content, **kwargs):
        self.content = content
        self.left = True
        self.min_width = 0
        self.pre_str = ""
        self.post_str = ""
        for key, value in kwargs.iteritems():
            setattr(self, key, value)
        setattr(self, "content_type", {
            str               : "s",
            unicode           : "s",
            type(None)        : "s",
            int               : "d",
            long              : "d",
            float             : "f",
            datetime.date     : "s",
            datetime.datetime : "s"}.get(type(self.content), "s"))
    def has_key(self, key):
        return hasattr(self, key)
    def __contains__(self, key):
        return hasattr(self, key)
    def __getitem__(self, key):
        return getattr(self, key)
    def min_len(self):
        return max(len(str(self)), self.min_width)
    def __str__(self):
        return self.form_str() % (self.content)
    def form_str(self, max_len=None):
        if self.content_type == "d":
            form_str = "d"
        elif self.content_type == "f":
            form_str = "f"
        else:
            form_str = "s"
        if max_len is None:
            form_str = "%%%s" % (form_str)
        else:
            form_str = "%%%s%d%s" % (
                "-" if self.left else "",
                max_len,
                form_str,
                )
        return "%s%s%s" % (self.pre_str, form_str, self.post_str)
    def format(self, max_len):
        return self.form_str(max_len) % (self.content)

class form_entry_right(form_entry):
    def __init__(self, content, **kwargs):
        form_entry.__init__(self, content, left=False, **kwargs)

class new_form_list(object):
    def __init__(self, **kwargs):
        self.__content = []
        self.__header_dict = {}
        self.__col_sep = kwargs.get("column_separator", " ")
        self.__strict_mode = kwargs.get("strict_mode", False)
        self.__none_string = kwargs.get("none_string", "None")
        # self.__format_dict = {}
    def append(self, add_list):
        # add list is a list of dicts
        for row_idx, item in enumerate(add_list):
            if item.content is None:
                item.content = self.__none_string
            if "header" in item:
                self.__header_dict[row_idx] = (item["left"], item["header"])
        self.__content.append(add_list)
    def __str__(self):
        return unicode(self)
    def __unicode__(self):
        if not self.__content:
            if self.__strict_mode:
                raise ValueError("empty list (no lines)")
            else:
                return ""
        # count number of rows
        row_count = [len(line) for line in self.__content]
        _min_rows, max_rows = (
            min(row_count),
            max(row_count))
        row_lens = [0] * max_rows
        for line in self.__content:
            line_rows = len(line)
            # hack because part has to be casted to a string
            line_lens = []
            for part in line:
                line_lens.append(part.min_len())
            if line_rows < max_rows:
                if line_rows > 1:
                    # only count the first (line_rows - 1) rows
                    row_lens = [max(old_len, new_len) for old_len, new_len in zip(
                        row_lens[:line_rows - 1],
                        line_lens[:line_rows - 1])] + row_lens[line_rows - 1:]
            else:
                # count all rows
                row_lens = [max(old_len, new_len) for old_len, new_len in zip(row_lens, line_lens)]
        # take header into account
        row_lens = [max(old_len, len(self.__header_dict.get(idx, (True, ""))[1])) for idx, old_len in enumerate(row_lens)]
        out_lines = []
        if self.__header_dict:
            # header = [self.__header_dict.get(idx, "header%d" % (idx)) for idx in xrange(max_rows)]
            header_list = [self.__header_dict.get(idx, (True, "")) for idx in xrange(max_rows)]
            form_str = self.__col_sep.join(["%%%s%ds" % ("-" if header_list[idx][0] else "", row_len) for idx, row_len in enumerate(row_lens)])
            out_lines.append((form_str % tuple([_e[1] for _e in header_list])).rstrip())
            out_lines.append("-" * len(out_lines[-1]))
        for line in self.__content:
            out_lines.append(self.__col_sep.join([entry.format(max_len) for entry, max_len in zip(line, row_lens[:len(line)])]))
        return "\n".join(out_lines)
    def __len__(self):
        return len(self.__content)

def compress_list(ql, **kwargs):
    # node prefix, postfix, start_string, end_string
    def add_p(np, ap, s_str, e_str):
        if s_str == e_str:
            return "%s%s%s" % (np, s_str, ap)
        elif int(s_str) + 1 == int(e_str):
            return "%s%s%s/%s%s" % (np, s_str, ap, e_str, ap)
        else:
            return "%s%s%s-%s%s" % (np, s_str, ap, e_str, ap)
    pf_re = re.compile("^(?P<pef>.*?)(?P<num>\d+)(?P<pof>.*)$")
    nc_dict, unmatch_list = ({}, [])
    for q_e in ql:
        pf_m = pf_re.match(q_e)
        if pf_m:
            # prefix, postfix and index
            pef, pof = (
                pf_m.group("pef"),
                pf_m.group("pof"),
            )
            nc_dict.setdefault(pef, {}).setdefault(pof, {})[int(pf_m.group("num"))] = pf_m.group("num")
        else:
            # no match found
            unmatch_list.append(q_e)
    nc_a = []
    for pef in nc_dict.keys():
        for pof in nc_dict[pef].keys():
            act_l = nc_dict[pef][pof]
            s_idx = None
            for e_idx in sorted(act_l.keys()):
                e_num = act_l[e_idx]
                if s_idx is None:
                    s_idx, s_num = (e_idx, e_num)
                    l_num, l_idx = (s_num, s_idx)
                else:
                    if e_idx == l_idx + 1:
                        pass
                    else:
                        nc_a += [add_p(pef, pof, s_num, l_num)]
                        s_num, s_idx = (e_num, e_idx)
                    l_num, l_idx = (e_num, e_idx)
            if pef:
                nc_a += [add_p(pef, pof, s_num, l_num)]
    return kwargs.get("separator", ", ").join(sorted(nc_a) + sorted(unmatch_list))

def compress_num_list(ql, excl_list=[]):
    def add_p(s_idx, e_idx):
        if e_idx == s_idx:
            return "{:d}".format(s_idx)
        elif e_idx == s_idx + 1:
            return "{:d}/{:d}".format(s_idx, e_idx)
        else:
            return "{:d}-{:d}".format(s_idx, e_idx)
    if type(ql) == list:
        ql.sort()
    nc_a = []
    s_num = None
    for t_num in ql:
        if t_num not in excl_list:
            e_num = t_num
            if s_num is None:
                s_num, l_num = (e_num, e_num)
            else:
                if e_num == l_num + 1:
                    pass
                else:
                    nc_a.append(add_p(s_num, l_num))
                    s_num = e_num
                l_num = e_num
    if s_num:
        nc_a.append(add_p(s_num, e_num))
    return ", ".join(nc_a)

def my_syslog(out_str, log_lev=LOG_LEVEL_OK, out=False):
    if log_lev >= LOG_LEVEL_WARN:
        log_type = syslog.LOG_WARNING | syslog.LOG_USER
    elif log_lev >= LOG_LEVEL_ERROR:
        log_type = syslog.LOG_ERR | syslog.LOG_USER
    else:
        log_type = syslog.LOG_INFO | syslog.LOG_USER
    try:
        if type(out_str) == str:
            syslog.syslog(log_type, str(out_str))
        else:
            syslog.syslog(log_type, out_str.encode("utf-8"))
    except:
        exc_info = sys.exc_info()
        error_str = "({}, {})".format(
            unicode(exc_info[0]),
            unicode(exc_info[1]),
        )
        if type(out_str) == unicode:
            syslog.syslog(
                syslog.LOG_ERR | syslog.LOG_USER,
                "error logging unicode ({}, len {:d}, log_type {:d})".format(
                    error_str,
                    len(out_str),
                    log_type)
                )
        else:
            syslog.syslog(
                syslog.LOG_ERR | syslog.LOG_USER,
                "error logging string ({}, len {:d}, log_type {:d})".format(
                    error_str,
                    len(str(out_str)),
                    log_type)
                )
    if out:
        print(out_str)

def get_log_level_str(level):
    return {
        LOG_LEVEL_OK       : "ok",
        LOG_LEVEL_WARN     : "warn",
        LOG_LEVEL_ERROR    : "err",
        LOG_LEVEL_CRITICAL : "crit"
    }.get(level, "lev{:d}".format(level))

class my_formatter(logging.Formatter):
    def __init__(self, *args):
        logging.Formatter.__init__(self, *args)
        self.set_max_line_length(0)
    def set_max_line_length(self, max_length):
        self.__max_line_length = max_length
    def format(self, message):
        # threshold is 20 bytes longer because of double-formatting
        if self.__max_line_length and len(message.msg) > self.__max_line_length + 20:
            left = len(message.msg) - self.__max_line_length
            if left > 4:
                message.msg = "{} ({:d} left)".format(message.msg[:self.__max_line_length], len(message.msg))
        return logging.Formatter.format(self, message)

class logfile(logging.handlers.BaseRotatingHandler):
    def __init__(self, filename, mode="a", max_bytes=1000000, encoding=None, max_age_days=365):
        # always append if max_size > 0
        if max_bytes > 0:
            mode = "a"
        logging.handlers.BaseRotatingHandler.__init__(self, filename, mode, encoding, delay=False)
        self.__last_record = None
        self.set_max_bytes(max_bytes)
        self.max_age = max_age_days
        self._cleanup_old_logfiles()
    def set_max_bytes(self, max_bytes):
        self.__max_size = max_bytes
    def shouldRollover(self, record):
        do_rollover = False
        if self.__max_size > 0:
            msg = "{}\n".format(self.format(record))
            try:
                if self.stream.tell() + len(msg) > self.__max_size:
                    do_rollover = True
            except ValueError:
                pass
        return do_rollover
    def _cleanup_old_logfiles(self):
        cur_dir = os.path.dirname(self.baseFilename)
        base_name = os.path.basename(self.baseFilename)
        file_list = [entry for entry in os.listdir(cur_dir) if entry.startswith(base_name) and entry != base_name]
        for cur_file in file_list:
            f_name = os.path.join(cur_dir, cur_file)
            act_age = int(abs(time.time() - os.stat(f_name)[stat.ST_MTIME]) / (24 * 3600))
            if act_age > self.max_age:
                try:
                    os.unlink(f_name)
                except:
                    my_syslog("cannot remove file '{}' ({:d} > {:d} days)".format(f_name, act_age, self.max_age), LOG_LEVEL_ERROR)
                else:
                    my_syslog("removed file '{}' ({:d} > {:d} days)".format(f_name, act_age, self.max_age))
    def doRollover(self):
        self._cleanup_old_logfiles()
        self.stream.close()
        act_time = time.localtime()
        base_postfix = "%04d%02d%02d" % (act_time[0], act_time[1], act_time[2])
        if bz2:
            gz_postfix = "bz2"
        else:
            gz_postfix = "gz"
        act_idx = 0
        while True:
            act_postfix = "{}.{:d}".format(base_postfix, act_idx) if act_idx else base_postfix
            gz_file_name = "{}-{}.{}".format(
                self.baseFilename,
                act_postfix,
                gz_postfix)
            if os.path.isfile(gz_file_name):
                act_idx += 1
            else:
                break
        try:
            if bz2:
                act_z = bz2.BZ2File(gz_file_name, "w")
            else:
                act_z = gzip.open(gz_file_name, "wb", 4)
        except:
            exc_info = sys.exc_info()
            my_syslog("error opening {}: {} ({})".format(
                gz_file_name,
                str(exc_info[0]),
                str(exc_info[1])))
        else:
            act_z.write(open(self.baseFilename, "r").read())
            act_z.close()
            os.chmod(gz_file_name, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
            self.stream.close()
            os.unlink(self.baseFilename)
            self.stream = self._open()
            os.chmod(self.baseFilename, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
            self.mode = "w"
            self.stream = self._open()

class syslog_helper_obj(object):
    def __init__(self):
        pass
    def _split_str(self, in_str, max_count=1):
        act_list = []
        act_str = ""
        in_count = 0
        for in_c in in_str:
            if in_c == " ":
                if in_count:
                    act_str = "{}{}".format(act_str, in_c)
                else:
                    act_str = act_str.strip()
                    if act_str:
                        act_list.append(act_str)
                    act_str = ""
            else:
                if in_c == "(":
                    if in_count == max_count:
                        raise ValueError("already in parentheses_mode ({}) ...".format(in_str))
                    if in_count > 1:
                        act_str = "{}{}".format(act_str, in_c)
                    in_count += 1
                elif in_c == ")":
                    if not in_count:
                        raise ValueError("not in parentheses_mode ...")
                    in_count -= 1
                    if not in_count:
                        act_str = "{}{}".format(act_str, in_c)
                act_str = "{}{}".format(act_str, in_c)
        act_str = act_str.strip()
        if act_str:
            act_list.append(act_str)
        return act_list
    def _parse_stream(self, in_stream, mc_list, str_start):
        str_end = {"{" : "}",
                   "(" : ")"}[str_start]
        if str_start == "(":
            max_struct = 2
        else:
            max_struct = 1
        s_list = []
        struct_count, pre_str, in_str = (0, "", "")
        need_semi = False
        for in_c in in_stream:
            if in_c not in [" ", ";"] and need_semi:
                raise ValueError("need semikolon, error ...")
            elif in_c == ";" and not struct_count and need_semi:
                pre_parts = pre_str.split()
                com = pre_parts.pop(0)
                if com in mc_list:
                    name = pre_parts.pop(0)
                    key_str = (com, name)
                else:
                    key_str = com
                s_list.append((key_str, in_str.strip()))
                # print "got struct %s(%s)" % (str(key_str), in_str)
                need_semi = False
                pre_str = ""
                in_str = ""
            else:
                if in_c == str_start:
                    if struct_count == max_struct:
                        raise ValueError("already in structure, error ...")
                    struct_count += 1
                    if struct_count > 1:
                        in_str = "{}{}".format(in_str, in_c)
                elif in_c == str_end:
                    if not struct_count:
                        raise ValueError("not in structure, error ...")
                    # now we need a semikolon
                    struct_count -= 1
                    if not struct_count:
                        need_semi = True
                        pre_str = pre_str.strip()
                        in_str = in_str.strip()
                    else:
                        in_str = "{}{}".format(in_str, in_c)
                else:
                    if struct_count:
                        in_str = "{}{}".format(in_str, in_c)
                    else:
                        pre_str = "{}{}".format(pre_str, in_c)
        return s_list
    def is_string(self, in_str):
        return type(in_str) == str and in_str[0] == in_str[-1] and in_str[0] in ["'", '"']
    def flatten_string(self, in_str):
        if self.is_string(in_str):
            return in_str[1:-1]
        else:
            return in_str
    def get_dict_sort(self, in_dict):
        ret_dict = {}
        for top_k, top_v in in_dict.iteritems():
            for sub_k, sub_v in top_v.get_dict().iteritems():
                for sub_part in sub_v:
                    if self.is_string(sub_part):
                        ret_dict[self.flatten_string(sub_part)] = (top_k, sub_k, [x for x in sub_v if x != sub_part])
        return ret_dict

class syslog_ng_destination(syslog_helper_obj):
    def __init__(self, in_str):
        syslog_helper_obj.__init__(self)
        d_list = self._parse_stream(in_str, [], "(")
        if len(d_list) > 1:
            raise ValueError("__destination to long ({:d})".format(len(d_list)))
        elif d_list:
            self.__type, self.__args = d_list[0]
            self.__args = self._split_str(self.__args)
    def __repr__(self):
        return "{} {}, {}".format("destination", self.__type, " ".join(self.__args))
    def get_conf_str(self):
        return " "

class syslog_ng_source(syslog_helper_obj):
    def __init__(self, in_str):
        syslog_helper_obj.__init__(self)
        self.__sources = dict([(key, self._split_str(value)) for key, value in self._parse_stream(in_str, [], "(")])
    def get_dict(self):
        return self.__sources
    def __repr__(self):
        return "{} {}".format("source", " ".join(["{}({})".format(x, " ".join(y)) for x, y in self.__sources.iteritems()]))
    def get_conf_str(self):
        return " "

class syslog_ng_filter(syslog_helper_obj):
    def __init__(self, in_str):
        syslog_helper_obj.__init__(self)
        self.__filter_list = self._split_str(in_str, 4)
    def __repr__(self):
        return "{} {}".format("filter", " ".join(self.__filter_list))
    def get_conf_str(self):
        return " ".join(self.__filter_list)

class syslog_ng_log(syslog_helper_obj):
    def __init__(self, in_str):
        syslog_helper_obj.__init__(self)
        obj_list = self._parse_stream(in_str, [], "(")
        o_dict = dict([(k, []) for k in ["source", "destination", "filter", "flags"]])
        for key, value in obj_list:
            if key in o_dict.keys():
                o_dict[key].append(value)
            else:
                raise KeyError("unknown key {}".format(key))
        if not o_dict["source"]:
            raise ValueError("need at least one source")
        elif not o_dict["destination"]:
            raise ValueError("need at least one destination")
        self.__obj_dict = o_dict
    def __repr__(self):
        return "log from (%s)%s to (%s)%s" % (", ".join(self.__obj_dict["source"]),
                                                self.__obj_dict["filter"] and " with filter (%s)" % (", ".join(self.__obj_dict["destination"])) or "",
                                                ", ".join(self.__obj_dict["destination"]),
                                                self.__obj_dict["flags"] and ", flags (%s)" % (", ".join(self.__obj_dict["flags"])) or "")

class syslog_ng_config(syslog_helper_obj):
    def __init__(self, name="/etc/syslog-ng/syslog-ng.conf"):
        syslog_helper_obj.__init__(self)
        self.__stream = " ".join([y for y in [x.strip() for x in file(name, "r").read().split("\n")] if len(y) and not y.startswith("#")])
        self.__multi_commands = {"destination" : syslog_ng_destination,
                                 "source"      : syslog_ng_source,
                                 "filter"      : syslog_ng_filter}
        self.__multi_objects = dict([(k, {}) for k in self.__multi_commands.keys()])
        self.__log_list = []
        # parse stream
        s_list = self._parse_stream(self.__stream, self.__multi_commands.keys(), "{")
        for key, value in s_list:
            if type(key) == set:
                key, name = key
            if key in self.__multi_commands.keys():
                self.__multi_objects[key][name] = self.__multi_commands[key](value)
            elif key == "log":
                self.__log_list.append(syslog_ng_log(value))
            elif key == "options":
                self.__options = dict([(k, value) for k, value in self._parse_stream(value, [], "(")])
            else:
                raise KeyError("unknown key %s (%s)" % (key, str(value)))
    def get_config_lines(self):
        # return lines with the config
        r_lines = ["# auto-generated syslog-ng.conf", ""]
        if self.__options:
            r_lines.append("options {")
            for key, value in self.__options.iteritems():
                r_lines.append("    %s(%s);" % (key, value))
            r_lines.extend(["};", ""])
        for mc in self.__multi_commands.keys():
            for key, value in self.__multi_objects[mc].iteritems():
                r_lines.append("%s %s %s" % (mc, key, value.get_conf_str()))
        return r_lines
    def pprint_config(self):
        pprint.pprint(self.__multi_objects)
        pprint.pprint(self.__log_list)
        pprint.pprint(self.__options)
    def get_multi_object(self, name):
        return self.__multi_objects[name]
        # pprint.pprint(s_dict)

# def main():
#    a = new_form_list()
#    a.append([form_entry("xxx", header="a"),
#              form_entry(u"öäöü", header="test"),
#              form_entry_right(89, header="num")])
#    print(unicode(a))
#    # a = syslog_ng_config()
#    # print a.get_dict_sort(a.get_multi_object("source"))
#    # print "\n".join(a.get_config_lines())
#    sys.exit(0)
#
# if __name__ == "__main__":
#    main()
#    print("Loadable module, exiting...")
#    sys.exit(0)
