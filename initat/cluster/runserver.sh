#!/bin/bash

export DEBUG_WEBFRONTEND=1

if [ "$1" != "--nostatic" ] ; then
     echo -ne "collecting static files ... "
    ./manage.py collectstatic --noinput -c > /dev/null
    echo "done"
fi

export NODE_PATH=$(/opt/cluster/bin/npm -g root)
export NODE_PATH=${NODE_PATH}:${NODE_PATH}/npm/node_modules

echo "NODE_PATH=${NODE_PATH}"

./manage.py runserver $* --traceback 0.0.0.0:8080 

