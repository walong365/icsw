#!/bin/bash

export JOB_SCRIPT=/usr/local/share/home/local/development/clustersoftware/build-extern/rms-tools/sgetest/jobscript
./epilogue.py slayer local 1234 testjob testqueue

