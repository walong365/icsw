#!/bin/bash

SDS="proc sys dev"

function do_umount() {
    echo "Unmounting ${SDS} ..."
    for sd in ${SDS} ; do
        umount ${path}/${sd}
    done
}

function do_mount() {
    echo "Mounting ${SDS} ..."
    for sd in ${SDS} ; do
        if [ "${sd}" == "proc" ] ; then
	    mount -t proc proc ${path}/${sd}
        elif [ "${sd}" == "sys" ] ; then
	    mount -t sysfs sysfs ${path}/${sd}
        elif [ "${sd}" == "dev" ] ; then
	    mount -o bind /dev ${path}/${sd}
	fi
    done
    mount | grep ${path}
}

image=$1
shift

path=/opt/cluster/system/images/${image}

if [ ! -d ${path} ] ; then
    echo "No image found at ${path}"
    exit -1
fi

if [ -n "$*" ] ; then
    echo "executing \"$*\" in ${path}"
    do_umount
    do_mount
    chroot ${path} $*
    do_umount
else
    echo "No command given"
fi
