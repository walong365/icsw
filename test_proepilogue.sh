#!/bin/bash

export JOB_SCRIPT=$(pwd)/testjob
export PE_HOSTFILE=test_pefile
#./proepilogue.py slayer local 4004 testjob p4.q@slayer ; echo $?
./pestart eddie local 4004 testjob p4.q@eddie ; echo "returncode=$?"

