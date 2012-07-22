#!/bin/bash
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2012 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
# 
# This file is part of mother
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

if [ "$#" -lt "2" ] ; then
    echo "Need at least two parameters (kernel_name and local kernel_dir, optional the xen-version)"
    echo "Local kernels found:"
    echo "$(ls -1 /lib/modules/)"
    echo ""
    echo "Xen versions found:"
    echo "$(find /boot -type f -name "xen*gz" -printf '%f\n')"
    exit -1
fi

k_name=$1
loc_dir=$2
xen_version=${3:-0}

lib_dir=/lib/modules/${k_name}
firm_dir=/lib/firmware/${k_name}
targ_dir=$loc_dir/${k_name}

if [ ! -d $lib_dir ] ; then
    echo "Kernelmoduledir $lib_dir not found"
    exit -1
fi

if [ ! -d $loc_dir ] ; then
    echo "Local dir $loc_dir not found"
    exit -1
fi

if [ -d ${targ_dir} ] ; then
    echo "Target directory ${targ_dir} already exists"
    exit -1
fi

if [ "${xen_version}" != "0" ] ; then
    xen_file=/boot/xen-${xen_version}
    if [ ! -f $xen_file ] ; then
	echo "Xen file $xen_file not found"
	exit -1
    fi
else
    xen_file="not set"
fi

if [ ! -f "/boot/System.map-${k_name}" ] ; then
    echo "No System-map file /boot/System.map-${k_name} found"
    exit -1
fi
if [ ! -f "/boot/vmlinuz-${k_name}" ] ; then
    echo "No vmlinuz file /boot/vmlinuz-${k_name} found"
    exit -1
fi

echo "Copying local kernel ${k_name} to kernel_dir $loc_dir (target_dir is ${targ_dir}, xen_file is $xen_file)"

[ -L $lib_dir/build ] && rm $lib_dir/build
[ -L $lib_dir/source ] && rm $lib_dir/source

mkdir ${targ_dir}

config_file=config-${k_name}

echo "Copying bzImage and System.map"
cp -a /boot/System.map-${k_name} ${targ_dir}/System.map
cp -a /boot/vmlinuz-${k_name} ${targ_dir}/bzImage

if [ "$xen_version" != "0" ] ; then
    echo "Copying xen"
    cp -a $xen_file ${targ_dir}/xen.gz
fi

if [ ! -f /boot/$config_file ] ; then
    echo "No config file $config_file found"
else
    echo "Copying config $config_file"
    cp -a /boot/$config_file ${targ_dir}/.config
fi

echo "Copying modules (${lib_dir} -> ${targ_dir}/lib/modules)"
mkdir -p ${targ_dir}/lib/modules
cp -a $lib_dir ${targ_dir}/lib/modules

echo "Copying firmware (${firm_dir} -> ${targ_dir}/lib/firmware/${k_name})"
mkdir -p ${targ_dir}/lib/firmware
cp -a ${firm_dir} ${targ_dir}/lib/firmware/${k_name}

echo "Compressing modules"
pushd . > /dev/null
cd ${targ_dir}
tar cpsjf modules.tar.bz2 lib
popd > /dev/null

echo "Generating dummy initrd_lo.gz"
touch ${targ_dir}/initrd_lo.gz
