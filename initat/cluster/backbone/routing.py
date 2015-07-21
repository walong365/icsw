# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of cluster-backbone-sql
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

""" helper functions for cluster routing """

from lxml import etree  # @UnresolvedImports
import json
import logging

from initat.tools.config_tools import server_check, device_with_config, router_object
from django.core.cache import cache
from django.db.models import Q
from initat.cluster.backbone.models import device
from initat.tools import uuid_tools, logging_tools, server_command
from initat.icsw.service.instance import InstanceXML


logger = logging.getLogger("cluster.routing")


def _log(what, log_level):
    logger.log(log_level, what)

_INSTANCE = InstanceXML(_log)


def get_type_from_config(c_name):
    _REVERSE_MAP = {
        "package_server": "package",
        "package-server": "package",
        "config-server": "config",
        "config_server": "config",
    }
    return _REVERSE_MAP.get(c_name, None)


def get_server_uuid(srv_type, uuid=None):
    if uuid is None:
        uuid = uuid_tools.get_uuid().get_urn()
    if not uuid.startswith("urn"):
        uuid = "urn:uuid:{}".format(uuid)
    return "{}:{}:".format(
        uuid,
        _INSTANCE.get_uuid_postfix(srv_type),
    )


class srv_type_routing(object):
    ROUTING_KEY = "_WF_ROUTING"

    def __init__(self, force=False, logger=None):
        if logger is None:
            self.logger = logging.getLogger("cluster.routing")
        else:
            self.logger = logger
        _resolv_dict = cache.get(self.ROUTING_KEY)
        # if _resolv_dict is None or True:
        if _resolv_dict is None or force:
            _resolv_dict = self._build_resolv_dict()
        else:
            _resolv_dict = json.loads(_resolv_dict)
            if "_local_device" not in _resolv_dict:
                # old version, recalc
                _resolv_dict = self._build_resolv_dict()
        if "_local_device" in _resolv_dict:
            self._local_device = device.objects.get(Q(pk=_resolv_dict["_local_device"][0]))
        else:
            self._local_device = None
        self._alias_dict = _resolv_dict.get("_alias_dict", {})
        self._resolv_dict = _resolv_dict
        self._node_split_list = _resolv_dict.get("node_split_list", [])

    def update(self, force=False):
        if not cache.get(self.ROUTING_KEY) or force:
            self.logger.info("update srv_type_routing")
            self._resolv_dict = self._build_resolv_dict()
            if "_local_device" in self._resolv_dict:
                self._local_device = device.objects.get(Q(pk=self._resolv_dict["_local_device"][0]))
            else:
                self._local_device = None

    def __getitem__(self, srv_type):
        if srv_type in self._alias_dict:
            return self._resolv_dict[self._alias_dict[srv_type]]
        else:
            return self._resolv_dict[srv_type]

    def __contains__(self, srv_type):
        if srv_type in self._alias_dict:
            return True
        else:
            return srv_type in self._resolv_dict

    @property
    def service_types(self):
        return [key for key in self._resolv_dict.keys() if not key.startswith("_")]

    def get_connection_string(self, srv_type, server_id=None):
        if srv_type in self:
            # server list
            _srv_list = self[srv_type]
            if server_id:
                # filter
                _found_srv = [entry for entry in _srv_list if entry[2] == server_id]
                if not _found_srv:
                    self.logger.critical("no server_id {:d} found for srv_type {}, taking first one".format(server_id, srv_type))
                    _found_srv = _srv_list
            else:
                _found_srv = _srv_list
            # no server id, take first one
            return "tcp://{}:{:d}".format(
                _found_srv[0][1],
                _INSTANCE.get_port_dict(srv_type, command=True),
            )
        else:
            self.logger.critical("no srv_type {} defined".format(srv_type))
            return None

    @property
    def resolv_dict(self):
        return {key: value for key, value in self._resolv_dict.iteritems() if not key.startswith("_")}

    @property
    def local_device(self):
        return self._local_device

    @property
    def no_bootserver_devices(self):
        return self.__no_bootserver_devices

    def _srv_type_to_string(self, in_list):
        return ", ".join(in_list)

    def _build_resolv_dict(self):
        # local device
        _myself = server_check(server_type="", fetch_network_info=True)
        _router = router_object(self.logger)
        conf_names = sum([_INSTANCE.get_config_names(_inst.get("name")) for _inst in _INSTANCE.get_all_instances()], [])
        # build reverse lut
        _rv_lut = {}
        _INSTANCES_WITH_NAMES = set()
        # list of configs with node-splitting enabled
        node_split_list = []
        for _inst in _INSTANCE.get_all_instances():
            _inst_name = _inst.attrib["name"]
            if _INSTANCE.do_node_split(_inst):
                node_split_list.append(_inst_name)
            for _conf_name in _INSTANCE.get_config_names(_inst):
                _INSTANCES_WITH_NAMES.add(_inst_name)
                _rv_lut.setdefault(_conf_name, []).append(_inst_name)  # [_conf_name] = _inst_name
        # for key, value in _SRV_NAME_TYPE_MAPPING.iteritems():
        #     _rv_lut.update({_name: key for _name in value})
        # resolve dict
        _resolv_dict = {}
        # list of all already used srv_type / config_name / device_idx tuples
        _used_tuples = set()
        # dict resolving all srv_type / device_idx to set configs
        _dev_srv_type_lut = {}
        # simple routing cache
        routing_cache = {}
        # get all configs
        for _conf_name in conf_names:
            _srv_type_list = _rv_lut[_conf_name]
            _sc = device_with_config(config_name=_conf_name)
            if _conf_name in _sc:
                for _dev in _sc[_conf_name]:
                    # routing info
                    if _dev.effective_device.is_meta_device:
                        # server-like config is set for an md-device, not good
                        self.logger.error(
                            "device '{}' (srv_type_list {}) is a meta-device".format(
                                _dev.effective_device.full_name,
                                self._srv_type_to_string(_srv_type_list),
                            )
                        )
                    else:
                        if _myself.device and _dev.effective_device.pk == _myself.device.pk:
                            _first_ip = "127.0.0.1"
                            _penalty = 1
                        else:
                            # print _myself, dir(_myself)
                            _ri = _dev.get_route_to_other_device(
                                _router,
                                _myself,
                                allow_route_to_other_networks=True,
                                prefer_production_net=True,
                                cache=routing_cache
                            )
                            if _ri:
                                _first_ri = _ri[0]
                                _first_ip = _first_ri[2][1][0]
                                _penalty = _first_ri[0]
                            else:
                                _first_ip = None
                        if _first_ip:
                            for _srv_type in _srv_type_list:
                                _add_t = (_srv_type, _conf_name, _dev.effective_device.pk)
                                if _add_t not in _used_tuples:
                                    _used_tuples.add(_add_t)
                                    # lookup for simply adding new config names
                                    _dst_key = (_srv_type, _dev.effective_device.pk)
                                    if _dst_key in _dev_srv_type_lut:
                                        _ce = [_entry for _entry in _resolv_dict[_srv_type] if _entry[2] == _dev.effective_device.pk][0]
                                        _ce[4].append(_conf_name)
                                    else:
                                        _resolv_dict.setdefault(_srv_type, []).append(
                                            (
                                                _dev.effective_device.full_name,
                                                _first_ip,
                                                _dev.effective_device.pk,
                                                _penalty,
                                                [_conf_name],
                                            )
                                        )
                                    _dev_srv_type_lut.setdefault(_dst_key, []).append(_conf_name)
                                    self.logger.info(
                                        "adding device '{}' (IP {}, {:d}) to srv_type {} (config {})".format(
                                            _dev.effective_device.full_name,
                                            _first_ip,
                                            _dev.effective_device.pk,
                                            _srv_type,
                                            _conf_name,
                                        )
                                    )
                        else:
                            self.logger.error(
                                "no route to device '{}' found (srv_type_list {}, config {})".format(
                                    _dev.effective_device.full_name,
                                    self._srv_type_to_string(_srv_type_list),
                                    _conf_name,
                                )
                            )
        # missing routes
        _missing_srv = _INSTANCES_WITH_NAMES - set(_resolv_dict.keys())
        if _missing_srv:
            for _srv_type in sorted(_missing_srv):
                self.logger.warning("no device for srv_type '{}' found".format(_srv_type))
        # sort entry
        for key, value in _resolv_dict.iteritems():
            # format: device name, device IP, device_pk, penalty
            _resolv_dict[key] = [_v2[1] for _v2 in sorted([(_v[3], _v) for _v in value])]
        # set local device
        if _myself.device is not None:
            _resolv_dict["_local_device"] = (_myself.device.pk,)
        _resolv_dict["_alias_dict"] = _INSTANCE.get_alias_dict()
        _resolv_dict["_node_split_list"] = node_split_list
        # valid for 15 minutes
        cache.set(self.ROUTING_KEY, json.dumps(_resolv_dict), 60 * 15)
        return _resolv_dict

    def check_for_split_send(self, srv_type, in_com):
        # init error set
        self.__no_bootserver_devices = set()
        if srv_type in self._node_split_list:
            return self._split_send(srv_type, in_com)
        else:
            return [(None, in_com)]

    def _split_send(self, srv_type, in_com):
        cur_devs = in_com.xpath(".//ns:devices/ns:devices/ns:device")
        _dev_dict, _bs_hints = ({}, {})
        for _dev in cur_devs:
            _pk = int(_dev.attrib["pk"])
            _bs_hints[_pk] = int(_dev.get("bootserver_hint", "0"))
            _dev_dict[_pk] = etree.tostring(_dev)  # @UndefinedVariable
        # eliminate zero hints
        _bs_hints = {key: value for key, value in _bs_hints.iteritems() if value}
        _pk_list = _dev_dict.keys()
        _cl_dict = {}
        for _value in device.objects.filter(Q(pk__in=_pk_list)).values_list("pk", "bootserver", "name"):
            if _value[1]:
                _cl_dict.setdefault(_value[1], []).append(_value[0])
            elif _value[0] in _bs_hints:
                # using boothints
                self.logger.warning(
                    "using bootserver_hint {:d} for {:d} ({})".format(
                        _bs_hints[_value[0]],
                        _value[0],
                        _value[2],
                    )
                )
                _cl_dict.setdefault(_bs_hints[_value[0]], []).append(_value[0])
            else:
                self.__no_bootserver_devices.add((_value[0], _value[2]))
                self.logger.warning(
                    "device {:d} ({}) has no bootserver associated".format(
                        _value[0],
                        _value[2],
                    )
                )
        # do we need more than one server connection ?
        if len(_cl_dict) > 1:
            _srv_keys = _cl_dict.keys()
            _srv_dict = {key: server_command.srv_command(source=etree.tostring(in_com.tree)) for key in _srv_keys}  # @UndefinedVariable
            # clear devices
            [_value.delete_subtree("devices") for _value in _srv_dict.itervalues()]
            # add devices where needed
            for _key, _pk_list in _cl_dict.iteritems():
                _tree = _srv_dict[_key]
                _devlist = _tree.builder("devices")
                _tree["devices"] = _devlist
                _devlist.extend([etree.fromstring(_dev_dict[_pk]) for _pk in _pk_list])  # @UndefinedVariable
                # print "T", _key, _tree.pretty_print()
            return [(key, value) for key, value in _srv_dict.iteritems()]
        elif len(_cl_dict) == 1:
            return [(_cl_dict.keys()[0], in_com)]
        else:
            return []

    def start_result_feed(self):
        # clear result
        self.result = None

    def _log(self, request, log_lines, log_str, log_level=logging_tools.LOG_LEVEL_OK):
        if request and hasattr(request, "xml_response"):
            request.xml_response.log(log_level, log_str)
        else:
            log_lines.append((log_level, log_str))

    def feed_result(self, orig_com, result, request, conn_str, log_lines, log_result, log_error):
        # TODO: if log_error, log all msgs with log_level >= 40
        if result is None:
            if log_error:
                _err_str = "error contacting server {}, {}".format(
                    conn_str,
                    orig_com["command"].text
                )
                self._log(request, log_lines, _err_str, logging_tools.LOG_LEVEL_ERROR)
        else:
            # TODO: check if result is set
            log_str, log_level = result.get_log_tuple()
            if log_result or (log_error and log_level >= logging_tools.LOG_LEVEL_ERROR):
                self._log(request, log_lines, log_str, log_level)
            if self.result is None:
                self.result = result
            else:
                # merge result
                # possible sub-structs
                for _sub_name in ["devices", "cd_ping_list"]:
                    _s2_name = "{}:{}".format(_sub_name, _sub_name)
                    if _s2_name in result:
                        # preset in result to merge
                        if _s2_name not in self.result:
                            # add to main part if not present
                            self.result[_sub_name] = self.result.builder(_sub_name)
                        add_list = self.result[_s2_name]
                        _merged = 0
                        for entry in result.xpath(".//ns:{}/ns:{}/*".format(_sub_name, _sub_name)):
                            _merged += 1
                            add_list.append(entry)
                        self.logger.info(
                            "merged {} of {}".format(
                                logging_tools.get_plural("element", _merged),
                                _sub_name,
                            )
                        )
