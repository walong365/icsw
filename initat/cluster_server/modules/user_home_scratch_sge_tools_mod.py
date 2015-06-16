#!/usr/bin/python -Ot
#
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

from django.db.models import Q
from initat.cluster.backbone.models import user, config_str
from initat.cluster_server.config import global_config
import commands
import cs_base_class
import cs_tools
import os
from initat.tools import process_tools
from initat.tools import server_command
import shutil
import tempfile


class create_user_home(cs_base_class.server_com):
    class Meta:
        needed_option_keys = ["username"]

    def _call(self, cur_inst):
        def change_own(arg, act_dir, entries):
            uid, gid = arg
            for entry in entries:
                fname = os.path.join(act_dir, entry)
                os.chown(fname, uid, gid)
        # to entries possible:
        # homeexport: used for automounter maps
        # createdir : used for creation
        # when using NFSv4 createdir can be different from homeexport (homeexport is for instance relative to nfsv4root)
        try:
            cur_user = user.objects.select_related("group").get(Q(login=cur_inst.option_dict["username"]))  # @UndefinedVariable
        except user.DoesNotExist:  # @UndefinedVariable
            cur_inst.srv_com.set_result(
                "cannot find user '{}'".format(cur_inst.option_dict["username"]),
                server_command.SRV_REPLY_STATE_ERROR
            )
        else:
            # get homedir and / or createdir of export entry
            hd_exports = config_str.objects.filter(
                (
                    Q(name="homeexport") | Q(name="createdir")
                ) & Q(config__device_config=cur_user.export)
            )
            if cur_user.only_webfrontend:
                cur_inst.srv_com.set_result(
                    "user '{}' is only valid for webfrontend".format(cur_inst.option_dict["username"]),
                    server_command.SRV_REPLY_STATE_ERROR
                )
            elif not cur_user.active:
                cur_inst.srv_com.set_result(
                    "user '{}' is not active".format(cur_inst.option_dict["username"]),
                    server_command.SRV_REPLY_STATE_ERROR
                )
            elif not len(hd_exports):
                cur_inst.srv_com.set_result(
                    "no createdir / homeexport found for user '{}'".format(cur_inst.option_dict["username"]),
                    server_command.SRV_REPLY_STATE_ERROR
                )
            else:
                exp_dict = dict([(hd_export.name, hd_export.value) for hd_export in hd_exports])
                self.log("export dict: {}".format(", ".join(["{}='{}'".format(key, value) for key, value in exp_dict.iteritems()])))
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
                self.log(
                    "homestart is '{}', skel_dir '{}', uid/gid is {:d}/{:d}".format(
                        home_start,
                        skel_dir,
                        uid,
                        gid,
                    )
                )
                if not os.path.isdir(home_start):
                    try:
                        os.makedirs(home_start)
                    except:
                        pass
                if os.path.isdir(home_start):
                    full_home = os.path.normpath(
                        os.path.join(home_start, cur_user.home or cur_user.login)
                    )
                    create_hdir, hdir_exists = (True, False)
                    if os.path.exists(full_home):
                        create_hdir, hdir_exists, hdir_err_str = (
                            False,
                            True,
                            "path {} already exists".format(full_home))
                        cur_user.home_dir_created = False
                        cur_user.save(update_fields=["home_dir_created"])
                    else:
                        if skel_dir:
                            try:
                                shutil.copytree(skel_dir, full_home, 1)
                            except:
                                create_hdir, hdir_exists, hdir_err_str = (
                                    False,
                                    False,
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
                                create_hdir, hdir_exists, hdir_err_str = (
                                    False,
                                    False,
                                    "cannot create home-directory %s: %s" % (
                                        full_home,
                                        process_tools.get_except_info()
                                    )
                                )
                            else:
                                pass
                    if create_hdir:
                        os.chown(full_home, uid, gid)
                        os.path.walk(full_home, change_own, (uid, gid))
                        try:
                            os.chmod(full_home, 0755)
                        except:
                            pass
                        hdir_exists = True
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
                        cur_inst.srv_com.set_result(
                            "created homedirectory '{}' for user '{}'".format(
                                full_home,
                                unicode(user)
                            )
                        )
                    else:
                        if hdir_exists:
                            cur_user.home_dir_created = True
                            cur_user.save()
                            cur_inst.srv_com.set_result(
                                hdir_err_str,
                            )
                        else:
                            cur_inst.srv_com.set_result(
                                hdir_err_str,
                                server_command.SRV_REPLY_STATE_ERROR
                            )
                else:
                    cur_inst.srv_com.set_result(
                        "no homestart directory '{}'".format(home_start),
                        server_command.SRV_REPLY_STATE_ERROR
                    )


class create_sge_user(cs_base_class.server_com):
    class Meta:
        needed_configs = ["sge_server"]
        needed_option_keys = ["username"]

    def _call(self, cur_inst):
        # get fairshare-value
        fshare = 30
        f_str = "default fairshare-value"
        f_str += " %s" % (str(fshare))
        user = cur_inst.option_dict["username"]
        try:
            sge_root = file("/etc/sge_root", "r").readline().strip()
            sge_cell = file("/etc/sge_cell", "r").readline().strip()
            _sge_stat, sge_arch = commands.getstatusoutput("/%s/util/arch" % (sge_root))
        except:
            cur_inst.srv_com["result"].attrib.update({
                "state": "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                "reply": "error sge-/etc/files not found"
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
                cur_inst.srv_com.set_result(
                    "error cannot create SGE user {}: '{}'".format(user, cout),
                    server_command.SRV_REPLY_STATE_ERROR
                )
            else:
                cur_inst.srv_com.set_result(
                    "ok created user {} for SGE ({})".format(user, f_str),
                )
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
            _sge_stat, sge_arch = commands.getstatusoutput("/%s/util/arch" % (sge_root))
        except:
            cur_inst.srv_com["result"].attrib.update({
                "state": "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                "reply": "error sge-/etc/files not found"
            })
        else:
            os.environ["SGE_ROOT"] = sge_root
            os.environ["SGE_CELL"] = sge_cell
            cstat, cout = commands.getstatusoutput("/%s/bin/%s/qconf -duser %s" % (sge_root, sge_arch, user))
            if cstat:
                cur_inst.srv_com["result"].attrib.update({
                    "state": "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                    "reply": "error cannot delete SGE user %s: '%s'" % (user, cout)
                })
            else:
                cur_inst.srv_com["result"].attrib.update({
                    "state": "%d" % (server_command.SRV_REPLY_STATE_OK),
                    "reply": "ok deleted user %s for SGE" % (user)
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
            _sge_stat, sge_arch = commands.getstatusoutput("/%s/util/arch" % (sge_root))
        except:
            cur_inst.srv_com.set_result(
                "error sge-/etc/files not found",
                server_command.SRV_REPLY_STATE_ERROR,
            )
        else:
            cstat, cout = commands.getstatusoutput("/%s/bin/%s/qconf -suser %s" % (sge_root, sge_arch, old_user))
            if cstat:
                cur_inst.srv_com.set_result(
                    "error cannot fetch info for SGE user %s: %s" % (old_user, cout),
                    server_command.SRV_REPLY_STATE_ERROR,
                )
            else:
                user_dict = {
                    a: b for a, b in [
                        _line.strip().split(None, 1) for _line in cout.strip().split("\n")
                    ] if a != "name"
                }
                user_dict["name"] = user
                tmp_name = tempfile.mktemp("sge")
                file(tmp_name, "w").write("\n".join(["%s %s" % (k, v) for k, v in user_dict.iteritems()]))
                os.environ["SGE_ROOT"] = sge_root
                os.environ["SGE_CELL"] = sge_cell
                commands.getstatusoutput("/%s/bin/%s/qconf -duser %s" % (sge_root, sge_arch, old_user))
                cstat, cout = commands.getstatusoutput("/%s/bin/%s/qconf -Auser %s" % (sge_root, sge_arch, tmp_name))
                if cstat:
                    cur_inst.srv_com["result"].attrib.update({
                        "state": "%d" % (server_command.SRV_REPLY_STATE_ERROR),
                        "reply": "error cannot create modified SGE user %s: '%s'" % (user, cout)
                    })
                else:
                    cur_inst.srv_com["result"].attrib.update({
                        "state": "%d" % (server_command.SRV_REPLY_STATE_OK),
                        "reply": "ok modified SGE user %s" % (user)
                    })
                try:
                    os.unlink(tmp_name)
                except:
                    pass
