#!/bin/bash

base_dir=/tftpboot/kernels
for kdir in ${base_dir}/* ; do
    if [ -d $kdir ] ; then
	if grep "CPU does not support long mode" $kdir/bzImage > /dev/null ; then
	    echo skipping $kdir due to incompatible arch
	    continue
        fi
	if [ -d $kdir/lib/modules ] ; then
	    kver=`basename $kdir/lib/modules/*`
	    echo "Kernel $kver in directory $kdir..."
	    /usr/local/cluster/bin/populate_ramdisk.sh $kdir $kver
	fi
    fi
done

