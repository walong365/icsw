#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (c) 2001,2002,2003,2004,2005,2006,2007,2009,2010,2012,2013 Andreas Lang-Nevyjel, init.at
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
import commands
import codecs
import cPickle
import inspect
import locale
import logging_tools
import marshal
import os
import platform
import random
import re
import signal
import socket
import stat
import sys
import threading
import time
import traceback

if sys.platform in ["linux2", "linux3"]:
    import cpu_database
    import grp
    import pwd
    # helper function for proepilogue
    from io_stream_helper import io_stream
    from lxml import etree # @UnresolvedImports
    from lxml.builder import E # @UnresolvedImports

try:
    ENCODING = locale.getpreferredencoding()
except locale.Error:
    ENCODING = "C"

try:
    import affinity_tools # @UnresolvedImports
except:
    affinity_tools = None

# net to sys and reverse functions
def net_to_sys(in_val):
    try:
        result = cPickle.loads(in_val)
    except:
        try:
            result = marshal.loads(in_val)
        except:
            raise ValueError
    return result

def sys_to_net(in_val):
    return cPickle.dumps(in_val)

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
                "line %d, %s in %s" % (
                    frame.f_lineno,
                    frame.f_code.co_name,
                    frame.f_code.co_filename
                    ) for frame in frame_info
            ]
        except:
            frame_info = []
    # print frame.f_lineno, frame.f_code.co_name
    return u"%s (%s, %s)" % (
        unicode(exc_info[0]),
        unicode(exc_info[1]),
        ", ".join(frame_info) if frame_info else "no frame_info")

class exception_info(object):
    def __init__(self, **kwargs):
        self.thread_name = threading.currentThread().getName()
        self.except_info = kwargs.get("exc_info", sys.exc_info())
        tb_object = self.except_info[2]
        exc_type = str(self.except_info[0]).split(".")[-1].split("'")[0]
        self.log_lines = [
            "caught exception %s (%s), traceback follows:" % (
                exc_type,
                get_except_info(self.except_info)),
            "exception in process/thread '%s'" % (self.thread_name)]
        for file_name, line_no, name, line in traceback.extract_tb(tb_object):
            self.log_lines.append("File '%s', line %d, in %s" % (file_name, line_no, name))
            if line:
                self.log_lines.append(" - %d : %s" % (line_no, line))
        self.log_lines.append(get_except_info(self.except_info))

def zmq_identity_str(id_string):
    return "%s:%s:%d" % (get_machine_name(),
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

LOCAL_ZMQ_DIR = "/tmp/.zmq_%d:%d" % (os.getuid(),
                                     os.getpid())

LOCAL_ROOT_ZMQ_DIR = "/var/log/cluster/sockets"
INIT_ZMQ_DIR_PID = "%d" % (os.getpid())
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
    _name = "ipc://%s/%s" % (sub_dir,
                             name)
    return _name

def bind_zmq_socket(zmq_socket, name):
    if name.startswith("ipc://"):
        s_name = name[6:]
        if os.path.exists(s_name):
            try:
                os.unlink(s_name)
            except:
                logging_tools.my_syslog(
                    "error removing zmq_socket '%s': %s" % (
                        s_name,
                        get_except_info()),
                    logging_tools.LOG_LEVEL_ERROR)
    try:
        zmq_socket.bind(name)
    except:
        logging_tools.my_syslog(
            "error binding to zmq_socket '%s': %s" % (
                name,
                get_except_info()))
        raise
    else:
        logging_tools.my_syslog("zmq_socket bound to %s" % (name))

def submit_at_command(com, diff_time=0):
    if os.path.isfile("/etc/redhat-release") or os.path.isfile("/etc/debian_version") or not diff_time:
        pre_time_str = "now"
    else:
        pre_time_str = ""
    diff_time_str = diff_time and "+%d minutes" % (diff_time) or ""
    time_str = "%s%s" % (pre_time_str, diff_time_str)
    cstat, cout = commands.getstatusoutput(
        "echo %s | /usr/bin/at %s" % (
            com,
            time_str))
    log_f = [
        "Starting command '%s' at time '%s' resulted in stat %d" % (
            com,
            time_str,
            cstat
        )
    ]
    for out_l in cout.split("\n"):
        log_f.append(" - %s" % (out_l))
    return cstat, log_f

def get_mem_info(pid=0, **kwargs):
    if not pid:
        pid = os.getpid()
    if type(pid) not in [list, set]:
        pid = [pid]
    ps_list = []
    for cur_pid in pid:
        tot_size = 0
        smap_file_name = "/proc/%d/smaps" % (cur_pid)
        map_file_name = "/proc/%d/maps" % (cur_pid)
        if os.path.isfile(smap_file_name):
            have_pss = False
            shared, private, pss = (0, 0, 0.)
            try:
                for line in open(smap_file_name, "rb").readlines():
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
                map_lines = [[y.strip() for y in x.strip().split()] for x in
                             file(map_file_name, "r").read().split("\n") if x.strip()]
            except:
                pass
            else:
                for map_p in map_lines:
                    # print "map_p", map_p
                    try:
                        mem_start, mem_end = map_p[0].split("-")
                        mem_start, mem_end = (int(mem_start, 16),
                                              int(mem_end  , 16))
                        mem_size = mem_end - mem_start
                        _perm, _offset, _dev, inode = (
                            map_p[1],
                            int(map_p[2], 16),
                            map_p[3],
                            int(map_p[4]))
                        if not inode:
                            tot_size += mem_size
                    except:
                        pass
        ps_list.append(tot_size)
    return sum(ps_list)

def get_stat_info(pid=0):
    if not pid:
        pid = os.getpid()
    stat_file_name = "/proc/%d/stat" % (pid)
    stat_dict = {}
    if os.path.isfile(stat_file_name):
        try:
            stat_line = open(stat_file_name, "r").read().strip()
        except:
            pass
        else:
            # parse stat_line
            pid_part, rest_part = [part.strip() for part in stat_line.split("(", 1)]
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
            stat_dict = dict([(key.replace("*", ""), value if key.endswith("*") else int(value))
                              for key, value in zip(stat_keys, stat_parts)])
            stat_dict["pid"] = int(pid_part)
            stat_dict["comm"] = com_part
    return stat_dict

def beautify_mem_info(mi=None, short=0):
    if short:
        bs = "B"
    else:
        bs = "Bytes"
    if mi is None:
        mi = get_mem_info()
    if mi < 1024:
        return "%d %s" % (mi, bs)
    elif mi < 1024 * 1024:
        return "%.2f k%s" % (mi / 1024., bs)
    elif mi < 1024 * 1024 * 1024:
        return "%.2f M%s" % (mi / (1024. * 1024.), bs)
    else:
        return "%.2f G%s" % (mi / (1024. * 1024. * 1024.), bs)


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
            ("start_command"    , "s", None),
            ("stop_command"     , "s", None),
            ("kill_pids"        , "b", False),
            ("check_memory"     , "b", True),
            ("exe_name"         , "s", None),
            ("need_any_pids"    , "b", 0),
            # how many pids can be too much
            ("fuzzy_ceiling"    , "i", 0),
            # how many pids can be too less
            ("fuzzy_floor"      , "i", 0),
            # heartbeat timeout, 0 means disabled
            ("heartbeat_timeout", "i", 0)]
        if name.startswith("/"):
            self.__file_name = name
            # try to read complete info from file
            self.__name = None
            xml_struct = None
            parsed = False
            if etree:
                try:
                    xml_struct = etree.fromstring(file(name, "r").read())
                except:
                    logging_tools.my_syslog("error parsing XML file %s (meta_server_info): %s" % (
                        name, get_except_info()))
            if xml_struct is not None:
                self.__name = xml_struct.xpath(".//name/text()")[0]
                # reads pids
                self.__pids = []
                for pid_struct in xml_struct.xpath(".//pid_list/pid"):
                    self.__pids.extend([int(pid_struct.text)] * int(pid_struct.get("mult", "1")))
                # self.__pids = sorted([int(cur_pid) for cur_pid in xml_struct.xpath(".//pid_list/pid/text()")])
                for opt, val_type, def_val in self.__prop_list:
                    cur_prop = xml_struct.xpath(".//properties/prop[@type and @key='%s']" % (opt))
                    if cur_prop:
                        cur_prop = cur_prop[0]
                        cur_value = cur_prop.text
                        if cur_prop.attrib["type"] == "integer":
                            cur_value = int(cur_value)
                        elif cur_prop.attrib["type"] == "boolean":
                            cur_value = bool(cur_value)
                    else:
                        cur_value = def_val
                    setattr(self, opt, cur_value)
                parsed = True
            else:
                try:
                    lines = [line.strip() for line in file(name, "r").read().split("\n")]
                except:
                    logging_tools.my_syslog("error reading file %s (meta_server_info): %s" % (
                        name,
                        get_except_info()))
                else:
                    act_dict = dict([(line[0].strip().lower(), line[1].strip()) for line in [lp.split("=", 1) for lp in lines if lp.count("=")] if len(line) > 1])
                    self.__name = act_dict.get("name", None)
                    self.__pids = sorted([int(cur_pid) for cur_pid in act_dict.get("pids", "").split() if cur_pid.isdigit()])
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
                self.pid_checks_ok, self.pid_checks_failed, self.heartbeat_checks_ok, self.heartbeat_checks_failed = (0, 0, 0, 0)
                self.set_last_pid_check_ok_time()
                self.set_last_heartbeat_check_ok_time()
        else:
            self.__file_name = None
            self.set_meta_server_dir("/var/lib/meta-server")
            self.__name = name
            self.__pids = []
            for opt, val_type, def_val in self.__prop_list:
                setattr(self, opt, def_val)
        self.file_init_time = time.time()
        self.heartbeat_time = time.time()
    def get_file_name(self):
        return self.__file_name
    def get_heartbeat_file_name(self):
        return "%s.hb" % (self.__file_name)
    def get_name(self):
        return self.__name
    def get_last_pid_check_ok_time(self):
        return self.__last_check_ok
    def get_last_heartbeat_check_ok_time(self):
        return self.__last_heartbeat_check_ok
    def set_last_pid_check_ok_time(self, last_t=None):
        self.__last_check_ok = last_t or time.time()
    def set_last_heartbeat_check_ok_time(self, last_t=None):
        self.__last_heartbeat_check_ok = last_t or time.time()
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
    def fuzzy_ceiling_get(self):
        return self._fuzzy_ceiling
    def fuzzy_ceiling_set(self, fc):
        self._fuzzy_ceiling = int(fc)
    fuzzy_ceiling = property(fuzzy_ceiling_get, fuzzy_ceiling_set)
    def fuzzy_floor_get(self):
        return self._fuzzy_floor
    def fuzzy_floor_set(self, ff):
        self._fuzzy_floor = int(ff)
    fuzzy_floor = property(fuzzy_floor_get, fuzzy_floor_set)
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
    def heartbeat_timeout_get(self):
        return self.__heartbeat_timeout
    def heartbeat_timeout_set(self, hb_to=0):
        self.__heartbeat_timeout = hb_to
    heartbeat_timeout = property(heartbeat_timeout_get, heartbeat_timeout_set)
    def add_actual_pid(self, act_pid=None, mult=1):
        if not act_pid:
            act_pid = os.getpid()
        self.__pids.extend(mult * [act_pid])
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
    def get_pids(self):
        return self.__pids
    def get_unique_pids(self):
        return set(self.__pids)
    def get_info(self):
        pid_dict = dict([(pid, self.__pids.count(pid)) for pid in self.__pids])
        all_pids = sorted(pid_dict.keys())
        return "%s (%s): %s" % (
            logging_tools.get_plural("different pid", len(all_pids)),
            logging_tools.get_plural("total pid", len(self.__pids)),
            all_pids and ", ".join(["%d%s" % (pid, pid_dict[pid] and " (x %d)" % (pid_dict[pid]) or "") for pid in all_pids]) or "---")
    def heartbeat(self):
        try:
            file(self.get_heartbeat_file_name(), "wb").write("%d" % (os.getpid()))
        except:
            logging_tools.my_syslog("error writing file %s (meta_server_info for %s)" % (self.get_heartbeat_file_name(), self.__name))
    def save_block(self):
        if etree:
            xml_struct = E.meta_info(
                E.name(self.__name),
                E.pid_list(*[E.pid("%d" % (cur_pid), mult="%d" % (self.__pids.count(cur_pid))) for cur_pid in set(self.__pids)]),
                E.properties()
                )
            for opt, val_type, _dev_val in self.__prop_list:
                prop_val = getattr(self, opt)
                if prop_val is not None:
                    xml_struct.find("properties").append(
                        E.prop(str(prop_val), **{
                            "key"  : opt,
                            "type" : {
                                "s" : "string",
                                "i" : "integer",
                                "b" : "boolean"}[val_type]}))
            file_content = etree.tostring(xml_struct, pretty_print=True, encoding=unicode)
        else:
            file_content = ["NAME = %s" % (self.__name),
                            "PIDS = %s" % (" ".join(["%d" % (x) for x in self.__pids]))]
            for opt, val_type, _dev_val in self.__prop_list:
                prop_val = getattr(self, opt)
                if prop_val is not None:
                    file_content.append("%s = %s" % (opt.upper(), str(prop_val)))
            file_content = "\n".join(file_content + [""])
        if not self.__file_name:
            self.__file_name = "%s/%s" % (self.__meta_server_dir, self.__name)
        try:
            file(self.__file_name, "w").write(file_content)
        except:
            logging_tools.my_syslog("error writing file %s (meta_server_info for %s)" % (self.__file_name, self.__name))
    def __eq__(self, other):
        return self.__name == other.get_name() and self.__pids == other.get_pids()
    def __ne__(self, other):
        return self.__name != other.get_name() or self.__pids != other.get_pids()
    def remove_meta_block(self):
        if not self.__file_name:
            self.__file_name = "%s/%s" % (self.__meta_server_dir, self.__name)
        try:
            os.unlink(self.__file_name)
        except:
            logging_tools.my_syslog("error removing file %s (meta_server_info for %s): %s" % (
                self.__file_name,
                self.__name,
                get_except_info()))
        if os.path.isfile(self.get_heartbeat_file_name()):
            try:
                os.unlink(self.get_heartbeat_file_name())
            except:
                logging_tools.my_syslog("error removing heartbeat file %s (meta_server_info for %s): %s" % (
                    self.get_heartbeat_file_name(),
                    self.__name,
                    get_except_info()))
    def check_block(self, act_pids=[], act_dict={}):
        if not act_pids:
            act_pids = get_process_id_list(True, True)
        if not self.__pids:
            if not act_dict:
                act_dict = get_proc_list()
            # search pids
            pids_found = [key for key, value in act_dict.iteritems() if value["name"] == self.__exe_name]
            self.__pids = sum([[key] * act_pids[key] for key in pids_found], [])
        self.__pids_found = dict([(cur_pid, act_pids[cur_pid]) for cur_pid in self.__pids if cur_pid in act_pids.keys()])
        self.__pids_expected = dict([(cur_pid, len([True for s_pids in self.__pids if cur_pid == s_pids])) for cur_pid in self.__pids])
        num_found = sum([value for value in self.__pids_found.values()])
        num_expected = sum([value for value in self.__pids_expected.values()])
        if num_found < (num_expected + self.fuzzy_floor):
            self.pid_checks_failed += 1
        else:
            if not num_found and self.__need_any_pids:
                self.pid_checks_failed += 1
            elif num_found > (num_expected + self.fuzzy_ceiling):
                self.pid_checks_failed += 1
            else:
                # clear failed_checks
                self.pid_checks_failed = 0
                self.pid_checks_ok += 1
                self.__last_check_ok = time.time()
        if self.heartbeat_timeout:
            hb_fname = self.get_heartbeat_file_name()
            if os.path.isfile(hb_fname):
                hb_time = os.stat(hb_fname)[stat.ST_MTIME]
                if hb_time >= abs(time.time() - int(self.heartbeat_timeout)):
                    self.__last_heartbeat_check_ok = time.time()
                    self.heartbeat_checks_failed = 0
                    self.heartbeat_checks_ok += 1
                else:
                    self.heartbeat_checks_failed += 1
            else:
                self.heartbeat_checks_failed += 1
    def get_problem_str_hb(self):
        return "heartbeat failed for %d times" % (self.heartbeat_checks_failed)
    def get_problem_str_pids(self):
        pid_f = []
        too_much, missing = (0, 0)
        for pid in self.__pids_expected:
            p_w, p_f = (self.__pids_expected[pid], self.__pids_found.get(pid, 0))
            if p_w == p_f:
                pid_f.append("pid %d: ok (%d)" % (
                    pid,
                    p_w))
            elif p_f < p_w:
                pid_f.append("pid %d: %d of %d missing" % (
                    pid,
                    p_w - p_f,
                    p_w))
                missing += p_w - p_f
            else:
                pid_f.append("pid %d: %d too mouch (should be %d)" % (
                    pid,
                    p_f - p_w,
                    p_w))
                too_much += p_f - p_w
        return "%s missing, %s too much: %s" % (
            logging_tools.get_plural("process", missing),
            logging_tools.get_plural("process", too_much),
            ", ".join(pid_f))
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
            return "%s to kill (%s); ok: %s, error: %s" % (
                logging_tools.get_plural("pid", len(all_pids)),
                ",".join(["%d" % (cur_pid) for cur_pid in all_pids]),
                ok_pids and "%s (%s)" % (
                    logging_tools.get_plural("pid", len(ok_pids)),
                    ", ".join(["%d" % (cur_pid) for cur_pid in ok_pids])) or "---",
                error_pids and "%s (%s)" % (
                    logging_tools.get_plural("pid", len(error_pids)),
                    ", ".join(["%d" % (cur_pid) for cur_pid in error_pids])) or "---")
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
                self.log("error stating() %s: %s" % (self.__name,
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
                        content = file(self.__name, "r").read()
                    except:
                        self.log("error reading from %s: %s" % (self.__name,
                                                                get_except_info()),
                                 logging_tools.LOG_LEVEL_ERROR)
                        self.content = None
                    else:
                        self.content = content
                    self.changed()
        else:
            self.log("file '%s' does not exist" % (self.__name), logging_tools.LOG_LEVEL_ERROR)
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
    if pid == None:
        actp = [os.getpid()]
    else:
        if type(pid) in [int, long]:
            actp = [pid]
        elif type(pid) in [str, unicode]:
            actp = [int(pid)]
        else:
            actp = pid
    if name.startswith("/"):
        fname = name
    else:
        fname = "%s.pid" % (os.path.join(RUN_DIR, name))
    dir_name = os.path.dirname(fname)
    if not os.path.isdir(dir_name):
        try:
            os.makedirs(dir_name)
        except:
            pass
    long_mode = {"a" : "appending",
                 "w" : "writing"}[mode]
    try:
        file(fname, mode).write("\n".join(mult * ["%d" % (cur_p) for cur_p in actp] + [""]))
    except:
        logging_tools.my_syslog("error %s %s (%s) to %s: %s" % (
            long_mode,
            logging_tools.get_plural("pid", len(actp)),
            ", ".join(["%d" % (line) for line in actp]), fname,
            get_except_info()))
    else:
        try:
            os.chmod(fname, 0644)
        except:
            logging_tools.my_syslog("error changing mode of %s to 0644: %s" % (
                fname,
                get_except_info()))

def remove_pids(name, pid=None, mult=0):
    """
    mult: number of pids to remove, defaults to 0 (means all)
    """
    if pid == None:
        actp = [os.getpid()]
    else:
        if type(pid) in [int, long]:
            actp = [pid]
        elif type(pid) in [str, unicode]:
            actp = [int(pid)]
        else:
            actp = pid
    if name.startswith("/"):
        fname = name
    else:
        fname = "%s.pid" % (os.path.join(RUN_DIR, name))
    try:
        pid_lines = [entry.strip() for entry in file(fname, "r").read().split("\n")]
    except:
        logging_tools.my_syslog("error interpreting file: %s" % (get_except_info()))
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
            file(fname, "w").write("\n".join(pid_lines))
            os.chmod(fname, 0644)
        except:
            logging_tools.my_syslog("error removing %d pids (%s) to %s" % (
                len(actp),
                ",".join(["%d" % (line) for line in actp]), fname))

def delete_pid(name):
    if name.startswith("/"):
        fname = name
    else:
        fname = "%s.pid" % (os.path.join(RUN_DIR, name))
    if os.path.isfile(fname):
        try:
            os.unlink(fname)
        except:
            pass

def create_lockfile(lf_name):
    file(lf_name, "w").write(".")
    try:
        os.unlink(get_msg_file_name(lf_name))
    except:
        pass

def get_msg_file_name(lf_name):
    return "%s_msg" % (lf_name)

def set_lockfile_msg(lf_name, msg):
    if msg and os.path.isfile(lf_name):
        lf_msg_name = get_msg_file_name(lf_name)
        try:
            file(lf_msg_name, "w").write(msg.strip())
        except:
            pass

def delete_lockfile(lf_name, msg="OK", check=True):
    set_lockfile_msg(lf_name, msg)
    if os.path.isfile(lf_name):
        try:
            os.unlink(lf_name)
        except OSError:
            if check:
                logging_tools.my_syslog("error (OSError) deleting lockfile %s: %s" % (lf_name, get_except_info()))
        except IOError:
            if check:
                logging_tools.my_syslog("error (IOError) deleting lockfile %s: %s" % (lf_name, get_except_info()))

def wait_for_lockfile(lf_name, timeout=1, max_iter=10):
    lf_msg_name = get_msg_file_name(lf_name)
    last_out = "???"
    while True:
        max_iter -= 1
        if not max_iter:
            print "timeout"
            break
        try:
            try:
                if os.path.isfile(lf_msg_name):
                    out = file(lf_msg_name, "r").read().strip()
                else:
                    out = "."
            except:
                out = "."
            if out == "." or out != last_out or not os.path.isfile(lf_name):
                # write out if
                # - lockfile is deleted
                # - out is "." (standard wait)
                # - out is different from last out
                sys.stderr.write(" %s" % (out))
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
            print "<got SIGINT>"
            break
    return

def set_handles(pfix, error_only=False, **kwargs):
    # ancient, rotten code ... ugly, FIXME
# pfix can be:
#  o   a string, then the pf_dict will be created automatically
#  o   a dictionary with the following keys: err, out
#      each key points to a tuple with two values, the first
#      being an integer (0 ... do not create files, 1 ... create files)
#      the second being a filename. If the filename starts with a "/",
#      it is handled as an absolute path
    zmq_context = kwargs.get("zmq_context", None)
    ext_return = kwargs.get("ext_return", False)
    pf_dict = {}
    if type(pfix) in [str, unicode]:
        pf_dict = {"out" : (1, "%s.out" % (pfix)),
                   "err" : (1, "%s.err" % (pfix))}
    else:
        pf_dict = pfix
    if not "strict" in pf_dict:
        pf_dict["strict"] = True
    dirs = ["/var/log/cluster", "/tmp", "."]
    h_changed = 0
    for act_dir in dirs:
        if error_only:
            cvs = ["err"]
            close_num = [2]
        else:
            cvs = [x for x in ["out", "err"] if x in pf_dict.keys()]
            close_num = [0, 1, 2]
        h_names = {}
        new_h_struct = {}
        for cv in cvs:
            create_new, f_name = pf_dict[cv]
            new_name = f_name.startswith("/") and f_name or os.path.normpath("%s/%s" % (act_dir, f_name))
            h_names[cv] = (create_new, new_name)
        for name, (c_new, f_name) in h_names.iteritems():
            act_h = None
            if os.path.exists(f_name):
                n_stat = os.stat(f_name)
                if stat.S_ISSOCK(n_stat[stat.ST_MODE]):
                    if zmq_context is not None:
                        act_h, acth_t = (io_stream(f_name, zmq_context=zmq_context), "s")
                    else:
                        act_h, acth_t = (io_stream(f_name), "s")
            else:
                if not c_new:
                    break
            if not act_h:
                try:
                    act_h = file(f_name, "a", 0)
                except:
                    act_h = None
                    break
                else:
                    acth_t = "f"
                    try:
                        os.chmod(f_name, 0640)
                    except:
                        logging_tools.my_syslog("cannot chmod() '%s' to 0640" % (f_name))
            if act_h:
                new_h_struct[name] = {"handle" : act_h,
                                      "type"   : acth_t}
        if len(new_h_struct.keys()) < len(h_names.keys()):
            for act_h in new_h_struct.keys():
                new_h_struct[act_h]["handle"].close()
            new_h_struct = {}
        else:
            act_time = time.ctime(time.time())
            sys.stderr.close()
            if not error_only:
                sys.stdin.close()
                sys.stdout.close()
            for c_handle in close_num:
                os.close(c_handle)
            if not error_only:
                sys.stdin = file("/dev/null", "r")
                sys.stdout = new_h_struct["out"]["handle"]
                if new_h_struct["out"]["type"] == "f":
                    sys.stdout.write("starting at %s\n" % (act_time))
            sys.stderr = new_h_struct["err"]["handle"]
            if new_h_struct["err"]["type"] == "f":
                sys.stderr.write("starting at %s\n" % (act_time))
            h_changed = 1
            break
    if not h_changed and not pf_dict["strict"]:
        h_changed = 2
    if ext_return:
        return h_changed, new_h_struct
    else:
        return h_changed

def handles_write_endline(error_only=False):
    act_time = time.ctime(time.time())
    if error_only:
        t_handles = [sys.stderr]
    else:
        t_handles = [sys.stdout, sys.stderr]
    for t_handle in t_handles:
        if not isinstance(t_handle, io_stream):
            t_handle.write("ending at %s\n%s\n" % (act_time,
                                                   "-" * 40))

def renice(nice=16):
    try:
        os.nice(nice)
    except:
        logging_tools.my_syslog("Cannot renice to %d" % (nice))
    else:
        logging_tools.my_syslog("reniced to %d" % (nice))

def resolve_user(user):
    try:
        if type(user) in [int, long]:
            uid_stuff = pwd.getpwuid(user)
        else:
            uid_stuff = pwd.getpwnam(user)
    except KeyError:
        uid_stuff = None
    return uid_stuff

def change_user_group(user, group, groups=[], **kwargs):
    try:
        if type(user) in [int, long]:
            uid_stuff = pwd.getpwuid(user)
        else:
            uid_stuff = pwd.getpwnam(user)
        new_uid, new_uid_name = (uid_stuff[2], uid_stuff[0])
    except KeyError:
        new_uid, new_uid_name = (0, "root")
        logging_tools.my_syslog("Cannot find user '%s', using %s (%d)" % (user, new_uid_name, new_uid))
    try:
        if type(group) in [int, long]:
            gid_stuff = grp.getgrgid(group)
        else:
            gid_stuff = grp.getgrnam(group)
        new_gid, new_gid_name = (gid_stuff[2], gid_stuff[0])
    except KeyError:
        new_gid, new_gid_name = (0, "root")
        logging_tools.my_syslog("Cannot find group '%s', using %s (%d)" % (group, new_gid_name, new_gid))
    add_groups, add_group_names = ([], [])
    for add_grp in groups:
        try:
            addgrp_stuff = grp.getgrnam(add_grp)
            add_gid, add_gid_name = (addgrp_stuff[2], addgrp_stuff[0])
        except KeyError:
            add_gid, add_gid_name = (0, "root")
            logging_tools.my_syslog("Cannot find group '%s', using %s (%d)" % (add_grp, add_gid_name, add_gid))
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
        logging_tools.my_syslog("Trying to set additional groups to %s (%s)" % (", ".join(add_group_names), ", ".join(["%d" % (x) for x in add_groups])))
        os.setgroups(add_groups)
    logging_tools.my_syslog("Trying to drop pid %d from [%s (%d), %s (%d)] to [%s (%d), %s (%d)] ..." % (
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
        logging_tools.my_syslog("error changing uid / gid: %s" % (get_except_info()))
        ok = False
    else:
        ok = True
    logging_tools.my_syslog("  ... actual uid/gid of %d is now (%d/%d) ..." % (os.getpid(), new_uid, new_gid))
    return ok

def fix_sysconfig_rights():
    conf_dir = "/etc/sysconfig/cluster"
    target_group = "idg"
    os.chown(conf_dir, 0, grp.getgrnam(target_group)[2])
    os.chmod(conf_dir, 0775)

def change_user_group_path(path, user, group):
    try:
        if type(user) in [int, long]:
            uid_stuff = pwd.getpwuid(user)
        else:
            uid_stuff = pwd.getpwnam(user)
        new_uid, new_uid_name = (uid_stuff[2], uid_stuff[0])
    except KeyError:
        new_uid, new_uid_name = (0, "root")
        logging_tools.my_syslog("Cannot find user '%s', using %s (%d)" % (user, new_uid_name, new_uid))
    try:
        if type(group) in [int, long]:
            gid_stuff = grp.getgrgid(group)
        else:
            gid_stuff = grp.getgrnam(group)
        new_gid, new_gid_name = (gid_stuff[2], gid_stuff[0])
    except KeyError:
        new_gid, new_gid_name = (0, "root")
        logging_tools.my_syslog("Cannot find group '%s', using %s (%d)" % (group, new_gid_name, new_gid))
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
        logging_tools.my_syslog("Trying to change path '%s' from [%s (%d), %s (%d)] to [%s (%d), %s (%d)] ..." % (
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
        logging_tools.my_syslog("  ... actual uid/gid of %s is now (%d/%d) ..." % (path, new_uid, new_gid))
    else:
        logging_tools.my_syslog("  ... path '%s' does not exist" % (path))
    return ok

def become_daemon(debug=None, wait=0, mother_hook=None, mother_hook_args=None, **kwargs):
    os.chdir("/")
    debug_f = None
    if debug:
        try:
            debug_f = file(debug, "A")
        except:
            pass
    npid = os.fork()
    if debug_f:
        debug_f.write("First fork returned %d\n" % (npid))
    if npid:
        if wait:
            time.sleep(wait)
        if mother_hook:
            if mother_hook_args:
                mother_hook(*mother_hook_args)
            else:
                mother_hook()
        os._exit(0)
    os.setsid()
    os.umask(0)
    os.chdir("/")
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    npid = os.fork()
    if debug_f:
        debug_f.write("Second fork returned %d\n" % (npid))
    if npid:
        time.sleep(wait)
        os._exit(0)
    return True

def get_process_id_list(with_threadcount=True, with_dotprocs=False):
    max_try_count = 10
    for _idx in xrange(max_try_count):
        try:
            if with_dotprocs:
                pid_list, dotpid_list = (
                    [int(x) for x in os.listdir("/proc") if x.isdigit()],
                    [int(x[1:]) for x in os.listdir("/proc") if x.startswith(".") and x[1:].isdigit()]
                )
            else:
                pid_list, dotpid_list = (
                    [int(x) for x in os.listdir("/proc") if x.isdigit()],
                    []
                )
        except:
            pid_list, dotpid_list = ([], [])
        else:
            break
    if with_threadcount:
        pid_dict = {}
        for pid in pid_list:
            stat_f = "/proc/%d/status" % (pid)
            if os.path.isfile(stat_f):
                for _idx in range(max_try_count):
                    try:
                        stat_dict = dict([(z[0].lower(), z[1].strip()) for z in [y.split(":", 1) for y in [x.strip() for x in file(stat_f, "r").read().replace("\t", " ").split("\n") if x.count(":")]]])
                    except:
                        stat_dict = {}
                    else:
                        break
                pid_dict[pid] = int(stat_dict.get("threads", "1"))
            else:
                pid_dict[pid] = 1
        # add dotpid-files
        for pid in dotpid_list:
            stat_f = "/proc/.%d/status" % (pid)
            if os.path.isfile(stat_f):
                try:
                    stat_dict = dict([(z[0].lower(), z[1].strip()) for z in [y.split(":", 1) for y in [x.strip() for x in file(stat_f, "r").read().replace("\t", " ").split("\n") if x.count(":")]]])
                except:
                    pass
                else:
                    if "ppid" in stat_dict:
                        ppid = int(stat_dict["ppid"])
                        if ppid in pid_dict:
                            pid_dict[ppid] += 1
        return pid_dict
    else:
        return pid_list + [".%d" % (x) for x in dotpid_list]

def get_proc_list(last_dict=None, **kwargs):
    # s_time = time.time()
    s_fields = ["name", "state"]
    i_fields = ["pid", "uid", "gid", "ppid"]
    add_stat = kwargs.get("add_stat_info", False)
    add_affinity = kwargs.get("add_affinity", False)
    try:
        pid_list = [int(key) for key in os.listdir("/proc") if key.isdigit()]
    except:
        p_dict = last_dict
    else:
        p_dict = {}
        for pid in pid_list:
            check_pid = True
            if last_dict and pid in last_dict:
                p_dict[pid] = last_dict[pid]
                check_pid = False
            if check_pid:
                try:
                    status_lines = [(line.split() + ["", ""])[0 : 2] for line in open("/proc/%d/status" % (pid), "r").read().split("\n")]
                    stat_fields = open("/proc/%d/stat" % (pid), "r").read().split(")", 1)[1].split()
                except IOError:
                    pass
                else:
                    t_dict = {}
                    for what, rest in status_lines:
                        r_what = what.lower()[:-1]
                        if r_what in s_fields:
                            t_dict[r_what] = rest
                        elif r_what in i_fields:
                            t_dict[r_what] = int(rest)
                    try:
                        t_dict["cmdline"] = [line for line in codecs.open("/proc/%d/cmdline" % (pid), "r", "utf-8").read().split("\x00") if line]
                    except:
                        t_dict["cmdline"] = [get_except_info()]
                    if t_dict["pid"] == pid:
                        p_dict[pid] = t_dict
                    try:
                        t_dict["exe"] = os.readlink("/proc/%d/exe" % (pid))
                    except:
                        t_dict["exe"] = None
                    if len(stat_fields) > 36:
                        t_dict["last_cpu"] = int(stat_fields[36])
                    else:
                        t_dict["last_cpu"] = 0
                    if affinity_tools and add_affinity:
                        try:
                            t_dict["affinity"] = affinity_tools.get_process_affinity_mask(pid)
                        except:
                            # process has gone away ?
                            pass
                    if add_stat:
                        t_dict["stat_info"] = get_stat_info(pid)
    # print time.time()-s_time
    return p_dict

def bpt_show_childs(in_dict, idx, start):
    print " " * idx, start, in_dict[start]["name"]
    if in_dict[start]["childs"]:
        p_list = in_dict[start]["childs"].keys()
        for pid in p_list:
            bpt_show_childs(in_dict[start]["childs"], idx + 2, pid)

def build_ps_tree(pdict):
    def bpt_get_childs(master):
        r_dict = {}
        for pid in pdict.keys():
            if pdict[pid]["ppid"] == master:
                r_dict[pid] = pdict[pid]
                r_dict[pid]["master"] = master
                r_dict[pid]["childs"] = bpt_get_childs(pid)
        return r_dict
    # find master process (with ppid == 0)
    ps_tree = bpt_get_childs(0)
    # show_childs(ps_tree, 0,ps_tree.keys()[0])
    return ps_tree

def build_ppid_list(p_dict, pid=None):
    if not pid:
        pid = os.getpid()
        ppid_list = []
    else:
        ppid_list = [pid]
    while pid in p_dict and "ppid" in p_dict[pid]:
        pid = p_dict[pid]["ppid"]
        if pid:
            ppid_list.append(pid)
    return ppid_list

def build_kill_dict(name, exclude_list=[]):
    # process dict
    pdict = get_proc_list()
    # list of parent pids (up to init)
    ppl = build_ppid_list(pdict, os.getpid())
    kill_dict = {}
    for pid, p_struct in pdict.iteritems():
        if name.startswith(p_struct["name"]) and pid not in ppl and pid not in exclude_list:
            kill_dict[pid] = p_struct["name"]
    return kill_dict

def kill_running_processes(p_name=None, **kwargs):
    my_pid = os.getpid()
    exclude_pids = kwargs.get("exclude", [])
    kill_sig = kwargs.get("kill_signal", 9)
    if type(exclude_pids) != list:
        exclude_pids = [exclude_pids]
    if p_name is None:
        p_name = file("/proc/%d/status" % (my_pid), "r").readline().strip().split()[1]
    log_lines = ["my_pid is %d, searching for process '%s' to kill, kill_signal is %d, exclude_list is %s" % (
        my_pid,
        p_name,
        kill_sig,
        "empty" if not exclude_pids else ", ".join(["%d" % (exc_pid) for exc_pid in sorted(exclude_pids)]))]
    kill_dict = build_kill_dict(p_name, exclude_pids)
    any_killed = False
    if kill_dict:
        for pid, name in kill_dict.iteritems():
            if name not in kwargs.get("ignore_names", []):
                log_str = "%s (%d): Trying to kill pid %d (%s) with signal %d ..." % (
                    p_name,
                    my_pid,
                    pid,
                    name,
                    kill_sig)
                try:
                    os.kill(pid, kill_sig)
                except:
                    log_lines.append("%s error (%s)" % (log_str, get_except_info()))
                else:
                    log_lines.append("%s ok" % (log_str))
                    any_killed = True
    else:
        log_lines[-1] = "%s, nothing to do" % (log_lines[-1])
    wait_time = kwargs.get("wait_time", 1)
    if any_killed:
        log_lines.append("sleeping for %.2f seconds" % (wait_time))
    if kwargs.get("do_syslog", True):
        for log_line in log_lines:
            logging_tools.my_syslog(log_line)
    if any_killed:
        time.sleep(wait_time)
    return log_lines

def fd_change((uid, gid), d_name, files):
    os.chown("%s" % (d_name), uid, gid)
    for f_name in files:
        try:
            os.chown("%s/%s" % (d_name, f_name), uid, gid)
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
        logging_tools.my_syslog("Cannot find user '%s', using root (0)" % (user))
    try:
        if type(group) != str:
            named_gid = group
        else:
            named_gid = grp.getgrnam(group)[2]
    except KeyError:
        named_gid = 0
        logging_tools.my_syslog("Cannot find group '%s', using root (0)" % (group))
    if type(f_list) in [str, unicode]:
        f_list = [f_list]
    for act_dir in f_list:
        if type(act_dir) == dict:
            dir_name = act_dir["name"]
            dir_mode = act_dir.get("dir_mode", 0755)
            walk_dir = act_dir.get("walk_dir", True)
        elif type(act_dir) == set:
            dir_name, dir_mode = act_dir
            walk_dir = True
        else:
            dir_name, dir_mode, walk_dir = (act_dir, 0755, True)
        try_walk = True
        if not os.path.isdir(dir_name):
            try:
                os.makedirs(dir_name)
            except:
                logging_tools.my_syslog("Error creating directory '%s', except in walking : %s" % (dir_name, get_except_info()))
                try_walk = False
        if try_walk and walk_dir:
            try:
                os.chmod(dir_name, dir_mode)
            except OSError:
                logging_tools.my_syslog("Error changing mode of directory '%s', to %d : %s" % (dir_name, dir_mode, get_except_info()))
            try:
                os.path.walk(dir_name, fd_change, (named_uid, named_gid))
            except:
                logging_tools.my_syslog("Something went wrong while walking() '%s' (uid %d, gid %d): %s" % (
                    dir_name,
                    named_uid,
                    named_gid,
                    get_except_info()))

def fix_files(user, group, f_dict):
    try:
        named_uid = pwd.getpwnam(user)[2]
    except KeyError:
        named_uid = 0
        logging_tools.my_syslog("Cannot find user '%s', using root (0)" % (user))
    try:
        named_gid = grp.getgrnam(group)[2]
    except KeyError:
        named_gid = 0
        logging_tools.my_syslog("Cannot find group '%s', using root (0)" % (group))
    for act_file in f_dict:
        if os.path.isfile(act_file):
            try:
                os.chown(act_file, named_uid, named_gid)
            except:
                pass

def is_linux():
    return sys.platform in ["linux2", "linux3"]

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
            full_sock_name = "%s.%s" % (mach_name, full_sock_name.split(".")[1])
    return full_sock_name, mach_name

def get_programm_name():
    p_name = os.path.basename(sys.argv[0])
    if p_name.endswith(".py"):
        p_name = p_name[:-3]
    return p_name

def get_machine_name(short=True):
    if sys.platform in ["linux2", "linux3"]:
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
            c_name = file(f_name, "r").read().strip().split()[0]
        except:
            c_name = "error reading: %s" % (get_except_info())
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
            act_path = "%s/automount" % (act_p)
            if os.path.isfile(act_path):
                break
            else:
                act_path = ""
        self.__automount_path = act_path
        for act_p in ["/etc/init.d", "/etc/rc.d"]:
            act_path = "%s/autofs" % (act_p)
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
        return "%s restart" % (self.__autofs_path)
    def check(self):
        stat, out = commands.getstatusoutput("%s status" % (self.__autofs_path))
        a_dict = {"c" : {},
                  "r" : {}}
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
                ret_f.append("%s from %s (%s)" % (logging_tools.get_plural("map", len(m_points)),
                                                  used_type,
                                                  ", ".join(m_points)))
            return ", ".join(ret_f)
        else:
            return "None defined"

def get_arp_dict():
    try:
        arp_dict = dict([(line_p[3].lower(), line_p[0]) for line_p in [line.strip().split() for line in file("/proc/net/arp", "r").read().split("\n")[1:]] if line_p])
    except:
        arp_dict = {}
    return arp_dict

def get_char_block_device_dict():
    # parses /proc/devices and returns two dicts
    char_dict, block_dict = ({}, {})
    try:
        lines = [line.strip().lower() for line in file("/proc/devices", "r").read().split("\n") if line.strip()]
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
        ret_dict = dict([(c_line[0].strip(), c_line[1].strip()) for c_line in [line.strip().lower().split("=", 1) for line in file(f_name, "r").read().split("\n") if line.strip() and not line.strip().startswith("#") and line.count("=")]])
    return ret_dict

def fetch_sysinfo(root_dir="/"):
    log_lines, sys_dict = ([], {})
    try:
        isl = [x.strip().lower() for x in file("%s/etc/issue" % (root_dir), "r").read().split("\n")]
        if os.path.isfile("%s/etc/redhat-release" % (root_dir)):
            isl.extend([x.strip().lower() for x in file("%s/etc/redhat-release" % (root_dir), "r").read().split("\n")])
        if os.path.isfile("%s/etc/fedora-release" % (root_dir)):
            isl.extend([x.strip().lower() for x in file("%s/etc/fedora-release" % (root_dir), "r").read().split("\n")])
    except:
        log_lines.append(("error invalid root_path '%s' ?" % (root_dir), logging_tools.LOG_LEVEL_CRITICAL))
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
            arch_com = "file %s" % (ls_path)
            c_stat, out = commands.getstatusoutput(arch_com)
            if c_stat:
                log_lines.append(("Cannot execute %s (%d): %s" % (arch_com, c_stat, out), logging_tools.LOG_LEVEL_ERROR))
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
            # check for sles
            if re.search("sles", arch_str):
                arch_m = re.match("^.*suse sles (\d+).*$", arch_str)
                sys_dict["version"] = "sles%s" % (arch_m.group(1))
            elif re.search("enterprise server", arch_str):
                arch_m = re.match("^.*enterprise server (\d+).*$", arch_str)
                sys_dict["version"] = "sles%s" % (arch_m.group(1))
                sr_dict = _read_issue_file("/etc/SuSE-release")
                if "patchlevel" in sr_dict:
                    sys_dict["version"] = "%s.%s" % (sys_dict["version"],
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
                        isl = [y for y in [x.strip().lower() for x in file("/etc/SuSE-release", "r").read().split("\n")] if y]
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
                        isl = [x.strip().lower() for x in file("/etc/SLOX-release", "r").read().split("\n")]
                    except:
                        pass
                    else:
                        sr_ems = True
                        ems_file = "/etc/SLOX-release"
                    if sr_ems:
                        try:
                            isl = [x.strip().lower() for x in file(ems_file, "r").read().split("\n")]
                        except:
                            pass
                        else:
                            for eml in isl:
                                if len(eml):
                                    eml_m = re.match("^version\s*=\s*(.*)$", eml)
                                    if eml_m:
                                        sys_dict["version"] = "sox%s" % (eml_m.group(1))
                elif sys_dict["vendor"] == "redhat":
                    if re.search("enterprise linux", arch_str):
                        arch_m = re.match("^.*nterprise linux (?P<type>\S+)\s*release\s*(?P<version>\S+)\s+.*$", arch_str)
                        if arch_m:
                            sys_dict["version"] = "%s%s" % (arch_m.group("type"),
                                                            arch_m.group("version"))
                elif sys_dict["vendor"] == "debian" and os.path.isdir("/etc/apt"):
                    # try to get info from /etc/apt
                    try:
                        s_list = [z[2].split("/")[0] for z in [y.split() for y in [x.strip() for x in file("/etc/apt/sources.list", "r").read().split("\n")] if y and not y.startswith("#")] if len(z) > 3]
                    except:
                        pass
                    else:
                        # unify list
                        s_list = dict([(x, 0) for x in s_list]).keys()
                        # hack
                        sys_dict["version"] = s_list[0]
    return log_lines, sys_dict

def find_file(file_name, s_path=None):
    if not s_path:
        s_path = ["/opt/cluster/sbin", "/opt/cluster/bin", "/bin", "/usr/bin", "/sbin", "/usr/sbin"]
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
    chars = kwargs.get("chars", "%s%s%s" % (
        def_chars,
        def_chars.upper(),
        "".join(["%d" % (idx) for idx in range(0, 10)])))
    if kwargs.get("special_characters", False):
        chars = "%s!§$%%&/()[]#+*~" % (chars)
    length = kwargs.get("lenght", 8)
    return "".join([chars[random.randrange(len(chars))] for idx in xrange(length)])

def get_sys_bits():
    return int(platform.architecture()[0][0:2])

if __name__ == "__main__":
    print "Loadable module, exiting..."
    sys.exit(0)
