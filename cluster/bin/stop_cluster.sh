#!/bin/bash

echo "Server scripts ... "
/opt/cluster/sbin/stop_server.sh $@

echo "Node scripts ... "
/opt/cluster/sbin/stop_node.sh $@
