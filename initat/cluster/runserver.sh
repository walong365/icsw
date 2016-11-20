#!/bin/bash

base=$(basename $0)

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

export ICSW_DEBUG_SOFTWARE=1

[ ! -z "${EXTRA_OPTIONS}" ] && echo "settings: EXTRA_OPTIONS='${EXTRA_OPTIONS}'"

if [ "${base}" = "rundaphne.sh" ] ; then
    # use local path for asgi layer
    /opt/python-init/bin/daphne asgi:channel_layer --bind 0.0.0.0 --port 8084
elif [ "${base}" = "runworker.sh" ] ; then
    ./manage.py runworker
else
    ./manage.py runserver --noworker --noasgi --traceback ${EXTRA_OPTIONS} 0.0.0.0:8081
fi
