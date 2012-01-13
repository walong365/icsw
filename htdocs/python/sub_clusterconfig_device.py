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
import cdef_network
import cdef_device
import pprint

def check_device_groups(req, dev_tree, devg_dict, dev_dict, c_log):
    # server command list
    com_dict = {0 : [],
                1 : [],
                2 : [],
                3 : [],
                4 : []}
    dev_location_dict = tools.get_device_location_dict(req.dc)
    dev_class_dict = tools.get_device_class_dict(req.dc)
    devt_dict = tools.get_all_device_types(req.dc)
    name_field = html_tools.text_field(req, "dn", size=64, display_len=32)
    descr_field = html_tools.text_field(req, "dgd", size=128, display_len=32)
    meta_button = html_tools.checkbox(req, "meta")
    del_button = html_tools.checkbox(req, "del", auto_reset=1)
    cdg_button = html_tools.checkbox(req, "cdg")
    low_submit = html_tools.checkbox(req, "sub")
    sub = low_submit.check_selection("")
    bootserver_list = html_tools.selection_list(req, "bs", {}, sort_new_keys=False)
    show_in_bc_button = html_tools.checkbox(req, "view")
    is_xen_guest_button = html_tools.checkbox(req, "isxg")
    bootserver_list.add_pe_key("sd", -1, "--- keep ---")
    # fetch bootservers
    bs_dict = tools.boot_server_struct(req.dc, c_log, add_zero_entry=True)
    for bs_name in bs_dict.get_names():
        bootserver_list[bs_dict[bs_name]] = bs_name
    devg_list = html_tools.selection_list(req, "dg", {}, sort_new_keys=False)
    devt_list = html_tools.selection_list(req, "dt", {}, sort_new_keys=False)
    devt_list.add_pe_key("sd", 0, "---keep---")
    devt_lut = dict([(val["identifier"], val) for val in devt_dict.values()])
    for idx, stuff in devt_dict.iteritems():
        if stuff["identifier"] != "MD":
            devt_list[idx] = stuff["description"]
    new_is_cdg = cdg_button.check_selection("")
    range_field = html_tools.text_field(req, "range", size=8, display_len=8)
    # dict of new target bs
    new_bs_dict = {}
    # dict of bs to remove
    old_bs_dict = {}
    # check for deletion of selected devices
    devg_list.add_pe_key("sd", 0, "---keep---")
    del_selected = del_button.check_selection("sd", 0)
    # device config not changed
    dev_conf_changed = False
    # get selected devices
    dg_sel, d_sel, dg_sel_eff = dev_tree.get_selection()
    if dev_tree:
        # check for changes
        new_name = name_field.check_selection("", "")
        new_descr = descr_field.check_selection("", "")
        new_meta = meta_button.check_selection("")
        new_dg = None
        if new_name:
            if new_name.lower() in [x.lower() for x in dev_tree.get_all_devg_names()]:
                c_log.add_error("Cannot add new DeviceGroup '%s'" % (new_name), "name already used")
            else:
                if req.dc.execute("INSERT INTO device_group SET name=%s, description=%s, cluster_device_group=%s", (new_name,
                                                                                                                    new_descr,
                                                                                                                    new_is_cdg)):
                    new_dg_idx = req.dc.insert_id()
                    c_log.add_ok("Added new DeviceGroup '%s'" % (new_name), "SQL")
                    new_dg = cdef_device.device_group(new_name, new_dg_idx)
                    new_dg.set_forced_object(1)
                    new_dg.set_descr(new_descr)
                    name_field.check_selection(new_dg.get_suffix(), new_dg.get_name())
                    descr_field.check_selection(new_dg.get_suffix(), new_dg.get_descr())
                    # set meta_button
                    if new_meta:
                        meta_button.set_sys_value(new_dg.get_suffix(), new_meta)
                    else:
                        meta_button.del_sys_value(new_dg.get_suffix())
                    #meta_button.set_forced_set(
                    # reset in order to initialise the dictionary
                    del_button[new_dg.get_suffix()] = 0
                    new_dg_struct = {"device_group_idx" : new_dg_idx, "dgname" : new_name, "dgdescr" : new_descr, "cluster_device_group" : new_is_cdg}
                    dev_tree.add_device_group(new_dg_struct)
                    devg_dict[new_dg_idx] = new_dg
                else:
                    c_log.add_error("Cannot add new DeviceGroup '%s'" % (new_name), "SQL")
        if new_dg:
            name_field[""] = ""
            descr_field[""] = ""
        # d_sel_list has the form [(dev_idx, dg_idx),..., ()]
        dg_del_list, d_del_list = ([], [])
        for dg in dev_tree.get_sorted_devg_idx_list():
            act_dg = devg_dict[dg]
            if del_button.check_selection(act_dg.get_suffix(), 0):
                if act_dg.has_meta_device():
                    d_del_list.append((act_dg.get_meta_device_idx(), dg, "M"))
                    c_log.add_ok("Deleted Metadevice for DeviceGroup '%s'" % (act_dg.get_name()), "SQL")
                dg_del_list.append(dg)
                c_log.add_ok("Deleted DeviceGroup '%s'" % (act_dg.get_name()), "SQL")
                del devg_dict[dg]
                dev_tree.delete_device_group(dg)
            else:
                new_name = name_field.check_selection(act_dg.get_suffix(), act_dg.get_name())
                if new_name != act_dg.get_name():
                    if new_name.lower() in [x.lower() for x in dev_tree.get_all_devg_names()]:
                        c_log.add_error("Cannot rename DeviceGroup from '%s' to '%s'" % (act_dg.get_name(), new_name), "name already used")
                        name_field[act_dg.get_suffix()] = act_dg.get_name()
                    else:
                        c_log.add_ok("Renamed DeviceGroup '%s' to '%s'" % (act_dg.get_name(), new_name), "change")
                        act_dg.add_sql_changes({"name" : new_name})
                        act_dg.set_name(new_name)
                        dev_tree.rename_device_group(dg, new_name)
                new_descr = descr_field.check_selection(act_dg.get_suffix(), act_dg.get_descr())
                if new_descr != act_dg.get_descr():
                    c_log.add_ok("Changed description of DeviceGroup '%s' to '%s'" % (act_dg.get_name(), new_descr), "change")
                    act_dg.add_sql_changes({"description" : new_descr})
                    act_dg.set_descr(new_descr)
                if sub:
                    new_button = meta_button.check_selection(act_dg.get_suffix(), act_dg.has_meta_device() and act_dg.is_forced_object())
                else:
                    new_button = meta_button.check_selection(act_dg.get_suffix(), act_dg.has_meta_device())
                if new_button != act_dg.has_meta_device():
                    if new_button:
                        # add meta-device
                        if not devt_lut.has_key("MD"):
                            c_log.add_error("Cannot add MetaDevice to DeviceGroup '%s'" % (act_dg.get_name()), "no MetaDeviceType defined")
                        else:
                            new_meta_name = "METADEV_%s" % (act_dg.get_name())
                            if req.dc.execute("INSERT INTO device SET name=%s, device_group=%s, device_type=%s", (new_meta_name,
                                                                                                                  dg,
                                                                                                                  devt_lut["MD"]["device_type_idx"])):
                                new_md_idx = req.dc.insert_id()
                                req.dc.execute("UPDATE device_group SET device=%d WHERE device_group_idx=%d" % (new_md_idx, dg))
                                c_log.add_ok("Added MetaDevice for DeviceGroup '%s'" % (act_dg.get_name()), "SQL")
                                meta_struct = {"device_idx" : new_md_idx, "name" : new_meta_name}
                                act_dg.set_meta_device(new_meta_name, new_md_idx)
                                dev_tree.add_meta_device(dg, meta_struct)
                            else:
                                c_log.add_error("Cannot add MetaDevice to DeviceGroup '%s'" % (act_dg.get_name()), "SQL")
                    else:
                        # delete meta-device
                        d_del_list.append((act_dg.get_meta_device_idx(), dg, "M"))
                        c_log.add_ok("Deleted Metadevice for DeviceGroup '%s'" % (act_dg.get_name()), "SQL")
                        req.dc.execute("UPDATE device_group SET device=0 WHERE device_group_idx=%d" % (dg))
                        dev_tree.delete_meta_device(dg)
                act_dg.commit_sql_changes(req.dc)
                if not dev_tree.get_devg_struct(dg)["cluster_device_group"]:
                    devg_list[dg] = act_dg.get_name()
        devg_list.mode_is_normal()
        bootserver_list.mode_is_normal()
        devt_list.mode_is_normal()
        # check for group movement of selected devices
        new_devg_selected = devg_list.check_selection("sd", 0)
        devg_list["sd"] = 0
        # check for bootserver change of selected devices
        new_bs_selected = bootserver_list.check_selection("sd", -1)
        xen_guest_selected = is_xen_guest_button.check_selection("sd", 0)
        bootserver_list["sd"] = -1
        # check for type change of selected devices
        new_devt_selected = devt_list.check_selection("sd", 0)#0, (0, None), 1)
        devt_list["sd"] = None
        # check for new device
        new_name = name_field.check_selection("D", "")
        new_com = descr_field.check_selection("D", "")
        new_devg = devg_list.check_selection("D", 0)
        #print "*",new_com,"*",new_name,"*",new_devg,"<br>"
        new_bootserver = bootserver_list.check_selection("D", -1)
        new_show_in_bc = show_in_bc_button.check_selection("D")
        new_xen_guest = is_xen_guest_button.check_selection("D")
        new_dev_has_range = del_button.check_selection("D", 0)
        new_dev_type = devt_list.check_selection("D", 0)
        range_start, range_end, range_digits = (range_field.check_selection("Ds", ""),
                                                range_field.check_selection("De", ""),
                                                range_field.check_selection("Dd", ""))
        range_sed_change = 0
        if range_start == "" or not range_start.isdigit():
            range_start = 1
            range_field["Ds"] = str(range_start)
            range_sed_change = 1
        if range_end == "" or not range_end.isdigit():
            range_end = 16
            range_field["De"] = str(range_end)
            range_sed_change = 1
        if range_digits == "" or not range_digits.isdigit() or range_digits == "0":
            range_digits = 2
            range_field["Dd"] = str(range_digits)
            range_sed_change = 1
        if sub and range_sed_change and new_dev_has_range:
            c_log.add_warn("Attention ! Range parameters modifed, no device(s) added", "range error")
        if new_name and not (new_dev_has_range and range_sed_change):
            if new_dev_has_range:
                f_str = "%%s%%0%dd" % (int(range_digits))
                new_names = [f_str % (new_name, idx) for idx in range(min(int(range_start), int(range_end)), max(int(range_start), int(range_end))+1)]
            else:
                new_names = [new_name]
            # check if none of the new names is used
            all_dev_names = [x.lower() for x in dev_tree.get_all_dev_names()]
            add_it = 1
            for new_name in new_names:
                if new_name.lower() in all_dev_names:
                    c_log.add_error("Cannot add new Device '%s' to DeviceGroup '%s'" % (new_name, dev_tree.get_devg_name(new_devg)), "name already used")
                    add_it = 0
            if add_it:
                for new_name in new_names:
                    if req.dc.execute("INSERT INTO device SET name=%s, comment=%s, device_type=%s, " + \
                                          "device_group=%s, device_class=%s, device_location=%s, " + \
                                          "show_in_bootcontrol=%s, xen_guest=%s", (new_name,
                                                                                   new_com,
                                                                                   new_dev_type,
                                                                                   new_devg,
                                                                                   dev_class_dict.keys()[0],
                                                                                   dev_location_dict.keys()[0],
                                                                                   1 if new_show_in_bc else 0,
                                                                                   1 if new_xen_guest else 0)):
                        new_d_idx = req.dc.insert_id()
                        req.dc.execute("SELECT * FROM device WHERE device_idx=%s", new_d_idx)
                        d_struct = req.dc.fetchone()
                        d_struct["identifier"] = devt_dict[new_dev_type]["identifier"]
                        dev_tree.add_device(new_devg, d_struct)
                        new_dev = cdef_device.device(new_name, new_d_idx, new_devg, new_dev_type)
                        if new_xen_guest:
                            req.dc.execute("INSERT INTO xen_device SET device=%s" % (new_d_idx))
                            new_dev.set_xen_device(req.dc.insert_id())
                        new_dev.set_comment(new_com)
                        dev_dict[new_dev.get_idx()] = new_dev
                        new_dev.set_bootserver(new_bootserver)
                        new_dev.set_show_in_bootcontrol(d_struct["show_in_bootcontrol"])
                        new_dev.set_xen_guest(d_struct["xen_guest"])
                        new_bs_dict.setdefault(new_bootserver, []).append(new_name)
                        c_log.add_ok("Added Device '%s' to DeviceGroup '%s' (bootserver %s)" % (new_name, dev_tree.get_devg_name(new_devg), bs_dict[new_bootserver]), "SQL")
                        # disable name_field
                        del name_field["D"]
                        # disable range-button
                        dev_conf_changed = True
                        # set button stati
                        is_xen_guest_button.set_sys_value(new_dev.get_suffix(), d_struct["xen_guest"])
                        show_in_bc_button.set_sys_value(new_dev.get_suffix(), d_struct["show_in_bootcontrol"])
                    else:
                        c_log.add_error("Cannot add Device to DeviceGroup '%s'" % (dev_tree.get_devg_name(new_dg)), "SQL")
        sub = low_submit.check_selection("")
        mov_list = []
        for dg in dev_tree.get_sorted_devg_idx_list():
            for d_idx in dev_tree.get_sorted_dev_idx_list(dg):
                act_d = dev_dict[d_idx]
                if del_button.check_selection(act_d.get_suffix(), 0) or (del_selected and d_idx in d_sel):
                    c_log.add_ok("Deleted Device '%s' from DeviceGroup '%s'" % (act_d.get_name(), dev_tree.get_devg_name(dg)), "SQL")
                    d_del_list.append((d_idx, dg, "D"))
                else:
                    act_devt_id, act_bs, act_view_bc, act_xen_guest = (act_d.get_device_type(),
                                                                       act_d.get_bootserver(),
                                                                       act_d.get_show_in_bootcontrol(),
                                                                       act_d.get_xen_guest())
                    new_devt = devt_list.check_selection(act_d.get_suffix(), act_devt_id)
                    new_group = devg_list.check_selection(act_d.get_suffix(), act_d.get_device_group())
                    new_view_bc = show_in_bc_button.check_selection(act_d.get_suffix(), (not sub) and act_view_bc)
                    new_xen_guest = is_xen_guest_button.check_selection(act_d.get_suffix(), (not sub) and act_xen_guest)
                    new_bs = bootserver_list.check_selection(act_d.get_suffix(), act_bs)
                    if d_idx in d_sel:
                        if new_devg_selected:
                            new_group = new_devg_selected
                        if new_devt_selected:
                            new_devt = new_devt_selected
                        #print "***", new_bs, new_bs_selected
                        if new_bs_selected > -1:
                            new_bs = new_bs_selected
                    if new_view_bc != act_view_bc:
                        c_log.add_ok("Changed viewable_in_bootcontrol of Device '%s' from '%s' to '%s'" % (act_d.get_name(),
                                                                                                           "enabled" if act_view_bc else "disabled",
                                                                                                           "enabled" if new_view_bc else "disabled"),
                                     "change")
                        act_d.set_show_in_bootcontrol(new_view_bc)
                        act_d.add_sql_changes({"show_in_bootcontrol" : new_view_bc})
                    if new_xen_guest != act_xen_guest:
                        c_log.add_ok("Changed xen_guest of Device '%s' from '%s' to '%s'" % (act_d.get_name(),
                                                                                             "enabled" if act_xen_guest else "disabled",
                                                                                             "enabled" if new_xen_guest else "disabled"),
                                     "change")
                        act_d.set_xen_guest(new_xen_guest)
                        act_d.add_sql_changes({"xen_guest" : new_xen_guest})
                    if new_devt != act_devt_id:
                        c_log.add_ok("Changed type of Device '%s' from '%s' to '%s'" % (act_d.get_name(), devt_dict[act_devt_id]["description"], devt_dict[new_devt]["description"]), "change")
                        act_d.set_device_type(new_devt)
                        devt_list[act_d.get_suffix()] = new_devt
                        act_d.add_sql_changes({"device_type" : new_devt})
                    old_name = act_d.get_name()
                    new_name = name_field.check_selection(act_d.get_suffix(), act_d.get_name())
                    if new_name != act_d.get_name():
                        if new_name.lower() in [x.lower() for x in dev_tree.get_all_dev_names()]:
                            c_log.add_error("Cannot rename Device '%s' to '%s'" % (act_d.get_name(), new_name), "name already used")
                        else:
                            c_log.add_ok("Renamed Device '%s' to '%s'" % (act_d.get_name(), new_name), "change")
                            act_d.add_sql_changes({"name" : new_name})
                            act_d.set_name(new_name)
                            dev_tree.rename_device(dg, d_idx, new_name)
                    #print old_name, new_bs, act_bs
                    if new_bs != act_bs:
                        if bs_dict.has_key(act_bs):
                            c_log.add_ok("Changed bootserver of Device '%s' from '%s' to '%s'" % (new_name, bs_dict[act_bs], bs_dict[new_bs]), "change")
                        else:
                            c_log.add_ok("Set bootserver of Device '%s' '%s'" % (new_name, bs_dict[new_bs]), "change")
                        act_d.set_bootserver(new_bs)
                        bootserver_list[act_d.get_suffix()] = act_d.get_bootserver()
                        new_bs_dict.setdefault(new_bs, []).append(new_name)
                        if bs_dict.has_key(act_bs):
                            old_bs_dict.setdefault(act_bs, []).append(old_name)
                    new_com = descr_field.check_selection(act_d.get_suffix(), act_d.get_comment())
                    if new_com != act_d.get_comment():
                        c_log.add_ok("Changed comment of Device '%s' to '%s'" % (act_d.get_name(), new_com), "change")
                        act_d.add_sql_changes({"comment" : new_com})
                        act_d.set_comment(new_com)
                    if new_group != act_d.get_device_group():
                        c_log.add_ok("Moving Device '%s' from DeviceGroup '%s' to DeviceGroup '%s'" % (act_d.get_name(), dev_tree.get_devg_name(act_d.get_device_group()), dev_tree.get_devg_name(new_group)), "change")
                        act_d.add_sql_changes({"device_group" : new_group})
                        act_d.set_device_group(new_group)
                        mov_list.append((d_idx, dg, act_d.get_device_group()))
                        #print new_group, act_d.get_device_group(), devg_list.get_selection(act_d.get_suffix()), "<br>"
                    act_d.commit_sql_changes(req.dc)
        # move devices
        for d_idx, old_dg, new_dg in mov_list:
            dev_tree.move_device(d_idx, old_dg, new_dg)
        if d_del_list:
            dev_conf_changed = True
            for d_idx, dg_idx, d_type in d_del_list:
                if dev_dict.has_key(d_idx):
                    del dev_dict[d_idx]
                if d_type == "D":
                    dev_tree.delete_device(d_idx, dg_idx)
            # delete subsequent stuff of devices
            dev_idx_del_str = " OR ".join(["device_idx=%d" % (x[0]) for x in d_del_list])
            dev_del_str = " OR ".join(["device=%d" % (x[0]) for x in d_del_list])
            # fetch netdevices
            req.dc.execute("SELECT netdevice_idx FROM netdevice WHERE (%s)" % (dev_del_str))
            del_netdev_idxs = [x["netdevice_idx"] for x in req.dc.fetchall()]
            if del_netdev_idxs:
                req.dc.execute("DELETE FROM netip WHERE %s" % (" OR ".join(["netdevice=%d" % (x) for x in del_netdev_idxs])))
                req.dc.execute("DELETE FROM peer_information WHERE %s OR %s" % (" OR ".join(["s_netdevice=%d" % (x) for x in del_netdev_idxs]),
                                                                                " OR ".join(["d_netdevice=%d" % (x) for x in del_netdev_idxs])))
            req.dc.execute("SELECT rrd_set_idx FROM rrd_set WHERE (%s)" % (dev_del_str))
            del_rrdset_idxs = [x["rrd_set_idx"] for x in req.dc.fetchall()]
            if del_rrdset_idxs:
                req.dc.execute("DELETE FROM rrd_data WHERE %s" % (" OR ".join(["rrd_set=%d" % (x) for x in del_rrdset_idxs])))
            # del tables
            dev_del_tables = ["device_variable",
                              "device_device_selection",
                              "apc_device",
                              "hw_entry",
                              "msoutlet",
                              "netdevice",
                              "device_config",
                              "wc_files",
                              "config_script",
                              "config_int",
                              "config_str",
                              "config_blob",
                              "snmp_config",
                              "macbootlog",
                              "devicelog",
                              "netbotz_picture",
                              # not really used ...
                              #"ng_sst_device",
                              "instp_device",
                              "sge_pe_host",
                              "sge_host",
                              "rrd_set",
                              "ccl_event",
                              "ccl_event_log"]
            for dev_del_table in dev_del_tables:
                req.dc.execute("DELETE FROM %s WHERE %s" % (dev_del_table,
                                                            dev_del_str))
            req.dc.execute("DELETE FROM device WHERE %s" % (dev_idx_del_str))
            com_dict[4] = tools.rebuild_hopcount(req, c_log, {"device_delete": "device"})
        if dg_del_list:
            dev_conf_changed = True
            req.dc.execute("DELETE FROM device_group WHERE %s" % (" OR ".join(["device_group_idx=%d" % (x) for x in dg_del_list])))
    if dev_conf_changed:
        c_log.add_warn("Device config changed, forcing rebuild of server_connection_dict", "SQL change")
        if req.session_data.has_property("server_routes"):
            req.session_data.del_property("server_routes")
        req.session_data.set_property("signal_other_sessions", 1)
    bs_del_nodes, bs_set_nodes = ([], [])
    # delete bootserver
    for bs_idx, node_list in old_bs_dict.iteritems():
        if bs_idx:
            com_dict[0].append(tools.s_command(req, "mother_server", 8001, "delete_macadr", node_list, 10, bs_dict[bs_idx]))
            com_dict[1].append(tools.s_command(req, "mother_server", 8001, "remove_bs"    , node_list, 10, bs_dict[bs_idx]))
        bs_del_nodes.extend(node_list)
    if bs_del_nodes:
        if com_dict[0]:
            tools.iterate_s_commands(com_dict[0], c_log)
            tools.iterate_s_commands(com_dict[1], c_log)
        req.dc.execute("UPDATE device SET bootserver = 0 WHERE %s" % (" OR ".join(["name='%s'" % (x) for x in bs_del_nodes])))
    # set bootservers
    for bs_idx, node_list in new_bs_dict.iteritems():
        if bs_idx:
            com_dict[2].append(tools.s_command(req, "mother_server", 8001, "new_bs"      , node_list, 10, bs_dict[bs_idx]))
            com_dict[3].append(tools.s_command(req, "mother_server", 8001, "alter_macadr", node_list, 10, bs_dict[bs_idx]))
        bs_set_nodes.append((bs_idx, node_list))
    if bs_set_nodes:
        for bs_idx, node_list in bs_set_nodes:
            req.dc.execute("UPDATE device SET bootserver=%d WHERE %s" % (bs_idx, " OR ".join(["name='%s'" % (x) for x in node_list])))
        if com_dict[2]:
            tools.iterate_s_commands(com_dict[2], c_log)
            tools.iterate_s_commands(com_dict[3], c_log)
    if com_dict[4]:
        tools.iterate_s_commands(com_dict[4], c_log)
##     print com_dict
##     print "*** old: ", old_bs_dict, "<br>"
##     print "*** new: ", new_bs_dict, "<br>"
    return name_field, descr_field, meta_button, del_button, low_submit, cdg_button, devg_list, devt_list, range_field, bootserver_list, show_in_bc_button, is_xen_guest_button
        
def show_device_groups(req, dev_tree, devg_dict, dev_dict, stuff):
    name_field, descr_field, meta_button, del_button, low_submit, cdg_button, devg_list, devt_list, range_field, bootserver_list, show_in_bc_button, is_xen_guest_button = stuff
    if dev_tree:
        # get selection
        dg_sel, d_sel, dg_sel_eff = dev_tree.get_selection()
        req.dc.execute("SELECT d.name, d.device_idx, d.show_in_bootcontrol, d.device_group, d.xen_guest FROM device d, device_type dt WHERE dt.device_type_idx=d.device_type AND dt.identifier='MD'")

        out_table = html_tools.html_table(cls="normal")
        req.write("%s%s" % (html_tools.gen_hline("Device/Group config, %s defined" % (logging_tools.get_plural("devicegroup", dev_tree.get_num_of_devgs())), 2),
                            out_table.get_header()))
        row0_idx = 0
        # found cluster-device group?
        cdg_found = 0
        for cd_group in [1, 0]:
            header_written = 0
            for dg in dev_tree.get_sorted_devg_idx_list():
                dg_struct = dev_tree.get_devg_struct(dg)
                act_dg = devg_dict[dg]
                if dg_struct["cluster_device_group"] == cd_group:
                    num_of_d = dev_tree.get_num_of_devs(dg)
                    line0_class = "line0%d" % (row0_idx)
                    if not header_written:
                        header_written = 1
                        # generate table header structure
                        out_table[0]["class"] = "lineh"
                        if cd_group:
                            out_table[None][1 : 7] = html_tools.content("ClusterDeviceGroup", type="th", cls="center")
                        else:
                            out_table[None][1] = html_tools.content("Name"             , type="th", cls="left")
                            out_table[None][0] = html_tools.content("Description"      , type="th", cls="left")
                            out_table[None][0] = html_tools.content("DeviceType"       , type="th", cls="center")
                            out_table[None][0] = html_tools.content("MetaDevice"       , type="th", cls="center")
                            out_table[None][0] = html_tools.content("Bootserver / show", type="th", cls="center")
                            out_table[None][0] = html_tools.content("XenGuest"         , type="th", cls="center")
                            out_table[None][0] = html_tools.content("Delete"           , type="th", cls="center")
                        req.write(out_table.flush_lines(""))
                    row0_idx = 1 - row0_idx
                    # generate table structure
                    out_table[0]["class"] = line0_class
                    out_table[None][1] = html_tools.content(["DG: ",
                                                             name_field,
                                                             dg in dg_sel and " (*)" or ""], cls="left")
                    out_table[None][0] = html_tools.content(descr_field, cls="left")
                    out_table[None][0] = html_tools.content(cd_group and "-" or logging_tools.get_plural("device", num_of_d), cls="center")
                    out_table[None][0] = html_tools.content(meta_button, cls="center")
                    out_table[None][0:2] = html_tools.content("&nbsp;", cls="center")
                    out_table[None][0] = html_tools.content(num_of_d and "&nbsp;" or del_button, cls=num_of_d and "center" or "errormin")
                    name_field.set_class(act_dg.get_suffix(), line0_class)
                    descr_field.set_class(act_dg.get_suffix(), line0_class)
                    cdg_found = cdg_found or dev_tree.get_devg_struct(dg)["cluster_device_group"]
                    # iterate over devices
                    row1_idx = 0
                    for d_idx in dev_tree.get_sorted_dev_idx_list(dg):
                        line1_class="line1%d" % (row1_idx)
                        act_d = dev_dict[d_idx]
                        del_button.check_selection(act_d.get_suffix())
                        out_table[0]["class"] = "line1%d" % (row1_idx)
                        out_table[None][1] = html_tools.content([name_field,
                                                                 d_idx in d_sel and " (*)" or ""], act_d.get_suffix(), cls="left")
                        out_table[None][0] = html_tools.content(descr_field, act_d.get_suffix()    , cls="left")
                        out_table[None][0] = html_tools.content(devt_list, act_d.get_suffix()      , cls="center")
                        out_table[None][0] = html_tools.content(devg_list, act_d.get_suffix()      , cls="center")
                        out_table[None][0] = html_tools.content([bootserver_list,
                                                                 " / ",
                                                                 show_in_bc_button], act_d.get_suffix(), cls="center")
                        out_table[None][0] = html_tools.content(is_xen_guest_button, act_d.get_suffix(), cls="center")
                        out_table[None][0] = html_tools.content(del_button, act_d.get_suffix()     , cls="errormin")
                        name_field.set_class(act_d.get_suffix(), line1_class)
                        descr_field.set_class(act_d.get_suffix(), line1_class)
                        row1_idx = 1 - row1_idx
                    req.write(out_table.flush_lines(act_dg.get_suffix()))
        out_table[0]["class"] = "lineh"
        out_table[None][1]   = html_tools.content("DeviceGroupName" , type="th", cls="left")
        out_table[None][0]   = html_tools.content("Description"     , type="th", cls="left")
        out_table[None][0 : 5] = html_tools.content("Flags Metadevice", type="th", cls="center")
        out_table[0]["class"] = "devup"
        out_table[None][1]   = html_tools.content(["New:", name_field]                , cls="left")
        out_table[None][0]   = html_tools.content(descr_field                         , cls="left")
        out_table[None][0]   = html_tools.content(["MetaDevice: ", meta_button]       , cls="center")
        out_table[None][0 : 4] = html_tools.content(["CDG:",
                                                     cdg_found and "N/A" or cdg_button], cls="center")
        req.write(out_table.flush_lines(""))
        if dev_tree.get_sorted_devg_idx_list():
            # device_groups present, stuff for new device
            out_table[0]["class"] = "lineh"
            out_table[None][1] = html_tools.content("DeviceName" , type="th", cls="left")
            out_table[None][0] = html_tools.content("Comment"    , type="th", cls="left")
            out_table[None][0] = html_tools.content("DeviceType" , type="th", cls="center")
            out_table[None][0] = html_tools.content("DeviceGroup", type="th", cls="center")
            out_table[None][0] = html_tools.content("Bootserver" , type="th", cls="center")
            out_table[None][0] = html_tools.content("XenGuest"   , type="th", cls="center")
            out_table[None][0] = html_tools.content("&nbsp;"     , type="th", cls="center")
            out_table[0]["class"] = "devup"
            out_table[None][1] = html_tools.content(["New:", name_field], cls="left")
            out_table[None][0] = html_tools.content(descr_field        , cls="left")
            out_table[None][0] = html_tools.content(devt_list          , cls="center")
            out_table[None][0] = html_tools.content(devg_list          , cls="center")
            out_table[None][0] = html_tools.content([bootserver_list,
                                                     " / ",
                                                     show_in_bc_button], cls="center")
            out_table[None][0] = html_tools.content(is_xen_guest_button, cls="center")
            out_table[None][0] = html_tools.content("&nbsp;"           , cls="center")
            out_table[0]["class"] = "devup"
            out_table[None][1] = html_tools.content(["Range:",
                                                     del_button,
                                                     ", from ",
                                                     html_tools.content(range_field, "Ds"),
                                                     " to ",
                                                     html_tools.content(range_field, "De"),
                                                     " with ",
                                                     html_tools.content(range_field, "Dd"),
                                                     " digits"]        , cls="left")
            out_table[None][0] = html_tools.content("Actions on selected devices:", cls="right")
            out_table[None][0] = html_tools.content(devt_list      , "sd", cls="center")
            out_table[None][0] = html_tools.content(devg_list      , "sd", cls="center")
            out_table[None][0] = html_tools.content(bootserver_list, "sd", cls="center")
            out_table[None][0] = html_tools.content(is_xen_guest_button, "sd", cls="center")
            out_table[None][0] = html_tools.content(del_button     , "sd", cls="errormin")
            req.write(out_table.flush_lines("D"))
        low_submit[""] = 1
        submit_button = html_tools.submit_button(req, "submit")
        submit_button.set_class("", "button")
        req.write("%s%s<div class=\"center\">%s</div>\n" % (out_table.get_footer(),
                                                            low_submit.create_hidden_var(),
                                                            submit_button("")))
        del out_table
    else:
        req.write(html_tools.gen_hline("No devices/devicegroups defined", 2))
