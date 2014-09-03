# Copyright (C) 2008-2010,2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file belongs to the python-modules-base package
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
""" midleware layer for rrdtools """

from lxml import etree  # @UnresolvedImport
from lxml.builder import E
import subprocess
import logging_tools
import os
import re
import rrdtool  # @UnresolvedImport
import tempfile
import time


WS_RE = re.compile("^(?P<slot_num>\d+)\s*(?P<slot_type>\S+?)s*\s+for\s+(?P<total_num>\d+)\s*(?P<total_type>\S+?)s*$")


def _format_value(in_value):
    if in_value is None:
        return "NaN"
    elif type(in_value) in [int, long]:
        return "{:d}".format(in_value)
    else:
        return "{:.10e}".format(in_value)


def _parse_rrd_info(rrd_info):
    def get_key_list(in_key):
        ret_list = []
        for entry in in_key.split("."):
            if entry.count("["):
                first_key = entry.split("[")[0]
                second_key = entry.split("[")[1].split("]")[0]
                if second_key.isdigit():
                    second_key = int(second_key)
                ret_list.extend([first_key, second_key])
            else:
                ret_list.append(entry)
        return ret_list
    if "ds" in rrd_info:
        # old style, pass
        pass
    else:
        # reinterpret rrd-tool
        new_info = {}
        for key, value in rrd_info.iteritems():
            if key.count("["):
                key_list = get_key_list(key)
                sub_dict = new_info
                for sub_key in key_list[:-1]:
                    sub_dict = sub_dict.setdefault(sub_key, {})
                sub_dict[key_list[-1]] = value
            else:
                new_info[key] = value
        rrd_info = new_info
    return rrd_info


class RRA(object):
    def __init__(self, step, rra_entry, src_file, **kwargs):
        self.step = step
        self.src_file = src_file
        self.length = self.step * rra_entry["pdp_per_row"] * rra_entry["rows"]
        self.name = RRA.rra_name(rra_entry, self.step)
        self.pdp_per_row = rra_entry["pdp_per_row"]
        self.rows = rra_entry["rows"]
        self.cf = rra_entry["cf"]
        self.xff = rra_entry["xff"]
        self.cdp_prep = rra_entry["cdp_prep"]
        self.log_com = kwargs.get("log_com", None)
        # only use actual time if act_time is not specified
        # otherwise we would loose a lot of information
        act_time = kwargs.get("act_time", int(time.time()))
        if src_file:
            args = [
                src_file,
                self.cf,
                "-r", "{:d}".format(self.step * self.pdp_per_row),
                "-s", "{:d}".format(act_time - self.length),
                "-e", "{:d}".format(act_time),
            ]
            self.stream = rrdtool.fetch(*args)

            # print self.stream
        else:
            ref_rra = kwargs["ref_rra"]
            num_data = len(ref_rra.stream[1])
            self.stream = (
                (
                    int(act_time) - (self.pdp_per_row + 1) * self.step * self.rows,
                    int(act_time),
                    self.step * self.pdp_per_row
                ),
                ref_rra.stream[1],
                [tuple([None] * num_data)] * (self.rows + 1)
            )
        self._pad_stream()
        self.stream_info = self.stream[0]
        self.start_time = self.stream_info[0]
        self.end_time = self.stream_info[1]
        self.time_step = self.stream_info[2]

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        if self.log_com:
            self.log_com("[RRA] {}".format(what), log_level)
        else:
            print("[RRA {}] {}".format(logging_tools.get_log_level_str(log_level), what))

    @property
    def popcount(self):
        # count data rows where any /all of the data is not None
        _any, _all = (0, 0)
        for _vv in self.stream[2]:
            if any([_v is not None for _v in _vv]):
                _any += 1
            if all([_v is not None for _v in _vv]):
                _all += 1
        return len(self.stream[2]), _any, _all

    @staticmethod
    def create(**kwargs):
        ref_rra = kwargs["ref_rra"]
        if "step" in kwargs:
            return RRA(
                kwargs["step"],
                {
                    "rows": kwargs["rows"],
                    "cf": kwargs["cf"],
                    "xff": kwargs.get("xff", 0.5),
                    "pdp_per_row": kwargs["pdp"],
                    "cdp_prep": ref_rra.cdp_prep
                },
                src_file=None,
                ref_rra=ref_rra,
                act_time=kwargs.get("act_time", int(time.time())),
                log_com=kwargs.get("log_com", None),
            )
        else:
            # simple string-spec
            str_split = [int(value) if value.isdigit() else value for value in kwargs["string_spec"].split("-")]
            return RRA(
                str_split[4],
                {
                    "rows": str_split[3],
                    "cf": str_split[1],
                    "xff": kwargs.get("xff", 0.5),
                    "pdp_per_row": str_split[2],
                    "cdp_prep": ref_rra.cdp_prep
                },
                src_file=None,
                ref_rra=ref_rra
            )

    @staticmethod
    def total_width(rra_name):
        # return the total covered timeframe in seconds from rra-name
        _parts = rra_name.split("-")
        if _parts[0] == "RRA":
            return int(_parts[2]) * int(_parts[3]) * int(_parts[4])
        else:
            return int(_parts[0]) * int(_parts[1]) * int(_parts[2])

    @staticmethod
    def width(rra_name):
        # return the timeframe of a datapoint in seconds from rra-name
        _parts = rra_name.split("-")
        if _parts[0] == "RRA":
            return int(_parts[2]) * int(_parts[4])
        else:
            return int(_parts[0]) * int(_parts[2])

    @staticmethod
    def rra_name(rra_entry, step, short=False):
        _name = "{:d}-{:d}-{:d}".format(
            rra_entry["pdp_per_row"],
            rra_entry["rows"],
            step
        )
        if not short:
            _name = "RRA-{}-{}".format(
                rra_entry["cf"],
                _name,
            )
        return _name

    @staticmethod
    def fill_rra_name(short_name, full_name):
        return "{}-{}".format("-".join(full_name.split("-", 2)[0:2]), short_name)

    @staticmethod
    def parse_cf(in_str):
        return in_str.split("-")[1]

    @staticmethod
    def parse_width_str(in_str, step=60):
        _res_dict = None
        # returns
        # - slot width in seconds
        # - total width in seconds
        # - number of slots
        # - primary datapoints needed
        _cm = WS_RE.match(in_str)
        if _cm:
            _lut = {
                "min": 60,
                "minute": 60,
                "hour": 3600,
                "day": 24 * 3600,
                "week": 24 * 3600 * 7,
                "month": 24 * 3600 * 31,
                "year": 24 * 3600 * 366,
            }
            slot_width = int(_cm.group("slot_num")) * _lut.get(_cm.group("slot_type"), 0)
            total_width = int(_cm.group("total_num")) * _lut.get(_cm.group("total_type"), 0)
            if slot_width and total_width:
                num_rows = total_width / slot_width
                total_width = num_rows * slot_width
                num_pdp = slot_width / step
                if num_pdp:
                    _res_dict = {
                        "width": slot_width,
                        "total": total_width,
                        "rows": num_rows,
                        "pdp": num_pdp,
                        "name": "{:d}-{:d}-{:d}".format(
                            num_pdp,
                            num_rows,
                            step,
                        )
                    }
        return _res_dict

    def check_slot_mismatch(self, ignore_error):
        if self.pdp_per_row * self.step != self.stream_info[2]:
            print "%s, reported step differs from expected vor rra %s (file %s): %d != %d" % (" +++ Warn" if ignore_error else " *** Error",
                                                                                              self.name,
                                                                                              self.src_file,
                                                                                              self.pdp_per_row * self.step,
                                                                                              self.stream_info[2])
            slot_ok = ignore_error
        else:
            slot_ok = True
        return slot_ok

    def _pad_stream(self):
        if len(self.stream[2]) != self.rows + 1:
            num_miss = self.rows + 1 - len(self.stream[2])
            none_tuple = tuple([None] * len(self.stream[2][0]))
            self.log("+++ padding stream with {:d} none-tuples {} to {:d} entries".format(num_miss, str(none_tuple), self.rows))
            self.stream = (
                (
                    self.stream[0][0] - (num_miss * self.stream[0][2]),
                    self.stream[0][1],
                    self.stream[0][2]),
                self.stream[1],
                [none_tuple] * num_miss + self.stream[2]
            )

    def show_info(self):
        return "{:<30s} : CF {:<10s}, {:6d} rows, {:4d} pdp ({:12s}), length is {:18s}".format(
            self.name,
            self.cf,
            self.rows,
            self.pdp_per_row,
            logging_tools.get_diff_time_str(self.pdp_per_row * self.step),
            logging_tools.get_diff_time_str(self.length),
        )

    def xml(self):
        ds_list = self.stream[1]
        rra_stream = self.stream
        if len(rra_stream[2]) < 10:
            print self.name
            print rra_stream
        if rra_stream[0][2] == 0:
            print("empty step size")
            return None
        _res_xml = E.rra(
            E.cf(self.cf),
            E.pdp_per_row(_format_value(self.pdp_per_row)),
            E.params(
                E.xff(_format_value(self.xff))
            ),
            E.cdp_prep(
                *[
                    E.ds(
                        E.primary_value(_format_value(prim_value)),
                        E.secondary_value("NaN"),
                        E.value(_format_value(self.cdp_prep[ds_struct]["value"])),
                        E.unknown_datapoints(_format_value(self.cdp_prep[ds_struct]["unknown_datapoints"])),
                    ) for _ds_name, ds_struct, prim_value in zip(ds_list, self.cdp_prep, rra_stream[2][-4])
                ]
            ),
            E.database(
                *[
                    E.row(
                        *[
                            E.v(_format_value(value)) for value in values
                        ]
                    ) for _act_time, values in zip(range(*rra_stream[0]), rra_stream[2])[:-1]
                ]
            )
        )
        return _res_xml

    def get_val_tuple(self, tuple_time):
        my_tuple = (None,) * len(self.stream[2][0])
        s_idx = int((tuple_time - self.start_time) / self.time_step)
        if s_idx >= 0:
            # time difference between tuple at s_idx and tuple_time
            it_time = tuple_time - (s_idx * self.time_step + self.start_time)
            if s_idx < len(self.stream[2]):
                my_tuple = self.stream[2][s_idx]
                if it_time > 0:
                    # no exact match
                    if s_idx + 1 < len(self.stream[2]):
                        next_tuple = self.stream[2][s_idx + 1]
                        f1 = it_time / float(self.time_step)
                        f0 = 1. - f1
                        my_tuple = tuple(
                            [
                                f0 * left_value + f1 * right_value if (
                                    left_value is not None and right_value is not None
                                ) else None for left_value, right_value in zip(list(my_tuple), list(next_tuple))
                            ]
                        )
                elif it_time == 0:
                    my_tuple = tuple(
                        [
                            left_value or None for left_value in my_tuple
                        ]
                    )
        return my_tuple

    def fit_data(self, other_rras):
        # this is the first idx from the other stream, mapped to our system
        _checked, _changed = (0, 0)
        _debug = False  # self.name=="RRA-MAX-288-500-300" and other_rra.name=="RRA-MAX-1-600-300"
        for other_rra in other_rras:
            other_s_idx = self.rows - (other_rra.end_time - other_rra.start_time) / self.time_step + 1
            idx_offset = other_s_idx if other_s_idx > 0 else 0
            for s_idx, val_tuple in enumerate(self.stream[2][idx_offset:]):
                _checked += 1
                if None in val_tuple:
                    tuple_time = (s_idx + idx_offset) * self.time_step + self.start_time
                    other_val_tuple = other_rra.get_val_tuple(tuple_time)
                    real_tuple = tuple([my_val if my_val is not None else other_val for my_val, other_val in zip(list(val_tuple), list(other_val_tuple))])
                    # print s_idx, real_tuple, val_tuple
                    if real_tuple != val_tuple:
                        _changed += 1
                        self.stream[2][idx_offset + s_idx] = real_tuple
        if _changed or _debug:
            self.log(
                "Copying from {} to {}, checked {:d}, changed {:d} (stream_len is {:d})".format(
                    ", ".join([other_rra.name.split("-", 2)[2] for other_rra in other_rras]),
                    self.name,
                    _checked,
                    _changed,
                    len(self.stream[2]),
                )
            )
        return True if _changed else False

    def check_values(self, cap_to_none, min_value, max_value):
        new_stream = []
        changed = 0
        for data in self.stream[2]:
            new_data = []
            for val in list(data):
                if val is not None:
                    if val < min_value:
                        val = None if cap_to_none else min_value
                        changed += 1
                    if val > max_value:
                        val = None if cap_to_none else max_value
                        changed += 1
                new_data.append(val)
            new_stream.append(tuple(new_data))
        self.stream = [self.stream[0], self.stream[1], new_stream]
        return changed


class RRD(dict):
    def __init__(self, f_name, **kwargs):
        dict.__init__(self)
        self.__ignore_slot_mismatch = kwargs.get("ignore_slot_mismatch", False)
        self.file_name = f_name
        self.__rras_built = False
        self.__build_rras = kwargs.get("build_rras", False)
        self.log_com = kwargs.get("log_com", None)
        first_bytes = file(self.file_name, "rb").read(8)
        _verbose = kwargs.get("verbose", False)
        if first_bytes[0:3] == "RRD":
            if _verbose:
                self.log("Reading RRA-file from {}".format(self.file_name))
            self._parse_raw()
        else:
            if _verbose:
                self.log("Reading Dump-file from {}".format(self.file_name))
            self._parse_dump()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        if self.log_com:
            self.log_com("[RRD] {}".format(what), log_level)
        else:
            if log_level > logging_tools.LOG_LEVEL_WARN:
                print "**** [RRD, {}] {}".format(logging_tools.get_log_level_str(log_level), what)

    def add_rra(self, new_rra):
        self["rra_list"].append(new_rra.name)
        self["rra_names"].append(new_rra.name)
        self["rra_short_names"].append(new_rra.name.split("-", 2)[2])
        self["rra_dict"][new_rra.name] = new_rra

    def remove_rra(self, rra_name):
        self["rra_list"].remove(rra_name)
        self["rra_names"].remove(rra_name)
        self["rra_short_names"].remove(rra_name.split("-", 2)[2])
        # if rra_name in self["rra_dict"]:
        del self["rra_dict"][rra_name]

    def _parse_raw(self):
        self["raw"] = rrdtool.info(self.file_name)
        self.update(_parse_rrd_info(self["raw"]))
        # rra_list: list of builded rras
        # rra_names: list of rras (always set)
        self["rra_list"] = []
        self["rra_dict"] = {}
        # pprint.pprint(self["raw"])
        # pprint.pprint(self["rra"])
        self["rra_names"] = []
        self["rra_short_names"] = []
        for _new_name, _new_short_name in [
            (
                RRA.rra_name(_value, self["step"]),
                RRA.rra_name(_value, self["step"], short=True)
            ) for _value in self["rra"].itervalues()
        ]:
            if _new_name not in self["rra_names"]:
                self["rra_names"].append(_new_name)
                self["rra_short_names"].append(_new_short_name)
        if self.__build_rras:
            self.build_rras()

    def build_rras(self):
        if not self.__rras_built:
            self.__rras_built = True
            for _rra_idx, rra_entry in self["rra"].iteritems():
                # print rra_entry
                _new_name = RRA.rra_name(rra_entry, self["step"])
                if _new_name not in self["rra_list"]:

                    new_rra = RRA(self["step"], rra_entry, self.file_name, act_time=self["last_update"])
                    # if new_rra.check_slot_mismatch(self.__ignore_slot_mismatch):
                    self["rra_list"].append(new_rra.name)
                    self["rra_dict"][new_rra.name] = new_rra
                else:
                    # print self["rra_dict"][new_rra.name].popcount, new_rra.popcount
                    self.log("RRA name {} already used".format(_new_name), logging_tools.LOG_LEVEL_ERROR)

    def find_best_match(self, rra_name, **args):
        rra_parts = rra_name.split("-")
        rra_parts.pop(0)
        rra_parts = [int(part) if part.isdigit() else part for part in rra_parts]
        if len(rra_parts) == 4:
            s_cf, s_pdps, s_rows, _s_steps = rra_parts
        else:
            s_cf, s_pdps, s_rows = rra_parts
            # s_steps = 300
        # s_length = s_steps * s_rows * s_pdps
        take_name, take_rows = ("", 0)
        cf_matches = [key for key, stuff in self["rra_dict"].iteritems() if stuff.cf == s_cf]
        if not cf_matches and "default_cf" in args:
            use_default_cf = True
        else:
            use_default_cf = False
        for rra_name, stuff in self["rra_dict"].iteritems():
            # print s_steps, stuff["step"], stuff
            if stuff.cf == s_cf or (use_default_cf and stuff.cf == args["default_cf"]):
                # must match consolidation function
                if stuff.pdp_per_row == s_pdps:
                    # pdps match, take it
                    if not take_name:
                        take_name, take_rows = (rra_name, stuff.rows)
                    else:
                        take_new = stuff.rows > take_rows
                        print "**** %s another match for pdps, target_rows is %d, previous match has %d rows, actual has %d rows" % ("using" if take_new else "found",
                                                                                                                                     s_rows,
                                                                                                                                     take_rows,
                                                                                                                                     stuff.rows)
                        if take_new:
                            take_name, take_rows = (rra_name, stuff.rows)
        if not take_name:
            # search for
            for cf_match in cf_matches:
                stuff = self["rra_dict"][cf_match]
                pdp_fac = int(stuff.pdp_per_row / s_pdps)
                if pdp_fac * s_pdps == stuff.pdp_per_row and not take_name:
                    print " +++ taking suboptimal RRA, pdp_factor is %d" % (pdp_fac)
                    take_name = cf_match
        return take_name

    def merge_object(self, merge_obj):
        for rra in self["rra_list"]:
            if rra in merge_obj["rra_list"]:
                print "   merging RRA %s ..." % (rra)
                my_rra = self["rra_dict"][rra]
                other_rra = merge_obj["rra_dict"][rra]
                if my_rra.stream[0] != other_rra.stream[0]:
                    print "      Timeinfo of both streams differ: %s != %s" % (str(my_rra.stream[0]),
                                                                               str(other_rra.stream[0]))
                else:
                    merged_stream, num_merged = ([], 0)
                    for my_vals, other_vals in zip(my_rra.stream[2], other_rra.stream[2]):
                        new_vals = []
                        for my_val, other_val in zip(my_vals, other_vals):
                            if my_val is None:
                                if other_val is None:
                                    pass
                                else:
                                    num_merged += 1
                                    my_val = other_val
                            else:
                                if other_val is None:
                                    pass
                                elif other_val > my_val:
                                    num_merged += 1
                                    my_val = other_val
                            new_vals.append(my_val)
                        merged_stream.append(tuple(new_vals))
                    print "      took %s from merge_stream" % (logging_tools.get_plural("value", num_merged))
                    my_rra.stream = (my_rra.stream[0], my_rra.stream[1], merged_stream)
            else:
                print " *** RRA %s not present in merge_obj" % (rra)

    def copy_inline(self):
        print "  Filling data from one rra with values from other rras"
        changed = False
        all_rras = self["rra_list"]
        rra_structs = [self["rra_dict"][key] for key in all_rras]
        cf_dict = dict([(cf, []) for cf in set([rra.cf for rra in rra_structs])])
        for key in cf_dict.iterkeys():
            sort_keys = sorted([(value.pdp_per_row, -value.rows, value.name) for value in rra_structs if value.cf == key])
            # cf_rras is now a list of rras with the correct cf, sorted so that the rras
            #   with the finest granularity come first (and we prefer longer rras)
            cf_rras = [self["rra_dict"][s_key[2]] for s_key in sort_keys]
            for rra_idx, rra in enumerate(cf_rras):
                other_idxs = [idx for idx in range(len(cf_rras)) if idx != rra_idx]
                for other_idx in other_idxs:
                    # print "copy from %s to %s" % (cf_rras[other_idx].name,
                    #                              rra.name)
                    if rra.copy_from_rra(cf_rras[other_idx]):
                        changed = True
        return changed

    def copy_object(self, copy_obj, s_time, e_time):
        # all data from copy_obj gets copied to actual rra between s_time and e_time
        for rra in self["rra_list"]:
            if rra in copy_obj["rra_list"]:
                rra_to_take = rra
            else:
                rra_to_take = copy_obj.find_best_match(rra)
            if rra_to_take:
                print "   merging RRA %s with %s from copy_obj ..." % (rra, rra_to_take)
                self.copy_rra_object(copy_obj, rra, rra_to_take, s_time, e_time)
            else:
                print " *** RRA %s not present in copy_obj and no best_match found" % (rra)

    def check_values(self, cap_to_none, min_value, max_value):
        tot_changed = 0
        for rra in self["rra_list"]:
            tot_changed += self["rra_dict"][rra].check_values(cap_to_none, min_value, max_value)
        return tot_changed

    def copy_rra_object(self, copy_obj, self_rra, rra_to_take, s_time, e_time, **args):
        success = True
        my_rra = self["rra_dict"][self_rra]
        other_rra = copy_obj["rra_dict"][rra_to_take]
        stream_s_time, stream_e_time, time_step = my_rra.stream[0]
        if e_time < stream_s_time or s_time > stream_e_time:
            # time out of range
                # print e_time, stream_s_time, s_time, stream_e_time
            print "    time_range for copying out of stream_range"
        else:
            copy_stream = True
            real_source_stream = other_rra.stream
            if my_rra.stream[0] != other_rra.stream[0]:
                print "      Timeinfo of both streams differ: %s != %s" % (str(my_rra.stream[0]),
                                                                           str(other_rra.stream[0]))
                # self._show_stream_info(my_rra.stream)
                # self._show_stream_info(other_rra.stream)
                if my_rra.stream[0][2] != other_rra.stream[0][2]:
                    fac = int(other_rra.stream[0][2] / my_rra.stream[0][2])
                    rev_fac = int(my_rra.stream[0][2] / other_rra.stream[0][2])
                    if fac * my_rra.stream[0][2] == other_rra.stream[0][2]:
                        # stretching other_stream by fac
                        print " ++++ stretching source stream by %d" % (fac)
                        src_info = other_rra.stream[0]
                        new_stream = sum([[val] * fac for val in other_rra.stream[2]], [])
                        # new stream info
                        new_src_info = (src_info[1] - src_info[2] / fac * len(new_stream), src_info[1], src_info[2] / fac)
                        real_source_stream = (new_src_info, other_rra.stream[1], new_stream)
                    elif rev_fac * other_rra.stream[0][2] == my_rra.stream[0][2]:
                        print " ++++ compressing source_stream by %d" % (rev_fac)
                        src_info = other_rra.stream[0]
                        new_stream = []
                        tuple_size = len(other_rra.stream[2][0])
                        act_idx, num_data, sum_tuple = (0, [0] * tuple_size, [0.] * tuple_size)
                        for in_tuple in other_rra.stream[2]:
                            for add_idx, in_v in enumerate(list(in_tuple)):
                                if in_v is not None:
                                    sum_tuple[add_idx] += in_v
                                    num_data[add_idx] += 1
                            act_idx += 1
                            if act_idx == rev_fac:
                                sum_tuple = tuple([val / num_dat if num_dat else 0. for val, num_dat in zip(sum_tuple, num_data)])
                                new_stream.append(sum_tuple)
                                act_idx, num_data, sum_tuple = (0, [0] * tuple_size, [0.] * tuple_size)
                        # new stream info
                        new_src_info = (src_info[1] - src_info[2] * rev_fac * len(new_stream), src_info[1], src_info[2] * rev_fac)
                        real_source_stream = (new_src_info, other_rra.stream[1], new_stream)
                        self._show_stream_info(other_rra.stream)
                if my_rra.stream[0][2] != other_rra.stream[0][2]:
                    print " *** effective steps differ, error, skipping stream", my_rra.stream[0][2], other_rra.stream[0][2], self["step"], copy_obj["step"]
                    copy_stream = False
                else:
                    # extend or shorten other stream
                    my_stream_len, other_stream_len = (len(my_rra.stream[2]),
                                                       len(other_rra.stream[2]))
                    diff_len = abs(my_stream_len - other_stream_len)
                    if my_stream_len == other_stream_len:
                        # exakt match
                        sub_stream = other_rra.stream[2]
                    elif my_stream_len < other_stream_len:
                        print "      removing %s from copy_stream" % (logging_tools.get_plural("entry", diff_len))
                        sub_stream = other_rra.stream[2][diff_len:]
                    else:
                        num_vals = len(my_rra.stream[2][0])
                        print "      padding copy_stream with %s" % (logging_tools.get_plural("entry", diff_len))
                        sub_stream = [tuple([None] * num_vals)] * diff_len + other_rra.stream[2]
                    real_source_stream = (other_rra.stream[0], other_rra.stream[1], sub_stream)
                    # copy_stream = False
            none_tuple = tuple([None] * len(my_rra.stream[2][0]))
            if copy_stream:
                # print s_time, e_time, my_rra.stream[0]
                # print (stream_e_time - stream_s_time) / time_step, len(my_rra.stream[2])
                trans_dict = {}
                if my_rra.stream[1] != real_source_stream[1]:
                    if len(my_rra.stream[1]) != len(real_source_stream[1]):
                        if my_rra.stream[1] in args.get("row_mapping", {}):
                            trans_dict = args["row_mapping"][my_rra.stream[1]]
                        else:
                            print "row_format differs, ERROR (%s != %s)" % (str(my_rra.stream[1]),
                                                                            str(real_source_stream[1]))
                            success = False
                    else:
                        try:
                            trans_dict = dict([(my_rra.stream[1].index(key), real_source_stream[1].index(key)) for key in my_rra.stream[1]])
                        except (KeyError, ValueError):
                            if my_rra.stream[1] in args.get("row_mapping", {}):
                                trans_dict = args["row_mapping"][my_rra.stream[1]]
                            else:
                                print "row_names differ, ERROR (%s != %s)" % (str(my_rra.stream[1]),
                                                                              str(real_source_stream[1]))
                                success = False
            if copy_stream and success:
                merged_stream, num_copied = ([], 0)
                for diff_time, my_vals, other_vals in zip(xrange(len(my_rra.stream[2])), my_rra.stream[2], real_source_stream[2]):
                    act_time = stream_s_time + time_step * diff_time
                    if act_time > s_time and act_time < e_time:
                        # copy
                        if trans_dict:
                            if len(other_vals) < len(my_vals):
                                # pad if necessary
                                other_vals = tuple(list(other_vals) + [None] * (len(my_vals) - len(other_vals)))
                            other_vals = tuple([other_vals[trans_dict[idx]] for idx in xrange(len(other_vals))])
                        if my_vals != none_tuple and args.get("overwrite_if_unknown", False):
                            merged_stream.append(my_vals)
                        else:
                            merged_stream.append(other_vals)
                            num_copied += 1
                        # print my_vals, other_vals, merged_stream[-1]
                    else:
                        merged_stream.append(my_vals)
                print "      took %s from copy_stream, resulting stream has %s" % (logging_tools.get_plural("value", num_copied),
                                                                                   logging_tools.get_plural("value", len(merged_stream)))
                my_rra.stream = (my_rra.stream[0], my_rra.stream[1], merged_stream)
        return success

    def xml(self):
        # self.log("Writing RRD-file to {}".format(file_name))
        # generate dump-file
        _xml = E.rrd(
            E.version(self["rrd_version"]),
            E.step(_format_value(self["step"])),
            E.lastupdate(_format_value(self["last_update"])),
            *[
                # data sources
                E.ds(
                    E.name(ds_struct["ds_name"] if "ds_name" in ds_struct else ds_name),
                    E.type(ds_struct["type"]),
                    E.minimal_heartbeat(_format_value(ds_struct["minimal_heartbeat"])),
                    E.min(_format_value(ds_struct["min"])),
                    E.max(_format_value(ds_struct.get("max", None))),
                    E.last_ds(ds_struct["last_ds"]),
                    E.value(_format_value(ds_struct["value"])),
                    E.unknown_sec(_format_value(ds_struct["unknown_sec"])),
                ) for ds_name, ds_struct in [(_ds_name, self["ds"][_ds_name]) for _ds_name in self["rra_dict"].values()[0].stream[1]]
            ] + [
                # rra databases
                self["rra_dict"][rra_name].xml() for rra_name in self["rra_list"]
            ]
        )
        return _xml

    def content(self):
        with tempfile.NamedTemporaryFile(delete=False) as _xmlfile:
            with tempfile.NamedTemporaryFile(delete=False) as _rrdfile:
                _xmlfile.write(etree.tostring(self.xml()))
                _xmlfile.close()
                os.unlink(_rrdfile.name)
                args = [
                    "/opt/cluster/bin/rrdtool",
                    "restore",
                    _xmlfile.name,
                    _rrdfile.name,
                    "-r"
                ]
                _stat = subprocess.call(args)
                _content = file(_rrdfile.name, "rb").read()
                os.unlink(_xmlfile.name)
                os.unlink(_rrdfile.name)
        return _content

    def show_info(self, **args):
        if args.get("full_info", False):
            print(
                "{}:".format(
                    logging_tools.get_plural("RRA", len(self["rra_list"]))
                )
            )
            for rra_key in sorted(self["rra_list"]):
                print(
                    self["rra_dict"][rra_key].show_info()
                )
        else:
            print(
                "{}: {}".format(
                    logging_tools.get_plural("RRA", len(self["rra_list"])),
                    ", ".join(sorted(self["rra_list"]))
                )
            )
