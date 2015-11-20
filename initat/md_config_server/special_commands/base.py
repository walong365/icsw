# Copyright (C) 2008-2015 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
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
""" special tasks for md-config-server, should be split into submodules, FIXME """

import datetime
import time

from django.db.models import Q

from initat.cluster.backbone.models import monitoring_hint, cluster_timezone
from initat.host_monitoring import ipc_comtools
from initat.md_config_server.constants import DEFAULT_CACHE_MODE
from initat.tools import logging_tools, process_tools
from initat.icsw.service.instance import InstanceXML

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
        # contact server
        server_contact = False
        # is active ?
        is_active = True
        # command line
        command_line = ""
        # description
        description = "no description available"
        # meta, triggers a cascade of checks
        meta = False
        # identifier
        identifier = ""

    def __init__(self, log_com, build_proc=None, s_check=None, host=None, global_config=None, build_cache=None, parent_check=None, **kwargs):
        self.__log_com = log_com
        self.__hm_port = InstanceXML(quiet=True).get_port_dict("host-monitoring", command=True)
        for key in dir(SpecialBase.Meta):
            if not key.startswith("__") and not hasattr(self.Meta, key):
                setattr(self.Meta, key, getattr(SpecialBase.Meta, key))
        self.Meta.name = self.__class__.__name__.split("_", 1)[1]
        self.ds_name = self.Meta.name
        # print "ds_name=", self.ds_name
        self.cache_mode = kwargs.get("cache_mode", DEFAULT_CACHE_MODE)
        self.build_process = build_proc
        self.s_check = s_check
        self.parent_check = parent_check
        self.host = host
        self.build_cache = build_cache

    def add_variable(self, new_var):
        # helper function: add device variable
        new_var.device = self.host
        new_var.save()
        # add to cache
        self.build_cache.add_variable(new_var)

    def set_variable(self, var_name, var_value):
        self.build_cache.set_variable(self.host, var_name, var_value)

    def _store_cache(self):
        self.log("storing cache ({})".format(logging_tools.get_plural("entry", len(self.__hint_list))))
        monitoring_hint.objects.filter(Q(device=self.host) & Q(m_type=self.ds_name)).delete()
        for ch in self.__hint_list:
            ch.save()

    def _load_cache(self):
        self.__cache_created, self.__cache_age, self.__cache_valid = (0, 0, False)
        self.__cache = monitoring_hint.objects.filter(Q(device=self.host) & Q(m_type=self.ds_name))
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
        if self.__cache:
            _now = cluster_timezone.localize(datetime.datetime.now())
            self.__cache_age = max([abs(_now - _entry.changed).total_seconds() for _entry in self.__cache])
            self.__cache_valid = self.__cache_age < self.Meta.cache_timeout

    def _show_cache_info(self):
        if self.__cache:
            self.log(
                "cache is present ({}, age is {}, timeout {}, {})".format(
                    logging_tools.get_plural("entry", len(self.__cache)),
                    logging_tools.get_diff_time_str(self.__cache_age),
                    logging_tools.get_diff_time_str(self.Meta.cache_timeout),
                    "valid" if self.__cache_valid else "invalid",
                )
            )
        else:
            self.log("no cache set")

    def remove_cache_entries(self):
        # remove all cached entries, cached entries are always local (with m_type set as ds_name)
        self.log("removing all {:d} cached entries".format(len(self.__cache)))
        [_entry.delete() for _entry in self.__cache]
        self.__cache = []

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

    def collrelay(self, command, *args, **kwargs):
        return self._call_server(
            command,
            "collrelay",
            *args,
            **kwargs
        )

    def snmprelay(self, command, *args, **kwargs):
        return self._call_server(
            command,
            "snmp_relay",
            *args,
            snmp_community=self.host.dev_variables["SNMP_READ_COMMUNITY"],
            snmp_version=self.host.dev_variables["SNMP_VERSION"],
            **kwargs
        )

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

    def _call_server(self, command, server_name, *args, **kwargs):
        if not self.Meta.server_contact:
            # not beautifull but working
            self.log("not allowed to make an external call", logging_tools.LOG_LEVEL_CRITICAL)
            return None
        self.log("calling server '{}' for {}, command is '{}', {}, {}".format(
            server_name,
            self.host.valid_ip.ip,
            command,
            "args is '{}'".format(", ".join([str(value) for value in args])) if args else "no arguments",
            ", ".join(["{}='{}'".format(key, str(value)) for key, value in kwargs.iteritems()]) if kwargs else "no kwargs",
        ))
        connect_to_localhost = kwargs.pop("connect_to_localhost", False)
        conn_ip = "127.0.0.1" if connect_to_localhost else self.host.valid_ip.ip
        if not self.__use_cache:
            # contact the server / device
            hint_list = []
            for cur_iter in xrange(self.Meta.retries + 1):
                _result_ok = False
                log_str, log_level = (
                    "iteration {:d} of {:d} (timeout={:d})".format(cur_iter, self.Meta.retries, self.Meta.timeout),
                    logging_tools.LOG_LEVEL_ERROR,
                )
                s_time = time.time()
                try:
                    srv_reply = ipc_comtools.send_and_receive_zmq(
                        conn_ip,
                        command,
                        *args,
                        server=server_name,
                        zmq_context=self.build_process.zmq_context,
                        port=self.__hm_port,
                        timeout=self.Meta.timeout,
                        **kwargs
                    )
                except:
                    log_str = "{}, error connecting to '{}' ({}, {}): {}".format(
                        log_str,
                        server_name,
                        conn_ip,
                        command,
                        process_tools.get_except_info()
                    )
                    self.__server_contact_ok = False
                else:
                    srv_error = srv_reply.xpath(".//ns:result[@state != '0']", smart_strings=False)
                    if srv_error:
                        self.__server_contact_ok = False
                        log_str = "{}, got an error ({:d}): {}".format(
                            log_str,
                            int(srv_error[0].attrib["state"]),
                            srv_error[0].attrib["reply"],
                        )
                    else:
                        e_time = time.time()
                        log_str = "{}, got a valid result in {}".format(
                            log_str,
                            logging_tools.get_diff_time_str(e_time - s_time),
                        )
                        _result_ok = True
                        log_level = logging_tools.LOG_LEVEL_OK
                        # salt hints, add call_idx
                        hint_list = self._salt_hints(
                            self.to_hint(srv_reply),
                            self.__call_idx
                        )
                        # as default all hints are used for monitor checks
                        for _entry in hint_list:
                            _entry.check_created = True
                        self.__server_contacts += 1
                        self.__hint_list.extend(hint_list)
                self.log(log_str, log_level)
                if _result_ok:
                    break
                if self.__server_contacts <= self.Meta.retries:
                    # only wait if we are belov the retry threshold
                    self.log("waiting for {:d} seconds".format(self.Meta.error_wait), logging_tools.LOG_LEVEL_WARN)
                    time.sleep(self.Meta.error_wait)
            if hint_list == [] and self.__call_idx == 0 and len(self.__cache):
                # use cache only when first call went wrong and we have something in the cache
                self.__use_cache = True
        if self.__use_cache:
            hint_list = [_entry for _entry in self.__cache if _entry.call_idx == self.__call_idx]
            self.log("take {} from cache".format(logging_tools.get_plural("entry", len(hint_list))))
        else:
            # add persistent values
            self.add_persistent_entries(hint_list, self.__call_idx)
        self.__call_idx += 1
        return hint_list

    def __call__(self, **kwargs):
        s_name = self.__class__.__name__.split("_", 1)[1]
        self.log(
            "starting {} for {}, cache_mode is {}".format(
                s_name,
                self.host.name,
                self.cache_mode
            )
        )
        s_time = time.time()
        # flag to force store the cache (in case of migration of cache entries from FS to DB), only used internally
        self.__force_store_cache = False
        if self.Meta.server_contact:
            # at first we load the current cache
            self._load_cache()
            # show information
            self._show_cache_info()
            # use cache flag, dependent on the cache mode
            if self.cache_mode == "ALWAYS":
                self.__use_cache = True
            elif self.cache_mode == "DYNAMIC":
                self.__use_cache = self.__cache_valid
            elif self.cache_mode == "REFRESH":
                self.__use_cache = False
            # anything got from a direct all
            self.__server_contact_ok, self.__server_contacts = (True, 0)
            # init result list and number of server calls
            self.__hint_list, self.__call_idx = ([], 0)
        cur_ret = self._call(**kwargs)
        e_time = time.time()
        if self.Meta.server_contact and not self.__use_cache:
            self.log(
                "took {}, ({:d} ok, {:d} server contacts [{}], {})".format(
                    logging_tools.get_diff_time_str(e_time - s_time),
                    self.__call_idx,
                    self.__server_contacts,
                    "ok" if self.__server_contact_ok else "failed",
                    logging_tools.get_plural("hint", len(self.__hint_list)),
                )
            )
            # anything set (from cache or direct) and all server contacts ok (a little bit redundant)
            if (self.__server_contacts == self.__call_idx and self.__call_idx) or self.__force_store_cache:
                if (self.__server_contacts and self.__server_contact_ok) or self.__force_store_cache:
                    self._store_cache()
        else:
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
            if s_base.__class__.__name__ == "check_command":
                self.__arg_lut, self.__arg_list = s_base.arg_ll
            else:
                self.__arg_lut, self.__arg_list = s_base.s_check.arg_ll
        else:
            self.__arg_lut, self.__arg_list = ({}, [])
        # set defaults
        self.argument_names = sorted(list(set(self.__arg_list) | set(self.__arg_lut.values())))
        for arg_name in self.argument_names:
            dict.__setitem__(self, arg_name, "")
        for key, value in kwargs.iteritems():
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
