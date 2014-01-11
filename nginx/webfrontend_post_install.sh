#!/bin/bash

if [ ! -f /opt/cluster/bin/yuglify ] ; then
    echo "installing yuglify"
    /opt/cluster/bin/npm -g install yuglify
fi

sed -i sX/usr/bin/env\ nodeX/opt/cluster/bin/nodeXg /opt/cluster/lib/node_modules/yuglify/bin/yuglify

# check for product version

if [ -f /etc/init.d/mother ] ; then
    # seems to be a cluster
    touch /etc/sysconfig/cluster/.is_corvus
fi

/opt/python-init/lib/python/site-packages/initat/cluster/manage.py collectstatic --noinput

if [ -d /opt/cluster/etc/uwsgi/reload ] ; then
    touch /opt/cluster/etc/uwsgi/reload/webfrontend.touch
else
    echo "no reload-dir found, please restart uwsgi-init"
fi

# migrate static_precompiler if needed
/opt/python-init/lib/python/site-packages/initat/cluster/manage.py migrate static_precompiler

