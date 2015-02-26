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
    "adp": set(
        set(
            [
                "product_name", "serial_no", "fw_version", "virtual_drives",
                "degraded", "offline", "physical_devices", "disks", "critical_disks",
                "failed_disks",
            ]
        )
    ),
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


class ShortOutputKeyCache(object):
    def __init__(self):
        self._state = limits.nag_STATE_OK
        self._keys = []
        self._results = []
        self._info_strs = []
        self.valid = False

    @staticmethod
    def shorten_keys(in_list):
        first_parts = set([_key.split()[0] for _key in in_list])
        if len(first_parts) == 1:
            return "{} {}".format(
                list(first_parts)[0],
                " ".join([_key.split(None, 1)[1] for _key in in_list])
            )
        else:
            return " ".join(in_list)

    def feed(self, key, state, result, info_str):
        self.valid = True
        self._state = max(self._state, state)
        self._keys.append(key)
        self._results.append(result)
        self._info_strs.append(info_str)

    def get_passive_entry(self):
        return (
            ShortOutputKeyCache.shorten_keys(self._keys),
            self._state,
            ", ".join(self._results),
            ", ".join(self._info_strs),
        )


class ctrl_type_megaraid_sas(ctrl_type):
    class Meta:
        name = "megaraid_sas"
        exec_name = "megarc"
        description = "MegaRAID SAS"

    def get_exec_list(self, ctrl_list=[]):
        if ctrl_list == []:
            ctrl_list = self._dict.keys()
        return [("/bin/true", ctrl_id, "init") for ctrl_id in ctrl_list] + \
               [("{} -AdpAllInfo -a{:d} -noLog".format(self._check_exec, ctrl_id), ctrl_id, "adp") for ctrl_id in ctrl_list] + \
               [("{} -LdPdInfo   -a{:d} -noLog".format(self._check_exec, ctrl_id), ctrl_id, "ld") for ctrl_id in ctrl_list] + \
               [("{} -AdpBbuCmd  -a{:d} -noLog".format(self._check_exec, ctrl_id), ctrl_id, "bbu") for ctrl_id in ctrl_list] + \
               [("{} -EncStatus  -a{:d} -noLog".format(self._check_exec, ctrl_id), ctrl_id, "enc") for ctrl_id in ctrl_list] + \
               [("{} -LDGetProp -Name -Lall -a{:d} -noLog".format(self._check_exec, ctrl_id), ctrl_id, "vdname") for ctrl_id in ctrl_list] + \
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
        elif run_type == "vdname":
            vd_re = re.compile("^Adapter\s+(?P<adp_num>\d)-VD\s+(?P<vd_num>\d+).*:\s+Name:\s+(?P<vd_name>\S+).*$")
            for line_num, line in enumerate([cur_line.rstrip() for cur_line in ccs.read().split("\n")]):
                vd_m = vd_re.match(line)
                if vd_m:
                    _gd = vd_m.groupdict()
                    _adp_num, _vd_num = (
                        int(_gd["adp_num"]),
                        int(_gd["vd_num"]),
                    )
                    if _adp_num in self._dict:
                        _adp = self._dict[_adp_num]
                        _virt = _adp.get("virt", {}).get(_vd_num, None)
                        if _virt and "lines" in _virt:
                            _virt["lines"].append(("name", _gd["vd_name"]))
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
                if line.lower().count("get bbu") and line.lower().endswith("failed."):
                    # add failed state
                    cur_mode = "bbu"
                    ctrl_stuff, count_dict = _ci.check_for_ctrl(line, ctrl_id_for_enclosure)
                    cur_dict = {"main": {"battery_state": "cannot read state"}}
                    ctrl_stuff["bbu_keys"] = cur_dict
                elif (parts[0], cur_mode) in [("adapter", None), ("adapter", "pd"), ("adapter", "run"), ("adapter", "virt")]:
                    cur_mode = "adp"
                    ctrl_stuff, count_dict = _ci.check_for_ctrl(line, int(parts[-1].replace("#", "")))
                    ctrl_stuff.setdefault("lines", [])
                    cur_dict = ctrl_stuff
                elif line.lower().startswith("bbu status for "):
                    cur_mode = "bbu"
                    ctrl_stuff, count_dict = _ci.check_for_ctrl(line, int(parts[-1].replace("#", "")))
                    cur_dict = {"main": {}}
                    ctrl_stuff["bbu_keys"] = cur_dict
                elif (parts[0], cur_mode) in [("virtual", "pd")] or (cur_mode == "adp" and line.lower().startswith("number of virt")):
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
                    _new_ctrl_id = ctrl_id_for_enclosure
                    ctrl_stuff, count_dict = _ci.check_for_ctrl(line, _new_ctrl_id)
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
                elif cur_mode in ["bbu", "enc", "adp"]:
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

        def _get_info_str(key, lines):
            _entity_type = key.split(":")[-1][0]
            if _entity_type in ["v", "c", "b"]:
                _ld = get_log_dict(lines)
                if _entity_type == "v":
                    _ld["ctrl"] = key.split(":")[0]
                    if "name" not in _ld:
                        _ld["name"] = ""
                    _info_str = "vd {virtual_drive} ('{name}', ctrl {ctrl}), RAID level {raid_level}, " \
                        "size={size}, drives={number_of_drives}, state={state}".format(
                            **_ld
                        )
                elif _entity_type == "c":
                    _info_f = []
                    for key in ["product_name"]:
                        if key in _ld:
                            _info_f.append(
                                "{}: {}".format(
                                    key,
                                    _ld[key],
                                )
                            )
                    _info_str = ", ".join(_info_f)
                elif _entity_type == "b":
                    _info_f = []
                    for key in [
                        "temperature", "voltage", "absolute_state_of_charge", "relative_state_of_charge",
                        "*learn_cycle_requested", "learn_cycle_status", "cycle_count"
                    ]:
                        if key[0] in ["*"]:
                            _key = key[1:]
                            _ignore_true = True
                        else:
                            _key = key
                            _ignore_true = False
                        if _key in _ld:
                            if _ignore_true and _ld[_key] is True:
                                continue
                            _info_f.append(
                                "{}: {}".format(
                                    _key,
                                    _ld[_key],
                                )
                            )
                    _info_str = ", ".join(_info_f)
            else:
                _info_str = ""
            if _info_str:
                _info_str = "{}: {}".format(
                    _expand_key(_entity_type),
                    _info_str,
                )
            return _info_str

        def check_status(key, lines, check):
            _entity_type = key.split(":")[-1][0]
            if check == "status":
                _val = [_val for _key, _val in lines if _key.endswith("_status")]
            else:
                _val = [_val for _key, _val in lines if _key == check or _key.replace(" ", "_") == check]
            if _val:
                _key_found = True
                _val = _val[0]
            else:
                _key_found = False
                # correct key not found
                _val = "not present / key not found"
            # _checked not needed right now ?
            _checked, _ret_state = (False, limits.nag_STATE_CRITICAL)
            if _entity_type == "v":
                _checked = True
                if check == "state":
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
            elif _entity_type == "c":
                _ret_state = limits.nag_STATE_OK
            elif _entity_type == "b":
                if _val.lower() in ("operational", "optimal"):
                    _ret_state = limits.nag_STATE_OK
                elif not _key_found:
                    _ld = get_log_dict(lines)
                    # state not definde, check for other flags
                    if not _ld.get("battery_pack_missing", True) and not _ld.get("battery_replacement_required", True):
                        _ret_state = limits.nag_STATE_OK
            return _ret_state, _val, _entity_type

        def get_check_list(d_type, lines):
            if d_type == "virt":
                _keys = [_key for _key, _value in lines]
                return list(set(_keys) & set(["state", "current_cache_policy"]))
            elif d_type == "pd":
                _keys = [_key for _key, _value in lines]
                return ["firmware_state"]
            elif d_type == "bbu":
                return ["battery_state"]
            elif d_type == "ctrl":
                return []
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

        def emit_keys(in_dict, level=0):
            if type(in_dict) == dict:
                _dk_l = set(in_dict.iterkeys()) - set(["lines", "_checks"])
                r_list = sum(
                    [
                        [
                            "{}{}{}".format(_key, ":" if sub_key else "", sub_key) for sub_key in emit_keys(in_dict[_key], level+1)
                        ] for _key in _dk_l
                    ],
                    []
                )
                # force iteration over this key (to generate info_str)
                if "_checks" in in_dict:
                    r_list.append("")
                elif not level:
                    # add controller keys at top level
                    r_list.extend(in_dict.keys())
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
            return (_res.get("lines", []), _res.get("_checks", []))

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
            return "{}{}".format(
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
                "{:d}".format(int(_part[1:])) if len(_part) > 1 else "",
            )

        def get_service(_key, _check=None):
            return "{}{}".format(
                "/".join([_full_key(_part) for _part in _key.split(":")]),
                " {}".format(_check) if _check else "",
            )

        def _shorten_list(in_list):
            # pprint.pprint(in_list)
            # shorten_re = re.compile("^(?P<pre>c\d+:(v|e)\d+:(d|s|f))(?P<rest>\d+)$")
            shorten_re = re.compile("^(?P<pre>c\d+:((v\d+:(d|s|f))|e))(?P<rest>.*\d+)$")
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
            # print "out"
            # pprint.pprint(new_list)
            # pprint.pprint(_shorten_dict)
            # print "-" * 10
            return new_list, _shorten_dict

        def _generate_short_result(_common_key, _struct, _lss):
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
            # return get_service(_common_key), _ret_state, ", ".join(ret_list), ""

        def _compress_list(in_list):
            # reduce list
            if len(in_list) == 1:
                return in_list
            # find longest common prefix
            _len = 0
            while True:
                _pfs = set([_value[:_len + 1] for _value in in_list])
                if len(_pfs) == 1:
                    _len += 1
                else:
                    break
            if _len:
                _res = _compress_list(
                    [_value[_len:] for _value in in_list]
                )
                return [(in_list[0][:_len], _res)]
            else:
                _pfs = sorted(list(_pfs))
                # check for integer pfs
                if all([_pf.isdigit() for _pf in _pfs]):
                    _dict = {}
                    _pfs = set()
                    for _value in in_list:
                        _pf = _value[0]
                        if _value[2].isdigit():
                            _pf = _value[:3]
                        elif _value[1].isdigit():
                            _pf = _value[:2]
                        else:
                            _pf = _value[0]
                        _pfs.add(int(_pf))
                        _dict.setdefault(_pf, []).append(_value[len(_pf):])
                    _pfs = sorted(list(_pfs))
                    if len(_pfs) > 1 and len(set(["".join(_val) for _val in _dict.itervalues()])) == 1:
                        # all values are the same, return compressed list
                        return [("[{}]".format(logging_tools.compress_num_list(_pfs)), _compress_list(_dict.values()[0]))]
                    else:
                        _pfs = ["{:d}".format(_val) for _val in _pfs]
                        return [(_pf, _compress_list(_dict[_pf])) for _pf in _pfs]
                else:
                    return [(_pf, _compress_list([_value[len(_pf):] for _value in in_list if _value[:len(_pf)] == _pf])) for _pf in _pfs]

        def _expand_list(in_struct):
            # recursivly expand a given line_struct
            _pf, _list = in_struct
            _r = []
            for _entry in _list:
                if isinstance(_entry, basestring):
                    _r.append(_entry)
                else:
                    _r.append(_expand_list(_entry))
            if len(_r) == 1:
                return "{}{}".format(
                    _pf,
                    _r[0],
                )
            else:
                return "{}[{}]".format(
                    _pf,
                    "][".join(_r),
                )

        def _compress_infos(in_list):
            return _expand_list(_compress_list(in_list)[0])

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
        # pprint.pprint(_key_list)
        # print cur_ns
        # interpret flags
        _short_output = True if cur_ns.short_output in [True, "1", "y", "yes", "true", "True"] else False
        _ignore_missing_bbu = True if cur_ns.ignore_missing_bbu in [True, "1", "y", "yes", "true", "True"] else False
        _ignore_keys = [_char for _char in cur_ns.ignore_keys]
        if "N" in _ignore_keys:
            _ignore_keys = []
        if _ignore_keys:
            # filter key_list
            _key_list = [_entry for _entry in _key_list if not any([_entry.count(_ik) for _ik in _ignore_keys])]
        if cur_ns.get_hints:
            r_list = []
            _ctrl_found = set()
            for _key in sorted(_key_list):
                _ctrl_key = _key.split(":")[0]
                if _ctrl_key not in _ctrl_found:
                    _ctrl_found.add(_ctrl_key)
                    r_list.extend([(_ctrl_key, "all", "{} info".format(_full_key(_key)), True), ])
                _lines, _checks = get_source(_ro_dict, _key)
                if _checks:
                    if _short_output:
                        r_list.append(
                            (
                                _key,
                                "::".join(_checks),
                                ShortOutputKeyCache.shorten_keys([get_service(_key, _check) for _check in _checks]),
                                False
                            )
                        )
                    else:
                        r_list.extend([(_key, _check, get_service(_key, _check), False) for _check in _checks])
                # all checks in one line ? Todo ...
            if _short_output:
                # shorten list
                r_list, _ignore_dict = _shorten_list(r_list)
            # pprint.pprint(r_list)
            return r_list
        else:
            _store_passive = cur_ns.passive_check_prefix != "-"
            # generate passive results if cur_ns.passive_check_prefix is set (not "-")
            if not _store_passive:
                # only makes sense with _store_passive==True
                _short_output = False
            _passive_dict = {
                "prefix": cur_ns.passive_check_prefix,
                "list": [],
            }
            # print "*", _key_list
            # if cur_ns.key != "all":
            # else:
            if cur_ns.check != "all":
                single_key = True
                _key_list = list(set(_key_list) & set([cur_ns.key]))
                target_checks = set(cur_ns.check.split("::"))
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
                # cache for short output
                _so_cache = ShortOutputKeyCache()
                _lines, _checks = get_source(_ro_dict, _key)
                if target_checks:
                    _checks = list(set(_checks) & target_checks)
                _info_str = _get_info_str(_key, _lines)
                if not _checks:
                    _ret_list.append(_info_str)
                for _check in _checks:
                    _info = get_service(_key, _check)
                    if _short_output:
                        r_list.append((_key, _check, _info, None))
                    _ret_state, _result, _entity_type = check_status(_key, _lines, _check)
                    if _key.count(":b") and _ignore_missing_bbu:
                        # reduce state if necessary
                        _ret_state = min(_ret_state, limits.nag_STATE_WARNING)
                    if _store_passive and _entity_type != "c":
                        # never store controller checks in passive dict
                        if _short_output:
                            _so_cache.feed(_info, _ret_state, _result, _info_str)
                        else:
                            _passive_dict["list"].append(
                                # format: info, ret_state, result (always show), info (only shown in case of non-OK)
                                (
                                    _info, _ret_state, _result, _info_str
                                )
                            )
                    else:
                        _ret_list.append(_info_str)
                    _info_str = ""
                    # print _info, _ret_state, _result
                    if _ret_state != limits.nag_STATE_OK:
                        _ret_list.append("{}: {}".format(_info, _result))
                    else:
                        if single_key:
                            _ret_list.append(_result)
                        if _entity_type != "c":
                            # we ignore contoller checks because they are only dummy checks
                            _ok_dict.setdefault(_entity_type, []).append(0)
                    _g_ret_state = max(_g_ret_state, _ret_state)
                # check for addendum tio passive_dict
                if _short_output and _store_passive and _so_cache.valid:
                    _passive_dict["list"].append(_so_cache.get_passive_entry())
            _ret_list = [_val for _val in _ret_list if _val.strip()]
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
                    _passive_dict["list"].append(_generate_short_result(_key, _struct, _lss))
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
        self.parser.add_argument("--passive-check-prefix", default="-", type=str)
        self.parser.add_argument("--short-output", default="0", type=str)
        self.parser.add_argument("--ignore-missing-bbu", default="0", type=str)
        # which keys to ignore
        self.parser.add_argument("--ignore-keys", default="N", type=str)
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
