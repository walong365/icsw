#!/bin/bash

echo $@

echo $PATH
set
strace /opt/sge53/3rd_party/proepilogue.py $@ 
exit 0


