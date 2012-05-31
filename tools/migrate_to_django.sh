#!/bin/bash

file_list=$(cat /etc/sysconfig/cluster/db_access  | grep "=" | cut -d "=" -f 2 | grep "^/" | tr ";" "\n")

for conf in $file_list ; do
    [ -r $conf ] && break
done

[ -r $conf ] || { echo "No readable mysql-configfiles found, exiting..." ; exit -1 ; }

. $conf

echo "Migrates current database to django, configfile is $conf"

dump_name=$(mktemp /tmp/dbdump_XXXXXX)

echo "dump basename is ${dump_name}, postfixes are full and data"

mysql_dump.sh > ${dump_name}.full
mysql_dump.sh -d > ${dump_name}.data

C_DIR="/opt/python-init/lib/python/site-packages/cluster/"
MIG_DIR="${C_DIR}/backbone/migrations/"
if [ -d ${MIG_DIR} ] ; then
    echo "migration directory ${MIG_DIR} already exists, refuse to operate"
else
    echo "dropping and recreating database"
    
    echo "DROP DATABASE ${MYSQL_DATABASE}; CREATE DATABASE ${MYSQL_DATABASE}" |  mysql -u ${MYSQL_USER} -h ${MYSQL_HOST} -P ${MYSQL_PORT} -p${MYSQL_PASSWD} ${MYSQL_DATABASE}
    
    echo "sync database via django"

    # rewrite settings.py
    sed -i s/\"cluster.backbone\"/#\"cluster.backbone\"/g ${C_DIR}/settings.py
    ${C_DIR}/manage.py syncdb --noinput
    # reenable cluster.backbone settings.py
    sed -i s/#\"cluster.backbone\"/\"cluster.backbone\"/g ${C_DIR}/settings.py
    
    echo "create initial south information"
    
    ${C_DIR}/manage.py schemamigration backbone --initial
    ${C_DIR}/manage.py migrate backbone 
    
    echo "reinsert data"
    
    cat ${dump_name}.data | mysql -u ${MYSQL_USER} -h ${MYSQL_HOST} -P ${MYSQL_PORT} -p${MYSQL_PASSWD} ${MYSQL_DATABASE}
fi
