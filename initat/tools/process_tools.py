# -*- coding: utf-8 -*-
#
# Copyright (c) 2001-2007,2009-2015 Andreas Lang-Nevyjel, init.at
#
# this file is part of python-modules-base
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License
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
import codecs
import base64
import inspect
import locale
import marshal
import os
import pickle
import platform
import random
import re
import socket
import stat
import subprocess
import sys
import threading
import time
import traceback
import json
import bz2
from lxml import etree  # @UnresolvedImports
import grp
import pwd

from initat.tools import logging_tools
import psutil
from initat.tools import uuid_tools
import zmq
from lxml.builder import E  # @UnresolvedImports


def compress_struct(input):
    return base64.b64encode(bz2.compress(json.dumps(input)))


def decompress_struct(b64_str):
    return json.loads(bz2.decompress((base64.b64decode(b64_str))))

try:
    ENCODING = locale.getpreferredencoding()
except locale.Error:
    ENCODING = "C"

try:
    from initat.tools import affinity_tools  # @UnresolvedImports
except IOError:
    affinity_tools = None


def getstatusoutput(cmd):
    if sys.version_info[0] == 3:
        return subprocess.getstatusoutput(cmd)  # @UndefinedVariable
    else:
        import commands
        return commands.getstatusoutput(cmd)


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
    if exc_name == "ValidationError":
        # special handling of Django ValidationErrors
        _exc_list = ", ".join(_exc_list.messages)
    return u"{} ({}{})".format(
        unicode(exc_info[0]),
        unicode(_exc_list),
        ", {}".format(", ".join(frame_info)) if frame_info else "")


class exception_info(object):
    def __init__(self, **kwargs):
        self.thread_name = threading.currentThread().getName()
        self.except_info = kwargs.get("exc_info", sys.exc_info())
        tb_object = self.except_info[2]
        exc_type = str(self.except_info[0]).split(".")[-1].split("'")[0]
        self.log_lines = [
            "caught exception {} ({}), traceback follows:".format(
                exc_type,
                get_except_info(self.except_info)),
            "exception in process/thread '{}'".format(self.thread_name)]
        for file_name, line_no, name, line in traceback.extract_tb(tb_object):
            self.log_lines.append("File '{}', line {:d}, in {}".format(file_name, line_no, name))
            if line:
                self.log_lines.append(" - {:d} : {}".format(line_no, line))
        self.log_lines.append(get_except_info(self.except_info))

# mapping: server type -> postfix for ZMQ_IDENTITY string
_CLIENT_TYPE_UUID_MAPPING = {
    "meta": "meta-server",
    "package": "package-client",
}


def call_command(act_command, log_com, close_fds=False):
    log_com("calling command '{}'".format(act_command))
    s_time = time.time()
    _sub = subprocess.Popen(act_command.strip().split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=close_fds, cwd="/")
    ret_code = _sub.wait()
    _stdout, _stderr = _sub.communicate()
    e_time = time.time()
    log_com("execution took {}, return code was {:d}".format(
        logging_tools.get_diff_time_str(e_time - s_time),
        ret_code,
        ))
    for _val, _name, _lev in [(_stdout, "stdout", logging_tools.LOG_LEVEL_OK), (_stderr, "stderr", logging_tools.LOG_LEVEL_ERROR)]:
        if _val.strip():
            _lines = _val.split("\n")
            log_com("{} has {} ({})".format(_name, logging_tools.get_plural("byte", len(_val)), logging_tools.get_plural("line", len(_lines))))
            for _line_num, _line in enumerate(_lines):
                log_com(" {:3d} : {}".format(_line_num + 1, _line), _lev)
        else:
            log_com("{} is empty".format(_name))
    return ret_code, _stdout, _stderr


def get_client_uuid(client_type, uuid=None):
    if uuid is None:
        uuid = uuid_tools.get_uuid().get_urn()
    if not uuid.startswith("urn"):
        uuid = "urn:uuid:{}".format(uuid)
    return "{}:{}:".format(
        uuid,
        _CLIENT_TYPE_UUID_MAPPING[client_type],
    )


def get_socket(context, r_type, **kwargs):
    _sock = context.socket(getattr(zmq, r_type))
    # DEALER from grapher/server.py
    if r_type in ["ROUTER", "DEALER"]:
        _sock.setsockopt(zmq.IDENTITY, kwargs["identity"])  # @UndefinedVariable
    if r_type in ["ROUTER"]:
        _sock.setsockopt(zmq.ROUTER_MANDATORY, 1)  # @UndefinedVariable
    for _opt, _value in [
        ("LINGER", kwargs.get("linger", 100)),
        ("SNDHWM", kwargs.get("sndhwm", 256)),
        ("RCVHWM", kwargs.get("rcvhwm", 256)),
        ("SNDTIMEO", 500),
        ("BACKLOG", kwargs.get("backlog", 1)),
        ("TCP_KEEPALIVE", 1),
        ("TCP_KEEPALIVE_IDLE", 300),
        ("RECONNECT_IVL_MAX", kwargs.get("reconnect_ivl", 500)),
        ("RECONNECT_IVL", kwargs.get("reconnect_ivl_max", 200)),
    ]:
        _sock.setsockopt(getattr(zmq, _opt), _value)
    if kwargs.get("immediate", False):
        _sock.setsockopt(getattr(zmq, "IMMEDIATE"), True)
    return _sock


def zmq_identity_str(id_string):
    return "{}:{}:{:d}".format(
        get_machine_name(),
        id_string,
        os.getpid())


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

LOCAL_ZMQ_DIR = "/tmp/.icsw_zmq/.zmq_{:d}:{:d}".format(
    os.getuid(),
    os.getpid(),
)

LOCAL_ROOT_ZMQ_DIR = "/var/log/cluster/sockets"
INIT_ZMQ_DIR_PID = "{:d}".format(os.getpid())
ALLOW_MULTIPLE_INSTANCES = True


def get_zmq_ipc_name(name, **kwargs):
    if "s_name" in kwargs:
        s_name = kwargs["s_name"]
    else:
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
            os.chmod(_root_base, 01777)
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
                        get_except_info()),
                    logging_tools.LOG_LEVEL_ERROR)
    try:
        zmq_socket.bind(name)
    except:
        logging_tools.my_syslog(
            "error binding to zmq_socket '{}': {}".format(
                name,
                get_except_info()))
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
    psutil.STATUS_RUNNING:  "number of running processes",
    psutil.STATUS_ZOMBIE: "number of zombie processes",
    psutil.STATUS_DISK_SLEEP: "processes in uninterruptable sleep",
    psutil.STATUS_STOPPED: "processes stopped",
    psutil.STATUS_TRACING_STOP: "processes traced",
    psutil.STATUS_SLEEPING: "processes sleeping",
    psutil.STATUS_WAKING: "processes waking",
    psutil.STATUS_DEAD: "processes dead",
}

PROC_STATUSES_REV = {value: key for key, value in PROC_STATUSES.iteritems()}


def get_mem_info(pid=0, **kwargs):
    if not pid:
        pid = os.getpid()
    if type(pid) not in [list, set]:
        pid = [pid]
    ps_list = []
    for cur_pid in pid:
        try:
            # only count RSS (resident set size)
            ps_list.append(psutil.Process(cur_pid).memory_info()[0])
        except:
            # ignore missing process
            pass
    return sum(ps_list)

# old code, very slow compared to psutil (due to .so)
if False:
    cur_pid = 0
    tot_size = 0
    smap_file_name = "/proc/{:d}/smaps".format(cur_pid)
    map_file_name = "/proc/{:d}/maps".format(cur_pid)
    if os.path.isfile(smap_file_name):
        have_pss = False
        shared, private, pss = (0, 0, 0.)
        try:
            for line in open(smap_file_name, "r"):
                if line.startswith("Shared"):
                    shared += int(line.split()[1])
                elif line.startswith("Private"):
                    private += int(line.split()[1])
                elif line.startswith("Pss"):
                    have_pss = True
                    pss += float(line.split()[1]) + 0.5
        except IOError:
            pass
        if have_pss:
            # print shared, pss - private
            shared = pss - private
        tot_size = int((shared + private) * 1024)
    elif os.path.isfile(map_file_name):
        # not always correct ...
        try:
            map_lines = [
                [_part.strip() for _part in _line.strip().split()] for _line in
                open(map_file_name, "r") if _line.strip()]
        except:
            pass
        else:
            for map_p in map_lines:
                # print "map_p", map_p
                try:
                    mem_start, mem_end = map_p[0].split("-")
                    mem_start, mem_end = (int(mem_start, 16),
                                          int(mem_end, 16))
                    mem_size = mem_end - mem_start
                    _perm, _offset, _dev, inode = (
                        map_p[1],
                        int(map_p[2], 16),
                        map_p[3],
                        int(map_p[4])
                    )
                    if not inode:
                        tot_size += mem_size
                except:
                    pass


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


class meta_server_info(object):
    def __init__(self, name):
        self.__prop_list = [
            ("start_command", "s", None),
            ("stop_command", "s", None),
            ("kill_pids", "b", False),
            ("check_memory", "b", True),
            ("exe_name", "s", None),
            ("need_any_pids", "b", 0),
        ]
        parsed = False
        if name.startswith("/"):
            self.__file_name = name
            # try to read complete info from file
            self.__name = None
            try:
                xml_struct = etree.fromstring(open(name, "r").read())  # @UndefinedVariable
            except:
                logging_tools.my_syslog(
                    "error parsing XML file {} (meta_server_info): {}".format(
                        name,
                        get_except_info()
                    )
                )
                xml_struct = None
            if xml_struct is not None:
                self.__name = xml_struct.xpath(".//name/text()", smart_strings=False)[0]
                # reads pids
                self.__pids = []
                self.__pid_names = {}
                # name from psutil()
                self.__pid_proc_names = {}
                self.__pid_fuzzy = {}
                for cur_idx, pid_struct in enumerate(xml_struct.xpath(".//pid_list/pid", smart_strings=False)):
                    self.__pids.extend([int(pid_struct.text)] * int(pid_struct.get("mult", "1")))
                    self.__pid_names[int(pid_struct.text)] = pid_struct.get("name", "proc{:d}".format(cur_idx + 1))
                    self.__pid_proc_names[int(pid_struct.text)] = pid_struct.get("proc_name", "")
                    self.__pid_fuzzy[int(pid_struct.text)] = (
                        int(pid_struct.get("fuzzy_floor", "0")),
                        int(pid_struct.get("fuzzy_ceiling", "0")),
                    )
                for opt, val_type, def_val in self.__prop_list:
                    cur_prop = xml_struct.xpath(".//properties/prop[@type and @key='{}']".format(opt), smart_strings=False)
                    if cur_prop:
                        cur_prop = cur_prop[0]
                        cur_value = cur_prop.text
                        if cur_prop.attrib["type"] == "integer":
                            cur_value = int(cur_value)
                        elif cur_prop.attrib["type"] == "boolean":
                            cur_value = bool(cur_value)
                    else:
                        cur_value = def_val
                    if opt.startswith("fuzzy"):
                        # ignore fuzzy*
                        pass
                    else:
                        setattr(self, opt, cur_value)
                parsed = True
            else:
                try:
                    lines = [line.strip() for line in open(name, "r").read().split("\n")]
                except:
                    logging_tools.my_syslog("error reading file {} (meta_server_info): {}".format(
                        name,
                        get_except_info()))
                else:
                    act_dict = {line[0].strip().lower(): line[1].strip() for line in [lp.split("=", 1) for lp in lines if lp.count("=")] if len(line) > 1}
                    self.__name = act_dict.get("name", None)
                    self.__pids = sorted([int(cur_pid) for cur_pid in act_dict.get("pids", "").split() if cur_pid.isdigit()])
                    self.__pid_names = {pid: "proc{:d}".format(cur_idx + 1) for cur_idx, pid in enumerate(sorted(list(set(self.__pids))))}
                    self.__pid_proc_names = {pid: "unknown" for cur_idx, pid in enumerate(sorted(list(set(self.__pids))))}
                    self.__pid_fuzzy = {cur_pid: (0, 0) for cur_pid in set(self.__pids)}
                    for opt, val_type, def_val in self.__prop_list:
                        if opt in act_dict:
                            cur_value = act_dict[opt]
                            if val_type == "i":
                                cur_value = int(cur_value)
                            elif val_type == "b":
                                cur_value = bool(cur_value)
                        else:
                            cur_value = def_val
                        setattr(self, opt, cur_value)
                    parsed = True
            if parsed:
                self.__meta_server_dir = os.path.dirname(name)
                self.pid_checks_ok, self.pid_checks_failed = (0, 0)
                self.set_last_pid_check_ok_time()
        else:
            self.__file_name = None
            self.set_meta_server_dir("/var/lib/meta-server")
            self.__name = name
            self.__pids = []
            self.__pid_names = {}
            self.__pid_proc_names = {}
            self.__pid_fuzzy = {}
            self.pid_checks_ok, self.pid_checks_failed = (0, 0)
            for opt, val_type, def_val in self.__prop_list:
                setattr(self, opt, def_val)
        self.parsed = parsed
        self.file_init_time = time.time()

    def get_file_name(self):
        return self.__file_name

    def get_name(self):
        return self.__name

    @property
    def name(self):
        return self.__name

    def get_last_pid_check_ok_time(self):
        return self.__last_check_ok

    def set_last_pid_check_ok_time(self, last_t=None):
        self.__last_check_ok = last_t or time.time()

    def set_meta_server_dir(self, msd):
        self.__meta_server_dir = msd

    def file_init_time_get(self):
        return self.__file_init_time

    def file_init_time_set(self, fi_time):
        self.__file_init_time = fi_time
    file_init_time = property(file_init_time_get, file_init_time_set)

    def stop_command_get(self):
        return self._stop_command

    def stop_command_set(self, stop_com):
        self._stop_command = stop_com
    stop_command = property(stop_command_get, stop_command_set)

    def start_command_get(self):
        return self._start_command

    def start_command_set(self, start_com):
        self._start_command = start_com
    start_command = property(start_command_get, start_command_set)

    def exe_name_get(self):
        return self.__exe_name

    def exe_name_set(self, en):
        self.__exe_name = en
    exe_name = property(exe_name_get, exe_name_set)

    def need_any_pids_get(self):
        return self.__need_any_pids

    def need_any_pids_set(self, en):
        self.__need_any_pids = en
    need_any_pids = property(need_any_pids_get, need_any_pids_set)

    def kill_pids_get(self):
        return self.__kill_pids

    def kill_pids_set(self, kp=1):
        self.__kill_pids = kp
    kill_pids = property(kill_pids_get, kill_pids_set)

    def check_memory_get(self):
        return self.__check_memory

    def check_memory_set(self, cm=1):
        self.__check_memory = cm
    check_memory = property(check_memory_get, check_memory_set)

    def add_actual_pid(self, act_pid=None, mult=1, fuzzy_floor=0, fuzzy_ceiling=0, process_name=""):
        if not act_pid:
            act_pid = os.getpid()
        try:
            _ps_name = psutil.Process(pid=act_pid).name()
        except:
            logging_tools.my_syslog(
                "cannot get name of process {:d} :{}".format(
                    act_pid,
                    get_except_info()
                )
            )
            _ps_name = ""
        self.__pids.extend(mult * [act_pid])
        self.__pid_fuzzy[act_pid] = (fuzzy_floor, fuzzy_ceiling)
        if not process_name:
            process_name = "proc{:d}".format(len(self.__pid_names) + 1)
        self.__pid_names[act_pid] = process_name
        self.__pid_proc_names[act_pid] = _ps_name
        self.__pids.sort()

    def remove_actual_pid(self, act_pid=None, mult=0):
        """
        mult: number of pids to remove, defaults to 0 (means all)
        """
        if not act_pid:
            act_pid = os.getpid()
        if mult:
            for _idx in xrange(mult):
                if act_pid in self.__pids:
                    self.__pids.remove(act_pid)
        else:
            while act_pid in self.__pids:
                self.__pids.remove(act_pid)
        self.__pids.sort()

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
        # dangerous, pid_fuzzy not set
        self.__pids = in_pids
    pids = property(get_pids, set_pids)

    def get_unique_pids(self):
        return set(self.__pids)

    def get_process_name(self, pid):
        return self.__pid_names[pid]

    def get_sys_process_name(self, pid):
        return self.__pid_proc_names[pid]

    def get_info(self):
        pid_dict = {pid: self.__pids.count(pid) for pid in self.__pids}
        all_pids = sorted(pid_dict.keys())
        return "{} ({}): {}".format(
            logging_tools.get_plural("unique pid", len(all_pids)),
            logging_tools.get_plural("total thread", len(self.__pids)),
            all_pids and ", ".join(["{:d}{}".format(pid, pid_dict[pid] and " (x {:d})".format(pid_dict[pid]) or "") for pid in all_pids]) or "---")

    def save_block(self):
        pid_list = E.pid_list()
        for cur_pid in sorted(set(self.__pids)):
            cur_pid_el = E.pid(
                "{:d}".format(cur_pid),
                mult="{:d}".format(
                    self.__pids.count(cur_pid)
                ),
                name=self.__pid_names[cur_pid],
                proc_name=self.__pid_proc_names[cur_pid]
            )
            f_f, f_c = self.__pid_fuzzy[cur_pid]
            if f_f:
                cur_pid_el.attrib["fuzzy_floor"] = "{:d}".format(f_f)
            if f_c:
                cur_pid_el.attrib["fuzzy_ceiling"] = "{:d}".format(f_c)
            pid_list.append(cur_pid_el)
        xml_struct = E.meta_info(
            E.name(self.__name),
            pid_list,
            E.properties()
            )
        for opt, val_type, _dev_val in self.__prop_list:
            prop_val = getattr(self, opt)
            if prop_val is not None:
                xml_struct.find("properties").append(
                    E.prop(str(prop_val), **{
                        "key": opt,
                        "type": {
                            "s": "string",
                            "i": "integer",
                            "b": "boolean"}[val_type]
                        }
                    )
                )
        file_content = etree.tostring(xml_struct, pretty_print=True, encoding=unicode)  # @UndefinedVariable
        if not self.__file_name:
            self.__file_name = os.path.join(self.__meta_server_dir, self.__name)
        try:
            open(self.__file_name, "w").write(file_content)
        except:
            logging_tools.my_syslog("error writing file {} (meta_server_info for {})".format(self.__file_name, self.__name))

    def __eq__(self, other):
        return self.__name == other.get_name() and self.__pids == other.get_pids()

    def __ne__(self, other):
        return self.__name != other.get_name() or self.__pids != other.get_pids()

    def remove_meta_block(self):
        if not self.__file_name:
            self.__file_name = os.path.join(self.__meta_server_dir, self.__name)
        try:
            os.unlink(self.__file_name)
        except:
            logging_tools.my_syslog("error removing file {} (meta_server_info for {}): {}".format(
                self.__file_name,
                self.__name,
                get_except_info()))

    def check_block(self, act_tc_dict=None, act_dict={}):
        # threadcount dict
        if not act_tc_dict:
            act_tc_dict = get_process_id_list(True, True)
        if not self.__pids:
            if not act_dict:
                act_dict = get_proc_list_new()
            # search pids
            pids_found = [key for key, value in act_dict.iteritems() if value.name() == self.__exe_name]
            self.__pids = sum([[key] * act_tc_dict.get(key, 1) for key in pids_found], [])
            self.__pid_names.update({key: self.__exe_name for key in pids_found})
            self.__pid_proc_names.update({key: psutil.Process(key).name() for key in pids_found})
        self.__pids_found = {cur_pid: act_tc_dict[cur_pid] for cur_pid in self.__pids if cur_pid in act_tc_dict.keys()}
        # structure for check_scripts
        self.pids_found = sum([[cur_pid] * act_tc_dict.get(cur_pid, 0) for cur_pid in self.__pids_found.iterkeys()], [])
        self.__pids_expected = {
            cur_pid: (
                self.__pids.count(cur_pid) + self.__pid_fuzzy.get(cur_pid, (0, 0))[0],
                self.__pids.count(cur_pid) + self.__pid_fuzzy.get(cur_pid, (0, 0))[1]
            ) for cur_pid in self.__pids
        }
        # print self.__name, self.__pids_found, self.__pids_expected, self.__pid_fuzzy
        # difference to requested threadcount
        bound_dict = {}
        missing_list = []
        for unique_pid in set(self.__pids_found.keys()) | set(self.__pids_expected.keys()):
            p_f = self.__pids_found.get(unique_pid, 0)
            l_c, u_c = self.__pids_expected[unique_pid]
            if unique_pid not in self.__pids_found:
                missing_list.append(unique_pid)
                bound_dict[unique_pid] = -l_c
            elif unique_pid not in self.__pids_expected:
                bound_dict[unique_pid] = p_f
            else:
                if p_f < l_c:
                    bound_dict[unique_pid] = p_f - l_c
                elif p_f > u_c:
                    bound_dict[unique_pid] = p_f - u_c
                else:
                    bound_dict[unique_pid] = 0
        self.bound_dict = bound_dict
        # num_found = sum([value for value in self.__pids_found.values()])
        # num_expected = sum([value for value in self.__pids_expected.values()])
        self.pid_check_string = ", ".join(["{:d}: {}".format(
            cur_pid,
            "all {} missing".format(self.__pids_expected[cur_pid][0]) if cur_pid in missing_list else (
                "{:d} {}, {:d} found)".format(
                    abs(bound_dict[cur_pid]),
                    "missing (lower bound is {:d}".format(
                        self.__pids_expected[cur_pid][0]
                    ) if bound_dict[cur_pid] < 0 else "too many (upper bound is {:d}".format(
                        self.__pids_expected[cur_pid][1]
                    ),
                    self.__pids_found.get(cur_pid, 0),
                ) if bound_dict[cur_pid] else "OK"
            )
            ) for cur_pid in sorted(bound_dict.iterkeys())]) or "no PIDs"
        if any([value != 0 for value in bound_dict.itervalues()]):
            self.pid_checks_failed += 1
        else:
            if not self.__pids_found and self.__need_any_pids:
                self.pid_checks_failed += 1
            elif any([value > 0 for value in bound_dict.itervalues()]):
                self.pid_checks_failed += 1
            else:
                # clear failed_checks
                self.pid_checks_failed = 0
                self.pid_checks_ok += 1
                self.__last_check_ok = time.time()

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
                        get_except_info()),
                    logging_tools.LOG_LEVEL_ERROR)
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
                            u"error reading from {}: {}".format(
                                self.__name,
                                get_except_info()),
                            logging_tools.LOG_LEVEL_ERROR)
                        self.content = None
                    else:
                        self.content = content
                    self.changed()
        else:
            self.log("file '{}' does not exist".format(self.__name), logging_tools.LOG_LEVEL_ERROR)
            self.content = None
            self.changed()


def save_pid(name, pid=None, mult=1):
    return append_pids(name, pid=pid, mult=mult, mode="w")

save_pids = save_pid

RUN_DIR = "/var/run"
# not needed right now
# #if os.path.isfile("/etc/SuSE-release"):
# #    suse_ver = [line.strip().split()[-1] for line in file("/etc/SuSE-release", "r").read().split("\n") if line.startswith("VERSION")]
# #    if suse_ver == ["12.1"]:
# #        RUN_DIR = "/run"


def append_pids(name, pid=None, mult=1, mode="a"):
    if pid is None:
        actp = [os.getpid()]
    else:
        if type(pid) in [int, long]:
            actp = [pid]
        elif isinstance(pid, basestring):
            actp = [int(pid)]
        else:
            actp = pid
    if name.startswith("/"):
        fname = name
    else:
        fname = "{}.pid".format(os.path.join(RUN_DIR, name))
    dir_name = os.path.dirname(fname)
    if not os.path.isdir(dir_name):
        try:
            os.makedirs(dir_name)
        except:
            pass
    long_mode = {
        "a": "appending",
        "w": "writing"
    }[mode]
    try:
        open(fname, mode).write("\n".join(mult * ["{:d}".format(cur_p) for cur_p in actp] + [""]))
    except:
        logging_tools.my_syslog("error {} {} ({}) to {}: {}".format(
            long_mode,
            logging_tools.get_plural("pid", len(actp)),
            ", ".join(["{:d}".format(line) for line in actp]), fname,
            get_except_info()))
    else:
        try:
            os.chmod(fname, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
        except:
            logging_tools.my_syslog("error changing mode of {} to 0644: {}".format(
                fname,
                get_except_info()))


def remove_pids(name, pid=None, mult=0):
    """
    mult: number of pids to remove, defaults to 0 (means all)
    """
    if pid is None:
        actp = [os.getpid()]
    else:
        if type(pid) in [int, long]:
            actp = [pid]
        elif isinstance(pid, basestring):
            actp = [int(pid)]
        else:
            actp = pid
    if name.startswith("/"):
        fname = name
    else:
        fname = "{}.pid".format(os.path.join(RUN_DIR, name))
    try:
        pid_lines = [entry.strip() for entry in open(fname, "r").read().split("\n")]
    except:
        logging_tools.my_syslog("error interpreting file: {}".format(get_except_info()))
    else:
        for del_pid in actp:
            num_removed = 0
            new_lines = []
            for line in pid_lines:
                if line == str(del_pid) and (not mult or num_removed < mult):
                    num_removed += 1
                else:
                    new_lines.append(line)
            pid_lines = new_lines
        try:
            open(fname, "w").write("\n".join(pid_lines))
            os.chmod(fname, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
        except:
            logging_tools.my_syslog("error removing {:d} pids ({}) to {}".format(
                len(actp),
                ",".join(["{:d}".format(line) for line in actp]),
                fname))


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


def create_lockfile(lf_name):
    open(lf_name, "w").write(".")
    try:
        os.unlink(get_msg_file_name(lf_name))
    except:
        pass


def get_msg_file_name(lf_name):
    return "{}_msg".format(lf_name)


def set_lockfile_msg(lf_name, msg):
    if msg and os.path.isfile(lf_name):
        lf_msg_name = get_msg_file_name(lf_name)
        try:
            open(lf_msg_name, "w").write(msg.strip())
        except:
            pass


def delete_lockfile(lf_name, msg="OK", check=True):
    set_lockfile_msg(lf_name, msg)
    if os.path.isfile(lf_name):
        try:
            os.unlink(lf_name)
        except OSError:
            if check:
                logging_tools.my_syslog("error (OSError) deleting lockfile {}: {}".format(lf_name, get_except_info()))
        except IOError:
            if check:
                logging_tools.my_syslog("error (IOError) deleting lockfile {}: {}".format(lf_name, get_except_info()))


def wait_for_lockfile(lf_name, timeout=1, max_iter=10):
    lf_msg_name = get_msg_file_name(lf_name)
    last_out = "???"
    while True:
        max_iter -= 1
        if not max_iter:
            print("timeout")
            break
        try:
            try:
                if os.path.isfile(lf_msg_name):
                    out = open(lf_msg_name, "r").read().strip()
                else:
                    out = "."
            except:
                out = "."
            if out == "." or out != last_out or not os.path.isfile(lf_name):
                # write out if
                # - lockfile is deleted
                # - out is "." (standard wait)
                # - out is different from last out
                sys.stderr.write(" {}".format(out))
                last_out = out
            else:
                # write dot if else ;-)
                sys.stderr.write(".")
            if os.path.isfile(lf_name):
                pass
            else:
                break
            time.sleep(timeout)
        except int_error:
            print("<got SIGINT>")
            break
    return


def renice(nice=16):
    try:
        os.nice(nice)
    except:
        logging_tools.my_syslog("Cannot renice to {:d}".format(nice))
    else:
        logging_tools.my_syslog("reniced to {:d}".format(nice))


def resolve_user(user):
    try:
        if type(user) in [int, long]:
            uid_stuff = pwd.getpwuid(user)
        else:
            uid_stuff = pwd.getpwnam(user)
    except KeyError:
        uid_stuff = None
    return uid_stuff


def get_uid_from_name(user):
    try:
        if type(user) in [int, long]:
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
        if type(group) in [int, long]:
            gid_stuff = grp.getgrgid(group)
        else:
            gid_stuff = grp.getgrnam(group)
        new_gid, new_gid_name = (gid_stuff[2], gid_stuff[0])
    except KeyError:
        new_gid, new_gid_name = (0, "root")
        logging_tools.my_syslog("Cannot find group '{}', using {} ({:d})".format(group, new_gid_name, new_gid))
    return new_gid, new_gid_name


def change_user_group(user, group, groups=[], **kwargs):
    new_uid, new_uid_name = get_uid_from_name(user)
    new_gid, new_gid_name = get_gid_from_name(group)
    add_groups, add_group_names = ([], [])
    for add_grp in groups:
        try:
            addgrp_stuff = grp.getgrnam(add_grp)
            add_gid, add_gid_name = (addgrp_stuff[2], addgrp_stuff[0])
        except KeyError:
            add_gid, add_gid_name = (0, "root")
            logging_tools.my_syslog("Cannot find group '{}', using {} ({:d})".format(add_grp, add_gid_name, add_gid))
        if add_gid not in add_groups:
            add_groups.append(add_gid)
            add_group_names.append(add_gid_name)
    act_uid, act_gid = (os.getuid(), os.getgid())
    try:
        act_uid_name = pwd.getpwuid(act_uid)[0]
    except:
        act_uid_name = "<unknown>"
    try:
        act_gid_name = grp.getgrgid(act_gid)[0]
    except:
        act_gid_name = "<unknown>"
    if add_groups:
        logging_tools.my_syslog(
            "Trying to set additional groups to {} ({})".format(
                ", ".join(add_group_names), ", ".join(["{:d}".format(x) for x in add_groups])
            )
        )
        os.setgroups(add_groups)
    logging_tools.my_syslog("Trying to drop pid {:d} from [{} ({:d}), {} ({:d})] to [{} ({:d}), {} ({:d})] ...".format(
        os.getpid(),
        act_uid_name,
        act_uid,
        act_gid_name,
        act_gid,
        new_uid_name,
        new_uid,
        new_gid_name,
        new_gid))
    try:
        if "global_config" in kwargs:
            kwargs["global_config"].set_uid_gid(new_uid, new_gid)
        os.setgid(new_gid)
        os.setegid(new_gid)
        os.setuid(new_uid)
        os.seteuid(new_uid)
    except:
        logging_tools.my_syslog("error changing uid / gid: {}".format(get_except_info()))
        ok = False
    else:
        ok = True
    logging_tools.my_syslog("  ... actual uid/gid of {:d} is now ({:d}/{:d}) ...".format(os.getpid(), new_uid, new_gid))
    return ok


def fix_sysconfig_rights():
    conf_dir = "/etc/sysconfig/cluster"
    target_group = "idg"
    os.chown(conf_dir, 0, grp.getgrnam(target_group)[2])
    os.chmod(conf_dir, stat.S_IRWXU | stat.S_IRWXG | stat.S_IROTH | stat.S_IXOTH)


def change_user_group_path(path, user, group, **kwargs):
    if "log_com" in kwargs:
        log_com = kwargs["log_com"]
    else:
        log_com = logging_tools.my_syslog
    try:
        if type(user) in [int, long]:
            uid_stuff = pwd.getpwuid(user)
        else:
            uid_stuff = pwd.getpwnam(user)
        new_uid, new_uid_name = (uid_stuff[2], uid_stuff[0])
    except KeyError:
        new_uid, new_uid_name = (0, "root")
        log_com("Cannot find user '{}', using {} ({:d})".format(user, new_uid_name, new_uid))
    try:
        if type(group) in [int, long]:
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
        log_com("Trying to change path '{}' from [{} ({:d}), {} ({:d})] to [{} ({:d}), {} ({:d})] ...".format(
            path,
            act_uid_name,
            act_uid,
            act_gid_name,
            act_gid,
            new_uid_name,
            new_uid,
            new_gid_name,
            new_gid))
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


def get_process_id_list(with_threadcount=True, with_dotprocs=False):
    max_try_count = 10
    for _idx in xrange(max_try_count):
        try:
            _proc_list = os.listdir("/proc")
            if with_dotprocs:
                pid_list, dotpid_list = (
                    [int(x) for x in _proc_list if x.isdigit()],
                    [int(x[1:]) for x in _proc_list if x.startswith(".") and x[1:].isdigit()]
                )
            else:
                pid_list, dotpid_list = (
                    [int(x) for x in _proc_list if x.isdigit()],
                    []
                )
        except:
            pid_list, dotpid_list = ([], [])
        else:
            break
    if with_threadcount:
        pid_dict = {}
        for pid in pid_list:
            stat_f = "/proc/{:d}/status".format(pid)
            if os.path.isfile(stat_f):
                try:
                    _threads = 1
                    for _line in open(stat_f, "r"):
                        if _line.startswith("Threads"):
                            _threads = int(_line.split()[1])
                            break
                except:
                    _threads = 1
                pid_dict[pid] = _threads
            else:
                pid_dict[pid] = 1
        # add dotpid-files
        for pid in dotpid_list:
            stat_f = "/proc/.{:d}/status".format(pid)
            if os.path.isfile(stat_f):
                try:
                    _ppid = 0
                    for _line in open(stat_f, "r"):
                        if _line.startswith("PPid"):
                            _ppid = int(_line.split()[1])
                            break
                except:
                    _ppid = 0
                else:
                    if _ppid in pid_dict:
                        pid_dict[_ppid] += 1
        return pid_dict
    else:
        return pid_list + [".{:d}".format(x) for x in dotpid_list]


def get_proc_list_new(**kwargs):
    attrs = kwargs.get("attrs", None)
    proc_name_list = set(kwargs.get("proc_name_list", []))
    try:
        if "int_pid_list" in kwargs:
            pid_list = kwargs["int_pid_list"]
        else:
            pid_list = set(psutil.pids())
    except:
        p_dict = None
    else:
        p_dict = {}
        if attrs:
            for cur_proc in psutil.process_iter():
                try:
                    p_dict[cur_proc.pid] = cur_proc.as_dict(attrs)
                except psutil.NoSuchProcess:
                    pass
        else:
            for pid in pid_list:
                try:
                    cur_proc = psutil.Process(pid)
                    if proc_name_list:
                        if cur_proc.name() in proc_name_list:
                            p_dict[pid] = cur_proc
                    else:
                        p_dict[pid] = cur_proc
                except psutil.NoSuchProcess:
                    pass
    return p_dict


def get_proc_list(**kwargs):
    # s_time = time.time()
    s_fields = ["name", "state"]
    i_fields = ["pid", "uid", "gid", "ppid"]
    proc_name_list = set(kwargs.get("proc_name_list", []))
    add_stat = kwargs.get("add_stat_info", False)
    add_affinity = kwargs.get("add_affinity", False) and affinity_tools
    add_cmdline = kwargs.get("add_cmdline", True)
    add_exe = kwargs.get("add_exe", True)
    try:
        if "int_pid_list" in kwargs:
            pid_list = kwargs["int_pid_list"]
        else:
            pid_list = set([int(key) for key in os.listdir("/proc") if key.isdigit()])
    except:
        p_dict = None
    else:
        p_dict = {}
        for pid in pid_list:
            check_pid = True
            if check_pid:
                try:
                    t_dict = {}
                    _lnum = 0
                    _affinity_lines = []
                    for line in open("/proc/{:d}/status".format(pid), "r"):
                        _parts = line.split()
                        if not _lnum:
                            # first line, check for exclusion criteria
                            if proc_name_list and _parts[1] not in proc_name_list:
                                # leave inner loop
                                break
                        if len(_parts) >= 2:
                            what, rest = _parts[0:2]
                            r_what = what.lower()[:-1]
                            if r_what in s_fields:
                                t_dict[r_what] = rest
                            elif r_what in i_fields:
                                t_dict[r_what] = int(rest)
                            if add_affinity:
                                _affinity_lines.append(line.strip().lower())
                        _lnum += 1
                    if not _lnum:
                        # inner loop was not finished, ignore this process
                        continue
                except IOError:
                    pass
                else:
                    # t_dict = {"name" : status_lines[0][1]}
                    if proc_name_list and t_dict["name"] not in proc_name_list:
                        continue
                    # for what, rest in status_lines:
                    #    r_what = what.lower()[:-1]
                    #    if r_what in s_fields:
                    #        t_dict[r_what] = rest
                    #    elif r_what in i_fields:
                    #        t_dict[r_what] = int(rest)
                    if add_cmdline:
                        try:
                            t_dict["cmdline"] = [line for line in codecs.open("/proc/{:d}/cmdline".format(pid), "r", "utf-8").read().split("\x00") if line]
                        except:
                            t_dict["cmdline"] = [get_except_info()]
                    if add_exe:
                        try:
                            t_dict["exe"] = os.readlink("/proc/{:d}/exe".format(pid))
                        except:
                            t_dict["exe"] = None
                    if t_dict["pid"] == pid:
                        p_dict[pid] = t_dict
                    if affinity_tools and add_affinity:
                        try:
                            t_dict["affinity"] = affinity_tools.get_process_affinity_mask_from_status_lines(_affinity_lines)
                        except:
                            # process has gone away ?
                            pass
                    if add_stat:
                        try:
                            stat_content = open("/proc/{:d}/stat".format(pid), "r").read().strip()
                        except IOError:
                            pass
                        else:
                            stat_fields = stat_content.split(")", 1)[1].split()
                            if len(stat_fields) > 36:
                                t_dict["last_cpu"] = int(stat_fields[36])
                            else:
                                t_dict["last_cpu"] = 0
                            t_dict["stat_info"] = _build_stat_dict(stat_content)
    # print time.time()-s_time
    return p_dict


def bpt_show_childs(in_dict, idx, start):
    print(" " * idx, start, in_dict[start]["name"])
    if in_dict[start]["childs"]:
        p_list = in_dict[start]["childs"].keys()
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
    pdict = get_proc_list_new()
    # list of parent pids (up to init)
    ppl = build_ppid_list(pdict, os.getpid())
    kill_dict = {}
    for pid, p_struct in pdict.items():
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
        log_lines.append("my_pid is {:d}, searching for process '{}' to kill, kill_signal is {:d}, exclude_list is {}".format(
            my_pid,
            p_name,
            kill_sig,
            "empty" if not exclude_pids else ", ".join(["{:d}".format(exc_pid) for exc_pid in sorted(exclude_pids)])))
        kill_dict = build_kill_dict(p_name, exclude_pids)
        any_killed = False
        if kill_dict:
            for pid, name in kill_dict.items():
                if name not in kwargs.get("ignore_names", []):
                    log_str = "{} ({:d}): Trying to kill pid {:d} ({}) with signal {:d} ...".format(
                        p_name,
                        my_pid,
                        pid,
                        name,
                        kill_sig)
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
        if type(user) != str:
            named_uid = user
        else:
            named_uid = pwd.getpwnam(user)[2]
    except KeyError:
        named_uid = 0
        logging_tools.my_syslog("Cannot find user '{}', using root (0)".format(user))
    try:
        if type(group) != str:
            named_gid = group
        else:
            named_gid = grp.getgrnam(group)[2]
    except KeyError:
        named_gid = 0
        logging_tools.my_syslog("Cannot find group '{}', using root (0)".format(group))
    if isinstance(f_list, basestring):
        f_list = [f_list]
    for act_dir in f_list:
        if type(act_dir) == dict:
            dir_name = act_dir["name"]
            dir_mode = act_dir.get("dir_mode", stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
            walk_dir = act_dir.get("walk_dir", True)
        elif type(act_dir) == set:
            dir_name, dir_mode = act_dir
            walk_dir = True
        else:
            dir_name, dir_mode, walk_dir = (act_dir, 0o755, True)
        try_walk = True
        if not os.path.isdir(dir_name):
            try:
                os.makedirs(dir_name)
            except:
                logging_tools.my_syslog("Error creating directory '{}', except in walking : {}".format(dir_name, get_except_info()))
                try_walk = False
        if try_walk and walk_dir:
            try:
                os.chmod(dir_name, dir_mode)
            except OSError:
                logging_tools.my_syslog("Error changing mode of directory '{}', to {:d} : {}".format(dir_name, dir_mode, get_except_info()))
            try:
                os.path.walk(dir_name, fd_change, (named_uid, named_gid))
            except:
                logging_tools.my_syslog("Something went wrong while walking() '{}' (uid {:d}, gid {:d}): {}".format(
                    dir_name,
                    named_uid,
                    named_gid,
                    get_except_info()))


def fix_files(user, group, f_dict):
    try:
        named_uid = pwd.getpwnam(user)[2]
    except KeyError:
        named_uid = 0
        logging_tools.my_syslog("Cannot find user '{}', using root (0)".format(user))
    try:
        named_gid = grp.getgrnam(group)[2]
    except KeyError:
        named_gid = 0
        logging_tools.my_syslog("Cannot find group '{}', using root (0)".format(group))
    for act_file in f_dict:
        if os.path.isfile(act_file):
            try:
                os.chown(act_file, named_uid, named_gid)
            except:
                pass


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
    mach_name = get_machine_name()
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


class automount_checker(object):
    def __init__(self, **kwargs):
        if kwargs.get("check_paths", True):
            self._check_paths()
        else:
            self.__automount_path, self.__autofs_path = ("", "")
            self.__valid = True

    def _check_paths(self):
        for act_p in ["/usr/sbin", "/usr/bin", "/sbin", "/bin"]:
            act_path = "{}/automount".format(act_p)
            if os.path.isfile(act_path):
                break
            else:
                act_path = ""
        self.__automount_path = act_path
        for act_p in ["/etc/init.d", "/etc/rc.d"]:
            act_path = "{}/autofs".format(act_p)
            if os.path.isfile(act_path):
                break
            else:
                act_path = ""
        self.__autofs_path = act_path
        self.__valid = self.__automount_path and self.__autofs_path

    def valid(self):
        return self.__valid

    def set_dict(self, in_dict):
        self.__act_dict = in_dict

    def get_restart_command(self):
        return "{} restart".format(self.__autofs_path)

    def check(self):
        stat, out = getstatusoutput("{} status".format(self.__autofs_path))
        a_dict = {
            "c": {},
            "r": {}
        }
        act_mode = None
        for line in [y.lower() for y in [x.strip() for x in out.split("\n")] if y and not y.startswith("---")]:
            if line.startswith("config"):
                act_mode = "c"
            elif line.startswith("active"):
                act_mode = "r"
            else:
                if act_mode in ["c", "r"]:
                    line_split = line.split()
                    line_split.pop(0)
                    line_split = [x for x in line_split if not (x.startswith("--") or x.isdigit())]
                    mount_point = line_split.pop(0)
                    mount_type = ([x for x in line_split if x in ["yp", "ldap", "file"]] + ["unknown"])[0]
                    a_dict[act_mode].setdefault(mount_type, []).append(mount_point)
        self.__act_dict = a_dict
        return a_dict

    def dict_is_valid(self):
        return "c" in self.__act_dict and "r" in self.__act_dict

    def automounter_ok(self):
        return self.get_config_string() == self.get_running_string()

    def get_config_string(self):
        return self._get_autofs_str(self.__act_dict["c"])

    def get_running_string(self):
        return self._get_autofs_str(self.__act_dict["r"])

    def _get_autofs_str(self, in_dict):
        if in_dict:
            ret_f = []
            for used_type in sorted(in_dict.keys()):
                m_points = sorted(in_dict[used_type])
                ret_f.append(
                    "{} from {} ({})".format(
                        logging_tools.get_plural("map", len(m_points)),
                        used_type,
                        ", ".join(m_points)))
            return ", ".join(ret_f)
        else:
            return "None defined"


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
        lines = [line.strip().lower() for line in open("/proc/devices", "r").read().split("\n") if line.strip()]
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
    from initat.tools import cpu_database
    log_lines, sys_dict = ([], {})
    try:
        isl = []
        for _fname in ["/etc/issue", "/etc/redhat-release", "/etc/fedora-release"]:
            _full = os.path.join(root_dir, _fname)
            if os.path.isfile(_full):
                isl.extend([_line.strip().lower() for _line in file(_full, "r").read().split("\n")])
    except:
        log_lines.append(("error invalid root_path '{}' ?".format(root_dir), logging_tools.LOG_LEVEL_CRITICAL))
    else:
        for what in ["arch", "vendor", "version"]:
            sys_dict[what] = "<UNKNOWN>"
        # architecture
        arch = None
        if root_dir == "/" and False:
            # old code, uses installed CPU
            cpu_dict = cpu_database.correct_cpu_dict(cpu_database.get_cpu_basic_info())
            if "vendor_id" in cpu_dict and "cpu family" in cpu_dict and "model" in cpu_dict:
                arch, _long_type = cpu_database.get_cpu_info(cpu_dict["vendor_id"], cpu_dict["cpu family"], cpu_dict["model"])
                sys_dict["arch"] = arch
        else:
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
            # check for sles
            if re.search("sles", arch_str):
                arch_m = re.match("^.*suse sles (\d+).*$", arch_str)
                sys_dict["version"] = "sles{}".format(arch_m.group(1))
            elif re.search("enterprise server", arch_str):
                arch_m = re.match("^.*enterprise server (\d+).*$", arch_str)
                sys_dict["version"] = "sles{}".format(arch_m.group(1))
                sr_dict = _read_issue_file("/etc/SuSE-release")
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
                        isl = [y for y in [x.strip().lower() for x in open("/etc/SuSE-release", "r").read().split("\n")] if y]
                    except:
                        pass
                    else:
                        # sr_vers = None
                        for eml in isl:
                            if re.search("email server", eml):
                                sr_ems = True
                                ems_file = "/etc/IMAP-release"
                                # m = re.match("^version\s*=\s*(.*)$", eml)
                                # if m:
                                #    sr_vers = m.group(1)
                    try:
                        isl = [x.strip().lower() for x in open("/etc/SLOX-release", "r").read().split("\n")]
                    except:
                        pass
                    else:
                        sr_ems = True
                        ems_file = "/etc/SLOX-release"
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
                elif sys_dict["vendor"] == "debian" and os.path.isdir("/etc/apt"):
                    # try to get info from /etc/apt
                    try:
                        s_list = [
                            z[2].split("/")[0] for z in [
                                y.split() for y in [x.strip() for x in open("/etc/apt/sources.list", "r").read().split("\n")] if y and not y.startswith("#")
                            ] if len(z) > 3
                        ]
                    except:
                        pass
                    else:
                        # hack, take first from list
                        sys_dict["version"] = list(set(s_list))[0]
    return log_lines, sys_dict


def find_file(file_name, s_path=None):
    if not s_path:
        s_path = []
    elif type(s_path) != list:
        s_path = [s_path]
    s_path.extend(["/opt/cluster/sbin", "/opt/cluster/bin", "/bin", "/usr/bin", "/sbin", "/usr/sbin"])
    found = False
    for cur_path in s_path:
        if os.path.isfile(os.path.join(cur_path, file_name)):
            found = True
            break
    if found:
        return os.path.join(cur_path, file_name)
    else:
        return None


def create_password(**kwargs):
    def_chars = "".join([chr(asc) for asc in range(ord("a"), ord("z") + 1)])
    chars = kwargs.get("chars", "{}{}{}".format(
        def_chars,
        def_chars.upper(),
        "".join(["{:d}".format(idx) for idx in range(0, 10)])))
    if kwargs.get("special_characters", False):
        chars = "{}!§$%&/()[]#+*~".format(chars)
    length = kwargs.get("length", 8)
    return "".join([chars[random.randrange(len(chars))] for idx in xrange(length)])


def get_sys_bits():
    return int(platform.architecture()[0][0:2])


if __name__ == "__main__":
    num = 100
    for call in [get_proc_list, get_proc_list_new]:
        s_time = time.time()
        for i in xrange(num):
            a = call(add_affinity=True, add_stat_info=True)
        e_time = time.time()
        d_time = e_time - s_time
        print "stresstest {:d} : {:.2f} sec ({:.8f} per call)".format(num, d_time, d_time / num)
    # pprint.pprint(a)
