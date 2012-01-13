#!/usr/bin/python -Ot
#
# Copyright (C) 2007,2008,2009,2010 Andreas Lang-Nevyjel
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
""" tools for modifying LDAP servers """

import sys
import cs_base_class
import logging_tools
import os
import cs_tools
import time
import commands
import pprint
import pkg_resources
import process_tools
import hashlib
import crypt
pkg_resources.require("python-LDAP")
try:
    import ldap
except ImportError:
    ldap = None
else:
    import ldap.modlist

""" possible smb.conf:

[global]
        workgroup = WORKGROUP
        passdb backend = ldapsam
        encrypt passwords = true
        idmap backend =  ldap:"ldap://localhost"
        ldap suffix = dc=local
        ldap admin dn = cn=admin,dc=local
        bind interfaces only = no
        ldap ssl= off
        ldap user suffix = ou=People
        map to guest = Bad User
        include = /etc/samba/dhcp.conf
        logon path = \\%L\profiles\.msprofile
        logon home = \\%L\%U\.9xprofile
        logon drive = P:
        usershare allow guests = Yes
[homes]
        comment = Home Directories
        valid users = %S, %D%w%S
        browseable = No
        read only = No
        inherit acls = Yes
        path = /tmp/%S
"""

class init_ldap_config(cs_base_class.server_com):
    def __init__(self):
        cs_base_class.server_com.__init__(self)
        self.set_config(["ldap_server"])
    def _add_entry(self, ld, dn, in_dict):
        try:
            ld.add_s(dn, ldap.modlist.addModlist(in_dict))
        except ldap.LDAPError:
            success, err_str = (False, self._get_ldap_err_str())
        else:
            success, err_str = (True, "")
        return success, err_str
    def _delete_entry(self, ld, dn):
        try:
            ld.delete_s(dn)
        except ldap.LDAPError:
            success, err_str = (False, self._get_ldap_err_str(dn))
        else:
            success, err_str = (True, "")
        return success, err_str
    def call_command(self, command, *args):
        success, result = (False, [])
        bin_com = process_tools.find_file(command)
        if bin_com:
            c_stat, c_out = commands.getstatusoutput("%s %s" % (bin_com, " " .join(args)))
            if c_stat:
                result = ["%d" % (c_stat)] + c_out.split("\n")
            else:
                success = True
                result = c_out.split("\n")
        return success, result
    def _get_ldap_err_str(self):
        err_dict = sys.exc_info()[1].args[0]
        return " / ".join(["%s: %s" % (x, err_dict[x]) for x in ["info", "desc"] if err_dict.has_key(x)])
    def call_it(self, opt_dict, call_params):
        # fetch configs
        call_params.dc.execute("SELECT cs.value, cs.name FROM new_config c INNER JOIN config_str cs INNER JOIN device_config dc INNER JOIN device d INNER JOIN device_group dg LEFT JOIN " + \
                               "device d2 ON d2.device_idx=dg.device WHERE d.device_group=dg.device_group_idx AND (dc.device=d2.device_idx OR dc.device=d.device_idx) AND dc.new_config=c.new_config_idx AND c.name='ldap_server' AND cs.new_config=c.new_config_idx")
        par_dict = dict([(x["name"], x["value"]) for x in call_params.dc.fetchall()])
        errors = []
        needed_keys = ["base_dn", "admin_cn", "root_passwd"]
        missed_keys = [x for x in needed_keys if not par_dict.has_key(x)]
        if len(missed_keys):
            errors.append("%s missing: %s" % (logging_tools.get_plural("config_key", len(missed_keys)),
                                              ", ".join(missed_keys)))
        else:
            full_dn = par_dict["base_dn"]
            call_params.log("will modify ldap_tree below %s" % (full_dn))
            try:
                ld_read = ldap.initialize("ldap://localhost")
                ld_read.simple_bind_s("", "")
            except ldap.LDAPError:
                ldap_err_str = self._get_ldap_err_str()
                call_params.log("cannot initialize read_cursor: %s" % (ldap_err_str),
                                logging_tools.LOG_LEVEL_ERROR)
                errors.append(ldap_err_str)
                ld_read = None
            else:
                try:
                    ld_write = ldap.initialize("ldap://localhost")
                    ld_write.simple_bind_s("cn=%s,%s" % (par_dict["admin_cn"],
                                                         par_dict["base_dn"]),
                                           par_dict["root_passwd"])
                except ldap.LDAPError:
                    ldap_err_str = self._get_ldap_err_str()
                    call_params.log("cannot initialize write_cursor: %s" % (ldap_err_str),
                                    logging_tools.LOG_LEVEL_ERROR)
                    errors.append(ldap_err_str)
                    ld_write = None
                    ld_read.unbind_s()
            if ld_read and ld_write:
                root_ok = True
                # init root
                try:
                    ld_read.search_s(par_dict["base_dn"], ldap.SCOPE_SUBTREE, "objectclass=*")
                except ldap.NO_SUCH_OBJECT:
                    ok, err_str = self._add_entry(ld_write,
                                                  par_dict["base_dn"],
                                                  {"objectClass" : ["top", "dcObject", "organization"],
                                                   "dc"          : [par_dict["base_dn"].split(",")[0].split("=")[1]],
                                                   "o"           : [par_dict["base_dn"].split(",")[0].split("=")[1]]})
                    if ok:
                        call_params.log("added root-entry at %s" % (par_dict["base_dn"]))
                    else:
                        root_ok = False
                        errors.append(err_str)
                        call_params.log("cannot add root entry %s: %s" % (par_dict["base_dn"], err_str),
                                        logging_tools.LOG_LEVEL_ERROR)
                if root_ok:
                    if par_dict.has_key("sub_ou"):
                        act_sub_ou = par_dict["sub_ou"]
                        call_params.log("using %s as default OU" % (par_dict["sub_ou"]))
                        sub_ou_str = ",".join(["ou=%s" % (sub_str) for sub_str in act_sub_ou.split(",")])
                    else:
                        act_sub_ou = ""
                        call_params.log("using no default OU")
                        sub_ou_str = ""
                    # init main groups
                    needed_dns = []
                    if act_sub_ou:
                        needed_dns.append("%s,%s" % (sub_ou_str, full_dn))
                        # rewrite full_dn
                        full_dn = "%s,%s" % (sub_ou_str, full_dn)
                    needed_dns.extend(["ou=%s,%s" % (entry, full_dn) for entry in ["People", "Group", "Automount"]])
                    for dn, attrs in ld_read.search_s(full_dn, ldap.SCOPE_SUBTREE, "objectclass=organizationalUnit"):
                        if dn in needed_dns:
                            needed_dns.remove(dn)
                    if needed_dns:
                        call_params.log("%s missing: %s" % (logging_tools.get_plural("dn", len(needed_dns)),
                                                            ", ".join(needed_dns)))
                        for needed_dn in needed_dns:
                            short_dn = needed_dn.split(",")[0].split("=")[1]
                            ok, err_str = self._add_entry(ld_write,
                                                          needed_dn,
                                                          {"objectClass" : ["top", "organizationalUnit"],
                                                           "ou"          : [short_dn],
                                                           "description" : "added by cluster-server on %s" % (call_params.get_l_config()["SERVER_SHORT_NAME"])})
                            if ok:
                                call_params.log("added entry %s" % (needed_dn))
                            else:
                                errors.append(err_str)
                                call_params.log("cannot add entry %s: %s" % (needed_dn, err_str),
                                                logging_tools.LOG_LEVEL_ERROR)
                    if "sambadomain" in par_dict:
                        samba_dn = "sambaDomainName=%s,%s" % (par_dict["sambadomain"], full_dn)
                        for dn, attrs in ld_read.search_s(full_dn, ldap.SCOPE_SUBTREE, "objectclass=sambaDomain"):
                            ok, err_str = self._delete_entry(ld_write,
                                                             dn)
                            call_params.log("removed previous sambaDomain '%s'" % (dn))
                        call_params.log("init SAMBA-structure (domainname is '%s', dn is '%s')" % (par_dict["sambadomain"],
                                                                                                   samba_dn))
                        local_sid = self.call_command("net", "getlocalsid")[1][0].split()[-1]
                        call_params.log("local SID is %s" % (local_sid))
                        ok, err_str = self._add_entry(ld_write,
                                                      samba_dn,
                                                      {"objectClass" : ["sambaDomain"],
                                                       #"structuralObjectClass" : "sambaDomain",
                                                       "sambaDomainName"               : par_dict["sambadomain"],
                                                       "sambaSID"                      : local_sid,
                                                       "sambaAlgorithmicRidBase"       : "1000",
                                                       "sambaMinPwdLength"             : "5",
                                                       "sambaPwdHistoryLength"         : "0",
                                                       "sambaLogonToChgPwd"            : "0",
                                                       "sambaMaxPwdAge"                : "-1",
                                                       "sambaMinPwdAge"                : "0",
                                                       "sambaLockoutDuration"          : "30",
                                                       "sambaLockoutObservationWindow" : "30",
                                                       "sambaLockoutThreshold"         : "0",
                                                       "sambaForceLogoff"              : "-1",
                                                       "sambaRefuseMachinePwdChange"   : "0",
                                                       })
                        if ok:
                            call_params.log("added entry %s" % (samba_dn))
                        else:
                            errors.append(err_str)
                            call_params.log("cannot add entry %s: %s" % (samba_dn, err_str),
                                            logging_tools.LOG_LEVEL_ERROR)
                ld_read.unbind_s()
                ld_write.unbind_s()
        if errors:
            return "error %s" % ("; ".join(errors))
        else:
            return "ok checked"

class sync_ldap_config(cs_base_class.server_com):
    def __init__(self):
        cs_base_class.server_com.__init__(self)
        self.set_config(["ldap_server"])
    def _add_entry(self, ld, dn, in_dict):
        try:
            ld.add_s(dn, ldap.modlist.addModlist(in_dict))
        except ldap.LDAPError:
            success, err_str = (False, self._get_ldap_err_str(dn))
        else:
            success, err_str = (True, "")
        return success, err_str
    def _modify_entry(self, ld, dn, change_list):
        try:
            ld.modify_s(dn, change_list)
        except ldap.LDAPError:
            success, err_str = (False, self._get_ldap_err_str(dn))
        else:
            success, err_str = (True, "")
        return success, err_str
    def _delete_entry(self, ld, dn):
        try:
            ld.delete_s(dn)
        except ldap.LDAPError:
            success, err_str = (False, self._get_ldap_err_str(dn))
        else:
            success, err_str = (True, "")
        return success, err_str
    def _get_ldap_err_str(self, dn):
        err_dict = sys.exc_info()[1].args[0]
        return "%s (%s)" % (dn, " / ".join(["%s: %s" % (x, err_dict[x]) for x in ["info", "desc"] if err_dict.get(x, None)]))
    def call_it(self, opt_dict, call_params):
        # fetch configs
        call_params.dc.execute("SELECT cs.value, cs.name FROM new_config c INNER JOIN config_str cs INNER JOIN device_config dc INNER JOIN device d INNER JOIN device_group dg LEFT JOIN " + \
                               "device d2 ON d2.device_idx=dg.device WHERE d.device_group=dg.device_group_idx AND (dc.device=d2.device_idx OR dc.device=d.device_idx) AND dc.new_config=c.new_config_idx AND c.name='ldap_server' AND cs.new_config=c.new_config_idx")
        par_dict = dict([(x["name"], x["value"]) for x in call_params.dc.fetchall()])
        errors = []
        needed_keys = ["base_dn", "admin_cn", "root_passwd"]
        missed_keys = [x for x in needed_keys if not par_dict.has_key(x)]
        if len(missed_keys):
            errors.append("%s missing: %s" % (logging_tools.get_plural("config_key", len(missed_keys)),
                                              ", ".join(missed_keys)))
        else:
            try:
                ld_read = ldap.initialize("ldap://localhost")
                ld_read.simple_bind_s("", "")
            except ldap.LDAPError:
                ldap_err_str = self._get_ldap_err_str("read_access")
                call_params.log("cannot initialize read_cursor: %s" % (ldap_err_str),
                                logging_tools.LOG_LEVEL_ERROR)
                errors.append(ldap_err_str)
                ld_read = None
            else:
                try:
                    ld_write = ldap.initialize("ldap://localhost")
                    ld_write.simple_bind_s("cn=%s,%s" % (par_dict["admin_cn"],
                                                         par_dict["base_dn"]),
                                           par_dict["root_passwd"])
                except ldap.LDAPError:
                    ldap_err_str = self._get_ldap_err_str("write_access")
                    call_params.log("cannot initialize write_cursor: %s" % (ldap_err_str),
                                    logging_tools.LOG_LEVEL_ERROR)
                    errors.append(ldap_err_str)
                    ld_write = None
                    ld_read.unbind_s()
            if ld_read and ld_write:
                ldap_version = call_params.get_g_config()["LDAP_SCHEMATA_VERSION"]
                call_params.log("using LDAP_SCHEMATA_VERSION %d" % (ldap_version))
                # fetch user / group info
                call_params.dc.execute("SELECT g.* FROM ggroup g")
                all_groups = dict([(x["ggroup_idx"], x) for x in call_params.dc.fetchall()])
                call_params.dc.execute("SELECT u.* FROM user u")
                all_users = dict([(x["user_idx"], x) for x in call_params.dc.fetchall() if x["ggroup"] in all_groups.keys()])
                call_params.dc.execute("SELECT d.name, udl.user FROM device d, user_device_login udl WHERE udl.device=d.device_idx")
                devlog_dict = {}
                for db_rec in call_params.dc.fetchall():
                    devlog_dict.setdefault(db_rec["user"], []).append(db_rec["name"])
                # secondary groups
                call_params.dc.execute("SELECT * FROM user_ggroup")
                for db_rec in call_params.dc.fetchall():
                    if all_users.has_key(db_rec["user"]) and all_groups.has_key(db_rec["ggroup"]):
                        all_users[db_rec["user"]].setdefault("secondary_groups", []).append(db_rec["ggroup"])
                # luts
                group_lut = dict([(x["ggroupname"], x["ggroup_idx"]) for x in all_groups.itervalues()])
                user_lut = dict([(x["login"], x["user_idx"]) for x in all_users.itervalues()])
                # get sub_ou
                if par_dict.has_key("sub_ou"):
                    act_sub_ou = par_dict["sub_ou"]
                    call_params.log("using %s as default OU" % (par_dict["sub_ou"]))
                    sub_ou_str = "%s," % (",".join(["ou=%s" % (sub_str) for sub_str in act_sub_ou.split(",")]))
                else:
                    act_sub_ou = ""
                    call_params.log("using no default OU")
                    sub_ou_str = ""
                if "sambadomain" in par_dict:
                    dom_node = ld_read.search_s("%s%s" % (sub_ou_str,
                                                          par_dict["base_dn"]), ldap.SCOPE_SUBTREE, "objectclass=sambaDomain")[0]
                    samba_sid = dom_node[1]["sambaSID"][0]
                    call_params.log("sambaSID is '%s' (domain %s)" % (samba_sid,
                                                                      par_dict["sambadomain"]))
                # build ldap structures
                for g_idx, g_stuff in all_groups.iteritems():
                    g_stuff["dn"] = "cn=%s,ou=Group,%s%s" % (g_stuff["ggroupname"],
                                                             sub_ou_str,
                                                             par_dict["base_dn"])
                    primary_users   = [x["login"] for x in all_users.itervalues() if x["active"] and x["ggroup"] == g_idx]
                    secondary_users = [x["login"] for x in all_users.itervalues() if x["active"] and g_idx in x.get("secondary_groups", []) and x["login"] not in primary_users]
                    group_classes = ["posixGroup", "top", "clusterGroup"]
                    g_stuff["attrs"] = {"objectClass" : group_classes,
                                        "cn"          : [g_stuff["ggroupname"]],
                                        "gidNumber"   : [str(g_stuff["gid"])],
                                        "memberUid"   : primary_users + secondary_users,
                                        "description" : ["Responsible person: %s %s %s (%s)" % (g_stuff["resptitan"],
                                                                                                g_stuff["respvname"],
                                                                                                g_stuff["respnname"],
                                                                                                g_stuff["respemail"])]}
                    if "sambadomain" in par_dict:
                        g_stuff["attrs"]["objectClass"].append("sambaGroupMapping")
                        g_stuff["attrs"]["sambaGroupType"] = "2"
                        g_stuff["attrs"]["sambaSID"] = "%s-%d" % (samba_sid,
                                                                  g_stuff["gid"] * 2 + 1)
                for u_idx, u_stuff in all_users.iteritems():
                    u_stuff["dn"] = "uid=%s,ou=People,%s%s" % (u_stuff["login"],
                                                               sub_ou_str,
                                                               par_dict["base_dn"])
                    g_stuff = all_groups[u_stuff["ggroup"]]
                    # ldap.conf filter: pam_filter      &(objectclass=posixAccount)(|(host=\*)(host=zephises))
                    u_stuff["attrs"] = {"objectClass"      : ["account", "posixAccount", "shadowAccount", "top", "clusterAccount"],
                                        "cn"               : [u_stuff["login"]],
                                        "userid"           : [u_stuff["login"]],
                                        "gecos"            : ["%s %s %s (%s)" % (u_stuff["usertitan"],
                                                                                 u_stuff["uservname"],
                                                                                 u_stuff["usernname"],
                                                                                 u_stuff["useremail"])],
                                        "gidNumber"        : [str(g_stuff["gid"])],
                                        "uidNumber"        : [str(u_stuff["uid"])],
                                        "userPassword"     : ["{crypt}%s" % (u_stuff["password"])],
                                        "homeDirectory"    : [os.path.normpath("%s/%s" % (g_stuff["homestart"], u_stuff["home"]))],
                                        "loginShell"       : [u_stuff["shell"]],
                                        "shadowLastChange" : ["11192"],
                                        "shadowMin"        : ["-1"],
                                        "shadowMax"        : ["99999"],
                                        "shadowWarning"    : ["7"],
                                        "shadowInactive"   : ["-1"],
                                        "shadowExpire"     : ["-1"],
                                        "shadowFlag"       : ["1345383808"],
                                        "host"             : devlog_dict.get(u_stuff["user_idx"], ["*"]),
                                        "description"      : [u_stuff["usercom"] or "no description"]}
                    if "sambadomain" in par_dict:
                        u_stuff["attrs"]["objectClass"].append("sambaSamAccount")
                        u_stuff["attrs"]["sambaSID"] = "%s-%d" % (samba_sid,
                                                                  u_stuff["uid"] * 2)
                        u_stuff["attrs"]["sambaAcctFlags"] = "[U          ]"
                        u_stuff["attrs"]["sambaPwdLastSet"] = "%d" % (int(time.time()))
                        u_stuff["attrs"]["sambaNTPassword"] = u_stuff["nt_password"]
                        u_stuff["attrs"]["sambaLMPassword"] = u_stuff["lm_password"]
                # fetch all groups from ldap
                groups_ok, groups_to_change, groups_to_remove = ([], [], [])
                for dn, attrs in ld_read.search_s(par_dict["base_dn"], ldap.SCOPE_SUBTREE, "(&(objectClass=posixGroup)(objectClass=clusterGroup))"):
                    dn_parts = ldap.explode_dn(dn, True)
                    if dn.endswith(",ou=Group,%s%s" % (sub_ou_str,
                                                       par_dict["base_dn"])):
                        group_name = dn_parts[0]
                        if group_name in group_lut.keys():
                            group_struct = all_groups[group_lut[group_name]]
                            if group_struct["active"]:
                                group_struct["orig_attrs"] = attrs
                                group_struct["change_list"] = ldap.modlist.modifyModlist(group_struct["orig_attrs"], group_struct["attrs"])
                                if group_struct["change_list"]:
                                    # changing group
                                    call_params.log("changing group %s (content differs)" % (group_name))
                                    groups_to_change.append(group_name)
                                else:
                                    groups_ok.append(group_name)
                            else:
                                # remove group (no longer active)
                                call_params.log("removing group %s (not active)" % (group_name))
                                groups_to_remove.append(group_name)
                        else:
                            # remove group (not found in db)
                            call_params.log("removing group %s (not found in db)" % (group_name))
                            groups_to_remove.append(group_name)
                    else:
                        call_params.log("ignoring posixGroup with dn %s" % (dn),
                                        logging_tools.LOG_LEVEL_WARN)
                # add groups
                groups_to_add = [x for x in group_lut.keys() if x not in groups_ok and x not in groups_to_change and x not in groups_to_remove]
                for group_to_add in groups_to_add:
                    group_struct = all_groups[group_lut[group_to_add]]
                    if group_struct["active"]:
                        ok, err_str = self._add_entry(ld_write,
                                                      group_struct["dn"],
                                                      group_struct["attrs"])
                        if ok:
                            call_params.log("added group %s" % (group_to_add))
                        else:
                            errors.append(err_str)
                            call_params.log("cannot add group %s: %s" % (group_to_add, err_str),
                                            logging_tools.LOG_LEVEL_ERROR)
                    else:
                        call_params.log("cannot add group %s: not active" % (group_to_add),
                                        logging_tools.LOG_LEVEL_WARN)
                # modify groups
                for group_to_change in groups_to_change:
                    group_struct = all_groups[group_lut[group_to_change]]
                    ok, err_str = self._modify_entry(ld_write,
                                                     group_struct["dn"],
                                                     group_struct["change_list"])
                    if ok:
                        call_params.log("modified group %s" % (group_to_change))
                    else:
                        errors.append(err_str)
                        call_params.log("cannot modify group %s: %s" % (group_to_change, err_str),
                                        logging_tools.LOG_LEVEL_ERROR)
                # remove groups
                for group_to_remove in groups_to_remove:
                    ok, err_str = self._delete_entry(ld_write,
                                                     "cn=%s,ou=Group,%s%s" % (group_to_remove,
                                                                              sub_ou_str,
                                                                              par_dict["base_dn"]))
                    
                    if ok:
                        call_params.log("deleted group %s" % (group_to_remove))
                    else:
                        errors.append(err_str)
                        call_params.log("cannot delete group %s: %s" % (group_to_remove, err_str),
                                        logging_tools.LOG_LEVEL_ERROR)
                # fetch all users from ldap
                users_ok, users_to_change, users_to_remove = ([], [], [])
                for dn, attrs in ld_write.search_s(par_dict["base_dn"], ldap.SCOPE_SUBTREE, "(&(objectclass=posixAccount)(objectClass=clusterAccount))"):
                    dn_parts = ldap.explode_dn(dn, True)
                    if dn.endswith(",ou=People,%s%s" % (sub_ou_str,
                                                        par_dict["base_dn"])):
                        user_name = dn_parts[0]
                        if user_name in user_lut.keys():
                            user_struct = all_users[user_lut[user_name]]
                            if user_struct["active"] and all_groups[user_struct["ggroup"]]["active"] and all_groups[user_struct["ggroup"]]["homestart"]:
                                # debian fixes
                                if attrs.has_key("uid") and not attrs.has_key("userid"):
                                    attrs["userid"] = attrs["uid"]
                                    del attrs["uid"]
                                user_struct["orig_attrs"] = attrs
                                user_struct["change_list"] = ldap.modlist.modifyModlist(user_struct["orig_attrs"], user_struct["attrs"], [sub_key for sub_key in user_struct["attrs"].keys() if sub_key.startswith("shadow") or sub_key.lower() in (["userpassword"] if ("do_not_sync_password" in par_dict) else [])])
                                if user_struct["change_list"]:
                                    # changing user
                                    call_params.log("changing user %s (content differs)" % (user_name))
                                    users_to_change.append(user_name)
                                else:
                                    users_ok.append(user_name)
                            else:
                                # remove user (no longer active)
                                call_params.log("removing user %s (not active or group not active or no group_homestart)" % (user_name))
                                users_to_remove.append(user_name)
                        else:
                            # remove user (not found in db)
                            call_params.log("removing user %s (not found in db)" % (user_name))
                            users_to_remove.append(user_name)
                    else:
                        call_params.log("ignoring posixUser with dn %s" % (dn),
                                        logging_tools.LOG_LEVEL_WARN)
                # add users
                users_to_add = [x for x in user_lut.keys() if x not in users_ok and x not in users_to_change and x not in users_to_remove]
                for user_to_add in users_to_add:
                    user_struct = all_users[user_lut[user_to_add]]
                    if user_struct["active"] and all_groups[user_struct["ggroup"]]["active"]:
                        ok, err_str = self._add_entry(ld_write,
                                                      user_struct["dn"],
                                                      user_struct["attrs"])
                        if ok:
                            call_params.log("added user %s" % (user_to_add))
                        else:
                            errors.append(err_str)
                            call_params.log("cannot add user %s: %s" % (user_to_add, err_str),
                                            logging_tools.LOG_LEVEL_ERROR)
                    else:
                        call_params.log("cannot add user %s: not active" % (user_to_add),
                                        logging_tools.LOG_LEVEL_WARN)
                # modify users
                for user_to_change in users_to_change:
                    user_struct = all_users[user_lut[user_to_change]]
                    ok, err_str = self._modify_entry(ld_write,
                                                     user_struct["dn"],
                                                     user_struct["change_list"])
                    if ok:
                        call_params.log("modified user %s" % (user_to_change))
                    else:
                        errors.append(err_str)
                        call_params.log("cannot modify user %s: %s" % (user_to_change, err_str),
                                        logging_tools.LOG_LEVEL_ERROR)
                # remove users
                for user_to_remove in users_to_remove:
                    ok, err_str = self._delete_entry(ld_write,
                                                     "uid=%s,ou=People,%s%s" % (user_to_remove,
                                                                                sub_ou_str,
                                                                                par_dict["base_dn"]))
                    
                    if ok:
                        call_params.log("deleted user %s" % (user_to_remove))
                    else:
                        errors.append(err_str)
                        call_params.log("cannot delete user %s: %s" % (user_to_remove, err_str),
                                        logging_tools.LOG_LEVEL_ERROR)
                # automounter
                call_params.dc.execute("SELECT d.name, cs.name AS csname, cs.value, cs.new_config FROM device d INNER JOIN new_config c INNER JOIN device_config dc INNER JOIN config_str cs INNER JOIN " + \
                                       "device_group dg INNER JOIN device_type dt LEFT JOIN device d2 ON d2.device_idx=dg.device WHERE d.device_type=dt.device_type_idx AND dt.identifier='H' AND d.device_group=dg.device_group_idx " + \
                                       "AND cs.new_config=c.new_config_idx AND dc.new_config=c.new_config_idx AND (dc.device=d.device_idx OR dc.device=d2.device_idx) AND (cs.name='export' OR cs.name='import' OR cs.name='options' or cs.name='node_postfix') ORDER BY d.name, cs.config")
                export_dict = {}
                ei_dict = {}
                for entry in call_params.dc.fetchall():
                    dev_name, act_idx = (entry["name"], entry["new_config"])
                    # generate a small dict for each export-entry (per device)
                    ei_dict.setdefault(dev_name, {}).setdefault(act_idx, {"export"       : None,
                                                                          "import"       : None,
                                                                          "node_postfix" : "",
                                                                          "options"      : "-soft"})[entry["csname"]] = cs_tools.hostname_expand(entry["name"], entry["value"])
                for mach, aeid_d in ei_dict.iteritems():
                    for aeid_idx, aeid in aeid_d.iteritems():
                        if aeid["export"] and aeid["import"]:
                            aeid["import"] = cs_tools.hostname_expand(mach, aeid["import"])
                            export_dict[aeid["import"]] = (aeid["options"], "%s%s:%s" % (mach, aeid["node_postfix"], aeid["export"]))
                # home-exports
                call_params.dc.execute("SELECT d.name, cs.value, dc.device_config_idx, cs.name AS csname FROM device d, new_config c, device_config dc, config_str cs, device_type dt WHERE d.device_type=dt.device_type_idx AND " + \
                                       "dt.identifier='H' AND cs.new_config=c.new_config_idx AND dc.new_config=c.new_config_idx AND dc.device=d.device_idx AND (cs.name='homeexport' OR cs.name='options' OR cs.name='node_postfix') ORDER BY d.name")
                home_exp_dict = {}
                for entry in call_params.dc.fetchall():
                    home_exp_dict.setdefault(entry["device_config_idx"], {"name"         : entry["name"],
                                                                          "options"      : "",
                                                                          "node_postfix" : "",
                                                                          "homeexport"   : ""})[entry["csname"]] = entry["value"]
                # remove invalid exports (with no homeexport-entry)
                invalid_home_keys = [x for x in home_exp_dict.keys() if not home_exp_dict[x]["homeexport"]]
                for ihk in invalid_home_keys:
                    del home_exp_dict[ihk]
                # scratch-exports
                call_params.dc.execute("SELECT d.name, cs.value, dc.device_config_idx, cs.name AS csname FROM device d, new_config c, config_str cs, device_config dc, device_type dt WHERE d.device_type=dt.device_type_idx AND " + \
                                       "dt.identifier='H' AND cs.new_config=c.new_config_idx AND dc.new_config=c.new_config_idx AND dc.device=d.device_idx AND (cs.name='scratchexport' OR cs.name='options' OR cs.name='node_postfix') ORDER BY d.name")
                scratch_exp_dict = {}
                for entry in call_params.dc.fetchall():
                    scratch_exp_dict.setdefault(entry["device_config_idx"], {"name"          : entry["name"],
                                                                             "options"       : "",
                                                                             "node_postfix"  : "",
                                                                             "scratchexport" : ""})[entry["csname"]] = entry["value"]
                # remove invalid exports (with no scratchexport-entry)
                invalid_scratch_keys = [x for x in scratch_exp_dict.keys() if not scratch_exp_dict[x]["scratchexport"]]
                for isk in invalid_scratch_keys:
                    del scratch_exp_dict[isk]
                for user_stuff in [x for x in all_users.values() if x["active"] and all_groups[x["ggroup"]]["active"]]:
                    group_stuff = all_groups[user_stuff["ggroup"]]
                    if user_stuff["export"] in home_exp_dict.keys():
                        home_stuff = home_exp_dict[user_stuff["export"]]
                        export_dict[os.path.normpath("%s/%s" % (group_stuff["homestart"], user_stuff["home"]))] = (home_stuff["options"], "%s%s:%s/%s" % (home_stuff["name"], home_stuff["node_postfix"], home_stuff["homeexport"], user_stuff["home"]))
                    if user_stuff["export_scr"] in scratch_exp_dict.keys():
                        scratch_stuff = scratch_exp_dict[user_stuff["export_scr"]]
                        export_dict[os.path.normpath("%s/%s" % (group_stuff["scratchstart"], user_stuff["scratch"]))] = (scratch_stuff["options"], "%s%s:%s/%s" % (scratch_stuff["name"], scratch_stuff["node_postfix"], scratch_stuff["scratchexport"], user_stuff["export"]))
                #pprint.pprint(home_exp_dict)
                #pprint.pprint(scratch_exp_dict)
                # now we have all automount-maps in export_dict, form is mountpoint: (options, source)
                # build mountmaps
                # SUSE 10.1 mappings
                if ldap_version > 0:
                    master_object_class = ["top", "nisMap", "clusterAutomount"]
                    master_map_pfix     = "nisMapName"
                    mount_info_name     = "nisMapName"
                    mount_point_name    = "nisMapEntry"
                    mount_point_class   = ["top", "nisObject", "clusterAutomount"]
                # defaults ?
                else:
                    master_object_class = ["top", "automountMap", "clusterAutomount"]
                    master_map_pfix     = "ou"
                    mount_info_name     = "automountInformation"
                    mount_point_name    = "automountInformation"
                    mount_point_class   = ["top", "automount", "clusterAutomount"]
                master_map_dn = "%s=auto.master" % (master_map_pfix)
                auto_maps = []
                # remove mount_points which would overwrite '/'
                error_keys = sorted([key for key in export_dict.keys() if os.path.dirname(key) == "/"])
                if error_keys:
                    call_params.log("found %s: %s; ignoring them" % (logging_tools.get_plural("wrong key", len(error_keys)),
                                                                     ", ".join(error_keys)),
                                    logging_tools.LOG_LEVEL_ERROR)
                mount_points = dict([(os.path.dirname(x), 0) for x in export_dict.keys() if x not in error_keys]).keys()
                if mount_points:
                    map_lut = dict([(k, k.replace("/", "").replace(".", "_")) for k in mount_points])
                    # automounter_map
                    auto_maps.append({"dn"       : "%s,ou=Automount,%s%s" % (master_map_dn,
                                                                             sub_ou_str,
                                                                             par_dict["base_dn"]),
                                      "attrs"    : {"objectClass"   : master_object_class,
                                                    master_map_pfix : ["auto.master"]}})
                    if ldap_version > 0:
                        ldap_add_list = [("nisMapName", "auto.master")]
                        ldap_add_list_1 = [("nisMapName", "map_name")]
                    else:
                        ldap_add_list = []
                        ldap_add_list_1 = []
                    for mount_point in mount_points:
                        map_name = "auto.%s" % (map_lut[mount_point])
                        auto_maps.append({"dn"       : "%s=%s,ou=Automount,%s%s" % (master_map_pfix,
                                                                                    map_name,
                                                                                    sub_ou_str,
                                                                                    par_dict["base_dn"]),
                                          "attrs"    : {"objectClass"   : master_object_class,
                                                        master_map_pfix : [map_name]}})
                        auto_maps.append({"dn"    : "cn=%s,%s,ou=Automount,%s%s" % (mount_point,
                                                                                    master_map_dn,
                                                                                    sub_ou_str,
                                                                                    par_dict["base_dn"]),
                                          "attrs" : dict([("objectClass"   , mount_point_class),
                                                          ("cn"            , [mount_point]),
                                                          (mount_point_name, ["ldap://%s/%s=%s,ou=Automount,%s%s" % (self.server_device_name, master_map_pfix, map_name, sub_ou_str, par_dict["base_dn"])]),
                                                          ("description"   , ["automounter map created by cluster-server on %s" % (self.server_device_name)])] + ldap_add_list)})
                        sub_keys = [k for k, v in export_dict.iteritems() if k.startswith("%s/" % (mount_point))]
                        for sub_key in sub_keys:
                            sub_mount_point = os.path.basename(sub_key)
                            mount_opts, mount_src = export_dict[sub_key]
                            auto_maps.append({"dn"    : "cn=%s,%s=%s,ou=Automount,%s%s" % (sub_mount_point, master_map_pfix, map_name, sub_ou_str, par_dict["base_dn"]),
                                              "attrs" : dict([("objectClass"   , mount_point_class),
                                                              ("cn"            , [sub_mount_point]),
                                                              (mount_point_name, ["%s %s" % (mount_opts, mount_src)])] + ldap_add_list)})
                map_keys = [x["dn"] for x in auto_maps]
                auto_dict = dict([(x["dn"], x) for x in auto_maps])
                # fetch all maps from ldap
                maps_ok, maps_to_change, maps_to_remove = ([], [], [])
                for dn, attrs in ld_read.search_s(par_dict["base_dn"], ldap.SCOPE_SUBTREE, "(objectClass=clusterAutomount)"):
                    if dn in map_keys:
                        map_struct = auto_dict[dn]
                        map_struct["orig_attrs"] = attrs
                        map_struct["change_list"] = ldap.modlist.modifyModlist(map_struct["orig_attrs"], map_struct["attrs"])
                        if map_struct["change_list"]:
                            # changing map
                            call_params.log("changing map %s (content differs)" % (dn))
                            maps_to_change.append(dn)
                        else:
                            maps_ok.append(dn)
                    else:
                        # remove map (not found in db)
                        call_params.log("removing map %s (not found in db)" % (dn))
                        maps_to_remove.append(dn)
                # add maps
                maps_to_add = [x for x in map_keys if x not in maps_ok and x not in maps_to_change and x not in maps_to_remove]
                for map_to_add in maps_to_add:
                    map_struct = auto_dict[map_to_add]
                    ok, err_str = self._add_entry(ld_write,
                                                  map_struct["dn"],
                                                  map_struct["attrs"])
                    if ok:
                        call_params.log("added map %s" % (map_to_add))
                    else:
                        errors.append(err_str)
                        call_params.log("cannot add map %s: %s" % (map_to_add, err_str),
                                        logging_tools.LOG_LEVEL_ERROR)
                # modify maps
                for map_to_change in maps_to_change:
                    map_struct = auto_dict[map_to_change]
                    ok, err_str = self._modify_entry(ld_write,
                                                     map_struct["dn"],
                                                     map_struct["change_list"])
                    if ok:
                        call_params.log("modified map %s" % (map_to_change))
                    else:
                        errors.append(err_str)
                        call_params.log("cannot modify map %s: %s" % (map_to_change, err_str),
                                        logging_tools.LOG_LEVEL_ERROR)
                # remove maps
                maps_to_remove.reverse()
                for map_to_remove in maps_to_remove:
                    ok, err_str = self._delete_entry(ld_write,
                                                     map_to_remove)
                    
                    if ok:
                        call_params.log("deleted map %s" % (map_to_remove))
                    else:
                        errors.append(err_str)
                        call_params.log("cannot delete map %s: %s" % (map_to_remove, err_str),
                                        logging_tools.LOG_LEVEL_ERROR)
                #pprint.pprint(export_dict)
                ld_read.unbind_s()
                ld_write.unbind_s()
        if errors:
            return "error %s" % ("; ".join(errors))
        else:
            return "ok checked"

if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
    
