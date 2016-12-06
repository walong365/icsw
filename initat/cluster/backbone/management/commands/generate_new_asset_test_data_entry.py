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
from initat.cluster.backbone.models.asset.dynamic_asset import ASSETTYPE_HM_COMMAND_MAP
from initat.icsw.service.instance import InstanceXML
from initat.tools import server_command, net_tools
from lxml import etree

import pickle

class Command(BaseCommand):
    help = "Create new test data entry to be used by asset management tests"

    def add_arguments(selfself, parser):
        parser.add_argument('ip', type=str, help="ip/hostname of device to scan")
        parser.add_argument('identifier', type=str, help="identifier string for this entry")

    def handle(self, **options):
        hm_port = InstanceXML(quiet=True).get_port_dict("host-monitoring", command=True)
        conn_str = "tcp://{}:{:d}".format(options['ip'], hm_port)

        result_dict = {}
        valid = True
        for asset_type, hm_command in ASSETTYPE_HM_COMMAND_MAP.items():
            result_dict[asset_type] = None

            srv_com = server_command.srv_command(command=hm_command)
            new_con = net_tools.ZMQConnection(hm_command)
            new_con.add_connection(conn_str, srv_com)
            result = new_con.loop()
            if result:
                result = result[0]
                (status_string, server_result_code) = result.get_result()

                if server_result_code == server_command.SRV_REPLY_STATE_OK:
                    result_dict[asset_type] = etree.tostring(result.tree)
                else:
                    valid = False
            else:
                valid = False

        if valid:
            try:
                f = open("backbone/tools/tests/asset_management_tests/data/asset_management_test_data", "rb")
                data = pickle.load(f)
                f.close()
            except IOError:
                data = []

            data.append((options['identifier'], result_dict))

            f = open("backbone/tools/tests/asset_management_tests/data/asset_management_test_data", "wb")
            pickle.dump(data, f)
            f.close()

            print("New entry added")
        else:
            print("Failed to generate new entry")
