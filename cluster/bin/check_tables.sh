#!/bin/bash

echo "show tables" | mysql_session.sh | grep -v Tables_in | tr "\n" "," | sed s/,$/\;/g | sed s/^/check\ table\ /g| mysql_session.sh | grep -v "OK"

