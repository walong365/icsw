# Copyright (C) 2007-2009,2013-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file belongs to the rrd-server package
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
""" data_store structure for rrd-grapher """

from django.db.models import Q
from initat.cluster.backbone.models import device
from initat.cluster.backbone.models import MachineVector, MVStructEntry, MVValueEntry
from initat.rrd_grapher.config import global_config
from lxml import etree  # @UnresolvedImport
from lxml.builder import E  # @UnresolvedImport
from initat.tools import logging_tools
import os
import pprint  # @UnusedImport
from initat.tools import process_tools
import re
import time


class compound_entry(object):
    def __init__(self, _xml):
        self.__re_list = []
        self.__key = _xml.attrib["key"]
        self.__info = _xml.attrib["info"]
        self.__order_key = _xml.get("order_key", None)
        for _key in _xml.findall("key_list/key"):
            _req = True if int(_key.get("required", "1")) else False
            self.__re_list.append(
                (
                    _req,
                    re.compile(_key.attrib["match"]),
                    re.compile(_key.attrib["nomatch"]) if "nomatch" in _key.attrib else None,
                    _key
                )
            )

    def __unicode__(self):
        return "compound {}".format(self.__key)

    def match(self, in_list):
        if self.__order_key:
            for _entry in self._match_multi(in_list):
                yield _entry
        else:
            for _entry in self._match_single(in_list):
                yield _entry

    def _match_single(self, in_list):
        # returns a list of matching keys
        _success = False
        if self.__re_list:
            _res = []
            _success = True
            for _req, _pos_re, _neg_re, _xml in self.__re_list:
                _found = [key for key in in_list if _pos_re.match(key)]
                if _neg_re is not None:
                    _ignore = [key for key in in_list if _neg_re.match(key)]
                    _found = [key for key in _found if key not in _ignore]
                if _req and not _found:
                    _success = False
                _res.extend([(key, _xml) for key in _found])
        if _success and _res:
            yield (_res, {})
        raise StopIteration

    def _match_multi(self, in_list):
        # returns a list of matching keys
        _success = False
        if self.__re_list:
            _res = []
            _success = True
            for _req, _pos_re, _neg_re, _xml in self.__re_list:
                _found = [(key, _pos_re.match(key)) for key in in_list if _pos_re.match(key)]
                if _neg_re is not None:
                    _ignore = [key for key in in_list if _neg_re.match(key)]
                    _found = [(key, _bla) for key, _bla in _found if key not in _ignore]
                if _req and not _found:
                    _success = False
                _res.extend([(key, _xml, _match.groupdict()) for key, _match in _found])
        _ok = self.__order_key
        _all_keys = set([_gd[_ok] for key, _xml, _gd in _res if _ok in _gd])
        for _key in _all_keys:
            yield (
                [
                    (key, _xml) for key, _xml, _gd in _res if _gd.get(_ok) == _key
                ],
                {
                    _ok: _key
                }
            )
        raise StopIteration

    def entry(self, result, ref_dict):
        m_list, gd = result
        for _key in [key for key, _xml in m_list]:
            # update dict with attribute dicts from the top-level node
            gd.update({_sk: _sv for _sk, _sv in ref_dict[key][0].iteritems() if _sk in ["info"]})
        # expand according to dict
        compound_key = self.__key.format(**gd)
        _info = "{} ({:d})".format(self.__info.format(**gd), len(m_list))
        # build info
        _build_info = [
            {
                "key": _s_key,
                "color": _xml.attrib["color"],
                "draw_type": _xml.get("draw_type", "LINE1"),
                "invert": _xml.get("invert", "0"),
            } for _s_key, _xml, in m_list
        ]
        _node = [
            {
                # should not be needed for display
                # "type": "compound",
                "fn": "",
                "ti": "",
                "key": compound_key,
                "is_active": True,
                "is_compound": True,
                "mvvs": [
                    {
                        "unit": "",
                        "info": _info,
                        "key": "",
                        "build_info": process_tools.compress_struct(_build_info),
                        # "color": _xml.attrib["color"],
                        # "draw_type": _xml.get("draw_type", "LINE1"),
                        # "invert": _xml.get("invert", "0"),
                    }  #
                ],
            }
        ]
        return _node


COMPOUND_NG = """
<element name="compound" xmlns="http://relaxng.org/ns/structure/1.0">
    <attribute name="key">
    </attribute>
    <attribute name="info">
    </attribute>
    <optional>
        <attribute name="order_key">
        </attribute>
    </optional>
    <element name="key_list">
        <oneOrMore>
            <element name="key">
                <attribute name="match">
                </attribute>
                <optional>
                    <attribute name="nomatch">
                    </attribute>
                </optional>
                <attribute name="color">
                </attribute>
                <optional>
                    <attribute name="required">
                    </attribute>
                </optional>
                <optional>
                    <attribute name="invert">
                    </attribute>
                </optional>
                <optional>
                    <attribute name="draw_type">
                    </attribute>
                </optional>
            </element>
        </oneOrMore>
    </element>
</element>
"""


class compound_tree(object):
    def __init__(self, log_com):
        self.__compounds = []
        self.__log_com = log_com
        compound_xml = """
<compounds>
    <compound key="compound.load" info="load">
        <key_list>
            <key match="^load\.1$" required="1" color="#ff0000"></key>
            <key match="^load\.5$" color="#4444cc"></key>
            <key match="^load\.15$" required="1" color="#44aa44" draw_type="LINE2"></key>
        </key_list>
    </compound>
    <compound key="compound.cpu" info="CPU">
        <key_list>
            <key match="^vms\.iowait$" required="0" color="#8dd3c7" draw_type="AREA1"></key>
            <key match="^vms\.sys(tem)*$" required="1" color="#ffffb3" draw_type="AREA1STACK"></key>
            <key match="^vms\.irq$" required="1" color="#bebada" draw_type="AREA1STACK"></key>
            <key match="^vms\.softirq$" required="1" color="#fb8072" draw_type="AREA1STACK"></key>
            <key match="^vms\.user$" required="1" color="#80b1d3" draw_type="AREA1STACK"></key>
            <key match="^vms\.steal$" required="0" color="#fbd462" draw_type="AREA1STACK"></key>
            <key match="^vms\.nice$" required="0" color="#fccde5" draw_type="AREA1STACK"></key>
            <key match="^vms\.idle$" required="1" color="#b3de69" draw_type="AREA1STACK"></key>
            <key match="^vms\.guest$" required="0" color="#ff0000" draw_type="LINE2"></key>
            <key match="^vms\.guest_nice$" required="0" color="#ffff00" draw_type="LINE2"></key>
        </key_list>
    </compound>
    <compound key="compound.sys.processes" info="Processes">
        <key_list>
            <key match="^proc\..*$" nomatch="proc\.(sleeping|total)" required="1" color="set312" draw_type="LINE1"></key>
        </key_list>
    </compound>
    <compound key="compound.sys.memory" info="System Memory">
        <key_list>
            <key match="mem\.used\.phys$" required="1" color="#eeeeee" draw_type="AREA1"></key>
            <key match="mem\.used\.buffers" required="1" color="#66aaff" draw_type="AREASTACK"></key>
            <key match="mem\.used\.cached" required="1" color="#eeee44" draw_type="AREASTACK"></key>
            <key match="mem\.free\.phys$" required="1" color="#44ff44" draw_type="AREA1STACK"></key>
            <!--<key match="mem\.used\.swap$" required="0" color="#ff4444" draw_type="AREASTACK"></key>-->
            <!--<key match="mem\.free\.swap$" required="0" color="#55ee55" draw_type="AREA1STACK"></key>-->
            <key match="mem\.used\.swap$" required="0" color="#ff4444" draw_type="LINE2"></key>
        </key_list>
    </compound>
    <compound key="compound.io" info="IO">
        <key_list>
            <key match="^net\.all\.rx$" required="1" color="#44ffffa0" draw_type="AREA1"></key>
            <key match="^net\.all\.tx$" required="1" invert="1" color="#ff4444a0" draw_type="AREA1"></key>
            <key match="^io\.total\.bytes\.read$" required="1" color="#4444ffa0" draw_type="AREA1"></key>
            <key match="^io\.total\.bytes\.written$" required="1" invert="1" color="#44ff44a0" draw_type="AREA1"></key>
        </key_list>
    </compound>
    <compound key="compound.icsw memory" info="CORVUS Memory">
        <key_list>
            <key match="^mem\.icsw\..*\.total$" required="1" color="rdgy11" draw_type="AREA1STACK"></key>
        </key_list>
    </compound>
    <compound key="compound.net.snmp_{key}" info="SNMP info for interface {key}" order_key="key">
        <key_list>
            <key match="^net\.snmp_(?P&lt;key&gt;.*)\.rx$" required="1" color="#00dd00" draw_type="AREA"></key>
            <key match="^net\.snmp_(?P&lt;key&gt;.*)\.tx$" required="1" color="#0000ff" draw_type="LINE1"></key>
            <key match="^net\.snmp_(?P&lt;key&gt;.*)\.errors$" required="1" color="#ff0000" draw_type="LINE2"></key>
        </key_list>
    </compound>
</compounds>
        """
        _ng = etree.RelaxNG(etree.fromstring(COMPOUND_NG))  # @UndefinedVariable
        comp_xml = etree.fromstring(compound_xml)  # @UndefinedVariable
        for _entry in comp_xml.findall("compound"):
            _valid = _ng.validate(_entry)
            if _valid:
                new_comp = compound_entry(_entry)
                self.__compounds.append(new_comp)
                self.log("added {}".format(unicode(new_comp)))
            else:
                self.log("compound is invalid: {}".format(str(_ng.error_log)), logging_tools.LOG_LEVEL_ERROR)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[comp] {}".format(what), log_level)

    def append_compounds(self, in_list):
        # build key list
        _refs = {}
        for _entry in in_list:
            for _sub in _entry["mvvs"]:
                if _sub["key"]:
                    _refs["{}.{}".format(_entry["key"], _sub["key"])] = (_entry, _sub)
                else:
                    _refs[_entry["key"]] = (_entry, _sub)
        # all keys
        all_keys = set(_refs.keys())
        _compounds = []
        for _comp in self.__compounds:
            for _result in _comp.match(all_keys):
                _compounds.extend(_comp.entry(_result, _refs))
        return _compounds


class DataStore(object):
    def __init__(self, machine_vector):
        self.mv = machine_vector
        self.pk = machine_vector.device.pk
        self.name = unicode(machine_vector.device.full_name)
        # link
        DataStore.__devices[self.pk] = self

    def vector_struct(self):
        _struct = []
        for mvs in MVStructEntry.objects.filter(Q(machine_vector=self.mv)).prefetch_related("mvvalueentry_set"):
            mvv_list = []
            for mvv in mvs.mvvalueentry_set.all():
                if not mvv.full_key:
                    mvv.full_key = "{}{}".format(mvs.key, ".{}".format(mvv.key) if mvv.key else "")
                    mvv.save(update_fields=["full_key"])
                    self.log("correcting full_key of {}".format(unicode(mvv)), logging_tools.LOG_LEVEL_WARN)
                mvv_list.append(
                    {
                        "unit": mvv.unit,
                        "info": mvv.info,
                        "key": mvv.key,
                        "build_info": "",
                    }
                )
            _struct.append(
                {
                    # not needed for display
                    # "type": mvs.se_type,
                    "fn": mvs.file_name,
                    "ti": mvs.type_instance,
                    "key": mvs.key,
                    "is_active": mvs.is_active,
                    "mvvs": mvv_list,
                }
            )
        return _struct

    @staticmethod
    def compound_struct(in_list):
        try:
            _comps = DataStore.compound_tree.append_compounds(in_list)
        except:
            for _line in process_tools.exception_info().log_lines:
                DataStore.g_log(_line, logging_tools.LOG_LEVEL_ERROR)
            _comps = []
        else:
            # pprint.pprint(_comps)
            pass
        return _comps

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        DataStore.process.log(
            "[ds {}] {}".format(
                self.name,
                what
            ),
            log_level
        )

    @staticmethod
    def has_machine_vector(dev_pk):
        if dev_pk not in DataStore.__devices:
            try:
                _mv = MachineVector.objects.get(
                    Q(device__pk=dev_pk) &
                    Q(device__enabled=True) &
                    Q(device__device_group__enabled=True)
                )
            except MachineVector.DoesNotExist:
                pass
            else:
                DataStore.__devices[dev_pk] = _mv
        return dev_pk in DataStore.__devices

    @staticmethod
    def present_pks():
        return DataStore.__devices.keys()

    @staticmethod
    def get_instance(pk):
        return DataStore.__devices[pk]

    @staticmethod
    def setup(srv_proc):
        DataStore.process = srv_proc
        DataStore.g_log("init")
        DataStore.debug = global_config["DEBUG"]
        # pk -> DataStore
        DataStore.__devices = {}
        # DataStore.store_dir = os.path.join(global_config["RRD_DIR"], "DataStore")
        # if not os.path.isdir(data_store.store_dir):
        #     os.mkdir(data_store.store_dir)
        # entry_re = re.compile("^(?P<full_name>.*)_(?P<pk>\d+).info.xml$")
        for mv in MachineVector.objects.filter(Q(device__enabled=True) & Q(device__device_group__enabled=True)):
            DataStore.g_log("building structure for {}".format(unicode(mv.device)))
            new_ds = DataStore(mv)
        DataStore.compound_tree = compound_tree(DataStore.g_log)

    @staticmethod
    def g_log(what, log_level=logging_tools.LOG_LEVEL_OK):
        DataStore.process.log("[ds] {}".format(what), log_level)
