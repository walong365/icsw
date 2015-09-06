#!/bin/bash
# Copyright (C) 2013-2015 Andreas Lang-Nevyjel, init.at
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

function is_chroot() {
    p1_inode=$(ls --color=no -di /proc/1/root/ | tr -s " " | cut -d " " -f 1)
    root_inode=$(ls --color=no -di / | tr -s " " | cut -d " " -f 1)
    if [ "${p1_inode}" = "${root_inode}" ] ; then
        return 1
    else
        return 0
    fi
}
