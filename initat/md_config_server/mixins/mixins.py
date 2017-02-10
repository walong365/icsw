# Copyright (C) 2001-2017 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-server-server
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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
""" mixins providing various functions for build process / md-config-server """

import configparser
import base64
import binascii
import codecs
import subprocess
import operator
import os
import sqlite3
import time

import networkx
from django.db.models import Q

from initat.cluster.backbone.models import device, mon_ext_host, \
    netdevice, device_group, user
from initat.tools import logging_tools, process_tools
from ..config.global_config import global_config
from functools import reduce

__all__ = [
    "ImageMapMixin",
    "DistanceMapMixin",
    "NagVisMixin",
]


class ImageMapMixin(object):
    def IM_get_mon_ext_hosts(self):
        return {
            cur_ext.pk: cur_ext for cur_ext in mon_ext_host.objects.all()
        }

    def IM_check_image_maps(self):
        min_width, max_width, min_height, max_height = (16, 64, 16, 64)
        all_image_stuff = self.IM_get_mon_ext_hosts()
        self.log("Found {}".format(logging_tools.get_plural("ext_host entry", len(list(all_image_stuff.keys())))))
        logos_dir = "{}/share/images/logos".format(self.gc["MD_BASEDIR"])
        base_names = set()
        if os.path.isdir(logos_dir):
            logo_files = os.listdir(logos_dir)
            for log_line in [entry.split(".")[0] for entry in logo_files]:
                if log_line not in base_names:
                    if "{}.png".format(log_line) in logo_files and "{}.gd2".format(log_line) in logo_files:
                        base_names.add(log_line)
        name_case_lut = {}
        if base_names:
            stat, out = subprocess.getstatusoutput("file {}".format(" ".join([os.path.join(logos_dir, "{}.png".format(entry)) for entry in base_names])))
            if stat:
                self.log(
                    "error getting filetype of {}".format(
                        logging_tools.get_plural("logo", len(base_names))
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                base_names = set()
                for logo_name, logo_data in [
                    (os.path.basename(y[0].strip()), [z.strip() for z in y[1].split(",") if z.strip()]) for y in [
                        line.strip().split(":", 1) for line in out.split("\n")] if len(y) == 2]:
                    if len(logo_data) == 4:
                        width, height = [int(value.strip()) for value in logo_data[1].split("x")]
                        if min_width <= width and width <= max_width and min_height <= height and height <= max_height:
                            base_name = logo_name[:-4]
                            base_names.add(base_name)
                            name_case_lut[base_name.lower()] = base_name
                        else:
                            self.log(
                                "width or height ({:d} x {:d}) not in range ([{:d} - {:d}] x [{:d} - {:d}])".format(
                                    width,
                                    height,
                                    min_width,
                                    max_width,
                                    min_height,
                                    max_height,
                                )
                            )
        name_lut = {eh.name.lower(): pk for pk, eh in all_image_stuff.items()}
        all_images_present = set([eh.name for eh in list(all_image_stuff.values())])
        all_images_present_lower = set([name.lower() for name in all_images_present])
        base_names_lower = set([name.lower() for name in base_names])
        new_images = base_names_lower - all_images_present_lower
        del_images = all_images_present_lower - base_names_lower
        present_images = base_names_lower & all_images_present_lower
        for new_image in new_images:
            mon_ext_host(
                name=new_image,
                icon_image="{}.png".format(new_image),
                statusmap_image="%s.gd2" % (new_image)
            ).save()
        for p_i in present_images:
            img_stuff = all_image_stuff[name_lut[p_i]]
            # check for wrong case
            if img_stuff.icon_image != "{}.png".format(name_case_lut[img_stuff.name]):
                # correct case
                img_stuff.icon_image = "{}.png".format(name_case_lut[img_stuff.name])
                img_stuff.statusmap_image = "{}.gd2".format(name_case_lut[img_stuff.name])
                img_stuff.save()
        if del_images:
            mon_ext_host.objects.filter(Q(name__in=del_images)).delete()
        self.log(
            "Inserted {}, deleted {}".format(
                logging_tools.get_plural("new ext_host_entry", len(new_images)),
                logging_tools.get_plural("ext_host_entry", len(del_images))
            )
        )


class DistanceMapMixin(object):
    def DM_build_distance_map(self, root_node, router_obj):
        s_time = time.time()
        self.log("building distance map, root node is '{}'".format(root_node))
        # exclude all without attached netdevices
        dm_dict = {
            cur_dev.pk: cur_dev for cur_dev in device.objects.filter(
                Q(enabled=True) & Q(device_group__enabled=True)
            ).exclude(netdevice=None).select_related("domain_tree_node").prefetch_related("netdevice_set")
        }
        nd_dict = {}
        for dev_pk, nd_pk in netdevice.objects.filter(Q(enabled=True)).values_list("device", "pk"):
            nd_dict.setdefault(dev_pk, set()).add(nd_pk)
        nd_lut = {
            value[0]: value[1] for value in netdevice.objects.filter(
                Q(enabled=True)
            ).values_list("pk", "device") if value[1] in list(dm_dict.keys())
        }
        for cur_dev in dm_dict.values():
            # set 0 for root_node, -1 for all other devices
            cur_dev.md_dist_level = 0 if cur_dev.pk == root_node.pk else -1
        all_pks = set(dm_dict.keys())
        all_nd_pks = set(nd_lut.keys())
        max_level = 0
        # limit for loop
        for cur_iter in range(128):
            run_again = False
            # iterate until all nodes have a valid dist_level set
            src_nodes = set([key for key, value in dm_dict.items() if value.md_dist_level >= 0])
            dst_nodes = all_pks - src_nodes
            self.log(
                "dm_run {:3d}, {}, {}".format(
                    cur_iter,
                    logging_tools.get_plural("source node", len(src_nodes)),
                    logging_tools.get_plural("dest node", len(dst_nodes))
                )
            )
            src_nds = reduce(operator.ior, [nd_dict[key] for key in src_nodes if key in nd_dict], set())
            # dst_nds = reduce(operator.ior, [nd_dict[key] for key in dst_nodes], set())
            # build list of src_nd, dst_nd tuples
            nb_list = []
            for src_nd in src_nds:
                try:
                    for dst_nd in networkx.all_neighbors(router_obj.nx, src_nd):
                        if dst_nd not in src_nds:
                            nb_list.append((src_nd, dst_nd))
                except networkx.exception.NetworkXError:
                    self.log(
                        "netdevice {} is not in graph: {}".format(
                            src_nd,
                            process_tools.get_except_info(),
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
            for src_nd, dst_nd, in nb_list:
                if src_nd in all_nd_pks and dst_nd in all_nd_pks:
                    src_dev, dst_dev = (dm_dict[nd_lut[src_nd]], dm_dict[nd_lut[dst_nd]])
                    new_level = src_dev.md_dist_level + 1
                    if dst_dev.md_dist_level >= 0 and new_level > dst_dev.md_dist_level:
                        self.log(
                            "pushing node {} farther away from root ({:d} => {:d})".format(
                                str(dst_dev),
                                dst_dev.md_dist_level,
                                new_level,
                            )
                        )
                    dst_dev.md_dist_level = max(dst_dev.md_dist_level, new_level)
                    max_level = max(max_level, dst_dev.md_dist_level)
                    run_again = True
                else:
                    self.log(
                        "dropping link ({:d}, {:d}), devices disabled?".format(
                            src_nd,
                            dst_nd
                        ),
                        logging_tools.LOG_LEVEL_WARN
                    )
            if not run_again:
                break
        e_time = time.time()
        self.log(
            "time spent: {}, max distance level: {:d}".format(
                logging_tools.get_diff_time_str(e_time - s_time),
                max_level,
            )
        )
        nodes_ur = [str(value) for value in dm_dict.values() if value.md_dist_level < 0]
        ur_pks = [_entry.pk for _entry in dm_dict.values() if _entry.md_dist_level < 0]
        for level in range(max_level + 1):
            self.log(
                "nodes in level {:d}: {}".format(
                    level,
                    len([True for value in dm_dict.values() if value.md_dist_level == level]),
                )
            )
        return {
            key: value.md_dist_level for key, value in dm_dict.items()
        }, ur_pks, nodes_ur


class NagVisMixin(object):
    def NV_add_nagvis_info(self, act_host, host, nagvis_maps):
        act_host["_nagvis_map"] = "{}".format(host.full_name.encode("ascii", errors="ignore"))
        map_file = os.path.join(
            self.gc["NAGVIS_DIR"],
            "etc",
            "maps",
            "{}.cfg".format(
                host.full_name.encode("ascii", errors="ignore")
            )
        )
        map_dict = {
            "sources": "automap",
            "alias": host.comment or host.full_name,
            "iconset": "std_big",
            "child_layers": 10,
            "backend_id": "live_1",
            "root": host.full_name,
            "label_show": "1",
            "label_border": "transparent",
            "render_mode": "directed",
            "rankdir": "TB",
            "width": 800,
            "height": 600,
            "header_menu": True,
            "hover_menu": True,
            "context_menu": True,
            # parent map
            "parent_map": host.device_group.name.replace(" ", "_"),
            # special flag for anovis
            "use_childs_for_overview_icon": False,
        }
        try:
            map_h = codecs.open(map_file, "w", "utf-8")
        except:
            self.log(
                "cannot open {}: {}".format(
                    map_file,
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_CRITICAL
            )
        else:
            nagvis_maps.add(map_file)
            map_h.write("define global {\n")
            for key in sorted(map_dict.keys()):
                value = map_dict[key]
                if isinstance(value, bool):
                    value = "1" if value else "0"
                elif isinstance(value, int):
                    value = "%d" % (value)
                map_h.write("    {}={}\n".format(key, value))
            map_h.write("}\n")
            map_h.close()

    def NV_store_nagvis_maps(self, nagvis_map_dir, nagvis_maps):
        skipped_customs = 0
        for entry in os.listdir(nagvis_map_dir):
            if entry.startswith("custom_"):
                skipped_customs += 1
            else:
                full_name = os.path.join(nagvis_map_dir, entry)
                if full_name not in nagvis_maps:
                    self.log("removing old nagvis mapfile {}".format(full_name))
                    try:
                        os.unlink(full_name)
                    except:
                        self.log(
                            "error removing {}: {}".format(
                                full_name,
                                process_tools.get_except_info()
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
        if skipped_customs:
            self.log("skipped removing of {}".format(logging_tools.get_plural("custom map", skipped_customs)))
        # create group maps
        dev_groups = device_group.objects.filter(
            Q(enabled=True) &
            Q(device_group__name__in=[os.path.basename(entry).split(".")[0] for entry in nagvis_maps])
        ).distinct()
        self.log("creating maps for {}".format(logging_tools.get_plural("device group", len(dev_groups))))
        for dev_group in dev_groups:
            map_name = os.path.join(nagvis_map_dir, "{}.cfg".format(dev_group.name.replace(" ", "_")))
            open(map_name, "w").write(
                "\n".join(
                    [
                        "define global {",
                        "    alias=Group {}".format(dev_group.name),
                        "}",
                    ]
                )
            )

    def NV_clear_cache_dirs(self, cache_dir):
        rem_ok, rem_failed = (0, 0)
        for entry in os.listdir(cache_dir):
            try:
                full_name = os.path.join(cache_dir, entry)
            except:
                self.log(
                    "error building full_name from entry '{}'".format(
                        entry
                    ),
                    logging_tools.LOG_LEVEL_CRITICAL
                )
                rem_failed += 1
            else:
                if os.path.isfile(full_name):
                    try:
                        os.unlink(full_name)
                    except:
                        rem_failed += 1
                    else:
                        rem_ok += 1
        self.log(
            "cleaned cache_dir {} ({:d} ok, {:d} failed)".format(
                cache_dir,
                rem_ok,
                rem_failed,
            ),
            logging_tools.LOG_LEVEL_ERROR if rem_failed else logging_tools.LOG_LEVEL_OK
        )

    def NV_create_base_entries(self):
        if os.path.isdir(global_config["NAGVIS_DIR"]):
            self.log(
                "creating base entries for nagvis (under {})".format(
                    global_config["NAGVIS_DIR"]
                )
            )
            #
            nagvis_main_cfg = configparser.RawConfigParser(allow_no_value=True)
            for sect_name, var_list in [
                (
                        "global",
                        [
                            ("audit_log", 1),
                            ("authmodule", "CoreAuthModSQLite"),
                            ("authorisationmodule", "CoreAuthorisationModSQLite"),
                            ("controls_size", 10),
                            ("dateformat", "Y-m-d H:i:s"),
                            ("dialog_ack_sticky", 1),
                            ("dialog_ack_notify", 1),
                            ("dialog_ack_persist", 0),
                            # ("file_group", ""),
                            ("file_mode", "660"),
                            # ("http_proxy", ""),
                            ("http_timeout", 10),
                            ("language_detection", "user,session,browser,config"),
                            ("language", "en_US"),
                            ("logonmodule", "LogonMixed"),
                            ("logonenvvar", "REMOTE_USER"),
                            ("logonenvcreateuser", 1),
                            ("logonenvcreaterole", "Guests"),
                            ("refreshtime", 60),
                            ("sesscookiedomain", "auto-detect"),
                            ("sesscookiepath", "/nagvis"),
                            ("sesscookieduration", "86400"),
                            ("startmodule", "Overview"),
                            ("startaction", "view"),
                            ("startshow", ""),
                        ]
                ),
                (
                        "paths",
                        [
                            ("base", "{}/".format(os.path.normpath(global_config["NAGVIS_DIR"]))),
                            ("htmlbase", global_config["NAGVIS_URL"]),
                            ("htmlcgi", "/icinga/cgi-bin"),
                        ]
                ),
                (
                        "defaults",
                        [
                            ("backend", "live_1"),
                            ("backgroundcolor", "#ffffff"),
                            ("contextmenu", 1),
                            ("contexttemplate", "default"),
                            ("event_on_load", 0),
                            ("event_repeat_interval", 0),
                            ("event_repeat_duration", -1),
                            ("eventbackground", 0),
                            ("eventhighlight", 1),
                            ("eventhighlightduration", 10000),
                            ("eventhighlightinterval", 500),
                            ("eventlog", 0),
                            ("eventloglevel", "info"),
                            ("eventlogevents", 24),
                            ("eventlogheight", 75),
                            ("eventloghidden", 1),
                            ("eventscroll", 1),
                            ("eventsound", 1),
                            ("headermenu", 1),
                            ("headertemplate", "default"),
                            ("headerfade", 1),
                            ("hovermenu", 1),
                            ("hovertemplate", "default"),
                            ("hoverdelay", 0),
                            ("hoverchildsshow", 0),
                            ("hoverchildslimit", 100),
                            ("hoverchildsorder", "asc"),
                            ("hoverchildssort", "s"),
                            ("icons", "std_medium"),
                            ("onlyhardstates", 0),
                            ("recognizeservices", 1),
                            ("showinlists", 1),
                            ("showinmultisite", 1),
                            # ("stylesheet", ""),
                            ("urltarget", "_self"),
                            ("hosturl", "[htmlcgi]/status.cgi?host=[host_name]"),
                            ("hostgroupurl", "[htmlcgi]/status.cgi?hostgroup=[hostgroup_name]"),
                            ("serviceurl", "[htmlcgi]/extinfo.cgi?type=2&host=[host_name]&service=[service_description]"),
                            ("servicegroupurl", "[htmlcgi]/status.cgi?servicegroup=[servicegroup_name]&style=detail"),
                            ("mapurl", "[htmlbase]/index.php?mod=Map&act=view&show=[map_name]"),
                            ("view_template", "default"),
                            ("label_show", 0),
                            ("line_weather_colors", "10:#8c00ff,25:#2020ff,40:#00c0ff,55:#00f000,70:#f0f000,85:#ffc000,100:#ff0000"),
                        ]
                ),
                (
                        "index",
                        [
                            ("backgroundcolor", "#ffffff"),
                            ("cellsperrow", 4),
                            ("headermenu", 1),
                            ("headertemplate", "default"),
                            ("showmaps", 1),
                            ("showgeomap", 0),
                            ("showrotations", 1),
                            ("showmapthumbs", 0),
                        ]
                ),
                (
                        "automap",
                        [
                            ("defaultparams", "&childLayers=2"),
                            ("defaultroot", ""),
                            ("graphvizpath", "/opt/cluster/bin/"),
                        ]
                ),
                (
                        "wui",
                        [
                            ("maplocktime", 5),
                            ("grid_show", 0),
                            ("grid_color", "#D5DCEF"),
                            ("grid_steps", 32),
                        ]
                ),
                (
                        "worker",
                        [
                            ("interval", "10"),
                            ("requestmaxparams", 0),
                            ("requestmaxlength", 1900),
                            ("updateobjectstates", 30),
                        ]
                ),
                (
                        "backend_live_1",
                        [
                            ("backendtype", "mklivestatus"),
                            ("statushost", ""),
                            ("socket", "unix:/opt/icinga/var/live"),
                        ]
                ),
                (
                        "backend_ndomy_1",
                        [
                            ("backendtype", "ndomy"),
                            ("statushost", ""),
                            ("dbhost", "localhost"),
                            ("dbport", 3306),
                            ("dbname", "nagios"),
                            ("dbuser", "root"),
                            ("dbpass", ""),
                            ("dbprefix", "nagios_"),
                            ("dbinstancename", "default"),
                            ("maxtimewithoutupdate", 180),
                            ("htmlcgi", "/nagios/cgi-bin"),
                        ]
                ),
                (
                        "states",
                        [
                            ("down", 10),
                            ("down_ack", 6),
                            ("down_downtime", 6),
                            ("unreachable", 9),
                            ("unreachable_ack", 6),
                            ("unreachable_downtime", 6),
                            ("critical", 8),
                            ("critical_ack", 6),
                            ("critical_downtime", 6),
                            ("warning", 7),
                            ("warning_ack", 5),
                            ("warning_downtime", 5),
                            ("unknown", 4),
                            ("unknown_ack", 3),
                            ("unknown_downtime", 3),
                            ("error", 4),
                            ("error_ack", 3),
                            ("error_downtime", 3),
                            ("up", 2),
                            ("ok", 1),
                            ("unchecked", 0),
                            ("pending", 0),
                            ("unreachable_bgcolor", "#F1811B"),
                            ("unreachable_color", "#F1811B"),
                            # ("unreachable_ack_bgcolor", ""),
                            # ("unreachable_downtime_bgcolor", ""),
                            ("down_bgcolor", "#FF0000"),
                            ("down_color", "#FF0000"),
                            # ("down_ack_bgcolor", ""),
                            # ("down_downtime_bgcolor", ""),
                            ("critical_bgcolor", "#FF0000"),
                            ("critical_color", "#FF0000"),
                            # ("critical_ack_bgcolor", ""),
                            # ("critical_downtime_bgcolor", ""),
                            ("warning_bgcolor", "#FFFF00"),
                            ("warning_color", "#FFFF00"),
                            # ("warning_ack_bgcolor", ""),
                            # ("warning_downtime_bgcolor", ""),
                            ("unknown_bgcolor", "#FFCC66"),
                            ("unknown_color", "#FFCC66"),
                            # ("unknown_ack_bgcolor", ""),
                            # ("unknown_downtime_bgcolor", ""),
                            ("error_bgcolor", "#0000FF"),
                            ("error_color", "#0000FF"),
                            ("up_bgcolor", "#00FF00"),
                            ("up_color", "#00FF00"),
                            ("ok_bgcolor", "#00FF00"),
                            ("ok_color", "#00FF00"),
                            ("unchecked_bgcolor", "#C0C0C0"),
                            ("unchecked_color", "#C0C0C0"),
                            ("pending_bgcolor", "#C0C0C0"),
                            ("pending_color", "#C0C0C0"),
                            ("unreachable_sound", "std_unreachable.mp3"),
                            ("down_sound", "std_down.mp3"),
                            ("critical_sound", "std_critical.mp3"),
                            ("warning_sound", "std_warning.mp3"),
                            # ("unknown_sound", ""),
                            # ("error_sound", ""),
                            # ("up_sound", ""),
                            # ("ok_sound", ""),
                            # ("unchecked_sound", ""),
                            # ("pending_sound", ""),
                        ]
                )
            ]:
                nagvis_main_cfg.add_section(sect_name)
                for key, value in var_list:
                    nagvis_main_cfg.set(sect_name, key, str(value))
            try:
                nv_target = os.path.join(global_config["NAGVIS_DIR"], "etc", "nagvis.ini.php")
                with open(nv_target, "wb") as nvm_file:
                    nvm_file.write("; <?php return 1; ?>\n")
                    nagvis_main_cfg.write(nvm_file)
            except IOError:
                self.log(
                    "error creating {}: {}".format(
                        nv_target,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            # clear SALT
            config_php = os.path.join(global_config["NAGVIS_DIR"], "share", "server", "core", "defines", "global.php")
            if os.path.exists(config_php):
                lines = open(config_php, "r").read().split("\n")
                new_lines, save = ([], False)
                for cur_line in lines:
                    if cur_line.lower().count("auth_password_salt") and len(cur_line) > 60:
                        # remove salt
                        cur_line = "define('AUTH_PASSWORD_SALT', '');"
                        save = True
                    new_lines.append(cur_line)
                if save:
                    self.log("saving {}".format(config_php))
                    open(config_php, "w").write("\n".join(new_lines))
            else:
                self.log("config.php '{}' does not exist".format(config_php), logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("no nagvis_directory '{}' found".format(global_config["NAGVIS_DIR"]), logging_tools.LOG_LEVEL_ERROR)

    def NV_create_access_entries(self):
        # modify auth.db
        auth_db = os.path.join(global_config["NAGVIS_DIR"], "etc", "auth.db")
        self.log("modifying authentication info in {}".format(auth_db))
        try:
            conn = sqlite3.connect(auth_db)
        except:
            self.log(
                "cannot create connection: {}".format(
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_CRITICAL
            )
        else:
            cur_c = conn.cursor()
            cur_c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            # tables
            all_tables = [value[0] for value in cur_c.fetchall()]
            self.log(
                "found {}: {}".format(
                    logging_tools.get_plural("table", len(all_tables)),
                    ", ".join(sorted(all_tables))
                )
            )
            # delete previous users
            cur_c.execute("DELETE FROM users2roles")
            cur_c.execute("DELETE FROM users")
            cur_c.execute("DELETE FROM roles")
            cur_c.execute("DELETE FROM roles2perms")
            admin_role_id = cur_c.execute("INSERT INTO roles VALUES(Null, 'admins')").lastrowid
            perms_dict = {
                "{}.{}.{}".format(
                    cur_perm[1].lower(),
                    cur_perm[2].lower(),
                    cur_perm[3].lower()
                ): cur_perm[0] for cur_perm in cur_c.execute("SELECT * FROM perms")
                }
            # pprint.pprint(perms_dict)
            cur_c.execute(
                "INSERT INTO roles2perms VALUES({:d},{:d})".format(
                    admin_role_id,
                    perms_dict["*.*.*"]
                )
            )
            role_dict = {
                cur_role[1].lower().split()[0]: cur_role[0] for cur_role in cur_c.execute("SELECT * FROM roles")
                }
            self.log(
                "role dict: {}".format(
                    ", ".join(
                        [
                            "{}={:d}".format(key, value) for key, value in role_dict.items()
                            ]
                    )
                )
            )
            # get nagivs root points
            nagvis_rds = device.objects.filter(Q(automap_root_nagvis=True)).select_related("domain_tree_node", "device_group")
            self.log(
                "{}: {}".format(
                    logging_tools.get_plural("NagVIS root device", len(nagvis_rds)),
                    ", ".join([str(cur_dev) for cur_dev in nagvis_rds])
                )
            )
            devg_lut = {}
            for cur_dev in nagvis_rds:
                devg_lut.setdefault(cur_dev.device_group.pk, []).append(cur_dev.full_name)
            for cur_u in user.objects.filter(Q(active=True) & Q(mon_contact__pk__gt=0)).prefetch_related("allowed_device_groups"):
                # check for admin
                if cur_u.has_perm("backbone.device.all_devices"):
                    target_role = "admins"
                else:
                    # create special role
                    target_role = cur_u.login
                    role_dict[target_role] = cur_c.execute("INSERT INTO roles VALUES(Null, '{}')".format(cur_u.login)).lastrowid
                    add_perms = ["auth.logout.*", "overview.view.*", "general.*.*", "user.setoption.*"]
                    perm_names = []
                    for cur_devg in cur_u.allowed_device_groups.values_list("pk", flat=True):
                        for dev_name in devg_lut.get(cur_devg, []):
                            perm_names.extend(
                                [
                                    "map.view.{}".format(dev_name),
                                    "automap.view.{}".format(dev_name),
                                ]
                            )
                    for perm_name in perm_names:
                        if perm_name not in perms_dict:
                            try:
                                perms_dict[perm_name] = cur_c.execute(
                                    "INSERT INTO perms VALUES(Null, '{}', '{}', '{}')".format(
                                        perm_name.split(".")[0].title(),
                                        perm_name.split(".")[1],
                                        perm_name.split(".")[2]
                                    )
                                ).lastrowid
                                self.log("permission '{}' has id {:d}".format(perm_name, perms_dict[perm_name]))
                            except:
                                self.log(
                                    "cannot create permission '{}': {}".format(
                                        perm_name,
                                        process_tools.get_except_info()
                                    ),
                                    logging_tools.LOG_LEVEL_ERROR
                                )
                        add_perms.append(perm_name)
                    # add perms
                    for new_perm in add_perms:
                        if new_perm in perms_dict:
                            cur_c.execute("INSERT INTO roles2perms VALUES({:d}, {:d})".format(
                                role_dict[target_role],
                                perms_dict[new_perm]))
                    self.log(
                        "creating new role '{}' with perms {}".format(
                            target_role,
                            ", ".join(add_perms)
                        )
                    )
                self.log("creating user '{}' with role {}".format(
                    str(cur_u),
                    target_role,
                ))
                new_userid = cur_c.execute(
                    "INSERT INTO users VALUES(Null, '{}', '{}')".format(
                        cur_u.login,
                        binascii.hexlify(base64.b64decode(cur_u.password.split(":", 1)[1])),
                    )
                ).lastrowid
                cur_c.execute(
                    "INSERT INTO users2roles VALUES({:d}, {:d})".format(
                        new_userid,
                        role_dict[target_role],
                    )
                )
            conn.commit()
            conn.close()
