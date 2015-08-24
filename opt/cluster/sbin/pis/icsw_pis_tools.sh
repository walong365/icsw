#!/bin/bash

function is_chroot() {
    p1_inode=$(ls --color=no -di /proc/1/root/ | tr -s " " | cut -d " " -f 1)
    root_inode=$(ls --color=no -di / | tr -s " " | cut -d " " -f 1)
    if [ "${p1_inode}" = "${root_inode}" ] ; then
        return 1
    else
        return 0
    fi
}
