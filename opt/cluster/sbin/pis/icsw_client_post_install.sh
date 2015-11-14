#!/bin/bash
# Copyright (C) 2013-2015 Andreas Lang-Nevyjel, init.at
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

ICSW_BASE=/opt/cluster
ICSW_BIN=${ICSW_BASE}/bin
ICSW_SBIN=${ICSW_BASE}/sbin
ICSW_SGE=${ICSW_BASE}/sge
ICSW_PIS=${ICSW_SBIN}/pis
ICSW_ETC=${ICSW_BASE}/etc
ICSW_SHARE=${ICSW_BASE}/share
ICSW_SYSCONF=${SYSCONF}/cluster
ICSW_TFTP=${ICSW_BASE}/system/tftpboot
ICSW_MOTHER=${ICSW_SHARE}/mother

USRSBIN=/usr/sbin
USRBIN=/usr/bin
INIT=/etc/init.d

BOLD="\033[1m"
RED="\033[31m"
GREEN="\033[32m"
YELLOW="\033[33m"
OFF="\033[m"

/sbin/ldconfig

# some cleanup tasks

rm -rf /usr/local/sbin/check_scripts.py*
rm -rf ${ICSW_SBIN}/modules/*.pyo
rm -rf /opt/python-init/lib/python2.7/site-packages/initat/tools/logging_tools
rm -f /opt/python-init/lib/python2.7/site-packages/initat/icsw/setup/*.py{c,o}
rm -f /opt/python-init/lib/python2.7/site-packages/initat/tools/logging_tools.py{c,o}

[ -d /var/log/cluster/sockets ] && rm -rf /var/log/cluster/sockets
[ -d /tmp/.icsw_zmq ] && rm -rf /tmp/.icsw_zmq
[ -d /usr/local/sbin/modules ] && rm -rf /usr/local/sbin/modules

# migrate client config files
/opt/cluster/sbin/pis/merge_client_configs.py

PY_FILES="host-monitoring limits hm_classes ipc_comtools"
for file in $PY_FILES ; do
    rm -f ${ICSW_SBIN}/$file.py{c,o}
done

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
for client in host-monitoring package-client ; do
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

if is_chroot ; then
    echo "running chrooted, skipping restart"
else
    [ -x /bin/systemctl ] && /bin/systemctl daemon-reload

    # logging-server
    ${ICSW_SBIN}/icsw service restart logging-server
    ${INIT}/hoststatus restart

    if [ ! -f ${ICSW_PIS}/icsw_server_post_install.sh ] ; then
        # start / stop to force restart of all services
        if [ ! -d /var/lib/meta-server/.srvstate ] ; then
            NUM_RS=2
        else
            NUM_RS=1
        fi

        for idx in $(seq ${NUM_RS} ) ; do
            echo -e "\n${GREEN}(${idx}) restarting all ICSW related services (client)${OFF}\n"
            ${ICSW_SBIN}/icsw service stop meta-server
            ${ICSW_SBIN}/icsw service start meta-server
        done
    fi
fi
