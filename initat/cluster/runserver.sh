#!/bin/bash

export DEBUG_WEBFRONTEND=1

./manage.py runserver $* --traceback 0.0.0.0:8080 

