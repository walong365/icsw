#!/usr/bin/python -Ot
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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
from rest_framework import viewsets
from rest_framework.generics import RetrieveAPIView
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter

from initat.cluster.backbone import routing
from initat.cluster.backbone.models import group, user, user_variable, csw_permission, \
    csw_object_permission, group_object_permission, user_object_permission, device, License
from initat.cluster.backbone.serializers import user_variable_serializer
from initat.cluster.backbone.server_enums import icswServiceEnum
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper
from initat.cluster.frontend.license_views import login_required_rest
from initat.cluster.frontend.rest_views import rest_logging
from initat.tools import config_tools, server_command

logger = logging.getLogger("cluster.user")

# local router for local REST urls
local_router = DefaultRouter()


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
                    str(create_user),
                    create_user.export.device.full_name,
                )
            )
            srv_com = server_command.srv_command(command="create_user_home")
            srv_com["server_key:username"] = create_user.login
            _result = contact_server(
                request,
                icswServiceEnum.cluster_server,
                srv_com,
                timeout=30,
                target_server_id=create_user.export.device_id
            )
        # force sync_users
        request.user.save()
        if config_tools.icswServerCheck(service_type_enum=icswServiceEnum.monitor_server).effective_device:
            srv_com = server_command.srv_command(command="sync_http_users")
            _result = contact_server(request, icswServiceEnum.monitor_server, srv_com)


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
                        "created new csw_object_permission {}".format(str(csw_objp)),
                        logger=logger
                    )
                if auth_obj._meta.model_name == "user":
                    new_obj = user_object_permission.objects.create(
                        user=auth_obj,
                        csw_object_permission=csw_objp,
                        level=level
                    )
                    request.xml_response["new_obj"] = json.dumps(
                        user_object_permission_serializer(new_obj).data
                    )
                else:
                    new_obj = group_object_permission.objects.create(
                        group=auth_obj,
                        csw_object_permission=csw_objp,
                        level=level
                    )
                    request.xml_response["new_obj"] = json.dumps(
                        group_object_permission_serializer(new_obj).data
                    )
                request.xml_response.info(
                    "added csw_object_permission {} to {}".format(
                        str(csw_objp),
                        str(auth_obj),
                    ),
                    logger=logger
                )
            else:
                request.xml_response.warn(
                    "permission '{}' for '{}' already set".format(
                        str(set_perm),
                        str(perm_model)
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
                            str(set_perm),
                            perm_model.pk,
                            str(auth_obj),
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
                            str(set_perm),
                            perm_model.pk,
                            str(auth_obj),
                        ),
                        logger=logger
                    )
                else:
                    if auth_obj._meta.model_name == "user":
                        user_object_permission.objects.filter(
                            Q(csw_object_permission=csw_objp) & Q(user=auth_obj)
                        ).delete()
                    else:
                        group_object_permission.objects.filter(
                            Q(csw_object_permission=csw_objp) & Q(group=auth_obj)
                        ).delete()
                    request.xml_response.info(
                        "removed csw_object_permission {} from {}".format(
                            str(csw_objp),
                            str(auth_obj),
                        ),
                        logger=logger
                    )
            else:
                # print "not there"
                pass


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
    """
    Retrieves ip address to communicate to from local device
    unly used in dashboard.coffee for icswUserVduOverview

    """
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
        server_by_type = config_tools.icswServerCheck(
            service_type_enum=icswServiceEnum.virtual_desktop_client
        )
        from_dev = server_by_type.effective_device

        if from_dev is None:
            # fall back to local device
            cur_routing = routing.SrvTypeRouting(force=True)
            from_dev = cur_routing.local_device

        from_server_check = config_tools.icswServerCheck(
            device=from_dev,
            config=None
        )
        to_server_check = config_tools.icswServerCheck(
            device=to_dev,
            config=None,
        )

        # calc route to it and use target ip
        _router = config_tools.RouterObject(logger)
        route = from_server_check.get_route_to_other_device(
            _router,
            to_server_check,
            allow_route_to_other_networks=True,
            prefer_production_net=True
        )

        if route:
            ip = route[0][3][1][0]
        else:
            ip = "127.0.0.1"  # try fallback (it might not work, but it will not make things more broken)

        return HttpResponse(json.dumps({"ip": ip}), content_type="application/json")


class GetGlobalPermissions(RetrieveAPIView):
    @staticmethod
    def _unfold(in_dict):
        # provide perms as "backbone.user.modify_tree: 0" as well as as "backbone { user { modify_tree: 0 } }"
        _keys = list(in_dict.keys())
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


class UserVariableViewSet(viewsets.ModelViewSet):
    queryset = user_variable.objects.all()
    serializer_class = user_variable_serializer

    def post(self, request):
        print("-" * 20)
        cur_var = self.get_object()
        print("**", cur_var)
        print("*", request.data)
        _var = user_variable.objects.get(pk=1)
        serializer = user_variable_serializer(_var)
        return Response(serializer.data)


local_router.register("user_variable_new", UserVariableViewSet)
