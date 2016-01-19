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

export PREFIX_INIT=/opt/python-init/lib/python2.7/site-packages

# static dir
STATIC_DIR=/srv/www/htdocs/icsw/static
WEBCACHE_DIR=${ICSW_BASE}/share/webcache

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

icsw_cleanup

# remove old socket and zmq dirs
[ -d /var/log/cluster/sockets ] && rm -rf /var/log/cluster/sockets
[ -d /tmp/.icsw_zmq ] && rm -rf /tmp/.icsw_zmq

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
    if [ "$(readlink -f /tftpboot)" != "${ICSW_TFTP}" ] ; then
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

# PostInstallTaks
[ -x ${ICSW_PIS}/check_content_stores.py ] && ${ICSW_PIS}/check_content_stores.py

# ... remove ...
# old config files
rm -f /etc/sysconfig/cluster/.is_corvus
rm -f /etc/sysconfig/cluster/local_settings.py?
# old license files
rm -f /etc/sysconfig/cluster/cluster_license*
# start disable file
rm -f /etc/sysconfig/cluster/.disable_rrdcached_start

# add idg to webserver group
if [ -f /etc/debian_version ] ; then
    usermod -G idg www-data
elif [ -f /etc/redhat-release ] ; then
    usermod -G idg apache
else
    usermod -G idg wwwrun
fi

[ ! -d ${STATIC_DIR} ] && mkdir -p ${STATIC_DIR}
[ ! -d ${WEBCACHE_DIR} ] && mkdir -p ${WEBCACHE_DIR}

chmod a+rwx ${WEBCACHE_DIR}

# restart because we are server (or valid slave)
RESTART_SRV=0
RESTART_CAUSE="unknown"

if is_chroot ; then
    echo "running chrooted, skipping setup and restart"
else
    DB_VALID=0

    if ${ICSW_SBIN}/icsw cstore --store icsw.db.access --mode storeexists ; then
        # already installed
        if [ "$(${ICSW_SBIN}/icsw cstore --store icsw.general --mode getkey --key db.auto.update)" = "True" ] ; then
            echo "running auto-update script ${ICSW_BASE}/sbin/icsw setup --migrate"
            ${ICSW_BASE}/sbin/icsw setup --migrate
            DB_VALID=1
        else
            echo "to update the current database schema via django please use ${ICSW_BASE}/sbin/icsw setup --migrate"
            DB_VALID=0
        fi
    else
        echo "to create a new database use ${ICSW_BASE}/sbin/icsw setup --enable-auto-update"
    fi

    [ -x /bin/systemctl ] && /bin/systemctl daemon-reload

    if [ "${DB_VALID}" = "1" ] ; then
        # PostInstallScripts
        [ -x ${ICSW_PIS}/sge_post_install.sh ] && ${ICSW_PIS}/sge_post_install.sh

        echo "Database is valid, restarting software"
        RESTART_SRV=1
        RESTART_CAUSE="database and software updated"
    else
        echo ""
        if ${ICSW_SBIN}/icsw cstore --store icsw.general --mode storeexists ; then
            if [ "$(${ICSW_SBIN}/icsw cstore --mode getkey --store icsw.general --key mode.is.slave)" = "True" ] ; then
                echo "Node is Slave-node, init webfrontend and restarting software"
                ${ICSW_SBIN}/icsw setup --init-webfrontend
                RESTART_SRV=1
                RESTART_CAUSE="software updated"
            else
                echo "Database is not valid and system is not slave, skipping restart"
            fi
        else
            echo "icsw.general store not present and database not valid, skipping restart"
        fi
    fi
fi

if [ "${RESTART_SRV}" = "1" ] ; then
    restart_software "server"
fi
