#!/bin/bash
# Copyright (C) 2001-2007,2014-2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
# 
# this file is part of python-modules-base
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
# removes any lines in INIT INFO block, otherwise chkconfig gets extremly confused on redhat systems (sigh)

file=/etc/init.d/$1

if [ -f ${file} ] ; then
    tmpfile=$(mktemp /tmp/.init_XXXXXX)
    cat $file | grep  INIT\ INFO -A 100 | grep INIT\ INFO -B 100 | diff - $file | grep \> | sed s/^\>\ //g > $tmpfile
    cat $tmpfile > $file
    rm -f $tmpfile
fi

exit 0
