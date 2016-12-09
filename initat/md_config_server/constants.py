# Copyright (C) 2013-2014,2016 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-{sync,config}-server
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
""" icinga and md-sync-/md-config-server constants """

from __future__ import unicode_literals, print_function

from enum import Enum


class BuildMode(object):
    def __init__(self, short, full_build=False, master=True, dynamic_check=False, user_sync=False, reload=False):
        self.short = short
        self.full_build = full_build
        self.master = master
        self.dynamic_check = dynamic_check
        self.user_sync = user_sync
        self.reload = reload


class BuildModesEnum(Enum):
    # build all and redistribute, master process
    all_master = BuildMode("all_master", full_build=True, master=True, reload=True)
    # build all and redistribute, slave process
    all_slave = BuildMode("all_slave", full_build=True, reload=True)
    # build some and do not redistribute
    some_check = BuildMode("some_check")
    # build some and redistribute, for dynamic updates, master process
    some_master = BuildMode("some_master", master=True, reload=True)
    # build some and redistribute, slave process
    some_slave = BuildMode("some_slave", reload=True)
    # dynamic update run
    dyn_master = BuildMode("dyn_master", dynamic_check=True, master=True)
    # http sync commands
    sync_users_master = BuildMode("sync_users_master", master=True, user_sync=True)
    sync_users_slave = BuildMode("sync_users_slave", user_sync=True)


# icinga constants
MON_HOST_UNKNOWN = -1
MON_HOST_UP = 0
MON_HOST_DOWN = 1
MON_HOST_UNREACHABLE = 2

# default template name
TEMPLATE_NAME = "t"

# maps to transfer for single_build
SINGLE_BUILD_MAPS = {"device", "command"}

# no longer needed / required

# IDOMOD_PROCESS_PROCESS_DATA = 2 ** 0
# IDOMOD_PROCESS_TIMED_EVENT_DATA = 2 ** 1
# IDOMOD_PROCESS_LOG_DATA = 2 ** 2
# IDOMOD_PROCESS_SYSTEM_COMMAND_DATA = 2 ** 3
# IDOMOD_PROCESS_EVENT_HANDLER_DATA = 2 ** 4
# IDOMOD_PROCESS_NOTIFICATION_DATA = 2 ** 5
# IDOMOD_PROCESS_SERVICE_CHECK_DATA = 2 ** 6
# IDOMOD_PROCESS_HOST_CHECK_DATA = 2 ** 7
# IDOMOD_PROCESS_COMMENT_DATA = 2 ** 8
# IDOMOD_PROCESS_DOWNTIME_DATA = 2 ** 9
# IDOMOD_PROCESS_FLAPPING_DATA = 2 ** 10
# IDOMOD_PROCESS_PROGRAM_STATUS_DATA = 2 ** 11
# IDOMOD_PROCESS_HOST_STATUS_DATA = 2 ** 12
# IDOMOD_PROCESS_SERVICE_STATUS_DATA = 2 ** 13
# IDOMOD_PROCESS_ADAPTIVE_PROGRAM_DATA = 2 ** 14
# IDOMOD_PROCESS_ADAPTIVE_HOST_DATA = 2 ** 15
# IDOMOD_PROCESS_ADAPTIVE_SERVICE_DATA = 2 ** 16
# IDOMOD_PROCESS_EXTERNAL_COMMAND_DATA = 2 ** 17
# IDOMOD_PROCESS_OBJECT_CONFIG_DATA = 2 ** 18
# IDOMOD_PROCESS_MAIN_CONFIG_DATA = 2 ** 19
# IDOMOD_PROCESS_AGGREGATED_STATUS_DATA = 2 ** 20
# IDOMOD_PROCESS_RETENTION_DATA = 2 ** 21
# IDOMOD_PROCESS_ACKNOWLEDGEMENT_DATA = 2 ** 22
# IDOMOD_PROCESS_STATECHANGE_DATA = 2 ** 23
# IDOMOD_PROCESS_CONTACT_STATUS_DATA = 2 ** 24
# IDOMOD_PROCESS_ADAPTIVE_CONTACT_DATA = 2 ** 25

BROKER_PROGRAM_STATE = 2 ** 0
BROKER_TIMED_EVENTS = 2 ** 1
BROKER_SERVICE_CHECKS = 2 ** 2
BROKER_HOST_CHECKS = 2 ** 3
BROKER_EVENT_HANDLERS = 2 ** 4
BROKER_LOGGED_DATA = 2 ** 5
BROKER_NOTIFICATIONS = 2 ** 6
BROKER_FLAPPING_DATA = 2 ** 7
BROKER_COMMENT_DATA = 2 ** 8
BROKER_DOWNTIME_DATA = 2 ** 9
BROKER_SYSTEM_COMMANDS = 2 ** 10
BROKER_OCP_DATA = 2 ** 11
BROKER_STATUS_DATA = 2 ** 12
BROKER_ADAPTIVE_DATA = 2 ** 13
BROKER_EXTERNALCOMMAND_DATA = 2 ** 14
BROKER_RETENTION_DATA = 2 ** 15
BROKER_ACKNOWLEDGEMENT_DATA = 2 ** 16
BROKER_STATECHANGE_DATA = 2 ** 17
BROKER_RESERVED18 = 2 ** 18
BROKER_RESERVED19 = 2 ** 19
