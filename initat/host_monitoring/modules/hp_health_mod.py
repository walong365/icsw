# Copyright (C) 2011,2013-2015 lang-nevyjel@init.at
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" frontend to various HP monitoring commands """

from initat.host_monitoring import hm_classes, limits
from initat.tools import logging_tools, server_command, process_tools

HPASM_BIN = "hpasmcli"


class _general(hm_classes.hm_module):
    def init_module(self):
        pass


class HPDimm(object):
    class Meta:
        command = "show dimm"

    def process(self, hph):
        dimm_list = []
        cur_dimm = None
        for line in hph.read().split("\n"):
            if line.count(":"):
                key, value = line.split(":", 1)
                key = key.strip().lower()
                if key.endswith("#"):
                    key = key[:-1].strip()
                if key.startswith("processor"):
                    if cur_dimm:
                        dimm_list.append(cur_dimm)
                    cur_dimm = {}
                if cur_dimm is not None:
                    cur_dimm[key] = value.strip()
        if cur_dimm:
            dimm_list.append(cur_dimm)
        hph.srv_com["result"] = dimm_list

    def interpret(self, srv_com, cur_ns):
        dimm_list = srv_com["*result"]
        if dimm_list:
            present_dimms = [entry for entry in dimm_list if entry["present"].lower() == "yes"]
            ret_v = ["found {}".format(logging_tools.get_plural("DIMM", len(present_dimms)))]
            ret_state = limits.nag_STATE_OK
            for entry in dimm_list:
                if entry["status"].lower() != "ok":
                    ret_state = max(limits.nag_STATE_CRITICAL, ret_state)
                ret_v.append(
                    "DIMM module {} (processor {}, {}): {}".format(
                        entry["module"],
                        entry["processor"],
                        entry["size"],
                        entry["status"]
                    )
                )
            return ret_state, "; ".join(ret_v)
        else:
            return limits.nag_STATE_CRITICAL, "nothing returned"


class HPPsu(object):
    class Meta:
        command = "show powersupply"

    def process(self, hph):
        psu_list = []
        cur_ps = None
        for line in hph.read().split("\n"):
            if line.lower().startswith("power supply"):
                if cur_ps:
                    psu_list.append(cur_ps)
                cur_ps = {"num": line.strip().split("#")[1]}
            if line.count(":"):
                key, value = line.split(":", 1)
                key = key.strip().lower()
                cur_ps[key] = value.strip()
        if cur_ps:
            psu_list.append(cur_ps)
        hph.srv_com["result"] = psu_list

    def interpret(self, srv_com, cur_ns):
        psu_list = srv_com["*result"]
        if psu_list:
            ret_v = [u"found {}".format(logging_tools.get_plural("PSU", len(psu_list)))]
            ret_state = limits.nag_STATE_OK
            for entry in psu_list:
                if entry["condition"].lower() != "ok":
                    ret_state = max(limits.nag_STATE_CRITICAL, ret_state)
                    ret_v.append(
                        u"PS {}, present: {}, condition: {}".format(
                            entry["num"],
                            entry["present"],
                            entry["condition"]
                        )
                    )
                else:
                    ret_v.append(
                        u"PS {}, {}".format(
                            entry["num"],
                            entry.get("power", "power not defined")
                        )
                    )
            return ret_state, "; ".join(ret_v)
        else:
            return limits.nag_STATE_CRITICAL, "nothing returned"


class hp_health_bg(hm_classes.subprocess_struct):
    class Meta:
        verbose = False
        id_str = "hp_health"

    def __init__(self, log_com, srv_com, hp_com):
        self.__log_com = log_com
        self.__hp_com = hp_com
        _bin = process_tools.find_file(HPASM_BIN)
        if not _bin:
            srv_com.set_result(
                "Failed to locate a binary named \"{}\"".format(HPASM_BIN),
                server_command.SRV_REPLY_STATE_ERROR
            )
            _com_line = []
        else:
            _com_line = [
                "{} -s '{}'".format(
                    _bin,
                    hp_com.Meta.command,
                )
            ]
        hm_classes.subprocess_struct.__init__(
            self,
            srv_com,
            _com_line,
        )

    def process(self):
        self.__hp_com.process(self)

    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[hph] {}".format(what), level)


class hp_dimm_command(hm_classes.hm_command):
    info_string = "check DIMM state via hpasmcli"

    def __call__(self, srv_com, cur_ns):
        return hp_health_bg(self.log, srv_com, HPDimm())

    def interpret(self, srv_com, cur_ns):
        return HPDimm().interpret(srv_com, cur_ns)


class hp_powersupply_command(hm_classes.hm_command):
    info_string = "check PSU state via hpasmcli"

    def __call__(self, srv_com, cur_ns):
        return hp_health_bg(self.log, srv_com, HPPsu())

    def interpret(self, srv_com, cur_ns):
        return HPPsu().interpret(srv_com, cur_ns)
