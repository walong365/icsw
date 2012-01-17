#!/bin/bash
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007 Andreas Lang-Nevyjel
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

start_id=$1

while true ; do
    grep ":$start_id:" /etc/passwd > /dev/null || break
    start_id=$(($start_id + 1))
done

echo $start_id
