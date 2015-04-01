#!/usr/bin/python-init -Otu

from django.conf import settings

def add_session(request):
    return {"session": request.session}

def add_settings(request):
    return {"settings": settings}

