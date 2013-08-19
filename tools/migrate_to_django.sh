#!/bin/bash

if [ -f /etc/sysconfig/cluster/db_access ] ; then
    file_list=$(cat /etc/sysconfig/cluster/db_access  | grep "=" | cut -d "=" -f 2 | grep "^/" | tr ";" "\n")
else
    file_list="/etc/sysconfig/cluster/db.cf"
fi

for conf in $file_list ; do
    [ -r $conf ] && break
done
    

[ -r $conf ] || { echo "No readable mysql-configfiles found, exiting..." ; exit -1 ; }

. $conf

if [ "$(basename $conf)" != "db.cf" ] ; then
    export DB_PORT=${MYSQL_PORT}
    export DB_DATABASE=${MYSQL_DATABASE}
    export DB_USER=${MYSQL_USER}
    export DB_HOST=${MYSQL_HOST}
    export DB_PASSWD=${MYSQL_PASSWD}
fi

echo "Migrates current database to django, configfile is $conf"

dump_name=$(mktemp /tmp/dbdump_XXXXXX)

echo "dump basename is ${dump_name}, postfixes are full and data"

mysql_dump.sh > ${dump_name}.full
mysql_dump.sh -d > ${dump_name}.data

group_xml=/tmp/cgroup.xml
user_xml=/tmp/cuser.xml
echo "group XML dump is ${group_xml}, user XML dump is ${user_xml}"
echo "SELECT * FROM ggroup" | mysql_session.sh cdbase -X > ${group_xml}
echo "SELECT * FROM user" | mysql_session.sh cdbase -X > ${user_xml}
echo "protecting ${group_xml} and ${user_xml}"
chmod 0400 ${group_xml} ${user_xml}

C_DIR="/opt/python-init/lib/python/site-packages/initat/cluster/"
CLUSTER_DIR=/opt/cluster
MIG_DIR="${C_DIR}/backbone/migrations/"
if [ -d ${MIG_DIR} ] ; then
    echo "migration directory ${MIG_DIR} already exists, refuse to operate"
else
    echo "dropping and recreating database"
    
    echo "DROP DATABASE ${DB_DATABASE}; CREATE DATABASE ${DB_DATABASE}" |  mysql -u ${DB_USER} -h ${DB_HOST} -P ${DB_PORT} -p${DB_PASSWD} ${DB_DATABASE}
    
    echo "sync database via django"

    # put old models file in place, a little hacky but working
    cp -a ${C_DIR}/backbone/models.py ${C_DIR}/backbone/models_new.py
    cp -a ${C_DIR}/backbone/models_old_csw.py ${C_DIR}/backbone/models.py
    # delete all created pyo/pyc models files
    rm -f ${C_DIR}/backbone/models.py?
    # put old initial_data in place
    cp -a ${C_DIR}/backbone/fixtures/initial_data.xml ${C_DIR}/backbone/fixtures/initial_data_new.xml
    cp -a ${C_DIR}/backbone/fixtures/initial_data_old_csw.xml ${C_DIR}/backbone/fixtures/initial_data.xml
    export NO_AUTO_ADD_APPLICATIONS=1
    ${C_DIR}/manage.py syncdb --noinput
    unset NO_AUTO_ADD_APPLICATIONS
    
    echo "create initial south information"
    
    ${C_DIR}/manage.py schemamigration backbone --initial
    ${C_DIR}/manage.py migrate backbone --no-initial-data
    ${C_DIR}/manage.py migrate reversion

    echo "reinsert data"
    
    cat ${dump_name}.data | /opt/cluster/sbin/db_magic.py | mysql -u ${DB_USER} -h ${DB_HOST} -P ${DB_PORT} -p${DB_PASSWD} ${DB_DATABASE}

    # restore new models file
    cp -a ${C_DIR}/backbone/models.py ${C_DIR}/backbone/models_old_csw.py
    cp -a ${C_DIR}/backbone/models_new.py ${C_DIR}/backbone/models.py
    # delete all created pyo/pyc models files
    rm -f ${C_DIR}/backbone/models.py?
    # restore fixture file
    cp -a ${C_DIR}/backbone/fixtures/initial_data.xml ${C_DIR}/backbone/fixtures/initial_data_old_csw.xml
    cp -a ${C_DIR}/backbone/fixtures/initial_data_new.xml ${C_DIR}/backbone/fixtures/initial_data.xml

    echo "database migrated. Now please call"
    echo " - ${CLUSTER_DIR}/sbin/create_django_users.py                           to migrate the users or"
    echo " - ${CLUSTER_DIR}/sbin/restore_user_group.py ${group_xml} ${user_xml}   to restore the users"
    echo " - ${CLUSTER_DIR}/sbin/update_django_db.sh                              to update to the latest database schema, then"
    echo " - ${CLUSTER_DIR}/sbin/fix_models.py ${dump_name}.data                  to fix wrong foreign keys (from 0 to None)"
fi

