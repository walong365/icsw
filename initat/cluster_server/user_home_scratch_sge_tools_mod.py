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

import sys
import cs_base_class
import os
import commands
import cs_tools
import tempfile
import shutil
import server_command
import process_tools
from django.db.models import Q
from initat.cluster.backbone.models import user, group, config, device_config, config_str
from initat.cluster_server.config import global_config

class create_user_home(cs_base_class.server_com):
    class Meta:
        needed_option_keys = ["username"]
    def _call(self, cur_inst):
        def change_own(arg, act_dir, entries):
            uid, gid = arg
            for entry in entries:
                fname = "%s/%s" % (act_dir, entry)
                os.chown(fname, uid, gid)
        # to entries possible:
        # homeexport: used for automounter maps
        # createdir : used for creation
        # when using NFSv4 createdir can be different from homeexport (homeexport is for instance relative to nfsv4root)
        try:
            cur_user = user.objects.select_related("group").get(Q(login=cur_inst.option_dict["username"]))
        except user.DoesNotExist:
            cur_inst.srv_com["result"].attrib.update({
                "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                "reply" : "error cannot find user '%s'" % (cur_inst.option_dict["username"])
            })
        else:
            # get homedir and / or createdir of export entry
            hd_exports = config_str.objects.filter(
                (Q(name="homeexport") | Q(name="createdir")) &
                Q(config__device_config=cur_user.export))
            if not len(hd_exports):
                cur_inst.srv_com["result"].attrib.update({
                    "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                    "reply" : "no createdir / homeexport found for user '%s'" % (cur_inst.option_dict["username"])
                })
            else:
                exp_dict = dict([(hd_export.name, hd_export.value) for hd_export in hd_exports])
                self.log("export dict: %s" %  (", ".join(["%s='%s'" % (key, value) for key, value in exp_dict.iteritems()])))
                homestart = exp_dict.get("createdir", exp_dict["homeexport"])
                # check for skeleton directory
                skel_dir = None
                for skel_dir in ["opt/cluster/skel", "/etc/skel"]:
                    if os.path.isdir(skel_dir):
                        skel_dir = skel_dir
                        break
                # get export directory
                
                home_start = cs_tools.hostname_expand(
                    global_config["SERVER_SHORT_NAME"],
                    homestart,
                )
                uid, gid = (cur_user.uid, cur_user.group.gid)
                self.log("homestart is '%s', skel_dir '%s', uid/gid is %d/%d" % (
                    home_start,
                    skel_dir,
                    uid,
                    gid,
                ))
                if not os.path.isdir(home_start):
                    try:
                        os.makedirs(home_start)
                    except:
                        pass
                if os.path.isdir(home_start):
                    full_home = os.path.normpath("%s/%s" % (home_start, cur_user.home or cur_user.login))
                    hdir_ok = 1
                    if os.path.exists(full_home):
                        hdir_ok, hdir_err_str = (0, "path %s already exists" % (full_home))
                    else:
                        if skel_dir:
                            try:
                                shutil.copytree(skel_dir, full_home, 1)
                            except:
                                exc_info = sys.exc_info()
                                hdir_ok, hdir_err_str = (
                                    0,
                                    "cannot create home-directory %s from skeleton '%s': %s" % (
                                        full_home,
                                        skel_dir,
                                        process_tools.get_except_info()
                                    )
                                )
                            else:
                                pass
                        else:
                            try:
                                os.mkdir(full_home)
                            except:
                                exc_info = sys.exc_info()
                                hdir_ok, hdir_err_str = (
                                    0,
                                    "cannot create home-directory %s: %s" % (
                                        full_home,
                                        process_tools.get_except_info()
                                    )
                                )
                            else:
                                pass
                    if hdir_ok:
                        os.chown(full_home, uid, gid)
                        os.path.walk(full_home, change_own, (uid, gid))
                        try:
                            os.chmod(full_home, 0755)
                        except:
                            pass
                        post_create_user_command = "/etc/sysconfig/post_create_user"
                        if os.path.isfile(post_create_user_command):
                            pcun_args = "0 %d %d %s %s" % (uid, gid, user, full_home)
                            pc_stat, pc_out = commands.getstatusoutput("%s %s" % (post_create_user_command, pcun_args))
                            self.log("Calling '%s %s' gave (%d): %s" % (
                                post_create_user_command,
                                pcun_args,
                                pc_stat,
                                pc_out))
                        cur_user.home_dir_created = True
                        cur_user.save()
                        cur_inst.srv_com["result"].attrib.update({
                            "state" : "%d" % (server_command.SRV_REPLY_STATE_OK),
                            "reply" : "ok created homedirectory '%s' for user '%s" % (full_home, user)
                            })
                    else:
                        cur_inst.srv_com["result"].attrib.update({
                            "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                            "reply" : "error %s" % (hdir_err_str)
                            })
                else:
                    cur_inst.srv_com["result"].attrib.update({
                        "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                        "reply" : "error no homestart directory '%s'" % (home_start)
                    })

class delete_user_home(cs_base_class.server_com):
    class Meta:
        needed_option_keys = ["username"]
    def _call(self, cur_inst):
        user = cur_inst.option_dict["username"]
        self.dc.execute("SELECT u.login, u.uid, u.home, cs.value, g.gid FROM user u, ggroup g, device_config dc, new_config c, config_str cs WHERE cs.new_config=c.new_config_idx AND cs.name='homeexport' AND u.login='%s' AND u.ggroup=g.ggroup_idx AND u.export=dc.device_config_idx AND dc.new_config=c.new_config_idx" % (user))
        if self.dc.rowcount == 1:
            dset = self.dc.fetchone()
            full_home = os.path.normpath("%s/%s" % (cs_tools.hostname_expand(global_config["SERVER_SHORT_NAME"], dset["value"]), dset["home"]))
            if os.path.isdir(full_home):
                shutil.rmtree(full_home, 1)
                cur_inst.srv_com["result"].attrib.update({
                    "state" : "%d" % (server_command.SRV_REPLY_STATE_OK),
                    "reply" : "ok delete homedirectory '%s' for user '%s'" % (full_home, user)
                })
            else:
                cur_inst.srv_com["result"].attrib.update({
                    "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                    "reply" : "error no homedirecotry '%s' for user '%s'" % (full_home, user)
                })
        else:
            cur_inst.srv_com["result"].attrib.update({
                "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                "reply" : "error cannot find user '%s'" % (user)
            })

class create_user_scratch(cs_base_class.server_com):
    class Meta:
        needed_option_keys = ["username"]
    def _call(self, cur_inst):
        def change_own(arg, t_dir, entries):
            uid, gid = arg
            for entry in entries:
                fname = "%s/%s" % (t_dir, entry)
                os.chown(fname, uid, gid)
        user = cur_inst.option_dict["username"]
        self.dc.execute("SELECT u.login, u.uid, u.scratch, cs.value, g.gid FROM user u, ggroup g, device_config dc, new_config c, config_str cs WHERE cs.new_config=c.new_config_idx AND cs.name='scratchexport' AND u.login='%s' AND u.ggroup=g.ggroup_idx AND u.export_scr = dc.device_config_idx AND dc.new_config=c.new_config_idx" % (user))
        if self.dc.rowcount == 1:
            dset = self.dc.fetchone()
            scratch_start = cs_tools.hostname_expand(global_config["SERVER_SHORT_NAME"], dset["value"])
            uid = dset["uid"]
            gid = dset["gid"]
            if os.path.isdir(scratch_start):
                full_scratch = os.path.normpath("%s/%s" % (scratch_start, dset["scratch"]))
                hdir_ok = 1
                try:
                    os.mkdir(full_scratch)
                except:
                    hdir_ok = 0
                    hdir_err_str = "cannot create scratch-directory : %s" % (sys.exc_info()[0])
                else:
                    pass
                if hdir_ok:
                    os.chown(full_scratch, uid, gid)
                    os.path.walk(full_scratch, change_own, (uid, gid))
                    cur_inst.srv_com["result"].attrib.update({
                        "state" : "%d" % (server_command.SRV_REPLY_STATE_OK),
                        "reply" : "ok create scratchdirectory '%s' for user '%s" % (full_scratch, user)
                    })
                else:
                    cur_inst.srv_com["result"].attrib.update({
                        "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                        "reply" : "error %s" % (hdir_err_str)
                    })
            else:
                cur_inst.srv_com["result"].attrib.update({
                    "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                    "reply" : "error no scratchstart directory '%s'" % (scratch_start)
                })
        else:
            cur_inst.srv_com["result"].attrib.update({
                "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                "reply" : "error cannot find user '%s'" % (user)
            })

class delete_user_scratch(cs_base_class.server_com):
    class Meta:
        needed_option_keys = ["username"]
    def _call(self, cur_inst):
        user = cur_inst.option_dict["username"]
        self.dc.execute("SELECT u.login, u.uid, u.home, cs.value, g.gid FROM user u, ggroup g, device_config dc, new_config c, config_str cs WHERE cs.new_config=c.new_config_idx AND cs.name='scratchexport' AND u.login='%s' AND u.ggroup=g.ggroup_idx AND u.export_scr=dc.device_config_idx AND dc.new_config=c.new_config_idx" % (user))
        if self.dc.rowcount == 1:
            dset = self.dc.fetchone()
            full_scratch = os.path.normpath("%s/%s" % (cs_tools.hostname_expand(global_config["SERVER_SHORT_NAME"], dset["value"]), dset["home"]))
            if os.path.isdir(full_scratch):
                shutil.rmtree(full_scratch, 1)
                cur_inst.srv_com["result"].attrib.update({
                    "state" : "%d" % (server_command.SRV_REPLY_STATE_OK),
                    "reply" : "ok delete scratchdirectory '%s' for user '%s'" % (full_scratch, user)
                })
            else:
                cur_inst.srv_com["result"].attrib.update({
                    "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                    "reply" : "error no scratchdirecotry '%s' for user '%s'" % (full_scratch, user)
                })
        else:
            cur_inst.srv_com["result"].attrib.update({
                "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                "reply" : "error cannot find user '%s'" % (user)
            })

class create_all_user_scratches(cs_base_class.server_com):
    def _call(self, cur_inst):
        def change_own(arg, t_dir, entries):
            uid, gid = arg
            for entry in entries:
                fname = "%s/%s" % (t_dir, entry)
                os.chown(fname, uid, gid)
        self.dc.execute("SELECT u.login, u.uid, u.scratch, cs.value, g.gid FROM user u, ggroup g, device_config dc, new_config c, config_str cs WHERE cs.new_config=c.new_config_idx AND cs.name='scratchexport' AND u.ggroup=g.ggroup_idx AND u.export_scr = dc.device_config_idx AND dc.device=%d AND dc.new_config=c.new_config_idx ORDER BY u.login" % (global_config["SERVER_IDX"]))
        if self.dc.rowcount:
            error_dict, ok_list = ({}, [])
            for dset in self.dc.fetchall():
                scratch_start = cs_tools.hostname_expand(global_config["SERVER_SHORT_NAME"], dset["value"])
                uid = dset["uid"]
                gid = dset["gid"]
                if os.path.isdir(scratch_start):
                    full_scratch = os.path.normpath("%s/%s" % (scratch_start, dset["scratch"]))
                    try:
                        os.mkdir(full_scratch)
                    except:
                        error_dict.setdefault("cannot create scratch-directory", []).append(dset["login"])
                    else:
                        os.chown(full_scratch, uid, gid)
                        os.path.walk(full_scratch, change_own, (uid, gid))
                        ok_list.append(dset["login"])
                else:
                    error_dict.setdefault("error no scratchstart directory '%s'" % (scratch_start), []).append(dset["login"])
            cur_inst.srv_com["result"].attrib.update({
                "state" : "%d" % (server_command.SRV_REPLY_STATE_OK),
                "reply" : "ok created user scratches"
            })
        else:
            cur_inst.srv_com["result"].attrib.update({
                "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                "reply" : "error no users scratch-directories on this server"
            })

class create_sge_user(cs_base_class.server_com):
    class Meta:
        needed_configs = ["sge_server"]
        needed_option_keys = ["username"]
    def _call(self, cur_inst):
        # get fairshare-value
        self.dc.execute("SELECT ci.value FROM new_config c, config_int ci, device_config dc WHERE ci.new_config=c.new_config_idx AND ci.name='fairshare' AND dc.new_config=c.new_config_idx AND dc.device=%d AND c.name='sge_server'" % (global_config["SERVER_IDX"]))
        if self.dc.rowcount == 1:
            fshare = self.dc.fetchone()["value"]
            f_str = "fairshare-value"
        else:
            fshare = 30
            f_str = "default fairshare-value"
        f_str += " %s" % (str(fshare))
        user = cur_inst.option_dict["username"]
        try:
            sge_root = file("/etc/sge_root", "r").readline().strip()
            sge_cell = file("/etc/sge_cell", "r").readline().strip()
            sge_stat, sge_arch = commands.getstatusoutput("/%s/util/arch" % (sge_root))
        except:
            cur_inst.srv_com["result"].attrib.update({
                "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                "reply" : "error sge-/etc/files not found"
            })
        else:
            if os.path.isfile("%s/%s/common/product_mode" % (sge_root, sge_cell)):
                sge60 = 0
            else:
                sge60 = 1
            tmp_name = tempfile.mktemp("sge")
            tf = file(tmp_name, "w")
            tf.write("\n".join(["name %s" % (user), "oticket 0", "fshare %s" % (str(fshare)), "default_project defaultproject", ""]))
            if sge60:
                tf.write("delete_time 0\n")
            tf.close()
            os.environ["SGE_ROOT"] = sge_root
            os.environ["SGE_CELL"] = sge_cell
            cstat, cout = commands.getstatusoutput("/%s/bin/%s/qconf -Auser %s" % (sge_root, sge_arch, tmp_name))
            if cstat:
                cur_inst.srv_com["result"].attrib.update({
                    "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                    "reply" : "error cannot create SGE user %s: '%s'" % (user, cout)
                })
            else:
                cur_inst.srv_com["result"].attrib.update({
                    "state" : "%d" % (server_command.SRV_REPLY_STATE_OK),
                    "reply" : "ok created user %s for SGE (%s)" % (user, f_str)
                })
            try:
                os.unlink(tmp_name)
            except:
                pass

class delete_sge_user(cs_base_class.server_com):
    class Meta:
        needed_option_keys = ["username"]
    def _call(self, cur_inst):
        user = cur_inst.option_dict["username"]
        try:
            sge_root = file("/etc/sge_root", "r").readline().strip()
            sge_cell = file("/etc/sge_cell", "r").readline().strip()
            sge_stat, sge_arch = commands.getstatusoutput("/%s/util/arch" % (sge_root))
        except:
            cur_inst.srv_com["result"].attrib.update({
                "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                "reply" : "error sge-/etc/files not found"
            })
        else:
            os.environ["SGE_ROOT"] = sge_root
            os.environ["SGE_CELL"] = sge_cell
            cstat, cout = commands.getstatusoutput("/%s/bin/%s/qconf -duser %s" % (sge_root, sge_arch, user))
            if cstat:
                cur_inst.srv_com["result"].attrib.update({
                    "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                    "reply" : "error cannot delete SGE user %s: '%s'" % (user, cout)
                })
            else:
                cur_inst.srv_com["result"].attrib.update({
                    "state" : "%d" % (server_command.SRV_REPLY_STATE_OK),
                    "reply" : "ok deleted user %s for SGE" % (user)
                })

class rename_sge_user(cs_base_class.server_com):
    class Meta:
        needed_configs = ["sge_server"]
        needed_option_keys = ["username", "old_username"]
    def _call(self, cur_inst):
        user, old_user = (cur_inst.option_dict["username"],
                          cur_inst.option_dict["old_username"])
        try:
            sge_root = file("/etc/sge_root", "r").readline().strip()
            sge_cell = file("/etc/sge_cell", "r").readline().strip()
            sge_stat, sge_arch = commands.getstatusoutput("/%s/util/arch" % (sge_root))
        except:
            cur_inst.srv_com["result"].attrib.update({
                "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                "reply" : "error sge-/etc/files not found"
            })
        else:
            if os.path.isfile("%s/%s/common/product_mode" % (sge_root, sge_cell)):
                sge60 = False
            else:
                sge60 = True
            cstat, cout = commands.getstatusoutput("/%s/bin/%s/qconf -suser %s" % (sge_root, sge_arch, old_user))
            if cstat:
                cur_inst.srv_com["result"].attrib.update({
                    "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                    "reply" : "error cannot fetch info for SGE user %s: %s" % (old_user, cout)
                })
            else:
                user_dict = dict([(a, b) for a, b in [x.strip().split(None, 1) for x in cout.strip().split("\n")] if a != "name"])
                user_dict["name"] = user
                tmp_name = tempfile.mktemp("sge")
                tf = file(tmp_name, "w").write("\n".join(["%s %s" % (k, v) for k, v in user_dict.iteritems()]))
                os.environ["SGE_ROOT"] = sge_root
                os.environ["SGE_CELL"] = sge_cell
                commands.getstatusoutput("/%s/bin/%s/qconf -duser %s" % (sge_root, sge_arch, old_user))
                cstat, cout = commands.getstatusoutput("/%s/bin/%s/qconf -Auser %s" % (sge_root, sge_arch, tmp_name))
                if cstat:
                    cur_inst.srv_com["result"].attrib.update({
                        "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                        "reply" : "error cannot create modified SGE user %s: '%s'" % (user, cout)
                    })
                else:
                    cur_inst.srv_com["result"].attrib.update({
                        "state" : "%d" % (server_command.SRV_REPLY_STATE_OK),
                        "reply" : "ok modified SGE user %s" % (user)
                    })
                try:
                    os.unlink(tmp_name)
                except:
                    pass

class create_user_quota(cs_base_class.server_com):
    class Meta:
        needed_configs = ["quota"]
        needed_option_keys = ["username"]
    def _call(self, cur_inst):
        self.dc.execute("SELECT cs.value FROM new_config c, config_str cs, device_config dc WHERE cs.new_config=c.new_config_idx AND cs.name='dummyuser' AND dc.new_config=c.new_config_idx AND dc.device=%d AND c.name='quota'" % (global_config["SERVER_IDX"]))
        if self.dc.rowcount == 1:
            quota_prot = self.dc.fetchone()["value"]
            user = cur_inst.option_dict["username"]
            cstat, cout = commands.getstatusoutput("/usr/sbin/edquota -p %s %s" % (quota_prot, user))
            if cstat:
                cur_inst.srv_com["result"].attrib.update({
                    "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                    "reply" : "error cannot duplicate quotas for user %s from proto %s: '%s'" % (user, quota_prot, cout)
                })
            else:
                cur_inst.srv_com["result"].attrib.update({
                    "state" : "%d" % (server_command.SRV_REPLY_STATE_OK),
                    "reply" : "ok duplicated quotas for user %s from proto %s" % (user, quota_prot)
                })
        elif self.dc.rowcount:
            cur_inst.srv_com["result"].attrib.update({
                "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                "reply" : "error more than one quota-config found (%d)" % (self.dc.rowcount)
            })
        else:
            cur_inst.srv_com["result"].attrib.update({
                "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                "reply" : "error quotas not configured"
            })

if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
