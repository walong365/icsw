#!/usr/bin/python -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2008 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
# 
# This file belongs to webfrontend
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

import functions
import logging_tools
import html_tools
import tools
import time
import sys
import configfile
import process_tools
import pprint
import re
import os
import server_command
import fetchdevlog
try:
    import xen_tools
except:
    xen_tools = None

# netdevice keys to fetch from database
NETDEV_KEYS = ["devname", "bridge_name", "netdevice_idx", "macadr"]

def module_info():
    return {"xeng" : {"description" : "Xen",
                      "priority"    : 50},
            "xeni" : {"description"           : "Xen Information",
                      "enabled"               : True,
                      "default"               : True,
                      "left_string"           : "Xen Information",
                      "right_string"          : "Information and control of the Xen servers",
                      "priority"              : 40,
                      "capability_group_name" : "xeng"}}

class xen_server(object):
    def __init__(self, req, connection_log, name, **args):
        self.__req = req
        self.__connection_log = connection_log
        self.__dc = req.dc
        self.name = name
        self.ip = args.get("ip_address", None)
        self.__dummy_server = args.get("dummy_server", False)
        self.__domains = []
    def get_server_type(self):
        return "Container" if self.__dummy_server else "Server"
    def is_real_server(self):
        return not self.__dummy_server
    def has_any_domains(self):
        return True if self.__domains else False
    def add_domain(self, domain):
        self.__domains.append(domain)
    def get_num_domains(self):
        return len(self.__domains)

class xen_domain(object):
    def __init__(self, dom_name, xen_dict, server, **args):
        self.__log = args.get("log")
        self.name = dom_name
        self.short_name = dom_name.split(".")[0]
        if xen_dict:
            self.__domain = xen_tools.xen_domain(xen_dict)
            self.__domain["server"] = server
            if self.__domain.has_key("domid"):
                self.dom0 = False if self.__domain["domid"] else True
                self.domu = True if self.__domain["domid"] else False
                self.__running = True
            else:
                self.dom0, self.domu = (False, True)
                self.__running = False
        else:
            self.__running = False
            # dummy entry
            self.__domain = {"name"   : self.name,
                             "server" : server}
            self.dom0, self.domu = (False, True)
        self.__db_device = None
        self.__xen_subdevice = None
        # netdevices from database
        self.__netdevices = {}
        # db status
        self.__db_stat = 0
        # db status
        self.__db_status = []
    def get_suffix(self):
        if self.has_db_device():
            return "ddb%d" % (self[("db", "device_idx")])
        else:
            return "d%s" % (self.name)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log.add("device %s: %s" % (self.short_name,
                                          what),
                       "db",
                       {logging_tools.LOG_LEVEL_OK    : 1,
                        logging_tools.LOG_LEVEL_WARN  : 2,
                        logging_tools.LOG_LEVEL_ERROR : 0}.get(log_level, 0))
    def link_db_device(self, db_rec):
        self.__db_device = db_rec
    def link_xen_subdevice(self, db_rec):
        self.__xen_subdevice = db_rec
    def has_db_device(self):
        return True if self.__db_device else False
    def has_xen_subdevice(self):
        return True if self.__xen_subdevice else False
    def create_xen_device(self, dc, **args):
        if self.has_db_device():
            dev_idx = self[("db", "device_idx")]
            add_xen = True
            if args.get("check", True):
                dc.execute("SELECT * FROM xen_device WHERE device=%s", (self[("db", "device_idx")]))
                if dc.rowcount:
                    self.link_xen_subdevice(dc.fetchone())
                    add_xen = False
            if add_xen:
                self.log("adding xen_device")
                if self.__running:
                    cmd_line = self["image"]["linux"]["args"]
                    if self["image"]["linux"].has_key("root"):
                        cmd_line = "root=%s %s" % (self["image"]["linux"]["root"], cmd_line)
                    dc.execute("INSERT INTO xen_device SET device=%s, memory=%s, max_memory=%s, cmdline=%s, vcpus=%s", (dev_idx,
                                                                                                                        self["memory"],
                                                                                                                        self["maxmem"],
                                                                                                                        cmd_line,
                                                                                                                        self["vcpus"]))
                else:
                    # fill with dummy-values
                    dc.execute("INSERT INTO xen_device SET device=%s", (dev_idx))
                dc.execute("SELECT * FROM xen_device WHERE device=%s", (dev_idx))
                self.link_xen_subdevice(dc.fetchone())
    def __getitem__(self, key):
        if type(key) == type(()):
            lu_dict, key = key
        else:
            lu_dict = "dom"
        if lu_dict == "dom":
            return self.__domain[key]
        elif lu_dict == "db":
            return self.__db_device[key]
        elif lu_dict == "xd":
            return self.__xen_subdevice[key]
    def has_key(self, key):
        return self.__domain.has_key(key)
    def beautify_memory(self):
        if self.__running:
            mem_val = self["memory"]
        else:
            mem_val = self[("xd", "memory")]
        if mem_val > 1024:
            return "%.2f GB" % (mem_val / 1024.)
        else:
            return "%d MB" % (mem_val)
    def get_builder(self):
        if self.__running:
            if self.has_key("image"):
                return self["image"].keys()[0]
            else:
                return "unknown"
        else:
            return "---"
    def get_domain_id(self):
        if self.__running:
            return "%d" % (self["domid"])
        else:
            return "-"
    def get_state(self):
        if self.__running:
            set_chars = [chr for chr in self["state"] if chr != "-"]
            if set_chars:
                set_char = set_chars[0]
                return {"r" : "running",
                        "b" : "blocked",
                        "p" : "paused",
                        "s" : "shutdown",
                        "c" : "crashed",
                        "d" : "dying"}.get(set_char, "state '%s' unknown" % (set_char))
            else:
                return "unknown"
        else:
            return "not running"
    def get_vif_info(self):
        if self.__running:
            if self.has_key("device"):
                return "%d" % (len(self["device"]["vif"]))
            else:
                return "0"
        else:
            return "-"
    def get_vbd_info(self):
        if self.__running:
            if self.has_key("device"):
                #pprint.pprint(self["device"]["vbd"])
                return "%d" % (len(self["device"]["vbd"]))
            else:
                return "0"
        else:
            return "-"
    def get_vcpu_info(self):
        if self.__running:
            return "%d" % (self["vcpus"])
        else:
            return "-"
    def feed_netdevice(self, db_rec):
        if db_rec["devname"] and db_rec["identifier"] in ["eth"] and not db_rec["devname"].count(":"):
            # only add ethernet-type netdevices which are not virtual
            ndev_dict = dict([(key, db_rec[key]) for key in NETDEV_KEYS])
            # matched against domain_vif
            ndev_dict["matched"] = False
            self.__netdevices[db_rec["netdevice_idx"]] = ndev_dict
    def compare_network(self, dc):
        if self.has_xen_subdevice():
            if not self.__running:
                self.__db_status.append("not running")
            elif not self.has_key("device"):
                self.__db_status.append("no device key found, xend out of sync?")
            else:
                dom_vifs = self["device"]["vif"]
                if not dom_vifs:
                    self.__db_status.append("none found")
                else:
                    if len(dom_vifs) != len(self.__netdevices.keys()):
                        self.__db_status.append("#vifs mismatch (%d != %d)" % (len(dom_vifs),
                                                                               len(self.__netdevices.keys())))
                    else:
                        # domain has the same number of network devices as the device from the db
                        # bridges used in this domain
                        domain_bridges = [vif["bridge"] for vif in dom_vifs]
                        set_netdevices, unset_netdevices = ([key for key, value in self.__netdevices.iteritems() if value["bridge_name"]],
                                                            [key for key, value in self.__netdevices.iteritems() if not value["bridge_name"]])
                        # netdevices with problems
                        error_netdevices = []
                        if set_netdevices:
                            # remove set_domains from domain_bridges
                            for set_netdevice in set_netdevices:
                                set_domain = self.__netdevices[set_netdevice]["bridge_name"]
                                if set_domain in domain_bridges:
                                    domain_bridges.remove(set_domain)
                                    self.__netdevices[set_netdevice]["matched"] = True
                                else:
                                    error_netdevices.append(set_netdevice)
                        if error_netdevices:
                            self.__db_status.append("#%d dbnd error" % (len(error_netdevices)))
                        else:
                            # set_netdevices has been matched to the domain_bridges
                            if len(unset_netdevices) == len(domain_bridges):
                                if len(unset_netdevices) == 1:
                                    # match
                                    self._copy_bridge_name_to_netdevice(dc, domain_bridges[0], unset_netdevices[0])
                                elif not unset_netdevices:
                                    # everything set, ok
                                    pass
                                else:
                                    self.__db_status.append("%d nd unknown" % (len(unset_netdevices)))
                            else:
                                # unable to match
                                self.__db_status.append("#vifs mismatch")
                        # match macadresses
                        domain_bridges = [vif["bridge"] for vif in dom_vifs]
                        set_netdevices = dict([(value["bridge_name"], key) for key, value in self.__netdevices.iteritems() if value["matched"]])
                        if len(domain_bridges) == len(set_netdevices.keys()):
                            for vif in dom_vifs:
                                if vif["bridge"] in domain_bridges:
                                    net_dev = self.__netdevices[set_netdevices[vif["bridge"]]]
                                    if net_dev["macadr"] != vif["mac"]:
                                        self.log("setting macadr of %s to %s" % (net_dev["devname"],
                                                                                 vif["mac"]))
                                        dc.execute("UPDATE netdevice SET macadr=%s WHERE netdevice_idx=%s", (vif["mac"],
                                                                                                             net_dev["netdevice_idx"]))
    def _copy_bridge_name_to_netdevice(self, dc, bridge_name, net_idx):
        self.__netdevices[net_idx]["bridge_name"] = bridge_name
        self.__netdevices[net_idx]["matched"] = True
        self.log("setting bridge_name of %s to %s" % (self.__netdevices[net_idx]["devname"],
                                                      bridge_name))
        dc.execute("UPDATE netdevice SET bridge_name=%s WHERE netdevice_idx=%s", (bridge_name,
                                                                                  net_idx))
    def get_db_status(self):
        if self.__db_status:
            return ", ".join(self.__db_status)
        else:
            return "ok"
    def check_domain_details(self, req, change_log):
        self.__req = req
        self.__change_log = change_log
        self._init_detail_fields()
        self._check_for_detail_changes()
    def show_domain_details(self, req, change_log):
        req.write(html_tools.gen_hline("Details for Domain %s" % (self.name), 2))
        self._show_details()
    def _init_detail_fields(self):
        self.__memory_field = html_tools.text_field(self.__req, "dommem", size=16, display_len=8)
        self.__cmdline_field = html_tools.text_field(self.__req, "domcmd", size=256, display_len=32)
    def _check_for_detail_changes(self):
        c_dict = {}
        act_mem = self[("xd", "memory")]
        new_mem = self.__memory_field.check_selection("", "%d" % (act_mem))
        if not new_mem.isdigit():
            new_mem = act_mem
        else:
            new_mem = int(new_mem)
        if new_mem != act_mem:
            self.__change_log.add_ok("Memory changed from %d MB to %d MB " % (act_mem, new_mem), "Xen")
            c_dict["memory"] = new_mem
        self.__memory_field[""] = "%d" % (new_mem)
        act_com = self[("xd", "cmdline")].strip()
        new_com = self.__cmdline_field.check_selection("", act_com).strip()
        if act_com != new_com:
            c_dict["cmdline"] = new_com
            self.__change_log.add_ok("Changed cmdline to '%s'" % (new_com), "Xen")
        self.__cmdline_field[""] = new_com
        if c_dict:
            sql_str, sql_tuple = ("UPDATE xen_device SET %s WHERE xen_device_idx=%d" % (", ".join(["%s=%%s" % (key) for key in sorted(c_dict.keys())]),
                                                                                        self[("xd", "xen_device_idx")]),
                                  tuple([c_dict[key] for key in sorted(c_dict.keys())]))
            self.__req.dc.execute(sql_str, sql_tuple)
    def _show_details(self):
        o_table = html_tools.html_table(cls="normalsmall")
        h_fields = ["Key", "Value"]
        o_table[0]["class"] = "line00"
        for h_field in h_fields:
            o_table[None][0] = html_tools.content(h_field, cls="center", type="th")
        o_table[0]["class"] = "line10"
        o_table[None][0] = html_tools.content("Builder : ", cls="right")
        o_table[None][0] = html_tools.content(self[("xd", "builder")], cls="left")
        o_table[0]["class"] = "line11"
        o_table[None][0] = html_tools.content("Memory : ", cls="right")
        o_table[None][0] = html_tools.content([self.__memory_field, "MB"], cls="left")
        o_table[0]["class"] = "line10"
        o_table[None][0] = html_tools.content("CmdLine : ", cls="right")
        o_table[None][0] = html_tools.content(self.__cmdline_field, cls="left")
        self.__req.write(o_table(""))

class xen_tree(object):
    def __init__(self, req, connection_log, change_log, active_submit):
        self.__req = req
        self.__dc = req.dc
        self.__connection_log = connection_log
        self.__change_log = change_log
        self._init_html_entities()
        self.display_mode = self.display_list.check_selection("", "ss")
        self.__act_regex = re.compile("%s" % (self.domain_regex.check_selection("", "") or ".*"))
        self.__xen_servers = {}
        self.__dummy_xen_server = xen_server(self.__req, connection_log, "container", dummy_server=True)
        self.__xen_servers[self.__dummy_xen_server.name] = self.__dummy_xen_server
        for s_name, s_ip in self.__req.conf["server"].get("xen_server", {}).iteritems():
            self.__xen_servers[s_name] = xen_server(self.__req, connection_log, s_name, ip_address=s_ip)
        self.__user_dict = tools.get_user_list(self.__dc, [], all_flag=True)
        self.__ulsi = self.__req.log_source.get("user", {"log_source_idx" : 0})["log_source_idx"]
    def __getitem__(self, key):
        return self.__xen_servers[key]
    def _init_html_entities(self):
        self.__running_action = html_tools.selection_list(self.__req, "xa", self._get_action_dict(), auto_reset=True)
        self.display_list = html_tools.selection_list(self.__req, "xendisp", {"sn" : "Show domains, sort by name",
                                                                              "ss" : "Show domains, sort by server"}, sort_new_keys=False)
        self.domain_regex = html_tools.text_field(self.__req, "xenreg", size=182, display_len=16)
        self.__toggle_field = html_tools.toggle_field(self.__req, "sdl", text="Show / Hide Devicelog", target="tr#")
        # not used ?
#         self.xen_server_list = html_tools.selection_list(self.__req, "xenssel", {}, sort_new_key=False)
#         for s_name, s_ip in self.__req.conf["server"].get("xen_server").iteritems():
#             self.xen_server_list[s_name] = "Xen on %s (via %s)" % (new_xen_server.name,
#                                                                    new_xen_server.ip)
#         self.xen_server_list.mode_is_normal()
    def _get_action_dict(self):
        return {0 : {"name"       : "---",
                     "srv_action" : None},
                1 : {"name"       : "pause Domain",
                     "srv_action" : "pause"},
                2 : {"name"       : "unpause Domain",
                     "srv_action" : "unpause"},
                3 : {"name"       : "reboot Domain",
                     "srv_action" : "reboot"},
                4 : {"name"       : "shutdown Domain",
                     "srv_action" : "shutdown"},
                5 : {"name"       : "destroy Domain",
                     "srv_action" : "destroy"}}
    def fetch_domain_dicts(self):
        com_list = []
        for server_name, server_stuff in self.__xen_servers.iteritems():
            if server_stuff.is_real_server():
                com_list.append(tools.s_command(self.__req, "xen_server", 8019, "get_domain_dicts", [], 10, server_name))
        tools.iterate_s_commands(com_list, self.__connection_log)
        self.__domain_list = []
        for com in com_list:
            if com.server_reply:
                if com.get_state() == "o":
                    act_xen_dict = com.server_reply.get_option_dict()
                    domain_list = [xen_domain(xen_dict["name"], xen_dict, com.hostname, log=self.__change_log) for xen_dict in server_command.net_to_sys(act_xen_dict["net_dicts"])]
                    for domain in domain_list:
                        if self.__act_regex.match(domain["name"]):
                            self.__xen_servers[com.hostname].add_domain(domain)
                            self.__domain_list.append(domain)
                else:
                    self.__connection_log.add_error("Error connecting to Xen-server %s" % (com.hostname), "Xen")
        self._modify_xen_db()
    def _modify_xen_db(self):
        # create xen-entries for recognized devices
        name_dict, domain_dict = ({}, {})
        for domain in self.__domain_list:
            if domain.domu:
                # skip domain-0
                name_dict.setdefault(domain.short_name, 0)
                name_dict[domain.short_name] += 1
                domain_dict[domain.short_name] = domain
        xen_names, error_names = ([], [])
        for name, name_count in name_dict.iteritems():
            if name_count > 1:
                self.__connection_log.add_error("Shortname '%s' is not uniqe: %s used" % (name,
                                                                                          logging_tools.get_plural("time", name_count)),
                                                "xen")
                error_names.append(name)
                del domain_dict[name]
            else:
                xen_names.append(name)
        # fetch all xen_devices
        sql_str = "SELECT d.* FROM device d WHERE ((%s) OR d.xen_guest)" % (" OR ".join(["d.name='%s'" % (dev_name) for dev_name in xen_names]) or "0")
        self.__dc.execute(sql_str)
        self.__xen_devices = {}
        db_doms_found = []
        set_xen_guest_flag_list = []
        for db_rec in self.__dc.fetchall():
            if db_rec["name"] in error_names or not self.__act_regex.match(db_rec["name"]):
                # skip problematic names
                pass
            else:
                db_doms_found.append(db_rec["device_idx"])
                # add domain entry without server and domain info
                if domain_dict.has_key(db_rec["name"]):
                    # found in running domain_dict, ok
                    domain = domain_dict[db_rec["name"]]
                else:
                    domain = xen_domain(db_rec["name"], {}, self.__dummy_xen_server.name, log=self.__change_log)
                    self.__domain_list.append(domain)
                    domain_dict[domain.short_name] = domain
                    self.__dummy_xen_server.add_domain(domain)
                if not domain.has_db_device():
                    domain.link_db_device(db_rec)
                    if not db_rec["xen_guest"]:
                        print db_rec["device_idx"], db_rec
                        # set xen_guest flag
                        self.__connection_log.add_warn("Setting xen_guest flag for device %s" % (db_rec["name"]), 
                                                       "xen")
                        set_xen_guest_flag_list.append(db_rec["device_idx"])
        # check if these devices have entries in the device-db
        if db_doms_found:
            sql_str = "SELECT d.*, %s, nt.identifier FROM network_device_type nt, device d LEFT JOIN netdevice n ON n.device=d.device_idx WHERE " % (", ".join(["n.%s" % (netdev_key) for netdev_key in NETDEV_KEYS])) + \
                "(%s) AND n.network_device_type=nt.network_device_type_idx" % (" OR ".join(["d.device_idx=%d" % (dev_idx) for dev_idx in db_doms_found]))
            self.__dc.execute(sql_str)
            # list of devices to set the xen-guest flag
            for db_rec in self.__dc.fetchall():
                domain = domain_dict[db_rec["name"]]
                domain.feed_netdevice(db_rec)
        if set_xen_guest_flag_list:
            self.__dc.execute("UPDATE device SET xen_guest=1 WHERE %s" % (" OR ".join(["device_idx=%d" % (idx) for idx in set_xen_guest_flag_list])))
        # add xen_device 
        self.__dc.execute("SELECT d.name, x.* FROM device d, xen_device x WHERE x.device=d.device_idx")
        for db_rec in self.__dc.fetchall():
            if domain_dict.has_key(db_rec["name"]):
                domain_dict[db_rec["name"]].link_xen_subdevice(db_rec)
        # add xen-devices where needed
        devices_without_xendev = [key for key, struct in domain_dict.iteritems() if not struct.has_xen_subdevice()]
        for dev_name in devices_without_xendev:
            domain_dict[dev_name].create_xen_device(self.__dc, check=False)
        # fetch xen_vbds
        # compare network devices with domain info
        for domain_name, domain in domain_dict.iteritems():
            domain.compare_network(self.__dc)
    def get_info_str(self):
        real_servers = len([True for s_struct in self.__xen_servers.itervalues() if s_struct.has_any_domains()])
        fake_servers = len(self.__xen_servers.keys()) - real_servers
        return "Found %s on %s%s" % (logging_tools.get_plural("domain", len(self.__domain_list)),
                                     logging_tools.get_plural("server", len(self.__xen_servers.keys())),
                                     " (%s)" % (logging_tools.get_plural("domain container", fake_servers)) if fake_servers else "")
    def check_for_changes(self):
        # act_dict for action lookup
        act_dict = self._get_action_dict()
        # generate show list
        action_dict = {}
        name_dict = dict([(key, {}) for key in set([domain["name"] for domain in self.__domain_list])])
        for domain in self.__domain_list:
            name_dict[domain["name"]][domain["server"]] = domain
        show_list = []
        if self.display_mode == "sn":
            self.__headers = ["Domain name", "Xen server"]
            for domain_name in sorted(name_dict.keys()):
                for server in sorted(name_dict[domain_name].keys()):
                    show_list.append((domain_name, server))
        else:
            self.__headers = ["Domain name"]
            for server in sorted(self.__xen_servers.iterkeys()):
                for domain_name in sorted(name_dict.keys()):
                    if server in sorted(name_dict[domain_name].keys()):
                        show_list.append((domain_name, server))
        self.__show_list, self.__name_dict = (show_list, name_dict)
        logs_to_write = []
        for dom_name, srv_name in self.__show_list:
            domain = self.__name_dict[dom_name][srv_name]
            if domain.domu:
                action = self.__running_action.check_selection(domain.get_suffix(), 0)
                if action:
                    action_dict.setdefault(srv_name, {})[dom_name] = action
                    if domain.has_db_device():
                        dev_idx = domain[("db", "device_idx")]
                        logs_to_write.append(("(0, %s, %s, %s, %s, %s, null)", (dev_idx,
                                                                                self.__ulsi,
                                                                                self.__req.user_info.get_idx(),
                                                                                self.__req.log_status.get("w", {"log_status_idx" : 0})["log_status_idx"],
                                                                                "submitting DomU-command '%s' to %s" % (act_dict[action]["name"],
                                                                                                                        srv_name))))
        if logs_to_write:
            form_str = ",".join([x for x, y in logs_to_write])
            form_data = tuple(sum([list(y) for x, y in logs_to_write], []))
            self.__dc.execute("INSERT INTO devicelog VALUES%s" % (form_str), form_data)
        if action_dict:
            com_list = []
            for srv_name, com_dict in action_dict.iteritems():
                com_list.append(tools.s_command(self.__req, "xen_server", 8019, "domu_command", [], 10, srv_name, dict([(key, act_dict[value]["srv_action"]) for key, value in com_dict.iteritems()])))
            tools.iterate_s_commands(com_list, self.__change_log)
    def show_overview(self):
        submit_button = html_tools.submit_button(self.__req, "submit")
        self.__req.write(html_tools.gen_hline(self.get_info_str(), 2))
        if self.__show_list:
            headers = self.__headers + ["id", "DBlink", "builder", "vIFs", "vBDs", "vCPUs", "memory", "state", "devlog"]
            o_table = html_tools.html_table(cls="normal")
            o_table[0]["class"] = "lineh"
            for h_string in headers:
                o_table[None][0] = html_tools.content(h_string, type="th", cls="center")
            line_idx = 0
            last_server = ""
            for domain_name, server_name in self.__show_list:
                server = self[server_name]
                domain = self.__name_dict[domain_name][server_name]
                if server_name != last_server and self.display_mode == "ss":
                    o_table[0]["class"] = "line01"
                    o_table[None][0:len(headers)] = html_tools.content("%s %s, %s" % (self[server_name].get_server_type(),
                                                                                      server_name,
                                                                                      logging_tools.get_plural("domain", server.get_num_domains())), type="th", cls="center")
                    last_server = server_name
                #pprint.pprint(domain.get_net_dict())
                line_idx = 1 - line_idx
                line_class = "line1%d" % (line_idx)
                o_table[0]["class"] = line_class
                if domain.has_db_device():
                    o_table[None][0] = html_tools.content("<a href=\"%s.py?%s&mm=dd&idx=%d&srv=%s\">%s</a>" % (self.__req.module_name,
                                                                                                               functions.get_sid(self.__req),
                                                                                                               domain[("db", "device_idx")],
                                                                                                               server_name,
                                                                                                               domain_name), cls="left")
                else:
                    o_table[None][0] = html_tools.content(domain_name, cls="left")
                if self.display_mode == "sn":
                    o_table[None][0] = html_tools.content(domain["server"], cls="left")
                o_table[None][0] = html_tools.content(domain.get_domain_id(), cls="center")
                # database status
                if domain.domu:
                    if domain.has_db_device():
                        if domain.has_xen_subdevice():
                            db_status = domain.get_db_status()
                            o_table[None][0] = html_tools.content(db_status, cls="center" if db_status == "ok" else "errorcenter")
                        else:
                            o_table[None][0] = html_tools.content("missing", cls="errorcenter")
                    else:
                        o_table[None][0] = html_tools.content("no device", cls="warncenter")
                else:
                    o_table[None][0] = html_tools.content("n/a", cls="center")
                o_table[None][0] = html_tools.content(domain.get_builder(), cls="center")
                # number of vifs
                if domain.has_key("device"):
                    num_vifs = len(domain["device"]["vif"])
                    num_vbds = len(domain["device"]["vbd"])
                else:
                    num_vifs, num_vbds = (0, 0)
                o_table[None][0] = html_tools.content(domain.get_vif_info(), cls="center")
                o_table[None][0] = html_tools.content(domain.get_vbd_info(), cls="center")
                o_table[None][0] = html_tools.content(domain.get_vcpu_info(), cls="center")
                o_table[None][0] = html_tools.content(domain.beautify_memory(), cls="center")
                if domain.domu:
                    o_table[None][0] = html_tools.content([domain.get_state(), ", ", self.__running_action, ", ", submit_button()], domain.get_suffix(), cls="center")
                else:
                    o_table[None][0] = html_tools.content(domain.get_state(), cls="center")
                if domain.has_db_device():
                    o_table[None][0] = html_tools.content(self.__toggle_field, domain.get_suffix(), cls="center")
                    o_table[0]["class"] = line_class
                    # make a unique identifier
                    o_table[None]["id"] = self.__toggle_field.get_var_name(domain.get_suffix())
                    # default display-style is off
                    o_table[None]["style"] = "display:none"
                    o_table[None][0:len(headers)] = html_tools.content(fetchdevlog.show_device_history(self.__req,
                                                                                                       domain[("db", "device_idx")],
                                                                                                       self.__user_dict,
                                                                                                       verbose=False,
                                                                                                       max_lines=50,
                                                                                                       width=120,
                                                                                                       header_type="span"), domain.get_suffix(), cls="center", beautify=False)
                else:
                    o_table[None][0] = html_tools.content("&nbsp;", cls="center")
            self.__req.write(o_table(""))
            self.__req.write(self.__toggle_field.get_js_lines())

def process_page(req):
    if req.conf["genstuff"].has_key("AUTO_RELOAD"):
        del req.conf["genstuff"]["AUTO_RELOAD"]
    tools.init_log_and_status_fields(req)
    functions.write_header(req, js_list=["jquery-1.2.3.min", "jquery.flydom-3.1.1"])#, js_list=["MochiKit", "sortable_tables"])
    functions.write_body(req)
    req.write("\n".join(["<script type=\"text/javascript\">",
                         "$(document).ready(function(){",
                         "// Your code here",
                         "});",
                         #'$("a").click(function(){',
                         #'alert("Thanks for visiting!");',
                         #"return false;",
                         #'});',
                         "</script>"]))
    if not xen_tools:
        req.write(html_tools.gen_hline("No xen_tools found", 1))
    else:
        main_mode_field = html_tools.text_field(req, "mm", size=16, display_len=16)
        main_mode = main_mode_field.check_selection("", "ov")
        # logs
        # only errors and warnings are display
        connection_log = html_tools.message_log()
        # everything is shown
        change_log = html_tools.message_log()
        submit_button = html_tools.submit_button(req, "submit")
        if main_mode == "ov":
            low_submit = html_tools.checkbox(req, "sub")
            act_xen_tree = xen_tree(req, connection_log, change_log, low_submit.check_selection(""))
            select_button = html_tools.submit_button(req, "select")
            req.write("<form action=\"%s.py?%s\" method = post>" % (req.module_name,
                                                                    functions.get_sid(req)))
            req.write("<div class=\"center\">%s, domain filter %s, %s</div></form>\n" % (act_xen_tree.display_list(""),
                                                                                         act_xen_tree.domain_regex(""),
                                                                                         select_button("")))
            if act_xen_tree:
                act_xen_tree.fetch_domain_dicts()
                act_xen_tree.check_for_changes()
            req.write(connection_log.generate_stack("Connection log", show_only_errors=True, show_only_warnings=True))
            req.write(change_log.generate_stack("Change log"))
            if act_xen_tree:
                low_submit[""] = True
                req.write("<form action=\"%s.py?%s\" method = post>" % (req.module_name,
                                                                        functions.get_sid(req)))
                act_xen_tree.show_overview()
                req.write("%s%s%s<div class=\"center\">%s</div>\n" % (low_submit.create_hidden_var(),
                                                                      act_xen_tree.display_list.create_hidden_var(),
                                                                      act_xen_tree.domain_regex.create_hidden_var(),
                                                                      submit_button()))
                req.write("</form>")
        else:
            domain_idx, srv_name = (req.sys_args["idx"],
                                    req.sys_args["srv"])
            req.dc.execute("SELECT * FROM device WHERE device_idx=%d" % (int(domain_idx)))
            if not req.dc.rowcount:
                req.write(html_tools.gen_hline("No device (Domain) with this idx found", 1))
                req.write("<div class=\"center\"><a href=\"%s.py?%s&mm=ov\">Back to Overview</a>" % (req.module_name,
                                                                                                     functions.get_sid(req)))
            else:
                db_rec = req.dc.fetchone()
                dom_struct = xen_domain(db_rec["name"], {}, srv_name, log=change_log)
                dom_struct.link_db_device(db_rec)
                dom_struct.create_xen_device(req.dc)
                req.write("<form action=\"%s.py?%s&mm=%s&idx=%s&srv=%s\" method = post>" % (req.module_name,
                                                                                            functions.get_sid(req),
                                                                                            main_mode,
                                                                                            domain_idx,
                                                                                            srv_name))
                dom_struct.check_domain_details(req, change_log)
                req.write(change_log.generate_stack("Change log"))
                dom_struct.show_domain_details(req, change_log)
                req.write("<div class=\"center\">%s or <a href=\"%s.py?%s&mm=ov\">Back to Overview</a></div>\n" % (submit_button(),
                                                                                                                   req.module_name,
                                                                                                                   functions.get_sid(req)))
                req.write("</form>")
