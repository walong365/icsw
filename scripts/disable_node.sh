#!/bin/bash

for node in hoststatus logging-server meta-server host-monitoring package-client ; do
    if [ -f /etc/init.d/$node ] ; then
		insserv -r $node
		chkconfig $node off
    fi
done
