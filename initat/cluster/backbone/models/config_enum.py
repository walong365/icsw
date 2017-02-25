# Copyright (C) 2016-2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server-server
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
# -*- coding: utf-8 -*-
#
""" enums for config to create a app-spanning 'global' configenum object """

from enum import Enum

from initat.cluster.backbone.models.service_enum_base import icswServiceEnumBase, EggAction
from initat.cluster.backbone.models.functions import register_service_enum
from initat.cluster.backbone.available_licenses import LicenseEnum


class AppEnum(Enum):
    config_server = icswServiceEnumBase(
        "config-server",
        "enables node provisioning features",
        msi_block_name="cluster-config-server",
        egg_actions=[
            EggAction("configure", "device", ghost=True),
        ]
    )
    memcached = icswServiceEnumBase(
        "memcached",
        "runs the memcached-server",
        sync_config=False,
    )
    cluster_server = icswServiceEnumBase(
        "cluster-server",
        "sets device as a cluster-server (DB access)",
        egg_actions=[
            EggAction("allegro", "user", weight=100, timeframe=160, ghost=True),
            EggAction("vdesktop", "user", weight=20, ghost=True),
        ]
    )
    mother_server = icswServiceEnumBase(
        "mother-server",
        "enables basic nodeboot via PXE functionalities",
        msi_block_name="mother",
        egg_actions=[
            EggAction("handle", "device", ghost=False, license_enum=LicenseEnum.netboot),
        ]
    )
    monitor_server = icswServiceEnumBase(
        "monitor-server",
        "sets device as the monitor master server",
        msi_block_name="md-config-server",
        egg_actions=[
            EggAction("dashboard", "device", timeframe=60, ghost=True),
            EggAction("history", "device", timeframe=60, ghost=True),
            EggAction("monconfig", "device", ghost=False, license_enum=LicenseEnum.md_config_server),
        ]
    )
    discovery_server = icswServiceEnumBase(
        "discovery-server",
        "enables network discovery and inventory",
        egg_actions=[
            EggAction("discover", "device", ghost=True),
            EggAction("asset", "device", timeframe=60, ghost=True),
        ]
    )
    logcheck_server = icswServiceEnumBase(
        "logcheck-server",
        "store and check node logs",
    )
    package_server = icswServiceEnumBase(
        "package-server",
        "enables packge-server functionalities (RPM/deb distribution)",
        egg_actions=[
            EggAction("handle", "device", ghost=True),
        ]
    )
    collectd_server = icswServiceEnumBase(
        "collectd-server",
        "Collect MachineVectors from remote machines and store them",
        msi_block_name="collectd",
        egg_actions=[
            EggAction("graph", "device", ghost=True),
        ]
    )
    rms_server = icswServiceEnumBase(
        "rms-server",
        "device hosts the RMS-server (Jobsystem)",
        egg_actions=[
            EggAction("handle", "device", ghost=True),
        ]
    )
    grapher_server = icswServiceEnumBase(
        "grapher-server",
        "Draw graphs, frontend to collectd",
        msi_block_name="rrd-grapher",
        egg_actions=[
            EggAction("graph", "device", timeframe=500, ghost=True),
        ]
    )
    image_server = icswServiceEnumBase(
        "image-server",
        "device holds images for nodes",
        root_service=False,
    )
    kernel_server = icswServiceEnumBase(
        "kernel-server",
        "device holds kernels for nodes",
        root_service=False,
    )
    virtual_desktop_client = icswServiceEnumBase(
        "virtual-desktop-client",
        "device has a virtual desktop client",
        root_service=False,
    )
    virtual_desktop_server = icswServiceEnumBase(
        "virtual-desktop-server",
        "device can offer virtual desktops to users",
        root_service=False,
    )
    auto_etc_hosts = icswServiceEnumBase(
        "auto-etc-hosts",
        "/etc/hosts file can be created from local cluster-server",
        root_service=False,
    )
    mongodb_server = icswServiceEnumBase(
        "monogdb-server",
        "Starts a mongodb server",
        root_service=True,
    )
    report_server = icswServiceEnumBase(
        "report-server",
        "Starts a report server",
        root_service=True,
    )
    ldap_server = icswServiceEnumBase(
        "ldap-server",
        "controls an LDAP-Server",
        root_service=False,
    )
    yp_server = icswServiceEnumBase(
        "yp-server",
        "controls an YP (YellowPage)-Server",
        root_service=False,
    )
    bind_server = icswServiceEnumBase(
        "bind-server",
        "Configure a bind9 Server (Nameservice)",
        root_service=False,
    )
    nmap_scan_device = icswServiceEnumBase(
        "nmap-scan-device",
        "Configure device to allow performing of nmap scans",
        root_service=False,
    )
    quota_scan = icswServiceEnumBase(
        "quota-scan",
        "Tracks quota usage on a given server",
        root_service=False,
    )
    infiniband_query = icswServiceEnumBase(
        "infiniband-query",
        "Queries attached IB Networks via ibqueryerrors",
        root_service=False,
    )
    user_scan = icswServiceEnumBase(
        "user-scan",
        "scan user dirs for all users found on this device",
        root_service=False,
    )
    usv_server = icswServiceEnumBase(
        "usv-server",
        "device has an USV from APC directly attached",
        root_service=False,
    )

register_service_enum(AppEnum, "backbone")
