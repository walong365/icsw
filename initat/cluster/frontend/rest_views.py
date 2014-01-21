#!/usr/bin/python -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2014 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
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

""" REST views """

from django.contrib.contenttypes.models import ContentType
from django.db.models import get_model, Q
from initat.cluster.backbone import models
from initat.cluster.backbone.models import user , group, user_serializer_h, group_serializer_h, \
     get_related_models, get_change_reset_list, device, device_serializer, \
     device_serializer_package_state, device_serializer_monitoring, domain_name_tree, \
     device_serializer_monitor_server, category_tree, device_serializer_cat, device_selection, \
     device_selection_serializer, partition_table_serializer_save, partition_disc_serializer_save, \
     partition_disc_serializer_create, device_serializer_variables, device_serializer_device_configs, \
     device_config, device_config_hel_serializer, home_export_list, csw_permission, \
     device_serializer_disk_info
from rest_framework import mixins, generics, status, viewsets, serializers
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import exception_handler, APIView
import json
import logging
import logging_tools
import operator
import process_tools
import sys
import time
import types

logger = logging.getLogger("cluster.rest")

# build REST_LIST from models content
REST_LIST = []
for key in dir(models):
    if key.endswith("_serializer") and key not in ["device_selection_serializer"]:
        REST_LIST.append("_".join(key.split("_")[:-1]))

@api_view(('GET',))
def api_root(request, format=None):
    return Response({
        'user'         : reverse('rest:user_list_h', request=request),
        'group'        : reverse('rest:group_list_h', request=request),
        # 'network_type' : reverse('rest:network_type_list_h', request=request),
    })

def csw_exception_handler(exc):
    response = exception_handler(exc)
    if response is None:
        detail_str, detail_info = (exc.__class__.__name__, [])
        if hasattr(exc, "messages"):
            detail_info.extend([unicode(_part) for _part in exc.messages])
        if hasattr(exc, "message"):
            detail_info.append(unicode(exc.message))
        if hasattr(exc, "args"):
            for entry in exc.args:
                detail_info.append(unicode(entry))
        detail_info = list(set([_entry for _entry in [_part.strip() for _part in detail_info if _part.strip()] if _entry not in ["()"]]))
        response = Response(
            {
                "detail" : "%s%s" % (
                    detail_str,
                    " (%s)" % (", ".join(detail_info)) if detail_info else ""
                ),
            },
            status=status.HTTP_406_NOT_ACCEPTABLE,
        )
    return response

class rest_logging(object):
    def __init__(self, func):
        self._func = func
        self.__name__ = self._func.__name__
        self.__obj_name = None
    def __get__(self, obj, owner_class=None):
        # magic ...
        return types.MethodType(self, obj)
    def log(self, what="", log_level=logging_tools.LOG_LEVEL_OK):
        logger.log(log_level, "[%s%s] %s" % (
            self.__name__,
            " %s" % (self.__obj_name) if self.__obj_name else "",
            what))
    def __call__(self, *args, **kwargs):
        s_time = time.time()
        if hasattr(args[0], "model"):
            self.__obj_name = args[0].model._meta.object_name
        else:
            self.__obj_name = getattr(args[0], "display_name", "unknown")
        try:
            result = self._func(*args, **kwargs)
        except:
            self.log("exception: %s" % (
                process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
            exc_info = process_tools.exception_info()
            for line in exc_info.log_lines:
                self.log("  %s" % (line))
            raise
        e_time = time.time()
        self.log("call took %s" % (
            logging_tools.get_diff_time_str(e_time - s_time)))
        return result

class detail_view(mixins.RetrieveModelMixin,
                  mixins.UpdateModelMixin,
                  mixins.DestroyModelMixin,
                  generics.SingleObjectAPIView):
    @rest_logging
    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)
    @rest_logging
    def get_serializer_class(self):
        if self.model._meta.object_name == "partition_table":
            return partition_table_serializer_save
        if self.model._meta.object_name == "partition_disc":
            return partition_disc_serializer_save
        else:
            return self.serializer_class
    # def get_serializer(self, instance=None, data=None,
    #                   files=None, many=False, partial=False):
    #    """
    #    Return the serializer instance that should be used for validating and
    #    deserializing input, and for serializing output.
    #    """
    #    serializer_class = self.get_serializer_class()
    #    context = self.get_serializer_context()
    #    return serializer_class(instance, data=data, files=files,
    #                            many=many, partial=partial, context=context, allow_add_remove=self.model._meta.object_name in ["config"])
    @rest_logging
    def put(self, request, *args, **kwargs):
        req_changes = request.DATA
        prev_model = self.model.objects.get(Q(pk=kwargs["pk"]))
        # try:
        resp = self.update(request, *args, **kwargs)
        # except ValidationError as cur_exc:
        #    print cur_exc
        # print dir(resp), resp.data
        new_model = self.model.objects.get(Q(pk=kwargs["pk"]))
        c_list, r_list = get_change_reset_list(prev_model, new_model, req_changes)
        # print c_list, r_list
        resp.data["_change_list"] = c_list
        resp.data["_reset_list"] = r_list
        return resp
    @rest_logging
    def delete(self, request, *args, **kwargs):
        # just be careful
        cur_obj = self.model.objects.get(Q(pk=kwargs["pk"]))
        ignore_objs = {"device_group" : list(device.objects.filter(Q(device_group=kwargs["pk"]) & Q(device_type__identifier="MD")))}.get(self.model._meta.object_name, [])
        num_refs = get_related_models(cur_obj, ignore_objs=ignore_objs)
        if num_refs:
            raise ValueError("cannot delete %s: referenced %s" % (
                self.model._meta.object_name,
                logging_tools.get_plural("time", num_refs)))
        else:
            return self.destroy(request, *args, **kwargs)
            # it makes no sense to return something meaningfull because the DestroyModelMixin returns
            # a 204 status on successfull deletion
            # print "****", "del"
            # print unicode(cur_obj), resp.data
            # if not resp.data:
            #    resp.data = {}
            # resp.data["_messages"] = [u"deleted '%s'" % (unicode(cur_obj))]
            # return resp

class list_view(mixins.ListModelMixin,
                mixins.CreateModelMixin,
                generics.MultipleObjectAPIView):
    @rest_logging
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)
    @rest_logging
    def post(self, request, *args, **kwargs):
        resp = self.create(request, *args, **kwargs)
        if resp.status_code in [200, 201, 202, 203]:
            resp.data["_messages"] = [u"created '%s'" % (unicode(self.object))]
        return resp
    @rest_logging
    def get_serializer_class(self):
        if self.request.method == "POST":
            if self.model._meta.object_name == "partition_disc":
                return partition_disc_serializer_create
        return self.serializer_class
    @rest_logging
    def get_queryset(self):
        model_name = self.model._meta.model_name
        if model_name == "domain_tree_node":
            return domain_name_tree()
        elif model_name == "category":
            return category_tree(with_ref_count=True)
        related_fields, prefetch_fields = {
            "kernel" : ([], ["initrd_build_set", "kernel_build_set", "new_kernel", "act_kernel"]),
            "image" : ([], ["new_image", "act_image"]),
            "partition_table" : ([], ["new_partition_table", "act_partition_table", "sys_partition_set",
                "lvm_lv_set__partition_fs" , "lvm_vg_set", "partition_disc_set__partition_set__partition_fs"]),
            "mon_period" : ([], ["service_check_period"]),
            "device" : (["domain_tree_node", "device_type", "device_group"], []),
            "mon_check_command" : ([], ["exclude_devices", "categories"]),
            "mon_host_cluster" : ([], ["devices"]),
            "network" : ([], ["network_device_type"]),
            "user" : (["group"], ["permissions", "secondary_groups", "object_permissions", "allowed_device_groups"]),
            "group" : (["parent_group"], ["permissions", "object_permissions", "allowed_device_groups"]),
            "config" : ([], [
                "categories", "config_str_set", "config_int_set", "config_blob_set",
                "config_bool_set", "config_script_set", "mon_check_command_set__categories", "mon_check_command_set__exclude_devices",
                "device_config_set"]),
            }.get(model_name, ([], []))
        res = self.model.objects.all()
        filter_list = []
        for key, value in self.request.QUERY_PARAMS.iteritems():
            filter_list.append(Q(**{key : value}))
        if filter_list:
            res = res.filter(reduce(operator.iand, filter_list))
        return res.select_related(*related_fields).prefetch_related(*prefetch_fields)

class device_tree_detail(detail_view):
    model = device
    def _get_post_boolean(self, name, default):
        if name in self.request.QUERY_PARAMS:
            p_val = self.request.QUERY_PARAMS[name]
            if p_val.lower() in ["1", "true"]:
                return True
            else:
                return False
        else:
            return default
    @rest_logging
    def get_serializer_class(self):
        if self._get_post_boolean("tree_mode", False):
            return device_serializer
        else:
            return device_serializer_monitoring

class rest_home_export_list(mixins.ListModelMixin,
                            generics.MultipleObjectAPIView):
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    model = device_config
    @rest_logging
    def get_serializer_class(self):
        return device_config_hel_serializer
    @rest_logging
    def get(self, request, *args, **kwargs):
        # print self.list(request, *args, **kwargs)
        return self.list(request, *args, **kwargs)
    @rest_logging
    def get_queryset(self):
        return home_export_list().all()

class csw_object_serializer(serializers.Serializer):
    idx = serializers.IntegerField()
    name = serializers.CharField()
    tr_class = serializers.CharField()

class csw_object_group_serializer(serializers.Serializer):
    content_label = serializers.CharField()
    content_type = serializers.IntegerField()
    object_list = csw_object_serializer(many=True)

class csw_object_group(object):
    def __init__(self, ct_label, ct_idx, obj_list):
        self.content_label = ct_label
        self.content_type = ct_idx
        self.object_list = obj_list

class csw_object(object):
    def __init__(self, idx, name, tr_class):
        self.idx = idx
        self.name = name
        self.tr_class = tr_class

# not needed right now, maybe we can use this as an template for the csw with objects
class csw_object_list(viewsets.ViewSet):
    display_name = "csw_object_groups"
    @rest_logging
    def list(self, request):
        all_db_perms = csw_permission.objects.filter(Q(valid_for_object_level=True)).select_related("content_type")
        perm_cts = ContentType.objects.filter(Q(pk__in=[cur_perm.content_type_id for cur_perm in all_db_perms])).order_by("name")
        group_list = []
        for perm_ct in perm_cts:
            cur_group = csw_object_group(
                "{}.{}".format(perm_ct.app_label, perm_ct.name),
                perm_ct.pk,
                self._get_objects(perm_ct, [ct_perm for ct_perm in all_db_perms if ct_perm.content_type_id == perm_ct.pk])
            )
            group_list.append(cur_group)
        _ser = csw_object_group_serializer(group_list, many=True)
        return Response(_ser.data)
    def _get_objects(self, cur_ct, perm_list):
        cur_model = get_model(cur_ct.app_label, cur_ct.name)
        _q = cur_model.objects
        _key = "{}.{}".format(cur_ct.app_label, cur_ct.name)
        if _key == "backbone.device":
            _q = _q.select_related("device_type", "device_group"). \
                filter(Q(enabled=True, device_group__enabled=True)). \
                order_by("-device_group__cluster_device_group", "device_group__name", "-device_type__priority", "name")
        return [csw_object(cur_obj.pk, self._get_name(_key, cur_obj), self._tr_class(_key, cur_obj)) for cur_obj in _q.all()]
    def _get_name(self, _key, cur_obj):
        if _key == "backbone.device":
            if cur_obj.device_type.identifier == "MD":
                return unicode(cur_obj)[8:] + (" [CDG]" if cur_obj.device_group.cluster_device_group else " [MD]")
        return unicode(cur_obj)
    def _tr_class(self, _key, cur_obj):
        _lt = ""
        if _key == "backbone.device":
            if cur_obj.device_type.identifier == "MD":
                _lt = "warning"
        return _lt

# class get_object_permissions(View):
#     @method_decorator(login_required)
#     def post(self, request):
#         _post = request.POST
#         auth_type, auth_pk = _post["auth_key"].split("__")
#         if auth_type == "group":
#             auth_obj = group.objects.get(Q(pk=auth_pk))
#         else:
#             auth_obj = user.objects.get(Q(pk=auth_pk))
#         # pprint.pprint(_post)
#         all_db_perms = csw_permission.objects.filter(Q(valid_for_object_level=True)).select_related("content_type")
#         all_perms = E.csw_permissions(
#             *[cur_p.get_xml() for cur_p in all_db_perms])
#         perm_ct_pks = set([int(pk) for pk in all_perms.xpath(".//csw_permission/@content_type")])
#         perm_cts = ContentType.objects.filter(Q(pk__in=perm_ct_pks)).order_by("name")
#         request.xml_response["perms"] = all_perms
#         request.xml_response["content_types"] = E.content_types(
#             *[E.content_type(
#                 unicode(cur_ct),
#                 self._get_objects(cur_ct, auth_obj, [ct_perm for ct_perm in all_db_perms if ct_perm.content_type_id == cur_ct.pk]),
#                 name=cur_ct.name,
#                 app_label=cur_ct.app_label,
#                 pk="%d" % (cur_ct.pk)
#                 ) for cur_ct in perm_cts]
#             )
#     def _get_objects(self, cur_ct, auth_obj, perm_list):
#         cur_model = get_model(cur_ct.app_label, cur_ct.name)
#         model_name = cur_model._meta.object_name
#         return {
#             "device" : device_object_emitter,
#             "group"  : group_object_emitter,
#             "user"   : user_object_emitter,
#             }[model_name](cur_model).get_objects(auth_obj, perm_list)
#
# class object_emitter(object):
#     class Meta:
#         pass
#     def __init__(self, cur_model):
#         self.model = cur_model
#         self.model_name = self.model._meta.object_name
#         self.query = self.model.objects.all()
#     def update_query(self):
#         # add select_related
#         pass
#     def get_attrs(self, cur_obj):
#         return {}
#     def get_objects(self, auth_obj, perm_list):
#         self.update_query()
#         return E.objects(
#             *[
#                 E.object(
#                 unicode(cur_obj),
#                 perms=self._get_object_perms(
#                     auth_obj,
#                     cur_obj,
#                     perm_list,
#                     ),
#                     pk="%d" % (cur_obj.pk),
#                     **self.get_attrs(cur_obj)
#                 ) for cur_obj in self.query
#             ],
#             object_name=self.model_name,
#             has_group="1" if getattr(self.Meta, "has_group", False) else "0",
#             has_second_group="1" if getattr(self.Meta, "has_second_group", False) else "0"
#         )
#     def _get_object_perms(self, auth_obj, cur_obj, perm_list):
#         set_perms = ["%d" % (cur_perm.pk) for cur_perm in perm_list if auth_obj.has_object_perm(
#             cur_perm,
#             cur_obj,
#             ask_parent=False,
#             )]
#         return ",".join(set_perms)
#
# class device_object_emitter(object_emitter):
#     class Meta:
#         has_group = True
#         has_second_group = True
#     def update_query(self):
#         self.query = self.query.filter(Q(enabled=True) & Q(device_group__enabled=True)).select_related("device_group", "device_type")
#     def get_attrs(self, cur_obj):
#         return {
#             "group" : unicode(cur_obj.device_group),
#             "second_group" : "meta (group)" if cur_obj.device_type.identifier == "MD" else "real"
#             }
#
# class user_object_emitter(object_emitter):
#     class Meta:
#         has_group = True
#     def update_query(self):
#         self.query = self.query.select_related("group")
#     def get_attrs(self, cur_obj):
#         return {"group" : unicode(cur_obj.group)}
#
# class group_object_emitter(object_emitter):
#     pass

class device_tree_list(mixins.ListModelMixin,
                       mixins.CreateModelMixin,
                       generics.MultipleObjectAPIView):
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    model = device
    @rest_logging
    def get_serializer_class(self):
        if self._get_post_boolean("package_state", False):
            return device_serializer_package_state
        elif self._get_post_boolean("all_monitoring_servers", False):
            return device_serializer_monitor_server
        elif self._get_post_boolean("with_categories", False):
            return device_serializer_cat
        elif self._get_post_boolean("with_variables", False):
            return device_serializer_variables
        elif self._get_post_boolean("with_device_configs", False):
            return device_serializer_device_configs
        elif self._get_post_boolean("with_disk_info", False):
            return device_serializer_disk_info
        else:
            return device_serializer
    @rest_logging
    def get(self, request, *args, **kwargs):
        # print self.list(request, *args, **kwargs)
        return self.list(request, *args, **kwargs)
    @rest_logging
    def post(self, request, *args, **kwargs):
        resp = self.create(request, *args, **kwargs)
        if resp.status_code in [200, 201, 202, 203]:
            resp.data["_messages"] = [u"created '%s'" % (unicode(self.object))]
        return resp
    def _get_post_boolean(self, name, default):
        if name in self.request.QUERY_PARAMS:
            p_val = self.request.QUERY_PARAMS[name]
            if p_val.lower() in ["1", "true"]:
                return True
            else:
                return False
        else:
            return default
    @rest_logging
    def get_queryset(self):
        # with_variables = self._get_post_boolean("with_variables", False)
        package_state = self._get_post_boolean("package_state", False)
        _q = device.objects
        if self._get_post_boolean("all_monitoring_servers", False):
            _q = _q.filter(Q(device_config__config__name__in=["monitor_server", "monitor_slave"]))
        elif self._get_post_boolean("all_mother_servers", False):
            _q = _q.filter(Q(device_config__config__name__in=["mother_server", "mother"]))
        elif self._get_post_boolean("all_devices", False):
            pass
        else:
            # flags
            # ignore meta devices (== device groups)
            ignore_md = self._get_post_boolean("ignore_meta_devices", False)
            # ignore the cluster device group
            ignore_cdg = self._get_post_boolean("ignore_cdg", True)
            # always add the meta_devices
            with_md = self._get_post_boolean("with_meta_devices", False)
            if with_md:
                ignore_md = False
            if "pks" in self.request.QUERY_PARAMS:
                dev_keys = json.loads(self.request.QUERY_PARAMS["pks"])
            else:
                # only selected ones
                # normally (frontend in-sync with backend) meta-devices have the same selection state
                # as their device_groups, devg_keys are in fact redundant ...
                dev_keys = [key.split("__")[1] for key in self.request.session.get("sel_list", []) if key.startswith("dev_")]
            # devg_keys = [key.split("__")[1] for key in self.request.session.get("sel_list", []) if key.startswith("devg_")]
            if ignore_cdg:
                # ignore cluster device group
                _q = _q.exclude(Q(device_group__cluster_device_group=True))
            if ignore_md:
                # ignore all meta-devices
                _q = _q.exclude(Q(device_type__identifier="MD"))
            if with_md:
                md_pks = set(device.objects.filter(Q(pk__in=dev_keys)).values_list("device_group__device", flat=True))
                dev_keys.extend(md_pks)
            _q = _q.filter(Q(pk__in=dev_keys))
        if not self._get_post_boolean("ignore_disabled", False):
            _q = _q.filter(Q(enabled=True) & Q(device_group__enabled=True))
        _q = _q.select_related("domain_tree_node", "device_type", "device_group")
        if package_state:
            _q = _q.prefetch_related("package_device_connection_set", "device_variable_set")
        if self._get_post_boolean("with_categories", False):
            _q = _q.prefetch_related("categories")
        if self._get_post_boolean("with_variables", False):
            _q = _q.prefetch_related("device_variable_set")
        if self._get_post_boolean("with_device_configs", False):
            _q = _q.prefetch_related("device_config_set")
        if self._get_post_boolean("with_disk_info", False):
            _q = _q.prefetch_related(
                "partition_table__partition_disc_set__partition_set",
                "partition_table__lvm_vg_set",
                "partition_table__lvm_lv_set",
                "partition_table__sys_partition_set",
                "partition_table__new_partition_table",
                "partition_table__act_partition_table",
                "act_partition_table__partition_disc_set__partition_set",
                "act_partition_table__lvm_vg_set",
                "act_partition_table__lvm_lv_set",
                "act_partition_table__sys_partition_set",
                "act_partition_table__new_partition_table",
                "act_partition_table__act_partition_table",
            )
        # ordering: at first cluster device group, then by group / device_type / name
        _q = _q.order_by("-device_group__cluster_device_group", "device_group__name", "-device_type__priority", "name")
        # print _q.count(), self.request.QUERY_PARAMS, self.request.session.get("sel_list", [])
        return _q

class device_selection_list(APIView):
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    def get(self, request):
        ser = device_selection_serializer([device_selection(cur_sel) for cur_sel in request.session.get("sel_list", [])], many=True)
        return Response(ser.data)

class user_list_h(generics.ListCreateAPIView):
    authentication_classes = (BasicAuthentication, SessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    model = user
    serializer_class = user_serializer_h

class user_detail_h(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = (BasicAuthentication, SessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    model = user
    serializer_class = user_serializer_h

class group_list_h(generics.ListCreateAPIView):
    authentication_classes = (BasicAuthentication, SessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    model = group
    serializer_class = group_serializer_h

class group_detail_h(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = (BasicAuthentication, SessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    model = group
    serializer_class = group_serializer_h

# _models = __import__("initat.cluster.backbone.models")
for obj_name in REST_LIST:
    ser_name = "%s_serializer" % (obj_name)
    ser_class = getattr(models, ser_name)
    for mode in ["list", "detail"]:
        class_name = "%s_%s" % (obj_name, mode)
        globals()[class_name] = type(
            class_name,
            (detail_view,) if mode == "detail" else (list_view,),
            {"authentication_classes" : (SessionAuthentication,),
             "permission_classes"     : (IsAuthenticated,),
             "model"                  : ser_class.Meta.model,
             "serializer_class"       : ser_class})

