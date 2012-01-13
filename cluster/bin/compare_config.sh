#!/bin/bash

TEMP_DB1=tcdb1
TEMP_DB2=tcdb2

[ "$#" -lt 3 ] && { echo "Need 2 filenames and arguments (at least -v or -h) !"; /usr/local/cluster/bin/check_config.py -h ; exit -1 ; }

echo "Creating temporary databases ${TEMP_DB1} from '$1' and ${TEMP_DB2} from '$2' ..."
echo "DROP DATABASE IF EXISTS ${TEMP_DB1} ; CREATE DATABASE ${TEMP_DB1} ; " | mysql_session.sh
echo "DROP DATABASE IF EXISTS ${TEMP_DB2} ; CREATE DATABASE ${TEMP_DB2} ; " | mysql_session.sh

tar -C / -xjf $1
cat /tmp/db_dump | mysql_session.sh ${TEMP_DB1}
rm -f /tmp/db_dump

shift

tar -C / -xjf $1
cat /tmp/db_dump | mysql_session.sh ${TEMP_DB2}
rm -f /tmp/db_dump

shift

/usr/local/cluster/bin/check_config.py -p ${TEMP_DB1} -d ${TEMP_DB2} $@

echo "Deleting temporary databases ${TEMP_DB1} and ${TEMP_DB2}"
echo "DROP DATABASE IF EXISTS ${TEMP_DB1} ; " | mysql_session.sh
echo "DROP DATABASE IF EXISTS ${TEMP_DB2} ; " | mysql_session.sh

