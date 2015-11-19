# Copyright (C) 2007,2013-2014 Andreas Lang-Nevyjel
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

""" create rsync config """

import os
import re

from django.db.models import Q

import cs_base_class
from initat.cluster.backbone.models import image
from initat.cluster_server.config import global_config
from initat.tools import logging_tools, process_tools, server_command


class write_rsyncd_config(cs_base_class.server_com):
    class Meta:
        needed_configs = ["rsync_server"]

    def _call(self, cur_inst):
        rsyncd_cf_name = "/etc/rsyncd.conf"
        # print cur_inst.srv_com.pretty_print()
        # not_full = opt_dict.get("not_full", 0)
        def_lines = [
            "uid = 0",
            "gid = 0",
            "read only = true",
            "use chroot = true",
            "transfer logging = false",
            "log format = %h %o %f %l %b",
            "log file = /var/log/rsyncd.log",
            "slp refresh = 300"]
        # aer_post_lines
        ae_post_lines = []
        try:
            in_lines = file("/etc/rsyncd.conf", "r").read().split("\n")
        except:
            pass
        else:
            aep_found = False
            for line in in_lines:
                if line.startswith("### AER-START-POST"):
                    aep_found = True
                elif line.startswith("### AER-END-POST"):
                    aep_found = False
                else:
                    if aep_found:
                        ae_post_lines.append(line)
        # empty image list
        im_list = []
        if False:  # not_full:
            if os.path.isfile(rsyncd_cf_name):
                im_re = re.compile("^.*\[(?P<image_name>.*)\].*$")
                com_re = re.compile("^\s*(?P<key>\S+)\s*=\s*(?P<value>.*)$")
                op_mode = "dl"
                def_lines, im_dict = ([], {})
                for line in [x.strip() for x in file(rsyncd_cf_name, "r").read().split("\n") if x.strip()]:
                    im_match = im_re.match(line)
                    if im_match:
                        image_name = im_match.group("image_name")
                        op_mode = "if"
                        im_dict[image_name] = {"path": "/",
                                               "exclude": ""}
                    if op_mode == "dl":
                        def_lines.append(line)
                    elif op_mode == "if":
                        com_match = com_re.match(line)
                        if com_match:
                            im_dict[image_name][com_match.group("key")] = com_match.group("value")
                if "root" in im_dict:
                    im_list = [
                        (
                            "root", im_dict["root"].get("path", "/"), im_dict["root"]["exclude"] and im_dict["root"]["exclude"].split() or ["/proc/", "/sys/"]
                        )
                    ]
        num_images, num_rsync = (0, 0)
        if not im_list:
            im_list = [("root", "/", ["/proc/", "/sys/"]), ]  # + opt_dict.get("exclude_dirs", "").split(":"))]
            extra_info = ""
        else:
            extra_info = " (root kept)"
        _server_idxs = [global_config["SERVER_IDX"]]
        # check for rsync
        rsync_dict = {}
        # for db_rec in call_params.dc.fetchall():
        #    rsync_dict.setdefault(db_rec["config_name"], {})[db_rec["name"]] = db_rec["value"]
        rsync_keys = sorted(rsync_dict.keys())
        self.log("found %s: %s" % (logging_tools.get_plural("rsync entry", len(rsync_keys)),
                                   ", ".join(rsync_keys) or "---"))
        # check for validity
        needed_keys = ["export_rsync", "rsync_name"]
        rsync_del_keys = []
        for rs_key in rsync_keys:
            if len([True for x in rsync_dict[rs_key].keys() if x in needed_keys]) != len(needed_keys):
                rsync_del_keys.append(rs_key)
                del rsync_dict[rs_key]
        if rsync_del_keys:
            self.log("deleting %s because of missing keys: %s" % (logging_tools.get_plural("rsync", len(rsync_del_keys)),
                                                                  ", ".join(rsync_del_keys)),
                     logging_tools.LOG_LEVEL_WARN)
            rsync_keys = [x for x in rsync_keys if x not in rsync_del_keys]
        # self.dc.execute("SELECT * FROM image")
        im_list.extend([(cur_img.name, cur_img.source, []) for cur_img in image.objects.filter(Q(enabled=True))])
        for im_name, im_source, im_exclude in im_list:
            num_images += 1
            def_lines.extend(["",
                              "[%s]" % (im_name),
                              "    path = %s" % (im_source)])
            if im_exclude:
                def_lines.append("    exclude = %s" % (" ".join(im_exclude)))
        for rsync_key in rsync_keys:
            rsync_stuff = rsync_dict[rsync_key]
            num_rsync += 1
            def_lines.extend(["",
                              "[%s]" % (rsync_stuff["rsync_name"]),
                              "    path = %s" % (rsync_stuff["export_rsync"])])
            if rsync_stuff.get("excluded_dirs", ""):
                def_lines.append("    exclude = %s" % (" ".join([os.path.normpath(x) for x in rsync_stuff["excluded_dirs"].strip().split()])))
        def_lines.append("")
        # add post lines
        def_lines.extend(["### AER-START-POST insert post-rsyncd.conf lines below"] +
                         ae_post_lines +
                         ["### AER-END-POST insert post-rsyncd.conf lines above", ""])
        try:
            file(rsyncd_cf_name, "w").write("\n".join(def_lines))
        except IOError:
            ret_state, ret_str = (server_command.SRV_REPLY_STATE_ERROR, "error creating %s" % (rsyncd_cf_name))
        else:
            cstat, log_f = process_tools.submit_at_command("/etc/init.d/rsyncd restart", 1)
            for log_line in log_f:
                self.log(log_line)
            if cstat:
                ret_state, ret_str = (
                    server_command.SRV_REPLY_STATE_ERROR,
                    "error unable to submit at-command (%d, see logs) to restart rsyncd" % (cstat))
            else:
                ret_state, ret_str = (
                    server_command.SRV_REPLY_STATE_OK,
                    "ok wrote rsyncd-config file %s for %s%s, %s" % (
                        rsyncd_cf_name, logging_tools.get_plural("image", num_images), extra_info,
                        logging_tools.get_plural("rsync", num_rsync))
                )
        cur_inst.set_result(ret_str, ret_state)
