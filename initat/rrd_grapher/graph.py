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
from initat.cluster.backbone.models import device
from initat.rrd_grapher.config import global_config
from lxml import etree # @UnresolvedImport
from lxml.builder import E # @UnresolvedImport
import dateutil.parser
import logging_tools
import os
import pprint
import process_tools
import re
import rrdtool # @UnresolvedImport
import server_command
import threading_tools
import time

class colorizer(object):
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
            (re.compile("^{}".format(entry.attrib["key"].replace(".", r"\."))),
             entry) for entry in self.color_rules.xpath(".//entry[@key]", smart_strings=False)]
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
        self.entry = entry
        self.key = key
        self.dev_name = dev_name
        self.rrd_graph = rrd_graph
        self.max_info_width = 60 + int((self.rrd_graph.width - 800) / 8)
        self.name = "v{:d}".format(self.rrd_graph.get_def_idx())
    def __getitem__(self, key):
        return self.entry.attrib[key]
    def __contains__(self, key):
        return key in self.entry.attrib
    def get(self, key, default):
        return self.entry.attrib.get(key, default)
    @property
    def info(self):
        info = self["info"]
        parts = self["name"].split(".")
        for idx in xrange(len(parts)):
            info = info.replace("${:d}".format(idx + 1), parts[idx])
        if self.dev_name:
            info = "{} ({})".format(info, str(self.dev_name))
        return info
    def get_color_and_style(self):
        self.color, self.style_dict = self.rrd_graph.colorizer.get_color_and_style(self.entry)
    @property
    def config(self):
        self.get_color_and_style()
        src_cf = "AVERAGE"
        if self.entry.tag == "value":
            # pde entry
            c_lines = [
                "DEF:{}={}:{}:{}".format(self.name, self["file_name"], self["part"], src_cf),
            ]
        else:
            # machvector entry
            c_lines = [
                "DEF:{}={}:v:{}".format(self.name, self["file_name"], src_cf),
            ]
        if int(self.style_dict.get("invert", "0")):
            c_lines.append(
                "CDEF:{}inv={},-1,*".format(self.name, self.name),
            )
            draw_name = "{}inv".format(self.name)
        else:
            draw_name = self.name
        draw_type = self.style_dict.get("draw_type", "LINE1")
        if draw_type in ["AREA1", "AREA2", "AREA3"]:
            # support area with outline style
            c_lines.extend(
                [
                    "{}:{}{}:<tt>{}</tt>".format(
                        "AREA",
                        draw_name,
                        self.color,
                        ("{{:<{:d}s}}".format(self.max_info_width)).format(self.info)[:self.max_info_width]
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
                    ("{{:<{:d}s}}".format(self.max_info_width)).format(self.info)[:self.max_info_width]),
            )
        for rep_name, cf in [
            ("min"  , "MINIMUM"),
            ("ave"  , "AVERAGE"),
            ("max"  , "MAXIMUM"),
            ("last" , "LAST"),
            ("total", "TOTAL")]:
            c_lines.extend(
                [
                    "VDEF:{}{}={},{}".format(self.name, rep_name, self.name, cf),
                    "GPRINT:{}{}:<tt>%6.1lf%s</tt>{}".format(
                        self.name,
                        rep_name,
                        r"\l" if rep_name == "total" else r""
                    ),
                    # "VDEF:{}{}2={},{}".format(self.name, rep_name, self.name, cf),
                    "PRINT:{}{}:{}.{}=%.4lf".format(self.name, rep_name, self.key.replace(":", r"\:"), cf),
                ]
            )
        return c_lines
    @property
    def header_line(self):
        return "COMMENT:<tt>{}{}</tt>\\n".format(
            ("{{:<{:d}s}}".format(self.max_info_width + 2)).format("Description"),
            "".join(["{:9s}".format(rep_name) for rep_name in ["min", "ave", "max", "latest", "total"]])
        )

class RRDGraph(object):
    def __init__(self, log_com, colorzer, para_dict):
        self.log_com = log_com
        self.para_dict = {
            "size"       : "400x200",
            "graph_root" : global_config["GRAPH_ROOT"],
        }
        self.para_dict.update(para_dict)
        self.colorizer = colorzer
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.log_com(u"[RRDG] {}".format(what), log_level)
    def _create_graph_keys(self, graph_keys):
        # graph_keys ... list of keys
        first_level_keys = set([key.split(".")[0].split(":")[-1] for key in graph_keys])
        g_key_dict = dict([(flk, sorted([key for key in graph_keys if key.split(".")[0].split(":")[-1] == flk])) for flk in first_level_keys])
        return g_key_dict
    def get_def_idx(self):
        return len(self.defs) + 1
    def graph(self, vector_dict, dev_pks, graph_keys):
        timeframe = abs((self.para_dict["end_time"] - self.para_dict["start_time"]).total_seconds())
        graph_size = self.para_dict["size"]
        graph_width, graph_height = [int(value) for value in graph_size.split("x")]
        self.log("width / height : {:d} x {:d}, timeframe is {}".format(
            graph_width,
            graph_height,
            logging_tools.get_diff_time_str(timeframe),
        ))
        # store for DEF generation
        self.width = graph_width
        self.height = graph_height
        dev_dict = dict([(cur_dev.pk, unicode(cur_dev.full_name)) for cur_dev in device.objects.filter(Q(pk__in=dev_pks))])
        graph_key_dict = self._create_graph_keys(graph_keys)
        self.log("found device pks: {}".format(", ".join(["{:d}".format(pk) for pk in dev_pks])))
        self.log("graph keys: {}".format(", ".join(graph_keys)))
        self.log("top level keys (== distinct graphs): {:d}; {}".format(
            len(graph_key_dict),
            ", ".join(sorted(graph_key_dict)),
            ))

        graph_list = E.graph_list()
        for tlk in sorted(graph_key_dict):
            graph_keys = graph_key_dict[tlk]
            graph_name = "gfx_{}_{:d}.png".format(tlk, int(time.time()))
            abs_file_loc, rel_file_loc = (
                os.path.join(self.para_dict["graph_root"], graph_name),
                os.path.join("/{}/static/graphs/{}".format(settings.REL_SITE_ROOT, graph_name)),
            )
            dt_1970 = dateutil.parser.parse("1970-01-01 00:00 +0000")
            # clear list of defs
            self.defs = {}
            # reset colorizer for current graph
            self.colorizer.reset()
            rrd_pre_args = [
                    abs_file_loc,
                    "-E",
                    "-Rlight",
                    "-G",
                    "normal",
                    "-P",
                    # "-nDEFAULT:8:",
                    "-w {:d}".format(graph_width),
                    "-h {:d}".format(graph_height),
                    "-a"
                    "PNG",
                    "--daemon",
                    "unix:/var/run/rrdcached.sock",
                    "-W init.at clustersoftware",
                    "--slope-mode",
                    "-cBACK#ffffff",
                    "--end",
                    # offset to fix UTC, FIXME
                    "{:d}".format(int((self.para_dict["end_time"] - dt_1970).total_seconds())),
                    "--start",
                    "{:d}".format(int((self.para_dict["start_time"] - dt_1970).total_seconds())),
                    graph_var(self, None, "").header_line,
            ]
            for graph_key in sorted(graph_keys):
                for cur_pk in dev_pks:
                    dev_vector = vector_dict[cur_pk]
                    if graph_key.startswith("pde:"):
                        # performance data from icinga
                        def_xml = dev_vector.find(".//value[@name='{}']".format(graph_key))
                    else:
                        # machine vector entry
                        def_xml = dev_vector.find(".//mve[@name='{}']".format(graph_key))
                    if def_xml is not None:
                        self.defs[graph_key] = graph_var(self, def_xml, graph_key, dev_dict[cur_pk]).config
            if self.defs:
                draw_it = True
                removed_keys = set()
                while draw_it:
                    graph_keys = set(self.defs.keys())
                    rrd_args = rrd_pre_args + sum(self.defs.values(), [])
                    rrd_args.extend([
                        "--title",
                        "{} ({}, timeframe is {})".format(
                            tlk,
                            logging_tools.get_plural("result", len(self.defs)),
                            logging_tools.get_diff_time_str(timeframe)),
                    ])
                    try:
                        draw_result = rrdtool.graphv(*rrd_args)
                    except:
                        self.log("error creating graph: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                        if global_config["DEBUG"]:
                            pprint.pprint(rrd_args)
                    else:
                        res_dict = {value.split("=", 1)[0] : value.split("=", 1)[1] for key, value in draw_result.iteritems() if key.startswith("print[")}
                        # reorganize
                        val_dict = {}
                        for key, value in res_dict.iteritems():
                            cf = key.split(".")[-1]
                            try:
                                value = float(value)
                            except:
                                pass
                            else:
                                value = None if value == 0.0 else value
                            if value is not None:
                                val_dict.setdefault(key[:-len(cf) - 1], {})[cf] = value
                        empty_keys = set(graph_keys) - set(val_dict.keys())
                        if empty_keys:
                            self.log(
                                u"{}: {}".format(
                                    logging_tools.get_plural("empty key", len(empty_keys)),
                                    ", ".join(sorted(empty_keys)),
                                )
                            )
                            removed_keys |= empty_keys
                            self.defs = {key : value for key, value in self.defs.iteritems() if key not in empty_keys}
                        else:
                            draw_it = False
                graph_list.append(
                    E.graph(
                        E.removed_keys(
                            *[E.removed_key(_rk) for _rk in removed_keys]
                        ),
                        href=rel_file_loc,
                        **dict([(key, "{:d}".format(value) if type(value) in [int, long] else "{:.6f}".format(value)) for key, value in draw_result.iteritems() if not key.startswith("print[")])
                    )
                )
            else:
                self.log("no DEFs for graph_key_dict {}".format(tlk), logging_tools.LOG_LEVEL_ERROR)
        return graph_list

class graph_process(threading_tools.process_obj, threading_tools.operational_error_mixin):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context, init_logger=True)
        connection.close()
        self.register_func("graph_rrd", self._graph_rrd)
        self.register_func("xml_info", self._xml_info)
        self.vector_dict = {}
        self.graph_root = global_config["GRAPH_ROOT"]
        self.log("graphs go into {}".format(self.graph_root))
        self.colorizer = colorizer(self.log)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def loop_post(self):
        self._close()
        self.__log_template.close()
    def _close(self):
        pass
    def _xml_info(self, *args, **kwargs):
        dev_id, xml_str = (args[0], etree.fromstring(args[1]))
        self.vector_dict[dev_id] = xml_str # self._struct_vector(xml_str)
    def _graph_rrd(self, *args, **kwargs):
        src_id, srv_com = (args[0], server_command.srv_command(source=args[1]))
        dev_pks = [entry for entry in map(lambda x: int(x), srv_com.xpath(".//device_list/device/@pk", smart_strings=False)) if entry in self.vector_dict]
        graph_keys = sorted(srv_com.xpath(".//graph_key_list/graph_key/text()", smart_strings=False))
        para_dict = {}
        for para in srv_com.xpath(".//parameters", smart_strings=False)[0]:
            para_dict[para.tag] = para.text
        # cast to integer
        para_dict = dict([(key, int(value) if key in [] else value) for key, value in para_dict.iteritems()])
        for key in ["start_time", "end_time"]:
            # cast to datetime
            para_dict[key] = dateutil.parser.parse(para_dict[key])
        graph_list = RRDGraph(self.log, self.colorizer, para_dict).graph(self.vector_dict, dev_pks, graph_keys)
        srv_com["graphs"] = graph_list
        # print srv_com.pretty_print()
        srv_com.set_result(
            "generated {}".format(logging_tools.get_plural("graph", len(graph_list))),
            server_command.SRV_REPLY_STATE_OK
        )
        self.send_pool_message("send_command", src_id, unicode(srv_com))
