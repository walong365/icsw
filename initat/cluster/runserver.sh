#!/bin/bash
# Copyright (C) 2013-2017 Andreas Lang-Nevyjel, init.at
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

base=$(basename $0)

trap 'killall' INT TERM

function killall() {
    trap '' INT TERM
    echo "*** Shutting down ***"
    kill -TERM 0
    echo "*** done ***"
    exit 0
}

function print_help {
    echo "usage:"
    echo
    echo "$0 [-h] [[ EXTRA_OPTIONS ]]"
    echo
    exit -1
}

EXTRA_OPTIONS=""

while (( "$#" )) ; do
    case "$1" in
        "-h")
            print_help
            ;;
        *)
            EXTRA_OPTIONS="${EXTRA_OPTIONS} $1"
            ;;
    esac
    shift
done

# enable debugging

export ICSW_DEBUG_MODE=1

# disable __pycache__

export PYTHONDONTWRITEBYTECODE=1

[ ! -z "${EXTRA_OPTIONS}" ] && echo "settings: EXTRA_OPTIONS='${EXTRA_OPTIONS}'"

echo "Starting daphne, worker and server ..."

/opt/cluster/bin/daphne asgi:channel_layer -v 1 --bind 0.0.0.0 --port 8084 &
./manage.py runworker_safe -v 2 --only-channels=websocket.* &
./manage.py runserver --noworker --noasgi --traceback ${EXTRA_OPTIONS} 0.0.0.0:8081 &

# wait forever

cat
