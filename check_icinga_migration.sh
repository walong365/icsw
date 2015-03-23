#!/bin/bash

pep8 --config .pep8rc initat/md_config_server/icinga_migration/*.py
pep8 --config .pep8rc icinga_migration_tests.py

