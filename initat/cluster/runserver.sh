#!/bin/bash

_debug=1
_localstatic=0
_nostatic=0
_insecure=0

function print_help {
    echo "usage:"
    echo
    echo "$0 [--nostatic] [--localstatic] [-h] [[ EXTRA_OPTIONS ]]"
    echo
    exit -1
}

EXTRA_OPTIONS=""

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
[ "${_localstatic}" == "1" ] && export LOCAL_STATIC=1
[ "${_insecure}" == "1" ] && RSOPTIONS="${RSOPTIONS} --insecure"

echo "settings: DEBUG=${_debug}, LOCAL_STATIC=${_localstatic}, NOSTATIC=${_nostatic}, INSECURE=${_insecure}, RSOPTIONS='${RSOPTIONS}', EXTRA_OPTIONS='${EXTRA_OPTIONS}'"

export NODE_PATH=$(/opt/cluster/bin/npm -g root)
export NODE_PATH=${NODE_PATH}:${NODE_PATH}/npm/node_modules
echo "NODE_PATH=${NODE_PATH}"

if [ "${_nostatic}" == "0" ] ; then
    echo -ne "collecting static files ... "
    ./manage.py collectstatic --noinput -c > /dev/null
    echo "done"
fi

if [ "${_gulp}" == "1" ] ; then
    echo "special gulp-mode, no static handling via django"
else
    all_urls=$(dirname $0)/frontend/templates/all_urls.html
    echo -ne "writing URLS to ${all_urls} ... "
    ./manage.py show_icsw_urls > ${all_urls}
    echo "done"
fi

./manage.py runserver ${RSOPTIONS} ${EXTRA_OPTIONS} 0.0.0.0:8080
