#!/usr/bin/python-init -Otu

""" contex processor """

def add_session(request):
    return {"session": request.session}

