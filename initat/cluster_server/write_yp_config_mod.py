#!/usr/bin/python -Ot
#
# Copyright (C) 2007,2012,2013 Andreas Lang-Nevyjel
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

import sys
import cs_base_class
import cs_tools
import os
import mysql_tools
import re
import shutil
import time
import commands
import server_command
from initat.cluster_server.config import global_config

class write_yp_config(cs_base_class.server_com):
    class Meta:
        needed_configs = ["yp_server"]
    def _call(self, cur_inst):#call_it(self, opt_dict, call_params):
        try:
            import gdbm
        except ImportError:
            return "error unable to load gdbm-Module (gdbm-devel missing on compile machine?)"
        # generate passwd-databases
        # init autofs-master-dict
        am_dict = {}
        # collect machine export-entries (not the homedir-exports!)
        self.dc.execute("SELECT d.name, cs.name AS csname, cs.value, cs.new_config FROM device d INNER JOIN new_config c " + \
                               "INNER JOIN device_config dc INNER JOIN config_str cs INNER JOIN device_group dg INNER JOIN device_type dt " + \
                               "LEFT JOIN device d2 ON d2.device_idx=dg.device WHERE d.device_type=dt.device_type_idx AND dt.identifier='H' AND " + \
                               "d.device_group=dg.device_group_idx AND cs.new_config=c.new_config_idx AND dc.new_config=c.new_config_idx AND " + \
                               "(dc.device=d.device_idx OR dc.device=d2.device_idx) AND (cs.name='export' OR cs.name='import' OR cs.name='options') ORDER BY d.name, cs.config")
        export_dict = {}
        ei_dict = {}
        for entry in self.dc.fetchall():
            dev_name, act_idx = (entry["name"], entry["new_config"])
            # generate a small dict for each export-entry (per device)
            ei_dict.setdefault(dev_name, {}).setdefault(act_idx, {"export"  : None,
                                                                  "import"  : None,
                                                                  "options" : "-soft"})[entry["csname"]] = cs_tools.hostname_expand(entry["name"], entry["value"])
        for mach, aeid_d in ei_dict.iteritems():
            for aeid_idx, aeid in aeid_d.iteritems():
                if aeid["export"] and aeid["import"]:
                    aeid["import"] = cs_tools.hostname_expand(mach, aeid["import"])
                    #print ei_dict
                    export_dict[aeid["import"]] = "%s %s:%s" % (aeid["options"], mach, aeid["export"])
        #print export_dict
        # auto.master map
        auto_master = []
        #print export_dict
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
                ext_keys[exp].append((dirname, export_dict[ext_k]))
            else:
                mysql_tools.device_log_entry(self.dc,
                                             global_config["SERVER_IDX"],
                                             global_config["LOG_SOURCE_IDX"],
                                             0,
                                             global_config["LOG_STATUS"]["e"]["log_status_idx"],
                                             "refuse to create automont-map for / ")
        # collect homedir-export entries and create group/passwd entries
        # group-entries
        gbg = []
        gbn = []
        groups = {}
        self.dc.execute("SELECT g.ggroup_idx, g.ggroupname, g.gid FROM ggroup g WHERE g.active=1")
        for entry in self.dc.fetchall():
            name = entry["ggroupname"]
            gid = entry["gid"]
            groups[name] = entry
            self.dc.execute("SELECT u.login FROM user u, ggroup g WHERE u.ggroup=g.ggroup_idx AND u.export > 0 AND g.gid=%d" % (gid))
            users = []
            for user in self.dc.fetchall():
                users.append(user["login"])
            self.dc.execute("SELECT u.login FROM user u, ggroup g, user_ggroup ug WHERE ug.user=u.user_idx AND ug.ggroup=g.ggroup_idx AND u.export > 0 AND g.gid=%d" % (gid))
            for user in self.dc.fetchall():
                users.append(user["login"])
            if len(users):
                gbn.append((name, "%s:*:%d:%s" % (name, gid, ",".join(users))))
                gbg.append(("%d" % (gid), "%s:*:%d:%s" % (name, gid, ",".join(users))))
        ext_keys["group.bygid"] = gbg
        ext_keys["group.byname"] = gbn
        # passwd-entries
        pbu = []
        pbn = []
        self.dc.execute("SELECT u.login, u.uid, u.password, u.home, u.shell, u.uservname, u.usernname, u.usertitan, g.homestart, g.ggroupname, g.gid FROM user u, ggroup g, new_config c, device_config dc, device d WHERE u.active=1 AND u.ggroup=g.ggroup_idx AND u.export=dc.device_config_idx AND dc.new_config=c.new_config_idx AND dc.device=d.device_idx ORDER by u.login")
        for entry in self.dc.fetchall():
            home = os.path.normpath("%s/%s" % (entry["homestart"], entry["home"]))
            full_name = "%s %s" % (entry["uservname"], entry["usernname"])
            full_name = "%s %s" % (entry["usertitan"], full_name.strip())
            full_name = full_name.strip()
            if len(full_name) == 0:
                full_name = entry["login"]
            pbn.append((entry["login"], "%s:%s:%d:%d:%s:%s:%s" % (entry["login"], entry["password"], entry["uid"], entry["gid"], full_name, home, entry["shell"])))
            pbu.append(("%d" % (entry["uid"]), "%s:%s:%d:%d:%s:%s:%s" % (entry["login"], entry["password"], entry["uid"], entry["gid"], full_name, home, entry["shell"])))
        ext_keys["passwd.byuid"] = pbu
        ext_keys["passwd.byname"] = pbn
        # home-exports
        self.dc.execute("SELECT d.name, cs.value, dc.device_config_idx, cs.name AS csname FROM device d, new_config c, device_config dc, config_str cs, device_type dt WHERE d.device_type=dt.device_type_idx AND dt.identifier='H' AND cs.new_config=c.new_config_idx AND dc.new_config=c.new_config_idx AND dc.device=d.device_idx AND (cs.name='homeexport' OR cs.name='options') ORDER BY d.name")
        home_exp_dict = {}
        for entry in self.dc.fetchall():
            home_exp_dict.setdefault(entry["device_config_idx"], {"name"       : entry["name"],
                                                                  "options"    : "",
                                                                  "homeexport" : ""})[entry["csname"]] = entry["value"]
        valid_home_keys = [x for x in home_exp_dict.keys() if home_exp_dict[x]["homeexport"]]
        if valid_home_keys:
            self.dc.execute("SELECT u.login, g.homestart, u.home, u.export FROM user u, ggroup g WHERE u.ggroup=g.ggroup_idx AND (%s)" % (" OR ".join(["u.export=%d" % (x) for x in valid_home_keys])))
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
                        mysql_tools.device_log_entry(self.dc,
                                                     global_config["SERVER_IDX"],
                                                     global_config["LOG_SOURCE_IDX"],
                                                     0,
                                                     global_config["LOG_STATUS"]["e"]["log_status_idx"],
                                                     "refuse to create automont-map for / (homedir-export)")
        # scratch-exports
        self.dc.execute("SELECT d.name, cs.value, dc.device_config_idx, cs.name AS csname FROM device d, new_config c, config_str cs, device_config dc, device_type dt WHERE d.device_type=dt.device_type_idx AND " + \
                               "dt.identifier='H' AND cs.new_config=c.new_config_idx AND dc.new_config=c.new_config_idx AND dc.device=d.device_idx AND (cs.name='scratchexport' OR cs.name='options') ORDER BY d.name")
        scratch_exp_dict = {}
        for entry in self.dc.fetchall():
            scratch_exp_dict.setdefault(entry["device_config_idx"], {"name"          : entry["name"],
                                                                     "options"       :"",
                                                                     "scratchexport" : ""})[entry["csname"]] = entry["value"]
        valid_scratch_keys = [x for x in scratch_exp_dict.keys() if scratch_exp_dict[x]["scratchexport"]]
        if valid_scratch_keys:
            self.dc.execute("SELECT u.login, g.scratchstart, u.scratch, u.export_scr FROM user u, ggroup g WHERE u.ggroup=g.ggroup_idx AND (%s)" % (" OR ".join(["u.export_scr=%d" % (x) for x in valid_scratch_keys])))
            for e2 in self.dc.fetchall():
                if e2["scratchstart"]:
                    scratchstart = e2["scratchstart"].replace("/", "").strip()
                    entry = scratch_exp_dict[e2["export_scr"]]
                    if scratchstart:
                        scratchstart = "auto.%s" % (scratchstart)
                        if not ext_keys.has_key(scratchstart):
                            ext_keys[scratchstart] = []
                            auto_master.append((e2["scratchstart"], scratchstart))
                        ext_keys[scratchstart].append((e2["scratch"], "%s %s:%s/%s" % (entry["options"], entry["name"], cs_tools.hostname_expand(entry["name"], entry["scratchexport"]), e2["login"])))
                    else:
                        mysql_tools.device_log_entry(self.dc,
                                                     global_config["SERVER_IDX"],
                                                     global_config["LOG_SOURCE_IDX"],
                                                     0,
                                                     global_config["LOG_STATUS"]["e"]["log_status_idx"],
                                                     "refuse to create automont-map for / (scratch-export)")
        ext_keys["auto.master"] = auto_master
        # get yp-name
        self.dc.execute("SELECT cs.value, d.name FROM new_config c INNER JOIN config_str cs INNER JOIN device_config dc INNER JOIN device d INNER JOIN device_group dg LEFT JOIN " + \
                               "device d2 ON d2.device_idx=dg.device WHERE d.device_group=dg.device_group_idx AND (dc.device=d2.device_idx OR dc.device=d.device_idx) AND " + \
                               "dc.new_config=c.new_config_idx AND c.name='yp_server' AND cs.name='domainname' AND cs.new_config=c.new_config_idx")
        # check for correct hostname is missing (shit)
        nis_name = self.dc.fetchone()["value"]
        # parse /etc/services for the services.byname and services.byservicename maps
        array = [x.strip() for x in file("/etc/services", "r").read().split("\n") if not re.match("^(#.*|\s*)$", x)]
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
        ext_keys["ypservers"] = [(global_config["SERVER_FULL_NAME"],
                                  global_config["SERVER_FULL_NAME"])]
        temp_map_dir = "/var/yp/%s" % (temp_map_dir)
        if not os.path.isdir("/var/yp"):
            cur_inst.srv_com["result"].attrib.update({
                "reply" : "error no /var/yp directory",
                "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
        else:
            if os.path.isdir(temp_map_dir):
                shutil.rmtree(temp_map_dir, 1)
            if not os.path.isdir(temp_map_dir):
                os.mkdir(temp_map_dir)
            map_keys = sorted(ext_keys.keys())
            for mapname in map_keys:
                self.log("creating map named %s ..." % (mapname))
                map_name = "%s/%s" % (temp_map_dir, mapname)
                #print map_name
                gdbf = gdbm.open(map_name, "n", 0600)
                gdbf["YP_INPUT_NAME"] = "%s.mysql" % (mapname)
                gdbf["YP_OUTPUT_NAME"] = map_name
                gdbf["YP_MASTER_NAME"] = global_config["SERVER_FULL_NAME"]
                gdbf["YP_LAST_MODIFIED"] = str(int(time.time()))
                for key, value in ext_keys[mapname]:
                    gdbf[key] = value
                    #print "%s --> %s" % (a, b)
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
                cur_inst.srv_com["result"].attrib.update({
                    "reply" : "error wrote %d yp-maps, reloading gave :'%s'" % (num_maps, cout),
                    "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
            else:
                cur_inst.srv_com["result"].attrib.update({
                    "reply" : "ok wrote %d yp-maps and successfully reloaded configuration" % (num_maps),
                    "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)})

if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
