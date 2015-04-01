#!/bin/bash

# A simple load sensor fo SGE.
#
# run environment check for scnpr
# this should be a link in the sge binary directory 
# so we know if certain prerequisits are fullfiIlled
# 
# check filesystems
#	/usr/prog/. /db/. /usr/people/camm/.
# check application start point
# 	/usr/prog/tripos/setup/ta_root.sh
#
# return true/false


while [ 1 ]; do 
    # wait for input
    read input 
    result=$?
    if [ "$result" != 0 ]; then
	exit 1 
    fi 
    if [ "$input" = "quit" ]; then 
	exit 0 
    fi 
    re_scnpr=1
    echo "begin"
    # since we can only do negative checks
    if (! test -e /usr/prog/. ) then re_scnpr=FALSE; fi
    if (! test -e /db/. ) then re_scnpr=FALSE; fi
    if (! test -e /usr/people/. ) then re_scnpr=FALSE; fi
    if (! test -e /usr/prog/tripos/setup/ta_root.sh ) then re_scnpr=FALSE; fi
    if ( test "SunOS" = `uname` ) then re_scnpr=FALSE; fi
    echo `hostname` | grep -q '^cl[0-9][0-9]*.eu.novartis.net$'
    if [ $? -ne 0 ];then
	re_scnpr=0
    fi
#   if (! test -e /CHANGEME ) then re_scnpr=FALSE; fi
    echo `hostname`:re_scnpr:$re_scnpr
    echo `hostname`:unity:$re_scnpr
    echo "end"
done # we never get here 
exit 0

