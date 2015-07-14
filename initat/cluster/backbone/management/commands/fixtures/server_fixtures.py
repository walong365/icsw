# -*- coding: utf-8 -*-
#
# Copyright (C) 2014-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of cluster-server
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FTNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" creates fixtures for cluster-server """

from initat.cluster.backbone import factories


def add_fixtures(**kwargs):
    sys_cat = factories.ConfigCatalog(name="local", system_catalog=True)

    factories.Config(
        name="server",
        config_catalog=sys_cat,
        description="sets device as a cluster-server",
        server_config=True,
        system_config=True,
    )
    factories.Config(
        name="quota_scan",
        config_catalog=sys_cat,
        description="scan quotas for all users when device has quotas enabled",
        server_config=True,
        system_config=True,
    )
    factories.Config(
        name="user_scan",
        config_catalog=sys_cat,
        description="scan user dirs for all users found on this device",
        server_config=True,
        system_config=True,
    )
    factories.Config(
        name="usv_server",
        config_catalog=sys_cat,
        description="device has an USV from APC directly attached",
        server_config=True,
        system_config=True,
    )
    factories.Config(
        name="virtual_desktop",
        config_catalog=sys_cat,
        description="device can offer virtual desktops to users",
        server_config=True,
        system_config=True,
    )
    factories.Config(
        name="virtual_desktop_client",
        config_catalog=sys_cat,
        description="device has a virtual desktop client",
        server_config=True,
        system_config=True,
    )
    factories.Config(
        name="auto_etc_hosts",
        config_catalog=sys_cat,
        description="/etc/hosts file can be created from local cluster-server",
        server_config=True,
        system_config=True,
    )
