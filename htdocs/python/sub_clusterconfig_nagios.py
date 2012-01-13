#!/usr/bin/python -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008 Andreas Lang-Nevyjel, init.at
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

import logging_tools
import html_tools
import tools
import re
import cdef_config
import cdef_nagios

class new_time_range_vs(html_tools.validate_struct):
    def __init__(self, req, time_ranges):
        new_dict = {"name"  : {"he"  : html_tools.text_field(req, "pn",  size=63, display_len=20),
                               "new" : 1,
                               "vf"  : self.validate_name,
                               "def" : ""},
                    "alias" : {"he"  : html_tools.text_field(req, "pa", size=128, display_len=20),
                               "def" : "New timerange"},
                    "del"   : {"he"  : html_tools.checkbox(req, "pd", auto_reset=1),
                               "del" : 1}}
        for tr in time_ranges:
            new_dict["%srange" % (tr)] = {"he"  : html_tools.text_field(req, "pr%s" % (tr), size=16, display_len=12),
                                          "vf"  : getattr(self, "validate_%srange" % (tr)),
                                          "def" : "00:00-24:00"}
        html_tools.validate_struct.__init__(self, req, "Nagios timerange", new_dict)
    def validate_name(self):
        if self.new_val_dict["name"] in self.names:
            self.new_val_dict["name"] = self.old_val_dict["name"]
            raise ValueError, "already used"
    def validate_monrange(self):
        self.validate_range("mon")
    def validate_tuerange(self):
        self.validate_range("tue")
    def validate_wedrange(self):
        self.validate_range("wed")
    def validate_thurange(self):
        self.validate_range("thu")
    def validate_frirange(self):
        self.validate_range("fri")
    def validate_satrange(self):
        self.validate_range("sat")
    def validate_sunrange(self):
        self.validate_range("sun")
    def validate_range(self, name):
        r_name = "%srange" % (name)
        tf_re = re.compile("^(?P<sh>\d+):(?P<sm>\d+)-(?P<eh>\d+):(?P<em>\d+)$")
        tf_m = tf_re.match(self.new_val_dict[r_name])
        if not tf_m:
            raise ValueError, "wrong timeframe (parse error) for %s" % (name)
        else:
            s_h, s_m = (int(tf_m.group("sh")), int(tf_m.group("sm")))
            e_h, e_m = (int(tf_m.group("eh")), int(tf_m.group("em")))
            s_min = 60 * s_h + s_m
            e_min = 60 * e_h + e_m
            if s_min < 0:
                raise ValueError, "wrong timeframe (start_time < 00:00) for %s" % (name)
            elif e_min > 1440:
                raise ValueError, "wrong timeframe (end_time > 24:00) for %s" % (name)
            elif s_min > e_min:
                raise ValueError, "wrong timeframe (start_time > end_time) for %s" % (name)
            else:
                self.new_val_dict[r_name] = "%02d:%02d-%02d:%02d" % (s_h, s_m, e_h, e_m)

class new_contact_group_vs(html_tools.validate_struct):
    def __init__(self, req, ng_g_dgroups, ng_g_members, ng_g_templates):
        html_tools.validate_struct.__init__(self, req, "Nagios Contactgroup",
                                            {"name"              : {"he"  : html_tools.text_field(req, "gn",  size=63, display_len=20),
                                                                    "new" : 1,
                                                                    "vf"  : self.validate_name,
                                                                    "def" : ""},
                                             "alias"             : {"he"  : html_tools.text_field(req, "ga", size=128, display_len=20),
                                                                    "def" : "New Contactgroup"},
                                             "device_groups"     : {"he"  : ng_g_dgroups,
                                                                    "def" : [],
                                                                    "vf"  : self.validate_dgroups},
                                             "members"           : {"he"  : ng_g_members,
                                                                    "def" : [],
                                                                    "vf"  : self.validate_members},
                                             "service_templates" : {"he"  : ng_g_templates,
                                                                    "def" : [],
                                                                    "vf"  : self.validate_templates},
                                             "del"               : {"he"  : html_tools.checkbox(req, "gd", auto_reset=1),
                                                                    "del" : 1}})
        self.__device_groups_dict = ng_g_dgroups
        self.__members_dict       = ng_g_members
        self.__templates_dict     = ng_g_templates
    def validate_name(self):
        if self.new_val_dict["name"] in self.names:
            self.new_val_dict["name"] = self.old_val_dict["name"]
            raise ValueError, "already used"
    def validate_dgroups(self):
        def get_list(idx_f):
            if not idx_f:
                return "empty"
            else:
                return ", ".join([self.__device_groups_dict.list_dict.get(x, {"name" : "key %d not found" % (x)})["name"] for x in idx_f])
        # remove unknown keys
        self.new_val_dict["device_groups"] = [x for x in self.new_val_dict["device_groups"] if self.__device_groups_dict.list_dict.has_key(x)]
        self.old_b_val_dict["device_groups"] = get_list(self.old_val_dict["device_groups"])
        self.new_b_val_dict["device_groups"] = get_list(self.new_val_dict["device_groups"])
    def validate_members(self):
        def get_list(idx_f):
            if not idx_f:
                return "empty"
            else:
                return ", ".join([self.__members_dict.list_dict.get(x, {"name" : "key %d not found" % (x)})["name"] for x in idx_f])
        # remove unknown keys
        self.new_val_dict["members"] = [x for x in self.new_val_dict["members"] if self.__members_dict.list_dict.has_key(x)]
        self.old_b_val_dict["members"] = get_list(self.old_val_dict["members"])
        self.new_b_val_dict["members"] = get_list(self.new_val_dict["members"])
    def validate_templates(self):
        def get_list(idx_f):
            if not idx_f:
                return "empty"
            else:
                return ", ".join([self.__templates_dict.list_dict.get(x, {"name" : "key %d not found" % (x)})["name"] for x in idx_f])
        # remove unknown keys
        self.new_val_dict["service_templates"] = [x for x in self.new_val_dict["service_templates"] if self.__templates_dict.list_dict.has_key(x)]
        self.old_b_val_dict["service_templates"] = get_list(self.old_val_dict["service_templates"])
        self.new_b_val_dict["service_templates"] = get_list(self.new_val_dict["service_templates"])

class new_contact_vs(html_tools.validate_struct):
    def __init__(self, req, first_period_idx, ng_c_users, ng_c_snps, ng_c_hnps):
        html_tools.validate_struct.__init__(self, req, "Nagios Contact",
                                            {"user"          : {"he"  : ng_c_users,
                                                                "new" : 1,
                                                                "vf"  : self.validate_user,
                                                                "def" : 0},
                                             "snperiod"      : {"he"  : ng_c_snps,
                                                                "def" : first_period_idx},
                                             "hnperiod"      : {"he"  : ng_c_hnps,
                                                                "def" : first_period_idx},
                                             "snrecovery"    : {"he"  : html_tools.checkbox(req, "csnr"),
                                                                "def" : True},
                                             "snwarning"     : {"he"  : html_tools.checkbox(req, "csnw"),
                                                                "def" : True},
                                             "sncritical"    : {"he"  : html_tools.checkbox(req, "csnc"),
                                                                "def" : True},
                                             "snunknown"     : {"he"  : html_tools.checkbox(req, "csnu"),
                                                                "def" : False},
                                             "hnrecovery"    : {"he"  : html_tools.checkbox(req, "chnr"),
                                                                "def" : True},
                                             "hndown"        : {"he"  : html_tools.checkbox(req, "chnd"),
                                                                "def" : True},
                                             "hnunreachable" : {"he"  : html_tools.checkbox(req, "chnu"),
                                                                "def" : False},
                                             "del"           : {"he"  : html_tools.checkbox(req, "cd", auto_reset=1),
                                                                "del" : 1}})
    def validate_user(self):
        self.old_b_val_dict["user"] = self.users.get(self.old_val_dict["user"], "not set")
        self.new_b_val_dict["user"] = self.users.get(self.new_val_dict["user"], "not set")
        if self.new_val_dict["user"] in self.users:
            self.new_val_dict["user"] = 0
            raise ValueError, "User already used"

class new_service_vs(html_tools.validate_struct):
    def __init__(self, req, first_period_idx, ng_s_attempts, ng_s_checks, ng_s_retries, ng_s_notif, ng_s_nsc, ng_s_nsn):
        html_tools.validate_struct.__init__(self, req, "Service template",
                                            {"name"           : {"he"  : html_tools.text_field(req, "sn", size=63, display_len=20),
                                                                 "new" : 1,
                                                                 "vf"  : self.validate_name,
                                                                 "def" : ""},
                                             "del"            : {"he"  : html_tools.checkbox(req, "sd", auto_reset=1),
                                                                 "del" : 1},
                                             "max_attempts"   : {"he"  : ng_s_attempts,
                                                                 "def" : 1},
                                             "check_interval" : {"he"  : ng_s_checks,
                                                                 "def" : 1},
                                             "retry_interval" : {"he"  : ng_s_retries,
                                                                 "def" : 1},
                                             "nsc_period"     : {"he"  : ng_s_nsc,
                                                                 "def" : first_period_idx},
                                             "nsn_period"     : {"he"  : ng_s_nsn,
                                                                 "def" : first_period_idx},
                                             "volatile"       : {"he"  : html_tools.checkbox(req, "svol"),
                                                                 "def" : False},
                                             "ninterval"      : {"he"  : ng_s_notif,
                                                                 "def" : 0},
                                             "nrecovery"      : {"he"  : html_tools.checkbox(req, "snr"),
                                                                 "def" : True},
                                             "ncritical"      : {"he"  : html_tools.checkbox(req, "snc"),
                                                                 "def" : True},
                                             "nwarning"       : {"he"  : html_tools.checkbox(req, "snw"),
                                                                 "def" : True},
                                             "nunknown"       : {"he"  : html_tools.checkbox(req, "snu"),
                                                                 "def" : False}}
                                             )
    def validate_name(self):
        if self.new_val_dict["name"] in self.names:
            self.new_val_dict["name"] = ""
            raise ValueError, "Name already used"

class new_device_vs(html_tools.validate_struct):
    def __init__(self, req, first_period_idx, ng_d_templates, ng_d_attempts, ng_d_ng, ng_d_notif):
        html_tools.validate_struct.__init__(self, req, "Device template",
                                            {"name"             : {"he"  : html_tools.text_field(req, "dn", size=63, display_len=20),
                                                                   "new" : 1,
                                                                   "vf"  : self.validate_name,
                                                                   "def" : ""},
                                             "ng_service_templ" : {"he"  : ng_d_templates,
                                                                   "def" : (ng_d_templates.get_sort_list() + [0])[0]},
                                             "max_attempts"     : {"he"  : ng_d_attempts,
                                                                   "def" : 1},
                                             "ng_period"        : {"he"  : ng_d_ng,
                                                                   "def" : first_period_idx},
                                             "ninterval"        : {"he"  : ng_d_notif,
                                                                   "def" : 0},
                                             "nrecovery"        : {"he"  : html_tools.checkbox(req, "dnr"),
                                                                   "def" : 1},
                                             "ndown"            : {"he"  : html_tools.checkbox(req, "dnd"),
                                                                   "def" : 1},
                                             "nunreachable"     : {"he"  : html_tools.checkbox(req, "dnu"),
                                                                   "def" : 1},
                                             "del"              : {"he"  : html_tools.checkbox(req, "dd", auto_reset=1),
                                                                   "del" : 1}})
    def validate_name(self):
        if self.new_val_dict["name"] in self.names:
            self.new_val_dict["name"] = ""
            raise ValueError, "Name already used"

class new_nagios_vs(html_tools.validate_struct):
    def __init__(self, req, config_list, nag_class, ncct_list):
        html_tools.validate_struct.__init__(self, req, "nagios_command",
                                            {"new_config"            : {"he"  : config_list},
                                             "command_line"          : {"he"  : html_tools.text_field(req, "cnc", size=255, display_len=45),
                                                                        "vf"  : self.validate_command,
                                                                        "def" : ""},
                                             "description"           : {"he"  : html_tools.text_field(req, "cne", size=255, display_len=25),
                                                                        "def" : "New nagios config"},
                                             "ng_service_templ"      : {"he"  : nag_class,
                                                                        "vf"  : self.validate_ngt,
                                                                        "def" : 0},
                                             "ng_check_command_type" : {"he"  : ncct_list,
                                                                        "vf"  : self.validate_nct,
                                                                        "def" : 0}})
    def validate_name(self):
        if not self.new_val_dict["name"]:
            self.new_val_dict["name"] = self.old_val_dict["name"]
            raise ValueError, "must not be empty"
    def validate_command(self):
        if not self.new_val_dict["command_line"]:
            raise ValueError, "must not be empty"
    def validate_ngt(self):
        oi, ni = (int(self.old_val_dict["ng_service_templ"]),
                  int(self.new_val_dict["ng_service_templ"]))
        self.old_b_val_dict["ng_service_templ"] = self.ng_service_templates.get(oi,
                                                                                {"name" : "not set"})["name"]
        self.new_b_val_dict["ng_service_templ"] = self.ng_service_templates.get(ni,
                                                                                {"name" : "not set"})["name"]
    def validate_nct(self):
        oi, ni = (int(self.old_val_dict["ng_check_command_type"]),
                  int(self.new_val_dict["ng_check_command_type"]))
        self.old_b_val_dict["ng_check_command_type"] = self.act_ng_check_command_types.get(oi,
                                                                                           {"name" : "not set"})["name"]
        self.new_b_val_dict["ng_check_command_type"] = self.act_ng_check_command_types.get(ni,
                                                                                           {"name" : "not set"})["name"]

def show_nagios_options(req, sub_sel):
    if sub_sel == "a":
        show_global_nagios_options(req)
    else:
        show_local_nagios_options(req)

def show_local_nagios_options(req):
    low_submit = html_tools.checkbox(req, "sub")
    sub = low_submit.check_selection("")
    change_log = html_tools.message_log()
    # nagios
    nag_class  = html_tools.selection_list(req, "cns", {}, sort_new_keys=0)
    ng_service_templates = tools.get_ng_service_templates(req.dc)
    ng_service_templates[0] = {"name" : "default"}
    for key, value in ng_service_templates.iteritems():
        nag_class[key] = value["name"]
    nag_class.mode_is_normal()
    # config types
    act_ng_check_command_types = tools.ng_check_command_types(req.dc, change_log)
    ncct_list = html_tools.selection_list(req, "ncct", {0 : "none"}, sort_new_keys=False)
    for key, value in act_ng_check_command_types.iteritems():
        ncct_list[key] = value["name"]
    ncct_list.mode_is_normal()
    # configs
    req.dc.execute("SELECT name, new_config_idx FROM new_config ORDER BY name")
    ng_configs_list = html_tools.selection_list(req, "cle", sort_new_keys=False)
    for db_rec in req.dc.fetchall():
        ng_configs_list[db_rec["new_config_idx"]] = db_rec["name"]
    nag_vs = new_nagios_vs(req, ng_configs_list, nag_class, ncct_list)
    # fetch all nagios configs
    nag_dict = {}
    req.dc.execute("SELECT c.*, nc.name AS nc_name FROM ng_check_command c, new_config nc WHERE c.new_config=nc.new_config_idx ORDER BY c.name")
    for db_rec in req.dc.fetchall():
        new_nag = cdef_config.config_nagios(db_rec["name"], db_rec["ng_check_command_idx"], db_rec)
        new_nag.config_name = db_rec["nc_name"]
        nag_dict[db_rec["ng_check_command_idx"]] = new_nag
        new_nag.act_values_are_default()
    for nag_idx in nag_dict.keys():
        n_stuff = nag_dict[nag_idx]
        nag_vs.ng_service_templates = ng_service_templates
        nag_vs.act_ng_check_command_types = act_ng_check_command_types
        nag_vs.link_object(nag_idx, n_stuff, False)
        nag_vs.check_for_changes()
        nag_vs.process_changes(change_log, {})
        nag_vs.unlink_object()
    if sub:
        tools.signal_nagios_config_server(req, change_log)
    req.write(change_log.generate_stack("Action log"))
    # nagios names
    nag_name_dict = {}
    for key, value in nag_dict.iteritems():
        nag_name_dict.setdefault(value["name"], []).append(key)
    out_table = html_tools.html_table(cls="normal")
    out_table[0]["class"] = "line00"
    for what in ["Name", "Config", "Service_templ", "command_line", "DisplayString", "Command_type"]:
        out_table[None][0] = html_tools.content(what, cls="center", type="th")
    req.write(html_tools.gen_hline("Found %s" % (logging_tools.get_plural("Nagios Checkcommand", len(nag_dict.keys()))), 3))
    line_idx = 1
    for nag_name in sorted(nag_name_dict.keys()):
        for idx in sorted(nag_name_dict[nag_name]):
            nag_stuff = nag_dict[idx]
            line_idx = 1 - line_idx
            out_table[0]["class"] = "line1%d" % (line_idx % 2)
            out_table[None][0] = html_tools.content(nag_name, cls="left")
            #out_table[None][0] = html_tools.content(nag_stuff.config_name, cls="left")
            out_table[None][0] = html_tools.content(nag_vs.get_he("new_config"), nag_stuff.get_suffix(), cls="center")
            out_table[None][0] = html_tools.content(nag_vs.get_he("ng_service_templ"), nag_stuff.get_suffix(), cls="center")
            out_table[None][0] = html_tools.content(nag_vs.get_he("command_line"), nag_stuff.get_suffix(), cls="center")
            out_table[None][0] = html_tools.content(nag_vs.get_he("description"), nag_stuff.get_suffix(), cls="center")
            out_table[None][0] = html_tools.content(nag_vs.get_he("ng_check_command_type"), nag_stuff.get_suffix(), cls="center")
    req.write(out_table(""))
    low_submit[""] = 1
    submit_button = html_tools.submit_button(req, "submit")
    submit_button.set_class("", "button")
    req.write("%s<div class=\"center\">%s</div>\n" % (low_submit.create_hidden_var(),
                                                      submit_button("")))

def show_global_nagios_options(req):
    low_submit = html_tools.checkbox(req, "sub")
    sub = low_submit.check_selection("")
    change_log = html_tools.message_log()
    # nagios time_periods
    ng_periods = tools.get_nagios_periods(req.dc)
    time_ranges = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    if not ng_periods:
        change_log.add_ok("Adding default Nagios period", "ok")
        req.dc.execute("INSERT INTO ng_period SET name='always', alias='Always', %s" % (", ".join(["%srange='00:00-24:00'" % (x) for x in time_ranges])))
        ng_periods = tools.get_nagios_periods(req.dc)
    ng_p_vs = new_time_range_vs(req, time_ranges)
    # sel_list for all time ranges
    ng_c_snp_field = html_tools.selection_list(req, "csnp")
    ng_c_hnp_field = html_tools.selection_list(req, "chnp")
    ng_s_nsc_field = html_tools.selection_list(req, "snsc")
    ng_s_nsn_field = html_tools.selection_list(req, "snsn")
    ng_d_ng_field  = html_tools.selection_list(req,  "dng")
    ng_p_dict = tools.ordered_dict()
    for ng_p_idx, ng_p_stuff in ng_periods.iteritems():
        ng_p_dict[ng_p_idx] = cdef_nagios.ng_period(ng_p_stuff["name"], ng_p_idx, ng_p_stuff)
        ng_c_snp_field[ng_p_idx] = ng_p_stuff["name"]
        ng_c_hnp_field[ng_p_idx] = ng_p_stuff["name"]
        ng_s_nsc_field[ng_p_idx] = ng_p_stuff["name"]
        ng_s_nsn_field[ng_p_idx] = ng_p_stuff["name"]
        ng_d_ng_field[ng_p_idx]  = ng_p_stuff["name"]
        ng_p_dict[ng_p_idx].act_values_are_default()
    ng_p_dict[0] = cdef_nagios.ng_period(ng_p_vs.get_default_value("name"), 0, ng_p_vs.get_default_dict())
    ng_p_dict[0].act_values_are_default()
    # nagios contact_groups
    ng_groups = tools.get_nagios_contact_groups(req.dc)
    if not ng_groups:
        change_log.add_ok("Adding default Nagios contact_group", "ok")
        req.dc.execute("INSERT INTO ng_contactgroup SET name='admins', alias='Default contactgroup'")
        ng_groups = tools.get_nagios_contact_groups(req.dc)
    ng_g_members_field   = html_tools.selection_list(req, "cgm", multiple = 1, size = 4, sort_new_keys=0)
    ng_g_dgroups_field   = html_tools.selection_list(req, "cgd", multiple = 1, size = 4, sort_new_keys=0)
    ng_g_templates_field = html_tools.selection_list(req, "cgs", multiple = 1, size = 4, sort_new_keys=0)
    ng_d_templates_field = html_tools.selection_list(req, "dts", sort_new_keys=0)
    ng_g_dict = tools.ordered_dict()
    for ng_g_idx, ng_g_stuff in ng_groups.iteritems():
        ng_g_dict[ng_g_idx] = cdef_nagios.ng_contactgroup(ng_g_stuff["name"], ng_g_idx, ng_g_stuff)
    ng_g_vs = new_contact_group_vs(req, ng_g_dgroups_field, ng_g_members_field, ng_g_templates_field)
    # fetch device_groups
    req.dc.execute("SELECT dg.*, c.* FROM device_group dg LEFT JOIN ng_device_contact c ON c.device_group=dg.device_group_idx ORDER BY dg.name")
    dg_added = []
    for db_rec in req.dc.fetchall():
        if db_rec["device_group_idx"] not in dg_added:
            dg_added.append(db_rec["device_group_idx"])
            ng_g_dgroups_field[db_rec["device_group_idx"]] = db_rec["name"]
        if db_rec["ng_contactgroup"]:
            if ng_g_dict.has_key(db_rec["ng_contactgroup"]):
                ng_g_dict[db_rec["ng_contactgroup"]].add_device_group(db_rec["device_group"])
    # fetch members
    req.dc.execute("SELECT c.* FROM ng_contactgroup cg LEFT JOIN ng_ccgroup c ON c.ng_contactgroup=cg.ng_contactgroup_idx")
    for db_rec in req.dc.fetchall():
        if db_rec["ng_contactgroup"]:
            if ng_g_dict.has_key(db_rec["ng_contactgroup"]):
                ng_g_dict[db_rec["ng_contactgroup"]].add_member(db_rec["ng_contact"])
    # fetch templates
    req.dc.execute("SELECT c.* FROM ng_service_templ st LEFT JOIN ng_cgservicet c ON c.ng_service_templ=st.ng_service_templ_idx")
    for db_rec in req.dc.fetchall():
        if db_rec["ng_contactgroup"]:
            if ng_g_dict.has_key(db_rec["ng_contactgroup"]):
                ng_g_dict[db_rec["ng_contactgroup"]].add_service_template(db_rec["ng_service_templ"])
    ng_g_dict[0] = cdef_nagios.ng_contactgroup(ng_g_vs.get_default_value("name"), 0, ng_g_vs.get_default_dict())
    # set values as default
    for idx, stuff in ng_g_dict.iteritems():
        stuff.act_values_are_default()
    # nagios_contacts
    req.dc.execute("SELECT u.login, u.useremail,u.user_idx FROM user u ORDER BY u.login")
    ng_c_user_field = html_tools.selection_list(req, "cu", {0 : "---"}, sort_new_keys=0)
    all_users = tools.ordered_dict()
    for db_rec in req.dc.fetchall():
        all_users[db_rec["user_idx"]] = db_rec
        ng_c_user_field[db_rec["user_idx"]] = "%s (%s)" % (db_rec["login"],
                                                           db_rec["useremail"] if db_rec["useremail"] else "no email")
    # flag fields
    ng_contacts = tools.get_nagios_contacts(req.dc)
    ng_c_dict = tools.ordered_dict()
    for ng_c_idx, ng_c_stuff in ng_contacts.iteritems():
        ng_c_dict[ng_c_idx] = cdef_nagios.ng_contact(ng_c_stuff["login"], ng_c_idx, ng_c_stuff)
        ng_g_members_field[ng_c_idx] = ng_c_stuff["login"]
        for tp in [ng_c_stuff[x] for x in ["snperiod", "hnperiod"]]:
            if ng_p_dict.has_key(tp):
                ng_p_dict[tp].used += 1
    service_options = ["recovery", "critical", "unknown", "warning"]
    host_options = ["recovery", "down", "unreachable"]
    first_period_idx = ([x for x in ng_p_dict.keys() if x] + [0])[0]
    ng_c_vs = new_contact_vs(req, first_period_idx, ng_c_user_field, ng_c_snp_field, ng_c_hnp_field)
    ng_c_dict[0] = cdef_nagios.ng_contact(ng_c_vs.get_default_value("user"), 0, ng_c_vs.get_default_dict())
    # set values as default
    for idx, stuff in ng_c_dict.iteritems():
        stuff.act_values_are_default()
    # nagios service_templates
    ng_stemps = tools.get_nagios_service_templates(req.dc)
    # attempts/checks/retries/notif
    ng_s_attempts_field = html_tools.selection_list(req, "sat", sort_new_keys=0)
    ng_s_checks_field   = html_tools.selection_list(req, "sci", sort_new_keys=0)
    ng_s_retries_field  = html_tools.selection_list(req, "sri", sort_new_keys=0)
    ng_s_notif_field    = html_tools.selection_list(req, "sni", sort_new_keys=0)
    n_at = 0
    ng_s_notif_field[n_at] = "never"
    while n_at < 40:
        n_at += (n_at < 10 and 1 or 5)
        ng_s_attempts_field[n_at] = logging_tools.get_plural("time", n_at)
        ng_s_notif_field[n_at] = logging_tools.get_plural("min", n_at)
    r_iv = 0
    while r_iv < 40:
        r_iv += (r_iv < 10 and 1 or 5)
        ng_s_checks_field[r_iv] = logging_tools.get_plural("min", r_iv)
        ng_s_retries_field[r_iv] = logging_tools.get_plural("min", r_iv)
    ng_s_dict = tools.ordered_dict()
    for ng_s_idx, ng_s_stuff in ng_stemps.iteritems():
        ng_s_dict[ng_s_idx] = cdef_nagios.ng_service_template(ng_s_stuff["name"], ng_s_idx, ng_s_stuff)
        ng_g_templates_field[ng_s_idx] = ng_s_stuff["name"]
        ng_d_templates_field[ng_s_idx] = ng_s_stuff["name"]
    ng_s_vs = new_service_vs(req, first_period_idx, ng_s_attempts_field, ng_s_checks_field, ng_s_retries_field, ng_s_notif_field, ng_s_nsc_field, ng_s_nsn_field)
    ng_s_dict[0] = cdef_nagios.ng_service_template(ng_s_vs.get_default_value("name"), 0, ng_s_vs.get_default_dict())
    # nagios device_templates
    ng_dtemps = tools.get_nagios_device_templates(req.dc)
    # attempts/notif
    ng_d_attempts_field = html_tools.selection_list(req, "dat", sort_new_keys=0)
    ng_d_notif_field    = html_tools.selection_list(req, "dni", sort_new_keys=0)
    n_at = 0
    ng_d_notif_field[n_at] = "never"
    while n_at < 40:
        n_at += (n_at < 10 and 1 or 5)
        ng_d_attempts_field[n_at] = logging_tools.get_plural("time", n_at)
        ng_d_notif_field[n_at] = logging_tools.get_plural("min", n_at)
    # set values as default
    for idx, stuff in ng_c_dict.iteritems():
        stuff.act_values_are_default()
    ng_d_dict = tools.ordered_dict()
    for ng_d_idx, ng_d_stuff in ng_dtemps.iteritems():
        ng_d_dict[ng_d_idx] = cdef_nagios.ng_device_template(ng_d_stuff["name"], ng_d_idx, ng_d_stuff)
    ng_d_vs = new_device_vs(req, first_period_idx, ng_d_templates_field, ng_d_attempts_field, ng_d_ng_field, ng_d_notif_field)
    ng_d_dict[0] = cdef_nagios.ng_device_template(ng_d_vs.get_default_value("name"), 0, ng_d_vs.get_default_dict())
    # set values as default
    for idx, stuff in ng_s_dict.iteritems():
        stuff.act_values_are_default()
    # set values as default
    for idx, stuff in ng_d_dict.iteritems():
        stuff.act_values_are_default()
    # switch all list_fields to normal op
    for field in [ng_c_vs.get_he("snperiod"), ng_c_vs.get_he("hnperiod"), ng_s_nsc_field, ng_s_nsn_field, ng_d_ng_field,
                  ng_g_members_field, ng_g_dgroups_field, ng_g_templates_field, ng_d_templates_field,
                  ng_c_vs.get_he("user"),
                  ng_s_vs.get_he("max_attempts"), ng_s_vs.get_he("check_interval"), ng_s_vs.get_he("retry_interval"), ng_s_vs.get_he("ninterval"),
                  ng_d_attempts_field, ng_d_notif_field]:
        field.mode_is_normal()
    # check for time_period changes
    for ng_p_idx in sorted(ng_p_dict.keys()):
        ng_p_stuff = ng_p_dict[ng_p_idx]
        ng_p_vs.names = [x["name"] for x in ng_p_dict.values() if x["name"] and x["name"] != ng_p_stuff["name"]]
        ng_p_vs.link_object(ng_p_idx, ng_p_stuff)
        ng_p_vs.check_for_changes()
        if not ng_p_vs.check_delete():
            ng_p_vs.process_changes(change_log, ng_p_dict)
        ng_p_vs.unlink_object()
    if ng_p_vs.get_delete_list():
        for del_idx in ng_p_vs.get_delete_list():
            change_log.add_ok("Deleted nagios_period '%s'" % (ng_p_dict[del_idx]["name"]), "SQL")
            del ng_p_dict[del_idx]
        req.dc.execute("DELETE FROM ng_period WHERE %s" % (" OR ".join(["ng_period_idx=%d" % (x) for x in ng_p_vs.get_delete_list()])))
    # check for contact changes
    ng_c_vs.set_submit_mode(sub)
    for ng_c_idx in sorted(ng_c_dict.keys()):
        ng_c_stuff = ng_c_dict[ng_c_idx]
        ng_c_vs.users = dict([(k, v["login"]) for k, v in all_users.iteritems() if k in [x["user"] for x in ng_c_dict.values()] and k != ng_c_stuff["user"]])
        ng_c_vs.link_object(ng_c_idx, ng_c_stuff)
        ng_c_vs.check_for_changes()
        if not ng_c_vs.check_delete():
            ng_c_vs.process_changes(change_log, ng_c_dict)
            if ng_c_vs.check_create():
                # add contact to ng_members
                ng_g_members_field.add_setup_key(ng_c_stuff.get_idx(), all_users[ng_c_stuff["user"]]["login"])
        ng_c_vs.unlink_object()
    if ng_c_vs.get_delete_list():
        for del_idx in ng_c_vs.get_delete_list():
            change_log.add_ok("Deleted nagios_contact '%s'" % (all_users[ng_c_dict[del_idx]["user"]]["login"]), "SQL")
            del ng_c_dict[del_idx]
            # delete from ng_member
            ng_g_members_field.del_setup_key(del_idx)
            # delete references from contact_groups
            for ng_g_stuff in ng_g_dict.values():
                ng_g_stuff.delete_member(del_idx)
        req.dc.execute("DELETE FROM ng_contact WHERE %s" % (" OR ".join(["ng_contact_idx=%d" % (x) for x in ng_c_vs.get_delete_list()])))
        req.dc.execute("DELETE FROM ng_ccgroup WHERE %s" % (" OR ".join(["ng_contact=%d" % (x) for x in ng_c_vs.get_delete_list()])))
    # check for service_template changes
    ng_s_vs.set_submit_mode(sub)
    for ng_s_idx in sorted(ng_s_dict.keys()):
        ng_s_stuff = ng_s_dict[ng_s_idx]
        ng_s_vs.names = [ng_s_dict[x]["name"] for x in ng_s_dict.keys() if x != ng_s_idx and x]
        ng_s_vs.link_object(ng_s_idx, ng_s_stuff)
        ng_s_vs.check_for_changes()
        if not ng_s_vs.check_delete():
            ng_s_vs.process_changes(change_log, ng_s_dict)
            if ng_s_vs.check_create():
                ng_g_templates_field.add_setup_key(ng_s_stuff.get_idx(), ng_s_stuff["name"])
                ng_d_templates_field.add_setup_key(ng_s_stuff.get_idx(), ng_s_stuff["name"])
        ng_s_vs.unlink_object()
    if ng_s_vs.get_delete_list():
        for del_idx in ng_s_vs.get_delete_list():
            change_log.add_ok("Deleted nagios_service_template '%s'" % (ng_s_dict[del_idx]["name"]), "SQL")
            del ng_s_dict[del_idx]
            # delete from ng_._templates
            ng_g_templates_field.del_setup_key(del_idx)
            ng_d_templates_field.del_setup_key(del_idx)
            # delete references from contact_groups
            for ng_g_stuff in ng_g_dict.values():
                ng_g_stuff.delete_service_template(del_idx)
        req.dc.execute("DELETE FROM ng_service_templ WHERE %s" % (" OR ".join(["ng_service_templ_idx=%d" % (x) for x in ng_s_vs.get_delete_list()])))
        req.dc.execute("DELETE FROM ng_cgservicet WHERE %s" % (" OR ".join(["ng_service_templ=%d" % (x) for x in ng_s_vs.get_delete_list()])))
    # check for contactgroup changes
    ng_g_vs.set_submit_mode(sub)
    for ng_g_idx in sorted(ng_g_dict.keys()):
        ng_g_stuff = ng_g_dict[ng_g_idx]
        ng_g_vs.names = [ng_g_dict[x]["name"] for x in ng_g_dict.keys() if x != ng_g_idx and x]
        ng_g_vs.link_object(ng_g_idx, ng_g_stuff)
        ng_g_vs.check_for_changes()
        if not ng_g_vs.check_delete():
            ng_g_vs.process_changes(change_log, ng_g_dict)
        ng_g_vs.unlink_object()
    if ng_g_vs.get_delete_list():
        for del_idx in ng_g_vs.get_delete_list():
            change_log.add_ok("Deleted nagios_contactgroup '%s'" % (ng_g_dict[del_idx]["name"]), "SQL")
            del ng_g_dict[del_idx]
        req.dc.execute("DELETE FROM ng_contactgroup WHERE %s" % (" OR ".join(["ng_contactgroup_idx=%d" % (x) for x in ng_g_vs.get_delete_list()])))
        del_str = " OR ".join(["ng_contactgroup=%d" % (x) for x in ng_g_vs.get_delete_list()])
        for del_list in ["ng_ccgroup", "ng_cgservicet"]:
            req.dc.execute("DELETE FROM %s WHERE %s" % (del_list, del_str))
    # check for device_template changes
    ng_d_vs.set_submit_mode(sub)
    for ng_d_idx in sorted(ng_d_dict.keys()):
        ng_d_stuff = ng_d_dict[ng_d_idx]
        ng_d_vs.names = [ng_d_dict[x]["name"] for x in ng_d_dict.keys() if x != ng_d_idx and x]
        ng_d_vs.link_object(ng_d_idx, ng_d_stuff)
        ng_d_vs.check_for_changes()
        if not ng_d_vs.check_delete():
            ng_d_vs.process_changes(change_log, ng_d_dict)
        ng_d_vs.unlink_object()
    if ng_d_vs.get_delete_list():
        for del_idx in ng_d_vs.get_delete_list():
            change_log.add_ok("Deleted nagios_device_template '%s'" % (ng_d_dict[del_idx]["name"]), "SQL")
            del ng_d_dict[del_idx]
        req.dc.execute("DELETE FROM ng_device_templ WHERE %s" % (" OR ".join(["ng_device_templ_idx=%d" % (x) for x in ng_d_vs.get_delete_list()])))
    if sub:
        tools.signal_nagios_config_server(req, change_log)
    req.write(change_log.generate_stack("Action log"))
    # recheck ng_period used values
    for ng_p_stuff in ng_p_dict.values():
        ng_p_stuff.used = 0
    for ng_c_idx, ng_c_stuff in ng_c_dict.iteritems():
        if ng_c_idx:
            for tp in [ng_c_stuff[x] for x in ["snperiod", "hnperiod"]]:
                if ng_p_dict.has_key(tp):
                    ng_p_dict[tp].used += 1
    # time_periods
    ng_p_table = html_tools.html_table(cls="normal")
    ng_p_table[1]["class"] = "line00"
    for what in ["Name", "del", "Alias"]+[x.capitalize() for x in time_ranges]:
        ng_p_table[None][0] = html_tools.content(what, type="th")
    line_idx = 0
    for ng_p_idx in tools.get_ordered_idx_list(ng_p_dict, "name") + [0]:
        ng_p_stuff = ng_p_dict[ng_p_idx]
        line_idx = 1 - line_idx
        ng_p_table[0]["class"] = "line1%d" % (line_idx)
        if ng_p_idx:
            ng_p_table[None][0] = html_tools.content(ng_p_vs.get_he("name"), ng_p_stuff.get_suffix(), cls="left")
            if ng_p_stuff.used:
                ng_p_table[None][0] = html_tools.content("%d" % (ng_p_stuff.used), cls="center")
            else:
                ng_p_table[None][0] = html_tools.content(ng_p_vs.get_he("del"), ng_p_stuff.get_suffix(), cls="errormin")
        else:
            ng_p_table[None][0:2] = html_tools.content(ng_p_vs.get_he("name"), ng_p_stuff.get_suffix(), cls="left")
        ng_p_table[None][0] = html_tools.content(ng_p_vs.get_he("alias"), ng_p_stuff.get_suffix(), cls="left")
        for tr in time_ranges:
            ng_p_table[None][0] = html_tools.content(ng_p_vs.get_he("%srange" % (tr)), ng_p_stuff.get_suffix(), cls="center")
    req.write("%s%s" % (html_tools.gen_hline("Time Periods", 3),
                        ng_p_table("")))
    # contacs
    ng_c_table = html_tools.html_table(cls="normal")
    ng_c_table[1]["class"] = "line00"
    for what in ["User", "del", "Host not.period", "Host options", "Service not. period", "Service options"]:
        ng_c_table[None][0] = html_tools.content(what, type="th")
    line_idx = 0
    for ng_c_idx in tools.get_ordered_idx_list(ng_c_dict, "user") + [0]:
        ng_c_stuff = ng_c_dict[ng_c_idx]
        line_idx = 1 - line_idx
        ng_c_table[0]["class"] = "line1%d" % (line_idx)
        if ng_c_idx:
            ng_c_table[None][0] = html_tools.content(ng_c_vs.get_he("user"), ng_c_stuff.get_suffix(), cls="left")
            ng_c_table[None][0] = html_tools.content(ng_c_vs.get_he("del"), ng_c_stuff.get_suffix(), cls="errormin")
        else:
            ng_c_table[None][0:2] = html_tools.content(ng_c_vs.get_he("user"), ng_c_stuff.get_suffix(), cls="left")
        ng_c_table[None][0] = html_tools.content(ng_c_vs.get_he("hnperiod"), ng_c_stuff.get_suffix(), cls="center")
        ho_list = []
        for ho in host_options:
            if ho_list:
                ho_list.append(", ")
            ho_list.extend(["%s:" % (ho.capitalize()), ng_c_vs.get_he("hn%s" % (ho))])
        ng_c_table[None][0] = html_tools.content(ho_list, ng_c_stuff.get_suffix(), cls="center")
        ng_c_table[None][0] = html_tools.content(ng_c_vs.get_he("snperiod"), ng_c_stuff.get_suffix(), cls="center")
        so_list = []
        for so in service_options:
            if so_list:
                so_list.append(", ")
            so_list.extend(["%s:" % (so.capitalize()), ng_c_vs.get_he("sn%s" % (so))])
        ng_c_table[None][0] = html_tools.content(so_list, ng_c_stuff.get_suffix(), cls="center")
    req.write("%s%s" % (html_tools.gen_hline("Contacts", 3),
                        ng_c_table("")))
    # service_templates
    ng_s_table = html_tools.html_table(cls="normal")
    ng_s_table[1]["class"] = "line00"
    for what in ["name", "del", "volatile", "Check period", "Max attempts", "Check Iv.", "Retry Iv.", "Notif. period", "Notif. Iv.", "Rec", "Crt", "Wrn", "Unk"]:
        ng_s_table[None][0] = html_tools.content(what, type="th")
    line_idx = 0
    for ng_s_idx in tools.get_ordered_idx_list(ng_s_dict, "name") + [0]:
        ng_s_stuff = ng_s_dict[ng_s_idx]
        line_idx = 1 - line_idx
        ng_s_table[0]["class"] = "line1%d" % (line_idx)
        if ng_s_idx:
            ng_s_table[None][0] = html_tools.content(ng_s_vs.get_he("name"), ng_s_stuff.get_suffix(), cls="left")
            ng_s_table[None][0] = html_tools.content(ng_s_vs.get_he("del"), ng_s_stuff.get_suffix(), cls="errormin")
        else:
            ng_s_table[None][0:2] = html_tools.content(ng_s_vs.get_he("name"), ng_s_stuff.get_suffix(), cls="left")
        ng_s_table[None][0] = html_tools.content(ng_s_vs.get_he("volatile"), ng_s_stuff.get_suffix(), cls="center")
        ng_s_table[None][0] = html_tools.content(ng_s_vs.get_he("nsc_period"), ng_s_stuff.get_suffix(), cls="center")
        ng_s_table[None][0] = html_tools.content(ng_s_vs.get_he("max_attempts"), ng_s_stuff.get_suffix(), cls="center")
        ng_s_table[None][0] = html_tools.content(ng_s_vs.get_he("check_interval"), ng_s_stuff.get_suffix(), cls="center")
        ng_s_table[None][0] = html_tools.content(ng_s_vs.get_he("retry_interval"), ng_s_stuff.get_suffix(), cls="center")
        ng_s_table[None][0] = html_tools.content(ng_s_vs.get_he("nsn_period"), ng_s_stuff.get_suffix(), cls="center")
        ng_s_table[None][0] = html_tools.content(ng_s_vs.get_he("ninterval"), ng_s_stuff.get_suffix(), cls="center")
        for nt in ["recovery", "critical", "warning", "unknown"]:
            ng_s_table[None][0] = html_tools.content(ng_s_vs.get_he("n%s" % (nt)), ng_s_stuff.get_suffix(), cls="center")
    req.write("%s%s" % (html_tools.gen_hline("Service templates", 3),
                        ng_s_table("")))
    # contactgroups
    ng_g_table = html_tools.html_table(cls="normal")
    ng_g_table[1]["class"] = "line00"
    for what in ["Name", "del", "Alias", "Members", "DeviceGroups", "ServiceTemplates"]:
        ng_g_table[None][0] = html_tools.content(what, type="th")
    line_idx = 0
    for ng_g_idx in tools.get_ordered_idx_list(ng_g_dict, "name") + [0]:
        ng_g_stuff = ng_g_dict[ng_g_idx]
        line_idx = 1 - line_idx
        ng_g_table[0]["class"] = "line1%d" % (line_idx)
        if ng_g_idx:
            ng_g_table[None][0] = html_tools.content(ng_g_vs.get_he("name"), ng_g_stuff.get_suffix(), cls="left")
            ng_g_table[None][0] = html_tools.content(ng_g_vs.get_he("del"), ng_g_stuff.get_suffix(), cls="errormin")
        else:
            ng_g_table[None][0:2] = html_tools.content(ng_g_vs.get_he("name"), ng_g_stuff.get_suffix(), cls="left")
        ng_g_table[None][0] = html_tools.content(ng_g_vs.get_he("alias"), ng_g_stuff.get_suffix(), cls="left")
        ng_g_table[None][0] = html_tools.content(ng_g_members_field, ng_g_stuff.get_suffix(), cls="center")
        ng_g_table[None][0] = html_tools.content(ng_g_dgroups_field, ng_g_stuff.get_suffix(), cls="center")
        ng_g_table[None][0] = html_tools.content(ng_g_templates_field, ng_g_stuff.get_suffix(), cls="center")
    req.write("%s%s" % (html_tools.gen_hline("Contact groups", 3),
                        ng_g_table("")))
    # device_templates
    ng_d_table = html_tools.html_table(cls="normal")
    ng_d_table[1]["class"] = "line00"
    for what in ["name", "del", "Service template", "Max attempts", "Notif. period", "Notif. Iv.", "Rec", "Down", "Unreach"]:
        ng_d_table[None][0] = html_tools.content(what, type="th")
    line_idx = 0
    for ng_d_idx in tools.get_ordered_idx_list(ng_d_dict, "name") + [0]:
        ng_d_stuff = ng_d_dict[ng_d_idx]
        line_idx = 1 - line_idx
        ng_d_table[0]["class"] = "line1%d" % (line_idx)
        if ng_d_idx:
            ng_d_table[None][0] = html_tools.content(ng_d_vs.get_he("name"), ng_d_stuff.get_suffix(), cls="left")
            ng_d_table[None][0] = html_tools.content(ng_d_vs.get_he("del"), ng_d_stuff.get_suffix(), cls="errormin")
        else:
            ng_d_table[None][0:2] = html_tools.content(ng_d_vs.get_he("name"), ng_d_stuff.get_suffix(), cls="left")
        ng_d_table[None][0] = html_tools.content(ng_d_vs.get_he("ng_service_templ"), ng_d_stuff.get_suffix(), cls="center")
        ng_d_table[None][0] = html_tools.content(ng_d_vs.get_he("max_attempts"), ng_d_stuff.get_suffix(), cls="center")
        ng_d_table[None][0] = html_tools.content(ng_d_vs.get_he("ng_period"), ng_d_stuff.get_suffix(), cls="center")
        ng_d_table[None][0] = html_tools.content(ng_d_vs.get_he("ninterval"), ng_d_stuff.get_suffix(), cls="center")
        for nt in ["recovery", "down", "unreachable"]:
            ng_d_table[None][0] = html_tools.content(ng_d_vs.get_he("n%s" % (nt)), ng_d_stuff.get_suffix(), cls="center")
    req.write("%s%s" % (html_tools.gen_hline("Device templates", 3),
                        ng_d_table("")))
    low_submit[""] = 1
    submit_button = html_tools.submit_button(req, "submit")
    submit_button.set_class("", "button")
    req.write("%s<div class=\"center\">%s</div>\n" % (low_submit.create_hidden_var(),
                                                      submit_button("")))
