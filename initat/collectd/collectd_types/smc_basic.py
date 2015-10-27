#
# this file is part of collectd-init
#
# Copyright (C) 2014-2015 Andreas Lang-Nevyjel init.at
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
""" Supermicro Chassis Performance data checks """

import re

from lxml.builder import E

from .base import PerfdataObject, perfdata_value


class SMCChassisPSUPerfdata(PerfdataObject):
    PD_RE = re.compile("^smcipmi\s+psu=(?P<psu_num>\d+)\s+temp=(?P<temp>\S+)\s+amps=(?P<amps>\S+)\s+fan1=(?P<fan1>\d+)\s+fan2=(?P<fan2>\d+)$")

    def build_values(self, _host_info, _xml, in_dict):
        return self._wrap(
            _host_info,
            _xml,
            [int(in_dict["psu_num"]), float(in_dict["temp"]), float(in_dict["amps"]), int(in_dict["fan1"]), int(in_dict["fan2"])],
            rsi=1,
        )

    @property
    def file_name(self):
        return "smc_chassis_psu"

    @property
    def pd_name(self):
        return "smc_chassis_psu"

    @property
    def default_xml_info(self):
        return self.get_pd_xml_info([0])

    def get_pd_xml_info(self, v_list):
        psu_num = v_list[0]
        return E.perfdata_info(
            perfdata_value(
                "temp", "temperature of PSU {:d}".format(psu_num), v_type="f", unit="C", key="temp.psu{:d}".format(psu_num), rrd_spec="GAUGE:0:100"
            ).get_xml(),
            perfdata_value(
                "amps", "amperes consumed by PSU {:d}".format(psu_num), v_type="f", unit="A", key="amps.psu{:d}".format(psu_num), rrd_spec="GAUGE:0:100"
            ).get_xml(),
            perfdata_value(
                "fan1", "speed of FAN1 of PSU {:d}".format(psu_num), v_type="i", key="fan.psu{:d}fan1".format(psu_num), rrd_spec="GAUGE:0:10000"
            ).get_xml(),
            perfdata_value(
                "fan2", "speed of FAN2 of PSU {:d}".format(psu_num), v_type="i", key="fan.psu{:d}fan2".format(psu_num), rrd_spec="GAUGE:0:10000"
            ).get_xml(),
        )

    def get_type_instance(self, v_list):
        # set PSU index as instance
        return "{:d}".format(v_list[0])
