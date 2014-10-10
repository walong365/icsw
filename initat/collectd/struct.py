#
# this file is part of collectd-init
#
# Copyright (C) 2013-2014 Andreas Lang-Nevyjel init.at
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

from initat.collectd.config import global_config
from initat.cluster.backbone.models import device_variable, device
from initat.collectd.collectd_types import value
import initat.collectd.collectd_types
from django.db.models import Q
from lxml.builder import E  # @UnresolvedImports
import memcache
import os
import rrdtool
import rrd_tools
import json
import logging_tools
import process_tools
import subprocess
import time

mc = memcache.Client(["{}:{:d}".format(global_config["MEMCACHE_HOST"], global_config["MEMCACHE_PORT"])])


class file_creator(object):
    def __init__(self, log_com):
        self.__log_com = log_com
        self.log("init host_matcher")
        # dict, from {uuid, fqdn} to (uuid, fqdn, target_dir)
        cov_keys = [_key for _key in global_config.keys() if _key.startswith("RRD_COVERAGE")]
        self.rrd_coverage = [global_config[_key] for _key in cov_keys]
        self.log("RRD coverage: {}".format(", ".join(self.rrd_coverage)))
        self.__step = global_config["RRD_STEP"]
        self.__heartbeat = self.__step * 2
        self.log("RRD step is {:d}, hearbeat is {:d} seconds".format(self.__step, self.__heartbeat))
        self.__cfs = ["MIN", "MAX", "AVERAGE"]
        self.__created = {}

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com(u"[hm] {}".format(what), log_level)

    def get_target_file(self, base_dir, plugin_name, type_instance, v_type, **kwargs):
        _subdir = os.path.join(
            plugin_name,
            "{}{}.rrd".format(
                v_type,
                "-{}".format(type_instance) if type_instance else ""
            )
        )
        if _subdir not in self.__created:
            _path = os.path.join(
                base_dir,
                _subdir,
            )
            if not os.path.exists(_path):
                if "step" in kwargs:
                    _step = kwargs["step"]
                    if "heartbeat" in kwargs:
                        _hearbeat = kwargs["heartbeat"]
                    else:
                        _hearbeat = _step * 2
                else:
                    _step, _heartbeat = (self.__step, self.__heartbeat)
                _base_dir = os.path.dirname(_path)
                if not os.path.isdir(_base_dir):
                    self.log("creating base_dir {}".format(_base_dir))
                    os.makedirs(_base_dir)
                _ds_list = self.get_ds_spec(v_type, _step, _heartbeat)
                if _ds_list:
                    _rra_list = self.get_rra_spec(_step, _heartbeat)
                    try:
                        _args = [
                            str(_path),
                            "--step",
                            "{:d}".format(self.__step),
                        ] + _ds_list + _rra_list
                        rrdtool.create(*_args)
                    except:
                        self.log("error creating file {}: {}".format(
                            _path,
                            process_tools.get_except_info()
                        ), logging_tools.LOG_LEVEL_ERROR)
                        _path = None
                else:
                    self.log("no DS list for {}".format(v_type), logging_tools.LOG_LEVEL_ERROR)
                    _path = None
            self.__created[_subdir] = _path
        return self.__created.get(_subdir, None)

    def get_ds_spec(self, v_type, _step, _heartbeat):
        # get datasource spec
        if v_type == "icval":
            _rv = ["v:GAUGE:U:U"]
        else:
            if v_type.startswith("ipd_"):
                _tn = "{}_pdata".format(v_type[4:])
                _t_obj = getattr(initat.collectd.collectd_types, _tn)()
                _rv = [
                    "{}:{}".format(
                        _e.get("name"),
                        _e.get("rrd_spec")
                    ) for _e in _t_obj.default_xml_info.xpath(
                        ".//value[@rrd_spec]",
                        smart_strings=False,
                    )
                ]
            else:
                _rv = []
        return ["DS:{}:{:d}:{}".format(":".join(_val.split(":")[0:2]), self.__heartbeat, ":".join(_val.split(":")[2:])) for _val in _rv]

    def get_rra_spec(self, _step, _heartbeat):
        _rv = []
        _dict = {_key: rrd_tools.RRA.parse_width_str(_key, _step) for _key in self.rrd_coverage}
        for _value in _dict.itervalues():
            for _cf in self.__cfs:
                _rv.append(
                    "RRA:{}:{:.1f}:{:d}:{:d}".format(
                        _cf,
                        0.1,
                        _value["pdp"],
                        _value["rows"],
                    )
                )
        return _rv


class host_matcher(object):
    def __init__(self, log_com):
        self.__log_com = log_com
        self.log("init host_matcher")
        # dict, from {uuid, fqdn} to (uuid, fqdn, target_dir)
        self.__match = {}

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com(u"[hm] {}".format(what), log_level)

    def update(self, uuid_spec):
        # print in_vector, type(in_vector), etree.tostring(in_vector, pretty_print=True)
        # at first check for uuid
        match_dev = None
        if uuid_spec not in self.__match:
            match_mode = None
            try:
                match_dev = device.objects.get(Q(uuid=uuid_spec))
            except device.DoesNotExist:
                if uuid_spec.count("."):
                    short_name, dom_name = (uuid_spec.split(".")[0], uuid_spec.split(".", 1)[1])
                    try:
                        match_dev = device.objects.get(Q(name=short_name) & Q(domain_tree_node__full_name=dom_name))
                    except device.DoesNotExist:
                        pass
                    else:
                        match_mode = "fqdn"
                else:
                    try:
                        match_dev = device.objects.get(Q(name=uuid_spec))
                    except device.DoesNotExist:
                        pass
                    except device.MultipleObjectsReturned:
                        self.log("spec {} is not unique".format(uuid_spec), logging_tools.LOG_LEVEL_WARN)
                    else:
                        match_mode = "name"
            else:
                match_mode = "uuid"
            if match_mode:
                _uuid, _fqdn = (match_dev.uuid, match_dev.full_name)
                self.log("found match via {} for device {} (pk {:d}, UUID {})".format(match_mode, _fqdn, match_dev.pk, _uuid))
                _target_dir = self.check_for_dirs(match_dev)
                self.__match[_uuid] = (_uuid, _fqdn, _target_dir)
                self.__match[_fqdn] = (_uuid, _fqdn, _target_dir)
        return self.__match.get(uuid_spec, (None, None, None))[2]

    def check_for_dirs(self, match_dev):
        main_dir = global_config["RRD_DIR"]
        _targ_dir = os.path.join(main_dir, match_dev.full_name)
        _check_list = [("u", match_dev.uuid), ("f", match_dev.full_name)]
        _found = {}
        for _cn, _cp in _check_list:
            _path = os.path.join(main_dir, _cp)
            if os.path.isdir(_path):
                _found[_cn] = os.path.islink(_path)
        if not _found:
            # create structure
            self.log("creating disk structure (dir / link) for {}".format(unicode(match_dev)))
            os.mkdir(_targ_dir)
            os.symlink(match_dev.full_name, os.path.join(main_dir, match_dev.uuid))
        else:
            if "f" not in _found:
                self.log("creating FQDN dir for {}".format(unicode(match_dev)))
                os.mkdir(_targ_dir)
            if "u" not in _found:
                self.log("creating UUID link for {}".format(unicode(match_dev)))
                os.symlink(match_dev.full_name, os.path.join(main_dir, match_dev.uuid))
        return _targ_dir

# a similiar structure is used in md-config-server/config.py
class var_cache(dict):
    def __init__(self, cdg, def_dict=None):
        super(var_cache, self).__init__(self)
        self.__cdg = cdg
        self.__def_dict = def_dict or {}

    def get_vars(self, cur_dev):
        global_key, dg_key, dev_key = (
            "GLOBAL",
            "dg__{:d}".format(cur_dev.device_group_id),
            "dev__{:d}".format(cur_dev.pk))
        if global_key not in self:
            # read global configs
            self[global_key] = {cur_var.name: cur_var.get_value() for cur_var in device_variable.objects.filter(Q(device=self.__cdg))}
            # update with def_dict
            for key, value in self.__def_dict.iteritems():
                if key not in self[global_key]:
                    self[global_key][key] = value
        if dg_key not in self:
            # read device_group configs
            self[dg_key] = {cur_var.name: cur_var.get_value() for cur_var in device_variable.objects.filter(Q(device=cur_dev.device_group.device))}
        if dev_key not in self:
            # read device configs
            self[dev_key] = {cur_var.name: cur_var.get_value() for cur_var in device_variable.objects.filter(Q(device=cur_dev))}
        ret_dict, info_dict = ({}, {})
        # for s_key in ret_dict.iterkeys():
        for key, key_n in [(dev_key, "d"), (dg_key, "g"), (global_key, "c")]:
            info_dict[key_n] = 0
            for s_key, s_value in self.get(key, {}).iteritems():
                if s_key not in ret_dict:
                    ret_dict[s_key] = s_value
                    info_dict[key_n] += 1
        return ret_dict, info_dict


class ext_com(object):
    run_idx = 0

    def __init__(self, log_com, command, name=None):
        ext_com.run_idx += 1
        self.__name = name
        self.idx = ext_com.run_idx
        self.command = command
        self.popen = None
        self.__log_com = log_com

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com(
            u"[ec {:d}{}] {}".format(
                self.idx,
                ", {}".format(self.__name) if self.__name else "",
                what,
            ),
            log_level
        )

    def run(self):
        self.start_time = time.time()
        self.popen = subprocess.Popen(self.command, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        self.log("start with pid {}".format(self.popen.pid))

    def communicate(self):
        if self.popen:
            try:
                return self.popen.communicate()
            except:
                self.log(u"error in communicate: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                return ("", "")
        else:
            return ("", "")

    def finished(self):
        self.result = self.popen.poll()
        if self.result is not None:
            self.end_time = time.time()
        return self.result

    def terminate(self):
        self.popen.kill()


class host_info(object):
    def __init__(self, log_com, uuid, name):
        self.__log_com = log_com
        self.name = name
        self.uuid = uuid
        self.__dict = {}
        self.last_update = None
        self.updates = 0
        self.stores = 0
        self.store_to_disk = True
        self.log("init host_info for {} ({})".format(name, uuid))
        self.__mc_timeout = global_config["MEMCACHE_TIMEOUT"]

    @staticmethod
    def setup():
        host_info.entries = {}

    @staticmethod
    def host_update(hi):
        cur_time = time.time()
        # delete old entries
        del_keys = [key for key, value in host_info.entries.iteritems() if abs(value[0] - cur_time) > 15 * 60]
        if del_keys:
            for del_key in del_keys:
                del host_info.entries[del_key]
        # set new entry
        host_info.entries[hi.uuid] = (cur_time, hi.name)
        mc.set("cc_hc_list", json.dumps(host_info.entries))

    def mc_key(self):
        return "cc_hc_{}".format(self.uuid)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com(u"[h {}] {}".format(self.name, what), log_level)

    def get_host_info(self):
        return E.host_info(
            name=self.name,
            uuid=self.uuid,
            last_update="{:d}".format(int(self.last_update or 0) or 0),
            keys="{:d}".format(len(self.__dict)),
            # update calls (full info)
            updates="{:d}".format(self.updates),
            # store calls (short info)
            stores="{:d}".format(self.stores),
            store_to_disk="1" if self.store_to_disk else "0",
        )

    def get_key_list(self, key_filter):
        h_info = self.get_host_info()
        for key in sorted(self.__dict.keys()):
            if key_filter.match(key):
                h_info.append(self.__dict[key].get_key_info())
        return h_info

    def update(self, _xml):
        cur_time = time.time()
        old_keys = set(self.__dict.keys())
        for entry in _xml.findall("mve"):
            cur_name = entry.attrib["name"]
            if cur_name not in self.__dict:
                # set new value
                self.__dict[cur_name] = value(cur_name)
            # update value
            self.__dict[cur_name].update(entry, cur_time)
        self._store_json_to_memcached()
        new_keys = set(self.__dict.keys())
        c_keys = old_keys ^ new_keys
        if c_keys:
            self.updates += 1
            del_keys = old_keys - new_keys
            for del_key in del_keys:
                del self.__dict[del_key]
            self.log("{} changed".format(logging_tools.get_plural("key", len(c_keys))), logging_tools.LOG_LEVEL_WARN)
            return True
        else:
            return False

    def update_ov(self, _xml):
        cur_time = time.time()
        for entry in _xml.findall("m"):
            cur_name = entry.attrib["n"]
            if cur_name in self.__dict:
                self.__dict[cur_name].update_ov(entry, cur_time)
        self._store_json_to_memcached()

    def _store_json_to_memcached(self):
        json_vector = [_value.get_json() for _value in self.__dict.itervalues()]
        host_info.host_update(self)
        # set and ignore errors, default timeout is 2 minutes
        mc.set(self.mc_key(), json.dumps(json_vector), self.__mc_timeout)

    def transform(self, key, value, cur_time):
        self.last_update = cur_time
        if key in self.__dict:
            try:
                return (
                    self.__dict[key].sane_name,
                    self.__dict[key].transform(value, cur_time),
                )
            except:
                self.log("error transforming {}: {}".format(key, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                return (None, None)
        else:
            # key not known, skip
            return (None, None)

    def get_values(self, _xml, simple):
        self.stores += 1
        if simple:
            tag_name, name_name, value_name = ("m", "n", "v")
        else:
            tag_name, name_name, value_name = ("mve", "name", "value")
        cur_time = time.time()
        values = [self.transform(entry.attrib[name_name], entry.attrib[value_name], cur_time) for entry in _xml.findall(tag_name)]
        return values

    def __unicode__(self):
        return "{} ({})".format(self.name, self.uuid)
