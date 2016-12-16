# Copyright (C) 2016 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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

# variable related module

device_asset_module = angular.module(
    "icsw.device.asset",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "ngCsv"
    ]
).config(["icswRouteExtensionProvider", (icswRouteExtensionProvider) ->
    icswRouteExtensionProvider.add_route("main.devasset")
    icswRouteExtensionProvider.add_route("main.schedasset")
    icswRouteExtensionProvider.add_route("main.schedoverviewasset")
]).directive("icswDeviceAssetOverview",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.asset.overview")
        controller: "icswDeviceAssetCtrl"
        scope: true
    }
]).directive("icswDeviceAssetOverviewReduced",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.asset.overview.reduced")
        controller: "icswDeviceAssetCtrl"
        scope: true
    }
]).controller("icswDeviceAssetCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "$q", "$uibModal", "blockUI",
    "icswTools", "icswSimpleAjaxCall", "ICSW_URLS", "icswAssetHelperFunctions",
    "icswDeviceTreeService", "icswDeviceTreeHelperService", "$timeout",
    "icswDispatcherSettingTreeService", "Restangular", "icswAssetPackageTreeService", "icswWebSocketService"
(
    $scope, $compile, $filter, $templateCache, $q, $uibModal, blockUI,
    icswTools, icswSimpleAjaxCall, ICSW_URLS, icswAssetHelperFunctions,
    icswDeviceTreeService, icswDeviceTreeHelperService, $timeout,
    icswDispatcherSettingTreeService, Restangular, icswAssetPackageTreeService, icswWebSocketService
) ->
    # struct to hand over to VarCtrl
    $scope.struct = {
        # list of devices
        devices: []
        # device tree
        device_tree: undefined
        # data loaded
        data_loaded: false
        # dispatcher setting tree
        disp_setting_tree: undefined
        # package tree
        package_tree: undefined
        # num_selected
        num_selected: 0

        # AssetRun tab properties
        num_selected_ar: 0
        asset_runs: []
        show_changeset: false
        added_changeset: []
        removed_changeset: []

        asset_batch_lookup_cache: {}

        # Scheduled Runs tab properties
        schedule_items: []
        # reload timer
        reload_timer: undefined

        websocket: undefined

        package_list: []
    }

    $scope.struct.websocket = icswWebSocketService.register_ws("asset_batch")
    $scope.struct.websocket.onmessage = (data) ->
        asset_batch = JSON.parse(data.data)
        salt_asset_batch(asset_batch)

        if $scope.struct.asset_batch_lookup_cache[asset_batch.idx] == undefined
            $scope.struct.asset_batch_lookup_cache[asset_batch.idx] = asset_batch
            $timeout(
                () ->
                    if asset_batch.$$device.asset_batch_list == undefined
                        asset_batch.$$device.asset_batch_list = []
                    asset_batch.$$device.asset_batch_list.push(asset_batch)
                0
            )
        else
            old_obj = $scope.struct.asset_batch_lookup_cache[asset_batch.idx]
            if old_obj.run_status < asset_batch.run_status
                $timeout(
                    () ->
                        _.extend(old_obj, asset_batch)
                    0
                )

    reload_data = () ->
        idx_list = (idx for idx in Object.keys($scope.struct.asset_batch_lookup_cache) when $scope.struct.asset_batch_lookup_cache[idx].is_finished_processing == true)

        $q.all(
            [
                Restangular.all(ICSW_URLS.ASSET_GET_SCHEDULE_LIST.slice(1)).getList(
                    {
                        pks: angular.toJson((dev.idx for dev in $scope.struct.devices))
                    }
                )
                icswSimpleAjaxCall(
                    {
                        url: ICSW_URLS.ASSET_SIMPLE_ASSET_BATCH_LOADER
                        data:
                            device_pks: (dev.idx for dev in $scope.struct.devices)
                            excluded_assetbatch_pks: idx_list
                        dataType: "json"
                    }
                )
            ]
        ).then(
            (result) ->
                set_schedule_items(result[0])

                update_asset_batch_list(result[1])

                start_timer()
        )

    start_timer = () ->
        stop_timer()
        $scope.struct.reload_timer = $timeout(
            () ->
                reload_data()
            15000
        )

    stop_timer = () ->
        # check if present and stop timer
        if $scope.struct.reload_timer?
            $timeout.cancel($scope.struct.reload_timer)
            $scope.struct.reload_timer = undefined

    update_asset_batch_list = (asset_batch_list) ->
        for asset_batch in asset_batch_list
            salt_asset_batch(asset_batch)

            if $scope.struct.asset_batch_lookup_cache[asset_batch.idx] == undefined
                asset_batch.$$device.asset_batch_list.push(asset_batch)
                $scope.struct.asset_batch_lookup_cache[asset_batch.idx] = asset_batch
            else
                old_obj = $scope.struct.asset_batch_lookup_cache[asset_batch.idx]
                _.extend(old_obj, asset_batch)

    set_schedule_items = (sched_list) ->
        $scope.struct.schedule_items.length = 0

        for device in $scope.struct.devices
            device.schedule_items.length = 0

        for obj in sched_list
            $scope.struct.schedule_items.push(salt_schedule_item(obj))
            obj.$$device.schedule_items.push(obj)

    $scope.$on("$destroy", () ->
        if $scope.struct.websocket?
            $scope.struct.websocket.close()
            $scope.struct.websocket = undefined

        stop_timer()
    )

#    $scope.load_package_tree = () ->
#        blockUI.start("Loading Data ...")
#        $q.all(
#            [
#                icswAssetPackageTreeService.load($scope.$id)
#            ]
#        ).then(
#            (data) ->
#                $scope.struct.package_tree = data[0]
#                blockUI.stop()
#        )

    $scope.load_package_tree = () ->
        blockUI.start("Loading Data ...")
        icswSimpleAjaxCall(
            {
                url: ICSW_URLS.ASSET_ASSET_PACKAGE_LOADER
                data:
                    type: "AssetPackage"
                dataType: "json"
            }
        ).then((result) ->
            blockUI.stop()
            console.log(result)
            $scope.struct.package_list.length = 0
            for entry in result
                entry.$$package_type = icswAssetHelperFunctions.resolve("package_type", entry.package_type)
                $scope.struct.package_list.push(entry)
        )

    $scope.new_devsel = (devs) ->
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
                icswDispatcherSettingTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.device_tree = data[0]
                $scope.struct.disp_setting_tree = data[1]

                $scope.struct.devices.length = 0
                for dev in devs
                    # filter out metadevices
                    if not dev.is_meta_device
                        if not dev.asset_batch_list?
                            dev.asset_batch_list = []

                        if not dev.info_tabs?
                            dev.info_tabs = []
                        else
                            dev.info_tabs.length = 0

                        if not dev.schedule_items?
                            dev.schedule_items = []
                        else
                            dev.schedule_items.length = 0

                        dev.$$scan_device_button_disabled = false
                        dev.$$assetbatch_ids_selected_for_delete = []

                        $scope.struct.devices.push(dev)

                reload_data()
                start_timer()
                $scope.struct.data_loaded = true
        )

    # salt functions
    salt_asset_batch = (obj) ->
        obj.$$run_start_time = "N/A"
        obj.$$run_time = "N/A"
        obj.$$expanded = false
        obj.$$device = $scope.struct.device_tree.all_lut[obj.device]

        if obj.run_time > 0
            obj.$$run_time = obj.run_time + " seconds"

        if obj.run_start_time
            _moment = moment(obj.run_start_time)
            obj.$$run_start_time = _moment.format("YYYY-MM-DD HH:mm:ss")
            
        info_not_available_class = "alert-danger"
        info_not_available_text = "Not Available"
        info_available_class = "alert-success"
        info_available_text = "Available"

        info_list_names = [
            "installed_packages",
            "pending_updates",
            "installed_updates",
            "memory_modules",
            "cpus",
            "gpus",
            "network_devices",
            "partition_table",
            "displays",
        ]

        for info_list_name in info_list_names
            obj["$$" + info_list_name + "_availability_class"] = info_not_available_class
            obj["$$" + info_list_name + "_availability_text"] = info_not_available_text

            if obj[info_list_name + "_status"] > 1
                obj["$$" + info_list_name + "_availability_class"] = info_available_class
                obj["$$" + info_list_name + "_availability_text"] = info_available_text

    salt_schedule_item = (obj) ->
        obj.$$planned_time = moment(obj.planned_date).format("YYYY-MM-DD HH:mm:ss")
        obj.$$device = $scope.struct.device_tree.all_lut[obj.device]
        obj.$$full_name = obj.$$device.full_name
        obj.$$disp_setting = $scope.struct.disp_setting_tree.lut[obj.dispatch_setting]
        return obj

    $scope.filterSchedArrayForCsvExport = (filteredSchedItems) ->
        moreFilteredSchedItems = []
        for obj in filteredSchedItems
            sched_item = {}
            sched_item.dev_name = obj.dev_name
            sched_item.planned_time = obj.planned_time
            sched_item.ds_name = obj.ds_name
            moreFilteredSchedItems.push(sched_item)

        return moreFilteredSchedItems

    $scope.filterAssetRunArrayForCsvExport = (filteredARItems) ->
        moreFilteredARItems = []
        for obj in filteredARItems
            if obj.assets.length > 0
                for asset in obj.assets
                    asset_run = {}
                    asset_run.run_type = icswAssetHelperFunctions.resolve("run_type", obj.run_type)
                    asset_run.run_start_time = obj.run_start_time
                    asset_run.run_end_time = obj.run_end_time
                    if obj.hasOwnProperty("device_name")
                        asset_run.device_name = obj.device_name
                    asset_run.asset = asset
                    moreFilteredARItems.push(asset_run)
            else
                asset_run = {}
                asset_run.run_type = icswAssetHelperFunctions.resolve("run_type", obj.run_type)
                asset_run.run_start_time = obj.run_start_time
                asset_run.run_end_time = obj.run_end_time
                if obj.hasOwnProperty("device_name")
                    asset_run.device_name = obj.device_name
                moreFilteredARItems.push(asset_run)

        return moreFilteredARItems

    $scope.scan_device = (_device) ->
        _device.$$scan_device_button_disabled = true
        icswSimpleAjaxCall(
            {
                url: ICSW_URLS.ASSET_RUN_ASSETRUN_FOR_DEVICE_NOW
                data:
                    pk: _device.idx
                dataType: "json"
            }
        ).then(
            (ok) ->
                $timeout(
                    () ->
                        _device.$$scan_device_button_disabled = false
                        reload_data()
                    5000
                )
            (not_ok) ->
                $timeout(
                    () ->
                        _device.$$scan_device_button_disabled = false
                        reload_data()
                    5000
                )
        )

    $scope.close_tab = (to_be_closed_tab, _device) ->
        $timeout(
            () ->
                tabs_tmp = []

                for tab in _device.info_tabs
                    if tab != to_be_closed_tab
                        tabs_tmp.push(tab)
                _device.info_tabs.length = 0
                for tab in tabs_tmp
                    _device.info_tabs.push(tab)
            0
        )
]).filter('assetRunFilter'
[
    "$filter",
(
    $filter,
) ->
    return (input, predicate) ->
        strict = false
        return $filter('filter')(input, predicate, strict)
]).filter('packageFilter'
[
    "$filter",
(
    $filter,
) ->
    return (input, predicate) ->
        strict = false
        return $filter('filter')(input, predicate, strict)
]).directive("icswAssetScheduledRunsTable",
[
    "$q", "$templateCache",
(
    $q, $templateCache,
) ->
    return {
        scope: {
            schedule_items: "=icswScheduleItems"
        }
        restrict: "E"
        template: $templateCache.get("icsw.asset.scheduled.runs.table")
        controller: "icswScheduledRunsTableCtrl"
    }
]).controller("icswScheduledRunsTableCtrl",
[
    "$scope", "$q", "ICSW_URLS", "icswSimpleAjaxCall"
(
    $scope, $q, ICSW_URLS, icswSimpleAjaxCall
) ->
    $scope.downloadCsv = ->
        icswSimpleAjaxCall(
            {
                url: ICSW_URLS.ASSET_EXPORT_SCHEDULED_RUNS_TO_CSV
                dataType: 'json'
            }
        ).then(
            (result) ->
                    uri = 'data:text/csv;charset=utf-8,' + encodeURIComponent(result.csv)
                    downloadLink = document.createElement("a")
                    downloadLink.href = uri
                    downloadLink.download = "scheduled_runs.csv"

                    document.body.appendChild(downloadLink)
                    downloadLink.click()
                    document.body.removeChild(downloadLink)
            (not_ok) ->
                console.log not_ok
        )

]).directive("icswAssetKnownPackages",
[
    "$q", "$templateCache",
(
    $q, $templateCache,
) ->
    return {
        restrict: "E"
        template: $templateCache.get("icsw.asset.known.packages")
        scope: {
            package_list: "=icswAssetPackageList"
        }
        controller: "icswAssetKnownPackagesCtrl"
    }
]).controller("icswAssetKnownPackagesCtrl",
[
    "$scope", "ICSW_URLS", "icswSimpleAjaxCall", "blockUI"
(
    $scope, ICSW_URLS, icswSimpleAjaxCall, blockUI
) ->
    $scope.expand_package = ($event, obj) ->
        if obj.$$expanded == undefined
            obj.$$expanded = false
        obj.$$expanded = !obj.$$expanded

        if obj.$$expanded == true
            blockUI.start("Please wait ...")
            icswSimpleAjaxCall(
                {
                    url: ICSW_URLS.ASSET_ASSET_PACKAGE_LOADER
                    data:
                        type: "AssetPackageVersion"
                        asset_package_id: obj.idx
                    dataType: "json"
                }
            ).then((result) ->
                console.log(result)
                for version in result
                    version.$$release = "N/A"
                    if version.release
                        version.$$release = version.release

                obj.assetpackageversion_set = result
                blockUI.stop()
            )

    $scope.expand_version = ($event, obj) ->
        if obj.$$expanded == undefined
            obj.$$expanded = false
        obj.$$expanded = !obj.$$expanded

    $scope.format_time = (string) ->
         return moment(string).format("YYYY-MM-DD HH:mm:ss")

    $scope.get_history_timeline = (obj, from) ->
        moment_list = []
        for timestring in obj.install_history_list
            moment_obj = moment(timestring)
            moment_list.push(moment_obj)

        moment_list.sort(
            (a, b) ->
                return a - b
        )

        history_string = "N/A"

        if moment_list.length == 1
            history_string = moment_list[0].format("YYYY-MM-DD HH:mm:ss")

        else if moment_list.length > 1
            if !from
                history_string = moment_list[moment_list.length - 1].format("YYYY-MM-DD HH:mm:ss")
            else
                history_string = moment_list[0].format("YYYY-MM-DD HH:mm:ss")

        return history_string

]).directive("icswAssetRunDetails",
[
    "$q", "$templateCache", "$compile",
(
    $q, $templateCache, $compile,
) ->
    return {
        restrict: "E"
        scope: {
            asset_run: "=icswAssetRun"

        }
        link: (scope, element, attrs) ->
            element.children().remove()
            if scope.asset_run.run_type == 1
                _not_av_el = $compile($templateCache.get("icsw.asset.details.package"))(scope)
            else if scope.asset_run.run_type == 2
                _not_av_el = $compile($templateCache.get("icsw.asset.details.hardware"))(scope)
            else if scope.asset_run.run_type == 3
                _not_av_el = $compile($templateCache.get("icsw.asset.details.licenses"))(scope)
            else if scope.asset_run.run_type == 4
                _not_av_el = $compile($templateCache.get("icsw.asset.details.installed.updates"))(scope)
            else if scope.asset_run.run_type == 5
                _not_av_el = $compile($templateCache.get("icsw.asset.details.hw_entry"))(scope)
            else if scope.asset_run.run_type == 6
                _not_av_el = $compile($templateCache.get("icsw.asset.details.process"))(scope)
            else if scope.asset_run.run_type == 7
                _not_av_el = $compile($templateCache.get("icsw.asset.details.pending.updates"))(scope)
            else if scope.asset_run.run_type == 8
                _not_av_el = $compile($templateCache.get("icsw.asset.details.dmihandles"))(scope)
            else if scope.asset_run.run_type == 9
                _not_av_el = $compile($templateCache.get("icsw.asset.details.pcientries"))(scope)
            else if scope.asset_run.run_type == 10
                _not_av_el = $compile($templateCache.get("icsw.asset.details.hw_entry"))(scope)
            else
                _not_av_el = $compile($templateCache.get("icsw.asset.details.na"))(scope)
            element.append(_not_av_el)
    }
]).directive("icswAssetAssetBatchTable",
[
    "$q", "$templateCache",
(
    $q, $templateCache,
) ->
    return {
        restrict: "E"
        template: $templateCache.get("icsw.asset.asset.batch.table")
        scope: {
            asset_batch_list: "=icswAssetBatchList"
        }
        controller: "icswAssetAssetBatchTableCtrl"
    }
]).controller("icswAssetAssetBatchTableCtrl",
[
    "$scope", "$q", "ICSW_URLS", "blockUI", "Restangular", "icswAssetPackageTreeService", "icswSimpleAjaxCall",
    "icswTools", "icswAssetHelperFunctions"
(
    $scope, $q, ICSW_URLS, blockUI, Restangular, icswAssetPackageTreeService, icswSimpleAjaxCall, icswTools,
    icswAssetHelperFunctions
) ->
    for asset_batch in $scope.asset_batch_list
        asset_batch.$$selected = false

    $scope.select_assetbatch = (asset_batch) ->
        asset_batch.$$selected = !asset_batch.$$selected
        asset_batch.$$table_class_str = ""
        if asset_batch.$$selected == true
            asset_batch.$$table_class_str = "info"
            asset_batch.$$device.$$assetbatch_ids_selected_for_delete.push(asset_batch.idx)
        else
            _.pull(asset_batch.$$device.$$assetbatch_ids_selected_for_delete, asset_batch.idx)

    $scope.open_in_new_tab = (asset_batch) ->
        for tab in asset_batch.$$device.info_tabs
            if tab.asset_batch.idx == asset_batch.idx
                return

        blockUI.start("Please wait ...")

        $q.all(
            [
                Restangular.all(ICSW_URLS.ASSET_GET_ASSETBATCH_LIST.slice(1)).getList(
                    {
                        assetbatch_pks: angular.toJson([asset_batch.idx])
                    }
                )
            ]
        ).then(
            (result) ->
                tab = {}
                tab.asset_batch = result[0][0]
                tab.tab_heading_text = "Scan (ID:" + asset_batch.idx + ")"

                for memory_entry in tab.asset_batch.memory_modules
                    memory_entry.$$capacity = "N/A"
                    if memory_entry.capacity
                        memory_entry.$$capacity = memory_entry.capacity / (1024.0 * 1024.0)

                for display in tab.asset_batch.displays
                        display.$$manufacturer = "N/A"
                        if display.manufacturer
                                display.$$manufacturer = display.manufacturer
                        display.$$name = "N/A"
                        if display.name
                                display.$$name = display.name
                        display.$$xpixels = "N/A"
                        if display.xpixels
                                display.$$xpixels = display.xpixels
                        display.$$ypixels = "N/A"
                        if display.ypixels
                                display.$$ypixels = display.ypixels

                for install_info in tab.asset_batch.installed_packages
                    install_info.$$install_time = "N/A"
                    if install_info.timestamp > 1
                        install_info.$$install_time = moment.unix(install_info.timestamp).format("YYYY-MM-DD HH:mm:ss")

                    package_version = install_info.package_version
                    asset_package = package_version.asset_package

                    package_version.$$release = "N/A"
                    if package_version.release
                        package_version.$$release = package_version.release

                    package_version.$$version = "N/A"
                    if package_version.version
                        package_version.$$version = package_version.version

                    asset_package.$$package_type = icswAssetHelperFunctions.resolve("package_type", asset_package.package_type)

                    install_info.$$size = "N/A"

                    if asset_package.$$package_type == "Windows"
                        if install_info.size > 0
                            install_info.$$size = Number((install_info.size / 1024).toFixed(2)) + " MByte"

                    if asset_package.$$package_type == "Linux"
                        if install_info.size > 0
                            if install_info.size < (1024 * 1024)
                                install_info.$$size = Number((install_info.size / 1024).toFixed(2)) + " KByte"
                            else
                                install_info.$$size = Number((install_info.size / (1024 * 1024)).toFixed(2)) + " MByte"


                tab.asset_batch.hdds = []
                tab.asset_batch.logical_discs = []

                if tab.asset_batch.partition_table
                    for disc in tab.asset_batch.partition_table.partition_disc_set
                        o = {
                            "identifier": "N/A"
                            "serialnumber": "N/A"
                            "size": "N/A"
                            "size_sort_hint": 0
                            "partitions": []
                        }

                        if disc.disc
                            o["identifier"] = disc.disc

                        if disc.serial
                            o["serialnumber"] = disc.serial

                        if disc.size
                            o["size"] = icswTools.get_size_str(disc.size, 1024, "Byte")
                            o["size_sort_hint"] = disc["size"]

                        for partition in disc.partition_set
                            new_partition_o = {
                                "mountpoint": "N/A"
                                "size": "N/A"
                                "filesystem": partition.filesystem_name
                            }

                            if partition.mountpoint
                                new_partition_o["mountpoint"] = partition.mountpoint
                            if partition.size
                                new_partition_o["size"] = icswTools.get_size_str(partition.size, 1024, "Byte")

                            o["partitions"].push(new_partition_o)

                        tab.asset_batch.hdds.push(o)

                    for disc in tab.asset_batch.partition_table.logicaldisc_set
                        o = {
                            "name": disc.device_name
                            "size": "N/A"
                            "size_sort_hint": disc.size
                            "free": "N/A"
                            "free_sort_hint": disc.free
                            "filesystem_name": disc.filesystem_name
                            "fill_percentage": 100
                            "fill_percentage_sort_hint": 0
                            "fill_bar_style": {}
                            "mountpoint": disc.mountpoint
                        }

                        o["fill_bar_style"]["width"] = 100 + "%"
                        o["fill_bar_style"]["vertical-align"] = "middle"

                        if disc.size
                            o["size"] = icswTools.get_size_str(disc.size, 1024, "Byte")

                        if disc.free_space
                            o["free"] = icswTools.get_size_str(disc.free_space, 1024, "Byte")

                        if disc.size && disc.free_space
                            o["fill_percentage"] = (100 - (((disc.free_space / disc.size) * 100))).toFixed(2)
                            o["fill_percentage_sort_hint"] = disc.free_space / disc.size


                        tab.asset_batch.logical_discs.push(o)
                asset_batch.$$device.info_tabs.push(tab)
                blockUI.stop()
        )
]).directive("icswAssetBatchDetails",
[
    "$q", "$templateCache", "$compile",
(
    $q, $templateCache, $compile,
) ->
    return {
        restrict: "E"
        scope: {
            tab: "=icswTab"
        }
        link: (scope, element, attrs) ->
            element.children().remove()
            _not_av_el = $compile($templateCache.get("icsw.asset.details.all"))(scope)
            element.append(_not_av_el)
    }
]).directive("icswAssetDetailsPackageTable",
[
    "$q", "$templateCache",
(
    $q, $templateCache,
) ->
    return {
        restrict: "E"
        template: $templateCache.get("icsw.asset.details.package")
        scope: {
            tab: "=icswTab"
        }
    }
]).directive("icswAssetDetailsInstalledUpdatesTable",
[
    "$q", "$templateCache",
(
    $q, $templateCache,
) ->
    return {
        restrict: "E"
        template: $templateCache.get("icsw.asset.details.installed.updates")
        scope: {
            tab: "=icswTab"
        }
    }
]).directive("icswAssetDetailPendingUpdatesTable",
[
    "$q", "$templateCache",
(
    $q, $templateCache,
) ->
    return {
        restrict: "E"
        template: $templateCache.get("icsw.asset.details.pending.updates")
        scope: {
            tab: "=icswTab"
        }
    }
]).directive("icswAssetDetailsHardwareMemoryModulesTable",
[
    "$q", "$templateCache",
(
    $q, $templateCache,
) ->
    return {
        restrict: "E"
        template: $templateCache.get("icsw.asset.details.hw.memory.modules")
        scope: {
            tab: "=icswTab"
        }
    }
]).directive("icswAssetDetailsHardwareCpuTable",
[
    "$q", "$templateCache",
(
    $q, $templateCache,
) ->
    return {
        restrict: "E"
        template: $templateCache.get("icsw.asset.details.hw.cpu")
        scope: {
            tab: "=icswTab"
        }
    }
]).directive("icswAssetDetailsHardwareGpuTable",
[
    "$q", "$templateCache",
(
    $q, $templateCache,
) ->
    return {
        restrict: "E"
        template: $templateCache.get("icsw.asset.details.hw.gpu")
        scope: {
            tab: "=icswTab"
        }
    }
]).directive("icswAssetDetailsHardwareNicTable",
[
    "$q", "$templateCache",
(
    $q, $templateCache,
) ->
    return {
        restrict: "E"
        template: $templateCache.get("icsw.asset.details.hw.nic")
        scope: {
            tab: "=icswTab"
        }
    }
]).directive("icswAssetDetailsHardwareHddTable",
[
    "$q", "$templateCache",
(
    $q, $templateCache,
) ->
    return {
        restrict: "E"
        template: $templateCache.get("icsw.asset.details.hw.hdd")
        scope: {
            tab: "=icswTab"
        }
    }
]).directive("icswAssetDetailsHardwareDisplayTable",
[
    "$q", "$templateCache",
(
    $q, $templateCache,
) ->
    return {
        restrict: "E"
        template: $templateCache.get("icsw.asset.details.hw.display")
        scope: {
            tab: "=icswTab"
        }
    }
]).directive("icswAssetScanHistoryTab",
[
    "$q", "$templateCache",
(
    $q, $templateCache,
) ->
    return {
        scope: {
            device: "=device"
        }
        restrict: "E"
        template: $templateCache.get("icsw.asset.scan.history.tab")
        controller: "icswAssetScanHistoryTabCtrl"
    }
]).controller("icswAssetScanHistoryTabCtrl",
[
    "$scope", "icswSimpleAjaxCall", "ICSW_URLS", "$timeout", "icswToolsSimpleModalService", "blockUI"
(
    $scope, icswSimpleAjaxCall, ICSW_URLS, $timeout, icswToolsSimpleModalService, blockUI
) ->
    $scope.scan_device = () ->
        $scope.device.$$scan_device_button_disabled = true
        icswSimpleAjaxCall(
            {
                url: ICSW_URLS.ASSET_RUN_ASSETRUN_FOR_DEVICE_NOW
                data:
                    pk: $scope.device.idx
                dataType: "json"
            }
        ).then(
            (ok) ->
                $timeout(
                    () ->
                        $scope.device.$$scan_device_button_disabled = false
                    5000
                )
            (not_ok) ->
                $timeout(
                    () ->
                        $scope.device.$$scan_device_button_disabled = false
                    5000
                )
        )

    $scope.delete_selected = () ->
        icswToolsSimpleModalService("Delete selected items?").then(
            (_yes) ->
                blockUI.start("Please wait...")
                icswSimpleAjaxCall(
                    {
                        url: ICSW_URLS.ASSET_ASSET_BATCH_DELETER
                        data:
                            assetbatch_pks: $scope.device.$$assetbatch_ids_selected_for_delete
                        dataType: "json"
                    }
                ).then((result) ->
                    objs_selected_for_deletion = []
                    for idx in $scope.device.$$assetbatch_ids_selected_for_delete
                        for assetbatch in $scope.device.asset_batch_list
                            if assetbatch.idx == idx
                                objs_selected_for_deletion.push(assetbatch)

                    _.pullAllBy($scope.device.asset_batch_list, objs_selected_for_deletion, "idx")
                    $scope.device.$$assetbatch_ids_selected_for_delete.length = 0
                    blockUI.stop()
                )
            (_no) ->
                console.log("no")
        )
])
