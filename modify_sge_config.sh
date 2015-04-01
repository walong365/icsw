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

# generate general config file
echo "prolog root@${SGE_ROOT}/3rd_party/prologue \$host \$job_owner \$job_id \$job_name \$queue " > /tmp/.qconf_config
echo "epilog root@${SGE_ROOT}/3rd_party/epilogue \$host \$job_owner \$job_id \$job_name \$queue " >> /tmp/.qconf_config
echo "shell_start_mode posix_compliant " >> /tmp/.qconf_config
echo "reschedule_unknown 00:30:00 " >> /tmp/.qconf_config
echo "enforce_project true " >> /tmp/.qconf_config
echo "enforce_user true " >> /tmp/.qconf_config
echo "qmaster_params ENABLE_FORCED_QDEL " >> /tmp/.qconf_config
echo "execd_params ACCT_RESERVED_USAGE,NO_REPRIORITIZATION,SHARETREE_RESERVED_USAGE,ENABLE_ADDGRP_KILL=true " >> /tmp/.qconf_config
echo "qlogin_command ${SGE_ROOT}/3rd_party/qlogin_wrapper.sh" >> /tmp/.qconf_config
#echo "rsh_command none" >> /tmp/.qconf_config
echo "rlogin_command /usr/bin/ssh" >> /tmp/.qconf_config
echo "qlogin_daemon /usr/sbin/sshd -i" >> /tmp/.qconf_config
echo "rlogin_daemon /usr/sbin/sshd -i" >> /tmp/.qconf_config
#echo "rsh_daemon none" >> /tmp/.qconf_config
echo "xterm /usr/bin/xterm" >> /tmp/.qconf_config
export EDITOR=${SGE_ROOT}/bin/noarch/sge_editor_conf.py
echo "Modifying general SGE-config, storing old one in /tmp/.sge_conf_old ..."
qconf -sconf > /tmp/.sge_conf_old
qconf -mconf global
rm -f ${pe_tmp} ${conf_temp}
unset EDITOR

