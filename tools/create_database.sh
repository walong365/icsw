#!/bin/bash

C_DIR="/opt/python-init/lib/python/site-packages/initat/cluster/"

if [ "${UID:-X}" = "0" ] ; then 
    MIG_DIR="${C_DIR}/backbone/migrations/"
    if [ ${MIG_DIR} ] ; then
        export NO_AUTO_ADD_APPLICATIONS=1
        ${C_DIR}/manage.py syncdb --noinput
        unset NO_AUTO_ADD_APPLICATIONS
        ${C_DIR}/manage.py schemamigration backbone --initial
        ${C_DIR}/manage.py migrate
        echo ""
        echo "creating superuser"
        echo ""
        ${C_DIR}/manage.py createsuperuser
    else
        echo "migration directory ${MIG_DIR} present, refuse to operate"
    fi
else
    echo "need to be root to create database"
fi  
