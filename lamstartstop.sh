#!/bin/bash

echo $@

echo $0

echo $PATH

cat $8

if [ "`basename $0`" = "lamstart" ] ; then
   lamboot -v $8
else
   wipe -v
fi

exit 0
