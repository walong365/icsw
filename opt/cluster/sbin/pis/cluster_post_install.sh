#!/bin/bash

export PREFIX_INIT=/opt/python-init/lib/python2.7/site-packages
export CLUSTER_PATH=/opt/cluster

# remove cached urls.py files
rm -f ${PREFIX_INIT}/initat/cluster/urls.py*
rm -rf ${PREFIX_INIT}/initat/core

if [ -x ${CLUSTER_PATH}/sbin/check_local_settings.py ] ; then
    ${CLUSTER_PATH}/sbin/check_local_settings.py
fi

# add idg to webserver group

if [ -f /etc/debian_version ] ; then
    usermod -G idg www-data
elif [ -f /etc/redhat-release ] ; then
    usermod -G idg apache
else
    usermod -G idg wwwrun
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
fi
