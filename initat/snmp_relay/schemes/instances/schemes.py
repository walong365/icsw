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

import socket

from initat.host_monitoring import limits
from initat.snmp.snmp_struct import snmp_oid
from initat.tools import logging_tools, process_tools

from ..base import SNMPRelayScheme
from ..functions import k_str


class load_scheme(SNMPRelayScheme):
    def __init__(self, **kwargs):
        SNMPRelayScheme.__init__(self, "load", **kwargs)
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


class MemoryMixin(object):
    def show_memory(self, **kwargs):
        phys_total = kwargs["phys_total"]
        phys_used = kwargs["phys_used"]
        swap_total = kwargs["swap_total"]
        swap_used = kwargs["swap_used"]
        all_used = phys_used + swap_used
        phys_free, swap_free = (
            phys_total - phys_used,
            swap_total - swap_used
        )
        all_total, _all_free = (
            phys_total + swap_total,
            phys_free + swap_free
        )
        if phys_total == 0:
            memp = 100
        else:
            memp = 100. * phys_used / phys_total
        if all_total == 0:
            allp = 100
        else:
            allp = 100. * all_used / all_total
        ret_state = limits.nag_STATE_OK
        return ret_state, "meminfo: {:.2f} % of {} phys, {:.2f} % of {} tot".format(
            memp,
            k_str(phys_total),
            allp,
            k_str(all_total)
        )


class ucd_memory_scheme(SNMPRelayScheme, MemoryMixin):
    def __init__(self, **kwargs):
        SNMPRelayScheme.__init__(self, "ucd_memory", **kwargs)
        # T for table, G for get
        self.requests = snmp_oid("1.3.6.1.4.1.2021.4", cache=True, cache_timeout=5)

    def process_return(self):
        use_dict = self._simplify_keys(self.snmp_dict.values()[0])
        swap_total, swap_avail = (
            use_dict[(3, 0)] * 1024,
            use_dict[(4, 0)] * 1024,
        )
        phys_total, phys_avail = (
            use_dict[(5, 0)] * 1024,
            use_dict[(6, 0)] * 1024,
        )
        return self.show_memory(
            phys_total=phys_total,
            phys_used=phys_total - phys_avail,
            swap_total=swap_total,
            swap_used=swap_total - swap_avail,
        )


class linux_memory_scheme(SNMPRelayScheme, MemoryMixin):
    def __init__(self, **kwargs):
        SNMPRelayScheme.__init__(self, "linux_memory", **kwargs)
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
        return self.show_memory(
            phys_total=use_dict["physical memory"]["size"],
            phys_used=use_dict["physical memory"]["used"],
            swap_total=use_dict["swap space"]["size"],
            swap_used=use_dict["swap space"]["used"],
        )


class snmp_info_scheme(SNMPRelayScheme):
    def __init__(self, **kwargs):
        SNMPRelayScheme.__init__(self, "snmp_info", **kwargs)
        # T for table, G for get
        self.requests = snmp_oid("1.3.6.1.2.1.1", cache=True)
        self.parse_options(kwargs["options"])

    def process_return(self):
        simple_dict = self.snmp_dict.values()[0]
        self._check_for_missing_keys(simple_dict, needed_keys={(4, 0), (5, 0), (6, 0)})
        ret_state = limits.nag_STATE_OK
        return ret_state, "SNMP Info: contact {}, name {}, location {}".format(
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


class check_snmp_qos_scheme(SNMPRelayScheme):
    def __init__(self, **kwargs):
        SNMPRelayScheme.__init__(self, "check_snmp_qos", **kwargs)
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


class port_info_scheme(SNMPRelayScheme):
    def __init__(self, **kwargs):
        SNMPRelayScheme.__init__(self, "port_info", **kwargs)
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
                ", ".join(
                    [
                        logging_tools.get_plural(name, len(what_list)) for name, what_list in [
                            ("Host", host_list),
                            ("IP", ip_list),
                            ("MAC", mac_list)
                        ] if len(what_list)
                    ]
                ),
                ", ".join(host_list + ip_list + mac_list)
            )
        else:
            return limits.nag_STATE_OK, "port %d: ---" % (p_num)


class trunk_info_scheme(SNMPRelayScheme):
    def __init__(self, **kwargs):
        SNMPRelayScheme.__init__(self, "trunk_info", **kwargs)
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
                t_array.append(
                    "%s [%s]: %s to %s (%s)" % (
                        logging_tools.get_plural("port", len(t_ports)),
                        str(t_key),
                        "/".join(["%d-%d" % (port, port_map[port]) for port in t_ports]),
                        dest_name,
                        dest_hw
                    )
                )
        if t_array:
            return limits.nag_STATE_OK, "%s: %s" % (
                logging_tools.get_plural("trunk", len(t_array)),
                ", ".join(t_array))
        else:
            return limits.nag_STATE_OK, "no trunks"


class ibm_bc_blade_status_scheme(SNMPRelayScheme):
    def __init__(self, **kwargs):
        SNMPRelayScheme.__init__(self, "ibm_bc_blade_status", **kwargs)
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


class ibm_bc_storage_status_scheme(SNMPRelayScheme):
    def __init__(self, **kwargs):
        SNMPRelayScheme.__init__(self, "ibm_bc_storage_status", **kwargs)
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


class temperature_probe_scheme(SNMPRelayScheme):
    def __init__(self, **kwargs):
        SNMPRelayScheme.__init__(self, "temperature_probe_scheme", **kwargs)
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


class temperature_probe_hum_scheme(SNMPRelayScheme):
    def __init__(self, **kwargs):
        SNMPRelayScheme.__init__(self, "temperature_probe_hum_scheme", **kwargs)
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
