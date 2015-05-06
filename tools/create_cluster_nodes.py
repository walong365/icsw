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

import django
django.setup()

import csv
import argparse

from initat.cluster.backbone.models import device, cd_connection, domain_tree_node, netdevice, network, device_group, \
    net_ip, peer_information
from initat.cluster.backbone.models.network import netdevice_speed, network_device_type


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

IPInfo = collections.namedtuple("IPInfo", ("ip", "network", "domain_tree_node"))
NetDeviceInfo = collections.namedtuple("NetDeviceInfo", ("name", "mac", "iplist", "speed", "network_device_type"))


def create_device(args, name, group, domain_tree_node, netdevices, bootserver):
    print "Creating device {} with {} netdevices".format(name, len(netdevices))
    dev = device(
        name=name,
        device_group=group,
        domain_tree_node=domain_tree_node,
        bootserver=bootserver,
    )
    if args.write_to_db:
        dev.save()
    nds = []
    for nd_data in netdevices:
        nd_inst = netdevice(
            device=dev,
            macaddr=nd_data.mac,
            devname=nd_data.name,
            netdevice_speed=nd_data.speed,
            network_device_type=nd_data.network_device_type,
        )
        nds.append(nd_inst)
        if args.write_to_db:
            nd_inst.save()
        for nd_ip_data in nd_data.iplist:
            nd_ip_inst = net_ip(
                ip=nd_ip_data.ip,
                network=nd_ip_data.network,
                domain_tree_node=nd_ip_data.domain_tree_node,
                netdevice=nd_inst,
            )
            if args.write_to_db:
                nd_ip_inst.save()
    return dev, nds


def parse_mac(in_mac):
    in_mac = in_mac.strip()
    if in_mac.count(":") == 5:
        return in_mac  # looks fine
    elif len(in_mac) == 12:
        new_mac = ""
        for num, char in enumerate(in_mac):
            new_mac += char
            if num % 2 == 1 and num != len(in_mac) - 1:
                new_mac += ":"
        return new_mac
    else:
        raise RuntimeError("Invalid mac address: {}".format(in_mac))


def parse_ip(in_ip):
    if not in_ip.count(".") == 3:
        raise RuntimeError("Invalid ip: {}".format(in_ip))
    return in_ip


def handle_csv(csv_reader, config, args):

    prod_network = network.objects.get(identifier="prod")
    boot_network = network.objects.get(identifier="boot")
    ib_network = network.objects.get(identifier="ib")
    loopback_network = network.objects.get(identifier="loopback")
    apc_network = network.objects.get(identifier="apc")

    # cd_device_type = device_type.objects.get(identifier="CD")
    # host_device_type = device_type.objects.get(identifier="H")

    lo_netdevice_type = network_device_type.objects.get(identifier="lo")
    eth_netdevice_type = network_device_type.objects.get(identifier="eth")
    ib_netdevice_type = network_device_type.objects.get(identifier="ib")

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
            # dev_mac_2 = parse_mac(line[CSV_DEV_MAC_2_COLUMN])
            ipmi_mac = parse_mac(line[CSV_IPMI_MAC_COLUMN])
            ipmi_ip = parse_ip(line[CSV_IPMI_IP_COLUMN])

            # infiniband: 10.0.2.NN    maggieNNib.ac2t.ib    maggieNNib
            # ipmi: 172.18.2.NN         maggieNN-ipmi.ac2t.apc    maggieNN-ipmi
            # lan: 172.16.2.NN           maggieNN.ac2t.prod     maggieNN
            # ???: 172.17.2.NN           maggieNNi.ac2t.boot    maggieNNi

            ib_ip = "10.0.2.{}".format(dev_id)

            dev_prod_ip = "172.16.2.{}".format(dev_id)
            dev_boot_ip = "172.17.2.{}".format(dev_id)

            dtn = domain_tree_node.objects.get(full_name=config.DEVICE_DOMAIN_TREE_NODE)
            ipmi_dtn = domain_tree_node.objects.get(full_name=config.IPMI_DEVICE_DOMAIN_TREE_NODE)

            ac2t_prod_dtn = domain_tree_node.objects.get(full_name="ac2t.prod")
            ac2t_boot_dtn = domain_tree_node.objects.get(full_name="ac2t.boot")
            ac2t_ib_dtn = domain_tree_node.objects.get(full_name="ac2t.ib")
            local_dtn = domain_tree_node.objects.get(full_name="localdomain")
            ac2t_apc_dtn = domain_tree_node.objects.get(full_name="ac2t.apc")

            gbps1_full_duplex = netdevice_speed.objects.get(speed_bps=1000000000,
                                                            full_duplex=True,
                                                            check_via_ethtool=True)

            mbps100_half_duplex = netdevice_speed.objects.get(speed_bps=100000000,
                                                              full_duplex=False,
                                                              check_via_ethtool=True)

            bootserver = device.objects.get(name='admin')

            actual_device_group = device_group.objects.get(name="fastnodes_new")
            ipmi_group = device_group.objects.get(name="impi_new")

            new_ipmi_switch_nd = device.objects.get(name="ipmiswitch2").netdevice_set.all()[0]
            ib_switch_3_nd = device.objects.get(name="ibswitch3").netdevice_set.all()[0]
            ib_switch_4_nd = device.objects.get(name="ibswitch4").netdevice_set.all()[0]

            actual_device, actual_nds = create_device(
                args,
                config.DEVICE_NAME_PATTERN.format(dev_id),
                actual_device_group,
                dtn,
                [
                    NetDeviceInfo(
                        name="eth0",
                        mac=dev_mac,
                        iplist=[
                            IPInfo(ip=dev_prod_ip, network=prod_network, domain_tree_node=ac2t_prod_dtn),
                            IPInfo(ip=dev_boot_ip, network=boot_network, domain_tree_node=ac2t_boot_dtn),
                        ],
                        speed=mbps100_half_duplex,
                        network_device_type=eth_netdevice_type,
                    ),
                    NetDeviceInfo(
                        name="lo",
                        mac="00:00:00:00:00:00",
                        iplist=[IPInfo(ip="127.0.0.1", network=loopback_network, domain_tree_node=local_dtn)],
                        speed=gbps1_full_duplex,
                        network_device_type=lo_netdevice_type,
                    ),
                    NetDeviceInfo(
                        name="ib",
                        mac="00:00:00:00:00:00",
                        iplist=[IPInfo(ip=ib_ip, network=ib_network, domain_tree_node=ac2t_ib_dtn)],
                        speed=gbps1_full_duplex,
                        network_device_type=ib_netdevice_type,
                    )
                ],
                bootserver=bootserver,
            )

            ipmi_device, ipmi_nds = create_device(
                args,
                config.IPMI_DEVICE_NAME_PATTERN.format(dev_id),
                ipmi_group,
                ipmi_dtn,
                [
                    NetDeviceInfo(
                        name="eth0",
                        mac=ipmi_mac,
                        iplist=[
                            IPInfo(ip=ipmi_ip, network=apc_network, domain_tree_node=ac2t_apc_dtn),
                        ],
                        speed=gbps1_full_duplex,
                        network_device_type=eth_netdevice_type,
                    )
                ],
                bootserver=None
            )

            if args.write_to_db:
                cd_connection(
                    parent=ipmi_device,
                    child=actual_device,
                ).save()

                for ipmi_nd in ipmi_nds:
                    print 'adding ipmi peer info to {}'.format(ipmi_nd)
                    peer_information(
                        s_netdevice=new_ipmi_switch_nd,
                        d_netdevice=ipmi_nd,
                    ).save()

                for actual_nd in actual_nds:
                    if actual_device.network_device_type == ib_netdevice_type:
                        print 'adding peer info to {}'.format(actual_nd)
                        peer_information(
                            s_netdevice=ib_switch_3_nd,
                            d_netdevice=actual_nd,
                        ).save()

                        peer_information(
                            s_netdevice=ib_switch_4_nd,
                            d_netdevice=actual_nd,
                        ).save()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", dest="config", help="config file", required=True)
    parser.add_argument("-w", "--write-to-db", dest="write_to_db", help="actually write to db", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()

    conf_dir = os.path.dirname(args.config)
    sys.path.append(conf_dir)
    config = __import__(os.path.basename(args.config).rsplit(".", 1)[0])
    sys.path.remove(conf_dir)

    handle_csv(csv.reader(open(config.CSV_FILE, "r"), delimiter="\t"), config=config, args=args)


if __name__ == "__main__":
    main()