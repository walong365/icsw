# Copyright (C) 2013-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file belongs to the collectd-init package
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
""" aggregation part of rrd-grapher service via memcache structure """

import json
import os
import re
import time

import memcache
import zmq
from lxml import etree
from lxml.builder import E

from initat.cluster.backbone import db_tools
from initat.cluster.backbone.models import device_group
from initat.collectd.config import global_config
from initat.tools import logging_tools, process_tools, server_mixins, threading_tools


class AGStruct(object):
    def __init__(self, log_com):
        self.__log_com = log_com
        self.groups = []
        self.system_group = None
        self.log("init structure")
        # matched uuids from collectd
        self.__matched_uuids = set()
        # group_uuids
        self.__group_uuids = set()
        # group names, uuid -> send name (METADEV_*)
        self.__group_names = {}
        # lut, contains FQDNs and uuids
        self.__lut = {}
        # all uuids
        self.__uuids = set()
        # all fqdns
        self.__fqdns = set()
        # all short names
        self.__snames = set()
        # all problematic (non-unique) short names
        self.__prob_snames = set()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com(u"[ags] {}".format(what), log_level)

    def add_group(self, agg):
        agg.struct = self
        self.groups.append(agg)
        self.__group_uuids.add(agg.uuid)
        self.__group_names[agg.uuid] = agg.send_name

    def set_system_group(self, sg, uuid, send_name):
        self.system_group = sg
        self.__sys_uuid = uuid
        self.__sys_send_name = send_name

    def add_lut(self, agd):
        self.__lut[agd.name] = agd
        self.__lut[agd.uuid] = agd
        self.__uuids.add(agd.uuid)
        self.__fqdns.add(agd.name)
        _s_name = agd.name.split(".")[0]
        if _s_name in self.__snames:
            self.log(
                "short name '{}' already used (uuid {}, FQDN {})...".format(
                    _s_name,
                    agd.uuid,
                    agd.name,
                ),
                logging_tools.LOG_LEVEL_WARN
            )
            self.__prob_snames.add(_s_name)
        self.__snames.add(_s_name)
        self.__lut[_s_name] = agd

    def match(self, h_struct):
        # info dict
        _mdict = {_key: 0 for _key in ["uuid", "fqdn", "sname"]}
        # get all unmatched
        _um = set(h_struct.keys()) - set(self.__matched_uuids) - self.__group_uuids
        for _found in _um & self.__uuids:
            self.__matched_uuids.add(_found)
            _um.remove(_found)
            self.__lut[_found].collectd_uuid = _found
            _mdict["uuid"] += 1
        fqdns = {h_struct[_uuid][1]: _uuid for _uuid in _um}
        for _found in set(fqdns.keys()) & self.__fqdns:
            _uuid = fqdns[_found]
            self.__matched_uuids.add(_uuid)
            _um.remove(_uuid)
            self.__lut[_found].collectd_uuid = _uuid
            # add lut from foreigin uuid
            self.__lut[_uuid] = self.__lut[_found]
            _mdict["fqdn"] += 1
        snames = {h_struct[_uuid][1].split(".")[0]: _uuid for _uuid in _um}
        for _found in set(snames.keys()) & self.__snames:
            _uuid = snames[_found]
            if _found in self.__prob_snames:
                self.log("ignoring {} ({}, unsafe match)".format(_found, _uuid))
            else:
                self.__matched_uuids.add(_uuid)
                _um.remove(_uuid)
                self.__lut[_found].collectd_uuid = _uuid
                # add lut from foreigin uuid
                self.__lut[_uuid] = self.__lut[_found]
                _mdict["sname"] += 1
        if sum(_mdict.values()):
            self.log(
                "match info: {}".format(
                    ", ".join(["{}={:d}".format(_key, _value) for _key, _value in _mdict.iteritems() if _value])
                )
            )
        # list of valid uuids for this run
        _valid_uuids = set(h_struct.keys()) & self.__matched_uuids
        # build structure
        _comp_dict = {}
        for _valid_uuid in _valid_uuids:
            _comp_dict.setdefault(self.__lut[_valid_uuid].group.uuid, []).append(_valid_uuid)
        # list how to build to aggregates
        _build_list = [(_key, self.__group_names[_key], _value) for _key, _value in _comp_dict.iteritems()]
        if _build_list:
            # append sys list
            _build_list.append((self.__sys_uuid, self.__sys_send_name, _comp_dict.keys()))
        return _build_list

    def set_last_update(self, h_dict):
        for _um in self.__matched_uuids:
            if _um in h_dict:
                self.__lut[_um].last_udpate = h_dict[_um][0]
            else:
                self.__lut[_um].last_update = None


class AGDeviceGroup(object):
    def __init__(self, name, uuid, send_name, cdg=False):
        self.name = name
        self.uuid = uuid
        # name with METADEV_ prefix
        self.send_name = send_name
        self.cdg = cdg
        self.devices = []
        # link to AGStruct
        self.struct = None

    def add_device(self, agd):
        agd.struct = self.struct
        agd.group = self
        self.devices.append(agd)
        self.struct.add_lut(agd)


class AGDevice(object):
    def __init__(self, name, uuid):
        self.name = name
        self.uuid = uuid
        # uuid from collectd, may differ
        self.collectd_uuid = None
        # link to AGStruct
        self.struct = None
        # link to device_group
        self.group = None
        # last update
        self.last_udpate = None


AGGREGATE_NG = """
<element name="aggregate" xmlns="http://relaxng.org/ns/structure/1.0">
    <attribute name="action">
    </attribute>
    <attribute name="name">
    </attribute>
    <optional>
        <attribute name="target-key">
        </attribute>
    </optional>
    <element name="key_list">
        <oneOrMore>
            <element name="key">
                <attribute name="match">
                </attribute>
                <attribute name="top-level">
                </attribute>
            </element>
        </oneOrMore>
    </element>
</element>
"""


class AGTopLevelStruct(object):
    def __init__(self, log_com):
        self.__log_com = log_com
        self.__ags = []
        # list of all regular expressions
        self.__re_list = []
        # with top-level keys as dict
        self.__re_dict = {}
        # list of all already matched keys
        self.__all_matched = set()
        self.__all_matched_lut = {}
        # current aggregate idx
        self.__agg_idx = 0
        # aggregate lut
        self.__agg_lut = {}
        self.log("init")
        self._update_re()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com(u"[tls] {}".format(what), log_level)

    def __getitem__(self, name):
        return self.__agg_lut[name]

    def add_aggregate(self, _obj):
        _obj.tls = self
        self.__ags.append(_obj)
        self.__agg_idx += 1
        _obj.name = "agg{:d}".format(self.__agg_idx)
        self.__agg_lut[_obj.name] = _obj
        self.__re_list.extend(_obj.re_list)
        for _tl, _re_list in _obj.re_dict.iteritems():
            self.__re_dict.setdefault(_tl, []).append((_obj.name, _re_list))
        # print "-" * 20
        self._update_re()

    def _update_re(self):
        self.__top_level_keys = set()
        self.__second_level_keys = set()
        # for speedup we organize the aggregates according to their top-level keys
        self.__top_level_res = {}
        for _key in self.__re_dict:
            _parts = _key.split(".")
            self.__top_level_keys.add(_parts[0])
            if len(_parts) > 1:
                self.__second_level_keys.add(".".join(_parts[:2]))
            self.__top_level_res.setdefault(_parts[0], []).extend(self.__re_dict[_key])
        for _key, _list in self.__top_level_res.iteritems():
            self.__top_level_res[_key] = self._build_re(_key, _list)

    def _build_re(self, key, _in_list):
        _list = []
        for _name, _re_list in _in_list:
            _sub_list = "|".join(_re_list)
            _re = "(?P<{}>({}))".format(_name, _sub_list)
            _list.append(_re)
        # incremental logging
        self.log(
            "re_list for key {}: {}".format(
                key,
                ", ".join(_list),
            )
        )
        # return a list of regexps so that one value can go into more than one aggregate
        return [re.compile(_entry) for _entry in _list]

    def filter(self, in_list):
        # filter in dict
        _used_aggs = set()
        _res = []
        for _v_values in in_list:  # _format, _key, _info, _unit, _v_type, _value, _base, _factor in in_list:
            _key = _v_values[1]
            if _key not in self.__all_matched:
                _parts = _key.split(".")
                if _parts[0] in self.__top_level_keys:
                    _matches = [_re.match(_key) for _re in self.__top_level_res[_parts[0]]]
                    # print _key, _parts[0], _match
                    for _match in _matches:
                        if _match:
                            for _mk, _mv in _match.groupdict().iteritems():
                                self.__all_matched.add(_mv)
                                self.__all_matched_lut.setdefault(_mv, []).append(_mk)
                                # _res.append((self.__all_matched_lut[_key], _format, _key, _info, _unit, _v_type, _value, _base, _factor))
            if _key in self.__all_matched:
                _used_aggs |= set(self.__all_matched_lut[_key])
                _res.append((self.__all_matched_lut[_key], VE(*_v_values)))  # _format, _key, _info, _unit, _v_type, _value, _base, _factor))
        return _used_aggs, _res


class VE(object):
    # vector entry (duplicated in md_config_server.kpi.kpi_data)
    def __init__(self, *args):
        self.format, self.key, self.info, self.unit, self.v_type, self.value, self.base, self.factor = args

    def __repr__(self):
        return u"ve {}".format(self.key)

    def get_value(self):
        return self.value * self.factor

    def get_expanded_info(self):
        # replace "$2" by 2nd part of key and so on
        expanded_info = self.info
        for num, subst in enumerate(self.key.split("."), start=1):
            expanded_info = expanded_info.replace("${}".format(num), subst)
        return expanded_info


class AGSink(object):
    # aggregate sink, has sub entries for each key
    def __init__(self, **kwargs):
        # aggregate sink
        self.action = kwargs.get("action", "sum")
        self.target_key = kwargs.get("target_key", None)
        self.key_sinks = {}
        # base data set ?

    def get_vector(self):
        return [_key_sink.get_vector() for _key_sink in self.key_sinks.itervalues()]

    def feed_ve(self, _ve):
        # feed vector entry
        # one target key or use _ve key
        if self.target_key:
            _ve.key = self.target_key
        if _ve.key not in self.key_sinks:
            self.key_sinks[_ve.key] = KeySink(_ve, self.action)
        self.key_sinks[_ve.key].feed_ve(_ve)

    def __repr__(self):
        return u"ag_sink [{}] {}: {}; {}".format(
            self.target_key if self.target_key else "N/A",
            logging_tools.get_plural("key_sink", len(self.key_sinks)),
            ", ".join(sorted(self.key_sinks.keys())),
            ", ".join([str(_val) for _val in self.key_sinks.itervalues()]),
        )

    def get_debug(self, num_src):
        # return debug info
        _sinks = [_value.get_debug(num_src) for _value in self.key_sinks.itervalues()]
        _sinks = [_entry for _entry in _sinks if _entry]
        _total = len(self.key_sinks)
        return u"ag_sink ({:d} keys): {:.1f}%; {}".format(
            _total,
            float((_total - len(_sinks)) * 100. / len(self.key_sinks)),
            ", ".join(_sinks) or "---",
        )


class KeySink(object):
    def __init__(self, _ve, action):
        for _attr in ["format", "key", "info", "unit", "v_type", "base", "factor"]:
            setattr(self, _attr, getattr(_ve, _attr))
        self.action = action
        self.__values = []

    def feed_ve(self, _ve):
        # feed vector entry
        self.__values.append(_ve.get_value())

    def __repr__(self):
        return u"key_sink {}, {:d} values ({})".format(
            self.key,
            len(self.__values),
            str(self.__values),
        )

    def get_debug(self, num_src):
        if len(self.__values) != num_src:
            return "{}: {:d}".format(self.key, len(self.__values))
        else:
            return ""

    def get_vector(self):
        return (self.format, self.key, self.info, self.unit, self.v_type, self.get_value(), self.base, self.factor)

    def get_value(self):
        if self.action == "sum":
            return sum(self.__values) / (self.factor)
        elif self.action == "mean":
            if len(self.__values):
                return sum(self.__values) / (len(self.__values) * self.factor)
            else:
                return 0
        else:
            print("action '{}' not implemented for key_sink, return 0".format(self.action))
            return 0

    @staticmethod
    def build_xml(values):
        return E.mve(
            name=values[1],
            info=values[2],
            unit=values[3],
            v_type=values[4],
            value=str(values[5]),
            base="{:d}".format(values[6]),
            factor="{:d}".format(values[7]),
        )


class AGObj(object):
    def __init__(self, ag_xml):
        # list of matched keys
        self.__matched = set()
        self.__re_list = []
        self.__re_dict = {}
        for _key in ag_xml.findall(".//key_list/key"):
            _tl = _key.attrib["top-level"]
            _re = "^{}\\.{}".format(_tl.replace(".", "\\."), _key.attrib["match"])
            self.__re_list.append((_tl, _re))
            self.__re_dict.setdefault(_tl, []).append(_re)
        self.action = ag_xml.attrib["action"]
        # target key, summarize all values
        self.target_key = ag_xml.attrib.get("target-key", None)
        # set by ag_tls
        self.tls = None
        self.name = None

    @property
    def re_list(self):
        return self.__re_list

    @property
    def re_dict(self):
        return self.__re_dict

    def new_sink(self):
        # return empty structure
        return AGSink(action=self.action, target_key=self.target_key)


class aggregate_process(threading_tools.process_obj, server_mixins.OperationalErrorMixin):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True
        )
        db_tools.close_connection()
        self.__debug = global_config["DEBUG"]
        # cache address
        self.__memcache_address = [
            "{}:{:d}".format(
                global_config["MEMCACHE_ADDRESS"].split(":")[0],
                global_config["MEMCACHE_PORT"],
            )
        ]
        # last update of aggregation structure
        self.__struct_update = None
        # cache for filtered values
        self.__vector_filter_cache = {}
        self.init_sockets()
        self.init_ag_xml()
        self.register_timer(self.aggregate, 30, instant=False, first_timeout=1)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self.drop_socket.close()
        self.__log_template.close()

    def init_sockets(self):
        t_sock = self.zmq_context.socket(zmq.PUSH)  # @UndefinedVariable
        t_sock.setsockopt(zmq.LINGER, 0)  # @UndefinedVariable
        t_sock.setsockopt(zmq.SNDHWM, 16)  # @UndefinedVariable
        t_sock.setsockopt(zmq.BACKLOG, 4)  # @UndefinedVariable
        t_sock.setsockopt(zmq.SNDTIMEO, 1000)  # @UndefinedVariable
        t_sock.setsockopt(zmq.RECONNECT_IVL, 1000)  # @UndefinedVariable
        t_sock.setsockopt(zmq.RECONNECT_IVL_MAX, 30000)  # @UndefinedVariable
        conn_str = "tcp://localhost:8002"
        t_sock.connect(conn_str)
        self.log("connected drop socket to {}".format(conn_str))
        self.drop_socket = t_sock

    def init_ag_xml(self):
        # validator
        _ng = etree.RelaxNG(etree.fromstring(AGGREGATE_NG))  # @UndefinedVariable
        _ag_dir = global_config["AGGREGATE_DIR"]
        tls = AGTopLevelStruct(self.log)
        for _dir, _dirs, _files in os.walk(_ag_dir):
            for _file in [_entry for _entry in _files if _entry.startswith("agg") and _entry.endswith(".xml")]:
                _file = os.path.join(_dir, _file)
                try:
                    cur_xml = etree.fromstring(file(_file, "rb").read())
                except:
                    self.log(
                        "error interpreting aggregate file {}: {}".format(
                            _file,
                            process_tools.get_except_info(),
                        )
                    )
                else:
                    for _xml_num, _xml in enumerate(cur_xml, 1):
                        _valid = _ng.validate(_xml)
                        if _valid:
                            self.log(
                                "added aggregate #{:d} from {}".format(
                                    _xml_num,
                                    _file,
                                )
                            )
                            tls.add_aggregate(AGObj(_xml))
                        else:
                            self.log(
                                "aggregate #{:d} from {} is invalid: {}".format(
                                    _xml_num,
                                    _file,
                                    str(_ng.error_log),
                                )
                            )
        self.ag_tls = tls

    def _update_struct(self):
        cur_time = time.time()
        if self.__struct_update is None or abs(cur_time - self.__struct_update) > global_config["AGGREGATE_STRUCT_UPDATE"]:
            self.log("updating aggregate structure")
            all_groups = device_group.objects.all().prefetch_related("device_group__domain_tree_node")
            _sys_group = [group for group in all_groups if group.cluster_device_group][0]
            _sys_md = [_dev for _dev in _sys_group.device_group.all() if _dev.is_meta_device][0]
            _ags = AGStruct(self.log)
            _ags.set_system_group(_sys_group, _sys_md.uuid, _sys_md.full_name)
            for _group in all_groups:
                if _group.cluster_device_group:
                    continue
                _devs = [_dev for _dev in _group.device_group.all() if not _dev.is_meta_device]
                _meta_dev = [_dev for _dev in _group.device_group.all() if _dev.is_meta_device][0]
                cur_agg = AGDeviceGroup(_group.name, _meta_dev.uuid, _meta_dev.full_name)
                _ags.add_group(cur_agg)
                for _dev in _devs:
                    cur_agg.add_device(AGDevice(_dev.full_name, _dev.uuid))
            self.struct = _ags
            self.__struct_update = cur_time

    def get_mc(self):
        return memcache.Client(self.__memcache_address)

    def _fetch_hosts(self, mc):
        try:
            h_dict = json.loads(mc.get("cc_hc_list"))
        except:
            self.log(
                "error fetching host_list: {}".format(
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            h_dict = {}
        build_list = self.struct.match(h_dict)
        self.struct.set_last_update(h_dict)
        return build_list

    def _fetch_values(self, mc, build_list):
        # fetch values
        _uuid_list = sum([_v[2] for _v in build_list[:-1]], [])
        # print _uuid_list
        v_dict = {}
        for _key in _uuid_list:
            _val = mc.get("cc_hc_{}".format(_key))
            if _val is not None:
                v_dict[_key] = self.ag_tls.filter(json.loads(_val))
                self.__vector_filter_cache[_key] = v_dict[_key]
            else:
                if _key in self.__vector_filter_cache:
                    self.log("error fetching data for {}, using cache".format(_key), logging_tools.LOG_LEVEL_WARN)
                    v_dict[_key] = self.__vector_filter_cache[_key]
                    del self.__vector_filter_cache[_key]
                else:
                    self.log("error fetching data for {}, and cache is empty".format(_key), logging_tools.LOG_LEVEL_ERROR)
                    _uuid_list.remove(_key)
        return v_dict

    def _create_aggregates(self, src_uuids, v_dict):
        _local_aggs = {}
        for _uuid in src_uuids:
            if _uuid in v_dict:
                _total_agg_list, _v_list = v_dict[_uuid]
                for _agg_name in _total_agg_list:
                    if _agg_name not in _local_aggs:
                        _local_aggs[_agg_name] = self.ag_tls[_agg_name].new_sink()
                for _target_agg, _ve in _v_list:
                    [_local_aggs[_agg_name].feed_ve(_ve) for _agg_name in _target_agg]
        # build values for cluster-wide aggregation
        _group_values = sum([_ag_sink.get_vector() for _ag_sink in _local_aggs.itervalues()], [])
        if self.__debug:
            _num_src = len(v_dict)
            self.log(
                "dbg ({:d} srcs): {}".format(
                    _num_src,
                    ", ".join(
                        [
                            _ag_sink.get_debug(_num_src) for _ag_sink in _local_aggs.itervalues()
                        ]
                    )
                )
            )
        return _group_values

    def build_vectors(self, build_list, v_dict):
        # build vectors and send them to the local collectd
        _meta_dict = {}
        for _meta_uuid, _send_name, _ref_uuids in build_list[:-1]:
            # meta aggregates
            _meta_aggs = self._create_aggregates(_ref_uuids, v_dict)
            self.send_vector(_meta_uuid, _send_name, _meta_aggs)
            _meta_dict[_meta_uuid] = self.ag_tls.filter(_meta_aggs)
        if build_list:
            _sys_uuid, _send_name, _sys_srcs = build_list[-1]
            # sys aggregates
            _sys_aggs = self._create_aggregates(_sys_srcs, _meta_dict)
            self.send_vector(_sys_uuid, _send_name, _sys_aggs)

    def send_vector(self, target_uuid, send_name, entries):
        _vector = E.machine_vector(
            *[
                KeySink.build_xml(_entry) for _entry in entries
            ],
            version="0",
            uuid=target_uuid,
            name=send_name,
            time="{:d}".format(int(time.time())),
            simple="0"
        )
        try:
            self.drop_socket.send_unicode(unicode(etree.tostring(_vector)))  # @UndefinedVariable
        except:
            self.log(
                "error sending vector: {}".format(
                    process_tools.get_except_info(),
                ),
                logging_tools.LOG_LEVEL_CRITICAL,
            )

    def aggregate(self):
        mc = self.get_mc()
        self._update_struct()
        build_list = self._fetch_hosts(mc)
        v_dict = self._fetch_values(mc, build_list)
        self.build_vectors(build_list, v_dict)
