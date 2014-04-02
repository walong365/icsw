#!/bin/bash
# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2008,2012-2014 Andreas Lang-Nevyjel, init.at
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

echo "deprecated, please use the version in cluster-backbone-tools"
exit -1

if [ "$#" -lt "2" ] ; then
    echo "Need at least two parameters (kernel_name and local kernel_dir, optional the xen-version)"
    echo "Local kernels found:"
    for cur_kern in $(ls -1 ${IMAGE_ROOT}/lib/modules/) ; do
        if [ -d ${IMAGE_ROOT}/lib/modules/${cur_kern}/kernel ] ; then
            echo "$cur_kern (at ${IMAGE_ROOT}/lib/modules/${cur_kern})"
        fi
    done
    echo ""
    echo "Xen versions found:"
    echo "$(find ${IMAGE_ROOT}/boot -type f -name "xen*gz" -printf '%f\n')"
    echo ""
    echo "set IMAGE_ROOT to change root directory from ''"
    exit -1
fi

k_name=$1
loc_dir=$2
xen_version=${3:-0}

lib_dir=${IMAGE_ROOT}/lib/modules/${k_name}
firm_dir=${IMAGE_ROOT}/lib/firmware/
firm_dir_local=${IMAGE_ROOT}/lib/firmware/${k_name}
targ_dir=$loc_dir/${k_name}
config_file=config-${k_name}

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
    xen_file=${IMAGE_ROOT}/boot/xen-${xen_version}
    if [ ! -f $xen_file ] ; then
    echo "Xen file $xen_file not found"
    exit -1
    fi
else
    xen_file="not set"
fi

if [ ! -f "${IMAGE_ROOT}/boot/System.map-${k_name}" ] ; then
    echo "No System-map file ${IMAGE_ROOT}/boot/System.map-${k_name} found"
    exit -1
fi
if [ ! -f "${IMAGE_ROOT}/boot/vmlinuz-${k_name}" ] ; then
    echo "No vmlinuz file ${IMAGE_ROOT}/boot/vmlinuz-${k_name} found"
    exit -1
fi

echo "Copying local kernel ${k_name} to kernel_dir $loc_dir (target_dir is ${targ_dir}, xen_file is $xen_file)"

[ -L $lib_dir/build ] && rm $lib_dir/build
[ -L $lib_dir/source ] && rm $lib_dir/source

mkdir ${targ_dir}

echo "Copying bzImage and System.map"
cp -a ${IMAGE_ROOT}/boot/System.map-${k_name} ${targ_dir}/System.map
cp -a ${IMAGE_ROOT}/boot/vmlinuz-${k_name} ${targ_dir}/bzImage
if [ ! -f "${IMAGE_ROOT}/boot/${config_file}" ] ; then
    echo "No config file ${IMAGE_ROOT}/boot/${config_file} found, ignoring"
else
    echo "Copying config $config_file"
    cp -a ${IMAGE_ROOT}/boot/${config_file} ${targ_dir}/.config
fi

if [ "$xen_version" != "0" ] ; then
    echo "Copying xen"
    cp -a $xen_file ${targ_dir}/xen.gz
fi

echo "Copying modules (${lib_dir} -> ${targ_dir}/lib/modules)"
mkdir -p ${targ_dir}/lib/modules
cp -a $lib_dir ${targ_dir}/lib/modules

echo "Copying firmware (${firm_dir} -> ${targ_dir}/lib/firmware/${k_name})"
mkdir -p ${targ_dir}/lib/firmware
cp -a ${firm_dir} ${targ_dir}/lib/firmware/${k_name}
echo "Copying local firmware (${firm_dir_local} -> ${targ_dir}/lib/firmware/${k_name})"
cp -a ${firm_dir_local}/* ${targ_dir}/lib/firmware/${k_name}

echo "Generating dummy initrd_lo.gz"
touch ${targ_dir}/initrd_lo.gz
