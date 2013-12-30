#!/bin/bash

export DEBUG_WEBFRONTEND=1

echo "collecting static files ..."

./manage.py collectstatic --noinput

echo "done"

./manage.py runserver $* --traceback 0.0.0.0:8080 

