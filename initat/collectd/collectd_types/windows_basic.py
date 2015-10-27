#
# this file is part of collectd-init
#
# Copyright (C) 2013-2015 Andreas Lang-Nevyjel init.at
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
""" windows checks """

import re

from lxml.builder import E

from .base import PerfdataObject, perfdata_value


class WinMemoryPerfdata(PerfdataObject):
    PD_RE = re.compile("^Memory usage=(?P<used>\d+\.\d+)Mb;\d+\.\d+;\d+\.\d+;\d+\.\d+;(?P<total>\d+\.\d+)$", re.I)
    PD_XML_INFO = E.perfdata_info(
        perfdata_value("used", "memory in use", v_type="i", unit="B", rrd_spec="GAUGE:0:U", base=1024, key="memory.used").get_xml(),
        perfdata_value("total", "memory total", v_type="i", unit="B", rrd_spec="GAUGE:0:U", base=1024, key="memory.total").get_xml(),
    )

    @property
    def file_name(self):
        return "win_memory"

    @property
    def pd_name(self):
        return "win_memory"

    def build_values(self, _host_info, _xml, in_dict):
        return self._wrap(
            _host_info,
            _xml,
            [
                int(float(in_dict[key]) * 1024 * 1024) for key in ["used", "total"]
            ]
        )


class WinDiskPerfdata(PerfdataObject):
    PD_RE = re.compile("^(?P<disk>.): Used Space=(?P<used>\d+\.\d+)Gb;\d+\.\d+;\d+\.\d+;\d+\.\d+;(?P<total>\d+\.\d+)$")

    @property
    def file_name(self):
        return "win_disk"

    @property
    def pd_name(self):
        return "win_disk"

    @property
    def default_xml_info(self):
        return self.get_pd_xml_info(["C"])

    def get_pd_xml_info(self, v_list):
        disk = v_list[0]
        return E.perfdata_info(
            perfdata_value("used", "space used on {}".format(disk), v_type="i", unit="B", rrd_spec="GAUGE:0:U", key="disk.{}.used".format(disk)).get_xml(),
            perfdata_value("total", "total size of {}".format(disk), v_type="i", unit="B", rrd_spec="GAUGE:0:U", key="disk.{}.total".format(disk)).get_xml(),
        )

    def build_values(self, _host_info, _xml, in_dict):
        return self._wrap(
            _host_info,
            _xml,
            [in_dict["disk"], int(float(in_dict["used"]) * 1000 * 1000 * 1000), int(float(in_dict["total"]) * 1000 * 1000 * 1000)],
            rsi=1
        )

    def get_type_instance(self, v_list):
        # set PSU index as instance
        return "{}".format(v_list[0])


class WinLoadPerfdata(PerfdataObject):
    PD_RE = re.compile("^1 min avg Load=(?P<load1>\d+)%\S+ 5 min avg Load=(?P<load5>\d+)%\S+ 15 min avg Load=(?P<load15>\d+)%\S+$")
    PD_XML_INFO = E.perfdata_info(
        perfdata_value("load1", "mean load of the last minute", rrd_spec="GAUGE:0:10000", unit="%", v_type="i").get_xml(),
        perfdata_value("load5", "mean load of the 5 minutes", rrd_spec="GAUGE:0:10000", unit="%", v_type="i").get_xml(),
        perfdata_value("load15", "mean load of the 15 minutes", rrd_spec="GAUGE:0:10000", unit="%", v_type="i").get_xml(),
    )

    @property
    def file_name(self):
        return "win_load"

    @property
    def pd_name(self):
        return "win_load"

    def build_values(self, _host_info, _xml, in_dict):
        return self._wrap(
            _host_info,
            _xml,
            [float(in_dict[key]) for key in ["load1", "load5", "load15"]]
        )
