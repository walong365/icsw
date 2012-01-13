#!/bin/bash

echo "Server scripts ... "
/usr/local/cluster/bin/disable_server.sh $@
echo "Node scripts ... "
/usr/local/sbin/disable_node.sh $@
