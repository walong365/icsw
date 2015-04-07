# Copyright (C) 2007-2009,2013-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file belongs to the rrd-server package
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
""" grapher part of rrd-grapher service """

from django.conf import settings
from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models import device, rms_job_run, cluster_timezone, MachineVector, \
    MVStructEntry, MVValueEntry
from initat.rrd_grapher.config import global_config
from lxml import etree  # @UnresolvedImport
from lxml.builder import E  # @UnresolvedImport
import copy
import datetime
import dateutil.parser
import logging_tools
import os
import pprint  # @UnusedImport
import process_tools
import re
import rrdtool  # @UnresolvedImport
import select
import server_command
import json
import server_mixins
import socket
import stat
import threading_tools
import time
import uuid

FLOAT_FMT = "{:.6f}"


def full_graph_key(*args):
    # create a string representation
    if type(args[0]) == tuple:
        s_key, v_key = args[0]
    elif type(args[0]) == dict:
        s_key, v_key = (args[0]["struct_key"], args[0]["value_key"])
    else:
        s_key, v_key = args
    return "{}{}".format(
        s_key,
        ".{}".format(
            v_key
        ) if v_key else ""
    )


def rrd_escape(in_str):
    return in_str.replace(":", "\:")


def strftime(in_dt, comp_dt=None):
    if comp_dt is None:
        now = datetime.datetime.now()
        if now.year == in_dt.year:
            return cluster_timezone.normalize(in_dt).strftime("%d. %b, %H:%M:%S")
        else:
            return cluster_timezone.normalize(in_dt).strftime("%d. %b %Y, %H:%M:%S")
    else:
        if comp_dt.year == in_dt.year:
            if comp_dt.month == in_dt.month and comp_dt.day == in_dt.day:
                return cluster_timezone.normalize(in_dt).strftime("%H:%m:%S")
            else:
                return cluster_timezone.normalize(in_dt).strftime("%d. %b, %H:%M:%S")
        else:
            return cluster_timezone.normalize(in_dt).strftime("%d. %b %Y, %H:%M:%S")


class SimpleColorTable(object):
    def __init__(self, entries):
        self.__entries = entries
        self.__idx = 0

    @property
    def color(self):
        _col = self.__entries[self.__idx]
        self.__idx += 1
        if self.__idx == len(self.__entries):
            self.__idx = 0
        return _col


class Colorizer(object):
    def __init__(self, log_com):
        self.log_com = log_com
        self.def_color_table = "dark28"
        self._gc_base = global_config["GRAPHCONFIG_BASE"]
        if not os.path.isdir(self._gc_base):
            # not defined, set old value
            self._gc_base = "/opt/cluster/share"
        self._read_files()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.log_com("[col] {}".format(what), log_level)

    def _read_files(self):
        _ct_file = os.path.join(self._gc_base, "color_tables.xml")
        _cr_file = os.path.join(self._gc_base, "color_rules.xml")
        self.colortables = etree.fromstring(file(_ct_file, "r").read())  # @UndefinedVariable
        self.color_tables = {}
        for c_table in self.colortables.findall(".//colortable[@name]"):
            self.color_tables[c_table.get("name")] = ["#{:s}".format(color.get("rgb")) for color in c_table if self._check_color(color)]
        self.log("read colortables from {}".format(_ct_file))
        self.color_rules = etree.fromstring(file(_cr_file, "r").read())  # @UndefinedVariable
        self.log("read colorrules from {}".format(_cr_file))
        self.match_re_keys = [
            (
                re.compile(
                    "^{}".format(
                        entry.attrib["key"].replace(".", r"\.")
                    )
                ),
                entry
            ) for entry in self.color_rules.xpath(".//entry[@key]", smart_strings=False)
        ]
        # fast lookup table, store computed lookups
        self.fast_lut = {}

    def _check_color(self, color):
        cur_c = "#{}".format(color.get("rgb"))
        return (int(cur_c[1:3], 16) + int(cur_c[3:5], 16) + int(cur_c[5:7], 16)) < 3 * 224

    def reset(self):
        # reset values for next graph
        self.table_offset = {}

    def simple_color_table(self, name):
        if name in self.color_tables:
            return SimpleColorTable(self.color_tables[name])
        else:
            return SimpleColorTable(self.color_tables[self.color_tables.keys()[0]])

    def get_color_and_style(self, mvs_entry, mvv_entry):
        if hasattr(mvv_entry, "color"):
            # specified in entry
            _clr = getattr(mvv_entry, "color")
            s_dict = {}
            for _attr in["draw_type", "invert"]:
                if hasattr(mvv_entry, _attr):
                    s_dict[_attr] = getattr(mvv_entry, _attr)
        else:
            t_name, s_dict = self.get_table_name(mvs_entry, mvv_entry)
            if t_name not in self.table_offset:
                self.table_offset[t_name] = 0
            self.table_offset[t_name] += 1
            if self.table_offset[t_name] == len(self.color_tables[t_name]):
                self.table_offset[t_name] = 0
            _clr = self.color_tables[t_name][self.table_offset[t_name]]
            if "transparency" in s_dict:
                _clr = "{}{:02x}".format(_clr, int(s_dict["transparency"]))
        return _clr, s_dict

    def get_table_name(self, mvs_entry, mvv_entry):
        s_dict = {}
        key_name = full_graph_key(mvs_entry.key, mvv_entry.key)
        # print "* key for get_table_name(): ", key_name
        # already cached in fast_lut ?
        if key_name not in self.fast_lut:
            # no, iterate over files
            for c_re, c_entry in self.match_re_keys:
                if c_re.match(key_name):
                    self.fast_lut[key_name] = c_entry
        t_name = self.def_color_table
        if key_name in self.fast_lut:
            c_xml = self.fast_lut[key_name]
            if c_xml.find(".//range[@colortable]") is not None:
                t_name = c_xml.find(".//range[@colortable]").get("colortable")
            for modify_xml in c_xml.findall("modify"):
                if re.match(modify_xml.get("key_match"), key_name):
                    s_dict[modify_xml.attrib["attribute"]] = modify_xml.attrib["value"]
        return t_name, s_dict


class GraphVar(object):
    def __init__(self, rrd_graph, graph_target, mvs_entry, mvv_entry, key, dev_name=""):
        # print key, mvs_entry, mvv_entry
        # mvs / mvv entry
        self.mvs_entry = mvs_entry
        self.mvv_entry = mvv_entry
        # graph key (load.1)
        self.key = key
        # device name
        self.dev_name = dev_name
        self.rrd_graph = rrd_graph
        self.graph_target = graph_target
        if self.rrd_graph.para_dict["show_values"]:
            self.max_info_width = max(2, 60 + int((self.rrd_graph.width - 800) / 8))
        else:
            self.max_info_width = self.rrd_graph.width / 7
        self.name = "v{:d}".format(self.graph_target.get_def_idx())

    def __getitem__(self, key):
        return self.entry.attrib[key]

    def __contains__(self, key):
        return key in self.entry.attrib

    def get(self, key, default):
        return self.entry.attrib.get(key, default)

    def info(self, timeshift, forecast):
        info = self.mvv_entry.info
        parts = full_graph_key(self.mvs_entry.key, self.mvv_entry.key).split(".")
        for idx in xrange(len(parts)):
            info = info.replace("${:d}".format(idx + 1), parts[idx])
        info_parts = []
        if self.dev_name:
            info_parts.append(unicode(self.dev_name))
        if timeshift:
            info_parts.append("ts {}".format(logging_tools.get_diff_time_str(timeshift)))
        if forecast:
            info_parts.append("fc")
        return rrd_escape(
            "{}{}".format(
                info,
                " ({})".format(", ".join(info_parts)) if info_parts else "",
            )
        )

    def get_color_and_style(self):
        self.color, self.style_dict = self.rrd_graph.colorizer.get_color_and_style(self.mvs_entry, self.mvv_entry)

    @property
    def create_total(self):
        if self.mvs_entry is not None:
            return True if self.mvv_entry.unit.endswith("/s") else False
        else:
            return True

    def graph_def(self, unique_id, **kwargs):
        # unique_id = device pk
        timeshift = kwargs.get("timeshift", 0)
        self.get_color_and_style()
        src_cf = "AVERAGE"
        if self.mvs_entry.se_type in ["pde", "mvl"]:
            # pde entry
            _src_str = "{}:{}:{}".format(self.mvs_entry.file_name, self.mvv_entry.key, src_cf)
        else:
            # machvector entry
            _src_str = "{}:v:{}".format(self.mvs_entry.file_name, src_cf)
        c_lines = [
            "DEF:{}={}".format(self.name, _src_str)
        ]
        if int(self.style_dict.get("invert", "0")):
            c_lines.append(
                "CDEF:{}inv={},-1,*".format(self.name, self.name),
            )
            draw_name = "{}inv".format(self.name)
        else:
            draw_name = self.name
        # if timeshift:
        #    c_lines.append("SHIFT:{}:{:d}".format(draw_name, timeshift))
        draw_type = self.style_dict.get("draw_type", "LINE1")
        _stacked = draw_type.endswith("STACK")
        if _stacked:
            draw_type = draw_type[:-5]
        # plot forecast ?
        if draw_type.startswith("LINE") or (draw_type.startswith("AREA") and not _stacked):
            show_forecast = self.rrd_graph.para_dict["show_forecast"]
        else:
            show_forecast = False
        # area: modes area (pure are), area{1,2,3} (area with lines)
        # print draw_name, draw_type, _stacked
        if draw_type.startswith("AREA"):  # in ["AREA", "AREA1", "AREA2", "AREA3"]:
            # support area with outline style
            c_lines.append(
                "{}:{}{}:<tt>{}</tt>{}".format(
                    "AREA",
                    draw_name,
                    self.color,
                    ("{{:<{:d}s}}".format(self.max_info_width)).format(self.info(timeshift, show_forecast))[:self.max_info_width],
                    ":STACK" if _stacked else "",
                ),
            )
            if draw_type != "AREA":
                if _stacked:
                    # arealine draw_name
                    c_lines.append(
                        "CDEF:{}zero={},0,*".format(self.name, self.name),
                    )
                    al_dn = "{}zero".format(self.name)
                else:
                    al_dn = draw_name
                c_lines.append(
                    "{}:{}{}:{}".format(
                        draw_type.replace("AREA", "LINE"),
                        al_dn,
                        "#000000",
                        ":STACK" if _stacked else "",
                    )
                )
        else:
            c_lines.append(
                "{}:{}{}:<tt>{}</tt>{}".format(
                    draw_type,
                    draw_name,
                    self.color,
                    (
                        "{{:<{:d}s}}".format(self.max_info_width)
                    ).format(self.info(timeshift, show_forecast))[:self.max_info_width],
                    ":STACK" if _stacked else "",
                ),
            )
            # c_lines.append(
            #    "CDEF:{}trend={},1800,TRENDNAN".format(
            #        self.name,
            #        self.name,
            #    )
            # )
        if show_forecast:
            c_lines.extend(
                [
                    "VDEF:{0}dl={0},LSLSLOPE".format(
                        draw_name,
                    ),
                    "VDEF:{0}kl={0},LSLINT".format(
                        draw_name,
                    ),
                    "CDEF:{0}lsls={0},POP,{0}dl,COUNT,*,{0}kl,+".format(
                        draw_name,
                    ),
                    "{}:{}lsls{}".format(
                        draw_type.replace("AREA", "LINE"),
                        draw_name,
                        self.color,
                    ),
                ],
            )
        if timeshift:
            # draw timeshifted graph
            ts_name = "{}ts".format(draw_name)
            ts_draw_type = draw_type.replace("AREA", "LINE")
            if draw_type != ts_draw_type:
                ts_color = "#000000"
            else:
                ts_color = self.color
            c_lines.extend(
                [
                    "DEF:{}={}:start={:d}:end={:d}".format(
                        ts_name,
                        _src_str,
                        self.rrd_graph.abs_start_time - timeshift,
                        self.rrd_graph.abs_end_time - timeshift,
                    ),
                    "CDEF:{}inv={},{:d},*".format(ts_name, ts_name, -1 if int(self.style_dict.get("invert", "0")) else 1),
                    "SHIFT:{}inv:{:d}".format(
                        ts_name,
                        timeshift,
                    ),
                    # "{}:{}inv{}40".format(
                    #    "LINE3",
                    #    ts_name,
                    #    self.color,
                    # ),
                    "{}:{}inv{}::dashes".format(
                        ts_draw_type,  # "LINE1",  # ts_draw_type,
                        ts_name,
                        ts_color,  # "#000000",  # ts_color,
                    )
                ]
            )
        # legend list
        l_list = self.get_legend_list()
        _unit = self.mvv_entry.unit.replace("%", "%%")
        # simplify some units
        _unit = {"1": ""}.get(_unit, _unit)
        _sum_unit = _unit
        if _sum_unit.endswith("/s"):
            _sum_unit = _sum_unit[:-2]
            if _sum_unit == "1":
                _sum_unit = ""
        if self.rrd_graph.para_dict["show_values"]:
            c_lines.append(
                "COMMENT:<tt>{}</tt>".format(
                    "{:>4s}".format(
                        _unit.replace("%%", "%")
                    ),
                )
            )
        for _num, (rep_name, cf, total) in enumerate(l_list):
            _last = _num == len(l_list) - 1
            c_lines.extend(
                [
                    "VDEF:{}{}={},{}".format(self.name, rep_name, self.name, cf),
                    # "VDEF:{}{}2={},{}".format(self.name, rep_name, self.name, cf),
                    # use 3 dots to separate struct from value key, oh boy ...
                    "PRINT:{}{}:{:d}.{}...{}.{}=%.4lf".format(
                        self.name,
                        rep_name,
                        unique_id,
                        rrd_escape(self.mvs_entry.key),
                        rrd_escape(self.mvv_entry.key),
                        cf,
                    ),
                ]
            )
            if self.rrd_graph.para_dict["show_values"]:
                c_lines.extend(
                    [
                        "GPRINT:{}{}:<tt>%6.1lf%s{}</tt>{}".format(
                            self.name,
                            rep_name,
                            _sum_unit if total else "",
                            r"\l" if _last else r""
                        ),
                    ]
                )
        return c_lines

    def get_legend_list(self):
        l_list = [
            ("min", "MINIMUM", 39, False),
            ("ave", "AVERAGE", 0, False),
            ("max", "MAXIMUM", 39, False),
            ("last", "LAST", 0, False)
        ]
        if self.create_total:
            l_list.append(
                ("total", "TOTAL", 39, True)
            )
        l_list = [(rep_name, cf, total) for rep_name, cf, min_width, total in l_list if self.max_info_width > min_width or True]
        return l_list

    @property
    def header_line(self):
        _sv = self.rrd_graph.para_dict["show_values"]
        if _sv:
            _l_list = self.get_legend_list()
        else:
            _l_list = []
        return "COMMENT:<tt>{}{}{}</tt>\\n".format(
            (
                "{{:<{:d}s}}".format(
                    self.max_info_width + 4
                )
            ).format(
                "Description"
            )[:self.max_info_width + 4],
            "unit" if _sv else "",
            "".join(
                [
                    "{:>9s}".format(rep_name) for rep_name, _cf, _total in _l_list
                ]
            )
        )


class GraphTarget(object):
    def __init__(self, g_key, dev_list, graph_keys):
        # can also be a short key (for instance 'load')
        self.graph_key = g_key
        self.dev_list = dev_list
        self.__headers = []
        # list of full keys (<type>:<root>.<leaf>)
        self.graph_keys = graph_keys
        self.graph_name = "gfx_{}_{}_{:d}.png".format(self.graph_key, uuid.uuid4(), int(time.time()))  #
        self.rel_file_loc = os.path.join(
            "/{}/static/graphs/{}".format(
                settings.REL_SITE_ROOT,
                self.graph_name
            )
        )
        # rrd post arguments, will not be reset
        self.__post_args = {}
        self.reset_keys()

    def reset_keys(self):
        self.__draw_keys = []
        self.__unique = 0

    @property
    def header(self):
        # hacky but working
        if self.graph_keys:
            return self.graph_keys[0][0].split(".")[0]
        else:
            return "???"

    @property
    def draw_keys(self):
        return self.__draw_keys

    def remove_keys(self, remove_keys):
        self.__draw_keys = [_key for _key in self.__draw_keys if _key not in remove_keys]

    @property
    def dev_id_str(self):
        return ",".join([dev_id for dev_id, _dev_pk in self.dev_list])

    @property
    def rrd_post_args(self):
        return [
            "{} {}".format(_key, _value) for _key, _value in self.__post_args.iteritems()
        ]

    def set_post_arg(self, key, value):
        if key in ["-l", "-u"]:
            if key not in self.__post_args:
                self.__post_args[key] = value
            else:
                if key == "l" and float(value) < float(self.__post_args[key]):
                    self.__post_args[key] = value
                elif key == "u" and float(value) > float(self.__post_args[key]):
                    self.__post_args[key] = value
        else:
            self.__post_args[key] = value

    def reset(self):
        self.defs = {}
        self.file_names = set()
        self.draw_result = None
        self.removed_keys = []
        self.__result_dict = None

    def get_def_idx(self):
        return len(self.defs) + 1

    def add_def(self, key, g_var, header_str, **kwargs):
        self.__unique += 1
        self.__draw_keys.append((self.__unique, key))
        self.__headers.append(header_str)
        self.defs[(self.__unique, key)] = g_var.graph_def(self.__unique, **kwargs)
        self.file_names.add(g_var.mvs_entry.file_name)

    def set_y_mm(self, _min, _max):
        # set min / max values for ordinate
        self.set_post_arg("-l", _min)
        self.set_post_arg("-u", _max)

    @property
    def removed_key_xml(self):
        return E.removed_keys(
            *[
                E.removed_key(
                    struct_key=_key[0],
                    value_key=_key[1],
                    device="{:d}".format(_pk)
                ) for _pk, _key in self.removed_keys
            ]
        )

    @property
    def valid(self):
        return True if self.defs and (self.draw_result is not None) else False

    @property
    def result_dict(self):
        if self.__result_dict is None:
            self.__result_dict = {
                key: "{:d}".format(value) if type(value) in [
                    int, long
                ] else FLOAT_FMT.format(value) for key, value in self.draw_result.iteritems() if not key.startswith("print[")
            }
        return self.__result_dict

    def graph_xml(self, dev_dict):
        _xml = E.graph(
            E.devices(
                *[
                    E.device(
                        unicode(dev_dict[_dev_key[1]]),
                        pk="{:d}".format(_dev_key[1])
                    ) for _dev_key in self.dev_list
                ]
            ),
            self.removed_key_xml,
            fmt_graph_key="gk_{}".format(self.graph_key),
            # devices key
            fmt_device_key="dk_{}".format(self.dev_id_str),
        )
        if self.valid:
            _xml.attrib["href"] = self.rel_file_loc
            for _key, _value in self.result_dict.iteritems():
                _xml.attrib[_key] = _value
        return _xml


class DataSource(object):
    def __init__(self, log_com, dev_pks, graph_keys, colorizer):
        self.__log_com = log_com
        self.__colorizer = colorizer
        # lut machinevector_id -> device_id
        _mv_lut = {_v[1]: _v[0] for _v in MachineVector.objects.filter(Q(device__in=dev_pks)).values_list("device_id", "pk")}
        self.__flat_keys = [(_v["struct_key"], _v["value_key"]) for _v in graph_keys]
        _query_keys = set([full_graph_key(_key) for _key in self.__flat_keys])
        # expand compounds
        _compound_dict = {}
        for _req in graph_keys:
            if _req.get("build_info", ""):
                _key = (_req["struct_key"], _req["value_key"])
                _full_key = full_graph_key(_key)
                _build_info = process_tools.decompress_struct(_req["build_info"])
                _compound_dict[_key] = []
                for _entry in _build_info:
                    _query_keys.add(_entry["key"])
                    _compound_dict[_key].append(_entry)
        # pprint.pprint(_compound_dict)
        # get mvv_list
        _mvv_list = MVValueEntry.objects.filter(
            Q(full_key__in=_query_keys) &
            Q(mv_struct_entry__machine_vector__device__in=dev_pks)
        ).select_related("mvstructentry")
        _mvv_dict = {_mvv.full_key: _mvv for _mvv in _mvv_list}
        self.log(
            "init datasource for {} / {}, found {}".format(
                logging_tools.get_plural("device", len(dev_pks)),
                logging_tools.get_plural("graph key", len(graph_keys)),
                logging_tools.get_plural("MVValueEntry", _mvv_list.count()),
            )
        )
        # format: key = (dev_pk, (struct_key, value_key)); value = (mvs, mvv)
        self.__dict = {}
        # first step: check for flat (non-compound) keys
        for _flat in self.flat_keys:
            _fk = full_graph_key(_flat)
            if _fk in _mvv_dict:
                _mvv = _mvv_dict[_fk]
                _mvs = _mvv.mv_struct_entry
                _dev_pk = _mv_lut[_mvs.machine_vector_id]
                self.__dict[(_dev_pk, _flat)] = [(_mvs, _mvv)]
        # color tables
        _color_tables = {}
        # second step: resolve compounds (its important to keep the order)
        for _c_key, _cs in _compound_dict.iteritems():
            # reset colorizer
            self.__colorizer.reset()
            for _entry in _cs:
                if _entry["key"] in _mvv_dict:
                    _mvv = _mvv_dict[_entry["key"]]
                    _mvs = _mvv.mv_struct_entry
                    _dev_pk = _mv_lut[_mvs.machine_vector_id]
                    if "color" in _entry and not _entry["color"].startswith("#"):
                        # lookup color table
                        _clr = _entry["color"]
                        if _clr not in _color_tables:
                            _color_tables[_clr] = self.__colorizer.simple_color_table(_clr)
                        _entry["color"] = _color_tables[_clr].color
                    self.__dict.setdefault((_dev_pk, _c_key), []).append(
                        (
                            _mvs,
                            _mvv.copy_and_modify(_entry),
                        )
                    )

    @property
    def flat_keys(self):
        # list of a tuple of all requested (not expanded) (mvs, mvv) keys
        return self.__flat_keys

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[DS] {}".format(what), log_level)

    def __contains__(self, key):
        return key in self.__dict

    def __getitem__(self, key):
        # return a list of values
        return self.__dict.get(key, [])


class RRDGraph(object):
    def __init__(self, graph_root, log_com, colorizer, para_dict, proc):
        self.log_com = log_com
        self.para_dict = {
            "size": "400x200",
            "graph_root": graph_root,
            "hide_empty":  False,
            "include_zero": False,
            "show_forecast": False,
            "scale_y": False,
            "merge_devices": True,
            "job_mode": "none",
            "selected_job": 0,
            "merge_cd": False,
        }
        self.dt_1970 = dateutil.parser.parse("1970-01-01 00:00 +0000")
        self.para_dict.update(para_dict)
        self.colorizer = colorizer
        self.proc = proc

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.log_com(u"[RRDG] {}".format(what), log_level)

    def _create_graph_keys(self, graph_keys):
        g_key_dict = {}
        for key_dict in graph_keys:
            s_key, v_key = (key_dict["struct_key"], key_dict["value_key"])
            if key_dict.get("build_info", ""):
                # is a compound (has build info)
                g_key_dict.setdefault(full_graph_key(key_dict), []).append((s_key, v_key))
            else:
                _flk = s_key.split(".")[0]
                # no compound, one graph per top level key
                g_key_dict.setdefault(_flk, []).append((s_key, v_key))
        return g_key_dict

    def _create_graph_keys_old(self, graph_keys):
        # graph_keys ... list of keys
        first_level_keys = set()
        g_key_dict = {}
        for key in graph_keys:
            _type, _key = key.split(":", 1)
            _flk = _key.split(".")[0]
            first_level_keys.add(_flk)
            if _flk == "compound":
                # compound, one graph per key
                g_key_dict.setdefault(key, [key])
            else:
                # no compound, one graph per top level key
                g_key_dict.setdefault(_flk, []).append(key)
        return g_key_dict

    def _get_jobs(self, dev_dict):
        # job addon dict
        _job_add_dict = {}
        if self.para_dict["job_mode"] in ["selected", "all"]:
            _jobs = rms_job_run.objects.filter(
                (
                    Q(device__in=dev_dict.keys()) | Q(rms_pe_info__device__in=dev_dict.keys())
                ) & (
                    (
                        Q(start_time_py__lte=self.para_dict["end_time_fc"]) &
                        Q(start_time_py__gte=self.para_dict["start_time"])
                    ) | (
                        Q(end_time_py__lte=self.para_dict["end_time_fc"]) &
                        Q(end_time_py__gte=self.para_dict["start_time"])
                    ) | (
                        Q(start_time__lte=self.para_dict["end_time_fc"]) &
                        Q(start_time__gte=self.para_dict["start_time"])
                    ) | (
                        Q(end_time__lte=self.para_dict["end_time_fc"]) &
                        Q(end_time__gte=self.para_dict["start_time"])
                    )
                )
            ).prefetch_related(
                "rms_pe_info_set"
            ).select_related(
                "rms_job",
                "rms_job__user",
                "device__domain_tree_node"
            ).order_by(
                "rms_job__jobid",
                "rms_job__taskid"
            )
            if self.para_dict["job_mode"] == "selected":
                _sj_id = self.para_dict["selected_job"]
                if _sj_id.count("."):
                    _jobs = _jobs.filter(Q(rms_job__jobid=_sj_id.split(".")[0]) & Q(rms_job__taskid=_sj_id.split(".")[1]))
                else:
                    _jobs = _jobs.filter(Q(rms_job__jobid=_sj_id))
            self.log(
                "jobs to add: {:d}, {}".format(
                    _jobs.count(),
                    ", ".join(sorted([_run.rms_job.full_id for _run in _jobs]))
                )
            )
            for _run in _jobs:
                _pe_info = _run.rms_pe_info()
                if not _pe_info:
                    # create serial pe_info
                    _pe_info = [{
                        "device": _run.device_id,
                        "slots": _run.slots,
                        "hostname": _run.device.full_name,
                    }]
                _dev_dict = {}
                for _entry in _pe_info:
                    _start_time = _run.start_time or _run.start_time_py
                    _end_time = _run.end_time or _run.end_time_py
                    # set start and / or end time to None if outside of graph
                    if _start_time and (_start_time <= self.para_dict["start_time"] or _start_time >= self.para_dict["end_time_fc"]):
                        _start_time = None
                    if _end_time and (_end_time <= self.para_dict["start_time"] or _end_time >= self.para_dict["end_time_fc"]):
                        _end_time = None
                    _job_add_dict.setdefault(_entry["device"], []).append(
                        {
                            "slots": _entry["slots"] or 1,
                            "start_time": _start_time,
                            "end_time_fc": _end_time,
                            "job": _run.rms_job.full_id,
                            "user": unicode(_run.rms_job.user.login),
                            "hostname": _entry["hostname"],
                        }
                    )
        return _job_add_dict

    def _create_job_args(self, dev_list, _job_add_dict):
        _ext_args = []
        for _stuff, _pk in dev_list:
            for _job_info in _job_add_dict.get(_pk, []):
                if len(dev_list) == 1:
                    _us_info = "{}, {}".format(
                        _job_info["user"],
                        logging_tools.get_plural("slot", _job_info["slots"]),
                    )
                else:
                    _us_info = "{}, {} on {}".format(
                        _job_info["user"],
                        logging_tools.get_plural("slot", _job_info["slots"]),
                        _job_info["hostname"],
                    )
                if _job_info["start_time"] and _job_info["end_time_fc"]:
                    _ext_args.extend(
                        [
                            "VRULE:{}#4444ee:{}".format(
                                int((_job_info["start_time"] - self.dt_1970).total_seconds()),
                                rrd_escape(
                                    "{} start".format(
                                        _job_info["job"],
                                    )
                                )
                            ),
                            "VRULE:{}#ee4444:{}\l".format(
                                int((_job_info["end_time_fc"] - self.dt_1970).total_seconds()),
                                rrd_escape(
                                    "end, {} - {}, {}".format(
                                        strftime(_job_info["start_time"]),
                                        strftime(_job_info["end_time_fc"], _job_info["start_time"]),
                                        _us_info,
                                    )
                                )
                            ),
                        ]
                    )
                elif _job_info["start_time"]:
                    _ext_args.append(
                        "VRULE:{}#4444ee:{}\l".format(
                            int((_job_info["start_time"] - self.dt_1970).total_seconds()),
                            rrd_escape(
                                "{} start, {}, {}".format(
                                    _job_info["job"],
                                    strftime(_job_info["start_time"]),
                                    _us_info,
                                )
                            )
                        )
                    )
                elif _job_info["end_time_fc"]:
                    _ext_args.append(
                        "VRULE:{}#ee4444:{}\l".format(
                            int((_job_info["end_time_fc"] - self.dt_1970).total_seconds()),
                            rrd_escape(
                                "{} end  , {}, {}".format(
                                    _job_info["job"],
                                    strftime(_job_info["end_time_fc"]),
                                    _us_info,
                                )
                            )
                        )
                    )
        return _ext_args

    def graph(self, dev_pks, graph_keys):
        # end time with forecast
        local_ds = DataSource(self.log_com, dev_pks, graph_keys, self.colorizer)
        self.para_dict["end_time_fc"] = self.para_dict["end_time"]
        if self.para_dict["show_forecast"]:
            self.para_dict["end_time_fc"] += self.para_dict["end_time"] - self.para_dict["start_time"]
        timeframe = abs((self.para_dict["end_time_fc"] - self.para_dict["start_time"]).total_seconds())
        graph_size = self.para_dict["size"]
        graph_width, graph_height = [int(value) for value in graph_size.split("x")]
        self.log("width / height : {:d} x {:d}, timeframe {}".format(
            graph_width,
            graph_height,
            logging_tools.get_diff_time_str(timeframe),
        ))
        # store for DEF generation
        self.width = graph_width
        self.height = graph_height
        dev_dict = {cur_dev.pk: unicode(cur_dev.display_name) for cur_dev in device.objects.filter(Q(pk__in=dev_pks))}
        s_graph_key_dict = self._create_graph_keys(graph_keys)
        self.log(
            "found {}: {}".format(
                logging_tools.get_plural("device", len(dev_pks)),
                ", ".join(
                    [
                        "{:d} ({})".format(pk, dev_dict.get(pk, "unknown")) for pk in dev_pks
                    ]
                )
            )
        )
        self.log(
            "graph keys: {}".format(
                ", ".join([full_graph_key(_v) for _v in graph_keys])
            )
        )
        self.log(
            "top level keys: {:d}; {}".format(
                len(s_graph_key_dict),
                ", ".join(sorted(s_graph_key_dict)),
            )
        )
        enumerated_dev_pks = [
            (
                "{:d}.{:d}".format(_idx, _pk),
                _pk
            ) for _idx, _pk in enumerate(dev_pks)
        ]
        if self.para_dict["merge_devices"]:
            # one device per graph
            graph_key_list = [
                [
                    GraphTarget(g_key, enumerated_dev_pks, v_list)
                ] for g_key, v_list in s_graph_key_dict.iteritems()
            ]
        elif self.para_dict["merge_cd"]:
            graph_key_list = []
            # slave: controlling device(s)
            # merge controlling devices with devices on a single graph
            _all_slaves = set(device.objects.filter(Q(master_connections__in=dev_pks)).values_list("pk", flat=True))
            # all slaves now holds all controlling devices
            for _dev in device.objects.filter(Q(pk__in=dev_pks)):
                _slave_pks = set(_dev.slave_connections.all().values_list("pk", flat=True))
                # device is no controlling device
                if _dev.pk not in _all_slaves:
                    _merged_pks = set([_dev.pk]) | (_slave_pks & set(dev_pks))
                    for g_key, v_list in sorted(s_graph_key_dict.iteritems()):
                        graph_key_list.append(
                            [
                                GraphTarget(
                                    g_key,
                                    [(dev_id, dev_pk) for dev_id, dev_pk in enumerated_dev_pks if dev_pk in _merged_pks],
                                    v_list
                                )
                            ]
                        )
        else:
            graph_key_list = []
            for g_key, v_list in sorted(s_graph_key_dict.iteritems()):
                graph_key_list.append(
                    [
                        GraphTarget(
                            g_key,
                            [(dev_id, dev_pk)],
                            v_list
                        ) for dev_id, dev_pk in enumerated_dev_pks
                    ]
                )
        self.log("number of graphs to create: {:d}".format(len(graph_key_list)))
        graph_list = E.graph_list()
        _job_add_dict = self._get_jobs(dev_dict)
        for _graph_line in graph_key_list:
            # iterate in case scale_y is True
            _iterate_line, _line_iteration = (True, 0)
            while _iterate_line:
                for _graph_target in _graph_line:
                    abs_file_loc = os.path.join(self.para_dict["graph_root"], _graph_target.graph_name)
                    # clear list of defs, reset result
                    _graph_target.reset()
                    # reset colorizer for current graph
                    self.colorizer.reset()
                    self.abs_start_time = int((self.para_dict["start_time"] - self.dt_1970).total_seconds())
                    self.abs_end_time = int((self.para_dict["end_time_fc"] - self.dt_1970).total_seconds())
                    rrd_pre_args = [
                        abs_file_loc,
                        "-E",  # slope mode
                        "-Rlight",  # font render mode, slight hint
                        "-Gnormal",  # render mode
                        "-P",  # use pango markup
                        # "-nDEFAULT:8:",
                        "-w {:d}".format(graph_width),
                        "-h {:d}".format(graph_height),
                        "-aPNG",  # image format
                        # "--daemon", "unix:{}".format(global_config["RRD_CACHED_SOCKET"]),  # rrd caching daemon address
                        "-W {} by init.at".format(settings.INIT_PRODUCT_NAME),  # title
                        "--slope-mode",  # slope mode
                        "-cBACK#ffffff",
                        "--end", "{:d}".format(self.abs_end_time),  # end
                        "--start", "{:d}".format(self.abs_start_time),  # start
                        GraphVar(self, _graph_target, None, None, "").header_line,
                    ]
                    # reset graph keys
                    _graph_target.reset_keys()
                    # outer loop: iterate over all keys for the graph
                    for graph_key in sorted(_graph_target.graph_keys):
                        # inner loop: iterate over all dev ids for the graph
                        for _cur_id, cur_pk in _graph_target.dev_list:
                            # print "***", _cur_id, cur_pk
                            if (cur_pk, graph_key) in local_ds:
                                # resolve
                                for _mvs, _mvv in local_ds[(cur_pk, graph_key)]:
                                    _take = True
                                    try:
                                        if os.stat(_mvs.file_name)[stat.ST_SIZE] < 100:
                                            self.log(
                                                "skipping {} (file is too small)".format(
                                                    _mvs.file_name,
                                                ),
                                                logging_tools.LOG_LEVEL_ERROR
                                            )
                                            _take = False
                                    except:
                                        self.log(
                                            "RRD file {} not accessible: {}".format(
                                                _mvs.file_name,
                                                process_tools.get_except_info(),
                                            ),
                                            logging_tools.LOG_LEVEL_ERROR
                                        )
                                        _take = False
                                    if _take:
                                        # print "**", graph_key, _mvs.key, _mvv.key
                                        # store def
                                        _graph_target.add_def(
                                            (_mvs.key, _mvv.key),
                                            GraphVar(
                                                self,
                                                _graph_target,
                                                _mvs,
                                                _mvv,
                                                graph_key,
                                                dev_dict[cur_pk]
                                            ),
                                            "header_str",
                                            timeshift=self.para_dict["timeshift"]
                                        )
                    if _graph_target.defs:
                        draw_it = True
                        removed_keys = set()
                        while draw_it:
                            rrd_args = rrd_pre_args + sum([_graph_target.defs[_key] for _key in _graph_target.draw_keys], [])
                            rrd_args.extend(_graph_target.rrd_post_args)
                            rrd_args.extend(
                                [
                                    "--title",
                                    "{} on {} (tf: {}{})".format(
                                        _graph_target.header,
                                        dev_dict.get(
                                            _graph_target.dev_list[0][1],
                                            "unknown"
                                        ) if len(_graph_target.dev_list) == 1 else logging_tools.get_plural(
                                            "device",
                                            len(_graph_target.dev_list)
                                        ),
                                        logging_tools.get_diff_time_str(timeframe),
                                        ", with forecast" if self.para_dict["end_time"] != self.para_dict["end_time_fc"] else "",
                                    )
                                ]
                            )
                            rrd_args.extend(self._create_job_args(_graph_target.dev_list, _job_add_dict))
                            self.proc.flush_rrdcached(_graph_target.file_names)
                            try:
                                draw_result = rrdtool.graphv(*rrd_args)
                            except:
                                self.log("error creating graph: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                                if global_config["DEBUG"]:
                                    for _idx, _entry in enumerate(rrd_args, 1):
                                        self.log("  {:4d} {}".format(_idx, _entry))
                                draw_result = None
                                draw_it = False
                            else:
                                # compare draw results, add -l / -u when scale_y is true
                                # pprint.pprint(draw_result)
                                res_dict = {
                                    value.split("=", 1)[0]: value.split("=", 1)[1] for key, value in draw_result.iteritems() if key.startswith("print[")
                                }
                                # reorganize
                                val_dict = {}
                                for key, value in res_dict.iteritems():
                                    _split = key.split(".")
                                    cf = _split.pop(-1)
                                    try:
                                        value = float(value)
                                    except:
                                        pass
                                    else:
                                        value = None if value == 0.0 else value
                                    # extract device pk from key
                                    _unique_id = int(_split.pop(0))
                                    _sum_key = ".".join(_split)
                                    _s_key, _v_key = _sum_key.split("...")
                                    if value is not None:
                                        val_dict.setdefault((_unique_id, (_s_key, _v_key)), {})[cf] = value
                                # pprint.pprint(val_dict)
                                # check if the graphs shall always include y=0
                                draw_it = False
                                if self.para_dict["include_zero"]:
                                    if "value_min" in draw_result and "value_max" in draw_result:
                                        if draw_result["value_min"] > 0.0:
                                            _graph_target.set_post_arg("-l", "0")
                                            draw_it = True
                                        if draw_result["value_max"] < 0.0:
                                            _graph_target.set_post_arg("-u", "0")
                                            draw_it = True
                                # check for empty graphs
                                empty_keys = set(_graph_target.draw_keys) - set(val_dict.keys())
                                if empty_keys and self.para_dict["hide_empty"]:
                                    self.log(
                                        u"{}: {}".format(
                                            logging_tools.get_plural("empty key", len(empty_keys)),
                                            ", ".join(sorted(["{} (dev {:d})".format(_key, _pk) for _pk, _key in empty_keys])),
                                        )
                                    )
                                    removed_keys |= empty_keys
                                    _graph_target.remove_keys(empty_keys)
                                    # draw_keys = [_key for _key in draw_keys if _key not in empty_keys]
                                    if not _graph_target.draw_keys:
                                        draw_result = None
                                    else:
                                        draw_it = True
                        _graph_target.draw_result = draw_result
                        _graph_target.removed_keys = removed_keys
                    else:
                        self.log("no DEFs for graph_key_dict {}".format(_graph_target.graph_key), logging_tools.LOG_LEVEL_ERROR)
                _iterate_line = False
                _valid_graphs = [_entry for _entry in _graph_line if _entry.valid]
                if _line_iteration == 0 and self.para_dict["scale_y"] and len(_valid_graphs) > 1:
                    _line_iteration += 1
                    _vmin_v, _vmax_v = (
                        [_entry.draw_result["value_min"] for _entry in _valid_graphs],
                        [_entry.draw_result["value_max"] for _entry in _valid_graphs],
                    )
                    if set(_vmin_v) > 1 or set(_vmax_v) > 1:
                        _vmin, _vmax = (FLOAT_FMT.format(min(_vmin_v)), FLOAT_FMT.format(max(_vmax_v)))
                        self.log(
                            "setting y_min / y_max for {} to {} / {}".format(
                                _valid_graphs[0].graph_key,
                                _vmin,
                                _vmax,
                            )
                        )
                        [_entry.set_y_mm(_vmin, _vmax) for _entry in _valid_graphs]
                        _iterate_line = True
                if not _iterate_line:
                    graph_list.extend(
                        [_graph_target.graph_xml(dev_dict) for _graph_target in _graph_line]
                    )
        # print etree.tostring(graph_list, pretty_print=True)
        return graph_list


class graph_process(threading_tools.process_obj, server_mixins.operational_error_mixin):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True
        )
        connection.close()
        self.register_func("graph_rrd", self._graph_rrd)
        self.graph_root = global_config["GRAPH_ROOT"]
        self.graph_root_debug = global_config["GRAPH_ROOT_DEBUG"]
        self.log("graphs go into {} for non-debug calls and into {} for debug calls".format(self.graph_root, self.graph_root_debug))
        self.colorizer = Colorizer(self.log)
        self.__rrdcached_socket = None

    def _open_rrdcached_socket(self):
        self._close_rrdcached_socket()
        try:
            self.__rrdcached_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.__rrdcached_socket.connect(global_config["RRD_CACHED_SOCKET"])
        except:
            self.log("error opening rrdcached socket: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            self.__rrdcached_socket = None
        else:
            self.log("connected to rrdcached socket {}".format(global_config["RRD_CACHED_SOCKET"]))
        self.__flush_cache = set()

    def _close_rrdcached_socket(self):
        if self.__rrdcached_socket:
            try:
                self.__rrdcached_socket.close()
            except:
                self.log("error closing rrdcached socket: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            else:
                self.log("closed rrdcached socket")
            self.__rrdcached_socket = None

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self._close()
        self.__log_template.close()

    def _close(self):
        pass

    def flush_rrdcached(self, f_names):
        if f_names:
            f_names -= self.__flush_cache
            if f_names:
                self.__flush_cache |= f_names
                if self.__rrdcached_socket:
                    _s_time = time.time()
                    self.log("sending flush() to rrdcached for {}".format(logging_tools.get_plural("file", len(f_names))))
                    _lines = [
                        "BATCH"
                    ] + [
                        "FLUSH {}".format(_f_name) for _f_name in f_names
                    ] + [
                        ".",
                        "",
                    ]
                    self.__rrdcached_socket.send("\n".join(_lines))
                    _read, _write, _exc = select.select([self.__rrdcached_socket.fileno()], [], [], 5000)
                    _e_time = time.time()
                    if not _read:
                        self.log("read list is empty after {}".format(logging_tools.get_diff_time_str(_e_time - _s_time)), logging_tools.LOG_LEVEL_ERROR)
                    else:
                        _recv = self.__rrdcached_socket.recv(16384)
                else:
                    self.log("no valid rrdcached_socket, skipping flush()", logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("no file names given, skipping flush()", logging_tools.LOG_LEVEL_WARN)

    def _graph_rrd(self, *args, **kwargs):
        src_id, srv_com = (args[0], server_command.srv_command(source=args[1]))
        dev_pks = device.objects.filter(
            Q(pk__in=srv_com.xpath(".//device_list/device/@pk", smart_strings=False)) &
            Q(machinevector__pk__gt=0)
        ).values_list("pk", flat=True)
        graph_keys = json.loads(srv_com["*graph_key_list"])
        #    [
        #        (_el.get("struct_key"), _el.get("value_key")) for _el in srv_com.xpath(".//graph_key_list/graph_key[@struct_key]", smart_strings=False)
        #    ]
        # )
        para_dict = {}
        for para in srv_com.xpath(".//parameters", smart_strings=False)[0]:
            para_dict[para.tag] = para.text
        # cast to integer
        para_dict = {key: int(value) if key in ["timeshift"] else value for key, value in para_dict.iteritems()}
        for key in ["start_time", "end_time"]:
            # cast to datetime
            para_dict[key] = dateutil.parser.parse(para_dict[key])
        for key, _default in [
            ("hide_empty", "0"),
            ("merge_devices", "1"),
            ("scale_y", "0"),
            ("show_values", "1"),
            ("include_zero", "0"),
            ("show_forecast", "0"),
            ("debug_mode", "0"),
            ("merge_cd", "0"),
        ]:
            para_dict[key] = True if int(para_dict.get(key, "0")) else False
        self._open_rrdcached_socket()
        try:
            graph_list = RRDGraph(
                self.graph_root_debug if para_dict.get("debug_mode", False) else self.graph_root,
                self.log,
                self.colorizer,
                para_dict,
                self
            ).graph(dev_pks, graph_keys)
        except:
            for _line in process_tools.exception_info().log_lines:
                self.log(_line, logging_tools.LOG_LEVEL_ERROR)
            srv_com["graphs"] = []
            srv_com.set_result(
                "error generating graphs: {}".format(process_tools.get_except_info()),
                server_command.SRV_REPLY_STATE_CRITICAL
            )
        else:
            srv_com["graphs"] = graph_list
            srv_com.set_result(
                "generated {}".format(logging_tools.get_plural("graph", len(graph_list))),
                server_command.SRV_REPLY_STATE_OK
            )
        self._close_rrdcached_socket()
        self.send_pool_message("send_command", src_id, unicode(srv_com))
