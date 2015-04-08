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
""" linux basic checks """

from .base import PerfdataObject, perfdata_value
import re
from lxml.builder import E


class LinuxLoadPerfdata(PerfdataObject):
    PD_RE = re.compile("^load1=(?P<load1>\S+)\s+load5=(?P<load5>\S+)\s+load15=(?P<load15>\S+)$")
    PD_XML_INFO = E.perfdata_info(
        perfdata_value("load1", "mean load of the last minute", rrd_spec="GAUGE:0:10000").get_xml(),
        perfdata_value("load5", "mean load of the 5 minutes", rrd_spec="GAUGE:0:10000").get_xml(),
        perfdata_value("load15", "mean load of the 15 minutes", rrd_spec="GAUGE:0:10000").get_xml(),
    )

    @property
    def file_name(self):
        return "load"

    def build_values(self, _host_info, _xml, in_dict):
        return self._wrap(
            _host_info,
            _xml,
            [float(in_dict[key]) for key in ["load1", "load5", "load15"]]
        )
