#!/bin/bash

gid_base=99
uid_base=90
while [ "$#" -gt 0 ] ; do
    case "$1" in 
	-h)
	    echo "Usage: $0 [ -u uid_base ($uid_base) ] [ -g gid_base ($gid_base) ]"
	    exit
	    ;;
	-u)
	    uid_base=$2;
	    shift;
	    ;;
	-g)
	    gid_base=$2;
	    shift;
	    ;;
	*)
	    echo "Unknown option: $1"
	    exit
	    ;;
    esac
    shift ;
done

echo "Using uid_base $uid_base and gid_base $gid_base"

cgl="idg:$gid_base sge:$(($gid_base + 1 ))"
cul="idlog:0:idg:/var/lib/logging-server:/bin/false: idccs:1:idg:/var/lib/cluster-config-server:/bin/false: idmother:2:idg:/var/lib/mother:/bin/false: idpacks:3:idg:/var/lib/package-server:/bin/false: idrrd:4:idg:/var/lib/rrd-server:/bin/false: idnagios:5:idg:/var/lib/nagios-config-server:/bin/false: sge:6:sge:/var/lib/sge-server:/bin/false:idg"

for cg in $cgl ; do
    gname=`echo $cg | cut -d ":" -f 1`
    gid=`echo $cg | cut -d ":" -f 2`
    cat /etc/group | grep "${gname}:" >/dev/null || {
	while true ; do
	    cat /etc/group | cut -d ":" -f 3 | sort -n | sed s/^/Q/g | sed s/$/Q/g | grep "Q${gid}Q" > /dev/null && {
		echo "gid $gid already used, increasing..."
		gid=$(( $gid + 1 ))
	    } || {
		echo "Issuing groupadd -g $gid $gname"
		groupadd -g $gid $gname
		break
	    }
	done
    } || {
	echo "Group $gname already present"
    }
done

for cu in $cul ; do
    uname=`echo $cu | cut -d ":" -f 1`
    uid=$(($uid_base + `echo $cu | cut -d ":" -f 2`))
    ug=`echo $cu | cut -d ":" -f 3`
    uh=`echo $cu | cut -d ":" -f 4`
    us=`echo $cu | cut -d ":" -f 5`
    addg=`echo $cu | cut -d ":" -f 6`
    [ "$addg" != "" ] && addg=" -G $addg "
    cat /etc/passwd | grep "${uname}:" >/dev/null || {
	while true ; do
	    cat /etc/passwd | cut -d ":" -f 3 | sort -n | sed s/^/Q/g | sed s/$/Q/g | grep "Q${uid}Q" > /dev/null && {
		echo "uid $uid already used, increasing..."
		uid=$(( $uid + 1 ))
	    } || {
		echo "Issuing useradd -M -u $uid $addg -g $ug -d $uh -s $us $uname"
		useradd -M -u $uid -g $ug -d $uh -s $us $uname
		break
	    }
	done
    } || {
	echo "User $uname already present"
    }
done

