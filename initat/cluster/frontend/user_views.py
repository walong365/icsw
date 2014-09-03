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

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.apps import apps
from django.utils.decorators import method_decorator
from django.views.generic import View
from initat.cluster.backbone.models import group, user, user_variable, csw_permission, \
    csw_object_permission, group_permission, user_permission, group_object_permission, \
    user_object_permission
from initat.cluster.backbone.serializers import group_object_permission_serializer, user_object_permission_serializer
from initat.cluster.backbone.render import permission_required_mixin, render_me
from initat.cluster.frontend.forms import group_detail_form, user_detail_form, \
    account_detail_form, global_settings_form
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper, update_session_object
from lxml.builder import E  # @UnresolvedImport
import json
import config_tools
import logging
import server_command

logger = logging.getLogger("cluster.user")


class overview(permission_required_mixin, View):
    any_required_permissions = (
        "backbone.user.admin",
        "backbone.group.group_admin"
    )

    @method_decorator(login_required)
    def get(self, request, *args, **kwargs):
        return render_me(request, "user_overview_tree.html", {
            "group_detail_form": group_detail_form(),
            "user_detail_form": user_detail_form(),
            })()


class sync_users(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        # create homedirs
        create_user_list = user.objects.exclude(Q(export=None)).filter(Q(home_dir_created=False) & Q(active=True) & Q(group__active=True)).select_related("export__device")
        logger.info("user homes to create: %d" % (len(create_user_list)))
        for create_user in create_user_list:
            logger.info(
                "trying to create user_home for '{}' on server {}".format(
                    unicode(create_user),
                    create_user.export.device.full_name,
                )
            )
            srv_com = server_command.srv_command(command="create_user_home")
            srv_com["server_key:username"] = create_user.login
            _result = contact_server(request, "server", srv_com, timeout=30, target_server_id=create_user.export.device_id)
        # check for configs, can be optimised ?
        if config_tools.server_check(server_type="ldap_server").effective_device:
            srv_com = server_command.srv_command(command="sync_ldap_config")
            _result = contact_server(request, "server", srv_com, timeout=30)
        if config_tools.server_check(server_type="yp_server").effective_device:
            srv_com = server_command.srv_command(command="write_yp_config")
            _result = contact_server(request, "server", srv_com, timeout=30)
        if config_tools.server_check(server_type="md-config").effective_device:
            srv_com = server_command.srv_command(command="sync_http_users")
            _result = contact_server(request, "md-config", srv_com)


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


class change_object_permission(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        auth_pk = int(_post["auth_pk"])
        auth_obj = {"g": group, "u": user}[_post["auth_type"]].objects.get(Q(pk=auth_pk))
        set_perm = csw_permission.objects.select_related("content_type").get(Q(pk=_post["csw_idx"]))
        obj_pk = int(_post["obj_idx"])
        add = True if int(_post["set"]) else False
        level = int(_post["level"])
        perm_model = apps.get_model(set_perm.content_type.app_label, set_perm.content_type.name).objects.get(Q(pk=obj_pk))
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
                if auth_obj._meta.model_name == "user":
                    new_obj = user_object_permission.objects.create(user=auth_obj, csw_object_permission=csw_objp, level=level)
                    new_obj.date = 0
                    request.xml_response["new_obj"] = json.dumps(user_object_permission_serializer(new_obj).data)
                else:
                    new_obj = group_object_permission.objects.create(group=auth_obj, csw_object_permission=csw_objp, level=level)
                    new_obj.date = 0
                    request.xml_response["new_obj"] = json.dumps(group_object_permission_serializer(new_obj).data)
                logger.info("added csw_object_permission %s to %s" % (
                    unicode(csw_objp),
                    unicode(auth_obj),
                    ))
            else:
                logger.info("permission '%s' for '%s' already set" % (unicode(set_perm), unicode(perm_model)))
        else:
            if auth_obj.has_object_perm(set_perm, perm_model, ask_parent=False):
                try:
                    csw_objp = csw_object_permission.objects.get(Q(
                        csw_permission=set_perm,
                        object_pk=perm_model.pk
                        ))
                except csw_object_permission.MultipleObjectsReturned:
                    logger.critical("multiple objects returned for csw_object_permission (perm=%s, pk=%d, auth_obj=%s)" % (
                        unicode(set_perm),
                        perm_model.pk,
                        unicode(auth_obj),
                        ))
                    csw_object_permission.objects.filter(Q(
                        csw_permission=set_perm,
                        object_pk=perm_model.pk
                        )).delete()
                except csw_object_permission.DoesNotExist:
                    logger.error("csw_object_permission doest not exist (perm=%s, pk=%d, auth_obj=%s)" % (
                        unicode(set_perm),
                        perm_model.pk,
                        unicode(auth_obj),
                        ))
                else:
                    if auth_obj._meta.model_name == "user":
                        user_object_permission.objects.filter(Q(csw_object_permission=csw_objp) & Q(user=auth_obj)).delete()
                    else:
                        group_object_permission.objects.filter(Q(csw_object_permission=csw_objp) & Q(group=auth_obj)).delete()
                    logger.info("removed csw_object_permission %s from %s" % (
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
        return render_me(
            request, "account_info.html", {
                "form": cur_form,
                "user": cur_user,
            }
        )()


class global_settings(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def get(self, request):
        return render_me(request, "global_settings.html", {
            "form": global_settings_form()
            })()


class background_job_info(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def get(self, request):
        return render_me(request, "background_job_info.html", {
            })()


class clear_home_dir_created(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        user_pk = int(_post["user_pk"])
        cur_user = user.objects.get(Q(pk=user_pk))
        cur_user.home_dir_created = False
        cur_user.save(update_fields=["home_dir_created"])
