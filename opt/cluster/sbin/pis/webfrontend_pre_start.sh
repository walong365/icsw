#!/bin/bash

APP_DIR=/var/run/${DJANGO_APP}
mkdir -p ${APP_DIR}
chown -R ${USER}.${GROUP} ${APP_DIR}

# create static files
/opt/python-init/lib/python/site-packages/initat/cluster/manage.py collectstatic --noinput

logger "init ${APP_DIR} with ${USER}.${GROUP}"
