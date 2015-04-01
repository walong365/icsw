#!/bin/bash

echo $*

echo "-----------------------------"

echo $PE_HOSTFILE

/opt/sge53/mpi/startmpi.sh -catch_rsh $PE_HOSTFILE
