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
import net_tools
import pprint
import logging
import logging_tools
import process_tools
import server_command
from lxml import etree
from lxml.builder import E

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, UserManager, Permission
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.db.models import Q
from django.views.generic import View
from django.utils.decorators import method_decorator

from initat.cluster.backbone.models import partition_table, partition_disc, partition, \
     partition_fs, image, architecture, group, user, device_config, device_group, \
     user_variable
from initat.core.render import render_me, render_string
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper, update_session_object
from initat.cluster.frontend.forms import dummy_password_form, group_detail_form, user_detail_form

logger = logging.getLogger("cluster.user")

class overview(View):
    @method_decorator(login_required)
    def get(self, request, *args, **kwargs):
        if kwargs["mode"] == "table":
            return render_me(request, "user_overview_table.html", {})()
        elif kwargs["mode"] == "tree":
            return render_me(request, "user_overview_tree.html", {})()
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request, *args, **kwargs):
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
        group_perm_dict, user_perm_dict = ({}, {})
        for group_perm in Permission.objects.all().prefetch_related("group_set"):
            for cur_group in group_perm.group_set.all():
                group_perm_dict.setdefault(cur_group.name, []).append(group_perm)
        for user_perm in Permission.objects.all().prefetch_related("user_set"):
            for cur_user in user_perm.user_set.all():
                user_perm_dict.setdefault(cur_user.username, []).append(user_perm)
        group_device_group_dict, user_device_group_dict = ({}, {})
        for cur_user in user.objects.all().prefetch_related("allowed_device_groups"):
            user_device_group_dict[cur_user.login] = list([dg.pk for dg in cur_user.allowed_device_groups.all()])
        for cur_group in group.objects.all().prefetch_related("allowed_device_groups"):
            group_device_group_dict[cur_group.groupname] = list([dg.pk for dg in cur_group.allowed_device_groups.all()])
        xml_resp = E.response(
            exp_list,
            perm_list,
            E.groups(
                *[
                    cur_g.get_xml(
                        with_permissions=True,
                        group_perm_dict=group_perm_dict,
                        with_allowed_device_groups=True,
                        allowed_device_group_dict=group_device_group_dict,
                        ) for cur_g in group.objects.all().prefetch_related("allowed_device_groups")
                    ]
                ),
            E.users(
                *[
                    cur_u.get_xml(
                        with_permissions=True,
                        user_perm_dict=user_perm_dict,
                        with_allowed_device_groups=True,
                        allowed_device_group_dict=user_device_group_dict) for cur_u in user.objects.all().prefetch_related("secondary_groups", "allowed_device_groups")
                    ]
                ),
            E.shells(*[E.shell(cur_shell, pk=cur_shell) for cur_shell in sorted(shell_names)]),
            E.device_groups(*[cur_dg.get_xml(full=False, with_devices=False) for cur_dg in device_group.objects.exclude(Q(cluster_device_group=True))])
        )
        request.xml_response["response"] = xml_resp

class sync_users(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        # create homedirs
        create_user_list = user.objects.filter(Q(home_dir_created=False) & Q(active=True) & Q(group__active=True))
        logger.info("user homes to create: %d" % (len(create_user_list)))
        for create_user in create_user_list:
            logger.info("trying to create user_home for '%s'" % (unicode(create_user)))
            srv_com = server_command.srv_command(command="create_user_home")
            srv_com["server_key:username"] = create_user.login
            result = contact_server(request, "tcp://localhost:8004", srv_com, timeout=30)
        srv_com = server_command.srv_command(command="sync_ldap_config")
        result = contact_server(request, "tcp://localhost:8004", srv_com, timeout=30)
        srv_com = server_command.srv_command(command="sync_http_users")
        result = contact_server(request, "tcp://localhost:8010", srv_com)

class get_password_form(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        request.xml_response["form"] = render_string(
            request,
            "crispy_form.html",
            {
                "form" : dummy_password_form()
            }
        )

class save_layout_state(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        if "user_vars" not in request.session:
            request.session["user_vars"] = {}
        user_vars = request.session["user_vars"]
        for key, value in _post.iteritems():
            if key.count("isClosed"):
                value = True if value.lower() in ["true"] else False
                if key in user_vars:
                    if user_vars[key].value != value:
                        user_vars[key].value = value
                        user_vars[key].save()
                else:
                    user_vars[key] = user_variable.objects.create(
                        user=request.session["db_user"],
                        name=key,
                        value=value)
        update_session_object(request)
        request.session.save()

class set_user_var(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        user_vars = request.session["user_vars"]
        key, value = (_post["key"], _post["value"])
        if key in user_vars:
            if user_vars[key].value != value:
                user_vars[key].value = value
                user_vars[key].save()
        else:
            user_vars[key] = user_variable.objects.create(
                user=request.session["db_user"],
                name=key,
                value=value)
        update_session_object(request)
        request.session.save()

class move_user(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        cur_user = user.objects.get(Q(pk=_post["src_id"].split("__")[1]))
        cur_group = group.objects.get(Q(pk=_post["dst_id"].split("__")[1]))
        cur_user.group = cur_group
        cur_user.save()
        request.xml_response.info("user %s moved to group %s" % (
            unicode(cur_user),
            unicode(cur_group)), logger)
        
class ug_detail_form(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        key = _post["key"]
        if key.startswith("group__"):
            cur_group = group.objects.get(Q(pk=key.split("__")[1]))
            request.xml_response["form"] = render_string(
                request,
                "crispy_form.html",
                {
                    "form" : group_detail_form(
                        auto_id="group__%d__%%s" % (cur_group.pk),
                        instance=cur_group,
                    )
                }
            )
        else:
            cur_user = user.objects.get(Q(pk=key.split("__")[1]))
            request.xml_response["form"] = render_string(
                request,
                "crispy_form.html",
                {
                    "form" : user_detail_form(
                        auto_id="user__%d__%%s" % (cur_user.pk),
                        instance=cur_user,
                    )
                }
            )
            
        