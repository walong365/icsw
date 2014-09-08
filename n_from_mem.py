#!/usr/bin/python-init -Otu
#
# Copyright (C) 2007-2009,2012,2014 Andreas Lang-Nevyjel
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
""" calculates N for HPL from memory """

import argparse
import math
import sys


class my_opt_parser(argparse.ArgumentParser):
    def __init__(self):
        argparse.ArgumentParser.__init__(self)
        self.add_argument("--nodes", type=int, dest="nodes", help="set number of nodes [%(default)d]", default=1)
        self.add_argument("--reserve-relative", type=int, dest="reserve_relative", help="set remaning memory in percent [%(default)d %%]", default=5)
        self.add_argument("--reserve-absolute", type=int, dest="reserve_absolute", help="set remaning memory in MByte [%(default)d MB]", default=150)
        self.add_argument("--precision", type=int, dest="precision", help="set precision [%(default)d]", default=100)
        self.add_argument("--memory", type=int, dest="memory", help="set size of memory is Megabytes (or - Gigabytes), [default is autodetermine]", default=0)
        # self.add_option("--cores", type="int", dest="cores", help="set number of cores per node [default is autodetermine]", default=0)

    def parse(self):
        return self.parse_args()


def main():
    options = my_opt_parser().parse()
    if options.memory == 0:
        mem_dict = {
            key: [
                int(sub_val) if sub_val.isdigit() else sub_val for sub_val in value.strip().split()
            ] for key, value in [
                line.split(":") for line in file("/proc/meminfo", "r").read().lower().split("\n") if line.count(":")
            ]
        }
        for key, value in mem_dict.iteritems():
            if len(value) == 2 and value[1] in ["kb", "mb"]:
                mem_dict[key] = value[0] * {
                    "k": 1024,
                    "m": 1024 * 1024,
                    "g": 1024 * 1024 * 1024
                }[value[1][0]]
            else:
                mem_dict[key] = value[0]
        options.memory = mem_dict["memtotal"]
    else:
        options.memory *= 1024 * 1024
        if options.memory < 0:
            options.memory *= -1024
    # not used right now
    # if options.cores == 0:
    #    options.cores = len([True for line in file("/proc/cpuinfo", "r").read().split("\n") if line.lower().startswith("processor")])
    mem_tot_rel, mem_tot_abs = (options.memory * (1. - options.reserve_relative / 100.),
                                options.memory - 1024 * 1024 * options.reserve_absolute)
    mem_tot_use = min(mem_tot_rel, mem_tot_abs) * options.nodes
    if mem_tot_use <= 0:
        print "No memory left, please check settings"
        sys.exit(-1)
    n_mat = math.sqrt(mem_tot_use / 8)
    print options.precision * (int(n_mat / options.precision))

if __name__ == "__main__":
    main()
