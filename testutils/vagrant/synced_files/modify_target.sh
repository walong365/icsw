#!/bin/sh -ex

sed -i 's/lang-nevyjel/bahlon/g' /opt/cluster/etc/cstores.d/client_config.xml
sed -i 's/\<logging-server\>/VAGRANT_logging-server/g' /opt/cluster/etc/cstores.d/client_config.xml
sed -i 's/\<meta-server\>/VAGRANT_meta-server/g' /opt/cluster/etc/cstores.d/client_config.xml
sed -i 's/cluster\@init.at/bahlon\@init.at/g' /opt/cluster/etc/cstores.d/client_config.xml
/opt/cluster/sbin/icsw service restart logging-server
