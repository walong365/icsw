#!/bin/bash
# Copyright (C) 2012-2015 Andreas Lang-Nevyjel, lang-nevyjel@init.at

echo $$ > /.firmware_pid

FW_SYS_DIR=/sys/class/firmware
FW_DIR=/lib/firmware/

while true ; do
    if [ -d ${FW_SYS_DIR} ] ; then
        for link_name in $(find ${FW_SYS_DIR} -type l) ; do
            export DEVICE=$(readlink -f ${link_name})
            . ${DEVICE}/uevent
            echo "requesting firmware $FIRMWARE"
            fw_file=$(find ${FW_DIR} -iname $(basename ${FIRMWARE}) | head -n 1)
            if [ "${fw_file:-X}" = "X" ] ; then
                echo "Firmwarefile ${FIRMWARE} not found"
            else
                echo "found firmwarefile ${fw_file}"
                echo 1 > ${DEVICE}/loading
                cat ${fw_file} > ${DEVICE}/data
                echo 0 > ${DEVICE}/loading
            fi
        done
    fi
    sleep 1
done
