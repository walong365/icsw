#!/usr/bin/python-init -Ot
#
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
import copy
import logging_tools
import os
import pprint  # @UnusedImport
import process_tools
import re
import time


class compound_entry(object):
    def __init__(self, _xml):
        self.__re_list = []
        self.__name = _xml.attrib["name"]
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
        # returns a list of matching keys
        _success = False
        # print "-"*20
        # print self.__name
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
            return _res
        else:
            return []

    def entry(self, m_list):
        # cve: compount vector entry
        return E.cve(
            *[
                E.cve_entry(
                    key=_key,
                    color=_xml.attrib["color"],
                    draw_type=_xml.get("draw_type", "LINE1"),
                    invert=_xml.get("invert", "0"),
                ) for _key, _xml in m_list
            ],
            # keys="||".join(m_list),
            name="compound.{}".format(self.__name),
            part=self.__name,
            info="{} ({:d})".format(
                self.__name,
                len(m_list),
            )
        )


COMPOUND_NG = """
<element name="compound" xmlns="http://relaxng.org/ns/structure/1.0">
    <attribute name="name">
    </attribute>
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
    <compound name="load">
        <key_list>
            <key match="^load\.1$" required="1" color="#ff0000"></key>
            <key match="^load\.5$" color="#4444cc"></key>
            <key match="^load\.15$" required="1" color="#44aa44" draw_type="LINE2"></key>
        </key_list>
    </compound>
    <compound name="cpu">
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
    <compound name="processes">
        <key_list>
            <key match="^proc\..*$" nomatch="proc\.(sleeping|total)" required="1" color="set312" draw_type="LINE1"></key>
        </key_list>
    </compound>
    <compound name="memory">
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
    <compound name="io">
        <key_list>
            <key match="^net\.all\.rx$" required="1" color="#44ffffa0" draw_type="AREA1"></key>
            <key match="^net\.all\.tx$" required="1" invert="1" color="#ff4444a0" draw_type="AREA1"></key>
            <key match="^io\.total\.bytes\.read$" required="1" color="#4444ffa0" draw_type="AREA1"></key>
            <key match="^io\.total\.bytes\.written$" required="1" invert="1" color="#44ff44a0" draw_type="AREA1"></key>
        </key_list>
    </compound>
    <compound name="icsw memory">
        <key_list>
            <key match="^mem\.icsw\..*\.total$" required="1" color="rdgy11" draw_type="AREA1STACK"></key>
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

    def append_compounds(self, top_el, in_list):
        _added = 0
        # print "*", len(in_list)
        for _comp in self.__compounds:
            m_list = _comp.match(in_list)
            if m_list:
                top_el.append(_comp.entry(m_list))
                _added += 1
        return _added
    # print "*", etree.tostring(top_el)


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
            for fix_el in self.xml_vector.xpath(".//*[@file_name and not(@active)]", smart_strings=False):
                fix_el.attrib["active"] = "1"
                changed = True
            if changed:
                self.log("vector was changed on load, storing")
                self.store()
            # changed
        # send a copy to the grapher
        self.sync_to_grapher()

    def feed(self, in_vector):
        # self.xml_vector = in_vector
        if self.store_name != in_vector.attrib["name"]:
            self.log("changing store_name from '%s' to '%s'" % (
                self.store_name,
                in_vector.attrib["name"]))
            self.store_name = in_vector.attrib["name"]
            self.xml_vector.attrib["store_name"] = self.store_name
        old_keys = set(self.xml_vector.xpath(".//mve/@name", smart_strings=False))
        rrd_dir = global_config["RRD_DIR"]
        for entry in in_vector.findall("mve"):
            cur_name = entry.attrib["name"]
            cur_entry = self.xml_vector.find(".//mve[@name='%s']" % (cur_name))
            if cur_entry is None:
                cur_entry = E.mve(
                    name=cur_name,
                    sane_name=cur_name.replace("/", "_sl_"),
                    init_time="%d" % (time.time()),
                )
                self.xml_vector.append(cur_entry)
            self._update_entry(cur_entry, entry, rrd_dir)
        new_keys = set(self.xml_vector.xpath(".//mve/@name", smart_strings=False))
        c_keys = old_keys ^ new_keys
        if c_keys:
            self.log("mve: %d keys total, %d keys changed" % (len(new_keys), len(c_keys)))
        else:
            self.log("mve: %d keys total" % (len(new_keys)))
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
            cur_entry = self.xml_vector.xpath(".//pde[@name='%s' and @type_instance='%s']" % (pd_type, type_instance), smart_strings=False)
        else:
            cur_entry = self.xml_vector.xpath(".//pde[@name='%s']" % (pd_type), smart_strings=False)
        cur_entry = cur_entry[0] if cur_entry else None
        if cur_entry is None:
            # create new entry
            cur_entry = E.pde(
                name=pd_type,
                host=host_name,
                type_instance=pd_info.get("type_instance", ""),
                init_time="%d" % (time.time()),
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

    def _update_entry(self, entry, src_entry, rrd_dir):
        for key, def_value in [
            ("info", None),
            ("v_type", None),
            ("full", entry.get("name")),
            ("unit", "1"),
            ("base", "1"),
            ("factor", "1")
        ]:
            entry.attrib[key] = src_entry.get(key, def_value)
        # last update time
        entry.attrib["last_update"] = "{:d}".format(int(time.time()))
        entry.attrib["active"] = "1"
        if "file_name" in src_entry.attrib:
            entry.attrib["file_name"] = src_entry.attrib["file_name"]
        else:
            entry.attrib["file_name"] = os.path.join(rrd_dir, self.store_name, "collserver", "icval-{}.rrd".format(entry.attrib["sane_name"]))

    def store(self):
        file(self.data_file_name(), "wb").write(etree.tostring(self.xml_vector))  # @UndefinedVariable
        # sync XML to grapher
        self.sync_to_grapher()

    def sync_to_grapher(self):
        data_store.process.send_to_process(
            "graph",
            "xml_info",
            self.pk,
            etree.tostring(self.struct_xml_vector("graph"))  # @UndefinedVariable
        )

    def data_file_name(self):
        return os.path.join(data_store.store_dir, "%s_%d.info.xml" % (self.name, self.pk))

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        data_store.process.log("[ds %s] %s" % (
            self.name,
            what), log_level)

    @staticmethod
    def has_rrd_xml(dev_pk):
        return dev_pk in data_store.__devices

    @staticmethod
    def present_pks():
        return data_store.__devices.keys()

    def struct_xml_vector(self, mode):
        """
        rebuild the flat tree to a structured tree
        """
        # mode is one of web or graph
        if mode not in ["web", "graph"]:
            raise ValueError("mode '{}' is not correct".format(mode))
        # web mode: show tree in webfrontend
        web_mode = mode == "web"
        # graph mode: sent shortened representation to graph process
        graph_mode = mode == "graph"
        cur_xml = self.xml_vector
        _ct = compound_tree()
        all_keys = set(cur_xml.xpath(".//mve[@active='1']/@name", smart_strings=False))
        xml_vect, lu_dict = (E.machine_vector(), {})
        compound_top = self._create_struct(xml_vect, "{}.{}".format("compound", ""))
        any_added = _ct.append_compounds(compound_top, all_keys)
        if not any_added:
            # remove compound
            compound_top.getparent().remove(compound_top)
        for key in sorted(all_keys):
            parts = key.split(".")
            s_dict, s_xml = (lu_dict, xml_vect)
            for part in parts:
                if part not in s_dict:
                    new_el = E.entry(part=part)
                    s_xml.append(new_el)
                    s_dict[part] = (new_el, {})
                s_xml, s_dict = s_dict[part]
            add_entry = copy.deepcopy(cur_xml.find(".//mve[@name='%s']" % (key)))
            # remove unneded entries, depending on mode
            if web_mode:
                for rem_attr in ["file_name", "last_update", "sane_name"]:
                    if rem_attr in add_entry.attrib:
                        del add_entry.attrib[rem_attr]
            if "info" in add_entry.attrib:
                add_entry.attrib["info"] = self._expand_info(add_entry)
            s_xml.append(add_entry)
        # remove structural entries with only one mve-child
        for struct_ent in xml_vect.xpath(".//entry[not(@name) = 'compound' and not(entry)]", smart_strings=False):
            # print "*", struct_ent.attrib
            parent = struct_ent.getparent()
            # print etree.tostring(parent, pretty_print=True)
            if struct_ent:
                parent.append(struct_ent[0])
            parent.remove(struct_ent)
            # pprint.pprint(struct_ent)
        # print etree.tostring(xml_vect, pretty_print=True)
        # print xml_vect.xpath(".//*/@name")
        # print etree.tostring(xml_vect, pretty_print=True)
        # add pde entries
        pde_keys = sorted([(pde_node.attrib["name"], pde_node.get("type_instance", ""), pde_node) for pde_node in cur_xml.findall("pde[@active='1']")])
        # add performance data entries
        for pde_key, type_inst, pde_node in pde_keys:
            ti_str = "/{}".format(type_inst) if type_inst else ""
            for sub_val in pde_node:
                new_val = copy.deepcopy(sub_val)
                v_key = sub_val.get("key", sub_val.get("name"))
                sr_node = self._create_struct(xml_vect, "{}.{}".format(pde_key, v_key))
                new_val.attrib["part"] = new_val.attrib["name"]
                new_val.attrib["name"] = "pde:{}.{}{}".format(
                    sr_node.get("name", sr_node.get("part")),
                    new_val.get("name"),
                    ti_str,
                )
                new_val.attrib["type_instance"] = type_inst
                new_val.attrib["info"] += " [PD]"
                if graph_mode:
                    new_val.attrib["file_name"] = pde_node.attrib["file_name"]
                sr_node.append(new_val)
        # print etree.tostring(xml_vect, pretty_print=True)
        return xml_vect

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

    @staticmethod
    def merge_node_results(res_list):
        if len(res_list) > 1:
            # print etree.tostring(res_list, pretty_print=True)
            # remove empty node_results
            empty_nodes = []
            for entry in res_list:
                if len(entry) == 0:
                    # attrib is fairly empty (only pk)
                    empty_nodes.append(entry.attrib)
                    entry.getparent().remove(entry)
            data_store.g_log(
                "merging {} ({} empty)".format(
                    logging_tools.get_plural("node result", len(res_list)),
                    logging_tools.get_plural("entry", len(empty_nodes))
                )
            )
            if len(res_list):
                # build a list of all structural entries
                all_keys = set()
                for cur_node in res_list:
                    for entry in cur_node[0].xpath(".//entry", smart_strings=False):
                        parts = []
                        _parent = entry
                        while _parent.tag == "entry":
                            parts.insert(0, _parent.attrib["part"])
                            _parent = _parent.getparent()
                        all_keys.add(".".join(parts))
                merged_mv = E.machine_vector()
                key_dict = {}
                # build structural part of machine_vector and lookup dict (key_dict)
                for key in sorted(all_keys):
                    add_key = key.split(".")[-1]
                    key_dict[key] = E.entry(part=add_key)
                    if add_key == key:
                        merged_mv.append(key_dict[key])
                    else:
                        key_dict[key[:-(len(add_key) + 1)]].append(key_dict[key])
                # print etree.tostring(merged_mv, pretty_print=True)
                # add entries
                for cur_node in res_list:
                    # print etree.tostring(cur_node, pretty_print=True)
                    for val_el in cur_node[0].xpath(".//value|.//mve|.//cve", smart_strings=False):
                        # build unique key and distinguish between MV and PD values
                        # (machine vector and performance data)
                        _name = val_el.get("name")
                        if val_el.tag == "value":
                            # remove pde: prefix
                            _name = _name.split(":", 1)[1]
                        _key = "{}:{}".format(
                            val_el.tag,
                            _name,
                        )
                        _add_key = ".".join(_name.split(".")[:-1])
                        if _key not in key_dict:
                            key_dict[_key] = val_el
                            key_dict[_add_key].append(val_el)
                        else:
                            val_el = key_dict[_key]
                            cur_devc = int(val_el.attrib.get("devices", "1")) + 1
                            val_el.attrib["devices"] = "{:d}".format(cur_devc)
                            _parent = val_el.getparent()
                            # iterate
                            while _parent.tag == "entry":
                                _parent.attrib["devices"] = "{:d}".format(max(cur_devc, int(_parent.get("attributes", "1"))))
                                _parent = _parent.getparent()
                # print etree.tostring(merged_mv, pretty_print=True)
                return E.node_results(E.node_result(merged_mv, devices="{:d}".format(len(res_list))))
            else:
                return E.node_results()
        else:
            return res_list

    def _expand_info(self, entry):
        info = entry.attrib["info"]
        parts = entry.attrib["name"].split(".")
        for idx in xrange(len(parts)):
            info = info.replace("$%d" % (idx + 1), parts[idx])
        return info

    @staticmethod
    def get_rrd_xml(dev_pk, mode=None):
        if mode:
            return data_store.__devices[dev_pk].struct_xml_vector(mode=mode)
        else:
            # do a deepcopy (just to be sure)
            return copy.deepcopy(data_store.__devices[dev_pk].xml_vector)

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
                    data_store.g_log("cannot initialize data_store for %s: %s" % (
                        full_name,
                        process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                else:
                    data_store.__devices[pk] = new_ds
                    data_store.g_log(
                        "recovered info for %s from disk (pk %d, memory usage now %s)" % (
                            full_name,
                            pk,
                            logging_tools.get_size_str(process_tools.get_mem_info())))
            else:
                data_store.g_log("ignoring direntry '%s'" % (entry), logging_tools.LOG_LEVEL_WARN)

    @staticmethod
    def g_log(what, log_level=logging_tools.LOG_LEVEL_OK):
        data_store.process.log("[ds] %s" % (what), log_level)

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
                data_store.g_log("found device %s (%s) for pd_type=%s" % (unicode(match_dev), match_mode, pd_type))
            if match_dev.pk not in data_store.__devices:
                data_store.__devices[match_dev.pk] = data_store(match_dev)
            data_store.__devices[match_dev.pk].feed_pd(name, pd_type, pd_info, file_name)
        else:
            data_store.g_log(
                "no device found (name=%s, pd_type=%s)" % (name, pd_type),
                logging_tools.LOG_LEVEL_ERROR)

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
            data_store.g_log("no device found (%s: %s)" % (
                logging_tools.get_plural("key", len(in_vector.attrib)),
                ", ".join(["%s=%s" % (key, str(value)) for key, value in in_vector.attrib.iteritems()])
            ),
            logging_tools.LOG_LEVEL_ERROR
        )
