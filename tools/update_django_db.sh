#!/bin/bash

C_DIR="/opt/python-init/lib/python/site-packages/initat/cluster/"
MIG_DIR="${C_DIR}/backbone/migrations/"
if [ -d ${MIG_DIR} ] ; then
    echo "migration schema, migration directory is ${MIG_DIR}"
    ${C_DIR}/manage.py schemamigration backbone --auto
    ${C_DIR}/manage.py migrate --no-initial-data backbone 
    /opt/cluster/bin/migrate_to_domain_name.py
else
    echo "no migration directory ${MIG_DIR} present, refuse to operate"
fi
