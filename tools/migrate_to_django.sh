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

C_DIR="/opt/python-init/lib/python/site-packages/init/cluster/"
MIG_DIR="${C_DIR}/backbone/migrations/"
if [ -d ${MIG_DIR} ] ; then
    echo "migration directory ${MIG_DIR} already exists, refuse to operate"
else
    echo "dropping and recreating database"
    
    echo "DROP DATABASE ${MYSQL_DATABASE}; CREATE DATABASE ${MYSQL_DATABASE}" |  mysql -u ${MYSQL_USER} -h ${MYSQL_HOST} -P ${MYSQL_PORT} -p${MYSQL_PASSWD} ${MYSQL_DATABASE}
    
    echo "sync database via django"

    # put old models file in place, a little hacky but working
    cp -a ${C_DIR}/backbone/models.py ${C_DIR}/backbone/models_new.py
    cp -a ${C_DIR}/backbone/models_old_csw.py ${C_DIR}/backbone/models.py
    # put old initial_data in place
    cp -a ${C_DIR}/backbone/fixtures/initial_data.py ${C_DIR}/backbone/fixtures/initial_data_new.py
    cp -a ${C_DIR}/backbone/fixtures/initial_data_old_csw.py ${C_DIR}/backbone/fixtures/initial_data.py
    export NO_AUTO_ADD_APPLICATIONS=1
    ${C_DIR}/manage.py syncdb --noinput
    unset NO_AUTO_ADD_APPLICATIONS
    
    echo "create initial south information"
    
    ${C_DIR}/manage.py schemamigration backbone --initial
    ${C_DIR}/manage.py migrate backbone --no-initial-data
    
    echo "reinsert data"
    
    cat ${dump_name}.data | /opt/cluster/sbin/db_magic.py | mysql -u ${MYSQL_USER} -h ${MYSQL_HOST} -P ${MYSQL_PORT} -p${MYSQL_PASSWD} ${MYSQL_DATABASE}

    # restore new models file
    cp -a ${C_DIR}/backbone/models.py ${C_DIR}/backbone/models_old_csw.py
    cp -a ${C_DIR}/backbone/models_new.py ${C_DIR}/backbone/models.py
    # restore fixture file
    cp -a ${C_DIR}/backbone/fixtures/initial_data.py ${C_DIR}/backbone/fixtures/initial_data_old_csw.py
    cp -a ${C_DIR}/backbone/fixtures/initial_data_new.py ${C_DIR}/backbone/fixtures/initial_data.py

    echo "database migrated. Now please call"
    echo " - ${C_DIR}/sbin/create_django_users.py    to migrate the users"
    echo " - ${C_DIR}/sbin/update_django_db.sh       to update to the latest database schema"
fi
