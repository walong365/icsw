#!/bin/bash

for server in logcheck-server package-server mother rrd-server sge-server cluster-server cluster-config-server host-relay nagios-config-server ; do
    if [ -f /etc/init.d/$server ] ; then
	insserv -r $server
	chkconfig $server off
    fi
done
