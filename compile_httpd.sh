#!/bin/bash

apache_version=2.0.58

cd httpd-${apache_version}

./configure --prefix=/opt/apache-init --enable-v4-mapped --enable-ssl --enable-static-support --enable-shared-support --enable-so --enable-mods-shared --enable-http

make
