# Copyright (C) 2009-2015 Andreas Lang-Nevyjel
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
""" base objects for SNMP schemes for SNMP relayer """

import cStringIO
import argparse
import sys
import time

from initat.host_monitoring import limits
from initat.snmp.snmp_struct import value_cache
from initat.tools import logging_tools, process_tools

# maximum cache time, 15 minutes
MAX_CACHE_TIME = 15 * 60

# timeout of Eonstor
EONSTOR_TIMEOUT = 5 * 60


class SNMPNetObject(object):
    def __init__(self, log_com, verb_level, host, snmp_community, snmp_version):
        self.__verbose_level = verb_level
        self.name = host
        self.snmp_community = snmp_community
        self.snmp_version = snmp_version
        self.__cache_tree = {}
        self.__pending_requests = set()
        # self.__oid_times = {}
        # self.__time_steps = {}
        self.__oid_cache_defaults = {}
        # partially taken from collectd / background
        self.value_cache = value_cache()
        log_com(
            "init new SNMPNetObject ({}, {}, {:d})".format(
                self.name,
                self.snmp_community,
                self.snmp_version
            )
        )

    def log(self, log_com, what, log_level=logging_tools.LOG_LEVEL_OK):
        log_com("[{}] {}".format(self.name, what), log_level)

    def get_pending_requests(self, in_set, log_com):
        pend_reqs = self.__pending_requests & in_set
        if self.__verbose_level > 1:
            self.log(log_com, "{} pending".format(logging_tools.get_plural("request", len(pend_reqs))))
        return pend_reqs

    def add_to_pending_requests(self, in_set):
        # print "add", threading.currentThread().getName(), in_set
        self.__pending_requests |= in_set
        # print "after", threading.currentThread().getName(), self.__pending_requests

    def remove_from_pending_requests(self, in_set):
        # print "remove", threading.currentThread().getName(), in_set
        self.__pending_requests -= in_set
        # print "after", threading.currentThread().getName(), self.__pending_requests

    def cache_still_hot_enough(self, oid_set, log_com):
        he_reqs = set([key for key in oid_set if key in self.__cache_tree and self.__cache_tree[key]["refresh"] > time.time()])
        if self.__verbose_level > 1:
            self.log(log_com, "{} hot enough".format(logging_tools.get_plural("request", len(he_reqs))))
        return he_reqs

    def save_snmp_tree(self, oid, tree):
        oid_t = tuple(oid)
        if oid_t not in self.__oid_cache_defaults:
            self.__oid_cache_defaults[oid_t] = {
                "timeout": oid.cache_timeout,
                "refresh": oid.refresh_timeout
            }
        self.__cache_tree[oid_t] = {
            "expires": time.time() + self.__oid_cache_defaults[oid_t]["timeout"],
            "refresh": time.time() + self.__oid_cache_defaults[oid_t]["refresh"],
            "tree": tree
        }

    def snmp_tree_valid(self, oid):
        return (oid in self.__cache_tree and self.__cache_tree[oid]["expires"] > time.time())

    def get_snmp_tree(self, oid):
        return self.__cache_tree[oid]["tree"]


class SNMPRelayScheme(object):
    def __init__(self, name, **kwargs):
        self.name = name
        self.parser = argparse.ArgumentParser(prog=self.name)
        # public stuff
        self.snmp_dict = {}
        # for helper functions (show info)
        self.__dummy_init = kwargs.get("dummy_init", False)
        if not self.__dummy_init:
            self.__init_time = kwargs["init_time"]
            self.net_obj = kwargs["net_obj"]
            self.envelope = kwargs["envelope"]
            self.xml_input = kwargs["xml_input"]
            self.srv_com = kwargs["srv_com"]
            self.timeout = kwargs.get("timeout", 10)
        # print self.timeout
        self.__errors = []
        self.__missing_headers = []
        self.return_sent = False
        self.__req_list = []
        self.transform_single_key = False
        self.__info_tuple = ()

    def __del__(self):
        pass

    @property
    def dummy_init(self):
        return self.__dummy_init

    @property
    def proc_data(self):
        return [
            self.net_obj.snmp_version,
            self.net_obj.name,
            self.net_obj.snmp_community,
            self.envelope,
            self.transform_single_key,
            self.timeout
        ] + self.snmp_start()

    def parse_options(self, options, **kwargs):
        self.opts = argparse.Namespace()
        if self.__dummy_init:
            return
        old_stdout, old_stderr = (sys.stdout, sys.stderr)
        act_io = cStringIO.StringIO()
        sys.stdout = act_io
        sys.stderr = act_io
        one_integer_ok = kwargs.get("one_integer_arg_allowed", False)
        if one_integer_ok:
            self.parser.add_argument("iarg", type=int, default=0)
        try:
            self.opts = self.parser.parse_args(options)
        except SystemExit:
            self.__errors.append(act_io.getvalue())
        except:
            self.__errors.append(act_io.getvalue())
        finally:
            sys.stdout, sys.stderr = (
                old_stdout,
                old_stderr
            )

    def get_missing_headers(self):
        # for subclasses
        return self.__missing_headers

    def get_errors(self):
        # for subclasses
        return self.__errors

    def set_single_value(self, single_value):
        self.__single_value = single_value

    def pre_snmp_start(self, log_com):
        if not self.__info_tuple:
            self.__hv_mapping = {tuple(base_oid): base_oid for base_oid in self.requests}
            # list of oids we need and oids already pending
            act_oids, _pending_oids = (set(self.__hv_mapping.keys()), set())
            self.__hv_optional = {tuple(base_oid) for base_oid in self.requests if base_oid.optional}
            # check for caching and already pending requests
            # self.net_obj.lock()
            cache_ok = all(
                [
                    True if oid_struct.cache_it and self.net_obj.snmp_tree_valid(wf_oid) else False for wf_oid, oid_struct in self.__hv_mapping.iteritems()
                ]
            )
            if cache_ok:
                num_cached = len(act_oids)
                # copy snmp_values
                for wf_oid in act_oids:
                    self.snmp_dict[tuple(wf_oid)] = self.net_obj.get_snmp_tree(wf_oid)
            else:
                num_cached = 0
            # check for oids already pending (no need for double fetch)
            pending, hot_enough = (
                self.net_obj.get_pending_requests(act_oids, log_com),
                self.net_obj.cache_still_hot_enough(act_oids, log_com)
            )
            act_oids -= pending
            # also remove oids for which the cache needs no upgrade
            act_oids -= hot_enough
            num_refresh = len(act_oids)
            if cache_ok:
                # send return
                self._send_ok_return()
            elif not act_oids:
                self._send_cache_warn()
            self.net_obj.add_to_pending_requests(act_oids)
            # self.net_obj.release()
            self.__act_oids = act_oids
            self.__waiting_for, self.__received = (
                self.__act_oids,
                set()
            )
            self.__info_tuple = (cache_ok, num_cached, num_refresh, len(pending), len(hot_enough))
        return self.__info_tuple

    def snmp_start(self):
        if self.__act_oids:
            # order requests
            request_list = [
                (
                    key,
                    [
                        oid for oid in self.requests if oid.single_value == single_value and tuple(oid) in self.__act_oids
                    ]
                ) for (key, single_value) in [
                    ("V", True),
                    ("T", False)
                ]
            ]
        else:
            request_list = []
        # print "3", request_list
        return request_list

    def snmp_end(self, log_com):
        # remove all waiting headers from pending_list
        # self.net_obj.lock()
        self.net_obj.remove_from_pending_requests(self.__waiting_for)
        self.__waiting_for = self.__waiting_for.difference(self.__received)
        # remove optionals
        self.__waiting_for -= self.__hv_optional
        if self.__waiting_for:
            self.__missing_headers.extend(self.__waiting_for)
        else:
            # store in net_obj if needed
            for recv in self.__received:
                if self.__hv_mapping[recv].cache_it:
                    self.net_obj.save_snmp_tree(self.__hv_mapping[recv], self.snmp_dict[recv])
        # self.net_obj.release()
        # print "SNMP_END", self.__missing_headers, self.__errors
        # pprint.pprint(self.snmp_dict)
        if not self.return_sent:
            if self.__missing_headers or self.__errors:
                self._send_error_return()
            else:
                self._send_ok_return()
        # remove reference
        self.snmp_dict = None
        self.__hv_mapping = None

    def flag_error(self, what):
        self.__errors.append(what)

    def process_return(self):
        return limits.nag_STATE_CRITICAL, "process_return() not implemented for {}".format(self.name)

    def _send_cache_warn(self):
        act_state = limits.nag_STATE_WARNING
        self.send_return(act_state, "warning cache warming up")

    def _send_ok_return(self):
        try:
            act_state, act_str = self.process_return()
        except:
            act_state, act_str = (
                limits.nag_STATE_CRITICAL,
                "error in process_return() for {}: {}".format(
                    self.name,
                    process_tools.get_except_info()
                )
            )
        self.send_return(act_state, act_str)

    def error(self):
        pass

    def _send_error_return(self):
        self.error()
        err_str = "{}: {}; missing headers: {}".format(
            self.name,
            ", ".join(self.__errors) or "unspecified error",
            ", ".join([".".join(["{:d}".format(part) for part in oid]) for oid in self.__missing_headers]) or "none",
        )
        self.send_return(limits.nag_STATE_CRITICAL, err_str, True)

    def send_return(self, ret_state, ret_str, log_it=False):
        self.return_sent = True
        self.return_tuple = (ret_state, ret_str, log_it)
        if self.xml_input:
            self.srv_com.set_result(
                self.return_tuple[1],
                self.return_tuple[0],
            )

    def _simplify_keys(self, in_dict):
        # changes all keys from (x,) to x
        return {key[0] if (type(key) == tuple and len(key) == 1) else key: value for key, value in in_dict.iteritems()}

    def _check_for_missing_keys(self, in_dict, needed_keys):
        if not needed_keys < set(in_dict.keys()):
            mis_keys = needed_keys - set(in_dict.keys())
            raise KeyError("some keys missing: {}".format(", ".join([str(mis_key) for mis_key in mis_keys])))

    def _reorder_dict(self, in_dict):
        new_dict = {}
        for key, value in in_dict.iteritems():
            sub_idx, part_idx = key
            new_dict.setdefault(part_idx, {})[sub_idx] = value
        return new_dict

    # @property
    def get_requests(self):
        return self.__req_list

    # @requests.setter
    def set_requests(self, in_value):
        if type(in_value) is list:
            self.__req_list.extend(in_value)
        else:
            self.__req_list.append(in_value)

    requests = property(get_requests, set_requests)

    @property
    def snmp(self):
        return self.snmp_dict

    @snmp.setter
    def snmp(self, in_value):
        if type(in_value) is dict:
            self.__received |= set(in_value.keys())
            # set complete dict
            self.snmp_dict = in_value
        else:
            header, key, value = in_value
            if header in self.__waiting_for:
                self.__received.add(header)
                if self.__single_value:
                    self.snmp_dict[header] = value
                else:
                    if self.transform_single_key and len(key) == 1:
                        key = key[0]
                    self.snmp_dict.setdefault(header, {})[key] = value
