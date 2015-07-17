# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
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

    sys_cc = factories.ConfigCatalog(name="local", system_catalog=True)
    for _name, _descr in [
        ("config_server", "enables node provisioning features"),
        ("discovery_server", "enables network discovery and inventory"),
        ("logcheck_server", "store and check node logs"),
        ("syslog_server", "store and check node logs (for stage2)"),
        ("monitor_server", "sets device as the monitor master server"),
        ("monitor_slave", "sets device as a monitor slave (sattelite)"),
        ("mother_server", "enables basic nodeboot via PXE functionalities"),
        ("kernel_server", "device holds kernels for nodes"),
        ("image_server", "device holds images for nodes"),
        ("package_server", "enables packge-server functionalities (RPM/deb distribution)"),
        ("rms_server", "device hosts the RMS-server (Jobsystem)"),
        ("rrd_collector", "devices acts as a collector"),
        ("rrd_server", "devices acts as a graphing server (via collectd)"),
        ("server", "sets device as a cluster-server"),
        ("virtual_desktop_client", "device has a virtual desktop client"),
        ("auto_etc_hosts", "/etc/hosts file can be created from local cluster-server"),
    ]:
        _new_c = factories.Config(
            name=_name,
            description=_descr,
            config_catalog=sys_cc,
            server_config=True,
            system_config=True,
        )
