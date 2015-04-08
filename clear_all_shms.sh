#!/bin/bash

for i in `cat /etc/nodenames` ; do
    echo "Host $i..."
    rsh $i /opt/sge/3rd_party/clear_shm.sh
done
