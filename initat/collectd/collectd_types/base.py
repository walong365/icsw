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
""" base definitions for collectd types """

from lxml.builder import E  # @UnresolvedImports
from initat.tools import server_command


class perfdata_value(object):

    def __init__(self, name, info, unit="1", v_type="f", key="", rrd_spec="GAUGE:0:100", base=1):
        self.name = name
        self.info = info
        self.unit = unit
        self.v_type = v_type
        self.key = key or name
        self.rrd_spec = rrd_spec
        # base is not used right now
        self.base = base

    def get_xml(self):
        return E.value(
            name=self.name,
            unit=self.unit,
            info=self.info,
            v_type=self.v_type,
            key=self.key,
            rrd_spec=self.rrd_spec,
        )


class PerfdataObject(object):
    def _wrap(self, _host_info, _xml, v_list, rsi=0):
        # rsi: report start index, used to skip values from v_list which should not be graphed
        # add name, host and timestamp values
        pd_tuple = (self, self.get_type_instance(v_list))
        _send_info = _host_info.feed_perfdata(pd_tuple)
        if _send_info:
            _send_xml = self.build_perfdata_info(_host_info, pd_tuple, v_list)  # mach_values
        else:
            _send_xml = None
        # print "****", self.PD_NAME, self.get_type_instance(v_list)
        return [
            # tuple of
            # (
            #   name of instance (has to exist in init_types.db) and
            #   instance type (for non-unique perfdata objects, PSUs on a bladecenterchassis for instance)
            # )
            pd_tuple,
            # host_info
            _host_info,
            # xml send info (may be None)
            _send_xml,
            # time
            int(_xml.get("time")),
            # report offset
            rsi,
            # list of variables
            v_list,
        ]

    def get_type_instance(self, v_list):
        return ""

    @property
    def file_name(self):
        return self.__class__.__name__

    @property
    def pd_name(self):
        return self.__class__.__name__

    @property
    def default_xml_info(self):
        return self.get_pd_xml_info([])

    def get_pd_xml_info(self, v_list):
        return self.PD_XML_INFO

    def build_perfdata_info(self, host_info, pd_tuple, v_list):  # mach_values):
        new_com = E.perfdata(
            hostname=host_info.name,
            uuid=host_info.uuid,
            pd_type=self.pd_name,
            file_name=host_info.target_file_name(pd_tuple),
        )
        info = self.get_pd_xml_info(v_list)
        if pd_tuple[1]:
            new_com.attrib["type_instance"] = pd_tuple[1]
        new_com.append(info)
        return new_com


class value(object):
    # somehow resembles mvect_entry from hm_classes
    __slots__ = ["name", "sane_name", "info", "unit", "base", "value", "factor", "v_type", "last_update", "set_value", "timeout"]

    def __init__(self, name):
        self.name = name
        self.sane_name = self.name.replace("/", "_sl_")
        self.timeout = None

    def update(self, entry, cur_time):
        self.info = entry.attrib["info"]
        self.v_type = entry.attrib["v_type"]
        self.unit = entry.get("unit", "1")
        self.base = int(entry.get("base", "1"))
        self.factor = int(entry.get("factor", "1"))
        if self.v_type == "i":
            self.set_value = self._set_value_int
        elif self.v_type == "f":
            self.set_value = self._set_value_float
        else:
            self.set_value = self._set_value_str
        self.set_value(entry.attrib["value"], cur_time)

    def update_ov(self, entry, cur_time):
        self.set_value(entry.attrib["v"], cur_time)

    def _set_value_int(self, value, cur_time):
        self.last_update = cur_time
        self.value = int(value)

    def _set_value_float(self, value, cur_time):
        self.last_update = cur_time
        self.value = float(value)

    def _set_value_str(self, value, cur_time):
        self.last_update = cur_time
        self.value = value

    def transform(self, value, cur_time):
        self.set_value(value, cur_time)
        return self.value * self.factor

    def get_key_info(self):
        return E.key(
            value=str(self.value),
            name=self.name,
            v_type=self.v_type,
            base="{:d}".format(self.base),
            factor="{:d}".format(self.factor),
            unit=self.unit,
        )

    def get_json(self):
        return (
            # version field, for future enhancements
            0,
            self.name,
            self.info,
            self.unit,
            self.v_type,
            self.value,
            self.base,
            self.factor,
        )
