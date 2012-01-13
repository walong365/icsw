#!/bin/bash

if [ "$#" -eq 1 ] ; then
    kver=$1
else
    kver=$(uname -r)
fi

echo "Using $kver as Kernel version, creating kernel in /tmp/kernel.tar"

vmlinuz_name="/boot/vmlinuz-$kver"
systemmap_name="/boot/System.map-$kver"
libdir_name="/lib/modules/$kver"

[ -f $vmlinuz_name ] || { echo "Cannot find vmlinuz $vmlinuz_name" ; exit -1 ; }
[ -f $systemmap_name ] || { echo "Cannot find System.map $systemmap_name" ; exit -1 ; }
[ -d $libdir_name ] || { echo "Cannot find /lib/modules/<modules> $libdir_name" ; exit -1 ; }

echo "Compressing $libdir_name"
tar cpsjf /tmp/modules.tar.bz2 $libdir_name
cd /tmp
echo "Adding vmlinuz and System.map"
cp -a $vmlinuz_name vmlinuz
cp -a $systemmap_name System.map

tar cpsv --remove-files -f kernel.tar modules.tar.bz2 vmlinuz System.map

tdir=/tftpboot/kernels/$kver

echo
echo " - Now copy /tmp/kernel.tar to $tdir on the"
echo " - destination server and untar it."
echo " - Then cd to $tdir and untar modules.tar.bz2 ."
echo " - Finally, create the initrd and restart mother:"
echo 
echo "mkdir $tdir"
echo "cp -a /tmp/kernel.tar $tdir"
echo "cd $tdir"
echo "tar xf kernel.tar"
echo "tar xjf modules.tar.bz2"
echo "rm kernel.tar"
echo "populate_ramdisk.py $tdir"
echo "rcmother restart"
echo
