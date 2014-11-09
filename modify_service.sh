#!/bin/bash

ACTION=$1
SRV_NAME=$2

if [ -f /etc/corosync/corosync.conf ] ; then
    export HA=1
else
    export HA=0
fi

export INIT=/etc/init.d

ret_state=0

if [ "${ACTION}" = "activate" ] ; then
    if [ "${HA}" = "0" ] ; then
	if [ -f /etc/redhat-release ] ; then
            /opt/cluster/sbin/force_redhat_init_script.sh ${SRV_NAME}
            /sbin/chkconfig --add ${SRV_NAME}
	else
            /sbin/insserv ${INIT}/${SRV_NAME}
	fi
    fi
elif [ "${ACTION}" = "deactivate" ] ; then
    if [ "${HA}" = "0" ] ; then
	if [ -f /etc/redhat-release ] ; then
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
