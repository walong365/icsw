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

/sbin/ldconfig

# cluster-backbone-tools
if [ -f /root/.bashrc ] ; then
    grep ${ICSW_BASE} /root/.bashrc >/dev/null || echo "export PATH=\$PATH:${ICSW_BIN}" >> /root/.bashrc
else
    echo "export PATH=\$PATH:${ICSW_BIN}" > /root/.bashrc
    chmod 0644 /root/.bashrc
fi

if [ -L /tftpboot ] ; then
    # /tftpboot is a link
    if [ "$(readlink /tftpboot)" != "${ICSW_TFTP}" ] ; then
        echo "/tftpboot is a link but points to $(readlink /tftpboot) instead of ${ICSW_TFTP}"
    fi
else
    if [ -d /tftpboot ] ; then
        echo "/tftpboot is a directory ... ?"
    else
        if [ -d ${ICSW_TFTP} -a ! -L /tftpboot ] ; then
            echo "Generating link from /tftpboot to ${ICSW_TFTP}"
            ln -s ${ICSW_TFTP} /
        fi
    fi
fi

# deactivate all services (now handled via meta-server)
for server in ${SERVER_SERVICES} ; do
    ${ICSW_PIS}/modify_service.sh deactivate ${server}
done

# PostInstallScripts
[ -x ${ICSW_PIS}/sge_post_install.sh ] && ${ICSW_PIS}/sge_post_install.sh
[ -x ${ICSW_PIS}/webfrontend_post_install.sh ] && ${ICSW_PIS}/webfrontend_post_install.sh
[ -x ${ICSW_PIS}/cluster_post_install.sh ] && ${ICSW_PIS}/cluster_post_install.sh

[ -x /bin/systemctl ] && /bin/systemctl daemon-reload

# start / stop to force restart of all services
${ICSW_SBIN}/icsw stop meta-server
${ICSW_SBIN}/icsw start meta-server

