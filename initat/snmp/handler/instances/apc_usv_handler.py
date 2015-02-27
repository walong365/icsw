# Copyright (C) 2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of init-snmp-libs
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
""" SNMP handler for APC USVs """

from lxml.builder import E
from initat.host_monitoring import limits

from ..base import SNMPHandler
from ...struct import simple_snmp_oid, MonCheckDefinition, snmp_oid
from ...functions import simplify_dict, flatten_dict


USV_BASE = "1.3.6.1.4.1.318.1.1.1"


class handler(SNMPHandler):
    class Meta:
        description = "USV"
        vendor_name = "apc"
        name = "usv"
        tl_oids = [USV_BASE]

    def collect_fetch(self):
        return [
            (
                "T",
                [
                    simple_snmp_oid("{}.3".format(USV_BASE)),
                    simple_snmp_oid("{}.4".format(USV_BASE)),
                ]
            )
        ]

    def collect_feed(self, result_dict, **kwargs):
        res_dict = flatten_dict(simplify_dict(self.filter_results(result_dict, keys_are_strings=False), (1, 3, 6, 1, 4, 1, 318, 1, 1, 1)))
        mv_tree = kwargs["mv_tree"]
        mv_tree.extend([
            E.mve(
                info="Input frequency",
                unit="1/s",
                base="1",
                v_type="i",
                value="{:d}".format(res_dict[(3, 2, 4, 0)]),
                name="usv.frequency.in",
            ),
            E.mve(
                info="Output frequency",
                unit="1/s",
                base="1",
                v_type="i",
                value="{:d}".format(res_dict[(4, 2, 2, 0)]),
                name="usv.frequency.out",
            ),
            E.mve(
                info="Input line voltage",
                unit="V",
                base="1",
                v_type="i",
                value="{:d}".format(res_dict[(3, 2, 1, 0)]),
                name="usv.voltage.in.line",
            ),
            E.mve(
                info="Input line voltage max",
                unit="V",
                base="1",
                v_type="i",
                value="{:d}".format(res_dict[(3, 2, 2, 0)]),
                name="usv.voltage.in.line_max",
            ),
            E.mve(
                info="Input line voltage min",
                unit="V",
                base="1",
                v_type="i",
                value="{:d}".format(res_dict[(3, 2, 3, 0)]),
                name="usv.voltage.in.line_min",
            ),
            E.mve(
                info="Output voltage",
                unit="V",
                base="1",
                v_type="i",
                value="{:d}".format(res_dict[(4, 2, 1, 0)]),
                name="usv.voltage.out",
            ),
            E.mve(
                info="Output load",
                unit="%",
                base="1",
                v_type="i",
                value="{:d}".format(res_dict[(4, 2, 3, 0)]),
                name="usv.load.out",
            ),
            E.mve(
                info="Output current",
                unit="A",
                base="1",
                v_type="i",
                value="{:d}".format(res_dict[(4, 2, 4, 0)]),
                name="usv.ampere.out",
            ),
        ])

    def config_mon_check(self):
        return [
            usv_mon_all(self),
            usv_mon_detail(self),
        ]


class USVMetric(object):
    def __init__(self, key, short, info, unit):
        self.key = key
        self.short = short
        self.info = info
        self.unit = unit


USV_METRICS = [
    USVMetric((3, 2, 4, 0), "frequency.in", "Input frequency", "1/s"),
    USVMetric((4, 2, 2, 0), "frequency.out", "Output frequency", "1/s"),
    USVMetric((3, 2, 1, 0), "voltage.in.line", "Input line voltage", "V"),
    USVMetric((3, 2, 2, 0), "voltage.in.line_max", "Input line voltage max", "V"),
    USVMetric((3, 2, 3, 0), "voltage.in.line_min", "Input line voltage min", "V"),
    USVMetric((4, 2, 1, 0), "voltage.out", "Output voltage", "V"),
    USVMetric((4, 2, 3, 0), "load.out", "Output load", "%"),
    USVMetric((4, 2, 4, 0), "ampere.out", "Output current", "A"),
]


class usv_mon_base(MonCheckDefinition):
    def mon_start(self, scheme):
        return [
            snmp_oid(
                "{}.3".format(
                    USV_BASE,
                ),
                cache=True,
            ),
            snmp_oid(
                "{}.4".format(
                    USV_BASE,
                ),
                cache=True,
            ),
        ]

    def _rewrite_result(self, scheme):
        _val_dict = {}
        for _key, _value in scheme.snmp.iteritems():
            for _sk, _sv in _value.iteritems():
                _val_dict[tuple(list(_key)[-1:] + list(_sk))] = _sv
        return _val_dict


class usv_mon_all(usv_mon_base):
    class Meta:
        short_name = "usvoverview"
        command_line = "*"
        info = "Check USV via SNMP in one line"
        description = "Check USV via SNMP (one-line version)"

    def config_call(self, s_com):
        dev = s_com.host
        _field = [
            s_com.get_arg_template(
                "USV info",
                arg1=dev.dev_variables["SNMP_READ_COMMUNITY"],
                arg2=dev.dev_variables["SNMP_VERSION"],
            )
        ]
        return _field

    def mon_result(self, scheme):
        _net_obj = scheme.net_obj
        _val_dict = self._rewrite_result(scheme)
        ret_f = []
        for _metric in USV_METRICS:
            _value = _val_dict[_metric.key]
            ret_f.append(
                "{} is {} {}".format(
                    _metric.info,
                    _value,
                    _metric.unit,
                )
            )
        return limits.nag_STATE_OK, ", ".join(ret_f)


class usv_mon_detail(usv_mon_base):
    class Meta:
        short_name = "usvdetail"
        command_line = "* --type $ARG3$"
        info = "Check USV via SNMP"
        description = "Check USV via SNMP"

    def parser_setup(self, parser):
        parser.add_argument("--type", type=str, dest="type", default="freqin", help="value to query", choices=[_m.short for _m in USV_METRICS])

    def config_call(self, s_com):
        dev = s_com.host
        _field = []
        for _metric in USV_METRICS:
            _field.append(
                s_com.get_arg_template(
                    _metric.info,
                    arg1=dev.dev_variables["SNMP_READ_COMMUNITY"],
                    arg2=dev.dev_variables["SNMP_VERSION"],
                    arg3=_metric.short,
                )
            )
        return _field

    def mon_result(self, scheme):
        _net_obj = scheme.net_obj
        _val_dict = self._rewrite_result(scheme)
        _type = scheme.opts.type
        _metric = [_m for _m in USV_METRICS if _m.short == _type][0]
        _value = _val_dict[_metric.key]
        return limits.nag_STATE_OK, "{} is {} {}".format(
            _metric.info,
            _value,
            _metric.unit,
        )
