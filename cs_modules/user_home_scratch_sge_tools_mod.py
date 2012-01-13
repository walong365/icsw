#!/usr/bin/python -Ot
#
# Copyright (C) 2007 Andreas Lang-Nevyjel
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

class create_user_home(cs_base_class.server_com):
    def __init__(self):
        cs_base_class.server_com.__init__(self)
        #self.set_config_type(["e"])
        self.set_needed_option_keys(["username"])
    def call_it(self, opt_dict, call_params):
        def change_own(arg, act_dir, entries):
            uid, gid = arg
            for entry in entries:
                fname = "%s/%s" % (act_dir, entry)
                os.chown(fname, uid, gid)
        user = opt_dict["username"]
        call_params.dc.execute("SELECT u.login, u.uid, u.home, cs.value, g.gid FROM user u, ggroup g, device_config dc, new_config c, config_str cs WHERE cs.new_config=c.new_config_idx AND cs.name='homeexport' AND u.login='%s' AND u.ggroup=g.ggroup_idx AND u.export=dc.device_config_idx AND dc.new_config=c.new_config_idx" % (user))
        if call_params.dc.rowcount == 1:
            os.umask(0022)
            dset = call_params.dc.fetchone()
            # check for skeleton directory
            skel_dir = None
            for skel_dir in ["/usr/local/cluster/skel", "/etc/skel"]:
                if os.path.isdir(skel_dir):
                    skel_dir = skel_dir
                    break
            home_start = cs_tools.hostname_expand(call_params.get_l_config()["SERVER_SHORT_NAME"], dset["value"])
            uid = dset["uid"]
            gid = dset["gid"]
            if not os.path.isdir(home_start):
                try:
                    os.makedirs(home_start)
                except:
                    pass
            if os.path.isdir(home_start):
                full_home = os.path.normpath("%s/%s" % (home_start, dset["home"]))
                hdir_ok = 1
                if os.path.exists(full_home):
                    hdir_ok, hdir_err_str = (0, "path %s already exists" % (full_home))
                else:
                    if skel_dir:
                        try:
                            shutil.copytree(skel_dir, full_home, 1)
                        except:
                            exc_info = sys.exc_info()
                            hdir_ok, hdir_err_str = (0, "cannot create home-directory %s from skeleton '%s': %s, %s" % (full_home, skel_dir, str(exc_info[0]), str(exc_info[1])))
                        else:
                            pass
                    else:
                        try:
                            os.mkdir(full_home)
                        except:
                            exc_info = sys.exc_info()
                            hdir_ok, hdir_err_str = (0, "cannot create home-directory %s: %s, %s" % (full_home, str(exc_info[0]), str(exc_info[1])))
                        else:
                            pass
                if hdir_ok:
                    os.chown(full_home, uid, gid)
                    os.path.walk(full_home, change_own, (uid, gid))
                    ret_str = "ok created homedirectory '%s' for user '%s" % (full_home, user)
                    try:
                        os.chmod(full_home, 0755)
                    except:
                        pass
                    post_create_user_command = "/etc/sysconfig/post_create_user"
                    if os.path.isfile(post_create_user_command):
                        pcun_args = "0 %d %d %s %s" % (uid, gid, user, full_home)
                        stat, out = commands.getstatusoutput("%s %s" % (post_create_user_command, pcun_args))
                        call_params.log("Calling '%s %s' gave (%d): %s" % (post_create_user_command, pcun_args, stat, out))
                else:
                    ret_str = "error %s" % (hdir_err_str)
            else:
                ret_str = "error no homestart directory '%s'" % (home_start)
        else:
            ret_str = "error cannot find user '%s'" % (user)
        return ret_str

class delete_user_home(cs_base_class.server_com):
    def __init__(self):
        cs_base_class.server_com.__init__(self)
        #self.set_config_type(["e"])
        self.set_needed_option_keys(["username"])
    def call_it(self, opt_dict, call_params):
        user = opt_dict["username"]
        call_params.dc.execute("SELECT u.login, u.uid, u.home, cs.value, g.gid FROM user u, ggroup g, device_config dc, new_config c, config_str cs WHERE cs.new_config=c.new_config_idx AND cs.name='homeexport' AND u.login='%s' AND u.ggroup=g.ggroup_idx AND u.export=dc.device_config_idx AND dc.new_config=c.new_config_idx" % (user))
        if call_params.dc.rowcount == 1:
            dset = call_params.dc.fetchone()
            full_home = os.path.normpath("%s/%s" % (cs_tools.hostname_expand(call_params.get_l_config()["SERVER_SHORT_NAME"], dset["value"]), dset["home"]))
            if os.path.isdir(full_home):
                shutil.rmtree(full_home, 1)
                ret_str = "ok delete homedirectory '%s' for user '%s'" % (full_home, user)
            else:
                ret_str = "error no homedirecotry '%s' for user '%s'" % (full_home, user)
        else:
            ret_str = "error cannot find user '%s'" % (user)
        return ret_str

class create_user_scratch(cs_base_class.server_com):
    def __init__(self):
        cs_base_class.server_com.__init__(self)
        #self.set_config_type(["e"])
        self.set_needed_option_keys(["username"])
    def call_it(self, opt_dict, call_params):
        def change_own(arg, dir, entries):
            uid, gid = arg
            for entry in entries:
                fname = "%s/%s" % (dir, entry)
                os.chown(fname, uid, gid)
        user = opt_dict["username"]
        call_params.dc.execute("SELECT u.login, u.uid, u.scratch, cs.value, g.gid FROM user u, ggroup g, device_config dc, new_config c, config_str cs WHERE cs.new_config=c.new_config_idx AND cs.name='scratchexport' AND u.login='%s' AND u.ggroup=g.ggroup_idx AND u.export_scr = dc.device_config_idx AND dc.new_config=c.new_config_idx" % (user))
        if call_params.dc.rowcount == 1:
            dset = call_params.dc.fetchone()
            scratch_start = cs_tools.hostname_expand(call_params.get_l_config()["SERVER_SHORT_NAME"], dset["value"])
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
                    ret_str = "ok create scratchdirectory '%s' for user '%s" % (full_scratch, user)
                else:
                    ret_str = "error %s" % (hdir_err_str)
            else:
                ret_str = "error no scratchstart directory '%s'" % (scratch_start)
        else:
            ret_str = "error cannot find user '%s'" % (user)
        return ret_str

class delete_user_scratch(cs_base_class.server_com):
    def __init__(self):
        cs_base_class.server_com.__init__(self)
        #self.set_config_type(["e"])
        self.set_needed_option_keys(["username"])
    def call_it(self, opt_dict, call_params):
        user = opt_dict["username"]
        call_params.dc.execute("SELECT u.login, u.uid, u.home, cs.value, g.gid FROM user u, ggroup g, device_config dc, new_config c, config_str cs WHERE cs.new_config=c.new_config_idx AND cs.name='scratchexport' AND u.login='%s' AND u.ggroup=g.ggroup_idx AND u.export_scr=dc.device_config_idx AND dc.new_config=c.new_config_idx" % (user))
        if call_params.dc.rowcount == 1:
            dset = call_params.dc.fetchone()
            full_scratch = os.path.normpath("%s/%s" % (cs_tools.hostname_expand(call_params.get_l_config()["SERVER_SHORT_NAME"], dset["value"]), dset["home"]))
            if os.path.isdir(full_scratch):
                shutil.rmtree(full_scratch, 1)
                ret_str = "ok delete scratchdirectory '%s' for user '%s'" % (full_scratch, user)
            else:
                ret_str = "error no scratchdirecotry '%s' for user '%s'" % (full_scratch, user)
        else:
            ret_str = "error cannot find user '%s'" % (user)
        return ret_str

class create_all_user_scratches(cs_base_class.server_com):
    def __init__(self):
        cs_base_class.server_com.__init__(self)
        #self.set_config_type(["e"])
    def call_it(self, opt_dict, call_params):
        def change_own(arg, dir, entries):
            uid, gid = arg
            for entry in entries:
                fname = "%s/%s" % (dir, entry)
                os.chown(fname, uid, gid)
        call_params.dc.execute("SELECT u.login, u.uid, u.scratch, cs.value, g.gid FROM user u, ggroup g, device_config dc, new_config c, config_str cs WHERE cs.new_config=c.new_config_idx AND cs.name='scratchexport' AND u.ggroup=g.ggroup_idx AND u.export_scr = dc.device_config_idx AND dc.device=%d AND dc.new_config=c.new_config_idx ORDER BY u.login" % (call_params.get_server_idx()))
        if call_params.dc.rowcount:
            error_dict, ok_list = ({}, [])
            for dset in call_params.dc.fetchall():
                scratch_start = cs_tools.hostname_expand(call_params.get_l_config()["SERVER_SHORT_NAME"], dset["value"])
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
            ret_str = "ok"
        else:
            ret_str = "error no users scratch-directories on this server"
        return ret_str

class create_sge_user(cs_base_class.server_com):
    def __init__(self):
        cs_base_class.server_com.__init__(self)
        self.set_config(["sge_server"])
        self.set_needed_option_keys(["username"])
    def call_it(self, opt_dict, call_params):
        # get fairshare-value
        call_params.dc.execute("SELECT ci.value FROM new_config c, config_int ci, device_config dc WHERE ci.new_config=c.new_config_idx AND ci.name='fairshare' AND dc.new_config=c.new_config_idx AND dc.device=%d AND c.name='sge_server'" % (call_params.get_server_idx()))
        if call_params.dc.rowcount == 1:
            fshare = call_params.dc.fetchone()["value"]
            f_str = "fairshare-value"
        else:
            fshare = 30
            f_str = "default fairshare-value"
        f_str += " %s" % (str(fshare))
        user = opt_dict["username"]
        try:
            sge_root = file("/etc/sge_root", "r").readline().strip()
            sge_cell = file("/etc/sge_cell", "r").readline().strip()
            stat, sge_arch = commands.getstatusoutput("/%s/util/arch" % (sge_root))
        except:
            ret_str = "error sge-/etc/files not found"
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
                ret_str = "error cannot create SGE user %s: '%s'" % (user, cout)
            else:
                ret_str = "ok created user %s for SGE (%s)" % (user, f_str)
            try:
                os.unlink(tmp_name)
            except:
                pass
        return ret_str

class delete_sge_user(cs_base_class.server_com):
    def __init__(self):
        cs_base_class.server_com.__init__(self)
        self.set_needed_option_keys(["username"])
    def call_it(self, opt_dict, call_params):
        user = opt_dict["username"]
        try:
            sge_root = file("/etc/sge_root", "r").readline().strip()
            sge_cell = file("/etc/sge_cell", "r").readline().strip()
            stat, sge_arch = commands.getstatusoutput("/%s/util/arch" % (sge_root))
        except:
            ret_str = "error sge-/etc/files not found"
        else:
            os.environ["SGE_ROOT"] = sge_root
            os.environ["SGE_CELL"] = sge_cell
            cstat, cout = commands.getstatusoutput("/%s/bin/%s/qconf -duser %s" % (sge_root, sge_arch, user))
            if cstat:
                ret_str = "error cannot delete SGE user %s: '%s'" % (user, cout)
            else:
                ret_str = "ok deleted user %s for SGE" % (user)
        return ret_str

class rename_sge_user(cs_base_class.server_com):
    def __init__(self):
        cs_base_class.server_com.__init__(self)
        self.set_config(["sge_server"])
        self.set_needed_option_keys(["username", "old_username"])
    def call_it(self, opt_dict, call_params):
        user, old_user = (opt_dict["username"],
                          opt_dict["old_username"])
        try:
            sge_root = file("/etc/sge_root", "r").readline().strip()
            sge_cell = file("/etc/sge_cell", "r").readline().strip()
            stat, sge_arch = commands.getstatusoutput("/%s/util/arch" % (sge_root))
        except:
            ret_str = "error sge-/etc/files not found"
        else:
            if os.path.isfile("%s/%s/common/product_mode" % (sge_root, sge_cell)):
                sge60 = 0
            else:
                sge60 = 1
            cstat, cout = commands.getstatusoutput("/%s/bin/%s/qconf -suser %s" % (sge_root, sge_arch, old_user))
            if cstat:
                ret_str = "error cannot fetch info for SGE user %s: %s" % (old_user, cout)
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
                    ret_str = "error cannot create modified SGE user %s: '%s'" % (user, cout)
                else:
                    ret_str = "ok modified SGE user %s" % (user)
                try:
                    os.unlink(tmp_name)
                except:
                    pass
        return ret_str

class create_user_quota(cs_base_class.server_com):
    def __init__(self):
        cs_base_class.server_com.__init__(self)
        self.set_config(["quota"])
        self.set_needed_option_keys(["username"])
    def call_it(self, opt_dict, call_params):
        call_params.dc.execute("SELECT cs.value FROM new_config c, config_str cs, device_config dc WHERE cs.new_config=c.new_config_idx AND cs.name='dummyuser' AND dc.new_config=c.new_config_idx AND dc.device=%d AND c.name='quota'" % (call_params.get_server_idx()))
        if call_params.dc.rowcount == 1:
            quota_prot = call_params.dc.fetchone()["value"]
            user = opt_dict["username"]
            cstat, cout = commands.getstatusoutput("/usr/sbin/edquota -p %s %s" % (quota_prot, user))
            if cstat:
                ret_str = "error cannot duplicate quotas for user %s from proto %s: '%s'" % (user, quota_prot, cout)
            else:
                ret_str = "ok duplicated quotas for user %s from proto %s" % (user, quota_prot)
        elif call_params.dc.rowcount:
            ret_str = "error more than one quota-config found (%d)" % (call_params.dc.rowcount)
        else:
            ret_str = "error quotas not configured"
        return ret_str

if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
    
