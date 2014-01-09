#!/bin/bash

export DEBUG_WEBFRONTEND=1

if [ "$1" != "--nostatic" ] ; then
     echo "collecting static files ..."
    ./manage.py collectstatic --noinput
    echo "done"
fi


./manage.py runserver $* --traceback 0.0.0.0:8080 

