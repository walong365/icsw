# Copyright (C) 2015-2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of discovery-server
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
""" discovery-server, base scan functions """


import collections
import datetime
import time
import traceback
import netaddr
import ast

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from lxml import etree

from initat.cluster.backbone.models import ComCapability, netdevice, netdevice_speed, net_ip, network, \
    device_variable, AssetRun, RunStatus, BatchStatus, ScanType, AssetBatch, RunResult, \
    DispatcherSettingScheduleEnum, ScheduleItem, device, DispatcherLink, NmapScan, BackgroundJobState, \
    background_job
from initat.discovery_server.wmi_struct import WmiUtils
from initat.icsw.service.instance import InstanceXML
from initat.snmp.snmp_struct import ResultNode
from initat.tools import logging_tools, process_tools, server_command, ipvx_tools
from .config import global_config
from .discovery_struct import ExtCom
from initat.cluster.backbone.models.asset.dynamic_asset import ASSETTYPE_HM_COMMAND_MAP
from initat.tools.bgnotify import create_bg_job
from initat.tools.bgnotify.create import propagate_channel_object
from initat.constants import PlatformSystemTypeEnum

DEFAULT_NRPE_PORT = 5666

# the mapping between the result of the server command and the result of the
# asset run
SERVER_RESULT_RUN_RESULT = {
    server_command.SRV_REPLY_STATE_OK: RunResult.SUCCESS,
    server_command.SRV_REPLY_STATE_WARN: RunResult.WARNING,
    server_command.SRV_REPLY_STATE_ERROR: RunResult.FAILED,
    server_command.SRV_REPLY_STATE_CRITICAL: RunResult.FAILED,
    server_command.SRV_REPLY_STATE_UNSET: RunResult.UNKNOWN,
}

HM_CMD_TUPLES = [(asset_type, hm_command, 60 * 5) for asset_type, hm_command in list(ASSETTYPE_HM_COMMAND_MAP.items())]


class ScanBatch(object):
    """
    Base class for all scan batches.
    Each of these currently has related mixins, see below.
    """
    # these are set by setup() and written here to make code analysis happy
    process = None
    _base_run_id = None
    _batch_lut = None

    SCAN_TYPE = "scan"  # overwrite in subclass

    def __init__(self, dev_com, scan_dev):
        self.start_time = time.time()
        self.dev_com = dev_com
        self.device = scan_dev
        self.id = self.next_batch_id(self)
        self.end_time = None

        if "scan_address" in dev_com.attrib:
            self.device.target_ip = dev_com.attrib["scan_address"]
        else:
            self.__class__.process.get_route_to_devices([self.device])

        if not self.device.target_ip:
            self.log("no valid IP found for {}".format(str(self.device)), logging_tools.LOG_LEVEL_ERROR)
            self.start_result = ResultNode(error="no valid IP found")
            self.finish()
        # NOTE: set self.start_result in subclass accordingly

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__class__.process.log("[{} {:d}] {}".format(self.__class__.SCAN_TYPE, self.id, what), log_level)

    def check_ext_com(self):
        # this is called periodically
        raise NotImplementedError()

    def finish(self):
        # TODO: add locking
        self.end_time = time.time()
        self.log("finished in {}".format(logging_tools.get_diff_time_str(self.end_time - self.start_time)))
        self.__class__.remove_batch(self)

    @classmethod
    def next_batch_id(cls, bsb):
        cls._base_run_id += 1
        cls._batch_lut[cls._base_run_id] = bsb
        return cls._base_run_id

    @classmethod
    def setup(cls, proc):
        cls.process = proc
        cls._base_run_id = 0
        cls._batch_lut = {}

    @classmethod
    def remove_batch(cls, bsb):
        del cls._batch_lut[bsb.id]

    @classmethod
    def g_check_ext_com(cls):
        # iterate on copy since function calls can change the dict
        for item in list(cls._batch_lut.values()):
            item.check_ext_com()


class BaseScanBatch(ScanBatch):
    """ Batch class for base scan (scans for capabilities by open ports) """
    SCAN_TYPE = 'base'

    def __init__(self, dev_com, scan_dev):
        super(BaseScanBatch, self).__init__(dev_com, scan_dev)

        if self.device.target_ip:
            self._ext_com = ExtCom(self.log, self._build_command())
            self._ext_com.run()
            self.start_result = ResultNode(ok="started base_scan")

    def _build_command(self):
        # example: /opt/cluster/bin/nmap -sU -sS -p U:53,T:80 192.168.1.50
        _tcp_list, _udp_list = ([], [])
        _ref_lut = {}
        for _com in ComCapability.objects.all():
            for _port in _com.port_spec.strip().split():
                if _port.endswith(","):
                    _port = _port[:-1]
                _num, _type = _port.split("/")
                if _com.name == "NRPE":
                    nrpe_port = device_variable.objects.get_device_variable_value(self.device, "NRPE_PORT",
                                                                                  DEFAULT_NRPE_PORT)
                    _port = "{:d}/{}".format(nrpe_port, _type)
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
        self.port_ref_lut = _ref_lut
        self.log("scan_command is {}".format(_com))
        return _com

    def check_ext_com(self):
        _res = self._ext_com.finished()
        if _res is not None:
            _output = self._ext_com.communicate()
            if _res != 0:
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
                found_comspecs = set()
                for _port in _xml.xpath(".//port[state[@state]]", smart_strings=False):
                    _portspec = "{}/{}".format(
                        _port.attrib["portid"],
                        _port.attrib["protocol"],
                    )
                    _state = _port.find("state").get("state")
                    self.log("state of port {} is {}".format(_portspec, _state))
                    if _portspec in self.port_ref_lut:
                        if _state.count("open"):
                            found_comspecs.add(self.port_ref_lut[_portspec])
                    else:
                        self.log("unknown portspec {}".format(_portspec), logging_tools.LOG_LEVEL_WARN)
                if found_comspecs:
                    self.log(
                        "found {}: {}".format(
                            logging_tools.get_plural("comspec", len(found_comspecs)),
                            ", ".join(found_comspecs)
                        )
                    )
                    self.device.com_capability_list.clear()
                    for _spec in found_comspecs:
                        self.device.com_capability_list.add(ComCapability.objects.get(Q(matchcode=_spec)))
                else:
                    # todo: handle some kind of strict mode and delete all comspecs
                    self.log("no comspecs found", logging_tools.LOG_LEVEL_WARN)
            self.finish()


class WmiScanBatch(ScanBatch):
    SCAN_TYPE = 'wmi'

    NETWORK_ADAPTER_MODEL = "Win32_NetworkAdapter"
    NETWORK_ADAPTER_CONFIGURATION_MODEL = "Win32_NetworkAdapterConfiguration"

    def __init__(self, dev_com, scan_dev):
        super(WmiScanBatch, self).__init__(dev_com, scan_dev)

        self.username = dev_com.attrib.get('username')
        self.password = dev_com.attrib.get('password')
        self.discard_disabled_interfaces = bool(int(dev_com.attrib.get('discard_disabled_interfaces')))

        self._ext_coms = None

        if self.device.target_ip:
            self.__init()

    def __init(self):
        _QueryData = collections.namedtuple("_QueryData", ['columns', 'where_clause'])
        query_structures = {
            self.NETWORK_ADAPTER_MODEL:
                _QueryData(
                    ['Name', 'Speed', 'MACAddress', 'Index'],
                    "WHERE NetEnabled = TRUE" if self.discard_disabled_interfaces else "",
                ),
            self.NETWORK_ADAPTER_CONFIGURATION_MODEL:
                _QueryData(['IPAddress', 'IPSubnet', 'MTU', 'Index', 'DefaultIPGateway'], "")
        }

        self._ext_coms = {}

        for query_structure in query_structures.items():
            cmd = WmiUtils.get_wmic_cmd(
                username=self.username,
                password=self.password,
                target_ip=self.device.target_ip,
                columns=query_structure[1].columns,
                table=query_structure[0],
                where_clause=query_structure[1].where_clause
            )
            self.log("starting WMI scan with command: {}".format(cmd))
            ext_com = ExtCom(self.log, cmd, shell=False)  # shell=False since args must not be parsed again
            ext_com.run()
            self._ext_coms[query_structure[0]] = ext_com

        self.start_result = ResultNode(ok="started base_scan")

    def check_ext_com(self):
        if all(ext_com.finished() is not None for ext_com in self._ext_coms.values()):

            outputs = {ext_com_key: ext_com.communicate() for ext_com_key, ext_com in self._ext_coms.items()}

            any_err = False
            for ext_com_key, ext_com in self._ext_coms.items():
                if ext_com.result != 0:
                    any_err = True
                    self.log("Error querying {}, output:".format(ext_com_key), logging_tools.LOG_LEVEL_ERROR)
                    self.log("Stdout: {}".format(outputs[ext_com_key][0]), logging_tools.LOG_LEVEL_ERROR)
                    self.log("Stderr: {}".format(outputs[ext_com_key][1]), logging_tools.LOG_LEVEL_ERROR)

                if outputs[ext_com_key][1]:
                    self.log(
                        "Query for {} wrote to stderr: {}".format(
                            ext_com_key,
                            outputs[ext_com_key][1]
                        ),
                        logging_tools.LOG_LEVEL_WARN
                    )

            if not any_err:
                network_adapter_data = WmiUtils.parse_wmic_output(outputs[self.NETWORK_ADAPTER_MODEL][0])
                network_adapter_configuration_data = WmiUtils.parse_wmic_output(
                    outputs[self.NETWORK_ADAPTER_CONFIGURATION_MODEL][0]
                )

                nd_speed_lut = netdevice_speed.build_lut()
                updated_nds, created_nds, created_ips, existing_ips = [], [], [], []

                # iterate by adapter since only adapters are filtered
                for adapter in network_adapter_data:
                    adapter_index = int(adapter['Index'])
                    adapter_name = adapter['Name']
                    # corresponding adapter and adapter_configuration have same index according to some sources
                    # http://blogs.technet.com/b/heyscriptingguy/archive/2011/10/07/use-powershell-to-identify-your-real-network-adapter.aspx
                    # http://blogs.technet.com/b/heyscriptingguy/archive/2005/06/14/how-can-i-associate-a-network-connection-with-an-ip-address.aspx
                    adapter_configuration = next(c for c in network_adapter_configuration_data
                                                 if int(c['Index']) == adapter_index)

                    device_netdevices = netdevice.objects.filter(device=self.device)

                    # find existing dev by idx or else by name
                    present_nds = [nd for nd in device_netdevices if nd.wmi_interface_index == adapter_index]
                    if not present_nds:
                        present_nds = [nd for nd in device_netdevices if nd.devname == adapter_name]

                    if len(present_nds) > 1:
                        self.log("Error: Found multiple netdevices matching specification:" +
                                 "Index: {}; Name: {}; Net devices: {}".format(
                                     adapter['Index'], adapter['Name'], present_nds)
                                 )
                    else:
                        if present_nds:  # only one
                            nd = present_nds[0]
                            updated_nds.append(nd)
                        else:
                            nd = netdevice(
                                device=self.device,
                                wmi_interface_index=adapter_index,
                                force_network_device_type_match=False,
                            )
                            created_nds.append(nd)

                        nd.devname = adapter_name
                        nd.macaddr = adapter['MACAddress'] or ""  # must not be None
                        nd.mtu = adapter_configuration['MTU']
                        nd.speed = int(adapter['Speed'])
                        nd.netdevice_speed = nd_speed_lut.get(int(adapter['Speed']), nd_speed_lut.get(0))
                        nd.save()

                        for ip_found in WmiUtils.WmiList.handle(adapter_configuration['IPAddress']):
                            try:
                                ip_found_struct = ipvx_tools.IPv4(ip_found)
                            except ValueError:
                                self.log("Found IP which is not supported: {}".format(ip_found),
                                         logging_tools.LOG_LEVEL_WARN)
                            else:
                                # find ipv4 subnet
                                netmasks_found = []
                                for _nm in WmiUtils.WmiList.handle(adapter_configuration["IPSubnet"]):
                                    try:
                                        netmasks_found.append(ipvx_tools.IPv4(_nm))
                                    except ValueError:
                                        pass

                                if not netmasks_found:
                                    self.log("No netmask found among: {}".format(adapter['IPSubnet']))
                                else:
                                    netmask_found_struct = netmasks_found[0]

                                    _gws = []
                                    for _gw in WmiUtils.WmiList.handle(adapter_configuration["DefaultIPGateway"]):
                                        try:
                                            _gws.append(ipvx_tools.IPv4(_gw))
                                        except ValueError:
                                            pass

                                    gw_found_struct = _gws[0] if _gws else None

                                    cur_nw = network.objects.get_or_create_network(
                                        network_addr=ip_found_struct & netmask_found_struct,
                                        netmask=netmask_found_struct,
                                        gateway=gw_found_struct,
                                        context="WMI",
                                    )

                                    try:
                                        nip = net_ip.objects.get(netdevice=nd, ip=ip_found)
                                        existing_ips.append(nip)
                                    except net_ip.DoesNotExist:
                                        try:
                                            nip = net_ip(
                                                netdevice=nd,
                                                ip=ip_found,
                                                network=cur_nw,
                                            )
                                            nip.save()
                                            created_ips.append(nip)
                                        except ValidationError as e:
                                            self.log(
                                                "Failed to create ip {} for netdevice {}: {}".format(ip_found, nd, e),
                                                logging_tools.LOG_LEVEL_ERROR
                                            )
                                            self.log(traceback.format_exc(e))

                self.log(
                    "Created {}, updated {}, created {}, found {}".format(
                        logging_tools.get_plural("net device", len(created_ips)),
                        logging_tools.get_plural("net device", len(updated_nds)),
                        logging_tools.get_plural("ip", len(created_ips)),
                        logging_tools.get_plural("existing ip", len(existing_ips)),
                    )
                )

            self.finish()

        # TODO; check peers? (cf. snmp)


class _ExtComScanMixin(object):
    log = None
    register_timer = None
    """ Base class for all scan mixins """
    def _register_timer(self):
        if not hasattr(self, "_timer_registered"):
            self.log("registering base_timer")
            self._timer_registered = True
            self.register_timer(self._check_commands, 2)

    @staticmethod
    def _check_commands():
        ScanBatch.g_check_ext_com()


class BaseScanMixin(_ExtComScanMixin):
    def base_scan(self, dev_com, scan_dev):
        self._register_timer()
        return BaseScanBatch(dev_com, scan_dev).start_result


class WmiScanMixin(_ExtComScanMixin):
    def wmi_scan(self, dev_com, scan_dev):
        self._register_timer()
        return WmiScanBatch(dev_com, scan_dev).start_result


def align_second(now, sched_start_second):
    while True:
        now += datetime.timedelta(seconds=1)
        if now.second == sched_start_second:
            break

    return now


def align_minute(now, sched_start_minute):
    while True:
        now += datetime.timedelta(minutes=1)
        if now.minute == sched_start_minute:
            break

    return now


def align_hour(now, sched_start_hour):
    while True:
        now += datetime.timedelta(hours=1)
        if now.hour == sched_start_hour:
            break
    return now


def align_day(now, sched_start_day):
    while True:
        if now.weekday() == sched_start_day:
            break
        now += datetime.timedelta(days=1)
    return now


def align_week(now, sched_start_week):
    while True:
        now += datetime.timedelta(days=1)
        if (now.isocalendar()[1] % 4) == sched_start_week:
            break
    return now


def align_month(now, sched_start_month):
    while True:
        now += datetime.timedelta(days=1)
        if now.month == sched_start_month:
            break
    return now


def align_time_to_baseline(now, ds):
    if ds.run_schedule.baseline == DispatcherSettingScheduleEnum.minute:
        now = align_second(now, ds.sched_start_second)
    elif ds.run_schedule.baseline == DispatcherSettingScheduleEnum.hour:
        now = align_second(now, ds.sched_start_second)
        now = align_minute(now, ds.sched_start_minute)

    elif ds.run_schedule.baseline == DispatcherSettingScheduleEnum.day:
        now = align_second(now, ds.sched_start_second)
        now = align_minute(now, ds.sched_start_minute)
        now = align_hour(now, ds.sched_start_hour)

    elif ds.run_schedule.baseline == DispatcherSettingScheduleEnum.week:
        now = align_second(now, ds.sched_start_second)
        now = align_minute(now, ds.sched_start_minute)
        now = align_hour(now, ds.sched_start_hour)
        now = align_day(now, ds.sched_start_day)

    elif ds.run_schedule.baseline == DispatcherSettingScheduleEnum.month:
        now = align_second(now, ds.sched_start_second)
        now = align_minute(now, ds.sched_start_minute)
        now = align_hour(now, ds.sched_start_hour)
        now = align_day(now, ds.sched_start_day)
        now = align_week(now, ds.sched_start_week)

    elif ds.run_schedule.baseline == DispatcherSettingScheduleEnum.year:
        now = align_second(now, ds.sched_start_second)
        now = align_minute(now, ds.sched_start_minute)
        now = align_hour(now, ds.sched_start_hour)
        now = align_day(now, ds.sched_start_day)
        now = align_week(now, ds.sched_start_week)
        now = align_month(now, ds.sched_start_month)

    return now


def get_time_inc_from_ds(ds):
    if ds.run_schedule.baseline == DispatcherSettingScheduleEnum.second:
        time_inc = datetime.timedelta(seconds=(1 * ds.mult))
    elif ds.run_schedule.baseline == DispatcherSettingScheduleEnum.minute:
        time_inc = datetime.timedelta(minutes=(1 * ds.mult))
    elif ds.run_schedule.baseline == DispatcherSettingScheduleEnum.hour:
        time_inc = datetime.timedelta(hours=(1 * ds.mult))
    elif ds.run_schedule.baseline == DispatcherSettingScheduleEnum.day:
        time_inc = datetime.timedelta(days=(1 * ds.mult))
    elif ds.run_schedule.baseline == DispatcherSettingScheduleEnum.week:
        time_inc = datetime.timedelta(weeks=(1 * ds.mult))
    elif ds.run_schedule.baseline == DispatcherSettingScheduleEnum.month:
        time_inc = datetime.timedelta(weeks=(4 * 1 * ds.mult))
    elif ds.run_schedule.baseline == DispatcherSettingScheduleEnum.year:
        time_inc = datetime.timedelta(weeks=(52 * 1 * ds.mult))
    else:
        time_inc = None

    return time_inc


class HostMonitoringCommand:
    host_monitoring_commands = {}

    def __init__(self, callback, callback_dict, timeout=60, always_call_callback=False, command_string="N/A"):
        self.callback = callback
        self.callback_dict = callback_dict
        self.run_index = self.__get_free_run_index()
        self.host_monitoring_commands[self.run_index] = self
        self.timeout_date = timezone.now() + datetime.timedelta(seconds=timeout)
        self.always_call_callback = always_call_callback
        self.command_string = command_string

    def __get_free_run_index(self):
        run_index = 1
        while True:
            if run_index not in self.host_monitoring_commands:
                return run_index
            run_index += 1

    def handle(self, result=None):
        if result or self.always_call_callback:
            self.callback(self.callback_dict, result)
        del self.host_monitoring_commands[self.run_index]


class Dispatcher(object):
    def __init__(self, discovery_process):
        self.discovery_process = discovery_process
        # quasi-static constants
        self.__hm_port = InstanceXML(quiet=True).get_port_dict("host-monitoring", command=True)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.discovery_process.log("[Disp] {}".format(what), log_level)

    @staticmethod
    def schedule_call():
        # called every 10 seconds
        _now = timezone.now().replace(microsecond=0)

        links = DispatcherLink.objects.all().select_related("dispatcher_setting")

        for schedule_item in ScheduleItem.objects.all():
            if schedule_item.run_now:
                continue

            found_links = links.filter(
                dispatcher_setting=schedule_item.dispatch_setting,
                model_name=schedule_item.model_name,
                schedule_handler=schedule_item.schedule_handler,
                object_id=schedule_item.object_id)

            if not found_links:
                schedule_item.delete()

        for link in links:
            dispatcher_setting = link.dispatcher_setting

            # every object_id, model_name, schedule_handler and dispatcher_setting  pair should have the next
            # two planned runs created
            schedule_items = [schedule_item for schedule_item in ScheduleItem.objects.filter(
                object_id=link.object_id,
                model_name=link.model_name,
                schedule_handler=link.schedule_handler,
                dispatch_setting=link.dispatcher_setting)]

            if len(schedule_items) == 0:
                new_schedule_item = ScheduleItem.objects.create(
                    model_name=link.model_name,
                    object_id=link.object_id,
                    planned_date=align_time_to_baseline(_now, dispatcher_setting),
                    dispatch_setting=dispatcher_setting,
                    schedule_handler=link.schedule_handler,
                    schedule_handler_data=link.schedule_handler_data
                )
                schedule_items.append(new_schedule_item)

            if len(schedule_items) == 1:
                last_schedule_item = schedule_items[0]
                ScheduleItem.objects.create(
                    model_name=link.model_name,
                    object_id=link.object_id,
                    planned_date=last_schedule_item.planned_date + get_time_inc_from_ds(dispatcher_setting),
                    dispatch_setting=dispatcher_setting,
                    schedule_handler=link.schedule_handler,
                    schedule_handler_data=link.schedule_handler_data
                )

    def dispatch_call(self):
        _now = timezone.now().replace(microsecond=0)

        for asset_batch in AssetBatch.objects.filter(
            run_status__in=[
                BatchStatus.PLANNED, BatchStatus.RUNNING, BatchStatus.FINISHED_RUNS, BatchStatus.GENERATING_ASSETS
            ]
        ):
            if asset_batch.run_start_time:
                diff_time = (_now - asset_batch.run_start_time).total_seconds()
                if diff_time > 86400:
                    self.log("Closing pending/processing AssetBatch [now={}, run_start_time={}, diff_time={}]".format(
                        _now, asset_batch.run_start_time, diff_time), logging_tools.LOG_LEVEL_ERROR)

                    asset_batch.run_end_time = _now
                    asset_batch.run_status = BatchStatus.FINISHED
                    asset_batch.save()

        for schedule_item in ScheduleItem.objects.all():
            if schedule_item.run_now or schedule_item.planned_date < _now:
                schedule_handler_function = getattr(self, schedule_item.schedule_handler)
                schedule_handler_function(schedule_item)
                schedule_item.delete()

        # timeout handling
        _now = timezone.now()
        for run_index, host_monitoring_command in list(HostMonitoringCommand.host_monitoring_commands.items()):
            if _now > host_monitoring_command.timeout_date:
                self.log("HostMonitoring command [run_index:{} | command:{}] timed out".format(
                    host_monitoring_command.run_index, host_monitoring_command.command_string))
                host_monitoring_command.handle()
                self.discovery_process.send_pool_message("host_monitoring_command_timeout_handler", run_index)

    def asset_schedule_handler(self, schedule_item):
        # check for allowed
        try:
            target_device = device.objects.get(idx=schedule_item.object_id)
        except device.DoesNotExist:
            self.log(
                "device with id {:d} does not exist".format(schedule_item.object_id),
                logging_tools.LOG_LEVEL_ERROR
            )
        else:
            if self.discovery_process.EC.consume("asset", target_device):
                cap_dict = {
                    _com.matchcode: True for _com in target_device.com_capability_list.all()
                    }

                self.discovery_process.get_route_to_devices([target_device])

                new_asset_batch = AssetBatch(device=target_device, user=schedule_item.user)
                new_asset_batch.manual_scan = schedule_item.run_now
                new_asset_batch.state_init()
                if cap_dict.get("hm", False) and target_device.target_ip:
                    self.log("Starting asset scan of device {} [ip: {}]".format(target_device.name,
                             target_device.target_ip))

                    new_asset_batch.save()

                    for _idx, (runtype, _command, timeout) in enumerate(HM_CMD_TUPLES):
                        run_index = len(new_asset_batch.assetrun_set.all())
                        new_asset_run = AssetRun(
                            run_index=run_index,
                            run_type=runtype,
                            run_status=RunStatus.PLANNED,
                            scan_type=ScanType.HM,
                            batch_index=_idx,
                            asset_batch=new_asset_batch
                        )
                        new_asset_run.save()

                        callback_dict = {
                            "asset_batch_id": new_asset_batch.idx,
                            "asset_run_id": run_index
                        }

                        hm_command = HostMonitoringCommand(self.asset_schedule_handler_callback, callback_dict,
                                                           timeout=timeout,
                                                           always_call_callback=True,
                                                           command_string=_command)
                        conn_str = "tcp://{}:{:d}".format(target_device.target_ip, self.__hm_port)
                        new_srv_com = server_command.srv_command(command=_command)

                        self.discovery_process.send_pool_message(
                            "send_host_monitor_command",
                            hm_command.run_index,
                            conn_str,
                            str(new_srv_com)
                        )
                else:
                    new_asset_batch.state_finished()
                    new_asset_batch.error_string = "No hostmonitor communication capability found!"
                    new_asset_batch.save()

                    self.log(
                        "Skipping non-capable device {}".format(
                            str(target_device)
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )

    def asset_schedule_handler_callback(self, callback_dict, result):
        asset_batch_id = callback_dict["asset_batch_id"]
        asset_batch = AssetBatch.objects.get(idx=callback_dict["asset_batch_id"])
        asset_run = asset_batch.assetrun_set.get(run_index=callback_dict["asset_run_id"])

        run_result = RunResult.SUCCESS if result else RunResult.FAILED

        self.log("start processing of assetrun [AssetBatch.idx={:d}]".format(callback_dict["asset_batch_id"]))
        asset_run.raw_result_str = etree.tostring(result.tree) if result else None
        asset_run.save()
        s_time = time.time()
        try:
            asset_run.generate_assets()
        except Exception as e:
            _ = e
            _exc = process_tools.icswExceptionInfo()
            _err = process_tools.get_except_info()
            self.log(
                "error in asset_run.generate_assets: {}".format(_err),
                logging_tools.LOG_LEVEL_ERROR
            )
            for line in _exc.log_lines:
                self.log(line, logging_tools.LOG_LEVEL_ERROR)
            asset_run.interpret_error_string = _err
            asset_run.save()
        finally:
            e_time = time.time()
            self.log(
                "generate_asset_run for [AssetBatch.idx={:d}] took {}".format(
                    asset_batch_id,
                    logging_tools.get_diff_time_str(e_time - s_time),
                )
            )
            asset_run.generate_duration = e_time - s_time
            asset_run.state_finished(run_result)
            asset_run.save()

        if asset_batch.run_status == BatchStatus.FINISHED_RUNS:
            self.log("start processing of assetbatch {:d}".format(asset_batch_id))
            s_time = time.time()
            try:
                asset_batch.generate_assets()
            except Exception as e:
                _ = e
                _exc = process_tools.icswExceptionInfo()
                _err = process_tools.get_except_info()
                self.log(
                    "error in asset_batch.generate_assets: {}".format(_err),
                    logging_tools.LOG_LEVEL_ERROR
                )
                for line in _exc.log_lines:
                    self.log(line, logging_tools.LOG_LEVEL_ERROR)
            finally:
                e_time = time.time()
                self.log(
                    "processing of assetbatch {:d} took {}".format(
                        asset_batch_id,
                        logging_tools.get_diff_time_str(e_time - s_time),
                    )
                )
                asset_batch.state_finished()
                asset_batch.save()
                self.log("Finished asset batch {}.".format(asset_batch.idx))

    def network_scan_schedule_handler(self, schedule_item):
        target_device = device.objects.get(idx=int(schedule_item.schedule_handler_data))
        _network = network.objects.get(idx=schedule_item.object_id)
        network_str = str(netaddr.IPNetwork("{}/{}".format(_network.network, _network.netmask)))

        self.discovery_process.get_route_to_devices([target_device])

        conn_str = "tcp://{}:{:d}".format(target_device.target_ip, self.__hm_port)
        new_srv_com = server_command.srv_command(command="nmap_scan", network=network_str)

        new_nmap_scan = NmapScan.create(network=_network, manual_scan=schedule_item.run_now)
        new_nmap_scan.save()

        _background_job = create_bg_job(
            global_config["SERVER_IDX"],
            schedule_item.user,
            "Network scan of {}".format(network_str),
            "nmap_scan",
            None,
            state=BackgroundJobState.pending,
            # set timeout to 30 minutes for big installs
            timeout=60*60*24
        )

        callback_dict = {
            "nmap_scan_id": new_nmap_scan.idx,
            "background_job_id": _background_job.idx
        }

        # timeout for nmap scans needs to be very large, scanning can take a very long time
        hm_command = HostMonitoringCommand(self.network_scan_schedule_handler_callback, callback_dict, timeout=60*60*24)

        self.discovery_process.send_pool_message(
            "send_host_monitor_command",
            hm_command.run_index,
            conn_str,
            str(new_srv_com)
        )

    @staticmethod
    def network_scan_schedule_handler_callback(callback_dict, result):
        _background_job = background_job.objects.get(idx=callback_dict["background_job_id"])
        _background_job.set_state(BackgroundJobState.done)
        try:
            nmap_scan = NmapScan.objects.get(idx=callback_dict['nmap_scan_id'])

            _raw_result, _status = result.get_result()

            nmap_scan.in_progress = False
            if _status == 0:
                nmap_scan.initialize(raw_result=_raw_result)
            else:
                nmap_scan.error_string = _raw_result

            nmap_scan.save()
        except NmapScan.DoesNotExist:
            # Happens if "in progress" nmap scan gets deleted via webinterface, simply discard return value and continue
            pass

    def hostmonitor_status_schedule_handler(self, schedule_item):
        device_pks = ast.literal_eval(schedule_item.schedule_handler_data)
        devices = device.objects.filter(idx__in=device_pks)
        self.discovery_process.get_route_to_devices(devices)

        status_commands = ["platform", "version", "modules_fingerprint"]

        for _device in devices:
            conn_str = "tcp://{}:{:d}".format(_device.target_ip, self.__hm_port)

            for command in status_commands:
                new_srv_com = server_command.srv_command(command=command)

                callback_dict = {
                    "command": command,
                    "device_pk": _device.idx
                }

                hm_command = HostMonitoringCommand(self.hostmonitor_status_schedule_handler_callback,
                                                   callback_dict,
                                                   timeout=5)

                self.discovery_process.send_pool_message(
                    "send_host_monitor_command",
                    hm_command.run_index,
                    conn_str,
                    str(new_srv_com)
                )

    @staticmethod
    def hostmonitor_status_schedule_handler_callback(callback_dict, result):
        callback_dict["result"] = None
        if callback_dict["command"] == "platform":
            try:
                callback_dict["result"] = PlatformSystemTypeEnum(int(result["platform"].text)).name
            except Exception as e:
                _ = e
        elif callback_dict["command"] == "version":
            try:
                callback_dict["result"] = result["version"].text
            except Exception as e:
                _ = e
        elif callback_dict["command"] == "modules_fingerprint":
            try:
                callback_dict["result"] = result["checksum"].text
            except Exception as e:
                _ = e

        propagate_channel_object("hm_status", callback_dict)

    def hostmonitor_update_modules_handler(self, schedule_item):
        device_pk = int(schedule_item.schedule_handler_data)
        _device = device.objects.get(idx=device_pk)
        self.discovery_process.get_route_to_devices([_device])

        from initat.host_monitoring.modules import local_mc
        import pickle
        import binascii
        import bz2

        update_dict = {}

        for module in local_mc.HM_PATH_DICT.keys():
            path = local_mc.HM_PATH_DICT[module]
            f = open(path, "rb")
            data = f.read()
            f.close()

            update_dict[module] = data

        update_dict_s = pickle.dumps(update_dict)
        update_dict_s = bz2.compress(update_dict_s)
        update_dict_s = binascii.b2a_base64(update_dict_s).decode()

        conn_str = "tcp://{}:{:d}".format(_device.target_ip, self.__hm_port)
        new_srv_com = server_command.srv_command(command="update_modules")
        new_srv_com["update_dict"] = update_dict_s

        callback_dict = {
            "device_pk": _device.idx
        }

        hm_command = HostMonitoringCommand(self.hostmonitor_update_modules_handler_callback,
                                           callback_dict,
                                           timeout=30)

        self.discovery_process.send_pool_message(
            "send_host_monitor_command",
            hm_command.run_index,
            conn_str,
            str(new_srv_com)
        )

    @staticmethod
    def hostmonitor_update_modules_handler_callback(callback_dict, result):
        callback_dict["command"] = "modules_fingerprint"
        callback_dict["result"] = "N/A"
        try:
            callback_dict["result"] = result["new_modules_fingerprint"].text
        except Exception as e:
            _ = e

        propagate_channel_object("hm_status", callback_dict)

    def hostmonitor_full_update_handler(self, schedule_item):
        import pickle
        import binascii

        data = pickle.loads(binascii.a2b_base64(schedule_item.schedule_handler_data))

        devices = device.objects.filter(idx__in=data["device_ids"])
        update_file_data = binascii.b2a_base64(data["update_file_data"]).decode()
        self.discovery_process.get_route_to_devices(devices)

        for _device in devices:
            conn_str = "tcp://{}:{:d}".format(_device.target_ip, self.__hm_port)
            new_srv_com = server_command.srv_command(command="full_update")
            new_srv_com["update_file_data"] = update_file_data

            callback_dict = {
                "device_pk": _device.idx
            }

            hm_command = HostMonitoringCommand(self.hostmonitor_full_update_handler_callback,
                callback_dict,
                timeout=30)

            self.discovery_process.send_pool_message(
                "send_host_monitor_command",
                hm_command.run_index,
                conn_str,
                str(new_srv_com)
            )

    @staticmethod
    def hostmonitor_full_update_handler_callback(callback_dict, result):
        pass

    @staticmethod
    def handle_hm_result(run_index, srv_result):
        if run_index in HostMonitoringCommand.host_monitoring_commands:
            host_monitoring_command = HostMonitoringCommand.host_monitoring_commands[run_index]
            host_monitoring_command.handle(result=srv_result)
