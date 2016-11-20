#!/bin/bash
# Copyright (C) 2013-2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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

if [ "${1}" == "start" ] ; then
    /opt/python-init/bin/daphne initat.cluster.asgi:channel_layer --port 8085 --bind 0.0.0.0 --access-log=/var/log/icsw/daphne_access.log &
    /opt/cluster/sbin/clustermanage.py runworker --only-channels=websocket.* --threads=4 &
else
    kill $(ps auxw | grep daphne | grep 8085 | tr -s " " | cut -d " " -f 2)
    kill $(ps auxw | grep clustermanage.py | grep runworker | tr -s " " | cut -d " " -f 2)
fi
