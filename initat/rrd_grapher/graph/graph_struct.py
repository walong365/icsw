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

import os
import math
import time
import uuid

from django.conf import settings

from django.db.models import Q

from lxml.builder import E

from initat.cluster.backbone.models import cluster_timezone, MachineVector, \
    MVValueEntry, GraphLegendModeEnum
from initat.tools import logging_tools, process_tools
from .base_functions import FLOAT_FMT, full_graph_key, rrd_escape


class GraphVar(object):
    def __init__(self, rrd_graph, graph_target, mvs_entry, mvv_entry, key, dev_name=""):
        # print key, mvs_entry, mvv_entry
        # mvs / mvv entry
        self.mvs_entry = mvs_entry
        self.mvv_entry = mvv_entry
        if self.mvv_entry and self.mvv_entry.pk:
            self.thresholds = list(self.mvv_entry.sensorthreshold_set.all().prefetch_related("sensorthresholdaction_set"))
        else:
            self.thresholds = []
        # graph key (load.1)
        self.key = key
        # device name
        self.dev_name = dev_name
        self.rrd_graph = rrd_graph
        self.draw_result = None
        self.scale_y_factor = 1
        self.y_scaled = False
        self.graph_target = graph_target
        if self.rrd_graph.para_dict["graph_setting"].legend_mode in [GraphLegendModeEnum.full_with_values]:
            self.max_info_width = max(2, 60 + int((self.rrd_graph.width - 800) / 8))
        else:
            self.max_info_width = self.rrd_graph.width / 7
        self.name = "v{:d}".format(self.graph_target.get_def_idx())

    def __getitem__(self, key):
        return self.entry.attrib[key]

    def __contains__(self, key):
        return key in self.entry.attrib

    def set_draw_result(self, res):
        # res is a dict {CF: (value, xml result via print)}
        self.draw_result = res

    def adjust_max_y(self, max_val):
        _max, _min = (0, 0)
        if self.draw_result and "MAXIMUM" in self.draw_result:
            if not math.isnan(self.draw_result["MAXIMUM"][0]):
                _max = abs(self.draw_result["MAXIMUM"][0])
        if self.draw_result and "MINIMUM" in self.draw_result:
            if not math.isnan(self.draw_result["MINIMUM"][0]):
                _min = abs(self.draw_result["MINIMUM"][0])
        if _max or _min:
            self.set_y_scaling(max_val / max(_max, _min))

    def valid_graph_var(self):
        return True if self.draw_result and "MAXIMUM" in self.draw_result and not math.isnan(self.draw_result.get("MAXIMUM", [0.])[0]) else False

    def get_y_scaling(self):
        if self.y_scaled:
            return self.scale_y_factor
        else:
            return 1

    def set_y_scaling(self, val):
        self.scale_y_factor = val
        self.y_scaled = True

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

    @property
    def is_stacked(self):
        return self.style_dict.get("draw_type", "LINE1").endswith("STACK")

    # helper function
    def _transform(self, lines, var_name, postfix, form_str):
        new_name = "{}{}".format(var_name, postfix)
        add_line = form_str.format(new_name, var_name)
        lines.append(add_line)
        return new_name

    def graph_def(self, unique_id, **kwargs):
        # unique_id = device pk
        timeshift = kwargs.get("timeshift", 0)
        self.get_color_and_style()
        src_cf = self.rrd_graph.para_dict["graph_setting"].cf.value
        if self.mvs_entry.se_type in ["pde", "mvl"]:
            # pde entry
            _src_str = "{}:{}:{}".format(self.mvs_entry.file_name, self.mvv_entry.name or self.mvv_entry.key, src_cf)
        else:
            # machvector entry
            _src_str = "{}:v:{}".format(self.mvs_entry.file_name, src_cf)
        c_lines = [
            "DEF:{}={}".format(self.name, _src_str)
        ]
        draw_name = self.name
        if int(self.style_dict.get("invert", "0")):
            draw_name = self._transform(c_lines, draw_name, "inv", "CDEF:{}={},-1,*")
        draw_type = self.style_dict.get("draw_type", "LINE1")
        _stacked = draw_type.endswith("STACK")
        if _stacked:
            draw_type = draw_type[:-5]
        # plot forecast ?
        if draw_type.startswith("LINE") or (draw_type.startswith("AREA") and not _stacked):
            show_forecast = True if self.rrd_graph.para_dict["graph_setting"].graph_setting_forecast_id else False
        else:
            show_forecast = False
        # area: modes area (pure are), area{1,2,3} (area with lines)
        # print draw_name, draw_type, _stacked
        comment_str = ":<tt>{}</tt>".format(
            (
                "{{:<{:d}s}}".format(self.max_info_width)
            ).format(
                self.info(timeshift, show_forecast)
            )[:self.max_info_width],
        ) if self.rrd_graph.para_dict["graph_setting"].legend_mode in [
            GraphLegendModeEnum.full_with_values, GraphLegendModeEnum.only_text
        ] else ""
        if draw_type.startswith("AREA"):
            # support area with outline style
            if self.y_scaled:
                draw_name = self._transform(c_lines, draw_name, "sc", "CDEF:{{}}={{}},{},*".format(self.scale_y_factor))
            c_lines.append(
                "{}:{}{}{}{}".format(
                    "AREA",
                    draw_name,
                    self.color,
                    comment_str,
                    ":STACK" if _stacked else "",
                ),
            )
            if draw_type != "AREA":
                if _stacked:
                    draw_name = self._transform(c_lines, draw_name, "z", "CDEF:{}={},0,*")
                c_lines.append(
                    "{}:{}{}:{}".format(
                        draw_type.replace("AREA", "LINE"),
                        draw_name,
                        "#000000",
                        ":STACK" if _stacked else "",
                    )
                )
        else:
            # scale test
            if self.y_scaled:
                draw_name = self._transform(c_lines, draw_name, "scl", "CDEF:{{}}={{}},{},*".format(self.scale_y_factor))
            c_lines.append(
                "{}:{}{}{}{}".format(
                    draw_type,
                    draw_name,
                    self.color,
                    comment_str,
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
                ]
            )
            c_lines.append(
                "{}:{}lsls{}".format(
                    draw_type.replace("AREA", "LINE"),
                    draw_name,
                    self.color,
                ),
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
                ]
            )
            if self.y_scaled:
                ts_name = self._transform(c_lines, ts_name, "scl", "CDEF:{{}}={{}},{},*".format(self.scale_y_factor))
            c_lines.extend(
                [
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
        if self.rrd_graph.para_dict["graph_setting"].legend_mode in [GraphLegendModeEnum.full_with_values]:
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
                    # use a simple XML structure to encode various lookup values
                    "PRINT:{}{}:<value unique_id='{:d}' device='{:d}' mvs_key='{}' mvs_id='{}' mvv_key='{}' mvv_id='{}' cf='{}'>%.4lf</value>".format(
                        self.name,
                        rep_name,
                        unique_id,
                        self.mvs_entry.machine_vector.device_id,
                        rrd_escape(self.mvs_entry.key),
                        self.mvs_entry.pk,
                        rrd_escape(self.mvv_entry.key),
                        self.mvv_entry.pk,
                        cf,
                    ),
                ]
            )
            if self.rrd_graph.para_dict["graph_setting"].legend_mode in [GraphLegendModeEnum.full_with_values]:
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
        if self.thresholds:
            _th_base = "{}th".format(self.name)
            for _th in self.thresholds:
                _thl_name = "{}{:d}l".format(_th_base, _th.idx)
                _thu_name = "{}{:d}u".format(_th_base, _th.idx)
                c_lines.extend(
                    [
                        "CDEF:{}={},{},-,{},ADDNAN".format(
                            _thl_name,
                            draw_name,
                            draw_name,
                            _th.lower_value,
                        ),
                        "CDEF:{}={},{},-,{},ADDNAN".format(
                            _thu_name,
                            draw_name,
                            draw_name,
                            _th.upper_value,
                        ),
                        "LINE3:{}{}".format(_thl_name, self.color),
                        "AREA:{}{}40#ffffe040::STACK".format(
                            _th.upper_value - _th.lower_value,
                            # remove transparency part (if present)
                            self.color[:7],
                        ),
                        "LINE3:{}{}:<tt>{} [{:.4f}, {:.4f}]</tt>\\l".format(
                            _thu_name,
                            self.color,
                            _th.name,
                            _th.lower_value,
                            _th.upper_value,
                        ),
                    ]
                )
                _events = {}
                for _sta in _th.sensorthresholdaction_set.filter(
                    # Q(date__gte=cluster_timezone.normalize(self.rrd_graph.para_dict["start_time"])),
                    # Q(date__lte=cluster_timezone.normalize(self.rrd_graph.para_dict["end_time_fc"])),
                ):
                    _loc = cluster_timezone.normalize(_sta.date)
                    if self.rrd_graph.para_dict["end_time"] > _loc > self.rrd_graph.para_dict["start_time"]:
                        _events.setdefault(_sta.action_type, []).append(_sta)
                for _event_type in sorted(_events.iterkeys()):
                    for _event_num, _sta in enumerate(_events[_event_type]):
                        if not _event_num:
                            _legend = "<tt>  {}</tt>\\l".format(
                                logging_tools.get_plural(
                                    "{} event".format(
                                        _event_type
                                    ),
                                    len(_events[_event_type])
                                )
                            )
                        else:
                            _legend = ""
                        c_lines.append(
                            "VRULE:{:d}{}:{}:dashes={}".format(
                                int(time.mktime(cluster_timezone.normalize(_sta.date).timetuple())),
                                self.color,
                                _legend,
                                "4,2" if _sta.action_type == "upper" else "1,3"
                            )
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
        _lm = self.rrd_graph.para_dict["graph_setting"].legend_mode
        if _lm in [GraphLegendModeEnum.full_with_values, GraphLegendModeEnum.only_text]:
            _sv = _lm in [GraphLegendModeEnum.full_with_values]
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
        else:
            return "COMMENT:"


class GraphTarget(object):
    """
    graph (==png) to create
    """
    def __init__(self, g_key, dev_list, graph_keys):
        # can also be a short key (for instance 'load')
        self.graph_key = g_key
        self.dev_list = dev_list
        self.__header = None
        self.__headers = []
        # list of full keys (<type>:<root>.<leaf>)
        self.graph_keys = graph_keys
        self.graph_name = "gfx_{}_{}_{:d}.png".format(
            self.graph_key,
            uuid.uuid4(),
            int(time.time())
        )
        self.rel_file_loc = os.path.join(
            "/",
            settings.REL_SITE_ROOT,
            "static",
            "graphs",
            self.graph_name,
        )
        # rrd post arguments, will not be reset
        self.__post_args = {}
        self.removed_keys = []
        # evaluated defs
        self.defs = {}
        # graph vars
        self.vars = {}
        self.file_names = set()
        self.__draw_keys = []
        self.__unique = 0

    def set_header(self, title):
        self.__header = title

    @property
    def header(self):
        # hacky but working
        if self.__header:
            return self.__header
        elif self.graph_keys:
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
        return ",".join(
            [
                dev_id for dev_id, _dev_pk in self.dev_list
            ]
        )

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
        self.draw_result = None
        self.__result_dict = None

    def get_def_idx(self):
        return self.__unique + 1

    def add_def(self, key, g_var, header_str):
        self.__unique += 1
        self.__draw_keys.append((self.__unique, key))
        self.__headers.append(header_str)
        self.vars[(self.__unique, key)] = g_var
        self.file_names.add(g_var.mvs_entry.file_name)

    def graph_var_def(self, key, **kwargs):
        _unique = key[0]
        return self.vars[key].graph_def(_unique, **kwargs)

    def feed_draw_result(self, key, draw_res):
        # set draw result for
        # 1) scaling
        # 2) to get copied into the result XML
        self.vars[key].set_draw_result(draw_res)

    def adjust_max_y(self, max_val):
        [_val.adjust_max_y(max_val) for _val in self.vars.itervalues()]
        # list of keys with the same factor
        _eval_list = []
        for _key in self.draw_keys:
            _var = self.vars[_key]
            if _var.valid_graph_var():
                if self.vars[_key].is_stacked:
                    _eval_list.append(_key)
                else:
                    if len(_eval_list) > 1:
                        self._same_scaling(_eval_list, max_val)
                    _eval_list = [_key]
        if len(_eval_list) > 1:
            self._same_scaling(_eval_list, max_val)

    def _same_scaling(self, eval_list, max_val):
        _total = 0
        for _key in eval_list:
            _var = self.vars[_key]
            _total += _var.draw_result["MAXIMUM"][0]
        _min_fac = max_val / max(_total, 1)
        [self.vars[_key].set_y_scaling(_min_fac) for _key in eval_list]

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
        return True if self.__draw_keys and (self.draw_result is not None) else False

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
            _var_dict = {}
            for _var in self.vars.itervalues():
                if _var.draw_result:
                    for _val, _v_xml in _var.draw_result.itervalues():
                        if not _v_xml.text.count("nan"):
                            _mvs_id, _mvv_id = (_v_xml.get("mvs_id"), _v_xml.get("mvv_id"))
                            # unset keys will be transformed to the empty string
                            _mvs_id = "" if _mvs_id == "None" else _mvs_id
                            _mvv_id = "" if _mvv_id == "None" else _mvv_id
                            _full_key = "{}{}".format(
                                _v_xml.get("mvs_key"),
                                ".{}".format(_v_xml.get("mvv_key")) if _v_xml.get("mvv_key") else "",
                            )
                            _var_dict.setdefault(("{}.{}".format(_mvs_id, _mvv_id), _full_key, int(_v_xml.get("device"))), {})[_v_xml.get("cf")] = _v_xml.text
            if _var_dict:
                _xml.append(
                    E.graph_values(
                        *[
                            E.graph_value(
                                E.cfs(
                                    *[
                                        E.cf(
                                            _cf_value,
                                            cf=_cf_key,
                                        ) for _cf_key, _cf_value in _value.iteritems()
                                    ]
                                ),
                                db_key=_key[0],
                                mv_key=_key[1],
                                device="{:d}".format(_key[2]),
                            ) for _key, _value in _var_dict.iteritems()
                        ]
                    )
                )
            # pprint.pprint(_var_dict)
        return _xml


class DataSource(object):
    def __init__(self, log_com, dev_pks, graph_keys, colorizer):
        self.__log_com = log_com
        self.__colorizer = colorizer
        # lut machinevector_id -> device_id
        _mv_lut = {_v[1]: _v[0] for _v in MachineVector.objects.filter(Q(device__in=dev_pks)).values_list("device_id", "pk")}
        self.__flat_keys = [
            (_v["struct_key"], _v["value_key"]) for _v in graph_keys
        ]
        _query_keys = {full_graph_key(_key) for _key in self.__flat_keys}
        # expand compounds
        _compound_dict = {}
        for _req in graph_keys:
            if _req.get("build_info", ""):
                _key = (_req["struct_key"], _req["value_key"])
                _full_key = full_graph_key(_key)
                _build_infos = [process_tools.decompress_struct(_entry) for _entry in _req["build_info"] if _entry]
                _compound_dict[_key] = []
                for _build_info in _build_infos:
                    for _entry in _build_info:
                        _query_keys.add(_entry["key"])
                        if _entry not in _compound_dict[_key]:
                            _compound_dict[_key].append(_entry)
        # import pprint
        # pprint.pprint(_compound_dict)
        # get mvv_list
        _mvv_list = MVValueEntry.objects.filter(
            Q(full_key__in=_query_keys) &
            Q(mv_struct_entry__machine_vector__device__in=dev_pks)
        ).select_related(
            "mv_struct_entry"
        ).prefetch_related(
            "sensorthreshold_set"
        )
        _mvv_dict = {}
        for _mvv in _mvv_list:
            _mvv_dict.setdefault(_mvv.full_key, []).append(_mvv)
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
                for _mvv in _mvv_dict[_fk]:
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
                    if "color" in _entry and not _entry["color"].startswith("#"):
                        # lookup color table
                        _clr = _entry["color"]
                        if _clr not in _color_tables:
                            _color_tables[_clr] = self.__colorizer.simple_color_table(_clr)
                        _entry["color"] = _color_tables[_clr].color
                    for _mvv in _mvv_dict[_entry["key"]]:
                        _mvs = _mvv.mv_struct_entry
                        _dev_pk = _mv_lut[_mvs.machine_vector_id]
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
