#!/usr/bin/python-init -Otu
#
# Copyright (C) 2014 Andreas Lang-Nevyjel
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
""" migrates old simple permission base to new with access level """

import sys
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

from initat.cluster.backbone.models import user, group, \
    group_permission, user_permission, group_object_permission, user_object_permission

def main():
    # for d_perm in [group_permission, user_permission, group_object_permission, user_object_permission]:
    #    d_perm.objects.all().delete()
    new_perms_count = group_permission.objects.all().count() + user_permission.objects.all().count() + \
        group_object_permission.objects.all().count() + user_object_permission.objects.all().count()
    if new_perms_count:
        print "New permission scheme already in use, skipping migration ..."
        sys.exit(0)
    # groups
    g_created, o_created = (0, 0)
    for obj_type, obj_name, g_perm, o_perm in [
        (group, "group", group_permission, group_object_permission),
        (user, "user", user_permission, user_object_permission)]:
        for cur_obj in obj_type.objects.all():
            for perm in cur_obj.permissions.all():
                g_perm.objects.create(**{obj_name : cur_obj, "csw_permission" : perm})
                g_created += 1
            for obj_perm in cur_obj.object_permissions.all():
                o_perm.objects.create(**{obj_name : cur_obj, "csw_object_permission" : obj_perm})
                o_created += 1
    print "created: global %d, object level %d" % (g_created, o_created)

if __name__ == "__main__":
    main()
