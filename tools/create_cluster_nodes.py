#!/usr/bin/python-init -Ot
#
# Copyright (C) 2015 Bernhard Mallinger
#
# this file is part of icsw-server
#
# Send feedback to: <mallinger@init.at>
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
import collections

import os
import re
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import csv
import argparse

from initat.cluster.backbone.models import device, device_type, cd_connection, domain_tree_node, netdevice, network


"""
cd_device_type = device_type.objects.get(identifier="CD")
host_device_type = device_type.objects.get(identifier="H")

prod_network = network.objects.get(identifier="prod")
boot_network = network.objects.get(identifier="boot")
ib_network = network.objects.get(identifier="ib")
loopback_network = network.objects.get(identifier="loopback")
"""


"""
device(
    name=name,
    device_group=group,
    device_type=dev_type,
    domain_tree_node=domain_tree_node,
    bootserver=bootserver,
)

netdevice(
    device=dev,
    devname=netdevice_name,
    netdevice_speed=netdevice_speed,
    network_device_type=network_device_type,
)

net_ip(
    ip=ip_address,
    network=ip_network,
    netdevice=netdevice,
)


cd_connection(
    parent=parent_dev,
    child=child_dev,
)
"""

IPInfo = collections.namedtuple("IPInfo", ("ip", "network"))
NetDeviceInfo = collections.namedtuple("NetDeviceInfo", ("name", "mac", "iplist", "speed", "network_device_type"))

def create_device(name, domain_tree_node, dev_type, netdevices):
    pass


def parse_mac(in_mac):
    in_mac = in_mac.strip()
    if in_mac.count(":") == 5:
        return in_mac  # looks fine
    elif len(in_mac) == 12:
        new_mac = ""
        for num, char in enumerate(in_mac):
            new_mac += char
            if num % 2 == 1:
                new_mac += ":"
        return new_mac
    else:
        raise RuntimeError("Invalid mac address: {}".format(in_mac))


def parse_ip(in_ip):
    if not in_ip.count(".") == 3:
        raise RuntimeError("Invalid ip: {}".format(in_ip))
    return in_ip


def handle_csv(csv_reader, config):

    prod_network = network.objects.get(identifier="prod")
    boot_network = network.objects.get(identifier="boot")
    ib_network = network.objects.get(identifier="ib")
    loopback_network = network.objects.get(identifier="loopback")

    cd_device_type = device_type.objects.get(identifier="CD")
    host_device_type = device_type.objects.get(identifier="H")

    CSV_NAME_COLUMN = 0
    CSV_DEV_MAC_COLUMN = 3
    CSV_DEV_MAC_2_COLUMN = 3
    CSV_IPMI_MAC_COLUMN = 5
    CSV_IPMI_IP_COLUMN = 6
    for line in csv_reader:
        name = line[CSV_NAME_COLUMN]
        # id is last part of name which is number
        dev_id_re = re.match("^[a-zA-Z]*(\d+)$", name)
        if not dev_id_re:
            raise RuntimeError("Invalid node name: {}".format(name))
        else:
            dev_id = int(dev_id_re.groups()[0])

            dev_mac = parse_mac(line[CSV_DEV_MAC_COLUMN])
            dev_mac_2 = parse_mac(line[CSV_DEV_MAC_2_COLUMN])
            ipmi_mac = parse_mac(line[CSV_IPMI_MAC_COLUMN])
            ipmi_ip = parse_ip(line[CSV_IPMI_IP_COLUMN])

            main_device = create_device(
                config.DEVICE_NAME_PATTERN.format(dev_id),
                dtn,
                host_device_type,
                [
                    NetDeviceInfo(
                        name="eth0",
                        mac=dev_mac,
                        iplist=[
                            IPInfo(ip=, network=)
                        ],
                    ),
                    NetDeviceInfo(
                        name="lo",
                        mac="00:00:00:00:00:00",
                        iplist=[IPInfo(ip="127.0.0.1", network=loopback_network)],
                        speed=,
                        network_device_type=,
                    )
                ]
            )

            ipmi_device = create_device(
                config.IPMI_NAME_PATTERN.format(dev_id),
                ipmi_dtn,
                cd_device_type,
                [
                    NetDeviceInfo(
                        name="",
                        mac=ipmi_mac,
                        iplist=[
                            IPInfo(ip=ipmi_ip, network=)
                        ]
                        speed=,
                        network_device_type=,
                    )
                ]
            )


            cd_connection(
                parent=parent_dev,
                child=child_dev,
            ).save()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", dest="config", help="config file", required=True)
    return parser.parse_args()


def main():
    args = parse_args()

    conf_dir = os.path.dirname(args.config)
    sys.path.append(conf_dir)
    config = __import__(os.path.basename(args.config).rsplit(".", 1)[0])
    sys.path.remove(conf_dir)

    handle_csv(csv.reader(open(config.CSV_FILE, "r")))


if __name__ == "__main__":
    main()