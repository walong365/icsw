#!/bin/bash -ex

XML_PATH=/opt/cluster/bin
CONF=/opt/cluster/etc/cstores.d/client_config.xml
TMP=/opt/cluster/etc/cstores.d/client_config_tmp.xml

$XML_PATH/xml ed \
 -u "//key[@name='log.mail.from.name']" -v 'VAGRANT_logging-server' -u "//key[@name='mail.target.address']" -v 'bahlon@init.at' -u "//key[@name='meta.mail.from.name']" -v 'VAGRANT_meta-server' $CONF > $TMP

echo "copy $TMP to $CONF and remove $TMP"

cp -v $TMP $CONF
rm $TMP

exit 0

#/opt/cluster/sbin/icsw service restart
