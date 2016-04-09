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

partition_table_module = angular.module(
    "icsw.config.partition_table",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "ui.select", "restangular"
    ]
).directive("icswDevicePartitionEditOverview",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.partition.edit.overview")
        controller: "icswDevicePartitionEditOverviewCtrl"
    }
]).service("icswPartitionTableTree",
[
    "ICSW_URLS", "$q", "$rootScope", "Restangular",
(
    ICSW_URLS, $q, $rootScope, Restangular,
) ->
    class icswPartitionTableTree
        constructor: (part_list, fs_list) ->
            @list = []
            @fs_list = []
            @update(part_list, fs_list)

        update: (part_list, fs_list) =>
            @list.length = 0
            for entry in part_list
                @list.push(entry)
            @fs_list.length = 0
            for entry in fs_list
                @fs_list.push(entry)
            @build_luts()

        build_luts: () =>
            @lut = _.keyBy(@list, "key")
            @fs_lut = _.keyBy(@fs_list, "key")
            @link()
        
        link: () =>
            # create helper fields
            for entry in @list
                entry.$$td_class = if entry.valid then "success" else "danger"
                if entry.new_partition_table.length or entry.act_partition_table.length
                    entry.$$delete_ok = false
                else
                    entry.$$delete_ok = true

        delete_partition_table: (part) ->
            d = $q.defer()
            Restangular.restangularizeElement(null, part, ICSW_URLS.REST_PARTITION_TABLE_DETAIL.slice(1).slice(0, -2))
            part.remove().then(
                (ok) =>
                    # partition table deleted
                    _.remove(@list, (entry) -> return entry.idx == part.idx)
                    @build_luts()
                    d.resolve("deleted")
                (not_ok) =>
                    d.reject("not deleted")
            )
            return d.promise

]).service("icswPartitionTableTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall",
    "icswTools", "$rootScope", "ICSW_SIGNALS", "icswPartitionTableTree",
(
    $q, Restangular, ICSW_URLS, $window, icswCachingCall,
    icswTools, $rootScope, ICSW_SIGNALS, icswPartitionTableTree,
) ->
    rest_map = [
        [
            ICSW_URLS.REST_PARTITION_TABLE_LIST, {}
        ]
        [
            ICSW_URLS.REST_PARTITION_FS_LIST, {}
        ]
    ]
    _fetch_dict = {}
    _result = undefined
    # load called
    load_called = false

    load_data = (client) ->
        load_called = true
        _wait_list = (icswCachingCall.fetch(client, _entry[0], _entry[1], []) for _entry in rest_map)
        _defer = $q.defer()
        $q.all(_wait_list).then(
            (data) ->
                console.log "*** partition tree loaded ***"
                _result = new icswPartitionTableTree(data[0], data[1])
                _defer.resolve(_result)
                for client of _fetch_dict
                    # resolve clients
                    _fetch_dict[client].resolve(_result)
                # $rootScope.$emit(ICSW_SIGNALS("ICSW_DEVICE_TREE_LOADED"), _result)
                # reset fetch_dict
                _fetch_dict = {}
        )
        return _defer

    fetch_data = (client) ->
        if client not of _fetch_dict
            # register client
            _defer = $q.defer()
            _fetch_dict[client] = _defer
        if _result
            # resolve immediately
            _fetch_dict[client].resolve(_result)
        return _fetch_dict[client]

    return {
        "load": (client) ->
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise
    }
]).controller("icswDevicePartitionEditOverviewCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular",
    "restDataSource", "$q", "$timeout", "ICSW_URLS", "icswToolsSimpleModalService",
    "icswPartitionTableTreeService", "blockUI",
(
    $scope, $compile, $filter, $templateCache, Restangular,
    restDataSource, $q, $timeout, ICSW_URLS, icswToolsSimpleModalService,
    icswPartitionTableTreeService, blockUI,
) ->
    $scope.entries = []
    $scope.edit_pts = []
    $scope.struct = {
        # loading flag
        loading: false
        # partition tree
        partition_tree: undefined
        # edit partitions
        edit_parts: []
    }
    $scope.reload = () ->
        $scope.struct.loading = true
        $q.all(
            [
                icswPartitionTableTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.loading = false
                $scope.struct.partition_tree = data[0]
                console.log data[0]
        )
    $scope.xreload = (cb_func) ->
        wait_list = [
            restDataSource.reload([ICSW_URLS.REST_PARTITION_TABLE_LIST, {}]),
            restDataSource.reload([ICSW_URLS.REST_PARTITION_FS_LIST, {}]),
        ]
        $q.all(wait_list).then((data) ->
            $scope.entries = data[0]
            $scope.partition_fs = data[1]
            if cb_func?
                cb_func()
        )
    $scope.create = () ->
        names = (entry.name for entry in $scope.entries)
        _idx = -1
        while true
            _idx += 1
            new_name = if _idx then "new_part_#{_idx}" else "new_part"
            if not (new_name in names)
                break
        Restangular.all(ICSW_URLS.REST_PARTITION_TABLE_LIST.slice(1)).post(
            {
                "name" : new_name
                "sys_partition_set" : []
                "lvm_vg_set" : []
                "partition_disc_set" : []
                "lvm_lv_set" : []
            }
        ).then((data) ->
            $scope.reload(() ->
                $scope.edit_part(data)
            )
        )
    # tab functions
    $scope.edit = ($event, part) ->
        if !part.$$tab_open
            part.$$tab_active = true
            part.$$tab_open = true
            $scope.struct.edit_parts.push(part)

    $scope.close = ($event, part) ->
        if part.$$tab_open
            $timeout(
                () ->
                    part.$$tab_open = false
                    _.remove($scope.struct.edit_parts, (entry) -> return !entry.$$tab_open)
                10
            )

    $scope.delete = ($event, part) ->
        icswToolsSimpleModalService("Really delete partition table '#{part.name}' ?").then(
            () ->
                blockUI.start("Deleting partition...")
                $scope.struct.partition_tree.delete_partition_table(part).then(
                    (ok) ->
                        # close tab if open
                        $scope.close_part(part)
                        console.log "part deleted"
                        blockUI.stop()
                    (not_ok) ->
                        console.log "not deleted"
                        blockUI.stop()
                )
                #obj.remove().then(
                #    $scope.close_part(obj)
                #    $scope.entries = (entry for entry in $scope.entries when entry.idx != obj.idx)
                #)
        )

    $scope.reload()
]).directive("icswConfigDiskLayout",
[
    "$compile", "$templateCache", "Restangular", "ICSW_URLS", "icswSimpleAjaxCall", "$q",
(
    $compile, $templateCache, Restangular, ICSW_URLS, icswSimpleAjaxCall, $q
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.disk.layout")
        scope  : true
        replace : false
        link : (scope, element, attrs) ->
            scope.part = scope.$eval(attrs["partTable"])
            scope.partition_fs = scope.$eval(attrs["partitionFs"])
            scope.edit_obj = scope.part
            scope.$on("icsw.part_changed", (args) ->
                if not scope.create_mode
                    scope.validate()
            )
            scope.valid_label_types = [
                {
                    label: "msdos"
                    info_string: "MSDOS"
                },
                {
                    label: "gpt"
                    info_string: "GPT",
                },
            ]
            scope.get_partition_fs = () ->
                for entry in scope.partition_fs
                    entry.full_info = "#{entry.name}" + if entry.need_mountpoint then " (need mountpoint)" else "" 
                return scope.partition_fs
            scope.partition_need_mountpoint = (part) ->
                if part.partition_fs
                    return (entry.need_mountpoint for entry in scope.partition_fs when entry.idx == part.partition_fs)[0]
                else
                    return true
            scope.validate = () ->
                if !scope.part.idx?
                    return
                icswSimpleAjaxCall(
                    url : ICSW_URLS.SETUP_VALIDATE_PARTITION
                    data : {
                        "pt_pk" : scope.part.idx
                    }
                    ignore_log_level: true
                ).then(
                    (xml) ->
                        error_list = []
                        $(xml).find("problem").each (idx, cur_p) =>
                            cur_p = $(cur_p)
                            error_list.push(
                                {
                                    msg: cur_p.text()
                                    level: parseInt(cur_p.attr("level"))
                                    global: if parseInt(cur_p.attr("g_problem")) then true else false
                                }
                            )
                        is_valid = if parseInt($(xml).find("problems").attr("valid")) then true else false
                        scope.edit_obj.valid = is_valid
                        scope.error_list = error_list
                )
            scope.error_list = []
            # watch edit_obj and validate if changed
            scope.$watch("edit_obj", () ->
                if not scope.create_mode
                    scope.validate()
            )
            scope.layout_edit = new angular_edit_mixin(scope, $templateCache, $compile, Restangular, $q)
            scope.layout_edit.change_signal = "icsw.part_changed"
            scope.layout_edit.create_template = "partition.disc.form"
            scope.layout_edit.create_rest_url = Restangular.all(ICSW_URLS.REST_PARTITION_DISC_LIST.slice(1))
            scope.layout_edit.create_list = scope.part.partition_disc_set
            scope.layout_edit.modify_data_after_post = (new_disc) ->
                new_disc.partition_set = []
                new_disc.sys_partition_set = []
            scope.layout_edit.new_object = (scope) ->
                return {
                    "partition_table"   : scope.edit_obj.idx
                    "disc"              : "/dev/sd"
                    "label_type"        : "gpt"
                }
            scope.sys_edit = new angular_edit_mixin(scope, $templateCache, $compile, Restangular, $q)
            scope.sys_edit.change_signal = "icsw.part_changed"
            scope.sys_edit.create_template = "partition.sys.form"
            scope.sys_edit.create_rest_url = Restangular.all(ICSW_URLS.REST_SYS_PARTITION_LIST.slice(1))
            scope.sys_edit.create_list = scope.part.sys_partition_set
            scope.sys_edit.new_object = (scope) ->
                return {
                    "partition_table" : scope.edit_obj.idx
                    "name"            : "new"
                    "mount_options"   : "defaults"
                    "mountpoint"      : "/"
                }
            scope.modify = () ->
                scope.part.put()
    }
]).directive("icswConfigPartitionTable",
[
    "$compile", "$templateCache",
(
    $compile, $templateCache
) ->
    return {
        restrict : "EA"
        scope : false
        template : $templateCache.get("partition.table.form")
        link : (scope, element, attrs) ->
             scope.edit_obj = scope.data
    }
]).directive("icswConfigPartitionTableDisc",
[
    "$compile", "$templateCache", "$q", "Restangular", "ICSW_URLS",
(
    $compile, $templateCache, $q, Restangular, ICSW_URLS
) ->
    return {
        restrict : "EA"
        #replace : true
        scope : true
        template : $templateCache.get("icsw.config.partition.table.disc")
        link : (scope, element, attrs) ->
            if scope.disc.partition_set.length
                # dirty hack but working
                element.after($("<tr>").append($templateCache.get("icsw.config.partition.table.header")))
            scope.partition_fs = scope.$eval(attrs["partitionFs"])
            scope.disc_edit = new angular_edit_mixin(scope, $templateCache, $compile, Restangular, $q)
            scope.disc_edit.change_signal = "icsw.part_changed"
            scope.disc_edit.create_template = "partition.form"
            scope.disc_edit.edit_template = "partition.disc.form"
            scope.disc_edit.modify_rest_url = ICSW_URLS.REST_PARTITION_DISC_DETAIL.slice(1).slice(0, -2)
            scope.disc_edit.create_rest_url = Restangular.all(ICSW_URLS.REST_PARTITION_LIST.slice(1))
            scope.disc_edit.create_list = scope.disc.partition_set
            scope.disc_edit.delete_list = scope.edit_obj.partition_disc_set
            scope.disc_edit.delete_confirm_str = (obj) -> "Really delete disc '#{obj.disc}' ?"
            scope.disc_edit.new_object = (scope) ->
                return {
                    "size" : 128
                    "partition_disc" : scope.disc.idx
                    "partition_fs" : (entry.idx for entry in scope.partition_fs when entry.name == "btrfs")[0]
                    "fs_freq" : 1
                    "fs_passno" : 2
                    "pnum" : 1
                    "warn_threshold" : 85
                    "crit_threshold" : 95
                    "mount_options" : "defaults"
                    "partition_hex" : "82"
                }
    }
]).directive("icswConfigPartitionTablePartition",
[
    "$compile", "$templateCache", "$q", "Restangular", "ICSW_URLS",
(
    $compile, $templateCache, $q, Restangular, ICSW_URLS
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.partition.table.partition")
        link : (scope, element, attrs) ->
            scope.part_edit = new angular_edit_mixin(scope, $templateCache, $compile, Restangular, $q)
            scope.part_edit.change_signal = "icsw.part_changed"
            scope.part_edit.edit_template = "partition.form"
            scope.part_edit.modify_rest_url = ICSW_URLS.REST_PARTITION_DETAIL.slice(1).slice(0, -2)
            scope.part_edit.delete_list = scope.disc.partition_set
            scope.part_edit.delete_confirm_str = (obj) -> "Really delete partition '#{obj.pnum}' ?"
    }
]).directive("icswConfigPartitionTableSystemPartition",
[
    "$compile", "$templateCache", "$q", "Restangular", "ICSW_URLS",
(
    $compile, $templateCache, $q, Restangular, ICSW_URLS
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.partition.table.system.partition")
        link : (scope, element, attrs) ->
            scope.sys_edit = new angular_edit_mixin(scope, $templateCache, $compile, Restangular, $q)
            scope.sys_edit.change_signal = "icsw.part_changed"
            scope.sys_edit.edit_template = "partition.sys.form"
            scope.sys_edit.modify_rest_url = ICSW_URLS.REST_SYS_PARTITION_DETAIL.slice(1).slice(0, -2)
            scope.sys_edit.delete_list = scope.edit_obj.sys_partition_set
            scope.sys_edit.delete_confirm_str = (obj) -> "Really delete sys partition '#{obj.name}' ?"
    }
])
