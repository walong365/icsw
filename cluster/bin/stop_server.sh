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

for server in logcheck-server package-server mother sge-server cluster-server cluster-config-server host-relay snmp-relay md-config-server ; do
    rc_reset
    if [ -f /etc/init.d/$server ] ; then
        /etc/init.d/$server $stop_arg
    else
        echo -n "$stop_type $server ... "
        rc_status -u
    fi
done
