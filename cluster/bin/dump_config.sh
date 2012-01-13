#!/bin/bash

PATH=$PATH:/usr/local/cluster/bin

[ "$#" != 1 ] && { echo "Need filename !"; exit -1 ; }

dtb_temp=/tmp/db_dump

for db in ng_check_command config config_int config_str config_blob snmp_config snmp_mib config_type ; do 
    mysql_dump.sh $db -c --add-drop-table >> $dtb_temp
done

tar cjf $1 $dtb_temp

rm -rf $dtb_temp

