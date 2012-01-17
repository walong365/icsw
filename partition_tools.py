#!/usr/bin/python-init -Ot
#
# Copyright (C) 2008,2009 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" partition stuff """

import os
import commands
import sys
import process_tools
import logging_tools
import pprint

class lvm_object(object):
    def __init__(self, lv_type, in_dict):
        self.lv_type = lv_type
        self.__ignore_list = ["percent"]
        self.__int_keys = ["major", "minor", "kernel_major", "kernel_minor", "used", "max_pv", "max_lv", "stripes", "free"]
        self.__val_dict = {}
        for key, value in in_dict.iteritems():
            self[key] = value
    def __getitem__(self, key):
        return self.__val_dict[key]
    def get(self, key, def_value):
        return self.__val_dict.get(key, def_value)
    def __setitem__(self, key, value):
        if key.startswith("%s_" % (self.lv_type)):
            key = key[3:]
        if key in self.__int_keys or key.count("size") or key.count("count"):
            if value.endswith("B"):
                value = value[:-1]
            value = int(value)
        elif type(value) == type(""):
            value = value.strip()
        self.__val_dict[key] = value
    def __repr__(self):
        return "\n".join(["{",
                          "--- name %s, type %s --- " % (self["name"], self.lv_type)] +
                         ["%-20s: (%s) %s" % (key, str(type(value)), str(value)) for key, value in self.__val_dict.iteritems()] +
                         ["}"])
    
class lvm_struct(object):
    def __init__(self, source, **args):
        # represents the LVM-information of a machine, source can be
        # - binaries
        # - dict (rom network)
        self.lvm_present = False
        self.__source = source
        if self.__source == "bin":
            self._check_binary_paths()
            self.update()
        elif self.__source == "dict":
            self._set_dict(args.get("source_dict", {}))
    def _check_binary_paths(self):
        lvm_path = ["/sbin", "/usr/sbin", "/usr/local/sbin"]
        lvm_bins = {"pv" : ["pv_uuid", "pv_fmt", "pv_size", "dev_size",
                            "pv_free", "pv_used", "pv_name", "pv_attr",
                            "pv_pe_count", "pv_pe_alloc_count", "pv_tags"],
                    "vg" : ["vg_uuid", "vg_fmt", "vg_name", "vg_attr",
                            "vg_size", "vg_free", "vg_sysid", "vg_extent_size", "vg_extent_count", "vg_free_count",
                            "max_lv", "max_pv", "pv_count", "lv_count", "snap_count", "vg_seqno", "vg_tags", "pv_name"],
                    "lv" : ["lv_uuid", "lv_name", "lv_attr",
                            "lv_major", "lv_minor", "lv_kernel_major", "lv_kernel_minor",
                            "lv_size", "seg_count", "origin", "snap_percent", "copy_percent",
                            "move_pv", "lv_tags", "segtype", "stripes", "stripesize", "chunksize",
                            "seg_start", "seg_size", "seg_tags", "devices", "vg_name"]}
        self.__lvm_bin_dict = {}
        for bn, bn_opts in lvm_bins.iteritems():
            path_found = [x for x in ["%s/%ss" % (y, bn) for y in lvm_path] if os.path.isfile(x)]
            if path_found:
                self.__lvm_bin_dict[bn] = (path_found[0], bn_opts)
    def update(self):
        self.lv_dict = {}
        if self.__source == "bin" and self.__lvm_bin_dict:
            self.lvm_present = True
            ret_dict = {}
            for name, (bin_path, options) in self.__lvm_bin_dict.iteritems():
                ret_dict[name] = []
                if bin_path:
                    num_sep = len(options)
                    com = "%s --separator \; --units b -o %s" % (bin_path, ",".join(options))
                    stat, out = commands.getstatusoutput(com)
                    if not stat:
                        lines = [x.strip() for x in out.split("\n") if x.strip() and x.count(";") >= num_sep / 2]
                        if lines:
                            header = lines.pop(0)
                            remove_semic = header.endswith(";")
                            if remove_semic:
                                header = header[:-1]
                            ret_dict[name] = []
                            for line in lines:
                                if remove_semic:
                                    line_p = line[:-1].split(";")
                                else:
                                    line_p = line.split(";")
                                targ_dict = dict(zip(options, line_p))
                                ret_dict[name].append(targ_dict)
            self._parse_dict(ret_dict)
    def _parse_dict(self, ret_dict):
        self.lv_dict = {}
        for name in ["lv", "pv", "vg"]:
            for stuff in ret_dict.get(name, []):
                try:
                    new_lv_obj = lvm_object(name, stuff)
                except:
                    print process_tools.get_except_info()
                else:
                    self.lv_dict.setdefault(name, {})[new_lv_obj["name"]] = new_lv_obj
    def generate_send_dict(self):
        # creator for send_dict
        return {"version"     : 1,
                "lvm_present" : self.lvm_present,
                "lv_dict"     : self.lv_dict}
    def _set_dict(self, in_dict):
        # interpreter for send_dict
        self.lvm_present = in_dict.get("lvm_present", False)
        self.lv_dict = in_dict.get("lv_dict", {})
    def _get_size_str(self, in_b):
        pf_list = ["", "k", "M", "G", "T", "E", "P"]
        rst = float(in_b)
        while rst > 1024:
            pf_list.pop(0)
            rst /= 1024.
        return "%.2f %sB" % (rst, pf_list[0])
    def get_info(self):
        vg_names = sorted(self.lv_dict.get("vg", {}).keys())
        vg_info = {}
        for vg_name in vg_names:
            vg_stuff = self.lv_dict.get("vg", {})[vg_name]
            vg_extent_size = vg_stuff["extent_size"]
            vg_extent_count = vg_stuff["extent_count"]
            vg_info[vg_name] = (self._get_size_str(vg_stuff["size"]),
                                self._get_size_str(vg_stuff["free"]))
        lv_names = sorted(self.lv_dict.get("lv", {}).keys())
        lv_info = {}
        for lv_name in lv_names:
            lv_stuff = self.lv_dict.get("lv", {})[lv_name]
            vg_name = lv_stuff["vg_name"]
            lv_size = lv_stuff["size"]
            lv_info.setdefault(vg_name, []).append("%s%s (%s)" % (lv_name,
                                                                  lv_stuff["attr"][5] == "o" and "[open]" or "",
                                                                  self._get_size_str(lv_size)))
            #print "*", lv_name, vg_stuff["name"], vg_extent_size, vg_extent_count, vg_size, lv_extents
        ret_info = []
        for vg_name in vg_names:
            ret_info.append("%s (%s, %s free, %s: %s)" % (vg_name,
                                                           vg_info[vg_name][0],
                                                           vg_info[vg_name][1],
                                                           logging_tools.get_plural("LV", len(lv_info.get(vg_name, []))),
                                                           ", ".join(lv_info.get(vg_name, [])) or "NONE"))
        return "%s: %s" % (logging_tools.get_plural("VG", len(ret_info)),
                           "; ".join(ret_info))
    def __repr__(self):
        order_list = ["pv", "vg", "lv"]
        ret_a = ["%s:" % (", ".join(["%s" % (logging_tools.get_plural(k, len(self.lv_dict.get(k, {}).keys()))) for k in order_list]))]
        for ol in order_list:
            ret_a.append("\n".join([str(x) for x in self.lv_dict.get(ol, {}).values()]))
        return "\n".join(ret_a)

class disk_lut(object):
    def __init__(self, **args):
        self.start_path = args.get("start_path", "/dev/disk")
        self.__lut = {}
        if os.path.isdir(self.start_path):
            for entry in os.listdir(self.start_path):
                if entry.startswith("by-"):
                    entry_type = entry[3:]
                    loc_dict = {}
                    loc_dir = "%s/%s" % (self.start_path, entry)
                    for sub_entry in os.listdir(loc_dir):
                        full_path = "%s/by-%s/%s" % (self.start_path, entry_type, sub_entry)
                        if os.path.islink(full_path):
                            target = os.path.normpath(os.path.join(loc_dir, os.readlink(full_path)))
                            loc_dict.setdefault(target, []).append(sub_entry)
                            loc_dict[sub_entry] = target
                    self.__lut[entry_type] = loc_dict
    def get_top_keys(self):
        return self.__lut.keys()
    def __getitem__(self, key):
        entry_type = None
        if type(key) == type(""):
            if key.startswith("/dev/disk/by-"):
                entry_type, key = key.split("-", 1)[1].split("/")
            else:
                return self.__lut[key]
        else:
            entry_type, key = key
        return self.__lut[entry_type][key]

def test_it():
    my_lut = disk_lut()
    print my_lut[("id", "/dev/sda8")]

if __name__ == "__main__":
    #test_it()
    print "loadable module, exiting ..."
    sys.exit(-1)
