#!/bin/bash

uids="`ps auxn --no-headers | tr -s ' ' | cut -d ' ' -f 2 | sort |uniq` "
cat /proc/sysvipc/shm | grep -v key | while read line ; do
    shmid=`echo $line | cut -d " " -f 2`
    uid=`echo $line | cut -d " " -f 10`
    echo $uids | grep "$uid\ " > /dev/null || {
	echo "`hostname`: Delete shmid $shmid, uid $uid";
	ipcrm -m $shmid
    } && {
	echo "shm $shmid in use by user $uid"
    }
done
