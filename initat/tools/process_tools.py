# -*- coding: utf-8 -*-
#
# Copyright (c) 2001-2007,2009-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of python-modules-base
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; Version 3 of the License
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
""" various tools to handle processes and stuff """

import atexit
import base64
import bz2
import grp
import inspect
import json
import marshal
import os
import pickle
import platform
import pwd
import random
import re
import socket
import stat
import subprocess
import sys
import threading
import time
import traceback

import six
from lxml import etree
from lxml.builder import E

from initat.tools import logging_tools

from initat.constants import META_SERVER_DIR

if os.path.exists("/proc/stat"):
    try:
        import psutil
    except (NotImplementedError, ImportError, IOError):
        # handle chrooted calls
        print("cannot import psutil, running chrooted ? setting psutil to None")
        psutil = None
else:
    psutil = None

RUN_DIR = "/var/run"


def safe_unicode(obj):
    """Return the unicode/text representation of `obj` without throwing UnicodeDecodeError

    Returned value is only a *representation*, not necessarily identical.
    """
    if isinstance(obj, list):
        return [safe_unicode(_entry) for _entry in obj]
    else:
        if type(obj) not in (six.text_type, six.binary_type):
            obj = six.text_type(obj)
        if type(obj) is six.text_type:
            return obj
        else:
            return obj.decode(errors='ignore')


def compress_struct(input):
    return base64.b64encode(bz2.compress(json.dumps(input)))


def decompress_struct(b64_str, version=2):
    if version == 2:
        return json.loads(bz2.decompress((base64.b64decode(b64_str))))
    elif version == 1:
        return marshal.loads(bz2.decompress(base64.b64decode(b64_str)))
    else:
        raise ValueError("unknown version {} for decompress_struct".format(version))


def getstatusoutput(cmd):
    return subprocess.getstatusoutput(cmd)


# net to sys and reverse functions
def net_to_sys(in_val):
    try:
        result = pickle.loads(in_val)
    except:
        try:
            result = marshal.loads(in_val)
        except:
            raise ValueError
    return result


def sys_to_net(in_val):
    return pickle.dumps(in_val)


def get_except_info(exc_info=None, **kwargs):
    if not exc_info:
        exc_info = sys.exc_info()
    frame_info = []
    if kwargs.get("frame_info", False):
        fr_idx = 0
        while True:
            try:
                frame_info.append(sys._getframe(fr_idx))
            except:
                break
            else:
                fr_idx += 1
        frame_info.reverse()
        try:
            frame_info = [
                "line {:d}, {} in {}".format(
                    frame.f_lineno,
                    frame.f_code.co_name,
                    frame.f_code.co_filename
                ) for frame in frame_info
            ]
        except:
            frame_info = []
    # print frame.f_lineno, frame.f_code.co_name
    _exc_list = exc_info[1]
    exc_name = _exc_list.__class__.__name__
    if exc_name in ["ValidationError"]:
        # special handling of Django ValidationErrors
        _result = []
        if type(_exc_list) is dict:
            _result = [
                "{}: {}".format(_key, ", ".join(_values)) for _key, _values in _exc_list.items()
            ]
        else:
            if hasattr(_exc_list, "messages"):
                _result.extend(_exc_list.messages)
        _exc_list = ", ".join(_result)
    elif hasattr(_exc_list, "message"):
        _exc_list = _exc_list.message
    return "{} ({}{})".format(
        safe_unicode(exc_info[0]),
        safe_unicode(_exc_list),
        ", {}".format(", ".join(frame_info)) if frame_info else ""
    )


class exception_info(object):
    def __init__(self, **kwargs):
        self.thread_name = threading.currentThread().getName()
        self.except_info = kwargs.get("exc_info", sys.exc_info())
        tb_object = self.except_info[2]
        exc_type = str(self.except_info[0]).split(".")[-1].split("'")[0]
        self.log_lines = [
            "caught exception {} ({}), traceback follows:".format(
                exc_type,
                get_except_info(self.except_info)
            ),
            "exception in process/thread '{}'".format(self.thread_name)
        ]
        for file_name, line_no, name, line in traceback.extract_tb(tb_object):
            self.log_lines.append("File '{}', line {:d}, in {}".format(file_name, line_no, name))
            if line:
                self.log_lines.append(" - {:d} : {}".format(line_no, line))
        self.log_lines.append(get_except_info(self.except_info))


def call_command(act_command, log_com, close_fds=False, log_stdout=True):
    log_com("calling command '{}'".format(act_command))
    s_time = time.time()
    try:
        _sub = subprocess.Popen(act_command.strip().split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=close_fds, cwd="/")
    except:
        ret_code = 1
        _stdout, _stderr = ("", get_except_info())
    else:
        ret_code = _sub.wait()
        _stdout, _stderr = _sub.communicate()
    e_time = time.time()
    log_com(
        "execution took {}, return code was {:d}".format(
            logging_tools.get_diff_time_str(e_time - s_time),
            ret_code,
        )
    )
    for _val, _name, _lev in [
        (_stdout, "stdout", logging_tools.LOG_LEVEL_OK),
        (_stderr, "stderr", logging_tools.LOG_LEVEL_ERROR)
    ]:
        if _val.strip():
            _lines = _val.decode("utf-8").split("\n")
            log_com("{} has {} ({})".format(_name, logging_tools.get_plural("byte", len(_val)), logging_tools.get_plural("line", len(_lines))))
            if log_stdout:
                for _line_num, _line in enumerate(_lines):
                    log_com(" {:3d} : {}".format(_line_num + 1, _line), _lev)
        else:
            if log_stdout:
                log_com("{} is empty".format(_name))
    return ret_code, _stdout, _stderr


def get_socket(context, r_type, **kwargs):
    import zmq
    _sock = context.socket(getattr(zmq, r_type))
    # DEALER from grapher/server.py
    if r_type in ["ROUTER", "DEALER"]:
        _sock.setsockopt_string(zmq.IDENTITY, kwargs["identity"])
    if r_type in ["ROUTER"]:
        _sock.setsockopt(zmq.ROUTER_MANDATORY, 1)
    for _opt, _value in [
        ("LINGER", kwargs.get("linger", 100)),
        ("SNDHWM", kwargs.get("sndhwm", 256)),
        ("RCVHWM", kwargs.get("rcvhwm", 256)),
        ("SNDTIMEO", 500),
        ("BACKLOG", kwargs.get("backlog", 1)),
        ("TCP_KEEPALIVE", 1),
        ("TCP_KEEPALIVE_IDLE", 300),
        ("RECONNECT_IVL_MAX", kwargs.get("reconnect_ivl_max", 500)),
        ("RECONNECT_IVL", kwargs.get("reconnect_ivl", 200)),
    ]:
        _sock.setsockopt(getattr(zmq, _opt), _value)
    if kwargs.get("immediate", False):
        _sock.setsockopt(getattr(zmq, "IMMEDIATE"), True)
    return _sock


def zmq_identity_str(id_string, short=False):
    if short:
        # without pid
        return "{}:{}".format(
            get_machine_name(),
            id_string,
        )
    else:
        return "{}:{}:{:d}".format(
            get_machine_name(),
            id_string,
            os.getpid()
        )


def remove_zmq_dirs(dir_name):
    for cur_dir, dir_names, _file_names in os.walk(dir_name, topdown=False):
        for c_dir in dir_names:
            try:
                os.rmdir(os.path.join(cur_dir, c_dir))
            except:
                pass
    try:
        os.rmdir(dir_name)
    except:
        pass

LOCAL_ZMQ_DIR = "/var/run/icsw/zmq/.zmq_{:d}:{:d}".format(
    os.getuid(),
    os.getpid(),
)

LOCAL_ROOT_ZMQ_DIR = "/var/run/icsw/sockets"
INIT_ZMQ_DIR_PID = "{:d}".format(os.getpid())
ALLOW_MULTIPLE_INSTANCES = True


def get_zmq_ipc_name(name, **kwargs):
    if "s_name" in kwargs:
        s_name = kwargs["s_name"]
    else:

        # debug code
        # open("/tmp/frame_info", "a").write("---------\n")
        # for _frame in inspect.getouterframes(inspect.currentframe()):
        #     open("/tmp/frame_info", "a").write(os.path.basename(_frame[1]) + "\n")

        outest_frame = inspect.getouterframes(inspect.currentframe())[-1]
        s_name = os.path.basename(outest_frame[1])
        s_name = s_name.replace("-", "_").replace("__", "_").replace("__", "_")
        if s_name.endswith(".py"):
            s_name = s_name[:-3]
        if s_name.endswith("_zmq"):
            s_name = s_name[:-4]
    # flag: connect to root instance
    ctri = kwargs.get("connect_to_root_instance", False)
    # print __name__, globals()
    if os.getuid() and not ctri:
        # non-root call
        root_dir = LOCAL_ZMQ_DIR
        _root_base = os.path.dirname(root_dir)
        if not os.path.isdir(_root_base):
            os.mkdir(_root_base)
            os.chmod(_root_base, 0o01777)
        atexit.register(remove_zmq_dirs, root_dir)
    else:
        if ALLOW_MULTIPLE_INSTANCES and not ctri:
            root_dir = os.path.join(LOCAL_ROOT_ZMQ_DIR, INIT_ZMQ_DIR_PID)
            atexit.register(remove_zmq_dirs, root_dir)
        else:
            root_dir = LOCAL_ROOT_ZMQ_DIR
    if not os.path.isdir(root_dir):
        os.mkdir(root_dir)
    sub_dir = os.path.join(root_dir, s_name)
    if not os.getuid():
        atexit.register(remove_zmq_dirs, sub_dir)
    if not os.path.isdir(sub_dir):
        os.mkdir(sub_dir)
    _name = "ipc://{}/{}".format(
        sub_dir,
        name
    )
    return _name


def bind_zmq_socket(zmq_socket, name):
    if name.startswith("ipc://"):
        s_name = name[6:]
        if os.path.exists(s_name):
            try:
                os.unlink(s_name)
            except:
                logging_tools.my_syslog(
                    "error removing zmq_socket '{}': {}".format(
                        s_name,
                        get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
    try:
        zmq_socket.bind(name)
    except:
        logging_tools.my_syslog(
            "error binding to zmq_socket '{}': {}".format(
                name,
                get_except_info()
            )
        )
        raise
    else:
        logging_tools.my_syslog("zmq_socket bound to {}".format(name))


def submit_at_command(com, diff_time=0, as_root=False):
    pre_time_str = "now"
    diff_time_str = diff_time and "+{:d} minutes".format(diff_time) or ""
    time_str = "{}{}".format(pre_time_str, diff_time_str)
    if as_root and os.getuid():
        _esc = "sudo "
    else:
        _esc = ""
    cstat, cout = getstatusoutput(
        "echo {} | {} /usr/bin/at {}".format(
            com,
            _esc,
            time_str))
    log_f = [
        "Starting command '{}' at time '{}' resulted in stat {:d}".format(
            com,
            time_str,
            cstat
        )
    ]
    for out_l in cout.split("\n"):
        log_f.append(" - {}".format(out_l))
    return cstat, log_f

if psutil is not None:
    PROC_STATUSES = {
        "R": psutil.STATUS_RUNNING,
        "S": psutil.STATUS_SLEEPING,
        "D": psutil.STATUS_DISK_SLEEP,
        "T": psutil.STATUS_STOPPED,
        "t": psutil.STATUS_TRACING_STOP,
        "Z": psutil.STATUS_ZOMBIE,
        "X": psutil.STATUS_DEAD,
        "W": psutil.STATUS_WAKING
    }

    PROC_INFO_DICT = {
        psutil.STATUS_RUNNING: "number of running processes",
        psutil.STATUS_ZOMBIE: "number of zombie processes",
        psutil.STATUS_DISK_SLEEP: "processes in uninterruptable sleep",
        psutil.STATUS_STOPPED: "processes stopped",
        psutil.STATUS_TRACING_STOP: "processes traced",
        psutil.STATUS_SLEEPING: "processes sleeping",
        psutil.STATUS_WAKING: "processes waking",
        psutil.STATUS_DEAD: "processes dead",
    }

    PROC_STATUSES_REV = {value: key for key, value in PROC_STATUSES.items()}


def get_mem_info(pid=0, **kwargs):
    if not pid:
        pid = os.getpid()
    if type(pid) not in [list, set]:
        pid = [pid]
    ps_list = []
    for cur_pid in pid:
        try:
            _proc = psutil.Process(cur_pid)
            # print(_proc.name())
            # only count RSS (resident set size)
            # ps_list.append(_proc.memory_info()[0])
            _mi = _proc.memory_info_ex()
            # count rss minus shared
            ps_list.append(_mi.rss - _mi.shared)
        except:
            # ignore missing process
            pass
        else:
            pass
    return sum(ps_list)


def get_stat_info(pid=0):
    if not pid:
        pid = os.getpid()
    stat_file_name = "/proc/{:d}/stat".format(pid)
    stat_dict = {}
    if os.path.isfile(stat_file_name):
        try:
            stat_line = open(stat_file_name, "r").read().strip()
        except:
            pass
        else:
            stat_dict = _build_stat_dict(stat_line)
    return stat_dict


def _build_stat_dict(content):
    # parse stat_line
    pid_part, rest_part = [part.strip() for part in content.split("(", 1)]
    # handle more than one closing parentheses
    s_parts = rest_part.split(")")
    rest_part = s_parts.pop(-1).strip()
    com_part = (")".join(s_parts)).strip()
    stat_parts = rest_part.split()
    stat_keys = [
        "state*", "ppid", "pgrp", "session",
        "tty_nr", "tpgid", "flags",
        "minflt", "cminflt", "maxflt", "cmaxflt",
        "utime", "stime", "cutime", "cstime",
        "priority", "nice", "num_threads",
        "itrealvalue", "starttime",
        "vsize", "rss", "rlim"
    ]
    stat_dict = {
        key.replace("*", ""): value if key.endswith("*") else int(value) for key, value in zip(stat_keys, stat_parts)
    }
    stat_dict["pid"] = int(pid_part)
    stat_dict["comm"] = com_part
    return stat_dict


def beautify_mem_info(mi=None, short=False):
    bs = "B" if short else "Bytes"
    if mi is None:
        mi = get_mem_info()
    if mi < 1024:
        return "{:d} {}".format(mi, bs)
    elif mi < 1024 * 1024:
        return "{:.2f} k{}".format(mi / 1024., bs)
    elif mi < 1024 * 1024 * 1024:
        return "{:.2f} M{}".format(mi / (1024. * 1024.), bs)
    else:
        return "{:.2f} G{}".format(mi / (1024. * 1024. * 1024.), bs)


class error(Exception):
    def __init__(self, value=None):
        Exception.__init__(self)
        self.value = value

    def __str__(self):
        return self.value


class int_error(error):
    def __init__(self):
        error.__init__(self)


class MSIBlock(object):
    def __init__(self, name, log_com=None):
        self.__log_com = log_com
        self._reset()
        if name.startswith("/"):
            parsed = self._parse_file(name)
            if not parsed:
                # unparseable, set name to None
                name = None
        else:
            parsed = False
        if parsed:
            pass
        else:
            self.__start_time = time.time()
            self.__name = name
        self.parsed = parsed
        self.file_init_time = time.time()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        if self.__log_com:
            self.__log_com("[MSI] {}".format(what), log_level)
        else:
            logging_tools.my_syslog(what)

    def _reset(self):
        self.__pids = set()
        self.__pid_names = {}
        self.__pid_proc_names = {}
        # when the MSI-block was startet (== main process start)
        self.__start_time = {}

    def _parse_file(self, name):
        # try to read complete info from file
        self.__name = None
        try:
            xml_struct = etree.fromstring(open(name, "r").read())
        except:
            self.log(
                "error parsing XML file {} (MSIBlock): {}".format(
                    name,
                    get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            parsed = False
        else:
            self.__name = xml_struct.xpath(".//name/text()", smart_strings=False)[0]
            _start_time = xml_struct.find(".//start_time")
            if _start_time is None:
                self.__start_time = os.stat(name)[stat.ST_CTIME]
            else:
                self.__start_time = int(float(_start_time.text))
            # reads pids
            for cur_idx, pid_struct in enumerate(xml_struct.xpath(".//pid_list/pid", smart_strings=False)):
                self.__pids.add(int(pid_struct.text))
                self.__pid_names[int(pid_struct.text)] = pid_struct.get("name", "proc{:d}".format(cur_idx + 1))
                self.__pid_proc_names[int(pid_struct.text)] = pid_struct.get("proc_name", "")
            parsed = True
        return parsed

    @staticmethod
    def path_name(name):
        return os.path.join(META_SERVER_DIR, name)

    @property
    def file_name(self):
        return self.path_name(self.__name)

    @property
    def name(self):
        return self.__name

    @property
    def start_time(self):
        return self.__start_time

    def file_init_time_get(self):
        return self.__file_init_time

    def file_init_time_set(self, fi_time):
        self.__file_init_time = fi_time
    file_init_time = property(file_init_time_get, file_init_time_set)

    def exe_name_get(self):
        return self.__exe_name

    def exe_name_set(self, en):
        self.__exe_name = en
    exe_name = property(exe_name_get, exe_name_set)

    def add_actual_pid(self, act_pid=None, process_name=""):
        if not act_pid:
            act_pid = os.getpid()
        try:
            _ps_name = psutil.Process(pid=act_pid).name()
        except:
            self.log(
                "cannot get name of process {:d} :{}".format(
                    act_pid,
                    get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            _ps_name = ""
        self.__pids.add(act_pid)
        if not process_name:
            process_name = "proc{:d}".format(len(self.__pid_names) + 1)
        self.__pid_names[act_pid] = process_name
        self.__pid_proc_names[act_pid] = _ps_name

    def remove_actual_pid(self, act_pid=None):
        if not act_pid:
            act_pid = os.getpid()
        self.__pids.remove(act_pid)

    def get_pids(self, process_name=None, name=None):
        pid_list = self.__pids
        if process_name is None:
            pass
        else:
            if set(self.__pid_proc_names.values()) == set([""]):
                # no process names set, return all pids
                pass
            else:
                pid_list = [_pid for _pid in pid_list if self.__pid_proc_names[_pid] == process_name]
        if name is not None:
            pid_list = [_pid for _pid in pid_list if self.__pid_names.get(_pid, "???") == name]
        # get parent processes
        _parent_pids = []
        for _pid in pid_list:
            try:
                _parent_pid = psutil.Process(_pid).parent().pid
            except psutil.NoSuchProcess:
                pass
            else:
                _parent_pids.append((_pid, _parent_pid))
        # WTF ? removed to signal main process with SIGHUP (ALN, 20141014)
        # pid_list = [_pid for _pid, _parent in _parent_pids if _parent in pid_list or _parent == 1]
        return pid_list

    def set_pids(self, in_pids):
        self.__pids = set(in_pids)
    pids = property(get_pids, set_pids)

    def get_unique_pids(self):
        return set(self.__pids)

    def get_process_name(self, pid):
        return self.__pid_names[pid]

    def get_sys_process_name(self, pid):
        return self.__pid_proc_names[pid]

    def get_info(self):
        pid_dict = {pid: 1 for pid in self.__pids}
        all_pids = sorted(pid_dict.keys())
        return "{}: {}".format(
            logging_tools.get_plural("pid", len(all_pids)),
            all_pids and ", ".join(["{:d}".format(pid) for pid in all_pids]) or "---"
        )

    def save_block(self):
        return self.save()

    def save(self):
        pid_list = E.pid_list()
        for cur_pid in sorted(self.__pids):
            cur_pid_el = E.pid(
                "{:d}".format(cur_pid),
                name=self.__pid_names[cur_pid],
                proc_name=self.__pid_proc_names[cur_pid]
            )
            pid_list.append(cur_pid_el)
        xml_struct = E.meta_info(
            E.name(self.__name),
            E.start_time("{:d}".format(int(self.__start_time))),
            pid_list,
        )
        file_content = etree.tostring(xml_struct, pretty_print=True, encoding="unicode")
        path_name = self.path_name(self.__name)
        try:
            open(path_name, "w").write(file_content)
        except:
            self.log(
                "error writing file {} (MSIBlock for {})".format(
                    path_name,
                    self.__name
                ),
                logging_tools.LOG_LEVEL_ERROR
            )

    def __eq__(self, other):
        return self.__name == other.name and sorted(list(self.__pids)) == sorted(list(other.get_pids()))

    def __ne__(self, other):
        return self.__name != other.name or sorted(list(self.__pids)) != sorted(list(other.get_pids()))

    def remove_meta_block(self):
        return self.remove()

    def remove(self):
        path_name = self.path_name(self.__name)
        try:
            os.unlink(path_name)
        except:
            self.log(
                "error removing file {} (MSIBlock for {}): {}".format(
                    path_name,
                    self.__name,
                    get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )

    def get_main_pid(self):
        main_pids = [_key for _key, _value in self.__pid_names.items() if _value == "main"]
        if main_pids:
            return main_pids[0]
        else:
            return None

    def check_block(self, act_dict={}):
        if not act_dict:
            act_dict = get_proc_list()
        self.__pids_found = {}
        # print "*", self.__pids
        for cur_pid in self.__pids:
            # print cur_pid, cur_pid in act_dict
            if cur_pid in act_dict:
                try:
                    _stat = act_dict[cur_pid].status().lower()
                    if _stat not in ["zombie", "dead"]:
                        # check for correct name
                        if act_dict[cur_pid].name() == self.__pid_proc_names.get(cur_pid, ""):
                            self.__pids_found[cur_pid] = 1
                        else:
                            # process found but wrong name
                            pass
                except psutil.NoSuchProcess:
                    pass
        self.pids_found = [cur_pid for cur_pid in self.__pids_found.keys() if cur_pid in act_dict]
        bound_dict = {}
        missing_list = []
        for unique_pid in set(self.__pids_found.keys()) | set(self.__pids):
            if unique_pid not in self.__pids_found:
                missing_list.append(unique_pid)
                bound_dict[unique_pid] = -1
            elif unique_pid not in self.__pids:
                bound_dict[unique_pid] = 1
            else:
                bound_dict[unique_pid] = 0
        self.missing_list = missing_list
        self.bound_dict = bound_dict
        if any([value != 0 for value in bound_dict.values()]):
            _ok = False
        else:
            if not self.__pids_found:
                _ok = False
            elif any([value > 0 for value in bound_dict.values()]):
                _ok = False
            else:
                _ok = True
        return _ok

    def pid_check_string(self, proc_dict):
        def _get_mis_info(cur_pid):
            if cur_pid in self.missing_list:
                return "missing"
            elif self.bound_dict[cur_pid]:
                return "{:d} {}, {:d} found)".format(
                    abs(self.bound_dict[cur_pid]),
                    "missing" if self.bound_dict[cur_pid] < 0 else "too much",
                    self.__pids_found.get(cur_pid, 0),
                )
            else:
                return "OK"

        def _get_name(cur_pid):
            return _pid_dict.get(cur_pid, {}).get("name", "unknown")
        # proc_dict is from threading_tools.get_info_dict
        # map
        _pid_dict = {_value["pid"]: _value for _key, _value in proc_dict.items()}
        _p_list = [
            "{}@{:d}: {}".format(
                _get_name(cur_pid),
                cur_pid,
                _get_mis_info(cur_pid),
            ) for cur_pid in sorted(self.bound_dict.keys())
        ]
        if _p_list:
            return "{}: {}".format(
                logging_tools.get_plural("process", len(_p_list)),
                ", ".join(_p_list),
            )
        else:
            return "no processes"

    def kill_all_found_pids(self):
        all_pids = sorted(self.__pids_found.keys())
        if all_pids:
            ok_pids, error_pids = ([], [])
            for pid in all_pids:
                try:
                    os.kill(pid, 9)
                except:
                    error_pids += [pid]
                else:
                    ok_pids += [pid]
            return "{} to kill ({}); ok: {}, error: {}".format(
                logging_tools.get_plural("pid", len(all_pids)),
                ", ".join(["{:d}".format(cur_pid) for cur_pid in all_pids]),
                ok_pids and "{} ({})".format(
                    logging_tools.get_plural("pid", len(ok_pids)),
                    ", ".join(["{:d}".format(cur_pid) for cur_pid in ok_pids])
                ) or "---",
                error_pids and "{} ({})".format(
                    logging_tools.get_plural("pid", len(error_pids)),
                    ", ".join(["{:d}".format(cur_pid) for cur_pid in error_pids])
                ) or "---"
            )
        else:
            return "no pids to kill"


class cached_file(object):
    def __init__(self, name, **kwargs):
        self.__name = name
        self.__log_handle = kwargs.get("log_handle", None)
        self.__cache_time = kwargs.get("cache_time", 3600)
        self.__last_stat, self.__last_update = (None, None)
        self.update()

    @property
    def name(self):
        return self.__name

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        if self.__log_handle:
            self.__log_handle(what, log_level)
        else:
            logging_tools.my_syslog(what, log_level)

    def changed(self):
        pass

    def update(self):
        if os.path.exists(self.__name):
            try:
                act_stat = os.stat(self.__name)
            except:
                self.log(
                    "error stating() {}: {}".format(
                        self.__name,
                        get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
                self.content = None
                self.changed()
            else:
                update, act_time = (True, time.time())
                if self.__last_stat and self.__last_update:
                    if self.__last_stat[stat.ST_MTIME] == act_stat[stat.ST_MTIME] and abs(self.__last_update - act_time) < self.__cache_time:
                        update = False
                if update:
                    self.__last_stat, self.__last_update = (act_stat, act_time)
                    try:
                        content = open(self.__name, "r").read()
                    except:
                        self.log(
                            "error reading from {}: {}".format(
                                self.__name,
                                get_except_info()
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                        self.content = None
                    else:
                        self.content = content
                    self.changed()
        else:
            self.log("file '{}' does not exist".format(self.__name), logging_tools.LOG_LEVEL_ERROR)
            self.content = None
            self.changed()


def save_pid(name, pid=None):
    return append_pids(name, pid=pid, mode="w")

save_pids = save_pid


def append_pids(name, pid=None, mode="a"):
    if pid is None:
        actp = [os.getpid()]
    else:
        if type(pid) in [int, int]:
            actp = [pid]
        elif isinstance(pid, str):
            actp = [int(pid)]
        else:
            actp = pid
    if name.startswith("/"):
        fname = name
    else:
        fname = os.path.join(RUN_DIR, name)
        if not fname.endswith(".pid"):
            fname = "{}.pid".format(fname)
    dir_name = os.path.dirname(fname)
    if not os.path.isdir(dir_name):
        try:
            os.makedirs(dir_name)
        except:
            pass
    long_mode = {
        "a": "appending",
        "w": "writing",
    }[mode]
    try:
        open(fname, mode).write(
            "\n".join(
                [
                    "{:d}".format(cur_p) for cur_p in actp
                ] + [
                    ""
                ]
            )
        )
    except:
        logging_tools.my_syslog(
            "error {} {} ({}) to {}: {}".format(
                long_mode,
                logging_tools.get_plural("pid", len(actp)),
                ", ".join(["{:d}".format(line) for line in actp]), fname,
                get_except_info()
            )
        )
    else:
        try:
            os.chmod(fname, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
        except:
            logging_tools.my_syslog(
                "error changing mode of {} to 0644: {}".format(
                    fname,
                    get_except_info()
                )
            )


def remove_pids(name, pid=None):
    if pid is None:
        actp = [os.getpid()]
    else:
        if type(pid) in [int, int]:
            actp = [pid]
        elif isinstance(pid, str):
            actp = [int(pid)]
        else:
            actp = pid
    if name.startswith("/"):
        fname = name
    else:
        if not name.endswith(".pid"):
            name = "{}.pid".format(name)
        fname = os.path.join(RUN_DIR, name)
    if os.path.isfile(fname):
        try:
            pid_lines = [entry.strip() for entry in open(fname, "r").read().split("\n")]
        except:
            logging_tools.my_syslog("error interpreting file: {}".format(get_except_info()))
        else:
            for del_pid in actp:
                num_removed = 0
                new_lines = []
                for line in pid_lines:
                    if line == str(del_pid):
                        num_removed += 1
                    else:
                        new_lines.append(line)
                pid_lines = new_lines
            try:
                open(fname, "w").write("\n".join(pid_lines))
                os.chmod(fname, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
            except:
                logging_tools.my_syslog(
                    "error removing {:d} pids ({}) to {}".format(
                        len(actp),
                        ",".join(["{:d}".format(line) for line in actp]),
                        fname
                    )
                )
    else:
        logging_tools.my_syslog("pidfile {} does not exist".format(fname))


def delete_pid(name):
    if name.startswith("/"):
        fname = name
    else:
        fname = "{}.pid".format(os.path.join(RUN_DIR, name))
    if os.path.isfile(fname):
        try:
            os.unlink(fname)
        except:
            pass


def get_uid_from_name(user):
    try:
        if type(user) in [int, int]:
            uid_stuff = pwd.getpwuid(user)
        else:
            uid_stuff = pwd.getpwnam(user)
        new_uid, new_uid_name = (uid_stuff[2], uid_stuff[0])
    except KeyError:
        new_uid, new_uid_name = (0, "root")
        logging_tools.my_syslog("Cannot find user '{}', using {} ({:d})".format(user, new_uid_name, new_uid))
    return new_uid, new_uid_name


def get_gid_from_name(group):
    try:
        if type(group) in [int, int]:
            gid_stuff = grp.getgrgid(group)
        else:
            gid_stuff = grp.getgrnam(group)
        new_gid, new_gid_name = (gid_stuff[2], gid_stuff[0])
    except KeyError:
        new_gid, new_gid_name = (0, "root")
        logging_tools.my_syslog("Cannot find group '{}', using {} ({:d})".format(group, new_gid_name, new_gid))
    return new_gid, new_gid_name


def change_user_group_path(path, user, group, **kwargs):
    if "log_com" in kwargs:
        log_com = kwargs["log_com"]
    else:
        log_com = logging_tools.my_syslog
    try:
        if type(user) in [int, int]:
            uid_stuff = pwd.getpwuid(user)
        else:
            uid_stuff = pwd.getpwnam(user)
        new_uid, new_uid_name = (uid_stuff[2], uid_stuff[0])
    except KeyError:
        new_uid, new_uid_name = (0, "root")
        log_com("Cannot find user '{}', using {} ({:d})".format(user, new_uid_name, new_uid))
    try:
        if type(group) in [int, int]:
            gid_stuff = grp.getgrgid(group)
        else:
            gid_stuff = grp.getgrnam(group)
        new_gid, new_gid_name = (gid_stuff[2], gid_stuff[0])
    except KeyError:
        new_gid, new_gid_name = (0, "root")
        log_com("Cannot find group '{}', using {} ({:d})".format(group, new_gid_name, new_gid))
    ok = False
    if os.path.exists(path):
        act_uid, act_gid = (os.stat(path)[stat.ST_UID], os.stat(path)[stat.ST_GID])
        try:
            act_uid_name = pwd.getpwuid(act_uid)[0]
        except:
            act_uid_name = "<unknown>"
        try:
            act_gid_name = grp.getgrgid(act_gid)[0]
        except:
            act_gid_name = "<unknown>"
        log_com(
            "Trying to change path '{}' from [{} ({:d}), {} ({:d})] to [{} ({:d}), {} ({:d})] ...".format(
                path,
                act_uid_name,
                act_uid,
                act_gid_name,
                act_gid,
                new_uid_name,
                new_uid,
                new_gid_name,
                new_gid
            )
        )
        try:
            os.chown(path, new_uid, new_gid)
        except:
            pass
        else:
            ok = True
        log_com("  ... actual uid/gid of {} is now ({:d}/{:d}) ...".format(path, new_uid, new_gid))
    else:
        log_com("  ... path '{}' does not exist".format(path))
    return ok


def get_proc_list(**kwargs):
    attrs = kwargs.get("attrs", None)
    proc_name_list = set(kwargs.get("proc_name_list", []))
    p_dict = {}
    if attrs:
        for cur_proc in psutil.process_iter():
            try:
                p_dict[cur_proc.pid] = cur_proc.as_dict(attrs)
            except psutil.NoSuchProcess:
                pass
    else:
        if proc_name_list:
            for cur_proc in psutil.process_iter():
                try:
                    if cur_proc.name() in proc_name_list:
                        p_dict[cur_proc.pid] = cur_proc
                except psutil.NoSuchProcess:
                    pass
        else:
            for cur_proc in psutil.process_iter():
                p_dict[cur_proc.pid] = cur_proc
    return p_dict


def bpt_show_childs(in_dict, idx, start):
    print(" " * idx, start, in_dict[start]["name"])
    if in_dict[start]["childs"]:
        p_list = list(in_dict[start]["childs"].keys())
        for pid in p_list:
            bpt_show_childs(in_dict[start]["childs"], idx + 2, pid)


def build_ppid_list(p_dict, pid=None):
    if not pid:
        pid = os.getpid()
        ppid_list = []
    else:
        ppid_list = [pid]
    while pid in p_dict and p_dict[pid].ppid():
        pid = p_dict[pid].ppid()
        if pid:
            ppid_list.append(pid)
    return ppid_list


def build_kill_dict(name, exclude_list=[]):
    # process dict
    pdict = get_proc_list()
    # list of parent pids (up to init)
    ppl = build_ppid_list(pdict, os.getpid())
    kill_dict = {}
    for pid, p_struct in list(pdict.items()):
        try:
            if get_python_cmd(p_struct.cmdline()) == name and pid not in ppl and pid not in exclude_list:
                kill_dict[pid] = " ".join(p_struct.cmdline())
        except psutil.NoSuchProcess:
            # process has vanished, ignore
            pass
    return kill_dict


def get_python_cmd(cmdline):
    p_name = None
    for entry in cmdline:
        _base_exe = os.path.basename(entry)
        if _base_exe.startswith("python"):
            continue
        elif _base_exe.startswith("-"):
            continue
        elif _base_exe.endswith(".py"):
            p_name = _base_exe
            break
        else:
            break
    return p_name


def kill_running_processes(p_name=None, **kwargs):
    my_pid = os.getpid()
    log_lines = []
    exclude_pids = kwargs.get("exclude", [])
    kill_sig = kwargs.get("kill_signal", 9)
    if type(exclude_pids) != list:
        exclude_pids = [exclude_pids]
    if p_name is None:
        my_proc = psutil.Process(my_pid)
        p_name = get_python_cmd(my_proc.cmdline())
        if not p_name:
            log_lines.append("cannot extract process name from cmdline '{}'".format(" ".join(my_proc.cmdline())))
    if p_name:
        log_lines.append(
            "my_pid is {:d}, searching for process '{}' to kill, kill_signal is {:d}, exclude_list is {}".format(
                my_pid,
                p_name,
                kill_sig,
                "empty" if not exclude_pids else ", ".join(
                    [
                        "{:d}".format(exc_pid) for exc_pid in sorted(exclude_pids)
                    ]
                )
            )
        )
        kill_dict = build_kill_dict(p_name, exclude_pids)
        any_killed = False
        if kill_dict:
            for pid, name in list(kill_dict.items()):
                if name not in kwargs.get("ignore_names", []):
                    log_str = "{} ({:d}): Trying to kill pid {:d} ({}) with signal {:d} ...".format(
                        p_name,
                        my_pid,
                        pid,
                        name,
                        kill_sig
                    )
                    try:
                        # print log_str
                        os.kill(pid, kill_sig)
                        pass
                    except:
                        log_lines.append("{} error ({})".format(log_str, get_except_info()))
                    else:
                        log_lines.append("{} ok".format(log_str))
                        any_killed = True
        else:
            log_lines[-1] = "{}, nothing to do".format(log_lines[-1])
        wait_time = kwargs.get("wait_time", 1)
        if any_killed:
            log_lines.append("sleeping for {:.2f} seconds".format(wait_time))
        if kwargs.get("do_syslog", True):
            for log_line in log_lines:
                logging_tools.my_syslog(log_line)
        if any_killed:
            time.sleep(wait_time)
    return log_lines


def fd_change(uid_gid_tuple, d_name, files):
    uid, gid = uid_gid_tuple
    os.chown("{}".format(d_name), uid, gid)
    for f_name in files:
        try:
            os.chown(os.path.join(d_name, f_name), uid, gid)
        except:
            pass


def fix_directories(user, group, f_list):
    try:
        if not isinstance(user, str):
            named_uid = user
        else:
            named_uid = pwd.getpwnam(user)[2]
    except KeyError:
        named_uid = 0
        logging_tools.my_syslog("Cannot find user '{}', using root (0)".format(user))
    try:
        if not isinstance(group, str):
            named_gid = group
        else:
            named_gid = grp.getgrnam(group)[2]
    except KeyError:
        named_gid = 0
        logging_tools.my_syslog("Cannot find group '{}', using root (0)".format(group))
    if isinstance(f_list, str):
        f_list = [f_list]
    for act_dir in f_list:
        if isinstance(act_dir, dict):
            dir_name = act_dir["name"]
            dir_mode = act_dir.get("dir_mode", stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
            walk_dir = act_dir.get("walk_dir", True)
        elif isinstance(act_dir, set):
            dir_name, dir_mode = act_dir
            walk_dir = True
        else:
            dir_name, dir_mode, walk_dir = (act_dir, 0o755, True)
        try_walk = True
        if not os.path.isdir(dir_name):
            try:
                os.makedirs(dir_name)
            except:
                logging_tools.my_syslog(
                    "Error creating directory '{}', except in walking : {}".format(
                        dir_name,
                        get_except_info()
                    )
                )
                try_walk = False
        if try_walk and walk_dir:
            try:
                os.chmod(dir_name, dir_mode)
            except OSError:
                logging_tools.my_syslog(
                    "Error changing mode of directory '{}', to {:d} : {}".format(
                        dir_name,
                        dir_mode,
                        get_except_info()
                    )
                )
            try:
                os.path.walk(dir_name, fd_change, (named_uid, named_gid))
            except:
                logging_tools.my_syslog(
                    "Something went wrong while walking() '{}' (uid {:d}, gid {:d}): {}".format(
                        dir_name,
                        named_uid,
                        named_gid,
                        get_except_info()
                    )
                )


def is_linux():
    return sys.platform in ["linux2", "linux3", "linux"]


def is_windows():
    return not is_linux()


def get_fqdn():
    """
    return short and fqdn
    """
    short_sock_name = get_machine_name()
    full_sock_name = socket.getfqdn(short_sock_name)
    mach_name = short_sock_name
    if full_sock_name.count(".") > 0:
        if full_sock_name.split(".")[0] in ["localhost"]:
            # rewrite fqdn to something meaningfull
            full_sock_name = "{}.{}".format(mach_name, full_sock_name.split(".")[1])
    return full_sock_name, mach_name


def get_programm_name():
    p_name = os.path.basename(sys.argv[0])
    if p_name.endswith(".py"):
        p_name = p_name[:-3]
    return p_name


def get_machine_name(short=True):
    if sys.platform in ["linux2", "linux3", "linux"]:
        # for linux
        m_name = os.uname()[1]
    else:
        # for windows
        m_name = os.getenv("COMPUTERNAME")
    if short:
        return m_name.split(".")[0]
    else:
        return m_name


def get_cluster_name(f_name="/etc/sysconfig/cluster/cluster_name"):
    if os.path.isfile(f_name):
        try:
            c_name = open(f_name, "r").read().strip().split()[0]
        except:
            c_name = "error reading: {}".format(get_except_info())
    else:
        c_name = "not set"
    return c_name


def get_arp_dict():
    try:
        arp_dict = {
            line_p[3].lower(): line_p[0] for line_p in [
                line.strip().split() for line in open("/proc/net/arp", "r").read().split("\n")[1:]
            ] if line_p
        }
    except:
        arp_dict = {}
    return arp_dict


def get_char_block_device_dict():
    # parses /proc/devices and returns two dicts
    char_dict, block_dict = ({}, {})
    try:
        lines = [
            line.strip().lower() for line in open("/proc/devices", "r").read().split("\n") if line.strip()
        ]
    except:
        pass
    else:
        act_dict = None
        for line in lines:
            if line.startswith("char"):
                act_dict = char_dict
            elif line.startswith("block"):
                act_dict = block_dict
            elif act_dict is not None:
                l_spl = line.split()
                act_dict[int(l_spl[0])] = l_spl[1]
    return char_dict, block_dict


def _read_issue_file(f_name):
    ret_dict = {}
    if os.path.isfile(f_name):
        ret_dict = {
            c_line[0].strip(): c_line[1].strip() for c_line in [
                line.strip().lower().split("=", 1) for line in open(f_name, "r").read().split("\n") if
                line.strip() and not line.strip().startswith("#") and line.count("=")
            ]
        }
    return ret_dict


def fetch_sysinfo(root_dir="/"):
    # late import due to strange build problem on Debian (once again) systems
    log_lines, sys_dict = ([], {})
    try:
        isl = []
        for _fname in ["etc/issue", "etc/redhat-release", "etc/fedora-release"]:
            _full = os.path.join(root_dir, _fname)
            if os.path.isfile(_full):
                isl.extend([_line.strip().lower() for _line in open(_full, "r").read().split("\n")])
    except:
        log_lines.append(
            (
                "error invalid root_path '{}' ?".format(root_dir),
                logging_tools.LOG_LEVEL_CRITICAL
            )
        )
    else:
        for what in ["arch", "vendor", "version"]:
            sys_dict[what] = "<UNKNOWN>"
        # architecture
        arch = None
        # new code, uses /bin/ls format
        ls_path = os.path.join(root_dir, "/bin/ls")
        if os.path.islink(ls_path):
            ls_path = os.path.join(root_dir, os.readlink(ls_path))
        arch_com = "file {}".format(ls_path)
        c_stat, out = getstatusoutput(arch_com)
        if c_stat:
            log_lines.append(("Cannot execute {} ({:d}): {}".format(arch_com, c_stat, out), logging_tools.LOG_LEVEL_ERROR))
        else:
            arch_str = out.split(",")[1].strip().lower()
            if arch_str.count("386"):
                arch = "i586"
            elif arch_str.count("586"):
                arch = "i586"
            elif arch_str.count("x86-64") or arch_str.count("x86_64") or arch_str.count("amd64"):
                arch = "x86_64"
            elif arch_str.count("alpha"):
                arch = "alpha"
            if arch:
                sys_dict["arch"] = arch
        for arch_str in [line for line in isl if line]:
            if not arch:
                if arch_str.count("i386"):
                    arch = "i586"
                elif arch_str.count("i586"):
                    arch = "i586"
                elif arch_str.count("x86-64") or arch_str.count("x86_64") or arch_str.count("amd64"):
                    arch = "x86_64"
                elif arch_str.count("alpha"):
                    arch = "alpha"
                if arch:
                    sys_dict["arch"] = arch
            # vendor
            if arch_str.count("suse"):
                sys_dict["vendor"] = "suse"
            elif arch_str.count("fedora"):
                sys_dict["vendor"] = "fedoracore"
            elif arch_str.count("redhat") or arch_str.count("red hat"):
                sys_dict["vendor"] = "redhat"
            elif arch_str.count("centos"):
                sys_dict["vendor"] = "centos"
            elif arch_str.count("debian"):
                sys_dict["vendor"] = "debian"
            elif arch_str.count("ubuntu"):
                sys_dict["vendor"] = "ubuntu"
            elif arch_str.count("scientific"):
                sys_dict["vendor"] = "scientific"
            # check for sles
            if re.search("sles", arch_str):
                arch_m = re.match("^.*suse sles (\d+).*$", arch_str)
                sys_dict["version"] = "sles{}".format(arch_m.group(1))
            elif re.search("enterprise server", arch_str):
                arch_m = re.match("^.*enterprise server (\d+).*$", arch_str)
                sys_dict["version"] = "sles{}".format(arch_m.group(1))
                sr_dict = _read_issue_file(os.path.join(root_dir, "etc/SuSE-release"))
                if "patchlevel" in sr_dict:
                    sys_dict["version"] = "{}.{}".format(
                        sys_dict["version"],
                        sr_dict["patchlevel"])
            else:
                versm = re.search("(\d+\.\d+)", arch_str)
                if versm:
                    sys_dict["version"] = versm.group(1)
                if sys_dict["vendor"] == "fedoracore":
                    versm = re.search("release (\d+) ", arch_str)
                    if versm:
                        sys_dict["version"] = versm.group(1)
                elif sys_dict["vendor"] == "suse":
                    sr_ems = False
                    try:
                        isl = [y for y in [x.strip().lower() for x in open(os.path.join(root_dir, "etc/SuSE-release"), "r").read().split("\n")] if y]
                    except:
                        pass
                    else:
                        # sr_vers = None
                        for eml in isl:
                            if re.search("email server", eml):
                                sr_ems = True
                                ems_file = os.path.join(root_dir, "etc/IMAP-release")
                    try:
                        isl = [x.strip().lower() for x in open(os.path.join(root_dir, "etc/SLOX-release"), "r").read().split("\n")]
                    except:
                        pass
                    else:
                        sr_ems = True
                        ems_file = os.path.join(root_dir, "etc/SLOX-release")
                    if sr_ems:
                        try:
                            isl = [x.strip().lower() for x in open(ems_file, "r").read().split("\n")]
                        except:
                            pass
                        else:
                            for eml in isl:
                                if len(eml):
                                    eml_m = re.match("^version\s*=\s*(.*)$", eml)
                                    if eml_m:
                                        sys_dict["version"] = "sox{}".format(eml_m.group(1))
                elif sys_dict["vendor"] == "redhat":
                    if re.search("enterprise linux", arch_str):
                        arch_m = re.match("^.*nterprise linux (?P<type>\S+)\s*release\s*(?P<version>\S+)\s+.*$", arch_str)
                        if arch_m:
                            sys_dict["version"] = "{}{}".format(
                                arch_m.group("type"),
                                arch_m.group("version")
                            )
                elif sys_dict["vendor"] == "debian" and os.path.isdir(os.path.join(root_dir, "etc/apt")):
                    # try to get info from /etc/apt
                    try:
                        s_list = [
                            z[2].split("/")[0] for z in [
                                y.split() for y in [x.strip() for x in open(
                                    os.path.join(root_dir, "etc/apt/sources.list"), "r"
                                ).read().split("\n")] if y and not y.startswith("#")
                            ] if len(z) > 3
                        ]
                    except:
                        pass
                    else:
                        # hack, take first from list
                        sys_dict["version"] = list(set(s_list))[0]
                        sys_dict["version"] = {
                            "jessie": "8.1"
                        }.get(sys_dict["version"], sys_dict["version"])
    return log_lines, sys_dict


def find_file(file_name, s_path=None, exception_on_error=False):
    if not s_path:
        s_path = []
    elif not isinstance(s_path, list):
        s_path = [s_path]
    s_path.extend(
        [
            "/opt/cluster/sbin", "/opt/cluster/bin", "/bin", "/usr/bin", "/sbin", "/usr/sbin"
        ]
    )
    for cur_path in s_path:
        if os.path.isfile(os.path.join(cur_path, file_name)):
            return os.path.join(cur_path, file_name)
    if exception_on_error:
        raise RuntimeError("Failed to find {} (not present any of: {})".format(file_name, s_path))
    else:
        return None


def create_password(**kwargs):
    def_chars = "".join(
        [
            chr(asc) for asc in range(ord("a"), ord("z") + 1)
        ]
    )
    chars = kwargs.get(
        "chars", "{}{}{}".format(
            def_chars,
            def_chars.upper(),
            "".join(
                [
                    "{:d}".format(idx) for idx in range(0, 10)
                ]
            )
        )
    )
    if kwargs.get("special_characters", False):
        chars = "{}!§$%&/()[]#+*~".format(chars)
    length = kwargs.get("length", 8)
    return "".join(
        [
            chars[
                random.randrange(len(chars))
            ] for _idx in range(length)
        ]
    )


def get_sys_bits():
    return int(platform.architecture()[0][0:2])
