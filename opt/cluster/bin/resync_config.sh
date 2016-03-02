#!/bin/bash
#
# Copyright (C) 2001-2008,2013,2015-2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file belongs to cluster-backbone
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

function copy_config() {
    # get partition
    echo "Requesting configuration"
    conf_str=`get_conf_str "create_config"`
    num_req=`echo $conf_str| cut -d " " -f 1`
    echo "Waiting for configuration ACK"
    conf_str=`get_conf_str "ack_config"`
    if [ "$(echo $conf_str | cut -d " " -f 2)" != "ok" ] ; then
        echo "error getting config: $conf_str"
        ret_val=1;
    else
        if [ ! -f /conf/config_files_${1} ] ; then
            echo "No file config_files_${1} found in /conf, exiting ..."
            ret_val=1;
        else
            num_ack=`echo $conf_str| cut -d " " -f 1`
            tot_req=$(($num_req + $num_ack))
            if [ -f /conf/.config_files ] ; then
                while read file ; do
                    rm -f /$basedir/$file ;
                done < /conf/.config_files
            fi
            rm -f /conf/.config_files
            if [ -f /conf/config_dirs_${1} ] ; then
                echo "Generating directory for config $1 from server"
                while read num dir ; do
                    num_w=`echo $dir | wc -w`
                    if [ "${num_w}" -ge "4" ] ; then
                        uid=`echo $dir | cut -d " " -f 1`
                        gid=`echo $dir | cut -d " " -f 2`
                        mode=`echo $dir | cut -d " " -f 3`
                        dir=`echo $dir | cut -d " " -f 4-`
                    else
                        uid=0;
                        gid=0;
                        mode="0755";
                    fi
                    echo "Generating directory ($mode,$uid,$gid) ${dir}";
                    mkdir -p "/$basedir/$dir"
                    chown ${uid}:${gid} "/$basedir/$dir"
                    chmod ${mode} "/$basedir/$dir"
                done < /conf/config_dirs_${1}
            fi
            if [ -f /conf/config_files_${1} ] ; then
                echo "Installing config files for config $1 from server"
                while read num uid gid mode file ; do
                    echo "Installing ($mode,$uid,$gid) $file" ;
                    filedir=`dirname /$basedir/$file`
                    echo "$file" >> /conf/.config_files
                    [ ! -d "$filedir" ] && mkdir -p "$filedir"
                    [ -d "$filedir" ] && {
                        cp -a /conf/content_${1}/$num /$basedir/$file ;
                        chown ${uid}:${gid} /$basedir/$file ;
                        chmod ${mode} /$basedir/$file ;
                    }
                done < /conf/config_files_${1}
            fi
            if [ -f /conf/config_links_${1} ] ; then
                echo "Linking files config $1 from server"
                while read num dest src ; do
                    echo "Linking from $src to $dest "
                    chroot /$basedir [ -L $src ] && rm -f /${basedir}/$src
                    chroot /$basedir /bin/ln -sf $dest $src
                    echo $src >> /conf/.config_files
                done < /conf/config_links_${1}
            fi
            if [ -f /conf/config_${1}.rc ] ; then
                echo "Installing rc.config for config $1 from server"
                file="etc/rc.config"
                echo "$file" >> /conf/.config_files
                cp -a /conf/config_${1}.rc /$basedir/$file
            fi
            ret_val=0;
        fi
    fi
#start_shell
    return $ret_val;
}

function get_conf_str() {
    num_retries=1
    while true ; do 
        ret=`tell_mother_zmq -m $bserver -p 8005 -w $1 2>&1`  && {
            state=`echo $ret| cut -d " " -f 1`
            [ "$state" == "ok" ] && break
        }
        #time_wait=$(( 10 + $RANDOM / 5000))
        time_wait=$(( 1 ))
        echo >&2 "error ($ret), will sleep for $time_wait seconds"
        num_retries=$(($num_retries + 1))
        sleep $time_wait
    done
    echo "$num_retries $ret"
}

function fix_uuid() {
    if [ -d /etc/sysconfig/cluster/ ] ; then
        cat /opt/cluster/etc/cstores.d/icsw.device_config.xml | grep uuid |cut -d ">" -f 2 |cut -d "<" -f 1  > /etc/sysconfig/cluster/.cluster_device_uuid
    fi
}

export PATH=$PATH:/sbin:/usr/sbin:/usr/local/bin:/usr/local/sbin

fix_uuid

[ -f /etc/motherserver ] || { echo "No motherserver defined, exiting ..." ; exit -1  ; }
FNAME=/tmp/.hoststat
[ -f $FNAME ] && old_stat=`cat $FNAME`
# get target_state
bserver=`cat /etc/motherserver`
basedir="/"

echo "Requesting target state/network"
conf_str=`get_conf_str "get_target_sn "`
num=`echo $conf_str| cut -d " " -f 1`
tstate=`echo $conf_str | cut -d " " -f 3`
prod_net=`echo $conf_str | cut -d " " -f 4`
rsync_flag=`echo $conf_str | cut -d " " -f 5`
rsync_compr=`echo $conf_str | cut -d " " -f 6`
device_name=`echo $conf_str | cut -d " " -f 7`
if [ $(echo $conf_str | wc -w) -eq 8 ] ; then
    config_server=$bserver
    config_dir=`echo $conf_str | cut -d " " -f 8`
else
    config_server=`echo $conf_str | cut -d " " -f 8`
    config_dir=`echo $conf_str | cut -d " " -f 9`
fi

echo "Target state is $tstate (prod_net $prod_net)"

[ ! -d /conf ] && mkdir /conf

mountd=$config_dir/$device_name

echo -n "Trying to mount $mountd from $config_server to /conf (with -o noacl) "
ret=`mount -o noacl $config_server:$mountd /conf`
echo $ret | grep un\.\*noacl >/dev/null && {
    echo "error"
    echo -n "Trying to mount $mountd from $config_server to /conf "
    mount $config_server:$mountd /conf
}
echo "OK"

copy_config $prod_net

umount /conf
rmdir /conf

[ -n "$old_stat" ] && echo $old_stat > $FNAME
