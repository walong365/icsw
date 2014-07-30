#!/usr/bin/python-init -Otu
# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of host-monitoring
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

""" check_cluster, enhanced version of check-cluster from icinga """

import argparse
import sys

def main():
    my_parser = argparse.ArgumentParser(add_help=False)
    my_parser.add_argument("-s", "--service", dest="check_type", action="store_const", const="s", default=None, help="check service cluster")
    my_parser.add_argument("-h", "--host", dest="check_type", action="store_const", const="h", default=None, help="check host cluster")
    my_parser.add_argument("--help", help="show help", action="help")
    my_parser.add_argument("-w", "--warning", type=int, default=1, help="warning value (lower boundary) [%(default)s]")
    my_parser.add_argument("-c", "--critical", type=int, default=2, help="critical value (lower boundary) [%(default)s]")
    my_parser.add_argument("-d", "--data", type=str, default="", help="status codes of hosts or services of the cluster, separated by commas [%(default)s]")
    my_parser.add_argument("-n", "--names", type=str, default="", help="names of hosts or services of the cluster, separated by commas [%(default)s]")
    my_parser.add_argument("-l", "--label", type=str, default="", help="label to prefix output [%(default)s]")
    my_parser.add_argument("--show-zero", default=False, action="store_true", help="show entities with zero count [%(default)s]")
    opts = my_parser.parse_args()
    ret_value = 2
    _parse = True
    if not opts.check_type:
        print("missing check_type")
    elif not opts.data:
        print("missing data")
    else:
        try:
            opts.data = [int(_value) for _value in opts.data.split(",")]
        except:
            print("cannot parse data '{}'".format(opts.data))
        else:
            if opts.names.strip():
                opts.names = [_value.strip() for _value in opts.names.split(",") if _value.strip()]
                if len(opts.names) != len(opts.data):
                    print("length of data and names differ")
                    _parse = False
        if _parse:
            if set(opts.data) - set([0, 1, 2, 3] if opts.check_type == "s" else [0, 1, 2]):
                print("illegal values in data")
                _parse = False
        if _parse:
            n_dict = {}
            if opts.names:
                for _state, _info in zip(opts.data, opts.names):
                    n_dict.setdefault(_state, []).append(_info)
            if opts.check_type == "s":
                # service check
                info_dict = {0 : "ok", 1 : "warning", 2 : "unknown", 3: "critical"}
            else:
                # host check
                info_dict = {0 : "up", 1 : "down", 2 : "unreachable"}
            count_dict = {key : opts.data.count(key) for key, value in info_dict.iteritems()}
            prob_count = sum([value for key, value in count_dict.iteritems() if key])
            if prob_count >= opts.critical and opts.critical:
                ret_value = 2
            elif prob_count >= opts.warning and opts.warning:
                ret_value = 1
            else:
                ret_value = 0
            info_f = []
            for _state in sorted(info_dict.keys()):
                if count_dict[_state] or opts.show_zero:
                    info_f.append(
                        "{:d} {}{}".format(
                            count_dict[_state],
                            info_dict[_state],
                            " ({})".format(
                                ", ".join(sorted(n_dict[_state]))
                            ) if n_dict.get(_state, None) else "",
                        )
                    )
            info_str = ", ".join(info_f) or "---"
            print(
                "CLUSTER {}: {}{}".format(
                    {0 : "OK", 1 : "WARNING", 2 : "CRITICAL"}[ret_value],
                    "{}: ".format(opts.label) if opts.label else "",
                    info_str,
                )
            )
    return ret_value

if __name__ == "__main__":
    sys.exit(main())

