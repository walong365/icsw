#!/usr/bin/python-init -Ot
#
# Copyright (c) 2008,2009,2013 Andreas Lang-Nevyjel, init.at
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
""" handles process affinity """

import commands
import cpu_database
import process_tools
import sys

TASKSET_BIN = process_tools.find_file("taskset")
MAX_CORES = cpu_database.global_cpu_info(parse=True).num_cores()
MAX_MASK = (1 << MAX_CORES) - 1

class cpu_container(object):
    __slots__ = ("dict", "usage")
    def __init__(self):
        self.dict = {}
        self.usage = {}
        for idx in xrange(MAX_CORES):
            self.dict[idx] = cpu_struct(idx)
            self.usage[idx] = 0.0
    def add_proc(self, cur_s):
        self.dict[cur_s.single_cpu_num].add_proc(cur_s)
        self.usage[cur_s.single_cpu_num] = self.dict[cur_s.single_cpu_num].usage["t"]
    def get_min_usage_cpu(self):
        return list(sorted([(value, key) for key, value in self.usage.iteritems()]))[0][1]

class cpu_struct(object):
    __slots__ = ("cpu_num", "procs", "usage")
    def __init__(self, cpu_num):
        self.cpu_num = cpu_num
        self.procs = []
        self.usage = {"u": 0.0, "s" : 0.0, "t": 0.0}
    def add_proc(self, p_struct):
        self.procs.append(p_struct)
        for key in set(["t", "u", "s"]):
            self.usage[key] += p_struct.usage[key]

class proc_struct(object):
    __slots__ = ("pid", "act_mask", "single_cpu_num", "stat", "usage")
    def __init__(self, pid, stat=None):
        self.pid = pid
        self.single_cpu_num = -1
        self.stat = stat
        self.usage = {}
        self.read_mask()
    def feed(self, new_stat, diff_time):
        usage_dict = dict([(
            t_key[0],
            100. * float(
                new_stat[t_key] - self.stat[t_key]
            ) / diff_time) for t_key in ["utime", "stime"]])
        usage_dict["t"] = usage_dict["u"] + usage_dict["s"]
        self.stat = new_stat
        # usage dict is now populated with (u)ser, (s)ystem and (t)otal load in percent
        self.usage = usage_dict
    @property
    def mask_set(self):
        return self.act_mask != MAX_MASK
    @property
    def single_cpu_set(self):
        for cpu_num in xrange(MAX_CORES):
            if self.act_mask == 1 << cpu_num:
                self.single_cpu_num = cpu_num
                return True
        return False
    @property
    def proc_nums(self):
        p_nums = []
        for cpu_num in xrange(MAX_CORES):
            if self.act_mask & (1 << cpu_num):
                p_nums.append(cpu_num)
        return p_nums
    def migrate(self, target_cpu):
        self.act_mask = 1 << target_cpu
        c_stat, c_out = self._set_mask(target_cpu)
        return c_stat
    def read_mask(self):
        self.act_mask = self._get_mask()
    def _get_mask(self):
        c_stat, c_out = self._call("-p %d" % (self.pid))
        if c_stat:
            return MAX_MASK
        else:
            return int(c_out.strip().split()[-1], 16)
    def _set_mask(self, t_cpu):
        return self._call("-pc %d %d" % (t_cpu, self.pid))
    def _call(self, com_line):
        return commands.getstatusoutput("%s %s" % (TASKSET_BIN, com_line))

if __name__ == "__main__":
    print "Loadable module, exiting..."
    sys.exit(0)
