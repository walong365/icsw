#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2010,2011,2012 Andreas Lang-Nevyjel
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

import sys
import time
import os
import os.path
import gzip
import stat
try:
    import bz2
except:
    bz2 = None
import re
import datetime
import logging
import logging.handlers
import cPickle
import pprint
import socket
import threading
if sys.platform in ["linux2", "linux3"]:
    import syslog
try:
    import zmq
except ImportError:
    zmq = None

LOG_LEVEL_OK       = 20
LOG_LEVEL_WARN     = 30
LOG_LEVEL_ERROR    = 40
LOG_LEVEL_CRITICAL = 50

# add the levels to the logging dict
logging.addLevelName(LOG_LEVEL_OK      , "ok"  )
logging.addLevelName(LOG_LEVEL_WARN    , "warn")
logging.addLevelName(LOG_LEVEL_ERROR   , "err" )
logging.addLevelName(LOG_LEVEL_CRITICAL, "crit")

def rewrite_log_destination(log_dest):
    if log_dest.startswith("uds:"):
        log_dest = log_dest.replace("uds:", "ipc://")
    return log_dest

def map_old_to_new_level(in_level):
    return {0  : LOG_LEVEL_OK,
            5  : LOG_LEVEL_WARN,
            10 : LOG_LEVEL_ERROR,
            20 : LOG_LEVEL_CRITICAL}.get(in_level, in_level)

def map_log_level_to_log_status(log_lev):
    return {LOG_LEVEL_OK       : "i",
            LOG_LEVEL_WARN     : "w",
            LOG_LEVEL_ERROR    : "e",
            LOG_LEVEL_CRITICAL : "c"}.get(log_lev, "c")

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
    
def get_plural(in_str, num, show_int=1, fstr_len=0, **args):
    if type(num) in [type([]), type(set())]:
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

def get_size_str(in_s, long_version=False, divider=1024):
    if type(in_s) == type(""):
        len_in_s = len(in_s)
    else:
        len_in_s = in_s
    b_str = long_version and "Byte" or "B"
    pf_f, pf_str = (["k", "M", "G", "T", "P", "E"], "")
    while in_s > divider:
        in_s = in_s / float(divider)
        pf_str = pf_f.pop(0)
    return "%s %s%s" % (pf_str and "%6.2f" % (in_s) or "%4d" % (in_s),
                        pf_str,
                        b_str)

def get_diff_time_str(diff_secs):
    abs_diffs = abs(diff_secs)
    is_int = type(abs_diffs) in [type(0), type(0L)]
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
                        diff_str = "%dy:%03d:%02d:%02d:%02d" % (abs_years, abs_days, abs_hours, abs_mins, abs_secs)
                    else:
                        diff_str = "%d:%02d:%02d:%02d" % (abs_days, abs_hours, abs_mins, abs_secs)
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
    """ specify init_logger=True to append init.at to the logname """
    is_linux, cur_pid = (
        sys.platform in ["linux2", "linux3"],
        os.getpid())
    if kwargs.get("init_logger", False) and is_linux:
        # force init.at logger
        if not name.startswith("init.at."):
            name ="init.at.%s" % (name)
    # get unique logger for 0MQ send
    act_logger = logging.getLogger("%s.%d" % (name, cur_pid))
    act_logger.name = name
    act_logger.propagate = 0
    if not hasattr(act_logger, "handler_strings"):
        # only initiate once
        act_logger.handler_strings = []
    act_logger.setLevel(kwargs.get("base_log_level", logging.DEBUG))
    if type(destination) != type([]):
        destination = [destination]
    # hack to make destination unique with respect to pid
    destination = [(cur_pid, cur_dest) for cur_dest in destination]
    for act_dest in destination:
        #print name, act_dest
        if (cur_pid, act_dest) not in act_logger.handler_strings:
            act_dest = act_dest[1]
            act_logger.handler_strings.append((cur_pid, act_dest))
            if kwargs.get("zmq", False):
                cur_context = kwargs["context"]
                pub = cur_context.socket(zmq.PUSH)
                pub.connect(rewrite_log_destination(act_dest if act_dest.endswith("_zmq") else "%s_zmq" % (act_dest)))
                act_logger.addHandler(zmq_handler(pub))
                pass
            else:
                if act_dest.count("zmq"):
                    raise ValueError, "requested ZMQ-type destination '%s' without ZMQ-Protocol" % (act_dest)
                if act_dest.startswith("uds:"):
                    if is_linux:
                        # linux, ok
                        if act_logger.handlers:
                            # FIXME, handlers already set / used
                            pass
                        else:
                            act_logger.addHandler(local_uds_handler(act_dest[4:]))
                    else:
                        # Windows
                        # Formatter
                        # dont forget to correct the bug in logging/__init__.py line 772 (2.6.3): \n -> \r\n
                        act_form = logging.Formatter("%(asctime)s : %(levelname)-5s (%(threadName)s) %(message)s",
                                                     "%a %b %d %H:%M:%S %Y")
                        dst_file = os.path.abspath("c:\\var\\log\\%s.log" % (name))
                        if not os.path.isdir(os.path.dirname(dst_file)):
                            os.makedirs(os.path.dirname(dst_file))
                        new_h = logging.handlers.RotatingFileHandler(dst_file,
                                                                     maxBytes=kwargs.get("max_bytes", 100000),
                                                                     backupCount=kwargs.get("backup_count", 500),
                                                                     encoding="utf-8")
                        new_h.setFormatter(act_form)
                        act_logger.addHandler(new_h)
                elif act_dest.startswith("udp:"):
                    act_logger.addHandler(udp_handler(act_dest[4:]))
                elif act_dest == "threadqueue":
                    act_logger.addHandler(queue_handler(kwargs["target_queue"], **kwargs))
                elif act_dest == "stdout":
                    act_logger.addHandler(logging.StreamHandler())
    if log_adapter:
        # by using the log_adapter we also add thread-safety to the logger
        act_adapter = log_adapter(act_logger, {})
    else:
        act_adapter = act_logger
    return act_adapter

try:
    class log_adapter(logging.LoggerAdapter):
        """ small adapater which adds host information to logRecords """
        def __init__(self, logger, extra):
            self.__lock = threading.Lock()
            self.set_prefix()
            logging.LoggerAdapter.__init__(self, logger, extra)
        def process(self, msg, kwargs):
            # add hostname and parent process id (to handle multiprocessing logging)
            if sys.platform in ["linux2", "linux3"]:
                kwargs.setdefault("extra", {})
                kwargs["extra"].setdefault("host", os.uname()[1])
                kwargs["extra"].setdefault("ppid", os.getppid())
            elif sys.platform in ["win32"]:
                kwargs.setdefault("extra", {})
                kwargs["extra"].setdefault("host", os.getenv("COMPUTERNAME").lower())
                kwargs["extra"].setdefault("ppid", os.getppid())
            return msg, kwargs
        def set_prefix(self, pfix=""):
            self.__prefix = pfix
        def log_command(self, what):
            self.log("<LCH>%s</LCH>" % (what))
        def log(self, level, what=LOG_LEVEL_OK, *args, **kwargs):
            self.__lock.acquire()
            if type(level) == type(""):
                if self.__prefix:
                    level = "%s%s" % (self.__prefix, level)
                logging.LoggerAdapter.log(self, what, level, *args, **kwargs)
            else:
                if self.__prefix:
                    what = "%s%s" % (self.__prefix, what)
                logging.LoggerAdapter.log(self, level, what, *args, **kwargs)
            self.__lock.release()
        def close(self):
            self.log_command("close")
            for handle in self.logger.handlers:
                if hasattr(handle, "close"):
                    handle.close()
except:
    log_adapter = None

class zmq_handler(logging.Handler):
    def __init__(self, t_sock):
        self.__target = t_sock
        self._open = True
        logging.Handler.__init__(self)
    def makePickle(self, record):
        """
        Pickles the record in binary format with a length prefix, and
        returns it ready for transmission across the socket.
        """
        ei = record.exc_info
        if ei:
            dummy = self.format(record) # just to get traceback text into record.exc_text
            record.exc_info = None  # to avoid Unpickleable error
        p_str = cPickle.dumps(record.__dict__, 1)
        if ei:
            record.exc_info = ei  # for next handler
        return p_str
    def emit(self, record):
        self.__target.send(self.makePickle(record))
    def close(self):
        if self._open:
            self._open = False
            self.__target.close()
        
class queue_handler(logging.Handler):
    """ sends log requests to other queues """
    def __init__(self, t_queue, **args):
        self.__target_queue = t_queue
        self.__pre_tuple = args.get("pre_tuple", "int_log")
        logging.Handler.__init__(self)
    def emit(self, record):
        try:
            self.__target_queue.put((self.__pre_tuple, record))
        except:
            self.handleError(record)
    
class udp_handler(logging.handlers.DatagramHandler):
    def __init__(self, target_str):
        # parse target_str
        if target_str.count(":"):
            host, port = target_str.split(":")
            port = int(port)
        else:
            # default port is logging_server port
            host, port = (target_str,
                          8011)
        logging.handlers.DatagramHandler.__init__(self, host, port)
    def makePickle(self, record):
        ei = record.exc_info
        if ei:
            dummy = self.format(record) # just to get traceback text into record.exc_text
            record.exc_info = None  # to avoid Unpickleable error
        out_str = cPickle.dumps(record.__dict__, 1)
        if ei:
            record.exc_info = ei  # for next handler
        return "%08d" % (len(out_str)) + out_str
##    def send(self, out_str):
##        if self.sock is None:
##            self.createSocket()
##        while len(out_str):
##            print "*", len(out_str)
##            self.sock.sendto(out_str[0:8192], (self.host, self.port))
##            out_str = out_str[8192:]
    
class local_uds_handler(logging.Handler):
    """ local unix domain socket handler """
    def __init__(self, address, **args):
        self.__address = address
        logging.Handler.__init__(self)
        self.__unix_socket = True
        self._connect_unixsocket()
    def _connect_unixsocket(self):
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        # syslog may require either DGRAM or STREAM sockets
        try:
            self.socket.connect(self.__address)
        except socket.error:
            self.socket.close()
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                self.socket.connect(self.__address)
            except socket.error:
                self.socket = None
                pass
        if self.socket:
            self.socket.setblocking(False)
    def close(self):
        if hasattr(self, "socket"):
            if self.socket:
                self.socket.close()
                del self.socket
    def makePickle(self, record):
        """
        Pickles the record in binary format with a length prefix, and
        returns it ready for transmission across the socket.
        """
        ei = record.exc_info
        if ei:
            dummy = self.format(record) # just to get traceback text into record.exc_text
            record.exc_info = None  # to avoid Unpickleable error
        p_str = cPickle.dumps(record.__dict__, 1)
        if ei:
            record.exc_info = ei  # for next handler
        return "%08d%s" % (len(p_str), p_str)
    def handleError(self, record):
        my_syslog("%s:%s" % (record.threadName, record.msg), record.levelno)
    def emit(self, record):
        """
        Emit a record.
        """
        if not self.socket:
            self._connect_unixsocket()
        msg = self.makePickle(record)
        if self.socket:
            # add unique id to record in case of multi-thread (process) logging via the same unixsocket FIXME
            to_send = 8000
            while msg:
                try:
                    just_sent = self.socket.send(msg[:to_send])
                except socket.error:
                    self._connect_unixsocket()
                except (KeyboardInterrupt, SystemExit):
                    raise
                except:
                    self.handleError(record)
                    msg = None
                else:
                    msg = msg[to_send:]
        else:
            my_syslog(record)
    
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
            log_str = "%s %d (%s announced), %s total, %s per entity" % (self.__action,
                                                                         self.__sum_lc,
                                                                         self.__total_count,
                                                                         get_diff_time_str(diff_time),
                                                                         get_diff_time_str(diff_time / self.__sum_lc if self.__sum_lc else 0))
        else:
            log_str = "no entities to work with (%s)" % (self.__action)
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
                info_str = "%s, %s" % (info_str, kwargs["info_str"])
            log_str = "%s %d, %5.2f %%, %d (%s) to go%s" % (self.__action,
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
    def __init__(self):
        self.out_buffer = []
    def write(self, what):
        self.out_buffer.append(what)
    def close(self):
        pass
    def __del__(self):
        pass
    
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
        if type(l_p) in [type(0), type(0L)]:
            l_p = str(l_p)
        if type(l_p) == type("a"):
            l_p = [l_p]
        self.lines.append(tuple(l_p))
    def set_column_separator(self, def_val=" "):
        self.col_separator = def_val
    def set_format_string(self, row_idx, r_t="s", left="-", pre_string="", post_string="", min_size=0):
        if type(row_idx) == type(""):
            row_idx = dict([(v, k) for k, v in self.header_dict.iteritems()])[row_idx]
        if row_idx == -1:
            act_row_idx = self.act_row_idx + 1
        else:
            act_row_idx = row_idx
        self.form_dict[act_row_idx] = (r_t, left, pre_string, post_string, 0)
        self.act_row_idx = act_row_idx
    def set_header_string(self, row_idx, header):
        if type(header) == type([]):
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
                raise ValueError, "empty list (no lines)"
            # count number of rows
            num_rows = max([len(x) for x in self.lines])
            min_rows = min([len(x) for x in self.lines])
            #if num_rows != min_rows:
            #    print "Number of rows differ"
            row_lens = [0] * num_rows
            for l_p in self.lines:
                l_p_l = len(l_p)
                if l_p_l < num_rows:
                    if l_p_l > 1:
                        row_lens = [max(x, y) for x, y in zip(row_lens[:l_p_l - 1], [len(str(y)) for y in list(l_p[:-1])])] + row_lens[l_p_l-1:]
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
        for key, value in kwargs.iteritems():
            setattr(self, key, value)
    def has_key(self, key):
        return hasattr(self, key)
    def __contains__(self, key):
        return hasattr(self, key)
    def __getitem__(self, key):
        return getattr(self, key)

class form_entry_right(form_entry):
    def __init__(self, content, **kwargs):
        form_entry.__init__(self, content, left=False, **kwargs)

class new_form_list(object):
    def __init__(self, **kwargs):
        self.__content = []
        self.__header_dict = {}
        self.__col_sep = kwargs.get("column_separator", " ")
        self.__strict_mode = kwargs.get("strict_mode", False)
        self.__format_dict = {}
    def append(self, add_list):
        # add list is a list of dicts
        line_content = []
        for row_idx, item in enumerate(add_list):
            if "header" in item:
                self.__header_dict[row_idx] = item["header"]
            act_content = item["content"]
            if not row_idx in self.__format_dict:
                self.__format_dict[row_idx] = {"left"      : True,
                                               "format"    : {type("")          : "s",
                                                              type(u"")         : "s",
                                                              type(None)        : "s",
                                                              type(0)           : "d",
                                                              type(0L)          : "d",
                                                              datetime.date     : "s",
                                                              datetime.datetime : "s"}.get(type(act_content), "f"),
                                               "min_width" : 0}
            for key in self.__format_dict[row_idx].iterkeys():
                if key in item:
                    self.__format_dict[row_idx][key] = item[key]
            line_content.append(act_content)
        self.__content.append(line_content)
    def __str__(self):
        return unicode(self)
    def __unicode__(self):
        if not self.__content:
            if self.__strict_mode:
                raise ValueError, "empty list (no lines)"
            else:
                return ""
        # count number of rows
        row_count = [len(line) for line in self.__content]
        min_rows, max_rows = (min(row_count),
                              max(row_count))
        row_lens = [0] * max_rows
        for line in self.__content:
            line_rows = len(line)
            # hack because part has to be casted to a string
            line_lens = [len(unicode(part)) for part in line]
            if line_rows < max_rows:
                if line_rows > 1:
                    # only count the first (line_rows - 1) rows
                    row_lens = [max(old_len, new_len) for old_len, new_len in zip(row_lens[:line_rows - 1],
                                                                                  line_lens[:line_rows - 1])] + row_lens[line_rows - 1:]
            else:
                # count all rows
                row_lens = [max(old_len, new_len) for old_len, new_len in zip(row_lens, line_lens)]
        # body formats, header formats
        body_forms, header_forms = ([], [])
        for idx in xrange(max_rows):
            f_info = self.__format_dict[idx]
            # actual width row
            act_width = max(row_lens[idx], f_info["min_width"], len(self.__header_dict.get(idx, "")))
            if f_info["format"] == "f":
                # float format
                body_forms.append("".join(["%",
                                           "-" if f_info["left"] else "",
                                           "%d" % (act_width),
                                           f_info["format"]]))
            else:
                # int / str format
                body_forms.append("".join(["%",
                                           "-" if f_info["left"] else "",
                                           "%d" % (act_width),
                                           f_info["format"]]))
            header_forms.append("".join(["%",
                                         "-" if f_info["left"] else "",
                                         "%ds" % (act_width)]))
        out_lines = []
        if self.__header_dict:
            header = [self.__header_dict.get(idx, "H%d" % (idx)) for idx in xrange(max_rows)]
            form_str = self.__col_sep.join(header_forms[0 : len(header)])
            out_lines.append((form_str % tuple(header)).strip())
            out_lines.append("-" * len(out_lines[-1]))
        for line in self.__content:
            if len(line) < max_rows:
                form_str = self.__col_sep.join(body_forms[0 : len(line)])
            else:
                form_str = self.__col_sep.join(body_forms)
            
            out_lines.append((form_str % tuple(line)).rstrip())
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
    pf_re = re.compile("^(?P<pef>.*?)(?P<num>\d+)(?P<pof>\D*)$")
    nc_dict = {}
    for q_e in ql:
        pf_m = pf_re.match(q_e)
        if pf_m:
            pef = pf_m.group("pef")
            idx = pf_m.group("num")
            pof = pf_m.group("pof")
        else:
            # no match found
            pef, idx, i_idx, pof = (q_e, "", 0, "")
        if idx:
            i_idx = int(idx)
        else:
            i_idx = 0
        nc_dict.setdefault(pef, {}).setdefault(pof, {})[i_idx] = idx
    nc_a = []
    for pef in sorted(nc_dict.keys()):
        for pof in sorted(nc_dict[pef].keys()):
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
    return kwargs.get("separator", ", ").join(nc_a)

def compress_num_list(ql, excl_list=[]):
    def add_p(s_idx, e_idx):
        if e_idx == s_idx:
            return "%d" % (s_idx)
        elif e_idx == s_idx + 1:
            return "%d/%d" % (s_idx, e_idx)
        else:
            return "%d-%d" % (s_idx, e_idx)
    if type(ql) == type([]):
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
        log_type = syslog.LOG_ERR     | syslog.LOG_USER
    else:
        log_type = syslog.LOG_INFO    | syslog.LOG_USER
    try:
        syslog.syslog(log_type, str(out_str))
    except:
        syslog.syslog(syslog.LOG_ERR | syslog.LOG_USER, "error logging string (len %d, log_type %d)" % (len(str(out_str)),
                                                                                                        log_type))
    if out:
        print out_str

def get_log_level_str(level):
    return {LOG_LEVEL_OK       : "ok",
            LOG_LEVEL_WARN     : "warn",
            LOG_LEVEL_ERROR    : "err",
            LOG_LEVEL_CRITICAL : "crit"}.get(level, "lev%d" % (level))

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
                message.msg = "%s (%d left)" % (message.msg[:self.__max_line_length], len(message.msg))
        return logging.Formatter.format(self, message)
    
class new_logfile(logging.handlers.BaseRotatingHandler):
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
            msg = "%s\n" % (self.format(record))
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
            act_age = abs(time.time() - os.stat(f_name)[stat.ST_MTIME]) / (24 * 3600)
            if act_age > self.max_age:
                try:
                    os.unlink(f_name)
                except:
                    my_syslog("cannot remove file '%s' (%d > %d days)" % (f_name, act_age, self.max_age), LOG_LEVEL_ERROR)
                else:
                    my_syslog("removed file '%s' (%d > %d days)" % (f_name, act_age, self.max_age))
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
            act_postfix = "%s.%d" % (base_postfix, act_idx) if act_idx else base_postfix
            gz_file_name = "%s-%s.%s" % (self.baseFilename,
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
            my_syslog("error opening %s: %s (%s)" % (gz_file_name,
                                                     str(exc_info[0]),
                                                     str(exc_info[1])))
        else:
            act_z.write(open(self.baseFilename, "r").read())
            act_z.close()
            os.chmod(gz_file_name, 0640)
            self.stream.close()
            os.unlink(self.baseFilename)
            self.stream = self._open()
            os.chmod(self.baseFilename, 0640)
            self.mode = "w"
            self.stream = self._open()
        
class logfile(object):
    def __init__(self, name, max_size=10000000, max_repeat=100, temp_close_timeout=60):
        # if name is None we use stdout for writing
        self.__name = name
        self.__max_size = max_size
        self.__max_repeat = max_repeat
        self.__last_line = None
        self.__repeated = 0
        self.__lines = 0
        # temporarily close ?
        self.__temporary_closed = False
        # temp_close timeout
        self.__temporary_close_timeout = temp_close_timeout
        if self.__name:
            self.__stdout = False
            try:
                os.makedirs(os.path.dirname(name))
            except:
                pass
            self._open()
            self.__last_postfix = ""
            self.__act_index = 0
        else:
            self.__stdout = True
            self.__handle = None
        act_time = time.time()
        self.__create_time, self.__last_write = (act_time,
                                                 act_time)
    def _open(self):
        try:
            if os.path.exists(self.__name):
                self.__act_size = os.path.getsize(self.__name)
            else:
                self.__act_size = 0
            self.__handle = file(self.__name, "a+")
            try:
                os.chmod(self.__name, 0640)
            except:
                pass
        except:
            self.__handle = None
    def check_for_temp_close(self):
        if abs(time.time() - self.__last_write) > self.__temporary_close_timeout and not self.__temporary_closed and self.__handle:
            self.__temporary_closed = True
            self.__handle.close()
            tc = True
        else:
            tc = False
        return tc
    def write_header(self):
        if self.__handle:
            self.write("starting at %s" % (time.ctime(time.time())))
        elif self.__stdout:
            print "starting at %s" % (time.ctime(time.time()))
    def write_footer(self):
        if self.__handle:
            self.write("wrote %d lines" % (self.__lines))
        elif self.__stdout:
            print "wrote %d lines" % (self.__lines)
    def write(self, what, header=1, log_time=None):
        if self.__temporary_closed:
            self._open()
        self.__last_write = time.time()
        if not self.__stdout:
            if self.__last_line and self.__last_line == what:
                self.__repeated += 1
                if self.__repeated >= self.__max_repeat:
                    what_list = ["last message repeated %s" % (get_plural("time", self.__repeated))]
                    self.__repeated = 0
                else:
                    what_list = []
            else:
                if self.__repeated:
                    what_list = ["last message repeated %s" % (get_plural("time", self.__repeated)), what]
                    self.__repeated = 0
                else:
                    what_list = [what]
        else:
            what_list = [what]
        if what_list:
            self.__last_line = what
            for what in what_list:
                if header:
                    if not log_time:
                        log_time = time.time()
                    out_str = "%s : %s" % (time.ctime(log_time), what)
                else:
                    out_str = what
                if self.__stdout:
                    print out_str
                else:
                    if self.__handle:
                        try:
                            self.__handle.write("%s\n" % (out_str))
                        except:
                            my_syslog(out_str)
                        self.__lines += 1
                        self.__act_size += len(out_str) + 1
                    else:
                        my_syslog(what)
            if self.__handle:
                if self.__act_size > self.__max_size:
                    act_time = time.localtime()
                    base_postfix = "%04d%02d%02d" % (act_time[0], act_time[1], act_time[2])
                    if self.__last_postfix == base_postfix:
                        self.__act_index += 1
                    else:
                        self.__act_index = 0
                    self.__last_postfix = base_postfix
                    act_postfix = "%s%d" % (base_postfix, self.__act_index)
                    if bz2:
                        gz_postfix = "bz2"
                    else:
                        gz_postfix = "gz"
                    gz_file_name = "%s-%s.%s" % (self.__name,
                                                 act_postfix,
                                                 gz_postfix)
                    try:
                        if bz2:
                            act_z = bz2.BZ2File(gz_file_name, "w")
                        else:
                            act_z = gzip.open(gz_file_name, "wb", 4)
                    except:
                        exc_info = sys.exc_info()
                        my_syslog("error opening %s: %s, %s" % (gz_file_name,
                                                                str(exc_info[0]),
                                                                str(exc_info[1])))
                    else:
                        self.__handle.seek(0, 0)
                        act_z.write(self.__handle.read())
                        act_z.close()
                        os.chmod(gz_file_name, 0640)
                        self.__handle.close()
                        os.unlink(self.__name)
                        self.__handle = file(self.__name, "a+")
                        os.chmod(self.__name, 0640)
                        self.__act_size = 0
                else:
                    try:
                        self.__handle.flush()
                    except:
                        pass
    def close(self, footer=0):
        if footer:
            self.write_footer()
        if self.__handle:
            self.__handle.close()
    def __del__(self):
        self.close(0)

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
                    act_str = "%s%s" % (act_str, in_c)
                else:
                    act_str = act_str.strip()
                    if act_str:
                        act_list.append(act_str)
                    act_str = ""
            else:
                if in_c == "(":
                    if in_count == max_count:
                        raise ValueError, "already in parentheses_mode (%s) ..." % (in_str)
                    if in_count > 1:
                        act_str = "%s%s" % (act_str, in_c)
                    in_count += 1
                elif in_c == ")":
                    if not in_count:
                        raise ValueError, "not in parentheses_mode ..."
                    in_count -= 1
                    if not in_count:
                        act_str = "%s%s" % (act_str, in_c)
                act_str = "%s%s" % (act_str, in_c)
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
                raise ValueError, "need semikolon, error ..."
            elif in_c == ";" and not struct_count and need_semi:
                pre_parts = pre_str.split()
                com = pre_parts.pop(0)
                if com in mc_list:
                    name = pre_parts.pop(0)
                    key_str = (com, name)
                else:
                    key_str = com
                s_list.append((key_str, in_str.strip()))
                #print "got struct %s(%s)" % (str(key_str), in_str)
                need_semi = False
                pre_str = ""
                in_str = ""
            else:
                if in_c == str_start:
                    if struct_count == max_struct:
                        raise ValueError, "already in structure, error ..."
                    struct_count += 1
                    if struct_count > 1:
                        in_str = "%s%s" % (in_str, in_c)
                elif in_c == str_end:
                    if not struct_count:
                        raise ValueError, "not in structure, error ..."
                    # now we need a semikolon
                    struct_count -= 1
                    if not struct_count:
                        need_semi = True
                        pre_str = pre_str.strip()
                        in_str = in_str.strip()
                    else:
                        in_str = "%s%s" % (in_str, in_c)
                else:
                    if struct_count:
                        in_str = "%s%s" % (in_str, in_c)
                    else:
                        pre_str = "%s%s" % (pre_str, in_c)
        return s_list
    def is_string(self, in_str):
        return type(in_str) == type("") and in_str[0] == in_str[-1] and in_str[0] in ["'", '"']
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
            raise ValueError, "__destination to long (%d)" % (len(d_list))
        elif d_list:
            self.__type, self.__args = d_list[0]
            self.__args = self._split_str(self.__args)
    def __repr__(self):
        return "%s %s, %s" % ("destination", self.__type, " ".join(self.__args))
    def get_conf_str(self):
        return " "

class syslog_ng_source(syslog_helper_obj):
    def __init__(self, in_str):
        syslog_helper_obj.__init__(self)
        self.__sources = dict([(key, self._split_str(value)) for key, value in self._parse_stream(in_str, [], "(")])
    def get_dict(self):
        return self.__sources
    def __repr__(self):
        return "%s %s" % ("source", " ".join(["%s(%s)" % (x, " ".join(y)) for x, y in self.__sources.iteritems()]))
    def get_conf_str(self):
        return " "

class syslog_ng_filter(syslog_helper_obj):
    def __init__(self, in_str):
        syslog_helper_obj.__init__(self)
        self.__filter_list = self._split_str(in_str, 4)
    def __repr__(self):
        return "%s %s" % ("filter", " ".join(self.__filter_list))
    def get_conf_str(self):
        #print "XXX", self.__filter_list
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
                raise KeyError, "unknown key %s" % (key)
        if not o_dict["source"]:
            raise ValueError, "need at least one source"
        elif not o_dict["destination"]:
            raise ValueError, "need at least one destination"
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
            if type(key) == type(()):
                key, name = key
            if key in self.__multi_commands.keys():
                self.__multi_objects[key][name] = self.__multi_commands[key](value)
            elif key == "log":
                self.__log_list.append(syslog_ng_log(value))
            elif key == "options":
                self.__options = dict([(k, value) for k, value in self._parse_stream(value, [], "(")])
            else:
                raise KeyError, "unknown key %s (%s)" % (key, str(value))
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
        #pprint.pprint(s_dict)

def main():
    a = syslog_ng_config()
    #print a.get_dict_sort(a.get_multi_object("source"))
    print "\n".join(a.get_config_lines())
    sys.exit(0)
##     a = form_list()
##     a.add_line([2,3,4])
##     a.add_line([2,34])
##     a.add_line(["aiopduqwoeuqwie",34])
##     a.set_format_string(0, "s", "")
##     print a
##     a = logfile("/tmp/lf", 10000, 100, 1)
##     a.write("test")
##     time.sleep(2)
##     print a.check_for_temp_close()
##     a.write("test2")
##     a.close()
    
if __name__ == "__main__":
    main()
    print "Loadable module, exiting..."
    sys.exit(0)
