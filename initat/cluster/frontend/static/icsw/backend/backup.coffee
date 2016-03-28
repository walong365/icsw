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
).service("icswBackupDefinition", [() ->

    class backup_def
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
            obj.$$_ICSW_backup = _bu

        restore_backup: (obj) =>
            if obj.$$_ICSW_backup?
                _bu = obj.$$_ICSW_backup
                @pre_restore(obj, _bu)
                for _entry in @simple_attributes
                    obj[_entry] = _bu[_entry]
                for _entry in @list_attributes
                    obj[_entry] = _.cloneDeep(_bu[_entry])
                @post_restore(obj, _bu)
                delete obj.$$_ICSW_backup

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

])
