#!/bin/bash

APP_DIR=/var/run/${DJANGO_APP}
mkdir -p ${APP_DIR}
chown -R ${USER}.${GROUP} ${APP_DIR}

logger "init ${APP_DIR} with ${USER}.${GROUP}"
