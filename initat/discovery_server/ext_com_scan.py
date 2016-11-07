# Copyright (C) 2015-2016 Andreas Lang-Nevyjel, init.at
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
from __future__ import unicode_literals

import collections
import datetime
import time
import traceback

import pytz
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from lxml import etree

from initat.cluster.backbone.models import ComCapability, netdevice, netdevice_speed, net_ip, network, \
    device_variable, AssetRun, RunStatus, BatchStatus, AssetType, ScanType, \
    AssetBatch, RunResult, DeviceDispatcherLink, DispatcherSettingScheduleEnum, \
    ScheduleItem, DiscoverySource
from initat.discovery_server.wmi_struct import WmiUtils
from initat.icsw.service.instance import InstanceXML
from initat.snmp.snmp_struct import ResultNode
from initat.tools import logging_tools, process_tools, server_command, net_tools, \
    ipvx_tools
from .discovery_struct import ExtCom

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

        if "scan_address" in dev_com.attrib:
            self.device.target_ip = dev_com.attrib["scan_address"]
        else:
            self.__class__.process.get_route_to_devices([self.device])

        if not self.device.target_ip:
            self.log("no valid IP found for {}".format(unicode(self.device)), logging_tools.LOG_LEVEL_ERROR)
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
        for item in list(cls._batch_lut.itervalues()):
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
                    nrpe_port = device_variable.objects.get_device_variable_value(self.device, "NRPE_PORT", DEFAULT_NRPE_PORT)
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

        for query_structure in query_structures.iteritems():
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
        if all(ext_com.finished() is not None for ext_com in self._ext_coms.itervalues()):

            outputs = {ext_com_key: ext_com.communicate() for ext_com_key, ext_com in self._ext_coms.iteritems()}

            any_err = False
            for ext_com_key, ext_com in self._ext_coms.iteritems():
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

                ND_SPEED_LUT = netdevice_speed.build_lut()
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
                        nd.netdevice_speed = ND_SPEED_LUT.get(int(adapter['Speed']), ND_SPEED_LUT.get(0))
                        nd.save()

                        for ip_found in WmiUtils.WmiList.handle(adapter_configuration['IPAddress']):
                            try:
                                ip_found_struct = ipvx_tools.ipv4(ip_found)
                            except ValueError:
                                self.log("Found IP which is not supported: {}".format(ip_found),
                                         logging_tools.LOG_LEVEL_WARN)
                            else:
                                # find ipv4 subnet
                                netmasks_found = []
                                for _nm in WmiUtils.WmiList.handle(adapter_configuration["IPSubnet"]):
                                    try:
                                        netmasks_found.append(ipvx_tools.ipv4(_nm))
                                    except ValueError:
                                        pass

                                if not netmasks_found:
                                    self.log("No netmask found among: {}".format(adapter['IPSubnet']))
                                else:
                                    netmask_found_struct = netmasks_found[0]

                                    _gws = []
                                    for _gw in WmiUtils.WmiList.handle(adapter_configuration["DefaultIPGateway"]):
                                        try:
                                            _gws.append(ipvx_tools.ipv4(_gw))
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
    """ Base class for all scan mixins """
    def _register_timer(self):
        if not hasattr(self, "_timer_registered"):
            self.log("registering base_timer")
            self._timer_registered = True
            self.register_timer(self._check_commands, 2)

    def _check_commands(self):
        ScanBatch.g_check_ext_com()


class BaseScanMixin(_ExtComScanMixin):
    def base_scan(self, dev_com, scan_dev):
        self._register_timer()
        return BaseScanBatch(dev_com, scan_dev).start_result


class WmiScanMixin(_ExtComScanMixin):
    def wmi_scan(self, dev_com, scan_dev):
        self._register_timer()
        return WmiScanBatch(dev_com, scan_dev).start_result


class NRPEScanMixin(_ExtComScanMixin):
    def nrpe_scan(self, dev_com, scan_dev):
        self._register_timer()
        return NRPEScanBatch(dev_com, scan_dev).start_result

PACKAGE_CMD = "package"
LICENSE_CMD = "license"
HARDWARE_CMD = "hardware"
UPDATES_CMD = "updates"
PROCESS_CMD = "process"
PENDING_UPDATES_CMD = "pending_updates"


class NRPEScanBatch(ScanBatch):
    SCAN_TYPE = 'NRPE'

    def __init__(self, dev_com, scan_dev):
        dev_com.attrib['scan_address'] = "127.0.0.1"
        super(NRPEScanBatch, self).__init__(dev_com, scan_dev)

        self._commands = self._command = dev_com.attrib.get('commands').split(",")
        self._build_command()

        if self.device.target_ip:
            # self._ext_com = ExtCom(self.log, self._build_command())
            # self._ext_com.run()
            self.start_result = ResultNode(ok="started NRPE_scan")

    def _build_command(self):
        for _command in self._commands:
            source = None
            if _command == PACKAGE_CMD:
                source = DiscoverySource.PACKAGE
            elif _command == LICENSE_CMD:
                source = DiscoverySource.LICENSE
            elif _command == HARDWARE_CMD:
                source = DiscoverySource.HARDWARE
            elif _command == UPDATES_CMD:
                source = DiscoverySource.UPDATE
            elif _command == PROCESS_CMD:
                source = DiscoverySource.PROCESS
            elif _command == PENDING_UPDATES_CMD:
                source = DiscoverySource.PENDING_UPDATE

            if not source:
                continue

            # run scan once every hour
            si = ScheduleItem.objects.create(
                device=self.device,
                source=10,
                planned_date=datetime.datetime.now(tz=pytz.utc),
                run_now=True,
                dispatch_setting=None
            )
            si.save()

        self.finish()

LIST_SOFTWARE_CMD = "list-software-py3"
LIST_KEYS_CMD = "list-keys-py3"
LIST_METRICS_CMD = "list-metrics-py3"
LIST_PROCESSES_CMD = "list-processes-py3"
LIST_UPDATES_CMD = "list-updates-alt-py3"
LIST_PENDING_UPDATES_CMD = "list-pending-updates-py3"
LIST_HARDWARE_CMD = "list-hardware-lstopo-py3"
DMIINFO_CMD = "dmiinfo"
PCIINFO_CMD = "pciinfo"
PRETTYWINHW_CMD = "list-hardware-py3"


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

    return time_inc


class PlannedRunState(object):
    run_idx = 0

    def __init__(self, pdrf, run_db_obj, ext_com, timeout):
        # mirrors AssetRuns
        self.__pdrf = pdrf
        # for external ref
        self.run_idx = 0
        self.run_db_obj = run_db_obj
        self.ext_com = ext_com
        self.timeout = timeout
        # state diagram: (started, running) :
        # (False, False) -> (True, True) -> (True, False)
        # started
        self.started = False
        # is running
        self.running = False
        self.is_zmq_connection = not isinstance(self.ext_com, ExtCom)
        # zmq connection parameters
        self.zmq_conn_str = None
        self.zmq_command = None

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__pdrf.log(
            "[{:d}] {}".format(self.run_db_obj.batch_index, what),
            log_level
        )

    def set_zmq_parameters(self, conn_str):
        self.zmq_conn_str = conn_str
        self.zmq_command = server_command.srv_command(command=self.ext_com)
        self.log(
            u"connection_str is {} ({})".format(
                self.zmq_conn_str,
                self.ext_com,
            )
        )

    def get_send_parameters(self):
        return self.run_idx, self.zmq_conn_str, unicode(self.zmq_command)

    def start(self):
        self.started = True
        self.running = True
        PlannedRunState.run_idx += 1
        self.run_idx = PlannedRunState.run_idx
        _db_obj = self.run_db_obj
        _db_obj.state_start_scan()
        if _db_obj.asset_batch.run_status != BatchStatus.RUNNING:
            _db_obj.asset_batch.state_start_runs()
            _db_obj.asset_batch.save()
        self.__pdrf.num_running += 1

    def store_nrpe_result(self, state, result):
        _stdout, _stderr = result
        self.log(
            "stdout has {}, stderr has {} [{:d}]".format(
                logging_tools.get_size_str(len(_stdout)),
                logging_tools.get_size_str(len(_stderr)),
                state,
            )
        )
        s = _stdout
        if s is None or state != 0:
            res = RunResult.FAILED
        else:
            res = RunResult.SUCCESS
        self._store_result(res, "", s)

    def store_zmq_result(self, result):
        raw_result_str = ""
        error_string = ""
        (status_string, server_result_code) = result.get_result()

        res = SERVER_RESULT_RUN_RESULT[server_result_code]
        if res != RunResult.SUCCESS:
            error_string = status_string
        else:
            # store the whole XML tree
            raw_result_str = etree.tostring(result.tree)

        self._store_result(res, error_string, raw_result_str)

    def _store_result(self, result, error_string, raw_result_str):
        self._stop()
        if result == RunResult.SUCCESS:
            self.run_db_obj.state_finished_scan(
                result,
                error_string,
                raw_result_str,
            )
            self.generate_assets()
        else:
            self.run_db_obj.state_finished(
                result,
                error_string,
            )

    def cancel(self, error_string):
        self._stop()
        self.generate_assets()

    def _stop(self):
        self.running = False
        self.__pdrf.remove_planned_run(self)

    def generate_assets(self):
        self.run_db_obj.state_start_generation()
        self.__pdrf.disp.discovery_process.send_pool_message(
            "generate_assets",
            self.run_db_obj.idx,
        )


class PlannedRunsForDevice(object):

    def __init__(self, disp, device, ip):
        # mirrors AssetBatch
        self.disp = disp
        self.device = device
        self.planned_runs = []
        self.ip = ip
        # numbers of jobs running
        self.num_running = 0
        self.to_delete = False
        self.asset_batch = AssetBatch(device=self.device)
        self.asset_batch.state_init()
        self.asset_batch.save()
        self.zmq_connections = []

    def start_feed(self, cmd_tuples):
        self.asset_batch.num_runs = len(cmd_tuples)
        self.asset_batch.save()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.disp.log(
            "[PR] [{}] {}".format(
                unicode(self.device),
                what
            ),
            log_level
        )

    def cancel(self, err_cause):
        self.log(
            "canceling because of '{}'".format(err_cause),
            logging_tools.LOG_LEVEL_ERROR
        )
        # make copy of list
        for _run in [_x for _x in self.planned_runs]:
            _run.cancel(error_string="run canceled")
        self.asset_batch.error_string = err_cause
        self.asset_batch.state_finished()
        self.asset_batch.save()
        # canceled, delete
        self.to_delete = True

    def add_planned_run(self, run_db_obj, ext_com, timeout):
        self.planned_runs.append(
            PlannedRunState(self, run_db_obj, ext_com, timeout)
        )

    def remove_planned_run(self, pdrf):
        self.num_running -= 1
        self.planned_runs = [entry for entry in self.planned_runs if entry.run_db_obj.idx != pdrf.run_db_obj.idx]
        if not self.num_running and not self.planned_runs:
            # no more running, delete
            self.to_delete = True

class Dispatcher(object):
    def __init__(self, discovery_process):
        self.discovery_process = discovery_process
        # runs per device
        self.__device_planned_runs = {}
        # lut for external connection commands (0MQ)
        self.__ext_con_lut = {}
        # lut for external background commands
        self.__ext_bg_lut = {}
        self.log("init Dispatcher")
        # quasi-static constants
        self.__hm_port = InstanceXML(quiet=True).get_port_dict("host-monitoring", command=True)

        self.schedule_items = []

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.discovery_process.log("[Disp] {}".format(what), log_level)

    def schedule_call(self):
        # called every 10 seconds
        _now = timezone.now().replace(microsecond=0)

        links = DeviceDispatcherLink.objects.all().select_related(
            "device",
            "dispatcher_setting",
        )

        for link in links:
            device = link.device
            ds = link.dispatcher_setting

            # schedule settings counter
            last_scheds = {}
            # latest planned data for DispatcherSetting
            last_sched = {}
            for sched in ScheduleItem.objects.all():
                if sched.device_id == device.idx and sched.dispatch_setting_id == ds.idx:
                    if ds not in last_scheds:
                        last_scheds[ds] = 0
                    last_scheds[ds] += 1

                    if ds not in last_sched:
                        last_sched[ds] = sched
                    elif sched.planned_date > last_sched[ds].planned_date:
                        last_sched[ds] = sched

            if ds not in last_sched:
                # not scheduled
                next_run = _ScheduleItem(
                    device,
                    # this makes absolutely no sense, FIXME, TODO
                    DiscoverySource.PACKAGE,
                    align_time_to_baseline(_now, ds)
                )
                ScheduleItem.objects.create(
                    device=next_run.device,
                    source=next_run.source,
                    planned_date=next_run.planned_date,
                    dispatch_setting=ds
                )
                last_scheds[ds] = 1
                last_sched[ds] = next_run

            # plan next schedule when counter is below 2
            if last_scheds[ds] < 2:
                next_run = _ScheduleItem(
                    device,
                    DiscoverySource.PACKAGE,
                    last_sched[ds].planned_date + get_time_inc_from_ds(ds)
                )
                ScheduleItem.objects.create(
                    device=next_run.device,
                    source=next_run.source,
                    planned_date=next_run.planned_date,
                    dispatch_setting=ds,
                )

        # remove schedule items that are no longer linked to a device/dispatch_setting
        schedule_items = ScheduleItem.objects.all()
        # valid link list
        link_items = DeviceDispatcherLink.objects.all().values_list("device", "dispatcher_setting")
        for sched in schedule_items:
            if sched.run_now:
                # keep in list
                continue

            found = any(sched.device_id == v[0] and sched.dispatch_setting_id == v[1] for v in link_items)

            if not found:
                self.log(
                    "Remove orphaned ScheduleItem {:d}".format(
                        sched.pk
                    ),
                    logging_tools.LOG_LEVEL_WARN
                )
                sched.delete()

    def dispatch_call(self):
        # called every second, way too often...
        _now = timezone.now().replace(microsecond=0)

        # prestep: close all pending scans
        _pending = 0

        for asset_batch in AssetBatch.objects.filter(
            run_status__in=[BatchStatus.PLANNED, BatchStatus.RUNNING, BatchStatus.FINISHED_RUNS, BatchStatus.GENERATING_ASSETS]):
            if asset_batch.run_start_time:
                diff_time = (_now - asset_batch.run_start_time).total_seconds()
                if diff_time > 86400:
                    self.log("Closing pending/processing AssetBatch now={}".format(_now), logging_tools.LOG_LEVEL_ERROR)
                    self.log("Closing pending/processing AssetBatch run_start_time={}".format(asset_batch.run_start_time), logging_tools.LOG_LEVEL_ERROR)
                    self.log("Closing pending/processing AssetBatch diff_time={}".format(diff_time), logging_tools.LOG_LEVEL_ERROR)

                    asset_batch.run_end_time = _now
                    asset_batch.run_status = BatchStatus.FINISHED
                    asset_batch.save()
                    _pending += 1

        for schedule_item in ScheduleItem.objects.all().select_related(
            "device"
        ).prefetch_related(
            "device__com_capability_list"
        ):
            if schedule_item.planned_date < _now:
                # check for allowed
                if self.discovery_process.EC.consume("asset", schedule_item.device):
                    cap_dict = {
                        _com.matchcode: True for _com in schedule_item.device.com_capability_list.all()
                    }

                    _dev = schedule_item.device
                    if _dev.idx not in self.__device_planned_runs:
                        self.__device_planned_runs[_dev.idx] = []

                    self.discovery_process.get_route_to_devices([_dev])
                    self.log("Address of device {} is {}".format(unicode(_dev), _dev.target_ip))
                    new_pr = PlannedRunsForDevice(self, _dev, _dev.target_ip)
                    new_pr.nrpe_port = device_variable.objects.get_device_variable_value(_dev, "NRPE_PORT", DEFAULT_NRPE_PORT)

                    if cap_dict.get("hm", False):
                        self.__device_planned_runs[_dev.idx].append(new_pr)
                        self._do_hm_scan(schedule_item, new_pr)
                    elif cap_dict.get("nrpe", False):
                        self.__device_planned_runs[_dev.idx].append(new_pr)
                        self._do_nrpe_scan(schedule_item, new_pr)
                    else:
                        self.log(
                            "Skipping non-capable device {}".format(
                                unicode(schedule_item.device)
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                        new_pr.asset_batch.state_finished()
                        new_pr.asset_batch.save()
                schedule_item.delete()

        # step 1: init commands
        for _dev_idx, prfd_list in self.__device_planned_runs.iteritems():
            for prfd in prfd_list:
                if prfd.ip:
                    for prs in prfd.planned_runs:
                        if not prs.started:
                            if prs.is_zmq_connection:
                                prs.start()
                                conn_str = "tcp://{}:{:d}".format(
                                    prfd.ip,
                                    self.__hm_port,
                                )
                                # set parameters
                                prs.set_zmq_parameters(conn_str)
                                self.discovery_process.send_pool_message("send_msg", *prs.get_send_parameters())
                                self.__ext_con_lut[prs.run_idx] = prs
                                # store zmq connection idx
                                # prs.zmq_con_idx = zmq_con.add_connection(
                                #     conn_str,
                                #     server_command.srv_command(command=prs.ext_com),
                                #     multi=True
                                # )
                            else:
                                prs.start()
                                prs.ext_com.run()
                                self.__ext_bg_lut[prs.run_idx] = prs
                else:
                    prfd.cancel("no IP")
        # check for finished ext coms
        cur_time = timezone.now()
        _to_remove = set()
        for key, prd in self.__ext_bg_lut.iteritems():
            _ext_com_state = prd.ext_com.finished()
            if _ext_com_state is not None:
                _output = prd.ext_com.communicate()
                prd.store_nrpe_result(_ext_com_state, _output)
                _to_remove.add(key)
            else:
                diff_time = (cur_time - prd.run_db_obj.run_start_time).seconds
                if diff_time > prd.timeout:
                    try:
                        prd.ext_com.terminate()
                    except:
                        self.log(
                            "error terminating external process (timeout): {}".format(
                                process_tools.get_except_info()
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                    else:
                        self.log("external command terminated due to timeout")
                    prd.cancel("timeout")
                    _to_remove.add(key)
        for _key in _to_remove:
            del self.__ext_bg_lut[_key]

        # check for finished hm connections
        cur_time = timezone.now()
        _to_remove = set()
        for key, planned_run_state in self.__ext_con_lut.iteritems():
            diff_time = (cur_time - planned_run_state.run_db_obj.run_start_time).seconds

            if diff_time > planned_run_state.timeout:
                planned_run_state.cancel("timeout")
                _to_remove.add(key)

        for _key in _to_remove:
            del self.__ext_con_lut[_key]

        self._check_for_finished_runs()

    def got_result(self, run_idx, srv_reply):
        if run_idx in self.__ext_con_lut:
            prs = self.__ext_con_lut[run_idx]
            prs.store_zmq_result(srv_reply)
            del self.__ext_con_lut[run_idx]
        self._check_for_finished_runs()

    def _check_for_finished_runs(self):
        # remove PlannedRuns which should be deleted
        _removed = 0
        for _dev_idx, pdrf_list in self.__device_planned_runs.iteritems():
            _keep = [entry for entry in pdrf_list if not entry.to_delete]
            _removed += len(pdrf_list) - len(_keep)
            self.__device_planned_runs[_dev_idx] = _keep
        if _removed:
            self.log("Removed {}".format(logging_tools.get_plural("PlannedRunsForDevice", _removed)))

    def _do_hm_scan(self, schedule_item, planned_run):
        cmd_tuples = [
            (AssetType.PACKAGE, "rpmlist", 60),
            (AssetType.HARDWARE, "lstopo", 60),
            (AssetType.PROCESS, "proclist", 60),
            (AssetType.PENDING_UPDATE, "updatelist", 60),
            (AssetType.DMI, "dmiinfo", 60),
            (AssetType.PCI, "pciinfo", 60),
            (AssetType.LSHW, "lshw", 60),
            (AssetType.PARTITION, "partinfo", 60),
            (AssetType.LSBLK, "lsblk", 60),
            (AssetType.XRANDR, "xrandr", 60),
        ]
        planned_run.start_feed(cmd_tuples)
        for _idx, (runtype, _command, timeout) in enumerate(cmd_tuples):
            run_index = len(planned_run.asset_batch.assetrun_set.all())
            new_asset_run = AssetRun(
                run_index=run_index,
                run_type=runtype,
                run_status=RunStatus.PLANNED,
                scan_type=ScanType.HM,
                batch_index=_idx,
                asset_batch=planned_run.asset_batch,
            )
            new_asset_run.save()

            planned_run.add_planned_run(
                new_asset_run,
                _command,
                timeout,
            )

    def _do_nrpe_scan(self, schedule_item, planned_run):
        cmd_tuples = [
            (AssetType.PACKAGE, LIST_SOFTWARE_CMD),
            (AssetType.HARDWARE, LIST_HARDWARE_CMD),
            (AssetType.UPDATE, LIST_UPDATES_CMD),
            (AssetType.DMI, DMIINFO_CMD),
            (AssetType.PCI, PCIINFO_CMD),
            (AssetType.PRETTYWINHW, PRETTYWINHW_CMD),
            (AssetType.PENDING_UPDATE, LIST_PENDING_UPDATES_CMD)
        ]
        planned_run.start_feed(cmd_tuples)
        for _idx, (runtype, _command) in enumerate(cmd_tuples):
            timeout = 30
            if runtype == AssetType.PENDING_UPDATE:
                timeout = 3600

            _com = "/opt/cluster/sbin/check_nrpe -H{} -2 -P1048576 -p{} -n -c{} -t{}".format(
                planned_run.ip,
                planned_run.nrpe_port,
                _command,
                timeout
            )
            ext_com = ExtCom(self.log, _com)

            run_index = len(planned_run.asset_batch.assetrun_set.all())
            new_asset_run = AssetRun(
                run_index=run_index,
                run_type=runtype,
                run_status=RunStatus.PLANNED,
                scan_type=ScanType.NRPE,
                batch_index=_idx,
                asset_batch=planned_run.asset_batch,
            )
            new_asset_run.save()

            planned_run.add_planned_run(
                new_asset_run,
                ext_com,
                timeout
            )


class _ScheduleItem(object):
    def __init__(self, device, source, planned_date):
        """
        :type dispatch_setting: DispatchSetting
        """
        # date always means datetime
        self.device = device
        self.source = source
        self.planned_date = planned_date  # naive date according to interval

    def __repr__(self):
        return "ScheduleItem(dev={}, src={}, planned={})".format(
            self.device, self.source, self.planned_date
        )
