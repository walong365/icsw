# Copyright (C) 2001-2017 Andreas Lang-Nevyjel, init.at
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
""" simple database for the most common CPUs  """

import base64
import bz2
import marshal
import os
import re
import subprocess
import tempfile

from initat.tools import logging_tools, server_command


# copy from process_tools
def getstatusoutput(cmd):
    return subprocess.getstatusoutput(cmd)


def get_cpu_basic_info():
    try:
        cpu_dict = {
            k.strip().lower(): v.strip() for k, v in [
                x.strip().split(":", 1) for x in open("/proc/cpuinfo", "r").readlines() if x.count(":")
            ]
        }
    except:
        cpu_dict = {}
    return cpu_dict


def correct_cpu_dict(in_dict):
    for t_id, s_id in [
        ("vendor_id", "vendor"),
        ("cpu family", "family")
    ]:
        if s_id in in_dict and t_id not in in_dict:
            in_dict[t_id] = in_dict[s_id]
    return in_dict


class cpu_value(object):
    int_re = re.compile("^(?P<pre_str>.*)\s+\((?P<int>\d+)\)")

    def __init__(self, in_str):
        self.add_value = ""
        if isinstance(in_str, int):
            self.v_type = "i"
            self.value = in_str
        else:
            int_match = self.int_re.match(in_str)
            if in_str.lower() in ["true", "false"]:
                # boolean
                self.v_type = "b"
                self.value = bool(in_str)
            elif int_match:
                # integer with pre-string
                self.v_type = "i"
                self.value = int(int_match.group("int"))
                self.add_value = int_match.group("pre_str")
            elif in_str.isdigit():
                self.v_type = "i"
                self.value = int(in_str)
            else:
                # string
                self.v_type = "s"
                self.value = in_str

    def __repr__(self):
        return "cpu_value, type {}, value {}{}".format(
            self.v_type,
            self.value,
            self.add_value and ", {}".format(self.add_value) or ""
        )


class cpu_info_part(object):
    def __init__(self, act_key):
        act_source = act_key.split("(")[1].split(")")[0].strip()
        act_key = act_key.split("(")[0].strip()
        if act_source.count("/"):
            act_source = act_source.split("/")
            act_source[0] = int(act_source[0], 16)
            act_source = tuple(act_source)
        else:
            act_source = int(act_source, 16)
        self.num_key = act_source
        self.str_key = act_key
        self.__value_dict = {}

    def bump_num_key(self):
        # increase num_key
        num_key = self.num_key
        if isinstance(num_key, int):
            num_key = (num_key,)
        num_key = list(num_key)
        if isinstance(num_key[-1], str):
            num_key.append(0)
        else:
            num_key[-1] += 1
        self.num_key = tuple(num_key)

    def add_line(self, line):
        if line.count("---"):
            pass
        else:
            if isinstance(self.num_key, int):
                in_key, in_value = [part.strip() for part in line.split(":", 1)]
                in_key = int(in_key, 16)
            else:
                in_key, in_value = [part.strip() for part in line.split("=", 1)]
            self[in_key] = in_value

    def __setitem__(self, key, value):
        self.__value_dict[key] = cpu_value(value)

    def __getitem__(self, key):
        return self.__value_dict[key]

    def has_key(self, key):
        return key in self.__value_dict

    def __contains__(self, key):
        return key in self.__value_dict

    def keys(self):
        return list(self.__value_dict.keys())

    def values(self):
        return list(self.__value_dict.values())

    def __repr__(self):
        return "cpu_info_part {} ({})".format(
            self.str_key,
            logging_tools.get_plural("key", len(list(self.__value_dict.keys()))))


class cpu_layout(object):
    def __init__(self):
        # cache share
        self.__cache_share = {}
        self.__cores = {}
        # dict : socket -> domain -> die -> core -> lcore
        self.__layout = {}

    def add_logical_core(self, core_num, core_struct, socket_num):
        self.__cores[core_num] = core_struct
        l1_cache_idx = self.__cache_share[1].get_cache_num(core_num)
        l2_cache_idx = self.__cache_share[2].get_cache_num(core_num)
        if 3 in self.__cache_share:
            self.has_l3_cache = True
            l3_cache_idx = self.__cache_share[3].get_cache_num(core_num)
        else:
            self.has_l3_cache = False
            l3_cache_idx = 0
        num_dict = {
            "core_num": core_num,
            "ht_core_num": l1_cache_idx,
            "die_num": l2_cache_idx,
            "domain_num": l3_cache_idx,
            "socket_num": socket_num
        }
        self.__layout.setdefault(
            num_dict["socket_num"], {}
        ).setdefault(
            num_dict["domain_num"], {}
        ).setdefault(
            num_dict["die_num"], {}
        ).setdefault(
            num_dict["ht_core_num"], []
        ).append(num_dict["core_num"])
        core_struct._set_num_dict(num_dict)

    def place_core(self, core_num, cache_level, shares_with):
        if cache_level not in self.__cache_share:
            self.__cache_share[cache_level] = share_map(cache_level)
        self.__cache_share[cache_level].place_core(core_num, shares_with)

    def _get_layout_dict(self):
        return self.__layout


class share_map(object):
    def __init__(self, c_level):
        self.cache_level = c_level
        self.num_caches = 0
        self.__core_dict = {}
        self.__cache_lut = {}
        self.__core_lut = {}

    def place_core(self, core_num, shares_with):
        self.__core_dict[core_num] = shares_with
        if core_num in self.__core_lut:
            cache_num = self.__core_lut[core_num]
        else:
            cache_num = self.num_caches
            self.num_caches += 1
            for s_core in shares_with:
                self.__core_lut[s_core] = cache_num
            self.__cache_lut[cache_num] = shares_with

    def get_cache_num(self, core_num):
        return self.__core_lut.get(core_num, None)

    def __repr__(self):
        return "share_map for level {:d} cache, {}: {}".format(
            self.cache_level,
            logging_tools.get_plural("cache", self.num_caches),
            ", ".join(
                [
                    "{:d} [{}]".format(
                        c_num,
                        ":".join(
                            [
                                "{:d}".format(core_num) for core_num in self.__cache_lut[c_num]
                            ]
                        )
                    ) for c_num in range(self.num_caches)
                ]
            )
        )


class cpu_info(object):
    def __init__(self, in_dict):
        self.__v_dict = in_dict
        # we only set local processor capabilities, stuff like socket_num, die_num are set later on by layout
        # core_num ...... number of core
        # ht_core_num ... number of hyper-threading core (one ht-core shares an l1 cache)
        # die_num ....... number of die (one die shares an l2 cache)
        # domain_num .... number of domain (one domain shares an l3 cache) (optional)
        # socket_num .... number of processor socket
        self._set_num_dict()
        if "cpu MHz" in in_dict:
            self["speed"] = int(float(in_dict["cpu MHz"]))
        else:
            self["speed"] = 0
        # set cache sizes
        self.cache_info = {}
        if "cache" in in_dict.get("sys_info", {}):
            self._set_cache_info(in_dict["sys_info"]["cache"])
        self._set_cpu_id()

    def _set_num_dict(self, in_dict=None):
        if in_dict is None:
            for key in ["core", "ht_core", "die", "domain", "socket"]:
                self["{}_num".format(key)] = 0
        else:
            self.__v_dict.update(in_dict)

    def has_key(self, key):
        return key in self.__v_dict

    def __contains__(self, key):
        return key in self.__v_dict

    def keys(self):
        return list(self.__v_dict.keys())

    def __getitem__(self, key):
        return self.__v_dict[key]

    def get(self, key, default):
        return self.__v_dict.get(key, default)

    def __setitem__(self, key, value):
        self.__v_dict[key] = value

    def _set_cpu_id(self):
        if self["online"]:
            self["cpu_id"] = ".".join([str(self[key]) for key in ["cpu_family", "model", "stepping", "cpuid_level"]])

    def has_valid_cache_info(self):
        return True if self.cache_info else False

    def _set_cache_info(self, in_dict=None):
        if in_dict is not None:
            self.cache_info["share_dict"] = {}
            self.cache_info["size"] = dict([(key, 0) for key in range(1, 4)])
            for _c_index, c_stuff in in_dict.items():
                self.cache_info["size"][c_stuff["level"]] += c_stuff["size"]
                if "shared_cpu_map" in c_stuff:
                    scm = c_stuff["shared_cpu_map"]
                    if scm == "":
                        # hack, FIXME
                        scm = "1"
                    scm = int(scm.replace(",", ""), 16)
                    core_list = set([idx for idx in range(256) if (1 << idx) & scm])
                    self.cache_info["share_dict"].setdefault(c_stuff["level"], set()).update(core_list)
        # pprint.pprint(self.cache_info)

    def _get_cache_share_info(self, c_num):
        if c_num in self.cache_info.get("share_dict", {}):
            share_info = self.cache_info["share_dict"][c_num]
            if share_info == {self["core_num"]}:
                return "excl"
            else:
                return "shared by {}".format(", ".join(["{:d}".format(core) for core in sorted(share_info)]))

    def get_cache_sizes(self):
        return self.cache_info["size"]

    def get_short_cache_info(self):
        return "".join([self._get_size_str(self.cache_info["size"][cache_num]).replace(" ", "").replace("B", "") for cache_num in [1, 2, 3]])

    def get_cache_info_str(self):
        if sum(list(self.cache_info["size"].values()), 0):
            return ", ".join(
                [
                    "L{:d}: {}{}".format(
                        cache_num,
                        self._get_size_str(self.cache_info["size"][cache_num]),
                        " ({})".format(
                            self._get_cache_share_info(cache_num)
                        ) if self._get_cache_share_info(cache_num) else ""
                    ) for cache_num in range(1, 4) if self.cache_info["size"][cache_num]
                ]
            )
        else:
            return "No cache info found"

    def set_cache_from_cpuid_info(self, in_dict):
        # if self.has_key(4):
        #    # this information is not reliable, hyper_threading is always reported true even when disabled in bios (bignode / Liebherr)
        #    self.hyper_threading = self[4]["extra threads sharing this cache"].value > 0
        #    self.num_cores = self[4]["extra processor cores on this die"].value + 1
        # else:
        #    # opterons do not have key 4, so we imply no hyper-threading and single-core
        #    self.hyper_threading, self.num_cores = (0, 1)
        # get cache sizes
        self.cache_info["size"] = dict([(num, 0) for num in range(1, 4)])
        if 2 in in_dict:
            for cache_key in list(in_dict[2].keys()):
                act_value = in_dict[2][cache_key].value
                if act_value.startswith("L"):
                    cache_num = int(act_value[1])
                    cache_size = act_value.split(",")[0].split(":")[1]
                    pfix = {"k": 1024,
                            "m": 1024 * 1024,
                            "g": 1024 * 1024 * 1024}.get(cache_size[-1].lower(), 1)
                    cache_size = int(cache_size[:-1]) * pfix
                    self.cache_info["size"][cache_num] += cache_size
        # correct wrong cache-reporting
        if not self.cache_info["size"][2] and self.cache_info["size"][3]:
            self.cache_info["size"][2] = self.cache_info["size"][3]
            self.cache_info["size"][3] = 0

    def _get_size_str(self, num):
        if num >= 1024 * 1024:
            return "{:d} MB".format(num / (1024 * 1024))
        elif num:
            return "{:d} kB".format(num / (1024))
        else:
            return "0 B"

    def __repr__(self):
        if self["online"]:
            return "core info (idx {:d}), socket is {:d}, phys_core {:d}, {}, {}".format(
                self["core_num"],
                self["socket_num"],
                self["ht_core_num"],
                self.get_cache_info_str(),
                self["cpu_id"]
            )
        else:
            print("core info (idx {:d}), offline".format(self.core_num))


class global_cpu_info(object):
    def __init__(self, **kwargs):
        for bin_name in ["/opt/cluster/bin/cpuid", "/usr/bin/cpuid"]:
            if os.path.isfile(bin_name):
                self.__cpuid_binary = bin_name
                break
        _xml = kwargs.get("xml", None)
        if _xml is not None:
            kernel_tuple = _xml.xpath(".//ns0:cpu_info/ns0:kernel_tuple", namespaces={"ns0": server_command.XML_NS}, smart_strings=False)[0]
            self.c_stat_kernel, self.c_out_kernel = (int(kernel_tuple.attrib["stat"]), bz2.decompress(base64.b64decode(kernel_tuple.text)))
            cpuid_tuple = _xml.xpath(".//ns0:cpu_info/ns0:cpuid_tuple", namespaces={"ns0": server_command.XML_NS}, smart_strings=False)[0]
            self.c_stat_cpuid, self.c_out_cpuid = (int(cpuid_tuple.attrib["stat"]), bz2.decompress(base64.b64decode(cpuid_tuple.text)))
            proc_dict = _xml.xpath(".//ns0:cpu_info/ns0:proc_dict", namespaces={"ns0": server_command.XML_NS}, smart_strings=False)[0]
            self.__proc_dict = marshal.loads(bz2.decompress(base64.b64decode(proc_dict.text)))
        else:
            self.c_stat_kernel, self.c_out_kernel = getstatusoutput("{} -k -r".format(self.__cpuid_binary))
            if self.c_stat_kernel:
                # try to load cpuid
                getstatusoutput("/sbin/modprobe cpuid")
                self.c_stat_kernel, self.c_out_kernel = getstatusoutput("{} -k -r".format(self.__cpuid_binary))
            self.c_stat_cpuid, self.c_out_cpuid = getstatusoutput("{} -r".format(self.__cpuid_binary))
            self.__proc_dict = self._read_proc_info()
        if kwargs.get("parse", False):
            self.parse_info()

    def get_send_dict(self, srv_com):
        el_builder = srv_com.builder
        cpu_info = el_builder("cpu_info", version="1")
        cpu_info.extend(
            [
                el_builder("kernel_tuple", base64.b64encode(bz2.compress(self.c_out_kernel)), stat="{:d}".format(self.c_stat_kernel)),
                el_builder("cpuid_tuple", base64.b64encode(bz2.compress(self.c_out_cpuid)), stat="{:d}".format(self.c_stat_cpuid)),
                el_builder("proc_dict", base64.b64encode(bz2.compress(marshal.dumps(self.__proc_dict))))
            ]
        )
        srv_com["cpu_info"] = cpu_info

    def parse_info(self):
        if self.c_out_kernel.split("\n")[1].strip().startswith("0x"):
            # only parse if hex_dump is found
            os_h, tmp_f_name = tempfile.mkstemp("cpuid")
            open(tmp_f_name, "w").write(self.c_out_kernel)
            self.c_stat_kernel, self.c_out_kernel = getstatusoutput("%s -f %s" % (self.__cpuid_binary, tmp_f_name))
            open(tmp_f_name, "w").write(self.c_out_cpuid)
            self.c_stat_cpuid, self.c_out_cpuid = getstatusoutput("%s -f %s" % (self.__cpuid_binary, tmp_f_name))
            os.close(os_h)
            os.unlink(tmp_f_name)
            if self.c_stat_kernel and self.c_stat_cpuid:
                raise ValueError("error calling cpuid with and without -k flag ('%s', '%s')" % (
                    self.c_out_kernel,
                    self.c_out_cpuid)
                )
        if not self.c_stat_kernel:
            source_kernel = True
            c_out = self.c_out_kernel
        else:
            source_kernel = False
            c_out = self.c_out_cpuid
        lines = c_out.split("\n")
        if lines[0].lower() == "cpu:":
            self.from_kernel_module = False
        else:
            self.from_kernel_module = True
        self._check_proc_dict()
        self.__cpu_dict = {}
        for core_idx in list(self.__proc_dict.keys()):
            self.__cpu_dict[core_idx] = cpu_info(self.__proc_dict[core_idx])
        # helper flags for layouting
        self.__hyper_threading = False
        self._check_layout()

    def _check_layout(self):
        phys_dict = {}
        # socket -> core -> cpu_num
        proc_dict = self.__proc_dict
        self.__multi_core = False
        # dict core_num -> socket
        cs_dict = {}
        # find first valid info
        valid_info = [value for value in proc_dict.values() if value["online"]][0]
        if "cpu cores" in valid_info:
            self.__multi_core = True
            # multi-core info
            for cpu_num, cpu_stuff in proc_dict.items():
                if cpu_stuff["online"]:
                    cs_dict[cpu_num] = cpu_stuff["physical_id"]
                    _num_cores, core_id, physical_id = (
                        cpu_stuff["cpu_cores"],
                        cpu_stuff["core_id"],
                        cpu_stuff["physical_id"]
                    )
                    phys_dict.setdefault(physical_id, {}).setdefault(core_id, []).append(cpu_num)
        elif valid_info.get("siblings", 1) > 1:
            # hyperthreading info
            for cpu_num, cpu_stuff in proc_dict.items():
                if cpu_stuff["online"]:
                    cs_dict[cpu_num] = cpu_stuff["physical_id"]
                    physical_id = (cpu_stuff["physical_id"])
                    phys_dict.setdefault(physical_id, {}).setdefault(0, []).append(cpu_num)
        else:
            # nothing left, single core, single threaded
            for cpu_num, cpu_stuff in proc_dict.items():
                if cpu_stuff["online"]:
                    cs_dict[cpu_num] = 0
                    phys_dict.setdefault(cpu_num, {}).setdefault(0, []).append(cpu_num)
        # pprint.pprint(phys_dict)
        # in fact we don't use much info from phys_dict ...
        my_layout = cpu_layout()
        # build the share maps
        for core_num in sorted(self.__cpu_dict.keys()):
            core_stuff = self.__cpu_dict[core_num]
            if "share_dict" in core_stuff.cache_info:
                for c_level, s_map in core_stuff.cache_info["share_dict"].items():
                    my_layout.place_core(core_num, c_level, s_map)
                    # share_maps.setdefault(c_level, share_map(c_level)).place_core(core_num, s_map)
            else:
                # no share_dict, place by hand
                # check for cache_info (in case of disabled cores)
                if core_stuff.cache_info:
                    for c_level, c_size in core_stuff.cache_info["size"].items():
                        if c_size:
                            if not self.__multi_core:
                                if self.__hyper_threading:
                                    # 2 cores per l1, 2 cores per l2
                                    for _sock_num, sock_stuff in phys_dict.items():
                                        if core_num in sock_stuff[0]:
                                            core_stuff.cache_info.setdefault("share_dict", {})[c_level] = set(sock_stuff[0])
                                            my_layout.place_core(core_num, c_level, sock_stuff[0])
                                else:
                                    for _sock_num, sock_stuff in phys_dict.items():
                                        if core_num in sock_stuff[0]:
                                            core_stuff.cache_info.setdefault("share_dict", {})[c_level] = set(sock_stuff[0])
                                            my_layout.place_core(core_num, c_level, sock_stuff[0])
                            else:
                                if len(list(self.__cpu_dict.keys())) == 1:
                                    # simple layout (only one core)
                                    for _sock_num, sock_stuff in phys_dict.items():
                                        if core_num in sock_stuff[0]:
                                            core_stuff.cache_info.setdefault("share_dict", {})[c_level] = set(sock_stuff[0])
                                            my_layout.place_core(core_num, c_level, sock_stuff[0])
                                else:
                                    # print "unable to layout, please fixme (# is %d, mc is %s, ht is %s)" % (len(self.__cpu_dict.keys()),
                                    #                                                                        str(self.__multi_core),
                                    #                                                                        str(self.__hyper_threading))
                                    # treat is as multi-socket single-core system
                                    for _sock_num, sock_stuff in phys_dict.items():
                                        if core_num in sock_stuff[0]:
                                            core_stuff.cache_info.setdefault("share_dict", {})[c_level] = set(sock_stuff[0])
                                            my_layout.place_core(core_num, c_level, sock_stuff[0])

        for core_num in sorted(self.__cpu_dict.keys()):
            if self.__cpu_dict[core_num]["online"]:
                my_layout.add_logical_core(
                    core_num,
                    self.__cpu_dict[core_num],
                    cs_dict[core_num]
                )
        self.layout = my_layout

    def _check_proc_dict(self):
        # some sanity checks for proc_dict
        for _key, value in self.__proc_dict.items():
            if "online" not in value:
                value["online"] = True

    def _parse_size(self, in_str):
        if in_str.isdigit():
            return int(in_str)
        else:
            return int(in_str[:-1]) * {
                "k": 1024,
                "m": 1024 * 1024,
                "g": 1024 * 1024 * 1024
            }[in_str[-1].lower()]

    def _parse_proc_value(self, in_val):
        in_val = in_val.strip()
        if in_val.isdigit():
            return int(in_val)
        else:
            return in_val

    def _read_proc_info(self):
        sys_base_dir = "/sys/devices/system/cpu/"
        if os.path.isdir(sys_base_dir):
            sys_cpus = [int(entry[3:]) for entry in os.listdir(sys_base_dir) if entry.startswith("cpu") and entry[3:].isdigit()]
        else:
            sys_cpus = []
        cpu_info_file = "/proc/cpuinfo"
        if os.path.isfile(cpu_info_file):
            cpu_dict = {}
            lines = open(cpu_info_file, "r").read().split("\n")
            while lines:
                act_cpu_lines = []
                while True:
                    if lines:
                        act_line = lines.pop(0).replace("\t", " ")
                        if act_line:
                            act_cpu_lines.append(act_line)
                        else:
                            break
                    else:
                        break
                if act_cpu_lines:
                    act_cpu_dict = {
                        key.strip().replace(" ", "_"): self._parse_proc_value(value) for key, value in [
                            act_line.split(":", 1) for act_line in act_cpu_lines
                        ]
                    }
                    act_cpu_dict["online"] = True
                    # check for info from /sys/
                    sys_dict = {}
                    if act_cpu_dict["processor"] in sys_cpus:
                        cache_dir = os.path.join(
                            sys_base_dir,
                            "cpu{:d}".format(act_cpu_dict["processor"]),
                            "cache",
                        )
                        if os.path.isdir(cache_dir):
                            sys_dict["cache"] = {}
                            for act_c_dir in os.listdir(cache_dir):
                                sys_dict["cache"][act_c_dir] = {}
                                for entry in os.listdir(os.path.join(cache_dir, act_c_dir)):
                                    try:
                                        content = open(
                                            os.path.join(
                                                cache_dir,
                                                act_c_dir,
                                                entry
                                            ),
                                            "r"
                                        ).read().strip()
                                    except:
                                        # unreadable file (cache_disable_*)
                                        pass
                                    else:
                                        if entry == "shared_cpu_map":
                                            # do not parse shared_cpu_map
                                            pass
                                        elif entry == "size":
                                            content = self._parse_size(content)
                                        elif content.isdigit():
                                            content = int(content)
                                        sys_dict["cache"][act_c_dir][entry] = content
                        topo_dir = os.path.join(sys_base_dir, "cpu{:d}".format(act_cpu_dict["processor"]), "topology")
                        if os.path.isdir(topo_dir):
                            sys_dict["topology"] = {}
                            for entry in os.listdir(topo_dir):
                                content = open(
                                    os.path.join(
                                        topo_dir,
                                        entry
                                    ), "r"
                                ).read().strip()
                                if entry.endswith("_siblings"):
                                    # parse not local
                                    pass
                                elif content.isdigit():
                                    content = int(content)
                                sys_dict["topology"][entry] = content
                        # read cache info
                    act_cpu_dict["sys_info"] = sys_dict
                    cpu_dict[act_cpu_dict["processor"]] = act_cpu_dict
        else:
            raise IOError("cannot find %s" % (cpu_info_file))
        # check for disabled cpus
        dis_cpus = [cpu_idx for cpu_idx in sys_cpus if cpu_idx not in cpu_dict]
        for dis_cpu in dis_cpus:
            cpu_dict[dis_cpu] = {
                "online": False,
                "processor": dis_cpu
            }
        return cpu_dict

    def cpu_idxs(self):
        return list(self.__cpu_dict.keys())

    def __getitem__(self, key):
        return self.__cpu_dict[key]

    def __setitem__(self, key, value):
        self.__cpu_dict[key] = value

    def __repr__(self):
        return "CPU info, {} found:\n{}".format(
            logging_tools.get_plural("core", self.num_cores()),
            "\n".join(
                [
                    "  {}".format(str(self[core_num])) for core_num in sorted(self.cpu_cores())
                ]
            )
        )

    def num_sockets(self):
        # return number of cpu_sockets
        return len(set([cpu["socket_num"] for cpu in self.__cpu_dict.values() if cpu["online"]]))

    def num_cores(self):
        # return number of cpu_cores
        return len(list(self.__cpu_dict.keys()))

    def cpu_cores(self):
        # return cpu_cores
        return sorted(self.__cpu_dict.keys())


def get_cpuid():
    gci = global_cpu_info(parse=True)  # , check_topology=False)
    first_cpu = gci[gci.cpu_idxs()[0]]
    # full cpuid-string:
    # [VERSION]_[L1SIZE][L2SIZE][L3SIZE]_[CPUID]
    return "0_{}_{}".format(
        first_cpu.get_short_cache_info(),
        first_cpu["cpu_id"]
    )

# most likely source: http://www.softeng.rl.ac.uk/st/archive/SoftEng/SESP/html/SoftwareTools/vtune/
# users_guide/mergedProjects/analyzer_ec/mergedProjects/reference_olh/mergedProjects/instructions/instruct32_hh/vc46.htm
CPU_FLAG_LUT = {
    "FPU": "Floating Point Unit On-Chip. The processor contains an x87 FPU.",
    "VME": "Virtual 8086 Mode Enhancements. Virtual 8086 mode enhancements, including CR4.VME for controlling the feature, "
    "CR4.PVI for protected mode virtual interrupts, software interrupt indirection, expansion of the TSS with the software indirection bitmap, "
    "and EFLAGS.VIF and EFLAGS.VIP flags.",
    "DE": "Debugging Extensions. Support for I/O breakpoints, including CR4.DE for controlling the feature, and optional trapping of "
    "accesses to DR4 and DR5.",
    "PSE": "Page Size Extension. Large pages of size 4Mbyte are supported, including CR4.PSE for controlling the feature, the defined "
    "dirty bit in PDE (Page Directory Entries), optional reserved bit trapping in CR3, PDEs, and PTEs.",
    "TSC": "Time Stamp Counter. The RDTSC instruction is supported, including CR4.TSD for controlling privilege.",
    "MSR": "Model Specific Registers RDMSR and WRMSR Instructions. The RDMSR and WRMSR instructions are supported. Some of the MSRs "
    "are implementation dependent.",
    "PAE": "Physical Address Extension. Physical addresses greater than 32 bits are supported: extended page table entry formats, an "
    "extra level in the page translation tables is defined, 2 Mbyte pages are supported instead of 4 Mbyte pages if PAE bit is 1. "
    "The actual number of address bits beyond 32 is not defined, and is implementation specific.",
    "MCE": "Machine Check Exception. Exception 18 is defined for Machine Checks, including CR4.MCE for controlling the feature. This "
    "feature does not define the model-specific implementations of machine-check error logging, reporting, and processor shutdowns. Machine "
    "Check exception handlers may have to depend on processor version to do model specific processing of the exception, or test for the presence "
    "of the Machine Check feature.",
    "CX8": "CMPXCHG8B Instruction. The compare-and-exchange 8 bytes (64 bits) instruction is supported (implicitly locked and atomic).",
    "APIC": "APIC On-Chip. The processor contains an Advanced Programmable Interrupt Controller (APIC), responding to memory mapped commands in "
    "the physical address range FFFE0000H to FFFE0FFFH (by default - some processors permit the APIC to be relocated).",
    "SEP": "SYSENTER and SYSEXIT Instructions. The SYSENTER and SYSEXIT and associated MSRs are supported.",
    "MTRR": "Memory Type Range Registers. MTRRs are supported. The MTRRcap MSR contains feature bits that describe what memory types are supported, "
    "how many variable MTRRs are supported, and whether fixed MTRRs are supported.",
    "PGE": "PTE Global Bit. The global bit in page directory entries (PDEs) and page table entries (PTEs) is supported, indicating TLB entries that "
    "are common to different processes and need not be flushed. The CR4.PGE bit controls this feature.",
    "MCA": "Machine Check Architecture. The Machine Check Architecture, which provides a compatible mechanism for error reporting in P6 family, "
    "Pentium 4, and Intel Xeon processors is supported. The MCG_CAP MSR contains feature bits describing how many banks of error reporting MSRs "
    "are supported.",
    "CMOV": "Conditional Move Instructions. The conditional move instruction CMOV is supported. In addition, if x87 FPU is present as indicated by "
    "the CPUID.FPU feature bit, then the FCOMI and FCMOV instructions are supported.",
    "PAT": "Page Attribute Table. Page Attribute Table is supported. This feature augments the Memory Type Range Registers (MTRRs), allowing an "
    "operating system to specify attributes of memory on a 4K granularity through a linear address.",
    "PSE-36": "32-Bit Page Size Extension. Extended 4-MByte pages that are capable of addressing physical memory beyond 4 GBytes are supported. This "
    "feature indicates that the upper four bits of the physical address of the 4-MByte page is encoded by bits 13-16 of the page directory entry.",
    "PSN": "Processor Serial Number. The processor supports the 96-bit processor identification number feature and the feature is enabled.",
    "CLFLSH": "CLFLUSH Instruction. CLFLUSH Instruction is supported.",
    "DS": "Debug Store. The processor supports the ability to write debug information into a memory resident buffer. This feature is used by the "
    "branch trace store (BTS) and precise event-based sampling (PEBS) facilities (see Chapter 15, Debugging and Performance Monitoring, in the "
    "IA-32 Intel Architecture Software Developer's Manual, Volume 3).",
    "ACPI": "Thermal Monitor and Software Controlled Clock Facilities. The processor implements internal MSRs that allow processor temperature to "
    "be monitored and processor performance to be modulated in predefined duty cycles under software control.",
    "MMX": "Intel MMX Technology. The processor supports the Intel MMX technology.",
    "FXSR": "FXSAVE and FXRSTOR Instructions. The FXSAVE and FXRSTOR instructions are supported for fast save and restore of the floating point "
    "context. Presence of this bit also indicates that CR4.OSFXSR is available for an operating system to indicate that it supports the FXSAVE "
    "and FXRSTOR instructions.",
    "SSE": "SSE. The processor supports the SSE extensions.",
    "SSE2": "SSE2. The processor supports the SSE2 extensions.",
    "SS": "Self Snoop. The processor supports the management of conflicting memory types by performing a snoop of its own cache structure for "
    "transactions issued to the bus.",
    "HTT": "Hyper-Threading Technology. The processor implements Hyper-Threading technology.",
    "TM": "Thermal Monitor. The processor implements the thermal monitor automatic thermal control circuitry (TCC).",
    "PBE": "Pending Break Enable. The processor supports the use of the FERR#/PBE# pin when the processor is in the stop-clock state (STPCLK# is "
    "asserted) to signal the processor that an interrupt is pending and that the processor should return to normal operation to handle the interrupt. "
    "Bit 10 (PBE enable) in the IA32_MISC_ENABLE MSR enables this capability.",
}
