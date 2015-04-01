#!/bin/bash
#
# Copyright (C) 2008 Andreas Lang-Nevyjel
#
# this file is part of package-client
#
# Send feedback to: <lang-nevyjel@init.at>
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

VAR_DIR=/var/lib/cluster/package-client

estate=0
if [ -d ${VAR_DIR} ] ; then
    if ls ${VAR_DIR}/*status >/dev/null 2>&1 ; then
	for stat_file in ${VAR_DIR}/*_status ; do
	    echo -e "\nStatfile $stat_file:"
	    tail -n 5 $stat_file
	done
    else
	echo "no status files in ${VAR_DIR} found"
	estate=-2
    fi
else
    echo "no directory ${VAR_DIR} found"
    estate=-1
fi

exit $estate