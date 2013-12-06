#!/usr/bin/python-init -Ot
#
# Copyright (C) 2007,2008,2009,2013 Andreas Lang-Nevyjel, init.at
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
from lxml import etree # @UnresolvedImport
from lxml.builder import E # @UnresolvedImport
import copy
import logging_tools
import os
import process_tools
import re
import time

class data_store(object):
    def __init__(self, cur_dev):
        self.pk = cur_dev.pk
        self.name = unicode(cur_dev.full_name)
        # name of rrd-files on disk
        self.store_name = ""
        self.xml_vector = E.machine_vector()
    def restore(self):
        try:
            self.xml_vector = etree.fromstring(file(self.data_file_name(), "r").read())
        except:
            self.log("cannot interpret XML: %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
            self.xml_vector = E.machine_vector()
        else:
            # for pure-pde vectors no store name is set
            self.store_name = self.xml_vector.attrib.get("store_name", "")
            all_mves = self.xml_vector.xpath(".//mve/@name")
            if len(all_mves) != len(set(all_mves)):
                self.log("found duplicate entries, removing them")
                removed = 0
                for cur_mve in all_mves:
                    sub_list = self.xml_vector.xpath(".//mve[@name='%s']" % (cur_mve))
                    for sub_entry in sub_list[:-1]:
                        sub_entry.getparent().remove(sub_entry)
                        removed += 1
                self.log("removed %d entries" % (removed))
                self.store_info()
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
        old_keys = set(self.xml_vector.xpath(".//mve/@name"))
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
        new_keys = set(self.xml_vector.xpath(".//mve/@name"))
        c_keys = old_keys ^ new_keys
        if c_keys:
            self.log("mve: %d keys total, %d keys changed" % (len(new_keys), len(c_keys)))
        else:
            self.log("mve: %d keys total" % (len(new_keys)))
        self.store_info()
    def feed_pd(self, host_name, pd_type, pd_info):
        # we ignore the global store name for perfdata stores
        old_keys = set(self.xml_vector.xpath(".//pde/@name"))
        rrd_dir = global_config["RRD_DIR"]
        # only one entry
        cur_entry = self.xml_vector.find(".//pde[@name='%s']" % (pd_type))
        if cur_entry is None:
            # create new entry
            cur_entry = E.pde(
                name=pd_type,
                host=host_name,
                init_time="%d" % (time.time()),
            )
            for cur_idx, entry in enumerate(pd_info):
                cur_entry.append(
                    E.value(
                        name=entry.get("name"),
                    )
                )
            self.xml_vector.append(cur_entry)
        self._update_pd_entry(cur_entry, pd_info, rrd_dir)
        new_keys = set(self.xml_vector.xpath(".//pde/@name"))
        c_keys = old_keys ^ new_keys
        if c_keys:
            self.log("pde: %d keys total, %d keys changed" % (len(new_keys), len(c_keys)))
        # else:
        #    too verbose
        #    self.log("pde: %d keys total" % (len(new_keys)))
        self.store_info()
    def _update_pd_entry(self, entry, src_entry, rrd_dir):
        entry.attrib["last_update"] = "%d" % (time.time())
        entry.attrib["file_name"] = os.path.join(
            rrd_dir,
            entry.get("host"),
            "perfdata",
            "ipd_%s.rrd" % (entry.get("name"))
        )
        if len(entry) == len(src_entry):
            for v_idx, (cur_value, src_value) in enumerate(zip(entry, src_entry)):
                for key, def_value in [
                    ("info"  , "performance_data"),
                    ("v_type", "f"),
                    ("unit"  , "1"),
                    ("name"  , None),
                    ("index" , "%d" % (v_idx))]:
                    cur_value.attrib[key] = src_value.get(key, def_value)
    def _update_entry(self, entry, src_entry, rrd_dir):
        for key, def_value in [
            ("info"  , None),
            ("v_type", None),
            ("full"  , entry.get("name")),
            ("unit"  , "1"),
            ("base"  , "1"),
            ("factor", "1")]:
            entry.attrib[key] = src_entry.get(key, def_value)
        # last update time
        entry.attrib["last_update"] = "%d" % (time.time())
        entry.attrib["file_name"] = os.path.join(rrd_dir, self.store_name, "collserver", "icval-%s.rrd" % (entry.attrib["sane_name"]))
    def store_info(self):
        file(self.data_file_name(), "wb").write(etree.tostring(self.xml_vector, pretty_print=True))
        self.sync_to_grapher()
    def sync_to_grapher(self):
        data_store.process.send_to_process("graph", "xml_info", self.pk, etree.tostring(self.xml_vector))
    def data_file_name(self):
        return os.path.join(data_store.store_dir, "%s_%d.info.xml" % (self.name, self.pk))
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        data_store.process.log("[ds %s] %s" % (
            self.name,
            what), log_level)
    @staticmethod
    def has_rrd_xml(dev_pk):
        return dev_pk in data_store.__devices
    def struct_xml_vector(self):
        cur_xml = self.xml_vector
        all_keys = set(cur_xml.xpath(".//mve/@name"))
        xml_vect, lu_dict = (E.machine_vector(), {})
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
            # remove unneded entries
            for rem_attr in ["file_name", "last_update", "sane_name"]:
                if rem_attr in add_entry.attrib:
                    del add_entry.attrib[rem_attr]
            if "info" in add_entry.attrib:
                add_entry.attrib["info"] = self._expand_info(add_entry)
            s_xml.append(add_entry)
        # remove structural entries with only one mve-child
        for struct_ent in xml_vect.xpath(".//entry[not(entry)]"):
            parent = struct_ent.getparent()
            parent.append(struct_ent[0])
            parent.remove(struct_ent)
        # print etree.tostring(xml_vect, pretty_print=True)
         # add pde entries
        pde_keys = set(cur_xml.xpath(".//pde/@name"))
        for key in sorted(pde_keys):
            new_el = E.entry(name=key, part=key)
            xml_vect.append(new_el)
            for sub_val in cur_xml.find(".//pde[@name='%s']" % (key)):
                new_val = copy.deepcopy(sub_val)
                new_val.attrib["name"] = "%s.%s" % (new_el.get("name"), new_val.get("name"))
                new_el.append(new_val)
        return xml_vect
    @staticmethod
    def merge_node_results(res_list):
        if len(res_list) > 1:
            # print etree.tostring(res_list, pretty_print=True)
            # remove empty node_results
            empty_nodes = 0
            for entry in res_list:
                if len(entry) == 0:
                    empty_nodes += 1
                    entry.getparent().remove(entry)
            data_store.g_log("merging %s (%s empty)" % (logging_tools.get_plural("node result", len(res_list)),
                                                        logging_tools.get_plural("entry", empty_nodes)))
            first_mv = res_list[0][0]
            ref_dict = {"mve" : {}, "value" : {}}
            for val_el in first_mv.xpath(".//*"):
                if val_el.tag in ["value", "mve"]:
                    ref_dict[val_el.tag][val_el.get("name")] = val_el
                val_el.attrib["devices"] = "1"
            # pprint.pprint(ref_dict)
            for other_node in res_list[1:]:
                if len(other_node):
                    other_mv = other_node[0]
                    for add_el in other_mv.xpath(".//mve|.//value"):
                        add_tag, add_name = (add_el.tag, add_el.get("name"))
                        ref_el = ref_dict[add_tag].get(add_name)
                        if ref_el is not None:
                            new_count = int(ref_el.get("devices")) + 1
                            while "devices" in ref_el.attrib:
                                if int(ref_el.get("devices")) < new_count:
                                    ref_el.attrib["devices"] = "%d" % (new_count)
                                # increase all above me
                                ref_el = ref_el.getparent()
                        else:
                            print "***", add_tag, add_name
                other_node.getparent().remove(other_node)
        # print etree.tostring(res_list, pretty_print=True)
    def _expand_info(self, entry):
        info = entry.attrib["info"]
        parts = entry.attrib["name"].split(".")
        for idx in xrange(len(parts)):
            info = info.replace("$%d" % (idx + 1), parts[idx])
        return info
    @staticmethod
    def get_rrd_xml(dev_pk, sort=False):
        if sort:
            return data_store.__devices[dev_pk].struct_xml_vector()
        else:
            # do a deepcopy (just to be sure)
            return copy.deepcopy(data_store.__devices[dev_pk].xml_vector)
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
                    data_store.g_log("recovered info for %s from disk (%s)" % (
                        full_name,
                        logging_tools.get_size_str(process_tools.get_mem_info())))
    @staticmethod
    def g_log(what, log_level=logging_tools.LOG_LEVEL_OK):
        data_store.process.log("[ds] %s" % (what), log_level)
    @staticmethod
    def feed_perfdata(name, pd_type, pd_info):
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
            data_store.__devices[match_dev.pk].feed_pd(name, pd_type, pd_info)
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
            ), logging_tools.LOG_LEVEL_ERROR)

