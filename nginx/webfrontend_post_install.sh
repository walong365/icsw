#!/bin/bash

if [ ! -f /opt/cluster/bin/yuglify ] ; then
    echo "installing yuglify"
    /opt/cluster/bin/npm -g install yuglify
fi

/usr/bin/sed -i sX/usr/bin/env\ nodeX/opt/cluster/bin/nodeXg /opt/cluster/lib/node_modules/yuglify/bin/yuglify

/opt/python-init/lib/python/site-packages/initat/cluster/manage.py collectstatic --noinput

if [ -d /opt/cluster/etc/uwsgi/reload ] ; then
    touch /opt/cluster/etc/uwsgi/reload/webfrontend.touch
else
    echo "no reload-dir found, please restart uwsgi-init"
fi

# migrate static_precompiler if needed
/opt/python-init/lib/python/site-packages/initat/cluster/manage.py migrate static_precompiler

