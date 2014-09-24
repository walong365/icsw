# Copyright (C) 2008-2014 Andreas Lang-Nevyjel, init.at
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
""" tools for handling partition tables (LVM and UUID / label stuff) """

import commands
import logging_tools
import os
import process_tools
import re


class uuid_label_struct(dict):
    def __init__(self):
        # after init can be used like
        # _uls = uuid_label_struct()
        # print _uls[UUID]
        dict.__init__(self)
        c_stat, c_out = commands.getstatusoutput("/sbin/blkid")
        if not c_stat:
            for _line in c_out.split("\n"):
                if _line.count(":"):
                    part, _rest = _line.split(":", 1)
                    _dict = dict([_part.split("=", 1) for _part in _rest.strip().split()])
                    _dict = {key: value[1:-1] if value.startswith('"') else value for key, value in _dict.iteritems()}
                    _dict["part"] = part
                    for key in set(_dict) & set(["UUID"]):
                        self[_dict[key]] = _dict


class lvm_object(dict):
    def __init__(self, lv_type, in_dict):
        dict.__init__(self)
        self.lv_type = lv_type
        self.__ignore_list = ["percent"]
        self.__int_keys = ["major", "minor", "kernel_major", "kernel_minor", "used", "max_pv", "max_lv", "stripes", "free"]
        if type(in_dict) == dict:
            for key, value in in_dict.iteritems():
                self[key] = value
        else:
            # xml input
            for key, value in in_dict.attrib.iteritems():
                self[key] = value
            if len(in_dict):
                self["mount_options"] = {
                    sub_key: sub_value if sub_key not in ["fsck", "dump"] else int(sub_value) for sub_key, sub_value in in_dict[0].attrib.iteritems()
                }

    def __setitem__(self, key, value):
        if key.startswith("{}_".format(self.lv_type)):
            key = key[3:]
        if key in self.__int_keys or key.count("size") or key.count("count"):
            if value.endswith("B"):
                value = value[:-1]
            value = int(value)
        elif isinstance(value, basestring):
            value = value.strip()
        dict.__setitem__(self, key, value)

    def build_xml(self, builder):
        cur_el = builder(self.lv_type, **self._get_xml_attributes())
        if "mount_options" in self:
            cur_el.append(builder("mount_options", **self._get_xml_attributes(self["mount_options"])))
        return cur_el

    def _get_xml_attributes(self, src_obj=None):
        src_obj = src_obj or self
        r_dict = {}
        for key, value in src_obj.iteritems():
            if isinstance(value, basestring):
                r_dict[key] = value
            elif type(value) in [int, long]:
                r_dict[key] = "{:d}".format(value)
        return r_dict

    def __repr__(self):
        return "\n".join(
            [
                "{",
                "--- name {}, type {} --- ".format(self["name"], self.lv_type)
            ] + [
                "{:<20s}: ({}) {}".format(key, str(type(value)), str(value)) for key, value in self.iteritems()
            ] + ["}"]
        )


class multipath_struct(object):
    def __init__(self, source, **kwargs):
        self.multi_present = False
        self.__source = source
        if self.__source == "bin":
            self._check_binary_paths()
            self.update()

    def _check_binary_paths(self):
        mp_path = ["/sbin", "/usr/sbin", "/usr/local/sbin"]
        mp_bins = {"multipath": "-ll"}
        self.__mp_bin_dict = {}
        for bn, bn_opts in mp_bins.iteritems():
            path_found = [entry for entry in [os.path.join(name, bn) for name in mp_path] if os.path.isfile(entry)]
            if path_found:
                self.__mp_bin_dict[bn] = (path_found[0], bn_opts)

    def update(self):
        dev_dict = {}
        if self.__mp_bin_dict:
            cur_stat, cur_out = commands.getstatusoutput("{} {}".format(*self.__mp_bin_dict["multipath"]))
            if not cur_stat:
                re_dict = {
                    "header1": re.compile("^(?P<name>\S+)\s+\((?P<id>\S+)\)\s+(?P<devname>\S+)\s+(?P<info>.*)$"),
                    "header2": re.compile("^(?P<id>\S+)\s+(?P<devname>dm-\S+)\s+(?P<info>.*)$"),
                    "feature": re.compile("^size=(?P<size>\S+)\s+features=\'(?P<features>[^\']+)\' hwhandler=\'(?P<hwhandler>\d+)\'\s+(?P<wp_info>\S+)$"),
                    "policy": re.compile("^.*policy=\'(?P<policy>[^\']+)\'\s+prio=(?P<prio>\d+)\s+status=(?P<status>\S+)$"),
                    "device": re.compile(
                        "^.*(?P<scsiid>\d+:\d+:\d+:\d+)\s+(?P<device>\S+)\s+(?P<major>\d+):(?P<minor>\d+)\s+(?P<active>\S+)\s+(?P<ready>\S+)\s+(?P<running>\S+)$"
                    ),
                }
                result_list = []
                prev_re, all_parsed = (None, True)
                for line in cur_out.split("\n"):
                    re_line = [(re_name, cur_re.match(line).groupdict()) for re_name, cur_re in re_dict.iteritems() if cur_re.match(line)]
                    if re_line:
                        re_type, re_obj = re_line[0]
                        # check for correct order
                        if re_type in {
                            None: ["header1", "header2"],
                            "header1": ["feature"],
                            "header2": ["feature"],
                            "feature": ["policy"],
                            "policy": ["device"],
                            "device": ["policy", "header1", "header2"]
                        }.get(prev_re, []):
                            result_list.append((re_type, re_obj))
                            prev_re = re_type
                        else:
                            all_parsed = False
                            break
                if all_parsed:
                    # for integer cleanup
                    _int_set = ["hwhandler", "major", "minor", "prio"]
                    # build dict
                    for re_name, g_dict in result_list:
                        for key, value in g_dict.iteritems():
                            # tidy
                            g_dict[key] = value.strip()
                            if key in _int_set:
                                g_dict[key] = int(g_dict[key])
                        if re_name in ["header1", "header2"]:
                            new_dev = g_dict
                            if "name" in g_dict:
                                dev_dict[g_dict["name"]] = new_dev
                            else:
                                dev_dict[g_dict["id"]] = new_dev
                        elif re_name == "feature":
                            new_dev.update(g_dict)
                        elif re_name == "policy":
                            cur_entry = g_dict
                            new_dev.setdefault("list", []).append(cur_entry)
                        else:
                            cur_entry.update(g_dict)
        self.dev_dict = dev_dict


class lvm_struct(object):
    def __init__(self, source, **kwargs):
        # represents the LVM-information of a machine, source can be
        # - binaries
        # - dict (rom network)
        self.lvm_present = False
        self.__source = source
        if self.__source == "bin":
            self._check_binary_paths()
            self.update()
        elif self.__source == "dict":
            self._set_dict(kwargs.get("source_dict", {}))
        elif self.__source == "xml":
            self._parse_xml(kwargs["xml"])
        else:
            print "unknown source '{}' for lvm_struct.__init__".format(source)

    def _check_binary_paths(self):
        lvm_path = ["/sbin", "/usr/sbin", "/usr/local/sbin"]
        lvm_bins = {
            "pv": [
                "pv_uuid", "pv_fmt", "pv_size", "dev_size",
                "pv_free", "pv_used", "pv_name", "pv_attr",
                "pv_pe_count", "pv_pe_alloc_count", "pv_tags"
            ],
            "vg": [
                "vg_uuid", "vg_fmt", "vg_name", "vg_attr",
                "vg_size", "vg_free", "vg_sysid", "vg_extent_size", "vg_extent_count", "vg_free_count",
                "max_lv", "max_pv", "pv_count", "lv_count", "snap_count", "vg_seqno", "vg_tags", "pv_name"
            ],
            "lv": [
                "lv_uuid", "lv_name", "lv_attr",
                "lv_major", "lv_minor", "lv_kernel_major", "lv_kernel_minor",
                "lv_size", "seg_count", "origin", "snap_percent", "copy_percent",
                "move_pv", "lv_tags", "segtype", "stripes", "stripesize", "chunksize",
                "seg_start", "seg_size", "seg_tags", "devices", "vg_name"
            ]
        }
        self.__lvm_bin_dict = {}
        for bn, bn_opts in lvm_bins.iteritems():
            path_found = [entry for entry in [os.path.join(name, "{}s".format(bn)) for name in lvm_path] if os.path.isfile(entry)]
            if path_found:
                self.__lvm_bin_dict[bn] = (path_found[0], bn_opts)

    def _read_dm_links(self):
        m_dict = {"dmtolv": {}, "lvtodm": {}}
        s_dir = "/dev/mapper"
        if os.path.isdir(s_dir):
            for entry in os.listdir(s_dir):
                f_path = os.path.join(s_dir, entry)
                if os.path.islink(f_path):
                    target = os.path.normpath(os.path.join(s_dir, os.readlink(f_path)))
                    m_dict["lvtodm"][entry] = target
                    m_dict["lvtodm"][os.path.join("/dev", *entry.split("-"))] = target
                    m_dict["dmtolv"][target] = f_path
                    # m_dict[os.path.basename(target)] = entry
                    # m_dict[target] = entry
        return m_dict

    def update(self):
        # read all dm-links
        self.dm_dict = self._read_dm_links()
        # pprint.pprint(self.dm_dict)
        self.lv_dict = {}
        if self.__source == "bin" and self.__lvm_bin_dict:
            self.lvm_present = True
            ret_dict = {}
            for name, (bin_path, options) in self.__lvm_bin_dict.iteritems():
                ret_dict[name] = []
                if bin_path:
                    num_sep = len(options)
                    com = "{} --separator \; --units b -o {}".format(bin_path, ",".join(options))
                    c_stat, c_out = commands.getstatusoutput(com)
                    if not c_stat:
                        lines = [line.strip() for line in c_out.split("\n") if line.strip() and line.count(";") >= num_sep / 2]
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
        return {
            "version": 1,
            "lvm_present": self.lvm_present,
            "lv_dict": self.lv_dict
        }

    def generate_xml_dict(self, builder):
        lvm_el = builder("lvm_config",
                         version="2",
                         lvm_present="1" if self.lvm_present else "0")
        for m_key, val_list in self.lv_dict.iteritems():
            sub_struct = builder("lvm_{}".format(m_key), lvm_type=m_key, entities="{:d}".format(len(val_list)))
            lvm_el.append(sub_struct)
            for _el_key, element in val_list.iteritems():
                sub_struct.append(element.build_xml(builder))
        return lvm_el

    def _parse_xml(self, top_el):
        self.lv_dict = {}
        for top_struct in top_el[0]:
            cur_key = top_struct.tag.split("}")[1][4:]
            for sub_el in top_struct:
                new_lv_obj = lvm_object(cur_key, sub_el)
                self.lv_dict.setdefault(cur_key, {})[new_lv_obj["name"]] = new_lv_obj
        self.lvm_present = True if top_el[0].attrib["lvm_present"] == "1" else False

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
        return "{:.2f} {}B".format(rst, pf_list[0])

    def get_info(self, short=True):
        vg_names = sorted(self.lv_dict.get("vg", {}).keys())
        vg_info = {}
        for vg_name in vg_names:
            vg_stuff = self.lv_dict.get("vg", {})[vg_name]
            _vg_extent_size = vg_stuff["extent_size"]
            _vg_extent_count = vg_stuff["extent_count"]
            vg_info[vg_name] = (self._get_size_str(vg_stuff["size"]),
                                self._get_size_str(vg_stuff["free"]))
        lv_names = sorted(self.lv_dict.get("lv", {}).keys())
        lv_info = {}
        for lv_name in lv_names:
            lv_stuff = self.lv_dict.get("lv", {})[lv_name]
            vg_name = lv_stuff["vg_name"]
            lv_size = lv_stuff["size"]
            lv_info.setdefault(vg_name, []).append("{}{} ({})".format(
                lv_name,
                lv_stuff["attr"][5] == "o" and "[open]" or "",
                self._get_size_str(lv_size)))
            # print "*", lv_name, vg_stuff["name"], vg_extent_size, vg_extent_count, vg_size, lv_extents
        if short:
            ret_info = []
            for vg_name in vg_names:
                ret_info.append("{} ({}, {} free, {}: {})".format(
                    vg_name,
                    vg_info[vg_name][0],
                    vg_info[vg_name][1],
                    logging_tools.get_plural("LV", len(lv_info.get(vg_name, []))),
                    ", ".join(lv_info.get(vg_name, [])) or "NONE"))
            return "{}: {}".format(
                logging_tools.get_plural("VG", len(ret_info)),
                "; ".join(ret_info))
        else:
            ret_info = logging_tools.new_form_list()
            for vg_name in vg_names:
                ret_info.append([
                    logging_tools.form_entry("VG", header="type"),
                    logging_tools.form_entry(vg_name, header="name"),
                    logging_tools.form_entry_right(vg_info[vg_name][0], header="size"),
                    logging_tools.form_entry_right(vg_info[vg_name][1], header="free"),
                    logging_tools.form_entry("", header="options"),
                ])
                for lv_name in lv_names:
                    lv_stuff = self.lv_dict.get("lv", {})[lv_name]
                    if lv_stuff["vg_name"] == vg_name:
                        ret_info.append([
                            logging_tools.form_entry("  LV", header="type"),
                            logging_tools.form_entry(lv_name, header="name"),
                            logging_tools.form_entry_right(self._get_size_str(lv_stuff["size"]), header="size"),
                            logging_tools.form_entry(""),
                            logging_tools.form_entry(lv_stuff["attr"]),
                        ])
            return unicode(ret_info)

    def __repr__(self):
        order_list = ["pv", "vg", "lv"]
        ret_a = ["{}:".format(", ".join(["{}".format(logging_tools.get_plural(k, len(self.lv_dict.get(k, {}).keys()))) for k in order_list]))]
        for ol in order_list:
            ret_a.append("\n".join([str(x) for x in self.lv_dict.get(ol, {}).values()]))
        return "\n".join(ret_a)


class disk_lut(object):
    def __init__(self, **args):
        self.start_path = args.get("start_path", "/dev/disk")
        self.__rev_lut, self.__fw_lut, self.__lut = ({}, {}, {})
        if os.path.isdir(self.start_path):
            for top_entry in os.listdir(self.start_path):
                top_path = os.path.join(self.start_path, top_entry)
                cur_lut = self.__lut.setdefault(top_entry, {})
                if os.path.isdir(top_path):
                    for entry in os.listdir(top_path):
                        cur_path = os.path.join(top_path, entry)
                        if os.path.islink(cur_path):
                            target = os.path.normpath(os.path.join(top_path, os.readlink(cur_path)))
                            cur_lut[entry] = target
                            self.__fw_lut[cur_path] = target
                            self.__rev_lut.setdefault(target, []).append(cur_path)
        # pprint.pprint(self.__lut)
        # pprint.pprint(self.__fw_lut)
        # pprint.pprint(self.__rev_lut)

    def get_top_keys(self):
        return self.__lut.keys()

    def __getitem__(self, key):
        entry_type = None
        if isinstance(key, basestring):
            if key.startswith("by-"):
                return self.__lut[key]
            elif key.startswith("/dev/disk/by-"):
                return self.__fw_lut[key]
            else:
                return self.__rev_lut[key]
        else:
            return self.__lut[entry_type][key]


def test_it():
    my_lut = disk_lut()
    print my_lut[("id", "/dev/sda8")]
