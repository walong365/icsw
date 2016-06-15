#!/bin/bash

if [ ! -f /etc/sge_root ] ; then
    echo "no /etc/sge_root found, exiting ..."
    exit -1
fi
export SGE_ROOT=$(cat /etc/sge_root)
export SGE_CELL=$(cat /etc/sge_cell)

ARCH=`$SGE_ROOT/util/arch`

if [ -f ${SGE_ROOT}/${SGE_CELL}/common/product_mode ] ; then
    sge6=0
else
    sge6=1
fi

echo "Architecture is $ARCH (root is $SGE_ROOT)"

# adding usefull stuff to SGE (PEs and so one)
pe_tmp=`mktemp /tmp/.pe_XXXXXX`
conf_temp=`mktemp /tmp/.conf_XXXXXX`
orte_pe_name="orte";
simple_pe_name="simple";
pvm_pe_name="pvm";
# orte pe
echo "pe_name            $orte_pe_name
slots              65536
user_lists         NONE
xuser_lists        NONE
start_proc_args    ${SGE_ROOT}/3rd_party/pestart \$host \$job_owner \$job_id \$job_name \$queue \$pe_hostfile \$pe \$pe_slots
stop_proc_args     ${SGE_ROOT}/3rd_party/pestop \$host \$job_owner \$job_id \$job_name \$queue \$pe_hostfile \$pe \$pe_slots
allocation_rule    \$fill_up
control_slaves     FALSE
job_is_first_task  TRUE
accounting_summary TRUE
urgency_slots      min
qsort_args         NONE
" > $pe_tmp

. /etc/profile.d/batchsys.sh
${SGE_ROOT}/bin/${ARCH}/qconf -spl | grep $orte_pe_name > /dev/null || {
    echo "Adding PE named '$orte_pe_name' ..."
    ${SGE_ROOT}/bin/${ARCH}/qconf -Ap $pe_tmp
}
# simple pe
echo "pe_name            $simple_pe_name
slots              65536
user_lists         NONE
xuser_lists        NONE
start_proc_args    ${SGE_ROOT}/3rd_party/pestart \$host \$job_owner \$job_id \$job_name \$queue \$pe_hostfile \$pe \$pe_slots
stop_proc_args     ${SGE_ROOT}/3rd_party/pestop \$host \$job_owner \$job_id \$job_name \$queue \$pe_hostfile \$pe \$pe_slots
allocation_rule    \$fill_up
control_slaves     FALSE
job_is_first_task  TRUE
accounting_summary TRUE
urgency_slots      min
qsort_args         NONE
" > $pe_tmp
. /etc/profile.d/batchsys.sh
${SGE_ROOT}/bin/${ARCH}/qconf -spl | grep $simple_pe_name > /dev/null || {
    echo "Adding PE named '$simple_pe_name' ..."
    ${SGE_ROOT}/bin/${ARCH}/qconf -Ap $pe_tmp
}
# add default project
${SGE_ROOT}/bin/${ARCH}/qconf -sprjl | grep defaultproject > /dev/null || {
    echo "Adding default project named 'defaultproject' ..."
    echo "name defaultproject
oticket 0
fshare 0
acl NONE
xacl NONE " > ${conf_temp}
    [ "$sge6" = "0" ] && echo "default_project NONE ">> ${conf_temp}
    qconf -Aprj ${conf_temp}
}

export EDITOR=${SGE_ROOT}/bin/noarch/sge_editor_conf.py

# generate general config file
cat > /tmp/.qconf_config << EOF
prolog root@${SGE_ROOT}/3rd_party/prologue \$host \$job_owner \$job_id \$job_name \$queue 
epilog root@${SGE_ROOT}/3rd_party/epilogue \$host \$job_owner \$job_id \$job_name \$queue 
shell_start_mode posix_compliant
reschedule_unknown 00:30:00
qmaster_params ENABLE_FORCED_QDEL
execd_params ACCT_RESERVED_USAGE,NO_REPRIORITIZATION,SHARETREE_RESERVED_USAGE,ENABLE_ADDGRP_KILL=true,NOTIFY_KILL,H_MEMORYLOCKED=infinity
qlogin_command ${SGE_ROOT}/3rd_party/qlogin_wrapper.sh
rlogin_command /usr/bin/ssh
qlogin_daemon /usr/sbin/sshd -i
rlogin_daemon /usr/sbin/sshd -i
xterm /usr/bin/xterm
enforce_project false
auto_user_fshare 1000
enforce_user auto
EOF
#echo "rsh_command none" >> /tmp/.qconf_config
#echo "rsh_daemon none" >> /tmp/.qconf_config

echo "Modifying general SGE-config, storing old one in /tmp/.sge_conf_old ..."
qconf -sconf > /tmp/.sge_conf_old
qconf -mconf global

# generate scheduler config file
# generate general config file
cat > /tmp/.qconf_config << EOF
flush_submit_sec 1
flush_finish_sec 1
EOF

echo "Modifying SGE schedulerconfig, storing old one in /tmp/.sge_sconf_old ..."
qconf -ssconf > /tmp/.sge_sconf_old
qconf -msconf

rm -f ${pe_tmp} ${conf_temp}
unset EDITOR

echo "Copying sge_request and sge_qstat to ${SGE_ROOT}/${SGE_CELL}/common"
cp -a /opt/cluster/sge/sge_request /opt/cluster/sge/sge_qstat ${SGE_ROOT}/${SGE_CELL}/common

CONF_FILE="${SGE_ROOT}/3rd_party/proepilogue.conf"

if [ ! -f ${CONF_FILE} ] ; then
    echo "Creating ${CONF_FILE}"
    ${SGE_ROOT}/3rd_party/proepilogue.py > ${CONF_FILE}
fi

# add user sge to group idg such that it can access the sqlite database file
usermod -a -G idg sge
