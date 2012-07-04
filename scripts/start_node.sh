#!/bin/bash

if [ -f /etc/rc.status ] ; then
    . /etc/rc.status
else
    . /etc/rc.status_suse
fi

for node in hoststatus logging-server meta-server host-monitoring package-client ; do
    rc_reset
    if [ -f /etc/init.d/$node ] ; then
	/etc/init.d/$node start
    else
	echo -n "Starting $node ... "
	rc_status -u
    fi
done
