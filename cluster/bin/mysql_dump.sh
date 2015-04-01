#!/bin/bash

print_usage () {
    echo "Usage:"
    echo ""
    echo "  $0 [-d]"
    echo "  [-d]		only dump data"
}

ONLY_DATA=0

args=$(getopt hd $*) || { print_usage ; exit -1 ; }

set -- $args

for i ; do
    case "$i" in
    -d) shift ; ONLY_DATA=1 ;;
    -h) shift ; print_usage ; exit -1 ;;
    --) shift ; break ;;
    esac
done

if [ -f /etc/sysconfig/cluster/db_access ] ; then
    file_list=$(cat /etc/sysconfig/cluster/db_access  | grep "=" | cut -d "=" -f 2 | grep "^/" | tr ";" "\n")
else
    file_list="/etc/sysconfig/cluster/db.cf"
fi

for conf in $file_list ; do
    [ -r $conf ] && break
done

[ -r $conf ] || { echo "No readable mysql-configfiles found, exiting..." ; exit -1 ; }

. $conf

if [ "$(basename $conf)" != "db.cf" ] ; then
    export DB_PORT=${MYSQL_PORT}
    export DB_DATABASE=${MYSQL_DATABASE}
    export DB_USER=${MYSQL_USER}
    export DB_HOST=${MYSQL_HOST}
    export DB_PASSWD=${MYSQL_PASSWD}
fi

all_tables=$(echo "SHOW TABLES" | mysql_session.sh | grep -v Tables_in)

sorted_tables="application architecture cluster_event config_type device_class device_group device_location device_shape device_type distribution genstuff hw_entry_type image image_excl kernel log_status mac_ignore netdevice_speed network_device_type network_type new_config_type ng_check_command_type ng_contactgroup ng_device_contact ng_ext_host ng_period ng_service ng_service_templ package_set partition_fs partition_table rrd_class rrd_rra sge_complex sge_project sge_queue sge_userlist sge_userlist_type snmp_class snmp_mib status sys_partition capability ggroup ggroupcap vendor sge_ul_ult partition_disc partition package ng_device_templ ng_cgservicet new_config network lvm_vg lvm_lv inst_package device config_str config_script config_int config_bool config_blob app_instpack_con app_devgroup_con app_config_con apc_device device_config device_connection device_relationship device_rsync_config device_variable dmi_entry dmi_key hw_entry ibc_connection ibc_device instp_device kernel_build kernel_local_info kernel_log log_source macbootlog msoutlet netbotz_picture netdevice netip network_network_device_type new_rrd_data ng_check_command pci_entry peer_information pi_connection rrd_data_store rrd_set sge_host snmp_config user user_device_login user_ggroup user_var usercap wc_files xen_device xen_vbd sge_user_con sge_user sge_job session_data rrd_data ng_contact ng_ccgroup hopcount dmi_ext_key devicelog device_selection device_device_selection ccl_event ccl_dloc_con ccl_dgroup_con ccl_event_log ccl_user_con extended_log sge_job_run sge_log sge_pe_host"

if [ "$ONLY_DATA" = "1" ] ; then
    for table in ${sorted_tables} ; do
        mysqldump -u ${DB_USER} -h ${DB_HOST} -P ${DB_PORT} -p${DB_PASSWD} --add-locks --lock-tables --no-create-info --skip-add-drop-table --no-create-db  ${@:-${DB_DATABASE}} $table
    done
else
    mysqldump -u ${DB_USER} -h ${DB_HOST} -P ${DB_PORT} -p${DB_PASSWD} ${@:-${DB_DATABASE}}
fi
