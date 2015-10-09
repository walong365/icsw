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
""" structures and functions for the grapher part of rrd-grapher service """

import datetime
import os
import rrdtool
import stat
from lxml import etree

from django.db.models import Q
from lxml.builder import E
import dateutil.parser

from initat.cluster.backbone.models.license import License
from initat.cluster.backbone.models import device, rms_job_run, GraphScaleModeEnum
from initat.tools import logging_tools, process_tools
from ..config import global_config
from .base_functions import FLOAT_FMT, full_graph_key, rrd_escape, strftime
from .graph_struct import GraphVar, GraphTarget, DataSource


class RRDGraph(object):
    def __init__(self, graph_root, log_com, colorizer, para_dict, proc):
        self.log_com = log_com
        self.para_dict = {
            "graph_root": graph_root,
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
        if self.para_dict["graph_setting"].graph_setting_forecast_id:
            _fc = self.para_dict["graph_setting"].graph_setting_forecast
            if _fc.seconds:
                # add seconds
                self.para_dict["end_time_fc"] += datetime.timedelta(seconds=_fc.seconds)
            else:
                # add timeframe
                self.para_dict["end_time_fc"] += self.para_dict["end_time"] - self.para_dict["start_time"]
        timeframe = abs((self.para_dict["end_time_fc"] - self.para_dict["start_time"]).total_seconds())
        graph_width, graph_height = (
            self.para_dict["graph_setting"].graph_setting_size.width,
            self.para_dict["graph_setting"].graph_setting_size.height,
        )
        self.log(
            "width / height : {:d} x {:d}, timeframe {}".format(
                graph_width,
                graph_height,
                logging_tools.get_diff_time_str(timeframe),
            )
        )
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
        if self.para_dict["graph_setting"].merge_graphs:
            # reorder all graph_keys into one graph_key_dict
            s_graph_key_dict = {
                "all": sum(s_graph_key_dict.values(), [])
            }
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
        if self.para_dict["graph_setting"].merge_devices:
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
        if self.para_dict["graph_setting"].merge_graphs:
            # set header
            [_gt.set_header("all") for _gt in sum(graph_key_list, [])]
        self.log("number of graphs to create: {:d}".format(len(graph_key_list)))
        graph_list = E.graph_list()
        _job_add_dict = self._get_jobs(dev_dict)
        for _graph_line in graph_key_list:
            self.log("starting graph_line")
            # iterate in case scale_mode is not None
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
                        "-W {} by init.at".format(License.objects.get_init_product().name),  # title
                        "--slope-mode",  # slope mode
                        "-cBACK#ffffff",
                        "--end", "{:d}".format(self.abs_end_time),  # end
                        "--start", "{:d}".format(self.abs_start_time),  # start
                        GraphVar(self, _graph_target, None, None, "").header_line,
                    ]
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
                                    if _take and _line_iteration == 0:
                                        # add GraphVars only on the first iteration
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
                                        )
                    if _graph_target.draw_keys:
                        draw_it = True
                        removed_keys = set()
                        while draw_it:
                            if self.para_dict["graph_setting"].graph_setting_timeshift_id:
                                timeshift = self.para_dict["graph_setting"].graph_setting_timeshift.seconds
                                if timeshift == 0:
                                    timeshift = self.abs_end_time - self.abs_start_time
                            else:
                                timeshift = 0
                            rrd_args = rrd_pre_args + sum(
                                [
                                    _graph_target.graph_var_def(
                                        _key,
                                        timeshift=timeshift,
                                    ) for _key in _graph_target.draw_keys
                                ],
                                []
                            )
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
                                # compare draw results, add -l / -u when scale_mode is not None
                                val_dict = {}
                                # new code
                                for key, value in draw_result.iteritems():
                                    if not key.startswith("print["):
                                        continue
                                    _xml = etree.fromstring(value)
                                    _unique_id = int(_xml.get("unique_id"))
                                    # print etree.tostring(_xml, pretty_print=True)
                                    try:
                                        value = float(_xml.text)
                                    except:
                                        value = None
                                    else:
                                        pass   # value = None if value == 0.0 else value
                                    _s_key, _v_key = (_xml.get("mvs_key"), _xml.get("mvv_key"))
                                    if value is not None:
                                        _key = (_unique_id, (_s_key, _v_key))
                                        val_dict.setdefault(_key, {})[_xml.get("cf")] = (value, _xml)
                                # list of empty (all none or 0.0 values) keys
                                _zero_keys = [key for key, value in val_dict.iteritems() if all([_v[0] in [0.0, None] for _k, _v in value.iteritems()])]
                                if _zero_keys and self.para_dict["graph_setting"].hide_empty:
                                    # remove all-zero structs
                                    val_dict = {key: value for key, value in val_dict.iteritems() if key not in _zero_keys}
                                for key, value in val_dict.iteritems():
                                    _graph_target.feed_draw_result(key, value)
                                # check if the graphs shall always include y=0
                                draw_it = False
                                if self.para_dict["graph_setting"].include_zero:
                                    if "value_min" in draw_result and "value_max" in draw_result:
                                        if draw_result["value_min"] > 0.0:
                                            _graph_target.set_post_arg("-l", "0")
                                            draw_it = True
                                        if draw_result["value_max"] < 0.0:
                                            _graph_target.set_post_arg("-u", "0")
                                            draw_it = True
                                # check for empty graphs
                                empty_keys = set(_graph_target.draw_keys) - set(val_dict.keys())
                                if empty_keys and self.para_dict["graph_setting"].hide_empty:
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
                if _line_iteration == 0 and self.para_dict["graph_setting"].scale_mode in [
                    GraphScaleModeEnum.level, GraphScaleModeEnum.to100
                ] and (len(_valid_graphs) > 1 or self.para_dict["graph_setting"].scale_mode == GraphScaleModeEnum.to100):
                    _line_iteration += 1
                    if self.para_dict["graph_setting"].scale_mode == GraphScaleModeEnum.level:
                        _vmin_v, _vmax_v = (
                            [_entry.draw_result["value_min"] for _entry in _valid_graphs],
                            [_entry.draw_result["value_max"] for _entry in _valid_graphs],
                        )
                        if set(_vmin_v) > 1 or set(_vmax_v) > 1:
                            _vmin, _vmax = (
                                FLOAT_FMT.format(min(_vmin_v)),
                                FLOAT_FMT.format(max(_vmax_v)),
                            )
                            self.log(
                                "setting y_min / y_max for {} to {} / {}".format(
                                    _valid_graphs[0].graph_key,
                                    _vmin,
                                    _vmax,
                                )
                            )
                            [_entry.set_y_mm(_vmin, _vmax) for _entry in _valid_graphs]
                            _iterate_line = True
                    else:
                        [_entry.adjust_max_y(100) for _entry in _valid_graphs]
                        self.log("set max y_val to 100 for all graphs")
                        _iterate_line = True
                if not _iterate_line:
                    graph_list.extend(
                        [_graph_target.graph_xml(dev_dict) for _graph_target in _graph_line]
                    )
        # print etree.tostring(graph_list, pretty_print=True)
        return graph_list
