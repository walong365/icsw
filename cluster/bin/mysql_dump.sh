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

file_list=$(cat /etc/sysconfig/cluster/db_access  | grep "=" | cut -d "=" -f 2 | grep "^/" | tr ";" "\n")

for conf in $file_list ; do
    [ -r $conf ] && break
done

[ -r $conf ] || { echo "No readable mysql-configfiles found, exiting..." ; exit -1 ; }

. $conf

all_tables=$(echo "SHOW TABLES" | mysql_session.sh | grep -v Tables_in)
sorted_tables="application architecture capability cluster_event config_type device_class device_connection device_group device_location device_relationship device_selection device_shape device_type distribution dmi_ext_key extended_log genstuff ggroup ggroupcap hw_entry_type image image_excl kernel kernel_build log_source log_status mac_ignore macbootlog netdevice_speed network_device_type network_type new_config_type ng_check_command_type ng_contact ng_contactgroup ng_device_contact ng_device_templ ng_ext_host ng_period ng_service ng_service_templ package package_set partition_fs partition_table pci_entry pi_connection rrd_class rrd_data rrd_rra rrd_set session_data sge_complex sge_host sge_job sge_job_run sge_log sge_pe_host sge_project sge_queue sge_user sge_user_con sge_userlist sge_userlist_type snmp_class snmp_mib status sys_partition user user_ggroup user_var usercap vendor snmp_config sge_ul_ult partition_disc partition ng_cgservicet ng_ccgroup new_config network lvm_vg lvm_lv inst_package device config_str config_script config_int config_bool config_blob ccl_event_log ccl_event ccl_dloc_con ccl_dgroup_con app_instpack_con app_devgroup_con app_config_con apc_device ccl_user_con device_config device_device_selection device_rsync_config device_variable devicelog dmi_entry dmi_key hw_entry ibc_connection ibc_device instp_device kernel_local_info kernel_log msoutlet netbotz_picture netdevice netip network_network_device_type new_rrd_data ng_check_command peer_information rrd_data_store user_device_login wc_files xen_device xen_vbd hopcount"

if [ "$ONLY_DATA" = "1" ] ; then
	for table in ${sorted_tables} ; do
        mysqldump -u ${MYSQL_USER} -h ${MYSQL_HOST} -P ${MYSQL_PORT} -p${MYSQL_PASSWD} --add-locks --lock-tables --no-create-info --skip-opt --skip-add-drop-table --no-create-db  ${@:-${MYSQL_DATABASE}} $table
	done
else
	mysqldump -u ${MYSQL_USER} -h ${MYSQL_HOST} -P ${MYSQL_PORT} -p${MYSQL_PASSWD} ${@:-${MYSQL_DATABASE}}
fi
