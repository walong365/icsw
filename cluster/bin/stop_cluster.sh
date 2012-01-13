#!/bin/bash

echo "Server scripts ... "
/usr/local/cluster/bin/stop_server.sh $@
echo "Node scripts ... "
/usr/local/sbin/stop_node.sh $@
