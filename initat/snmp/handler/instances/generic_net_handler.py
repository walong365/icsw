# Copyright (C) 2015 Andreas Lang-Nevyjel, init.at
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
""" SNMP handler for basic network stuff (netdevices) """

import time

from initat.host_monitoring import limits
from lxml.builder import E
from initat.tools import logging_tools

from ...functions import simplify_dict
from ...snmp_struct import ResultNode, snmp_if, simple_snmp_oid, snmp_hs, MonCheckDefinition, snmp_oid
from ..base import SNMPHandler

try:
    from django.db.models import Q
    from initat.cluster.backbone.models import snmp_network_type, netdevice, netdevice_speed, \
        peer_information
    from initat.cluster.backbone.models import SpecialGroupsEnum, NetDeviceSNMPMonOptions, NetDeviceDesiredStateEnum
except:
    SpecialGroupsEnum = None


# if base
IF_BASE = "1.3.6.1.2.1.2"
# highspeed base
HS_BASE = "1.3.6.1.2.1.31.1.1.1"


def safe_string(in_str):
    return "".join([_char for _char in in_str if ord(_char) >= 32])


class handler(SNMPHandler):
    class Meta:
        description = "network settings (devices)"
        vendor_name = "generic"
        name = "net"
        version = 1
        tl_oids = [IF_BASE, HS_BASE]
        priority = 64
        initial = True

    def update(self, dev, scheme, result_dict, oid_list, flags):
        _if_dict = {key: snmp_if(value) for key, value in simplify_dict(result_dict[IF_BASE], (2, 1)).iteritems()}
        if HS_BASE in result_dict:
            _hs_dict = {key: snmp_hs(value) for key, value in simplify_dict(result_dict[HS_BASE], ()).iteritems()}
            # pprint.pprint(_hs_dict)
        else:
            _hs_dict = {}
        snmp_type_dict = {_value.if_type: _value for _value in snmp_network_type.objects.all()}
        _added, _updated, _removed = (0, 0, 0)
        # found and used database ids (for deletion)
        _found_nd_ids = set()
        # all present netdevices
        present_nds = netdevice.objects.filter(Q(device=dev))
        # build speed lut
        ND_SPEED_LUT = netdevice_speed.build_lut()
        # lut
        pnd_lut = {}
        for entry in present_nds:
            pnd_lut[entry.devname] = entry
            if entry.snmp_idx:
                pnd_lut[entry.snmp_idx] = entry
        # pprint.pprint(pnd_lut)
        # lookup dict for snmp_if -> dev_nd
        for if_idx, if_struct in _if_dict.iteritems():
            _created = False
            _dev_nd = pnd_lut.get(if_idx, pnd_lut.get(if_struct.name, None))
            if _dev_nd is None:
                _created = True
                _added += 1
                # create new entry, will be updated later with more values
                _dev_nd = netdevice(
                    device=dev,
                    snmp_idx=if_idx,
                    force_network_device_type_match=False,
                )
                # update lut
                pnd_lut[if_idx] = _dev_nd
                pnd_lut[if_struct.name] = _dev_nd
            if _dev_nd is not None:
                if not _created:
                    _updated += 1
                if if_struct.name in pnd_lut and pnd_lut[if_struct.name].snmp_idx != _dev_nd.snmp_idx:
                    self.log(
                        "namechange detected for SNMP interfaces, deleting previous interface ({}, {:d})".format(
                            if_struct.name,
                            if_idx,
                        )
                    )
                    pnd_lut[if_struct.name].delete()
                _dev_nd.snmp_idx = if_idx
                _dev_nd.devname = if_struct.name
                _dev_nd.netdevice_speed = ND_SPEED_LUT.get(if_struct.speed, ND_SPEED_LUT[0])
                _dev_nd.snmp_network_type = snmp_type_dict[if_struct.if_type]
                _dev_nd.mtu = if_struct.mtu
                _dev_nd.macaddr = if_struct.macaddr
                _dev_nd.snmp_admin_status = if_struct.admin_status
                _dev_nd.snmp_oper_status = if_struct.oper_status
                _dev_nd.save()
                _found_nd_ids.add(_dev_nd.idx)
        if flags["strict"]:
            stale_nds = netdevice.objects.exclude(Q(pk__in=_found_nd_ids)).filter(Q(device=dev))
            if stale_nds.count():
                _remove = True
                _stale_ids = [_nd.idx for _nd in stale_nds]
                # check peers
                stale_peers = peer_information.objects.filter(Q(s_netdevice__in=_stale_ids) | Q(d_netdevice__in=_stale_ids))
                if stale_peers.count():
                    # relink stale peers to first new netdevice
                    if _found_nd_ids:
                        # nds without loopback devices
                        relink_nds = netdevice.objects.exclude(Q(snmp_network_type__if_type__in=[24])).filter(Q(pk__in=_found_nd_ids))
                        if relink_nds.count():
                            # ok, take first one
                            relink_nd = relink_nds[0]
                        else:
                            # take first one without software loopback filter
                            relink_nd = netdevice.objects.get(Q(pk=list(_found_nd_ids)[0]))
                        for stale_peer in stale_peers:
                            if stale_peer.s_netdevice_id in _stale_ids and stale_peer.d_netdevice_id in _stale_ids:
                                # source and dest will be delete, delete this peer
                                pass
                            elif stale_peer.s_netdevice_id in _stale_ids:
                                stale_peer.s_netdevice = relink_nd
                                stale_peer.save()
                            else:
                                stale_peer.d_netdevice = relink_nd
                                stale_peer.save()
                    else:
                        # no netdevices found, skip removing stale nds
                        _remove = False
                if _remove:
                    _removed += stale_nds.count()
                    stale_nds.delete()
        return ResultNode(
            ok="updated interfaces (added {:d}, updated {:d}, removed {:d})".format(
                _added,
                _updated,
                _removed,
            )
        )

    def collect_fetch(self):
        return [
            (
                "T",
                [
                    simple_snmp_oid(IF_BASE),
                    simple_snmp_oid(HS_BASE),
                ]
            )
        ]

    def _build_if_mvl(self, vector, if_name, **kwargs):
        # to remove binary data from strings (yeah windows)
        return E.mvl(
            E.value(
                info="OctetsIn on {}".format(if_name),
                value="{:f}".format(vector[0]),
                key="rx",
                v_type="f",
                unit="Byte/s",
                base="1024",
            ),
            E.value(
                info="OctetsOut on {}".format(if_name),
                value="{:f}".format(vector[1]),
                key="tx",
                v_type="f",
                unit="Byte/s",
                base="1024",
            ),
            E.value(
                info="Discards on {}".format(if_name),
                value="{:f}".format(vector[2]),
                key="dsc",
                v_type="f",
                unit="1/s",
            ),
            E.value(
                info="Errors on {}".format(if_name),
                value="{:f}".format(vector[3]),
                key="errors",
                v_type="f",
                unit="1/s",
            ),
            # used for file lookup
            ** kwargs
        )

    def collect_feed(self, result_dict, **kwargs):
        result_dict = self.filter_results(result_dict, keys_are_strings=True)  # False)
        if IF_BASE in result_dict:
            # take result tree
            _base_dict = simplify_dict(
                result_dict[IF_BASE],
                (2, 1),
                sub_key_filter={2, 1, 10, 11, 12, 13, 14, 16, 117, 18, 19, 20}
            )
            if HS_BASE in result_dict:
                _hi_dict = simplify_dict(
                    result_dict[HS_BASE],
                    (),
                    sub_key_filter={6, 10}
                )
            else:
                _hi_dict = {}
            # pprint.pprint(result_dict)
            # reorder
            mv_tree = kwargs["mv_tree"]
            _vc = kwargs["vc"]
            _sum_vector = [0., 0., 0., 0.]
            for _if_idx, _if in _base_dict.iteritems():
                if 10 not in _if:
                    continue
                if _if_idx in _hi_dict and _hi_dict[_if_idx].get(6, 0):
                    # replace values from hi_dict
                    _if[10] = _hi_dict[_if_idx][6]
                    _if[16] = _hi_dict[_if_idx][10]
                _prefix = "net.snmp_{:d}".format(_if_idx)
                _name = safe_string(_if[2] or "idx#{:d}".format(_if_idx))
                # check if cache is present and set internal values
                if _vc.is_set(_if_idx):
                    _vector = [
                        _vc.get_value(_if, 10),
                        _vc.get_value(_if, 16),
                        _vc.get_value(_if, 13) + _vc.get_value(_if, 19),
                        _vc.get_value(_if, 14) + _vc.get_value(_if, 20),
                    ]
                    _sum_vector = [a + b for a, b in zip(_vector, _sum_vector)]
                    mv_tree.append(
                        self._build_if_mvl(
                            _vector,
                            _name,
                            name=_prefix,
                            info="if {}".format(_name),
                            timeout="{:d}".format(int(time.time()) + 120)
                        )
                    )
                _vc.set(_if_idx, _if)
            mv_tree.append(
                self._build_if_mvl(
                    _sum_vector,
                    "all",
                    name="net.snmp_all",
                    info="all",
                    timeout="{:d}".format(int(time.time()) + 120)
                )
            )

    def config_mon_check(self):
        return [
            if_mon(self),
        ]


class if_mon(MonCheckDefinition):
    class Meta:
        short_name = "if"
        command_line = "* --speed $ARG3$ --flags $ARG4$ $ARG5$"
        info = "SNMP Interface check"
        description = "SNMP Interface check, source is Database"
        if SpecialGroupsEnum:
            group = SpecialGroupsEnum.system_net

    def parser_setup(self, parser):
        parser.add_argument("--speed", type=int, dest="speed", help="target interface speed")
        parser.add_argument("--flags", type=str, dest="flags", default="", help="monitoring flags")
        parser.add_argument("if_idx", nargs=1, type=int, help="interface idx")

    def config_call(self, s_com):
        dev = s_com.host
        _field = []
        for net_dev in dev.netdevice_set.select_related("netdevice_speed").filter(Q(enabled=True) & Q(snmp_idx__gt=0)):
            _field.append(
                s_com.get_arg_template(
                    net_dev.devname,
                    arg1=dev.dev_variables["SNMP_READ_COMMUNITY"],
                    arg2=dev.dev_variables["SNMP_VERSION"],
                    arg3="{:d}".format(net_dev.netdevice_speed.speed_bps),
                    arg4=NetDeviceSNMPMonOptions.flags_to_str(net_dev),
                    arg5="{:d}".format(net_dev.snmp_idx),
                )
            )
        return _field

    def mon_start(self, scheme):
        return [
            snmp_oid(
                "{}.2.1.{:d}.{:d}".format(
                    IF_BASE,
                    _idx,
                    scheme.opts.if_idx[0]
                ),
                single_value=True
            ) for _idx in [5, 7, 8, 10, 16, 13, 14, 19, 20]
        ]
        #     + [
        #    snmp_oid(
        #        "{}.{:d}.{:d}".format(
        #            HS_BASE,
        #            _idx,
        #            scheme.opts.if_idx
        #        ),
        #        single_value=True
        #    ) for _idx in [6, 10]
        # ]

    def mon_result(self, scheme):
        _net_obj = scheme.net_obj
        _val_dict = {list(_key)[-2]: _value for _key, _value in scheme.snmp.iteritems()}
        # print ND_SPEED_LUT
        _key = "network-if-{:d}".format(scheme.opts.if_idx[0])
        _vc = _net_obj.value_cache
        if _vc.is_set(_key):
            _vector = [
                _vc.get_value(_val_dict, 10),
                _vc.get_value(_val_dict, 16),
                _vc.get_value(_val_dict, 13) + _vc.get_value(_val_dict, 19),
                _vc.get_value(_val_dict, 14) + _vc.get_value(_val_dict, 20),
            ]
        else:
            _vector = None
        _vc.set(_key, _val_dict)
        _mon_flags = NetDeviceSNMPMonOptions(scheme.opts.flags)
        ret_state, r_f = (limits.nag_STATE_OK, [])
        if _vector is None:
            r_f.append("only one value read out")
        else:
            r_f.extend(
                [
                    "rx (in): {}".format(
                        logging_tools.get_size_str(_vector[0], strip_spaces=True, per_second=True),
                    ),
                    "tx (out): {}".format(
                        logging_tools.get_size_str(_vector[1], strip_spaces=True, per_second=True),
                    )
                ]
            )
            if _vector[2]:
                if _vector[2] > 1:
                    ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                else:
                    ret_state = max(ret_state, limits.nag_STATE_WARNING)
                r_f.append(
                    "discards: {:.2f} /sec".format(
                        _vector[2]
                    )
                )
            if _vector[3]:
                ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                r_f.append(
                    "errors: {:.2f} / sec".format(
                        _vector[3],
                    )
                )
        # check oper status
        if _mon_flags.desired_status == NetDeviceDesiredStateEnum.up and not _val_dict[8]:
            r_f.append("OperStatus is down")
            ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
        elif _mon_flags.desired_status == NetDeviceDesiredStateEnum.down and _val_dict[8]:
            r_f.append("OperStatus is up")
            ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
        if scheme.opts.speed is not None and (scheme.opts.speed or _val_dict[5]) and not _mon_flags.ignore_netdevice_speed:
            if scheme.opts.speed == _val_dict[5]:
                r_f.append("speed is {}".format(logging_tools.get_size_str(_val_dict[5], strip_spaces=True, per_second=True, divider=1000)))
            else:
                if _val_dict[5] in [2 ** 32 - 1, 2 ** 31 - 1]:
                    pass
                else:
                    ret_state = max(ret_state, limits.nag_STATE_WARNING)
                    r_f.append(
                        "measured speed {} differs from target speed {}".format(
                            logging_tools.get_size_str(_val_dict[5], strip_spaces=True, per_second=True, divider=1000),
                            logging_tools.get_size_str(scheme.opts.speed, strip_spaces=True, per_second=True, divider=1000),
                        )
                    )
        return ret_state, ", ".join(r_f)
