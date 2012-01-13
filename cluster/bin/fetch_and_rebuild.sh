#!/bin/bash
#
# Copyright (C) 2001,2002,2003,2004,2005,2006 Andreas Lang, init.at
#
# Send feedback to: <lang@init.at>
#
# This file is part of cluster-backbone
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

function print_usage () {
    echo "Usage:"
    echo ""
    echo "  $0 [--nofetch] [-h]"
    echo "  [--nofetch]  dont fetch from www.initat.org"
    echo "  [--transfer] force transfer to www.initat.org"
}

args=$(getopt -l nofetch -l transfer h $*) || { print_usage ; exit -1 ; }

set -- $args

fetch=1;
transfer=0;

for i ; do
    case "$i" in
	--nofetch) shift ; fetch=0 ;;
	--transfer) shift ; transfer=1 ;;
	-h) shift ; print_usage ; exit -1 ;;
	--) shift ; break ;;
    esac
done

tdir=/usr/local/share/init_build/
mkdir -p ${tdir}/RPMs/general

if [ "$fetch" = "1" ] ; then
    wget -nH -nv --cut-dirs=2 -m -A latest.src.rpm -L --no-parent -P ${tdir}/SRPMs http://www.initat.org/cluster/SRPMs/
    wget -nH -nv --cut-dirs=3 -m -A latest.noarch.rpm -A latest.i586.rpm -A latest.x86_64.rpm -L --no-parent -P ${tdir}/RPMs/general http://www.initat.org/cluster/RPMs/general/
fi

# old .rebuildrc-code
if [ 1 = 0 ] ; then
    [ ! -f /root/.rebuildrc ] && { echo "no rc-file, exiting ..." ; exit -1 ; }
    . /root/.rebuildrc
else
    TARCH=$(/usr/local/sbin/collclient.py --no-headers sysinfo | tr " " "\n" | sed s/i686/i586/g | tail -1)
    TSYS=$(echo $(/usr/local/sbin/collclient.py --no-headers sysinfo | tr " " "\n" | grep Distribution -A 4 | tail -3 | grep -v version) | tr " " "_")
fi

mkdir -p ${tdir}/RPMs/${TSYS}

cd ${tdir}/RPMs/general

echo "Target architecture is $TARCH, target sys is $TSYS"

[ "${SDIR:-0}" = "0" ] && SDIR=packages/RPMS/$TARCH

rm -f ${tdir}/RPMs/${TSYS}/.latest_versions_${TARCH}

for r in ../../SRPMs/*-latest.src.rpm ; do
    name=`rpm -qp $r --queryformat %{NAME}`
    vers=`rpm -qp $r --queryformat %{VERSION}-%{RELEASE}`
    arch=`rpm -qp $r --queryformat %{ARCH}`
    ls ${name}-latest.*.rpm > /dev/null 2>&1 && {
        dest="."
        register=0;
    } || {
        dest="../${TSYS}/"
	register=1;
    }
    printf "Processing %-40s (Version %10s, arch %-10s, dest %-10s)\n" $name $vers $arch $dest
    df=${dest}/${name}-latest.${TARCH}.rpm
    #echo $df $r
    if [ "$arch" == "noarch" ] ; then
        echo "    $name is not bound to a specific architecture..."
        rebuild=0;
    elif [ ! -f  $df ] ; then
	echo " *** Rebuilding $name ($df not found) ..."
	rebuild=1;
    elif [ $df -ot $r ] ; then
        echo " *** Rebuilding $name ($df is older than $r) ..."
        rebuild=1
    else
        echo "    $name ($df, src $r) is up-to-date, skipping rebuild..."
        rebuild=0;
    fi
    if [ "$arch" != "noarch" ] ; then
	filename=${name}-${vers}.${TARCH}.rpm
	if [ "$rebuild" = "1" ] ; then
	    rpmbuild --rebuild --target $TARCH $r || { echo "ERROR" ;
		[ "${IGNORE_ERRORS:-0}" = "0" ] && exit -1 || continue ;
	    }
	    cp -a /usr/src/${SDIR}/${filename} $dest
	fi
	if [ "$rebuild" = "1" -o "$transfer" = "1" ] ; then
	    pushd . > /dev/null
	    cd $dest
	    dst_filename="/usr/local/share/software/linux/RPMs/${TSYS}/${filename}"
	    /usr/local/sbin/upload_file.py ${filename},http://im.init.at/upload.py,$dst_filename
	    rm -f ${name}-latest.${TARCH}.rpm ${name}.${TARCH}.rpm
	    ln -s ${filename} ${name}-latest.${TARCH}.rpm
	    ln -s ${filename} ${name}.${TARCH}.rpm
	    popd > /dev/null
	fi
    fi
    [ "$register" = "1" ] && echo ${name}-${vers}.${TARCH}.rpm >> ${tdir}/RPMs/${TSYS}/.latest_versions_${TARCH}
done
