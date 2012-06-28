""" contex processor """
from django.conf import settings
from edmdb.models import OlimUser


def add_session(request):
    return {"session" : request.session}


def add_svn_version(request):
    return {"PROJECT_VERSION" : settings.PROJECT_VERSION}


def add_project_name(request):
    return {"PROJECT_NAME": settings.PROJECT_NAME}


def add_settings(request):
    return {"settings": settings}
