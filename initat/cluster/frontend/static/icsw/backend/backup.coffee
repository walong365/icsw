# Copyright (C) 2012-2016 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
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

angular.module(

    # module for handling object backup and restore

    "icsw.backend.backup",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap",
        "init.csw.filters", "restangular", "noVNC", "ui.select", "icsw.tools",
        "icsw.device.info", "icsw.tools.tree", "icsw.user",
        "icsw.backend.devicetree",
    ]
).service("icswBackupDefinition", ["icswBaseMixinClass", (icswBaseMixinClass) ->

    class backup_def extends icswBaseMixinClass
        constructor: () ->
            @simple_attributes = []
            @list_attributes = []

        create_backup: (obj) =>
            _bu = {}
            @pre_backup(obj)
            for _entry in @simple_attributes
                _bu[_entry] = obj[_entry]
            for _entry in @list_attributes
                _bu[_entry] = _.cloneDeep(obj[_entry])
            @post_backup(obj, _bu)
            obj.$$_ICSW_backup_data = _bu
            obj.$$_ICSW_backup_def = @

        restore_backup: (obj) =>
            if obj.$$_ICSW_backup_data?
                _bu = obj.$$_ICSW_backup_data
                @pre_restore(obj, _bu)
                for _entry in @simple_attributes
                    obj[_entry] = _bu[_entry]
                for _entry in @list_attributes
                    obj[_entry] = _.cloneDeep(_bu[_entry])
                @post_restore(obj, _bu)
                delete obj.$$_ICSW_backup_data
                delete obj.$$_ICSW_backup_def
        
        changed: (obj) =>
            if obj.$$_ICSW_backup_data?
                _bu = obj.$$_ICSW_backup_data
                _changed = false
                if not _changed
                    for entry in @simple_attributes
                        if obj[entry] != _bu[entry]
                            _changed = true
                            break
                if not _changed
                    for entry in @list_attributes
                        _attr_name = "compare_#{entry}"
                        if @[_attr_name]
                            if not @[_attr_name](obj[entry], _bu[entry])
                                _changed = true
                                break
                        else
                            if not _.isEqual(obj[entry], _bu[entry])
                                _changed = true
                                break
                return _changed

        pre_backup: (obj) =>
            # called before backup

        post_backup: (obj, bu) =>
            # called after backuop

        pre_restore: (obj, bu) =>
            # called before restore

        post_restore: (obj, bu) =>
            # called after restore

]).service("icswDeviceBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswDeviceBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "name", "comment", "device_group", "domain_tree_node", "enabled",
                "alias", "mon_device_templ", "monitor_checks", "enable_perfdata",
                "flap_detection_enabled", "mon_resolve_name", "store_rrd_data"
            ]

]).service("icswDeviceBootBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswDeviceBootBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "dhcp_mac", "dhcp_write",
            ]

]).service("icswDeviceGroupBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswDeviceGroupBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = ["name", "comment", "domain_tree_node", "enabled", "description"]

]).service("icswNetworkTypeBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswNetworkTypeBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = ["identifier", "description"]

]).service("icswNetworkDeviceTypeBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswNetworkDeviceTypeBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = ["identifier", "description", "name_re", "mac_bytes", "allow_virtual_interfaces", "for_matching"]

]).service("icswNetworkDeviceBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswNetworkDeviceBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "devname", "macaddr", "driver_options", "speed", "netdevice_speed",
                "ignore_netdevice_speed", "driver", "routing", "inter_device_routing",
                "penalty", "dhcp_device", "fake_macaddr", "network_device_type", "description",
                "is_bridge", "is_bond", "bridge_device", "bond_master", "bridge_name", "vlan_id",
                "master_device", "enabled", "mtu", "snmp_idx", "force_network_device_type_match",
                "snmp_network_type", "snmp_admin_status", "snmp_oper_status", "desired_status",
                "wmi_interface_index",
            ]

]).service("icswNetworkIPBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswNetworkIPBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "ip", "network", "netdevice", "penalty", "alias", "alias_excl", "domain_tree_node",
            ]

]).service("icswNetworkBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswNetworkBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "identifier", "nework", "netmask", "gateway", "broadcast", "penalty", "enforce_unique_ips",
                "preferred_domain_tree_node", "start_range", "end_range", "master_network", "network_type"
            ]
            @list_attributes = [
                "network_device_type"
            ]

]).service("icswPeerInformationBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswPeerInformationBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "s_netdevice", "s_spec", "d_netdevice", "d_spec", "penalty", "autocreated", "info",
            ]

]).service("icswConfigCatalogBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswConfigCatalogBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "name", "author", "url",
            ]

]).service("icswConfigBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswConfigBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "name", "config_catalog", "description", "priority", "service_config", "system_config", "enabled",
            ]
            @list_attributes = [
                "categories"
            ]

]).service("icswCategoryBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswCategoryBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "name", "full_name", "parent", "depth", "immutable",
                "physical", "latitude", "longitude", "locked", "comment",
                "useable",
            ]

]).service("icswMonCheckCommandBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswMonCheckCOmmandBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "config", "mon_service_templ", "name", "mon_check_command_special",
                "command_line", "description", "enable_perfdata", "volatile", "event_handler",
                "is_event_handler", "event_handler_enabled", "is_active", "tcp_coverage",
            ]
            @list_attributes = [
                "categories", "exclude_devices"
            ]

]).service("icswConfigVarBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswConfigVarBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "config", "name", "description", "value", "device"
            ]

]).service("icswConfigScriptBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswConfigScriptBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "name", "description", "enabled", "priority", "config", "value", "error_text",
            ]

]).service("icswDeviceVariableBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswDeviceVariableBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "device", "is_public", "name", "description", "local_copy_ok", "inherit", "protected",
                "var_type", "val_str", "val_int", "val_blob", "val_data", "val_time",
            ]

]).service("icswDomainTreeNodeBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswDomainTreeNodeBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "name", "full_name", "parent", "node_postfix", "depth",
                "intermediate", "create_short_names", "always_create_ip",
                "write_nameserver_config",
            ]

]).service("icswLocationGfxBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswLocationGfxBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "name", "image_name", "uuid", "image_stored",
                "image_count", "width", "height",
                "content_type", "location", "locked", "changes", "comment",
            ]

]).service("icswCDConnectionBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswCDConnectionBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "parent", "child", "created_by", "connection_info",
                "parameter_i1", "parameter_i2", "parameter_i3", "parameter_i4",
            ]

]).service("icswRRDGraphSettingBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswRRDGraphSettingBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "user", "name", "hide_empty", "include_zero",
                "scale_mode", "legend_mode", "cf", "merge_devices", "merge_graphs",
                "merge_controlling_devices", "graph_setting_size",
                "graph_setting_timeshift", "graph_setting_forecast",
            ]

]).service("icswUserBackup", ["icswBackupDefinition", "icswUserGroupTools", (icswBackupDefinition, icswUserGroupTools) ->

    class icswUserBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "idx", "active", "login", "uid", "group",
                "aliases", "export", "home", "shell",
                "password",
                "first_name", "last_name", "title", "email",
                "pager", "tel", "comment",
                "is_superuser", "db_is_auth_for_password",
                "only_webfrontend", "create_rms_user",
                "scan_user_home", "scan_depth",
            ]
            @list_attributes = [
                "allowed_device_groups", "secondary_groups",
                "user_permission_set", "user_object_permission_set",
            ]

        compare_user_permission_set: (a_list, b_list) =>
            return @_compare_perms(a_list, b_list)

        compare_user_object_permission_set: (a_list, b_list) =>
            return @_compare_perms(a_list, b_list)

        _compare_perms: (a_list, b_list) =>
            return _.isEqual(
                [icswUserGroupTools.get_perm_fp(a) for a in a_list]
                [icswUserGroupTools.get_perm_fp(b) for b in b_list]
            )

]).service("icswGroupBackup", ["icswBackupDefinition", "icswUserGroupTools", (icswBackupDefinition, icswUserGroupTools) ->

    class icswGroupBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "idx", "active", "groupname", "gid",
                "homestart", "group_comment",
                "first_name", "last_name", "title", "email",
                "pager", "tel", "comment",
                "parent_group",
            ]
            @list_attributes = [
                "allowed_device_groups",
                "group_permission_set", "group_object_permission_set",
            ]

        compare_group_permission_set: (a_list, b_list) =>
            return @_compare_perms(a_list, b_list)

        compare_group_object_permission_set: (a_list, b_list) =>
            return @_compare_perms(a_list, b_list)

        _compare_perms: (a_list, b_list) =>
            return _.isEqual(
                [icswUserGroupTools.get_perm_fp(a) for a in a_list]
                [icswUserGroupTools.get_perm_fp(b) for b in b_list]
            )

]).service("icswMonPeriodBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswMonPeriodBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "name", "alias", "mon_range", "tue_range", "wed_range", "thu_range",
                "fri_range", "sat_range", "sun_range",
            ]

]).service("icswMonNotificationBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswMonNotificationBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "name", "channel", "not_type", "subject", "content", "enabled",
            ]

]).service("icswMonServiceTemplBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswMonServiceTemplBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "name", "volatile", "nsc_period", "max_attempts",
                "check_interval", "retry_interval", "ninterval", "nsn_period",
                "nrecovery", "ncritical", "nwarning", "nunknown", "nflapping",
                "nplanned_downtime", "low_flap_threshold", "high_flap_threshold",
                "flap_detection_enabled", "flap_detect_ok", "flap_detect_warn",
                "flap_detect_critical", "flap_detect_unknown", "check_freshness",
                "freshness_threshold",
            ]

]).service("icswMonDeviceTemplBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswMonDeviceTemplBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "name", "mon_service_templ", "host_check_command",
                "check_interval", "retry_interval", "max_attempts", "ninterval",
                "not_period", "mon_period",
                "nrecovery", "ndown", "nunreachable", "nflapping",
                "nplanned_downtime", "is_default", "low_flap_threshold", "high_flap_threshold",
                "flap_detection_enabled", "flap_detect_ok", "flap_detect_down",
                "flap_detect_unreachable", "check_freshness",
                "freshness_threshold",
            ]

]).service("icswHostCheckCommandBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswHostCheckCommandBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "name", "command_line",
            ]

]).service("icswMonContactBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswMonContactBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "user", "snperdio", "hnperiod",
                "snrecovery", "sncritical", "snwarning", "snunknown",
                "sflapping", "splanned_downtime",
                "hnrecovery", "hndown", "hnunreachable",
                "hflapping", "hplanned_downtime", "mon_alias"
            ]
            @list_attributes = [
                "notifications"
            ]

]).service("icswMonContactgroupBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswMonContactgroupBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "name", "alias",
            ]
            @list_attributes = [
                "device_groups", "members", "service_templates", "service_esc_templates",
            ]

]).service("icswDeviceMonitoringBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswDeviceMonitoringBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "monitor_server", "nagvis_parent", "automap_root_nagvis",
                "mon_resolve_name", "monitor_checks", "flap_detection_enabled",
                "enable_perfdata", "mon_ext_host", "md_cache_mode", "mon_device_templ",
            ]

]).service("icswPartitionTableBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswPartitionTableBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "name", "description", "enabled", "nodeboot"
            ]

]).service("icswPartitionDiscBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswPartitionDiscBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "disc", "label_type", "priority",
            ]

]).service("icswPartitionBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswPartitionBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "partition_disc", "mountpoint", "partition_hex", "size",
                "mount_options", "pnum", "bootable", "fs_freq", "fs_passno",
                "partition_fs", "disk_by_info", "warn_threshold", "crit_threshold",
            ]

]).service("icswSysPartitionBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswSysPartitionBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "name", "options", "mountpoint",
            ]
]).service("icswKernelBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswKernelBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "name", "display_name", "kernel_version", "major", "minor",
                "patchlevel", "version", "release", "builds", "build_machine",
                "master_server", "master_role", "device",
                "build_lock", "config_name", "cpu_arch", "sub_cpu_arch",
                "target_dir", "comment", "enabled", "initrd_version",
                "initrd_built", "module_list", "target_module_list",
                "xen_host_kernel", "xen_guest_kernel", "bitcount",
                "stage1_lo_present", "stage1_cpio_present", "stage1_cramfs_present",
                "stage2_present",
            ]
]).service("icswImageBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswImageBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "name", "source", "version", "release", "builds",
                "build_machine", "device", "build_lock", 
                "size", "size_string", "sys_vendor", "sys_version", "sys_release",
                "bitcount", "architecture", "full_build", "enabled",
            ]

]).service("icswMonitoringHintBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswMonitoringHintBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "value_float", "value_int", "value_string", "value_blob",
                "lower_crit_float", "lower_warn_float", "upper_crit_float", "upper_warn_float",
                "lower_crit_int", "lower_warn_int", "upper_crit_int", "upper_warn_int",
                "lower_crit_float_source", "lower_warn_float_source", "upper_crit_float_source", "upper_warn_float_source",
                "lower_crit_int_source", "lower_warn_int_source", "upper_crit_int_source", "upper_warn_int_source",
                "info", "enabled", "check_created", "changed",
                "persistent", "is_active", "datasource",
            ]

]).service("icswMonHostClusterBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswMonHostClusterBackupDefinition extends icswBackupDefinition
        constructor: () ->
            super()
            @simple_attributes = [
                "name", "description", "main_device", "mon_service_templ",
                "warn_value", "error_value", "user_editable",
            ]
            @list_attributes = [
                "devices",
            ]
]).service("icswMonServiceClusterBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswMonServiceClusterBackupDefinition extends icswBackupDefinition
        constructor: () ->
            super()
            @simple_attributes = [
                "name", "description", "main_device", "mon_service_templ",
                "mon_check_command",
                "warn_value", "error_value", "user_editable",
            ]
            @list_attributes = [
                "devices",
            ]
]).service("icswMonHostDependencyTemplBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswMonHostDependencyTemplBackupDefinition extends icswBackupDefinition
        constructor: () ->
            super()
            @simple_attributes = [
                "name", "inherits_parent", "priority", 
                "efc_up", "efc_down", "efc_unreachable", "efc_pending",
                "nfc_up", "nfc_down", "nfc_unreachable", "nfc_pending",
                "dependency_period",
            ]
]).service("icswMonServiceDependencyTemplBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswMonServiceDependencyTemplBackupDefinition extends icswBackupDefinition
        constructor: () ->
            super()
            @simple_attributes = [
                "name", "inherits_parent", "priority", 
                "efc_ok", "efc_warn", "efc_unknown", "efc_critical", "efc_pending",
                "nfc_ok", "nfc_warn", "nfc_unknown", "nfc_critical", "nfc_pending",
                "dependency_period",
            ]
]).service("icswMonHostDependencyBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswMonHostDependencyBackupDefinition extends icswBackupDefinition
        constructor: () ->
            super()
            @simple_attributes = [
                "devices", "mon_host_dependency_templ", "mon_host_cluster",
            ]
            @list_attributes = [
                "dependent_devices",
            ]
            
]).service("icswMonServiceDependencyBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswMonServiceDependencyBackupDefinition extends icswBackupDefinition
        constructor: () ->
            super()
            @simple_attributes = [
                "devices",
                "mon_check_command", "dependent_mon_check_command",
                "mon_service_dependency_templ", "mon_service_cluster",
            ]
            @list_attributes = [
                "dependent_devices",
            ]
])
