#!/bin/bash

if [ $# -lt 2 ] ; then
    echo "need action and service name"
    exit -1
fi

ACTION=$1
SRV_NAME=$2

if [ "${SRV_NAME}" == "logging-server" -o "${SRV_NAME}" == "meta-server" ] ; then
    export HA=0
else
    if [ -f /etc/corosync/corosync.conf ] ; then
        echo "HA-setup detected, skipping automatic activation and deactivation for ${SRV_NAME}"
        export HA=1
    else
        export HA=0
    fi
fi

export INIT=/etc/init.d

ret_state=0

if [ "${ACTION}" = "activate" ] ; then
    if [ "${HA}" = "0" ] ; then
        if [ -f /etc/debian_version ] ; then
            /usr/sbin/update-rc.d ${SRV_NAME} defaults
            /usr/sbin/update-rc.d ${SRV_NAME} enable
            # /usr/sbin/update-rc.d -f ${SRV_NAME} remove
        elif [ -f /etc/redhat-release ] ; then
            /opt/cluster/sbin/force_redhat_init_script.sh ${SRV_NAME}
            /sbin/chkconfig --add ${SRV_NAME}
        else
            /sbin/insserv ${INIT}/${SRV_NAME}
        fi
    fi
elif [ "${ACTION}" = "deactivate" ] ; then
    if [ "${HA}" = "0" ] ; then
        if [ -f /etc/debian_version ] ; then
            /usr/sbin/update-rc.d ${SRV_NAME} defaults
            /usr/sbin/update-rc.d ${SRV_NAME} disable
            /usr/sbin/update-rc.d -f ${SRV_NAME} remove
            # /usr/sbin/update-rc.d ${SRV_NAME} start 28 2 3 5 . stop 72 0 1 4 6
        elif [ -f /etc/redhat-release ] ; then
            /opt/cluster/sbin/force_redhat_init_script.sh ${SRV_NAME}
            /sbin/chkconfig --del ${SRV_NAME}
        else
            /sbin/insserv -r ${INIT}/${SRV_NAME}
        fi
    fi
else
    echo "unknown action \"${ACTION}\""
    ret_state=1
fi

exit ${ret_state}