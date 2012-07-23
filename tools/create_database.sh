#!/bin/bash

C_DIR="/opt/python-init/lib/python/site-packages/init/cluster/"

MIG_DIR="${C_DIR}/backbone/migrations/"
if [ ${MIG_DIR} ] ; then
    export NO_AUTO_ADD_APPLICATIONS=1
    ${C_DIR}/manage.py syncdb --noinput
    unset NO_AUTO_ADD_APPLICATIONS
    ${C_DIR}/manage.py schemamigration backbone --initial
    ${C_DIR}/manage.py migrate
else
    echo "migration directory ${MIG_DIR} present, refuse to operate"
fi
