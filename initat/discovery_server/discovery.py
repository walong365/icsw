# Copyright (C) 2014-2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of icsw-server-server
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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
"""
discovery-server, discovery part
"""

import copy
import time

from django.db.models import Q

from initat.cluster.backbone import db_tools
from initat.cluster.backbone.models import device, ActiveDeviceScanEnum, config
from initat.snmp.snmp_struct import ResultNode
from initat.tools import logging_tools, process_tools, server_command, threading_tools
from initat.tools.server_mixins import EggConsumeMixin, GetRouteToDevicesMixin
from .config import global_config
from .ext_com_scan import BaseScanMixin, ScanBatch, WmiScanMixin, Dispatcher
from .hm_functions import HostMonitoringMixin
from .snmp_functions import SNMPBatch


class DiscoveryProcess(GetRouteToDevicesMixin, threading_tools.icswProcessObj, HostMonitoringMixin, BaseScanMixin, WmiScanMixin, EggConsumeMixin):
    def process_init(self):
        # hm ...
        self.global_config = global_config
        global_config.enable_pm(self)
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            context=self.zmq_context
        )
        db_tools.close_connection()
        self.register_func("fetch_partition_info", self._fetch_partition_info)
        self.register_func("scan_network_info", self._scan_network_info)
        self.register_func("scan_system_info", self._scan_system_info)
        self.register_func("snmp_basic_scan", self._snmp_basic_scan)
        self.register_func("snmp_result", self._snmp_result)
        self.register_func("base_scan", self._base_scan)
        self.register_func("wmi_scan", self._wmi_scan)
        self.register_func("ext_con_result", self._ext_con_result)
        self.register_func("host_monitor_result", self._host_monitor_result)
        self.EC.init(global_config)
        self._server = device.objects.get(Q(pk=global_config["SERVER_IDX"]))
        self._config = config.objects.get(Q(pk=global_config["CONFIG_IDX"]))
        self.__run_idx = 0
        # global job list
        self.__job_list = []
        self.__pending_commands = {}
        self._init_subsys()

    def _scan_system_info(self, *args, **kwargs):
        srv_com = server_command.srv_command(source=args[0])
        self._iterate(srv_com, "scan_system_info", ActiveDeviceScanEnum.HM)
        self.send_pool_message("remote_call_async_result", str(srv_com))
        self._check_for_pending_jobs()

    def _fetch_partition_info(self, *args, **kwargs):
        srv_com = server_command.srv_command(source=args[0])
        self._iterate(srv_com, "fetch_partition_info", ActiveDeviceScanEnum.HM)
        self.send_pool_message("remote_call_async_result", str(srv_com))
        self._check_for_pending_jobs()

    def _scan_network_info(self, *args, **kwargs):
        srv_com = server_command.srv_command(source=args[0])
        self._iterate(srv_com, "scan_network_info", ActiveDeviceScanEnum.HM)
        self.send_pool_message("remote_call_async_result", str(srv_com))
        self._check_for_pending_jobs()

    def _base_scan(self, *args, **kwargs):
        srv_com = server_command.srv_command(source=args[0])
        self._iterate(srv_com, "base_scan", ActiveDeviceScanEnum.BASE)
        self.send_pool_message("remote_call_async_result", str(srv_com))
        self._check_for_pending_jobs()

    def _wmi_scan(self, *args, **kwargs):
        srv_com = server_command.srv_command(source=args[0])
        self._iterate(srv_com, "wmi_scan", ActiveDeviceScanEnum.BASE)
        self.send_pool_message("remote_call_async_result", str(srv_com))
        self._check_for_pending_jobs()

    def _snmp_basic_scan(self, *args, **kwargs):
        SNMPBatch(server_command.srv_command(source=args[0]))

    def _snmp_result(self, *args, **kwargs):
        _batch_id, _error, _src, _results = args
        SNMPBatch.glob_feed_snmp(_batch_id, _error, _src, _results)

    def _ext_con_result(self, *args, **kwargs):
        run_idx, srv_reply = args
        self.dispatcher.got_result(run_idx, server_command.srv_command(source=srv_reply))

    def _host_monitor_result(self, *args, **kwargs):
        run_index, srv_reply = args
        self.dispatcher.handle_hm_result(run_index, server_command.srv_command(source=srv_reply))

    def _iterate(self, srv_com, c_name, scan_type_enum):
        total_result = ResultNode()
        if "devices" in srv_com:
            for _dev_xml in srv_com["devices"]:
                _dev = device.objects.get(Q(pk=int(_dev_xml.get("pk", "0"))))
                if self.EC.consume("discover", _dev):
                    if not self.device_is_capable(_dev, scan_type_enum):
                        res_node = ResultNode(
                            error="device {} is missing the required ComCapability '{}'".format(
                                str(_dev),
                                scan_type_enum,
                            ),
                        )
                    else:
                        _new_lock = self.device_is_idle(_dev, scan_type_enum)
                        if _new_lock:
                            self.__job_list.append(
                                (c_name, _dev, scan_type_enum, _new_lock, copy.deepcopy(_dev_xml))
                            )
                            res_node = ResultNode(ok="starting scan for device {}".format(str(_dev)))
                        else:
                            res_node = ResultNode(warning="lock not possible for device {}".format(str(_dev)))
                else:
                    res_node = ResultNode(error="device not allowed (ova error)")
                total_result.merge(res_node)
            srv_com.set_result(*total_result.get_srv_com_result())
        else:
            srv_com.set_result("no devices given", server_command.SRV_REPLY_STATE_ERROR)

        # start calls
    def _check_for_pending_jobs(self):
        for c_name, _dev, scan_type_enum, _new_lock, _dev_xml in self.__job_list:
            # todo: make calls parallel
            s_time = time.time()
            try:
                getattr(self, c_name)(_dev_xml, _dev)
            except:
                _exc_info = process_tools.icswExceptionInfo()
                for _line in _exc_info.log_lines:
                    self.log("   {}".format(_line), logging_tools.LOG_LEVEL_ERROR)
            finally:
                [self.log(_what, _level) for _what, _level in _new_lock.close()]
            e_time = time.time()
            self.log("calling {} for device {} took {}".format(c_name, str(_dev), logging_tools.get_diff_time_str(e_time - s_time)))
        self.__job_list = []

    def device_is_capable(self, dev, lock_type):
        # lock_type is an ActiveDeviceScanEnum
        req_caps = device.get_com_caps_for_lock(lock_type)
        if req_caps:
            req_caps = [_value.name for _value in req_caps]
            _cap = dev.com_capability_list.filter(Q(matchcode__in=req_caps))
            if len(_cap):
                _cont = True
            else:
                self.log(
                    "device {} is missing the ComCapability '{}'".format(
                        str(dev),
                        ", ".join([str(_cap) for _cap in req_caps]),
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
                _cont = False
        else:
            _cont = True
        return _cont

    def device_is_idle(self, dev, lock_type):
        # lock_type is an ActiveDeviceScanEnum
        # check if device dev is idle (no scans running)
        _new_lock, _log_lines = dev.lock_possible(lock_type, dev, self._server, self._config)
        [self.log(_what, _log_level) for _what, _log_level in _log_lines]
        return _new_lock

    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(lev, what)

    def loop_post(self):
        self.__log_template.close()

    def _init_subsys(self):
        SNMPBatch.setup(self)
        ScanBatch.setup(self)
        self.dispatcher = Dispatcher(self)
        self.register_timer(self.dispatcher.dispatch_call, 1)
        self.register_timer(self.dispatcher.schedule_call, 10)
