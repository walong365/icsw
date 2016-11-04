# -*- coding: utf-8 -*-
#
# Copyright (C) 2014,2016 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" creates fixtures for noctua """

from __future__ import unicode_literals, print_function

import netifaces
import os
import socket
import struct
import subprocess
import sys

from django.db.models import Q
from initat.cluster.backbone import factories
from initat.cluster.backbone.models import config_catalog, category_tree, \
    device_group, config, mon_period, mon_contact, \
    user, network, network_type, netdevice_speed, network_device_type, group, \
    host_check_command, domain_name_tree
from initat.tools import ipvx_tools
from initat.tools import process_tools


def get_local_ip_address(target):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((target, 7))
        ipaddr = s.getsockname()[0]
        s.close()
    except:
        print("Unexpected error:", sys.exc_info()[0])
        raise

    return ipaddr


def get_default_gateway_linux():
    with open("/proc/net/route") as fh:
        for line in fh:
            fields = line.strip().split()
            if fields[1] != '00000000' or not int(fields[3], 16) & 2:
                continue
            return socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))


def get_interface_by_ip(if_address):
    for interface in netifaces.interfaces():
        # print interface
        try:
            for link in netifaces.ifaddresses(interface)[netifaces.AF_INET]:
                if(link['addr'] == if_address):
                    if_name = interface
                    return if_name
        except:
            pass


def get_netmask_by_interface(interface):
    return netifaces.ifaddresses(interface)[netifaces.AF_INET][0]['netmask']


def get_broadcast_by_interface(interface):
    return netifaces.ifaddresses(interface)[netifaces.AF_INET][0]['broadcast']


def create_noctua_fixtures():
    print("Creating Noctua fixtures...")
    # first config catalog
    first_cc = config_catalog.objects.all()[0]

    # category tree
    ct = category_tree()
    cat_serv = ct.add_category("/mon/services")
    cat_web = ct.add_category("/mon/services/web")
    cat_mail = ct.add_category("/mon/services/mail")

    # config
    print("Creeating configurations.")
    ping_config = factories.Config(
        name="check-ping",
        config_catalog=first_cc,
    )
    snmp_config = factories.Config(
        name="check-snmp-info",
        config_catalog=first_cc,
    )
    ssh_config = factories.Config(
        name="check-ssh",
        config_catalog=first_cc,
    )
    http_config = factories.Config(
        name="check-http",
        config_catalog=first_cc,
    )
    https_config = factories.Config(
        name="check-https",
        config_catalog=first_cc,
    )
    ldap_config = factories.Config(
        name="check-ldap",
        config_catalog=first_cc,
    )
    imap_config = factories.Config(
        name="check-imap",
        config_catalog=first_cc,
    )
    imaps_config = factories.Config(
        name="check-imaps",
        config_catalog=first_cc,
    )
    pop3s_config = factories.Config(
        name="check-pop3s",
        config_catalog=first_cc,
    )
    smtps_config = factories.Config(
        name="check-smtps",
        config_catalog=first_cc,
    )
    print("Creating monitoring checks.")
    factories.MonCheckCommand(
        name="snmp-info",
        command_line="$USER3$ -m $HOSTADDRESS$ -C $ARG1$ -V $ARG2$ snmp_info",
        config=snmp_config
    ).categories.add(cat_serv)
    factories.MonCheckCommand(
        name="check-ping",
        command_line="$USER2$ -m localhost ping $HOSTADDRESS$ 5 5.0",
        config=ping_config
    ).categories.add(cat_serv)
    factories.MonCheckCommand(
        name="check-ssh",
        command_line="$USER1$/check_ssh $HOSTADDRESS$",
        config=ssh_config
    ).categories.add(cat_serv)
    factories.MonCheckCommand(
        name="check-http",
        command_line="$USER1$/check_http -H $HOSTADDRESS$",
        config=http_config
    ).categories.add(cat_web)
    factories.MonCheckCommand(
        name="check-imaps",
        command_line="$USER1$/check_imap -H $HOSTADDRESS$ -p 993 -S",
        config=imaps_config
    ).categories.add(cat_mail)
    factories.MonCheckCommand(
        name="check-ldap",
        command_line="$USER1$/check_ldap -H $HOSTADDRESS$ -b dc=init,dc=at -3",
        config=ldap_config
    ).categories.add(cat_serv)
    factories.MonCheckCommand(
        name="check-https",
        command_line="$USER1$/check_http -S -H $HOSTADDRESS$ -C 30",
        config=https_config
    ).categories.add(cat_web)
    factories.MonCheckCommand(
        name="check-imap",
        command_line="$USER1$/check_imap -H $HOSTADDRESS$ -p 143",
        config=imap_config
    ).categories.add(cat_mail)
    factories.MonCheckCommand(
        name="check-pop3s",
        command_line="$USER1$/check_pop3 -H $HOSTADDRESS$ -p 995 -S",
        config=pop3s_config
    ).categories.add(cat_mail)
    factories.MonCheckCommand(
        name="check-smtps",
        command_line="$USER1$/check_smtps -H $HOSTADDRESS$ -p 465 -S",
        config=smtps_config
    ).categories.add(cat_mail)

    # domain name tree
    dnt = domain_name_tree()
    _top_level_dtn = dnt.get_domain_tree_node("")
    # device_group
    print("Creating device and device group.")
    first_devg = factories.DeviceGroup(name="server_group")
    first_dev = factories.Device(
        name=process_tools.get_machine_name(),
        device_group=first_devg,
        domain_tree_node=_top_level_dtn,
    )

    print("Creating device configurations.")
    factories.DeviceConfig(
        device=first_dev,
        config=factories.Config(
            name="rrd-server",
            config_catalog=first_cc
        ),
    )
    factories.DeviceConfig(
        device=first_dev,
        config=factories.Config(
            name="server",
            config_catalog=first_cc
        ),
    )
    factories.DeviceConfig(
        device=first_dev,
        config=factories.Config(
            name="rrd-collector",
            config_catalog=first_cc
        ),
    )
    factories.DeviceConfig(
        device=first_dev,
        config=ssh_config,
    )

    print("Creating monitoring periods.")
    initial_mon_period = factories.MonPeriod(
        name="always",
        sun_range="00:00-24:00",
        mon_range="00:00-24:00",
        tue_range="00:00-24:00",
        wed_range="00:00-24:00",
        thu_range="00:00-24:00",
        fri_range="00:00-24:00",
        sat_range="00:00-24:00"
    )
    first_st = factories.MonServiceTempl(
        name="dummy_service_template",
        nsc_period=initial_mon_period,
        nsn_period=initial_mon_period,
        )
    _first_dt = factories.MonDeviceTempl(
        name="dummy_device_template",
        mon_service_templ=first_st,
        mon_period=initial_mon_period,
        not_period=initial_mon_period,
        host_check_command=host_check_command.objects.get(Q(name="check-host-alive")),
    )
    is_ucs = os.path.isfile("/usr/sbin/ucr")

    # the create_cluster script adds an admin user
    # if there are no users, or in case of an ucs system, if only this one new admin exists,
    # then we want an admin and a user user
    users = user.objects.all()
    empty_install = users.count() == 0
    new_install = (users.count() == 1 and users[0].login == 'admin' and
                   users[0].login_count == 0)
    if empty_install or (is_ucs and new_install):
        print('Creating user and groups.')
        user.objects.all().delete()
        group.objects.all().delete()

        # group / users
        _group = factories.Group(
            groupname="group",
            homestart="/",
            gid=100,
        )
        _group.allowed_device_groups.add(first_devg)
        _user = factories.User(
            login="user",
            uid=400,
            group=_group,
            password="user",
        )
        _user.allowed_device_groups.add(first_devg)
        _first_mc = factories.MonContact(
            user=_user,
            snperiod=initial_mon_period,
            hnperiod=initial_mon_period,
        )
        _admin = user.objects.create_superuser(
            "admin",
            "noctua@init.at",
            "admin",
        )
        # we need contacts for all initial users so that they can access icinga
        factories.MonContact(
            user=_admin,
            snperiod=initial_mon_period,
            hnperiod=initial_mon_period,
        )
        _admin.allowed_device_groups.add(first_devg)
        # network
    if is_ucs:
        if_address = get_local_ip_address("62.99.204.238")
        # print if_address

        if_name = get_interface_by_ip(if_address)
        # print if_name

        p = subprocess.Popen(['ucr', 'get', 'interfaces/%s/address' % (if_name)], stdout=subprocess.PIPE)
        if_address = p.stdout.read().strip().split("\n")[0]

        p = subprocess.Popen(['ucr', 'get', 'interfaces/%s/network' % (if_name)], stdout=subprocess.PIPE)
        if_network = p.stdout.read().strip().split("\n")[0]

        p = subprocess.Popen(['ucr', 'get', 'interfaces/%s/broadcast' % (if_name)], stdout=subprocess.PIPE)
        if_broadcast = p.stdout.read().strip().split("\n")[0]

        p = subprocess.Popen(['ucr', 'get', 'interfaces/%s/netmask' % (if_name)], stdout=subprocess.PIPE)
        if_netmask = p.stdout.read().strip().split("\n")[0]

        p = subprocess.Popen(['ucr', 'get', 'gateway'], stdout=subprocess.PIPE)
        out = p.stdout.read().strip().split("\n")[0]
        if_gateway = out
    else:
        print("Not installed on UCS, /usr/sbin/ucr not found. Using python-netifaces.")

        if_address = get_local_ip_address("62.99.204.238")
        if_name = get_interface_by_ip(if_address)
        if_netmask = get_netmask_by_interface(if_name)
        if_broadcast = get_broadcast_by_interface(if_name)
        if_network = str(ipvx_tools.ipv4(if_netmask) & ipvx_tools.ipv4(if_broadcast))
        if_gateway = get_default_gateway_linux()

    print('Creating network objects.')
    _network = factories.Network(
        identifier="lan",
        network_type=network_type.objects.get(Q(identifier="o")),
        name="lan",
        network=if_network,
        broadcast=if_broadcast,
        netmask=if_netmask,
        gateway=if_gateway,
    )
    _netdevice = factories.NetDevice(
        device=first_dev,
        devname=if_name,
        routing=True,
        netdevice_speed=netdevice_speed.objects.get(Q(speed_bps=1000000000) & Q(full_duplex=True) & Q(check_via_ethtool=True)),
        network_device_type=network_device_type.objects.get(Q(identifier="eth")),
    )
    _net_ip = factories.NetIp(
        ip=if_address,
        network=_network,
        netdevice=_netdevice,
        domain_tree_node=_top_level_dtn,
    )
