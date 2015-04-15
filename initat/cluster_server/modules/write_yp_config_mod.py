# Copyright (C) 2007,2012-2015 Andreas Lang-Nevyjel
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
""" modifies yp-databases """

from django.db.models import Q
from initat.cluster.backbone.models import user, group, device_config, \
    config_str, home_export_list, device
from initat.cluster_server.config import global_config
import commands
import cs_base_class
import cs_tools
import logging_tools
import os
import re
import server_command
import shutil
import time


class write_yp_config(cs_base_class.server_com):
    class Meta:
        needed_configs = ["yp_server"]

    def _call(self, cur_inst):  # call_it(self, opt_dict, call_params):
        try:
            import gdbm
        except ImportError:
            return "error unable to load gdbm-Module (gdbm-devel missing on compile machine?)"
        par_dict = dict([(cur_var.name, cur_var.value) for cur_var in config_str.objects.filter(Q(config__name="yp_server"))])
        errors = []
        dryrun_flag = "server_key:dryrun"
        if dryrun_flag in cur_inst.srv_com:
            self.dryrun = True
        else:
            self.dryrun = False
        cur_inst.log("dryrun flag is '%s'" % (str(self.dryrun)))
        needed_keys = set(["domainname"])
        missed_keys = needed_keys - set(par_dict.keys())
        if len(missed_keys):
            errors.append(
                "%s missing: %s" % (
                    logging_tools.get_plural("config_key", len(missed_keys)),
                    ", ".join(missed_keys)))

        # fetch all users / groups
        all_groups = dict([(cur_g.pk, cur_g) for cur_g in group.objects.all()])
        all_users = dict([(cur_u.pk, cur_u) for cur_u in user.objects.prefetch_related("secondary_groups").all()])
        # normal exports
        exp_entries = device_config.objects.filter(
            Q(config__name__icontains="export")
        ).prefetch_related(
            "config__config_str_set"
        ).select_related(
            "device",
            "device__device_group",
        )
        export_dict = {}
        ei_dict = {}
        for entry in exp_entries:
            act_pk = entry.config.pk
            if not entry.device.is_meta_device:
                dev_names = [entry.device.name]
            else:
                # expand meta devices
                dev_names = device.objects.filter(Q(is_meta_device=False) & Q(device_group=entry.device.device_group)).values_list("name", flat=True)
            for dev_name in dev_names:
                ei_dict.setdefault(
                    dev_name, {}
                ).setdefault(
                    act_pk,
                    {
                        "export": None,
                        "import": None,
                        "node_postfix": "",
                        "options": "-soft"
                    }
                )
                for c_str in entry.config.config_str_set.all():
                    if c_str.name in ei_dict[dev_name][act_pk]:
                        ei_dict[dev_name][act_pk][c_str.name] = c_str.value
        for mach, aeid_d in ei_dict.iteritems():
            for _aeid_idx, aeid in aeid_d.iteritems():
                if aeid["export"] and aeid["import"]:
                    aeid["import"] = cs_tools.hostname_expand(mach, aeid["import"])
                    export_dict[aeid["import"]] = (aeid["options"], "%s%s:%s" % (mach, aeid["node_postfix"], aeid["export"]))
        # home-exports
        home_exp_dict = home_export_list().exp_dict
        for user_stuff in [cur_u for cur_u in all_users.values() if cur_u.active and cur_u.group.active]:
            group_stuff = all_groups[user_stuff.group_id]
            if user_stuff.export_id in home_exp_dict.keys():
                home_stuff = home_exp_dict[user_stuff.export_id]
                export_dict[
                    os.path.normpath(
                        os.path.join(group_stuff.homestart, user_stuff.home)
                    )
                ] = (
                    home_stuff["options"],
                    "%s%s:%s/%s" % (home_stuff["name"], home_stuff["node_postfix"], home_stuff["homeexport"], user_stuff.home)
                )
            else:
                self.log("skipping user %s (no valid export entry)" % (unicode(user_stuff)), logging_tools.LOG_LEVEL_WARN)
        # print export_dict
        # auto.master map
        auto_master = []
        # print export_dict
        ext_keys = {}
        for ext_k in export_dict.keys():
            splits = ext_k.split("/")
            dirname = os.path.normpath(splits.pop())
            mountpoint = "/".join(splits).replace("/", "").strip()
            if mountpoint:
                exp = "auto.%s" % (mountpoint)
                if exp not in ext_keys.keys():
                    ext_keys[exp] = []
                    auto_master.append((os.path.normpath("%s/" % ("/".join(splits))), exp))
                ext_keys[exp].append((dirname, " ".join(export_dict[ext_k])))
        # collect homedir-export entries and create group/passwd entries
        # group-entries
        gbg = []
        gbn = []
        # self.dc.execute("SELECT g.ggroup_idx, g.ggroupname, g.gid FROM ggroup g WHERE g.active=1")
        for group_pk, group_struct in all_groups.iteritems():
            # groups[name] = entry
            # self.dc.execute("SELECT u.login FROM user u, ggroup g WHERE u.ggroup=g.ggroup_idx AND u.export > 0 AND g.gid=%d" % (gid))
            users = [cur_u.login for cur_u in all_users.itervalues() if cur_u.group_id == group_pk]
            if len(users):
                gbn.append((group_struct.groupname, "%s:*:%d:%s" % (group_struct.groupname, group_struct.gid, ",".join(users))))
                gbg.append(("%d" % (group_struct.gid), "%s:*:%d:%s" % (group_struct.groupname, group_struct.gid, ",".join(users))))
        ext_keys["group.bygid"] = gbg
        ext_keys["group.byname"] = gbn
        # passwd-entries
        pbu = []
        pbn = []
        for _user_pk, user_struct in all_users.iteritems():
            group_struct = all_groups[user_struct.group_id]
            home = os.path.normpath(
                os.path.join(
                    group_struct.homestart,
                    user_struct.home or user_struct.login
                )
            )
            cur_pwd = user_struct.password
            if cur_pwd.count(":"):
                pw_hash, password = cur_pwd.split(":", 1)
            else:
                pw_hash, password = ("CRYPT", cur_pwd)
            if pw_hash == "CRYPT":
                pw_enc = password
            else:
                # from crypt(3):
                #  ID  | Method
                #  ----------------------------------------------------
                #  1   | MD5
                #  2a  | Blowfish, system-specific on 8-bit chars
                #  2y  | Blowfish, correct handling of 8-bit chars
                #  5   | SHA-256 (since glibc 2.7)
                #  6   | SHA-512 (since glibc 2.7)
                # hm, in fact we have an SHA1 password, this will not work...
                pw_enc = "$5$${}".format(password)
            full_name = " ".join([(getattr(user_struct, key) or "").strip() for key in ["title", "first_name", "last_name"]]) or user_struct.login
            pbn.append(
                (
                    user_struct.login,
                    "%s:%s:%d:%d:%s:%s:%s" % (
                        user_struct.login, pw_enc, user_struct.uid, group_struct.gid, full_name, home, user_struct.shell
                    )
                )
            )
            pbu.append(
                (
                    "%d" % (user_struct.uid),
                    "%s:%s:%d:%d:%s:%s:%s" % (user_struct.login, pw_enc, user_struct.uid, group_struct.gid, full_name, home, user_struct.shell)
                )
            )
        ext_keys["passwd.byuid"] = pbu
        ext_keys["passwd.byname"] = pbn
        # home-exports
        if False:
            #  self.dc.execute("SELECT d.name, cs.value, dc.device_config_idx, cs.name AS csname FROM device d, new_config c,
            #  device_config dc, config_str cs, device_type dt WHERE d.device_type=dt.device_type_idx AND dt.identifier='H'
            # AND cs.new_config=c.new_config_idx AND dc.new_config=c.new_config_idx AND dc.device=d.device_idx AND
            # (cs.name='homeexport' OR cs.name='options') ORDER BY d.name")
            home_exp_dict = {}
            for entry in self.dc.fetchall():
                home_exp_dict.setdefault(
                    entry["device_config_idx"],
                    {
                        "name": entry["name"],
                        "options": "",
                        "homeexport": ""
                    }
                )[entry["csname"]] = entry["value"]
            valid_home_keys = [x for x in home_exp_dict.keys() if home_exp_dict[x]["homeexport"]]
            if valid_home_keys:
                # self.dc.execute("SELECT u.login, g.homestart, u.home, u.export FROM user u,
                # ggroup g WHERE u.ggroup=g.ggroup_idx AND (%s)" % (" OR ".join(["u.export=%d" % (x) for x in valid_home_keys])))
                for e2 in self.dc.fetchall():
                    if e2["homestart"]:
                        mountpoint = e2["homestart"].replace("/", "").strip()
                        entry = home_exp_dict[e2["export"]]
                        if mountpoint:
                            homestart = "auto.%s" % (mountpoint)
                            if not ext_keys.has_key(homestart):
                                ext_keys[homestart] = []
                                auto_master.append((e2["homestart"], homestart))
                            ext_keys[homestart].append((e2["home"], "%s %s:%s/%s" % (entry["options"], entry["name"], cs_tools.hostname_expand(entry["name"], entry["homeexport"]), e2["home"])))
                        else:
                            pass
                            # mysql_tools.device_log_entry(self.dc,
                            #                             global_config["SERVER_IDX"],
                            #                             global_config["LOG_SOURCE_IDX"],
                            #                             0,
                            #                             global_config["LOG_STATUS"]["e"]["log_status_idx"],
                            #                             "refuse to create automont-map for / (homedir-export)")
        ext_keys["auto.master"] = auto_master
        nis_name = par_dict["domainname"]
        # parse /etc/services for the services.byname and services.byservicename maps
        array = [line.strip() for line in file("/etc/services", "r").read().split("\n") if not re.match("^(#.*|\s*)$", line)]
        sbn = []
        sbs = []
        for service in array:
            serv_split = re.match("^(\S+)\s+(\d+)/(\S+).*$", service)
            if serv_split:
                serv_name = serv_split.group(1)
                port = int(serv_split.group(2))
                prot = serv_split.group(3)
                sbn.append(("%d/%s" % (port, prot), "%s %d/%s" % (serv_name, port, prot)))
                sbs.append(("%s/%s" % (serv_name, prot), "%s %d/%s" % (serv_name, port, prot)))
        ext_keys["services.byname"] = sbn
        ext_keys["services.byservicename"] = sbs
        # generate ypservers map
        temp_map_dir = "_ics_tmd"
        ext_keys["ypservers"] = [
            (
                global_config["SERVER_FULL_NAME"],
                global_config["SERVER_FULL_NAME"],
            )
        ]
        # pprint.pprint(ext_keys)
        temp_map_dir = "/var/yp/%s" % (temp_map_dir)
        if not os.path.isdir("/var/yp"):
            cur_inst.srv_com.set_result(
                "no /var/yp directory",
                server_command.SRV_REPLY_STATE_ERROR
            )
        else:
            if os.path.isdir(temp_map_dir):
                shutil.rmtree(temp_map_dir, 1)
            if not os.path.isdir(temp_map_dir):
                os.mkdir(temp_map_dir)
            map_keys = sorted(ext_keys.keys())
            for mapname in map_keys:
                self.log("creating map named %s ..." % (mapname))
                map_name = "%s/%s" % (temp_map_dir, mapname)
                # print map_name
                gdbf = gdbm.open(map_name, "n", 0600)
                gdbf["YP_INPUT_NAME"] = "{}.dbl".format(mapname)
                gdbf["YP_OUTPUT_NAME"] = map_name
                gdbf["YP_MASTER_NAME"] = global_config["SERVER_FULL_NAME"]
                gdbf["YP_LAST_MODIFIED"] = str(int(time.time()))
                for key, value in ext_keys[mapname]:
                    gdbf[key] = value.encode("ascii", errors="ignore")
                    # print "%s --> %s" % (a, b)
                gdbf.close()
            # rename temporary name to new name
            map_dir = "/var/yp/%s" % (nis_name)
            if os.path.isdir(map_dir):
                shutil.rmtree(map_dir, 1)
            os.rename(temp_map_dir, map_dir)
            num_maps = len(ext_keys.keys())
            if os.path.isfile("/usr/lib64/yp/makedbm"):
                cstat, cout = commands.getstatusoutput("/usr/lib64/yp/makedbm -c")
            else:
                cstat, cout = commands.getstatusoutput("/usr/lib/yp/makedbm -c")
            if cstat:
                cur_inst.srv_com.set_result(
                    "wrote {}, reloading gave: '{}'".format(
                        logging_tools.get_plural("YP-map", num_maps),
                        cout,
                    ),
                    server_command.SRV_REPLY_STATE_ERROR
                )
            else:
                cur_inst.srv_com.set_result(
                    "wrote {} and successfully reloaded configuration".format(
                        logging_tools.get_plural("YP-map", num_maps),
                    ),
                )
