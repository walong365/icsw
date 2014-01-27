#!/bin/bash

LIB_DIR="/opt/python-init/lib/python/site-packages"
C_DIR="${LIB_DIR}/initat/cluster/"
MIG_DIR="${C_DIR}/backbone/migrations/"

if [ "${1:-X}" == "--clear-migrations" ] ; then
    shift
    echo "clearing migrations"
    for mig_dir in static_precompiler reversion django/contrib/auth initat/cluster/backbone initat/cluster/liebherr ; do
	fm_dir="${LIB_DIR}/${mig_dir}/migrations"
	if [ -d ${fm_dir} ] ; then
	    echo "clearing migration dir ${fm_dir}"
	    rm -rf ${fm_dir}
	fi
    done
fi

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
        export INITIAL_MIGRATION_RUN=1
        ${C_DIR}/manage.py syncdb --noinput ${ID_FLAGS}
        unset NO_AUTO_ADD_APPLICATIONS
        unset INITIAL_MIGRATION_RUN
        ${C_DIR}/manage.py schemamigration django.contrib.auth --initial
        ${C_DIR}/manage.py schemamigration backbone --initial
        ${C_DIR}/manage.py schemamigration reversion --initial
	${C_DIR}/manage.py schemamigration static_precompiler --initial
	sync_apps="liebherr"
	for sync_app in ${sync_apps} ; do
	    if [ -d "${C_DIR}${sync_app}" ] ; then
		echo "syncing app ${sync_app}"
		${C_DIR}/manage.py schemamigration ${sync_app} --auto
		${C_DIR}/manage.py migrate ${sync_app}
	    fi
	done
        ${C_DIR}/manage.py migrate auth
        ${C_DIR}/manage.py migrate backbone --no-initial-data
        ${C_DIR}/manage.py migrate reversion
        ${C_DIR}/manage.py migrate static_precompiler
        ${C_DIR}/manage.py syncdb --noinput ${ID_FLAGS}
        ${C_DIR}/manage.py migrate ${ID_FLAGS}
        if [ -z "$1" ]; then
            echo ""
            echo "creating superuser"
            echo ""
            ${C_DIR}/manage.py createsuperuser
        fi
	${C_DIR}/manage.py init_csw_permissions
	${C_DIR}/manage.py loaddata ${C_DIR}/backbone/fixtures/initial_new_data.xml
	/opt/cluster/bin/migrate_to_domain_name.py --init
    else
        echo "migration directory ${MIG_DIR} present, refuse to operate"
    fi
else
    echo "need to be root to create database"
fi  
