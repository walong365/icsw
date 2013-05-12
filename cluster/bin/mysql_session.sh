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

source $conf

mysql -u ${MYSQL_USER} -h ${MYSQL_HOST} -P ${MYSQL_PORT} -p${MYSQL_PASSWD} ${@:-${MYSQL_DATABASE}}
