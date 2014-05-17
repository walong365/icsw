#!/usr/bin/python-init -Otu

import sys
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

from initat.cluster.backbone.models import user, group # , capability
from django.contrib.auth.models import User, Group, Permission
import logging_tools
import django.contrib.auth.hashers
from django.contrib.contenttypes.models import ContentType

CRYPT_HASH_FORMSTR = "crypt$$%s"

def main():
    # User.objects.all().delete()
    # Group.objects.all().delete()
    django_users, django_groups, django_permissions = (
        User.objects.all(),
        Group.objects.all(),
        Permission.objects.all())
    if len(django_users) or len(django_groups):
        print "Django users (%d) and/or groups (%d) already present, exiting ..." % (
            len(django_users),
            len(django_groups))
        sys.exit(0)
    non_basic_perms = [cur_perm for cur_perm in django_permissions if cur_perm.codename.split("_")[0] not in ["add", "delete", "change"]]
    if non_basic_perms:
        print "removing %d non-django permissions" % (len(non_basic_perms))
        for nbp in non_basic_perms:
            nbp.delete()
    cluster_users, cluster_groups, cluster_perms = (
        user.objects.all().order_by("pk"),
        group.objects.all().order_by("pk"),
        # capability.objects.all().order_by("pk")
        [],
    )
    user_content_type = ContentType.objects.get(app_label="backbone", model="user")
    print "Found %s:" % (logging_tools.get_plural("custer capability", len(cluster_perms)))
    perm_lut = {}
    for cluster_perm in cluster_perms:
        new_perm = Permission(
            codename="wf_%s" % (cluster_perm.name),
            content_type=user_content_type,
            name=cluster_perm.description
        )
        new_perm.save()
        perm_lut[cluster_perm.pk] = new_perm
    print "Meta block for user should contain:"
    print
    print "    class Meta:"
    print "        permissions = {"
    print "\n".join(["            (\"%s\", \"%s\")," % ("wf_%s" % (cluster_perm.name), cluster_perm.description) for cluster_perm in cluster_perms])
    print "        }"
    print
    if not len(cluster_users) and not len(cluster_groups):
        print "No cluster users or groups defined, stragen ..."
        sys.exit(0)
    print "Found %s and %s:" % (
        logging_tools.get_plural("cluster group", len(cluster_groups)),
        logging_tools.get_plural("cluster user", len(cluster_users)))
    group_lut, user_lut = ({}, {})
    for c_group in cluster_groups:
        new_group = Group(
            name=c_group.groupname
        )
        new_group.save()
        group_lut[c_group.pk] = new_group
        print "    created django group %s" % (unicode(new_group))
        group_caps = c_group.group_cap_set.all()
        new_group.permissions.add(*[perm_lut[group_cap.capability_id] for group_cap in group_caps])
        print "        added %s" % (logging_tools.get_plural("capability", len(group_caps)))
    for c_user in cluster_users:
        new_user = User(
            username=c_user.login,
            first_name=c_user.uservname,
            last_name=c_user.usernname,
            email=c_user.useremail,
            password=CRYPT_HASH_FORMSTR % (c_user.password),
            is_staff=False,
            is_active=True if c_user.active else False,
            is_superuser=False)
        new_user.save()
        user_lut[c_user.pk] = new_user
        print "    created django user %s" % (unicode(new_user))
        # add primary user
        new_user.groups.add(group_lut[c_user.group_id])
        print "        added primary group %s" % (unicode(group_lut[c_user.group_id]))
        # secondary groups
        for sec_group in c_user.user_group_set.all():
            new_user.groups.add(group_lut[sec_group.pk])
            print "        added secondary group %s" % (unicode(group_lut[sec_group.pk]))
        # caps
        user_caps = c_user.user_cap_set.all()
        new_user.user_permissions.add(*[perm_lut[user_cap.capability_id] for user_cap in user_caps])
        print "        added %s" % (logging_tools.get_plural("capability", len(user_caps)))
        su_perm = "backbone.wf_mu"
        if new_user.has_perm(su_perm):
            new_user.is_staff = True
            new_user.is_superuser = True
            new_user.save()
            print "        user is staff and superuser because of %s permission" % (su_perm)

if __name__ == "__main__":
    main()
