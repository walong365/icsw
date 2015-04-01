#!/bin/bash

C_DIR="/opt/python-init/lib/python/site-packages/initat/cluster/"

if [ "${UID:-X}" = "0" ] ; then 
    if [ "${1:-X}" = "--no-initial-data" ] ; then
        ID_FLAGS="--no-initial-data"
    else
        ID_FLAGS=""
    fi
    MIG_DIR="${C_DIR}/backbone/migrations/"
    echo "migration_dir is ${MIG_DIR}, ID_FLAGS is '${ID_FLAGS}'"
    if [ ! -d ${MIG_DIR} ] ; then
        export NO_AUTO_ADD_APPLICATIONS=1
        ${C_DIR}/manage.py syncdb --noinput ${ID_FLAGS}
        unset NO_AUTO_ADD_APPLICATIONS
        ${C_DIR}/manage.py schemamigration backbone --initial
        ${C_DIR}/manage.py migrate ${ID_FLAGS}
        if [ -z "$1" ]; then
            echo ""
            echo "creating superuser"
            echo ""
            ${C_DIR}/manage.py createsuperuser
        fi
    else
        echo "migration directory ${MIG_DIR} present, refuse to operate"
    fi
else
    echo "need to be root to create database"
fi  
