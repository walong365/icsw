#!/bin/bash

# SGE Loadsensor
# Armin Widmer, Benjamin Almeida

# global section
# The number of licences will be determined by lmstat using
# the licence file defined by the standard Tripos setup.
# The availbale wildcards will count as available ExtraSearch,
# Unity and Unity3D licenses.

# local section
# check each machine if the paths to software and commonly used
# databases is available, if yes set the runenvironment scnpr true

# settings for the loadsensor
# global sensors should be done on select machines not all
    #if [ "$HOST" = `qconf -sss | awk -F. '{print $1}'` ]; then LOAD_GLOBAL="TRUE"; fi
    # sge master can't run the licence check thus we select a host

if [ "$HOST" = "scamm1" ]; then LOAD_GLOBAL="TRUE"; fi
if [ "$HOST" = "cl0.eu.novartis.net" ]; then LOAD_GLOBAL="TRUE"; fi
# this option will switch on/off the section that collects information on each node
LOAD_LOCAL="FALSE"

# parameters for the global section 
# RES = number of 'reserved' licenses
RES=8

# HST = host for which load is reported
HST=global





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
    # sge convention 
    echo "begin"
    # license monitoring should only run on the active qmaster 
    if [ "$LOAD_GLOBAL" = "TRUE" ]; then
      TA_LICENSE=/usr/prog/tripos/AdminTools9.2
      case `uname` in
        IRIX*)
        TA_OS=sgi
        ;;
        Linux*)
        TA_OS=linux
        ;;

        *)
        ;;
      esac
      license=`cat $TA_LICENSE/tables/license_file_location`:7182@scnpr.eu.novartis.net
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
                /^Users of IMPACT_MAIN:.*license.*issued.*licenses.*in use/ {
                   TIM+=$6;
                   UIM+=$11;
                }
                /^Users of IMPACT_GLIDE:.*license.*issued.*licenses.*in use/ {
                   TIG+=$6;
                   UIG+=$11;
                }
              END {
                  WA=TWC-UWC-R;
                  Unity=(WA+TU-UU); if (Unity < 0) Unity=0;
                  Unity3D=(WA+TU3-UU3); if (Unity3D < 0) Unity3D=0;
                  UnityExtra=(WA+TES-UES); if (UnityExtra < 0) UnityExtra=0;
                  print H ":lic_IMPACT_MAIN:" TIM-UIM;
                  print H ":lic_IMPACT_GLIDE:" TIG-UIG;
                  print H ":lic_Unity:" Unity;
                  print H ":lic_Unity3D:" Unity3D;
                  print H ":lic_UnityExtraSearch:" UnityExtra;
               }
            '
    fi
    if [ "$LOAD_LOCAL" = "TRUE" ]; then
    #now host values for each hosts (eg. run environment)
      re_scnpr=1
      # since we can only do negative checks
      #if (! test -e /usr/prog/. ) then re_scnpr=0; fi
      if (! test -e /db/. ) then re_scnpr=0; fi
      if (! test -e /usr/people/. ) then re_scnpr=0; fi
      if (! test -e /usr/prog/tripos/setup/ta_root.sh ) then re_scnpr=0; fi
      if ( test "SunOS" = `uname` ) then re_scnpr=0; fi
      echo `hostname` | grep -q '^cl[0-9][0-9]*.eu.novartis.net$'
      if [ $? -ne 0 ];then
	  re_scnpr=0
      fi
#     if (! test -e /CHANGEME ) then re_scnpr=0; fi
      echo `hostname`:re_scnpr:$re_scnpr
      echo `hostname`:unity:$re_scnpr
    fi
    echo "end"
done # we never get here 
exit 0

