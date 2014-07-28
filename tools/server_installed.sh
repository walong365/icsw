#!/bin/bash

export PREFIX_INIT=/opt/python-init/lib/python/site-packages
export CLUSTER_PATH=/opt/cluster

if [ -d ${PREFIX_INIT}/initat/cluster/backbone/migrations ] ; then
    # already installed
    ${CLUSTER_PATH}/sbin/setup_cluster.py --only-fixtures
fi
