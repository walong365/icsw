#!/bin/bash

# source mysql.cf
. /etc/sysconfig/cluster/mysql.cf

# read line
inline=`cat /dev/stdin`

# parse line
YP_USER=`echo $inline | cut -d " " -f 1`
YP_PASSWD_NEW=`echo $inline | cut -d " " -f 3 | cut -d ":" -f 2-`

logger "Changing passwor of user $YP_USER"
echo "UPDATE user SET password='$YP_PASSWD_NEW' WHERE login='$YP_USER'" | mysql -h ${MYSQL_HOST} -P ${MYSQL_PORT} -u ${MYSQL_USER} -p${MYSQL_PASSWD} ${MYSQL_DATABASE}

logger "Database changed, signaling cluster-server"
/usr/local/sbin/send_command.py localhost 8004 write_yp_config | logger

logger "done"
echo -e "OK\n"
