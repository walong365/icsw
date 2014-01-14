#!/usr/bin/python -Ot
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2014 Andreas Lang-Nevyjel
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

# from crispy_forms.layout import Submit, Layout, Field, ButtonHolder, Button
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.db.models import get_model, Q
from django.utils.decorators import method_decorator
from django.views.generic import View
from initat.cluster.backbone.models import group, user, device_config, device_group, \
     user_variable, csw_permission, get_related_models, csw_object_permission
from initat.cluster.backbone.render import permission_required_mixin
from initat.cluster.frontend.forms import dummy_password_form, group_detail_form, user_detail_form, \
    account_detail_form
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper, update_session_object
from initat.core.render import render_me, render_string
# from lxml import etree # @UnresolvedImports
from lxml.builder import E # @UnresolvedImports
import config_tools
import logging
import logging_tools
import os
import pprint
import process_tools
import server_command

logger = logging.getLogger("cluster.user")

class overview(permission_required_mixin, View):
    any_required_permissions = (
        "backbone.admin",
        "backbone.group_admin"
            )
    @method_decorator(login_required)
    def get(self, request, *args, **kwargs):
        return render_me(request, "user_overview_tree.html", {
            # "user_detail_form" : user_detail_form(),
            "group_detail_form" : group_detail_form(),
            "user_detail_form" : user_detail_form(),
            })()
#     @method_decorator(login_required)
#     @method_decorator(xml_wrapper)
#     def post(self, request, *args, **kwargs):
#         shell_names = [line.strip() for line in file("/etc/shells", "r").read().split("\n") if line.strip()]
#         shell_names = [line for line in shell_names if os.path.exists(line)] + ["/bin/false"]
#         # get homedir export
#         exp_list = E.homedir_exports(
#             E.homedir_export("none", pk="0")
#         )
#         home_exp = device_config.objects.filter(
#             Q(config__name__icontains="homedir") &
#             Q(config__name__icontains="export") &
#             Q(config__config_str__name="homeexport")).select_related("device", "config").prefetch_related("config__config_str_set")
#         for cur_exp in home_exp:
#             exp_list.append(
#                 E.homedir_export("%s on %s" % (
#                     cur_exp.config.config_str_set.get(Q(name="homeexport")).value,
#                     unicode(cur_exp.device)),
#                                  pk="%d" % (cur_exp.pk))
#             )
#         # all permissions
#         all_perms = csw_permission.objects.all().select_related("content_type").order_by("codename")
#         perm_list = E.permissions()
#         for entry in all_perms:
#             c_name, ctm = (entry.codename,
#                            entry.content_type.model)
#             c_parts = c_name.split("_")
#             if c_parts[0] in ["add", "change", "delete"] and c_name.endswith(ctm) or c_name.startswith("wf_"):
#                 pass
#             elif entry.content_type.app_label in ["backbone"]:
#                 perm_list.append(E.permission(entry.name, pk="%d" % (entry.pk)))
#         # caching for faster m2m lookup
#         group_perm_dict, user_perm_dict = ({}, {})
#         for group_perm in csw_permission.objects.all().prefetch_related("db_group_permissions").select_related("content_type"):
#             for cur_group in group_perm.db_group_permissions.all():
#                 group_perm_dict.setdefault(cur_group.groupname, []).append(group_perm)
#         for user_perm in csw_permission.objects.all().prefetch_related("db_user_permissions").select_related("content_type"):
#             for cur_user in user_perm.db_user_permissions.all():
#                 user_perm_dict.setdefault(cur_user.login, []).append(user_perm)
#         group_device_group_dict, user_device_group_dict = ({}, {})
#         for cur_user in user.objects.all().prefetch_related("allowed_device_groups"):
#             user_device_group_dict[cur_user.login] = list([dg.pk for dg in cur_user.allowed_device_groups.all()])
#         for cur_group in group.objects.all().prefetch_related("allowed_device_groups"):
#             group_device_group_dict[cur_group.groupname] = list([dg.pk for dg in cur_group.allowed_device_groups.all()])
#         xml_resp = E.response(
#             exp_list,
#             perm_list,
#             E.groups(
#                 *[
#                     cur_g.get_xml(
#                         with_permissions=True,
#                         group_perm_dict=group_perm_dict,
#                         with_allowed_device_groups=True,
#                         allowed_device_group_dict=group_device_group_dict,
#                         ) for cur_g in group.objects.all().prefetch_related("allowed_device_groups")
#                     ]
#                 ),
#             E.users(
#                 *[
#                     cur_u.get_xml(
#                         with_permissions=True,
#                         user_perm_dict=user_perm_dict,
#                         with_allowed_device_groups=True,
#                         allowed_device_group_dict=user_device_group_dict,
#                         ) for cur_u in user.objects.all().prefetch_related("secondary_groups", "allowed_device_groups")
#                         if request.user.has_object_perm("backbone.group_admin", cur_u.group)
#                     ]
#                 ),
#             E.shells(*[E.shell(cur_shell, pk=cur_shell) for cur_shell in sorted(shell_names)]),
#             E.device_groups(*[cur_dg.get_xml(full=False, with_devices=False) for cur_dg in device_group.objects.exclude(Q(cluster_device_group=True))])
#         )
#         request.xml_response["response"] = xml_resp

class sync_users(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        # create homedirs
        # FIXME: only create users for local server
        create_user_list = user.objects.exclude(Q(export=None)).filter(Q(home_dir_created=False) & Q(active=True) & Q(group__active=True))
        logger.info("user homes to create: %d" % (len(create_user_list)))
        for create_user in create_user_list:
            logger.info("trying to create user_home for '%s'" % (unicode(create_user)))
            srv_com = server_command.srv_command(command="create_user_home")
            srv_com["server_key:username"] = create_user.login
            _result = contact_server(request, "tcp://localhost:8004", srv_com, timeout=30)
        # check for configs, can be optimised ?
        if config_tools.server_check(server_type="ldap_server").effective_device:
            srv_com = server_command.srv_command(command="sync_ldap_config")
            _result = contact_server(request, "tcp://localhost:8004", srv_com, timeout=30)
        if config_tools.server_check(server_type="yp_server").effective_device:
            srv_com = server_command.srv_command(command="write_yp_config")
            _result = contact_server(request, "tcp://localhost:8004", srv_com, timeout=30)
        srv_com = server_command.srv_command(command="sync_http_users")
        _result = contact_server(request, "tcp://localhost:8010", srv_com)

# class get_password_form(View):
#     @method_decorator(login_required)
#     @method_decorator(xml_wrapper)
#     def post(self, request):
#         request.xml_response["form"] = render_string(
#             request,
#             "crispy_form.html",
#             {
#                 "form" : dummy_password_form()
#             }
#         )

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
                    # try to get var from DB
                    try:
                        user_vars[key] = user_variable.objects.get(Q(name=key) & Q(user=request.user))
                    except user_variable.DoesNotExist:
                        user_vars[key] = user_variable.objects.create(
                            user=request.user,
                            name=key,
                            value=value)
                    else:
                        user_vars[key].value = value
                        user_vars[key].save()
        update_session_object(request)
        request.session.save()

class set_user_var(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        user_vars = request.session["user_vars"]
        key, value = (_post["key"], _post["value"])
        v_type = _post.get("type", "unicode")
        if v_type == "unicode":
            value = unicode(value)
        elif v_type == "str":
            value = str(value)
        elif v_type == "int":
            value = int(value)
        elif v_type == "bool":
            value = True if value.lower() in ["true"] else False
        logger.info("setting user_var '%s' to '%s' (type %s)" % (
            key,
            str(value),
            v_type,
            ))
        if key in user_vars:
            if user_vars[key].value != value:
                user_vars[key].value = value
                user_vars[key].save()
        else:
            user_vars[key] = user_variable.objects.create(
                user=request.user,
                name=key,
                value=value)
        update_session_object(request)
        request.session.save()

class get_user_var(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        var_name = request.POST["var_name"]
        if var_name.endswith("*"):
            found_uv = [key for key in request.session["user_vars"] if key.startswith(var_name[:-1])]
        else:
            found_uv = [key for key in request.session["user_vars"] if key == var_name]
        user_vars = [request.session["user_vars"][key] for key in found_uv]
        request.xml_response["result"] = E.user_variables(
            *[
                E.user_variable(unicode(cur_var.value), name=cur_var.name, type=cur_var.var_type) for cur_var in user_vars
                ]
            )


class move_node(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        if _post["dst_id"] == "top":
            dst_group = None
        else:
            dst_group = group.objects.get(Q(pk=_post["dst_id"].split("__")[1]))
        if _post["src_id"].startswith("user_"):
            cur_user = user.objects.get(Q(pk=_post["src_id"].split("__")[1]))
            cur_user.group = dst_group
            cur_user.save()
            request.xml_response.info("user %s moved to group %s" % (
                unicode(cur_user),
                unicode(dst_group)), logger)
        else:
            cur_group = group.objects.get(Q(pk=_post["src_id"].split("__")[1]))
            cur_group.parent_group = dst_group
            cur_group.save()
            request.xml_response.info("group %s moved to %s" % (
                unicode(cur_group),
                u"group %s" % (unicode(dst_group)) if dst_group else "top"), logger)

class group_detail(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def get(self, request):
        new_form = group_detail_form(
            auto_id="group__new__%s",
        )
        new_form.create_mode()
        request.xml_response["form"] = render_string(
            request,
            "crispy_form.html",
            {
                "form" : new_form,
            }
        )
        return request.xml_response.create_response()
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        if "key" in _post:
            key, mode = (_post["key"], _post["mode"])
            if mode == "show":
                cur_group = group.objects.get(Q(pk=key.split("__")[1]))
                if request.user.has_object_perm("backbone.group_admin", cur_group):
                    new_form = group_detail_form(
                        auto_id="group__%d__%%s" % (cur_group.pk),
                        instance=cur_group,
                    )
                    new_form.delete_mode()
                    request.xml_response["form"] = render_string(
                        request,
                        "crispy_form.html",
                        {
                            "form" : new_form
                        }
                    )
                else:
                    request.xml_response.error("not enough rights to show group", logger)
            else:
                del_obj = group.objects.get(Q(pk=key.split("__")[1]))
                if del_obj == request.user.group:
                    request.xml_response.error("cannot delete your group", logger)
                else:
                    num_ref = get_related_models(del_obj)
                    if num_ref:
                        # pprint.pprint(get_related_models(del_obj, detail=True))
                        request.xml_response.error(
                            "cannot delete %s '%s': %s" % (
                                del_obj._meta.object_name,
                                unicode(del_obj),
                                logging_tools.get_plural("reference", num_ref)), logger)
                    else:
                        del_info = unicode(del_obj)
                        del_obj.delete()
                        request.xml_response.info("deleted %s '%s'" % (del_obj._meta.object_name, del_info), logger)
        else:
            cur_form = group_detail_form(_post, auto_id="group__new__%s")
            new_group = None
            if cur_form.is_valid():
                try:
                    new_group = cur_form.save()
                except:
                    line = process_tools.get_except_info()
                    request.xml_response.error(line, logger)
                else:
                    request.xml_response.info("created new group '%s'" % (unicode(new_group)))
            else:
                line = ", ".join(cur_form.errors.as_text().split("\n"))
                request.xml_response.error(line, logger)
            if not new_group:
                request.xml_response["error_form"] = render_string(
                    request,
                    "crispy_form.html",
                    {
                        "form" : cur_form
                    }
                )

class user_detail(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def get(self, request):
        new_form = user_detail_form(
            auto_id="user__new__%s",
            request=request,
        )
        new_form.create_mode()
        request.xml_response["form"] = render_string(
            request,
            "crispy_form.html",
            {
                "form" : new_form,
            }
        )
        return request.xml_response.create_response()
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        if "key" in _post:
            key, mode = (_post["key"], _post["mode"])
            if mode == "show":
                cur_user = user.objects.get(Q(pk=key.split("__")[1]))
                if request.user.has_object_perm("backbone.group_admin", cur_user.group):
                    new_form = user_detail_form(
                        auto_id="user__%d__%%s" % (cur_user.pk),
                        instance=cur_user,
                        request=request,
                    )
                    new_form.delete_mode()
                    request.xml_response["form"] = render_string(
                        request,
                        "crispy_form.html",
                        {
                            "form" : new_form
                        }
                    )
                else:
                    request.xml_response.error("not enough rights to show user", logger)
            else:
                del_obj = user.objects.get(Q(pk=key.split("__")[1]))
                if del_obj == request.user:
                    request.xml_response.error("cannot delete yourself", logger)
                else:
                    num_ref = get_related_models(del_obj)
                    if num_ref:
                        # pprint.pprint(get_related_models(del_obj, detail=True))
                        request.xml_response.error(
                            "cannot delete %s '%s': %s" % (
                                del_obj._meta.object_name,
                                unicode(del_obj),
                                logging_tools.get_plural("reference", num_ref)), logger)
                    else:
                        del_info = unicode(del_obj)
                        del_obj.delete()
                        request.xml_response.info("deleted %s '%s'" % (del_obj._meta.object_name, del_info), logger)
        else:
            cur_form = user_detail_form(
                _post,
                auto_id="user__new__%s",
                request=request,
                )
            new_user = None
            if cur_form.is_valid():
                try:
                    new_user = cur_form.save()
                except:
                    line = process_tools.get_except_info()
                    request.xml_response.error(line, logger)
                else:
                    request.xml_response.info("created new user '%s'" % (unicode(new_user)))
            else:
                line = ", ".join(cur_form.errors.as_text().split("\n"))
                request.xml_response.error(line, logger)
            if not new_user:
                request.xml_response["error_form"] = render_string(
                    request,
                    "crispy_form.html",
                    {
                        "form" : cur_form
                    }
                )

class change_object_permission(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        import pprint
        pprint.pprint(_post)
        if "auth_type" in _post:
            auth_pk = int(_post["auth_pk"])
            auth_obj = {"g" : group, "u" : user}[_post["auth_type"]].objects.get(Q(pk=auth_pk))
            set_perm = csw_permission.objects.select_related("content_type").get(Q(pk=_post["csw_idx"]))
            obj_pk = int(_post["obj_idx"])
            add = True if int(_post["set"]) else False
            print "***", add
        else:
            key = _post["key"]
            obj_pk, perm_pk = key.split("__")[1:3]
            auth_type, auth_pk = _post["auth_key"].split("__")
            if auth_type == "group":
                auth_obj = group.objects.get(Q(pk=auth_pk))
            else:
                auth_obj = user.objects.get(Q(pk=auth_pk))
            set_perm = csw_permission.objects.select_related("content_type").get(Q(pk=perm_pk))
            add = True if int(_post["selected"]) else False
        perm_model = get_model(set_perm.content_type.app_label, set_perm.content_type.name).objects.get(Q(pk=obj_pk))
        # print perm_model, auth_obj, set_perm
        if add:
            if not auth_obj.has_object_perm(set_perm, perm_model, ask_parent=False):
                # check if object_permission exists
                try:
                    csw_objp = csw_object_permission.objects.get(
                        csw_permission=set_perm,
                        object_pk=perm_model.pk,
                        )
                except csw_object_permission.DoesNotExist:
                    csw_objp = csw_object_permission.objects.create(
                        csw_permission=set_perm,
                        object_pk=perm_model.pk,
                        )
                    logger.info("created new csw_object_permission %s" % (unicode(csw_objp)))
                auth_obj.object_permissions.add(csw_objp)
                logger.info("added csw_object_permission %s to %s" % (
                    unicode(csw_objp),
                    unicode(auth_obj),
                    ))
            else:
                # print "there"
                pass
        else:
            if auth_obj.has_object_perm(set_perm, perm_model, ask_parent=False):
                try:
                    csw_objp = csw_object_permission.objects.get(Q(
                        csw_permission=set_perm,
                        object_pk=perm_model.pk
                        ))
                except csw_object_permission.MultipleObjectsReturned:
                    logger.critical("multiple objects returned for csw_object_permission (perm=%s, pk=%d)" % (
                        unicode(set_perm),
                        perm_model.pk,
                        ))
                    csw_object_permission.objects.filter(Q(
                        csw_permission=set_perm,
                        object_pk=perm_model.pk
                        )).delete()
                else:
                    auth_obj.object_permissions.remove(csw_objp)
                    logger.info("removed csw_object_permission %s to %s" % (
                        unicode(csw_objp),
                        unicode(auth_obj),
                        ))
            else:
                # print "not there"
                pass

class account_info(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def get(self, request):
        cur_user = request.user
        cur_form = account_detail_form(
            instance=cur_user,
            auto_id="user__%d__%%s" % (cur_user.pk),
        )
        return render_me(request, "account_info.html", {
            "form" : cur_form,
            "user" : cur_user,
            })()
