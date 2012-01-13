#!/bin/sh

# A simple load sensor fo SGE.
#
# Reports number of users logged in on current host

# Configurable parameter: RES = number of 'reserved' licenses
RES=0

# Configurable parameter: HST = host for which load is reported
HST=global

# The number of licences will be determined by lmstat using
# the licence file defined by the standard Tripos setup.
# The availbale wildcards will count as available ExtraSearch, 
# Unity and Unity3D licenses.


case `uname` in
    IRIX*)
    export TA_OS=sgi
    ;;

    Linux*)
    export TA_OS=linux
    ;;

    *)
    ;;
esac
. /usr/prog/tripos/setup/ta_root.sh

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
    license=`cat $TA_LICENSE/tables/license_file_location` 
    $TA_LICENSE/bin/$TA_OS/lmutil lmstat -a -c $license |\
	awk -v H=$HST -v R=$RES '
          /^Users of UnityExtraSearch:.*license.*issued.*license.*in use/ {
             TES+=$6;
             UES+=$11;
          }
          /^Users of Unity3D:.*license.*issued.*license.*in use/ {
             TU3+=$6;
             UU3+=$11;
          }
          /^Users of Unity:.*license.*issued.*license.*in use/ {
             TU+=$6;
             UU+=$11;
          }
          /^Users of WildCard:.*license.*issued.*license.*in use/ {
             TWC+=$6;
             UWC+=$11;
          }
         END {
             WA=TWC-UWC-R;
             Unity=(WA+TU-UU); if (Unity < 0) Unity=0;
             Unity3D=(WA+TU3-UU3); if (Unity3D < 0) Unity3D=0;
             UnityExtra=(WA+TES-UES); if (UnityExtra < 0) UnityExtra=0;
             print "begin";
             print H ":unitylic:" Unity;
             print H ":unity3dlic:" Unity3D;
             print H ":unityxtralic:" UnityExtra;
             print "end"
          }
        '
done # we never get here 
exit 0

