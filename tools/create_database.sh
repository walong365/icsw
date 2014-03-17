#!/bin/bash

LIB_DIR="/opt/python-init/lib/python/site-packages"
C_DIR="${LIB_DIR}/initat/cluster/"
MIG_DIR="${C_DIR}/backbone/migrations/"

if [ "${UID:-X}" != "0" ] ; then 
    echo "need to be root to create database"
    exit -1
fi  

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
else
    echo "checking for existing migrations"
    ok=1
    for mig_dir in static_precompiler reversion django/contrib/auth initat/cluster/backbone initat/cluster/liebherr ; do
	fm_dir="${LIB_DIR}/${mig_dir}/migrations"
	if [ -d ${fm_dir} ] ; then
            echo "migration directory present: ${fm_dir}"
            ok=0
	fi
    done
    if [ "${ok}" = "0" ] ; then
        echo "some migrations still presents, refuse to operate (call $0 with --clear-migrations)"
        exit -1
    fi
fi

if [ "${1:-X}" = "--no-initial-data" ] ; then
    ID_FLAGS="--no-initial-data"
    shift
else
    ID_FLAGS=""
fi
MIG_DIR="${C_DIR}/backbone/migrations/"
echo "migration_dir is ${MIG_DIR}, ID_FLAGS is '${ID_FLAGS}'"
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
if [ "${ID_FLAGS}" == "--no-initial-data" ] ; then
    echo "skipping initial data insert"
else
    if [ "${1:-x}" != "--auto" ]; then
	echo ""
	echo "creating superuser"
	echo ""
	${C_DIR}/manage.py createsuperuser
    fi
    ${C_DIR}/manage.py init_csw_permissions
    ${C_DIR}/manage.py create_fixtures
    ${C_DIR}/manage.py migrate_to_domain_name
    ${C_DIR}/manage.py migrate_to_config_catalog
    ${C_DIR}/manage.py create_cdg --name system
fi
