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
""" SNMP schemes for SNMP relayer """

from initat.host_monitoring import limits
from initat.snmp.struct import snmp_oid, value_cache
import cStringIO
from initat.tools import logging_tools
import argparse
from initat.tools import process_tools
import socket
import sys
import time

# maximum cache time, 15 minutes
MAX_CACHE_TIME = 15 * 60

# timeout of Eonstor
EONSTOR_TIMEOUT = 5 * 60


class net_object(object):
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
            "init new host_object ({}, {}, {:d})".format(
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
            self.log(log_com, "%s pending" % (logging_tools.get_plural("request", len(pend_reqs))))
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
            self.log(log_com, "%s hot enough" % (logging_tools.get_plural("request", len(he_reqs))))
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


class snmp_scheme(object):
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


class load_scheme(snmp_scheme):
    def __init__(self, **kwargs):
        snmp_scheme.__init__(self, "load", **kwargs)
        # T for table, G for get
        self.requests = snmp_oid("1.3.6.1.4.1.2021.10.1.3", cache=True)
        self.parser.add_argument("-w", type=float, dest="warn", help="warning value [%(default)s]", default=5.0)
        self.parser.add_argument("-c", type=float, dest="crit", help="critical value [%(default)s]", default=10.0)
        self.parse_options(kwargs["options"])

    def process_return(self):
        simple_dict = self._simplify_keys(self.snmp_dict.values()[0])
        load_array = [float(simple_dict[key]) for key in [1, 2, 3]]
        max_load = max(load_array)
        ret_state = limits.nag_STATE_CRITICAL if max_load > self.opts.crit else (limits.nag_STATE_WARNING if max_load > self.opts.warn else limits.nag_STATE_OK)
        return ret_state, "load 1/5/15: %.2f / %.2f / %.2f" % (
            load_array[0],
            load_array[1],
            load_array[2]
        )


def k_str(i_val):
    f_val = float(i_val)
    if f_val < 1024:
        return "%0.f kB" % (f_val)
    f_val /= 1024.
    if f_val < 1024.:
        return "%.2f MB" % (f_val)
    f_val /= 1024.
    return "%.2f GB" % (f_val)


class linux_memory_scheme(snmp_scheme):
    def __init__(self, **kwargs):
        snmp_scheme.__init__(self, "linux_memory", **kwargs)
        # T for table, G for get
        self.requests = snmp_oid("1.3.6.1.2.1.25.2.3.1", cache=True, cache_timeout=5)
        self.parse_options(kwargs["options"])

    def process_return(self):
        use_dict = self._simplify_keys(self.snmp_dict.values()[0])
        use_dict = {
            use_dict[(3, key)].lower(): {
                "allocation_units": use_dict[(4, key)],
                "size": use_dict[(5, key)],
                "used": use_dict.get((6, key), None)
            } for key in [
                _key[1] for _key in use_dict.keys() if _key[0] == 1
            ] if not use_dict[(3, key)].startswith("/")
        }
        # pprint.pprint(use_dict)
        phys_total, phys_used = (
            use_dict["physical memory"]["size"],
            use_dict["physical memory"]["used"]
        )
        # cached = use_dict["cached memory"]["size"]
        # buffers = use_dict["memory buffers"]["size"]
        # cb_size = cached + buffers
        swap_total, swap_used = (
            use_dict["swap space"]["size"],
            use_dict["swap space"]["used"]
        )
        # sub buffers and cache from phys_used
        # phys_used -= cb_size
        all_used = phys_used + swap_used
        phys_free, swap_free = (
            phys_total - phys_used,
            swap_total - swap_used)
        all_total, _all_free = (
            phys_total + swap_total,
            phys_free + swap_free)
        if phys_total == 0:
            memp = 100
        else:
            memp = 100 * phys_used / phys_total
        if all_total == 0:
            allp = 100
        else:
            allp = 100 * all_used / all_total
        ret_state = limits.nag_STATE_OK
        return ret_state, "meminfo: %d %% of %s phys, %d %% of %s tot" % (
            memp,
            k_str(phys_total),
            allp,
            k_str(all_total))


class snmp_info_scheme(snmp_scheme):
    def __init__(self, **kwargs):
        snmp_scheme.__init__(self, "snmp_info", **kwargs)
        # T for table, G for get
        self.requests = snmp_oid("1.3.6.1.2.1.1", cache=True)
        self.parse_options(kwargs["options"])

    def process_return(self):
        simple_dict = self.snmp_dict.values()[0]
        self._check_for_missing_keys(simple_dict, needed_keys=set([(4, 0), (5, 0), (6, 0)]))
        ret_state = limits.nag_STATE_OK
        return ret_state, "SNMP Info: contact %s, name %s, location %s" % (
            simple_dict[(4, 0)] or "???",
            simple_dict[(5, 0)] or "???",
            simple_dict[(6, 0)] or "???",
        )


class qos_cfg(object):
    def __init__(self, idx):
        self.idx = idx
        self.if_idx, self.direction = (0, 0)
        self.class_dict = {}

    def set_if_idx(self, if_idx):
        self.if_idx = if_idx

    def set_direction(self, act_dir):
        self.direction = act_dir
    # def add_class(self, cm_idx, idx):
    #    self.class_dict[idx] = qos_class(idx, cm_idx)

    def feed_bit_rate(self, class_idx, value):
        self.class_dict[class_idx].feed_bit_rate(value)

    def feed_drop_rate(self, class_idx, value):
        self.class_dict[class_idx].feed_drop_rate(value)

    def __repr__(self):
        return "qos_cfg %6d; if_idx %4d; direction %d; %s" % (
            self.idx,
            self.if_idx,
            self.direction,
            ", ".join([str(value) for value in self.class_dict.itervalues()]) if self.class_dict else "<NC>")


class check_snmp_qos_scheme(snmp_scheme):
    def __init__(self, **kwargs):
        snmp_scheme.__init__(self, "check_snmp_qos", **kwargs)
        self.oid_dict = {
            "if_name": (1, 3, 6, 1, 2, 1, 31, 1, 1, 1, 1),
            "if_alias": (1, 3, 6, 1, 2, 1, 31, 1, 1, 1, 18),
            "cb_qos_policy_direction": (1, 3, 6, 1, 4, 1, 9, 9, 166, 1, 1, 1, 1, 3),
            # qos_idx -> if_index
            "cb_qos_if_index": (1, 3, 6, 1, 4, 1, 9, 9, 166, 1, 1, 1, 1, 4),
            "cb_qos_config_index": (1, 3, 6, 1, 4, 1, 9, 9, 166, 1, 5, 1, 1, 2),
            # QoS classes
            "cb_qos_cmname": (1, 3, 6, 1, 4, 1, 9, 9, 166, 1, 7, 1, 1, 1),
            "cb_qos_bit_rate": (1, 3, 6, 1, 4, 1, 9, 9, 166, 1, 15, 1, 1, 11),
            "cb_qos_dropper_rate": (1, 3, 6, 1, 4, 1, 9, 9, 166, 1, 15, 1, 1, 18)
        }
        self.parser.add_argument("-k", type=str, dest="key", help="QOS keys [%(default)s]", default="1")
        self.parser.add_argument("-z", type=str, dest="qos_ids", help="QOS Ids [%(default)s]", default="")
        self.parse_options(kwargs["options"])
        self.transform_single_key = True
        if not self.dummy_init:
            if self.opts.key.count(","):
                self.qos_key, self.if_idx = [int(value) for value in self.opts.key.split(",")]
            else:
                self.qos_key, self.if_idx = (int(self.opts.key), 0)
        self.requests = [snmp_oid(value, cache=True, cache_timeout=150) for value in self.oid_dict.itervalues()]

    def _build_base_cfg(self):
        self.__qos_cfg_dict, self.__rev_dict = ({}, {})
        idx_list, idx_set = ([], set())
        cfg_keys = sorted(
            [
                key for key in self.snmp_dict[
                    self.oid_dict["cb_qos_if_index"]
                ].keys() if self.snmp_dict[self.oid_dict["cb_qos_policy_direction"]][key] == 2
            ]
        )
        for key in cfg_keys:
            act_cfg = qos_cfg(key)
            act_idx = self.snmp_dict[self.oid_dict["cb_qos_if_index"]][key]
            act_cfg.set_if_idx(act_idx)
            act_cfg.set_direction(self.snmp_dict[self.oid_dict["cb_qos_policy_direction"]][key])
            self.__qos_cfg_dict[key] = act_cfg
            self.__rev_dict[act_cfg.if_idx] = key
            if act_idx not in idx_set:
                idx_set.add(act_idx)
                idx_list.append(act_idx)
        self.idx_list, self.idx_set = (idx_list, idx_set)

    def process_return(self):
        self._build_base_cfg()
        idx_list, idx_set = (self.idx_list, self.idx_set)
        ret_value, ret_lines = (limits.nag_STATE_OK, [])
        if self.qos_key == 1:
            ret_lines = ["%d" % (value) for value in idx_list]
        elif self.qos_key == 2:
            ret_lines = ["%d!%d" % (value, value) for value in idx_list]
        elif self.qos_key == 3:
            ret_lines = ["%d!%s" % (value, self.snmp_dict[self.oid_dict["if_alias"]][value]) for value in sorted(idx_set)]
        elif self.qos_key == 4:
            ret_lines = ["%d!%s" % (value, self.snmp_dict[self.oid_dict["if_name"]][value]) for value in sorted(idx_set)]
        elif self.qos_key in [5, 6]:
            # qos class names
            cm_dict = {key: value for key, value in self.snmp_dict[self.oid_dict["cb_qos_cmname"]].iteritems()}
            if self.opts.qos_ids:
                needed_keys = [key for key, value in cm_dict.iteritems() if value in self.opts.qos_ids.split(",")]
            else:
                needed_keys = cm_dict.keys()
            # index dict
            try:
                cfg_idx_start, val_idx_start = (
                    self.oid_dict["cb_qos_config_index"],
                    self.oid_dict["cb_qos_bit_rate" if self.qos_key == 5 else "cb_qos_dropper_rate"]
                )
                # cfg_idx_start = tuple(list(cfg_idx_start) + [rev_dict[self.if_idx]])
                # val_idx_start = tuple(list(val_idx_start) + [rev_dict[self.if_idx]])
                # pprint.pprint(self.snmp_dict)
                idx_dict = {key[1]: value for key, value in self.snmp_dict[cfg_idx_start].iteritems() if key[0] == self.__rev_dict[self.if_idx]}
                value_dict = {key[1]: value for key, value in self.snmp_dict[val_idx_start].iteritems() if key[0] == self.__rev_dict[self.if_idx]}
                # #pprint.pprint(value_dict)
            except KeyError:
                ret_value, ret_lines = (limits.nag_STATE_CRITICAL, ["Could not find interface %d, giving up." % (self.if_idx)])
            else:
                # value dict
                # reindex value_dict
                r_value_dict = {idx_dict[key]: value for key, value in value_dict.iteritems()}
                ret_lines = [
                    " ".join(
                        [
                            "%s:%d" % (
                                cm_dict[needed_key],
                                r_value_dict[needed_key]
                            ) for needed_key in needed_keys if needed_key in r_value_dict
                        ]
                    )
                ]
        else:
            ret_value = limits.nag_STATE_CRITICAL
            ret_lines = ["unknown key / idx %d / %d" % (self.qos_key,
                                                        self.if_idx)]
        # pprint.pprint(self.snmp_dict)
        return ret_value, "\n".join(ret_lines)


class eonstor_object(object):
    def __init__(self, type_str, in_dict, **kwargs):
        # print time.ctime(), "new eonstor_object"
        self.type_str = type_str
        self.name = in_dict[8]
        self.state = int(in_dict[kwargs.get("state_key", 13)])
        # default values
        self.nag_state, self.state_strs = (limits.nag_STATE_OK, [])
        self.out_string = ""
        self.long_string = ""

    def __del__(self):
        # print time.ctime(), "del eonstor_object"
        pass

    def set_error(self, err_str):
        self.nag_state = max(self.nag_state, limits.nag_STATE_CRITICAL)
        self.state_strs.append(err_str)

    def set_warn(self, warn_str):
        self.nag_state = max(self.nag_state, limits.nag_STATE_WARNING)
        self.state_strs.append(warn_str)

    def get_state_str(self):
        return ", ".join(self.state_strs) or "ok"

    def get_ret_str(self, **kwargs):
        out_str = self.long_string if (self.long_string and kwargs.get("long_format", False)) else self.out_string
        if self.nag_state == limits.nag_STATE_OK and out_str:
            return "%s: %s" % (
                self.name,
                out_str,
            )
        elif self.nag_state:
            return "%s: %s%s" % (
                self.name,
                self.get_state_str(),
                " (%s)" % (out_str) if out_str else "",
            )
        else:
            return ""


class eonstor_disc(eonstor_object):
    lu_dict = {
        0: ("New Drive", limits.nag_STATE_OK),
        1: ("On-Line Drive", limits.nag_STATE_OK),
        2: ("Used Drive", limits.nag_STATE_OK),
        3: ("Spare Drive", limits.nag_STATE_OK),
        4: ("Drive Initialization in Progress", limits.nag_STATE_WARNING),
        5: ("Drive Rebuild in Progress", limits.nag_STATE_WARNING),
        6: ("Add Drive to Logical Drive in Progress", limits.nag_STATE_WARNING),
        9: ("Global Spare Drive", limits.nag_STATE_OK),
        int("11", 16): ("Drive is in process of Cloning another Drive", limits.nag_STATE_WARNING),
        int("12", 16): ("Drive is a valid Clone of another Drive", limits.nag_STATE_OK),
        int("13", 16): ("Drive is in process of Copying from another Drive", limits.nag_STATE_WARNING),
        int("3f", 16): ("Drive Absent", limits.nag_STATE_OK),
        # int("8x", 16) : "SCSI Device (Type x)",
        int("fc", 16): ("Missing Global Spare Drive", limits.nag_STATE_CRITICAL),
        int("fd", 16): ("Missing Spare Drive", limits.nag_STATE_CRITICAL),
        int("fe", 16): ("Missing Drive", limits.nag_STATE_CRITICAL),
        int("ff", 16): ("Failed Drive", limits.nag_STATE_CRITICAL)
    }

    def __init__(self, in_dict):
        eonstor_object.__init__(self, "disc", in_dict, state_key=11)
        disk_num = int(in_dict[13])
        self.name = "Disc{:d}".format(disk_num)
        if self.state in self.lu_dict:
            state_str, state_val = self.lu_dict[self.state]
            if state_val == limits.nag_STATE_WARNING:
                self.set_warn(state_str)
            elif state_val == limits.nag_STATE_CRITICAL:
                self.set_error(state_str)
        elif self.state & int("80", 16) == int("80", 16):
            self.name = "SCSI Disc {:d}".format(self.state & ~int("80", 16))
        else:
            self.set_warn("unknown state {:d}".format(self.state))
        # generate long string
        # ignore SCSIid and SCSILun
        if 15 in in_dict:
            disk_size = (2 ** int(in_dict[8])) * int(in_dict[7])
            vers_str = "{} ({})".format(
                (" ".join(in_dict[15].split())).strip(),
                in_dict[16].strip()
            )
            self.long_string = "{}, LC {:d}, PC {:d}, {}".format(
                logging_tools.get_size_str(disk_size, divider=1000),
                int(in_dict[2]),
                int(in_dict[3]),
                vers_str
            )
        else:
            self.long_string = "no disk"

    def __repr__(self):
        return "%s, state 0x%x (%d, %s)" % (
            self.name,
            self.state,
            self.nag_state,
            self.get_state_str())


class eonstor_ld(eonstor_object):
    lu_dict = {0: ("Good", limits.nag_STATE_OK),
               1: ("Rebuilding", limits.nag_STATE_WARNING),
               2: ("Initializing", limits.nag_STATE_WARNING),
               3: ("Degraded", limits.nag_STATE_CRITICAL),
               4: ("Dead", limits.nag_STATE_CRITICAL),
               5: ("Invalid", limits.nag_STATE_CRITICAL),
               6: ("Incomplete", limits.nag_STATE_CRITICAL),
               7: ("Drive missing", limits.nag_STATE_CRITICAL)}

    def __init__(self, in_dict):
        eonstor_object.__init__(self, "ld", in_dict, state_key=7)
        self.name = "LD"
        state_str, state_val = self.lu_dict[int(in_dict[6]) & 7]
        if state_val == limits.nag_STATE_WARNING:
            self.set_warn(state_str)
        elif state_val == limits.nag_STATE_CRITICAL:
            self.set_error(state_str)
        if self.state & 1:
            self.set_warn("rebuilding")
        if self.state & 2:
            self.set_warn("expanding")
        if self.state & 4:
            self.set_warn("adding drive(s)")
        if self.state & 64:
            self.set_warn("SCSI drives operation paused")
        # opmode
        op_mode = int(in_dict[5]) & 15
        op_mode_str = {0: "Single Drive",
                       1: "NON-RAID",
                       2: "RAID 0",
                       3: "RAID 1",
                       4: "RAID 3",
                       5: "RAID 4",
                       6: "RAID 5",
                       7: "RAID 6"}.get(op_mode, "NOT DEFINED")
        op_mode_extra_bits = int(in_dict[5]) - op_mode
        if type(in_dict[3]) == str and in_dict[3].lower().startswith("0x"):
            ld_size = int(in_dict[3][2:], 16) * 512
            vers_str = "id %s" % (in_dict[2])
        else:
            ld_size = (2 ** int(in_dict[4])) * (int(in_dict[3]))
            vers_str = "id %d" % (int(in_dict[2]))
        drv_total, drv_online, drv_spare, drv_failed = (int(in_dict[8]),
                                                        int(in_dict[9]),
                                                        int(in_dict[10]),
                                                        int(in_dict[11]))
        if drv_failed:
            self.set_error("%s failed" % (logging_tools.get_plural("drive", drv_failed)))
        drv_info = "%d total, %d online%s" % (drv_total,
                                              drv_online,
                                              ", %d spare" % (drv_spare) if drv_spare else "")
        self.long_string = "%s (0x%x) %s, %s, %s" % (op_mode_str,
                                                     op_mode_extra_bits,
                                                     logging_tools.get_size_str(ld_size, divider=1000),
                                                     drv_info,
                                                     vers_str)

    def __repr__(self):
        return "%s, state 0x%x (%d, %s)" % (
            self.name,
            self.state,
            self.nag_state,
            self.get_state_str())


class eonstor_slot(eonstor_object):
    def __init__(self, in_dict):
        eonstor_object.__init__(self, "slot", in_dict)
        if self.state & 1:
            self.set_error("Sense circuitry malfunction")
        if self.state & 2:
            self.set_error("marked BAD, waiting for replacement")
        if self.state & 4:
            self.set_warn("not activated")
        if self.state & 64:
            self.set_warn("ready for insertion / removal")
        if self.state & 128:
            self.set_warn("slot is empty")

    def __del__(self):
        eonstor_object.__del__(self)

    def __repr__(self):
        return "slot %s, state 0x%x (%d, %s)" % (
            self.name,
            self.state,
            self.nag_state,
            self.get_state_str())


class eonstor_psu(eonstor_object):
    def __init__(self, in_dict):
        eonstor_object.__init__(self, "PSU", in_dict)
        if self.state & 1:
            self.set_error("PSU malfunction")
        if self.state & 64:
            self.set_warn("PSU is OFF")
        if self.state & 128:
            self.set_warn("PSU not present")

    def __del__(self):
        eonstor_object.__del__(self)

    def __repr__(self):
        return "PSU %s, state 0x%x (%d, %s)" % (
            self.name,
            self.state,
            self.nag_state,
            self.get_state_str())


class eonstor_bbu(eonstor_object):
    def __init__(self, in_dict):
        eonstor_object.__init__(self, "BBU", in_dict)
        if self.state & 1:
            self.set_error("BBU malfunction")
        if self.state & 2:
            self.set_warn("BBU charging")
        if self.state & 64:
            self.set_warn("BBU disabled")
        if self.state & 128:
            self.set_warn("BBU not present")
        # check load state
        load_state = (self.state >> 2) & 7
        if load_state == 1:
            self.set_warn("not fully charged")
        elif load_state == 2:
            self.set_error("charge critically low")
        elif load_state == 3:
            self.set_error("completely drained")

    def __del__(self):
        eonstor_object.__del__(self)

    def __repr__(self):
        return "BBU %s, state 0x%x (%d, %s)" % (
            self.name,
            self.state,
            self.nag_state,
            self.get_state_str())


class eonstor_ups(eonstor_object):
    def __init__(self, in_dict):
        eonstor_object.__init__(self, "UPS", in_dict)
        if self.state & 128:
            self.set_warn("UPS not present")
        else:
            if self.state & 1:
                self.set_error("UPS malfunction")
            if self.state & 2:
                self.set_error("AC Power not present")
            if self.state & 64:
                self.set_warn("UPS is off")
        # check load state
        load_state = (self.state >> 2) & 7
        if load_state == 1:
            self.set_warn("not fully charged")
        elif load_state == 2:
            self.set_error("charge critically low")
        elif load_state == 3:
            self.set_error("completely drained")

    def __del__(self):
        eonstor_object.__del__(self)

    def __repr__(self):
        return "UPS %s, state 0x%x (%d, %s)" % (
            self.name,
            self.state,
            self.nag_state,
            self.get_state_str())


class eonstor_fan(eonstor_object):
    def __init__(self, in_dict):
        eonstor_object.__init__(self, "Fan", in_dict)
        if self.state & 1:
            self.set_error("Fan malfunction")
        if self.state & 64:
            self.set_warn("Fan is OFF")
        if self.state & 128:
            self.set_warn("Fan not present")
        if not self.state:
            self.out_string = "%.2f RPM" % (float(in_dict[9]) / 1000)

    def __del__(self):
        eonstor_object.__del__(self)

    def __repr__(self):
        return "fan %s, state 0x%x (%d, %s), %s" % (
            self.name,
            self.state,
            self.nag_state,
            self.get_state_str(),
            self.out_string)


class eonstor_temperature(eonstor_object):
    def __init__(self, in_dict, net_obj):
        eonstor_object.__init__(self, "temp", in_dict)
        if self.state & 1:
            self.set_error("Sensor malfunction")
        if self.state & 64:
            self.set_warn("Sensor not active")
        if self.state & 128:
            self.set_warn("Sensor not present")
        # check threshold
        sensor_th = (self.state >> 1) & 7
        if sensor_th in [2, 3]:
            self.set_warn("Sensor %s warning" % (
                {
                    2: "cold",
                    3: "hot"
                }[sensor_th]))
        elif sensor_th in [4, 5]:
            self.set_error("Sensor %s limit exceeded" % (
                {
                    4: "cold",
                    5: "hot"
                }[sensor_th]))
        if not self.state and int(in_dict[9]):
            if net_obj.eonstor_version == 2:
                self.out_string = "%.2f C" % (float(in_dict[9]) * float(in_dict[10]) / 1000 - 273)
            else:
                self.out_string = "%.2f C" % (float(in_dict[9]) / 1000000)

    def __del__(self):
        eonstor_object.__del__(self)

    def __repr__(self):
        return "temperature %s, state 0x%x (%d, %s), %s" % (
            self.name,
            self.state,
            self.nag_state,
            self.get_state_str(),
            self.out_string)


class eonstor_voltage(eonstor_object):
    def __init__(self, in_dict):
        eonstor_object.__init__(self, "Voltage", in_dict)
        if self.state & 1:
            self.set_error("Sensor malfunction")
        if self.state & 64:
            self.set_warn("Sensor not active")
        if self.state & 128:
            self.set_warn("Sensor not present")
        # check threshold
        sensor_th = (self.state >> 1) & 7
        if sensor_th in [2, 3]:
            self.set_warn("Sensor %s warning" % (
                {
                    2: "low",
                    3: "high"
                }[sensor_th]))
        elif sensor_th in [4, 5]:
            self.set_error("Sensor %s limit exceeded" % (
                {
                    4: "low",
                    5: "high"
                }[sensor_th]))
        if not self.state:
            self.out_string = "%.2f V" % (float(in_dict[9]) / 1000)

    def __del__(self):
        eonstor_object.__del__(self)

    def __repr__(self):
        return "voltage %s, state 0x%x (%d, %s), %s" % (
            self.name,
            self.state,
            self.nag_state,
            self.get_state_str(),
            self.out_string)


class eonstor_info_scheme(snmp_scheme):
    def __init__(self, **kwargs):
        snmp_scheme.__init__(self, "eonstor_info", **kwargs)
        if "net_obj" in kwargs:
            net_obj = kwargs["net_obj"]
            if not hasattr(net_obj, "eonstor_version"):
                net_obj.eonstor_version = 2
            _vers = net_obj.eonstor_version
        else:
            _vers = 2
        if _vers == 1:
            self.__th_system = snmp_oid(
                (1, 3, 6, 1, 4, 1, 1714, 1, 9, 1), cache=True, cache_timeout=EONSTOR_TIMEOUT
            )
            self.__th_disc = snmp_oid(
                (1, 3, 6, 1, 4, 1, 1714, 1, 6, 1), cache=True, cache_timeout=EONSTOR_TIMEOUT
            )
        else:
            self.__th_system = snmp_oid(
                (1, 3, 6, 1, 4, 1, 1714, 1, 1, 9, 1), cache=True, cache_timeout=EONSTOR_TIMEOUT
            )
            self.__th_disc = snmp_oid(
                (1, 3, 6, 1, 4, 1, 1714, 1, 1, 6, 1),
                cache=True,
                cache_timeout=EONSTOR_TIMEOUT,
                max_oid=(1, 3, 6, 1, 4, 1, 1714, 1, 1, 6, 1, 20)
            )
        self.requests = [
            self.__th_system,
            self.__th_disc
        ]

    def error(self):
        if len(self.get_missing_headers()) == 2:
            # change eonstor version
            self.net_obj.eonstor_version = 3 - self.net_obj.eonstor_version

    def process_return(self):
        # device dict (also for discs)
        dev_dict = {}
        for dev_idx, dev_stuff in self._reorder_dict(self.snmp_dict[tuple(self.__th_system)]).iteritems():
            if dev_stuff[6] == 17:
                # slot
                dev_dict[dev_idx] = eonstor_slot(dev_stuff)
            elif dev_stuff[6] == 2:
                # fan
                dev_dict[dev_idx] = eonstor_fan(dev_stuff)
            elif dev_stuff[6] == 3:
                # temperature
                dev_dict[dev_idx] = eonstor_temperature(dev_stuff, self.net_obj)
            elif dev_stuff[6] == 1:
                # power supply
                dev_dict[dev_idx] = eonstor_psu(dev_stuff)
            elif dev_stuff[6] == 11:
                # battery backup unit
                dev_dict[dev_idx] = eonstor_bbu(dev_stuff)
            elif dev_stuff[6] == 4:
                # UPS
                dev_dict[dev_idx] = eonstor_ups(dev_stuff)
            elif dev_stuff[6] == 5:
                # voltage
                dev_dict[dev_idx] = eonstor_voltage(dev_stuff)
        for disc_idx, disc_stuff in self._reorder_dict(self.snmp_dict[tuple(self.__th_disc)]).iteritems():
            dev_dict["d{:d}".format(disc_idx)] = eonstor_disc(disc_stuff)
        ret_state, ret_field = (limits.nag_STATE_OK, [])
        for key in sorted(dev_dict.keys()):
            value = dev_dict[key]
            if value.nag_state:
                # only show errors and warnings
                ret_state = max(ret_state, value.nag_state)
                ret_field.append(value.get_ret_str())
        ret_field.sort()
        return ret_state, "; ".join(ret_field) or "no errors or warnings"


class eonstor_proto_scheme(snmp_scheme):
    def __init__(self, name, **kwargs):
        snmp_scheme.__init__(self, name, **kwargs)
        if "net_obj" in kwargs:
            net_obj = kwargs["net_obj"]
            if not hasattr(net_obj, "eonstor_version"):
                net_obj.eonstor_version = 1
            eonstor_version = getattr(net_obj, "eonstor_version", 1)
        else:
            eonstor_version = 2
        if eonstor_version == 1:
            self.sys_oid = (1, 3, 6, 1, 4, 1, 1714, 1, 9, 1)
            self.disc_oid = (1, 3, 6, 1, 4, 1, 1714, 1, 6, 1)
            self.max_disc_oid = None
            self.ld_oid = (1, 3, 6, 1, 4, 1, 1714, 1, 2, 1)
        else:
            self.sys_oid = (1, 3, 6, 1, 4, 1, 1714, 1, 1, 9, 1)
            self.disc_oid = (1, 3, 6, 1, 4, 1, 1714, 1, 1, 6, 1)
            self.max_disc_oid = (1, 3, 6, 1, 4, 1, 1714, 1, 1, 6, 1, 20)
            self.ld_oid = (1, 3, 6, 1, 4, 1, 1714, 1, 1, 2, 1)
        if kwargs.get("ld_table", False):
            self.requests = snmp_oid(self.ld_oid, cache=True, cache_timeout=EONSTOR_TIMEOUT)
        if kwargs.get("disc_table", False):
            self.requests = snmp_oid(self.disc_oid, cache=True, cache_timeout=EONSTOR_TIMEOUT, max_oid=self.max_disc_oid)
        if kwargs.get("sys_table", False):
            self.requests = snmp_oid(self.sys_oid, cache=True, cache_timeout=EONSTOR_TIMEOUT)

    def error(self):
        if len(self.get_missing_headers()) == len(self.requests):
            # change eonstor version
            self.net_obj.eonstor_version = 3 - self.net_obj.eonstor_version

    def process_return(self):
        # reorder the snmp-dict
        pre_dict = self._reorder_dict(self.snmp_dict[tuple(self.requests[0])])
        return self._generate_return(self.handle_dict(pre_dict))

    def _generate_return(self, dev_dict):
        if "iarg" in self.opts:
            dev_idx = self.opts.iarg
        else:
            dev_idx = 0
        ret_state, ret_field = (limits.nag_STATE_OK, [])
        raw_dict = {}
        if dev_idx:
            if dev_idx in dev_dict:
                if self.xml_input:
                    raw_dict = {"state": dev_dict[dev_idx].state}
                else:
                    value = dev_dict[dev_idx]
                    ret_state = value.nag_state
                    ret_field.append(value.get_ret_str(long_format=True) or "%s is OK" % (value.name))
            else:
                ret_state = limits.nag_STATE_CRITICAL
                ret_field.append("idx %d not found in dict (possible values: %s)" % (
                    dev_idx,
                    ", ".join(["%d" % (key) for key in sorted(dev_dict.keys())])))
        else:
            for key in sorted(dev_dict.keys()):
                value = dev_dict[key]
                ret_state = max(ret_state, value.nag_state)
                act_ret_str = value.get_ret_str() or "%s is OK" % (value.name)
                ret_field.append(act_ret_str)
            ret_field.sort()
        if self.xml_input:
            self.srv_com["eonstor_info"] = raw_dict
            return limits.nag_STATE_OK, "ok got info"
        else:
            return ret_state, "; ".join(ret_field) or "no errors or warnings"


class eonstor_ld_info_scheme(eonstor_proto_scheme):
    def __init__(self, **kwargs):
        eonstor_proto_scheme.__init__(self, "eonstor_ld_info", ld_table=True, **kwargs)
        self.parse_options(kwargs["options"], one_integer_arg_allowed=True)

    def handle_dict(self, pre_dict):
        return {dev_idx: eonstor_ld(dev_stuff) for dev_idx, dev_stuff in pre_dict.iteritems()}


class eonstor_fan_info_scheme(eonstor_proto_scheme):
    def __init__(self, **kwargs):
        eonstor_proto_scheme.__init__(self, "eonstor_fan_info", sys_table=True, **kwargs)
        self.parse_options(kwargs["options"], one_integer_arg_allowed=True)

    def handle_dict(self, pre_dict):
        return {dev_idx: eonstor_fan(dev_stuff) for dev_idx, dev_stuff in pre_dict.iteritems() if dev_stuff[6] == 2}


class eonstor_temperature_info_scheme(eonstor_proto_scheme):
    def __init__(self, **kwargs):
        eonstor_proto_scheme.__init__(self, "eonstor_temperature_info", sys_table=True, **kwargs)
        self.parse_options(kwargs["options"], one_integer_arg_allowed=True)

    def handle_dict(self, pre_dict):
        return {dev_idx: eonstor_temperature(dev_stuff, self.net_obj) for dev_idx, dev_stuff in pre_dict.iteritems() if dev_stuff[6] == 3}


class eonstor_ups_info_scheme(eonstor_proto_scheme):
    def __init__(self, **kwargs):
        eonstor_proto_scheme.__init__(self, "eonstor_ups_info", sys_table=True, **kwargs)
        self.parse_options(kwargs["options"], one_integer_arg_allowed=True)

    def handle_dict(self, pre_dict):
        return {dev_idx: eonstor_ups(dev_stuff) for dev_idx, dev_stuff in pre_dict.iteritems() if dev_stuff[6] == 4}


class eonstor_bbu_info_scheme(eonstor_proto_scheme):
    def __init__(self, **kwargs):
        eonstor_proto_scheme.__init__(self, "eonstor_bbu_info", sys_table=True, **kwargs)
        self.parse_options(kwargs["options"], one_integer_arg_allowed=True)

    def handle_dict(self, pre_dict):
        return {dev_idx: eonstor_bbu(dev_stuff) for dev_idx, dev_stuff in pre_dict.iteritems() if dev_stuff[6] == 11}


class eonstor_voltage_info_scheme(eonstor_proto_scheme):
    def __init__(self, **kwargs):
        eonstor_proto_scheme.__init__(self, "eonstor_voltage_info", sys_table=True, **kwargs)
        self.parse_options(kwargs["options"], one_integer_arg_allowed=True)

    def handle_dict(self, pre_dict):
        return {dev_idx: eonstor_voltage(dev_stuff) for dev_idx, dev_stuff in pre_dict.iteritems() if dev_stuff[6] == 5}


class eonstor_slot_info_scheme(eonstor_proto_scheme):
    def __init__(self, **kwargs):
        eonstor_proto_scheme.__init__(self, "eonstor_slot_info", sys_table=True, **kwargs)
        self.parse_options(kwargs["options"], one_integer_arg_allowed=True)

    def handle_dict(self, pre_dict):
        return {dev_idx: eonstor_slot(dev_stuff) for dev_idx, dev_stuff in pre_dict.iteritems() if dev_stuff[6] == 17}


class eonstor_disc_info_scheme(eonstor_proto_scheme):
    def __init__(self, **kwargs):
        eonstor_proto_scheme.__init__(self, "eonstor_disc_info", disc_table=True, **kwargs)
        self.parse_options(kwargs["options"], one_integer_arg_allowed=True)

    def handle_dict(self, pre_dict):
        return {dev_idx: eonstor_disc(dev_stuff) for dev_idx, dev_stuff in pre_dict.iteritems()}


class eonstor_psu_info_scheme(eonstor_proto_scheme):
    def __init__(self, **kwargs):
        eonstor_proto_scheme.__init__(self, "eonstor_psu_info", sys_table=True, **kwargs)
        self.parse_options(kwargs["options"], one_integer_arg_allowed=True)

    def handle_dict(self, pre_dict):
        return {dev_idx: eonstor_psu(dev_stuff) for dev_idx, dev_stuff in pre_dict.iteritems() if dev_stuff[6] == 1}


class eonstor_get_counter_scheme(eonstor_proto_scheme):
    def __init__(self, **kwargs):
        eonstor_proto_scheme.__init__(self, "eonstor_get_counter", sys_table=True, disc_table=True, ld_table=True, **kwargs)
        self.parse_options(kwargs["options"])

    def process_return(self):
        sys_dict, disc_dict = (
            self._reorder_dict(self.snmp_dict[self.sys_oid]),
            self._reorder_dict(self.snmp_dict[self.disc_oid])
        )
        # number of discs
        info_dict = {"disc_ids": disc_dict.keys()}
        for idx, value in sys_dict.iteritems():
            ent_name = {
                1: "psu",
                2: "fan",
                3: "temperature",
                4: "ups",
                5: "voltage",
                11: "bbu",
                17: "slot"
            }.get(value[6], None)
            if ent_name:
                info_dict.setdefault("ent_dict", {}).setdefault(ent_name, {})[idx] = value[8]
        info_dict["ld_ids"] = self._reorder_dict(self.snmp_dict[self.ld_oid]).keys()
        if self.xml_input:
            self.srv_com["eonstor_info"] = info_dict
            return limits.nag_STATE_OK, "ok got info"
        else:
            # FIXME
            return limits.nag_STATE_OK, process_tools.sys_to_net(info_dict)


class port_info_scheme(snmp_scheme):
    def __init__(self, **kwargs):
        snmp_scheme.__init__(self, "port_info", **kwargs)
        self.__th_mac = (1, 3, 6, 1, 2, 1, 17, 4, 3, 1, 2)
        self.__th_type = (1, 3, 6, 1, 2, 1, 17, 4, 3, 1, 3)
        self.requests = [
            snmp_oid(self.__th_mac, cache=True, cache_timeout=240),
            snmp_oid(self.__th_type, cache=True, cache_timeout=240)]
        self.parser.add_argument("--arg0", type=int, dest="p_num", help="port number [%(default)s]", default=0)
        self.parse_options(kwargs["options"])

    def _transform_macs(self, mac_list):
        arp_dict = process_tools.get_arp_dict()
        host_list, ip_list, new_mac_list = ([], [], [])
        for mac in mac_list:
            if mac in arp_dict:
                try:
                    host = socket.gethostbyaddr(arp_dict[mac])
                except:
                    ip_list.append(arp_dict[mac])
                else:
                    host_list.append(host[0])
            else:
                new_mac_list.append(mac)
        return sorted(new_mac_list), sorted(ip_list), sorted(host_list)

    def process_return(self):
        s_mac_dict = self._simplify_keys(self.snmp_dict[self.__th_mac])
        s_type_dict = self._simplify_keys(self.snmp_dict[self.__th_type])
        p_num = self.opts.p_num
        port_ref_dict = {}
        for key, value in s_mac_dict.iteritems():
            mac = ":".join(["%02x" % (int(val)) for val in key])
            port_ref_dict.setdefault(value, []).append((mac, int(s_type_dict.get(key, 5))))
        macs = [mac for mac, p_type in port_ref_dict.get(p_num, []) if p_type == 3]
        if macs:
            mac_list, ip_list, host_list = self._transform_macs(macs)
            return limits.nag_STATE_OK, "port %d (%s): %s" % (
                p_num,
                ", ".join([logging_tools.get_plural(name, len(what_list)) for name, what_list in [
                    ("Host", host_list),
                    ("IP", ip_list),
                    ("MAC", mac_list)] if len(what_list)]),
                ", ".join(host_list + ip_list + mac_list))
        else:
            return limits.nag_STATE_OK, "port %d: ---" % (p_num)


class trunk_info_scheme(snmp_scheme):
    def __init__(self, **kwargs):
        snmp_scheme.__init__(self, "trunk_info", **kwargs)
        self.requests = snmp_oid("1.0.8802.1.1.2.1.4.1.1", cache=True)

    def process_return(self):
        simple_dict = self._simplify_keys(self.snmp_dict.values()[0])
        trunk_dict = {}
        for key, value in simple_dict.iteritems():
            sub_idx, trunk_id, port_num, _idx = key
            trunk_dict.setdefault(trunk_id, {}).setdefault(port_num, {})[sub_idx] = value
        t_array = []
        for t_key in sorted(trunk_dict.keys()):
            t_stuff = trunk_dict[t_key]
            t_ports = sorted(t_stuff.keys())
            try:
                port_map = {port: int(t_stuff[port][7]) for port in t_ports}
            except:
                t_array.append("error decoding port_num: %s" % (process_tools.get_except_info()))
            else:
                dest_name = t_stuff[t_ports[0]][9]
                dest_hw = t_stuff[t_ports[0]][10]
                t_array.append("%s [%s]: %s to %s (%s)" % (
                    logging_tools.get_plural("port", len(t_ports)),
                    str(t_key),
                    "/".join(["%d-%d" % (port, port_map[port]) for port in t_ports]),
                    dest_name,
                    dest_hw))
        if t_array:
            return limits.nag_STATE_OK, "%s: %s" % (
                logging_tools.get_plural("trunk", len(t_array)),
                ", ".join(t_array))
        else:
            limits.nag_STATE_OK, "no trunks"


class apc_rpdu_load_scheme(snmp_scheme):
    def __init__(self, **kwargs):
        snmp_scheme.__init__(self, "apc_rpdu_load", **kwargs)
        # T for table, G for get
        self.requests = snmp_oid("1.3.6.1.4.1.318.1.1.12.2.3.1.1")

    def process_return(self):
        simple_dict = self._simplify_keys(self.snmp_dict.values()[0])
        p_idx = 1
        act_load = simple_dict[(2, p_idx)]
        act_state = simple_dict[(3, p_idx)]
        ret_state = {
            1: limits.nag_STATE_OK,
            2: limits.nag_STATE_OK,
            3: limits.nag_STATE_WARNING,
            4:  limits.nag_STATE_CRITICAL
        }[act_state]
        return ret_state, "load is %.2f Ampere" % (float(act_load) / 10.)


class usv_apc_load_scheme(snmp_scheme):
    def __init__(self, **kwargs):
        snmp_scheme.__init__(self, "usv_apc_load", **kwargs)
        self.requests = snmp_oid((1, 3, 6, 1, 4, 1, 318, 1, 1, 1, 4, 2), cache=True)

    def process_return(self):
        WARN_LOAD, CRIT_LOAD = (70, 85)
        use_dict = self._simplify_keys(self.snmp_dict.values()[0])
        try:
            act_load = use_dict[(3, 0)]
        except KeyError:
            return limits.nag_STATE_CRITICAL, "error getting load"
        else:
            ret_state, prob_f = (limits.nag_STATE_OK, [])
            if act_load > CRIT_LOAD:
                ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                prob_f.append("load is very high (> %d)" % (CRIT_LOAD))
            elif act_load > WARN_LOAD:
                ret_state = max(ret_state, limits.nag_STATE_WARNING)
                prob_f.append("load is high (> %d)" % (WARN_LOAD))
            return ret_state, "load is %d %%%s" % (
                act_load,
                ": %s" % ("; ".join(prob_f)) if prob_f else "")


class usv_apc_output_scheme(snmp_scheme):
    def __init__(self, **kwargs):
        snmp_scheme.__init__(self, "usv_apc_output", **kwargs)
        self.requests = snmp_oid((1, 3, 6, 1, 4, 1, 318, 1, 1, 1, 4, 2), cache=True)

    def process_return(self):
        MIN_HZ, MAX_HZ = (49, 52)
        MIN_VOLT, MAX_VOLT = (219, 235)
        out_dict = self._simplify_keys(self.snmp_dict.values()[0])
        out_freq, out_voltage = (out_dict[(2, 0)],
                                 out_dict[(1, 0)])
        ret_state, prob_f = (limits.nag_STATE_OK, [])
        if out_freq not in xrange(MIN_HZ, MAX_HZ):
            ret_state = max(ret_state, limits.nag_STATE_WARNING)
            prob_f.append("output frequency not ok [%d, %d]" % (
                MIN_HZ,
                MAX_HZ))
        if out_voltage not in xrange(MIN_VOLT, MAX_VOLT):
            ret_state = max(ret_state, limits.nag_STATE_WARNING)
            prob_f.append("output voltage is not in range [%d, %d]" % (
                MIN_VOLT,
                MAX_VOLT))
        return ret_state, "output is %d V at %d Hz%s" % (
            out_voltage,
            out_freq,
            ": %s" % ("; ".join(prob_f)) if prob_f else "")


class usv_apc_input_scheme(snmp_scheme):
    def __init__(self, **kwargs):
        snmp_scheme.__init__(self, "usv_apc_input", **kwargs)
        self.requests = snmp_oid((1, 3, 6, 1, 4, 1, 318, 1, 1, 1, 3, 2), cache=True)

    def process_return(self):
        MIN_HZ, MAX_HZ = (49, 52)
        MIN_VOLT, MAX_VOLT = (216, 235)
        in_dict = self._simplify_keys(self.snmp_dict.values()[0])
        in_freq, in_voltage = (int(in_dict[(4, 0)]),
                               int(in_dict[(1, 0)]))
        ret_state, prob_f = (limits.nag_STATE_OK, [])
        if in_freq not in xrange(MIN_HZ, MAX_HZ):
            ret_state = max(ret_state, limits.nag_STATE_WARNING)
            prob_f.append("input frequency not ok [%d, %d]" % (
                MIN_HZ,
                MAX_HZ))
        if in_voltage not in xrange(MIN_VOLT, MAX_VOLT):
            ret_state = max(ret_state, limits.nag_STATE_WARNING)
            prob_f.append("input voltage is not in range [%d, %d]" % (
                MIN_VOLT,
                MAX_VOLT))
        return ret_state, "input is %d V at %d Hz%s" % (
            in_voltage,
            in_freq,
            ": %s" % ("; ".join(prob_f)) if prob_f else ""
        )


class usv_apc_battery_scheme(snmp_scheme):
    def __init__(self, **kwargs):
        snmp_scheme.__init__(self, "usv_apc_battery", **kwargs)
        self.requests = snmp_oid((1, 3, 6, 1, 4, 1, 318, 1, 1, 1, 2, 2), cache=True)
        self.parser.add_argument("-w", type=float, dest="warn", help="warning value [%(default)s]", default=35.0)
        self.parser.add_argument("-c", type=float, dest="crit", help="critical value [%(default)s]", default=40.0)
        self.parse_options(kwargs["options"])

    def process_return(self):
        warn_temp = int(self.opts.warn)
        crit_temp = int(self.opts.crit)
        warn_bat_load, crit_bat_load = (90, 50)
        bat_dict = self._simplify_keys(self.snmp_dict.values()[0])
        need_replacement, run_time, act_temp, act_bat_load = (
            int(bat_dict[(4, 0)]),
            int(bat_dict[(3, 0)]),
            int(bat_dict[(2, 0)]),
            int(bat_dict[(1, 0)]))
        ret_state, prob_f = (limits.nag_STATE_OK, [])
        if need_replacement > 1:
            ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
            prob_f.append("battery needs replacing")
        if act_temp > crit_temp:
            ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
            prob_f.append("temperature is very high (th %d)" % (crit_temp))
        elif act_temp > warn_temp:
            ret_state = max(ret_state, limits.nag_STATE_WARNING)
            prob_f.append("temperature is high (th %d)" % (warn_temp))
        if act_bat_load < crit_bat_load:
            ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
            prob_f.append("very low load (th %d)" % (crit_bat_load))
        elif act_bat_load < warn_bat_load:
            ret_state = max(ret_state, limits.nag_STATE_WARNING)
            prob_f.append("not fully loaded (th %d)" % (warn_bat_load))
        # run time in seconds
        run_time = run_time / 100.
        if run_time < 5 * 60:
            ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
            prob_f.append("run time below 5 minutes")
        elif run_time < 10 * 60:
            ret_state = max(ret_state, limits.nag_STATE_WARNING)
            prob_f.append("run time below 10 minutes")
        return ret_state, "bat temperature is %d C, bat load is %d %%, support time is %s %s%s" % (
            act_temp,
            act_bat_load,
            logging_tools.get_plural("min", int(run_time / 60)),
            logging_tools.get_plural("sec", int(run_time % 60)),
            ": %s" % ("; ".join(prob_f)) if prob_f else "")


class ibm_bc_blade_status_scheme(snmp_scheme):
    def __init__(self, **kwargs):
        snmp_scheme.__init__(self, "ibm_bc_blade_status", **kwargs)
        self.__blade_oids = {
            key: (1, 3, 6, 1, 4, 1, 2, 3, 51, 2, 22, 1, 5, 1, 1, idx + 1) for idx, key in enumerate(
                ["idx", "id", "exists", "power_state", "health_state", "name"]
            )
        }
        for value in self.__blade_oids.values():
            self.requests = snmp_oid(value, cache=True)
        self.parse_options(kwargs["options"])

    def process_return(self):
        all_blades = self.snmp_dict[self.__blade_oids["idx"]].values()
        ret_state, state_dict = (limits.nag_STATE_OK, {})
        for blade_idx in all_blades:
            loc_dict = {
                t_name: self._simplify_keys(self.snmp_dict[self.__blade_oids[t_name]])[blade_idx] for t_name in [
                    "exists", "power_state", "health_state", "name"
                ]
            }
            loc_state = limits.nag_STATE_OK
            if loc_dict["exists"]:
                if loc_dict["power_state"]:
                    loc_state = max(loc_state, {
                        0: limits.nag_STATE_UNKNOWN,
                        1: limits.nag_STATE_OK,
                        2: limits.nag_STATE_WARNING,
                        3: limits.nag_STATE_CRITICAL,
                    }.get(loc_dict["health_state"], limits.nag_STATE_CRITICAL))
                    loc_str = {
                        0: "unknown",
                        1: "good",
                        2: "warning",
                        3: "bad"
                    }.get(loc_dict["health_state"], "???")
                else:
                    loc_str = "off"
            else:
                loc_str = "N/A"
            ret_state = max(ret_state, loc_state)
            state_dict.setdefault(loc_str, []).append(loc_dict["name"])
        return ret_state, "%s, %s" % (
            logging_tools.get_plural("blade", len(all_blades)),
            "; ".join(["%s: %s" % (key, ", ".join(value)) for key, value in state_dict.iteritems()]))


class ibm_bc_storage_status_scheme(snmp_scheme):
    def __init__(self, **kwargs):
        snmp_scheme.__init__(self, "ibm_bc_storage_status", **kwargs)
        self.__blade_oids = {
            key: (1, 3, 6, 1, 4, 1, 2, 3, 51, 2, 22, 6, 1, 1, 1, idx + 1) for idx, key in enumerate(
                ["idx", "module", "status", "name"]
            )
        }
        for value in self.__blade_oids.values():
            self.requests = snmp_oid(value, cache=True)
        self.parse_options(kwargs["options"])

    def process_return(self):
        store_dict = {}
        for key, value in self.__blade_oids.iteritems():
            for s_key, s_value in self._simplify_keys(self.snmp_dict[value]).iteritems():
                if key in ["module"]:
                    s_value = int(s_value)
                store_dict.setdefault(s_key, {})[key] = s_value
        ret_state, state_dict = (limits.nag_STATE_OK, {})
        for idx in sorted(store_dict):
            loc_dict = store_dict[idx]
            if loc_dict["status"] != 1:
                loc_state, state_str = (limits.nag_STATE_CRITICAL, "problem")
            else:
                loc_state, state_str = (limits.nag_STATE_OK, "good")
            state_dict.setdefault(state_str, []).append(loc_dict["name"])
            ret_state = max(ret_state, loc_state)
        return ret_state, "%s, %s" % (
            logging_tools.get_plural("item", len(store_dict)),
            "; ".join(
                [
                    "%s: %s" % (key, ", ".join(value)) for key, value in state_dict.iteritems()
                ]
            )
        )


class temperature_probe_scheme(snmp_scheme):
    def __init__(self, **kwargs):
        snmp_scheme.__init__(self, "temperature_probe_scheme", **kwargs)
        self.requests = snmp_oid((1, 3, 6, 1, 4, 1, 22626, 1, 2, 1, 1), cache=True)
        self.parser.add_argument("-w", type=float, dest="warn", help="warning value [%(default)s]", default=35.0)
        self.parser.add_argument("-c", type=float, dest="crit", help="critical value [%(default)s]", default=40.0)
        self.parse_options(kwargs["options"])

    def process_return(self):
        warn_temp = int(self.opts.warn)
        crit_temp = int(self.opts.crit)
        use_dict = self._simplify_keys(self.snmp_dict.values()[0])
        cur_temp = float(use_dict.values()[0])
        if cur_temp > crit_temp:
            cur_state = limits.nag_STATE_CRITICAL
        elif cur_temp > warn_temp:
            cur_state = limits.nag_STATE_WARNING
        else:
            cur_state = limits.nag_STATE_OK
        return cur_state, "temperature %.2f C | temp=%.2f" % (
            cur_temp,
            cur_temp
        )


class temperature_probe_hum_scheme(snmp_scheme):
    def __init__(self, **kwargs):
        snmp_scheme.__init__(self, "temperature_probe_hum_scheme", **kwargs)
        self.requests = snmp_oid((1, 3, 6, 1, 4, 1, 22626, 1, 2, 1, 2), cache=True)
        self.parser.add_argument("-w", type=float, dest="warn", help="warning value [%(default)s]", default=80.0)
        self.parser.add_argument("-c", type=float, dest="crit", help="critical value [%(default)s]", default=95.0)
        self.parse_options(kwargs["options"])

    def process_return(self):
        warn_hum = int(self.opts.warn)
        crit_hum = int(self.opts.crit)
        use_dict = self._simplify_keys(self.snmp_dict.values()[0])
        cur_hum = float(use_dict.values()[0])
        if cur_hum > crit_hum:
            cur_state = limits.nag_STATE_CRITICAL
        elif cur_hum > warn_hum:
            cur_state = limits.nag_STATE_WARNING
        else:
            cur_state = limits.nag_STATE_OK
        return cur_state, "humidity %.2f %% | hum=%.2f%%" % (
            cur_hum,
            cur_hum
        )


class temperature_knurr_scheme(snmp_scheme):
    def __init__(self, **kwargs):
        snmp_scheme.__init__(self, "temperature_knurr_scheme", **kwargs)
        self.parser.add_argument(
            "--type",
            type="choice",
            dest="sensor_type",
            choices=["outlet", "inlet"],
            help="temperature probe [%(default)s]",
            default="outlet"
        )
        self.requests = snmp_oid((1, 3, 6, 1, 4, 1, 2769, 2, 1, 1), cache=True, cache_timeout=10)
        self.parse_options(kwargs["options"])

    def process_return(self):
        sensor_type = self.opts.sensor_type
        lut_id = {
            "outlet": 1,
            "inlet": 2
        }[sensor_type]
        new_dict = self._simplify_keys(
            {key[1]: float(value) / 10. for key, value in self.snmp_dict.values()[0].iteritems() if key[0] == lut_id}
        )
        warn_val, crit_val = (new_dict[5], new_dict[6])
        cur_val = new_dict[3]
        if cur_val > crit_val:
            cur_state = limits.nag_STATE_CRITICAL
        elif cur_val > warn_val:
            cur_state = limits.nag_STATE_WARNING
        else:
            cur_state = limits.nag_STATE_OK
        return cur_state, "temperature %.2f C | temp=%.2f" % (
            cur_val,
            cur_val
        )


class humidity_knurr_scheme(snmp_scheme):
    def __init__(self, **kwargs):
        snmp_scheme.__init__(self, "humidity_knurr_scheme", **kwargs)
        self.requests = snmp_oid((1, 3, 6, 1, 4, 1, 2769, 2, 1, 1, 7), cache=True, cache_timeout=10)
        self.parse_options(kwargs["options"])

    def process_return(self):
        new_dict = self._simplify_keys(
            {key[0]: float(value) / 10. for key, value in self.snmp_dict.values()[0].iteritems()}
        )
        low_crit, high_crit = (new_dict[3], new_dict[4])
        cur_val = new_dict[2]
        if cur_val > high_crit or cur_val < low_crit:
            cur_state = limits.nag_STATE_CRITICAL
        else:
            cur_state = limits.nag_STATE_OK
        return cur_state, "humidity %.2f %% [%.2f - %.2f] | humidity=%.2f" % (
            cur_val,
            low_crit,
            high_crit,
            cur_val)


class environment_knurr_scheme(snmp_scheme):
    def __init__(self, **kwargs):
        snmp_scheme.__init__(self, "environment_knurr_scheme", **kwargs)
        self.requests = snmp_oid((1, 3, 6, 1, 4, 1, 2769, 2, 1, 2, 4), cache=True, cache_timeout=10)
        self.parse_options(kwargs["options"])

    def process_return(self):
        new_dict = self._simplify_keys(
            {
                key[0]: int(value) for key, value in self.snmp_dict.values()[0].iteritems()
            }
        )
        del new_dict[4]
        if max(new_dict.values()) == 0:
            cur_state = limits.nag_STATE_OK
        else:
            cur_state = limits.nag_STATE_CRITICAL
        info_dict = {
            1: "fan1",
            2: "fan2",
            3: "fan3",
            5: "water",
            6: "smoke",
            7: "PSA",
            8: "PSB",
        }
        return cur_state, ", ".join(
            [
                "{}: {}".format(info_dict[key], {0: "OK", 1: "failed"}[new_dict[key]]) for key in sorted(new_dict.keys())
            ]
        )


class SNMPGenScheme(snmp_scheme):
    def __init__(self, **kwargs):
        self.handler = kwargs.pop("handler")
        snmp_scheme.__init__(self, self.handler.Meta.name, **kwargs)
        self.handler.parser_setup(self.parser)
        self.parse_options(kwargs["options"])
        if not self.get_errors():
            self.requests = self.handler.mon_start(self)

    def process_return(self):
        return self.handler.mon_result(self)


# new version of Emerson/Knuerr CoolCon rack (APP 1.15.10, HMI 1.15.10)
class environment2_knurr_scheme(snmp_scheme):
    def __init__(self, **kwargs):
        snmp_scheme.__init__(self, "environment2_knurr_scheme", **kwargs)
        self.requests = snmp_oid((1, 3, 6, 1, 4, 1, 2769, 2, 1, 9, 1), cache=True, cache_timeout=10)
        self.parse_options(kwargs["options"])

    def process_return(self):
        new_dict = self._simplify_keys(dict([(key[0], int(value)) for key, value in self.snmp_dict.values()[0].iteritems()]))
        del new_dict[4]
        if max(new_dict.values()) == 0:
            cur_state = limits.nag_STATE_OK
        else:
            cur_state = limits.nag_STATE_CRITICAL
        info_dict = {
            1: "fan1",
            2: "fan2",
            3: "fan3",
            5: "water",
            6: "smoke",
            7: "PSA",
            8: "PSB",
        }
        return cur_state, ", ".join(
            [
                "%s: %s" % (info_dict[key], {0: "OK", 1: "failed"}[new_dict[key]]) for key in sorted(info_dict.keys())
            ]
        )


# US version of Emerson/Liebert MPH Rack 3-Phase PDU
class current_pdu_emerson_scheme(snmp_scheme):
    def __init__(self, **kwargs):
        snmp_scheme.__init__(self, "current_pdu_emerson_scheme", **kwargs)
        self.requests = snmp_oid((1, 3, 6, 1, 4, 1, 476, 1, 42, 3, 8, 30, 40, 1, 22, 1, 1), cache=True, cache_timeout=10)
        self.parse_options(kwargs["options"])

    def process_return(self):
        new_dict = self._simplify_keys(dict([(key[0], int(value)) for key, value in self.snmp_dict.values()[0].iteritems()]))

        cur_state = limits.nag_STATE_OK

        info_dict = {
            1: "L1",
            2: "L2",
            3: "L3",
        }
        return cur_state, ", ".join(
            [
                "%s: %sA" % (info_dict[key], float(new_dict[key]) * 0.01) for key in sorted(info_dict.keys())
            ]
        )


class currentLLG_pdu_emerson_scheme(snmp_scheme):
    def __init__(self, **kwargs):
        snmp_scheme.__init__(self, "currentLLG_pdu_emerson_scheme", **kwargs)
        self.requests = snmp_oid((1, 3, 6, 1, 4, 1, 476, 1, 42, 3, 8, 40, 20, 1, 130, 1), cache=True, cache_timeout=10)
        self.parse_options(kwargs["options"])

    def process_return(self):
        new_dict = self._simplify_keys(dict([(key[0], int(value)) for key, value in self.snmp_dict.values()[0].iteritems()]))

        cur_state = limits.nag_STATE_OK

        info_dict = {
            1: "L1-L2",
            2: "L1-L2",
            3: "L2-L3",
            4: "L2-L3",
            5: "L3-L1",
            6: "L3-L1",
        }
        return cur_state, ", ".join(
            [
                "%s: %sA" % (info_dict[key], float(new_dict[key]) * 0.01) for key in sorted(info_dict.keys())
            ]
        )


class voltageLL_pdu_emerson_scheme(snmp_scheme):
    def __init__(self, **kwargs):
        snmp_scheme.__init__(self, "voltageLL_pdu_emerson_scheme", **kwargs)
        self.requests = snmp_oid((1, 3, 6, 1, 4, 1, 476, 1, 42, 3, 8, 30, 40, 1, 61, 1, 1), cache=True, cache_timeout=10)
        self.parse_options(kwargs["options"])

    def process_return(self):
        new_dict = self._simplify_keys(dict([(key[0], int(value)) for key, value in self.snmp_dict.values()[0].iteritems()]))

        cur_state = limits.nag_STATE_OK

        info_dict = {
            1: "L1-L2",
            2: "L2-L3",
            3: "L3-L1",
        }
        return cur_state, ", ".join(
            [
                "%s: %sV" % (info_dict[key], float(new_dict[key]) * 0.1) for key in sorted(info_dict.keys())
            ]
        )
