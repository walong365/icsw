#
# this file is part of collectd-init
#
# Copyright (C) 2015 Andreas Lang-Nevyjel init.at
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
""" disk checks via SNMP """

from .base import PerfdataObject, perfdata_value
import re
from lxml.builder import E

""" example: 'UCD-SNMP-MIB::dskPercent.3=14' """


class SNMPDiskCheckPerfData(PerfdataObject):
    PD_RE = re.compile("^UCD-SNMP-MIB::dskPercent.(?P<disk_num>\d+)=(?P<percent>\d+)$")

    def get_pd_xml_info(self, v_list):
        disk_num = v_list[0]
        return E.perfdata_info(
            perfdata_value(
                "disk", "usage of disk {:d}".format(disk_num), v_type="i", unit="%", key="disk.usage{:d}".format(disk_num), rrd_spec="GAUGE:0:100"
            ).get_xml(),
        )

    @property
    def default_xml_info(self):
        return self.get_pd_xml_info([0])

    def get_type_instance(self, v_list):
        return "{:d}".format(v_list[0])

    def build_values(self, _host_info, _xml, in_dict):
        return self._wrap(
            _host_info,
            _xml,
            [
                int(in_dict["disk_num"]), int(in_dict["percent"]),
            ],
            rsi=1,
        )
