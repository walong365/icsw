# user views

""" REST views """

# from django.core.exceptions import ValidationError
from django.db.models import Q
from initat.cluster.backbone import models
from initat.cluster.backbone.models import user , group, user_serializer_h, group_serializer_h, \
     get_related_models, get_change_reset_list, device, device_serializer, \
     device_serializer_package_state, device_serializer_monitoring
from rest_framework import mixins, generics, status, viewsets
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.routers import DefaultRouter
from rest_framework.views import exception_handler
import logging
import logging_tools
import operator
import process_tools
import time
import types

logger = logging.getLogger("cluster.rest")

# build REST_LIST from models content
REST_LIST = []
for key in dir(models):
    if key.endswith("_serializer"):
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
        if hasattr(exc, "messages"):
            response = Response(
                {"detail" : "%s (%s)" % (exc.__class__.__name__, ", ".join(exc.messages))},
                status=status.HTTP_406_NOT_ACCEPTABLE
            )
        elif hasattr(exc, "message"):
            response = Response(
                {"detail" : "%s (%s)" % (exc.__class__.__name__, exc.message)},
                status=status.HTTP_406_NOT_ACCEPTABLE
            )
        else:
            response = Response(
                {"detail" : "%s" % (exc.__class__.__name__)},
                status=status.HTTP_406_NOT_ACCEPTABLE
            )
    # print response
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
        self.__obj_name = args[0].model._meta.object_name
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
        num_refs = get_related_models(cur_obj)
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
    def get_queryset(self):
        model_name = self.model._meta.model_name
        related_fields, prefetch_fields = {
            "kernel" : ([], ["initrd_build_set", "kernel_build_set", "new_kernel", "act_kernel"]),
            "image" : ([], ["new_image", "act_image"]),
            "partition_table" : ([], ["new_partition_table", "act_partition_table", "sys_partition_set", "lvm_lv_set" , "lvm_vg_set", "partition_disc_set"]),
            "mon_period" : ([], ["service_check_period", "mon_device_templ_set"]),
            "device" : (["domain_tree_node", "device_type", "device_group"], []),
            "mon_check_command" : ([], ["exclude_devices", "categories"]),
            "mon_host_cluster" : ([], ["devices"]),
            "network" : ([], ["network_device_type"]),
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

class device_tree_list(mixins.ListModelMixin,
                       mixins.CreateModelMixin,
                       generics.MultipleObjectAPIView):
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    model = device
    @rest_logging
    def get_serializer_class(self):
        package_state = self._get_post_boolean("package_state", False)
        if package_state:
            return device_serializer_package_state
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
        # print "QSET", self.request.QUERY_PARAMS
        ignore_md = self._get_post_boolean("ignore_meta_devices", False)
        ignore_cdg = self._get_post_boolean("ignore_cdg", True)
        # with_variables = self._get_post_boolean("with_variables", False)
        package_state = self._get_post_boolean("package_state", False)
        _q = device.objects
        if self._get_post_boolean("all_monitoring_servers", False):
            _q = _q.filter(Q(device_config__config__name__in=["monitor_server", "monitor_slave"]))
        elif self._get_post_boolean("all_mother_servers", False):
            _q = _q.filter(Q(device_config__config__name__in=["mother_server"]))
        elif self._get_post_boolean("all_devices", False):
            pass
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
            # print dev_keys, devg_keys
            _q = _q.filter(Q(pk__in=dev_keys))
        if not self._get_post_boolean("all_devices", False):
            _q = _q.filter(Q(enabled=True) & Q(device_group__enabled=True))
        _q = _q.select_related("domain_tree_node", "device_type", "device_group")
        if package_state:
            _q = _q.prefetch_related("package_device_connection_set", "device_variable_set")
        # ordering: at first cluster device group, then by group / device_type / name
        _q = _q.order_by("-device_group__cluster_device_group", "device_group__name", "-device_type__priority", "name")
        # print _q.count(), self.request.QUERY_PARAMS, self.request.session.get("sel_list", [])
        return _q

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

