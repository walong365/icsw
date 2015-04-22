#!/bin/bash
# Copyright (C) 2001-2008,2012-2015 Andreas Lang-Nevyjel
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
### BEGIN INIT INFO
# Provides:          ics_tools
# Required-Start:    
# Required-Stop:
# Default-Start:     3 5
# Default-Stop:      0 1 2 6
# Short-Description: dummy for ics_tools
### END INIT INFO

check_threads() {
    if [ -n "$1" ] ; then
        ret=$(/opt/cluster/bin/ics_tools.py $1)
    else 
        ret=$(/opt/cluster/bin/ics_tools.py $SERVER_PID)
    fi
    ret_val=$?
    echo -n $ret
    return $ret_val
}

check_threads_ok() {
    if [ -n "$1" ] ; then
        ret=$(/opt/cluster/bin/ics_tools.py -o $1)
    else 
        ret=$(/opt/cluster/bin/ics_tools.py -o $SERVER_PID)
    fi
    ret_val=$?
    echo -n $ret
    return $ret_val
}

# check for redhat
if [ -f /etc/redhat-release ] ; then
    export IS_REDHAT=1
    . /etc/init.d/functions
else
    export IS_REDHAT=0
fi

# check for debian
if [ -f /etc/debian_version ] ; then
    export IS_DEBIAN=1
    . /lib/lsb/init-functions
else
    export IS_DEBIAN=0
fi

# check for suse
if [ -f /etc/SuSE-release ] ; then
    export IS_SUSE=1
else
    export IS_SUSE=0
fi

is_redhat() {
    if [ -f /etc/redhat-release ] ; then
        /bin/true
    else
        /bin/false
    fi
}

is_debian() {
    if [ -f /etc/debian_version ] ; then
        /bin/true
    else
        /bin/false
    fi
}

is_suse() {
    if [ -f /etc/SuSE-release ] ; then
        /bin/true
    else
        /bin/false
    fi
}
