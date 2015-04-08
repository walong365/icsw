#!/bin/bash

# shutdown script

# soft shutdown command, replace with halt
SSD_COM="status"
# hard shutdown command, replace with poweroff
HSD_COM="status"

SD_LIST="node01 node02 node03 node04 node05 node06 node07 node08 node09 node10 login"

for node in ${SD_LIST} ; do
    send_command_zmq.py -p 2002 --raw -H ${node} ${HSD_COM}
done

# wait some time
sleep 15

for node in ${SD_LIST} ; do
    ipmi_node=ipmi-${node}.ims.mgmt
    ipmitool -H ${ipmi_node} -U ADMIN -P ADMIN chassis power ${HSD_COM}
done
