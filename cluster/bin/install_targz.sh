#!/bin/bash

mybasedir=`dirname $0`


[ ! -d /var/spool/pbs ] && { echo "No pbs found ! " ; exit -1 ; }

imbasedir=/tftpboot/images/
tgzdir=/usr/local/share/images/tgzs
imconfig=${imbasedir}config
pimnames=`cat $imconfig | grep -v "#" | tr -s " " | cut -d " " -f 1 | tr "\n" " "`
tgznames=""
for i in `ls $tgzdir/*gz` ; do
  tgznames="$tgznames `basename $i`"
done

if [ $# -ne 2 ] ; then
  echo "Need image and tar.gz-name name !" ;
  echo "Possible values for image: $pimnames" ;
  echo "Possible values for tgz: $tgznames" ;
  exit -1 ;
else
  ric=`cat $imconfig | cut -d " " -f 1 | grep "^"$1"$"` ;
  if [ "${ric:-0}" == "0" ] ; then
    echo "Wrong image name $1, possible values are $pimnames." ;
    exit -1 ;
  fi
  ric=`cat $imconfig | grep "^"$1` ;
  imname=`echo $ric | tr -s " " | cut -d " " -f 1`
  imsource=`echo $ric | tr -s " " | cut -d " " -f 2`
  imtype=`echo $ric | tr -s " " | cut -d " " -f 3`
  tgz=$2
  ls $tgzdir/$tgz >/dev/null 2>&1 || { echo "Wrong tar.gz-name !" ; exit -1 ; }
fi

echo "Image directory is $imsource"
echo "Installing tar-gz named $tgzdir/$tgz... "
cd $imsource ; tar -xzs -f $tgzdir/$tgz
