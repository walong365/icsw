# Copyright (C) 2001-2008,2012-2015 Andreas Lang-Nevyjel, init.at
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
""" checks for Megaraid RAID controllers """

import argparse
import base64
import bz2
import json
import pprint  # @UnusedImport
import re

from initat.host_monitoring import limits, hm_classes
from initat.host_monitoring.struct import ExtReturn
import logging_tools
import server_command

from initat.host_monitoring.modules.raidcontrollers.base import ctrl_type, ctrl_check_struct


# global debug mode
DEBUG = False

SAS_OK_KEYS = {
    "adp": set(),
    "virt": set(
        [
            "virtual_drive", "raid_level", "name", "size", "state", "strip_size",
            "number_of_drives", "ongoing_progresses", "current_cache_policy", "is_vd_cached",
            "disk_cache_policy", "parity_size", "mirror_size",
        ]
    ),
    "pd": set(
        [
            "slot_number", "pd_type", "raw_size", "firmware_state", "media_type",
        ]
    )
}

# for which keys do we read the following line
SAS_CONT_KEYS = set(["ongoing_progresses"])


def get_size(in_str):
    try:
        s_p, p_p = in_str.split()
        return float(s_p) * {
            "k": 1000,
            "m": 1000 * 1000,
            "g": 1000 * 1000 * 1000,
            "t": 1000 * 1000 * 1000 * 1000
        }.get(p_p[0].lower(), 1)
    except:
        return 0


def _split_config_line(line):
    key, val = line.split(":", 1)
    key = key.lower().strip().replace(" ", "_")
    val = val.strip()
    if val.isdigit():
        val = int(val)
    elif val.lower() == "enabled":
        val = True
    elif val.lower() == "disabled":
        val = False
    return key, val


class SasCtrlInfo(object):
    def __init__(self, ctrl_struct):
        self.ctrl_id = None
        self.ctrl_struct = ctrl_struct

    def check_for_ctrl(self, line, new_id):
        if new_id != self.ctrl_id:
            if self.ctrl_id is None:
                self.log("setting ctrl_id (-> {:d}, line was: '{}')".format(new_id, line))
            else:
                self.log("changing ctrl_id ({:d} -> {:d}, line was: '{}')".format(self.ctrl_id, new_id, line))
            self.ctrl_id = new_id
            self.get_ctrl_dict(self.ctrl_id)
        return self.ctrl_stuff, self.ctrl_stuff["count_dict"]

    def get_ctrl_dict(self, ctrl_id):
        self.ctrl_stuff = self.ctrl_struct._dict.setdefault(
            ctrl_id,
            {},
        )
        if "count_dict" not in self.ctrl_stuff:
            self.ctrl_stuff["count_dict"] = {
                "virt": 0,
                "pd": 0,
                "enc": 0,
            }

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.ctrl_struct.log(what, log_level)


class ctrl_type_megaraid_sas(ctrl_type):
    class Meta:
        name = "megaraid_sas"
        exec_name = "megarc"
        description = "MegaRAID SAS"

    def get_exec_list(self, ctrl_list=[]):
        if ctrl_list == []:
            ctrl_list = self._dict.keys()
        return [("/bin/true", ctrl_id, "init") for ctrl_id in ctrl_list] + \
               [("%s -LdPdInfo -a%d -noLog" % (self._check_exec, ctrl_id), ctrl_id, "ld") for ctrl_id in ctrl_list] + \
               [("%s -AdpBbuCmd -GetBbuStatus -a%d -noLog" % (self._check_exec, ctrl_id), ctrl_id, "bbu") for ctrl_id in ctrl_list] + \
               [("%s -EncStatus -a%d -noLog" % (self._check_exec, ctrl_id), ctrl_id, "enc") for ctrl_id in ctrl_list] + \
               [("/bin/true", 0, "done")]

    def scan_ctrl(self):
        cur_stat, cur_lines = self.exec_command(" -AdpAllInfo -aAll -noLog", post="strip")
        if not cur_stat:
            _adp_check = False
            for line in cur_lines:
                if line.lower().startswith("adapter #"):
                    line_p = line.split()
                    ctrl_num = int(line_p[-1][1:])
                    self._dict[ctrl_num] = {
                        "info": " ".join(line_p),
                        "logical_lines": {}
                    }
                    self.log(
                        "Found Controller '{}' with ID {:d}".format(
                            self._dict[ctrl_num]["info"],
                            ctrl_num
                        )
                    )

    def process(self, ccs):

        def _print_debug(prev_mode, cur_mode, line):
            if DEBUG:
                print(
                    "{:6s} {:6s} :: {}".format(
                        prev_mode,
                        cur_mode,
                        line,
                    )
                )

        def parse_bbu_value(value):
            return {
                "no": False,
                "yes": True
            }.get(value.lower(), value)

        _com_line, ctrl_id_for_enclosure, run_type = ccs.run_info["command"]
        if run_type == "done":
            # last run type, store in ccs
            # pprint.pprint(self._dict)
            for ctrl_id, ctrl_stuff in self._dict.iteritems():
                ccs.srv_com["result:ctrl_{:d}".format(ctrl_id)] = ctrl_stuff
            return
        elif run_type == "init":
            self._dict[ctrl_id_for_enclosure] = {
                "count_dict": {
                    "virt": 0,
                    "pd": 0,
                    "enc": 0,
                }
            }
            return

        prev_mode, cur_mode, mode_sense, cont_mode = (None, None, True, False)
        _ci = SasCtrlInfo(self)
        for line_num, line in enumerate([cur_line.rstrip() for cur_line in ccs.read().split("\n")]):
            if not line.strip():
                mode_sense = True
                continue
            # some overrides for newer megarcs
            if line.lower().startswith("adapter #") or line.lower().startswith("bbu status for adapter"):
                mode_sense = True
            parts = line.lower().strip().split()
            # flag if the actal line should be parsed into a key/value pair
            add_line = True
            if mode_sense is True:
                add_line = False
                if line.lower().count("bbu status failed"):
                    # add failed state
                    cur_mode = "bbu"
                    ctrl_stuff, count_dict = _ci.check_for_ctrl(line, ctrl_type_megaraid_sas)
                    cur_dict = {"main": {"battery_state": "cannot read state"}}
                    ctrl_stuff["bbu_keys"] = cur_dict
                elif (parts[0], cur_mode) in [("adapter", None), ("adapter", "pd"), ("adapter", "run"), ("adapter", "virt")]:
                    cur_mode = "adp"
                    ctrl_stuff, count_dict = _ci.check_for_ctrl(line, int(parts[-1].replace("#", "")))
                elif line.lower().startswith("bbu status for "):
                    cur_mode = "bbu"
                    ctrl_stuff, count_dict = _ci.check_for_ctrl(line, int(parts[-1].replace("#", "")))
                    cur_dict = {"main": {}}
                    ctrl_stuff["bbu_keys"] = cur_dict
                elif (parts[0], cur_mode) in [("number", "adp"), ("virtual", "pd")]:
                    cur_mode = "virt"
                    count_dict[cur_mode] += 1
                    cur_dict = {"lines": []}
                    if parts[0] == "virtual":
                        # store line, needed for vd detection
                        add_line = True
                    ctrl_stuff.setdefault("virt", {})[count_dict["virt"] - 1] = cur_dict
                elif (parts[0], cur_mode) in [("is", "virt"), ("raw", "pd")]:
                    # continuation, no change
                    pass
                elif (parts[0], cur_mode) in [("pd:", "virt"), ("pd:", "pd")]:
                    cur_mode = "pd"
                    count_dict[cur_mode] += 1
                    cur_dict = {"lines": []}
                    ctrl_stuff["virt"][count_dict["virt"] - 1].setdefault("pd", {})[count_dict[cur_mode] - 1] = cur_dict
                elif parts[0] in ["exit"]:
                    # last line, pass
                    pass
                elif (parts[0], cur_mode) in [("enclosure", None), ("enclosure", "run"),  ("enclosure", "enc"), ("enclosure", "bbu")]:
                    # get enclosure id
                    enc_id = int(parts[-1])
                    cur_mode = "enc"
                    if ctrl_id_for_enclosure is not None:
                        _new_ctrl_id = ctrl_id_for_enclosure
                        # set unusable, only use ctrl_id_for_enclosure once per file
                        ctrl_id_for_enclosure = None
                    while True:
                        ctrl_stuff, count_dict = _ci.check_for_ctrl(line, _new_ctrl_id)
                        if enc_id not in ctrl_stuff.get("enclosures", {}).keys():
                            # new enclosure id, ok
                            break
                        else:
                            # enclosure id already set, increase controller id
                            _new_ctrl_id += 1
                    count_dict[cur_mode] += 1
                    cur_dict = {"lines": []}
                    ctrl_stuff.setdefault("enclosures", {})[count_dict["enc"] - 1] = cur_dict
                elif (parts[0], cur_mode) in [("number", "enc"), ("number", "run"), ("number", "bbu")]:
                    cur_dict = {"num": int(parts[-1]), "lines": []}
                    _sub_key = "_".join(parts[2:-2])
                    ctrl_stuff.setdefault("enclosures", {})[count_dict["enc"] - 1][_sub_key] = cur_dict
                    # special mode for parsing enclosure info lines
                    cur_mode = "run"
                elif cur_mode == "run":
                    cur_dict = {"lines": []}
                    ctrl_stuff.setdefault("enclosures", {})[count_dict["enc"] - 1][_sub_key][int(parts[-1])] = cur_dict
                elif cur_mode in ["bbu", "enc"]:
                    # ignore empty lines for bbu and enc
                    if cur_mode == "bbu":
                        # add line
                        add_line = True
                else:
                    _print_debug(prev_mode, cur_mode, line)
                    # unknown mode
                    raise ValueError(
                        "cannot determine mode, ctrl_type_megaraid_sas: {}, current mode is {}".format(
                            str(line),
                            cur_mode,
                        )
                    )
                mode_sense = False
            if add_line:
                #  print cur_mode, line
                if line.count(":"):
                    key, value = line.split(":", 1)
                    key = key.lower().strip().replace(" ", "_")
                    if cur_mode == "bbu":
                        cur_dict["main"][key] = parse_bbu_value(value.strip())
                    else:
                        if line.startswith(" "):
                            if cont_mode:
                                cur_val = cur_dict["lines"][-1]
                                cur_dict["lines"][-1] = (
                                    cur_val[0],
                                    "{}{}{}".format(
                                        cur_val[1],
                                        ", " if cur_val[1] else "",
                                        " ".join(line.strip().split())
                                    )
                                )
                        else:
                            if cur_mode not in SAS_OK_KEYS or key in SAS_OK_KEYS[cur_mode]:
                                value = value.strip()
                                cur_dict["lines"].append((key, value.strip()))
                            cont_mode = key in SAS_CONT_KEYS
            _print_debug(prev_mode, cur_mode, line)
            prev_mode = cur_mode
        del _ci
    # def set_result_from_cache(self, srv_com, cur_ns):
    #    for _key, _value in self._dict.iteritems():
    #        srv_com["result:ctrl_{:d}".format(_key)] = _value

    def update_ok(self, srv_com):
        if self._dict:
            return ctrl_type.update_ok(self, srv_com)
        else:
            srv_com.set_result(
                "no controller found",
                server_command.SRV_REPLY_STATE_ERROR
            )
            return False

    @staticmethod
    def _interpret(ctrl_dict, cur_ns):
        # pprint.pprint(ctrl_dict)
        def get_status_lines(lines):
            stat_keys = [_key for _key, _value in lines if _key.endswith("_status")]
            if stat_keys:
                # status keys found, return last status
                return [_value for _key, _value in lines if _key in stat_keys][-1]
            else:
                # not status keys found, return first value
                return lines[0][1]

        def get_log_dict(lines):
            return {key: value for key, value in lines}

        def check_status(key, lines, check):
            _info_str = ""
            _entity_type = key.split(":")[-1][0]
            if check == "status":
                _val = [_val for _key, _val in lines if _key.endswith("_status")][0]
            else:
                _val = [_val for _key, _val in lines if _key == check or _key.replace(" ", "_") == check]
                if _val:
                    _val = _val[0]
                else:
                    # correct key not found
                    _val = "not present / key not found"
            # _checked not needed right now ?
            _checked, _ret_state = (False, limits.nag_STATE_CRITICAL)
            if _entity_type == "v":
                _checked = True
                if check == "state":
                    _ld = get_log_dict(lines)
                    _ld["ctrl"] = key.split(":")[0]
                    # pprint.pprint(lines)
                    # pprint.pprint(_ld)
                    _info_str = "vd {virtual_drive} (ctrl {ctrl}), RAID level {raid_level}, size={size}, drives={number_of_drives}, state={state}".format(**_ld)
                    if _val.lower().startswith("optimal"):
                        _ret_state = limits.nag_STATE_OK

                elif check == "current_cache_policy":
                    if _val.lower().strip().split()[0].startswith("writeback"):
                        _ret_state = limits.nag_STATE_OK
                    else:
                        _ret_state = limits.nag_STATE_WARNING
            elif _entity_type == "d":
                if _val.lower() == "online, spun up":
                    _ret_state = limits.nag_STATE_OK
            elif _entity_type == "f":
                if _val.lower() == "ok":
                    _ret_state = limits.nag_STATE_OK
            elif _entity_type == "s":
                if _val.lower() == "ok":
                    _ret_state = limits.nag_STATE_OK
            elif _entity_type == "b":
                if _val.lower() in ("operational", "optimal"):
                    _ret_state = limits.nag_STATE_OK
            return _ret_state, _val, _info_str, _entity_type

        def get_check_list(d_type, lines):
            if d_type == "virt":
                _keys = [_key for _key, _value in lines]
                return list(set(_keys) & set(["state", "current_cache_policy"]))
            elif d_type == "pd":
                _keys = [_key for _key, _value in lines]
                return ["firmware_state"]
            elif d_type == "bbu":
                return ["battery_state"]
            else:
                status = get_status_lines(lines).lower()
                if status in set(["not installed", "unknown", "medium speed", "normal speed", "low speed", "high speed", "not available"]):
                    return None
                else:
                    return ["status"]

        def _prune(in_dict):
            return {_key: _prune(_value) if type(_value) is dict else _value for _key, _value in in_dict.iteritems() if _value}

        def reorder_dict(in_dict):
            _result = {
                "c{:02d}".format(_idx): _interpret_dict("ctrl", _value) for _idx, _value in in_dict.iteritems()
            }
            # prune twice to remove empty subdicts
            _result = _prune(_prune(_result))
            return _result

        def emit_keys(in_dict):
            if type(in_dict) == dict:
                r_list = sum(
                    [
                        [
                            "{}{}{}".format(_key, ":" if sub_key else "", sub_key) for sub_key in emit_keys(_value)
                        ] for _key, _value in in_dict.iteritems() if _key not in ["lines", "_checks"]
                    ],
                    []
                )
                if "_checks" in in_dict:
                    r_list.append("")
                return r_list
            else:
                return [""]

        def _interpret_dict(d_type, in_dict):
            map_dict = {
                "enclosures": ("e", "enclosure"),
                "fans": ("f", "fan"),
                "power_supplies": ("p", "psu"),
                "slots": ("s", "slot"),
                "temperature_senors": ("t", "tempsensor"),
                "virt": ("v", "virt"),
                "pd": ("d", "pd"),
                "bbus": ("b", "bbu"),
            }
            r_dict = {}
            for _key, _t in map_dict.iteritems():
                r_dict.update(
                    {"{}{:02d}".format(_t[0], _idx): _interpret_dict(_t[1], _value) for _idx, _value in in_dict.get(_key, {}).iteritems() if type(_idx) == int}
                )
            if in_dict.get("lines", []):
                r_dict["lines"] = in_dict["lines"]
                _checks = get_check_list(d_type, in_dict["lines"])
                if _checks:
                    r_dict["_checks"] = _checks
            return r_dict

        def get_source(_ro_dict, _key):
            # return lines and check_list for given key
            _res = _ro_dict
            for _skey in _key.split(":"):
                _res = _res[_skey]
            return (_res["lines"], _res["_checks"])

        def _expand_key(entity_type):
            return {
                "c": "Ctrl",
                "v": "Virt",
                "p": "PSU",
                "s": "Slot",
                "e": "Encl",
                "b": "BBU",
                "f": "Fan",
                "d": "Disc",
            }[entity_type]

        def _full_key(_part):
            return "{}{:d}".format(
                {
                    "c": "ctrl",
                    "v": "virt",
                    "p": "psu",
                    "s": "slot",
                    "e": "encl",
                    "b": "bbu",
                    "f": "fan",
                    "d": "disc",
                }[_part[0]],
                int(_part[1:])
            )

        def get_info(_key, _lines, _check):
            return "{} {}".format(
                "/".join([_full_key(_part) for _part in _key.split(":")]),
                _check,
            )

        def _shorten_list(in_list):
            shorten_re = re.compile("^(?P<pre>c\d+:(v|e)\d+:(d|s|f))(?P<rest>\d+)$")
            _shorten_dict = {}
            new_list, _shorten_keys = ([], [])
            for key, _check, _info, _flag in r_list:
                _keep = True
                _match = shorten_re.match(key)
                if _match:
                    _keep = False
                    _gd = _match.groupdict()
                    if _gd["pre"] not in _shorten_keys:
                        _shorten_keys.append(_gd["pre"])
                        _shorten_dict[_gd["pre"]] = {
                            "list": [],
                            "check": _check,
                            "infos": [],
                            "flag": _flag,
                        }
                    _sde = _shorten_dict[_gd["pre"]]
                    if (_check, _flag) == (_sde["check"], _sde["flag"]):
                        _sde["list"].append((key, _gd["rest"]))
                        _sde["infos"].append(_info)
                    else:
                        _keep = True
                if _keep:
                    new_list.append((key, _check, _info, _flag))
            for _shorten_key in _shorten_keys:
                _sde = _shorten_dict[_shorten_key]
                new_list.append((_shorten_key, _sde["check"], _compress_infos(_sde["infos"]), _sde["flag"]))
            return new_list, _shorten_dict

        def _generate_short_result(_struct, _lss):
            _state_dict = {}
            # all keys are needef for the passive check result lookup key
            _all_keys = []
            for _state, _output, _info, _skey in _lss:
                # we ignore _info here to make things easier
                _state_dict.setdefault(_state, {}).setdefault((_output, _info), []).append(_skey)
                _all_keys.append(_skey)
            _ret_state = max(_state_dict.keys())
            ret_list = []
            for _state in sorted(_state_dict.keys()):
                for _output, _info in sorted(_state_dict[_state].keys()):
                    ret_list.append(
                        "{:d} {}{}: {}".format(
                            len(_state_dict[_state][(_output, _info)]),
                            _output,
                            " / {}".format(_info) if _info else "",
                            _compress_infos(_state_dict[_state][(_output, _info)])
                        )
                    )
            return _compress_infos(_all_keys), _ret_state, ", ".join(ret_list), ""

        def _compress_infos(in_list):
            # only working for standard input
            _prefix, _what = in_list[0].split()
            while _prefix[-1].isdigit():
                _prefix = _prefix[:-1]
            _ints = [int(_part.strip().split()[0][len(_prefix):]) for _part in in_list]
            return "{}{} {}".format(
                _prefix,
                logging_tools.compress_num_list(_ints),
                _what,
            )
        # rewrite bbu info
        for _c_id, _c_dict in ctrl_dict.iteritems():
            if "main" in _c_dict.get("bbu_keys", {}):
                _c_dict["bbus"] = {
                    0: {
                        "lines": [(_key, _value) for _key, _value in _c_dict["bbu_keys"]["main"].iteritems()]
                    }
                }
                del _c_dict["bbu_keys"]
            if "virt" not in _c_dict:
                # rewrite from old to new format
                _c_dict["virt"] = {
                    key: {
                        "lines": [
                            (line[0].lower().replace(" ", "_").replace("virtual_disk", "virtual_drive"), line[1]) for line in value
                        ]
                    } for key, value in _c_dict["logical_lines"].iteritems()
                }
                del _c_dict["logical_lines"]
        # print cur_ns
        # reorder dict
        _ro_dict = reorder_dict(ctrl_dict)
        # pprint.pprint(_ro_dict)
        # pprint.pprint(ctrl_dict)
        _key_list = emit_keys(_ro_dict)
        # print cur_ns
        # interpret flags
        _short_output = True if cur_ns.short_output in [True, "1", "y", "yes", "true", "True"] else False
        _ignore_missing_bbu = True if cur_ns.ignore_missing_bbu in [True, "1", "y", "yes", "true", "True"] else False
        # generate passive results if cur_ns.passive_check_postfix is set (not "-")
        _store_passive = cur_ns.passive_check_postfix != "-"
        if not _store_passive:
            # only makes sense with _store_passive==True
            _short_output = False
        if cur_ns.get_hints:
            r_list = []
            _ctrl_found = set()
            for _key in sorted(_key_list):
                _ctrl_key = _key.split(":")[0]
                if _ctrl_key not in _ctrl_found:
                    _ctrl_found.add(_ctrl_key)
                    r_list.extend([(_ctrl_key, "all", "SAS Controller {}".format(_ctrl_key), True), ])
                _lines, _checks = get_source(_ro_dict, _key)
                r_list.extend([(_key, _check, get_info(_key, _lines, _check), False) for _check in _checks])
                # all checks in one line ? Todo ...
                # r_list.append((_key, "::".join(_checks), ", ".join([get_info(_key, _lines, _check) for _check in _checks]), False))
            if _short_output:
                # shorten list
                r_list, _ignore_dict = _shorten_list(r_list)
            # pprint.pprint(r_list)
            return r_list
        else:
            _passive_dict = {
                "postfix": cur_ns.passive_check_postfix,
                "list": [],
            }
            # print "*", _key_list
            # if cur_ns.key != "all":
            # else:
            if cur_ns.check != "all":
                single_key = True
                _key_list = list(set(_key_list) & set([cur_ns.key]))
                target_checks = set([cur_ns.check])
                # print "*", _key_list, target_checks
            else:
                target_checks = None
                single_key = False
                if cur_ns.key:
                    _key_list = [_entry for _entry in _key_list if _entry.startswith(cur_ns.key)]
            _ok_dict = {}
            _ret_list = []
            _g_ret_state = limits.nag_STATE_OK
            # list for shortened output
            r_list = []
            for _key in sorted(_key_list):
                _lines, _checks = get_source(_ro_dict, _key)
                if target_checks:
                    _checks = list(set(_checks) & target_checks)
                for _check in _checks:
                    _info = get_info(_key, _lines, _check)
                    if _short_output:
                        r_list.append((_key, _check, _info, None))
                    _ret_state, _result, _info_str, _entity_type = check_status(_key, _lines, _check)
                    if _key.count(":b") and _ignore_missing_bbu:
                        # reduce state if necessary
                        _ret_state = min(_ret_state, limits.nag_STATE_WARNING)
                    if _store_passive:
                        _passive_dict["list"].append(
                            # format: info, ret_state, result (always show), info (only shown in case of non-OK)
                            (
                                _info, _ret_state, _result, _info_str
                            )
                        )

                    # print _info, _ret_state, _result
                    if _ret_state != limits.nag_STATE_OK:
                        _ret_list.append("{}: {}".format(_info, _result))
                    else:
                        if single_key:
                            _ret_list.append(_result)
                        _ok_dict.setdefault(_entity_type, []).append(0)
                    if _info_str:
                        _ret_list.append(_info_str)
                    _g_ret_state = max(_g_ret_state, _ret_state)
            if _short_output:
                # pprint.pprint(_passive_dict)
                r_list, shorten_dict = _shorten_list(r_list)
                # passive lut
                _pl = {_info: (_ret_state, _result, _info_str) for _info, _ret_state, _result, _info_str in _passive_dict["list"]}
                # rewrite the passive dict
                for _key, _struct in shorten_dict.iteritems():
                    # pprint.pprint(_struct)
                    # local state list
                    _lss = [list(_pl[_info]) + [_info] for _info in _struct["infos"]]
                    # remove from passive_dict.list
                    _passive_dict["list"] = [(_a, _b, _c, _d) for _a, _b, _c, _d in _passive_dict["list"] if _a not in _struct["infos"]]
                    # add summed result
                    _passive_dict["list"].append(_generate_short_result(_struct, _lss))
                # pprint.pprint(_passive_dict)
            # pprint.pprint(_passive_dict)
            if _store_passive:
                ascii_chunk = base64.b64encode(bz2.compress(json.dumps(_passive_dict)))
            else:
                ascii_chunk = ""
            # print _ret_list, _ok_dict
            if _ok_dict:
                _num_ok = sum([len(_val) for _val in _ok_dict.itervalues()])
                if _num_ok == 1 and single_key:
                    pass
                else:
                    _ret_list.append(
                        "{}: {}".format(
                            logging_tools.get_plural("OK check", _num_ok),
                            ", ".join(
                                [
                                    logging_tools.get_plural(_expand_key(_key), len(_val)) for _key, _val in _ok_dict.iteritems()
                                ]
                            )
                        )
                    )
            # pprint.pprint(_ret_list)
            return ExtReturn(_g_ret_state, ", ".join(_ret_list), ascii_chunk=ascii_chunk)

    @staticmethod
    def _dummy_hints():
        return [("", "all", "SAS Controllers", True), ]


class megaraid_sas_status_command(hm_classes.hm_command):
    def __init__(self, name):
        self.__cache = {}
        hm_classes.hm_command.__init__(self, name)
        self.parser.add_argument("--get-hints", dest="get_hints", default=False, action="store_true")
        self.parser.add_argument("--key", default="", type=str)
        self.parser.add_argument("--check", default="all", type=str)
        self.parser.add_argument("--passive-check-postfix", default="-", type=str)
        self.parser.add_argument("--short-output", default="0", type=str)
        self.parser.add_argument("--ignore-missing-bbu", default="0", type=str)
        self.parser.add_argument("--controller", default="all", type=str)

    def __call__(self, srv_com, cur_ns):
        ctrl_type.update("megaraid_sas")
        _ctrl = ctrl_type.ctrl("megaraid_sas")
        if _ctrl.update_ok(srv_com):
            return ctrl_check_struct(self.log, srv_com, _ctrl, [])

    def interpret(self, srv_com, cur_ns):
        # also done in special_megaraid_sas
        ctrl_dict = {}
        for res in srv_com["result"]:
            ctrl_dict[int(res.tag.split("}")[1].split("_")[-1])] = srv_com._interpret_el(res)
        return self._interpret(ctrl_dict, cur_ns)

    def interpret_old(self, result, cur_ns):
        ctrl_dict = hm_classes.net_to_sys(result[3:])
        return self._interpret(ctrl_dict, cur_ns)

    def _interpret(self, ctrl_dict, cur_ns):
        return ctrl_type.ctrl_class("megaraid_sas")._interpret(ctrl_dict, cur_ns)
