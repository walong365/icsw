# Copyright (C) 2008-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-server
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
""" special (dynamic) tasks for md-config-server """

import time

import inflection
from django.db.models import Q

from ..config import global_config
from initat.cluster.backbone.models import monitoring_hint, DeviceLogEntry
from initat.icsw.service.instance import InstanceXML
from initat.cluster.backbone.server_enums import icswServiceEnum
from initat.tools import logging_tools

__all__ = [
    "SpecialBase",
    "ArgTemplate",
]


class SpecialBase(object):
    class Meta:
        # number of retries in case of error, can be zero
        retries = 1
        # timeout for connection to server
        timeout = 15
        # how long the cache is valid
        cache_timeout = 7 * 24 * 3600
        # wait time in case of connection error
        error_wait = 5
        # is active ?
        is_active = True
        # command line
        command_line = ""
        # description
        description = "no description available"
        # meta, triggers a cascade of checks
        meta = False
        # name in database
        database_name = ""

    def __init__(self, log_com, build_proc=None, s_check=None, host=None, build_cache=None, parent_check=None, **kwargs):
        self.__log_com = log_com
        self.__hm_port = InstanceXML(quiet=True).get_port_dict(
            icswServiceEnum.host_monitoring,
            command=True
        )
        for key in dir(SpecialBase.Meta):
            if not key.startswith("__") and not hasattr(self.Meta, key):
                setattr(self.Meta, key, getattr(SpecialBase.Meta, key))
        _name = self.__class__.__name__
        if _name.count("_"):
            _name = _name.split("_", 1)[1]
        elif _name.startswith("Special"):
            _name = _name[7:]
        self.Meta.name = _name
        # set a meaningfull, well-formatted database name
        self.Meta.database_name = inflection.underscore(self.Meta.name)
        self.ds_name = self.Meta.name
        # print "ds_name=", self.ds_name
        self.build_process = build_proc
        self.s_check = s_check
        self.parent_check = parent_check
        self.host = host
        self.build_cache = build_cache
        self.__hints_loaded = False
        # init with default
        self.__call_idx = 0

    def add_variable(self, new_var):
        # helper function: add device variable
        new_var.device = self.host
        new_var.save()
        # add to cache
        self.build_cache.add_variable(new_var)

    def set_variable(self, var_name, var_value):
        self.build_cache.set_variable(self.host, var_name, var_value)

    def store_hints(self, hint_list):
        self.log(
            "storing cache ({})".format(
                logging_tools.get_plural("entry", len(hint_list))
            )
        )
        cur_hints = monitoring_hint.objects.filter(
            Q(device=self.host) &
            Q(m_type=self.ds_name) &
            Q(call_idx=self.call_idx)
        )
        ch_dict = {
            (_h.m_type, _h.key): _h for _h in cur_hints
        }
        new_hints = self._salt_hints(hint_list, self.call_idx)
        nh_dict = {
            (_h.m_type, _h.key): _h for _h in new_hints
        }
        _del_keys = set(ch_dict.keys()) - set(nh_dict.keys())
        _new_keys = set(nh_dict.keys()) - set(ch_dict.keys())
        _same_keys = set(nh_dict.keys()) & set(ch_dict.keys())
        _log_level = logging_tools.LOG_LEVEL_OK
        _info = []
        if _new_keys:
            _info.append(
                "created {}".format(
                    logging_tools.get_plural("hint", len(_new_keys)),
                )
            )
            for _new_key in _new_keys:
                nh_dict[_new_key].save()
        if _same_keys:
            _info.append(
                "updated {}".format(
                    logging_tools.get_plural("hint", len(_same_keys)),
                )
            )
            for _same_key in _same_keys:
                ch_dict[_same_key].update(nh_dict[_same_key])
        if _del_keys:
            _log_level = logging_tools.LOG_LEVEL_WARN
            _info.append(
                "deleted {}".format(
                    logging_tools.get_plural("hint", len(_del_keys)),
                )
            )
            for _del_key in _del_keys:
                ch_dict[_del_key].delete()
        DeviceLogEntry.new(
            device=self.host,
            source=global_config["LOG_SOURCE_IDX"],
            level=_log_level,
            text=", ".join(_info) or "nothing done (no hints created)",
        )
        # import pprint
        # pprint.pprint(ch_dict)
        # pprint.pprint(nh_dict)

    def _load_cache(self):
        if not self.__hints_loaded:
            self.__hints_loaded = True
            self.__cache = monitoring_hint.objects.filter(
                Q(device=self.host) &
                Q(m_type=self.ds_name)
            )
            # set datasource to cache
            for _entry in self.__cache:
                if _entry.datasource not in ["c", "p"]:
                    _entry.datasource = "c"
                    _entry.save(update_fields=["datasource"])
            self.log(
                "loaded hints ({}) from db".format(
                    logging_tools.get_plural("entry", len(self.__cache))
                )
            )
        # hint_list = [_entry for _entry in self.__cache if _entry.call_idx == self.__call_idx]

    @property
    def hint_list(self):
        if not self.__hints_loaded:
            self._load_cache()
        return self.__cache

    # no longer needed, was referenced in megaraid_special
    # def remove_hints(self):
    #    self._load_cache()
    #    # remove all cached entries, cached entries are always local (with m_type set as ds_name)
    #    self.log("removing all {}".format(logging_tools.get_plural("cached entry", len(self.__cache))))
    #    [_entry.delete() for _entry in self.__cache]
    #    self.__cache = []

    def add_persistent_entries(self, hint_list, call_idx):
        pers_dict = {
            _hint.key: _hint for _hint in self.__cache if _hint.persistent and _hint.call_idx == call_idx
        }
        _hd = {_hint.key: _hint for _hint in hint_list}
        cache_keys = set(_hd.keys())
        missing_keys = set(pers_dict.keys()) - cache_keys
        same_keys = set(pers_dict.keys()) & cache_keys
        if missing_keys:
            self.log(
                "add {} to hint_list: {}".format(
                    logging_tools.get_plural("persistent entry", len(missing_keys)),
                    ", ".join(sorted(list(missing_keys))),
                )
            )
            for mis_key in missing_keys:
                _hint = pers_dict[mis_key]
                _hint.datasource = "p"
                _hint.save(update_fields=["datasource"])
                hint_list.append(_hint)
                # for later storage
                self.__hint_list.append(_hint)
        if same_keys:
            self.log("checking {}".format(logging_tools.get_plural("same key", len(same_keys))))
            for s_key in same_keys:
                # persistent hint
                _p_hint = pers_dict[s_key]
                # current hint
                _c_hint = _hd[s_key]
                # copy enabled field
                if _p_hint.enabled != _c_hint.enabled:
                    _c_hint.enabled = _p_hint.enabled

    def cleanup(self):
        self.build_process = None

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[sc] {}".format(what), log_level)

    def to_hint(self, srv_reply):
        # transforms server reply to monitoring hints
        return []

    def _salt_hints(self, in_list, call_idx):
        for hint in in_list:
            hint.datasource = "s"
            hint.device = self.host
            hint.m_type = self.ds_name
            hint.call_idx = call_idx
        return in_list

    @property
    def call_idx(self):
        # gives current server call number (for multi-call specials, for example: first call for network, second call for disks)
        return self.__call_idx

    def __call__(self, mode, **kwargs):
        s_name = self.Meta.name
        self.log(
            "starting {}@{} for {}".format(
                mode.name,
                s_name,
                self.host.full_name,
            )
        )
        s_time = time.time()
        if hasattr(self, "call"):
            cur_ret = self.call(**kwargs)
        else:
            cur_ret = []
        e_time = time.time()
        self.log(
            "took {}".format(
                logging_tools.get_diff_time_str(e_time - s_time),
            )
        )
        return cur_ret

    def get_arg_template(self, *args, **kwargs):
        return ArgTemplate(self.s_check, *args, is_active=self.Meta.is_active, **kwargs)


class ArgTemplate(dict):
    def __init__(self, s_base, *args, **kwargs):
        dict.__init__(self)
        self._addon_dict = {}
        self.info = args[0]
        # active flag for command
        self.is_active = kwargs.pop("is_active", True)
        # active flag for check (in case of special commands where more than one check is generated)
        # or checks where is_active is False
        self.check_active = kwargs.pop("check_active", None)
        if s_base is not None:
            if s_base.__class__.__name__ in ["DBStructuredMonBaseConfig", "CheckCommand"]:
                self.__arg_lut, self.__arg_list = s_base.arg_ll
            else:
                self.__arg_lut, self.__arg_list = s_base.s_check.arg_ll
        else:
            self.__arg_lut, self.__arg_list = ({}, [])
        # set defaults
        self.argument_names = sorted(list(set(self.__arg_list) | set(self.__arg_lut.values())))
        for arg_name in self.argument_names:
            dict.__setitem__(self, arg_name, "")
        for key, value in kwargs.items():
            self[key] = value

    @property
    def addon_dict(self):
        return self._addon_dict

    def __setitem__(self, key, value):
        l_key = key.lower()
        if l_key.startswith("arg"):
            if l_key.startswith("arg_"):
                key = "arg{:d}".format(len(self.argument_names) + 1 - int(l_key[4:]))
            if key.upper() not in self.argument_names:
                raise KeyError(
                    "key '{}' not defined in arg_list (info='{}', {})".format(
                        key,
                        self.info,
                        ", ".join(self.argument_names) or "no argument names"
                    )
                )
            else:
                dict.__setitem__(self, key.upper(), value)
        elif key.startswith("_"):
            self._addon_dict[key] = value
        else:
            if key in self.__arg_lut:
                dict.__setitem__(self, self.__arg_lut[key].upper(), value)
            elif "-{}".format(key) in self.__arg_lut:
                dict.__setitem__(self, self.__arg_lut["-{}".format(key)].upper(), value)
            elif "--{}".format(key) in self.__arg_lut:
                dict.__setitem__(self, self.__arg_lut["--{}".format(key)].upper(), value)
            else:
                raise KeyError(
                    "key '{}' not defined in arg_list ({})".format(
                        key,
                        self.info
                    )
                )
