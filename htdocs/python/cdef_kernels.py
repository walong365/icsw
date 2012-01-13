#!/usr/bin/python -Ot
#
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2007,2008 Andreas Lang-Nevyjel, init.at
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
""" kernel_stuff """

import html_tools
import logging_tools
import cgi
import md5
import config_tools
import time
import datetime
import server_command
import process_tools
import array
import re

class kernel_build(object):
    def __init__(self, in_dict):
        self.__build_machine = in_dict["kb.build_machine"]
        self.__version, self.__release = (in_dict["kb.version"],
                                          in_dict["kb.release"])
        self.__build_date = in_dict["kb.date"]
    def get_build_info(self):
        return "to %d.%d on %s, %s" % (self.__version,
                                       self.__release,
                                       self.__build_machine or "<not set>",
                                       self.__build_date.strftime("%a, %d. %b %Y %H:%M:%S"))
    
class kernel_machine_info(object):
    def __init__(self, in_dict):
        self.__keys = sorted([key for key in in_dict.keys() if key.count("md5")])
        self.__dict = dict([(key, in_dict[key]) for key in self.__keys])
    def keys(self):
        return self.__keys
    def has_key(self, key):
        return key in self.__keys
    def __getitem__(self, key):
        return self.__dict[key]
    def __eq__(self, other):
        # must be integers
        equal = False
        if sorted(self.keys()) == sorted(other.keys()):
            equal = True
            for key in self.keys():
                if self[key] != other[key]:
                    equal = False
        return equal
    def __ne__(self, other):
        equal = False
        if sorted(self.keys()) == sorted(other.keys()):
            equal = True
            for key in self.keys():
                if self[key] != other[key]:
                    equal = False
        return not equal
    def get_md5_differ_list(self, other):
        d_list = []
        missing_keys = [key for key in self.keys() if key not in other.keys()]
        toomuch_keys = [key for key in other.keys() if key not in self.keys()]
        differ_keys = [key for key in self.keys() if other.has_key(key) and self[key] != other[key]]
        if differ_keys:
            d_list.append("%s differ: %s" % (logging_tools.get_plural("key", len(differ_keys)),
                                             ", ".join(differ_keys)))
        if toomuch_keys:
            d_list.append("%s too much: %s" % (logging_tools.get_plural("key", len(toomuch_keys)),
                                               ", ".join(toomuch_keys)))
        if missing_keys:
            d_list.append("%s missing: %s" % (logging_tools.get_plural("key", len(missing_keys)),
                                              ", ".join(missing_keys)))
        return sorted(d_list)
    def get_md5_list(self):
        return self.keys()
        
class kernel(object):
    def __init__(self, req, k_idx, in_dict):
        self.__dict = in_dict
        self.__name = in_dict["name"]
        self.__idx, self.__db_idx = (k_idx, 
                                     in_dict["kernel_idx"])
        self.__arch, self.__sub_arch = (in_dict["cpu_arch"],
                                        in_dict["sub_cpu_arch"])
        self.__build_machine = in_dict["build_machine"]
        self.__initrd_built = in_dict["initrd_built"]
        self.__initrd_modules = [y for y in [x.strip() for x in (in_dict["module_list"] or "").split(",")] if y]
        self.__initrd_modules.sort()
        if in_dict["target_module_list"] == None:
            self.__tim_set = False
        else:
            self.__tim_set = True
        self.__target_initrd_modules = [y for y in [x.strip() for x in (in_dict["target_module_list"] or "").split(",")] if y]
        self.__target_initrd_modules.sort()
        self.__tim_field = html_tools.text_field(req, "tim", size=255, display_len=64)
        self.__build_list = []
        self.__build_sel_list = html_tools.selection_list(req, "kbl", {}, sort_new_keys=False, auto_reset=1)
        self.__build_sel_list[0] = "build overview"
        self.__build_sel_list.check_selection(self.get_suffix(), 0)
        self.__kernel_machines = {}
        self.__problems = {}
        self.__new_kernel_devices = {}
        self.__act_kernel_devices = {}
        self.__log_lines = []
        self.__consistency_action = 0
        self._sanitize_database(req.dc)
    def __getitem__(self, key):
        return self.__dict[key]
    def __setitem__(self, key, value):
        self.__dict[key] = value
    def get(self, key, def_value):
        return self.__dict.get(key, def_value)
    def _sanitize_database(self, dc):
        all_k_servers = config_tools.device_with_config("kernel_server", dc)
        all_k_servers.set_key_type("config")
        def_k_servers = all_k_servers.get("kernel_server", [])
        # remove all from kernel_database which is not related to an active server:
        if def_k_servers:
            idxs = [def_k_server.server_device_idx for def_k_server in def_k_servers]
            add_str = " AND ".join(["device != %d" % (idx) for idx in idxs])
            dc.execute("DELETE FROM kernel_log WHERE %s" % (add_str))
            dc.execute("DELETE FROM kernel_build WHERE %s" % (add_str))
            dc.execute("DELETE FROM kernel_local_info WHERE %s" % (add_str))
    def resolve_device_names(self, dc):
        search_idxs = set([line["device"] for line in self.__log_lines])
        if self["master_server"]:
            search_idxs.add(self["master_server"])
        if search_idxs:
            dc.execute("SELECT d.device_idx, d.name FROM device d WHERE %s" % (" OR ".join(["d.device_idx=%d" % (idx) for idx in search_idxs])))
            search_lut = dict([(db_rec["device_idx"], db_rec["name"]) for db_rec in dc.fetchall()])
        else:
            search_lut = {}
        # ???
        self.master_role = "mother"
        if self["master_server"]:
            self.master_name = search_lut.get(self["master_server"], "not found (%d)" % (self["master_server"]))
        else:
            self.master_name = "not set"
        # replace log_lines
        for ent in self.__log_lines:
            ent["server_name"] = search_lut.get(ent["device"], "srv %d" % (ent["device"]))
    def add_kernel_log(self, db_rec):
        self.__log_lines.append(db_rec)
    def add_new_kernel_device(self, nk_type, nkd_idx, nkd_name):
        self.__new_kernel_devices.setdefault(nk_type, []).append((nkd_idx, nkd_name))
    def get_new_kernel_num_refs(self):
        return sum([len(v) for v in self.__new_kernel_devices.values()])
    def set_consistency_action(self, ca):
        self.__consistency_action = ca
    def get_consistency_action(self):
        return self.__consistency_action
    consistency_action = property(get_consistency_action, set_consistency_action)
    def get_new_kernel_refs(self):
        o_f = []
        for rt in ["old", "new"]:
            dev_list = self.__new_kernel_devices.get(rt, [])
            if dev_list:
                o_f.append(logging_tools.compress_list(sorted([x[1] for x in dev_list])))
        return "; ".join(o_f)
    def add_act_kernel_device(self, ak_type, akd_idx, akd_name):
        self.__act_kernel_devices.setdefault(ak_type, []).append((akd_idx, akd_name))
    def get_act_kernel_num_refs(self):
        return sum([len(v) for v in self.__act_kernel_devices.values()])
    def get_act_kernel_refs(self):
        o_f = []
        for rt in ["old", "new"]:
            dev_list = self.__act_kernel_devices.get(rt, [])
            if dev_list:
                o_f.append(logging_tools.compress_list(sorted([x[1] for x in dev_list])))
        return "; ".join(o_f)
    def get_valid_stage1_flavours(self):
        return [key for key in ["cpio", "cramfs", "lo"] if self["stage1_%s_present" % (key)]]
    def get_initrd_built(self):
        return self.__initrd_built and self.__initrd_built.strftime("%a, %d. %b %Y %H:%M:%S") or None
    def get_initrd_modules(self):
        return self.__initrd_modules
    def get_tim_field(self):
        return self.__tim_field
    def add_kernel_info_from_machine(self, machrole_name, k_stuff):
        self.__kernel_machines[machrole_name] = kernel_machine_info(k_stuff)
    def get_consistency_info(self):
        k_machs = self.get_num_of_kernel_machines()
        if k_machs:
            all_machs = self.__kernel_machines.keys()
            master_pair = (self.master_name, self.master_role)
            if master_pair in all_machs:
                master_info = self.__kernel_machines[master_pair]
                md5_errors = {}
                for mach in [mach_name for mach_name in all_machs if mach_name != master_pair]:
                    if self.__kernel_machines[mach] != master_info:
                        md5_errors[mach] = ";".join(master_info.get_md5_differ_list(self.__kernel_machines[mach]))
                if md5_errors:
                    c_line = "warn: MD5-sums differ on %s from master_server: %s" % (logging_tools.get_plural("server", md5_errors.keys()),
                                                                                     ", ".join(["%s: %s" % (key, md5_errors[key]) for key in sorted(md5_errors.keys())]))
                else:
                    c_line = "ok: all %s ok on %s: %s" % (logging_tools.get_plural("MD5 sum", len(master_info.keys())),
                                                          logging_tools.get_plural("server", len(all_machs)),
                                                          ", ".join(sorted(["%s:%s" % (name, role) for name, role in all_machs])))
            else:
                if self["master_server"]:
                    c_line = "error: master_server %s:%s is not in server_list: %s" % (self.master_name,
                                                                                       self.master_role,
                                                                                       ", ".join(sorted(["%s:%s" % (name, role) for name, role in all_machs])))
                else:
                    c_line = "error not master_server defined"
        else:
            c_line = "error: No server serves this kernel"
        return c_line
    def get_suffix(self):
        return "k%d" % (self.__db_idx)
    def add_kernel_build(self, in_dict):
        self.__build_list.append(kernel_build(in_dict))
        self.__build_sel_list[in_dict["kernel_build_idx"]] = self.__build_list[-1].get_build_info()
    def get_idx(self):
        return self.__idx
    def get_db_idx(self):
        return self.__db_idx
    def get_arch(self):
        return "%s / %s" % (str(self.__arch),
                            str(self.__sub_arch))
    def get_name(self):
        return self.__name
    def get_xen_info(self, def_value="---"):
        info_str = "/".join([{"xen_host_kernel"  : "Host",
                              "xen_guest_kernel" : "Guest"}[db_name] for db_name in ["xen_host_kernel", "xen_guest_kernel"] if self[db_name]]) or def_value
        return info_str
    def get_num_of_kernel_builds(self):
        return len(self.__build_list)
    def get_kernel_build_sel_list(self):
        if self.__build_list:
            return self.__build_sel_list
        else:
            return "---"
    def get_build_machine(self):
        return self.__build_machine
    def get_kernel_machines(self, **args):
        if args.get("with_master", True):
            return sorted(self.__kernel_machines.keys())
        else:
            return sorted([name for name in self.__kernel_machines.keys() if name != self.master_name])
    def get_num_of_kernel_machines(self):
        return len(self.__kernel_machines.keys())
    def get_problems(self):
        return self.__problems
    def stages_ok(self, all_ok):
        if all_ok:
            return self["stage2_present"] and len([True for key in ["lo", "cramfs", "cpio"] if self["stage1_%s_present" % (key)]]) == 3
        else:
            return self["stage2_present"] and len([True for key in ["lo", "cramfs", "cpio"] if self["stage1_%s_present" % (key)]])
    def stages_error_str(self, show_ok):
        stage_keys = [("stage2_present", "s2")] + [("stage1_%s_present" % (key), "s1_%s" % (key)) for key in ["lo", "cramfs", "cpio"]]
        if show_ok:
            s_list = [s_key for l_key, s_key in stage_keys if self[l_key]]
        else:
            s_list = [s_key for l_key, s_key in stage_keys if not self[l_key]]
        return ", ".join(s_list) or "---"
    def add_problem_from_machine(self, host, prob_list):
        self.__problems.setdefault(host, []).extend(prob_list)
    def check_master_change(self, dc, action_log, master_list):
        new_m = master_list.check_selection(self.get_suffix(), 0)
        if new_m and new_m != self["master_server"]:
            m_name = master_list.list_dict[new_m]["name"]
            action_log.add_ok("setting master_server to '%s'" % (m_name), "SQL")
            dc.execute("UPDATE kernel SET master_server=%s WHERE kernel_idx=%s", (new_m,
                                                                                  self.__db_idx))
            self["master_server"] = new_m
            self.master_name = m_name
    def check_for_changes(self, dc, action_log):
        new_tim_str = self.__tim_field.check_selection(self.get_suffix(), " ".join(self.__target_initrd_modules))
        new_tim = []
        for nt_split in new_tim_str.split(","):
            if nt_split.strip():
                new_tim.extend([y.strip() for y in nt_split.split(" ") if y.strip()])
        new_tim = [x for x in new_tim if x not in ["autofs", "3w-xxxx", "3w-9xxx", "af_packet", "ext2", "ext3",
                                                   "gdth", "jbd", "libata", "mptctl", "mptbase", "mptscsih",
                                                   "sata_promise", "sata_via", "scsi_mod", "scsi_transport_spi",
                                                   "sd_mod", "sg", "sym53c8xx", "ata_piix", "lockd", "eata", "nfs", "reiserfs", "sunrpc", "runrpc"]]
        new_tim.sort()
        if new_tim != self.__target_initrd_modules or not self.__tim_set:
            if not self.__tim_set and new_tim == []:
                new_tim = self.__initrd_modules
            action_log.add_ok("Setting target_module_list to %s: %s" % (logging_tools.get_plural("module", len(new_tim)),
                                                                        ", ".join(new_tim)), "SQL")
            self.__target_initrd_modules = new_tim
            self.__tim_field[self.get_suffix()] = " ".join(new_tim)
            sql_str = "UPDATE kernel SET target_module_list='%s' WHERE kernel_idx=%d" % (",".join(self.__target_initrd_modules),
                                                                                         self.__db_idx)
            dc.execute(sql_str)
    def get_kernel_log(self):
        if self.__log_lines:
            out_lines = ["<div class=\"center\">Kernel log (%s)</div>" % (logging_tools.get_plural("line", len(self.__log_lines))),
                         "<div class=\"center\"><select size=\"%d\">" % (min(10, len(self.__log_lines)))]
            for entry in self.__log_lines:
                out_lines.append("<option class=\"mono%s\">%s:%s (%s): %s</option>" % ({logging_tools.LOG_LEVEL_OK   : "ok",
                                                                                        logging_tools.LOG_LEVEL_WARN : "warn"}.get(entry["log_level"], "error"),
                                                                                       entry["server_name"],
                                                                                       entry["syncer_role"],
                                                                                       entry["date"],
                                                                                       entry["log_str"]))
            out_lines.append("</div></select>")
        else:
            out_lines = ["<div class=\"center\">No Kernel log found</center>"]
        return "\n".join(out_lines)
        

class fetch_kernel_tree(object):
    def __init__(self, req, action_log):
        self.__req = req
        self.action_log = action_log
        self.fetch()
    def build_selection_list(self, **args):
        self.selection_list = html_tools.selection_list(self.__req, args.get("name", "kernel"), {0 : "--- not set ---"},
                                                        sort_new_keys=False,
                                                        show_indices=False)
        self.selection_list.add_pe_key("", -1, "--- keep actual ---")
        all_bcs = set([act_k["bitcount"] for act_k in self.__k_dict.itervalues()])
        add_idx = -1
        for act_bc in sorted(all_bcs):
            add_idx -= 1
            for k_name in sorted(self.__k_dict.keys()):
                act_k = self[k_name]
                self.selection_list[add_idx] = {"name"     : "--- %s ---" % ("%d Bit kernels" % (act_bc) if act_bc else "kernels with unkown bitcount"),
                                                "disabled" : True,
                                                "class"    : "inverse"}
                if act_k["bitcount"] == act_bc:
                    xen_info = act_k.get_xen_info("")
                    add_dict = {"name"         : "%s [%s.%s%s], %s, %s on %s" % (act_k["name"],
                                                                                 act_k["version"],
                                                                                 act_k["release"],
                                                                                 ", Xen: %s" % (xen_info) if xen_info else "",
                                                                                 ":".join(act_k.get_valid_stage1_flavours()) or "no valid stage1",
                                                                                 act_k["date"],
                                                                                 (act_k.get("build_machine", None) or "<unknown>").split(".")[0]),
                                "comment"      : act_k["comment"],
                                "comment_size" : 40,
                                "nosort"       : 1}
                    if not act_k["enabled"] or act_k["build_lock"]:
                        add_dict["disabled"] = True
                        add_dict["class"] = "error"
                        if act_k["build_lock"]:
                            add_dict["name"] += " (locked by %s)" % (act_k["build_machine"].split(".")[0])
                        if not act_k["enabled"]:
                            add_dict["name"] += ", disabled"
                    self.selection_list[act_k["kernel_idx"]] = add_dict
        self.selection_list.mode_is_normal()
    def fetch_local_info(self):
        if self.__k_lut:
            sql_str = "SELECT d.name, k.* FROM device d, kernel_local_info k WHERE k.device=d.device_idx AND (%s)" % (" OR ".join(["kernel=%d" % (idx) for idx in self.__k_lut.keys()]))
            self.__req.dc.execute(sql_str)
            for db_rec in self.__req.dc.fetchall():
                info_blob = db_rec["info_blob"]
                if type(info_blob) == type(array.array("c")):
                    info_blob = info_blob.tostring()
                try:
                    info_dict = server_command.net_to_sys(info_blob)
                except:
                    print process_tools.get_except_info()
                else:
                    self.__k_dict[self.__k_lut[db_rec["kernel"]]].add_kernel_info_from_machine((db_rec["name"], db_rec["syncer_role"]), info_dict)
    def fetch(self):
        self._init_basic_html_entities()
        self.__k_dict, self.__k_lut = ({}, {})
        self.__k_idx = 0
        self.__req.dc.execute("SELECT * FROM kernel k LEFT JOIN kernel_build kb ON kb.kernel=k.kernel_idx ORDER BY k.name, kb.date DESC")
        for db_rec in self.__req.dc.fetchall():
            if self.__act_regex.match(db_rec["name"]):
                self._add_kernel(db_rec)
        # add logs
        self.__req.dc.execute("SELECT * FROM kernel_log kl ORDER BY kl.date DESC, kl.kernel_log_idx DESC")
        for db_rec in self.__req.dc.fetchall():
            self._add_kernel_log(db_rec)
        self._resolve_device_names()
        self.__req.dc.execute("SELECT d.device_idx, d.name, d.newkernel, d.new_kernel, d.actkernel, d.act_kernel FROM device d")
        for db_rec in self.__req.dc.fetchall():
            self._add_device_usage(db_rec)
        self._init_html_entities()
    def _resolve_device_names(self):
        for kernel in self.__k_dict.itervalues():
            kernel.resolve_device_names(self.__req.dc)
    def _add_kernel(self, db_rec):
        if not self.__k_dict.has_key(db_rec["name"]):
            self.__k_idx += 1
            self.__k_dict[db_rec["name"]] = kernel(self.__req, self.__k_idx, db_rec)
            self.__k_lut[db_rec["kernel_idx"]] = db_rec["name"]
        if db_rec["kb.date"]:
            self[db_rec["name"]].add_kernel_build(db_rec)
    def _add_kernel_log(self, db_rec):
        if self.__k_lut.has_key(db_rec["kernel"]):
            self.__k_dict[self.__k_lut[db_rec["kernel"]]].add_kernel_log(db_rec)
    def _add_device_usage(self, db_rec):
        if db_rec["new_kernel"] and self.has_key(db_rec["new_kernel"]):
            self[db_rec["new_kernel"]].add_new_kernel_device("new", db_rec["device_idx"], db_rec["name"])
        elif db_rec["newkernel"] and self.has_key(db_rec["newkernel"]):
            self[db_rec["newkernel"]].add_new_kernel_device("old", db_rec["device_idx"], db_rec["name"])
        if db_rec["act_kernel"] and self.has_key(db_rec["act_kernel"]):
            self[db_rec["act_kernel"]].add_act_kernel_device("new", db_rec["device_idx"], db_rec["name"])
        elif db_rec["actkernel"] and self.has_key(db_rec["actkernel"]):
            self[db_rec["actkernel"]].add_act_kernel_device("old", db_rec["device_idx"], db_rec["name"])
    def __getitem__(self, key):
        if type(key) == type(""):
            return self.__k_dict[key]
        else:
            return self[self.__k_lut[key]]
    def __delitem__(self, key):
        del self.__k_dict[key]
    def get(self, key, default):
        if type(key) == type(""):
            return self.__k_dict.get(key, default)
        else:
            return self.get(self.__k_lut.get(key, ""), default)
    def has_key(self, key):
        if type(key) == type(""):
            return self.__k_dict.has_key(key)
        else:
            return self.__k_lut.has_key(key)
    def keys(self):
        return self.__k_dict.keys()
    def values(self):
        return self.__k_dict.values()
    def _init_basic_html_entities(self):
        # display list
        self.disp_list = html_tools.selection_list(self.__req, "dl", {"sb" : {"name" : "build history",
                                                                              "pri"  : -100},
                                                                      "sk" : {"name" : "kernel consistency",
                                                                              "pri"  : -50},
                                                                      "sd" : {"name" : "associated device(s)",
                                                                              "pri"  : -10},
                                                                      "sm" : {"name" : "module info",
                                                                              "pri"  : 0},
                                                                      "sl" : {"name" : "kernel logs",
                                                                              "pri"  : 10}}, inital_mode="n", use_priority_key=True, multiple=True, size=5)
        self.disp_sel = self.disp_list.check_selection("", [])
        self.kernel_regex = html_tools.text_field(self.__req, "kreg", size=182, display_len=16)
        self.__act_regex = re.compile("%s" % (self.kernel_regex.check_selection("", "") or ".*"))
    def _init_html_entities(self):
        self.__k_del_button = html_tools.checkbox(self.__req, "dk", auto_reset=1)
        self.__cons_list = html_tools.selection_list(self.__req, "ccs", {0 : "---",
                                                                         1 : "check consistency (on all servers)",
                                                                         2 : "sync from master to known servers",
                                                                         3 : "sync from master to all servers"}, sort_new_keys=False, auto_reset=True)
        all_k_servers = config_tools.device_with_config("kernel_server", self.__req.dc)
        all_k_servers.set_key_type("config")
        all_m_servers = config_tools.device_with_config("mother_server", self.__req.dc)
        all_m_servers.set_key_type("config")
        all_x_servers = config_tools.device_with_config("xen_server", self.__req.dc)
        all_x_servers.set_key_type("config")
        self.all_mother_servers = [value.short_host_name for value in all_m_servers.get("mother_server", [])]
        self.all_xen_servers = [value.short_host_name for value in all_x_servers.get("xen_server", [])]
        self.all_kernel_servers = [value.short_host_name for value in all_k_servers.get("kernel_server", [])]
        self.all_kernel_servers = [(s_name, "mother") for s_name in self.all_kernel_servers if s_name in self.all_mother_servers] + \
            [(s_name, "xen") for s_name in self.all_kernel_servers if s_name in self.all_xen_servers]
        self.__master_list = html_tools.selection_list(self.__req, "kmas", {0 : "keep"}, sort_new_keys=False, auto_reset=True)
        name_lut = dict([(value.short_host_name, value) for value in all_m_servers.get("mother_server", [])])
        for m_name in sorted(name_lut.keys()):
            self.__master_list[name_lut[m_name].server_device_idx] = m_name
    def get_consistency_action_kernels(self):
        return dict([(name, k_stuff.consistency_action) for name, k_stuff in self.__k_dict.iteritems() if k_stuff.consistency_action])
    def check_for_changes(self):
        disp_sel = self.disp_sel
        kernels_to_delete = []
        for k_name in self.keys():
            k_stuff = self[k_name]
            k_del = self.__k_del_button.check_selection(k_stuff.get_suffix())
            if k_del:
                kernels_to_delete.append(k_name)
                self.action_log.add_ok("Deleting kernel '%s' from database" % (k_name), "SQL")
            else:
                k_stuff.consistency_action = self.__cons_list.check_selection(k_stuff.get_suffix(), 0)
                k_stuff.check_master_change(self.__req.dc, self.action_log, self.__master_list)
                if "sm" in disp_sel:
                    k_stuff.check_for_changes(self.__req.dc, self.action_log)
        if kernels_to_delete:
            sql_str = "DELETE FROM kernel_log WHERE %s" % (" OR ".join(["kernel=%d" % (self[x].get_db_idx()) for x in kernels_to_delete]))
            self.__req.dc.execute(sql_str)
            sql_str = "DELETE FROM kernel_local_info WHERE %s" % (" OR ".join(["kernel=%d" % (self[x].get_db_idx()) for x in kernels_to_delete]))
            self.__req.dc.execute(sql_str)
            sql_str = "DELETE FROM kernel_build WHERE %s" % (" OR ".join(["kernel=%d" % (self[x].get_db_idx()) for x in kernels_to_delete]))
            self.__req.dc.execute(sql_str)
            sql_str = "DELETE FROM kernel WHERE %s" % (" OR ".join(["kernel_idx=%d" % (self[x].get_db_idx()) for x in kernels_to_delete]))
            self.__req.dc.execute(sql_str)
            for k_name in kernels_to_delete:
                del self[k_name]
    def show_table(self):
        disp_sel = self.disp_sel
        kern_table = html_tools.html_table(cls="normalsmall")
        kern_table[0]["class"] = "line00"
        headers = ["Name", "del", "master", "set master", "#servers", "Xen", "64Bit", "Arch", "Version.Release", "#builds", "maj/min/pl", "newrefs", "actrefs", "build device", "stages ok", "missing"]
        for head in headers:
            kern_table[None][0] = html_tools.content(head, type="th", cls="center")
        if self.keys():
            s_column = 3
            line_size = len(headers)
            self.__req.write(kern_table.get_header())
            self.__req.write(kern_table.flush_lines())
            line_idx = 1
            for k_name in sorted(self.keys()):
                act_kernel = self[k_name]
                line_idx = 1 - line_idx
                kernel_color = "line1%d" % (line_idx)
                kern_table[0][s_column] = html_tools.content("%s:%s" % (act_kernel.master_name, act_kernel.master_role) if act_kernel["master_server"] else "none", cls="left")
                kern_table[None][0] = html_tools.content(self.__master_list, act_kernel.get_suffix(), cls="center")
                kern_table[None][0] = html_tools.content("%d" % (act_kernel.get_num_of_kernel_machines()), cls="center")
                kern_table[None][0] = html_tools.content(act_kernel.get_xen_info(), cls="center")
                bc_str = {64 : "yes",
                          32 : "no"}.get(act_kernel["bitcount"], "???")
                kern_table[None][0] = html_tools.content(bc_str, cls="errorcenter" if bc_str == "???" else "center")
                kern_table[None][0] = html_tools.content(act_kernel.get_arch(), cls="center")
                kern_table[None][0] = html_tools.content("%s.%s" % (str(act_kernel["version"]),
                                                                    str(act_kernel["release"])), cls="center")
                kern_table[None][0] = html_tools.content(str(act_kernel["builds"]), cls="center")
                kern_table[None][0] = html_tools.content("%s / %s / %s" % (str(act_kernel["major"]),
                                                                           str(act_kernel["minor"]),
                                                                           str(act_kernel["patchlevel"])), cls="center")
                nknr = act_kernel.get_new_kernel_num_refs()
                aknr = act_kernel.get_act_kernel_num_refs()
                kern_table[None][0] = html_tools.content(nknr and "%d" % (nknr) or "---", cls="center")
                kern_table[None][0] = html_tools.content(aknr and "%d" % (aknr) or "---", cls="center")
                kern_table[None][0] = html_tools.content(cgi.escape(act_kernel.get_build_machine() or "<not set>"), cls="center")
                kern_table[None][0] = html_tools.content(act_kernel.stages_error_str(True) , cls="center" if act_kernel.stages_ok(False) else "errorcenter")
                kern_table[None][0] = html_tools.content(act_kernel.stages_error_str(False), cls="center" if act_kernel.stages_ok(True)  else "warncenter")
                if "sb" in disp_sel:
                    kern_table[0][s_column:len(headers)] = html_tools.content(["initrd built ",
                                                                               act_kernel.get_initrd_built() or "never",
                                                                               ", ",
                                                                               logging_tools.get_plural("build", act_kernel.get_num_of_kernel_builds()),
                                                                               " : ",
                                                                               act_kernel.get_kernel_build_sel_list()], act_kernel.get_suffix(), cls="left")
                if "sk" in disp_sel:
                    line = act_kernel.get_consistency_info()
                    kern_table[0][s_column:len(headers)] = html_tools.content(["action:", self.__cons_list], cls="left")
                    line = act_kernel.get_consistency_info()
                    kern_table[0][s_column:len(headers)] = html_tools.content(line, cls={"ok"    : "left",
                                                                                         "warn"  : "warn",
                                                                                         "error" : "error"}.get(line.split(":")[0], "error"))
                probs = act_kernel.get_problems()
                if probs:
                    kern_table[0][s_column:len(headers)] = html_tools.content("Problems: %s" % ("; ".join(["%s: %s" % (h, ", ".join(["%s:%s" % (a, b) for a, b in hp])) for h, hp in probs.iteritems()])))
                    kernel_color = "devwarn"

                if "sm" in disp_sel:
                    kern_table[0][s_column:len(headers)] = html_tools.content(["Requested modules: ", act_kernel.get_tim_field()], act_kernel.get_suffix(), cls="left")
                    if act_kernel.get_initrd_built():
                        k_mods = act_kernel.get_initrd_modules()
                        if k_mods:
                            kern_table[0][s_column:len(headers)] = html_tools.content("%s in actual initrd (stage1): %s" % (logging_tools.get_plural("module", len(k_mods)),
                                                                                                                            ", ".join(k_mods)), cls="left")
                        else:
                            kern_table[0][s_column:len(headers)] = html_tools.content("no modules in initrd (stage1)", cls="left")
                if "sd" in disp_sel:
                    if nknr:
                        kern_table[0][s_column:len(headers)] = html_tools.content("New References: %s" % (act_kernel.get_new_kernel_refs()))
                    if aknr:
                        kern_table[0][s_column:len(headers)] = html_tools.content("Actual References: %s" % (act_kernel.get_act_kernel_refs()))
                if "sl" in disp_sel:
                    kern_table[0][s_column:len(headers)] = html_tools.content(act_kernel.get_kernel_log(), cls="left", beautify=False)
                act_line = kern_table.get_cursor()[0]
                kern_table[1:act_line]["class"] = kernel_color
                if act_kernel.get_new_kernel_num_refs():
                    kern_table[1:act_line][1:2] = html_tools.content(act_kernel.get_name(), cls="left")
                else:
                    kern_table[1:act_line][1] = html_tools.content(act_kernel.get_name(), cls="left")
                    kern_table[1:act_line][2] = html_tools.content(self.__k_del_button, act_kernel.get_suffix(), cls="errormin")
                self.__req.write(kern_table.flush_lines(act_kernel.get_suffix()))
            self.__req.write(kern_table.get_footer())

class new_kernel(object):
    def __init__(self, req, name):
        self.__req = req
        self.__name = name
        self.__kernel_machines = {}
        self.__uid = md5.new(name).hexdigest()
        self.__device_list = html_tools.selection_list(req, "tkd", {}, sort_new_keys=0)
    def get_name(self):
        return self.__name
    def add_machine(self, mach_name, mach_role):
        self.__kernel_machines[(mach_name, mach_role)] = None
        self.__device_list[len(self.__kernel_machines)] = "%s:%s" % (mach_name, mach_role)
    def get_server_info(self):
        servers = self.__kernel_machines.keys()
        return "%s: %s" % (logging_tools.get_plural("device", len(servers)),
                           ", ".join(["%s:%s" % (m_name, m_role) for m_name, m_role in sorted(servers)]))
    def get_take_device(self):
        d_num = self.__device_list.check_selection(self.get_suffix(), 0) - 1
        if d_num >= 0 and d_num < len(self.__kernel_machines.keys()):
            dev_name, dev_role = self.__kernel_machines.keys()[d_num]
        else:
            dev_name, dev_role = ("", "")
        return dev_name, dev_role
    def get_suffix(self):
        return "nk%s" % (self.__uid)
    def get_device_list(self):
        return self.__device_list
