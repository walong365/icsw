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
import collections
import time
import traceback

from django.core.exceptions import ValidationError
from django.db.models import Q
from lxml import etree

from initat.cluster.backbone.models import ComCapability, netdevice, netdevice_speed, net_ip, network
from initat.discovery_server.wmi_struct import WmiUtils
from initat.snmp.snmp_struct import ResultNode
from initat.tools import logging_tools, ipvx_tools
from .discovery_struct import ExtCom


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
        if self.device.active_scan:
            self.__class__.process.clear_scan(self.device)
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
                    self.log("Query for {} wrote to stderr: {}".format(ext_com_key, outputs[ext_com_key][1]),
                             logging_tools.LOG_LEVEL_WARN)

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

                self.log("Created {}, updated {}, created {}, found {}".format(
                    logging_tools.get_plural("net device", len(created_ips)),
                    logging_tools.get_plural("net device", len(updated_nds)),
                    logging_tools.get_plural("ip", len(created_ips)),
                    logging_tools.get_plural("existing ip", len(existing_ips)),
                ))

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

import pytz
import datetime

from initat.cluster.backbone.models.asset import AssetRun, RunStatus, AssetType, ScanType
from initat.cluster.backbone.models.dispatch import DispatchSetting, DiscoverySource
from initat.discovery_server.dispatcher import DiscoveryDispatcher


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
            ds = DispatchSetting(
                device=self.device,
                source=source,
                duration_amount=5,
                duration_unit=DispatchSetting.DurationUnits.minutes,
                run_now=True
            )
            ds.save()

        self.finish()

LIST_SOFTWARE_CMD = "list-software-py3"
LIST_KEYS_CMD = "list-keys-py3"
LIST_METRICS_CMD = "list-metrics-py3"
LIST_PROCESSES_CMD = "list-processes-py3"
LIST_UPDATES_CMD = "list-updates-alt-py3"
LIST_PENDING_UPDATES_CMD = "list-pending-updates-py3"
LIST_HARDWARE_CMD = "list-hardware-lstopo-py3"

from initat.tools import logging_tools, process_tools, server_command, net_tools
from initat.icsw.service.instance import InstanceXML
from initat.cluster.backbone.models.dispatch import DeviceDispatcherLink, DispatcherSettingScheduleEnum, ScheduleItem

def align_second(now, sched_start_second):
    while 1:
        now += datetime.timedelta(seconds=1)
        if now.second == sched_start_second:
            break

    return now

def align_minute(now, sched_start_minute):
    while 1:
        now += datetime.timedelta(minutes=1)
        if now.minute == sched_start_minute:
            break

    return now

def align_hour(now, sched_start_hour):
    while 1:
        now += datetime.timedelta(hours=1)
        if now.hour == sched_start_hour:
            break
    return now

def align_day(now, sched_start_day):
    while 1:
        now += datetime.timedelta(days=1)
        if now.day == sched_start_day:
            break
    return now

def align_week(now, sched_start_week):
    while 1:
        now += datetime.timedelta(days=1)
        if (now.isocalendar()[1] % 4) == sched_start_week:
            break
    return now

def align_month(now, sched_start_month):
    while 1:
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

# from Queue import Queue
# import threading

class Dispatcher(object):
    def __init__(self, discovery_process):
        self.discovery_process = discovery_process
        self.device_asset_run_ext_coms = {}
        self.device_running_ext_coms = {}
    #    self.todo_asset_runs = Queue
    #
    #     thread = threading.Thread(target=self.generate_assets_call, args=())
    #     thread.start()
    #
    # def generate_assets_call(self):
    #     while True:
    #         ar = self.todo_asset_runs.get()
    #         print "starting argen"
    #         ar.generate_assets_new()
    #         ar.save()
    #         print "argen stopped"
    #         print ar

    def dispatch_call(self):
        _now = datetime.datetime.now(tz=pytz.utc).replace(microsecond=0)

        links = DeviceDispatcherLink.objects.all()

        for link in links:
            device = link.device
            ds = link.dispatcher_setting

            last_scheds = 0
            last_sched = None
            for sched in ScheduleItem.objects.all():
                # ignore run_now scheds
                if sched.run_now:
                    continue
                #print sched
                if sched.device == device:
                    last_scheds += 1
                    if last_sched and sched.planned_date > last_sched.planned_date:
                        last_sched = sched
                    elif not last_sched:
                        last_sched = sched

            if last_sched == None:
                last_sched = _ScheduleItem(device, DiscoverySource.PACKAGE, align_time_to_baseline(_now, ds))
                print "Next scheduled run: %s" % last_sched
                # self.schedule_items.append(last_sched)
                # self.schedule_items.sort(key=lambda s: s.planned_date)
                ScheduleItem.objects.create(device=last_sched.device,
                                            source=last_sched.source,
                                            planned_date=last_sched.planned_date)

            if last_scheds < 2:
                next_run = _ScheduleItem(device,
                                         DiscoverySource.PACKAGE,
                                         last_sched.planned_date + get_time_inc_from_ds(ds))
                print "Next scheduled run: %s" % next_run
                #self.schedule_items.append(next_run)
                #self.schedule_items.sort(key=lambda s: s.planned_date)
                ScheduleItem.objects.create(device=next_run.device,
                                            source=next_run.source,
                                            planned_date=next_run.planned_date)

        schedule_items = sorted(ScheduleItem.objects.all(), key=lambda x: x.planned_date)
        while schedule_items:
            schedule_item = schedule_items.pop(0)
            if schedule_item.planned_date < _now:
                print "need to run: %s" % schedule_item.__repr__()

                hm_capable = False
                nrpe_capable = False
                for _com in schedule_item.device.com_capability_list.all():
                    if _com.matchcode == "hm":
                        hm_capable = True
                    elif _com.matchcode == "nrpe":
                        nrpe_capable = True

                if hm_capable:
                    self.__do_hm_scan(schedule_item)
                elif nrpe_capable:
                    self.__do_nrpe_scan(schedule_item)
                else:
                    print "Skipping non capable device"
                schedule_item.delete()

        for _device in self.device_asset_run_ext_coms:
            if self.device_running_ext_coms[_device] == 0:
                if self.device_asset_run_ext_coms[_device]:
                    asset_run, com, timeout = self.device_asset_run_ext_coms[_device][0]
                    asset_run.run_status = RunStatus.RUNNING
                    asset_run.run_start_time = datetime.datetime.now()
                    asset_run.save()

                    if isinstance(com, ExtCom):
                        print "Executing: %s" % com.command
                        com.run()
                    else:
                        hm_port = InstanceXML(quiet=True).get_port_dict("host-monitoring", command=True)
                        self.discovery_process.get_route_to_devices([_device])
                        zmq_con = net_tools.zmq_connection(
                            "server:{}".format(process_tools.get_machine_name()),
                            context=self.discovery_process.zmq_context
                        )

                        ip = _device.all_ips()[0]
                        if ip:
                            conn_str = "tcp://{}:{:d}".format(
                                ip,
                                hm_port,
                            )
                            self.log(u"connection_str for {} is {}".format(unicode(_device), conn_str))
                            zmq_con.add_connection(
                                conn_str,
                                server_command.srv_command(command=com),
                                multi=True
                            )
                        else:
                            print "no ip for %s" % _device

                        # replace cmd_str in [AssetRun, com_type, timeout] list with zmq_con object
                        self.device_asset_run_ext_coms[_device][0][1] = zmq_con

                    self.device_running_ext_coms[_device] = 1
            if self.device_running_ext_coms[_device] == 1:
                asset_run, com, timeout = self.device_asset_run_ext_coms[_device][0]
                self.device_asset_run_ext_coms[_device][0][2] = timeout - 1
                print timeout
                if timeout < 1:
                    self.device_asset_run_ext_coms[_device].pop(0)
                    asset_run.run_status = RunStatus.ENDED
                    asset_run.run_end_time = datetime.datetime.now()
                    asset_run.save()
                    self.device_running_ext_coms[_device] = 0
                elif isinstance(com, ExtCom):
                    status = com.finished()
                    if status == 0:
                        self.device_asset_run_ext_coms[_device].pop(0)
                        _output = com.communicate()
                        asset_run.run_status = RunStatus.ENDED
                        asset_run.run_end_time = datetime.datetime.now()
                        asset_run.raw_result_str = _output[0]
                        asset_run.generate_assets_new()
                        #self.todo_asset_runs.append(asset_run)
                        asset_run.save()
                        self.device_running_ext_coms[_device] = 0
                    elif status != None:
                        self.device_asset_run_ext_coms[_device].pop(0)
                        _output = com.communicate()
                        asset_run.run_status = RunStatus.ENDED
                        asset_run.run_end_time = datetime.datetime.now()
                        asset_run.save()
                        self.device_running_ext_coms[_device] = 0
                else:
                    if com.poller.poll(1):
                        res_list = com.loop()
                        self.device_asset_run_ext_coms[_device].pop(0)
                        asset_run.run_status = RunStatus.ENDED
                        asset_run.run_end_time = datetime.datetime.now()

                        s = None
                        if asset_run.run_type == AssetType.PACKAGE:
                            s = res_list[0]["pkg_list"].text
                        elif asset_run.run_type == AssetType.HARDWARE:
                            s = res_list[0]["lstopo_dump"].text
                        elif asset_run.run_type == AssetType.LICENSE:
                            pass
                            #todo implement me
                        elif asset_run.run_type == AssetType.UPDATE:
                            pass
                            #todo implement me
                        elif asset_run.run_type == AssetType.PROCESS:
                            s = res_list[0]['process_tree'].text
                        elif asset_run.run_type == AssetType.PENDING_UPDATE:
                            s = res_list[0]["update_list"].text

                        asset_run.raw_result_str = s
                        asset_run.generate_assets_new()
                        #self.todo_asset_runs.append(asset_run)
                        asset_run.save()
                        self.device_running_ext_coms[_device] = 0

    def __do_hm_scan(self, schedule_item):
        cmd_tuples = [(AssetType.PACKAGE, "rpmlist"),
                      (AssetType.HARDWARE, "lstopo"),
                      (AssetType.PROCESS, "proclist"),
                      (AssetType.PENDING_UPDATE, "updatelist")]
        for runtype, _command in cmd_tuples:
            # runtype = None
            # _command = None
            # if schedule_item.source == DiscoverySource.PACKAGE:
            #     runtype = AssetType.PACKAGE
            #     _command = "rpmlist"
            # elif schedule_item.source == DiscoverySource.HARDWARE:
            #     runtype = AssetType.HARDWARE
            #     _command = "lstopo"
            # elif schedule_item.source == DiscoverySource.LICENSE:
            #     runtype = AssetType.LICENSE
            #     #todo implement me
            # elif schedule_item.source == DiscoverySource.UPDATE:
            #     runtype = AssetType.UPDATE
            #     #todo implement me
            # elif schedule_item.source == DiscoverySource.PROCESS:
            #     runtype = AssetType.PROCESS
            #     _command = "proclist"
            # elif schedule_item.source == DiscoverySource.PENDING_UPDATE:
            #     runtype = AssetType.PENDING_UPDATE
            #     _command = "updatelist"

            _device = schedule_item.device
            asset_run_len = len(_device.assetrun_set.all())
            new_asset_run = AssetRun(run_index=asset_run_len,
                                     run_type=runtype,
                                     run_status=RunStatus.PLANNED,
                                     scan_type = ScanType.HM)
            new_asset_run.save()
            _device.assetrun_set.add(new_asset_run)

            if _device not in self.device_running_ext_coms:
                self.device_running_ext_coms[_device] = 0
                self.device_asset_run_ext_coms[_device] = []

            self.device_asset_run_ext_coms[_device].append([new_asset_run, _command, 120])

    def __do_nrpe_scan(self, schedule_item):
        cmd_tuples = [(AssetType.PACKAGE, LIST_SOFTWARE_CMD),
                      (AssetType.HARDWARE, LIST_HARDWARE_CMD),
                      (AssetType.PROCESS, LIST_PROCESSES_CMD),
                      (AssetType.PENDING_UPDATE, LIST_PENDING_UPDATES_CMD),
                      (AssetType.UPDATE, LIST_UPDATES_CMD),
                      (AssetType.LICENSE, LIST_KEYS_CMD)]

        for runtype, _command in cmd_tuples:
            # if schedule_item.source == DiscoverySource.PACKAGE:
            #     _command = LIST_SOFTWARE_CMD
            #     runtype = AssetType.PACKAGE
            # elif schedule_item.source == DiscoverySource.HARDWARE:
            #     _command = LIST_HARDWARE_CMD
            #     runtype = AssetType.HARDWARE
            # elif schedule_item.source == DiscoverySource.LICENSE:
            #     _command = LIST_KEYS_CMD
            #     runtype = AssetType.LICENSE
            # elif schedule_item.source == DiscoverySource.UPDATE:
            #     _command = LIST_UPDATES_CMD
            #     runtype = AssetType.UPDATE
            # elif schedule_item.source == DiscoverySource.PROCESS:
            #     _command = LIST_PROCESSES_CMD
            #     runtype = AssetType.PROCESS
            # elif schedule_item.source == DiscoverySource.PENDING_UPDATE:
            #     _command = LIST_PENDING_UPDATES_CMD
            #     runtype = AssetType.PENDING_UPDATE

            _com = "/opt/cluster/sbin/check_nrpe -H {} -n -c {} -t120".format(schedule_item.device.all_ips()[0],
                                                                              _command)
            ext_com = ExtCom(self.log, _com)

            _device = schedule_item.device

            asset_run_len = len(_device.assetrun_set.all())

            new_asset_run = AssetRun(run_index=asset_run_len,
                                     run_type=runtype,
                                     run_status=RunStatus.PLANNED,
                                     scan_type=ScanType.NRPE)
            new_asset_run.save()
            _device.assetrun_set.add(new_asset_run)

            if _device not in self.device_running_ext_coms:
                self.device_running_ext_coms[_device] = 0
                self.device_asset_run_ext_coms[_device] = []

            self.device_asset_run_ext_coms[_device].append([new_asset_run, ext_com, 120])

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        print what

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