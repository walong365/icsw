#!/bin/bash

echo "Available latest-packages :"
wget -q http://www.initat.org/cluster/RPMs/latest.txt -O - | sed s/^/wget\ /g

