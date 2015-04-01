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
import cs_tools

class modify_user_dir(cs_base_class.server_com):
    def __init__(self):
        cs_base_class.server_com.__init__(self)
        self.set_needed_option_keys(["username", "export_type", "old_dir_name"])
    def call_it(self, opt_dict, call_params):
        def change_own(arg, dir_name, entries):
            uid, gid = arg
            for entry in entries:
                fname = "%s/%s" % (dir_name, entry)
                os.chown(fname, uid, gid)
        user, export_type, old_dir_name = (opt_dict["username"],
                                           opt_dict["export_type"],
                                           opt_dict["old_dir_name"])
        if export_type == "home":
            sql_str, sql_tuple = ("SELECT u.login, u.uid, u.home, cs.value, g.gid FROM user u, ggroup g, device_config dc, new_config c, config_str cs WHERE cs.new_config=c.new_config_idx AND cs.name='homeexport' AND u.login=%s AND u.ggroup=g.ggroup_idx AND u.export=dc.device_config_idx AND dc.new_config=c.new_config_idx", (user))
        elif export_type == "scratch":
            sql_str, sql_tuple = ("SELECT u.login, u.uid, u.home, cs.value, g.gid FROM user u, ggroup g, device_config dc, new_config c, config_str cs WHERE cs.new_config=c.new_config_idx AND cs.name='scratchexport' AND u.login=%s AND u.ggroup=g.ggroup_idx AND u.export_scr=dc.device_config_idx AND dc.new_config=c.new_config_idx", user)
        else:
            sql_str, ret_str = (None, "error unknown export_type '%s'" % (export_type))
        if sql_str:
            call_params.dc.execute(sql_str, sql_tuple)
            if call_params.dc.rowcount == 1:
                u_stuff = call_params.dc.fetchone()
                new_dir_start = os.path.normpath("%s/%s" % (cs_tools.hostname_expand(call_params.get_l_config()["SERVER_SHORT_NAME"], u_stuff["value"]),
                                                            u_stuff[export_type]))
                old_dir_start = os.path.normpath("%s/%s" % (cs_tools.hostname_expand(call_params.get_l_config()["SERVER_SHORT_NAME"], u_stuff["value"]),
                                                            old_dir_name))
                if os.path.isdir(old_dir_start):
                    if os.path.exists(new_dir_start):
                        ret_str = "error new %sdir '%s' already exists" % (export_type, new_dir_start)
                    else:
                        try:
                            os.rename(old_dir_start, new_dir_start)
                        except:
                            ret_str = "error %s : %s" % (str(sys.exc_info()[0]),
                                                         str(sys.exc_info()[1]))
                        else:
                            ret_str = "ok moved %s to %s" % (old_dir_start, new_dir_start)
                else:
                    ret_str = "error old %sdir '%s' not found" % (export_type, old_dir_start)
            else:
                ret_str = "error cannot find user '%s'" % (user)
        return ret_str
            
class modify_user_uid_gid(cs_base_class.server_com):
    def __init__(self):
        cs_base_class.server_com.__init__(self)
        self.set_blocking_mode(0)
        self.set_needed_option_keys(["username", "export_type"])
        self.set_is_restartable(1)
    def call_it(self, opt_dict, call_params):
        def change_own(arg, act_dir, entries):
            uid, gid = arg
            for entry in entries:
                fname = "%s/%s" % (act_dir, entry)
                os.chown(fname, uid, gid)
        user, export_type = (opt_dict["username"],
                             opt_dict["export_type"])
        if export_type == "home":
            sql_str, sql_tuple = ("SELECT u.login, u.uid, u.home, cs.value, g.gid FROM user u, ggroup g, device_config dc, new_config c, config_str cs WHERE cs.new_config=c.new_config_idx AND cs.name='homeexport' AND u.login=%s AND u.ggroup=g.ggroup_idx AND u.export=dc.device_config_idx AND dc.new_config=c.new_config_idx", (user))
        elif export_type == "scratch":
            sql_str, sql_tuple = ("SELECT u.login, u.uid, u.home, cs.value, g.gid FROM user u, ggroup g, device_config dc, new_config c, config_str cs WHERE cs.new_config=c.new_config_idx AND cs.name='scratchexport' AND u.login=%s AND u.ggroup=g.ggroup_idx AND u.export_scr=dc.device_config_idx AND dc.new_config=c.new_config_idx", user)
        else:
            sql_str, ret_str = (None, "error unknown export_type '%s'" % (export_type))
        if sql_str:
            call_params.dc.execute(sql_str, sql_tuple)
            if call_params.dc.rowcount == 1:
                os.umask(0022)
                u_stuff = call_params.dc.fetchone()
                dir_start = os.path.normpath("%s/%s" % (cs_tools.hostname_expand(call_params.get_l_config()["SERVER_SHORT_NAME"], u_stuff["value"]),
                                                        u_stuff[export_type]))
                uid, gid = (u_stuff["uid"], u_stuff["gid"])
                if os.path.isdir(dir_start):
                    os.chown(dir_start, uid, gid)
                    os.path.walk(dir_start, change_own, (uid, gid))
                    ret_str = "ok changed uid to %d and gid to %d" % (uid, gid)
                else:
                    ret_str = "error %sdir '%s' not found" % (export_type, dir_start)
            else:
                ret_str = "error cannot find user '%s'" % (user)
        return ret_str

if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
    
