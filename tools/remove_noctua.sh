#!/bin/bash

if rpm -q noctua > /dev/null ; then
    echo "NOCTUA is installed, removing";
    /opt/cluster/sbin/check_scripts.py --mode stop --instance ALL ;
    zypper remove -u cluster-backbone-sql ;
    DB_FILE=/opt/cluster/db/noctua.db
    if [ -f ${DB_FILE} ] ; then
        echo "moving SQLite database ${DB_FILE} to /tmp"
        mv ${DB_FILE} /tmp
    fi
else
    echo "NOCTUA not installed";
fi

