#
# this file is part of collectd-init
#
# Copyright (C) 2013-2014 Andreas Lang-Nevyjel init.at
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

from lxml.builder import E # @UnresolvedImports
import re
import server_command

__all__ = [
    "perfdata_value", "perfdata_object",
    "win_memory_pdata", "win_disk_pdata",
    "win_load_pdata", "load_pdata",
    "smc_chassis_psu_pdata", "ping_pdata",
    "value",
]

class perfdata_value(object):
    PD_NAME = "unique_name"
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

class perfdata_object(object):
    def _wrap(self, _xml, v_list, rsi=0):
        # rsi: report start index, used to skip values from v_list which should not be graphed
        # add name, host and timestamp values
        return [
            # name of instance (has to exist in init_types.db)
            self.PD_NAME,
            # instance type (for non-unique perfdata objects, PSUs on a bladecenterchassis for instance)
            self.get_type_instance(v_list),
            # hostname
            _xml.get("host"),
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
    def default_xml_info(self):
        return self.get_pd_xml_info([])
    def get_pd_xml_info(self, v_list):
        return self.PD_XML_INFO
    def build_perfdata_info(self, mach_values):
        new_com = server_command.srv_command(command="perfdata_info")
        new_com["hostname"] = mach_values[2]
        new_com["pd_type"] = self.PD_NAME
        info = self.get_pd_xml_info(mach_values[5])
        if mach_values[1]:
            info.attrib["type_instance"] = mach_values[1]
        new_com["info"] = info
        return new_com

class win_memory_pdata(perfdata_object):
    PD_RE = re.compile("^Memory usage=(?P<used>\d+\.\d+)Mb;\d+\.\d+;\d+\.\d+;\d+\.\d+;(?P<total>\d+\.\d+)$", re.I)
    PD_NAME = "win_memory"
    PD_XML_INFO = E.perfdata_info(
        perfdata_value("used", "memory in use", v_type="i", unit="B", rrd_spec="GAUGE:0:U", base=1024, key="memory.used").get_xml(),
        perfdata_value("total", "memory total", v_type="i", unit="B", rrd_spec="GAUGE:0:U", base=1024, key="memory.total").get_xml(),
        )
    def build_values(self, _xml, in_dict):
        return self._wrap(
            _xml,
            [
                int(float(in_dict[key]) * 1024 * 1024) for key in ["used", "total"]
            ]
        )

class win_disk_pdata(perfdata_object):
    PD_RE = re.compile("^(?P<disk>.): Used Space=(?P<used>\d+\.\d+)Gb;\d+\.\d+;\d+\.\d+;\d+\.\d+;(?P<total>\d+\.\d+)$")
    PD_NAME = "win_disk"
    @property
    def default_xml_info(self):
        return self.get_pd_xml_info(["C"])
    def get_pd_xml_info(self, v_list):
        disk = v_list[0]
        return E.perfdata_info(
            perfdata_value("used", "space used on {}".format(disk), v_type="i", unit="B", rrd_spec="GAUGE:0:U", key="disk.{}.used".format(disk)).get_xml(),
            perfdata_value("total", "total size of {}".format(disk), v_type="i", unit="B", rrd_spec="GAUGE:0:U", key="disk.{}.total".format(disk)).get_xml(),
        )
    def build_values(self, _xml, in_dict):
        return self._wrap(
            _xml,
            [in_dict["disk"], int(float(in_dict["used"]) * 1000 * 1000 * 1000), int(float(in_dict["total"]) * 1000 * 1000 * 1000)],
            rsi=1
        )
    def get_type_instance(self, v_list):
        # set PSU index as instance
        return "{}".format(v_list[0])

class win_load_pdata(perfdata_object):
    PD_RE = re.compile("^1 min avg Load=(?P<load1>\d+)%\S+ 5 min avg Load=(?P<load5>\d+)%\S+ 15 min avg Load=(?P<load15>\d+)%\S+$")
    PD_NAME = "win_load"
    PD_XML_INFO = E.perfdata_info(
        perfdata_value("load1", "mean load of the last minute", rrd_spec="GAUGE:0:10000", unit="%", v_type="i").get_xml(),
        perfdata_value("load5", "mean load of the 5 minutes", rrd_spec="GAUGE:0:10000", unit="%", v_type="i").get_xml(),
        perfdata_value("load15", "mean load of the 15 minutes", rrd_spec="GAUGE:0:10000", unit="%", v_type="i").get_xml(),
    )
    def build_values(self, _xml, in_dict):
        return self._wrap(
            _xml,
            [float(in_dict[key]) for key in ["load1", "load5", "load15"]]
        )

class load_pdata(perfdata_object):
    PD_RE = re.compile("^load1=(?P<load1>\S+)\s+load5=(?P<load5>\S+)\s+load15=(?P<load15>\S+)$")
    PD_NAME = "load"
    PD_XML_INFO = E.perfdata_info(
        perfdata_value("load1", "mean load of the last minute", rrd_spec="GAUGE:0:10000").get_xml(),
        perfdata_value("load5", "mean load of the 5 minutes", rrd_spec="GAUGE:0:10000").get_xml(),
        perfdata_value("load15", "mean load of the 15 minutes", rrd_spec="GAUGE:0:10000").get_xml(),
    )
    def build_values(self, _xml, in_dict):
        return self._wrap(
            _xml,
            [float(in_dict[key]) for key in ["load1", "load5", "load15"]]
        )

class smc_chassis_psu_pdata(perfdata_object):
    PD_RE = re.compile("^smcipmi\s+psu=(?P<psu_num>\d+)\s+temp=(?P<temp>\S+)\s+amps=(?P<amps>\S+)\s+fan1=(?P<fan1>\d+)\s+fan2=(?P<fan2>\d+)$")
    PD_NAME = "smc_chassis_psu"
    def build_values(self, _xml, in_dict):
        return self._wrap(
            _xml,
            [int(in_dict["psu_num"]), float(in_dict["temp"]), float(in_dict["amps"]), int(in_dict["fan1"]), int(in_dict["fan2"])],
            rsi=1,
            )
    @property
    def default_xml_info(self):
        return self.get_pd_xml_info([0])
    def get_pd_xml_info(self, v_list):
        psu_num = v_list[0]
        return E.perfdata_info(
            perfdata_value("temp", "temperature of PSU {:d}".format(psu_num), v_type="f", unit="C", key="temp.psu{:d}".format(psu_num), rrd_spec="GAUGE:0:100").get_xml(),
            perfdata_value("amps", "amperes consumed by PSU {:d}".format(psu_num), v_type="f", unit="A", key="amps.psu{:d}".format(psu_num), rrd_spec="GAUGE:0:100").get_xml(),
            perfdata_value("fan1", "speed of FAN1 of PSU {:d}".format(psu_num), v_type="i", key="fan.psu{:d}fan1".format(psu_num), rrd_spec="GAUGE:0:10000").get_xml(),
            perfdata_value("fan2", "speed of FAN2 of PSU {:d}".format(psu_num), v_type="i", key="fan.psu{:d}fan2".format(psu_num), rrd_spec="GAUGE:0:10000").get_xml(),
        )
    def get_type_instance(self, v_list):
        # set PSU index as instance
        return "{:d}".format(v_list[0])

class ping_pdata(perfdata_object):
    PD_RE = re.compile("^rta=(?P<rta>\S+) min=(?P<min>\S+) max=(?P<max>\S+) sent=(?P<sent>\d+) loss=(?P<loss>\d+)$")
    PD_NAME = "ping"
    PD_XML_INFO = E.perfdata_info(
        perfdata_value("sent", "packets sent", v_type="i", rrd_spec="GAUGE:0:100").get_xml(),
        perfdata_value("loss", "packets lost", v_type="i", rrd_spec="GAUGE:0:100").get_xml(),
        perfdata_value("rta", "mean package runtime", v_type="f", unit="s", rrd_spec="GAUGE:0:1000000").get_xml(),
        perfdata_value("min", "minimum package runtime", v_type="f", unit="s", rrd_spec="GAUGE:0:1000000").get_xml(),
        perfdata_value("max", "maximum package runtime", v_type="f", unit="s", rrd_spec="GAUGE:0:1000000").get_xml(),
    )
    def build_values(self, _xml, in_dict):
        return self._wrap(
            _xml,
            [int(in_dict["sent"]), int(in_dict["loss"]), float(in_dict["rta"]), float(in_dict["min"]), float(in_dict["max"])]
        )

class value(object):
    # somehow resembles mvect_entry from hm_classes
    __slots__ = ["name", "sane_name", "info", "unit", "base", "value", "factor", "v_type", "last_update", "set_value"]
    def __init__(self, name):
        self.name = name
        self.sane_name = self.name.replace("/", "_sl_")
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

