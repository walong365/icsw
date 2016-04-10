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
            @valid_label_type_list = [
                {
                    label: "msdos"
                    info_string: "MSDOS"
                },
                {
                    label: "gpt"
                    info_string: "GPT",
                },
            ]
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
            @lut = _.keyBy(@list, "idx")
            @fs_lut = _.keyBy(@fs_list, "idx")
            @valid_lable_type_lut = _.keyBy(@valid_label_type_list, "label")
            @link()
        
        link: () =>
            # create helper fields
            for entry in @list
                @link_layout(entry)
            for entry in @fs_list
                entry.full_info = "#{entry.name}" + if entry.need_mountpoint then " (need mountpoint)" else ""

        link_layout: (layout) =>
            # TODO, Fixme, no longer set from serializer
            if not layout.act_partition_table?
                layout.act_partition_table = []
                layout.new_partition_table = []
            # create helper fields for a single layoutition
            layout.$$td_class = if layout.valid then "success" else "danger"
            if layout.new_partition_table.length or layout.act_partition_table.length
                layout.$$delete_ok = false
            else
                layout.$$delete_ok = true
            for disc in layout.partition_disc_set
                true
            new_set = _.orderBy(layout.sys_partition_set, ["mountpoint", "asc"])
            layout.sys_partition_set.length = 0
            for entry in new_set
                layout.sys_partition_set.push(entry)

        create_partition_table_layout: (layout) ->
            d = $q.defer()
            Restangular.all(ICSW_URLS.REST_PARTITION_TABLE_LIST.slice(1)).post(layout).then(
                (new_layout) =>
                    @list.push(new_layout)
                    @build_luts()
                    d.resolve("updated")
                (not_ok) =>
                    d.reject("not updated")
            )
            return d.promise

        delete_partition_table_layout: (layout) ->
            d = $q.defer()
            Restangular.restangularizeElement(null, layout, ICSW_URLS.REST_PARTITION_TABLE_DETAIL.slice(1).slice(0, -2))
            layout.remove().then(
                (ok) =>
                    # partition table deleted
                    _.remove(@list, (entry) -> return entry.idx == layout.idx)
                    @build_luts()
                    d.resolve("deleted")
                (not_ok) =>
                    d.reject("not deleted")
            )
            return d.promise

        update_partition_table_layout: (layout) ->
            d = $q.defer()
            Restangular.restangularizeElement(null, layout, ICSW_URLS.REST_PARTITION_TABLE_DETAIL.slice(1).slice(0, -2))
            layout.put().then(
                (ok) =>
                    @build_luts()
                    d.resolve("updated")
                (not_ok) =>
                    d.reject("not updated")
            )
            return d.promise

        create_partition_disc: (layout, disc) ->
            d = $q.defer()
            Restangular.all(ICSW_URLS.REST_PARTITION_DISC_LIST.slice(1)).post(disc).then(
                (new_disc) =>
                    layout.partition_disc_set.push(new_disc)
                    @build_luts()
                    d.resolve("updated")
                (not_ok) =>
                    d.reject("not updated")
            )
            return d.promise

        update_partition_disc: (layout, disc) ->
            d = $q.defer()
            Restangular.restangularizeElement(null, disc, ICSW_URLS.REST_PARTITION_DISC_DETAIL.slice(1).slice(0, -2))
            disc.put().then(
                (ok) =>
                    @build_luts()
                    d.resolve("updated")
                (not_ok) =>
                    d.reject("not updated")
            )
            return d.promise

        delete_partition_disc: (layout, disc) ->
            d = $q.defer()
            Restangular.restangularizeElement(null, disc, ICSW_URLS.REST_PARTITION_DISC_DETAIL.slice(1).slice(0, -2))
            disc.remove().then(
                (ok) =>
                    _.remove(layout.partition_disc_set, (entry) -> return entry.idx == disc.idx)
                    @build_luts()
                    d.resolve("updated")
                (not_ok) =>
                    d.reject("not updated")
            )
            return d.promise

        create_partition_part: (layout, disc, part) ->
            d = $q.defer()
            Restangular.all(ICSW_URLS.REST_PARTITION_LIST.slice(1)).post(part).then(
                (new_part) =>
                    disc.partition_set.push(new_part)
                    @build_luts()
                    d.resolve("updated")
                (not_ok) =>
                    d.reject("not updated")
            )
            return d.promise

        update_partition_part: (layout, disc, part) ->
            d = $q.defer()
            Restangular.restangularizeElement(null, part, ICSW_URLS.REST_PARTITION_DETAIL.slice(1).slice(0, -2))
            part.put().then(
                (ok) =>
                    @build_luts()
                    d.resolve("updated")
                (not_ok) =>
                    d.reject("not updated")
            )
            return d.promise

        delete_partition_part: (layout, disc, part) ->
            d = $q.defer()
            Restangular.restangularizeElement(null, part, ICSW_URLS.REST_PARTITION_DETAIL.slice(1).slice(0, -2))
            part.remove().then(
                (ok) =>
                    _.remove(disc.partition_set, (entry) -> return entry.idx == part.idx)
                    @build_luts()
                    d.resolve("updated")
                (not_ok) =>
                    d.reject("not updated")
            )
            return d.promise

        create_sys_partition: (layout, sys) ->
            d = $q.defer()
            Restangular.all(ICSW_URLS.REST_SYS_PARTITION_LIST.slice(1)).post(sys).then(
                (new_sys) =>
                    layout.sys_partition_set.push(new_sys)
                    @build_luts()
                    d.resolve("updated")
                (not_ok) =>
                    d.reject("not updated")
            )
            return d.promise

        update_sys_partition: (layout, sys) ->
            d = $q.defer()
            Restangular.restangularizeElement(null, sys, ICSW_URLS.REST_SYS_PARTITION_DETAIL.slice(1).slice(0, -2))
            sys.put().then(
                (ok) =>
                    @build_luts()
                    d.resolve("updated")
                (not_ok) =>
                    d.reject("not updated")
            )
            return d.promise

        delete_sys_partition: (layout, sys) ->
            d = $q.defer()
            Restangular.restangularizeElement(null, sys, ICSW_URLS.REST_SYS_PARTITION_DETAIL.slice(1).slice(0, -2))
            sys.remove().then(
                (ok) =>
                    _.remove(layout.sys_partition_set, (entry) -> return entry.idx == sys.idx)
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
    "$q", "$timeout", "ICSW_URLS", "icswToolsSimpleModalService",
    "icswPartitionTableTreeService", "blockUI", "icswComplexModalService", "toaster",
(
    $scope, $compile, $filter, $templateCache, Restangular,
    $q, $timeout, ICSW_URLS, icswToolsSimpleModalService,
    icswPartitionTableTreeService, blockUI, icswComplexModalService, toaster,
) ->
    $scope.struct = {
        # loading flag
        loading: false
        # partition tree
        partition_tree: undefined
        # edit partition layout
        edit_layouts: []
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
        )

    $scope.create_layout = ($event) ->
        names = (entry.name for entry in $scope.struct.partition_tree.list)
        _idx = -1
        while true
            _idx += 1
            new_name = if _idx then "new_part_#{_idx}" else "new_part"
            if not (new_name in names)
                break

        new_layout = {
            name: new_name
            sys_partition_set: []
            lvm_vg_set: []
            partition_disc_set: []
            lvm_lv_set: []
            enabled: true
            nodeboot: true
        }

        sub_scope = $scope.$new(false)
        sub_scope.edit_obj = new_layout
        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.partition.table.layout.form"))(sub_scope)
                title: "Create new Parition layout"
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.invalid
                        toaster.pop("warning", "form validation problem", "", 0)
                        d.reject("form not valid")
                    else
                        blockUI.start("saving partition data...")
                        $scope.struct.partition_tree.create_partition_table_layout(sub_scope.edit_obj).then(
                            (ok) ->
                                blockUI.stop()
                                d.resolve("saved")
                            (not_ok) ->
                                blockUI.stop()
                                d.reject("not saved")
                        )
                    return d.promise
                cancel_callback: (modal) ->
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                sub_scope.$destroy()
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
                $scope.edit_layout(data)
            )
        )
    # tab functions
    $scope.edit = ($event, layout) ->
        if !layout.$$tab_open
            layout.$$tab_active = true
            layout.$$tab_open = true
            $scope.struct.edit_layouts.push(layout)

    $scope.close = ($event, layout) ->
        if layout.$$tab_open
            $timeout(
                () ->
                    layout.$$tab_open = false
                    _.remove($scope.struct.edit_layouts, (entry) -> return !entry.$$tab_open)
                10
            )

    $scope.delete = ($event, layout) ->
        icswToolsSimpleModalService("Really delete partition table '#{layout.name}' ?").then(
            () ->
                blockUI.start("Deleting partition layout...")
                $scope.struct.partition_tree.delete_partition_table_layout(layout).then(
                    (ok) ->
                        # close tab if open
                        $scope.close_part(layout)
                        console.log "layout deleted"
                        blockUI.stop()
                    (not_ok) ->
                        console.log "layout not deleted"
                        blockUI.stop()
                )
                #obj.remove().then(
                #    $scope.close_part(obj)
                #    $scope.entries = (entry for entry in $scope.entries when entry.idx != obj.idx)
                #)
        )

    $scope.reload()
]).directive("icswConfigPartitionTableLayout",
[
    "$compile", "$templateCache", "Restangular", "ICSW_URLS", "icswSimpleAjaxCall", "$q",
(
    $compile, $templateCache, Restangular, ICSW_URLS, icswSimpleAjaxCall, $q
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.config.partition.table.layout")
        scope: 
            layout: "=icswPartitionLayout"
            part_tree: "=icswPartitionTree"
        replace: false
        controller: "icswConfigPartitionTableLayoutCtrl"
    }
]).controller("icswConfigPartitionTableLayoutCtrl", 
[
    "$scope", "$q", "ICSW_URLS", "icswSimpleAjaxCall", "icswComplexModalService", "$compile",
    "$templateCache", "toaster", "blockUI", "icswPartitionTableBackup", "icswPartitionDiscBackup",
    "icswPartitionBackup", "icswSysPartitionBackup", "icswToolsSimpleModalService",
(
    $scope, $q, ICSW_URLS, icswSimpleAjaxCall, icswComplexModalService, $compile,
    $templateCache, toaster, blockUI, icswPartitionTableBackup, icswPartitionDiscBackup,
    icswPartitionBackup, icswSysPartitionBackup, icswToolsSimpleModalService,
) ->
    $scope.struct = {
        # error list
        error_list: []
        # messages
        messages: []
        # message_str
        message_str: ""
    }
    $scope.add_message = (msg) ->
        if msg not in $scope.struct.messages
            $scope.struct.messages.push(msg)
            $scope.struct.message_str = $scope.struct.messages.join(", ")

    $scope.remove_message = (msg) ->
        _.remove($scope.struct.messages, (entry) -> return entry == msg)
        $scope.struct.message_str = $scope.struct.messages.join(", ")

    $scope.validate = () ->
        $scope.add_message("validating")
        icswSimpleAjaxCall(
            url: ICSW_URLS.SETUP_VALIDATE_PARTITION
            data: {
                "pt_pk": $scope.layout.idx
            }
            ignore_log_level: true
        ).then(
            (xml) ->
                _error_list = []
                $(xml).find("problem").each (idx, cur_p) =>
                    cur_p = $(cur_p)
                    _error_list.push(
                        {
                            msg: cur_p.text()
                            level: parseInt(cur_p.attr("level"))
                            global: if parseInt(cur_p.attr("g_problem")) then true else false
                        }
                    )
                $scope.remove_message("validating")
                _is_valid = if parseInt($(xml).find("problems").attr("valid")) then true else false
                $scope.layout.valid = _is_valid
                $scope.struct.error_list = _error_list
                $scope.part_tree.link_layout($scope.layout)
        )
    $scope.validate()

    # edit functions
    $scope.edit_layout = ($event) ->
        # create backup
        dbu = new icswPartitionTableBackup()
        dbu.create_backup($scope.layout)

        sub_scope = $scope.$new(false)
        sub_scope.edit_obj = $scope.layout
        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.partition.table.layout.form"))(sub_scope)
                title: "Base settings of partition #{$scope.layout.name}"
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.invalid
                        toaster.pop("warning", "form validation problem", "", 0)
                        d.reject("form not valid")
                    else
                        blockUI.start("saving partition data...")
                        $scope.part_tree.update_partition_table($scope.layout).then(
                            (ok) ->
                                blockUI.stop()
                                d.resolve("saved")
                            (not_ok) ->
                                blockUI.stop()
                                d.reject("not saved")
                        )
                    return d.promise
                cancel_callback: (modal) ->
                    dbu.restore_backup($scope.layout)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                sub_scope.$destroy()
                $scope.validate()
        )

    $scope.create_or_modify_disc = ($event, create, disc) ->
        if create
            disc = {
                label_type: "gpt"
                disc: "/dev/sd"
                partition_table: $scope.layout.idx
            }
        else
            dbu = new icswPartitionDiscBackup()
            dbu.create_backup(disc)

        sub_scope = $scope.$new(false)
        sub_scope.edit_obj = disc
        sub_scope.part_tree = $scope.part_tree

        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.partition.table.disc.form"))(sub_scope)
                title: if create then "Settings for new disc" else "Settingfs for disc #{disc.name}"
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.invalid
                        toaster.pop("warning", "form validation problem", "", 0)
                        d.reject("form not valid")
                    else
                        blockUI.start("saving disc data...")
                        if create
                            $scope.part_tree.create_partition_disc($scope.layout, sub_scope.edit_obj).then(
                                (ok) ->
                                    blockUI.stop()
                                    d.resolve("saved")
                                (not_ok) ->
                                    blockUI.stop()
                                    d.reject("not saved")
                            )
                        else
                            $scope.part_tree.update_partition_disc($scope.layout, sub_scope.edit_obj).then(
                                (ok) ->
                                    blockUI.stop()
                                    d.resolve("saved")
                                (not_ok) ->
                                    blockUI.stop()
                                    d.reject("not saved")
                            )
                    return d.promise
                cancel_callback: (modal) ->
                    if not create
                        dbu.restore_backup(disc)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                sub_scope.$destroy()
                $scope.validate()
        )

    $scope.delete_disc = ($event, disc) ->
        icswToolsSimpleModalService("Really delete Disc #{disc.name} ?").then(
            () =>
                blockUI.start("deleting disc")
                $scope.part_tree.delete_partition_disc($scope.layout, disc).then(
                    (ok) ->
                        blockUI.stop()
                        $scope.validate()
                    (not_ok) ->
                        blockUI.stop()
                )
        )

    $scope.create_or_modify_part = ($event, create, disc, part) ->
        if create
            part = {
                size: 128
                partition_disc: disc.idx
                partition_fs: (entry for entry in $scope.part_tree.fs_list when entry.name == "ext4")[0].idx
                fs_freq: 1
                fs_passno: 2
                pnum: 1
                warn_threshold: 85
                crit_threshold: 95
                mount_options: "defaults"
                partition_hex: "82"
            }
        else
            dbu = new icswPartitionBackup()
            dbu.create_backup(part)

        sub_scope = $scope.$new(false)
        sub_scope.layout = $scope.layout
        sub_scope.disc = disc
        sub_scope.edit_obj = part
        sub_scope.part_tree = $scope.part_tree

        # helper functions
        sub_scope.partition_need_mountpoint = () ->
            if sub_scope.edit_obj.partition_fs
                return $scope.part_tree.fs_lut[sub_scope.edit_obj.partition_fs].need_mountpoint
            else
                return true

        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.partition.table.part.form"))(sub_scope)
                title: if create then "Settings for new partition" else "Settingfs for partition ##{part.pnum}"
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.invalid
                        toaster.pop("warning", "form validation problem", "", 0)
                        d.reject("form not valid")
                    else
                        blockUI.start("saving part data...")
                        if create
                            $scope.part_tree.create_partition_part($scope.layout, disc, sub_scope.edit_obj).then(
                                (ok) ->
                                    blockUI.stop()
                                    d.resolve("saved")
                                (not_ok) ->
                                    blockUI.stop()
                                    d.reject("not saved")
                            )
                        else
                            $scope.part_tree.update_partition_part($scope.layout, disc, sub_scope.edit_obj).then(
                                (ok) ->
                                    blockUI.stop()
                                    d.resolve("saved")
                                (not_ok) ->
                                    blockUI.stop()
                                    d.reject("not saved")
                            )
                    return d.promise
                cancel_callback: (modal) ->
                    if not create
                        dbu.restore_backup(sys)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                sub_scope.$destroy()
                $scope.validate()
        )

    $scope.delete_part = ($event, disc, part) ->
        icswToolsSimpleModalService("Really delete Partition ##{part.pnum} ?").then(
            () =>
                blockUI.start("deleting part")
                $scope.part_tree.delete_partition_part($scope.layout, disc, part).then(
                    (ok) ->
                        blockUI.stop()
                        $scope.validate()
                    (not_ok) ->
                        blockUI.stop()
                )
        )

    $scope.create_or_modify_sys = ($event, create, sys) ->
        if create
            sys = {
                partition_table: $scope.layout.idx
                name: "new"
                mount_options: "defaults"
                mountpoint: "/"
            }
        else
            dbu = new icswSysPartitionBackup()
            dbu.create_backup(sys)

        sub_scope = $scope.$new(false)
        sub_scope.layout = $scope.layout
        sub_scope.edit_obj = sys
        sub_scope.part_tree = $scope.part_tree

        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.partition.table.sys.form"))(sub_scope)
                title: if create then "Settings for new Systempartition" else "Settingfs for Systempartition #{sys.name}"
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.invalid
                        toaster.pop("warning", "form validation problem", "", 0)
                        d.reject("form not valid")
                    else
                        blockUI.start("saving Syspart data...")
                        if create
                            $scope.part_tree.create_sys_partition($scope.layout, sub_scope.edit_obj).then(
                                (ok) ->
                                    blockUI.stop()
                                    d.resolve("saved")
                                (not_ok) ->
                                    blockUI.stop()
                                    d.reject("not saved")
                            )
                        else
                            $scope.part_tree.update_sys_partition($scope.layout, sub_scope.edit_obj).then(
                                (ok) ->
                                    blockUI.stop()
                                    d.resolve("saved")
                                (not_ok) ->
                                    blockUI.stop()
                                    d.reject("not saved")
                            )
                    return d.promise
                cancel_callback: (modal) ->
                    if not create
                        dbu.restore_backup(sys)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                sub_scope.$destroy()
                $scope.validate()
        )

    $scope.delete_sys = ($event, sys) ->
        icswToolsSimpleModalService("Really delete SysPartition #{sys.name} ?").then(
            () =>
                blockUI.start("deleting syspart")
                $scope.part_tree.delete_sys_partition($scope.layout, sys).then(
                    (ok) ->
                        blockUI.stop()
                        $scope.validate()
                    (not_ok) ->
                        blockUI.stop()
                )
        )

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
])
