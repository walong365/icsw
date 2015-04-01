#!/bin/bash
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of rms-tools
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

fname=/etc/sysconfig/logging-server.d/tail

# set tail-log of logging-server
# filter old tail-file

if [ -f /etc/sge_cell -a -f /etc/sge_root ] ; then
    if [ -f ${fname} ] ; then
	echo "Remove old sge-lines..."
	ttail=`mktemp /tmp/.tail_XXXXXX`
	cat ${fname} | grep -v "^sgeserver:" | grep -v "^sges:" > $ttail
	mv $ttail ${fname}
    fi
    echo "sgeserver:$(cat /etc/sge_root | tr -d " ")/$(cat /etc/sge_cell | tr -d " ")/spool/qmaster/messages:10:localhost:8009:udp" >>${fname} && {
	echo "Successfully modified ${fname} , restarting logging-server ... "
	rclogging-server restart
	echo "actual content of $fname: $(cat $fname)"
    } || {
	echo "Something went wrong..."
    }
else
    echo "No /etc/sge_cell or /etc/sge_root file found."
fi

