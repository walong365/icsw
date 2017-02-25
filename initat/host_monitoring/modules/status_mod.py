# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2017 Andreas Lang-Nevyjel, init.at
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
""" status information module """

import subprocess

from initat.client_version import VERSION_STRING
from initat.constants import PlatformSystemTypeEnum
from initat.tools import uuid_tools, config_store
from .. import hm_classes, limits
from ..constants import HMAccessClassEnum, ZMQ_ID_MAP_STORE


class ModuleDefinition(hm_classes.MonitoringModule):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        required_access = HMAccessClassEnum.level0
        uuid = "930f76aa-96d8-4e85-81f1-7026b7d7e217"

    def init_module(self):
        pass


class version_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        required_access = HMAccessClassEnum.level0
        uuid = "5eb4ffef-e3cb-44f6-8bf5-8f15baee6fa5"
        description = "Version information"

    def __call__(self, srv_com, cur_ns):
        srv_com["version"] = VERSION_STRING

    def interpret(self, srv_com, cur_ns):
        try:
            return limits.mon_STATE_OK, "version is {}".format(srv_com["version"].text)
        except:
            return limits.mon_STATE_CRITICAL, "version not found"

    def interpret_old(self, result, parsed_coms):
        act_state = limits.mon_STATE_OK
        return act_state, "version is {}".format(result)


class get_0mq_id_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        required_access = HMAccessClassEnum.level0
        uuid = "0ff13b8d-ac77-4bf7-9087-f0b5bf41502c"
        description = "get 0MQ ID"

    def __call__(self, srv_com, cur_ns):
        _cs = config_store.ConfigStore(ZMQ_ID_MAP_STORE, log_com=self.log, prefix="bind")
        if "target_ip" in srv_com:
            target_ip = srv_com["target_ip"].text
        else:
            target_ip = "0"
        srv_com["zmq_id"] = _cs["0"]["uuid"]

    def interpret(self, srv_com, cur_ns):
        try:
            return limits.mon_STATE_OK, "0MQ id is {}".format(srv_com["zmq_id"].text)
        except:
            return limits.mon_STATE_CRITICAL, "version not found"


class status_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        required_access = HMAccessClassEnum.level0
        uuid = "cc4a3d1c-5908-48d3-8617-41738e4622ee"
        description = "get current status of system"

    def __call__(self, srv_com, cur_ns):
        _state, _output = subprocess.getstatusoutput("runlevel")
        srv_com["status_str"] = "ok running"
        srv_com["runlevel"] = _output

    def interpret(self, srv_com, cur_ns):
        try:
            _info = [
                "status is {}".format(srv_com["*status_str"]),
            ]
            if "runlevel" in srv_com:
                _level = srv_com["*runlevel"]
                _parts = _level.strip().split()
                if len(_parts) == 2:
                    _info.append(
                        "current runlevel is {}".format(_parts[1])
                    )
                else:
                    _info.append(
                        "runlevel '{}'".format(_level)
                    )
            return limits.mon_STATE_OK, ", ".join(_info)
        except:
            return limits.mon_STATE_CRITICAL, "status unknown"

    def interpret_old(self, result, parsed_coms):
        act_state = limits.mon_STATE_OK
        return act_state, "status is {}".format(result)


class get_uuid_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.ANY
        required_access = HMAccessClassEnum.level0
        uuid = "6a628622-0dd2-4307-ae3d-87448bd71251"
        description = "get UUID of system"

    def __call__(self, srv_com, cur_ns):
        srv_com["uuid"] = uuid_tools.get_uuid().urn

    def interpret(self, srv_com, cur_ns):
        try:
            return limits.mon_STATE_OK, "uuid is {}".format(srv_com["uuid"].text)
        except:
            return limits.mon_STATE_CRITICAL, "uuid not found"

    def interpret_old(self, result, parsed_coms):
        act_state = limits.mon_STATE_OK
        return act_state, "uuid is {}".format(result.split()[1])


class reboot_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.LINUX
        required_access = HMAccessClassEnum.level2
        uuid = "492768f4-48b8-488f-906c-f5ac201c71ca"
        create_mon_check_command = False
        description = "reboot system"

    def __call__(self, srv_com, cur_ns):
        _state, _output = subprocess.getstatusoutput("reboot")
        srv_com["output"] = _output

    def interpret(self, srv_com, cur_ns):
        return limits.mon_STATE_WARNING, "reboot called: {}".format(
            srv_com["*output"]
        )


class halt_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.LINUX
        required_access = HMAccessClassEnum.level2
        uuid = "fc554ecd-5d3d-4c49-a01f-5fd7b7e89f77"
        create_mon_check_command = False
        description = "halt system"

    def __call__(self, srv_com, cur_ns):
        _state, _output = subprocess.getstatusoutput("halt")
        srv_com["output"] = _output

    def interpret(self, srv_com, cur_ns):
        return limits.mon_STATE_WARNING, "halt called: {}".format(
            srv_com["*output"]
        )


class poweroff_command(hm_classes.MonitoringCommand):
    class Meta:
        required_platform = PlatformSystemTypeEnum.LINUX
        required_access = HMAccessClassEnum.level2
        uuid = "5aa56ce2-3a6a-404e-abae-6ada0326ab97"
        create_mon_check_command = False
        description = "poweroff system"

    def __call__(self, srv_com, cur_ns):
        _state, _output = subprocess.getstatusoutput("poweroff")
        srv_com["output"] = _output

    def interpret(self, srv_com, cur_ns):
        return limits.mon_STATE_WARNING, "poweroff called: {}".format(
            srv_com["*output"]
        )
