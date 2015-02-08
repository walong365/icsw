#!/bin/bash

_debug=1
_localstatic=0
_nostatic=0
_insecure=0
_doforms=1

function print_help {
    echo "usage:"
    echo
    echo "$0 [--nostatic] [--localstatic] [--noforms] [-h]"
    echo
    exit -1
}

while (( "$#" )) ; do
    case "$1" in
        "--nostatic")
            _nostatic=1
            ;;
        "--localstatic")
            _localstatic=1
            _insecure=1
            _debug=0
            ;;
        "--noforms")
            _doforms=0
            ;;
        "-h")
            print_help
            ;;
        *)
            echo "unknown option $1"
            print_help
            ;;
    esac
    shift
done

RSOPTIONS="--traceback"

[ "${_debug}" = "1" ] && export DEBUG_WEBFRONTEND=1
[ "${_localstatic}" == "1" ] && export LOCAL_STATIC=1
[ "${_insecure}" == "1" ] && RSOPTIONS="${RSOPTIONS} --insecure"

echo "settings: DEBUG=${_debug}, LOCAL_STATIC=${_localstatic}, NOSTATIC=${_nostatic}, INSECURE=${_insecure}, DOFORMS='${_doforms}', RSOPTIONS='${RSOPTIONS}'"
export NODE_PATH=$(/opt/cluster/bin/npm -g root)
export NODE_PATH=${NODE_PATH}:${NODE_PATH}/npm/node_modules
echo "NODE_PATH=${NODE_PATH}"

if [ "${_doforms}" == "1" ] ; then
    echo "compiling all forms ..."
    ./manage.py render_all_forms
fi

if [ "${_nostatic}" == "0" ] ; then
     echo -ne "collecting static files ... "
    ./manage.py collectstatic --noinput -c > /dev/null
    echo "done"
fi

./manage.py runserver ${RSOPTIONS} 0.0.0.0:8080
