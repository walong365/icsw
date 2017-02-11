# -*- coding: utf-8 -*-
# Copyright (C) 2010,2012-2017 Andreas Lang-Nevyjel init.at
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

from .. import limits
from initat.constants import PlatformSystemTypeEnum
from ..hm_classes import MonitoringCommand, MonitoringModule
from ..long_running_checks import LongRunningCheck, LONG_RUNNING_CHECK_RESULT_KEY
from ..constants import HMAccessClassEnum


try:
    import lsm
except ImportError:
    lsm = None


class ModuleDefinition(MonitoringModule):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        required_access = HMAccessClassEnum.level0
        uuid = "1e66d204-deef-4487-9895-6e6b3c9b5188"

    def init_module(self):
        self.enabled = True
        if lsm:
            pass
        else:
            self.log("disabled libstoragemanagement because no lsm module found")
            self.enabled = False


class LibstoragemgmtCheck(LongRunningCheck):
    """ Query storage systems for information using libstoragemgmt. """
    def __init__(self, uri, password):
        self.uri = uri
        self.password = password

    def perform_check(self, queue):
        client = lsm.Client(self.uri, plain_text_password=self.password)

        result = {}
        mapping = (
            ("systems", client.systems),
            ("pools", client.pools),
            ("disks", client.disks),
        )
        for key, function in mapping:
            result[key] = [(i.name, i.status) for i in function()]
        client.close()
        queue.put(result)


class libstoragemgmt_command(MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        required_access = HMAccessClassEnum.level0
        uuid = "dff5d4e7-3980-4dd4-8ed7-aacae07b46d2"
        description = "Generic check of Storage devices via libstoragemgmt"

    """
    A generic libstoragemgmt check. Needs a URI specifying the device to check.
    This check needs a running lsmd from the libstoragemgmt-init package.
    """
    def __init__(self, name):
        super(libstoragemgmt_command, self).__init__(
            name, positional_arguments=True
        )
        self.parser.add_argument(
            "uri", help="The URI of the storage device to check"
        )
        self.parser.add_argument(
            "password", help="The password to authenticate with"
        )

    def __call__(self, srv_command_obj, arguments):
        return LibstoragemgmtCheck(arguments.uri, arguments.password)

    def interpret(self, srv_com, *args, **kwargs):
        result = srv_com[LONG_RUNNING_CHECK_RESULT_KEY]
        result_strings = []
        mapping = (
            ("systems", lsm.System.STATUS_OK),
            ("pools", lsm.Pool.STATUS_OK),
            ("disks", lsm.Disk.STATUS_OK),
        )
        result_status = limits.mon_STATE_OK
        for key, status_ok in mapping:
            good = bad = 0
            for _, status in result[key]:
                if status & status_ok:
                    good += 1
                else:
                    result_status = limits.mon_STATE_CRITICAL
                    bad += 1
            result_strings.append("{}: (good={} bad={})".format(
                key, good, bad
            ))
        return result_status, ", ".join(result_strings)
