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
            obj._ICSW_backup = _bu
        restore_backup: (obj) =>
            if obj._ICSW_backup?
                _bu = obj._ICSW_backup
                @pre_restore(obj, _bu)
                for _entry in @simple_attributes
                    obj[_entry] = _bu[_entry]
                for _entry in @list_attributes
                    obj[_entry] = _.cloneDeep(_bu[_entry])
                @post_restore(obj, _bu)
                delete obj._ICSW_backup
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

]).service("icswDeviceGroupBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswDeviceGroupBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = ["name", "comment", "domain_tree_node", "enabled"]

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

]).service("icswNetworkBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswNetworkBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "identifier", "nework", "netmask", "gateway", "broadcast", "penalty", "force_unique_ips"
            ]

])
