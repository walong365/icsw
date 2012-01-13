#!/bin/bash

#set -x
#WHICH=which
WHICH="type -p"

#
####################### END OF SETTINGS ####################
usage () {
echo "Usage:"
echo " $0 </path/to/kerneldir> [<version>]"
echo
echo "   </path/to/kerneldir> points to the dir the kernel is residing in"
echo "                        e.g. /tftpboot/kernels/2.6.1-mm"
echo "   [<version>] optional, is the version as in /lib/modules/<version>/kernel/"
echo "                        e.g. 2.6.1-mm2"
echo "   INIT_MODS is an environment variable containing a list of modules"
echo "                        to add to initrd."
echo "                        e.g. INIT_MODS=\"fs/reiserfs.o fs/ext3/ext3.o\""
echo
}

LINUXRC_NAME=linuxrc

#returns number of next free loopdevice
find_free_loopdevice () {
l=0
while test $l -le 8 && ret=$(losetup /dev/loop$l 2>&1 >& /dev/null ; echo $?) && test $ret -ne 1 ; do
  l=$(($l + 1))
done
echo -n $l
}

is_64bit () {
egrep "^(CONFIG_X86_64)=" $kdir/.config > /dev/null 2>&1 && return 0 || return 1
}

sql_query () {
        echo $* | mysql -s -u ${MYSQL_USER}  -h ${MYSQL_HOST} -p${MYSQL_PASSWD} -D ${MYSQL_DATABASE}
}

init_sql () {
CONFIGFILE='/usr/local/cluster/etc/mysql.cf'
[ ! -f $CONFIGFILE ] && { echo "No configfile for database, exiting" ; return 1 ; }
. $CONFIGFILE
#        bm_stuff=`echo $(sql_query SELECT d.device_idx,d.name FROM device d, deviceconfig dc, config c WHERE dc.config=c.config_idx AND dc.device=d.device_idx AND c.name=\'kernel_server\' AND d.name=\'$(hostname)\')`
#        if [ "${bm_stuff:-0}" = "0" ] ; then
#                echo "${HOSTNAME} is not a kernel-server"
#                exit -1
#        fi
#        dev_idx=`echo $bm_stuff| cut -d " " -f 1`
return 0
}


populate_it() {
modlist="";
setup_lo=0;
opt="$1"
while [ ! -z "$opt" ] ; do 
  opt=${opt#-}
  case "$opt" in
      l) shift ; lrc="$1" ;;
      D) shift ; dest="$1" ;; 
      s) shift ; size="$1" ;; 
      m) shift ; modlist="$1" ;;
      d) shift ; dirlist="$1" ;;
      f) shift ; filelist="$1" ;;
      L) setup_lo=1 ;;
      *) echo "Unknown option -$opt !" ;;
  esac
  shift
  opt="$1"
done

tfile=`mktemp /tmp/initrd_XXXXXX`
tdir=${tfile}_d
mkdir $tdir
if [ "${setup_lo:-0}" = "1" ]  ; then
    echo "Setting up loopback-device ..."
    dd if=/dev/zero of=$tfile bs=1024 count=${size} > /dev/null 2>&1
    losetup /dev/$loopdevice $tfile || { echo $loopdevice already mounted? ; echo "$0 $* failed" ; exit 1 ; }
    mkfs.ext2 -F -v -m 0 -b 1024 $tfile ${size} > /dev/null
    mount -o loop -t ext2 $tfile $tdir
fi

if [ ! ".$modlist" = "." ] ; then
    mkdir -p ${tdir}/lib/modules/${kver}/kernel/drivers/
    echo -n "Adding modules: "
    modlist=`for i in $(for j in $modlist ; do echo $j | sed s/\\\.o$//g | sed s/\\\.ko$//g ; done) ; do find $kdir/lib/modules/$kver/kernel/ -type f -iname "$(basename $i).*" ; done`
    for f in $modlist ; do
      mkdir -p $(dirname $f)
      cp -a $f ${tdir}/lib/modules/${kver}/kernel/drivers/
      echo -n "$(basename $f) "
    done
    echo
fi
#XXX
#umount $tdir
#losetup -d /dev/$loopdevice
#exit 17
is_64bit && [ -d /lib64/security ] && pam_dir=lib64/security || { [ -d /lib/security ] && pam_dir=lib/security || pam_dir="" ; }
pam_files="rlogin su rsh rexec login other"
echo "Generating filelist ..."

rd_list="$pam_dir"
for dir in $dirlist ; do
  [ ".$dir" != "." ] && [ -d /$dir ] && rd_list="$rd_list $dir"
done
dir_list="$rd_list"

echo "Resolving symlinks ..."
file_list=$(/usr/local/cluster/bin/py_resolv.py -s $filelist)

echo "Resolving pam_libs ..."
pam_libs=$(/usr/local/cluster/bin/py_resolv.py -p $pam_dir $pam_files)
echo "Resolving libraries ..."
lib_list="$(/usr/local/cluster/bin/py_resolv.py -l $file_list) $pam_libs"
echo "Resolving directories ..."
dir_list="$dir_list $(/usr/local/cluster/bin/py_resolv.py -d $file_list $lib_list)"

# add entries
for file in console ram ram0 ram1 ram2 null zero fd0 log xconsole ptmx ; do
  file_list="$file_list /dev/$file"
done
for file in nsswitch.conf host.conf services protocols login.defs ; do
  file_list="$file_list /etc/$file"
done
for file in $pam_files ; do
  [ -f $file ] || continue
  file_list="$file_list /etc/pam.d/$file"
done

echo "Number of dirs / files / libs : $(echo $dir_list | wc -w) / $(echo $file_list | wc -w) / $(echo $lib_list | wc -w)"

#echo dir_list=$dir_list
#echo file_list=$file_list
#echo lib_list=$lib_list

for dir in $dir_list ; do
  mkdir -p $tdir/$dir ;
done
chmod 1777 $tdir/tmp

for file in $file_list ; do
  cp -a $file $tdir/$file
  [ -f $file ] && [ ! -h $file ] && strip -s $tdir/$file 2>/dev/null
done

for lib in $lib_list ; do
  cp -a $lib $tdir/$lib
done

touch $tdir/etc/fstab $tdir/etc/mtab

echo "generating /etc/passwd and /etc/group"
echo root::0:0:root:/root:/bin/bash > $tdir/etc/passwd
echo bin::1:1:bin:/bin/:/bin/bash >> $tdir/etc/passwd
echo daemon::2:2:daemon:/sbin:/bin/bash >> $tdir/etc/passwd
echo root:x:0:root > $tdir/etc/group
echo bin:x:1:root,bin,daemon >> $tdir/etc/group
echo tty:x:5: >> $tdir/etc/group
echo wheel:x:10: >> $tdir/etc/group

echo "shell   stream  tcp     nowait  root  /usr/sbin/tcpd in.rshd -L " > $tdir/etc/inetd.conf
echo "login   stream  tcp     nowait  root    /usr/sbin/tcpd  in.rlogind" >> $tdir/etc/inetd.conf
cat >$tdir/etc/xinetd.conf <<EOF 
defaults
{
        instances               = 60
        log_type                = SYSLOG authpriv
        log_on_success  = HOST PID
        log_on_failure  = HOST
        cps   = 25 30
}

EOF
mkdir $tdir/etc/xinetd.d
cat >$tdir/etc/xinetd.conf <<EOF 
service shell
{
        disable = no
        socket_type    = stream
        wait   = no
        user   = root
        log_on_success  += USERID
        log_on_failure    += USERID
        server   = /usr/sbin/in.rshd
}
EOF

is_64bit && [ -d /lib64 ] && { cp -a /lib64/libnss* $tdir/lib64 ; cp -a /lib64/libnsl* $tdir/lib64 ; } || { cp -a /lib/libnss* $tdir/lib ; cp -a /lib/libnsl* $tdir/lib ; }


echo "ALL: ALL " > $tdir/etc/hosts.allow

cp -a $lxdir/${lrc} $tdir/${LINUXRC_NAME}
cp -a $lxdir/stage3 $tdir/sbin/stage3
chmod +x $tdir/${LINUXRC_NAME} $tdir/sbin/stage3
chown 0.0 $tdir/${LINUXRC_NAME} $tdir/sbin/stage3

#touch $tdir/etc/ld.so.conf
cat >$tdir/etc/ld.so.conf <<eof
/usr/X11R6/lib64/Xaw95
/usr/X11R6/lib64/Xaw3d
/usr/X11R6/lib64
/usr/X11R6/lib/Xaw95
/usr/X11R6/lib/Xaw3d
/usr/X11R6/lib
/usr/x86_64-suse-linux/lib64
/usr/x86_64-suse-linux/lib
/usr/local/lib
/usr/openwin/lib
/opt/kde/lib
/opt/kde2/lib
/opt/kde3/lib
/opt/gnome/lib
/opt/gnome2/lib
/lib64
/lib
/usr/lib64
/usr/lib
/usr/local/lib64
/usr/openwin/lib64
/opt/kde/lib64
/opt/kde2/lib64
/opt/kde3/lib64
/opt/gnome/lib64
/opt/gnome2/lib64
eof
chroot $tdir /sbin/ldconfig

freespace=$(df -k $tdir | awk '{if (!/Filesystem/){print $3}}')
if [ $freespace -le 30 ] ; then
    echo Warning: initrd is ${size}k and only ${freespace}k left unused. ; echo Verify that all files made it to the initrd\! ; 
    echo continuing.. ; 
else 
    echo Ok: sizeof initrd is ${size}k and ${freespace}k are left ;
fi

du -hs $tdir

#ls -laR $tdir/
#du -hs $tdir/*

if [ "${setup_lo:-0}" = "1" ]  ; then
    umount $tdir
    losetup -d /dev/$loopdevice
    echo "Compressing image.."
    gzip -9 $tfile
    #mv $tfile ${tfile}.gz

else
    echo "Taring image.."
    tar cjpsf ${tfile}.gz -C $tdir .
fi
tfile=${tfile}.gz

cp -a $tfile $kdir/${dest}.gz
chmod a+r $kdir/${dest}.gz
echo "wrote '$kdir/${dest}.gz'"
rm -rf $tdir $tfile

}
################ END OF FUNCTION DEFINITIONS ####################


[ $# -lt 1 ] && { usage ; echo "Need arguments !" ; exit -2 ; }

[ ! -d $1 ] && { usage ; echo "First argument must be a directory" ; exit -2 ; }
kdir=$(echo $1 | sed -e s§/[/]*$§§)
# guess the optional <version> argument
kver=$kdir/lib/modules/${2-"*"}
[ -d $(echo $kver) ] && kver=$(echo ${kver} | sed -e "s§$kdir/lib/modules/§§" -e "s§/kernel$§§")
[ ! -d "$kdir/lib/modules/${kver}/kernel" ] && { usage ; echo "could not determine correct /kernel/ directory:" ; echo ${kver} ; echo ; echo "Please specify a correct <version>" ; exit -2 ; }  


echo "cmd is: $0 $kdir $kver"
echo -n "$kver is a "
is_64bit && echo -n 64 || echo -n 32
echo "bit kernel."


#initsize=16384
test -f $kdir/.config && initsize=$(egrep ^CONFIG_BLK_DEV_RAM_SIZE $kdir/.config | cut -d'=' -f2) || initsize=16384
echo "using initrd($(egrep ^CONFIG_BLK_DEV_RAM_SIZE $kdir/.config 2> /dev/null | cut -d'=' -f2)) with size: $initsize kB."

test -d /usr/local/cluster/lcs && \
  lxdir=/usr/local/cluster/lcs || \
  { echo "could not find proper linuxrc, using a local one." ; lxdir=$(cd `echo $0 | sed 's%/[^/]*$%%'` ; pwd ; ) ; [ ! -f $lxdir/linuxrc ] && echo you\'re screwed ; }

######init_sql
loopdevice=loop$(find_free_loopdevice)

#blockdev --flushbufs $ramdev

s1_dir_list="root tmp dev etc/pam.d proc sys var/empty var/run var/log dev/pts sbin usr/lib $pam_dir"
s1_file_list="free ethtool sh bash echo cp mount cat ls mount mkdir tar gunzip umount rmdir egrep fgrep grep rm chmod ps sed dmesg ping mknod true false logger modprobe modprobe.old lsmod lsmod.old rmmod rmmod.old depmod depmod.old insmod insmod.old mkfs.ext2 ifconfig pivot_root init route tell_mother bzip2 bunzip2 cut tr chroot whoami killall seq inetd xinetd in.rshd tcpd in.rlogind hoststatus chown wc arp tftp mkfifo ldconfig sleep"

s2_dir_list="root tmp dev etc/pam.d proc sys var/empty var/run var/log dev/pts sbin usr/lib $pam_dir"
s2_file_list="ethtool sh strace bash echo cp mount cat ls mount mkdir df tar gzip gunzip umount rmdir egrep fgrep grep basename rm chmod ps touch sed dd sync dmesg ping mknod usleep sleep login true false logger fsck modprobe modprobe.old lsmod lsmod.old rmmod rmmod.old depmod depmod.old insmod insmod.old mkfs.ext2 mkfs.ext3 mkfs.xfs fdisk cfdisk sfdisk ifconfig mkfs.reiserfs mkswap reboot halt shutdown init route tell_mother lilo grub-install grub syslogd bzip2 bunzip2 cut tr chroot whoami killall head tail seq inetd in.rshd tcpd in.rlogind hoststatus ldconfig sort dirname chown wc portmap klogd arp ln find tftp uname xinetd"

s2size=32768

echo -e "\nGenerating stage 1 initrd ...\n"
populate_it -L -l stage1 -D initrd -s $initsize -m "$INIT_MODS" -d "$s1_dir_list" -f "$s1_file_list"
echo -e "\nGenerating stage 2 initrd ...\n"
populate_it -l stage2 -D initrd_stage2 -s $s2size -d "$s2_dir_list" -f "$s2_file_list"

echo cleaning up

exit 0
