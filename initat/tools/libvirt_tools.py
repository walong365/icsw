# Copyright (C) 2010,2012-2015 Andreas Lang-Nevyjel
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

from lxml import etree  # @UnresolvedImport
import os
import time

from initat.tools import logging_tools, process_tools

try:
    import libvirt  # @UnresolvedImport
except:
    libvirt = None

LIBVIRT_RO_SOCK_NAME = "/var/run/libvirt/libvirt-sock-ro"


def libvirt_ok():
    return True if libvirt else False


class base_stats(object):
    def __init__(self):
        self.__first_run = True
        self.cpu_used = 0.0

    def feed(self, *args):
        act_time = time.time()
        cpu_used = args[4]
        if self.__first_run:
            self.__first_run = False
        else:
            diff_time = max(abs(act_time - self.__feed_time), 1)
            try:
                self.cpu_used = ((cpu_used - self.__cpu_used) / (10000000 * diff_time))
            except:
                self.cpu_used = 0.0
        self.__cpu_used, self.__feed_time = (cpu_used, act_time)


class disk_info(object):
    def __init__(self, xml_object):
        self.__xml_object = xml_object
        self.__first_run = True
        self._clear_stats()
        src_obj = self.__xml_object.find("source")
        if src_obj is not None:
            self.src_type, self.src_ref = ("???", "???")
            for src_type in ["file", "dev"]:
                if src_type in src_obj.attrib:
                    self.src_type, self.src_ref = (src_type, src_obj.attrib[src_type])
        self.dev = self.__xml_object.xpath(".//target", smart_strings=False)[0].attrib["dev"]
        self.bus = self.__xml_object.xpath(".//target", smart_strings=False)[0].attrib["bus"]

    def get_info(self):
        return "device '{}' on bus '{}', source is {} ({})".format(
            self.dev,
            self.bus,
            self.src_ref,
            self.src_type)

    def _clear_stats(self):
        self.stats = {
            key: {
                s_key: 0 for s_key in ["reqs", "bytes"]
            } for key in ["read", "write"]
        }

    def feed(self, *args):
        act_time = time.time()
        if self.__first_run:
            self.__first_run = False
        else:
            diff_time = max(abs(act_time - self.__feed_time), 1)
            try:
                for key, offset in [
                    ("read", 0),
                    ("write", 2)
                ]:
                    for rel_offset, rel_key in enumerate(["reqs", "bytes"]):
                        self.stats[key][rel_key] = (
                            args[offset + rel_offset] - self.__prev_args[offset + rel_offset]
                            ) / diff_time
            except:
                self._clear_stats()
        self.__prev_args, self.__feed_time = (args, act_time)


class net_info(object):
    def __init__(self, xml_object):
        self.__xml_object = xml_object
        self.__first_run = True
        self._clear_stats()
        self.dev = self.__xml_object.xpath(".//target", smart_strings=False)[0].attrib["dev"]
        self.model = self.__xml_object.xpath(".//model", smart_strings=False)[0].attrib["type"]
        self.source = self.__xml_object.xpath(".//source", smart_strings=False)[0].attrib["bridge"]
        self.mac_address = self.__xml_object.xpath(".//mac", smart_strings=False)[0].attrib["address"]

    def get_info(self):
        return "device {} (model {}) on {}, MAC is {}".format(
            self.dev,
            self.model,
            self.source,
            self.mac_address)

    def _clear_stats(self):
        self.stats = {
            key: {
                s_key: 0 for s_key in ["bytes", "packets", "errs", "drops"]
            } for key in ["read", "write"]
        }

    def feed(self, *args):
        act_time = time.time()
        if self.__first_run:
            self.__first_run = False
        else:
            diff_time = max(abs(act_time - self.__feed_time), 1)
            try:
                for key, offset in [
                    ("read", 0),
                    ("write", 4)
                ]:
                    for rel_offset, rel_key in enumerate(["bytes", "packets", "errs", "drops"]):
                        self.stats[key][rel_key] = (
                            args[offset + rel_offset] - self.__prev_args[offset + rel_offset]
                        ) / diff_time
            except:
                self._clear_stats()
        self.__prev_args, self.__feed_time = (args, act_time)


class virt_instance(object):
    def __init__(self, i_id, log_com, ro_conn):
        self.log_com = log_com
        self.inst_id = i_id
        self.dom_handle = ro_conn.lookupByID(self.inst_id)
        self._update_xml()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.log_com("[{}] {}".format(self.name, what), log_level)

    def _update_xml(self):
        self.name = self.dom_handle.name()
        self.log("Instance name is '{}', ID is {}".format(
            self.name,
            self.inst_id))
        self.xml_desc = etree.fromstring(self.dom_handle.XMLDesc(0))  # @UndefinedVariable
        self.memory = int(self.xml_desc.xpath(".//currentMemory", smart_strings=False)[0].text) * 1024
        self.vcpus = int(self.xml_desc.xpath(".//vcpu", smart_strings=False)[0].text)
        self.log(
            "memory is {}, {}".format(
                logging_tools.get_size_str(self.memory),
                logging_tools.get_plural("CPU", self.vcpus)
            )
        )
        self.disk_dict, self.net_dict = ({}, {})
        self.vnc_port = None
        vnc_entry = self.xml_desc.xpath(".//graphics[@type='vnc']", smart_strings=False)
        if vnc_entry:
            self.vnc_port = int(vnc_entry[0].attrib["port"]) - 5900
            self.log("VNC port is {:d}".format(self.vnc_port))
        else:
            self.log("no VNC-port defined", logging_tools.LOG_LEVEL_WARN)
        # print etree.tostring(self.xml_desc, pretty_print=True)
        for disk_entry in self.xml_desc.findall(".//disk[@device='disk']"):
            cur_disk_info = disk_info(disk_entry)
            self.disk_dict[disk_entry.xpath(".//target", smart_strings=False)[0].attrib["dev"]] = cur_disk_info
            self.log(cur_disk_info.get_info())
        for net_entry in self.xml_desc.findall(".//interface[@type='bridge']"):
            cur_net_info = net_info(net_entry)
            self.net_dict[net_entry.xpath(".//target", smart_strings=False)[0].attrib["dev"]] = cur_net_info
            self.log(cur_net_info.get_info())
        self.base_info = base_stats()

    def close(self):
        del self.dom_handle

    def update(self):
        # print dir(self.dom_handle)
        self.base_info.feed(*self.dom_handle.info())
        for act_disk in self.disk_dict:
            self.disk_dict[act_disk].feed(*self.dom_handle.blockStats(act_disk))
            # print "    ", act_disk, self.disk_dict[act_disk].stats
        for act_net in self.net_dict:
            self.net_dict[act_net].feed(*self.dom_handle.interfaceStats(act_net))
            # print "    ", act_net, self.net_dict[act_net].stats


class libvirt_connection(object):
    def __init__(self, read_only=True, **kwargs):
        self.__read_only = read_only
        self.log_com = kwargs.get("log_com", None)
        if self.log_com == "stdout":
            self.log_com = self.stdout_log
        self.log_lines = []
        self.__conn = None
        self.__inst_dict = {}
        self.__missing_logged = False

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.log_lines.append((log_level, what))
        if self.log_com:
            self.log_com("[lvc] {}".format(what), log_level)

    def stdout_log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        print "[{:<5s}] {}".format(logging_tools.get_log_level_str(log_level), what)

    def close(self, **kwargs):
        self._close_con()
        if kwargs.get("keep_log_lines", False):
            self.log_lines = []

    def _close_con(self):
        if self.__conn:
            try:
                self.__conn.close()
            except:
                self.log(
                    "error closing connection: {}".format(
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            del self.__conn
            self.__conn = None

    @property
    def connection(self):
        if not self.__conn:
            if libvirt and os.path.exists(LIBVIRT_RO_SOCK_NAME):
                try:
                    self.__conn = libvirt.openReadOnly(None)
                except:
                    self.__conn = None
                    self.log(
                        "error in openReadOnly(None): {}".format(
                            process_tools.get_except_info()
                        ),
                        logging_tools.LOG_LEVEL_CRITICAL
                    )
                else:
                    if os.getuid():
                        self.log(
                            "not running as root ({:d} != 0)".format(
                                os.getuid()
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
            else:
                if not self.__missing_logged:
                    self.__missing_logged = True
                    self.log(
                        "no libvirt defined or socket {} not found".format(
                            LIBVIRT_RO_SOCK_NAME
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                self.__conn = None
        return self.__conn

    def keys(self):
        return self.__inst_dict.keys()

    def __getitem__(self, key):
        return self.__inst_dict[key]

    def conn_call(self, conn, call_name, *args, **kwargs):
        for retry in [0, 1]:
            try:
                res = getattr(conn, call_name)(*args, **kwargs)
            except:
                self.log(
                    "error calling {}: {}".format(
                        call_name,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
                self._close_con()
                if retry:
                    raise
                else:
                    res = None
                conn = self.connection
            else:
                break
        return res

    def update(self):
        conn = self.connection
        if conn is not None:
            try:
                id_list = self.conn_call(conn, "listDomainsID")
            except:
                # connection gone ?
                self._close_con()
            else:
                cur_ids, present_ids = (set(id_list), set(self.__inst_dict.keys()))
                new_ids = cur_ids - present_ids
                old_ids = present_ids - cur_ids
                if new_ids:
                    self.log(
                        "{} found: {}".format(
                            logging_tools.get_plural("ID", len(new_ids)),
                            ", ".join(["{:d}".format(cur_id) for cur_id in sorted(new_ids)])
                        )
                    )
                    for new_id in new_ids:
                        self.add_domain(virt_instance(new_id, self.log, conn))
                if old_ids:
                    self.log(
                        "{} lost: {}".format(
                            logging_tools.get_plural("ID", len(old_ids)),
                            ", ".join(["{:d}".format(cur_id) for cur_id in sorted(old_ids)])
                        )
                    )
                    for old_id in old_ids:
                        self.remove_domain(old_id)
                for same_id in cur_ids & present_ids:
                    self[same_id].update()

    def add_domain(self, new_inst):
        self.__inst_dict[new_inst.inst_id] = new_inst

    def remove_domain(self, inst_id):
        self.__inst_dict[inst_id].close()
        del self.__inst_dict[inst_id]

    def get_status(self):
        conn = self.connection
        if conn:
            ret_dict = {
                "info": self.conn_call(conn, "getInfo"),
                "type": self.conn_call(conn, "getType"),
                "version": self.conn_call(conn, "getVersion"),
                "capabilities": self.conn_call(conn, "getCapabilities"),
            }
        else:
            ret_dict = {}
        return ret_dict

    def domain_overview(self):
        conn = self.connection
        if conn:
            dom_dict = {
                "running": {},
                "defined": {}
            }
            domain_ids = self.conn_call(conn, "listDomainsID")
            for act_id in domain_ids:
                act_dom = self.conn_call(conn, "lookupByID", act_id)
                dom_dict["running"][act_id] = {
                    "name": act_dom.name(),
                    "info": act_dom.info()
                }
                del act_dom
            domain_names = self.conn_call(conn, "listDefinedDomains")
            for act_name in domain_names:
                act_dom = self.conn_call(conn, "lookupByName", act_name)
                dom_dict["defined"][act_name] = act_dom.info()
                del act_dom
        else:
            # better return an error ?
            dom_dict = {}
        return dom_dict

    def domain_status(self, cm):
        conn = self.connection
        if conn:
            r_dict = {
                "cm": cm,
                "desc": None
            }
            domain_ids = self.conn_call(conn, "listDomainsID")
            for act_id in domain_ids:
                act_dom = self.conn_call(conn, "lookupByID", act_id)
                if cm and act_dom.name() == cm:
                    r_dict["desc"] = act_dom.XMLDesc(0)
                del act_dom
        else:
            r_dict = {}
        return r_dict

