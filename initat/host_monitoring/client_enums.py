# Copyright (C) 2016-2017 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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
""" init all enums and create the IcswAppEnum object """

from enum import Enum

from initat.host_monitoring.service_enum_base import icswServiceEnumBaseClient

__all__ = [
    "icswServiceEnum"
]


class icswAppBaseServiceEnumClass(object):
    def __init__(self, *args):
        if not isinstance(args[0], icswServiceEnumBaseClient):
            raise ValueError(
                "value of serviceEnum has to be an instance of icswServiceEnumBaseClient"
            )


# this gets initialised as soon as this module is imported so import this only
# when you need this object

icswServiceEnum = None


class client_enums(Enum):
    hoststatus = icswServiceEnumBaseClient(
        "hoststatus",
        "HostStatus (deprecated)",
    )
    host_monitoring = icswServiceEnumBaseClient(
        "host-monitoring",
        "Monitoring base",
    )
    host_relay = icswServiceEnumBaseClient(
        "host-relayer",
        "Relayer for host-monitoring calls",
        msi_block_name="host-relay"
    )
    snmp_relay = icswServiceEnumBaseClient(
        "SNMP-relayer",
        "Relayer for SNMP calls",
        msi_block_name="snmp-relay"
    )
    meta_server = icswServiceEnumBaseClient(
        "meta-server",
        "Takes care about all running processes"
    )
    logging_server = icswServiceEnumBaseClient(
        "logging-server",
        "handles all ICSW logs"
    )
    package_client = icswServiceEnumBaseClient(
        "package-client",
        "controls the installation of packages (RPMs / debs)",
    )
    monitor_slave = icswServiceEnumBaseClient(
        "monitor-slave",
        "sets device as a monitor slave (sattelite)",
        msi_block_name="md-sync-server",
        relayer_service=True,
    )
    salt_minion = icswServiceEnumBaseClient(
        "salt-minion",
        "Salt minion process",
    )


def init_app_enum():
    global icswServiceEnum
    from initat.icsw.service import instance
    icswServiceEnum = Enum(
        value="icswClientEnum",
        names=[
            (entry.name, entry.value) for entry in client_enums
        ],
        type=icswAppBaseServiceEnumClass
    )
    _xml = instance.InstanceXML(quiet=True)
    for _inst in _xml.get_all_instances():
        if _xml.get_attrib(_inst)["runs_on"] in ["client"] or _inst.find("ignore-missing-database") is not None:
            _attr = _xml.get_attrib(_inst)
            _enums = _xml.get_config_enums(_inst)
            for _enum_str in _enums:
                if _enum_str.count("-"):
                    _err_str = "config-enum names in *.xml are not allowed to have dashes in there name: {}".format(
                        _enum_str,
                    )
                    raise SyntaxError(_err_str)
                try:
                    _enum = getattr(icswServiceEnum, _enum_str)
                except AttributeError:
                    print("Unknown ClientEnum '{}'".format(_enum_str))
                else:
                    _enum.value.add_instance_name(_attr["name"])

init_app_enum()
