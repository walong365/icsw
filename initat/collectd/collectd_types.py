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

from lxml.builder import E  # @UnresolvedImports
import re
import server_command

__all__ = [
    "perfdata_value", "PerfdataObject",
    "WinMemoryPerfdata", "WinDiskPerfdata",
    "WinLoadPerfdata", "LinuxLoadPerfdata",
    "SMCChassisPSUPerfdata", "PingPerfdata",
    "HTTPRequestPerfdata",
    "value",
]


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
        pd_tuple = (self.__class__.__name__, self.get_type_instance(v_list))
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
    def default_xml_info(self):
        return self.get_pd_xml_info([])

    def get_pd_xml_info(self, v_list):
        return self.PD_XML_INFO

    def build_perfdata_info(self, host_info, pd_tuple, v_list):  # mach_values):
        new_com = server_command.srv_command(command="perfdata_info")
        new_com["hostname"] = host_info.name
        new_com["uuid"] = host_info.uuid
        # new_com["uuid"] =
        new_com["pd_type"] = self.__class__.__name__
        new_com["file_name"] = host_info.target_file_name(pd_tuple)
        info = self.get_pd_xml_info(v_list)
        if pd_tuple[1]:
            info.attrib["type_instance"] = pd_tuple[1]
        new_com["info"] = info
        return new_com


class WinMemoryPerfdata(PerfdataObject):
    PD_RE = re.compile("^Memory usage=(?P<used>\d+\.\d+)Mb;\d+\.\d+;\d+\.\d+;\d+\.\d+;(?P<total>\d+\.\d+)$", re.I)
    PD_XML_INFO = E.perfdata_info(
        perfdata_value("used", "memory in use", v_type="i", unit="B", rrd_spec="GAUGE:0:U", base=1024, key="memory.used").get_xml(),
        perfdata_value("total", "memory total", v_type="i", unit="B", rrd_spec="GAUGE:0:U", base=1024, key="memory.total").get_xml(),
    )

    @property
    def file_name(self):
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

    def build_values(self, _host_info, _xml, in_dict):
        return self._wrap(
            _host_info,
            _xml,
            [float(in_dict[key]) for key in ["load1", "load5", "load15"]]
        )


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

    def build_values(self, _host_info, _xml, in_dict):
        return self._wrap(
            _host_info,
            _xml,
            [int(in_dict["sent"]), int(in_dict["loss"]), float(in_dict["rta"]), float(in_dict["min"]), float(in_dict["max"])]
        )


class HTTPRequestPerfdata(PerfdataObject):
    PD_RE = re.compile("^time=(?P<time>\S+)\s+size=(?P<size>\S+)\s+time_connect=(?P<time_connect>\S+)\s+time_headers=(?P<time_headers>\S+)\s+time_firstbyte=(?P<time_firstbyte>\S+)\s+time_transfer=(?P<time_transfer>\S+)$")
    PD_XML_INFO = E.perfdata_info(
        perfdata_value("time", "time needed for request", key="request.time.total", v_type="f", rrd_spec="GAUGE:0:10000").get_xml(),
        perfdata_value("size", "size of response", key="request.size", v_type="i", rrd_spec="GAUGE:0:1000000").get_xml(),
        perfdata_value("connect", "time needed for connect", key="request.time.connect", v_type="f", unit="s", rrd_spec="GAUGE:0:100").get_xml(),
        perfdata_value("headers", "time needed for headers", key="request.time.headers", v_type="f", unit="s", rrd_spec="GAUGE:0:100").get_xml(),
        perfdata_value("firstbyte", "time needed until first byte", key="request.time.firstbyte", v_type="f", unit="s", rrd_spec="GAUGE:0:100").get_xml(),
        perfdata_value("transfer", "time needed for transfer", key="request.time.transfer", v_type="f", unit="s", rrd_spec="GAUGE:0:100").get_xml(),
    )

    def build_values(self, _host_info, _xml, in_dict):
        return self._wrap(
            _host_info,
            _xml,
            [
                float(in_dict["time"].split(";")[0][:-1]),
                int(in_dict["size"].split(";")[0][:-1]),
                float(in_dict["time_connect"].split(";")[0][:-1]),
                float(in_dict["time_headers"].split(";")[0][:-1]),
                float(in_dict["time_firstbyte"].split(";")[0][:-1]),
                float(in_dict["time_transfer"].split(";")[0][:-1]),
            ]
        )


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
