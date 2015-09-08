# Copyright (C) 2007-2010,2012-2015 Andreas Lang-Nevyjel
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

import commands
import os
import re
import sys
import time

from django.db.models import Q
from initat.cluster.backbone.models import user, group, device_config, \
    config_str, home_export_list, config
from initat.cluster_server.config import global_config
import ldap  # @UnresolvedImport @UnusedImport
import ldap.modlist  # important, do not remove  @UnresolvedImport
from initat.tools import logging_tools, process_tools, server_command

import cs_base_class

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

For a good overview see http://www.server-world.info/en/note?os=CentOS_7&p=openldap

config old .config to new ldap.d base:
slaptest -f /etc/openldap/slapd.conf -F /etc/openldap/slapd.d

{0}config.ldif needs an access entry:

dn: olcDatabase={0}config
objectClass: olcDatabaseConfig
olcDatabase: {0}config
olcAccess: {0}to *  by dn.base="gidNumber=0+uidNumber=0,cn=peercred,cn=externa
 l,cn=auth" manage  by * none


adding cluster.ldif:

ldapadd -Y EXTERNAL -H ldapi:/// -D cn=config -f /tmp/cluster.ldif

## not correct : /cn\=config/cn\=schema/cn\=\{0\}cluster.ldif ##

ldapadd -Y EXTERNAL -H ldapi:/// -D cn=config -f /tmp/x

cluster.ldif
dn: cn=cluster,cn=schema,cn=config
objectClass: olcSchemaConfig
cn: cluster
olcObjectClasses: {0}( 1.3.6.4.1.1.2.0 NAME 'clusterGroup' DESC 'group was cre
 ated from cluster-server' SUP top AUXILIARY )
olcObjectClasses: {1}( 1.3.6.4.1.1.2.1 NAME 'clusterAccount' DESC 'account was
  created from cluster-server' SUP top AUXILIARY )
olcObjectClasses: {2}( 1.3.6.4.1.1.2.2 NAME 'clusterAutomount' DESC 'automount
  was created from cluster-server' SUP top AUXILIARY )

"""

"""
Centos:

/usr/libexec/openldap/create-certdb.sh
/usr/libexec/openldap/generate-server-cert.sh -h <HOSTNAME> -a <ALTNAMES>

Centos uses a MozNSS CA cert directory to store the server certificate. There
are two ways to extract a PEM certificate:

    Local:
        $ cp -rf /etc/openldap/certs /tmp/cert-dir
        $ certutil -L -d /tmp/cert-dir
        ...
        A_CERTIFICATE_NAME
        ...
        $ certutil -L -d /tmp/cert-dir -a -n "A_CERTIFICATE_NAME" > cert.crt

    Remote:
        $ openssl s_client -showcerts -connect ldap.example.com:636 > s_client.dump
        <CTRL-C>
        $ openssl x509 -in s_client.dump -out cert.crt

Testing LDAP TLS connections:

    $ LDAPTLS_CERT=/path/to/cert.crt ldapsearch -ZZ -x -H ldap://ldap.example.com
"""


class ldap_mixin(object):
    def _get_ldap_err_str(self, dn):
        err_dict = sys.exc_info()[1].args[0]
        return u"{} ({})".format(
            dn,
            " / ".join([u"{}: {}".format(_val, err_dict[_val]) for _val in ["info", "desc"] if _val in err_dict]),
        )

    def _add_entry(self, ld, dn, in_dict):
        if self.dryrun:
            return True, ""
        for key, value in in_dict.iteritems():
            if type(value) == list:
                in_dict[key] = [sub_val.encode("utf-8") for sub_val in value]
        try:
            ld.add_s(dn, ldap.modlist.addModlist(in_dict))
        except ldap.LDAPError:
            self.log(
                u"add error: {}, {}".format(
                    dn,
                    str(in_dict)
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            success, err_str = (False, self._get_ldap_err_str(dn))
        else:
            success, err_str = (True, "")
        return success, err_str

    def _delete_entry(self, ld, dn):
        try:
            ld.delete_s(dn)
        except ldap.LDAPError:
            self.log(
                u"delete error: {}".format(
                    dn,
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            success, err_str = (False, self._get_ldap_err_str(dn))
        else:
            success, err_str = (True, "")
        return success, err_str

    def _modify_entry(self, ld, dn, change_list):
        if self.dryrun:
            return True, ""
        new_list = []
        for val_0, val_1, val_list in change_list:
            if type(val_list) == list:
                val_list = [sub_val.encode("utf-8") for sub_val in val_list]
            new_list.append((val_0, val_1, val_list))
        try:
            ld.modify_s(dn, new_list)
        except ldap.LDAPError:
            self.log(
                u"modify error: {}, {}".format(
                    dn,
                    str(new_list)
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            success, err_str = (False, self._get_ldap_err_str(dn))
        else:
            success, err_str = (True, "")
        return success, err_str

    def _expand(self, in_str, lut):
        for key, value in lut.iteritems():
            if value:
                in_str = in_str.replace("{{{}}}".format(key), value)
        return in_str

    def _get_base_lut(self):
        return {
            "BASE_DN": self.par_dict["base_dn"],
        }

    def _is_valid_dn(self, dn, obj_type):
        _dns = self._expand(self.par_dict["{}_dn_template".format(obj_type)], self._get_base_lut())
        # replace unexpanded vars with .*
        f_re = re.compile("^(?P<pre>.*?)(?P<match>{[^}]+?})(?P<post>.*)")
        while True:
            cur_m = f_re.match(_dns)
            if cur_m:
                _dns = "{}.*{}".format(
                    cur_m.group("pre"),
                    cur_m.group("post"),
                )
            else:
                break
        _dns_re = re.compile("^{}$".format(_dns))
        return True if _dns_re.match(dn) else False

    def _expand_dn(self, obj_type, c_user, c_group, **kwargs):
        _expand_type = kwargs.get("expand_type", "dn")
        info_str = u"obj_type {} (user {}, group {})".format(
            obj_type,
            unicode(c_user),
            unicode(c_group),
        )
        # build lookup dict
        _lut = self._get_base_lut()
        _lut.update({
            "GROUPNAME": c_group.groupname if c_group else "",
            "USERNAME": c_user.login.strip() if c_user else "",
        })
        # obj_type is one of user, group
        try:
            _dn = self.par_dict["{}_{}_template".format(obj_type, _expand_type)]
            if _expand_type != "base":
                _base_name = "{}_base_template".format(obj_type)
                if _base_name in self.par_dict:
                    _dn = "{},{}".format(_dn, self.par_dict[_base_name])
            _dns = _dn
            _dn = self._expand(_dn, _lut)
        except:
            self.log(
                u"cannot create dn for {}: {}".format(
                    info_str,
                    process_tools.get_except_info(),
                ),
                logging_tools.LOG_LEVEL_CRITICAL,
            )
            _dn = ""
        else:
            self.log(
                u"dn='{}' for {} from {}".format(
                    _dn,
                    info_str,
                    _dns,
                )
            )
        return _dn

    def _read_config_from_db(self, cur_inst):
        # default par_dict
        def_dict = {
            "group_object_classes": (
                "posixGroup top clusterGroup namedObject",
                "default group classes"
            ),
            "user_object_classes": (
                "account posixAccount shadowAccount top clusterAccount",
                "default user classes"
            ),
            "group_base_template": (
                "ou=Group,{BASE_DN}",
                "base of groups",
            ),
            "group_dn_template": (
                "cn={GROUPNAME}",
                "group dn template"
            ),
            "user_base_template": (
                "ou=People,{BASE_DN}",
                "base of users",
            ),
            "user_dn_template": (
                "uid={USERNAME}",
                "user dn template"
            ),
            "automount_base_template": (
                "ou=Automount,{BASE_DN}",
                "base of automounts",
            ),
        }
        ldap_config = config.objects.get(Q(name="ldap_server"))  # @UndefinedVariable
        par_dict = {cur_var.name.lower(): cur_var.value for cur_var in config_str.objects.filter(Q(config=ldap_config))}
        needed_keys = set(["base_dn", "admin_cn", "root_passwd"])
        missed_keys = needed_keys - set(par_dict.keys())
        if len(missed_keys):
            cur_inst.srv_com.set_result(
                u"{} missing: {}".format(
                    logging_tools.get_plural("config_key", len(missed_keys)),
                    ", ".join(missed_keys)),
                server_command.SRV_REPLY_STATE_ERROR)
            par_dict = {}
        else:
            # add default keys to par_dict
            to_create = set(def_dict) - set(par_dict)
            if to_create:
                self.log(
                    "{} to create: {}".format(
                        logging_tools.get_plural("config_var", len(to_create)),
                        ", ".join(sorted(to_create)),
                    )
                )
                for key in to_create:
                    par_dict[key] = def_dict[key][0]
                    config_str.objects.create(
                        config=ldap_config,
                        name=key,
                        value=def_dict[key][0],
                        description=def_dict[key][1],
                    )
            self.log("{} defined in par_dict:".format(logging_tools.get_plural("entry", len(par_dict))))
            for key_num, key in enumerate(sorted(par_dict)):
                self.log(
                    u" - {:02d} {:<20s} {}".format(
                        key_num + 1,
                        key.upper(),
                        "*" * len(par_dict[key]) if key.upper() in ["ROOT_PASSWD"] else par_dict[key],
                    )
                )
            # rewrite keys
            for rw_key in ["group_object_classes", "user_object_classes"]:
                par_dict[rw_key] = [_v for _v in sum([entry.split(",") for entry in par_dict[rw_key].split()], []) if _v and _v.strip()]
        # store to local structure
        self.par_dict = par_dict
        return par_dict


class setup_ldap_server(cs_base_class.server_com, ldap_mixin):
    class Meta:
        needed_configs = ["ldap_server"]

    def _call(self, cur_inst):
        ldap_base = "/etc/openldap/slapd.d"
        if not os.path.isdir(ldap_base):
            cur_inst.srv_com.set_result("no ldap_base dir '{}' found".format(ldap_base), server_command.SRV_REPLY_STATE_ERROR)
        else:
            par_dict = self._read_config_from_db(cur_inst)
            if par_dict:
                # step one: hash root_password
                cmd_stat, root_hash = commands.getstatusoutput("slappasswd -h {{SSHA}} -s {}".format(par_dict["root_passwd"]))
                if cmd_stat:
                    cur_inst.srv_com.set_result(
                        "error hashing root-password ({:d}): {}".format(cmd_stat, root_hash),
                        server_command.SRV_REPLY_STATE_ERROR,
                    )
                else:
                    c_list = [
                        "dn:  olcDatabase={1}bdb,cn=config",
                        # "olcRootDN: gidNumber=0+uidNumber=0,cn=peercred,cn=external,cn=auth",
                        # "dn:  olcDatabase={1}bdb,cn=config",
                        "changetype: modify",
                        "replace: olcSuffix",
                        "olcSuffix: {}".format(par_dict["base_dn"]),
                        "-",
                        "replace: olcRootDN",
                        "olcRootDN: cn={0},{1}".format(par_dict["admin_cn"], par_dict["base_dn"]),
                        "-",
                        "add: olcRootPW",
                        "olcRootPW: {}".format(root_hash),
                        "",
                    ]
                    file("/tmp/x", "w").write("\n".join(c_list))
                    print "\n".join(c_list)
                    print par_dict
                    print root_hash, cmd_stat


class command_mixin(object):
    def call_command(self, command, *args):
        success, result = (False, [])
        bin_com = process_tools.find_file(command)
        if bin_com:
            c_stat, c_out = commands.getstatusoutput(u"{} {}".format(bin_com, " " .join(args)))
            if c_stat:
                result = ["{:d}".format(c_stat)] + c_out.split("\n")
            else:
                success = True
                result = c_out.split("\n")
        return success, result

# class create_ldap_certs(cs_base_class.server_com, ldap_mixin, command_mixin):
#    class Meta:
#        needed_configs = ["ldap_server"]
#    def _call(self, cur_inst):
#        pass


class init_ldap_config(cs_base_class.server_com, ldap_mixin, command_mixin):
    class Meta:
        needed_configs = ["ldap_server"]

    def call_command(self, command, *args):
        success, result = (False, [])
        bin_com = process_tools.find_file(command)
        if bin_com:
            c_stat, c_out = commands.getstatusoutput(u"{} {}".format(bin_com, " " .join(args)))
            if c_stat:
                result = ["{:d}".format(c_stat)] + c_out.split("\n")
            else:
                success = True
                result = c_out.split("\n")
        return success, result

    def _call(self, cur_inst):
        # fetch configs
        self.dryrun = False
        par_dict = self._read_config_from_db(cur_inst)
        if par_dict:
            errors = []
            base_dn = par_dict["base_dn"]
            self.log("will modify ldap_tree below {}".format(base_dn))
            try:
                ld_read = ldap.initialize("ldap://localhost")
                ld_read.simple_bind_s("", "")
            except ldap.LDAPError:
                ldap_err_str = self._get_ldap_err_str("read_access")
                self.log(
                    "cannot initialize read_cursor: %s" % (ldap_err_str),
                    logging_tools.LOG_LEVEL_ERROR
                )
                errors.append(ldap_err_str)
                ld_read = None
            else:
                try:
                    ld_write = ldap.initialize("ldap://localhost")
                    ld_write.simple_bind_s(
                        u"cn={},{}".format(
                            par_dict["admin_cn"],
                            par_dict["base_dn"]),
                        par_dict["root_passwd"]
                    )
                except ldap.LDAPError:
                    ldap_err_str = self._get_ldap_err_str("write_access")
                    self.log(
                        u"cannot initialize write_cursor: {}".format(ldap_err_str),
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
                    ok, err_str = self._add_entry(
                        ld_write,
                        par_dict["base_dn"],
                        {
                            "objectClass": ["top", "dcObject", "organization"],
                            "dc": [par_dict["base_dn"].split(",")[0].split("=")[1]],
                            "o": [par_dict["base_dn"].split(",")[0].split("=")[1]]
                        }
                    )
                    if ok:
                        self.log(
                            u"added root-entry at {}".format(
                                par_dict["base_dn"]
                            )
                        )
                    else:
                        root_ok = False
                        errors.append(err_str)
                        self.log(
                            u"cannot add root entry {}: {}".format(
                                par_dict["base_dn"],
                                err_str),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                if root_ok:
                    # init main groups
                    needed_dns = []
                    needed_dns.extend([self._expand_dn(entry, None, None, expand_type="base") for entry in ["user", "group", "automount"]])
                    # explode all needed dns and create parent dns if needed
                    _add_dns = []
                    for needed_dn in needed_dns:
                        _parts = list(reversed(ldap.dn.explode_dn(needed_dn)))
                        _create = []
                        while _parts:
                            _create.insert(0, _parts.pop(0))
                            _dn = u",".join(_create)
                            if _dn.endswith(base_dn) and _dn != base_dn and _dn not in _add_dns:
                                _add_dns.append(_dn)
                    needed_dns = [_entry for _entry in _add_dns if _entry not in needed_dns] + needed_dns
                    for dn, _attrs in ld_read.search_s(base_dn, ldap.SCOPE_SUBTREE, "objectclass=organizationalUnit"):
                        if dn in needed_dns:
                            needed_dns.remove(dn)
                    if needed_dns:
                        self.log(u"{} missing: {}".format(
                            logging_tools.get_plural("dn", len(needed_dns)),
                            ", ".join(needed_dns)))
                        for needed_dn in needed_dns:
                            short_dn = needed_dn.split(",")[0].split("=")[1]
                            ok, err_str = self._add_entry(
                                ld_write,
                                needed_dn,
                                {
                                    "objectClass": ["top", "organizationalUnit"],
                                    "ou": [short_dn],
                                    "description": [u"added by cluster-server on {}".format(global_config["SERVER_SHORT_NAME"])]
                                }
                            )
                            if ok:
                                self.log(u"added entry {}".format(needed_dn))
                            else:
                                errors.append(err_str)
                                self.log(
                                    u"cannot add entry {}: {}".format(
                                        needed_dn, err_str
                                    ),
                                    logging_tools.LOG_LEVEL_ERROR
                                )
                    if "sambadomain" in par_dict:
                        samba_dn = u"sambaDomainName={},{}".format(par_dict["sambadomain"], base_dn)
                        for dn, _attrs in ld_read.search_s(base_dn, ldap.SCOPE_SUBTREE, "objectclass=sambaDomain"):
                            ok, err_str = self._delete_entry(ld_write,
                                                             dn)
                            self.log("removed previous sambaDomain '{}'".format(dn))
                        self.log(
                            u"init SAMBA-structure (domainname is '{}', dn is '{}')".format(
                                par_dict["sambadomain"],
                                samba_dn
                            )
                        )
                        local_sid = self.call_command("net", "getlocalsid")[1][0].split()[-1]
                        self.log(u"local SID is {}".format(local_sid))
                        ok, err_str = self._add_entry(
                            ld_write,
                            samba_dn,
                            {
                                "objectClass": ["sambaDomain"],
                                # "structuralObjectClass" : "sambaDomain",
                                "sambaDomainName": [par_dict["sambadomain"]],
                                "sambaSID": local_sid,
                                "sambaAlgorithmicRidBase": "1000",
                                "sambaMinPwdLength": "5",
                                "sambaPwdHistoryLength": "0",
                                "sambaLogonToChgPwd": "0",
                                "sambaMaxPwdAge": "-1",
                                "sambaMinPwdAge": "0",
                                "sambaLockoutDuration": "30",
                                "sambaLockoutObservationWindow": "30",
                                "sambaLockoutThreshold": "0",
                                "sambaForceLogoff": "-1",
                                "sambaRefuseMachinePwdChange": "0",
                            }
                        )
                        if ok:
                            self.log("added entry {}".format(samba_dn))
                        else:
                            errors.append(err_str)
                            self.log(
                                u"cannot add entry {}: {}".format(
                                    samba_dn,
                                    err_str
                                ),
                                logging_tools.LOG_LEVEL_ERROR
                            )
                ld_read.unbind_s()
                ld_write.unbind_s()
        if errors:
            cur_inst.srv_com.set_result(
                "error init LDAP tree: {}".format(", ".join(errors)),
                server_command.SRV_REPLY_STATE_ERROR,
            )
        else:
            cur_inst.srv_com.set_result(
                "ok init ldap tree",
            )


class sync_ldap_config(cs_base_class.server_com, ldap_mixin):
    class Meta:
        needed_configs = ["ldap_server"]

    def _call(self, cur_inst):
        # fetch configs
        dryrun_flag = "server_key:dryrun"
        if dryrun_flag in cur_inst.srv_com:
            self.dryrun = True
        else:
            self.dryrun = False
        cur_inst.log(u"dryrun flag is '{}'".format(str(self.dryrun)))
        par_dict = self._read_config_from_db(cur_inst)
        errors = []
        if par_dict:
            try:
                ld_read = ldap.initialize("ldap://localhost")
                ld_read.simple_bind_s("", "")
            except ldap.LDAPError:
                ldap_err_str = self._get_ldap_err_str("read_access")
                self.log(
                    u"cannot initialize read_cursor: {}".format(
                        ldap_err_str
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
                errors.append(ldap_err_str)
                ld_read = None
            else:
                try:
                    ld_write = ldap.initialize("ldap://localhost")
                    ld_write.simple_bind_s(
                        "cn={},{}".format(
                            par_dict["admin_cn"],
                            par_dict["base_dn"]),
                        par_dict["root_passwd"])
                except ldap.LDAPError:
                    ldap_err_str = self._get_ldap_err_str("write_access")
                    self.log(
                        "cannot initialize write_cursor: {}".format(ldap_err_str),
                        logging_tools.LOG_LEVEL_ERROR)
                    errors.append(ldap_err_str)
                    ld_write = None
                    ld_read.unbind_s()
            if ld_read and ld_write:
                # fetch user / group info
                all_groups = {cur_g.pk: cur_g for cur_g in group.objects.all()}
                all_users = {
                    cur_u.pk: cur_u for cur_u in user.objects.filter(
                        Q(only_webfrontend=False)
                    ).prefetch_related("secondary_groups")
                }
                # not used right now
                devlog_dict = {}
                # luts
                group_lut = {cur_g.groupname: cur_g.pk for cur_g in all_groups.itervalues()}
                user_lut = {cur_u.login.strip(): cur_u.pk for cur_u in all_users.itervalues()}
                if "sambadomain" in par_dict:
                    dom_node = ld_read.search_s(
                        "{}".format(
                            par_dict["base_dn"]
                        ),
                        ldap.SCOPE_SUBTREE,
                        "objectclass=sambaDomain"
                    )[0]
                    samba_sid = dom_node[1]["sambaSID"][0]
                    self.log(
                        u"sambaSID is '{}' (domain {})".format(
                            samba_sid,
                            par_dict["sambadomain"]
                        )
                    )
                # build ldap structures
                for g_idx, g_stuff in all_groups.iteritems():
                    g_stuff.dn = self._expand_dn("group", None, g_stuff)
                    primary_users = [cur_u.login.strip() for cur_u in all_users.itervalues() if cur_u.active and cur_u.group_id == g_idx]
                    secondary_users = [
                        cur_u.login.strip() for cur_u in all_users.itervalues() if cur_u.active and cur_u.group_id != g_idx and any(
                            [
                                sec_g.pk == g_idx for sec_g in cur_u.secondary_groups.all()
                            ]
                        )
                    ]
                    g_stuff.attributes = {
                        "objectClass": [_entry for _entry in par_dict["group_object_classes"]],
                        "cn": [g_stuff.groupname],
                        "gidNumber": [str(g_stuff.gid)],
                        "memberUid": primary_users + secondary_users,
                        "description": [
                            u"Responsible person: {} {} {} ({})".format(
                                g_stuff.title,
                                g_stuff.first_name,
                                g_stuff.last_name,
                                g_stuff.email
                            )
                        ]
                    }
                    if "sambadomain" in par_dict:
                        g_stuff.attributes["objectClass"].append("sambaGroupMapping")
                        g_stuff.attributes["sambaGroupType"] = "2"
                        g_stuff.attributes["sambaSID"] = "{}-{:d}".format(
                            samba_sid,
                            g_stuff.gid * 2 + 1
                        )
                for _u_idx, u_stuff in all_users.iteritems():
                    g_stuff = all_groups[u_stuff.group_id]
                    u_stuff.dn = self._expand_dn("user", u_stuff, g_stuff)
                    # ldap.conf filter: pam_filter      &(objectclass=posixAccount)(|(host=\*)(host=zephises))
                    u_password = u_stuff.password
                    if u_password.count(":"):
                        _enc, _pwd = u_password.split(":", 1)
                        _enc = {"SHA1": "SHA"}.get(_enc, _enc)
                        u_password = u"{{{}}}{}".format(_enc, u_password.split(":", 1)[1])
                    else:
                        self.log(u"user_password for {} is not parseable, using value".format(unicode(u_stuff)))
                    u_stuff.attributes = {
                        "objectClass": [_entry for _entry in par_dict["user_object_classes"]],
                        # "structuralObjectClass" : ["namedObject"],
                        "cn": [u_stuff.login.strip()],
                        "userid": [u_stuff.login.strip()],
                        "gecos": [
                            u"{} {} {} ({})".format(
                                u_stuff.title,
                                u_stuff.first_name,
                                u_stuff.last_name,
                                u_stuff.email)],
                        "gidNumber": [str(g_stuff.gid)],
                        "uidNumber": [str(u_stuff.uid)],
                        # "memberOf"         : [self._expand_dn("group", None, g_stuff)],
                        "userPassword": [u_password],
                        "homeDirectory": [os.path.normpath(u"{}/{}".format(g_stuff.homestart, u_stuff.home.strip() or u_stuff.login.strip()))],
                        "loginShell": [u_stuff.shell],
                        "shadowLastChange": ["11192"],
                        "shadowMin": ["-1"],
                        "shadowMax": ["99999"],
                        "shadowWarning": ["7"],
                        "shadowInactive": ["-1"],
                        "shadowExpire": ["-1"],
                        "shadowFlag": ["1345383808"],
                        "host": devlog_dict.get(u_stuff.pk, ["*"]),
                        "description": [u_stuff.comment or "no description"]
                    }
                    if "sambadomain" in par_dict:
                        u_stuff.attributes["objectClass"].append("sambaSamAccount")
                        u_stuff.attributes["sambaSID"] = [
                            "{}-{:d}".format(
                                samba_sid,
                                u_stuff.uid * 2
                            )
                        ]
                        u_stuff.attributes["sambaAcctFlags"] = ["[U          ]"]
                        u_stuff.attributes["sambaPwdLastSet"] = [u"{:d}".format(int(time.time()))]
                        u_stuff.attributes["sambaNTPassword"] = [u_stuff.nt_password]
                        u_stuff.attributes["sambaLMPassword"] = [u_stuff.lm_password]
                        u_stuff.attributes["sambaPwdCanChange"] = ["0"]
                        u_stuff.attributes["sambaPwdMustChange"] = ["0"]
                        u_stuff.attributes["sambaBadPasswordCount"] = ["0"]
                # fetch all groups from ldap
                groups_ok, groups_to_change, groups_to_remove = ([], [], [])
                # get pure posixGroups (for WU Cluster)
                self.log("checking for groups with posixGroup")
                for dn, attrs in ld_read.search_s(par_dict["base_dn"], ldap.SCOPE_SUBTREE, "(objectClass=posixGroup)"):
                    dn_parts = ldap.explode_dn(dn, True)
                    group_name = dn_parts[0]
                    if self._is_valid_dn(dn, "group") and group_name in group_lut:
                        group_struct = all_groups[group_lut[group_name]]
                        change_list = ldap.modlist.modifyModlist(attrs, group_struct.attributes)
                        if change_list:
                            self.log("found group {} with missing attributes: {}".format(group_name, unicode(change_list)))
                            ok, err_str = self._modify_entry(
                                ld_write,
                                dn,
                                change_list)
                            if ok:
                                self.log(u"modified group {}".format(group_name))
                            else:
                                errors.append(err_str)
                                self.log(
                                    u"cannot modify group {}: {}".format(
                                        group_name,
                                        err_str
                                    ),
                                    logging_tools.LOG_LEVEL_ERROR
                                )
                s_str = "(&{})".format("".join(["(objectClass={})".format(_class) for _class in par_dict["group_object_classes"]]))
                self.log("checking for groups with {}".format(s_str))
                for dn, attrs in ld_read.search_s(par_dict["base_dn"], ldap.SCOPE_SUBTREE, s_str):
                    dn_parts = ldap.explode_dn(dn, True)
                    group_name = dn_parts[0]
                    if self._is_valid_dn(dn, "group"):
                        if group_name in group_lut.keys():
                            group_struct = all_groups[group_lut[group_name]]
                            if group_struct.active:
                                group_struct.orig_attributes = attrs
                                group_struct.change_list = ldap.modlist.modifyModlist(group_struct.orig_attributes, group_struct.attributes)
                                if group_struct.change_list:
                                    # changing group
                                    self.log(u"changing group {} (attributes differ)".format(group_name))
                                    groups_to_change.append(group_name)
                                else:
                                    groups_ok.append(group_name)
                            else:
                                # remove group (no longer active)
                                self.log("removing group %s (not active)" % (group_name))
                                groups_to_remove.append(group_name)
                        else:
                            # remove group (not found in db)
                            self.log("removing group %s (not found in db)" % (group_name))
                            groups_to_remove.append(group_name)
                    else:
                        self.log(u"ignoring posixGroup with dn {}".format(dn),
                                 logging_tools.LOG_LEVEL_WARN)
                # add groups
                groups_to_add = [
                    group_name for group_name in group_lut.keys() if (
                        group_name not in groups_ok and group_name not in groups_to_change and group_name not in groups_to_remove
                    )
                ]
                for group_to_add in groups_to_add:
                    group_struct = all_groups[group_lut[group_to_add]]
                    if group_struct.active:
                        ok, err_str = self._add_entry(
                            ld_write,
                            group_struct.dn,
                            group_struct.attributes)
                        if ok:
                            self.log(u"added group {}".format(group_to_add))
                        else:
                            errors.append(err_str)
                            self.log(
                                u"cannot add group {}: {}".format(group_to_add, err_str),
                                logging_tools.LOG_LEVEL_ERROR
                            )
                    else:
                        self.log(
                            u"cannot add group {}: not active".format(group_to_add),
                            logging_tools.LOG_LEVEL_WARN
                        )
                # modify groups
                for group_to_change in groups_to_change:
                    group_struct = all_groups[group_lut[group_to_change]]
                    ok, err_str = self._modify_entry(
                        ld_write,
                        group_struct.dn,
                        group_struct.change_list)
                    if ok:
                        self.log("modified group %s" % (group_to_change))
                    else:
                        errors.append(err_str)
                        self.log("cannot modify group %s: %s" % (group_to_change, err_str),
                                 logging_tools.LOG_LEVEL_ERROR)
                # remove groups
                for group_to_remove in groups_to_remove:
                    ok, err_str = self._delete_entry(
                        ld_write,
                        self._expand_dn("group", None, group(groupname=group_to_remove, gid=0))
                    )
                    if ok:
                        self.log(u"deleted group {}".format(group_to_remove))
                    else:
                        errors.append(err_str)
                        self.log(
                            "cannot delete group {}: {}".format(
                                group_to_remove,
                                err_str
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                # fetch all users from ldap
                users_ok, users_to_change, users_to_remove = ([], [], [])
                for dn, attrs in ld_write.search_s(par_dict["base_dn"], ldap.SCOPE_SUBTREE, "(&(objectclass=posixAccount)(objectClass=clusterAccount))"):
                    dn_parts = ldap.explode_dn(dn, True)
                    if self._is_valid_dn(dn, "user"):
                        user_name = dn_parts[0]
                        if user_name in user_lut.keys():
                            user_struct = all_users[user_lut[user_name]]
                            if user_struct.active and all_groups[user_struct.group_id].active and all_groups[user_struct.group_id].homestart:
                                # debian fixes
                                if "uid" in attrs and "userid" not in attrs:
                                    attrs["userid"] = attrs["uid"]
                                    del attrs["uid"]
                                user_struct.orig_attributes = attrs
                                user_struct.change_list = ldap.modlist.modifyModlist(
                                    user_struct.orig_attributes,
                                    user_struct.attributes,
                                    [
                                        sub_key for sub_key in user_struct.attributes.keys() if sub_key.startswith("shadow") or sub_key.lower() in (
                                            [
                                                "userpassword"
                                            ] if ("do_not_sync_password" in par_dict or not user_struct.db_is_auth_for_password) else []
                                        )
                                    ]
                                )
                                if user_struct.change_list:
                                    # changing user
                                    self.log("changing user {} (attributes differ)".format(user_name))
                                    users_to_change.append(user_name)
                                else:
                                    users_ok.append(user_name)
                            else:
                                # remove user (no longer active)
                                self.log("removing user {} (not active or group not active or no group_homestart)".format(user_name))
                                users_to_remove.append(user_name)
                        else:
                            # remove user (not found in db)
                            self.log("removing user {} (not found in db)".format(user_name))
                            users_to_remove.append(user_name)
                    else:
                        self.log(
                            "ignoring posixUser with dn %s" % (dn),
                            logging_tools.LOG_LEVEL_WARN
                        )
                # add users
                users_to_add = [
                    user_pk for user_pk in user_lut.keys() if user_pk not in users_ok and user_pk not in users_to_change and user_pk not in users_to_remove
                ]
                for user_to_add in users_to_add:
                    user_struct = all_users[user_lut[user_to_add]]
                    # group_stuct = all_groups[user_struct.group_id]
                    if user_struct.active and group_struct.active and group_struct.homestart:
                        ok, err_str = self._add_entry(
                            ld_write,
                            user_struct.dn,
                            user_struct.attributes
                        )
                        if ok:
                            self.log("added user %s" % (user_to_add))
                        else:
                            errors.append(err_str)
                            self.log(
                                u"cannot add user {}: {}".format(
                                    user_to_add,
                                    err_str),
                                logging_tools.LOG_LEVEL_ERROR)
                    else:
                        self.log(
                            u"cannot add user {}: user is {}, group is {}, homestart is {}".format(
                                user_to_add,
                                "active" if user_struct.active else "inactive",
                                "active" if group_struct.active else "inactive",
                                "OK" if group_struct.homestart else" not OK",
                            ),
                            logging_tools.LOG_LEVEL_WARN
                        )
                # modify users
                for user_to_change in users_to_change:
                    user_struct = all_users[user_lut[user_to_change]]
                    ok, err_str = self._modify_entry(ld_write,
                                                     user_struct.dn,
                                                     user_struct.change_list)
                    if ok:
                        self.log("modified user %s" % (user_to_change))
                    else:
                        errors.append(err_str)
                        self.log("cannot modify user %s: %s" % (user_to_change, err_str),
                                 logging_tools.LOG_LEVEL_ERROR)
                # remove users
                for user_to_remove in users_to_remove:
                    ok, err_str = self._delete_entry(
                        ld_write,
                        self._expand_dn("user", user(login=user_to_remove), None)
                    )
                    if ok:
                        self.log("deleted user %s" % (user_to_remove))
                    else:
                        errors.append(err_str)
                        self.log("cannot delete user %s: %s" % (user_to_remove, err_str),
                                 logging_tools.LOG_LEVEL_ERROR)
                # normal exports
                exp_entries = device_config.objects.filter(
                    Q(config__name__icontains="export") &
                    Q(device__is_meta_device=False)
                ).prefetch_related("config__config_str_set").select_related("device")
                export_dict = {}
                ei_dict = {}
                for entry in exp_entries:
                    dev_name, act_pk = (entry.device.name,
                                        entry.config.pk)
                    ei_dict.setdefault(
                        dev_name, {}
                    ).setdefault(
                        act_pk, {
                            "export": None,
                            "import": None,
                            "node_postfix": "",
                            "options": "-soft"
                        }
                    )
                    for c_str in entry.config.config_str_set.all():
                        if c_str.name in ei_dict[dev_name][act_pk]:
                            ei_dict[dev_name][act_pk][c_str.name] = c_str.value.replace("%h", dev_name)
                for mach, aeid_d in ei_dict.iteritems():
                    for _aeid_idx, aeid in aeid_d.iteritems():
                        if aeid["export"] and aeid["import"]:
                            export_dict[aeid["import"]] = (aeid["options"], "%s%s:%s" % (mach, aeid["node_postfix"], aeid["export"]))
                # home-exports
                home_exp_dict = home_export_list().exp_dict
                # now we have all automount-maps in export_dict, form is mountpoint: (options, source)
                for user_stuff in [cur_u for cur_u in all_users.values() if cur_u.active and cur_u.group.active]:
                    group_stuff = all_groups[user_stuff.group_id]
                    if user_stuff.export_id in home_exp_dict.keys():
                        home_stuff = home_exp_dict[user_stuff.export_id]
                        if group_stuff.homestart and group_stuff.homestart not in ["/None", "/none"] and user_stuff.home:
                            export_dict[
                                os.path.normpath(
                                    os.path.join(group_stuff.homestart, user_stuff.home.strip())
                                )
                            ] = (
                                home_stuff["options"],
                                "%s%s:%s/%s" % (home_stuff["name"], home_stuff["node_postfix"], home_stuff["homeexport"], user_stuff.home.strip())
                            )
                        else:
                            self.log(
                                "ignoring export for user {} because of empty or invalid homestart in group {}".format(
                                    unicode(user_stuff),
                                    unicode(group_stuff),
                                ),
                                logging_tools.LOG_LEVEL_WARN
                            )
                # build mountmaps
                master_object_class = ["top", "nisMap", "clusterAutomount"]
                master_map_pfix = "nisMapName"
                mount_point_name = "nisMapEntry"
                mount_point_class = ["top", "nisObject", "clusterAutomount"]
                master_map_dn = "nisMapName=auto.master"
                auto_maps = []
                automount_base = self._expand_dn("automount", None, None, expand_type="base")
                # pprint.pprint(export_dict)
                # remove mount_points which would overwrite '/'
                error_keys = sorted([key for key in export_dict.keys() if os.path.dirname(key) == "/"])
                if error_keys:
                    self.log(
                        u"found {}: {}; ignoring them".format(
                            logging_tools.get_plural("wrong key", len(error_keys)),
                            ", ".join(error_keys)),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                mount_points = {os.path.dirname(x): 0 for x in export_dict.keys() if x not in error_keys}.keys()
                if mount_points:
                    map_lut = {k: k.replace("/", "").replace(".", "_") for k in mount_points}
                    # automounter_map
                    auto_maps.append(
                        {
                            "dn": u"{},{}".format(
                                master_map_dn,
                                automount_base
                            ),
                            "attrs": {
                                "objectClass": master_object_class,
                                master_map_pfix: ["auto.master"]
                            }
                        }
                    )
                    ldap_add_list = [("nisMapName", ["auto.master"])]
                    for mount_point in mount_points:
                        map_name = u"auto.{}".format(map_lut[mount_point])
                        auto_maps.append(
                            {
                                "dn": u"{}={},{}".format(
                                    master_map_pfix,
                                    map_name,
                                    automount_base,
                                ),
                                "attrs": {
                                    "objectClass": master_object_class,
                                    master_map_pfix: [map_name]
                                }
                            }
                        )
                        auto_maps.append(
                            {
                                "dn": u"cn={},{},{}".format(
                                    mount_point,
                                    master_map_dn,
                                    automount_base,
                                ),
                                "attrs": dict(
                                    [
                                        ("objectClass", mount_point_class),
                                        ("cn", [mount_point]),
                                        (mount_point_name, [u"ldap://{}/{}={},{}".format(
                                            self.server_device_name,
                                            master_map_pfix,
                                            map_name,
                                            automount_base)]),
                                        ("description", [u"automounter map created by cluster-server on {}".format(self.server_device_name)])
                                    ] + ldap_add_list
                                )
                            }
                        )
                        sub_keys = [key for key, value in export_dict.iteritems() if key.startswith("{}/".format(mount_point))]
                        for sub_key in sub_keys:
                            sub_mount_point = os.path.basename(sub_key)
                            mount_opts, mount_src = export_dict[sub_key]
                            auto_maps.append(
                                {
                                    "dn": u"cn={},{}={},{}".format(
                                        sub_mount_point,
                                        master_map_pfix,
                                        map_name,
                                        automount_base,
                                    ),
                                    "attrs": dict(
                                        [
                                            ("objectClass", mount_point_class),
                                            ("cn", [sub_mount_point]),
                                            (mount_point_name, [u"{} {}".format(mount_opts, mount_src)])
                                        ] + ldap_add_list
                                    )
                                }
                            )
                map_keys = [value["dn"] for value in auto_maps]
                auto_dict = {value["dn"]: value for value in auto_maps}
                # fetch all maps from ldap
                maps_ok, maps_to_change, maps_to_remove = ([], [], [])
                for dn, attrs in ld_read.search_s(par_dict["base_dn"], ldap.SCOPE_SUBTREE, "(objectClass=clusterAutomount)"):
                    if dn in map_keys:
                        map_struct = auto_dict[dn]
                        map_struct["orig_attrs"] = attrs
                        map_struct["change_list"] = ldap.modlist.modifyModlist(map_struct["orig_attrs"], map_struct["attrs"])
                        if map_struct["change_list"]:
                            # changing map
                            self.log("changing map %s (content differs)" % (dn))
                            maps_to_change.append(dn)
                        else:
                            maps_ok.append(dn)
                    else:
                        # remove map (not found in db)
                        self.log("removing map {} (not found in db)".format(dn))
                        maps_to_remove.append(dn)
                # add maps
                maps_to_add = [x for x in map_keys if x not in maps_ok and x not in maps_to_change and x not in maps_to_remove]
                for map_to_add in maps_to_add:
                    map_struct = auto_dict[map_to_add]
                    ok, err_str = self._add_entry(
                        ld_write,
                        map_struct["dn"],
                        map_struct["attrs"])
                    if ok:
                        self.log(u"added map {}".format(map_to_add))
                    else:
                        errors.append(err_str)
                        self.log(
                            u"cannot add map {}: {}".format(
                                map_to_add,
                                err_str),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                # modify maps
                for map_to_change in maps_to_change:
                    map_struct = auto_dict[map_to_change]
                    ok, err_str = self._modify_entry(
                        ld_write,
                        map_struct["dn"],
                        map_struct["change_list"])
                    if ok:
                        self.log("modified map {}".format(map_to_change))
                    else:
                        errors.append(err_str)
                        self.log(
                            u"cannot modify map {}: {}".format(
                                map_to_change,
                                err_str
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                # remove maps
                maps_to_remove.reverse()
                for map_to_remove in maps_to_remove:
                    ok, err_str = self._delete_entry(
                        ld_write,
                        map_to_remove
                    )
                    if ok:
                        self.log("deleted map %s" % (map_to_remove))
                    else:
                        errors.append(err_str)
                        self.log(
                            "cannot delete map %s: %s" % (map_to_remove, err_str),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                # pprint.pprint(export_dict)
                ld_read.unbind_s()
                ld_write.unbind_s()
        if errors:
            cur_inst.srv_com.set_result(
                "error synced LDAP tree: {}".format(", ".join(errors)),
                server_command.SRV_REPLY_STATE_ERROR
            )
        else:
            cur_inst.srv_com.set_result(
                "ok synced LDAP tree",
            )
