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
""" simple parser for HPL result files """

import sys
import re
import logging_tools
import os
import getopt
import process_tools
import configfile


class result_line(object):
    def __init__(self, m_obj, **args):
        self.__v_dict = {
            key: m_obj.group(key) for key in [
                "test",
                "n",
                "nb",
                "p",
                "q",
                "runtime",
                "flops"
            ]
        }
        self["file_name"] = args.get("file_name", "unknown")
        for int_key in ["n", "nb", "q", "p"]:
            self[int_key] = int(self[int_key])
        for float_key in ["flops", "runtime"]:
            self[float_key] = float(self[float_key])
        self["passed"] = True

    def __getitem__(self, key):
        return self.__v_dict[key]

    def __setitem__(self, key, value):
        self.__v_dict[key] = value

    def add_pass_fail(self, m_obj):
        if m_obj.group("state").lower() != "passed":
            self["passed"] = False


class hpl_result(object):
    def __init__(self):
        self.__res_dict = {}
        self.__flop_re = re.compile("^(?P<test>W\S+)\s+(?P<n>\d+)\s+(?P<nb>\d+)\s+(?P<p>\d+)\s+(?P<q>\d+)\s+(?P<runtime>\S+)\s+(?P<flops>\S+)$")
        self.__pf_re = re.compile("^.*(?P<state>PASSED|FAILED)$")
        self.__results = []
        self.__min_result, self.__max_result = (None, None)

    def _feed_line(self, line, **args):
        f_m, p_m = (self.__flop_re.match(line),
                    self.__pf_re.match(line))
        if f_m:
            self._add_result(f_m, **args)
        elif p_m:
            self._add_pass_fail(p_m, **args)

    def _add_result(self, m_obj, **args):
        act_result = result_line(m_obj, file_name=args.get("file_name", "unknown"))
        self.__results.append(act_result)
        if self.__min_result is None:
            self.__min_result, self.__max_result = (
                act_result,
                act_result
            )
        else:
            if act_result["flops"] < self.__min_result["flops"]:
                self.__min_result = act_result
            if act_result["flops"] > self.__max_result["flops"]:
                self.__max_result = act_result

    def _add_pass_fail(self, m_obj, **args):
        if self.__results:
            self.__results[-1].add_pass_fail(m_obj)
        else:
            print "Got fail/pass line without previous result"

    def __len__(self):
        return len(self.__results)

    def iterate_results(self):
        for result in self.__results:
            yield result
        raise StopIteration

    def get_min_result(self):
        return self.__min_result

    def get_max_result(self):
        return self.__max_result


class hpl_file(hpl_result):
    def __init__(self, file_name, loc_config):
        hpl_result.__init__(self)
        self.__loc_config = loc_config
        self.__file_names = []
        self.add_file(file_name)

    def add_file(self, file_name):
        self.__file_names.append(file_name)
        self.__lines = file(file_name, "r").read().split("\n")
        self._get_node_name()
        for line in self.__lines:
            self._feed_line(line, file_name=self.__file_names[-1])

    def _get_node_name(self):
        n_name = "unknown"
        r_names = [line for line in self.__lines if line.startswith("running on")]
        if r_names:
            # check for multiple runs ?
            n_name = r_names[-1].split()[3]
        self.node_name = n_name

    def get_info(self):
        num_passed, num_failed = (
            sum([1 for res in self.iterate_results() if res["passed"]]),
            sum([1 for res in self.iterate_results() if not res["passed"]])
        )
        files_failed = set([res["file_name"] for res in self.iterate_results() if not res["passed"]])
        min_res, max_res = (self.get_min_result(),
                            self.get_max_result())
        if min_res:
            return "Node %s (%s%s): %3d tests, %s (%s), %6.2f GFlop min (%8s), %6.2f GFlop max (%8s)%s" % (
                self.node_name,
                "%2d files" % (len(self.__file_names)),
                ", %s" % (", ".join(sorted(self.__file_names))) if self.__loc_config["VERBOSE"] else "",
                len(self),
                "%s passed" % ("all" if not num_failed else "%3d" % (num_passed)),
                " %3d failed" % (num_failed) if num_failed else "none failed",
                min_res["flops"],
                min_res["test"],
                max_res["flops"],
                max_res["test"],
                ", failed in %s" % (", ".join(sorted(files_failed))) if files_failed else ""
            )
        else:
            return "Node %s: no results" % (self.node_name)


class hpl_i_loader(object):
    def __init__(self, loc_config, file_names):
        self.__loc_config = loc_config
        self.__file_names, self.__file_dict = (file_names, {})
        self._load_files()

    def _load_files(self):
        if not self.__file_names:
            print "Need some files to interpret"
        else:
            for f_name in self.__file_names:
                try:
                    act_file = hpl_file(f_name, self.__loc_config)
                except:
                    print "error reading file %s: %s" % (f_name,
                                                         process_tools.get_except_info())
                else:
                    if self.__loc_config["MERGE_SAME_HOSTS"]:
                        nn_dict = dict([(value.node_name, value) for value in self.__file_dict.itervalues()])
                        if act_file.node_name in nn_dict.keys():
                            nn_dict[act_file.node_name].add_file(f_name)
                        else:
                            self.__file_dict[f_name] = act_file
                    else:
                        self.__file_dict[f_name] = act_file
            if self.__loc_config["VERBOSE"]:
                print "loaded %s from list with %s" % (logging_tools.get_plural("file", len(self.__file_dict.keys())),
                                                       logging_tools.get_plural("file_name", len(self.__file_names)))

    def show_info(self):
        for hpl_f in self.__file_dict.itervalues():
            print hpl_f.get_info()


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "vhm", ["help"])
    except getopt.GetoptError, _bla:
        print "Error parsing commandline %s: %s (%s)" % (
            " ".join(sys.argv[1:]),
            process_tools.get_except_info()
        )
        sys.exit(1)
    loc_config = configfile.configuration(
        "hpl_parser",
        {
            "VERBOSE": configfile.int_c_var(0),
            "MERGE_SAME_HOSTS": configfile.bool_c_var(False)
        }
    )
    pname = os.path.basename(sys.argv[0])
    for opt, _arg in opts:
        if opt in ["-h", "--help"]:
            print "Usage: %s [OPTIONS]" % (pname)
            print " where options is one or more of"
            print "  -h, --help          this help"
            print "  -v                  be verbose"
            print "  -m                  merge results for same hosts"
            sys.exit(1)
        if opt == "-v":
            loc_config["VERBOSE"] += 1
        if opt == "-m":
            loc_config["MERGE_SAME_HOSTS"] = True
    my_loader = hpl_i_loader(loc_config, args)
    my_loader.show_info()
    sys.exit(0)


if __name__ == "__main__":
    main()
