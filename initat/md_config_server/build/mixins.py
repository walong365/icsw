# Copyright (C) 2001-2016 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
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

import codecs
import commands
import operator
import os

import networkx
from django.db.models import Q

from initat.cluster.backbone.models import device, mon_ext_host, \
    netdevice, device_group
from initat.tools import logging_tools, process_tools


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
        self.log("Found {}".format(logging_tools.get_plural("ext_host entry", len(all_image_stuff.keys()))))
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
            stat, out = commands.getstatusoutput("file {}".format(" ".join([os.path.join(logos_dir, "{}.png".format(entry)) for entry in base_names])))
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
        name_lut = {eh.name.lower(): pk for pk, eh in all_image_stuff.iteritems()}
        all_images_present = set([eh.name for eh in all_image_stuff.values()])
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
    def DM_build_distance_map(self, root_node, router_obj, show_unroutable=True):
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
            ).values_list("pk", "device") if value[1] in dm_dict.keys()
        }
        for cur_dev in dm_dict.itervalues():
            # set 0 for root_node, -1 for all other devices
            cur_dev.md_dist_level = 0 if cur_dev.pk == root_node.pk else -1
        all_pks = set(dm_dict.keys())
        all_nd_pks = set(nd_lut.keys())
        max_level = 0
        # limit for loop
        for cur_iter in xrange(128):
            run_again = False
            # iterate until all nodes have a valid dist_level set
            src_nodes = set([key for key, value in dm_dict.iteritems() if value.md_dist_level >= 0])
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
                                unicode(dst_dev),
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
        self.log("max distance level: {:d}".format(max_level))
        nodes_ur = [unicode(value) for value in dm_dict.itervalues() if value.md_dist_level < 0]
        ur_pks = [_entry.pk for _entry in dm_dict.itervalues() if _entry.md_dist_level < 0]
        if nodes_ur and show_unroutable:
            self.log(
                u"{}: {}".format(
                    logging_tools.get_plural("unroutable node", len(nodes_ur)),
                    u", ".join(sorted(nodes_ur)),
                )
            )
        for level in xrange(max_level + 1):
            self.log(
                "nodes in level {:d}: {}".format(
                    level,
                    len([True for value in dm_dict.itervalues() if value.md_dist_level == level]),
                )
            )
        return {
            key: value.md_dist_level for key, value in dm_dict.iteritems()
        }, ur_pks


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
            self.mach_log(
                u"cannot open {}: {}".format(
                    map_file,
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_CRITICAL
            )
        else:
            nagvis_maps.add(map_file)
            map_h.write("define global {\n")
            for key in sorted(map_dict.iterkeys()):
                value = map_dict[key]
                if type(value) == bool:
                    value = "1" if value else "0"
                elif type(value) in [int, long]:
                    value = "%d" % (value)
                map_h.write(u"    {}={}\n".format(key, value))
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
            file(map_name, "w").write(
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
