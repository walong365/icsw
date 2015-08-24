#!/bin/bash
# Copyright (C) 2007-2009,2012,2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
# 
# This file is part of rms-tools
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

# """ configure, build and install a current version of SGE """

# untar (s)ge-6x.tar.gz

# cd gridengine/source

if [ ! -f /etc/sge_root ] ; then
    echo "No defaults in /etc/sge* found, exiting ..."
    exit -1
fi

export SGE_ROOT=$(cat /etc/sge_root)
export SGE_CELL=$(cat /etc/sge_cell)

echo "/etc/sge_root found, setting environment"
echo "SGE_ROOT=$SGE_ROOT, SGE_CELL=$SGE_CELL"

if [ ! -d ${SGE_ROOT}/bin ] ; then
    echo "No ${SGE_ROOT}/bin found, compiling SGE ..."
    if [ ! -f aimk ] ; then
        echo "Not in source directory (aimk has to be in the actual directory)"
        exit -1
    fi
    if [ ! -f /bin/csh ] ; then
        echo "need /bin/csh, exiting"
        exit -1
    fi
    # SECLIBS_STATIC fix
    sed -i s/set\ SECLIB.*=\ \"\"/set\ SECLIB=\"\"\;\ set\ SECLIBS_STATIC=\"\"/g aimk
    # HZ fix
    HZ=$(cat /boot/config* | grep CONFIG_HZ= | cut -d "=" -f 2| sort | uniq)
    sed -i sQ.*sys/param.*Q#define\ HZ\ ${HZ}Qg daemons/common/procfs.c
    echo "Compiling"
    export SGE_INPUT_CFLAGS=-Wno-error
    ./scripts/zerodepend
    ./aimk -only-depend -no-java -no-jni || exit -1
    ./aimk -man -no-java -no-jni || exit -1
    # removed parallel, not working with SoG
    # -parallel $(( $(cat /proc/cpuinfo | grep processor | wc -l ) * 2))
    #./aimk -spool-classic -no-dump -no-secure -no-jni -no-java  || { echo "Compilation failed, exiting" ; exit -1 ; }
    # set include path to find hwloc
    export SGE_INPUT_CFLAGS="-I/opt/cluster/include"
    # -lncurses is needed for centos, -ldl for build on eddie (13.1)
    export SGE_INPUT_LDFLAGS="-L/opt/cluster/lib64 -lncurses -ldl"
    ./aimk -spool-classic -no-secure -no-jni -no-java -no-qmake || {
        echo "Compilation failed, exiting" ;
	echo "maybe one of the following packages is missing:"
        echo "  - pam-devel"
        echo "  - xorg-x11-devel"
        echo "  - motif-devel (or openmotif-devel)"
        echo "  - ncurses-devel"
        echo ""
        echo "or (on debian systems)"
        echo "  - motif-dev"
        echo "  - ncurses-dev"
        echo "  - libpam-dev"
        echo "  - xorg-dev"
        echo ""
        echo "is missing"
        exit -1 ;
    }
  
    echo "Installing"
    echo Y | scripts/distinst -noexit -local -allall 
    echo "Modifying ownership of $SGE_ROOT to sge.sge"

    chown -R sge.sge ${SGE_ROOT}/
    # sge60/sge61/sge6x
    cd $SGE_ROOT
    # check for util/arch bug

    echo "Checking for buggy util/arch"
    ./util/arch | grep UNSUPPO >/dev/null && {
        echo "Fixing ${SGE_ROOT}/util/arch"
        cat util/arch | sed s/3\|4\|5/3\|4\|5\|6/g > /tmp/bla
        mv /tmp/bla util/arch
        chown sge.sge util/arch
        chmod 0755 util/arch
    }

    echo "Modify ld.so.conf.d"
    if [ ! -f /etc/ld.so.conf.d/sge.conf ] ; then
        echo "${SGE_ROOT}/lib/$(util/arch)" > /etc/ld.so.conf.d/sge.conf
        ldconfig
    fi
    # remove qmake reference
    sed -i s/qmake//g $(find . -iname inst_common.sh)
fi

sge_flavour=$(basename $SGE_ROOT)
cd $SGE_ROOT
inst_file=/tmp/sge_inst
echo "Creating installation template in $inst_file"

CELL_DIR="${SGE_ROOT}/${SGE_CELL}"
if [ -d "${CELL_DIR}" ] ; then
    echo "cell_dir ${CELL_DIR} already exists, moving to /tmp ..."
    if [ -d /tmp/${SGE_CELL} ] ; then
        mv ${CELL_DIR} /tmp/${SGE_CELL}
    else
        mv ${CELL_DIR} /tmp
    fi
fi

cat > $inst_file << EOF
SGE_ROOT=${SGE_ROOT}
SGE_QMASTER_PORT=$(cat /etc/services | grep sge_qmaster | tr "\t" " " | grep tcp | tr -s " " | cut -d " " -f 2 | cut -d "/" -f 1 | sort | uniq )
SGE_EXECD_PORT=$(cat /etc/services | grep sge_execd | tr "\t" " " | grep tcp | tr -s " " | cut -d " " -f 2 | cut -d "/" -f 1 | sort | uniq)
CELL_NAME=${SGE_CELL}
ADMIN_USER="sge"
QMASTER_SPOOL_DIR=/var/spool/${sge_flavour}
GID_RANGE=30000-30200
SPOOLING_METHOD=classic
PAR_EXECD_INST_COUNT=20
ADMIN_HOST_LIST=$(hostname)
SUBMIT_HOST_LIST=$(hostname)
EXEC_HOST_LIST=""
SGE_ENABLE_SMF="false"
EXECD_SPOOL_DIR_LOCAL=/var/spool/${sge_flavour}
EXECD_SPOOL_DIR=/var/spool/${sge_flavour}
HOSTNAME_RESOLVING="true"
SHELL_NAME="rsh"
COPY_COMMAND="rcp"
DEFAULT_DOMAIN="none"
ADMIN_MAIL="lang-nevyjel@init.at"
ADD_TO_RC="true"
SET_FILE_PERMS="true"
SCHEDD_CONF="1"
SHADOW_HOST=""
EXEC_HOST_LIST_RM=""
REMOVE_RC="false"
WINDOWS_SUPPORT="false"
SGE_CLUSTER_NAME="cluster"
EOF

./inst_sge  -m  -auto /tmp/sge_inst

