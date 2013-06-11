# user views

import os
import time
import process_tools
import logging
import logging_tools
import types

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.views.decorators.csrf import csrf_exempt

from rest_framework import mixins, generics
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.decorators import api_view, APIView
from rest_framework.parsers import XMLParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.renderers import XMLRenderer

from initat.core.render import render_me
from initat.cluster.backbone.models import user, user_serializer, group, group_serializer, \
     user_serializer_h, group_serializer_h, device_group_serializer

logger = logging.getLogger("cluster.rest")

@api_view(('GET',))
def api_root(request, format=None):
    return Response({
        'user'  : reverse('rest:user_list_h', request=request),
        'group' : reverse('rest:group_list_h', request=request)
    })

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
        return self.update(request, *args, **kwargs)
    @rest_logging
    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)

class list_view(mixins.ListModelMixin,
                mixins.CreateModelMixin,
                generics.MultipleObjectAPIView):
    @rest_logging
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)
    @rest_logging
    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

class user_list_h(generics.ListCreateAPIView):
    authentication_classes = (BasicAuthentication, SessionAuthentication, )
    permission_classes = (IsAuthenticated,)
    model = user
    serializer_class = user_serializer_h

class user_detail_h(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = (BasicAuthentication, SessionAuthentication, )
    permission_classes = (IsAuthenticated,)
    model = user
    serializer_class = user_serializer_h

class group_list_h(generics.ListCreateAPIView):
    authentication_classes = (BasicAuthentication, SessionAuthentication, )
    permission_classes = (IsAuthenticated,)
    model = group
    serializer_class = group_serializer_h

class group_detail_h(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = (BasicAuthentication, SessionAuthentication, )
    permission_classes = (IsAuthenticated,)
    model = group
    serializer_class = group_serializer_h

for obj_name in ["group", "user", "device_group"]:
    for mode in ["list", "detail"]:
        class_name = "%s_%s" % (obj_name, mode)
        ser_class = globals()["%s_serializer" % (obj_name)]
        globals()[class_name] = type(
            class_name,
            (detail_view, ) if mode == "detail" else (list_view,),
            {"authentication_classes" : (BasicAuthentication, SessionAuthentication, ),
             "permission_classes"     : (IsAuthenticated,),
             "model"                  : ser_class.Meta.model,
             "serializer_class"       : ser_class})
