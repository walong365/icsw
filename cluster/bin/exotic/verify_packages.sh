#!/bin/bash
#
# Copyright (C) 2001,2002,2003,2004 Andreas Lang, init.at
#
# Send feedback to: <lang@init.at>
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

if [ $# != 1 ] ; then
    arch=`uname -m`
else
    arch=$1
fi

echo "Using architecture $arch"

for p in $(cat /usr/local/cluster/etc/all_rpms ) ; do
    rpm -q $p > /dev/null && {
	files="$(find . -name "$p-latest.$arch.rpm") $(find . -name "$p-latest.noarch.rpm")"
	for file in $files ; do
	    echo "Checking installed package $p against file $file ..."
	    rpm -qVpl $file --nomtime | sed s/^/\ \ /g | grep -v "\.pyc"
	done
    }
done
