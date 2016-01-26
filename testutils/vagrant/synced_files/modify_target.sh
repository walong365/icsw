#!/bin/sh -ex

xml ed -u "//key[@name='log.mail.from.name']" -v 'VAGRANT_logging-server' /opt/cluster/etc/cstores.d/client_config.xm
xml ed -u "//key[@name='mail.target.address']" -v 'bahlon@init.at' /opt/cluster/etc/cstores.d/client_config.xm
xml ed -u "//key[@name='meta.mail.from.name']" -v 'VAGRANT_meta-server' /opt/cluster/etc/cstores.d/client_config.xm

/opt/cluster/sbin/icsw service restart
