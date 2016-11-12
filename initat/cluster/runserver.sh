#!/bin/bash

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

export DEBUG_ICSW_SOFTWARE=1

echo "settings: EXTRA_OPTIONS='${EXTRA_OPTIONS}'"

./manage.py runserver --traceback ${EXTRA_OPTIONS} 0.0.0.0:8081
