# Copyright (C) 2014 Andreas Lang-Nevyjel, init.at
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

import ipvx_tools
import server_command


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
        self.macaddr = ":".join(["{:02x}".format(ord(_val)) for _val in in_dict[6]])
        self.admin_status = in_dict[7]
        self.oper_status = in_dict[8]
        self.last_change = in_dict[9]
        self.in_counter = snmp_if_counter(in_dict[10], in_dict[11], in_dict[12], in_dict[13], in_dict[14])
        self.out_counter = snmp_if_counter(in_dict[16], in_dict[17], in_dict[18], in_dict[19], in_dict[20])
        self.in_unknown_protos = in_dict[15]

    def __repr__(self):
        return "if {} ({:d}), MTU is {:d}, type is {:d}".format(
            self.name,
            self.idx,
            self.mtu,
            self.if_type
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


def oid_to_str(oid):
    if type(oid) == tuple:
        oid = ".".join(["{:d}".format(_p) for _p in oid])
    return oid
