#!/bin/bash

if rpm -q noctua > /dev/null ; then
    echo "NOCTUA is installed, removing";
    /opt/cluster/sbin/check_scripts.py --mode stop --instance ALL ;
    zypper remove -u cluster-backbone-sql python-modules-base ;
    DB_FILE=/opt/cluster/db/noctua.db
    if [ -f ${DB_FILE} ] ; then
        echo "moving SQLite database ${DB_FILE} to /tmp"
        mv ${DB_FILE} /tmp
    fi
    # remove all migrations, not needed here (done via setup_cluster.py)
    #echo "removing all migration dirs"
    #find /opt/python-init/lib/python/site-packages/ -type d -iname migrations -exec rm -rf {} \;
else
    echo "NOCTUA not installed";
fi

