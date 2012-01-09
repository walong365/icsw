""" contex processor """
from django.conf import settings

def add_session(request):
    return {"session" : request.session}

def add_svn_version(request):
    return {"SVN_VERSION" : settings.SVN_VERSION}
    
def add_project_name(request):
    return {"PROJECT_NAME": settings.PROJECT_NAME}