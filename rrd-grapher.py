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

import time
import getopt
import socket
import colorsys
import pprint
import zmq
from lxml import etree

#import rrdtool
#import configfile
import logging_tools
import process_tools
import config_tools
import server_command
import threading_tools
import cluster_location
import uuid_tools
import configfile
from django.db import connection, connections
try:
    from rrd_grapher.version import VERSION_STRING
except ImportError:
    VERSION_STRING = "?.?"

SERVER_COM_PORT = 8003

class logging_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config):
        self.__sep_str = "-" * 50
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        self.__machlogs, self.__glob_log, self.__glob_cache = ({}, None, [])
        threading_tools.thread_obj.__init__(self, "logging", queue_size=500, priority=10)
        self.register_func("log", self._log)
        self.register_func("mach_log", self._mach_log)
        self.register_func("set_queue_dict", self._set_queue_dict)
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
        root = self.__glob_config["LOG_DIR"]
        if not os.path.exists(root):
            os.makedirs(root)
        glog_name = "%s/log" % (root)
        self.__glob_log = logging_tools.logfile(glog_name)
        self.__glob_log.write(self.__sep_str)
        self.__glob_log.write("Opening log")
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
    def loop_end(self):
        for mach in self.__machlogs.keys():
            self.__machlogs[mach].write("Closing log")
            self.__machlogs[mach].close()
        self.__glob_log.write("Closed %s" % (logging_tools.get_plural("machine log", len(self.__machlogs.keys()))))
        self.__glob_log.write("Closing log")
        self.__glob_log.write("logging thread exiting (pid %d)" % (self.pid))
        self.send_pool_message(("remove_pid", (self.name, self.pid)))
        self.__glob_log.close()
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self._mach_log((self.name, what, lev, ""))
    def _log(self, (s_thread, what, lev)):
        self._mach_log((s_thread, what, lev, ""))
    def _mach_log(self, (s_thread, what, lev, mach)):
        if mach == "":
            handle, pre_str = (self.__glob_log, "")
        else:
            handle, pre_str = self._get_handle(mach)
        if handle is None:
            self.__glob_cache.append((s_thread, what, lev, mach))
        else:
            log_act = []
            if self.__glob_cache:
                for c_s_thread, c_what, c_lev, c_mach in self.__glob_cache:
                    c_handle, c_pre_str = self._get_handle(c_mach)
                    self._handle_log(c_handle, c_s_thread, c_pre_str, c_what, c_lev, c_mach)
                self.__glob_cache = []
            self._handle_log(handle, s_thread, pre_str, what, lev, mach)
    def _handle_log(self, handle, s_thread, pre_str, what, lev, mach):
        handle.write("%-5s(%s) : %s%s" % (logging_tools.get_log_level_str(lev),
                                          s_thread,
                                          pre_str,
                                          what))
    def _get_handle(self, name):
        devname_dict = {}
        if self.__machlogs.has_key(name):
            handle, pre_str = (self.__machlogs[name], "")
        else:
            handle, pre_str = (self.__glob_log, "device %s: " % (name))
        return (handle, pre_str)
        
class command_thread(threading_tools.thread_obj):
    def __init__(self, glob_config, loc_config, db_con, log_queue):
        self.__db_con = db_con
        self.__log_queue = log_queue
        self.__glob_config, self.__loc_config = (glob_config, loc_config)
        threading_tools.thread_obj.__init__(self, "command", queue_size=100)
        self.register_func("set_queue_dict", self._set_queue_dict)
        self.register_func("com_con", self._com_con)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_queue.put(("log", (self.name, what, lev)))
    def thread_running(self):
        self.send_pool_message(("new_pid", (self.name, self.pid)))
    def loop_end(self):
        self.send_pool_message(("remove_pid", (self.name, self.pid)))
    def _set_queue_dict(self, q_dict):
        self.__queue_dict = q_dict
    def _com_con(self, tcp_obj):
        in_data = tcp_obj.get_decoded_in_str()
        try:
            server_com = server_command.server_command(in_data)
        except:
            tcp_obj.add_to_out_buffer("error no valid server_command")
            self.log("Got invalid data from host %s (port %d): %s" % (tcp_obj.get_src_host(),
                                                                      tcp_obj.get_src_port(),
                                                                      in_data[0:20]),
                     logging_tools.LOG_LEVEL_WARN)
        else:
            srv_com_name = server_com.get_command()
            call_func = {"status"                : self._status,
                         "report_lmma"           : self._report_latest_max_min_average,
                         "draw_graphs"           : self._draw_graphs}.get(srv_com_name, None)
            if call_func:
                call_func(tcp_obj, server_com)
            else:
                self.log("Got unknown server_command '%s' from host %s (port %d)" % (srv_com_name,
                                                                                     tcp_obj.get_src_host(),
                                                                                     tcp_obj.get_src_port()),
                         logging_tools.LOG_LEVEL_WARN)
                res_str = "unknown command %s" % (srv_com_name)
                tcp_obj.add_to_out_buffer(server_command.server_reply(state=server_command.SRV_REPLY_STATE_ERROR, result=res_str),
                                          res_str)
    def _status(self, tcp_obj, s_com):
        tp = self.get_thread_pool()
        num_threads, num_ok = (tp.num_threads(False),
                               tp.num_threads_running(False))
        if num_ok == num_threads:
            ret_str = "OK: all %d threads running, version %s" % (num_ok, self.__loc_config["VERSION_STRING"])
        else:
            ret_str = "ERROR: only %d of %d threads running, version %s" % (num_ok, num_threads, self.__loc_config["VERSION_STRING"])
        server_reply = server_command.server_reply()
        server_reply.set_ok_result(ret_str)
        tcp_obj.add_to_out_buffer(server_reply, "status")
    def _report_latest_max_min_average(self, tcp_obj, s_com):
        self.__queue_dict["report_queue"].put(("report_latest_max_min_average", (s_com, tcp_obj)))
    def _draw_graphs(self, tcp_obj, s_com):
        self.__queue_dict["report_queue"].put(("draw_graphs", (s_com, tcp_obj)))

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
                #print rrd_graph_args
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
                        #print "\n".join(out_list)
        report_end_time = time.time()
        self.log("fetching on %s took %s" % (logging_tools.get_plural("device", len(report_devs)),
                                             logging_tools.get_diff_time_str(report_end_time - report_start_time)))
        tcp_obj.add_to_out_buffer(server_command.server_reply(state = server_command.SRV_REPLY_STATE_OK,
                                                              result = "ok fetched",
                                                              node_results = node_res,
                                                              node_dicts = dev_rep_dict))
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
                    #print " ".join(rrd_graph_args)
                    #print rrd_graph_args
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
        tcp_obj.add_to_out_buffer(server_command.server_reply(state = server_command.SRV_REPLY_STATE_OK,
                                                              result = "ok drawn",
                                                              node_results = node_res,
                                                              option_dict = compound_results),
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

class server_thread_pool(threading_tools.thread_pool):
    def __init__(self, db_con, g_config, loc_config):
        self.__log_cache, self.__log_queue = ([], None)
        self.__db_con = db_con
        self.__glob_config, self.__loc_config = (g_config, loc_config)
        threading_tools.thread_pool.__init__(self, "main", blocking_loop=False)
        self.__msi_block = self._init_msi_block()
        self.register_func("new_pid", self._new_pid)
        self.register_func("remove_pid", self._remove_pid)
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.__log_queue = self.add_thread(logging_thread(self.__glob_config, self.__loc_config), start_thread=True).get_thread_queue()
        #self.register_exception("hup_error", self._hup_error)
        # log config
        self._log_config()
        # prepare directories
        #self._prepare_directories()
        dc = self.__db_con.get_connection(SQL_ACCESS)
        # re-insert config
        self._re_insert_config(dc)
        self.__ns = net_tools.network_server(timeout=2, log_hook=self.log, poll_verbose=self.__loc_config["VERBOSE"] > 1)
        self.__com_queue    = self.add_thread(command_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue), start_thread=True).get_thread_queue()
        self.__report_queue = self.add_thread(report_thread(self.__glob_config, self.__loc_config, self.__db_con, self.__log_queue), start_thread=True).get_thread_queue()
        self.__queue_dict = {"log_queue"         : self.__log_queue,
                             "command_queue"     : self.__com_queue,
                             "report_queue"      : self.__report_queue}
        self.__log_queue.put(("set_queue_dict", self.__queue_dict))
        self.__com_queue.put(("set_queue_dict", self.__queue_dict))
        self.__report_queue.put(("set_queue_dict", self.__queue_dict))
        dc.release()
        # uuid log
        my_uuid = uuid_tools.get_uuid()
        self.log("cluster_device_uuid is '%s'" % (my_uuid.get_urn()))
        self.__ns.add_object(net_tools.tcp_bind(self._new_tcp_command_con, port=self.__glob_config["COMMAND_PORT"], bind_retries=5, bind_state_call=self._bind_state_call, timeout=60))
    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("exit requested", logging_tools.LOG_LEVEL_WARN)
            self["exit_requested"] = True
            try:
                file(self.__loc_config["LOCK_FILE_NAME"], "w").write("init shutdown")
            except:
                self.log("error writing to %s: %s" % (self.__loc_config["LOCK_FILE_NAME"],
                                                      process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
            self.__ns.set_timeout(1)
    def _new_pid(self, (thread_name, new_pid)):
        self.log("received new_pid message from thread %s" % (thread_name))
        process_tools.append_pids(self.__loc_config["PID_NAME"], new_pid)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(new_pid)
            self.__msi_block.save_block()
    def _remove_pid(self, (thread_name, rem_pid)):
        self.log("received remove_pid message from thread %s" % (thread_name))
        process_tools.remove_pids(self.__loc_config["PID_NAME"], rem_pid)
        if self.__msi_block:
            self.__msi_block.remove_actual_pid(rem_pid)
            self.__msi_block.save_block()
    def _log_config(self):
        self.log("Config info:")
        for line, log_level in self.__glob_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = self.__glob_config.get_config_info()
        self.log("Found %d valid global config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
        conf_info = self.__loc_config.get_config_info()
        self.log("Found %d valid local config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def _re_insert_config(self, dc):
        self.log("re-insert config")
        configfile.write_config(dc, CAP_NAME, self.__glob_config)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_queue:
            if self.__log_cache:
                for c_what, c_lev in self.__log_cache:
                    self.__log_queue.put(("log", (self.name, "(delayed) %s" % (c_what), c_lev)))
                self.__log_cache = []
            self.__log_queue.put(("log", (self.name, what, lev)))
        else:
            self.__log_cache.append((what, lev))
    def _init_msi_block(self):
        process_tools.save_pid(self.__loc_config["PID_NAME"])
        if self.__loc_config["DAEMON"]:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info(PROG_NAME)
            msi_block.add_actual_pid()
            msi_block.start_command = "/etc/init.d/%s start" % (PROG_NAME)
            msi_block.stop_command = "/etc/init.d/%s force-stop" % (PROG_NAME)
            msi_block.kill_pids = True
            msi_block.save_block()
        else:
            msi_block = None
        return msi_block
    def _new_tcp_command_con(self, sock, src):
        self.log("got command from host %s, port %d" % (src[0], src[1]))
        return new_tcp_con("com", "tcp", None, src, self.__com_queue, self.__log_queue)
    def _bind_state_call(self, **args):
        if args["state"].count("ok"):
            self.log("Bind to %s (type %s) sucessfull" % (args["port"], args["type"]))
        else:
            self.log("Bind to %s (type %s) NOT sucessfull" % (args["port"], args["type"]), logging_tools.LOG_LEVEL_CRITICAL)
            self.log("unable to bind to all ports, exiting", logging_tools.LOG_LEVEL_ERROR)
            self._int_error("bind problem")
    def loop_function(self):
        self.__ns.step()
        if self.__loc_config["VERBOSE"] or self["exit_requested"]:
            tqi_dict = self.get_thread_queue_info()
            tq_names = sorted(tqi_dict.keys())
            self.log("tqi: %s" % (", ".join(["%s: %3d of %3d" % (t_name, t_used, t_total) for (t_name, t_used, t_total) in [(t_name,
                                                                                                                             tqi_dict[t_name][1],
                                                                                                                             tqi_dict[t_name][0]) for t_name in tq_names] if t_used]) or "clean"))
    def thread_loop_post(self):
        process_tools.delete_pid(self.__loc_config["PID_NAME"])
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
        try:
            os.unlink(self.__loc_config["LOCK_FILE_NAME"])
        except (IOError, OSError):
            pass

class server_process(threading_tools.process_pool):
    def __init__(self):
        self.__log_cache, self.__log_template = ([], None)
        self.__pid_name = global_config["PID_NAME"]
        self.__verbose = global_config["VERBOSE"]
        threading_tools.process_pool.__init__(self, "main", zmq=True, zmq_debug=global_config["ZMQ_DEBUG"])
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        if not global_config["DEBUG"]:
            process_tools.set_handles({
                "out" : (1, "rrd-server.out"),
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
    def _init_msi_block(self):
        process_tools.save_pid(self.__pid_name, mult=3)
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=4)
        if not global_config["DEBUG"] or True:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("rrd-grapher")
            msi_block.add_actual_pid(mult=3)
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=4)
            msi_block.start_command = "/etc/init.d/rrd-grapher start"
            msi_block.stop_command  = "/etc/init.d/rrd-grapher force-stop"
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
        print in_vector, type(in_vector), etree.tostring(in_vector, pretty_print=True)
    def _recv_command(self, zmq_sock):
        print "Recv"
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
                if self.__verbose or cur_com not in ["ocsp-event", "ochp-event"]:
                    self.log("got command '%s' from '%s'" % (
                        cur_com,
                        srv_com["source"].attrib["host"]))
                srv_com.update_source()
                send_return = False
                if cur_com in ["mv_info"]:
                    self._interpret_mv_info(srv_com["vector"])
                else:
                    self.log("got unknown command '%s'" % (cur_com), logging_tools.LOG_LEVEL_ERROR)
                if send_return:
                    srv_com["result"] = None
                    # blabla
                    srv_com["result"].attrib.update({"reply" : "ok processed command %s" % (cur_com),
                                                     "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)})
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

    global_config.add_config_entries([("LOG_SOURCE_IDX", configfile.int_c_var(cluster_location.log_source.create_log_source_entry("rrd-server", "Cluster RRDServer", device=sql_info.effective_device).pk))])

    process_tools.renice()
    process_tools.fix_directories(global_config["USER"], global_config["GROUP"], ["/var/run/rrd-server"])
    global_config.set_uid_gid(global_config["USER"], global_config["GROUP"])
    process_tools.change_user_group(global_config["USER"], global_config["GROUP"], global_config["GROUPS"], global_config=global_config)
    if not global_config["DEBUG"]:
        process_tools.become_daemon()
    else:
        print "Debugging rrd-server on %s" % (long_host_name)
    ret_state = server_process().loop()
    sys.exit(ret_state)

if __name__ == "__main__":
    main()
