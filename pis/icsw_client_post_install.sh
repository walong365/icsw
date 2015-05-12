#!/bin/bash

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

[ -d /var/log/cluster/sockets/snmprelay ] && rm -rf /var/log/cluster/sockets/snmprelay
[ -d /usr/local/sbin/modules ] && rm -rf /usr/local/sbin/modules

PY_FILES="host-monitoring limits hm_classes ipc_comtools"
for file in $PY_FILES ; do
    rm -f ${ICSW_SBIN}/$file.pyo
    rm -f ${ICSW_SBIN}/$file.pyc
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
else
    echo "export PATH=\$PATH:${ICSW_BIN}:${ICSW_SBIN}" > /root/.bashrc
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
# generate package-client config if not present
# not working right now, FIXME
# ${ICSW_SBIN}/package-client.py --writeback --exit-after-writeback

[ -x /bin/systemctl ] && /bin/systemctl daemon-reload

# logging-server
${ICSW_SBIN}/icsw restart logging-server
${INIT}/hoststatus restart

if [ ! -f ${ICSW_PIS}/icsw_server_post_install.sh ] ; then
    # start / stop to force restart of all services
    echo -e "\n${GREEN}restarting all ICSW related services (client)${OFF}\n"
    ${ICSW_SBIN}/icsw stop meta-server
    ${ICSW_SBIN}/icsw start meta-server
fi
