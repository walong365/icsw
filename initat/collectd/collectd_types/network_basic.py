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
""" network basic checks (ping) """

from .base import PerfdataObject, perfdata_value
import re
from lxml.builder import E


class PingPerfdata(PerfdataObject):
    PD_RE = re.compile("^rta=(?P<rta>\S+) min=(?P<min>\S+) max=(?P<max>\S+) sent=(?P<sent>\d+) loss=(?P<loss>\d+)$")
    PD_XML_INFO = E.perfdata_info(
        perfdata_value("sent", "packets sent", v_type="i", rrd_spec="GAUGE:0:100").get_xml(),
        perfdata_value("loss", "packets lost", v_type="i", rrd_spec="GAUGE:0:100").get_xml(),
        perfdata_value("rta", "mean package runtime", v_type="f", unit="s", rrd_spec="GAUGE:0:1000000").get_xml(),
        perfdata_value("min", "minimum package runtime", v_type="f", unit="s", rrd_spec="GAUGE:0:1000000").get_xml(),
        perfdata_value("max", "maximum package runtime", v_type="f", unit="s", rrd_spec="GAUGE:0:1000000").get_xml(),
    )

    @property
    def file_name(self):
        return "ping"

    @property
    def pd_name(self):
        return "ping"

    def build_values(self, _host_info, _xml, in_dict):
        return self._wrap(
            _host_info,
            _xml,
            [int(in_dict["sent"]), int(in_dict["loss"]), float(in_dict["rta"]), float(in_dict["min"]), float(in_dict["max"])]
        )
