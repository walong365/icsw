#!/usr/bin/python-init -Otu
#
# Copyright (C) 2007-2008,2014 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of cbc_tools
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
""" reads raw data from bonnie_runs and shows them """

from initat.tools import logging_tools
import os
from initat.tools import process_tools
from initat.tools import server_command
import sys


class aggreg(object):
    def __init__(self):
        pass

    def _str_to_int(self, in_str, def_mult):
        if in_str.lower().endswith("m"):
            mult = 1024 * 1024
            in_str = in_str[:-1]
        elif in_str.lower().endswith("g"):
            mult = 1024 * 1024 * 1024
            in_str = in_str[:-1]
        else:
            mult = 1
        mult *= def_mult
        if in_str.count("+"):
            return 0
        else:
            return float(in_str) * mult

    def _str_to_float(self, in_str, def_mult):
        if in_str.lower().endswith("m"):
            mult = 1024 * 1024
            in_str = in_str[:-1]
        elif in_str.lower().endswith("g"):
            mult = 1024 * 1024 * 1024
            in_str = in_str[:-1]
        else:
            mult = 1
        mult *= def_mult
        if in_str.count("+"):
            return 0
        else:
            return float(in_str) * mult

    def get_perc_graph(self, in_value):
        return ("#" * int(in_value / 5))


class sum_aggreg(aggreg):
    def __init__(self, **args):
        aggreg.__init__(self)
        self.__values = []
        self.__default_mult = args.get("mult", 1)
        self.__add_str = args.get("postfix", "/s")
        self.__unit_str = args.get("unit", "B")
        self.__float_input = args.get("float_input", False)

    def __add__(self, value):
        if self.__float_input:
            self.__values.append(self._str_to_float(value, self.__default_mult))
        else:
            self.__values.append(self._str_to_int(value, self.__default_mult))
        return self

    def __str__(self):
        mult = ["k", "M", "G", "T"]
        act_pf = ""
        in_int = sum(self.__values)
        while in_int > 1024:
            in_int /= 1024.
            act_pf = mult.pop(0)
        return "%.2f %s%s%s" % (in_int,
                                act_pf,
                                self.__unit_str,
                                self.__add_str)

    def value(self):
        return sum(self.__values)


class max_aggreg(aggreg):
    def __init__(self, **args):
        aggreg.__init__(self)
        self.__values = []
        self.__default_mult = args.get("mult", 1)
        self.__add_str = args.get("postfix", "%")

    def __add__(self, value):
        self.__values.append(self._str_to_int(value, self.__default_mult))
        return self

    def __str__(self):
        if self.__values:
            in_perc = max(self.__values)
        else:
            in_perc = 0.
        return "%3d%s" % (in_perc,
                          " %s" % (self.__add_str) if self.__add_str else "")

    def value(self):
        return max(self.__values)


class res_line(object):
    def __init__(self):
        self.__out_keys = ["size",
                           "seq_out_char_speed",
                           "seq_out_char_cpu",
                           "seq_out_block_speed",
                           "seq_out_block_cpu",
                           "seq_rew_block_speed",
                           "seq_rew_block_cpu",
                           "seq_in_char_speed",
                           "seq_in_char_cpu",
                           "seq_in_block_speed",
                           "seq_in_block_cpu",
                           "random_seek_speed",
                           "random_seek_cpu"]
        self.__value_dict = {}
        for sum_name in ["seq_out_char_speed",
                         "seq_out_block_speed",
                         "seq_rew_block_speed",
                         "seq_in_char_speed",
                         "seq_in_block_speed"]:
            self[sum_name] = sum_aggreg(mult=1024)
        self["random_seek_speed"] = sum_aggreg(mult=1, postfix="", unit="", float_input=True)
        for max_name in ["seq_out_char_cpu",
                         "seq_out_block_cpu",
                         "seq_rew_block_cpu",
                         "seq_in_char_cpu",
                         "seq_in_block_cpu"]:
            self[max_name] = max_aggreg()
        self["random_seek_cpu"] = max_aggreg(postfix="%")
        self.machine_name = "not set"
        self.size = 0

    def __setitem__(self, key, value):
        self.__value_dict[key] = value

    def __getitem__(self, key):
        if key in self.__value_dict:
            return self.__value_dict[key]
        else:
            return "not set"

    def add_line(self, line):
        if type(line) is list:
            for sub_line in line:
                self._add_line(sub_line)
        else:
            self._add_line(line)

    def _add_line(self, line):
        recs = line.split(",")
        if len(recs) != 27:
            raise ValueError("number of records (%d) != 27" % (len(recs)))
        self.__recs = recs
        self.machine_name = recs.pop(0)
        for key in self.__out_keys:
            if key == "size":
                self[key] = sum_aggreg(postfix="") + recs.pop(0)
            else:
                self[key] += recs.pop(0)

    def get_out_keys(self):
        return self.__out_keys


def main():
    if len(sys.argv) != 2:
        print "Need file to parse"
        sys.exit(1)
    file_name = sys.argv[1]
    if not os.path.isfile(file_name):
        print "File %s does not exist" % (file_name)
        sys.exit(2)
    try:
        file_struct = server_command.net_to_sys(file(file_name, "r").read())
    except:
        print "Error reading file %s: %s" % (file_name,
                                             process_tools.get_except_info())
        sys.exit(3)
    out_list = logging_tools.form_list()
    out_list.set_header_string(0, ["tnum", "ttot", "time spent",
                                   "machine", "size",
                                   "cout_spd", "cout_cpu",
                                   "seqout_spd", "seqout_cpu",
                                   "rew_spd", "rew_cpu",
                                   "cin_spd", "cin_cpu",
                                   "seqin_spd", "seqin_cpu",
                                   "seek_spd", "seek_cpu"])
    out_list.set_format_string("time spent", "s", "")
    out_list.set_format_string("cout_spd", "s", "")
    out_list.set_format_string("seqout_spd", "s", "")
    out_list.set_format_string("rew_spd", "s", "")
    out_list.set_format_string("cin_spd", "s", "")
    out_list.set_format_string("seqin_spd", "s", "")
    out_list.set_format_string("seek_spd", "s", "")
    run_keys = sorted([x for x in file_struct.keys() if type(x) in [type(0), type(0L)]])
    print "Found %s: %s" % (logging_tools.get_plural("run", len(run_keys)),
                            ", ".join([logging_tools.get_plural("thread", file_struct[x]["num_threads"]) for x in run_keys]))
    # dict special_key -> thread_num -> values
    spec_dict = dict([(key, {}) for key in res_line().get_out_keys() if key.count("speed")])
    for run_key in run_keys:
        run_stuff = file_struct[run_key]
        tot_threads = run_stuff["num_threads"]
        print "run with %s:" % (logging_tools.get_plural("thread", tot_threads))
        if run_stuff["started"] != run_stuff["ended"] or run_stuff["started"] != run_stuff["num_threads"]:
            print " + started / ended / num_threads differ: %d / %d / %d" % (run_stuff["started"],
                                                                             run_stuff["ended"],
                                                                             run_stuff["num_threads"])
        else:
            run_res = run_stuff["results"]
            run_obj = res_line()
            for res_thread in range(1, tot_threads + 1):
                thread_res = run_res[res_thread]
                if type(thread_res) is dict:
                    act_res_line = thread_res["output"]
                    run_time = thread_res.get("run_time", 0)
                else:
                    act_res_line = thread_res
                    run_time = 0
                try:
                    line_obj = res_line()
                    line_obj.add_line(act_res_line)
                    run_obj.add_line(act_res_line)
                except:
                    print " + %s" % (process_tools.get_except_info())
                else:
                    out_list.add_line([res_thread,
                                       tot_threads,
                                       logging_tools.get_time_str(run_time) or "---",
                                       line_obj.machine_name] + [line_obj[key] for key in line_obj.get_out_keys()])
            out_list.add_line([res_thread,
                               "all",
                               logging_tools.get_time_str(run_time) or "---",
                               run_obj.machine_name] + [run_obj[key] for key in run_obj.get_out_keys()])
            for key in spec_dict.keys():
                spec_dict[key][tot_threads] = run_obj[key]
    if out_list:
        print str(out_list)
    if spec_dict:
        out_list = logging_tools.form_list()
        out_list.set_header_string(0, ["key", "threads", "value", "percent", "graph"])
        for key in sorted(spec_dict.keys()):
            threads = sorted(spec_dict[key].keys())
            top_value = None
            for t_num in threads:
                act_struct = spec_dict[key][t_num]
                if top_value is None:
                    top_value = act_struct.value()
                act_val = act_struct.value()
                act_perc = 100 * act_val / top_value
                out_list.add_line([key,
                                   t_num,
                                   act_struct,
                                   "%7.2f %%" % (act_perc),
                                   act_struct.get_perc_graph(act_perc)])
            out_list.add_line(["-" * 50])
        print out_list

if __name__ == "__main__":
    main()
