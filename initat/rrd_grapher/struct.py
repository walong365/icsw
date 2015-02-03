# Copyright (C) 2007-2009,2013-2014 Andreas Lang-Nevyjel, init.at
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
from initat.rrd_grapher.config import global_config
from lxml import etree  # @UnresolvedImport
from lxml.builder import E  # @UnresolvedImport
import logging_tools
import os
import pprint  # @UnusedImport
import process_tools
import re
import time


def resolve_key(dev_xml, key):
    _type, _key = key.split(":", 1)
    _split = _key.split(".")
    if _type in ["pde", "mvl"]:
        _node = dev_xml.xpath(".//{}[@name='{}']".format(_type, ".".join(_split[:len(_split) - 1])))[0]
        return {_ak: _av for _ak, _av in _node.attrib.iteritems()}
    elif _type == "mve":
        _node = dev_xml.xpath(".//mve[@name='{}']".format(_key))[0]
        return {_ak: _av for _ak, _av in _node.attrib.iteritems()}
    else:
        return {}


class compound_entry(object):
    def __init__(self, _xml):
        self.__re_list = []
        self.__name = _xml.attrib["name"]
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

    def entry(self, result, dev_xml):
        m_list, gd = result
        for _key in [key for key, _xml in m_list]:
            # update dict with attribute dicts from the top-level nodes
            gd.update(resolve_key(dev_xml, _key))
        # expand according to dict
        _name = self.__name.format(**gd)
        _info = self.__info.format(**gd)
        # cve: compount vector entry
        _node = E.cve(
            *[
                E.cve_entry(
                    key=_key,
                    color=_xml.attrib["color"],
                    draw_type=_xml.get("draw_type", "LINE1"),
                    invert=_xml.get("invert", "0"),
                ) for _key, _xml in m_list
            ],
            # keys="||".join(m_list),
            name="compound.{}".format(_name),
            part=_name,
            key=_name,
            info="{} ({:d})".format(
                _info,
                len(m_list),
            )
        )
        return _node


COMPOUND_NG = """
<element name="compound" xmlns="http://relaxng.org/ns/structure/1.0">
    <attribute name="name">
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
    def __init__(self):
        self.__compounds = []
        compound_xml = """
<compounds>
    <compound name="load" info="load">
        <key_list>
            <key match="^mve:load\.1$" required="1" color="#ff0000"></key>
            <key match="^mve:load\.5$" color="#4444cc"></key>
            <key match="^mve:load\.15$" required="1" color="#44aa44" draw_type="LINE2"></key>
        </key_list>
    </compound>
    <compound name="cpu" info="CPU">
        <key_list>
            <key match="^mve:vms\.iowait$" required="0" color="#8dd3c7" draw_type="AREA1"></key>
            <key match="^mve:vms\.sys(tem)*$" required="1" color="#ffffb3" draw_type="AREA1STACK"></key>
            <key match="^mve:vms\.irq$" required="1" color="#bebada" draw_type="AREA1STACK"></key>
            <key match="^mve:vms\.softirq$" required="1" color="#fb8072" draw_type="AREA1STACK"></key>
            <key match="^mve:vms\.user$" required="1" color="#80b1d3" draw_type="AREA1STACK"></key>
            <key match="^mve:vms\.steal$" required="0" color="#fbd462" draw_type="AREA1STACK"></key>
            <key match="^mve:vms\.nice$" required="0" color="#fccde5" draw_type="AREA1STACK"></key>
            <key match="^mve:vms\.idle$" required="1" color="#b3de69" draw_type="AREA1STACK"></key>
            <key match="^mve:vms\.guest$" required="0" color="#ff0000" draw_type="LINE2"></key>
            <key match="^mve:vms\.guest_nice$" required="0" color="#ffff00" draw_type="LINE2"></key>
        </key_list>
    </compound>
    <compound name="sys.processes" info="Processes">
        <key_list>
            <key match="^mve:proc\..*$" nomatch="proc\.(sleeping|total)" required="1" color="set312" draw_type="LINE1"></key>
        </key_list>
    </compound>
    <compound name="sys.memory" info="Memory">
        <key_list>
            <key match="mve:mem\.used\.phys$" required="1" color="#eeeeee" draw_type="AREA1"></key>
            <key match="mve:mem\.used\.buffers" required="1" color="#66aaff" draw_type="AREASTACK"></key>
            <key match="mve:mem\.used\.cached" required="1" color="#eeee44" draw_type="AREASTACK"></key>
            <key match="mve:mem\.free\.phys$" required="1" color="#44ff44" draw_type="AREA1STACK"></key>
            <!--<key match="mve:mem\.used\.swap$" required="0" color="#ff4444" draw_type="AREASTACK"></key>-->
            <!--<key match="mve:mem\.free\.swap$" required="0" color="#55ee55" draw_type="AREA1STACK"></key>-->
            <key match="mve:mem\.used\.swap$" required="0" color="#ff4444" draw_type="LINE2"></key>
        </key_list>
    </compound>
    <compound name="io" info="IO">
        <key_list>
            <key match="^mve:net\.all\.rx$" required="1" color="#44ffffa0" draw_type="AREA1"></key>
            <key match="^mve:net\.all\.tx$" required="1" invert="1" color="#ff4444a0" draw_type="AREA1"></key>
            <key match="^mve:io\.total\.bytes\.read$" required="1" color="#4444ffa0" draw_type="AREA1"></key>
            <key match="^mve:io\.total\.bytes\.written$" required="1" invert="1" color="#44ff44a0" draw_type="AREA1"></key>
        </key_list>
    </compound>
    <compound name="icsw memory" info="CORVUS Memory">
        <key_list>
            <key match="^mve:mem\.icsw\..*\.total$" required="1" color="rdgy11" draw_type="AREA1STACK"></key>
        </key_list>
    </compound>
    <compound name="net.snmp_{key}" info="SNMP {info}" order_key="key">
        <key_list>
            <key match="^mvl:net\.snmp_(?P&lt;key&gt;.*)\.rx$" required="1" color="#00dd00" draw_type="AREA"></key>
            <key match="^mvl:net\.snmp_(?P&lt;key&gt;.*)\.tx$" required="1" color="#0000ff" draw_type="LINE1"></key>
            <key match="^mvl:net\.snmp_(?P&lt;key&gt;.*)\.errors$" required="1" color="#ff0000" draw_type="LINE2"></key>
        </key_list>
    </compound>
</compounds>
        """
        _ng = etree.RelaxNG(etree.fromstring(COMPOUND_NG))  # @UndefinedVariable
        comp_xml = etree.fromstring(compound_xml)  # @UndefinedVariable
        for _entry in comp_xml.findall("compound"):
            _valid = _ng.validate(_entry)
            if _valid:
                self.__compounds.append(compound_entry(_entry))
            else:
                print("compound is invalid: {}".format(str(_ng.error_log)))

    def append_compounds(self, dev_xml):
        # machine vector entries
        all_keys = set()
        for _mve_entry in dev_xml.xpath(".//mve[@active='1']"):
            all_keys.add(
                "mve:{}".format(_mve_entry.attrib["name"])
            )
        # performance data or wide machine vector entries
        for _pde_mvl_entry in dev_xml.xpath(".//pde[@active='1']|.//mvl[@active='1']"):
            _name = _pde_mvl_entry.attrib["name"]
            _info = _pde_mvl_entry.get("info")
            for _value in _pde_mvl_entry.findall("value"):
                #print _value.attrib
                all_keys.add(
                    "{}:{}.{}".format(
                        _pde_mvl_entry.tag,
                        _name,
                        _value.attrib["key"],
                    )
                )
        top_el = E.machine_vector()
        _added = 0
        # print "*", len(in_list)
        for _comp in self.__compounds:
            for _result in _comp.match(all_keys):
                top_el.append(_comp.entry(_result, dev_xml))
                _added += 1
        if _added:
            return top_el
        else:
            return None


class data_store(object):
    def __init__(self, cur_dev):
        self.pk = cur_dev.pk
        self.name = unicode(cur_dev.full_name)
        # name of rrd-files on disk
        self.store_name = ""
        self.xml_vector = E.machine_vector()

    def restore(self):
        try:
            self.xml_vector = etree.fromstring(file(self.data_file_name(), "r").read())  # @UndefinedVariable
        except:
            self.log("cannot interpret XML: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            self.xml_vector = E.machine_vector()
        else:
            # for pure-pde vectors no store name is set
            self.store_name = self.xml_vector.attrib.get("store_name", "")
            all_mves = self.xml_vector.xpath(".//mve/@name", smart_strings=False)
            changed = False
            # check for duplicates
            if len(all_mves) != len(set(all_mves)):
                self.log("found duplicate entries, removing them")
                removed = 0
                for cur_mve in all_mves:
                    sub_list = self.xml_vector.xpath(".//mve[@name='{}']".format(cur_mve), smart_strings=False)
                    for sub_entry in sub_list[:-1]:
                        sub_entry.getparent().remove(sub_entry)
                        removed += 1
                        changed = True
                self.log("removed {}".format(logging_tools.get_plural("entry", removed)))
            # check for entries ending with Perfdata
            del_entries = [_entry for _entry in self.xml_vector.xpath(".//pde[@name]") if _entry.attrib["name"].endswith("Perfdata")]
            if del_entries:
                changed = True
                self.log("removing {}".format(logging_tools.get_plural("stale Perfdata entries", len(del_entries))))
                for _del in del_entries:
                    _del.getparent().remove(_del)
            for fix_el in self.xml_vector.xpath(".//*[@file_name and not(@active)]", smart_strings=False):
                fix_el.attrib["active"] = "1"
                changed = True
            while True:
                _cc = self.xml_vector.find(".//compound")
                if _cc is not None:
                    _cc.getparent().remove(_cc)
                    self.log("remove compound entry from on-disk storage", logging_tools.LOG_LEVEL_WARN)
                    changed = True
                else:
                    break
            if changed:
                self.log("vector was changed on load, storing")
                self.store()
            # changed
        # send a copy to the grapher
        self.sync_to_grapher()

    def feed(self, in_vector):
        # self.xml_vector = in_vector
        if self.store_name != in_vector.attrib["name"]:
            self.log(
                "changing store_name from '{}' to '{}'".format(
                    self.store_name,
                    in_vector.attrib["name"]
                )
            )
            self.store_name = in_vector.attrib["name"]
            self.xml_vector.attrib["store_name"] = self.store_name
        old_mve_keys = set(self.xml_vector.xpath(".//mve/@name", smart_strings=False))
        old_mvl_keys = set(self.xml_vector.xpath(".//mvl/@name", smart_strings=False))
        rrd_dir = global_config["RRD_DIR"]
        # MVEs
        for entry in in_vector.findall("mve"):
            cur_name = entry.attrib["name"]
            cur_entry = self.xml_vector.find(".//mve[@name='{}']".format(cur_name))
            if cur_entry is None:
                cur_entry = E.mve(
                    name=cur_name,
                    sane_name=cur_name.replace("/", "_sl_"),
                    init_time="{:d}".format(int(time.time())),
                )
                self.xml_vector.append(cur_entry)
            self._update_mve_entry(cur_entry, entry, rrd_dir)
        # MVLs
        for entry in in_vector.findall("mvl"):
            cur_name = entry.attrib["name"]
            cur_entry = self.xml_vector.find(".//mvl[@name='{}']".format(cur_name))
            if cur_entry is None:
                cur_entry = E.mvl(
                    name=cur_name,
                    sane_name=cur_name.replace("/", "_sl_"),
                    init_time="{:d}".format(int(time.time())),
                )
                for _cur_idx, _value in enumerate(entry):
                    cur_entry.append(
                        E.value(
                            key=_value.get("key"),
                        )
                    )
                self.xml_vector.append(cur_entry)
            self._update_mvl_entry(cur_entry, entry, rrd_dir)
        new_mve_keys = set(self.xml_vector.xpath(".//mve/@name", smart_strings=False))
        new_mvl_keys = set(self.xml_vector.xpath(".//mvl/@name", smart_strings=False))
        self.log(
            "mve: {:d} keys total {:d} changed, mvl: {:d} keys total, {:d} changed".format(
                len(new_mve_keys),
                len(new_mve_keys ^ old_mve_keys),
                len(new_mvl_keys),
                len(new_mvl_keys ^ old_mvl_keys),
            )
        )
        self.store()

    def feed_pd(self, host_name, pd_type, pd_info, file_name):
        # we ignore the global store name for perfdata stores
        old_keys = set(self.xml_vector.xpath(".//pde/@name", smart_strings=False))
        rrd_dir = global_config["RRD_DIR"]
        # print host_name, pd_type
        # print etree.tostring(pd_info, pretty_print=True)
        type_instance = pd_info.get("type_instance", "")
        # only one entry
        if type_instance:
            cur_entry = self.xml_vector.xpath(".//pde[@name='{}' and @type_instance='{}']".format(pd_type, type_instance), smart_strings=False)
        else:
            cur_entry = self.xml_vector.xpath(".//pde[@name='{}']".format(pd_type), smart_strings=False)
        cur_entry = cur_entry[0] if cur_entry else None
        if cur_entry is None:
            # create new entry
            cur_entry = E.pde(
                name=pd_type,
                host=host_name,
                type_instance=pd_info.get("type_instance", ""),
                init_time="{:d}".format(int(time.time())),
            )
            for _cur_idx, entry in enumerate(pd_info):
                cur_entry.append(
                    E.value(
                        name=entry.get("name"),
                    )
                )
            self.xml_vector.append(cur_entry)
        else:
            cur_entry.attrib["type_instance"] = pd_info.get("type_instance", "")
        self._update_pd_entry(cur_entry, pd_info, rrd_dir, file_name)
        new_keys = set(self.xml_vector.xpath(".//pde/@name", smart_strings=False))
        c_keys = old_keys ^ new_keys
        if c_keys:
            self.log("pde: {:d} keys total, {:d} keys changed".format(len(new_keys), len(c_keys)))
        # else:
        #    too verbose
        #    self.log("pde: %d keys total" % (len(new_keys)))
        self.store()

    def _update_pd_entry(self, entry, src_entry, rrd_dir, file_name):
        entry.attrib["last_update"] = "%d" % (time.time())
        entry.attrib["active"] = "1"
        entry.attrib["file_name"] = file_name
        if len(entry) == len(src_entry):
            for v_idx, (cur_value, src_value) in enumerate(zip(entry, src_entry)):
                for key, def_value in [
                    ("info", "performance_data"),
                    ("v_type", "f"),
                    ("unit", "1"),
                    ("name", None),
                    ("index", "{:d}".format(v_idx))
                ]:
                    cur_value.attrib[key] = src_value.get(key, def_value)
                cur_value.attrib["key"] = src_value.get("key", cur_value.attrib["name"])
        else:
            self.log("number of pd entries differ: {:d} != {:d}".format(len(entry), len(src_entry)), logging_tools.LOG_LEVEL_CRITICAL)

    def _update_mve_entry(self, entry, src_entry, rrd_dir):
        # last update time
        entry.attrib["last_update"] = "{:d}".format(int(time.time()))
        entry.attrib["active"] = "1"
        # if "file_name" in src_entry.attrib:
        entry.attrib["file_name"] = src_entry.attrib["file_name"]
        # else:
        #    entry.attrib["file_name"] = os.path.join(rrd_dir, self.store_name, "collserver", "icval-{}.rrd".format(entry.attrib["sane_name"]))
        for key, def_value in [
            ("info", None),
            ("v_type", None),
            ("full", entry.get("name")),
            ("unit", "1"),
            ("base", "1"),
            ("factor", "1")
        ]:
            entry.attrib[key] = src_entry.get(key, def_value)

    def _update_mvl_entry(self, entry, src_entry, rrd_dir):
        entry.attrib["last_update"] = "{:d}".format(int(time.time()))
        entry.attrib["active"] = "1"
        if "info" in src_entry.attrib:
            entry.attrib["info"] = src_entry.attrib["info"]
        else:
            del entry.attrib["info"]
        entry.attrib["file_name"] = src_entry.attrib["file_name"]
        if len(entry) == len(src_entry):
            for _v_idx, (cur_value, src_value) in enumerate(zip(entry, src_entry)):
                for key, def_value in [
                    ("info", None),
                    ("v_type", "f"),
                    ("unit", "1"),
                    ("key", None),
                    ("base", "1"),
                    ("factor", "1")
                ]:
                    cur_value.attrib[key] = src_value.get(key, def_value)
                cur_value.attrib["key"] = src_value.attrib["key"]
        else:
            self.log(
                "number of mvl entries differ: {:d} != {:d}, replacing childs".format(
                    len(entry),
                    len(src_entry)
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            for _val in entry:
                entry.remove(_val)
            for _val in src_entry:
                entry.append(_val)

    def store(self):
        file(self.data_file_name(), "wb").write(etree.tostring(self.xml_vector))  # @UndefinedVariable
        # sync XML to grapher
        self.sync_to_grapher()

    def sync_to_grapher(self):
        _compound = self.compound_xml_vector()
        if _compound is not None:
            _compound = etree.tostring(_compound)  # @UndefinedVariable
        data_store.process.send_to_process(
            "graph",
            "xml_info",
            self.pk,
            etree.tostring(self.xml_vector),  # @UndefinedVariable
            _compound  # @UndefinedVariable
        )

    def data_file_name(self):
        return os.path.join(data_store.store_dir, "{}_{:d}.info.xml".format(self.name, self.pk))

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        data_store.process.log(
            "[ds {}] {}".format(
                self.name,
                what
            ),
            log_level
        )

    @staticmethod
    def has_rrd_xml(dev_pk):
        return dev_pk in data_store.__devices

    @staticmethod
    def present_pks():
        return data_store.__devices.keys()

    def compound_xml_vector(self):
        cur_xml = self.xml_vector
        # remove current compound, should never happen (only when wrong data is written to disk)
        while True:
            _cc = cur_xml.find(".//compound")
            if _cc is not None:
                _cc.getparent().remove(_cc)
            else:
                break
        return compound_tree().append_compounds(cur_xml)

    def _create_struct(self, top_node, full_key):
        parts = full_key.split(".")[:-1]
        cur_node = top_node
        for part_idx, part in enumerate(parts):
            cur_node = top_node.find("*[@part='{}']".format(part))
            if cur_node is None:
                cur_node = E.entry(name=".".join(parts[:part_idx + 1]), part=part)
                top_node.append(cur_node)
            top_node = cur_node
        return cur_node

    def _expand_info(self, entry):
        info = entry.attrib["info"]
        parts = entry.attrib["name"].split(".")
        for idx in xrange(len(parts)):
            info = info.replace("$%d" % (idx + 1), parts[idx])
        return info

    @staticmethod
    def get_instance(pk):
        return data_store.__devices[pk]

    @staticmethod
    def setup(srv_proc):
        data_store.process = srv_proc
        data_store.g_log("init")
        data_store.debug = global_config["DEBUG"]
        # pk -> data_store
        data_store.__devices = {}
        data_store.store_dir = os.path.join(global_config["RRD_DIR"], "data_store")
        if not os.path.isdir(data_store.store_dir):
            os.mkdir(data_store.store_dir)
        entry_re = re.compile("^(?P<full_name>.*)_(?P<pk>\d+).info.xml$")
        for entry in os.listdir(data_store.store_dir):
            entry_m = entry_re.match(entry)
            if entry_m:
                full_name, pk = (entry_m.group("full_name"), int(entry_m.group("pk")))
                try:
                    new_ds = data_store(device.objects.get(Q(pk=pk)))
                    new_ds.restore()
                except:
                    data_store.g_log(
                        "cannot initialize data_store for {}: {}".format(
                            full_name,
                            process_tools.get_except_info()
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                else:
                    data_store.__devices[pk] = new_ds
                    data_store.g_log(
                        "recovered info for {} from disk (pk {:d}, memory usage now {})".format(
                            full_name,
                            pk,
                            logging_tools.get_size_str(process_tools.get_mem_info())
                        )
                    )
            else:
                data_store.g_log(
                    "ignoring dir entry '{}'".format(
                        entry
                    ),
                    logging_tools.LOG_LEVEL_WARN
                )

    @staticmethod
    def g_log(what, log_level=logging_tools.LOG_LEVEL_OK):
        data_store.process.log("[ds] {}".format(what), log_level)

    @staticmethod
    def feed_perfdata(name, pd_type, pd_info, file_name):
        match_dev = None
        if name.count("."):
            full_name, short_name, dom_name = (name, name.split(".")[0], name.split(".", 1)[1])
        else:
            full_name, short_name, dom_name = (None, name, None)
        if full_name:
            # try according to full_name
            try:
                match_dev = device.objects.get(Q(name=short_name) & Q(domain_tree_node__full_name=dom_name))
            except device.DoesNotExist:
                pass
            else:
                match_mode = "fqdn"
        if match_dev is None:
            try:
                match_dev = device.objects.get(Q(name=short_name))
            except device.DoesNotExist:
                pass
            except device.MultipleObjectsReturned:
                pass
            else:
                match_mode = "name"
        if match_dev:
            if data_store.debug:
                data_store.g_log(
                    "found device {} ({}) for pd_type={}".format(
                        unicode(match_dev),
                        match_mode,
                        pd_type
                    )
                )
            if match_dev.pk not in data_store.__devices:
                data_store.__devices[match_dev.pk] = data_store(match_dev)
            data_store.__devices[match_dev.pk].feed_pd(name, pd_type, pd_info, file_name)
        else:
            data_store.g_log(
                "no device found (name={}, pd_type={})".format(name, pd_type),
                logging_tools.LOG_LEVEL_ERROR
            )

    @staticmethod
    def feed_vector(in_vector):
        # print in_vector, type(in_vector), etree.tostring(in_vector, pretty_print=True)
        # at first check for uuid
        match_dev = None
        if "uuid" in in_vector.attrib:
            uuid = in_vector.attrib["uuid"]
            try:
                match_dev = device.objects.get(Q(uuid=uuid))
            except device.DoesNotExist:
                pass
            else:
                match_mode = "uuid"
        if match_dev is None and "name" in in_vector.attrib:
            name = in_vector.attrib["name"]
            if name.count("."):
                full_name, short_name, dom_name = (name, name.split(".")[0], name.split(".", 1)[1])
            else:
                full_name, short_name, dom_name = (None, name, None)
            if full_name:
                # try according to full_name
                try:
                    match_dev = device.objects.get(Q(name=short_name) & Q(domain_tree_node__full_name=dom_name))
                except device.DoesNotExist:
                    pass
                else:
                    match_mode = "fqdn"
            if match_dev is None:
                try:
                    match_dev = device.objects.get(Q(name=short_name))
                except device.DoesNotExist:
                    pass
                except device.MultipleObjectsReturned:
                    pass
                else:
                    match_mode = "name"
        if match_dev:
            if data_store.debug:
                data_store.g_log("found device %s (%s)" % (unicode(match_dev), match_mode))
            if "name" in in_vector.attrib:
                if match_dev.pk not in data_store.__devices:
                    data_store.__devices[match_dev.pk] = data_store(match_dev)
                data_store.__devices[match_dev.pk].feed(in_vector)
            else:
                data_store.g_log("no name in vector for %s, discarding" % (unicode(match_dev)), logging_tools.LOG_LEVEL_ERROR)
        else:
            data_store.g_log(
                "no device found (%s: %s)" % (
                    logging_tools.get_plural("key", len(in_vector.attrib)),
                    ", ".join(["{}={}".format(key, str(value)) for key, value in in_vector.attrib.iteritems()])
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
