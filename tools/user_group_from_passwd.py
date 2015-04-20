#!/usr/bin/python-init -Otu
#
# Copyright (C) 2015 Andreas Lang-Nevyjel
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
""" restore users / groups from passwd / group files """

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import django
django.setup()

from django.db.models import Q
from initat.cluster.backbone.models import group, user, home_export_list
from lxml import etree  # @UnresolvedImport
import codecs
import logging_tools
import sys
import pprint
import argparse

OBJ_DICT = {
    "user": user,
    "group": group,
}


class SysGroup(object):
    def __init__(self, parts):
        self.name = parts[0]
        self.gid = int(parts[2])
        self.users = parts[3].split(",")

    def __unicode__(self):
        return "group {} ({:d})".format(self.name, self.gid)

    def __repr__(self):
        return unicode(self)


class SysUser(object):
    def __init__(self, parts):
        self.name = parts[0]
        self.uid = int(parts[2])
        self.gid = int(parts[3])
        self.info = parts[4]
        self.home_dir = parts[5]
        self.shell = parts[6]

    def __unicode__(self):
        return "user {} ({:d})".format(self.name, self.uid)

    def __repr__(self):
        return unicode(self)


def main():
    _groups = [SysGroup(_entry.split(":")) for _entry in file("/etc/group", "r").read().split("\n") if _entry.split()]
    _group_dict = {_g.gid: _g for _g in _groups}
    _users = [SysUser(_entry.split(":")) for _entry in file("/etc/passwd", "r").read().split("\n") if _entry.split()]
    ap = argparse.ArgumentParser()
    _hel = home_export_list()
    if not _hel.exp_dict:
        print("no home_exports defined, exiting")
        sys.exit(1)
    ap.add_argument("--minuid", type=int, default=100, help="minimum uid to use [%(default)d]")
    ap.add_argument("--maxuid", type=int, default=32768, help="minimum uid to use [%(default)d]")
    ap.add_argument("--export", type=int, default=_hel.exp_dict.keys()[0], choices=_hel.exp_dict.keys(), help="export entry to use [%(default)d]")
    ap.add_argument("--homestart", type=str, default="/home", help="homestart for newly creatd groups [%(default)s]")
    opts = ap.parse_args()
    print("Home export entry:")
    pprint.pprint(_hel.exp_dict[opts.export])
    _users = [_entry for _entry in _users if _entry.uid >= opts.minuid and _entry.uid <= opts.maxuid]
    # link to group
    for _entry in _users:
        _entry.group = _group_dict[_entry.gid]
    for _user in _users:
        try:
            cur_group = group.objects.get(Q(groupname=_user.group.name))
        except group.DoesNotExist:
            print("creating new group for {}".format(unicode(_user.group)))
            cur_group = group.objects.create(
                groupname=_user.group.name,
                homestart=opts.homestart,
                gid=_user.group.gid
            )
        try:
            cur_user = user.objects.get(Q(login=_user.name))
        except user.DoesNotExist:
            print("creating new user for {}".format(unicode(_user)))
            cur_user = user.objects.create(
                group=cur_group,
                login=_user.name,
                uid=_user.uid,
                shell=_user.shell,
                comment=_user.info,
                export=_hel.exp_dict[opts.export]["entry"],
                password="{}123".format(_user.name),
            )
        else:
            print("user {} already present".format(unicode(cur_user)))

if __name__ == "__main__":
    main()
