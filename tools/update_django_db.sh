#!/bin/bash

C_DIR="/opt/python-init/lib/python/site-packages/initat/cluster/"
MIG_DIR="${C_DIR}/backbone/migrations/"

if [ -d ${MIG_DIR} ] ; then
    echo "migrating schema, migration directory is ${MIG_DIR}"
    sync_apps="liebherr"
    for sync_app in ${sync_apps} ; do
	if [ -d "${C_DIR}${sync_app}" ] ; then
            echo "syncing app ${sync_app}"
            ${C_DIR}/manage.py schemamigration ${sync_app} --auto
            ${C_DIR}/manage.py migrate ${sync_app}
	fi
    done
    if [ -x /opt/cluster/sbin/check_local_settings.py ] ; then
	/opt/cluster/sbin/check_local_settings.py
    fi
    ${C_DIR}/manage.py schemamigration backbone --auto
    ${C_DIR}/manage.py migrate --no-initial-data backbone 
    ${C_DIR}/manage.py create_fixtures
    ${C_DIR}/manage.py init_csw_permissions
    ${C_DIR}/manage.py migrate_to_domain_name
    ${C_DIR}/manage.py migrate_to_config_catalog
else
    echo "no migration directory ${MIG_DIR} present, refuse to operate"
fi
