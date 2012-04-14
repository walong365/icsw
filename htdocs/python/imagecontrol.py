#i!/usr/bin/python -Ot
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
""" image information """

import functions
import logging_tools
import tools
import html_tools

def module_info():
    return {"ic" : {"description"           : "Image control",
                    "default"               : 0,
                    "enabled"               : 1,
                    "left_string"           : "Image control",
                    "right_string"          : "Modify installable images and set exclude paths",
                    "priority"              : -100,
                    "capability_group_name" : "conf"}}

def get_size_str(in_val):
    pf_l = ["k", "M", "G", "T"]
    if in_val:
        act_pf = pf_l.pop(0)
        while in_val > 1024:
            in_val = int(in_val) / 1024.
            act_pf = pf_l.pop(0)
    else:
        act_pf = ""
    return "%.2f %sB" % (in_val, act_pf)

class image_struct(object):
    def __init__(self, idx, name, extra_dict):
        self.__image_idx = idx
        self.name = name
        self.exclude_paths = {}
        self.extra_dict = extra_dict
        self.new_devices, self.act_devices = ([], [])
        self.parse_size_string()
    def parse_size_string(self):
        dir_dict = {"" : {"size" : 0}}
        key = None
        for entry in [x for x in (self.extra_dict.get("size_string", "") or "").split(";") if x]:
            if key is None:
                key = entry
            else:
                dir_dict[key] = {"size" : int(entry)}
                key = None
        self.dir_dict = dir_dict
        self.size = sum([x["size"] for x in dir_dict.values()])
        for key in self.dir_dict.keys():
            dir_dict[key]["rel"] = (dir_dict[key]["size"] * 100.) / max(1, self.size)
    def add_new_device(self, dev_name):
        self.new_devices.append(dev_name)
    def add_act_device(self, dev_name):
        self.act_devices.append(dev_name)
    def get_idx(self):
        return self.__image_idx
    def get_suffix(self):
        return "i%d" % (self.__image_idx)
    def get_info_str(self):
        return "%s%s, version %d.%d (%s)" % (self.extra_dict["build_lock"] and "(locked)" or "",
                                             self.name,
                                             self.extra_dict["version"],
                                             self.extra_dict["release"],
                                             logging_tools.get_plural("build", self.extra_dict["builds"]))
    def add_exclude_path(self, idx, excl_path, vfi, vfu):
        self.exclude_paths[idx] = (excl_path, vfi, vfu)
    def __getitem__(self, key):
        if key == "name":
            return self.name
        elif key in ["new_devices", "act_devices", "size", "dir_dict"]:
            return getattr(self, key)
        else:
            return self.extra_dict.get(key, "Key %s not defined" % (key))
    def __setitem__(self, key, value):
        if key == "name":
            self.name = value
        elif key in ["new_devices", "act_devices", "size", "dir_dict"]:
            setattr(self, key, value)
        else:
            self.extra_dict[key] = value
    def validate(self, dc, arch_dict):
        if arch_dict.has_key(self["architecture"]):
            act_bc = self["bitcount"]
            new_bc = {"i386"   : 32,
                      "i486"   : 32,
                      "i586"   : 32,
                      "i686"   : 32,
                      "x86_64" : 64,
                      "alpha"  : 64,
                      "ia64"   : 64}.get(arch_dict.get(self["architecture"], "???"), 0)
            if act_bc != new_bc:
                self["bitcount"] = new_bc
                dc.execute("UPDATE image SET bitcount=%s WHERE image_idx=%s", (new_bc,
                                                                               self.__image_idx))
                
def add_image(req, action_log, image_name, image_source, im_dict, im_fields, sys_dict, arch_lut):
    if image_name in [x["name"] for x in im_dict.values()]:
        action_log.add_error("Cannot add image with name '%s'" % (image_name), "Name already used")
    elif not image_source.startswith("/") or image_source.count("/") < 2:
        action_log.add_error("Cannot add image with name '%s', source_path '%s'" % (image_name, image_source), "Path error")
    else:
        action_log.add_ok("Added image '%s', source_path '%s'" % (image_name, image_source), "OK")
        ver_str = sys_dict.get("version", "unknown")
        if ver_str.count("."):
            rel_str = ".".join(ver_str.split(".")[1:])
            ver_str = ver_str.split(".")[0]
        else:
            rel_str = ""
        req.dc.execute("INSERT INTO image SET name=%s, source=%s, sys_vendor=%s, sys_version=%s, sys_release=%s, architecture=%s, bitcount=%s", (image_name,
                                                                                                                                                 image_source,
                                                                                                                                                 sys_dict.get("vendor", "unknown"),
                                                                                                                                                 ver_str,
                                                                                                                                                 rel_str,
                                                                                                                                                 arch_lut.get(sys_dict.get("arch", "unknown"), 0),
                                                                                                                                                 sys_dict.get("bitcount", 0)))
        ins_idx = req.dc.insert_id()
        req.dc.execute("SELECT i.* FROM image i WHERE i.image_idx=%d" % (ins_idx))
        db_rec = req.dc.fetchone()
        im_dict[ins_idx] = image_struct(db_rec["image_idx"], db_rec["name"], dict([(k, db_rec[k]) for k in im_fields]))
    
def path_is_valid(path):
    return path.startswith("/")

def show_image_exclude_paths(req, act_image, im_source, exclude_path, del_button, vfi_button, vfu_button, vendor_fields):
    req.write(html_tools.gen_hline("Selected image %s, vendor %s (%s.%s)" % (act_image["name"],
                                                                             vendor_fields["str"](""),
                                                                             vendor_fields["ver"](""),
                                                                             vendor_fields["rel"]("")), 2, 0))
    excl_table = html_tools.html_table(cls="normal")
    excl_table[0]["class"] = "lineh"
    for what in ["Directory", "Size", "rel", "Excludepath(s)", "del", "install", "upgrade"]:
        excl_table[None][0] = html_tools.content(what, type="th", cls="center")
    excl_table[0]["class"] = "line00"
    excl_table[None][0:2] = html_tools.content("Source directory:", cls="right")
    excl_table[None][0:5] = html_tools.content(im_source, "0", cls="left")
    dir_dict = act_image["dir_dict"]
    dirs = sorted(dir_dict.keys())
    line_idx = 0
    all_paths = dict([(v[0], k) for k, v in act_image.exclude_paths.iteritems()])
    all_path_names = sorted(all_paths.keys())
    # detect paths under "/"
    path_match = []
    for act_dir in dirs:
        path_match.extend([x for x in all_path_names if x.split("/")[1] == act_dir])
    slash_pathes = [x for x in all_path_names if x not in path_match]
    line_num = 0
    for act_dir in dirs:
        path_match = [x for x in all_path_names if x.split("/")[1] == act_dir]
        if act_dir == "":
            path_match.extend(slash_pathes)
        line_h = max(1, len(path_match))
        excl_table[0]["class"] = "line1%d" % (line_idx)
        excl_table[None:line_h][0] = html_tools.content("/%s" % (act_dir), cls="left")
        excl_table[None:line_h][0] = html_tools.content(get_size_str(dir_dict[act_dir]["size"]), cls="center")
        excl_table[None:line_h][0] = html_tools.content("%.2f %%" % (dir_dict[act_dir]["rel"]), cls="center")
        if path_match:
            nf_line = 0
            for idx in [all_paths[n] for n in path_match]:
                p_suf = "%d" % (idx)
                if nf_line:
                    excl_table[0]["class"] = "line1%d" % (line_idx)
                nf_line = 1
                excl_table[None][4] = html_tools.content(exclude_path, suffix = p_suf, cls = "left")
                excl_table[None][0] = html_tools.content(del_button, suffix = p_suf, cls = "errormin")
                excl_table[None][0] = html_tools.content(vfi_button, suffix = p_suf, cls = "center")
                excl_table[None][0] = html_tools.content(vfu_button, suffix = p_suf, cls = "center")
        else:
            excl_table[None][0:4] = html_tools.content("&nbsp;")
        line_idx = 1 - line_idx

    excl_table[0]["class"] = "line00"
    excl_table[None][0:5] = html_tools.content(["New:", exclude_path], "0", cls="left")
    excl_table[None][0] = html_tools.content(vfi_button, "0", cls="center")
    excl_table[None][0] = html_tools.content(vfu_button, "0", cls="center")
    return excl_table

def get_archs(req):
    req.dc.execute("SELECT * FROM architecture ORDER BY architecture")
    all_archs = dict([(x["architecture_idx"], x["architecture"]) for x in req.dc.fetchall()])
    arch_lut = dict([(v, k) for k, v in all_archs.iteritems()])
    arch_list = html_tools.selection_list(req, "imarch", {})
    for arch_name in sorted(arch_lut.keys()):
        arch_list[arch_lut[arch_name]] = arch_name
    arch_list.mode_is_normal()
    return all_archs, arch_list, arch_lut
    
def process_page(req):
    if req.conf["genstuff"].has_key("AUTO_RELOAD"):
        del req.conf["genstuff"]["AUTO_RELOAD"]
    functions.write_header(req)
    functions.write_body(req)
    action_log = html_tools.message_log()
    # basic buttons
    select_button = html_tools.submit_button(req, "select")
    submit_button = html_tools.submit_button(req, "submit")
    low_submit = html_tools.checkbox(req, "sub")
    sub = low_submit.check_selection("")
    low_submit[""] = 1
    # get images
    im_sel_list = html_tools.radio_list(req, "is", {}, sort_new_keys=0)
    exclude_path = html_tools.text_field(req, "ep", size=255, display_len=32)
    vfi_button = html_tools.checkbox(req, "vfi")
    vfu_button = html_tools.checkbox(req, "vfu")
    im_del_button = html_tools.checkbox(req, "ed", auto_reset=1)
    vendor_fields = {"str" : html_tools.text_field(req, "vend", size=16, display_len=16),
                     "ver" : html_tools.text_field(req, "vver", size=16, display_len=4),
                     "rel" : html_tools.text_field(req, "vrel", size=16, display_len=4)}
    #im_table[0][0] = html_tools.content(im_sel_list  , "", cls="center")
    im_dict = tools.ordered_dict()
    im_fields = ["source",
                 "version",
                 "release",
                 "builds",
                 "build_lock",
                 "date",
                 "size_string",
                 "sys_version",
                 "sys_release",
                 "sys_vendor",
                 "architecture",
                 "bitcount",
                 "full_build"]
    arch_dict, arch_list, arch_lut = get_archs(req)
    req.dc.execute("SELECT i.*, x.* FROM image i LEFT JOIN image_excl x ON x.image=i.image_idx GROUP BY i.name, x.exclude_path")
    for db_rec in req.dc.fetchall():
        im_idx = db_rec["image_idx"]
        if not im_dict.has_key(im_idx):
            new_image = image_struct(db_rec["image_idx"], db_rec["name"], dict([(k, db_rec[k]) for k in im_fields]))
            im_dict[im_idx] = new_image
        act_image = im_dict[im_idx]
        if db_rec["image_excl_idx"]:
            act_image.add_exclude_path(db_rec["image_excl_idx"], db_rec["exclude_path"], db_rec["valid_for_install"], db_rec["valid_for_upgrade"])
    for im_idx, act_image in im_dict.iteritems():
        act_image.validate(req.dc, arch_dict)
    # check for server scan
    show_server_images = 0
    if req.conf["server"].has_key("image_server"):
        check_image_servers = html_tools.checkbox(req, "cis", auto_reset=1)

        if check_image_servers.check_selection("", 0):
            im_list_command = tools.s_command(req, "image_server", 8004, "get_image_list", [], 10, None)
            im_list_commands = [im_list_command]
            if im_list_command.get_state() == "w" and len(im_list_command.get_possible_hosts()) > 1:
                for t_host in [x for x in im_list_command.get_possible_hosts() if x != im_list_command.get_hostname()]:
                    im_list_commands.append(tools.s_command(req, "image_server", 8004, "get_image_list", [], 10, t_host))
            tools.iterate_s_commands(im_list_commands, action_log)
            im_found = {}
            for im_list_command in im_list_commands:
                if im_list_command.get_state() == "o" and im_list_command.server_reply.get_option_dict():
                    opt_dict = im_list_command.server_reply.get_option_dict()
                    im_found[im_list_command.get_hostname()] = {"image_source" : opt_dict["image_dir"],
                                                                "images"       : opt_dict["images"]}
                else:
                    im_found[im_list_command.get_hostname()] = im_list_command.get_return()
            if im_found:
                show_server_images = 1
    else:
        check_image_servers = None
    im_change = 0
    new_image_f = html_tools.text_field(req, "nins", size=255, display_len=32)
    new_image_name, new_image_source = (new_image_f.check_selection("n", ""),
                                        new_image_f.check_selection("s", ""))
    new_image_f["n"] = ""
    if show_server_images:
        take_image = html_tools.checkbox(req, "ti", auto_reset=1)
        sim_table = html_tools.html_table(cls="normalsmall")
        req.write(html_tools.gen_hline("Found %s on %s" % (logging_tools.get_plural("image" , sum([type(v) == type({}) and len(v["images"]) or 0 for v in im_found.values()])),
                                                           logging_tools.get_plural("server", len(im_found.keys()))), 2))
        headers = ["take", "Name", "Vendor", "Version / Release", "Arch", "Bitcount"]
        line_idx = 1
        for s_name in sorted(im_found.keys()):
            s_dict = im_found[s_name]
            if type(s_dict) == type(""):
                sim_table[0]["class"] = "line01"
                sim_table[None][0:len(headers)] = html_tools.content("host %s: %s" % (s_name, s_dict), cls="left", type="th")
            else:
                sim_table[0]["class"] = "line01"
                if type(s_dict["images"]) == type([]):
                    s_dict["images"] = dict([(x, {}) for x in s_dict["images"]])
                sim_table[None][0:len(headers)] = html_tools.content("host %s, %s, source_dir %s" % (s_name, logging_tools.get_plural("image", len(s_dict["images"].keys())), s_dict["image_source"]), cls="center", type="th")
                sim_table[0]["class"] = "line00"
                for head in headers:
                    sim_table[None][0] = html_tools.content(head, type="th", cls="center")
                for im_name in sorted(s_dict["images"].keys()):
                    s_stuff = s_dict["images"][im_name]
                    im_suff = suffix = "%s%s" % (s_name, im_name)
                    if s_stuff.has_key("arch") and not arch_lut.has_key(s_stuff["arch"]):
                        req.dc.execute("INSERT INTO architecture SET architecture=%s", (s_stuff["arch"]))
                        arch_dict, arch_list, arch_lut = get_archs(req)
                    if take_image.check_selection(im_suff):
                        add_image(req, action_log, im_name, "%s/%s" % (s_dict["image_source"], im_name), im_dict, im_fields, s_stuff, arch_lut)
                    line_idx = 1 - line_idx
                    sim_table[0]["class"] = "line1%d" % (line_idx)
                    name_used = im_name in [x["name"] for x in im_dict.values()]
                    source_used = "%s/%s" % (s_dict["image_source"], im_name) in [x.extra_dict["source"] for x in im_dict.values()]
                    sim_table[None][0] = html_tools.content((name_used or source_used) and "name or source path used" or take_image, suffix = im_suff, cls="center")
                    sim_table[None][0] = html_tools.content(im_name, cls="left")
                    sim_table[None][0] = html_tools.content(s_stuff.get("vendor"  , "unknown"), cls="center")
                    sim_table[None][0] = html_tools.content(s_stuff.get("version" , "unknown"), cls="center")
                    sim_table[None][0] = html_tools.content(s_stuff.get("arch"    , "unknown"), cls="center")
                    sim_table[None][0] = html_tools.content(s_stuff.get("bitcount", "unknown"), cls="center")
        check_image_servers[""] = 1
        req.write("<form action=\"%s.py?%s\" method=post>%s%s<div class=\"center\">Use marked images: %s</div></form>\n" % (req.module_name,
                                                                                                                            functions.get_sid(req),
                                                                                                                            check_image_servers.create_hidden_var(),
                                                                                                                            sim_table(""),
                                                                                                                            submit_button("")))
        check_image_servers[""] = 0
    else:
        if new_image_name:
            add_image(req, action_log, new_image_name, new_image_source, im_dict, im_fields, {}, arch_lut)
    im_name_dict = dict([(v["name"], k) for k, v in im_dict.iteritems()])
    act_im_idxs = [im_name_dict[k] for k in sorted(im_name_dict.keys())]
    # iterate over images
    for idx in range(len(act_im_idxs)):
        im_idx = act_im_idxs[idx]
        act_image = im_dict[im_idx]
        new_arch = arch_list.check_selection(act_image.get_suffix(), act_image["architecture"])
        if act_image["architecture"] != new_arch:
            act_image["architecture"] = new_arch
            req.dc.execute("UPDATE image SET architecture=%d WHERE image_idx=%d" % (new_arch, act_image.get_idx()))
    if im_dict:
        req.dc.execute("SELECT d.name, d.act_image FROM device d WHERE %s" % (" OR ".join(["d.act_image=%d" % (x) for x in im_dict.keys()])))
        for db_rec in req.dc.fetchall():
            im_dict[db_rec["act_image"]].add_act_device(db_rec["name"])
        req.dc.execute("SELECT d.name, d.new_image FROM device d WHERE %s" % (" OR ".join(["d.act_image=%d" % (x) for x in im_dict.keys()])))
        for db_rec in req.dc.fetchall():
            if im_dict.has_key(db_rec["new_image"]):
                im_dict[db_rec["new_image"]].add_new_device(db_rec["name"])
    del_idxs = []
    for im_idx, im_stuff in im_dict.iteritems():
        if im_del_button.check_selection(im_idx, 0) and not im_stuff["new_devices"]:
            del_idxs.append(im_idx)
            act_im_idxs.remove(im_idx)
            action_log.add_ok("Deleting image '%s'" % (im_stuff["name"]), "SQL")
            im_change = 1
    if del_idxs:
        for del_idx in del_idxs:
            del im_dict[del_idx]
        req.dc.execute("DELETE FROM image_excl WHERE %s" % (" OR ".join(["image=%d" % (x) for x in del_idxs])))
        req.dc.execute("DELETE FROM image WHERE %s" % (" OR ".join(["image_idx=%d" % (x) for x in del_idxs])))
    im_table = html_tools.html_table(cls="normalsmall")
    del_button = html_tools.checkbox(req, "del", auto_reset=1)
    im_table[0]["class"] = "line00"
    for head in ["Idx", "Select", "Name", "Version", "Source", "full", "build", "build date", "locked", "delete", "devices", "size", "vendor", "version", "release", "arch", "bitcount"]:#, "actual", "new"]:
        im_table[None][0] = html_tools.content(head, type="th", cls="center")
    line_idx = 1
    for idx in range(len(act_im_idxs)):
        im_idx = act_im_idxs[idx]
        im_sel_list[im_idx] = {}
        act_image = im_dict[im_idx]
        line_idx = 1 - line_idx
        if not act_image["sys_vendor"] or not act_image["sys_version"]:
            im_table[0]["class"] = "error"
        else:
            im_table[0]["class"] = "line1%d" % (line_idx)
        im_table[None][0] = html_tools.content(idx + 1, cls="center")
        im_table[None][0] = html_tools.content(im_sel_list, cls="center")
        im_table[None][0] = html_tools.content(act_image["name"], cls="left")
        im_table[None][0] = html_tools.content("%d.%d" % (act_image["version"],
                                                          act_image["release"]), cls="center")
        im_table[None][0] = html_tools.content(act_image.extra_dict["source"], cls="left")
        im_table[None][0] = html_tools.content("yes" if act_image["full_build"] else "no", cls="center")
        im_table[None][0] = html_tools.content(logging_tools.get_plural("build", act_image["builds"]), cls="center")
        im_table[None][0] = html_tools.content(act_image["date"].ctime(), cls="right")
        im_table[None][0] = html_tools.content(act_image["build_lock"] and "locked" or "---", cls=act_image["build_lock"] and "errormin" or "center")
        act_devs, new_devs = (act_image["act_devices"],
                              act_image["new_devices"])
        if new_devs:
            im_table[None][0] = html_tools.content("N/A", cls="center")
        else:
            im_table[None][0] = html_tools.content(im_del_button, suffix=im_idx, cls="errormin")
        im_table[None][0] = html_tools.content("%d actual, %d new" % (len(act_devs),
                                                                      len(new_devs)), cls="left")
        im_table[None][0] = html_tools.content(act_image["size"] and get_size_str(act_image["size"]) or "unknown", cls="right")
        im_table[None][0] = html_tools.content(act_image["sys_vendor"] or "not set", cls="right")
        im_table[None][0] = html_tools.content(act_image["sys_version"] or "not set", cls="right")
        im_table[None][0] = html_tools.content(act_image["sys_release"] or "not set", cls="left")
        im_table[None][0] = html_tools.content(arch_list, act_image.get_suffix(), cls="left")
        im_table[None][0] = html_tools.content(act_image["bitcount"] or "unknown", cls="center")
        #im_table[None][0] = html_tools.content(new_devs and logging_tools.get_plural("device", new_devs) or "---", cls="left")
    if im_dict:
        sel_image = im_sel_list.check_selection("", (act_im_idxs + [0])[0])
        req.write(html_tools.gen_hline("Found %s, please select:" % (logging_tools.get_plural("Image", len(im_dict.keys()))), 2))
    else:
        sel_image = None
        req.write(html_tools.gen_hline("Found no images", 2))
    req.write("<form action=\"%s.py?%s\" method=post>\n" % (req.module_name,
                                                            functions.get_sid(req)))
    if check_image_servers:
        ims_output = "Scan for images on %s (%s): %s, " % (logging_tools.get_plural("server", len(req.conf["server"]["image_server"])),
                                                           ", ".join(req.conf["server"]["image_server"]),
                                                           check_image_servers(""))
    else:
        ims_output = ""
    req.write("%s\n<div class=\"center\">New Image Name: %s, source: %s</div>\n<div class=\"center\">%s%s</div></form>\n" % (im_dict and im_table("") or "",
                                                                                                                             new_image_f("n"),
                                                                                                                             new_image_f("s"),
                                                                                                                             ims_output,
                                                                                                                             select_button("")))
    if sel_image in im_dict.keys():
        im_source = html_tools.text_field(req, "ims", size=256, display_len=32)
        req.write("<form action=\"%s.py?%s\" method=post>\n" % (req.module_name,
                                                                functions.get_sid(req)))
        act_image = im_dict[sel_image]
        # check vendor change
        new_vi = {"str" : vendor_fields["str"].check_selection("", act_image["sys_vendor"]),
                  "ver" : vendor_fields["ver"].check_selection("", act_image["sys_version"]),
                  "rel" : vendor_fields["rel"].check_selection("", act_image["sys_release"])}
        if new_vi["str"] != act_image["sys_vendor"] or new_vi["ver"] != act_image["sys_version"] or new_vi["rel"] != act_image["sys_release"]:
            req.dc.execute("UPDATE image SET sys_vendor=%s, sys_version=%s, sys_release=%s WHERE image_idx=%s", (new_vi["str"],
                                                                                                                 new_vi["ver"],
                                                                                                                 new_vi["rel"],
                                                                                                                 sel_image))
            action_log.add_ok("Modified Vendor information to %s %s.%s" % (new_vi["str"], new_vi["ver"], new_vi["rel"]), "SQL")
            act_image["sys_vendor"]  = new_vi["str"]
            act_image["sys_version"] = new_vi["ver"]
            act_image["sys_release"] = new_vi["rel"]
        new_path, new_vfi, new_vfu = (exclude_path.check_selection("0", ""),
                                      vfi_button.check_selection("0"),
                                      vfu_button.check_selection("0"))
        new_idx = 0
        new_source = im_source.check_selection("0", act_image["source"])
        if new_source != act_image["source"]:
            if new_source.startswith("/") and new_source.count("/") > 2:
                action_log.add_ok("Modified source-path to '%s'" % (new_source), "OK")
                req.dc.execute("UPDATE image SET source=%s WHERE image_idx=%s", (new_source.strip(),
                                                                                 sel_image))
                im_source["0"] = new_source.strip()
                im_change = 1
            else:
                action_log.add_error("Cannot modify source-path to '%s'" % (new_source), "Path Error")
                im_source["0"] = act_image["source"]
        if new_path:
            exclude_path["0"] = ""
            if path_is_valid(new_path):
                action_log.add_ok("Adding exclude path '%s' to image" % (new_path), "SQL")
                req.dc.execute("INSERT INTO image_excl SET image=%s, exclude_path=%s, valid_for_install=%s, valid_for_upgrade=%s", (sel_image, new_path, new_vfi, new_vfu))
                new_idx = req.dc.insert_id()
                act_image.add_exclude_path(new_idx, new_path, new_vfi, new_vfu)
                im_change = 1
            else:
                action_log.add_error("Cannot add exclude path '%s' to image" % (new_path), "path error")
            
        if not new_idx and not act_image.exclude_paths:
            action_log.add_ok("Adding default exclude paths to image", "SQL")
            for ex_p, vfi, vfu in [("/var/log/*", 1, 1),
                                   ("/tmp/*"    , 1, 1),
                                   ("/var/run/*", 1, 1),
                                   ("/proc/*"   , 1, 1),
                                   ("/root/*"   , 1, 1),
                                   ("/sys/*"    , 1, 1)]:
                req.dc.execute("INSERT INTO image_excl SET exclude_path=%s, valid_for_install=%s, valid_for_upgrade=%s, image=%s", (ex_p, vfi, vfu, sel_image))
                p_suf = "%d" % (req.dc.insert_id())
                act_image.add_exclude_path(req.dc.insert_id(), ex_p, vfi, vfu)
                exclude_path.check_selection(p_suf, ex_p)
                vfi_button.check_selection(p_suf, vfi)
                vfu_button.check_selection(p_suf, vfu)
                im_change = 1            

        rem_paths = []
        for idx, (path, vfi, vfu) in act_image.exclude_paths.iteritems():
            p_suf = "%d" % (idx)
            if del_button.check_selection(p_suf):
                rem_paths.append(idx)
            else:
                act_path = exclude_path.check_selection(p_suf, path)
                if sub:
                    act_vfi = vfi_button.check_selection(p_suf, new_idx == idx)
                    act_vfu = vfu_button.check_selection(p_suf, new_idx == idx)
                else:
                    act_vfi = vfi_button.check_selection(p_suf, vfi)
                    act_vfu = vfu_button.check_selection(p_suf, vfu)
                if new_idx != idx:
                    change_list, change_tuple, change_ok = ([], [], True)
                    if act_path != path:
                        change_list.append("exclude_path=%s")
                        change_tuple.append(act_path)
                        if not path_is_valid(path):
                            change_ok = False
                            exclude_path[p_suf] = path
                    if act_vfi != vfi:
                        change_list.append("valid_for_install=%d" % (act_vfi))
                    if act_vfu != vfu:
                        change_list.append("valid_for_upgrade=%d" % (act_vfu))
                    if change_list:
                        if change_ok:
                            action_log.add_ok("Changing properites of exclude_path '%s'" % (path), "SQL")
                            req.dc.execute("UPDATE image_excl SET %s WHERE image_excl_idx=%d" % (", ".join(change_list), idx), change_tuple)
                            act_image.exclude_paths[idx] = (act_path, act_vfi, act_vfu)
                            im_change = 1
                        else:
                            action_log.add_error("Cannot change properites of exclude_path '%s'" % (path), "path error")
                    
        if rem_paths:
            action_log.add_ok("Removing %s from image" % (logging_tools.get_plural("path", len(rem_paths))), "SQL")
            for idx in rem_paths:
                del act_image.exclude_paths[idx]
            req.dc.execute("DELETE FROM image_excl WHERE (%s) AND image=%d" % (" OR ".join(["image_excl_idx=%d" % (x) for x in rem_paths]), sel_image))
            im_change = 1
    if im_change:
        tools.iterate_s_commands([tools.s_command(req, "image_server", 8004, "write_rsyncd_config", [], 10, None, {"not_full" : 1})], action_log)
    req.write(action_log.generate_stack("Log"))
    if sel_image in im_dict.keys():
        excl_table = show_image_exclude_paths(req, act_image, im_source, exclude_path, del_button, vfi_button, vfu_button, vendor_fields)
        req.write("%s%s%s<div class=\"center\">%s</div>\n</form>\n" % (excl_table(""),
                                                                       im_sel_list.create_hidden_var(),
                                                                       low_submit.create_hidden_var(),
                                                                       submit_button("")))
