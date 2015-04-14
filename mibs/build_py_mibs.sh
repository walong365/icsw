#!/bin/bash

# EXTRA_ARGS=" -l 0 2>/dev/null"
EXTRA_ARGS=" -l 1 "

# IBM Blade center
smidump -s -f smiv2 mmblade-mib ${EXTRA_ARGS} > /tmp/bla
smidump -s -f python /tmp/bla ${EXTRA_ARGS} | libsmi2pysnmp > mmblade-mib.py

# EONstore
smidump -s -f python eonstore-mib ${EXTRA_ARGS} | libsmi2pysnmp > eonstore-mib.py

# powernet
smidump -s -f python powernet385-mib ${EXTRA_ARGS} | libsmi2pysnmp > powernet385-mib.py
