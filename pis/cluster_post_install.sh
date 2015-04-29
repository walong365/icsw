#!/bin/bash

export PREFIX_INIT=/opt/python-init/lib/python/site-packages
export CLUSTER_PATH=/opt/cluster

# remove cached urls.py files
rm -f ${PREFIX_INIT}/initat/cluster/urls.py*
rm -rf ${PREFIX_INIT}/initat/core

if [ -x ${CLUSTER_PATH}/sbin/check_local_settings.py ] ; then
    ${CLUSTER_PATH}/sbin/check_local_settings.py
fi

if [ -f /etc/sysconfig/cluster/db.cf ] ; then
    # already installed
    if [ -f /etc/sysconfig/cluster/db_auto_update ] ; then
        echo "running auto-update script ${CLUSTER_PATH}/sbin/icsw setup --migrate"
        ${CLUSTER_PATH}/sbin/icsw setup --migrate
    else
        echo "to update the current database schema via django please use ${CLUSTER_PATH}/sbin/setup_cluster.py --migrate"
    fi
else
    echo "to create a new database use ${CLUSTER_PATH}/sbin/icsw setup"

    # do not show, only for ALN
    # echo "to migrate the database to a django-support format please use %{CLUSTER_PATH}/sbin/migrate_to_django.sh"
    # echo "to migrate the current user structure use %{CLUSTER_PATH}/sbin/create_django_users.py"
fi
