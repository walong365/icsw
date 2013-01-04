#!/bin/bash

if [ -f /etc/rc.status ] ; then
    . /etc/rc.status
else
    . /etc/rc.status_suse
fi

for server in logcheck-server package-server mother sge-server cluster-server cluster-config-server host-relay snmp-relay md-config-server ; do
    rc_reset
    if [ -f /etc/init.d/$server ] ; then
        /etc/init.d/$server start
    else
        echo -n "Starting $server ... "
        rc_status -u
    fi
done
