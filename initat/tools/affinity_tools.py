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


class CoreDistribution(object):
    def __init__(self, cpu_c, num_cpu):
        self.cpu_container = cpu_c
        self.num_cpu = num_cpu
        _stat, _out = self.cpu_container.dist_call("--single --taskset {:d}".format(self.num_cpu))
        self.taskset = [int(_part, 16) for _part in _out.split("\n")]
        self.cpunum = [CPU_MASKS[_set] for _set in self.taskset]


class CPUContainer(dict):
    def __init__(self):
        dict.__init__(self)
        # index of current distribution scheme
        self.__cds = 0
        self.taskset_bin = find_file("taskset")
        self.hwloc_distrib_bin = find_file("hwloc-distrib")
        for idx in xrange(MAX_CORES):
            self[idx] = CPUStruct(idx)
        self._distribution_cache = {}

    def cds_changed(self, num_cpu):
        # return True if core distribution scheme has changed
        if num_cpu != self.__cds:
            self.__cds = num_cpu
            return True
        else:
            return False

    def get_distribution_scheme(self, num_cpu):
        if num_cpu not in self._distribution_cache:
            self._distribution_cache[num_cpu] = CoreDistribution(self, num_cpu)
        return self._distribution_cache[num_cpu]

    def get_proc_struct(self, ps):
        # helper call to automatically add cpu_container
        return ProcStruct(self, ps)

    def clear_cpu_usage(self):
        [_value.clear_usage() for _value in self.itervalues()]

    def add_proc(self, cur_s):
        self[cur_s.single_cpu_num].add_proc(cur_s)
        # self.usage[cur_s.single_cpu_num] = self.dict[cur_s.single_cpu_num].usage["t"]

    def get_min_usage_cpu_list(self, excl_list=[]):
        free_list = [
            _entry[1] for _entry in list(
                sorted(
                    [
                        (value.usage["t"], key) for key, value in self.iteritems() if key not in excl_list
                    ]
                )
            )
        ]
        return free_list

    def ts_call(self, com_line):
        return commands.getstatusoutput("{} {}".format(self.taskset_bin, com_line))

    def dist_call(self, com_line):
        return commands.getstatusoutput("{} {}".format(self.hwloc_distrib_bin, com_line))

    def get_usage_str(self):
        return "|".join(
            [
                "{:d}:{:-.2f}({:d})".format(
                    key,
                    self[key].usage["t"],
                    len(self[key].procs)
                ) for key in sorted(self.keys())
            ]
        )


class CPUStruct(object):
    __slots__ = ("cpu_num", "procs", "usage")

    def __init__(self, cpu_num):
        self.cpu_num = cpu_num
        self.clear_usage()

    def clear_usage(self):
        self.procs = []
        self.usage = {
            "u": 0.0,
            "s": 0.0,
            "t": 0.0,
        }

    def add_proc(self, p_struct):
        self.procs.append(p_struct)
        for key in {"t", "u", "s"}:
            self.usage[key] += p_struct.usage[key]


class ProcStruct(object):
    __slots__ = ("pid", "act_mask", "single_cpu_num", "stat", "usage", "name", "cpu_container")

    def __init__(self, cpu_c, p_struct):  # pid, stat=None, name="not set"):
        self.cpu_container = cpu_c
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
        return sorted(
            [
                value for key, value in CPU_MASKS.iteritems() if self.act_mask & key
            ]
        )

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
        c_stat, c_out = self.cpu_container.ts_call("-p {:d}".format(self.pid))
        if c_stat:
            return MAX_MASK
        else:
            return int(c_out.strip().split()[-1], 16)

    def _set_mask(self, t_cpu):
        return self.cpu_container.ts_call("-pc {:d} {:d}".format(t_cpu, self.pid))

    def _clear_mask(self):
        return self.cpu_container.ts_call("-p {:x} {:d}".format(MAX_MASK, self.pid))

    def __unicode__(self):
        return "{} [{:d}]".format(self.name, self.pid)
