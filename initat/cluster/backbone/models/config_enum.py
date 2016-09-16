# Copyright (C) 2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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
# -*- coding: utf-8 -*-
#
""" enums for config to create a app-spanning 'global' configenum object """

from enum import Enum

from initat.cluster.backbone.models.service_enum_base import icswServiceEnumBase
from initat.cluster.backbone.models.functions import register_service_enum


class AppEnum(Enum):
    config_server = icswServiceEnumBase(
        "config-server",
        "enables node provisioning features",
        msi_block_name="cluster-config-server"
    )
    cluster_server = icswServiceEnumBase(
        "cluster-server",
        "sets device as a cluster-server (DB access)",
    )
    mother_server = icswServiceEnumBase(
        "mother-server",
        "enables basic nodeboot via PXE functionalities",
        msi_block_name="mother"
    )
    monitor_server = icswServiceEnumBase(
        "monitor-server",
        "sets device as the monitor master server",
        msi_block_name="md-config-server"
    )
    discovery_server = icswServiceEnumBase(
        "discovery-server",
        "enables network discovery and inventory",
    )
    logcheck_server = icswServiceEnumBase(
        "logcheck-server",
        "store and check node logs",
    )
    package_server = icswServiceEnumBase(
        "package-server",
        "enables packge-server functionalities (RPM/deb distribution)",
    )
    collectd_server = icswServiceEnumBase(
        "collectd-server",
        "Collect MachineVectors from remote machines and store them",
        msi_block_name="collectd"
    )
    rms_server = icswServiceEnumBase(
        "rms-server",
        "device hosts the RMS-server (Jobsystem)",
    )
    grapher_server = icswServiceEnumBase(
        "grapher-server",
        "Draw graphs, frontend to collectd",
        msi_block_name="rrd-grapher",
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
        root_service=False
    )

register_service_enum(AppEnum, "backbone")
