#!/bin/bash

PATH=$PATH:/usr/local/cluster/bin

TEMP_DB=tcdb

[ "$#" -lt 2 ] && { echo "Need filename and mode (at least -v or -h)!"; /usr/local/cluster/bin/check_config.py -h ; exit -1 ; }

tar -C / -xjf $1

shift

echo "Creating temporary database ${TEMP_DB}"
echo "DROP DATABASE IF EXISTS ${TEMP_DB} ; CREATE DATABASE ${TEMP_DB} ; " | mysql_session.sh

cat /tmp/db_dump | mysql_session.sh ${TEMP_DB}

/usr/local/cluster/bin/check_config.py -d ${TEMP_DB} $@

echo "Deleting temporary database ${TEMP_DB}"
echo "DROP DATABASE IF EXISTS ${TEMP_DB} ; " | mysql_session.sh

rm -f /tmp/db_dump
