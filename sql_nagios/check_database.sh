#!/bin/bash
#
# Copyright (C) 2008 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of nagios
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

function print_usage () {
    echo "Usage:"
    echo ""
    echo "  $0 [--verify] [-h]"
    echo "  [--verify] verify database before check"
}

args=$(getopt -l verify h $*) || { print_usage ; exit -1 ; }

set -- $args

verify=0;

for i ; do
    case "$i" in
	--verify) shift ; verify=1 ;;
	-h) shift ; print_usage ; exit -1 ;;
	--) shift ; break ;;
    esac
done

cdir=/opt/nagios/sql
file_list=$(cat /etc/sysconfig/cluster/db_access  | grep "=" | cut -d "=" -f 2 | grep "^/" | tr ";" "\n")

for conf in $file_list ; do
    [ -r $conf ] && break
done

[ -r $conf ] || { echo "No readable mysql-configfiles found, exiting..." ; exit -1 ; }

source $conf

NAGIOS_DATABASE=nagiosdb
TEMP_DATABASE=ngtemp

echo "Deleting old tables and creating temporary nagios database ..."
echo "DROP DATABASE IF EXISTS $TEMP_DATABASE ; CREATE DATABASE $TEMP_DATABASE ; " | mysql -u ${MYSQL_USER} -h ${MYSQL_HOST} -p${MYSQL_PASSWD} 

echo "Creating nagios tables ..."
mysql -u ${MYSQL_USER} -h ${MYSQL_HOST} -p${MYSQL_PASSWD} ${TEMP_DATABASE} < ${cdir}/create_nagios_tables.sql
mysql -u ${MYSQL_USER} -h ${MYSQL_HOST} -p${MYSQL_PASSWD} ${TEMP_DATABASE} < ${cdir}/mysql-mods-1.4b8.sql

dump_orig=`mktemp /tmp/mysql_dump_XXXXXX`
dump_temp=`mktemp /tmp/mysql_dump_XXXXXX`
# original database
mysqldump -u ${MYSQL_USER} -h ${MYSQL_HOST} -p${MYSQL_PASSWD} ${NAGIOS_DATABASE} --add-drop-table -d | sed -r s/\ AUTO_INCREMENT=[0-9]+//g > $dump_orig
mysqldump -u ${MYSQL_USER} -h ${MYSQL_HOST} -p${MYSQL_PASSWD} ${TEMP_DATABASE} --add-drop-table -d | sed -r s/\ AUTO_INCREMENT=[0-9]+//g > $dump_temp

echo "Database diff:"

diff -s -I "^--" -u $dump_orig $dump_temp

rm -f $dump_orig $dump_temp

echo "Python Database diff:"
if [ "$verify" = "1" ] ; then
    /usr/local/cluster/bin/check_database.py --verify ${NAGIOS_DATABASE} ${TEMP_DATABASE}
else
    /usr/local/cluster/bin/check_database.py ${NAGIOS_DATABASE} ${TEMP_DATABASE}
fi

echo "Removing temporary databases ..."
echo "DROP DATABASE IF EXISTS $TEMP_DATABASE ; " | mysql -u ${MYSQL_USER} -h ${MYSQL_HOST} -p${MYSQL_PASSWD}
