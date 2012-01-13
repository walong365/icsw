#!/bin/bash

mybasedir=`dirname $0`

[ ! -d /opt/pbspro ] && { echo "No pbspro found ! " ; exit -1 ; }

imbasedir=/tftpboot/images/
imconfig=${imbasedir}config
pimnames=`echo "SELECT name FROM image " | mysql -u root -p'init4u' -D cdbase | sed -e "1d" | tr "\n" " "`

if [ $# -ne 1 ] ; then
  echo "Need image name !" ;
  echo "Possible values are: $pimnames" ;
  exit -1 ;
else
  stuff=`echo "SELECT source FROM image WHERE name='"$1"'" | mysql -u root -p'init4u' -D cdbase | sed -e "1~4"d `
  if [ "${stuff:-0}" = "0" ] ; then
    echo "Wrong image name $1, possible values are $pimnames." ;
    exit -1 ;
  fi
  imname=$1;
  imsource=/usr/local/share/images/`echo $stuff | cut -d " " -f 1`
fi

echo "Image directory is $imsource"

echo "Installing startup scripts" $mybasedir
scrname="pbspro_mom"
cp -a ${mybasedir}/../init_scripts/${scrname} ${imsource}/etc/rc.d/
chmod +x ${imsource}/etc/rc.d/${scrname}
chroot ${imsource} /sbin/insserv /etc/rc.d/${scrname}
