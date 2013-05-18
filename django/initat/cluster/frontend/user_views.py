#!/usr/bin/python -Ot
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2012,2013 Andreas Lang-Nevyjel
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

""" user views """

import os
from django.http import HttpResponse
from initat.core.render import render_me
from initat.cluster.frontend.helper_functions import init_logging, logging_pool, contact_server
from django.conf import settings
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
import logging_tools
from lxml import etree
import pprint
from lxml.builder import E
import process_tools
from initat.cluster.backbone.models import partition_table, partition_disc, partition, \
     partition_fs, image, architecture, device_class, device_location, group, user, \
     device_config, device_group
import server_command
from django.contrib.auth.models import User, UserManager, Permission
import net_tools

@login_required
@init_logging
def overview(request, *args, **kwargs):
    if request.method == "GET":
        if kwargs["mode"] == "table":
            return render_me(request, "user_overview.html", {})()
    else:
        shell_names = [line.strip() for line in file("/etc/shells", "r").read().split("\n") if line.strip()]
        shell_names = [line for line in shell_names if os.path.exists(line)] + ["/bin/false"]
        # get homedir export
        exp_list = E.homedir_exports(
            E.homedir_export("none", pk="0")
        )
        home_exp = device_config.objects.filter(
            Q(config__name__icontains="homedir") &
            Q(config__name__icontains="export") &
            Q(config__config_str__name="homeexport")).select_related("device", "config").prefetch_related("config__config_str_set")
        for cur_exp in home_exp:
            exp_list.append(
                E.homedir_export("%s on %s" % (
                    cur_exp.config.config_str_set.get(Q(name="homeexport")).value,
                    unicode(cur_exp.device)),
                                 pk="%d" % (cur_exp.pk))
            )
        # all permissions
        all_perms = Permission.objects.all().select_related("content_type").order_by("codename")
        perm_list = E.permissions()
        for entry in all_perms:
            c_name, ctm = (entry.codename,
                           entry.content_type.model)
            c_parts = c_name.split("_")
            if c_parts[0] in ["add", "change", "delete"] and c_name.endswith(ctm) or c_name.startswith("wf_"):
                pass
            elif entry.content_type.app_label in ["backbone"]:
                perm_list.append(E.permission(entry.name, pk="%d" % (entry.pk)))
        # chaching for faster m2m lookup
        user_perm_dict = {}
        for user_perm in Permission.objects.all().prefetch_related("user_set"):
            for cur_user in user_perm.user_set.all():
                user_perm_dict.setdefault(cur_user.username, []).append(user_perm)
        device_group_dict = {}
        for cur_user in user.objects.all().prefetch_related("allowed_device_groups"):
            device_group_dict[cur_user.login] = list([dg.pk for dg in cur_user.allowed_device_groups.all()])
        xml_resp = E.response(
            exp_list,
            perm_list,
            E.groups(*[cur_g.get_xml() for cur_g in group.objects.all()]),
            E.users(*[cur_u.get_xml(with_permissions=True, user_perm_dict=user_perm_dict, allowed_device_group_dict=device_group_dict) for cur_u in user.objects.all()]),
            E.shells(*[E.shell(cur_shell, pk=cur_shell) for cur_shell in sorted(shell_names)]),
            E.device_groups(*[cur_dg.get_xml(full=False, with_devices=False) for cur_dg in device_group.objects.exclude(Q(cluster_device_group=True))])
        )
        request.xml_response["response"] = xml_resp
        return request.xml_response.create_response()

@login_required
@init_logging
def sync_users(request):
    # create homedirs
    create_user_list = user.objects.filter(Q(home_dir_created=False) & Q(active=True) & Q(group__active=True))
    request.log("user homes to create: %d" % (len(create_user_list)))
    for create_user in create_user_list:
        request.log("trying to create user_home for '%s'" % (unicode(create_user)))
        srv_com = server_command.srv_command(command="create_user_home")
        srv_com["server_key:username"] = create_user.login
        result = contact_server(request, "tcp://localhost:8004", srv_com, timeout=30)
    srv_com = server_command.srv_command(command="sync_ldap_config")
    result = contact_server(request, "tcp://localhost:8004", srv_com, timeout=30)
    srv_com = server_command.srv_command(command="sync_http_users")
    result = contact_server(request, "tcp://localhost:8010", srv_com)
    return request.xml_response.create_response()
