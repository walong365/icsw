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

SERVER_SERVICES="mother rrd-grapher rms-server cluster-config-server collectd discovery-server md-config-server logcheck-server package-server init-license-server cluster-server snmp-relay host-relay"

/sbin/ldconfig

# delete old config-files
for SRV in cluster-server collectd collectd-init mother ; do
    rm -f /etc/sysconfig/${SRV}
done

# purge debian packages
if [ -f /etc/debian_version ] ; then
    for service in ${SERVER_SERVICES} ; do
        if [ -f /etc/init.d/${service} ] ; then
            aptitude purge ${service}
        fi
    done
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

# deactivate all server services (now handled via meta-server)
for server in ${SERVER_SERVICES} ; do
    if [ -f /etc/init.d/${server} ] ; then
        ${ICSW_PIS}/modify_service.sh deactivate ${server}
    fi
done

# PostInstallScripts
[ -x ${ICSW_PIS}/cluster_post_install.sh ] && ${ICSW_PIS}/cluster_post_install.sh
[ -x ${ICSW_PIS}/webfrontend_post_install.sh ] && ${ICSW_PIS}/webfrontend_post_install.sh
[ -x ${ICSW_PIS}/sge_post_install.sh ] && ${ICSW_PIS}/sge_post_install.sh

[ -x /bin/systemctl ] && /bin/systemctl daemon-reload

# start / stop to force restart of all services
if [ ! -d /var/lib/meta-server/.srvstate ] ; then
    NUM_RS=2
else
    NUM_RS=1
fi

for idx in $(seq ${NUM_RS} ) ; do
    echo -e "\n${GREEN}(${idx}) restarting all ICSW related services (server)${OFF}\n"
    ${ICSW_SBIN}/icsw service stop meta-server
    ${ICSW_SBIN}/icsw service start meta-server
done
