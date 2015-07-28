#!/usr/bin/python-init -Otu
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-client
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
""" merge old client configs to new config_store """

import os
import re

from initat.tools import config_store
from initat.tools.logging_tools import logbase


def log(what, log_level=logbase.LOG_LEVEL_OK):
    print(
        "[{}] {}".format(
            logbase.get_log_level_str(log_level),
            what,
        )
    )


def parse_file(file_name):
    _name = os.path.join("/etc", "sysconfig", file_name)
    # kwargs:
    # section ... only read arugments from the given section (if found)
    act_section = "global"
    pf1 = re.compile("^(?P<key>\S+)\s*=\s*(?P<value>.+)\s*$")
    pf2 = re.compile("^(?P<key>\S+)\s+(?P<value>.+)\s*$")
    sec_re = re.compile("^\[(?P<section>\S+)\]$")
    _dict = {}
    if os.path.isfile(_name):
        try:
            lines = [line.strip() for line in open(_name, "r").read().split("\n") if line.strip() and not line.strip().startswith("#")]
        except:
            log(
                "Error while reading file {}: {}".format(
                    _name,
                    process_tools.get_except_info()
                ),
                logbase.LOG_LEVEL_ERROR
            )
        else:
            for line in lines:
                sec_m = sec_re.match(line)
                if sec_m:
                    act_section = sec_m.group("section")
                else:
                    for mo in [pf1, pf2]:
                        ma = mo.match(line)
                        if ma:
                            break
                    if ma:
                        key, value = (ma.group("key"), ma.group("value"))
                        # interpret using eval
                        if value not in ["\"\""]:
                            if value[0] == value[-1] and value[0] in ['"', "'"]:
                                pass
                            else:
                                # escape strings
                                value = "\"{}\"".format(value)
                        try:
                            _dict[key] = eval("{}".format(value))
                        except KeyError:
                            print(
                                "Error: key {} not defined in dictionary".format(
                                    key
                                ),
                                logbase.LOG_LEVEL_ERROR
                            )
                    else:
                        print(
                            "Error parsing line '{}'".format(
                                str(line)
                            ),
                            logbase.LOG_LEVEL_ERROR
                        )
    return _dict


# mapping dict
MAP_DICT = {
    "MS_MIN_CHECK_TIME": "meta.check.time",
    "MS_TRACK_CSW_MEMORY": "meta.track.icsw.memory",
    "PC_MODIFY_REPOS": "pc.modify.repos",
    "MS_MAILSERVER": "mail.server",
    "MS_FROM_NAME": "meta.mail.from.name",
    "MS_TO_ADDR": "mail.target.address",
    "LS_FORWARDER": "log.forward.address",
    "LS_ONLY_FORWARD": "log.forward.exclusive",
    "C_RUN_ARGUS": "hm.run.argus",
    "C_TRACK_IPMI": "hm.track.ipmi",
    "C_AFFINITY": "hm.enable.affinity.matcher",
    "C_NO_INOTIFY": "hm.disable.inotify.process",
    "C_ENABLE_KSM": "hm.enable.ksm",
    "C_ENABLE_HUGE": "hm.enable.hugepages",
    "C_HUGEPAGES": "hm.hugepage.percentage",
}


def main():
    src_files = ["logging-server", "meta-server", "package-client", "collserver"]
    if not config_store.ConfigStore.exists("client"):
        new_store = config_store.ConfigStore("client")
        new_store.read("client_sample")
        _dict = {}
        for _file in src_files:
            _short = "".join([_val[0].upper() for _val in _file.split("-")])
            for _key, _value in parse_file(_file).iteritems():
                # simple cast
                if _value.isdigit():
                    _value = int(_value)
                elif _value.lower() in ["true"]:
                    _value = True
                elif _value.lower() in ["false"]:
                    _value = False
                _new_key = "{}_{}".format(_short, _key)
                _dict[_new_key] = _value
                if _new_key in MAP_DICT:
                    new_store[MAP_DICT[_new_key]] = _value
        # new_store.show()
        new_store.write()


if __name__ == "__main__":
    main()
