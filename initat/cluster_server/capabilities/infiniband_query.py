# Copyright (C) 2015 Andreas Lang-Nevyjel
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
""" cluster-server, Infiniband query """

import commands
import time
import pprint
from lxml import etree
from lxml.builder import E
from django.db.models import Q

from initat.cluster.backbone.models import device
from initat.cluster_server.capabilities.base import bg_stuff
from initat.tools import process_tools, logging_tools
from initat.host_monitoring import hm_classes


def rewrite_key(key):
    _trans = [
        ("port", "Port", True),
        ("error", "Error", False),
        ("data", "Data", False),
        ("pkts", "Pkts", False),
        ("unicast", "Unicast", False),
        ("multicast", "Multicast", False),
        ("xmit", "Xmit", False),
        ("recv", "Rcv", False),
        ("discard", "Discard", False),
        ("wait", "Wait", False),
        ("symbol", "Symbol", False),
        ("counter", "Counter", False),
    ]
    for _src, _dst, _ignore in _trans:
        key = key.replace(_dst, "{}.".format(_src))
    _parts = key.split(".")
    key = [_src for _src, _dst, _ignore in _trans if _src in _parts and not _ignore]
    return ".".join(key)


class IBDataResult(object):
    def __init__(self):
        self.__feed_time = None
        self._speed = {}
        self._active_keys = []

    def feed(self, port_num, result):
        cur_time = time.time()
        if self.__feed_time is not None:
            diff_time = abs(cur_time - self.__feed_time)
            self._active_keys = sorted(result.keys())
            for _key in self._active_keys:
                if _key not in self._speed:
                    if _key.count("data"):
                        unit = "B/s"
                    else:
                        unit = "1/s"
                    self._speed[_key] = hm_classes.mvect_entry(
                        "net.port{}.{}".format(port_num, rewrite_key(_key)),
                        default=0.,
                        info="IB Readout for {} on port {}".format(_key, port_num),
                        unit=unit,
                        base=1000,
                    )
                # update value, update for 2 minutes
                self._speed[_key].update(result[_key] / diff_time, valid_until=cur_time + 2 * 60)
        else:
            self._speed = {}
            self._active_keys = []
        self.__feed_time = cur_time

    def build_mvect_entries(self, cur_time, port_num):
        _entries = []
        if self._speed:
            for _key in self._active_keys:
                _entries.append(self._speed[_key].build_xml(E))
        return _entries

    def show(self):
        _ret = []
        if self._speed:
            for _key in sorted(self._speed.keys()):
                if self._speed[_key] > 1000:
                    _ret.append("{}={:.2f}".format(_key, self._speed[_key]))
        return ", ".join(_ret) or None


class IBDataStoreDevice(object):
    def __init__(self, guid, name):
        self.guid = guid
        self.name = name
        # lookup name
        if self.name.count(" "):
            self.lu_name = self.name.split()[0]
        elif self.name.count(";"):
            self.lu_name = self.name.split(";")[1].split(":")[0]
        else:
            self.lu_name = self.name
        self.__ports = {}

    def show(self):
        _out = ["{} ({})".format(self.name, self.guid)]
        print " ".join(_out)
        for _port in sorted(self.__ports.keys()):
            _res = self.__ports[_port].show()
            if _res:
                print "   port {}: {}".format(_port, _res)

    def build_vector(self, dev_lu):
        cur_time = int(time.time())
        _dev = dev_lu.get(self.lu_name)
        if _dev is not None:
            _vector = E.machine_vector(
                time="{:d}".format(cur_time),
                name=_dev.full_name,
                simple="0",
                uuid=_dev.uuid,
            )
            for _port in sorted(self.__ports.keys()):
                _vector.extend(self.__ports[_port].build_mvect_entries(cur_time, _port))
            return _vector
        else:
            return None

    def feed(self, key, result):
        _port = key[1]
        if _port not in self.__ports:
            self.__ports[_port] = IBDataResult()
        self.__ports[_port].feed(_port, result)


class IBDataStore(object):
    def __init__(self):
        self.__guids = set()
        self.__devices = {}

    def show(self):
        for _key in sorted(self.__devices):
            self.__devices[_key].show()

    def build_vectors(self, dev_lu):
        _vectors = []
        for _key in sorted(self.__devices):
            _vec = self.__devices[_key].build_vector(dev_lu)
            if _vec is not None:
                _vectors.append(_vec)
        return _vectors

    def feed(self, lines):
        self.__target = None
        for _line in lines.split("\n"):
            _line = _line.rstrip()
            if _line and _line[0] != "#":
                if _line.startswith("ibwarn"):
                    print "WARN: {}".format(_line)
                elif _line[0] != " ":
                    self._parse_src(_line)
                else:
                    _key, _result = self._parse_data(_line)
                    if self.__target and _key[0] == self.__target.guid:
                        self.__target.feed(_key, _result)

    def _parse_data(self, line):
        _src, _data = [_part.strip() for _part in line.split(":", 1)]
        if _data[0] == "[":
            _data = _data[1:-1]
        _res = {}
        for _part in _data.split("] ["):
            _parts = _part.strip().split()
            _key, _value = (_parts[0], _parts[2])
            _res[_key] = float(_value)
        _sp = _src.split()
        _key = (_sp[1].lower(), int(_sp[3]))
        return _key, _res

    def _parse_src(self, line):
        self.__target = None
        _parts = line.strip().split(None, 4)
        _guid = _parts[3].lower()
        _name = _parts[4]
        if _name[0] in ["'", '"']:
            _name = _name[1:-1]
        if _guid not in self.__guids:
            self.__guids.add(_guid)
            new_dev = IBDataStoreDevice(_guid, _name)
            self.__devices[_guid] = new_dev
        self.__target = self.__devices[_guid]


class DeviceLookupEntry(object):
    def __init__(self, dev):
        self.init_time = time.time()
        self.name = dev.name
        self.full_name = dev.full_name
        self.uuid = dev.uuid
        self.pk = dev.pk

    def too_old(self, cur_time):
        if abs(cur_time - self.init_time) > 60 * 15:
            return True
        else:
            return False


class DeviceLookup(object):
    def __init__(self, log_com):
        self.__cache = {}
        self.__log_com = log_com
        self.log("init devicelookup")
        self.__unresolvable = set()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com(u"[DL] {}".format(what), log_level)

    def check_freshness(self):
        cur_time = time.time()
        to_delete = [key for key, value in self.__cache.iteritems() if value.too_old(cur_time)]
        if to_delete:
            self.log("removing {} from cache".format(logging_tools.get_plural("entry", len(to_delete))))
            for _to_del in to_delete:
                del self.__cache[_to_del]
        self.__unresolvable = set()

    def get(self, name):
        if name not in self.__cache:
            short_name = name.split(".")[0]
            match_dev, match_mode = (None, None)
            if short_name != name:
                # compare fqdn
                dom_name = name.split(".", 1)[1]
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
            if match_mode:
                self.__cache[name] = DeviceLookupEntry(match_dev)
        if name in self.__cache:
            return self.__cache[name]
        else:
            if name not in self.__unresolvable:
                self.__unresolvable.add(name)
                self.log("name '{}' is not resolveable".format(name), logging_tools.LOG_LEVEL_WARN)
            return None


class IBQueryClass(bg_stuff):
    class Meta:
        name = "infiniband_query"
        description = "Queries IB Network via ibqueryerrors"

    def init_bg_stuff(self):
        self.__dl = DeviceLookup(self.log)
        _ibq_bin = process_tools.find_file(("ibqueryerrors"))
        if _ibq_bin is None:
            self.log("no ibqueryerrors binary found, disabling", logging_tools.LOG_LEVEL_ERROR)
            self._ibq_bin = None
        else:
            self.log("found ibqueryerrors at {}".format(_ibq_bin))
            self._ibq_bin = _ibq_bin
            self.ibd = IBDataStore()

    def _call(self, cur_time, builder):
        m_vectors = []
        self.__dl.check_freshness()
        if self._ibq_bin:
            _cmd = "{} --counters --errors --details -k -K 2>/dev/null".format(process_tools.find_file("ibqueryerrors"))
            _stat, _out = commands.getstatusoutput(_cmd)
            self.ibd.feed(_out)
            m_vectors = self.ibd.build_vectors(self.__dl)
        else:
            m_vectors = []
        if False:
            m_vectors.append(
                E(
                    "machine_vector",
                    time="{:d}".format(int(cur_time)),
                    name="im",
                    simple="0",
                    uuid="5f0a0564-913a-40d1-97ee-22151ae13c7f",
                )
            )
            dummy_v = hm_classes.mvect_entry("test.value", default=0, info="test entry", unit="1", base=1, factor=1, value=4)
            m_vectors[0].append(
                dummy_v.build_xml(E)
            )
        # print etree.tostring(m_vectors[0], pretty_print=True)
        return m_vectors
