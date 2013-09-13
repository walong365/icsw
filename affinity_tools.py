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
import sys

try:
    import affinity
except:
    affinity = None

def get_process_affinity_mask(pid):
    c_stat, c_out = commands.getstatusoutput("taskset -p %d" % (pid))
    if c_stat:
        raise KeyError, "error getting affinity-mask for pid %d" % (pid)
    else:
        last_str = c_out.strip().split()[-1]
        return int(last_str, 16)
    
class affinity_struct(object):
    def __init__(self, pid, act_mask, max_cpu):
        self.__pid = pid
        self.__act_mask = act_mask
        self.__max_cpu = max_cpu
        self.__max_mask = (1 << self.__max_cpu) - 1
        self.__single_cpu_num = -1
    def mask_set(self):
        return self.__act_mask != self.__max_mask
    def single_cpu_set(self):
        for cpu_num in range(self.__max_cpu):
            if self.__act_mask == 1 << cpu_num:
                self.__single_cpu_num = cpu_num
                return True
        return False
    def get_single_cpu_num(self):
        return self.__single_cpu_num
    def get_proc_nums(self):
        p_nums = []
        for cpu_num in range(self.__max_cpu):
            if self.__act_mask & (1 << cpu_num):
                p_nums.append(cpu_num)
        return p_nums
    def migrate(self, target_cpu):
        self.__act_mask = 1 << target_cpu
        c_stat, c_out = commands.getstatusoutput(
            "taskset -pc %d %d" % (
                target_cpu,
                self.__pid))
        #print c_stat, c_out
        return c_stat

if __name__ == "__main__":
    print "Loadable module, exiting..."
    sys.exit(0)
    
