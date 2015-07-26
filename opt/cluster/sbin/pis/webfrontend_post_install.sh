#!/bin/bash

# delete modules install via npm
rm -rf /opt/cluster/lib/node_modules/yuglify/node_modules
# delete old modules
rm -rf /opt/python-init/lib/python2.7/site-packages/initat/cluster/rms

MANAGE=/opt/python-init/lib/python/site-packages/initat/cluster/manage.py

# static dir
STATIC_DIR=/srv/www/htdocs/icsw/static
WEBCACHE_DIR=/opt/cluster/share/webcache

[ ! -d ${STATIC_DIR} ] && mkdir -p ${STATIC_DIR}
[ ! -d ${WEBCACHE_DIR} ] && mkdir -p ${WEBCACHE_DIR}

chmod a+rwx ${WEBCACHE_DIR}

if [ -f /etc/sysconfig/cluster/db.cf ] ; then
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

    # restart memcached is now handled via the meta-server

fi
