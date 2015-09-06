#!/bin/bash
# Copyright (C) 2013-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
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

GROUP=sge
USER=sge

PREFIX=/opt/cluster
SGE_DIST_DIR=${PREFIX}/sge

cat /etc/services | grep sge_execd > /dev/null || {
    echo "adding sge_qmaster and sge_execd to /etc/services"
    echo "sge_qmaster     6444/tcp" >> /etc/services
    echo "sge_execd       6445/tcp" >> /etc/services
}

if [ ! -f /etc/sge_root ] ; then
    echo "/etc/sge_{root,cell,server} not found, writing default values ..."
    [ ! -f /etc/sge_root   ] && echo "/opt/sge" > /etc/sge_root
    [ ! -f /etc/sge_cell   ] && echo "sgecell" > /etc/sge_cell
    [ ! -f /etc/sge_server ] && echo "localhost" > /etc/sge_server

    SGE_ROOT=`cat /etc/sge_root`
    if [ ! -d ${SGE_ROOT} ] ; then
       echo "Creating sge_root ${SGE_ROOT} ..."
        mkdir ${SGE_ROOT}
        chown -R ${USER}:${GROUP} ${SGE_ROOT}
    fi

    SGE_SPOOL=/var/spool/$(basename $(cat /etc/sge_root))
    if [ ! -d ${SGE_SPOOL} ] ; then
        echo "Creating sge_spool ${SGE_SPOOL} ..."
        mkdir ${SGE_SPOOL}
        chown -R ${USER}:${GROUP} ${SGE_SPOOL}
    fi

    echo
    echo "most of the files described below can be found in ${SGE_DIST_DIR}"
    echo "Script to copy the tools and create the necessary links is located in ${SGE_ROOT}/bin/noarch/create_sge_links.py"
    echo "Script to modify SGE-config is located in ${SGE_ROOT}/bin/noarch/modify_sge_config.sh"
    echo "Script to modify logging-server.d is located in ${SGE_ROOT}/bin/noarch/add_logtail.sh"
    echo "Don't forget to set the starter_method of all queues to ${SGE_ROOT}/3rd_party/sge_starter.sh"
    echo "Don't forget to copy sge_request to ${SGE_ROOT}/${SGE_CELL}/common"
    echo "init-Scripts for SGE can be found in ${SGE_DIST_DIR}/init.d"
fi
