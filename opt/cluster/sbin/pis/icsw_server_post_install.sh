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

export PREFIX_INIT=/opt/python-init/lib/python/site-packages

USRSBIN=/usr/sbin
USRBIN=/usr/bin
INIT=/etc/init.d

MANAGE=${PREFIX_INIT}/initat/cluster/manage.py

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

# remove cached urls.py files
rm -f ${PREFIX_INIT}/initat/cluster/urls.py*
rm -rf ${PREFIX_INIT}/initat/core

# delete modules install via npm
rm -rf ${ICSW_BASE}/lib/node_modules/yuglify/node_modules
# delete old modules
rm -rf ${PREFIX_INIT}/initat/cluster/rms

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

# PostInstallTaks
[ -x ${ICSW_PIS}/check_local_settings.py ] && ${ICSW_PIS}/check_local_settings.py

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

if [ -f /etc/sysconfig/cluster/db.cf ] ; then
    # already installed
    if [ "$(/usr/bin/python-init ${PREFIX_INIT}/initat/tools/config_store.py --store icsw.general --key db.auto.update)" = "True" ] ; then
        echo "running auto-update script ${ICSW_BASE}/sbin/icsw setup --migrate"
        ${ICSW_BASE}/sbin/icsw setup --migrate
    else
        echo "to update the current database schema via django please use ${ICSW_BASE}/sbin/setup_cluster.py --migrate"
    fi
    # already configured; run collectstatic
    echo -ne "collecting static ..."
    ${MANAGE} collectstatic --noinput -c > /dev/null
    echo "done"
    echo -ne "building url_list ..."
    ${MANAGE} show_icsw_urls > /opt/python-init/lib/python/site-packages/initat/cluster/frontend/templates/all_urls.html
    echo "done"

    if [ -d /opt/cluster/etc/uwsgi/reload ] ; then
        touch /opt/cluster/etc/uwsgi/reload/webfrontend.touch
    else
        echo "no reload-dir found, please restart uwsgi-init"
    fi

else
    echo "to create a new database use ${ICSW_BASE}/sbin/icsw setup"
fi

# PostInstallScripts
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
