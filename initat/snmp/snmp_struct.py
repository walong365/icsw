# Copyright (C) 2014-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of init-snmp-libs
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
""" basic structures """

import time

from initat.host_monitoring import limits
from initat.tools import ipvx_tools, server_command


class ResultNode(object):
    def __init__(self, **kwargs):
        for inst_name in ["ok", "warn", "error"]:
            _target = "{}_list".format(inst_name)
            _val = kwargs.get(inst_name, [])
            if _val is None:
                _val = []
            elif type(_val) != list:
                _val = [_val]
            setattr(self, _target, _val)

    def ok(self, in_val):
        self._add_val("ok", in_val)

    def warn(self, in_val):
        self._add_val("warn", in_val)

    def error(self, in_val):
        self._add_val("error", in_val)

    def _add_val(self, v_type, in_val):
        if type(in_val) != list:
            in_val = [in_val]
        _l_name = "{}_list".format(v_type)
        setattr(self, _l_name, getattr(self, _l_name) + in_val)

    def merge(self, other_node):
        self.ok_list.extend(other_node.ok_list)
        self.warn_list.extend(other_node.warn_list)
        self.error_list.extend(other_node.error_list)

    def __repr__(self):
        return "; ".join(
            [
                "{:d} {}: {}".format(
                    len(_val),
                    _val_name,
                    ", ".join(_val)
                ) for _val, _val_name in [
                    (self.ok_list, "ok"),
                    (self.warn_list, "warn"),
                    (self.error_list, "error"),
                ] if _val
            ]
        ) or "empty ResultNode"

    def get_srv_com_result(self):
        if self.error_list:
            _state = server_command.SRV_REPLY_STATE_ERROR
        elif self.warn_list:
            _state = server_command.SRV_REPLY_STATE_WARN
        else:
            _state = server_command.SRV_REPLY_STATE_OK
        return unicode(self), _state


class MonCheckDefinition(object):
    class Meta:
        name = "notset"
        meta = False
        is_active = True
        identifier = ""

    def __init__(self, handler):
        # copy keys when needed
        _keys = ["meta", "is_active", "name", "description", "info", "command_line", "identifier"]
        for _key in _keys:
            if not hasattr(self.Meta, _key) and hasattr(MonCheckDefinition.Meta, _key):
                # copy key from default Meta
                setattr(self.Meta, _key, getattr(MonCheckDefinition.Meta, _key))
            if not hasattr(self.Meta, _key):
                raise KeyError("key {} missing from SNMPHandler Meta {}".format(_key, str(self)))
        self.Meta.name = "{}-{}".format(handler.Meta.full_name, self.Meta.short_name)
        self._rewrite()

    def _rewrite(self):
        if self.Meta.command_line.startswith("*"):
            self.Meta.command_line = "$USER3$ -m $HOSTADDRESS$ -C ${{ARG1:SNMP_COMMUNITY:public}} -V ${{ARG2:SNMP_VERSION:2}} SS:{}{}".format(
                self.Meta.name,
                self.Meta.command_line[1:],
            )

    def config_call(self, s_com):
        return []

    def parser_setup(self, parser):
        pass

    def mon_start(self, scheme):
        return []

    def mon_result(self, scheme):
        return limits.nag_STATE_CRITICAL, "not implemented"

    def __repr__(self):
        return self.Meta.name


class snmp_if_counter(object):
    def __init__(self, octets, ucast_pkts, nucast_pkts, discards, errors):
        self.octets = octets
        self.ucast_pkts = ucast_pkts
        self.nucast_pkts = nucast_pkts
        self.discards = discards
        self.errors = errors


class snmp_if(object):
    def __init__(self, in_dict):
        self.idx = in_dict[1]
        self.name = in_dict[2]
        self.if_type = in_dict[3]
        self.mtu = in_dict[4]
        self.speed = in_dict[5]
        if 6 in in_dict:
            self.macaddr = ":".join(["{:02x}".format(ord(_val)) for _val in in_dict[6]])
        else:
            self.macaddr = ""
        self.admin_status = in_dict[7]
        self.oper_status = in_dict[8]
        self.last_change = in_dict[9]
        if 10 in in_dict:
            self.in_counter = snmp_if_counter(in_dict[10], in_dict[11], in_dict[12], in_dict[13], in_dict[14])
        else:
            self.in_counter = None
        if 16 in in_dict:
            self.out_counter = snmp_if_counter(in_dict[16], in_dict[17], in_dict[18], in_dict[19], in_dict[20])
        else:
            self.out_counter = None
        self.in_unknown_protos = in_dict[15]

    def __repr__(self):
        return "if {} ({:d}), MTU is {:d}, type is {:d}".format(
            self.name,
            self.idx,
            self.mtu,
            self.if_type
        )


class snmp_hs_counter(object):
    def __init__(self, multicast_pkts, broadcast_pkts, octets):
        self.multicast_pkts = multicast_pkts
        self.broadcast_pkts = broadcast_pkts
        self.octets = octets


class snmp_hs(object):
    # high speed counter
    def __init__(self, in_dict):
        self.name = in_dict[1]
        if 2 in in_dict:
            self.in_counter = snmp_hs_counter(in_dict[2], in_dict[3], in_dict.get(6, 0))
        else:
            self.in_counter = None
        if 4 in in_dict:
            self.out_counter = snmp_hs_counter(in_dict[4], in_dict[5], in_dict.get(10, 0))
        else:
            self.out_counter = None
        self.trap_enable = in_dict.get(14, 2) == 1
        self.highspeed = in_dict[15]
        self.promiscious_mode = in_dict[16] == 1
        self.connector_present = in_dict.get(17, 0) == 1
        self.alias = in_dict.get(18, "")
        self.counter_discontinuity_time = in_dict[19]

    def __repr__(self):
        return "hs {} ({}), {}".format(
            self.name,
            self.alias or "---",
            "connector present" if self.connector_present else "no connector present",
        )


class snmp_ip(object):
    def __init__(self, in_dict):
        self.address = ".".join(["{:d}".format(ord(_val)) for _val in in_dict[1]])
        self.netmask = ".".join(["{:d}".format(ord(_val)) for _val in in_dict[3]])
        self.address_ipv4 = ipvx_tools.ipv4(self.address)
        self.netmask_ipv4 = ipvx_tools.ipv4(self.netmask)
        self.if_idx = in_dict[2]

    def __repr__(self):
        return "{}/{}".format(self.address, self.netmask)


class simple_snmp_oid(object):
    def __init__(self, *oid, **kwargs):
        self._target_value = kwargs.get("target_value", None)
        if type(oid[0]) in [tuple, list] and len(oid) == 1:
            oid = oid[0]
        if type(oid) == tuple and len(oid) == 1 and isinstance(oid[0], basestring):
            oid = oid[0]
        # store oid in tuple-form
        if isinstance(oid, basestring):
            self._oid = tuple([int(val) for val in oid.split(".")])
        else:
            self._oid = oid
        self._oid_len = len(self._oid)
        self._str_oid = ".".join(["{:d}".format(i_val) if type(i_val) in [int, long] else i_val for i_val in self._oid])

    def has_max_oid(self):
        return False

    def __str__(self):
        return self._str_oid

    def __repr__(self):
        return "OID {}".format(self._str_oid)

    def __iter__(self):
        # reset iteration idx
        self.__idx = -1
        return self

    def next(self):
        self.__idx += 1
        if self.__idx == self._oid_len:
            raise StopIteration
        else:
            return self._oid[self.__idx]

    def get_value(self, p_mod):
        if self._target_value is not None:
            if isinstance(self._target_value, basestring):
                return p_mod.OctetString(self._target_value)
            elif type(self._target_value) in [int, long]:
                return p_mod.Integer(self._target_value)
            else:
                return p_mod.Null("")
        else:
            return p_mod.Null("")

    def as_tuple(self):
        return self._oid


class snmp_oid(simple_snmp_oid):
    def __init__(self, *oid, **kwargs):
        simple_snmp_oid.__init__(self, *oid)
        self.single_value = kwargs.get("single_value", False)
        # store oid in tuple-form
        self._max_oid = kwargs.get("max_oid", None)
        if self._max_oid:
            self._max_oid_len = len(self._max_oid)
            self._str_max_oid = ".".join(["{:d}".format(i_val) for i_val in self._max_oid])
        else:
            self._max_oid_len, self._str_max_oid = (0, "")
        self.cache_it = kwargs.get("cache", False)
        if self.cache_it:
            # time after which cache invalidates
            self.cache_timeout = kwargs.get("cache_timeout", 60)
            # timer after which cache should be refreshed
            self.refresh_timeout = kwargs.get("refresh_timeout", self.cache_timeout / 2)

    def has_max_oid(self):
        return True if self._max_oid else False

    def get_max_oid(self):
        return self._str_max_oid


# for value caching
class value_cache(object):
    def __init__(self):
        # timestamp dict, defaults to None
        self.__ts_dict = {}
        self.__values = {}

    def set(self, key, _dict):
        self.__ts_dict[key] = time.time()
        self.__values[key] = _dict

    def is_set(self, key):
        if key in self.__ts_dict:
            self.__cur_value = self.__values[key]
            self.__dt = max(abs(time.time() - self.__ts_dict[key]), 1)
            return True
        else:
            return False

    def get_value(self, cur_dict, sub_key):
        _val = (cur_dict[sub_key] - self.__cur_value[sub_key]) / (self.__dt)
        if _val < 0:
            # wrap around
            _val = 0
        return _val
