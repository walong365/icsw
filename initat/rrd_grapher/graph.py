# Copyright (C) 2007-2009,2013-2014 Andreas Lang-Nevyjel, init.at
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
from initat.cluster.backbone.models import device, rms_job_run, cluster_timezone
from initat.rrd_grapher.config import global_config
from lxml import etree  # @UnresolvedImport
from lxml.builder import E  # @UnresolvedImport
import datetime
import dateutil.parser
import logging_tools
import os
import pprint
import process_tools
import re
import rrdtool  # @UnresolvedImport
import server_command
import threading_tools
import time
import uuid


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
        self.colortables = etree.fromstring(file(_ct_file, "r").read())
        self.color_tables = {}
        for c_table in self.colortables.findall(".//colortable[@name]"):
            self.color_tables[c_table.get("name")] = ["#{:s}".format(color.get("rgb")) for color in c_table if self._check_color(color)]
        self.log("read colortables from {}".format(_ct_file))
        self.color_rules = etree.fromstring(file(_cr_file, "r").read())
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

    def get_color_and_style(self, entry):
        t_name, s_dict = self.get_table_name(entry)
        if t_name not in self.table_offset:
            self.table_offset[t_name] = 0
        self.table_offset[t_name] += 1
        if self.table_offset[t_name] == len(self.color_tables[t_name]):
            self.table_offset[t_name] = 0
        _clr = self.color_tables[t_name][self.table_offset[t_name]]
        if "transparency" in s_dict:
            _clr = "{}{:02x}".format(_clr, int(s_dict["transparency"]))
        return _clr, s_dict

    def get_table_name(self, entry):
        s_dict = {}
        key_name = entry.get("full", entry.get("name"))
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


class graph_var(object):
    def __init__(self, rrd_graph, entry, key, dev_name=""):
        # XML entry
        self.entry = entry
        # graph key (load.1)
        self.key = key
        # device name
        self.dev_name = dev_name
        self.rrd_graph = rrd_graph
        self.max_info_width = max(2, 60 + int((self.rrd_graph.width - 800) / 8))
        self.name = "v{:d}".format(self.rrd_graph.get_def_idx())

    def __getitem__(self, key):
        return self.entry.attrib[key]

    def __contains__(self, key):
        return key in self.entry.attrib

    def get(self, key, default):
        return self.entry.attrib.get(key, default)

    def info(self, timeshift):
        info = self["info"]
        parts = self["name"].split(".")
        for idx in xrange(len(parts)):
            info = info.replace("${:d}".format(idx + 1), parts[idx])
        info_parts = []
        if self.dev_name:
            info_parts.append(unicode(self.dev_name))
        if timeshift:
            info_parts.append("ts {}".format(logging_tools.get_diff_time_str(timeshift)))
        return rrd_escape(
            "{}{}".format(
                info,
                " ({})".format(", ".join(info_parts)) if info_parts else "",
            )
        )

    def get_color_and_style(self):
        self.color, self.style_dict = self.rrd_graph.colorizer.get_color_and_style(self.entry)

    def graph_def(self, unique_id, **kwargs):
        # unique_id = device pk
        timeshift = kwargs.get("timeshift", 0)
        self.get_color_and_style()
        src_cf = "AVERAGE"
        if self.entry.tag == "value":
            # pde entry
            _src_str = "{}:{}:{}".format(self["file_name"], self["part"], src_cf)
        else:
            # machvector entry
            _src_str = "{}:v:{}".format(self["file_name"], src_cf)
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
        if draw_type in ["AREA1", "AREA2", "AREA3"]:
            # support area with outline style
            c_lines.extend(
                [
                    "{}:{}{}:<tt>{}</tt>".format(
                        "AREA",
                        draw_name,
                        self.color,
                        ("{{:<{:d}s}}".format(self.max_info_width)).format(self.info(timeshift))[:self.max_info_width]
                    ),
                    "{}:{}{}".format(
                        draw_type.replace("AREA", "LINE"),
                        draw_name,
                        "#000000",
                    )
                ]
            )
        else:
            c_lines.append(
                "{}:{}{}:<tt>{}</tt>".format(
                    draw_type,
                    draw_name,
                    self.color,
                    ("{{:<{:d}s}}".format(self.max_info_width)).format(self.info(timeshift))[:self.max_info_width]),
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
                    "{}:{}inv{}::dashes".format(
                        ts_draw_type,
                        ts_name,
                        ts_color,
                    )
                ]
            )
        # legend list
        l_list = self.get_legend_list()
        for _num, (rep_name, cf) in enumerate(l_list):
            _last = _num == len(l_list) - 1
            _unit = self.entry.get("unit", "").replace("%", "%%")
            # simply some units
            _unit = {"1": "", "1/s": "/s"}.get(_unit, _unit)
            c_lines.extend(
                [
                    "VDEF:{}{}={},{}".format(self.name, rep_name, self.name, cf),
                    "GPRINT:{}{}:<tt>%6.1lf%s{}</tt>{}".format(
                        self.name,
                        rep_name,
                        _unit if _last else "",
                        r"\l" if _last else r""
                    ),
                    # "VDEF:{}{}2={},{}".format(self.name, rep_name, self.name, cf),
                    "PRINT:{}{}:{:d}.{}.{}=%.4lf".format(
                        self.name,
                        rep_name,
                        unique_id,
                        rrd_escape(self.key),
                        cf,
                    ),
                ]
            )
        return c_lines

    def get_legend_list(self):
        l_list = [
            ("min", "MINIMUM", 39),
            ("ave", "AVERAGE", 0),
            ("max", "MAXIMUM", 39),
            ("last", "LAST", 0),
            ("total", "TOTAL", 39)]
        l_list = [(rep_name, cf) for rep_name, cf, min_width in l_list if self.max_info_width > min_width or True]
        return l_list

    @property
    def header_line(self):
        return "COMMENT:<tt>{}{}</tt>\\n".format(
            (
                "{{:<{:d}s}}".format(
                    self.max_info_width + 2
                )
            ).format(
                "Description"
            )[:self.max_info_width + 2],
            "".join(
                [
                    "{:>9s}".format(rep_name) for rep_name, _cf in self.get_legend_list()
                ]
            )
        )


class RRDGraph(object):
    def __init__(self, log_com, colorizer, para_dict):
        self.log_com = log_com
        self.para_dict = {
            "size": "400x200",
            "graph_root": global_config["GRAPH_ROOT"],
            "hide_empty":  False,
            "include_zero": False,
            "scale_y": False,
            "merge_devices": True,
            "job_mode": "none",
            "selected_job": 0,
        }
        self.para_dict.update(para_dict)
        self.colorizer = colorizer

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.log_com(u"[RRDG] {}".format(what), log_level)

    def _create_graph_keys(self, graph_keys):
        # graph_keys ... list of keys
        first_level_keys = set([key.split(".")[0].split(":")[-1] for key in graph_keys])
        g_key_dict = {flk: sorted([key for key in graph_keys if key.split(".")[0].split(":")[-1] == flk]) for flk in first_level_keys}
        return g_key_dict

    def get_def_idx(self):
        return len(self.defs) + 1

    def graph(self, vector_dict, dev_pks, graph_keys):
        timeframe = abs((self.para_dict["end_time"] - self.para_dict["start_time"]).total_seconds())
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
        dev_dict = {cur_dev.pk: unicode(cur_dev.full_name) for cur_dev in device.objects.filter(Q(pk__in=dev_pks))}
        s_graph_key_dict = self._create_graph_keys(graph_keys)
        self.log(
            "found {}: {}".format(
                logging_tools.get_plural("device", len(dev_pks)),
                ", ".join(["{:d} ({})".format(pk, dev_dict.get(pk, "unknown")) for pk in dev_pks])))
        self.log("graph keys: {}".format(", ".join(graph_keys)))
        self.log(
            "top level keys: {:d}; {}".format(
                len(s_graph_key_dict),
                ", ".join(sorted(s_graph_key_dict)),
            )
        )
        graph_key_list = []
        enumerated_dev_pks = [("{:d}.{:d}".format(_idx, _pk), _pk) for _idx, _pk in enumerate(dev_pks)]
        # one device per graph
        if self.para_dict["merge_devices"]:
            graph_key_list = [(g_key, enumerated_dev_pks, v_list) for g_key, v_list in s_graph_key_dict.iteritems()]
        else:
            for g_key, v_list in s_graph_key_dict.iteritems():
                for dev_id, dev_pk in enumerated_dev_pks:
                    graph_key_list.append((g_key, [(dev_id, dev_pk)], v_list))
        self.log("number of graphs to create: {:d}".format(len(graph_key_list)))
        graph_list = E.graph_list()
        # job addon dict
        _job_add_dict = {}
        if self.para_dict["job_mode"] in ["selected", "all"]:
            _jobs = rms_job_run.objects.filter(
                (
                    Q(device__in=dev_dict.keys()) | Q(rms_pe_info__device__in=dev_dict.keys())
                ) & (
                    (
                        Q(start_time_py__lte=self.para_dict["end_time"]) &
                        Q(start_time_py__gte=self.para_dict["start_time"])
                    ) | (
                        Q(end_time_py__lte=self.para_dict["end_time"]) &
                        Q(end_time_py__gte=self.para_dict["start_time"])
                    ) | (
                        Q(start_time__lte=self.para_dict["end_time"]) &
                        Q(start_time__gte=self.para_dict["start_time"])
                    ) | (
                        Q(end_time__lte=self.para_dict["end_time"]) &
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
                    if _start_time and (_start_time <= self.para_dict["start_time"] or _start_time >= self.para_dict["end_time"]):
                        _start_time = None
                    if _end_time and (_end_time <= self.para_dict["start_time"] or _end_time >= self.para_dict["end_time"]):
                        _end_time = None
                    _job_add_dict.setdefault(_entry["device"], []).append(
                        {
                            "slots": _entry["slots"] or 1,
                            "start_time": _start_time,
                            "end_time": _end_time,
                            "job": _run.rms_job.full_id,
                            "user": unicode(_run.rms_job.user.login),
                            "hostname": _entry["hostname"],
                        }
                    )
            # pprint.pprint(_job_add_dict)

        for tlk, dev_list, graph_keys in sorted(graph_key_list):
            dev_id_str = ",".join([dev_id for dev_id, dev_pk in dev_list])
            graph_name = "gfx_{}_{}_{:d}.png".format(tlk, uuid.uuid4(), int(time.time()))
            abs_file_loc, rel_file_loc = (
                os.path.join(self.para_dict["graph_root"], graph_name),
                os.path.join("/{}/static/graphs/{}".format(settings.REL_SITE_ROOT, graph_name)),
            )
            dt_1970 = dateutil.parser.parse("1970-01-01 00:00 +0000")
            # clear list of defs
            self.defs = {}
            # reset colorizer for current graph
            self.colorizer.reset()
            self.abs_start_time = int((self.para_dict["start_time"] - dt_1970).total_seconds())
            self.abs_end_time = int((self.para_dict["end_time"] - dt_1970).total_seconds())
            rrd_pre_args = [
                abs_file_loc,
                "-E",  # slope mode
                "-Rlight",  # font render mode, slight hint
                "-Gnormal",  # render mode
                "-P",  # use pango markup
                # "-nDEFAULT:8:",
                "-w {:d}".format(graph_width),
                "-h {:d}".format(graph_height),
                "-aPNG",  # image forma
                "--daemon", "unix:/var/run/rrdcached.sock",  # rrd caching daemon address
                "-W CORVUS by init.at",  # title
                "--slope-mode",  # slope mode
                "-cBACK#ffffff",
                "--end", "{:d}".format(self.abs_end_time),  # end
                "--start", "{:d}".format(self.abs_start_time),  # start
                graph_var(self, None, "").header_line,
            ]
            rrd_post_args = {}
            _unique = 0
            draw_keys = []
            for graph_key in sorted(graph_keys):
                for _cur_id, cur_pk in dev_list:
                    dev_vector = vector_dict[cur_pk]
                    if graph_key.startswith("pde:"):
                        # performance data from icinga
                        def_xml = dev_vector.find(".//value[@name='{}']".format(graph_key))
                    else:
                        # machine vector entry
                        def_xml = dev_vector.find(".//mve[@name='{}']".format(graph_key))
                    if def_xml is not None:
                        _unique += 1
                        self.defs[(_unique, graph_key)] = graph_var(
                            self,
                            def_xml,
                            graph_key,
                            dev_dict[cur_pk]
                        ).graph_def(_unique, timeshift=self.para_dict["timeshift"])
                        draw_keys.append((_unique, graph_key))
            if self.defs:
                draw_it = True
                removed_keys = set()
                while draw_it:
                    rrd_args = rrd_pre_args + sum([self.defs[_key] for _key in draw_keys], [])
                    rrd_args.extend(
                        [
                            "{} {}".format(_key, _value) for _key, _value in rrd_post_args.iteritems()
                        ]
                    )
                    rrd_args.extend([
                        "--title",
                        "{} on {} (tf: {})".format(
                            tlk,
                            dev_dict.get(dev_list[0][1], "unknown") if len(dev_list) == 1 else logging_tools.get_plural("device", len(dev_list)),
                            # logging_tools.get_plural("result", len(self.defs)),
                            logging_tools.get_diff_time_str(timeframe)),
                    ])
                    # add job info
                    # todo: draw rectangles for jobs
                    # rrd_args.extend(
                    #    [
                    #        "CDEF:xd=TIME,1408540706,GT,v1,*",
                    #        "LINE1:xd#0044ff",
                    #    ]
                    # )
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
                            if _job_info["start_time"] and _job_info["end_time"]:
                                rrd_args.extend(
                                    [
                                        "VRULE:{}#4444ee:{}".format(
                                            int((_job_info["start_time"] - dt_1970).total_seconds()),
                                            rrd_escape(
                                                "{} start".format(
                                                    _job_info["job"],
                                                )
                                            )
                                        ),
                                        "VRULE:{}#ee4444:{}\l".format(
                                            int((_job_info["end_time"] - dt_1970).total_seconds()),
                                            rrd_escape(
                                                "end, {} - {}, {}".format(
                                                    strftime(_job_info["start_time"]),
                                                    strftime(_job_info["end_time"], _job_info["start_time"]),
                                                    _us_info,
                                                )
                                            )
                                        ),
                                    ]
                                )
                            elif _job_info["start_time"]:
                                rrd_args.append(
                                    "VRULE:{}#4444ee:{}\l".format(
                                        int((_job_info["start_time"] - dt_1970).total_seconds()),
                                        rrd_escape(
                                            "{} start, {}, {}".format(
                                                _job_info["job"],
                                                strftime(_job_info["start_time"]),
                                                _us_info,
                                            )
                                        )
                                    )
                                )
                            elif _job_info["end_time"]:
                                rrd_args.append(
                                    "VRULE:{}#ee4444:{}\l".format(
                                        int((_job_info["end_time"] - dt_1970).total_seconds()),
                                        rrd_escape(
                                            "{} end  , {}, {}".format(
                                                _job_info["job"],
                                                strftime(_job_info["end_time"]),
                                                _us_info,
                                            )
                                        )
                                    )
                                )
                    # self.log("calling graphv ({})".format(" ".join(rrd_args)))
                    try:
                        draw_result = rrdtool.graphv(*rrd_args)
                    except:
                        self.log("error creating graph: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                        if global_config["DEBUG"]:
                            pprint.pprint(rrd_args)
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
                            _key = ".".join(_split)
                            if value is not None:
                                val_dict.setdefault((_unique_id, _key), {})[cf] = value
                        # check if the graphs shall always include y=0
                        draw_it = False
                        if self.para_dict["include_zero"]:
                            if "value_min" in draw_result and "value_max" in draw_result:
                                if draw_result["value_min"] > 0.0:
                                    rrd_post_args["-l"] = "0"
                                    draw_it = True
                                if draw_result["value_max"] < 0.0:
                                    rrd_post_args["-u"] = "0"
                                    draw_it = True
                        # check for empty graphs
                        empty_keys = set(draw_keys) - set(val_dict.keys())
                        if empty_keys and self.para_dict["hide_empty"]:
                            self.log(
                                u"{}: {}".format(
                                    logging_tools.get_plural("empty key", len(empty_keys)),
                                    ", ".join(sorted(["{} (dev {:d})".format(_key, _pk) for _pk, _key in empty_keys])),
                                )
                            )
                            removed_keys |= empty_keys
                            draw_keys = [_key for _key in draw_keys if _key not in empty_keys]
                            # self.defs = {key : value for key, value in self.defs.iteritems() if key not in empty_keys}
                            if not draw_keys:
                                draw_result = None
                            else:
                                draw_it = True
                rem_key_el = E.removed_keys(
                    *[E.removed_key(_key, device="{:d}".format(_pk)) for _pk, _key in removed_keys]
                )
                if self.defs and (draw_result is not None):
                    # defs present
                    graph_list.append(
                        E.graph(
                            # not needed right now
                            E.devices(
                                *[E.device(unicode(dev_dict[_dev_key[1]]), pk="{:d}".format(_dev_key[1])) for _dev_key in dev_list]
                            ),
                            rem_key_el,
                            # graph key
                            fmt_graph_key="gk_{}".format(tlk),
                            # devices key
                            fmt_device_key="dk_{}".format(dev_id_str),
                            href=rel_file_loc,
                            **dict(
                                [
                                    (
                                        key,
                                        "{:d}".format(value) if type(value) in [int, long] else "{:.6f}".format(value)
                                    ) for key, value in draw_result.iteritems() if not key.startswith("print[")
                                ]
                            )
                        )
                    )
                else:
                    # empty graph
                    graph_list.append(
                        E.graph(
                            rem_key_el
                        )
                    )
            else:
                self.log("no DEFs for graph_key_dict {}".format(tlk), logging_tools.LOG_LEVEL_ERROR)
        # print etree.tostring(graph_list, pretty_print=True)
        return graph_list


class graph_process(threading_tools.process_obj, threading_tools.operational_error_mixin):
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
        self.register_func("xml_info", self._xml_info)
        self.vector_dict = {}
        self.graph_root = global_config["GRAPH_ROOT"]
        self.log("graphs go into {}".format(self.graph_root))
        self.colorizer = Colorizer(self.log)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self._close()
        self.__log_template.close()

    def _close(self):
        pass

    def _xml_info(self, *args, **kwargs):
        dev_id, xml_str = (args[0], etree.fromstring(args[1]))
        self.vector_dict[dev_id] = xml_str  # self._struct_vector(xml_str)

    def _graph_rrd(self, *args, **kwargs):
        src_id, srv_com = (args[0], server_command.srv_command(source=args[1]))
        dev_pks = [entry for entry in map(lambda x: int(x), srv_com.xpath(".//device_list/device/@pk", smart_strings=False)) if entry in self.vector_dict]
        graph_keys = sorted(srv_com.xpath(".//graph_key_list/graph_key/text()", smart_strings=False))
        para_dict = {}
        for para in srv_com.xpath(".//parameters", smart_strings=False)[0]:
            para_dict[para.tag] = para.text
        # cast to integer
        para_dict = {key: int(value) if key in ["timeshift"] else value for key, value in para_dict.iteritems()}
        for key in ["start_time", "end_time"]:
            # cast to datetime
            para_dict[key] = dateutil.parser.parse(para_dict[key])
        for key, _default in [("hide_empty", "0"), ("merge_devices", "1"), ("scale_y", "0"), ("include_zero", "0")]:
            para_dict[key] = True if int(para_dict.get(key, "0")) else False
        graph_list = RRDGraph(self.log, self.colorizer, para_dict).graph(self.vector_dict, dev_pks, graph_keys)
        srv_com["graphs"] = graph_list
        # print srv_com.pretty_print()
        srv_com.set_result(
            "generated {}".format(logging_tools.get_plural("graph", len(graph_list))),
            server_command.SRV_REPLY_STATE_OK
        )
        self.send_pool_message("send_command", src_id, unicode(srv_com))
