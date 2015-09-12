# Copyright (C) 2001-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file belongs to host-monitoring
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

import commands
import os
import stat
import time

from initat.host_monitoring import filesys_tools
from initat.host_monitoring import limits, hm_classes
from initat.tools import logging_tools, process_tools, server_command


class _general(hm_classes.hm_module):
    def _parse_ecd(self, in_str):
        # parse exclude_checkdate, ecd has the form [WHHMM][-WHHMM]
        # W ... weekday, 1 ... monday, 7 ... sunday
        if in_str.count("-"):
            start_str, end_str = in_str.strip().split("-")
            if not len(start_str):
                start_str = None
            if not len(end_str):
                end_str = None
        else:
            start_str, end_str = (in_str.strip(), None)
        return (self._parse_ecd2(start_str), self._parse_ecd2(end_str))

    def _parse_ecd2(self, in_str):
        if in_str is None:
            return in_str
        else:
            if len(in_str) != 5 or not in_str.isdigit():
                raise SyntaxError("exclude_checkdate '{}' has wrong form (not WHHMM)".format(in_str))
            weekday, hour, minute = (
                int(in_str[0]),
                int(in_str[1:3]),
                int(in_str[3:5])
            )
            if weekday < 1 or weekday > 7:
                raise SyntaxError("exclude_checkdate '%s' has invalid weekday" % (in_str))
            if hour < 0 or hour > 23:
                raise SyntaxError("exclude_checkdate '%s' has invalid hour" % (in_str))
            if minute < 0 or minute > 59:
                raise SyntaxError("exclude_checkdate '%s' has invalid minute" % (in_str))
            return (weekday, hour, minute)


class check_file_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
        self.parser.add_argument("--mod", dest="mod_diff_time", type=int)
        self.parser.add_argument("--size", dest="min_file_size", type=int)
        self.parser.add_argument("--exclude-checkdate", dest="exclude_checkdate", type=str)

    def __call__(self, srv_com, cur_ns):
        if "arguments:arg0" not in srv_com:
            srv_com.set_result("need filename", server_command.SRV_REPLY_STATE_ERROR)
        else:
            file_name = srv_com["arguments:arg0"].text.strip()
            if os.path.isfile(file_name):
                f_stat = os.stat(file_name)
                stat_keys = [key for key in dir(f_stat) if key.startswith("st_")]
                f_stat = dict([(key, getattr(f_stat, key)) for key in stat_keys])
                srv_com["stat_result"] = {
                    "file": file_name,
                    "stat": f_stat,
                    "local_time": time.time()
                }
            else:
                srv_com.set_result("file '{}' not found".format(file_name), server_command.SRV_REPLY_STATE_ERROR)

    def interpret(self, srv_com, cur_ns):
        return self._interpret(srv_com["stat_result"], cur_ns)

    def interpret_old(self, result, cur_ns):
        return self._interpret(hm_classes.net_to_sys(result[3:]), cur_ns)

    def _interpret(self, f_dict, cur_ns):
        ret_state = limits.nag_STATE_OK
        file_stat = f_dict["stat"]
        if type(file_stat) == dict:
            file_size = file_stat["st_size"]
            file_mtime = file_stat["st_mtime"]
        else:
            file_size = file_stat[stat.ST_SIZE]
            file_mtime = file_stat[stat.ST_MTIME]
        add_array = ["size %s" % (logging_tools.get_size_str(file_size))]
        act_time = time.localtime()
        act_time = (act_time.tm_wday + 1,
                    act_time.tm_hour,
                    act_time.tm_min)
        act_time = act_time[2] + 60 * (act_time[1] + 24 * act_time[0])
        in_exclude_range = False
        if cur_ns.exclude_checkdate:
            for s_time, e_time in cur_ns.exclude_checkdate:
                if s_time:
                    s_time = s_time[2] + 60 * (s_time[1] + 24 * s_time[0])
                if e_time:
                    e_time = e_time[2] + 60 * (e_time[1] + 24 * e_time[0])
                if s_time and e_time:
                    if s_time <= act_time and act_time <= e_time:
                        in_exclude_range = True
                if s_time:
                    if s_time <= act_time:
                        in_exclude_range = True
                if e_time:
                    if act_time <= e_time:
                        in_exclude_range = True
        if in_exclude_range:
            add_array.append("in exclude_range")
        else:
            if cur_ns.mod_diff_time:
                md_time = abs(file_mtime - f_dict["local_time"])
                if md_time > cur_ns.mod_diff_time:
                    ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                    add_array.append("changed %s ago > %s" % (logging_tools.get_diff_time_str(md_time),
                                                              logging_tools.get_diff_time_str(cur_ns.mod_diff_time)))
                else:
                    add_array.append("changed %s ago < %s" % (logging_tools.get_diff_time_str(md_time),
                                                              logging_tools.get_diff_time_str(cur_ns.mod_diff_time)))
        return ret_state, "file %s %s" % (f_dict["file"],
                                          ", ".join(add_array))


class call_script_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
        self.parser.add_argument("--at-time", dest="time", type=int, default=0)
        self.parser.add_argument("--use-at", dest="use_at", default=False, action="store_true")

    def __call__(self, srv_com, cur_ns):
        if "arguments:arg0" not in srv_com:
            srv_com.set_result(
                "call_script(): missing argument",
                server_command.SRV_REPLY_STATE_ERROR,
            )
        else:
            script_name = srv_com["arguments:arg0"].text
            args = []
            while "arguments:arg%d" % (len(args) + 1) in srv_com:
                args.append(srv_com["arguments:arg%d" % (len(args) + 1)].text)
            if os.path.isfile(script_name):
                if cur_ns.time:
                    cur_ns.use_at = True
                info_str = "Starting script %s with %s: %s" % (
                    script_name,
                    logging_tools.get_plural("argument", len(args)),
                    " ".join(args))
                if cur_ns.use_at:
                    info_str = "%s after %s" % (
                        info_str,
                        logging_tools.get_plural("minute", cur_ns.time))
                self.log(info_str)
                if cur_ns.use_at:
                    c_stat, log_lines = process_tools.submit_at_command(
                        " ".join([script_name] + args),
                        cur_ns.time)
                    ipl = "\n".join(log_lines)
                else:
                    c_stat, ipl = commands.getstatusoutput(
                        " ".join([script_name] + args))
                    log_lines = ipl.split("\n")
                self.log(" - gave stat %d (%s):" % (c_stat,
                                                    logging_tools.get_plural("log line", len(log_lines))))
                for line in map(lambda s_line: s_line.strip(), log_lines):
                    self.log("   - %s" % (line))
                if c_stat:
                    srv_com.set_result(
                        "problem while executing {}: {}".format(script_name, ipl),
                        server_command.SRV_REPLY_STATE_ERROR
                    )
                else:
                    srv_com.set_result(
                        "script {} gave: {}".format(script_name, ipl)
                    )
            else:
                srv_com.set_result(
                    "script {} not found".format(script_name),
                    server_command.SRV_REPLY_STATE_ERROR
                )

    def interpret(self, srv_com, cur_ns):
        return limits.nag_STATE_OK, srv_com["result"].attrib["reply"]


class create_dir_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        filesys_tools.create_dir(srv_com, self.log)


class remove_dir_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        filesys_tools.remove_dir(srv_com, self.log)


class get_dir_tree_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        filesys_tools.get_dir_tree(srv_com, self.log)


class get_file_content_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        filesys_tools.get_file_content(srv_com, self.log)


class set_file_content_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        filesys_tools.set_file_content(srv_com, self.log)


class check_mount_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
        self.parser.add_argument("--type", default="nfs", type=str)

    def __call__(self, srv_com, cur_ns):
        if len(cur_ns.arguments) != 1:
            srv_com.set_result(
                "missing argument",
                server_command.SRV_REPLY_STATE_ERROR,
            )
        else:
            path_name = cur_ns.arguments[0]
            _dict = {_entry[1]: _entry for _entry in [_line.strip().split() for _line in file("/etc/mtab", "r").readlines() if _line.strip()]}
            if path_name in _dict:
                srv_com["mpinfo"] = _dict[path_name]
            else:
                srv_com.set_result(
                    "path '{}' not found in mtab".format(path_name),
                    server_command.SRV_REPLY_STATE_ERROR
                )

    def interpret(self, srv_com, cur_ns):
        mount_info = srv_com["*mpinfo"]
        # target_type
        _errors, _warnings = ([], [])
        t_type = cur_ns.type
        _ret_f = ["from {}".format(mount_info[0])]
        if mount_info[2] != t_type:
            _warnings.append("type differs: {} != {}".format(mount_info[2], t_type))
        else:
            _ret_f.append("type is {}".format(t_type))
        if _errors:
            ret_state = limits.nag_STATE_CRITICAL
            _ret_f.extend(_errors)
        elif _warnings:
            ret_state = limits.nag_STATE_WARNING
            _ret_f.extend(_warnings)
        else:
            ret_state = limits.nag_STATE_OK
        return ret_state, "mountpoint {}: {}".format(
            mount_info[1],
            ", ".join(_ret_f)
        )


class check_dir_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)

    def __call__(self, srv_com, cur_ns):
        if len(cur_ns.arguments) != 1:
            srv_com.set_result(
                "missing argument",
                server_command.SRV_REPLY_STATE_ERROR,
            )
        else:
            dir_name = cur_ns.arguments[0]
            link_followed = False
            while os.path.islink(dir_name):
                link_followed = True
                dir_name = os.readlink(dir_name)
            if os.path.isdir(dir_name):
                f_stat = os.stat(dir_name)
                srv_com["result"].append(
                    srv_com.builder(
                        "dir_stat",
                        directory=dir_name,
                        local_time="{}".format(time.time()),
                        link_followed="1" if link_followed else "0",
                    )
                )
                srv_com["result:dir_result:stat"] = {key: getattr(stat, key) for key in dir(f_stat) if key.startswith("ST")}
            else:
                srv_com.set_result(
                    "directory {} not found".format(dir_name),
                    server_command.SRV_REPLY_STATE_ERROR
                )

    def interpret(self, srv_com, cur_ns):
        return limits.nag_STATE_OK, "dir {} exists".format(srv_com["result:dir_stat"].attrib["directory"])
