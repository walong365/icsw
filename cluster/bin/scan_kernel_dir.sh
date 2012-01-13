#!/bin/bash

sql_query () {
	echo $* | mysql -s -u ${MYSQL_USER}  -h ${MYSQL_HOST} -p${MYSQL_PASSWD} -D ${MYSQL_DATABASE}
}

CONFIGFILE='/usr/local/cluster/etc/mysql.cf'
if [ -f $CONFIGFILE ] ; then
    . $CONFIGFILE ;
    dev_idx=$(sql_query "SELECT d.device_idx FROM device d WHERE d.name='$(hostname)'")
    if [ "${dev_idx:-0}" = "0" ] ; then
	echo "No device-entry found for this host, exiting ..."
	exit -1
    fi
    kdir=/tftpboot/kernels
    for k in $kdir/* ; do
	if [ -d $k ] ; then
	    if [ -f "$k/.version" ] ; then
		echo "Scanning kernel $k..."
		cat $k/.version | grep -v BUILDDATE >/tmp/.build_bla
		. /tmp/.build_bla
		kname=$(basename $k)
		kernel_idx=$(sql_query "SELECT k.kernel_idx FROM kernel k WHERE k.name='$kname'")
		if [ "${kernel_idx:-0}" = "0" ] ; then
		    build_machine=$(echo $BUILDMACHINE | cut -d "." -f 1 | sed s/dev90_64/dev90-64/g)
		    if [ "$build_machine" = "$(hostname)" ] ; then
			echo "Inserting info for kernel $kname"
			version=$(echo $VERSION | cut -d "." -f 1)
			release=$(echo $VERSION | cut -d "." -f 2)
			sql_str="INSERT INTO kernel SET name='$kname',version=$version,release=$release,build_machine='$(hostname -f)',device=$dev_idx,target_dir='$k',config_name='/usr/src/config/.config_$CONFIGNAME' "
			[ -s "$k/.comment" ] && sql_str="$sql_str,comment='$(cat $k/.comment)'"
			sql_query $sql_str
		    else
			echo "  Kernel was not builded on this host ($build_machine != $(hostname)), skipping ..."
		    fi
		else
		    if [ -s "$k/.comment" ] ; then
			sql_query "UPDATE kernel set comment='$(cat $k/.comment)' WHERE kernel_idx=$kernel_idx"
		    fi
		    echo "  Kernel $kname already in database, skipping ..."
		fi
	    else
		echo "$k has no .version-file, skipping ..."
	    fi
	else
	    echo "$k is not a directory, skipping ..."
	fi
    done
else
    echo "No configfile for database, exiting "
fi
