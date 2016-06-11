# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2016 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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

from django.apps import apps
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from initat.cluster.backbone import serializers as model_serializers
from initat.cluster.backbone.models.functions import can_delete_obj
from initat.cluster.backbone.models import get_related_models, get_change_reset_list, device, \
    domain_name_tree, category_tree, device_selection, device_config, home_export_list, \
    csw_permission, netdevice, cd_connection, ext_license_state_coarse, ext_license_check_coarse, \
    ext_license_version_state_coarse, ext_license_version, ext_license_user, ext_license_client, \
    ext_license_usage_coarse, peer_information
from initat.cluster.backbone.serializers import device_serializer, \
    device_selection_serializer, partition_table_serializer_save, partition_disc_serializer_save, \
    partition_disc_serializer_create, device_config_help_serializer, \
    network_with_ip_serializer, ComCapabilitySerializer, peer_information_serializer
from rest_framework import mixins, generics, status, viewsets, serializers
import rest_framework
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import exception_handler, APIView
import json
import logging
from initat.tools import logging_tools, process_tools
import operator
import pprint  # @UnusedImport
import time
import types
import importlib
import inspect

logger = logging.getLogger("cluster.rest")

SERIALIZER_BLACKLIST = ["device_selection_serializer"]

# build REST_LIST from models content
REST_LIST = []

model_serializer_modules = [model_serializers]

init_apps = [_app for _app in settings.INSTALLED_APPS if _app.startswith("initat.cluster")]

for addon_app in settings.ICSW_ADDON_APPS:
    try:
        module = importlib.import_module("initat.cluster.{}.serializers".format(addon_app))
    except ImportError as e:
        pass
    else:
        model_serializer_modules.append(module)

for module in model_serializer_modules:
    _ser_keys = dir(module)
    for key in _ser_keys:

        val = getattr(module, key)
        if inspect.isclass(val) and issubclass(val, rest_framework.serializers.Serializer):
            if key.endswith("_serializer") and key not in SERIALIZER_BLACKLIST:
                REST_LIST.append((module, "_".join(key.split("_")[:-1])))
            elif key.endswith("Serializer"):
                REST_LIST.append((module, key[:-10]))


# @api_view(('GET',))
# def api_root(request, format=None):
#    return Response({
#        'user'         : reverse('rest:user_list_h', request=request),
#        'group'        : reverse('rest:group_list_h', request=request),
#        # 'network_type' : reverse('rest:network_type_list_h', request=request),
#    })


def csw_exception_handler(exc, info_dict):
    response = exception_handler(exc, info_dict)
    if response is None:
        detail_str, detail_info = (exc.__class__.__name__, [])
        if hasattr(exc, "messages"):
            detail_info.extend([unicode(_part) for _part in exc.messages])
        if hasattr(exc, "message"):
            detail_info.append(unicode(exc.message))
        if hasattr(exc, "args"):
            for entry in exc.args:
                detail_info.append(unicode(entry))
        detail_info = list(
            set(
                [
                    _entry for _entry in [
                        _part.strip() for _part in detail_info if _part.strip()
                    ] if _entry not in ["()"]
                ]
            )
        )
        response = Response(
            {
                u"detail": u"{}{}".format(
                    detail_str,
                    u" ({})".format(
                        u", ".join(detail_info)
                    ) if detail_info else u""
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
        logger.log(
            log_level,
            u"[{}{}] {}".format(
                self.__name__,
                u" {}".format(self.__obj_name) if self.__obj_name else "",
                what
            )
        )

    def __call__(self, *args, **kwargs):
        s_time = time.time()

        display_name = getattr(args[0], "display_name", None)
        # get: head.im_class.__name__ (contains class name for django class views)
        view_class_name = getattr(getattr(getattr(args[0], 'head', None), 'im_class', None), '__name__', None)

        if hasattr(args[0], "model") and args[0].model is not None:
            self.__obj_name = args[0].model._meta.object_name
        elif display_name is not None:
            self.__obj_name = display_name
        elif view_class_name is not None:
            self.__obj_name = view_class_name
        else:
            self.__obj_name = "unknown"

        try:
            result = self._func(*args, **kwargs)
        except:
            self.log(
                u"exception: {}".format(
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            exc_info = process_tools.exception_info()
            for line in exc_info.log_lines:
                self.log(u"  {}".format(line))
            raise
        e_time = time.time()
        self.log(
            "call took {}".format(
                logging_tools.get_diff_time_str(e_time - s_time)
            )
        )
        return result


class DBPrefetchMixin(object):
    def _kernel_prefetch(self):
        return ["initrd_build_set", "kernel_build_set", "new_kernel", "kerneldevicehistory_set"]

    def _image_prefetch(self):
        return ["new_image", "imagedevicehistory_set"]

    def _partition_table_prefetch(self):
        return [
            "new_partition_table", "act_partition_table", "sys_partition_set",
            "lvm_lv_set__partition_fs", "lvm_vg_set", "partition_disc_set__partition_set__partition_fs"
        ]

    def _mon_period_prefetch(self):
        return ["service_check_period"]

    def _device_related(self):
        return ["domain_tree_node", "device_group", "mon_ext_host"]

    def _device_prefetch(self):
        return ["snmp_schemes__snmp_scheme_vendor", "DeviceSNMPInfo", "snmp_schemes__snmp_scheme_tl_oid_set", "com_capability_list"]

    def _mon_check_command_prefetch(self):
        return ["exclude_devices", "categories"]

    def _mon_host_cluster_prefetch(self):
        return ["devices"]

    def _graphsetting_related(self):
        return ["graph_setting_size"]

    def _mon_host_dependency_prefetch(self):
        return ["devices", "dependent_devices"]

    def _network_prefetch(self):
        return ["network_device_type", "net_ip_set"]

    def _category_prefetch(self):
        return ["config_set", "device_set", "mon_check_command_set", "deviceselection_set"]

    def _virtual_desktop_protocol_prefetch(self):
        return ["devices"]

    def _window_manager_prefetch(self):
        return ["devices"]

    def _netdevice_prefetch(self):
        return ["net_ip_set"]

    def _user_related(self):
        return ["group"]

    def _sensorthreshold_prefetch(self):
        return ["notify_users"]

    def _background_job_related(self):
        return ["initiator__domain_tree_node", "user"]

    def _deviceselection_prefetch(self):
        return ["devices", "device_groups", "categories"]

    def _user_prefetch(self):
        return [
            "user_permission_set", "user_object_permission_set__csw_object_permission", "secondary_groups",
            "allowed_device_groups", "user_quota_setting_set", "user_scan_run_set__user_scan_result_set",
        ]

    def _group_related(self):
        return ["parent_group"]

    def _group_prefetch(self):
        return ["group_permission_set", "group_object_permission_set", "group_object_permission_set__csw_object_permission", "allowed_device_groups"]

    def _config_prefetch(self):
        return [
            "categories", "config_str_set", "config_int_set", "config_blob_set",
            "config_bool_set", "config_script_set", "mon_check_command_set__categories", "mon_check_command_set__exclude_devices",
            "device_config_set"
        ]

    def _cransys_dataset_prefetch(self):
        return ["cransys_job_set", "cransys_job_set__cransys_run_set"]

    def _config_hint_prefetch(self):
        return [
            "config_var_hint_set",
            "config_script_hint_set",
        ]

    def _mon_dist_master_prefetch(self):
        return ["mon_dist_slave_set"]

    def _macbootlog_related(self):
        return ["device__domain_tree_node"]

    def _device_mon_location_related(self):
        return ["device__domain_tree_node"]

    def _location_gfx_put(self, req_changes, prev_model):
        req_changes.update(
            {
                key: getattr(prev_model, key) for key in ["image_count"]
            }
        )
        return req_changes


class detail_view(mixins.RetrieveModelMixin,
                  mixins.UpdateModelMixin,
                  mixins.DestroyModelMixin,
                  generics.GenericAPIView,
                  DBPrefetchMixin):
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

    @rest_logging
    def get_queryset(self):
        model_name = self.model._meta.model_name
        related_fields, prefetch_fields = (
            getattr(self, "_{}_related".format(model_name), lambda: [])(),
            getattr(self, "_{}_prefetch".format(model_name), lambda: [])(),
        )
        res = self.model.objects
        return res.select_related(*related_fields).prefetch_related(*prefetch_fields)

    @rest_logging
    def put(self, request, *args, **kwargs):
        model_name = self.model._meta.model_name
        prev_model = self.model.objects.get(Q(pk=kwargs["pk"]))
        # for user_var put for instance...
        silent = True if int(request.GET.get('silent', 0)) else False
        # print "silent=", silent
        req_changes = getattr(self, "_{}_put".format(model_name), lambda changed, prev: changed)(request.data, prev_model)
        # try:
        resp = self.update(request, *args, **kwargs)
        # except ValidationError as cur_exc:
        #    print cur_exc
        # print dir(resp), resp.data
        new_model = self.model.objects.get(Q(pk=kwargs["pk"]))
        if self.model._meta.object_name == "device":
            root_pwd = new_model.crypt(req_changes.get("root_passwd", ""))
            if root_pwd:
                new_model.root_passwd = root_pwd
                new_model.save()
        if not silent:
            c_list, r_list = get_change_reset_list(prev_model, new_model, req_changes)
            # print c_list, r_list
            resp.data["_change_list"] = c_list
            resp.data["_reset_list"] = r_list
        return resp

    @rest_logging
    def delete(self, request, *args, **kwargs):
        # just be careful
        cur_obj = self.model.objects.get(Q(pk=kwargs["pk"]))
        can_delete_answer = can_delete_obj(cur_obj, logger)
        if can_delete_answer:
            return self.destroy(request, *args, **kwargs)
            # it makes no sense to return something meaningful because the DestroyModelMixin returns
            # a 204 status on successful deletion
            # print "****", "del"
            # print unicode(cur_obj), resp.data
            # if not resp.data:
            #    resp.data = {}
            # resp.data["_messages"] = [u"deleted '%s'" % (unicode(cur_obj))]
            # return resp
        else:
            raise ValueError(can_delete_answer.msg)


class list_view(mixins.ListModelMixin,
                mixins.CreateModelMixin,
                generics.GenericAPIView,
                DBPrefetchMixin
                ):
    @rest_logging
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    @rest_logging
    def post(self, request, *args, **kwargs):
        resp = self.create(request, *args, **kwargs)
        silent = int(request.GET.get('silent', 0))
        if not silent and resp.status_code in [200, 201, 202, 203]:
            # TODO, FIXME, get name (or unicode representation) of new object
            resp.data["_messages"] = [u"created '{}'".format(unicode(self.model._meta.object_name))]
        return resp

    @rest_logging
    def get_serializer_class(self):
        if self.request.method == "POST":
            if self.model._meta.object_name == "partition_disc":
                return partition_disc_serializer_create
        elif self.request.method == "GET":
            if self.model._meta.object_name == "network":
                if "_with_ip_info" in self.request.query_params:
                    return network_with_ip_serializer
        return self.serializer_class

    @rest_logging
    def get_queryset(self):
        model_name = self.model._meta.model_name
        # if model_name == "domain_tree_node":
        #    return domain_name_tree()
        # elif model_name == "category":
        #    return category_tree(with_ref_count=True)
        related_fields, prefetch_fields = (
            getattr(self, "_{}_related".format(model_name), lambda: [])(),
            getattr(self, "_{}_prefetch".format(model_name), lambda: [])(),
        )
        res = self.model.objects.all()
        filter_list = []
        special_dict = {}
        for key, value in self.request.query_params.iteritems():
            if key.startswith("_"):
                special_dict[key[1:]] = value
            else:
                if key.endswith("__in"):
                    filter_list.append(Q(**{key: json.loads(value)}))
                else:
                    filter_list.append(Q(**{key: value}))
        if filter_list:
            res = res.filter(reduce(operator.iand, filter_list))
        res = res.select_related(*related_fields).prefetch_related(*prefetch_fields)
        if "distinct" in special_dict:
            res = res.distinct()
        if "order_by" in special_dict:
            res = res.order_by(special_dict["order_by"])
        if "num_entries" in special_dict:
            res = res[0:special_dict["num_entries"]]
        if model_name == "quota_capable_blockdevice":
            res = res.prefetch_related(
                "device__snmp_schemes__snmp_scheme_vendor",
                "device__com_capability_list",
                "device__DeviceSNMPInfo",
                "device__snmp_schemes__snmp_scheme_tl_oid_set",
            )
        return res


class form_serializer(serializers.Serializer):
    name = serializers.CharField()
    form = serializers.CharField()


class ext_peer_object(dict):
    def __init__(self, *args, **kwargs):
        dict.__init__(self, **kwargs)
        self["full_name"] = "{}{}".format(
            self["device__name"],
            ".{}".format(
                self["device__domain_tree_node__full_name"]
            ) if self["device__domain_tree_node__full_name"] else "",
        )


class ext_peer_serializer(serializers.Serializer):
    idx = serializers.IntegerField(source="pk")
    penalty = serializers.IntegerField()
    device_name = serializers.CharField(source="device__name")
    device_group_name = serializers.CharField(source="device__device_group__name")
    devname = serializers.CharField()
    routing = serializers.BooleanField()
    full_name = serializers.CharField()


class used_peer_list(viewsets.ViewSet):
    display_name = "used_peer_list"

    @rest_logging
    def list(self, request):
        _dev_pks = json.loads(request.GET.get("primary_dev_pks"))
        _peers = peer_information.objects.filter(
            Q(s_netdevice__device__in=_dev_pks) |
            Q(d_netdevice__device__in=_dev_pks)
        ).select_related(
            "s_netdevice",
            "d_netdevice",
        )
        _ser = peer_information_serializer(_peers, many=True)
        return Response(_ser.data)


class peerable_netdevice_list(viewsets.ViewSet):
    display_name = "peerable_netdevice_list"

    @rest_logging
    def list(self, request):
        peer_list = [
            ext_peer_object(**_obj) for _obj in netdevice.objects.filter(
                Q(device__enabled=True) & Q(device__device_group__enabled=True)
            ).filter(
                Q(enabled=True)
            ).filter(
                Q(routing=True)
            ).distinct().order_by(
                "device__device_group__name",
                "device__name",
                "devname",
            ).select_related(
                "device",
                "device__device_group",
                "device__domain_tree_node"
            ).values(
                "pk",
                "devname",
                "penalty",
                "routing",
                "device__name",
                "device__device_group__name",
                "device__domain_tree_node__full_name"
            )
        ]
        _ser = ext_peer_serializer(peer_list, many=True)
        return Response(_ser.data)


class rest_home_export_list(mixins.ListModelMixin,
                            generics.GenericAPIView):
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    model = device_config

    @rest_logging
    def get_serializer_class(self):
        return device_config_help_serializer

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
    group = serializers.CharField()
    tr_class = serializers.CharField()


class csw_object_group_serializer(serializers.Serializer):
    content_label = serializers.CharField()
    content_type = serializers.IntegerField()


class csw_object_group(object):
    def __init__(self, ct_label, ct_idx):
        self.content_label = ct_label
        self.content_type = ct_idx


class min_access_levels(viewsets.ViewSet):
    # returns minimum levels of access for a given object type / object list
    display_name = "min_access_levels"

    @rest_logging
    def list(self, request):
        obj_list = json.loads(request.query_params["obj_list"])
        min_dict = None
        for _dev in apps.get_model("backbone", request.query_params["obj_type"]).objects.filter(Q(pk__in=obj_list)):
            _cur_dict = request.user.get_object_access_levels(_dev)
            if min_dict is None:
                min_dict = _cur_dict
            else:
                for key, value in _cur_dict.iteritems():
                    min_dict[key] = min(min_dict.get(key, -1), value)
        if min_dict is None:
            min_dict = {}
        min_dict = {_key: _value for _key, _value in min_dict.iteritems() if _value >= 0}
        return Response(min_dict)


class csw_object_list(viewsets.ViewSet):
    display_name = "csw_object_groups"

    @rest_logging
    def list(self, request):
        all_db_perms = csw_permission.objects.filter(Q(valid_for_object_level=True)).select_related("content_type")
        perm_cts = ContentType.objects.filter(
            Q(pk__in=[cur_perm.content_type_id for cur_perm in all_db_perms])
        )
        perm_cts = sorted(perm_cts, key=operator.attrgetter("name"))
        group_list = []
        for perm_ct in perm_cts:
            cur_group = csw_object_group(
                "{}.{}".format(perm_ct.app_label, perm_ct.model_class().__name__),
                perm_ct.pk,
            )
            group_list.append(cur_group)
        _ser = csw_object_group_serializer(group_list, many=True)
        return Response(_ser.data)


class device_tree_detail(detail_view):
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    model = device

    @rest_logging
    def _get_serializer_context(self):
        return {
            "request": self.request,
        }

    @rest_logging
    def get_serializer_context(self):
        return self._get_serializer_context()

    @rest_logging
    def get_serializer_class(self):
        return device_serializer


class device_tree_list(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    generics.GenericAPIView,
):
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    model = device

    def _get_post_boolean(self, name, default):
        if name in self.request.query_params:
            p_val = self.request.query_params[name]
            if p_val.lower() in ["1", "true"]:
                return True
            else:
                return False
        else:
            return default

    @rest_logging
    def get_serializer_context(self):
        return {
            "request": self.request,
        }

    @rest_logging
    def get_serializer_class(self):
        return device_serializer

    @rest_logging
    def get(self, request, *args, **kwargs):
        # print self.list(request, *args, **kwargs)
        return self.list(request, *args, **kwargs)

    @rest_logging
    def post(self, request, *args, **kwargs):
        resp = self.create(request, *args, **kwargs)
        if resp.status_code in [200, 201, 202, 203]:
            resp.data["_messages"] = [u"created '{}'".format(unicode(self.model._meta.object_name))]
        return resp

    @rest_logging
    def get_queryset(self):
        _q = device.objects
        # permission handling
        if not self.request.user.is_superuser:
            # get all pks for device model
            allowed_pks = self.request.user.get_allowed_object_list_model("backbone.device")
            dg_list = list(
                device.objects.filter(
                    Q(pk__in=allowed_pks)
                ).values_list(
                    "pk",
                    "device_group",
                    "device_group__device",
                    "device_group__device__is_meta_device"
                )
            )
            # meta_list, device group selected
            meta_list = Q(device_group__in=[devg_idx for dev_idx, devg_idx, md_idx, dt in dg_list if dt])
            # device list, direct selected
            device_list = Q(
                pk__in=set(
                    sum(
                        [
                            [dev_idx, md_idx] for dev_idx, devg_idx, md_idx, dt in dg_list if not dt
                        ],
                        []
                    )
                )
            )
            _q = _q.filter(meta_list | device_list)
            if not self.request.user.has_perm("backbone.device.all_devices"):
                _q = _q.filter(Q(device_group__in=self.request.user.allowed_device_groups.all()))
        if "pks" in self.request.query_params:
            dev_keys = json.loads(self.request.query_params["pks"])
        else:
            # all devices
            dev_keys = device.objects.all().values_list("pk", flat=True)
        _q = _q.filter(
            Q(pk__in=dev_keys)
        ).select_related(
            "domain_tree_node",
            "device_group",
        ).prefetch_related(
            "categories"
        ).order_by(
            "-device_group__cluster_device_group",
            "device_group__name",
            "-is_meta_device",
            "name"
        )
        logger.info("device_tree_list has {}".format(logging_tools.get_plural("entry", _q.count())))
        # print _q.count(), self.request.query_params, self.request.session.get("sel_list", [])
        return _q


class device_com_capabilities(APIView):
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)

    @rest_logging
    def get(self, request):
        # have default value since in some strange corner cases, request does not contain devices
        _devs = json.loads(request.query_params.get("devices", "[]"))
        _devs = device.objects.filter(Q(pk__in=_devs)).prefetch_related("com_capability_list")
        _data = []
        for _dev in _devs:
            _data.append(ComCapabilitySerializer([_cap for _cap in _dev.com_capability_list.all()], many=True).data)
        return Response(_data)

# print len(REST_LIST)

for src_mod, obj_name in REST_LIST:
    is_camelcase = obj_name[0].lower() != obj_name[0]
    if is_camelcase:
        ser_name = "{}Serializer".format(obj_name)
        modes = [
            ("List", list_view),
            ("Detail", detail_view),
        ]
    else:
        ser_name = "{}_serializer".format(obj_name)
        modes = [
            ("_list", list_view),
            ("_detail", detail_view),
        ]
    ser_class = getattr(src_mod, ser_name)
    for mode_name, mode_impl in modes:
        class_name = "{}{}".format(obj_name, mode_name)
        globals()[class_name] = type(
            class_name,
            (mode_impl, ),
            {
                "authentication_classes": (SessionAuthentication,),
                "permission_classes": (IsAuthenticated,),
                "model": ser_class.Meta.model,
                "serializer_class": ser_class
            }
        )
