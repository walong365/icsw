#!/bin/bash

if [ "$#" -gt 0 ] ; then
    stop_type="Force-stopping"
    stop_arg="force-stop"
else
    stop_type="Stopping"
    stop_arg="stop"
fi

if [ -f /etc/rc.status ] ; then
    . /etc/rc.status
else
    . /etc/rc.status_suse
fi

for node in hoststatus logging-server meta-server host-monitoring package-client ; do
    rc_reset
    if [ -f /etc/init.d/$node ] ; then
	/etc/init.d/$node $stop_arg
    else
	echo -n "$stop_type $node ... "
	rc_status -u
    fi
done
