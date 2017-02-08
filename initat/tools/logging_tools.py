# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2017 Andreas Lang-Nevyjel
#
# this file is part of python-modules-base
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" logging tools, base code """

import bz2
import datetime
import gzip
import logging
import logging.handlers
import os
import re
import stat
import string
import sys
import syslog
import time

from pygments.token import Token

LOG_LEVEL_OK = 20
LOG_LEVEL_WARN = 30
LOG_LEVEL_ERROR = 40
LOG_LEVEL_CRITICAL = 50

# add the levels to the logging dict
logging.addLevelName(LOG_LEVEL_OK, "ok")
logging.addLevelName(LOG_LEVEL_WARN, "warn")
logging.addLevelName(LOG_LEVEL_ERROR, "err")
logging.addLevelName(LOG_LEVEL_CRITICAL, "crit")

# default unified name
UNIFIED_NAME = "unified"


def rewrite_log_destination(log_dest):
    if log_dest.startswith("uds:"):
        log_dest = log_dest.replace("uds:", "ipc://")
    if log_dest.startswith("ipc://"):
        if not log_dest.endswith("_zmq"):
            log_dest = "{}_zmq".format(log_dest)
    return log_dest


def map_old_to_new_level(in_level):
    return {
        0: LOG_LEVEL_OK,
        5: LOG_LEVEL_WARN,
        10: LOG_LEVEL_ERROR,
        20: LOG_LEVEL_CRITICAL,
    }.get(in_level, in_level)


def map_log_level_to_log_status(log_lev):
    return {
        LOG_LEVEL_OK: "i",
        LOG_LEVEL_WARN: "w",
        LOG_LEVEL_ERROR: "e",
        LOG_LEVEL_CRITICAL: "c",
    }.get(log_lev, "c")


def get_log_level_str(level):
    return {
        LOG_LEVEL_OK: "ok",
        LOG_LEVEL_WARN: "warn",
        LOG_LEVEL_ERROR: "err",
        LOG_LEVEL_CRITICAL: "crit"
    }.get(level, "lev{:d}".format(level))


def get_relative_dt(dt_struct):
    act_time = datetime.datetime.now()
    if dt_struct < act_time:
        # in past
        diff_days = (
            datetime.date(act_time.year, act_time.month, act_time.day) -
            datetime.date(dt_struct.year, dt_struct.month, dt_struct.day)
        ).days
        if diff_days < 2:
            if diff_days == 1:
                return dt_struct.strftime("yesterday %H:%M:%S")
            elif diff_days == 0:
                return dt_struct.strftime("today %H:%M:%S")
            else:
                return dt_struct.strftime("%a, {:d} days ago %H:%M:%S".format(int(diff_days)))
    else:
        # in future
        diff_days = (
            datetime.date(dt_struct.year, dt_struct.month, dt_struct.day) -
            datetime.date(act_time.year, act_time.month, act_time.day)
        ).days
        if diff_days < 2:
            if diff_days == 1:
                return dt_struct.strftime("tomorrow %H:%M:%S")
            elif diff_days == 0:
                return dt_struct.strftime("today %H:%M:%S")
            else:
                return dt_struct.strftime("%a, in {:d} days %H:%M:%S".format(int(diff_days)))
    return dt_struct.strftime("%a, %d. %b %Y %H:%M:%S")


def only_printable(in_str):
    return "".join([_chr for _chr in in_str if _chr in string.printable])


def get_plural(in_str, num, show_int=1, fstr_len=0, **kwargs):
    if isinstance(num, list) or isinstance(num, set):
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
        f_str = "{{:{:d}d}} ".format(fstr_len)
    elif fstr_len < 0:
        f_str = "{{:0{:d}d}} ".format(abs(fstr_len))
    else:
        f_str = "{:d} "
    return "{}{}{}".format(
        (show_int and f_str.format(int(r_num))) or "",
        in_str[0:end_idx],
        p_str
    )


def get_size_str(in_s, long_format=False, divider=1024, strip_spaces=False, long_version=True, per_second=False, to_int=False):
    if isinstance(in_s, str):
        _len_in_s = len(in_s)
    else:
        _len_in_s = in_s
    b_str = long_format and "Byte" or "B"
    if per_second:
        b_str = "{}/s".format(b_str)
    pf_f, pf_str = (["k", "M", "G", "T", "P", "E"], "")
    while in_s > divider:
        if (in_s / float(divider) * float(divider)) != in_s and to_int:
            break
        in_s = in_s / float(divider)
        if to_int:
            in_s = int(in_s)
        pf_str = pf_f.pop(0)
    if to_int:
        ret_str = "{:d} {}{}".format(
            in_s,
            pf_str,
            b_str,
        )
    else:
        ret_str = "{} {}{}".format(
            pf_str and "{:6.2f}".format(float(in_s)) or "{:4d}".format(int(in_s)),
            pf_str,
            b_str
        )
    if strip_spaces:
        ret_str = " ".join(ret_str.split())
    return ret_str


def interpret_size_str(in_str, **kwargs):
    size_re = re.compile("^(?P<value>\d+(\.\d+)*)\s*(?P<pfix>.*?)b*(yte)*s*$", re.IGNORECASE)
    size_m = size_re.match(in_str)
    if size_m:
        value = float(size_m.group("value"))
        pfix = size_m.group("pfix").lower()
        value = int(
            value * {
                "m": 1024 * 1024,
                "mi": 1000 * 1000,
                "g": 1024 * 1024 * 1024,
                "gi": 1000 * 1000 * 1000,
                "t": 1024 * 1024 * 1024 * 1024,
                "ti": 1000 * 1000 * 1000 * 1000,
            }.get(pfix, 1)
        )
        return value
    else:
        return 0


def get_diff_time_str(diff_secs, **kwargs):
    if isinstance(diff_secs, datetime.timedelta):
        diff_secs = diff_secs.total_seconds()
    abs_diffs = abs(diff_secs)
    is_int = isinstance(abs_diffs, int)
    _long = kwargs.get("long", True)
    _secs = {
        True: "seconds",
        False: "s",
    }[_long]
    if abs_diffs < 0.0001:
        diff_str = "{:.3f} u{}".format(abs_diffs * 1000000, _secs)
    elif abs_diffs < 0.1:
        diff_str = "{:.3f} m{}".format(abs_diffs * 1000, _secs)
    else:
        abs_mins, abs_hours = (0, 0)
        if abs_diffs > 60:
            abs_mins = int(abs_diffs / 60)
            abs_secs = int(abs_diffs - 60 * abs_mins)
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
                        diff_str = "{:d}y {:3d}d {:02d}:{:02d}:{:02d}".format(abs_years, abs_days, abs_hours, abs_mins, abs_secs)
                    else:
                        diff_str = "{:d}d {:02d}:{:02d}:{:02d}".format(abs_days, abs_hours, abs_mins, abs_secs)
                else:
                    diff_str = "{:d}:{:02d}:{:02d}".format(abs_hours, abs_mins, abs_secs)
            else:
                diff_str = "{:d}:{:02d}".format(abs_mins, abs_secs)
        else:
            diff_str = "{} {}".format(
                "{:d}".format(abs_diffs) if is_int else "{:.2f}".format(abs_diffs),
                _secs,
            )
    if diff_secs < 0:
        diff_str = "{} [NEGATIVE TIME]".format(diff_str)
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
                hms_f.append("{:02d}".format(int(hms)))
            else:
                hms_f.append("{:d}".format(int(hms)))
            any_written = True
        else:
            if any_written:
                hms_f.append("{:02d}".format(int(hms)))
    out_f.append(":".join(hms_f))
    return " ".join(out_f)


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
                get_diff_time_str(diff_time / self.__sum_lc if self.__sum_lc else 0)
            )
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
                info_str = " (rate: {:.2f} / sec)".format(self.__sum_lc / time_spent)
            else:
                info_str = ""
            if kwargs.get("info_str", ""):
                info_str = "{}, {}".format(info_str, kwargs["info_str"])
            log_str = "{} {:d}, {:5.2f} %, {:d} ({}) to go{}".format(
                self.__action,
                self.__lc,
                100. * (self.__sum_lc / float(max(1, self.__total_count))),
                self.__start_count,
                get_diff_time_str(time_to_go),
                info_str
            )
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
        if isinstance(l_p, int):
            l_p = str(l_p)
        if isinstance(l_p, str):
            l_p = [l_p]
        self.lines.append(tuple(l_p))

    def set_column_separator(self, def_val=" "):
        self.col_separator = def_val

    def set_format_string(self, row_idx, r_t="s", left="-", pre_string="", post_string="", min_size=0):
        if left == "-":
            left = "<"
        if isinstance(row_idx, str):
            row_idx = {v: k for k, v in self.header_dict.items()}[row_idx]
        if row_idx == -1:
            act_row_idx = self.act_row_idx + 1
        else:
            act_row_idx = row_idx
        self.form_dict[act_row_idx] = (r_t, left, pre_string, post_string, 0)
        self.act_row_idx = act_row_idx

    def set_header_string(self, row_idx, header):
        if isinstance(header, list):
            for idx in range(len(header)):
                self.header_dict[row_idx + idx] = header[idx]
        else:
            self.header_dict[row_idx] = header

    def __str__(self):
        if self.raw_mode:
            out_lines = [";".join([self.header_dict.get(idx, "").strip() for idx in range(len(list(self.header_dict.keys())))])]
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
                tp_str, lf_str, pre_str, post_str, min_len = self.form_dict.get(idx, ("s", "<", "", "", 0))
                act_len = max(row_lens[idx], min_len, len(self.header_dict.get(idx, "")))
                if tp_str.endswith("f") and tp_str.startswith("."):
                    b_f_parts.append(("{}{{:{}{:d}{}}}{}".format(pre_str, lf_str, act_len, tp_str, post_str)))
                else:
                    b_f_parts.append(("{}{{:{}{:d}{}}}{}".format(pre_str, lf_str, act_len, tp_str, post_str)))
                h_f_parts.append(("{}{{:{}{:d}}}{}".format(pre_str, lf_str, act_len, post_str)))
            b_form_str_dict = {num_rows: self.col_separator.join(b_f_parts)}
            h_form_str_dict = {num_rows: self.col_separator.join(h_f_parts)}
            for idx in range(1, len(b_f_parts)):
                b_form_str_dict[idx] = self.col_separator.join(b_f_parts[0:idx - 1] + ["{}"])
                h_form_str_dict[idx] = self.col_separator.join(h_f_parts[0:idx - 1] + ["{}"])
            out_lines = []
            if self.header_dict:
                headers = [self.header_dict.get(idx, "") for idx in range(len(list(self.header_dict.keys())))]
                out_lines.append((h_form_str_dict[len(headers)].format(*headers)).rstrip())
                out_lines.append("-" * len(out_lines[-1]))
            for l_p in self.lines:
                # print len(l_p), b_form_str_dict
                # print b_form_str_dict[len(l_p)]
                out_lines.append((b_form_str_dict[len(l_p)].format(*l_p)).rstrip())
        return "\n".join(out_lines)

    def __len__(self):
        return len(self.lines)

    def __unicode__(self):
        return self.__str__()


class form_entry(object):
    def __init__(self, content, **kwargs):
        self.content = content
        self.left = True
        self.center = False
        self.min_width = 0
        self.pre_str = ""
        self.post_str = ""
        for key, value in kwargs.items():
            setattr(self, key, value)
        setattr(
            self,
            "content_type", {
                str: "s",
                type(None): "s",
                int: "d",
                float: "f",
                datetime.date: "s",
                datetime.datetime: "s",
                bool: "b",
            }.get(type(self.content), "s")
        )

    def has_key(self, key):
        return hasattr(self, key)

    def __contains__(self, key):
        return hasattr(self, key)

    def __getitem__(self, key):
        return getattr(self, key)

    def min_len(self):
        return max(len(str(self)), self.min_width)

    def __str__(self):
        return self.form_str().format(self.content)

    def form_str(self, max_len=None):
        if self.content_type == "d":
            form_str = "d"
        elif self.content_type == "f":
            form_str = "f"
        elif self.content_type == "b":
            form_str = "d"
        else:
            form_str = "s"
        if max_len is None:
            form_str = "{{:{}}}".format(form_str)
        else:
            if self.left:
                _f = "<"
            elif self.center:
                _f = "^"
            else:
                _f = ">"
            form_str = "{{:{}{:d}{}}}".format(
                _f,
                max_len,
                form_str,
            )
        return "{}{}{}".format(self.pre_str, form_str, self.post_str)

    def format(self, max_len):
        return self.form_str(max_len).format(self.content)


class form_entry_right(form_entry):
    def __init__(self, content, **kwargs):
        form_entry.__init__(self, content, left=False, **kwargs)


class form_entry_center(form_entry):
    def __init__(self, content, **kwargs):
        form_entry.__init__(self, content, left=False, center=True, **kwargs)


class NewFormList(object):
    def __init__(self, **kwargs):
        self.__content = []
        self.__header_dict = {}
        self.__col_sep = kwargs.get("column_separator", " ")
        self.__strict_mode = kwargs.get("strict_mode", False)
        self.__none_string = kwargs.get("none_string", "None")
        self.__da_map = kwargs.get("display_attribute_map", None)
        # self.__format_dict = {}

    def append(self, add_list):
        # add list is a list of dicts
        for row_idx, item in enumerate(add_list):
            if item.content is None:
                item.content = self.__none_string
            if "header" in item:
                self.__header_dict[row_idx] = (item["left"], item["header"])
        self.__content.append(add_list)

    def extend(self, add_list):
        [self.append(_line) for _line in add_list]

    def __str__(self):
        return self.__unicode__()

    def get_da_map(self):
        return self.__da_map

    def set_da_map(self, value):
        self.__da_map = value

    display_attribute_map = property(get_da_map, set_da_map)

    def __unicode__(self):
        if not self.__content:
            if self.__strict_mode:
                raise ValueError("empty list (no lines)")
            else:
                return ""
        return self._format()

    def prompt_encode(self):
        return self._format(prompt=True)

    def _format(self, prompt=False):
        # count number of rows
        row_count = [len(line) for line in self.__content]
        _min_rows, max_rows = (
            min(row_count),
            max(row_count),
        )
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
                    row_lens = [
                        max(old_len, new_len) for old_len, new_len in zip(
                            row_lens[:line_rows - 1],
                            line_lens[:line_rows - 1],
                        )
                    ] + row_lens[line_rows - 1:]
            else:
                # count all rows
                row_lens = [
                    max(old_len, new_len) for old_len, new_len in zip(row_lens, line_lens)
                ]
        # take header into account
        row_lens = [
            max(
                old_len,
                len(self.__header_dict.get(idx, (True, ""))[1])
            ) for idx, old_len in enumerate(row_lens)
        ]
        out_lines = []
        if self.__header_dict:
            header_list = [self.__header_dict.get(idx, (True, "")) for idx in range(max_rows)]
            form_str = self.__col_sep.join(
                [
                    "{{:{}{:d}s}}".format(
                        "<" if header_list[idx][0] else "",
                        row_len
                    ) for idx, row_len in enumerate(row_lens)
                ]
            )
            out_lines.append(
                form_str.format(*[_e[1] for _e in header_list]).rstrip()
            )
            out_lines.append(
                "-" * len(out_lines[-1])
            )
        if prompt:
            # add one for CR
            out_lines = [[(Token.String.ICSW.Header, _line)] for _line in out_lines]
            for line in self.__content:
                _line = []
                for _idx, (entry, max_len) in enumerate(zip(line, row_lens[:len(line)])):
                    last = _idx == len(line) - 1
                    _str = entry.format(max_len)
                    if last:
                        _str = _str.rstrip()
                    _line.append(
                        (
                            getattr(
                                Token.String.ICSW,
                                getattr(entry, "display_attribute", "dummy").title() or "Dummy"
                            ),
                            _str
                        )
                    )
                    if not last:
                        _line.append(
                            (Token.String.ICSW.Dummy, self.__col_sep)
                        )
                out_lines.append(_line)
            return out_lines
        else:
            for line in self.__content:
                out_lines.append(
                    self.__col_sep.join(
                        [
                            self._apply_da_map(entry, max_len) for entry, max_len in zip(
                                line,
                                row_lens[:len(line)]
                            )
                        ]
                    )
                )
            return "\n".join([line.rstrip() for line in out_lines])

    def _apply_da_map(self, entry, max_len):
        _str = entry.format(max_len)
        if self.__da_map:
            da_name = getattr(entry, "display_attribute", None)
            if da_name in self.__da_map:
                _str = self.__da_map[da_name].format(_str)
        return _str

    def __len__(self):
        return len(self.__content)


def get_icsw_prompt_styles():
    return {
        Token.String.ICSW.Header: "bold",
        Token.String.ICSW.Dummy: "",
        Token.String.ICSW.Ok: "#00ff00",
        Token.String.ICSW.Warning: "#ffff00 bold",
        Token.String.ICSW.Critical: "#ff0000 bold",
    }


def compress_list(ql, **kwargs):
    # node prefix, postfix, start_string, end_string
    def add_p(np, ap, s_str, e_str):
        if s_str == e_str:
            return "{}{}{}".format(np, s_str, ap)
        elif int(s_str) + 1 == int(e_str):
            return "{}{}{}/{}{}".format(np, s_str, ap, e_str, ap)
        else:
            return "{}{}{}-{}{}".format(np, s_str, ap, e_str, ap)
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
    for pef in list(nc_dict.keys()):
        for pof in list(nc_dict[pef].keys()):
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
    if isinstance(ql, list):
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
    if s_num is not None:
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
        if isinstance(out_str, str):
            syslog.syslog(log_type, str(out_str))
        else:
            syslog.syslog(log_type, out_str.encode("utf-8"))
    except:
        exc_info = sys.exc_info()
        error_str = "({}, {})".format(
            str(exc_info[0]),
            str(exc_info[1]),
        )
        if isinstance(out_str, str):
            syslog.syslog(
                syslog.LOG_ERR | syslog.LOG_USER,
                "error logging unicode ({}, len {:d}, log_type {:d})".format(
                    error_str,
                    len(out_str),
                    log_type
                )
            )
        else:
            syslog.syslog(
                syslog.LOG_ERR | syslog.LOG_USER,
                "error logging string ({}, len {:d}, log_type {:d})".format(
                    error_str,
                    len(str(out_str)),
                    log_type
                )
            )
    if out:
        print(out_str)


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
            try:
                msg = "{}\n".format(self.format(record))
            except:
                msg = self.format(record) + "\n"
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
                    my_syslog(
                        "cannot remove file '{}' ({:d} > {:d} days)".format(
                            f_name,
                            act_age,
                            self.max_age
                        ),
                        LOG_LEVEL_ERROR
                    )
                else:
                    my_syslog(
                        "removed file '{}' ({:d} > {:d} days)".format(
                            f_name,
                            act_age,
                            self.max_age
                        )
                    )

    def doRollover(self):
        self._cleanup_old_logfiles()
        self.stream.close()
        act_time = time.localtime()
        base_postfix = "{:04d}{:02d}{:02d}".format(act_time[0], act_time[1], act_time[2])
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
                gz_postfix
            )
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
            my_syslog(
                "error opening {}: {} ({})".format(
                    gz_file_name,
                    str(exc_info[0]),
                    str(exc_info[1]),
                )
            )
        else:
            act_z.write(open(self.baseFilename, "r").read().encode("utf-8"))
            act_z.close()
            os.chmod(gz_file_name, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
            self.stream.close()
            os.unlink(self.baseFilename)
            self.stream = self._open()
            os.chmod(self.baseFilename, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
            self.mode = "w"
            self.stream = self._open()


def list_to_struct(in_list, **kwargs):
    # minimum size for matching prefixes
    pf_min_size = kwargs.get("prefix_min_size", 1)
    # reduce list and create a strcuture
    if len(in_list) == 1:
        return [("", in_list)]
    # find longest common prefix
    _len = 0
    if in_list:
        _min_len = min([len(_v) for _v in in_list])
    else:
        _min_len = 0
    if not _min_len:
        return [("", in_list)]
    while True:
        _pfs = set([_value[:_len + 1] for _value in in_list])
        if len(_pfs) == 1:
            _len += 1
            if _len > _min_len:
                break
        else:
            break
    if _len:
        _res = list_to_struct(
            [_value[_len:] for _value in in_list],
            **kwargs
        )
        return [(in_list[0][:_len], _res)]
    else:
        _pfs = sorted(list(_pfs))
        # check for integer pfs
        if all([_pf.isdigit() and (_pf[0] != "0" or _pf == "0") for _pf in _pfs]):
            _dict = {}
            _pfs = set()
            for _value in in_list:
                _pf = _value[0]
                if len(_value) > 2 and _value[1:3].isdigit():
                    _pf = _value[:3]
                elif len(_value) > 1 and _value[1].isdigit():
                    _pf = _value[:2]
                else:
                    _pf = _value[0]
                _pfs.add((int(_pf), _pf))
                _dict.setdefault(_pf, []).append(_value[len(_pf):])
            _pfs = sorted(list(_pfs))
            if len(_pfs) > 1 and len(set(["".join(_val) for _val in _dict.values()])) == 1:
                # all values are the same, return compressed list
                return [("[{}]".format(compress_num_list([_int for _int, _val in _pfs])), list_to_struct(list(_dict.values())[0], **kwargs))]
            else:
                _pfs = [_val for _int, _val in _pfs]
                return [(_pf, list_to_struct(_dict[_pf], **kwargs)) for _pf in _pfs]
        else:
            if len(_pfs[0]) < pf_min_size and min(len(_v) for _v in in_list) > pf_min_size:
                _pfs = set(sorted([_value[:pf_min_size] for _value in in_list]))
            return [(_pf, list_to_struct([_value[len(_pf):] for _value in in_list if _value[:len(_pf)] == _pf], **kwargs)) for _pf in _pfs]


def struct_to_string(in_struct):
    # recursivly expand a given line_struct
    _pf, _list = in_struct
    _r = []
    for _entry in _list:
        if isinstance(_entry, str):
            _r.append(_entry)
        else:
            _r.append(struct_to_string(_entry))
    if len(_r) == 1:
        return "{}{}".format(
            _pf,
            _r[0],
        )
    else:
        # empty strings will be displayed as [], so node[][2] means {node, node2}
        return "{}[{}]".format(
            _pf,
            "][".join(_r),
        )


def reduce_list(in_list, **kwargs):
    _top_join_str = kwargs.pop("top_join_str", ",")
    return _top_join_str.join([struct_to_string(_sub_list) for _sub_list in list_to_struct(in_list, **kwargs)])


# delayed access functions to get_logger and other functions
def get_logger(*args, **kwargs):
    from .logging_net import get_logger
    return get_logger(*args, **kwargs)

# compatibility definitions
new_form_list = NewFormList
