#!/bin/bash
# Copyright (C) 2013-2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

source $(dirname $0)/icsw_pis_tools.sh

/sbin/ldconfig

# some cleanup tasks
icsw_cleanup

# move logging dir
move_log_dir

# migrate client config files
/opt/cluster/sbin/pis/merge_client_configs.py

# check content stores for client
[ -x ${ICSW_PIS}/check_content_stores_client.py ] && ${ICSW_PIS}/check_content_stores_client.py

# purge debian packages
if [ -f /etc/debian_version ] ; then

    for service in host-monitoring package-client ; do
        if [ -f /etc/init.d/${service} ] ; then
            aptitude purge ${service}
        fi
    done
fi

# modify root bashrc
if [ -f /root/.bashrc ] ; then
    grep ${ICSW_BIN} /root/.bashrc >/dev/null || echo "export PATH=\$PATH:${ICSW_BIN}:${ICSW_SBIN}" >> /root/.bashrc
    grep PDSH_RCMD_TYPE /root/.bashrc >/dev/null || echo "export PDSH_RCMD_TYPE=ssh" >> /root/.bashrc
else
    echo "export PATH=\$PATH:${ICSW_BIN}:${ICSW_SBIN}" > /root/.bashrc
    echo "export PDSH_RCMD_TYPE=ssh" >> /root/.bashrc
    chmod 0644 /root/.bashrc
fi

for client in logging-server meta-server loadmodules hoststatus ; do
    ${ICSW_PIS}/modify_service.sh activate ${client}
done

# deactivate most client services (now handled via meta-server)
for client in host-monitoring package-client memcached ; do
    if [ -f /etc/init.d/${client} ] ; then
        ${ICSW_PIS}/modify_service.sh deactivate ${client}
    fi
done

# loadmodules
if [ -f /etc/debian_version ] ; then
    ${USRSBIN}/update-rc.d meta-server start 21 2 3 5 . stop 79 0 1 4 6 .
    ${USRSBIN}/update-rc.d loadmodules start 8 2 3 5 . stop 92 0 1 4 6 .
    for client in logging-server hoststatus ; do
        ${USRSBIN}/update-rc.d ${client} start 25 2 3 5 . stop 75 0 1 4 6 .
    done
fi

restart_software "client"
