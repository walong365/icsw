#!/usr/bin/python-init -Ot
#
# Copyright (C) 2007,2008,2009,2013 Andreas Lang-Nevyjel, init.at
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
""" rrd-grapher for graphing rrd-data """

import sys
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

from django.conf import settings

import colorsys
import commands
import copy
import datetime
import getopt
import re
import socket
import stat
import pprint
import time
import zmq
from colour import Color
from lxml import etree
from lxml.builder import E

# import rrdtool
# import configfile
import logging_tools
import process_tools
import config_tools
import server_command
import threading_tools
import cluster_location
import uuid_tools
import configfile
import rrdtool
from django.db import connection, connections
from django.db.models import Q
try:
    from rrd_grapher.version import VERSION_STRING
except ImportError:
    VERSION_STRING = "?.?"
from initat.cluster.backbone.models import device

SERVER_COM_PORT = 8003
MAX_INFO_WIDTH = 42

class report_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config, db_con, log_queue):
        self.__db_con = db_con
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        threading_tools.thread_obj.__init__(self, "report", queue_size=100)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("report_latest_max_min_average", self._report_lmma)
        self.register_func("draw_graphs", self._draw_graphs)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (self.name, what, lev)))
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
    def loop_end(self):
        self.send_pool_message(("remove_pid", (self.name, self.pid)))
    def _report_lmma(self, (s_com, tcp_obj)):
        opt_dict = s_com.get_option_dict()
        needed_rrds = opt_dict["rrds"]
        node_list = s_com.get_nodes()
        node_res = dict([(node_name, "error not found") for node_name in node_list])
        dc = self.__db_con.get_connection(SQL_ACCESS)
        dc.execute("SELECT d.name, rs.* FROM device d, rrd_set rs WHERE d.device_idx=rs.device AND (%s)" % (" OR ".join(["d.name='%s'" % (node_name) for node_name in node_list])))
        report_devs = []
        local_dict = {}
        rrd_data_dict = {}
        for db_rec in dc.fetchall():
            if db_rec["name"] in node_res.keys():
                node_res[db_rec["name"]] = "ok"
                report_devs.append(db_rec["name"])
                local_dict[db_rec["name"]] = db_rec
        if local_dict:
            dc.execute("SELECT * FROM rrd_data WHERE (%s) AND (%s)" % (" OR ".join(["rrd_set=%d" % (value["rrd_set_idx"]) for value in local_dict.itervalues()]),
                                                                       " OR ".join(["descr='%s'" % (needed_rrd) for needed_rrd in needed_rrds])))
            for db_rec in dc.fetchall():
                rrd_data_dict.setdefault(db_rec["rrd_set"], {})[db_rec["descr"]] = db_rec
        start_time, end_time = (opt_dict["start_time"],
                                opt_dict["end_time"])
        report_start_time = time.time()
        self.log("fetching latest/max/min/average for %s on %s: %s" % (logging_tools.get_plural("rrd_data", len(needed_rrds)),
                                                                       logging_tools.get_plural("device", len(report_devs)),
                                                                       logging_tools.compress_list(report_devs)))
        dev_rep_dict = {}
        for report_dev in report_devs:
            rrd_set_idx = local_dict[report_dev]["rrd_set_idx"]
            dev_rep_dict[report_dev] = {}
            fetch_rrds = []
            for needed_rrd in needed_rrds:
                if rrd_data_dict.get(rrd_set_idx, {}).has_key(needed_rrd):
                    fetch_rrds.append(needed_rrd)
                else:
                    dev_rep_dict[report_dev][needed_rrd] = "error not present"
            if fetch_rrds:
                rrd_graph_args = ["/dev/null",
                                  "-s",
                                  "-%d" % (start_time * 60),
                                  "-e", "-%d" % (end_time * 60)]
                act_idx = 0
                for fetch_rrd in fetch_rrds:
                    full_path = "%s/%s/%s" % (self.__glob_config["RRD_DIR"],
                                              local_dict[report_dev]["filename"],
                                              self._get_path(rrd_data_dict[rrd_set_idx][fetch_rrd]))
                    act_idx += 1
                    # Minimum part
                    rrd_graph_args.extend(["DEF:min%d=%s:v0:MIN" % (act_idx, full_path),
                                           "VDEF:d%dmin=min%d,MINIMUM" % (act_idx, act_idx),
                                           "PRINT:d%dmin:min\:%s\:%%14.6le" % (act_idx, fetch_rrd)])
                    # Maximum part
                    rrd_graph_args.extend(["DEF:max%d=%s:v0:MAX" % (act_idx, full_path),
                                           "VDEF:d%dmax=max%d,MAXIMUM" % (act_idx, act_idx),
                                           "PRINT:d%dmax:max\:%s\:%%14.6le" % (act_idx, fetch_rrd)])
                    # Average part
                    rrd_graph_args.extend(["DEF:av%d=%s:v0:AVERAGE" % (act_idx, full_path),
                                           "VDEF:d%dav=av%d,AVERAGE" % (act_idx, act_idx),
                                           "PRINT:d%dav:average\:%s\:%%14.6le" % (act_idx, fetch_rrd)])
                    # Last part
                    rrd_graph_args.extend(["VDEF:d%dlast=av%d,LAST" % (act_idx, act_idx),
                                           "PRINT:d%dlast:last\:%s\:%%14.6le" % (act_idx, fetch_rrd)])
                    # Total part
                    rrd_graph_args.extend(["VDEF:d%dtotal=av%d,TOTAL" % (act_idx, act_idx),
                                           "PRINT:d%dtotal:total\:%s\:%%14.6le" % (act_idx, fetch_rrd)])
                # print rrd_graph_args
                try:
                    rrd_res = rrdtool.graph(*rrd_graph_args)
                except:
                    self.log("Error fetching graph info: %s" % (process_tools.get_except_info()),
                             logging_tools.LOG_LEVEL_ERROR)
                    for fetch_rrd in fetch_rrds:
                        dev_rep_dict[report_dev][fetch_rrds] = "error fetching"
                else:
                    size_x, size_y, out_list = rrd_res
                    for f_type, fetch_rrd, value_str in [x.split(":") for x in out_list]:
                        if value_str.strip().lower() == "nan":
                            value = "nan"
                        else:
                            try:
                                value = float(value_str)
                            except:
                                value = None
                        dev_rep_dict[report_dev].setdefault(fetch_rrd, {})[f_type] = value
                        # print "\n".join(out_list)
        report_end_time = time.time()
        self.log("fetching on %s took %s" % (logging_tools.get_plural("device", len(report_devs)),
                                             logging_tools.get_diff_time_str(report_end_time - report_start_time)))
        tcp_obj.add_to_out_buffer(server_command.server_reply(state=server_command.SRV_REPLY_STATE_OK,
                                                              result="ok fetched",
                                                              node_results=node_res,
                                                              node_dicts=dev_rep_dict))
    def _get_path(self, rrd_data):
        valid_descrs = [l_d.replace("/", "") for l_d in [rrd_data["descr1"],
                                                         rrd_data["descr2"],
                                                         rrd_data["descr3"],
                                                         rrd_data["descr4"]] if l_d]
        return "%s/%s.rrd" % ("/".join(valid_descrs[:-1]),
                              valid_descrs[-1])
    def _draw_graphs(self, my_arg):
        srv_com, tcp_obj = my_arg
        node_list, opt_dict = (srv_com.get_nodes(),
                               srv_com.get_option_dict())
        rrd_options = opt_dict["rrd_options"]
        rrd_compounds = opt_dict["rrd_compounds"]
        node_res = dict([(node_name, "error not found") for node_name in node_list])
        dc = self.__db_con.get_connection(SQL_ACCESS)
        dc.execute("SELECT d.name, rs.* FROM device d, rrd_set rs WHERE d.device_idx=rs.device AND (%s)" % (" OR ".join(["d.name='%s'" % (node_name) for node_name in node_list])))
        report_devs = []
        local_dict = {}
        rrd_data_dict = {}
        for db_rec in dc.fetchall():
            if db_rec["name"] in node_res.keys():
                node_res[db_rec["name"]] = "ok"
                report_devs.append(db_rec["name"])
                local_dict[db_rec["name"]] = db_rec
        all_rrd_descrs = sum([rrd_compounds[name] for name in rrd_compounds["compound_list"]], [])
        if local_dict:
            sql_str = "SELECT * FROM rrd_data WHERE (%s) AND (%s)" % (" OR ".join(["rrd_set=%d" % (value["rrd_set_idx"]) for value in local_dict.itervalues()]),
                                                                      " OR ".join(["descr='%s'" % (descr) for descr in all_rrd_descrs]))
            dc.execute(sql_str)
            for db_rec in dc.fetchall():
                rrd_data_dict.setdefault(db_rec["rrd_set"], {})[db_rec["descr"]] = db_rec
        pprint.pprint(local_dict)
        pprint.pprint(rrd_data_dict)
        needed_rrds = opt_dict["rrds"]
        start_time, end_time = (opt_dict["start_time"],
                                opt_dict["end_time"])
        graph_width, graph_height = (opt_dict["width"],
                                     opt_dict["height"])
        draw_start_time = time.time()
        self.log("drawing graphs for %s on %s: %s" % (logging_tools.get_plural("rrd_data", len(needed_rrds)),
                                                      logging_tools.get_plural("device", len(report_devs)),
                                                      logging_tools.compress_list(report_devs)))
        compound_results = {}
        g_idx = 0
        for comp_name in rrd_compounds["compound_list"]:
            compound_results[comp_name] = {}
            comp_list = rrd_compounds[comp_name]
            g_idx += 1
            for report_dev in report_devs:
                rrd_set_idx = local_dict[report_dev]["rrd_set_idx"]
                fetch_rrds = []
                for needed_rrd in comp_list:
                    if rrd_data_dict.get(rrd_set_idx, {}).has_key(needed_rrd):
                        fetch_rrds.append(needed_rrd)
                    else:
                        self.log("device %s: rrd %s not present" % (report_dev,
                                                                    needed_rrd),
                                 logging_tools.LOG_LEVEL_WARN)
                        compound_results[comp_name][report_dev] = "error not present"
                if fetch_rrds:
                    dev_options = opt_dict.get("device_options", {}).get(report_dev, {})
                    graph_file_name = "%s/graph_%d" % (self.__glob_config["RRD_DIR"], g_idx)
                    abs_start_time = time.localtime(time.time() - start_time * 60)
                    abs_end_time = time.localtime(time.time() - end_time * 60)
                    start_form_str = "%a, %d. %b %Y %H:%M:%S"
                    if abs_start_time[0:3] == abs_end_time[0:3]:
                        end_form_str = "%H:%M:%S"
                    elif abs_start_time[0] == abs_end_time[0]:
                        end_form_str = "%a, %d. %b %H:%M:%S"
                    else:
                        end_form_str = "%a, %d. %b %Y %H:%M:%S"
                    rrd_graph_args = [graph_file_name,
                                      "-t %s on %s (from %s to %s)" % (comp_name,
                                                                       report_dev,
                                                                       time.strftime(start_form_str, abs_start_time),
                                                                       time.strftime(end_form_str, abs_end_time)),
                                      "-s -%d" % (start_time * 60),
                                      "-e -%d" % (end_time * 60),
                                      "-E",
                                      "-w %d" % (graph_width),
                                      "-h %d" % (graph_height),
                                      "-W init.at Clustersoftware",
                                      "-c",
                                      "BACK#ffffff"]
                    # any DEFs defined ?
                    any_defs_defined = False
                    if dev_options:
                        # draw hbars
                        if dev_options.has_key("hbars"):
                            check_keys = [x for x in dev_options["hbars"].keys() if x in comp_list]
                            hbar_list = sum([dev_options["hbars"][ck] for ck in check_keys], [])
                            if hbar_list:
                                for act_pri in sorted(set([(x["pri"]) for x in hbar_list])):
                                    for draw_hbar in [x for x in hbar_list if x["pri"] == act_pri]:
                                        if draw_hbar.has_key("upper"):
                                            rrd_graph_args.extend(["LINE0:%.7f#%s" % (draw_hbar["lower"],
                                                                                      draw_hbar["color"]),
                                                                   "AREA:%.7f#%s::STACK" % (draw_hbar["upper"] - draw_hbar["lower"],
                                                                                            draw_hbar["color"])])
                                            if draw_hbar.get("outline", False):
                                                rrd_graph_args.extend(["LINE1:%.7f#000000" % (draw_hbar["lower"]),
                                                                       "LINE1:%.7f#000000" % (draw_hbar["upper"])])
                                        else:
                                            rrd_graph_args.extend(["HRULE:%.7f#%s" % (draw_hbar["lower"],
                                                                                      draw_hbar["color"])])
                    # get longest descr
                    max_descr_len = 0
                    for draw_mode in ["AREAOUTLINE", "AREA", "LINE3", "LINE2", "LINE1"]:
                        for fetch_rrd in fetch_rrds:
                            rrd_option = rrd_options[fetch_rrd]
                            if not rrd_option.has_key("descr"):
                                rrd_option["descr"] = fetch_rrd
                            if rrd_option["mode"] == draw_mode:
                                for mma in ["max", "average", "min"]:
                                    if rrd_option[mma]:
                                        max_descr_len = max(max_descr_len, len(rrd_option["descr"]) + len(mma) + 3)
                    act_idx = 0
                    for draw_mode in ["AREAOUTLINE", "AREA", "LINE3", "LINE2", "LINE1"]:
                        for fetch_rrd in fetch_rrds:
                            rrd_option = rrd_options[fetch_rrd]
                            if not rrd_option.has_key("descr"):
                                rrd_option["descr"] = fetch_rrd
                            if rrd_option["mode"] == draw_mode:
                                full_path = "%s/%s/%s" % (self.__glob_config["RRD_DIR"],
                                                          local_dict[report_dev]["filename"],
                                                          self._get_path(rrd_data_dict[rrd_set_idx][fetch_rrd]))
                                if os.path.isfile(full_path):
                                    act_idx += 1
                                    # Minimum part
                                    for mma in ["max", "average", "min"]:
                                        if rrd_option[mma]:
                                            any_defs_defined = True
                                            rrd_graph_args.extend(self._create_draw_args(act_idx, full_path, rrd_option, mma, max_descr_len))
                                else:
                                    self.log("[%s] rrd %s not found, skipping" % (report_dev,
                                                                                  full_path),
                                             logging_tools.LOG_LEVEL_ERROR)
                    if dev_options:
                        # draw vrules
                        if dev_options.has_key("vrules"):
                            # build legend dict
                            l_dict = {}
                            for vr_time, vr_options in dev_options["vrules"].iteritems():
                                act_text = vr_options.get("text", "")
                                if act_text:
                                    if l_dict.has_key(act_text):
                                        l_dict[act_text] += 1
                                    else:
                                        l_dict[act_text] = 1
                            for text in l_dict.keys():
                                if l_dict[text] > 1:
                                    l_dict[text] = "%s (x %d)" % (text, l_dict[text])
                                else:
                                    l_dict[text] = text
                            for vr_time, vr_options in dev_options["vrules"].iteritems():
                                act_text = vr_options.get("text", "")
                                if act_text and l_dict.has_key(act_text):
                                    print_text = l_dict[act_text]
                                    del l_dict[act_text]
                                    act_text = print_text
                                else:
                                    act_text = ""
                                rrd_graph_args.append("VRULE:%d#%s%s" % (vr_time,
                                                                         vr_options.get("color", "000000"),
                                                                         act_text and ":%s" % (act_text) or ""))
                    # print " ".join(rrd_graph_args)
                    # print rrd_graph_args
                    if any_defs_defined:
                        draw_time_start = time.time()
                        try:
                            rrd_res = rrdtool.graph(*rrd_graph_args)
                        except:
                            self.log("[%s] Error fetching graph info: %s" % (report_dev,
                                                                             process_tools.get_except_info()),
                                     logging_tools.LOG_LEVEL_ERROR)
                            compound_results[comp_name][report_dev] = "error file not found"
                        else:
                            draw_time_end = time.time()
                            self.log("[%s] Creating the graph in %s resulted in %s" % (report_dev,
                                                                                       logging_tools.get_diff_time_str(draw_time_end - draw_time_start),
                                                                                       str(rrd_res)))
                            if os.path.isfile(graph_file_name):
                                compound_results[comp_name][report_dev] = file(graph_file_name, "r").read()
                            else:
                                compound_results[comp_name][report_dev] = "error file not found"
                    else:
                        self.log("[%s] no DEFs defined" % (report_dev),
                                 logging_tools.LOG_LEVEL_ERROR)
                        compound_results[comp_name][report_dev] = "error no DEFs defined"
                else:
                    compound_results[comp_name][report_dev] = "error no RRAs found"
        draw_end_time = time.time()
        self.log("fetching on %s took %s" % (logging_tools.get_plural("device", len(report_devs)),
                                             logging_tools.get_diff_time_str(draw_end_time - draw_start_time)))
        dc.release()
        tcp_obj.add_to_out_buffer(server_command.server_reply(state=server_command.SRV_REPLY_STATE_OK,
                                                              result="ok drawn",
                                                              node_results=node_res,
                                                              option_dict=compound_results),
                                  "draw_graph")
    def _create_draw_args(self, act_idx, full_path, rrd_option, mma, max_len):
        mma_short = {"average" : "aver"}.get(mma, mma)
        act_color = rrd_option["color"]
        if mma in ["min", "max"]:
            # modify colors for min/max
            hue, lev, sat = colorsys.rgb_to_hls(*[float(int(x, 16)) / 256. for x in [act_color[0:2], act_color[2:4], act_color[4:]]])
            if mma == "min":
                hue -= 0.1
            else:
                hue += 0.1
            act_color = "".join(["%02x" % (x * 255) for x in list(colorsys.hls_to_rgb(max(min(hue, 1), 0), lev, sat))])
        act_dat_name = "%s%d" % (mma, act_idx)
        ret_f = ["DEF:%s=%s:v0:%s" % (act_dat_name,
                                      full_path,
                                      mma.upper())]
        if full_path.count("/net/"):
            # cap Network readings above  1 GB/s to zero
            new_dat_name = "n%s" % (act_dat_name)
            if full_path.count("/eth"):
                cap_val = 120000000
            else:
                cap_val = 1000000000
            ret_f.extend(["CDEF:%s=%d,%s,GT,%s,PREV,IF" % (new_dat_name,
                                                           cap_val,
                                                           act_dat_name,
                                                           act_dat_name)])
            act_dat_name = new_dat_name
        report_names = {"max"   : "%smax" % (act_dat_name),
                        "min"   : "%smin" % (act_dat_name),
                        "ave"   : "%save" % (act_dat_name),
                        "last"  : "%slast" % (act_dat_name),
                        "total" : "%stotal" % (act_dat_name)}
        ret_f.extend(["VDEF:%s=%s,MAXIMUM" % (report_names["max"],
                                              act_dat_name),
                      "VDEF:%s=%s,MINIMUM" % (report_names["min"],
                                              act_dat_name),
                      "VDEF:%s=%s,AVERAGE" % (report_names["ave"],
                                              act_dat_name),
                      "VDEF:%s=%s,LAST" % (report_names["last"],
                                           act_dat_name),
                      "VDEF:%s=%s,TOTAL" % (report_names["total"],
                                            act_dat_name)])
        if rrd_option.get("invert", False):
            new_dat_name = "i%s" % (act_dat_name)
            ret_f.extend(["CDEF:%s=-1,%s,*" % (new_dat_name,
                                               act_dat_name)])
            act_dat_name = new_dat_name
        smooth_minutes = rrd_option.get("smooth", 0)
        if smooth_minutes:
            new_dat_name = "s%s" % (act_dat_name)
            ret_f.extend(["CDEF:%s=%s,%d,TREND" % (new_dat_name,
                                                   act_dat_name,
                                                   smooth_minutes * 60)])
            act_dat_name = new_dat_name
        act_mode = rrd_option["mode"]
        if act_mode == "AREAOUTLINE":
            ret_f.extend(["%s:%s#%s:%s" % ("AREA",
                                           act_dat_name,
                                           act_color,
                                           ("%%-%ds" % (max_len)) % ("%s (%s)" % (rrd_option["descr"], mma_short))),
                          "%s:%s#%s" % ("LINE1",
                                        act_dat_name,
                                        "000000")])
        else:
            ret_f.extend(["%s:%s#%s:%s" % (rrd_option["mode"],
                                           act_dat_name,
                                           act_color,
                                           ("%%-%ds" % (max_len)) % ("%s (%s)" % (rrd_option["descr"], mma_short)))])
        ret_f.extend(["GPRINT:%s:max %%6.1lf%%s" % (report_names["max"]),
                      "GPRINT:%s:min %%6.1lf%%s" % (report_names["min"]),
                      "GPRINT:%s:average %%6.1lf%%s" % (report_names["ave"]),
                      "GPRINT:%s:last %%6.1lf%%s" % (report_names["last"]),
                      "GPRINT:%s:total %%6.1lf%%s\l" % (report_names["total"])])
        return ret_f

class colorizer(object):
    def __init__(self, g_proc):
        self.graph_process = g_proc
        self.def_color_table = "dark28"
        self._read_files()
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.graph_process.log("[col] %s" % (what), log_level)
    def _read_files(self):
        self.colortables = etree.fromstring(file(global_config["COLORTABLE_FILE"], "r").read())
        self.color_tables = {}
        for c_table in self.colortables.findall(".//colortable[@name]"):
            self.color_tables[c_table.get("name")] = ["#%s" % (color.get("rgb")) for color in c_table if self._check_color(color)]
        self.log("read colortables from %s" % (global_config["COLORTABLE_FILE"]))
        self.color_rules = etree.fromstring(file(global_config["COLORRULES_FILE"], "r").read())
        self.log("read colorrules from %s" % (global_config["COLORRULES_FILE"]))
        self.match_re_keys = [
            (re.compile("^%s" % (entry.attrib["key"].replace(".", r"\."))),
             entry) for entry in self.color_rules.xpath(".//entry[@key]")]
        # fast lookup table, store computed lookups
        self.fast_lut = {}
    def _check_color(self, color):
        cur_c = "#%s" % (color.get("rgb"))
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
        return self.color_tables[t_name][self.table_offset[t_name]], s_dict
    def get_table_name(self, entry):
        s_dict = {}
        key_name = entry.get("full", entry.get("name"))
        if key_name not in self.fast_lut:
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
    var_idx = 0
    def __init__(self, entry, dev_name=""):
        self.entry = entry
        self.dev_name = dev_name
        graph_var.var_idx += 1
        self.name = "v%d" % (graph_var.var_idx)
    def __getitem__(self, key):
        return self.entry.attrib[key]
    def __contains__(self, key):
        return key in self.entry.attrib
    def get(self, key, default):
        return self.entry.attrib.get(key, default)
    @staticmethod
    def init(clrz):
        graph_var.var_idx = 0
        graph_var.colorizer = clrz
        graph_var.colorizer.reset()
    @property
    def info(self):
        info = self["info"]
        parts = self["name"].split(".")
        for idx in xrange(len(parts)):
            info = info.replace("$%d" % (idx + 1), parts[idx])
        if self.dev_name:
            info = "%s (%s)" % (info, str(self.dev_name))
        return info
    def get_color_and_style(self):
        self.color, self.style_dict = graph_var.colorizer.get_color_and_style(self.entry)
    @property
    def config(self):
        self.get_color_and_style()
        if self.entry.tag == "value":
            # pde entry
            c_lines = [
                "DEF:%s=%s:%s:AVERAGE" % (self.name, self.entry.getparent().get("file_name"), self["name"]),
            ]
        else:
            c_lines = [
                "DEF:%s=%s:v:AVERAGE" % (self.name, self["file_name"]),
            ]
        if int(self.get("invert", "0")):
            c_lines.append(
                "CDEF:%sinv=%s,-1,*" % (self.name, self.name),
            )
            draw_name = "%sinv" % (self.name)
        else:
            draw_name = self.name
        c_lines.append(
            "%s:%s%s:<tt>%s</tt>" % (
                self.style_dict.get("draw_type", "LINE1"),
                draw_name,
                self.color,
                ("%%-%ds" % (MAX_INFO_WIDTH)) % (self.info)[:MAX_INFO_WIDTH]),
        )
        for rep_name, cf in [
            ("min"  , "MINIMUM"),
            ("ave"  , "AVERAGE"),
            ("max"  , "MAXIMUM"),
            ("last" , "LAST"),
            ("total", "TOTAL")]:
            c_lines.extend(
                [
                    "VDEF:%s%s=%s,%s" % (self.name, rep_name, self.name, cf),
                    "GPRINT:%s%s:<tt>%%6.1lf%%s</tt>%s" % (
                        self.name, rep_name,
                        r"\l" if rep_name == "total" else r""
                        ),
                ]
            )
        return c_lines
    @property
    def header_line(self):
        return "COMMENT:<tt>%s%s</tt>" % (
            ("%%-%ds" % (MAX_INFO_WIDTH + 2)) % ("value"),
            "".join(["%9s" % (rep_name) for rep_name in ["min", "ave", "max", "latest", "total"]])
        )

class graph_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context, init_logger=True)
        self.register_func("graph_rrd", self._graph_rrd)
        self.register_func("xml_info", self._xml_info)
        self.raw_vector_dict, self.vector_dict = ({}, {})
        self.graph_root = global_config["GRAPH_ROOT"]
        self.log("graphs go into %s" % (self.graph_root))
        self.colorizer = colorizer(self)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def loop_post(self):
        self._close()
        self.__log_template.close()
    def _close(self):
        pass
    def _xml_info(self, *args, **kwargs):
        dev_id, xml_str = (args[0], etree.fromstring(args[1]))
        # needed ?
        self.raw_vector_dict[dev_id] = xml_str
        self.vector_dict[dev_id] = self._struct_vector(xml_str)
    def _struct_vector(self, cur_xml):
        # somehow related to struct_xml_vector
        all_keys = set(cur_xml.xpath(".//mve/@name"))
        xml_vect, lu_dict = (E.machine_vector(), {})
        for key in sorted(all_keys):
            parts = key.split(".")
            s_dict, s_xml = (lu_dict, xml_vect)
            for part in parts:
                if part not in s_dict:
                    new_el = E.entry(part=part, full=part)
                    s_xml.append(new_el)
                    s_dict[part] = (new_el, {})
                s_xml, s_dict = s_dict[part]
            add_entry = copy.deepcopy(cur_xml.find(".//mve[@name='%s']" % (key)))
            s_xml.append(add_entry)
        # remove structural entries with only one mve-child
        for struct_ent in xml_vect.xpath(".//entry[not(entry)]"):
            parent = struct_ent.getparent()
            parent.append(struct_ent[0])
            parent.remove(struct_ent)
        # set full names
        for ent in xml_vect.xpath(".//entry"):
            cur_p = ent.getparent()
            if cur_p.tag == "entry":
                ent.attrib["full"] = "%s.%s" % (cur_p.attrib["full"], ent.attrib["full"])
        # add pde entries
        pde_keys = set(cur_xml.xpath(".//pde/@name"))
        for key in sorted(pde_keys):
            cur_el = cur_xml.find(".//pde[@name='%s']" % (key))
            new_el = E.entry(name=key, part=key, file_name=cur_el.get("file_name"))
            xml_vect.append(new_el)
            for sub_val in cur_el:
                new_val = copy.deepcopy(sub_val)
                new_val.attrib["full"] = "%s.%s" % (new_el.get("name"), new_val.get("name"))
                new_el.append(new_val)
        return xml_vect
    def _create_graph_keys(self, graph_keys):
        # graph_keys ... list of keys
        first_level_keys = set([key.split(".")[0] for key in graph_keys])
        g_key_dict = dict([(flk, sorted([key for key in graph_keys if key.split(".")[0] == flk])) for flk in first_level_keys])
        return g_key_dict
    def _graph_rrd(self, *args, **kwargs):
        src_id, srv_com = (args[0], server_command.srv_command(source=args[1]))
        dev_pks = [entry for entry in map(lambda x: int(x), srv_com.xpath(None, ".//device_list/device/@pk")) if entry in self.vector_dict]
        dev_dict = dict([(cur_dev.pk, unicode(cur_dev.full_name)) for cur_dev in device.objects.filter(Q(pk__in=dev_pks))])
        graph_keys = sorted(srv_com.xpath(None, ".//graph_key_list/graph_key/text()"))
        graph_key_dict = self._create_graph_keys(graph_keys)
        self.log("found device pks: %s" % (", ".join(["%d" % (pk) for pk in dev_pks])))
        self.log("graph keys: %s" % (", ".join(graph_keys)))
        self.log("top level keys (== distinct graphs): %d" % (len(graph_key_dict)))
        para_dict = {
            "size" : "400x200",
        }
        for para in srv_com.xpath(None, ".//parameters")[0]:
            para_dict[para.tag] = para.text
        # cast to integer
        para_dict = dict([(key, int(value) if key in [] else value) for key, value in para_dict.iteritems()])
        for key in ["start_time", "end_time"]:
            # cast to datetime
            para_dict[key] = datetime.datetime.strptime(para_dict[key], "%Y-%m-%d %H:%M")
        para_dict["timeframe"] = abs((para_dict["end_time"] - para_dict["start_time"]).total_seconds())
        graph_list = E.graph_list()
        multi_dev_mode = len(dev_pks) > 1
        for tlk in sorted(graph_key_dict):
            graph_keys = graph_key_dict[tlk]
            graph_name = "gfx_%s_%d.png" % (tlk, int(time.time()))
            abs_file_loc, rel_file_loc = (
                os.path.join(self.graph_root, graph_name),
                os.path.join("/%s/graphs/%s" % (settings.REL_SITE_ROOT, graph_name)),
            )
            dt_1970 = datetime.datetime(1970, 1, 1)
            rrd_args = [
                    abs_file_loc,
                    "-E",
                    "-Rlight",
                    "-G",
                    "normal",
                    "-P",
                    # "-nDEFAULT:8:",
                    "-w %d" % (int(para_dict["size"].split("x")[0])),
                    "-h %d" % (int(para_dict["size"].split("x")[1])),
                    "-a"
                    "PNG",
                    "--daemon",
                    "unix:/var/run/rrdcached.sock",
                    "-W init.at clustersoftware",
                    "--slope-mode",
                    "-cBACK#ffffff",
                    "--end",
                    # offset to fix UTC, FIXME
                    "%d" % ((para_dict["end_time"] - dt_1970).total_seconds() - 2 * 3600),
                    "--start",
                    "%d" % ((para_dict["start_time"] - dt_1970).total_seconds() - 2 * 3600),
                    graph_var(None, "").header_line,
            ]
            graph_var.init(self.colorizer)
            for graph_key in sorted(graph_keys):
                for cur_pk in dev_pks:
                    dev_vector = self.vector_dict[cur_pk]
                    graph_mve = dev_vector.find(".//mve[@name='%s']" % (graph_key))
                    if graph_mve is not None:
                        rrd_args.extend(graph_var(graph_mve, dev_dict[cur_pk]).config)
                    graph_pde = dev_vector.find(".//value[@full='%s']" % (graph_key))
                    if graph_pde is not None:
                        rrd_args.extend(graph_var(graph_pde, dev_dict[cur_pk]).config)
            if graph_var.var_idx:
                rrd_args.extend([
                    "--title",
                    "%s (%s, %s)" % (
                                     tlk,
                                     logging_tools.get_plural("DEF", graph_var.var_idx),
                                     logging_tools.get_diff_time_str(para_dict["timeframe"])),
                ])
                try:
                    draw_result = rrdtool.graphv(*rrd_args)
                except:
                    self.log("error creating graph: %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                    if global_config["DEBUG"]:
                        pprint.pprint(rrd_args)
                else:
                    graph_list.append(
                        E.graph(
                            href=rel_file_loc,
                            **dict([(key, "%d" % (value) if type(value) in [int, long] else "%.6f" % (value)) for key, value in draw_result.iteritems()])
                        )
                    )
            else:
                self.log("no DEFs", logging_tools.LOG_LEVEL_ERROR)
        srv_com["graphs"] = graph_list
        # print srv_com.pretty_print()
        srv_com.set_result(
            "generated %s" % (logging_tools.get_plural("graph", len(graph_list))),
            server_command.SRV_REPLY_STATE_OK)
        self.send_pool_message("send_command", src_id, unicode(srv_com))

class data_store(object):
    def __init__(self, cur_dev):
        self.pk = cur_dev.pk
        self.name = unicode(cur_dev.full_name)
        # name of rrd-files on disk
        self.store_name = ""
        self.xml_vector = E.machine_vector()
    def restore(self):
        try:
            self.xml_vector = etree.fromstring(file(self.data_file_name(), "r").read())
        except:
            self.log("cannot interpret XML: %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            self.xml_vector = E.machine_vector()
        else:
            # for pure-pde vectors no store name is set
            self.store_name = self.xml_vector.attrib.get("store_name", "")
        # send a copy to the grapher
        self.sync_to_grapher()
    def feed(self, in_vector):
        # self.xml_vector = in_vector
        if self.store_name != in_vector.attrib["name"]:
            self.log("changing store_name from '%s' to '%s'" % (
                self.store_name,
                in_vector.attrib["name"]))
            self.store_name = in_vector.attrib["name"]
            self.xml_vector.attrib["store_name"] = self.store_name
        old_keys = set(self.xml_vector.xpath(".//mve/@name"))
        rrd_dir = global_config["RRD_DIR"]
        for entry in in_vector.findall("mve"):
            cur_name = entry.attrib["name"]
            cur_entry = self.xml_vector.find("mve[@name='%s']" % (cur_name))
            if not cur_entry:
                cur_entry = E.mve(
                    name=cur_name,
                    sane_name=cur_name.replace("/", "_sl_"),
                    init_time="%d" % (time.time()),
                )
                self.xml_vector.append(cur_entry)
            self._update_entry(cur_entry, entry, rrd_dir)
        new_keys = set(self.xml_vector.xpath(".//mve/@name"))
        c_keys = old_keys ^ new_keys
        if c_keys:
            self.log("mve: %d keys total, %d keys changed" % (len(new_keys), len(c_keys)))
        else:
            self.log("mve: %d keys total" % (len(new_keys)))
        self.store_info()
    def feed_pd(self, host_name, pd_type, pd_info):
        # we ignore the global store name for perfdata stores
        old_keys = set(self.xml_vector.xpath(".//pde/@name"))
        rrd_dir = global_config["RRD_DIR"]
        # only one entry
        cur_entry = self.xml_vector.find("pde[@name='%s']" % (pd_type))
        if not cur_entry:
            # create new entry
            cur_entry = E.pde(
                name=pd_type,
                host=host_name,
                init_time="%d" % (time.time()),
            )
            for cur_idx, entry in enumerate(pd_info):
                cur_entry.append(
                    E.value(
                        name=entry.get("name"),
                    )
                )
            self.xml_vector.append(cur_entry)
        self._update_pd_entry(cur_entry, pd_info, rrd_dir)
        new_keys = set(self.xml_vector.xpath(".//pde/@name"))
        c_keys = old_keys ^ new_keys
        if c_keys:
            self.log("pde: %d keys total, %d keys changed" % (len(new_keys), len(c_keys)))
        # else:
        #    too verbose
        #    self.log("pde: %d keys total" % (len(new_keys)))
        self.store_info()
    def _update_pd_entry(self, entry, src_entry, rrd_dir):
        entry.attrib["last_update"] = "%d" % (time.time())
        entry.attrib["file_name"] = os.path.join(
            rrd_dir,
            entry.get("host"),
            "perfdata",
            "ipd_%s.rrd" % (entry.get("name"))
        )
        if len(entry) == len(src_entry):
            for v_idx, (cur_value, src_value) in enumerate(zip(entry, src_entry)):
                for key, def_value in [
                    ("info"  , "performance_data"),
                    ("v_type", "f"),
                    ("unit"  , "1"),
                    ("name"  , None),
                    ("index" , "%d" % (v_idx))]:
                    cur_value.attrib[key] = src_value.get(key, def_value)
    def _update_entry(self, entry, src_entry, rrd_dir):
        for key, def_value in [
            ("info"  , None),
            ("v_type", None),
            ("full"  , entry.get("name")),
            ("unit"  , "1"),
            ("base"  , "1"),
            ("factor", "1")]:
            entry.attrib[key] = src_entry.get(key, def_value)
        # last update time
        entry.attrib["last_update"] = "%d" % (time.time())
        entry.attrib["file_name"] = os.path.join(rrd_dir, self.store_name, "collserver", "icval-%s.rrd" % (entry.attrib["sane_name"]))
    def store_info(self):
        file(self.data_file_name(), "wb").write(etree.tostring(self.xml_vector, pretty_print=True))
        self.sync_to_grapher()
    def sync_to_grapher(self):
        data_store.process.send_to_process("graph", "xml_info", self.pk, etree.tostring(self.xml_vector))
    def data_file_name(self):
        return os.path.join(data_store.store_dir, "%s_%d.info.xml" % (self.name, self.pk))
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        data_store.process.log("[ds %s] %s" % (
            self.name,
            what), log_level)
    @staticmethod
    def has_rrd_xml(dev_pk):
        return dev_pk in data_store.__devices
    def struct_xml_vector(self):
        cur_xml = self.xml_vector
        all_keys = set(cur_xml.xpath(".//mve/@name"))
        xml_vect, lu_dict = (E.machine_vector(), {})
        for key in sorted(all_keys):
            parts = key.split(".")
            s_dict, s_xml = (lu_dict, xml_vect)
            for part in parts:
                if part not in s_dict:
                    new_el = E.entry(part=part)
                    s_xml.append(new_el)
                    s_dict[part] = (new_el, {})
                s_xml, s_dict = s_dict[part]
            add_entry = copy.deepcopy(cur_xml.find(".//mve[@name='%s']" % (key)))
            # remove unneded entries
            for rem_attr in ["file_name", "last_update", "sane_name"]:
                if rem_attr in add_entry.attrib:
                    del add_entry.attrib[rem_attr]
            if "info" in add_entry.attrib:
                add_entry.attrib["info"] = self._expand_info(add_entry)
            s_xml.append(add_entry)
        # remove structural entries with only one mve-child
        for struct_ent in xml_vect.xpath(".//entry[not(entry)]"):
            parent = struct_ent.getparent()
            parent.append(struct_ent[0])
            parent.remove(struct_ent)
        # print etree.tostring(xml_vect, pretty_print=True)
         # add pde entries
        pde_keys = set(cur_xml.xpath(".//pde/@name"))
        for key in sorted(pde_keys):
            new_el = E.entry(name=key, part=key)
            xml_vect.append(new_el)
            for sub_val in cur_xml.find(".//pde[@name='%s']" % (key)):
                new_val = copy.deepcopy(sub_val)
                new_val.attrib["name"] = "%s.%s" % (new_el.get("name"), new_val.get("name"))
                new_el.append(new_val)
        return xml_vect
    @staticmethod
    def merge_node_results(res_list):
        if len(res_list) > 1:
            # print etree.tostring(res_list, pretty_print=True)
            # remove empty node_results
            empty_nodes = 0
            for entry in res_list:
                if len(entry) == 0:
                    empty_nodes += 1
                    entry.getparent().remove(entry)
            data_store.g_log("merging %s (%s empty)" % (logging_tools.get_plural("node result", len(res_list)),
                                                        logging_tools.get_plural("entry", empty_nodes)))
            first_mv = res_list[0][0]
            ref_dict = {"mve" : {}, "value" : {}}
            for val_el in first_mv.xpath(".//*"):
                if val_el.tag in ["value", "mve"]:
                    ref_dict[val_el.tag][val_el.get("name")] = val_el
                val_el.attrib["devices"] = "1"
            # pprint.pprint(ref_dict)
            for other_node in res_list[1:]:
                if len(other_node):
                    other_mv = other_node[0]
                    for add_el in other_mv.xpath(".//mve|.//value"):
                        add_tag, add_name = (add_el.tag, add_el.get("name"))
                        ref_el = ref_dict[add_tag].get(add_name)
                        if ref_el is not None:
                            new_count = int(ref_el.get("devices")) + 1
                            while "devices" in ref_el.attrib:
                                if int(ref_el.get("devices")) < new_count:
                                    ref_el.attrib["devices"] = "%d" % (new_count)
                                # increase all above me
                                ref_el = ref_el.getparent()
                        else:
                            print "***", add_tag, add_name
                other_node.getparent().remove(other_node)
        # print etree.tostring(res_list, pretty_print=True)
    def _expand_info(self, entry):
        info = entry.attrib["info"]
        parts = entry.attrib["name"].split(".")
        for idx in xrange(len(parts)):
            info = info.replace("$%d" % (idx + 1), parts[idx])
        return info
    @staticmethod
    def get_rrd_xml(dev_pk, sort=False):
        if sort:
            return data_store.__devices[dev_pk].struct_xml_vector()
        else:
            # do a deepcopy (just to be sure)
            return copy.deepcopy(data_store.__devices[dev_pk].xml_vector)
    @staticmethod
    def setup(srv_proc):
        data_store.process = srv_proc
        data_store.g_log("init")
        data_store.debug = global_config["DEBUG"]
        # pk -> data_store
        data_store.__devices = {}
        data_store.store_dir = os.path.join(global_config["RRD_DIR"], "data_store")
        if not os.path.isdir(data_store.store_dir):
            os.mkdir(data_store.store_dir)
        entry_re = re.compile("^(?P<full_name>.*)_(?P<pk>\d+).info.xml$")
        for entry in os.listdir(data_store.store_dir):
            entry_m = entry_re.match(entry)
            if entry_m:
                full_name, pk = (entry_m.group("full_name"), int(entry_m.group("pk")))
                try:
                    new_ds = data_store(device.objects.get(Q(pk=pk)))
                    new_ds.restore()
                except:
                    data_store.g_log("cannot initialize data_store for %s: %s" % (
                        full_name,
                        process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                else:
                    data_store.__devices[pk] = new_ds
                    data_store.g_log("recovered info for %s from disk" % (full_name))
    @staticmethod
    def g_log(what, log_level=logging_tools.LOG_LEVEL_OK):
        data_store.process.log("[ds] %s" % (what), log_level)
    @staticmethod
    def feed_perfdata(name, pd_type, pd_info):
        match_dev = None
        if name.count("."):
            full_name, short_name, dom_name = (name, name.split(".")[0], name.split(".", 1)[1])
        else:
            full_name, short_name, dom_name = (None, name, None)
        if full_name:
            # try according to full_name
            try:
                match_dev = device.objects.get(Q(name=short_name) & Q(domain_tree_node__full_name=dom_name))
            except device.DoesNotExist:
                pass
            else:
                match_mode = "fqdn"
        if match_dev is None:
            try:
                match_dev = device.objects.get(Q(name=short_name))
            except device.DoesNotExist:
                pass
            except device.MultipleObjectsReturned:
                pass
            else:
                match_mode = "name"
        if match_dev:
            if data_store.debug:
                data_store.g_log("found device %s (%s) for pd_type=%s" % (unicode(match_dev), match_mode, pd_type))
            if match_dev.pk not in data_store.__devices:
                data_store.__devices[match_dev.pk] = data_store(match_dev)
            data_store.__devices[match_dev.pk].feed_pd(name, pd_type, pd_info)
        else:
            data_store.g_log(
                "no device found (name=%s, pd_type=%s)" % (name, pd_type),
                logging_tools.LOG_LEVEL_ERROR)
    @staticmethod
    def feed_vector(in_vector):
        # print in_vector, type(in_vector), etree.tostring(in_vector, pretty_print=True)
        # at first check for uuid
        match_dev = None
        if "uuid" in in_vector.attrib:
            uuid = in_vector.attrib["uuid"]
            try:
                match_dev = device.objects.get(Q(uuid=uuid))
            except device.DoesNotExist:
                pass
            else:
                match_mode = "uuid"
        if match_dev is None and "name" in in_vector.attrib:
            name = in_vector.attrib["name"]
            if name.count("."):
                full_name, short_name, dom_name = (name, name.split(".")[0], name.split(".", 1)[1])
            else:
                full_name, short_name, dom_name = (None, name, None)
            if full_name:
                # try according to full_name
                try:
                    match_dev = device.objects.get(Q(name=short_name) & Q(domain_tree_node__full_name=dom_name))
                except device.DoesNotExist:
                    pass
                else:
                    match_mode = "fqdn"
            if match_dev is None:
                try:
                    match_dev = device.objects.get(Q(name=short_name))
                except device.DoesNotExist:
                    pass
                except device.MultipleObjectsReturned:
                    pass
                else:
                    match_mode = "name"
        if match_dev:
            if data_store.debug:
                data_store.g_log("found device %s (%s)" % (unicode(match_dev), match_mode))
            if "name" in in_vector.attrib:
                if match_dev.pk not in data_store.__devices:
                    data_store.__devices[match_dev.pk] = data_store(match_dev)
                data_store.__devices[match_dev.pk].feed(in_vector)
            else:
                data_store.g_log("no name in vector for %s, discarding" % (unicode(match_dev)), logging_tools.LOG_LEVEL_ERROR)
        else:
            data_store.g_log("no device found (%s: %s)" % (
                logging_tools.get_plural("key", len(in_vector.attrib)),
                ", ".join(["%s=%s" % (key, str(value)) for key, value in in_vector.attrib.iteritems()])
            ), logging_tools.LOG_LEVEL_ERROR)

class server_process(threading_tools.process_pool):
    def __init__(self):
        self.__log_cache, self.__log_template = ([], None)
        self.__pid_name = global_config["PID_NAME"]
        self.__verbose = global_config["VERBOSE"]
        threading_tools.process_pool.__init__(self, "main", zmq=True, zmq_debug=global_config["ZMQ_DEBUG"])
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        if not global_config["DEBUG"]:
            process_tools.set_handles({
                "out" : (1, "rrd-grapher.out"),
                "err" : (0, "/var/lib/logging-server/py_err_zmq")},
                                      zmq_context=self.zmq_context)
        self.__msi_block = self._init_msi_block()
        connection.close()
        # re-insert config
        self._re_insert_config()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("hup_error", self._hup_error)
        self._log_config()
        self._init_network_sockets()
        self.add_process(graph_process("graph"), start=True)
        self.register_func("send_command", self._send_command)
        self.register_timer(self._clear_old_graphs, 60, instant=True)
        data_store.setup(self)
    def _log_config(self):
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found %d valid global config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def _re_insert_config(self):
        cluster_location.write_config("rrd_server", global_config)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            while self.__log_cache:
                self.__log_template.log(*self.__log_cache.pop(0))
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))
    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True
    def _hup_error(self, err_cause):
        self.log("got sighup", logging_tools.LOG_LEVEL_WARN)
    def process_start(self, src_process, src_pid):
        mult = 3
        process_tools.append_pids(self.__pid_name, src_pid, mult=mult)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(src_pid, mult=mult)
            self.__msi_block.save_block()
    def _clear_old_graphs(self):
        cur_time = time.time()
        graph_root = global_config["GRAPH_ROOT"]
        del_list = []
        for entry in os.listdir(graph_root):
            if entry.endswith(".png"):
                full_name = os.path.join(graph_root, entry)
                c_time = os.stat(full_name)[stat.ST_CTIME]
                diff_time = abs(c_time - cur_time)
                if diff_time > 5 * 60:
                    del_list.append(full_name)
        if del_list:
            self.log("clearing %s is %s" % (
                logging_tools.get_plural("old graph", len(del_list)),
                graph_root))
            for del_entry in del_list:
                try:
                    os.unlink(del_entry)
                except:
                    pass
    def _init_msi_block(self):
        process_tools.save_pid(self.__pid_name, mult=3)
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=3)
        if not global_config["DEBUG"] or True:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("rrd-grapher")
            msi_block.add_actual_pid(mult=3)
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=3)
            msi_block.start_command = "/etc/init.d/rrd-grapher start"
            msi_block.stop_command = "/etc/init.d/rrd-grapher force-stop"
            msi_block.kill_pids = True
            msi_block.save_block()
        else:
            msi_block = None
        return msi_block
    def _send_command(self, *args, **kwargs):
        src_proc, src_id, full_uuid, srv_com = args
        self.log("init send of %s bytes to %s" % (len(srv_com), full_uuid))
        self.com_socket.send_unicode(full_uuid, zmq.SNDMORE)
        self.com_socket.send_unicode(srv_com)
    def _init_network_sockets(self):
        client = self.zmq_context.socket(zmq.ROUTER)
        client.setsockopt(zmq.IDENTITY, "%s:rrd_grapher" % (uuid_tools.get_uuid().get_urn()))
        client.setsockopt(zmq.SNDHWM, 256)
        client.setsockopt(zmq.RCVHWM, 256)
        client.setsockopt(zmq.TCP_KEEPALIVE, 1)
        client.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 300)
        bind_str = "tcp://*:%d" % (global_config["COM_PORT"])
        try:
            client.bind(bind_str)
        except zmq.core.error.ZMQError:
            self.log("error binding to %d: %s" % (global_config["COM_PORT"],
                                                  process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_CRITICAL)
            raise
        else:
            self.log("bound to %s" % (bind_str))
            self.register_poller(client, zmq.POLLIN, self._recv_command)
            self.com_socket = client
    def _interpret_mv_info(self, in_vector):
        data_store.feed_vector(in_vector[0])
    def _interpret_perfdata_info(self, host_name, pd_type, pd_info):
        data_store.feed_perfdata(host_name, pd_type, pd_info)
    def _get_node_rrd(self, srv_com):
        node_results = E.node_results()
        dev_list = srv_com.xpath(None, ".//device_list")[0]
        pk_list = [int(cur_pk) for cur_pk in dev_list.xpath(".//device/@pk")]
        for dev_pk in pk_list:
            cur_res = E.node_result(pk="%d" % (dev_pk))
            if data_store.has_rrd_xml(dev_pk):
                cur_res.append(data_store.get_rrd_xml(dev_pk, sort=True))
            else:
                self.log("no rrd_xml found for device %d" % (dev_pk), logging_tools.LOG_LEVEL_WARN)
            node_results.append(cur_res)
        if int(dev_list.get("merge_results", "0")):
            data_store.merge_node_results(node_results)
        srv_com["result"] = node_results
    def _recv_command(self, zmq_sock):
        in_data = []
        while True:
            in_data.append(zmq_sock.recv())
            if not zmq_sock.getsockopt(zmq.RCVMORE):
                break
        if len(in_data) == 2:
            src_id, data = in_data
            try:
                srv_com = server_command.srv_command(source=data)
            except:
                self.log("error interpreting command: %s" % (process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
                # send something back
                self.com_socket.send_unicode(src_id, zmq.SNDMORE)
                self.com_socket.send_unicode("internal error")
            else:
                cur_com = srv_com["command"].text
                if self.__verbose or cur_com not in ["ocsp-event", "ochp-event" "vector", "perfdata_info"]:
                    self.log("got command '%s' from '%s'" % (
                        cur_com,
                        srv_com["source"].attrib["host"]))
                srv_com.update_source()
                send_return = True
                if cur_com in ["mv_info"]:
                    self._interpret_mv_info(srv_com["vector"])
                    send_return = False
                elif cur_com in ["perfdata_info"]:
                    self._interpret_perfdata_info(srv_com["hostname"].text, srv_com["pd_type"].text, srv_com["info"][0])
                    send_return = False
                elif cur_com == "get_node_rrd":
                    self._get_node_rrd(srv_com)
                elif cur_com == "graph_rrd":
                    send_return = False
                    self.send_to_process("graph", "graph_rrd", src_id, unicode(srv_com))
                else:
                    self.log("got unknown command '%s'" % (cur_com), logging_tools.LOG_LEVEL_ERROR)
                if send_return:
                    srv_com["result"] = None
                    # blabla
                    srv_com["result"].attrib.update(
                        {
                            "reply" : "ok processed command %s" % (cur_com),
                            "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)
                        }
                    )
                    self.com_socket.send_unicode(src_id, zmq.SNDMORE)
                    self.com_socket.send_unicode(unicode(srv_com))
                else:
                    del cur_com
        else:
            self.log(
                "wrong count of input data frames: %d, first one is %s" % (
                    len(in_data),
                    in_data[0]),
                logging_tools.LOG_LEVEL_ERROR)
    def loop_end(self):
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
    def loop_post(self):
        self.com_socket.close()
        self.__log_template.close()
    def thread_loop_post(self):
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()

global_config = configfile.get_global_config(process_tools.get_programm_name())

def main():
    long_host_name, mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries([
        ("DEBUG"               , configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("ZMQ_DEBUG"           , configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
        ("KILL_RUNNING"        , configfile.bool_c_var(True, help_string="kill running instances [%(default)s]")),
        ("CHECK"               , configfile.bool_c_var(False, short_options="C", help_string="only check for server status", action="store_true", only_commandline=True)),
        ("USER"                , configfile.str_c_var("idrrd", help_string="user to run as [%(default)s")),
        ("GROUP"               , configfile.str_c_var("idg", help_string="group to run as [%(default)s]")),
        ("GROUPS"              , configfile.array_c_var([])),
        ("LOG_DESTINATION"     , configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME"            , configfile.str_c_var(prog_name)),
        ("PID_NAME"            , configfile.str_c_var(os.path.join(prog_name,
                                                                   prog_name))),
        ("COM_PORT"            , configfile.int_c_var(SERVER_COM_PORT)),
        ("VERBOSE"             , configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ("RRD_DIR"             , configfile.str_c_var("/var/cache/rrd", help_string="directory of rrd-files on local disc")),
        ("COLORTABLE_FILE"     , configfile.str_c_var("/opt/cluster/share/colortables.xml", help_string="name of colortable file")),
        ("COLORRULES_FILE"     , configfile.str_c_var("/opt/cluster/share/color_rules.xml", help_string="name of color_rules file")),
    ])
    global_config.parse_file()
    options = global_config.handle_commandline(
        description="%s, version is %s" % (prog_name,
                                           VERSION_STRING),
        add_writeback_option=True,
        positional_arguments=False)
    global_config.write_file()
    sql_info = config_tools.server_check(server_type="rrd_server")
    if not sql_info.effective_device:
        print "not an rrd_server"
        sys.exit(5)
    else:
        global_config.add_config_entries([("SERVER_IDX", configfile.int_c_var(sql_info.effective_device.pk, database=False))])
    if global_config["CHECK"]:
        sys.exit(0)
    if global_config["KILL_RUNNING"]:
        log_lines = process_tools.kill_running_processes(
            "%s.py" % (prog_name),
            ignore_names=[],
            exclude=configfile.get_manager_pid())

    cur_dir = os.path.dirname(os.path.abspath(__file__))
    global_config.add_config_entries(
        [
            ("LOG_SOURCE_IDX", configfile.int_c_var(cluster_location.log_source.create_log_source_entry("rrd-server", "Cluster RRDServer", device=sql_info.effective_device).pk)),
            ("GRAPH_ROOT"    , configfile.str_c_var(os.path.abspath(os.path.join(settings.FILE_ROOT if not global_config["DEBUG"] else os.path.join(cur_dir, "../webfrontend/django/initat/cluster"), "graphs"))))
        ]
    )

    process_tools.renice()
    process_tools.fix_directories(global_config["USER"], global_config["GROUP"], ["/var/run/rrd-grapher"])
    global_config.set_uid_gid(global_config["USER"], global_config["GROUP"])
    process_tools.change_user_group(global_config["USER"], global_config["GROUP"], global_config["GROUPS"], global_config=global_config)
    if not global_config["DEBUG"]:
        process_tools.become_daemon()
    else:
        print "Debugging rrd-grapher on %s" % (long_host_name)
    ret_state = server_process().loop()
    sys.exit(ret_state)

if __name__ == "__main__":
    main()
