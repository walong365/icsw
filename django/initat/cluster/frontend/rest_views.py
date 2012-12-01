# user views

import os
from django.http import HttpResponse
from initat.core.render import render_me
from django.http import Http404
from django.conf import settings
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
import logging_tools
from initat.cluster.backbone.models import user, user_serializer, group, group_serializer
from rest_framework.renderers import XMLRenderer
from rest_framework.parsers import XMLParser
from rest_framework.decorators import api_view, APIView
from rest_framework import mixins
from rest_framework import generics
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.reverse import reverse

@api_view(('GET',))
def api_root(request, format=None):
    return Response({
        'user'  : reverse('rest:user_list', request=request),
        'group' : reverse('rest:group_list', request=request)
    })

class user_list(generics.ListCreateAPIView):
    authentication_classes = (BasicAuthentication, SessionAuthentication, )
    permission_classes = (IsAuthenticated,)
    model = user
    serializer_class = user_serializer

class user_detail(generics.RetrieveUpdateDestroyAPIView):
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
