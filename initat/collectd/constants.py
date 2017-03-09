#
# this file is part of icsw-server
#
# Copyright (C) 2013-2015,2017 Andreas Lang-Nevyjel init.at
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

""" base constants for collectd """

from initat.tools import process_tools, configfile
from enum import Enum

IPC_SOCK_SNMP = process_tools.get_zmq_ipc_name(
    "snmp",
    connect_to_root_instance=True,
    s_name="collectd-init"
)

# constant, change to limit RRDs to be converted at once
MAX_FOUND = 0


class _KeyEmitter(object):
    def __init__(self, pfix):
        self.pfix = pfix

    def __call__(self, device):
        # device is a device instance or the uuid
        if isinstance(device, str):
            return "{}_{}".format(
                self.pfix,
                device,
            )
        else:
            return "{}_{}".format(
                self.pfix,
                device.uuid,
            )


class CollectdMCKeyEnum(Enum):
    # main structure
    main_key = "cc_hc_list"
    # full key dump
    host_key = _KeyEmitter("cc_hc")
    # weathermap key dump
    wm_key = _KeyEmitter("cc_wm")
