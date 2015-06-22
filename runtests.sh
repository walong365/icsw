#!/bin/bash
PATTERN="*.py"

if [ "$1" = "--coverage" ]; then
    COVERAGE=1
    shift
else
    COVERAGE=0
fi

if [ -z "$*" ]; then
    DIRS=$(find . -name tests -type d)
else
    DIRS=$@
fi

#echo "Running collectstatic"
#python-init manage.py collectstatic --noinput -v 0

if [ $COVERAGE -eq 0 ]; then

    echo "Running tests for $DIRS"
    python-init initat/cluster/manage.py test --keepdb --noinput -v 2 --pattern "$PATTERN" $DIRS
    TEST_STATUS=$?

else

    OMIT="initat/cluster/backbone/migrations/*"

    echo "Generating coverage reports for $DIRS"
    /opt/python-init/bin/coverage erase
    /opt/python-init/bin/coverage run  --omit "${OMIT}" initat/cluster/manage.py test --keepdb --noinput -v 2 --pattern "$PATTERN" $DIRS
    /opt/python-init/bin/coverage html --omit "${OMIT}"

fi

#rm -rf static/*
exit ${TEST_STATUS}
