#!/bin/bash

file=/usr/local/share/RPMs/tars/`hostname`_`date +%c | tr " " "_" | tr ":" "_"`.tar.bz2

echo $file

flist=""
for p in $(cat /usr/local/cluster/etc/all_rpms ) ; do
    rpm -q $p > /dev/null && {
	flist="$flist $(rpm -V $p | tr ' ' '\n' | grep '/' | grep -v nb-pics)"
    }
done

echo "Found $(echo $flist | wc -w) changed files"

tar cjpsvf $file $flist
