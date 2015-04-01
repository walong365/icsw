#!/bin/bash

# delete modules install via npm
rm -rf /opt/cluster/lib/node_modules/yuglify/node_modules

# static dir
STATIC_DIR=/srv/www/htdocs/icsw/static
[ ! -d ${STATIC_DIR} ] && mkdir -p ${STATIC_DIR}

if [ -f /etc/sysconfig/cluster/db.cf ] ; then
    # already configured; run collectstatic

    echo -ne "collecting static ..."
    /opt/python-init/lib/python/site-packages/initat/cluster/manage.py collectstatic --noinput -c > /dev/null
    echo "done"

    if [ -d /opt/cluster/etc/uwsgi/reload ] ; then
	touch /opt/cluster/etc/uwsgi/reload/webfrontend.touch
    else
	echo "no reload-dir found, please restart uwsgi-init"
    fi

    # restart memcached to clean compiled coffeescript snippets
    /etc/init.d/memcached restart

    # migrate static_precompiler if needed
    # removed, should be done via cluster-setup
    # /opt/python-init/lib/python/site-packages/initat/cluster/manage.py migrate static_precompiler
fi


