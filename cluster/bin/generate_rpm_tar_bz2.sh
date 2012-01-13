#!/bin/bash

tdir=/usr/local/share/init_build/

TARCH=$(/usr/local/sbin/collclient.py sysinfo | tr " " "\n" | sed s/i686/i586/g | tail -1)
TSYS=$(echo $(/usr/local/sbin/collclient.py sysinfo | tr " " "\n" | grep Distribution -A 4 | tail -3 | grep -v version) | tr " " "_")

rpmdir=${tdir}/RPMs/${TSYS}

cd $rpmdir

rm -f packages_${TARCH}.tar.bz2

tar cpsjvf packages_${TARCH}.tar.bz2 $(cat .latest_versions_${TARCH})
