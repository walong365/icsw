#!/usr/bin/python -Ot
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2016 Andreas Lang-Nevyjel
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

import json
import logging

from django.apps import apps
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http.response import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View
from lxml.builder import E
from rest_framework.generics import RetrieveAPIView
from rest_framework.response import Response

from initat.cluster.backbone import routing
from initat.cluster.backbone.license_file_reader import LicenseFileReader
from initat.cluster.backbone.models import group, user, user_variable, csw_permission, \
    csw_object_permission, group_object_permission, user_object_permission, device, License, device_variable
from initat.cluster.backbone.models.functions import db_t2000_limit
from initat.cluster.backbone.serializers import group_object_permission_serializer, user_object_permission_serializer
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper
from initat.cluster.frontend.license_views import login_required_rest
from initat.cluster.frontend.rest_views import rest_logging
from initat.server_version import VERSION_STRING, VERSION_MAJOR, BUILD_MACHINE
from initat.tools import config_tools, server_command

logger = logging.getLogger("cluster.user")


class get_num_quota_servers(View):
    def post(self, request):
        _num = device.objects.filter(Q(device_config__config__name="quota_scan")).count()
        return HttpResponse(json.dumps({"num_quota_servers": _num}), content_type="application/json")


class sync_users(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        # create homedirs
        create_user_list = user.objects.exclude(
            Q(export=None)
        ).filter(
            Q(home_dir_created=False) & Q(active=True) & Q(group__active=True)
        ).select_related("export__device")
        logger.info("user homes to create: {:d}".format(len(create_user_list)))
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
        # force sync_users
        request.user.save()
        if config_tools.server_check(server_type="monitor_server").effective_device:
            srv_com = server_command.srv_command(command="sync_http_users")
            _result = contact_server(request, "md-config", srv_com)


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
        logger.info(
            "setting user_var '{}' to '{}' (type {})".format(
                key,
                str(value),
                v_type,
            )
        )
        if key in user_vars:
            if user_vars[key].value != value:
                user_vars[key].value = value
                user_vars[key].save()
        else:
            user_vars[key] = user_variable.objects.create(
                user=request.user,
                name=key,
                value=value
            )
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
                E.user_variable(
                    unicode(cur_var.value),
                    name=cur_var.name,
                    type=cur_var.var_type
                ) for cur_var in user_vars
            ]
        )


class change_object_permission(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        auth_pk = int(_post["auth_pk"])
        auth_obj = {
            "g": group,
            "u": user
        }[_post["auth_type"]].objects.get(Q(pk=auth_pk))
        set_perm = csw_permission.objects.select_related("content_type").get(Q(pk=_post["csw_idx"]))
        obj_pk = int(_post["obj_idx"])
        add = True if int(_post["set"]) else False
        level = int(_post["level"])
        perm_model = apps.get_model(
            set_perm.content_type.app_label,
            set_perm.content_type.model_class().__name__
        ).objects.get(Q(pk=obj_pk))
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
                    request.xml_response.info(
                        "created new csw_object_permission {}".format(unicode(csw_objp)),
                        logger=logger
                    )
                if auth_obj._meta.model_name == "user":
                    new_obj = user_object_permission.objects.create(
                        user=auth_obj,
                        csw_object_permission=csw_objp,
                        level=level
                    )
                    request.xml_response["new_obj"] = json.dumps(user_object_permission_serializer(new_obj).data)
                else:
                    new_obj = group_object_permission.objects.create(
                        group=auth_obj,
                        csw_object_permission=csw_objp,
                        level=level
                    )
                    request.xml_response["new_obj"] = json.dumps(group_object_permission_serializer(new_obj).data)
                request.xml_response.info(
                    "added csw_object_permission {} to {}".format(
                        unicode(csw_objp),
                        unicode(auth_obj),
                    ),
                    logger=logger
                )
            else:
                request.xml_response.warn(
                    "permission '{}' for '{}' already set".format(
                        unicode(set_perm),
                        unicode(perm_model)
                    ),
                    logger=logger
                )
        else:
            if auth_obj.has_object_perm(set_perm, perm_model, ask_parent=False):
                try:
                    csw_objp = csw_object_permission.objects.get(
                        Q(
                            csw_permission=set_perm,
                            object_pk=perm_model.pk
                        )
                    )
                except csw_object_permission.MultipleObjectsReturned:
                    request.xml_response.critical(
                        "multiple objects returned for csw_object_permission (perm=%s, pk=%d, auth_obj=%s)" % (
                            unicode(set_perm),
                            perm_model.pk,
                            unicode(auth_obj),
                        ),
                        logger=logger
                    )
                    csw_object_permission.objects.filter(
                        Q(
                            csw_permission=set_perm,
                            object_pk=perm_model.pk
                        )
                    ).delete()
                except csw_object_permission.DoesNotExist:
                    request.xml_response.error(
                        "csw_object_permission doest not exist (perm={}, pk={:d}, auth_obj={})".format(
                            unicode(set_perm),
                            perm_model.pk,
                            unicode(auth_obj),
                        ),
                        logger=logger
                    )
                else:
                    if auth_obj._meta.model_name == "user":
                        user_object_permission.objects.filter(Q(csw_object_permission=csw_objp) & Q(user=auth_obj)).delete()
                    else:
                        group_object_permission.objects.filter(Q(csw_object_permission=csw_objp) & Q(group=auth_obj)).delete()
                    request.xml_response.info(
                        "removed csw_object_permission {} from {}".format(
                            unicode(csw_objp),
                            unicode(auth_obj),
                        ),
                        logger=logger
                    )
            else:
                # print "not there"
                pass


class upload_license_file(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        lic_file = request.FILES['license_file']
        lic_file_content = lic_file.read()

        try:
            reader = LicenseFileReader(lic_file_content)
        except LicenseFileReader.InvalidLicenseFile as e:
            request.xml_response.error(unicode(e), logger=logger)
        else:
            try:
                if db_t2000_limit():
                    # lic file content is encoded bz2, so we are safe ...
                    if len(lic_file_content) > 2000:
                        License.objects.get(Q(license_file__startswith=lic_file_content[:2000]))
                    else:
                        License.objects.get(license_file=lic_file_content)
                else:
                    # sane database
                    # check based on content, not filename
                    License.objects.get(license_file=lic_file_content)
            except License.DoesNotExist:

                local_cluster_id = device_variable.objects.get_cluster_id()
                file_cluster_ids = reader.get_referenced_cluster_ids()
                if local_cluster_id not in file_cluster_ids:
                    msg = u"This license file contains licenses for the following clusters: {}.".\
                        format(", ".join(file_cluster_ids))
                    msg += "\nThis cluster has the id {}.".format(local_cluster_id)
                    request.xml_response.error(msg)
                else:
                    License(file_name=lic_file.name, license_file=lic_file_content).save()
                    request.xml_response.info("Successfully uploaded license file")

                    srv_com = server_command.srv_command(command="check_license_violations")
                    contact_server(request, "server", srv_com, timeout=60, log_error=True, log_result=False)
            else:
                request.xml_response.warn("This license file has already been uploaded")


class clear_home_dir_created(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        user_pk = int(_post["user_pk"])
        cur_user = user.objects.get(Q(pk=user_pk))
        cur_user.home_dir_created = False
        cur_user.save(update_fields=["home_dir_created"])


class get_device_ip(View):
    '''
    Retrieves ip address to communicate to from local device
    '''
    @method_decorator(login_required)
    def post(self, request):
        _post = request.POST
        to_dev_pk = int(_post["device"])
        to_dev = device.objects.prefetch_related(
            "netdevice_set__net_ip_set__network__network_type"
        ).get(
            Q(pk=to_dev_pk)
        )

        # from-device is where virtual desktop client config is set
        server_by_type = config_tools.server_check(server_type="virtual_desktop_client")
        from_dev = server_by_type.effective_device

        if from_dev is None:
            # fall back to local device
            cur_routing = routing.SrvTypeRouting(force=True)
            from_dev = cur_routing.local_device

        from_server_check = config_tools.server_check(device=from_dev, config=None, server_type="node")
        to_server_check = config_tools.server_check(device=to_dev, config=None, server_type="node")

        # calc route to it and use target ip
        _router = config_tools.router_object(logger)
        route = from_server_check.get_route_to_other_device(_router, to_server_check, allow_route_to_other_networks=True, prefer_production_net=True)

        if route:
            ip = route[0][3][1][0]
        else:
            ip = "127.0.0.1"  # try fallback (it might not work, but it will not make things more broken)

        return HttpResponse(json.dumps({"ip": ip}), content_type="application/json")


class GetGlobalPermissions(RetrieveAPIView):
    @staticmethod
    def _unfold(in_dict):
        # provide perms as "backbone.user.modify_tree: 0" as well as as "backbone { user { modify_tree: 0 } }"
        _keys = in_dict.keys()
        # unfold dictionary
        for _key in _keys:
            _parts = _key.split(".")
            in_dict.setdefault(_parts[0], {}).setdefault(_parts[1], {})[_parts[2]] = in_dict[_key]
        in_dict["__authenticated"] = True
        return in_dict

    @method_decorator(login_required_rest(lambda: {"__authenticated": False}))
    @rest_logging
    def get(self, request, *args, **kwargs):
        return Response(self._unfold(request.user.get_global_permissions()))


class GetObjectPermissions(RetrieveAPIView):
    @method_decorator(login_required_rest(lambda: {"__authenticated": False}))
    @rest_logging
    def get(self, request, *args, **kwargs):
        return Response(GetGlobalPermissions._unfold(request.user.get_all_object_perms(None)))


class GetInitProduct(RetrieveAPIView):
    @rest_logging
    def get(self, request, *args, **kwargs):
        product = License.objects.get_init_product()
        family = product.get_version_family(VERSION_MAJOR)
        return Response(
            {
                'name': product.name,
                'version': VERSION_STRING,
                'family': family,
                "build_machine": BUILD_MACHINE,
            }
        )
