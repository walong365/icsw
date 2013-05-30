#!/bin/bash

C_DIR="/opt/python-init/lib/python/site-packages/initat/cluster/"
MIG_DIR="${C_DIR}/backbone/migrations/"
bu_name=${1:-xxx}

if [ ! -f ${bu_name} ] ; then
    echo "Backupfile missing"
    exit -1
fi

if [ "${UID:-X}" = "0" ] ; then 
    if [ ! -d ${MIG_DIR} ] ; then
        echo "resetting database"
        ${C_DIR}/manage.py reset_db -R default --noinput
        echo "initial setup"
        /opt/cluster/sbin/create_database.sh --no-initial-data
        echo "cleaning up database"
        echo "from django.contrib.auth.models import Permission; Permission.objects.all().delete()" | ${C_DIR}manage.py shell
        echo "from django.contrib.contenttypes.models import ContentType; ContentType.objects.all().delete()" | ${C_DIR}manage.py shell
        echo "loading values"
        ${C_DIR}/manage.py loaddata ${bu_name}
    else
        echo "migration directory ${MIG_DIR} present, refuse to operate"
    fi
else
    echo "you better be root"
fi
