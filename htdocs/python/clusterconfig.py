#!/usr/bin/python -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2007 Andreas Lang-Nevyjel, init.at
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
""" entry page for config pages """

import functions
import html_tools
import tools
import cdef_device

def module_info():
    return {"conf" : {"description" : "Configuration",
                      "priority"    : 10},
            "cc" : {"description"            : "Cluster configuration",
                    "enabled"                : 1,
                    "default"                : 0,
                    "left_string"            : "Clusterconfig",
                    "right_string"           : "Cluster configuration",
                    "priority"               : 0,
                    "capability_group_name" : "conf"},
            "ccl" : {"description"            : "Cluster location config",
                     "enabled"                : True,
                     "default"                : 0,
                     "mother_capability_name" : "cc"},
            "ccn" : {"description"            :"Cluster network",
                     "enabled"                : False,
                     "default"                : 0,
                     "mother_capability_name" : "cc"},
            "ncd" : {"description"            : "Generate new devices",
                     "enabled"                : 1,
                     "defvalue"               : 0,
                     "mother_capability_name" : "cc"}}

def process_page(req):
    if req.conf["genstuff"].has_key("AUTO_RELOAD"):
        del req.conf["genstuff"]["AUTO_RELOAD"]
    functions.write_header(req)
    functions.write_body(req)
    tools.init_log_and_status_fields(req)
    change_log = html_tools.message_log()
    # global selector
    glob_sel = html_tools.selection_list(req, "add_info", {"a0"    : {"name"     : "--- Cluster-wide options ---",
                                                                      "disabled" : True,
                                                                      "pri"      : -100,
                                                                      "class"    : "inverse"},
                                                           "cnet"  : {"name"     : "Cluster Networks",
                                                                      "pri"      : -95},
                                                           "ddevg" : {"name"     : "Devices and Devicegroups",
                                                                      "pri"      : -90},
                                                           "a2"    : {"name"     : "--- Configuration options ---",
                                                                      "disabled" : True,
                                                                      "pri"      : -60,
                                                                      "class"    : "inverse"},
                                                           "copts" : {"name"     : "Configurations",
                                                                      "pri"      : -50},
                                                           "cnag"  : {"name"     : "Nagios config",
                                                                      "pri"      : -15},
                                                           "csnmp" : {"name"     : "SNMP MIBs",
                                                                      "pri"      : -10},
                                                           #"drel"  : {"name"     : "Device Relationship",
                                                           #           "pri"      : -5},
                                                           "a1"    : {"name"     : "--- Device-local options ---",
                                                                      "disabled" : True,
                                                                      "pri"      : 0,
                                                                      "class"    : "inverse"},
                                                           "dnet"  : {"name"     : "Device networks",
                                                                      "pri"      : 5},
                                                           "dpar"  : {"name"     : "Device parameters",
                                                                      "pri"      : 10},
                                                           "dconf" : {"name"     : "Device config",
                                                                      "pri"      : 100},
                                                           "a3"    : {"name"     : "--- optional settings ---",
                                                                      "disabled" : True,
                                                                      "pri"      : 110,
                                                                      "class"    : "inverse"},
                                                           "cdevc" : {"name"     : "Netdevice classes and network types",
                                                                      "pri"      : 120},
                                                           "ctype" : {"name"     : "Configuration types",
                                                                      "pri"      : 130},
                                                           "dldc"  : {"name"     : "Device locations and classes",
                                                                      "pri"      : 140}}, initial_mode="n", use_priority_key=True)
    act_glob_sel = glob_sel.check_selection("", "cnet")
    dev_tree = tools.display_list(req, include_cluster_meta_device_group=(act_glob_sel == "dpar"))
    dev_tree.add_regexp_field()
    dev_tree.add_devsel_fields(tools.get_device_selection_lists(req.dc, req.user_info.get_idx()))
    dev_tree.query([],
                   ["comment", "snmp_class", "bootnetdevice", "bootserver", "device_type", "comment", "dg.description AS dgdescr", "dg.cluster_device_group"],
                   [],
                   [])
    sub_glob_sel_1, sub_glob_sel_2, ext_line, clear_vars, hidden_vars = (None, None, [], [], [])
    if act_glob_sel == "dnet":
        sub_glob_sel_1 = html_tools.selection_list(req, "sub_i0", {"i" : "IP information",
                                                                   "p" : "Routing/Forwarding",
                                                                   "h" : "Hardware options",
                                                                   "m" : "MAC/DHCP options"}, multiple=True, size=2, initial_mode="n", log_validation_errors=False)
        sub_glob_pre_sel_1 = []
    elif act_glob_sel == "dpar":
        sub_glob_sel_1 = html_tools.selection_list(req, "sub_i0", {"d"  : {"name" : "Device variables",
                                                                           "pri"  : -10},
                                                                   "a"  : {"name" : "SNMP/Location/Class",
                                                                           "pri"  : 0},
                                                                   "p"  : {"name" : "APC/IBC Connectivity",
                                                                           "pri"  : 20},
                                                                   "n"  : {"name" : "Nagios parameters",
                                                                           "pri"  : 30},
                                                                   "r"  : {"name" : "Device relationships",
                                                                           "pri"  : 50},
                                                                   "s"  : {"name" : "Security",
                                                                           "pri"  : 130},
                                                                   "pa" : {"name" : "Partiton settings",
                                                                           "pri"  : 200}}, initial_mode="n", log_validation_errors=False, use_priority_key=True)
        sub_glob_pre_sel_1 = "a"
    elif act_glob_sel == "cnag":
        sub_glob_sel_1 = html_tools.selection_list(req, "sub_i0", {"a" : "Global options",
                                                                   "b" : "configuration local options"}, initial_mode="n", log_validation_errors=False)
        sub_glob_pre_sel_1 = "a"
    elif act_glob_sel == "cnet":
        pass
    #sub_glob_sel_1 = html_tools.selection_list(req, "sub_i0", {"n" : "only networks",
    #"t" : "with types and classes"}, initial_mode="n", log_validation_errors=0)
    #sub_glob_pre_sel_1 = "n"
    elif act_glob_sel == "copts":
        import sub_clusterconfig_config
        import sub_clusterconfig_show_device_config
        sub_glob_sel_1, sub_glob_pre_sel_1 = sub_clusterconfig_show_device_config.get_sel_list(req, "sub_i1")
        order_opt_list = html_tools.selection_list(req, "oo", {"o0" : {"name" : "name"},
                                                               "o1" : {"name" : "pri/name"},
                                                               "o2" : {"name" : "type/name"},
                                                               "o3" : {"name" : "type/pri/name"}},
                                                   log_validation_errors=False)
        order_opt = order_opt_list.check_selection("", "o0")
        c_regexp = html_tools.text_field(req, "cre", size=64, display_len=8)
        saved_re        = req.user_info.get_user_var_value("_sdc_re", "")
        act_c_regexps = c_regexp.check_selection("", saved_re).split(",")
        req.user_info.modify_user_var("_sdc_re", ",".join(act_c_regexps))
        ext_line = ["Options: order by ", order_opt_list,
                    ", name regexp: ", c_regexp]
        clear_vars = [order_opt_list, c_regexp]
        
    elif act_glob_sel == "ctype":
        import sub_clusterconfig_config_classes
    elif act_glob_sel == "dconf":
        import sub_clusterconfig_show_device_config
        sub_glob_sel_1 = html_tools.selection_list(req, "sub_i0", {"o0" : "groups and devices",
                                                                   "o1" : "only groups",
                                                                   "o2" : "only devices"}, initial_mode="n", log_validation_errors=0)
        sub_glob_pre_sel_1 = "o2"
        sub_glob_sel_2, sub_glob_pre_sel_2 = sub_clusterconfig_show_device_config.get_sel_list(req, "sub_i1")
        c_regexp   = html_tools.text_field(req, "cre", size=64, display_len=8)
        sel_button = html_tools.checkbox(req, "sos")
        low_submit = html_tools.checkbox(req, "sub")
        high_submit = html_tools.checkbox(req, "high")
        saved_re            = req.user_info.get_user_var_value("_sdc_re", "")
        saved_only_selected = req.user_info.get_user_var_value("_sdc_os", 0)
        act_c_regexps = c_regexp.check_selection("", saved_re).split(",")
        #print low_submit.check_selection(), saved_only_selected, sel_button.check_selection("", 0)
        only_selected = sel_button.check_selection("", not (low_submit.check_selection("") or high_submit.check_selection("")) and saved_only_selected)
        high_submit[""] = 1
        req.user_info.modify_user_var("_sdc_re", ",".join(act_c_regexps))
        req.user_info.modify_user_var("_sdc_os", only_selected)
        ext_line = ["Name regexp: ", c_regexp, ", only selected: ", sel_button]
        clear_vars = [c_regexp, sel_button]
        hidden_vars = [high_submit]
    if sub_glob_sel_1:
        loc_glob_sel_1 = sub_glob_sel_1.check_selection("", sub_glob_pre_sel_1)
    if sub_glob_sel_2:
        loc_glob_sel_2 = sub_glob_sel_2.check_selection("", sub_glob_pre_sel_2)
    # dict of device_groups and devices
    devg_dict, dev_dict = ({}, {})
    for dg in dev_tree.get_sorted_devg_idx_list():
        new_dg = cdef_device.device_group(dev_tree.get_devg_name(dg), dg)
        new_dg.set_descr(dev_tree.get_devg_struct(dg)["dgdescr"])
        if dev_tree.devg_has_md(dg):
            md_s = dev_tree.get_md_struct(dg)
            new_dg.set_meta_device(md_s["name"], md_s["device_idx"])
        devg_dict[dg] = new_dg
        for d_idx in dev_tree.get_sorted_dev_idx_list(dg):
            dev_s = dev_tree.get_dev_struct(d_idx)
            new_d = cdef_device.device(dev_tree.get_dev_name(d_idx), d_idx, dg, dev_s["device_type"])
            new_d.set_comment(dev_s["comment"])
            new_d.set_bootserver(dev_s["bootserver"])
            new_d.set_show_in_bootcontrol(dev_s["show_in_bootcontrol"])
            new_d.set_xen_guest(dev_s["xen_guest"])
            dev_dict[d_idx] = new_d
    # check for changes befor we display the selection
    if act_glob_sel == "ddevg":
        import sub_clusterconfig_device
        html_stuff = sub_clusterconfig_device.check_device_groups(req, dev_tree, devg_dict, dev_dict, change_log)
    submit_button = html_tools.submit_button(req, "select")
    submit_button.set_class("", "button")
    sel_table = html_tools.html_table(cls="blindsmall")
    if dev_tree.get_num_of_devgs() and dev_tree.get_num_of_devs():
        sel_table[0][0] = html_tools.content(dev_tree, "devg", cls="center")
        sel_table[None][0] = html_tools.content(dev_tree, "dev", cls="center")
        ds_dict = dev_tree.get_device_selection_lists()
        if ds_dict:
            sel_table[None][0] = html_tools.content(dev_tree, "sel", cls="center")
            col_span = 3
        else:
            col_span = 2
    else:
        col_span = 2
    sel_table[0][0:col_span] = html_tools.content(["Regexp for Groups ", dev_tree.get_devg_re_field(), " and devices ", dev_tree.get_dev_re_field(),
                                                   "\n, ", dev_tree.get_devsel_action_field(), " selection", dev_tree.get_devsel_field()], cls="center")
    second_line = ["Actual displaytype is ", glob_sel]
    if sub_glob_sel_2:
        second_line.extend(["\n, options: ",
                            sub_glob_sel_1,
                            ", ",
                            sub_glob_sel_2])
    elif sub_glob_sel_1:
        second_line.extend(["\n, options: ",
                            sub_glob_sel_1])
    if ext_line:
        ext_line.extend([", ", submit_button])
    else:
        second_line.extend([", ", submit_button])
    sel_table[0][0:col_span] = html_tools.content(second_line + [x.create_hidden_var("") for x in hidden_vars], cls="center")
    if ext_line:
        sel_table[0][0:col_span] = html_tools.content(ext_line, cls="center")
    out_str = ["<form action=\"%s.py?%s\" method = post>\n%s</form>\n" % (req.module_name,
                                                                          functions.get_sid(req),
                                                                          sel_table(""))]
    del sel_table
    [x.clear_var_name("") for x in clear_vars]
    out_str.append(change_log.generate_stack("Action log"))
    out_str.append("<form action=\"%s.py?%s\" method = post enctype=\"multipart/form-data\" >" % (req.module_name, functions.get_sid(req)))
    out_str.append(glob_sel.create_hidden_var() + dev_tree.get_hidden_sel())
    if sub_glob_sel_1:
        out_str.append(sub_glob_sel_1.create_hidden_var())
    if sub_glob_sel_2:
        out_str.append(sub_glob_sel_2.create_hidden_var())
    req.write("".join(out_str))
    if act_glob_sel == "ddevg":
        sub_clusterconfig_device.show_device_groups(req, dev_tree, devg_dict, dev_dict, html_stuff)
    elif act_glob_sel == "cnet":
        import sub_clusterconfig_network
        sub_clusterconfig_network.show_cluster_networks(req)
    elif act_glob_sel == "cdevc":
        import sub_clusterconfig_network
        sub_clusterconfig_network.show_netdevice_classes(req)
    elif act_glob_sel == "copts":
        import sub_clusterconfig_config
        sub_clusterconfig_config.show_config_options(req, dev_tree, dev_dict, loc_glob_sel_1)
    elif act_glob_sel == "ctype":
        import sub_clusterconfig_config_classes
        sub_clusterconfig_config_classes.show_config_type_options(req)
    elif act_glob_sel == "cnag":
        import sub_clusterconfig_nagios
        sub_clusterconfig_nagios.show_nagios_options(req, loc_glob_sel_1)
    elif act_glob_sel == "csnmp":
        import sub_clusterconfig_config_snmp
        sub_clusterconfig_config_snmp.show_snmp_options(req)
    elif act_glob_sel == "dldc":
        import sub_clusterconfig_config_class_locations
        sub_clusterconfig_config_class_locations.show_options(req)
    elif act_glob_sel == "drel":
        import sub_clusterconfig_config_relationship
        sub_clusterconfig_config_relationship.process_page(req)
    elif act_glob_sel not in ["dpar", "dnet", "dconf"]:
        req.write(html_tools.gen_hline("Global selection '%s' has no action associated" % (act_glob_sel), 2))
    # options only valid if devices are selected
    if act_glob_sel in ["dpar", "dnet", "dconf"]:
        if dev_tree.devices_selected():
            if act_glob_sel == "dpar":
                import sub_clusterconfig_parameter
                sub_clusterconfig_parameter.show_device_parameters(req, dev_tree, loc_glob_sel_1)
            elif act_glob_sel == "dnet":
                import sub_clusterconfig_network
                sub_clusterconfig_network.show_device_networks(req, dev_tree, loc_glob_sel_1)
            elif act_glob_sel == "dconf":
                import sub_clusterconfig_config
                sub_clusterconfig_config.show_device_config(req, dev_tree, devg_dict, dev_dict, loc_glob_sel_1, loc_glob_sel_2)
        else:
            req.write(html_tools.gen_hline("No devices selected", 2))
    req.write("</form>\n")
