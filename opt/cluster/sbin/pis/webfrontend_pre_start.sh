#!/bin/bash

APP_DIR=/var/run/${DJANGO_APP}
mkdir -p ${APP_DIR}
chown -R ${USER}.${GROUP} ${APP_DIR}

# create static files is now handled in webfrontend_post_install

logger "init ${APP_DIR} with ${USER}.${GROUP}"
