#
# this file is part of collectd-init
#
# Copyright (C) 2013-2017 Andreas Lang-Nevyjel init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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
""" definitions for collectd """


import json
import os
import rrdtool
import shutil
import subprocess
import time

from django.db.models import Q
from lxml.builder import E

from initat.cluster.backbone.models import device
from initat.collectd.collectd_types.base import value, PerfdataObject
from initat.collectd.config import global_config
from initat.tools import logging_tools, process_tools, rrd_tools, server_mixins


class FileCreator(object):
    def __init__(self, log_com):
        self.__log_com = log_com
        self.log("init file_creator")
        # dict, from {uuid, fqdn} to (uuid, fqdn, target_dir)
        cov_keys = [_key for _key in list(global_config.keys()) if _key.startswith("RRD_COVERAGE")]
        self.rrd_coverage = [global_config[_key] for _key in cov_keys]
        self.log("RRD coverage: {}".format(", ".join(self.rrd_coverage)))
        self.__step = global_config["RRD_STEP"]
        self.__heartbeat = self.__step * 2
        self.log("RRD step is {:d}, hearbeat is {:d} seconds".format(self.__step, self.__heartbeat))
        self.__cfs = ["MIN", "MAX", "AVERAGE"]
        self.__main_dir = global_config["RRD_DIR"]
        self.__created = {}

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[hm] {}".format(what), log_level)

    def sane_name(self, name):
        return name.replace("/", "_sl_")

    def get_mve_file_path(self, uuid, entry):
        # file path for mve entries
        _targ_dir = os.path.join(
            self.__main_dir,
            uuid,
            "collserver",
            "icval-{}.rrd".format(
                self.sane_name(entry.attrib["name"]),
            )
        )
        return _targ_dir

    def get_mvl_file_path(self, uuid, entry):
        # file path for mvl entries
        _targ_dir = os.path.join(
            self.__main_dir,
            uuid,
            "mvl",
            "part-{}.rrd".format(
                entry.attrib["name"],
            )
        )
        return _targ_dir

    def get_pd_file_path(self, uuid, pd_tuple):
        _t_obj = pd_tuple[0]
        # file path for pd entries
        _targ_dir = os.path.join(
            self.__main_dir,
            uuid,
            "perfdata",
            "ipd_{}{}.rrd".format(
                self.sane_name(_t_obj.file_name),
                "-{}".format(self.sane_name(pd_tuple[1])) if pd_tuple[1] else "",
            )
        )
        return _targ_dir

    def _create_target_file(self, _path, **kwargs):
        v_type = kwargs.get("v_type", "icval")
        # if v_type != "icval":
        #     print "v_type=", type(v_type), v_type
        if _path not in self.__created:
            if not os.path.exists(_path):
                if "step" in kwargs:
                    _step = kwargs["step"]
                    if "heartbeat" in kwargs:
                        _heartbeat = kwargs["heartbeat"]
                    else:
                        _heartbeat = _step * 2
                else:
                    _step, _heartbeat = (self.__step, self.__heartbeat)
                _base_dir = os.path.dirname(_path)
                if not os.path.isdir(_base_dir):
                    self.log("creating base_dir {}".format(_base_dir))
                    os.makedirs(_base_dir)
                _ds_list = self.get_ds_spec(v_type, _step, _heartbeat, cols=kwargs.get("cols", None))
                if _ds_list:
                    _rra_list = self.get_rra_spec(_step, _heartbeat)
                    try:
                        _args = [
                            str(_path),
                            "--step",
                            "{:d}".format(_step),
                        ] + _ds_list + _rra_list
                        rrdtool.create(*[str(_val) for _val in _args])
                    except rrdtool.error:
                        self.log(
                            "error creating file {}: {}".format(
                                _path,
                                process_tools.get_except_info()
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                        _path = None
                else:
                    self.log("no DS list for {}".format(str(v_type)), logging_tools.LOG_LEVEL_ERROR)
                    _path = None
            self.__created[_path] = True
        return _path if _path in self.__created else None

    def get_ds_spec(self, v_type, _step, _heartbeat, **kwargs):
        # get datasource spec
        if v_type == "icval":
            cols = kwargs.get("cols", None)
            if cols:
                # for multi-value icvals
                _rv = [
                    "{}:GAUGE:U:U".format(_name) for _name in cols
                ]
            else:
                # single-value icvals
                _rv = ["v:GAUGE:U:U"]
        elif isinstance(v_type, PerfdataObject):
            _t_obj = v_type
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
            self.log("unknown v_type '{}'".format(v_type), logging_tools.LOG_LEVEL_ERROR)
            _rv = []
        return [
            "DS:{}:{:d}:{}".format(
                ":".join(_val.split(":")[0:2]),
                _heartbeat,
                ":".join(_val.split(":")[2:])
            ) for _val in _rv
        ]

    def get_rra_spec(self, _step, _heartbeat):
        _rv = []
        for _key in self.rrd_coverage:
            _value = rrd_tools.RRA.parse_width_str(_key, _step, correct_zero_pdp=True)
            if _value:
                for _cf in self.__cfs:
                    _rv.append(
                        "RRA:{}:{:.1f}:{:d}:{:d}".format(
                            _cf,
                            0.1,
                            int(_value["pdp"]),
                            int(_value["rows"]),
                        )
                    )
        return _rv


class HostActiveRRD(object):
    def __init__(self, pk):
        self.set_time = time.time() - 3600
        self.pk = pk
        self._active = False

    def set_active_rrds(self):
        cur_time = time.time()
        _activate = False
        if not self._active:
            _activate = True
        elif abs(self.set_time - cur_time) > 60 * 15:
            _activate = True
        if _activate:
            self._active = True
            device.objects.filter(Q(pk=self.pk)).update(has_active_rrds=True)
            self.set_time = cur_time


class HostMatcher(object):
    def __init__(self, log_com):
        self.__log_com = log_com
        self.log("init host_matcher")
        self.EC = server_mixins.EggConsumeObject(self)
        self.EC.init(global_config)
        # dict, from {uuid, fqdn} to _dev
        self.__match = {}
        # dict: pk -> HostActiveRRD struct
        self.__active_dict = {}

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[hm] {}".format(what), log_level)

    def update(self, uuid_spec, host_name):
        # print in_vector, type(in_vector), etree.tostring(in_vector, pretty_print=True)
        # at first check for uuid
        match_dev = self.__match.get(uuid_spec, self.__match.get(host_name, None))
        if match_dev is None:
            match_mode = None
            try:
                match_dev = device.objects.get(Q(uuid=uuid_spec))
            except device.DoesNotExist:
                short_name = host_name.split(".")[0]
                if short_name != host_name:
                    # compare fqdn
                    dom_name = host_name.split(".", 1)[1]
                    try:
                        match_dev = device.objects.get(Q(name=short_name) & Q(domain_tree_node__full_name=dom_name))
                    except device.DoesNotExist:
                        match_dev = None
                    else:
                        match_mode = "fqdn"
                if match_dev is None:
                    # compare short name
                    try:
                        match_dev = device.objects.get(Q(name=short_name))
                    except device.DoesNotExist:
                        pass
                    except device.MultipleObjectsReturned:
                        self.log("spec {} / {} is not unique".format(uuid_spec, host_name), logging_tools.LOG_LEVEL_WARN)
                        match_dev = None
                    else:
                        match_mode = "name"
            else:
                match_mode = "uuid"
            if match_mode:
                _uuid, _fqdn = (match_dev.uuid, match_dev.full_name)
                self.log("found match via {} for device {} (pk {:d}, UUID {})".format(match_mode, _fqdn, match_dev.pk, _uuid))
                _target_dir = self.check_dir_structure(match_dev)
                self.__match[_uuid] = match_dev
                self.__match[_fqdn] = match_dev
                # source name
                self.__match[host_name] = match_dev
            else:
                match_dev = None
        if match_dev:
            if self.EC.consume("graph", match_dev):
                if match_dev.pk not in self.__active_dict:
                    self.__active_dict[match_dev.pk] = HostActiveRRD(match_dev.pk)
                self.__active_dict[match_dev.pk].set_active_rrds()
        return match_dev

    def check_dir_structure(self, match_dev):
        main_dir = global_config["RRD_DIR"]
        _fqdn_path = os.path.join(main_dir, match_dev.full_name)
        _uuid_path = os.path.join(main_dir, match_dev.uuid)
        _check_dict = {"u": _uuid_path, "f": _fqdn_path}
        _found = {}
        for _cn, _path in _check_dict.items():
            if os.path.isdir(_path):
                _found[_cn] = os.path.islink(_path)
        if not _found:
            # create structure
            self.log("creating disk structure (dir / link) for {}".format(str(match_dev)))
            os.mkdir(_uuid_path)
            os.symlink(match_dev.uuid, _fqdn_path)
        else:
            if "f" in _found and "u" in _found and not _found["u"] and _found["f"]:
                # all ok, do nothing
                pass
            else:
                # remove all links
                for _key, _value in _found.items():
                    if _value:
                        self.log("removing link {}".format(_check_dict[_key]))
                        os.unlink(_check_dict[_key])
                # remove all links
                _found = {_key: _value for _key, _value in _found.items() if not _value}
                if "f" in _found:
                    # rename fqdn
                    if os.path.exists(_check_dict["u"]):
                        self.log(
                            "target dir {} already existing, removing old dir {}".format(
                                _check_dict["u"],
                                _check_dict["f"],
                            ),
                            logging_tools.LOG_LEVEL_WARN
                        )
                        shutil.rmtree(_check_dict["u"])
                    self.log("renaming {} to {}".format(_check_dict["f"], _check_dict["u"]))
                    os.rename(_check_dict["f"], _check_dict["u"])
                    _found["u"] = False
                    del _found["f"]
                if "u" in _found and "f" not in _found and not _found["u"]:
                    self.log("creating FQDN link for {}".format(str(match_dev)))
                    os.symlink(match_dev.uuid, _fqdn_path)
                # if "f" not in _found:
                #    self.log("creating FQDN dir for {}".format(unicode(match_dev)))
                #    os.mkdir(_fqdn_path)
                # if "u" not in _found:
                #    self.log("creating UUID link for {}".format(unicode(match_dev)))
                #    os.symlink(match_dev.full_name, _uuid_path)
        # remove dead df. entries
        if os.path.exists(_uuid_path):
            for _dir, _dirs, _files in os.walk(_uuid_path):
                if _dir.endswith("df."):
                    try:
                        shutil.rmtree(_dir)
                    except IOError:
                        self.log("error removing {}: {}".format(_dir, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                    else:
                        self.log("removed tree below {}".format(_dir))
        return _fqdn_path


class ext_com(object):
    run_idx = 0

    def __init__(self, log_com, command, debug=False, name=None, detach=False):
        ext_com.run_idx += 1
        self.__name = name
        self.__detach = detach
        self.idx = ext_com.run_idx
        self.command = command
        self.popen = None
        self.debug = debug
        self.__log_com = log_com

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com(
            "[ec {:d}{}] {}".format(
                self.idx,
                ", {}".format(self.__name) if self.__name else "",
                what,
            ),
            log_level
        )

    def run(self):
        _success = True
        self.start_time = time.time()
        if self.__detach:
            self.popen = subprocess.Popen(
                self.command,
                bufsize=1,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                close_fds=True
            )
            self.log("start with pid {} (detached)".format(self.popen.pid))
        else:
            try:
                self.popen = subprocess.Popen(
                    self.command,
                    shell=True,
                    stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE
                )
                if self.debug:
                    self.log("start with pid {}".format(self.popen.pid))
            except OSError:
                self.log(
                    "cannot start job: {}".format(
                        process_tools.get_except_info(),
                    ),
                    logging_tools.LOG_LEVEL_CRITICAL,
                )
                _success = False
        return _success

    def communicate(self):
        if self.popen:
            try:
                return self.popen.communicate()
            except OSError:
                self.log("error in communicate: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
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


class CollectdHostInfo(object):
    def __init__(self, log_com, _dev):
        self.device = _dev
        self.__log_com = log_com
        self.name = _dev.full_name
        self.uuid = _dev.uuid
        self.__dict = {}
        # width of target files (not set for mve entries, set for name of entries for mvl entries)
        self.__width = {}
        self.last_update = None
        self.updates = 0
        self.stores = 0
        self.store_to_disk = _dev.store_rrd_data
        self.__target_files = {}
        self.log(
            "init host_info for {} ({}, RRD store is {})".format(
                self.name,
                self.uuid,
                "enabled" if self.store_to_disk else "disabled",
            )
        )
        self.__mc_timeout = global_config["MEMCACHE_TIMEOUT"]
        # for perfdata values, init with one to trigger send on first feed
        self.__perfdata_count = {}

    @staticmethod
    def setup(fc):
        import memcache
        CollectdHostInfo.entries = {}
        CollectdHostInfo.fc = fc
        CollectdHostInfo.mc = memcache.Client(["{}:{:d}".format(global_config["MEMCACHE_HOST"], global_config["MEMCACHE_PORT"])])

    @staticmethod
    def host_update(hi):
        cur_time = time.time()
        # delete old entries
        del_keys = [key for key, value in CollectdHostInfo.entries.items() if abs(value[0] - cur_time) > 15 * 60]
        if del_keys:
            for del_key in del_keys:
                del CollectdHostInfo.entries[del_key]
        # set new entry
        CollectdHostInfo.entries[hi.uuid] = (cur_time, hi.name)
        CollectdHostInfo.mc.set("cc_hc_list", json.dumps(CollectdHostInfo.entries))

    def mc_key(self):
        return "cc_hc_{}".format(self.uuid)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[h {}] {}".format(self.name, what), log_level)

    def target_file(self, name, **kwargs):
        _tf, _exists = self.__target_files[name]
        if not _exists:
            _created = CollectdHostInfo.fc._create_target_file(_tf, cols=self.__width.get(name, None), **kwargs)
            if _created:
                self.__target_files[name] = (_tf, True)
                return _tf
            else:
                return None
        else:
            return _tf

    def target_file_name(self, name):
        return self.__target_files[name][0]

    def feed_perfdata(self, pd_tuple):
        if pd_tuple not in self.__perfdata_count:
            self.__perfdata_count[pd_tuple] = 1
            self.__target_files[pd_tuple] = (CollectdHostInfo.fc.get_pd_file_path(self.uuid, pd_tuple), False)
        self.__perfdata_count[pd_tuple] -= 1
        if not self.__perfdata_count[pd_tuple]:
            self.__perfdata_count[pd_tuple] = 10
            return True
        else:
            return False

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

    def update(self, _xml, _fc):
        cur_time = time.time()
        old_keys = set(self.__dict.keys())
        # machine vector entries
        for entry in _xml.findall("mve"):
            cur_name = entry.attrib["name"]
            if cur_name not in self.__dict:
                # set new value
                self.__dict[cur_name] = value(cur_name)
            # update value
            self.__dict[cur_name].update(entry, cur_time)
            _tf = _fc.get_mve_file_path(self.uuid, entry)
            self.__target_files[cur_name] = (_tf, False)
            entry.attrib["file_name"] = _tf
        # machine vector lines
        for entry in _xml.findall("mvl"):
            # get timeout value (valid until)
            timeout = int(entry.get("timeout", int(cur_time) + 120))
            entry_name = entry.attrib["name"]
            _tf = _fc.get_mvl_file_path(self.uuid, entry)
            self.__target_files[entry_name] = (_tf, False)
            self.__width[entry_name] = []
            for _val in entry.findall("value"):
                val_key = _val.attrib["key"]
                cur_name = "{}.{}".format(entry_name, val_key)
                if cur_name not in self.__dict:
                    self.__dict[cur_name] = value(cur_name)
                # update value
                self.__dict[cur_name].update(_val, cur_time)
                self.__dict[cur_name].timeout = timeout
                self.__width[entry_name].append(val_key)
            entry.attrib["file_name"] = _tf

        # check for timeout
        to_keys = set(
            [
                key for key, _value in self.__dict.items() if _value.timeout and _value.timeout < cur_time
            ]
        )
        for to_key in to_keys:
            del self.__dict[to_key]
            if to_key in old_keys:
                old_keys.remove(to_key)
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
        json_vector = [_value.get_json() for _value in self.__dict.values()]
        CollectdHostInfo.host_update(self)
        # set and ignore errors, default timeout is 2 minutes
        CollectdHostInfo.mc.set(self.mc_key(), json.dumps(json_vector), self.__mc_timeout)

    def transform(self, key, value, cur_time):
        self.last_update = cur_time
        if key in self.__dict:
            try:
                # format: key, value, multi-value flag
                return (
                    self.__dict[key].name,
                    self.__dict[key].transform(value, cur_time),
                    False,
                )
            except (ValueError, KeyError):
                self.log("error transforming {}: {}".format(key, process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                return (None, None, False)
        else:
            # key not known, skip
            return (None, None, False)

    def get_values(self, _xml, simple):
        self.stores += 1
        if simple:
            tag_name, name_name, value_name = ("m", "n", "v")
        else:
            tag_name, name_name, value_name = ("mve", "name", "value")
        cur_time = time.time()
        values = [
            self.transform(
                entry.attrib[name_name],
                entry.attrib[value_name],
                cur_time
            ) for entry in _xml.findall(tag_name)
        ]
        if not simple:
            for entry in _xml.findall("mvl"):
                entry_name = entry.attrib["name"]
                values.append(
                    (
                        entry_name,
                        ":".join(
                            [
                                str(
                                    self.transform(
                                        "{}.{}".format(entry_name, _val.attrib["key"]),
                                        _val.attrib["value"],
                                        cur_time
                                    )[1]
                                ) for _val in entry.findall("value")
                            ]
                        ),
                        True
                    )
                )
        return values

    def __unicode__(self):
        return "{} ({})".format(self.name, self.uuid)
