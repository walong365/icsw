#!/bin/bash
PATTERN="*.py"

if [ -z "$*" ]; then
    DIRS=$(find . -name tests -type d)
else
    DIRS=$@
fi


#echo "Running collectstatic"
#python-init manage.py collectstatic --noinput -v 0

echo "Running tests for $DIRS"
python-init initat/cluster/manage.py test --keepdb --noinput -v 2 --pattern "$PATTERN" $DIRS

TEST_STATUS=$?
#rm -rf static/*
exit ${TEST_STATUS}
