#!/bin/bash

logger "/opt/sge/3rd_party/qlogin_wrapper: $1 $2"

HOST=$1
PORT=$2
/usr/bin/ssh -X -p $PORT $HOST
