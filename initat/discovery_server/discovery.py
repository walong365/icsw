# Copyright (C) 2014-2015 Andreas Lang-Nevyjel, init.at
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
""" discovery-server, discovery part """

import time

from django.db.models import Q

from initat.cluster.backbone import db_tools
from initat.cluster.backbone.available_licenses import LicenseEnum, LicenseParameterTypeEnum
from initat.cluster.backbone.models import device, ComCapability, net_ip
from initat.cluster.backbone.models.license import LicenseUsage, LicenseLockListDeviceService
from initat.snmp.snmp_struct import ResultNode
from initat.tools import logging_tools, process_tools, server_command, config_tools, threading_tools
from .config import global_config
from .ext_com_scan import BaseScanMixin, ScanBatch, WmiScanMixin, NRPEScanMixin, Dispatcher
from .hm_functions import HostMonitoringMixin
from .snmp_functions import SNMPBatch


class DiscoveryProcess(threading_tools.process_obj, HostMonitoringMixin, BaseScanMixin, WmiScanMixin, NRPEScanMixin):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        # self.add_process(build_process("build"), start=True)
        db_tools.close_connection()
        self.register_func("fetch_partition_info", self._fetch_partition_info)
        self.register_func("scan_network_info", self._scan_network_info)
        self.register_func("scan_system_info", self._scan_system_info)
        self.register_func("snmp_basic_scan", self._snmp_basic_scan)
        self.register_func("snmp_result", self._snmp_result)
        self.register_func("base_scan", self._base_scan)
        self.register_func("wmi_scan", self._wmi_scan)
        self.register_func("nrpe_scan", self._nrpe_scan)
        self.__run_idx = 0
        self.__pending_commands = {}
        self._init_subsys()

    def _scan_system_info(self, *args, **kwargs):
        srv_com = server_command.srv_command(source=args[0])
        self._iterate(srv_com, "scan_system_info", "hm")
        self.send_pool_message("remote_call_async_result", unicode(srv_com))

    def _fetch_partition_info(self, *args, **kwargs):
        srv_com = server_command.srv_command(source=args[0])
        self._iterate(srv_com, "fetch_partition_info", "hm")
        self.send_pool_message("remote_call_async_result", unicode(srv_com))

    def _scan_network_info(self, *args, **kwargs):
        srv_com = server_command.srv_command(source=args[0])
        self._iterate(srv_com, "scan_network_info", "hm")
        self.send_pool_message("remote_call_async_result", unicode(srv_com))

    def _base_scan(self, *args, **kwargs):
        srv_com = server_command.srv_command(source=args[0])
        self._iterate(srv_com, "base_scan", "base")
        self.send_pool_message("remote_call_async_result", unicode(srv_com))

    def _wmi_scan(self, *args, **kwargs):
        srv_com = server_command.srv_command(source=args[0])
        self._iterate(srv_com, "wmi_scan", "base")
        self.send_pool_message("remote_call_async_result", unicode(srv_com))

    def _nrpe_scan(self, *args, **kwargs):
        srv_com = server_command.srv_command(source=args[0])
        self._iterate(srv_com, "nrpe_scan", "base")
        self.send_pool_message("remote_call_async_result", unicode(srv_com))

    def _iterate(self, srv_com, c_name, scan_type):
        total_result = ResultNode()
        if "devices" in srv_com:
            for _dev_xml in srv_com["devices"]:
                try:
                    _dev = device.objects.get(Q(pk=int(_dev_xml.get("pk", "0"))))
                    if LicenseLockListDeviceService.objects.is_device_locked(LicenseEnum.discovery_server, _dev):
                        raise RuntimeError(u"Device {} is locked by license lock list for discovery server".format(_dev))
                except:
                    res_node = ResultNode(error="device not available: {}".format(process_tools.get_except_info()))
                else:
                    LicenseUsage.log_usage(LicenseEnum.discovery_server, LicenseParameterTypeEnum.device, _dev)

                    s_time = time.time()
                    if not self.device_is_capable(_dev, scan_type):
                        res_node = ResultNode(
                            error="device {} is missing the required ComCapability '{}'".format(
                                unicode(_dev),
                                scan_type,
                            ),
                        )
                    elif not self.device_is_idle(_dev, scan_type):
                        res_node = ResultNode(
                            error="device {} is locked by scan {}".format(
                                unicode(_dev),
                                _dev.active_scan
                            )
                        )
                    else:
                        try:
                            res_node = getattr(self, c_name)(_dev_xml, _dev)
                        except:
                            _exc_info = process_tools.exception_info()
                            for _line in _exc_info.log_lines:
                                self.log("   {}".format(_line), logging_tools.LOG_LEVEL_ERROR)
                            res_node = ResultNode(error="device {}: error calling {}: {}".format(unicode(_dev), c_name, process_tools.get_except_info()))
                            self.clear_scan(_dev)
                    e_time = time.time()
                    self.log(u"calling {} for device {} took {}".format(c_name, unicode(_dev), logging_tools.get_diff_time_str(e_time - s_time)))
                total_result.merge(res_node)
            srv_com.set_result(*total_result.get_srv_com_result())
        else:
            srv_com.set_result("no devices given", server_command.SRV_REPLY_STATE_ERROR)

    def device_is_capable(self, dev, com_type):
        _cont = True
        # scan if device has the required com_type
        if com_type != "base":
            try:
                _cap = dev.com_capability_list.get(Q(matchcode=com_type))
            except ComCapability.DoesNotExist:
                self.log(
                    "device {} is missing the ComCapability '{}'".format(
                        unicode(dev),
                        com_type
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
                _cont = False
        return _cont

    def device_is_idle(self, dev, new_scan):
        # check if device dev is idle (no scans running)
        _idle = True
        if dev.active_scan and new_scan != "base":
            self.log(
                "device {} has an active scan running: '{}', cannot start new scan '{}'".format(
                    unicode(dev),
                    dev.active_scan,
                    new_scan,
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            _idle = False
        else:
            dev.active_scan = new_scan
            dev.save(update_fields=["active_scan"])
            self.log(
                "device {} has now the active scan '{}'".format(
                    unicode(dev),
                    new_scan,
                )
            )
        return _idle

    def clear_scan(self, dev):
        self.log("clearing active_scan '{}' of device {}".format(dev.active_scan, unicode(dev)))
        dev.active_scan = ""
        dev.save(update_fields=["active_scan"])

    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(lev, what)

    def loop_post(self):
        self.__log_template.close()

    def _init_subsys(self):
        SNMPBatch.setup(self)
        ScanBatch.setup(self)
        self.register_timer(Dispatcher().dispatch_call, 1)

    def _snmp_basic_scan(self, *args, **kwargs):
        SNMPBatch(server_command.srv_command(source=args[0]))

    def _snmp_result(self, *args, **kwargs):
        _batch_id, _error, _src, _results = args
        SNMPBatch.glob_feed_snmp(_batch_id, _error, _src, _results)

    def get_route_to_devices(self, dev_list):
        src_dev = device.objects.get(Q(pk=global_config["SERVER_IDX"]))
        src_nds = src_dev.netdevice_set.all().values_list("pk", flat=True)
        self.log("device list: {}".format(", ".join([unicode(cur_dev) for cur_dev in dev_list])))
        router_obj = config_tools.router_object(self.log)
        for cur_dev in dev_list:
            routes = router_obj.get_ndl_ndl_pathes(
                src_nds,
                cur_dev.netdevice_set.all().values_list("pk", flat=True),
                only_endpoints=True,
                add_penalty=True
            )
            cur_dev.target_ip = None
            if routes:
                for route in sorted(routes):
                    found_ips = net_ip.objects.filter(Q(netdevice=route[2]))
                    if found_ips:
                        cur_dev.target_ip = found_ips[0].ip
                        break
            if cur_dev.target_ip:
                self.log(
                    "contact device {} via {}".format(
                        unicode(cur_dev),
                        cur_dev.target_ip
                    )
                )
            else:
                self.log(
                    u"no route to device {} found".format(unicode(cur_dev)),
                    logging_tools.LOG_LEVEL_ERROR
                )
        del router_obj