#!/bin/bash

if [[ $# -gt 0 ]]; then
    python-init initat/cluster/manage.py test icinga_migration_tests.$*
else
    python-init initat/cluster/manage.py test icinga_migration_tests
fi

