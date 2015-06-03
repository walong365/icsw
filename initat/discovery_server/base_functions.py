# Copyright (C) 2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of discovery-server
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
""" discovery-server, base scan functions """

import time
from initat.tools import logging_tools, process_tools, server_command
from initat.snmp.struct import ResultNode
from .struct import ExtCom
from initat.cluster.backbone.models import ComCapability
from django.db.models import Q
from lxml import etree


class BaseScanBatch(object):
    def __init__(self, srv_com, scan_dev):
        self.start_time = time.time()
        self.srv_com = srv_com
        self.device = scan_dev
        self.id = BaseScanBatch.next_batch_id(self)
        BaseScanBatch.process.get_route_to_devices([self.device])
        if self.device.target_ip:
            self._ext_com = ExtCom(self.log, self._build_command())
            self._ext_com.run()
            self.start_result = ResultNode(ok="started base_scan")
        else:
            self.log("no valid IP found for {}".format(unicode(self.device)), logging_tools.LOG_LEVEL_ERROR)
            self.start_result = ResultNode(error="no valid IP found")
            self.finish()

    def _build_command(self):
        # example: /opt/cluster/bin/nmap -sU -sS -p U:53,T:80 192.168.1.50
        _tcp_list, _udp_list = ([], [])
        _ref_lut = {}
        for _com in ComCapability.objects.all():
            for _port in _com.port_spec.strip().split():
                if _port.endswith(","):
                    _port = _port[:-1]
                _num, _type = _port.split("/")
                if _type == "tcp":
                    _tcp_list.append(int(_num))
                elif _type == "udp":
                    _udp_list.append(int(_num))
                else:
                    self.log("unknown port spec {}".format(_port), logging_tools.LOG_LEVEL_ERROR)
                _ref_lut[_port] = _com.matchcode
        _ports = [
            "U:{:d}".format(_port) for _port in _udp_list
        ] + [
            "T:{:d}".format(_port) for _port in _tcp_list
        ]
        _com = "/opt/cluster/bin/nmap -sU -sT -p {} -oX - {}".format(
            ",".join(_ports),
            self.device.target_ip,
        )
        # store port reference lut
        self.port_ref_lust = _ref_lut
        self.log("scan_command is {}".format(_com))
        return _com

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK, result=False):
        BaseScanBatch.process.log("[base {:d}] {}".format(self.id, what), log_level)
        if result:
            self.srv_com.set_result(
                what,
                server_command.log_level_to_srv_reply(log_level)
            )

    def check_ext_com(self):
        _res = self._ext_com.finished()
        if _res is not None:
            _output = self._ext_com.communicate()
            if _res:
                self.log(
                    "error calling nmap [{:d}]: {}".format(
                        _res,
                        _output[0] + _output[1]
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                self.log(
                    "resulting XML has {:d} bytes".format(
                        len(_output[0]),
                    )
                )
                _xml = etree.fromstring(_output[0])
                print etree.tostring(_xml, pretty_print=True)
            self.finish()

    def finish(self):
        if self.device.active_scan:
            BaseScanBatch.process.clear_scan(self.device)
        self.end_time = time.time()
        self.log("finished in {}".format(logging_tools.get_diff_time_str(self.end_time - self.start_time)))
        BaseScanBatch.remove_batch(self)

    @staticmethod
    def next_batch_id(bsb):
        BaseScanBatch.base_run_id += 1
        BaseScanBatch.batch_lut[BaseScanBatch.base_run_id] = bsb
        return BaseScanBatch.base_run_id

    @staticmethod
    def setup(proc):
        BaseScanBatch.process = proc
        BaseScanBatch.base_run_id = 0
        BaseScanBatch.batch_lut = {}

    @staticmethod
    def remove_batch(bsb):
        del BaseScanBatch.batch_lut[bsb.id]
        del bsb

    @staticmethod
    def g_check_ext_com():
        _keys = list(BaseScanBatch.batch_lut.keys())
        [BaseScanBatch.batch_lut[_key].check_ext_com() for _key in _keys]


class BaseScanMixin(object):
    def base_scan(self, dev_com, scan_dev):
        self._register_base_timer()
        return BaseScanBatch(dev_com, scan_dev).start_result

    def _register_base_timer(self):
        if not hasattr(self, "_base_timer_registered"):
            self.log("registering base_timer")
            self._base_timer_registered = True
            self.register_timer(self._check_base_commands, 2)

    def _check_base_commands(self):
        BaseScanBatch.g_check_ext_com()
