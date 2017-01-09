#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2010,2013-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of cluster-backbone
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
""" shows error recorded in the error file """

from __future__ import print_function, unicode_literals

import commands
import datetime
import os
import sys
import time

from initat.constants import LOG_ROOT
from initat.tools import logging_tools, process_tools


class ErrorRecord(object):
    def __init__(self, pid, s_name, uid, uname, gid, gname):
        self.__pid = pid
        self.__source_name = s_name
        self.__uid, self.__gid = (uid, gid)
        self.__uname, self.__gname = (uname, gname)
        self.__lines = []
        self.set_idx()

    def set_idx(self, idx=0):
        self.__idx = idx

    @property
    def pid(self):
        return self.__pid

    @property
    def uid(self):
        return self.__uid

    @property
    def uname(self):
        return self.__uname

    @property
    def source_name(self):
        return self.__source_name

    def add_line(self, l_date, state, line):
        if not self.__lines:
            self.__err_time = datetime.datetime(*time.strptime(l_date)[0:6])
            self.__err_date = datetime.datetime(*time.strptime(l_date)[0:3])
        self.__lines.append((state, line))

    def get_err_time_str(self):
        diff_time = self.__err_date.now() - self.__err_date
        if diff_time.days == 0:
            t_str = self.__err_time.strftime("today, %H:%M:%S")
        elif diff_time.days == 1:
            t_str = self.__err_time.strftime("yesterday, %H:%M:%S")
        else:
            t_str = self.__err_time.strftime("%a, %d. %b %Y %H:%M:%S")
        return t_str

    def get_form_parts(self):
        return [
            logging_tools.form_entry(self.__idx, header="idx"),
            logging_tools.form_entry(self.get_err_time_str(), header="time"),
            logging_tools.form_entry(self.__pid, header="PID"),
            logging_tools.form_entry(len(self.__lines), header="lines"),
            logging_tools.form_entry("%d (%s)" % (self.__uid, self.__uname), header="user"),
            logging_tools.form_entry("%d (%s)" % (self.__gid, self.__gname), header="group"),
            logging_tools.form_entry(self.__source_name, header="source")
        ]

    def get_header(self):
        return "Error %d occured %s, pid %d, uid/gid is (%d/%d [%s/%s]), source %s, %s:" % (
            self.__idx,
            self.get_err_time_str(),
            self.__pid,
            self.__uid,
            self.__gid,
            self.__uname,
            self.__gname,
            self.__source_name,
            logging_tools.get_plural("line", len(self.__lines))
        )

    def show_lines(self):
        f_str = "%%3d (%%%ds) : %%s" % (max([len(x) for x, _y in self.__lines]))
        return "\n".join([f_str % (l_idx, state, line) for (state, line), l_idx in zip(self.__lines, xrange(len(self.__lines)))])

    def __repr__(self):
        return "error from pid {:d} ({})".format(
            self.__pid,
            logging_tools.get_plural("line", len(self.__lines))
        )


def main(options):
    options.overview = True if (not options.stat and not options.index and not options.num) else False
    options.index = [int(cur_idx) for cur_idx in options.index]
    err_file_name = os.path.join(LOG_ROOT, "logging-server", "err_py")
    if not os.path.isfile(err_file_name):
        print("{} does not exist".format(err_file_name))
        sys.exit(1)
    if options.clear:
        new_file_name = "{}_{}.tar".format(
            err_file_name,
            time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime())
        )
        if process_tools.find_file("xz"):
            _pf = ".xz"
            _compr = "J"
            c_stat, out = commands.getstatusoutput("tar cpJf {}{} {}".format(new_file_name, _pf, err_file_name))
        elif process_tools.find_file("bzip2"):
            _pf = ".bz2"
            _compr = "j"
            c_stat, out = commands.getstatusoutput("tar cpjf {}{} {}".format(new_file_name, _pf, err_file_name))
        else:
            _pf = ""
            _compr = ""
        print("taring {} to {}{} ...".format(err_file_name, new_file_name, _pf))
        c_stat, out = commands.getstatusoutput("tar cp{}f {}{} {}".format(_compr, new_file_name, _pf, err_file_name))
        if c_stat:
            print("*** error (%d): %s" % (c_stat, out))
        else:
            os.unlink(err_file_name)
        sys.exit(c_stat)
    try:
        err_lines = [line.strip() for line in file(err_file_name, "r").read().split("\n") if line.count("from pid")]
    except IOError:
        print(
            "Cannot read '{}': {}".format(
                err_file_name,
                process_tools.get_except_info()
            )
        )
        sys.exit(1)
    print(
        "Found error_file {} with {}".format(
            err_file_name,
            logging_tools.get_plural("line", len(err_lines))
        )
    )
    errs_found, act_err = ([], None)
    act_idx, idx_dict, prev_dt = (0, {}, None)
    for line in err_lines:
        line_parts = line.split(":")
        # date is always the first 4 parts
        line_date = ":".join(line_parts[0:3]).strip()
        info_part = line_parts[3].strip()
        err_line = ":".join(line_parts[4:])
        # parse info_part
        try:
            if info_part.startswith("("):
                line_state = ""
            else:
                line_state = info_part.split()[0]
                info_part = info_part[len(line_state):].strip()
            info_parts = info_part.split()
            # skip error-thread name and "from pid" string
            info_parts.pop(0)
            info_parts.pop(0)
            info_parts.pop(0)
        except:
            print("Error pre-parsing line '{}': {}".format(line, process_tools.get_except_info()))
        else:
            try:
                # get pid
                line_pid = int(info_parts.pop(0))
                # unknown or full source
                if len(info_parts) == 7:
                    # full source
                    line_s_name = info_parts[0][1:]
                    line_uid = int(info_parts[2])
                    line_uname = info_parts[3][1:-2]
                    line_gid = int(info_parts[5])
                    line_gname = info_parts[6][1:-3]
                else:
                    line_s_name = info_parts[0][1:-1]
                    line_uid, line_gid = (-1, -1)
                    line_uname, line_gname = ("unknown", "unknown")
                cur_dt = datetime.datetime.strptime(line_date, "%a %b %d %H:%M:%S %Y")
                if prev_dt:
                    dt_change = abs(cur_dt - prev_dt).seconds > 5
                else:
                    dt_change = False
                prev_dt = cur_dt
                if not act_err or act_err.pid != line_pid or dt_change or line.count("<type"):
                    act_idx += 1
                    act_err = ErrorRecord(
                        line_pid,
                        line_s_name,
                        line_uid,
                        line_uname,
                        line_gid,
                        line_gname,
                    )
                    act_err.set_idx(act_idx)
                    idx_dict[act_idx] = act_err
                    errs_found.append(act_err)
                if err_line.strip() or not options.noempty:
                    act_err.add_line(line_date, line_state, err_line)
            except:
                print("Error parsing line '%s': %s" % (line, process_tools.get_except_info()))
    print("Found {}".format(logging_tools.get_plural("error record", len(errs_found))))
    if options.overview:
        if errs_found:
            out_list = logging_tools.new_form_list()
            for err in errs_found:
                out_list.append(err.get_form_parts())
            print(unicode(out_list))
    elif options.stat:
        uid_dict = {}
        for err in errs_found:
            uid_dict.setdefault(err.uid, []).append(err)
        all_uids = uid_dict.keys()
        all_uids.sort()
        out_list = logging_tools.new_form_list()
        for uid in all_uids:
            uid_stuff = uid_dict[uid]
            diff_sources = []
            for err in uid_stuff:
                if err.source_name not in diff_sources:
                    diff_sources.append(err.source_name)
            diff_sources.sort()
            out_list.append(
                (
                    logging_tools.form_entry(uid, header="uid"),
                    logging_tools.form_entry(uid_stuff[0].uname, header="uname"),
                    logging_tools.form_entry(len(uid_stuff), header="# err"),
                    logging_tools.form_entry(len(diff_sources), header="# sources"),
                    logging_tools.form_entry(", ".join(diff_sources), header="sources"),
                )
            )
        print(unicode(out_list))
    elif options.num:
        idx_l = idx_dict.keys()
        idx_l.sort()
        idx_show = []
        while options.num and idx_l:
            options.num -= 1
            idx_show.append(idx_l.pop(-1))
        idx_show.reverse()
        options.index = idx_show
    if options.index:
        for idx in options.index:
            if idx in idx_dict:
                act_err = idx_dict[idx]
                print(act_err.get_header())
                print(act_err.show_lines())
            else:
                print(
                    "Index {:d} not in index_list {}".format(
                        idx,
                        logging_tools.compress_num_list(idx_dict.keys())
                    )
                )
