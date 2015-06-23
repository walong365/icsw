# Copyright (C) 2015 Bernhard Mallinger, init.at
#
# Send feedback to: <mallinger@init.at>
#
# this file is part of discovery-server
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
from initat.cluster.backbone.models import device_variable
from initat.discovery_server.discovery_struct import ExtCom

WMIC_BINARY = "/opt/cluster/bin/wmic"


__all__ = [
    'get_wmic_cmd',
    'WmiEventLogScanner',
]


def get_wmic_cmd(username, password, target_ip, columns, table, where_clause=""):
    # NOTE: this is an injection vulnerability
    # similar to wmi client wrapper https://pypi.python.org/pypi/wmi-client-wrapper
    return (
        WMIC_BINARY,
        "--delimiter={}".format("\01"),
        "--user={username}%{password}".format(
            username=username,
            password=password,
        ),
        "//{host}".format(host=target_ip),
        "SELECT {} FROM {} {}".format(", ".join(columns), table, where_clause),
    )


class WmiEventLogScanner(object):

    WMI_USERNAME_VARIABLE_NAME = "WMI_USERNAME"
    WMI_PASSWORD_VARIABLE_NAME = "WMI_PASSWORD"

    def __init__(self, target_device, target_ip, log):
        self.target_device = target_device
        self.target_ip = target_ip
        self.log = log

        self.username = device_variable.objects.get_device_variable_value(device=self.target_device,
                                                                          var_name=self.WMI_USERNAME_VARIABLE_NAME)
        if not self.username:
            raise RuntimeError(
                "For WMI event log scanning, the device {} must have a device variable " +
                "called \"{}\" which contains the user name for WMI on this device".format(
                    self.target_device, self.WMI_USERNAME_VARIABLE_NAME
                )
            )
        self.password = device_variable.objects.get_device_variable_value(device=self.target_device,
                                                                          var_name=self.WMI_PASSWORD_VARIABLE_NAME)
        if not self.password:
            raise RuntimeError(
                "For WMI event log scanning, the device {} must have a device variable " +
                "called \"{}\" which contains the user name for WMI on this device".format(
                    self.target_device, self.WMI_PASSWORD_VARIABLE_NAME
                )
            )

    def scan(self):

        cmd = get_wmic_cmd(
            username=self.username,
            password=self.password,
            target_ip=self.target_ip,
            columns="Category, CategoryString, ComputerName, Data, EventCode, EventIdentifier, EventType, " +
                    "InsertionStrings, Logfile, Message, RecordNumber, SourceName, TimeGenerated, TimeWritten, " +
                    "Type, User",
            table="Win32_NTLogEvent",
        )

        ext_com = ExtCom(self.log, cmd, shell=False)  # shell=False since args must not be parsed again
        ext_com.run()
        ext_com.popen.wait()
        import pprint
        pprint.pprint(ext_com.communicate())
