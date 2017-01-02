#!/usr/bin/python-init -Otu
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2016 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" shows and updates the current cluster routing table """

from __future__ import unicode_literals, print_function

from django.core.management.base import BaseCommand
from initat.cluster.backbone.models.asset.dynamic_asset import ASSETTYPE_HM_COMMAND_MAP, ASSETTYPE_NRPE_COMMAND_MAP, \
    ScanType
from initat.icsw.service.instance import InstanceXML
from initat.tools import server_command, net_tools
from lxml import etree

import pickle
import subprocess


ASSET_MANAGEMENT_TEST_LOCATION = "backbone/tools/tests/asset_management_tests/data/asset_management_test_data"
DEFAULT_NRPE_PORT = 5666


class ExpectedHdd(object):
    def __init__(self, device_name, serial, size):
        self.device_name = device_name
        self.serial = serial
        self.size = size


class ExpectedPartition(object):
    def __init__(self, device_name, mountpoint, size, filesystem):
        self.device_name = device_name
        self.mountpoint = mountpoint
        self.size = size
        self.filesystem = filesystem


class ExpectedLogicalVolume(object):
    def __init__(self, device_name, size, free, filesystem, mountpoint):
        self.device_name = device_name
        self.size = size
        self.free = free
        self.filesystem = filesystem
        self.mountpoint = mountpoint


class ResultObject(object):
    def __init__(self, identifier, ignore_tests, result_dict, scan_type):
        self.identifier = identifier
        self.ignore_tests = ignore_tests
        self.result_dict = result_dict
        self.scan_type = scan_type
        self.expected_hdds = []
        self.expected_partitions = []
        self.expected_logical_volumes = []


class Command(BaseCommand):
    help = "Create new test data entry to be used by asset management tests"
    ignorable_properties = ["cpus", "memory_modules", "gpus", "displays", "network_devices"]

    def add_arguments(self, parser):
        parser.add_argument('--ip',
                            action="store",
                            dest="ip",
                            type=str,
                            help="ip/hostname of device to scan")
        parser.add_argument('--identifier',
                            action="store",
                            dest="identifier",
                            type=str,
                            help="Identifier string for this entry")
        parser.add_argument('--list',
                            action='store_true',
                            dest="list",
                            default=False,
                            help="List stored result objects")
        parser.add_argument('--ignore-test',
                            action='append',
                            default=[],
                            dest='ignore_tests',
                            help="Ignore testing for this entry and property. Available properties [{}]".format(
                                ", ".join(self.ignorable_properties)))
        parser.add_argument('--delete',
                            action='store',
                            type=int,
                            default=None,
                            dest='delete_index',
                            help="Delete entry with this index (see --list)")
        parser.add_argument('--scan-type',
                            action='store',
                            type=str,
                            default=None,
                            dest='scan_type',
                            help="Which scan to perform for this device [NRPE, HM]")
        parser.add_argument('--add-expected-hdd',
                            action='store',
                            type=str,
                            default=None,
                            dest='expected_hdd',
                            help="Add an expected hdd. Syntax is index:device_name:serial:size")
        parser.add_argument('--add-expected-partition',
                            action='store',
                            type=str,
                            default=None,
                            dest='expected_partition',
                            help="Add an expected hdd. Syntax is index:device_name:mountpoint:size:filesystem")
        parser.add_argument('--add-expected-logical-volume',
                            action='store',
                            type=str,
                            default=None,
                            dest='expected_logical_volume',
                            help="Add an expected logical volume."
                                 " Syntax is index:device_name:size:free:filesystem:mountpoint")
        parser.add_argument('--parse_hdd_data_output',
                            action='store',
                            type=str,
                            default=None,
                            dest='parse_file',
                            help="Parse expected hdd/partition/logical volume information from file")

    def handle(self, **options):
        if options["parse_file"]:
            f = open("disk_output_data")
            lines = f.read()

            lines = lines.split("\n")

            f = open(ASSET_MANAGEMENT_TEST_LOCATION, "rb")
            data = pickle.load(f)
            f.close()


            new_device_for_next_line = False
            current_device = None
            parse_partition = False
            parse_partition_cnt = 0
            parse_disk = False
            parse_disk_cnt = 0
            parse_disk_device_name = ""
            parse_disk_size = ""
            parse_partition_mountpount = ""
            parse_partition_size = ""
            parse_logical = False
            parse_logical_cnt = 0
            parse_logical_device_name = ""
            parse_logical_size = ""
            parse_logical_free = ""
            parse_logical_filesystem = ""

            for line in lines:
                if line == "------":
                    new_device_for_next_line = True
                    continue

                if new_device_for_next_line:
                    new_device_for_next_line = False

                    for device in data:
                        if device.identifier == line:
                            current_device = device
                            current_device.expected_hdds = []
                            current_device.expected_partitions = []
                            current_device.expected_logical_volumes = []

                if line == "--DISK--":
                    parse_partition = False
                    parse_partition_cnt = 0
                    parse_disk = True
                    parse_disk_cnt = 0
                    parse_logical = False
                    parse_logical_cnt = 0
                    continue

                if parse_disk:
                    if parse_disk_cnt == 0:
                        parse_disk_device_name = line
                        parse_disk_cnt += 1

                    elif parse_disk_cnt == 1:
                        parse_disk_size = int(line)
                        parse_disk_cnt += 1

                    elif parse_disk_cnt == 2:
                        parse_disk_serial = line
                        parse_disk = False
                        parse_disk_cnt = 0

                        new_hdd = ExpectedHdd(parse_disk_device_name, parse_disk_serial, parse_disk_size)

                        current_device.expected_hdds.append(new_hdd)

                if line == "--PARTITION--":
                    parse_partition = True
                    parse_partition_cnt = 0
                    parse_disk = False
                    parse_disk_cnt = 0
                    parse_logical = False
                    parse_logical_cnt = 0
                    continue

                if parse_partition:
                    if parse_partition_cnt == 0:
                        parse_partition_mountpount = line
                        parse_partition_cnt += 1

                    elif parse_partition_cnt == 1:
                        parse_partition_size = int(line)
                        parse_partition_cnt += 1

                    elif parse_partition_cnt == 2:
                        parse_partition = False
                        parse_partition_cnt = 0

                        _partition = ExpectedPartition(parse_disk_device_name, parse_partition_mountpount,
                            parse_partition_size, line)
                        current_device.expected_partitions.append(_partition)

                if line == "--LOGICAL--":
                    parse_partition = False
                    parse_partition_cnt = 0
                    parse_disk = False
                    parse_disk_cnt = 0
                    parse_logical = True
                    parse_logical_cnt = 0
                    continue

                if parse_logical:
                    if parse_logical_cnt == 0:
                        parse_logical_device_name = line
                        parse_logical_cnt += 1

                    elif parse_logical_cnt == 1:
                        parse_logical_size = None
                        if line != "None":
                            parse_logical_size = int(line)

                        parse_logical_cnt += 1

                    elif parse_logical_cnt == 2:
                        parse_logical_free = None
                        if line != "None":
                            parse_logical_free = int(line)

                        parse_logical_cnt += 1

                    elif parse_logical_cnt == 3:
                        parse_logical_filesystem = line
                        parse_logical_cnt += 1

                    elif parse_logical_cnt == 4:
                        parse_logical = False
                        parse_logical_cnt = 0

                        elv = ExpectedLogicalVolume(parse_logical_device_name, parse_logical_size,
                            parse_logical_free, parse_logical_filesystem, line)

                        current_device.expected_logical_volumes.append(elv)

            f = open(ASSET_MANAGEMENT_TEST_LOCATION, "wb")
            pickle.dump(data, f)
            f.close()

            return
        if options['delete_index'] is not None:
            self.handle_delete(options['delete_index'])
            return
        if options['list']:
            self.handle_list()
            return
        if options['expected_hdd'] is not None:
            self.handle_add_expected_hdd(options['expected_hdd'])
            return
        if options['expected_partition'] is not None:
            self.handle_add_expected_partition(options['expected_partition'])
            return
        if options['expected_logical_volume'] is not None:
            self.handle_add_expected_logical_volume(options['expected_logical_volume'])
            return

        for _property in options['ignore_tests']:
            if _property not in self.ignorable_properties:
                print("Invalid property: {}".format(_property))
                return

        if options['scan_type'] is None:
            print("Scan Type missing")
            return
        if options['scan_type'] not in ['HM', 'NRPE']:
            print("Invalid Scan Type: {}".format(options['scan_type']))
        if options['ip'] is None:
            print("IP/Hostname missing")
            return
        if options['identifier'] is None:
            print("Identifier for this entry missing")
            return

        result_dict = {}
        if options['scan_type'] == "HM":
            scan_type = ScanType.HM
            hm_port = InstanceXML(quiet=True).get_port_dict("host-monitoring", command=True)
            conn_str = "tcp://{}:{:d}".format(options['ip'], hm_port)

            for asset_type, hm_command in ASSETTYPE_HM_COMMAND_MAP.items():
                result_dict[asset_type] = None

                print("Running command [{}] on {}".format(hm_command, conn_str))
                srv_com = server_command.srv_command(command=hm_command)
                new_con = net_tools.ZMQConnection(hm_command, timeout=30)
                new_con.add_connection(conn_str, srv_com)
                result = new_con.loop()
                if result:
                    result = result[0]
                    if result:
                        (status_string, server_result_code) = result.get_result()

                        if server_result_code == server_command.SRV_REPLY_STATE_OK:
                            result_dict[asset_type] = etree.tostring(result.tree)

            valid = all([result_dict[asset_type] is not None for asset_type in ASSETTYPE_HM_COMMAND_MAP])
        else:
            scan_type = ScanType.NRPE

            for asset_type, nrpe_command in ASSETTYPE_NRPE_COMMAND_MAP.items():
                result_dict[asset_type] = None

                _com = "/opt/cluster/sbin/check_nrpe -H{} -2 -P1048576 -p{} -n -c{} -t{}".format(
                    options['ip'],
                    DEFAULT_NRPE_PORT,
                    nrpe_command,
                    1000,
                )
                output = subprocess.check_output(_com.split(" "))

                if output and len(output) > 0:
                    result_dict[asset_type] = output

            valid = all([result_dict[asset_type] is not None for asset_type in ASSETTYPE_NRPE_COMMAND_MAP])
        if valid:
            try:
                f = open(ASSET_MANAGEMENT_TEST_LOCATION, "rb")
                data = pickle.load(f)
                f.close()
            except IOError:
                data = []

            data.append(ResultObject(options['identifier'], options['ignore_tests'], result_dict, scan_type))

            f = open(ASSET_MANAGEMENT_TEST_LOCATION, "wb")
            pickle.dump(data, f)
            f.close()

            print("New entry added")
        else:
            print("Failed to generate new entry")
            missing_types = []
            for asset_type, result in result_dict.items():
                if result is None:
                    missing_types.append(asset_type)
            print("No result for: {}".format(missing_types))

    @staticmethod
    def handle_list():
        f = open(ASSET_MANAGEMENT_TEST_LOCATION, "rb")
        data = pickle.load(f)
        f.close()

        index = 0
        print_lines = False
        for result_obj in data:
            if print_lines:
                print("-" * 80)

            expected_hdds_str = ""
            for expected_hdd in result_obj.expected_hdds:
                expected_hdd_str = "[{}:{}:{}]".format(
                    expected_hdd.device_name,
                    expected_hdd.serial,
                    expected_hdd.size)
                if expected_hdds_str:
                    expected_hdds_str = "{}, {}".format(expected_hdds_str, expected_hdd_str)
                else:
                    expected_hdds_str = expected_hdd_str
            if len(expected_hdds_str) == 0:
                expected_hdds_str = "N/A"

            expected_partitions_str = ""
            for expected_partition in result_obj.expected_partitions:
                expected_partition_str = "[{}:{}:{}:{}]".format(
                    expected_partition.device_name,
                    expected_partition.mountpoint,
                    expected_partition.size,
                    expected_partition.filesystem)
                if expected_partitions_str:
                    expected_partitions_str = "{}, {}".format(expected_partitions_str, expected_partition_str)
                else:
                    expected_partitions_str = expected_partition_str
            if len(expected_partitions_str) == 0:
                expected_partitions_str = "N/A"

            expected_logical_volumes_str = ""
            for expected_logical_volume in result_obj.expected_logical_volumes:
                expected_logical_volume_str = "[{}:{}:{}:{}:{}]".format(
                    expected_logical_volume.device_name,
                    expected_logical_volume.size,
                    expected_logical_volume.free,
                    expected_logical_volume.filesystem,
                    expected_logical_volume.mountpoint)
                if expected_logical_volumes_str:
                    expected_logical_volumes_str = "{}, {}".format(expected_logical_volumes_str,
                                                                   expected_logical_volume_str)
                else:
                    expected_logical_volumes_str = expected_logical_volume_str
            if len(expected_logical_volumes_str) == 0:
                expected_logical_volumes_str = "N/A"

            print("Index:\t\t\t\t{}".format(index))
            print("Identifier:\t\t\t{}".format(result_obj.identifier))
            print("Ignored Tests:\t\t\t{}".format(result_obj.ignore_tests))
            print("HM/NRPE Results:\t\t{}".format(len(result_obj.result_dict.items())))
            print("Scan Type:\t\t\t{}".format(result_obj.scan_type.name))
            print("Expected HDDs:\t\t\t{}".format(expected_hdds_str))
            print("Expected Partitions:\t\t{}".format(expected_partitions_str))
            print("Expected Logical Volumes:\t{}".format(expected_logical_volumes_str))
            print_lines = True
            index += 1

    @staticmethod
    def handle_delete(delete_index):
        f = open(ASSET_MANAGEMENT_TEST_LOCATION, "rb")
        data = pickle.load(f)
        f.close()

        del data[delete_index]

        f = open(ASSET_MANAGEMENT_TEST_LOCATION, "wb")
        pickle.dump(data, f)
        f.close()

    @staticmethod
    def handle_add_expected_hdd(expected_hdd_str):
        index, device_name, serial, size = expected_hdd_str.split(":")
        index, size = int(index), int(size)

        f = open(ASSET_MANAGEMENT_TEST_LOCATION, "rb")
        data = pickle.load(f)
        f.close()

        data[index].expected_hdds.append(ExpectedHdd(device_name, serial, size))

        f = open(ASSET_MANAGEMENT_TEST_LOCATION, "wb")
        pickle.dump(data, f)
        f.close()

    @staticmethod
    def handle_add_expected_partition(expected_partition_str):
        index, device_name, mountpoint, size, filesystem = expected_partition_str.split(":")
        index, size = int(index), int(size)

        f = open(ASSET_MANAGEMENT_TEST_LOCATION, "rb")
        data = pickle.load(f)
        f.close()

        data[index].expected_partitions.append(ExpectedPartition(device_name, mountpoint, size, filesystem))

        f = open(ASSET_MANAGEMENT_TEST_LOCATION, "wb")
        pickle.dump(data, f)
        f.close()

    @staticmethod
    def handle_add_expected_logical_volume(expected_logical_volume_str):
        index, device_name, size, free, filesystem, mountpoint = expected_logical_volume_str.split(":")
        index, size, free = int(index), int(size), int(free)

        f = open(ASSET_MANAGEMENT_TEST_LOCATION, "rb")
        data = pickle.load(f)
        f.close()

        data[index].expected_logical_volumes.append(ExpectedLogicalVolume(device_name, size, free, filesystem,
            mountpoint))

        f = open(ASSET_MANAGEMENT_TEST_LOCATION, "wb")
        pickle.dump(data, f)
        f.close()
