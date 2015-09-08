# Copyright (c) 2008-2009,2013-2015 Andreas Lang-Nevyjel, init.at
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
import os

import psutil

if "FAKEROOTKEY" in os.environ:
    MAX_CORES = 2
else:
    MAX_CORES = psutil.cpu_count(logical=True)

MAX_MASK = (1 << MAX_CORES) - 1
CPU_MASKS = {1 << cpu_num: cpu_num for cpu_num in xrange(MAX_CORES)}


def find_file(file_name, s_path=None):
    if not s_path:
        s_path = []
    elif type(s_path) != list:
            s_path = [s_path]
    s_path.extend(["/opt/cluster/sbin", "/opt/cluster/bin", "/bin", "/usr/bin", "/sbin", "/usr/sbin"])
    found = False
    for cur_path in s_path:
        if os.path.isfile(os.path.join(cur_path, file_name)):
            found = True
            break
    if found:
        return os.path.join(cur_path, file_name)
    else:
        return None

TASKSET_BIN = find_file("taskset")


def get_process_affinity_mask(pid):
    mask = 0
    if os.path.isfile("/proc/{:d}/status".format(pid)):
        lines = [line.split() for line in open("/proc/{:d}/status".format(pid), "r").read().lower().split("\n") if line.startswith("cpus_allowed")]
        if lines:
            mask = int(lines[0][1], 16)
    return mask


def get_process_affinity_mask_from_status_lines(lines):
    mask = 0
    lines = [line.split() for line in lines if line.startswith("cpus_allowed")]
    if lines:
        mask = int(lines[0][1], 16)
    return mask


class CPUContainer(dict):
    def __init__(self):
        dict.__init__(self)
        for idx in xrange(MAX_CORES):
            self[idx] = CPUStruct(idx)

    def add_proc(self, cur_s):
        self[cur_s.single_cpu_num].add_proc(cur_s)
        # self.usage[cur_s.single_cpu_num] = self.dict[cur_s.single_cpu_num].usage["t"]

    def get_min_usage_cpu(self, excl_list=[]):
        free_list = list(sorted([(value.usage["t"], key) for key, value in self.iteritems() if key not in excl_list]))
        if free_list:
            return free_list[0][1]
        else:
            return None

    def get_usage_str(self):
        return "|".join(["{:d}:{:-2f}({:d})".format(
            key,
            self[key].usage["t"],
            len(self[key].procs)) for key in sorted(self.keys())])


class CPUStruct(object):
    __slots__ = ("cpu_num", "procs", "usage")

    def __init__(self, cpu_num):
        self.cpu_num = cpu_num
        self.procs = []
        self.usage = {
            "u": 0.0,
            "s": 0.0,
            "t": 0.0,
        }

    def add_proc(self, p_struct):
        self.procs.append(p_struct)
        for key in set(["t", "u", "s"]):
            self.usage[key] += p_struct.usage[key]


class ProcStruct(object):
    __slots__ = ("pid", "act_mask", "single_cpu_num", "stat", "usage", "name")

    def __init__(self, p_struct):  # pid, stat=None, name="not set"):
        self.pid = p_struct.pid
        self.name = p_struct.name()
        self.single_cpu_num = -1
        _cpu_t = p_struct.cpu_times()
        self.stat = {"u": _cpu_t.user, "s": _cpu_t.system}
        self.usage = {}
        self.read_mask()

    def feed(self, p_struct, diff_time):
        try:
            _cpu_t = p_struct.cpu_times()
            stat_dict = {"u": _cpu_t.user, "s": _cpu_t.system}
            usage_dict = {
                key: 100. * float(
                    stat_dict[key] - self.stat[key]
                ) / diff_time for key in stat_dict.iterkeys()
            }
            usage_dict["t"] = usage_dict["u"] + usage_dict["s"]
            self.stat = stat_dict
            # usage dict is now populated with (u)ser, (s)ystem and (t)otal load in percent
            self.usage = usage_dict
        except psutil.NoSuchProcess:
            pass

    def clear_usage(self):
        self.usage = {}

    @property
    def mask_set(self):
        return self.act_mask != MAX_MASK

    @property
    def single_cpu_set(self):
        """
        return True if a single cpu is set via the affinity mask
        """
        self.single_cpu_num = CPU_MASKS.get(self.act_mask, -1)
        return True if self.single_cpu_num >= 0 else False

    @property
    def proc_nums(self):
        """
        return the cpus which are actually set in the affinity mask
        """
        return sorted([value for key, value in CPU_MASKS.iteritems() if self.act_mask & key])

    def migrate(self, target_cpu):
        self.act_mask = 1 << target_cpu
        c_stat, _c_out = self._set_mask(target_cpu)
        return c_stat

    def clear_mask(self):
        self.act_mask = MAX_MASK
        c_stat, _c_out = self._clear_mask()
        return c_stat

    def read_mask(self):
        self.act_mask = self._get_mask()

    def _get_mask(self):
        c_stat, c_out = self._call("-p {:d}".format(self.pid))
        if c_stat:
            return MAX_MASK
        else:
            return int(c_out.strip().split()[-1], 16)

    def _set_mask(self, t_cpu):
        return self._call("-pc {:d} {:d}".format(t_cpu, self.pid))

    def _clear_mask(self):
        return self._call("-p {:x} {:d}".format(MAX_MASK, self.pid))

    def _call(self, com_line):
        return commands.getstatusoutput("{} {}".format(TASKSET_BIN, com_line))

    def __unicode__(self):
        return "{} [{:d}]".format(self.name, self.pid)
