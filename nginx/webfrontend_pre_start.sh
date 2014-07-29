#!/bin/bash

APP_DIR=/var/run/${DJANGO_APP}
mkdir -p ${APP_DIR}
chown -R ${USER}.${GROUP} ${APP_DIR}

# check for product version

if [ -f /etc/init.d/mother ] ; then
    # seems to be a cluster
    touch /etc/sysconfig/cluster/.is_corvus
fi

# create static files
/opt/python-init/lib/python/site-packages/initat/cluster/manage.py collectstatic --noinput

logger "init ${APP_DIR} with ${USER}.${GROUP}"

