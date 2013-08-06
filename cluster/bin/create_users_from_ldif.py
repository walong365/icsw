#!/usr/bin/python-init -Otu
#
# Copyright (C) 2013 Andreas Lang-Nevyjel
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
""" create groups and users from ldif dumps """

import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import argparse
import crypt
import pprint
import process_tools

from django.db.models import Q
from initat.cluster.backbone.models import group, user

multiple_list = set(["member"])
integer_list = set(["uidNumber", "gidNumber"])

class entry(dict):
    def __init__(self, dn):
        dict.__init__(self)
        self["dn"] = dn
    def __setitem__(self, key, value):
        if key in multiple_list:
            self.setdefault(key, []).append(value)
        else:
            dict.__setitem__(self, key, value)
        # print key, self[key]
    def to_int(self):
        for key, value in self.iteritems():
            if key in integer_list:
                dict.__setitem__(self, key, int(value))
            # print key, type(self[key]), self[key]
    @staticmethod
    def to_integer(in_dict):
        print "Casting to int for %d entries" % (len(in_dict))
        for key, value in in_dict.iteritems():

            value.to_int()

class ad_user(entry):
    def __init__(self, dn):
        entry.__init__(self, dn)
        print "New user with dn=%s" % (self["dn"])
    @staticmethod
    def setup(f_name):
        ad_user.dict = {}
        cur_user = None
        for line in file(f_name).readlines():
            line = line.strip()
            if not line.strip().startswith("#") and line.count(":"):
                key, value = line.split(":", 1)
                value = value.strip()
                if value.startswith(":"):
                    if key == "dn":
                        cur_user = None
                else:
                    if key == "dn":
                        cur_user = ad_user(value)
                        ad_user.dict[value.lower()] = cur_user
                    elif cur_user:
                        cur_user[key] = value
        ad_user.to_integer(ad_user.dict)
    @staticmethod
    def sync_db(args, group_dict):
        for key, value in ad_user.dict.iteritems():
            name_parts = value["cn"].split()
            try:
                cur_u = user.objects.get(Q(uid=value["uidNumber"]))
            except user.DoesNotExist:
                # get group
                try:
                    cur_g = [g_struct.db_obj for g_struct in group_dict.itervalues() if g_struct.db_obj.gid == value["gidNumber"]][0]
                except:
                    print "no group for user %s found (%s)" % (key, process_tools.get_except_info())
                    cur_u = None
                else:
                    cur_u = user.objects.create(
                        active=True,
                        group=cur_g,
                        login=value["uid"].lower(),
                        uid=value["uidNumber"],
                        password=value["uid"].lower(),
                        db_is_auth_for_password=False,
                        home_dir_created=args.homedir_exists,
                        )
                print "created new user '%s'" % (unicode(cur_u))
            else:
                print "user '%s' already exists" % (unicode(cur_u))
            if cur_u is not None:
                first_name, last_name, comment = (
                    " ".join(name_parts[:-1]),
                    name_parts[-1],
                    " ".join(name_parts),
                    )
                cur_u.first_name = first_name
                cur_u.last_name = last_name
                cur_u.comment = comment
                cur_u.save()
                value.db_obj = cur_u

class ad_group(entry):
    def __init__(self, dn):
        entry.__init__(self, dn)
        print "New group with dn=%s" % (self["dn"])
    @staticmethod
    def setup(f_name):
        ad_group.dict = {}
        cur_group = None
        for line in file(f_name).readlines():
            line = line.strip()
            if not line.strip().startswith("#") and line.count(":"):
                key, value = line.split(":", 1)
                value = value.strip()
                if value.startswith(":"):
                    if key == "dn":
                        cur_group = None
                else:
                    if key == "dn":
                        cur_group = ad_group(value)
                        ad_group.dict[value.lower()] = cur_group
                    elif cur_group:
                        cur_group[key] = value
        ad_group.to_integer(ad_group.dict)
    @staticmethod
    def sync_db(args):
        for key, value in ad_group.dict.iteritems():
            try:
                cur_g = group.objects.get(Q(gid=value["gidNumber"]))
            except group.DoesNotExist:
                cur_g = group.objects.create(
                    active=True,
                    groupname=value["cn"].lower(),
                    gid=value["gidNumber"],
                    homestart=args.homestart,
                    comment=value["cn"],
                    )
                print "created new group '%s'" % (unicode(cur_g))
            else:
                print "%s already exists" % (unicode(cur_g))
            value.db_obj = cur_g

def main():
    my_parser = argparse.ArgumentParser()
    my_parser.add_argument("--group", type=str, help="Group ldif file [%(default)s]", default="AdGroups.ldif")
    my_parser.add_argument("--user", type=str, help="User ldif file [%(default)s]", default="AdUsers.ldif")
    my_parser.add_argument("--homestart", type=str, help="Homestart for new groups [%(default)s]", default="/home")
    my_parser.add_argument("--homedir-exists", default=False, help="homedir already exists [%(default)s]", action="store_true")
    args = my_parser.parse_args()
    if not os.path.exists(args.group):
        print "Group file does not exist"
        sys.exit(-1)
    if not os.path.exists(args.user):
        print "User file does not exist"
        sys.exit(-1)
    ad_group.setup(args.group)
    ad_user.setup(args.user)
    ad_group.sync_db(args)
    ad_user.sync_db(args, ad_group.dict)

if __name__ == "__main__":
    main()

