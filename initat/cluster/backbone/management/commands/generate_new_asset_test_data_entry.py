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


class ResultObject(object):
    def __init__(self, identifier, ignore_tests, result_dict, scan_type):
        self.identifier = identifier
        self.ignore_tests = ignore_tests
        self.result_dict = result_dict
        self.scan_type = scan_type


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

    def handle(self, **options):
        if options['delete_index'] is not None:
            self.handle_delete(options['delete_index'])
            return
        if options['list']:
            self.handle_list()
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
            print("Index:\t{}".format(index))
            print("Identifier:\t{}".format(result_obj.identifier))
            print("Ignored Tests:\t{}".format(result_obj.ignore_tests))
            print("HM/NRPE Results:\t{}".format(len(result_obj.result_dict.items())))
            print("Scan Type:\t{}".format(result_obj.scan_type.name))
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
