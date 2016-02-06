#!/bin/bash

_debug=1

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

RSOPTIONS="--traceback"

[ "${_debug}" = "1" ] && export DEBUG_WEBFRONTEND=1

echo "settings: DEBUG=${_debug}, RSOPTIONS='${RSOPTIONS}', EXTRA_OPTIONS='${EXTRA_OPTIONS}'"

./manage.py runserver ${RSOPTIONS} ${EXTRA_OPTIONS} 0.0.0.0:8081
