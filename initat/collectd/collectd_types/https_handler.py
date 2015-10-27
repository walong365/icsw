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
""" http(s) performance data """

import re

from lxml.builder import E

from .base import PerfdataObject, perfdata_value


class HTTPRequestPerfdata(PerfdataObject):
    PD_RE = re.compile(
        "^time=(?P<time>\S+)\s+size=(?P<size>\S+)\s+time_connect=(?P<time_connect>\S+)\s+"
        "time_headers=(?P<time_headers>\S+)\s+time_firstbyte=(?P<time_firstbyte>\S+)\s+time_transfer=(?P<time_transfer>\S+)$"
    )
    PD_XML_INFO = E.perfdata_info(
        perfdata_value("time", "time needed for request", key="request.time.total", v_type="f", rrd_spec="GAUGE:0:10000").get_xml(),
        perfdata_value("size", "size of response", key="request.size", v_type="i", rrd_spec="GAUGE:0:1000000").get_xml(),
        perfdata_value("connect", "time needed for connect", key="request.time.connect", v_type="f", unit="s", rrd_spec="GAUGE:0:100").get_xml(),
        perfdata_value("headers", "time needed for headers", key="request.time.headers", v_type="f", unit="s", rrd_spec="GAUGE:0:100").get_xml(),
        perfdata_value("firstbyte", "time needed until first byte", key="request.time.firstbyte", v_type="f", unit="s", rrd_spec="GAUGE:0:100").get_xml(),
        perfdata_value("transfer", "time needed for transfer", key="request.time.transfer", v_type="f", unit="s", rrd_spec="GAUGE:0:100").get_xml(),
    )

    @property
    def pd_name(self):
        return "http_request"

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


class HTTPsRequestPerfdata(PerfdataObject):
    PD_RE = re.compile(
        "^time=(?P<time>\S+)\s+size=(?P<size>\S+)\s+time_connect=(?P<time_connect>\S+)\s+"
        "time_ssl=(?P<time_ssl>\S+)\s+time_headers=(?P<time_headers>\S+)\s+time_firstbyte=(?P<time_firstbyte>\S+)\s+time_transfer=(?P<time_transfer>\S+)$"
    )
    PD_XML_INFO = E.perfdata_info(
        perfdata_value("time", "time needed for request", key="request.time.total", v_type="f", rrd_spec="GAUGE:0:10000").get_xml(),
        perfdata_value("size", "size of response", key="request.size", v_type="i", rrd_spec="GAUGE:0:1000000").get_xml(),
        perfdata_value("connect", "time needed for connect", key="request.time.connect", v_type="f", unit="s", rrd_spec="GAUGE:0:100").get_xml(),
        perfdata_value("ssl", "time needed for SSL", key="request.time.ssl", v_type="f", rrd_spec="GAUGE:0:10000").get_xml(),
        perfdata_value("headers", "time needed for headers", key="request.time.headers", v_type="f", unit="s", rrd_spec="GAUGE:0:100").get_xml(),
        perfdata_value("firstbyte", "time needed until first byte", key="request.time.firstbyte", v_type="f", unit="s", rrd_spec="GAUGE:0:100").get_xml(),
        perfdata_value("transfer", "time needed for transfer", key="request.time.transfer", v_type="f", unit="s", rrd_spec="GAUGE:0:100").get_xml(),
    )

    @property
    def pd_name(self):
        return "https_request"

    def build_values(self, _host_info, _xml, in_dict):
        return self._wrap(
            _host_info,
            _xml,
            [
                float(in_dict["time"].split(";")[0][:-1]),
                int(in_dict["size"].split(";")[0][:-1]),
                float(in_dict["time_connect"].split(";")[0][:-1]),
                float(in_dict["time_ssl"].split(";")[0][:-1]),
                float(in_dict["time_headers"].split(";")[0][:-1]),
                float(in_dict["time_firstbyte"].split(";")[0][:-1]),
                float(in_dict["time_transfer"].split(";")[0][:-1]),
            ]
        )
