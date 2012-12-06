# user views

import os
import time
from django.http import HttpResponse
from initat.core.render import render_me
from django.http import Http404
from django.conf import settings
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
import logging_tools
from initat.cluster.backbone.models import user, user_serializer, group, group_serializer, \
     user_serializer_h, group_serializer_h
from rest_framework.renderers import XMLRenderer
from rest_framework.parsers import XMLParser
from rest_framework.decorators import api_view, APIView
from rest_framework import mixins
from rest_framework import generics
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.reverse import reverse
import types

@api_view(('GET',))
def api_root(request, format=None):
    return Response({
        'user'  : reverse('rest:user_list_h', request=request),
        'group' : reverse('rest:group_list_h', request=request)
    })

class rest_logging(object):
    def __init__(self, func):
        #self.__name__ = func.__name__
        self._func = func
    def __get__(self, obj, owner_class=None):
        # magic ...
        return types.MethodType(self, obj)
    def __call__(self, *args, **kwargs):
        s_time = time.time()
        e_time = time.time()
        print args, kwargs
        result = self._func(*args, **kwargs)
        print e_time - s_time
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

class user_list(generics.ListCreateAPIView):
    authentication_classes = (BasicAuthentication, SessionAuthentication, )
    permission_classes = (IsAuthenticated,)
    model = user
    serializer_class = user_serializer

class user_detail(detail_view):
    authentication_classes = (BasicAuthentication, SessionAuthentication, )
    permission_classes = (IsAuthenticated,)
    model = user
    serializer_class = user_serializer

class group_list(generics.ListCreateAPIView):
    authentication_classes = (BasicAuthentication, SessionAuthentication, )
    permission_classes = (IsAuthenticated,)
    model = group
    serializer_class = group_serializer

class group_detail(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = (BasicAuthentication, SessionAuthentication, )
    permission_classes = (IsAuthenticated,)
    model = group
    serializer_class = group_serializer

