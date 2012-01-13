#!/bin/bash

mybasedir=`dirname $0`

[ ! -d /var/spool/pbs ] && { echo "No pbs found ! " ; exit -1 ; }

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
echo "Removing old pbs-directory..."

rm -rf ${imsource}/var/spool/pbs

echo "Installing new pbs-directory..."
mkdir ${imsource}/var/spool/pbs
for i in aux checkpoint mom_logs mom_priv pbs_environment spool undelivered ; do
  cp -a /var/spool/pbs/${i} ${imsource}/var/spool/pbs/${i}
done
rm -rf ${imsource}/opt/openpbs
cp -a /opt/openpbs ${imsource}/opt/

echo "Installing startup scripts" $mybasedir
scrname="openpbs_mom"
cp -a ${mybasedir}/../init_scripts/${scrname} ${imsource}/etc/rc.d/
chmod +x ${imsource}/etc/rc.d/${scrname}
chroot ${imsource} /sbin/insserv /etc/rc.d/${srcname}
