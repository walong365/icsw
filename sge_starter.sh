#!/bin/sh

if [ "${JOB_SCRIPT}" = "QRSH" ] ; then
   # qrsh command, no jobscript
    exec $*
else
    if [ "$SGE_TASK_ID" = "" ] || [ "$SGE_TASK_ID" = "undefined" ]; then
       exec ${JOB_SCRIPT}.new $*
    else
       exec ${JOB_SCRIPT}.${SGE_TASK_ID}.new $*
    fi
fi

