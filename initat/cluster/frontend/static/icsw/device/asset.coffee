# Copyright (C) 2016 init.at
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

# variable related module

device_asset_module = angular.module(
    "icsw.device.asset",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "ngCsv"
    ]
).config(["$stateProvider", ($stateProvider) ->
    $stateProvider.state(
        "main.devasset", {
            url: "/asset"
            templateUrl: 'icsw/device/asset/overview'
            icswData:
                pageTitle: "Device Assets"
                menuEntry:
                    menukey: "dev"
                    icon: "fa-code"
                    ordering: 30
        }
    )
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
]).service("icswAssetPackageTree",
[
    "$q", "Restangular", "ICSW_URLS", "icswAssetHelperFunctions", "icswTools",
(
    $q, Restangular, ICSW_URLS, icswAssetHelperFunctions, icswTools,
) ->
    class icswAssetPackageTree
        constructor: (list) ->
            @list = []
            @version_list = []
            @update(list)

        update: (list) =>
            @list.length = 0
            @version_list.length = 0
            for entry in list
                @list.push(entry)
                for vers in entry.assetpackageversion_set
                    @version_list.push(vers)
            @build_luts()

        build_luts: () =>
            @lut = _.keyBy(@list, "idx")
            @version_lut = _.keyBy(@version_list, "idx")
            @link()

        link: () =>
            # DT_FORM = "dd, D. MMM YYYY HH:mm:ss"
            # _cf = ["year", "month", "week", "day", "hour", "minute", "second"]
            # create fields for schedule_setting form handling
            for entry in @list
                entry.$$num_versions = entry.assetpackageversion_set.length
                entry.$$package_type = icswAssetHelperFunctions.resolve("package_type", entry.package_type)
                entry.$$expanded = false
                entry.$$created = moment(entry.created).format("YYYY-MM-DD HH:mm:ss")
                for vers in entry.assetpackageversion_set
                    vers.$$package = entry
                    vers.$$created = moment(vers.created).format("YYYY-MM-DD HH:mm:ss")
                    vers.$$size = icswTools.get_size_str(vers.size, 1024, "Byte")


]).service("icswAssetPackageTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall", "icswTools",
    "icswAssetPackageTree", "$rootScope", "ICSW_SIGNALS",
(
    $q, Restangular, ICSW_URLS, $window, icswCachingCall, icswTools,
    icswAssetPackageTree, $rootScope, ICSW_SIGNALS,
) ->
    rest_map = [
        [
            # asset packages
            ICSW_URLS.ASSET_GET_ALL_ASSET_PACKAGES
            {}
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
                if _result?
                    _result.update(data[0])
                else
                    console.log "*** AssetPackageTree loaded ***"
                    _result = new icswAssetPackageTree(data[0])
                _defer.resolve(_result)
                for client of _fetch_dict
                    # resolve clients
                    _fetch_dict[client].resolve(_result)
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
        load: (client) ->
            # loads from server
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise

        reload: (client) ->
            return load_data(client).promise
    }
]).service("icswAssetHelperFunctions",
[
    "$q",
(
    $q,
) ->
    info_dict = {
        asset_type: [
            [1, "Package", ""]
            [2, "Hardware", ""]
            [3, "License", ""]
            [4, "Update", ""]
            [5, "Software version", ""]
            [6, "Process", ""]
            [7, "Pending update", ""]
        ]
        package_type: [
            [1, "Windows", ""]
            [2, "Linux", ""]
        ]
        run_status: [
            [1, "Planned", ""]
            [2, "Running", "success"]
            [3, "Ended", ""]
        ]
        run_result: [
            [1, "Unknown", "warning"]
            [2, "Success", "success"]
            [3, "Success", "success"]
            [4, "Failed", "danger"]
            [5, "Canceled", "warning"]
        ]
        schedule_source: [
            [1, "SNMP", ""]
            [2, "ASU", ""]
            [3, "IPMI", ""]
            [4, "Package", ""]
            [5, "Hardware", ""]
            [6, "License", ""]
            [7, "Update", ""]
            [8, "Software Version", ""]
            [9, "Process", ""]
            [10, "Pending update", ""]
        ]
    }

    # create forward and backward resolves

    res_dict = {}
    for name, _list of info_dict
        res_dict[name] = {}
        for [_idx, _str, _class] in _list
            # forward resolve
            res_dict[name][_idx] = [_str, _class]
            # backward resolve
            res_dict[name][_str] = [_idx, _class]
            res_dict[name][_.lowerCase(_str)] = [_idx, _class]

    _resolve = (name, key, idx) ->
        if name of res_dict
            if key of res_dict[name]
                return res_dict[name][key][idx]
            else
                console.error "unknown key #{key} for name #{name} in resolve"
                return "???"
        else
            console.error "unknown name #{name} in resolve"
            return "????"

    return {
        resolve: (name, key) ->
            return _resolve(name, key, 0)

        get_class: (name, key) ->
            return _resolve(name, key, 1)
    }
]).controller("icswDeviceAssetCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "$q", "$uibModal", "blockUI",
    "icswTools", "icswSimpleAjaxCall", "ICSW_URLS", "icswAssetHelperFunctions",
    "icswDeviceTreeService", "icswDeviceTreeHelperService", "$timeout",
    "icswDispatcherSettingTreeService", "Restangular", "icswAssetPackageTreeService",
(
    $scope, $compile, $filter, $templateCache, $q, $uibModal, blockUI,
    icswTools, icswSimpleAjaxCall, ICSW_URLS, icswAssetHelperFunctions,
    icswDeviceTreeService, icswDeviceTreeHelperService, $timeout,
    icswDispatcherSettingTreeService, Restangular, icswAssetPackageTreeService,
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

        # Scheduled Runs tab properties
        schedule_items: []
        # reload timer
        reload_timer: undefined
        # reload flag
        reloading: false
    }

    reload_data = () ->
        $scope.struct.reloading = true
        $q.all(
            [
                Restangular.all(ICSW_URLS.ASSET_GET_SCHEDULE_LIST.slice(1)).getList(
                    {
                        pks: angular.toJson((dev.idx for dev in $scope.struct.devices))
                    }
                )
                Restangular.all(ICSW_URLS.ASSET_GET_ASSETRUNS_FOR_DEVICES.slice(1)).getList(
                    {
                        pks: angular.toJson((dev.idx for dev in $scope.struct.devices))
                    }
                )
                # todo, make faster
                # icswAssetPackageTreeService.reload($scope.$id)
            ]
        ).then(
            (result) ->
                set_schedule_items(result[0])
                set_asset_runs(result[1])
                start_timer()
                $scope.struct.reloading = false
        )

    start_timer = () ->
        stop_timer()
        $scope.struct.reload_timer = $timeout(
            () ->
                reload_data()
            10000
        )

    stop_timer = () ->
        # check if present and stop timer
        if $scope.struct.reload_timer?
            $timeout.cancel($scope.struct.reload_timer)
            $scope.struct.reload_timer = undefined

    set_schedule_items = (sched_list) ->
        $scope.struct.schedule_items.length = 0
        for obj in sched_list
            $scope.struct.schedule_items.push(salt_schedule_item(obj))

    set_asset_runs = (run_list) ->
        for dev in $scope.struct.devices
            # reset assetrun_set list
            dev.assetrun_set.length = 0
        _prev_lut = _.keyBy($scope.struct.asset_runs, "idx")
        $scope.struct.asset_runs.length = 0
        for obj in run_list
            _salted = salt_asset_run(obj)
            if _salted.idx of _prev_lut
                _prev = _prev_lut[_salted.idx]
                # copy values from previous run
                _salted.$$assets_loaded = _prev.$$assets_loaded
                _salted.$$expanded = _prev.$$expanded
                if _salted.$$assets_loaded
                    _salted.$$assets = _prev.$$assets
            $scope.struct.asset_runs.push(_salted)
            _dev = $scope.struct.device_tree.all_lut[_salted.device]
            _dev.assetrun_set.push(_salted)

    $scope.$on("$destroy", () ->
        stop_timer()
    )

    $scope.new_devsel = (devs) ->
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
                icswDispatcherSettingTreeService.load($scope.$id)
                icswAssetPackageTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.device_tree = data[0]
                $scope.struct.disp_setting_tree = data[1]
                $scope.struct.package_tree = data[2]
                $scope.struct.devices.length = 0
                for dev in devs
                    # filter out metadevices
                    if not dev.is_meta_device
                        if not dev.assetrun_set?
                            dev.assetrun_set = []
                        $scope.struct.devices.push(dev)

                $q.all(
                    [
                        Restangular.all(ICSW_URLS.ASSET_GET_SCHEDULE_LIST.slice(1)).getList(
                            {
                                pks: angular.toJson((dev.idx for dev in $scope.struct.devices))
                            }
                        )
                        Restangular.all(ICSW_URLS.ASSET_GET_ASSETRUNS_FOR_DEVICES.slice(1)).getList(
                            {
                                pks: angular.toJson((dev.idx for dev in $scope.struct.devices))
                            }
                        )

                    ]
                ).then(
                    (result) ->
                        # console.log "r", result
                        # schedule list
                        set_schedule_items(result[0])
                        # assetrun list
                        set_asset_runs(result[1])
                        $scope.struct.data_loaded = true
                        start_timer()

                )

        )

    # salt functions
    salt_schedule_item = (obj) ->
        obj.$$planned_time = moment(obj.planned_date).format("YYYY-MM-DD HH:mm:ss")
        obj.$$device = $scope.struct.device_tree.all_lut[obj.device]
        obj.$$full_name = obj.$$device.full_name
        obj.$$disp_setting = $scope.struct.disp_setting_tree.lut[obj.dispatch_setting]
        return obj

    salt_asset_run = (obj) ->
        obj.$$device = $scope.struct.device_tree.all_lut[obj.device]
        obj.$$full_name = obj.$$device.full_name
        obj.$$run_type = icswAssetHelperFunctions.resolve("asset_type", obj.run_type)
        obj.$$run_status = icswAssetHelperFunctions.resolve("run_status", obj.run_status)
        obj.$$run_status_class = icswAssetHelperFunctions.get_class("run_status", obj.run_status)
        obj.$$run_result = icswAssetHelperFunctions.resolve("run_result", obj.run_result)
        obj.$$run_result_class = icswAssetHelperFunctions.get_class("run_result", obj.run_result)
        obj.$$error_class = if obj.error_string then "error" else ""
        obj.$$assets_loaded = false
        obj.$$expanded = false
        # link assets
        if obj.run_type == 1
            # package
            obj.$$num_results = obj.num_packages
        else if obj.run_type == 2
            # hardware
            obj.$$num_results = obj.num_hardware
        else if obj.run_type == 6
            # processes
            obj.$$num_results = obj.num_processes
        else if obj.run_type == 4
            # update
            obj.$$num_results = obj.num_updates
        else if obj.run_type == 7
            # pending update
            obj.$$num_results = obj.num_pending_updates
        else if obj.run_type == 3
            # pending update
            obj.$$num_results = obj.num_licenses
        else
            obj.$$num_results = 0
        if obj.run_start_time
            _moment = moment(obj.run_start_time)
            obj.$$run_start_day = _moment.format("YYYY-MM-DD")
            obj.$$run_start_hour = _moment.format("HH:mm:ss")
        else
            obj.$$run_start_day = "N/A"
            obj.$$run_start_hour = "N/A"

        if obj.run_end_time
            _moment = moment(obj.run_end_time)
            obj.$$run_end_day = _moment.format("YYYY-MM-DD")
            obj.$$run_end_hour = _moment.format("HH:mm:ss")
        else
            obj.$$run_end_day = "N/A"
            obj.$$run_end_hour = "N/A"

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

    $scope.filterPackageArrayForCsvExport = (filteredPackageItems) ->
        moreFilteredPackageItems = []
        for obj in filteredPackageItems

            if obj.versions.length > 0
                for version in obj.versions
                    _pack = {}
                    _pack.name = obj.name
                    _pack.package_type = icswAssetHelperFunctions.resolve("package_type", obj.package_type)
                    _pack.version = version[1]
                    _pack.release = version[2]
                    _pack.size = version[3]
                    moreFilteredPackageItems.push(_pack)
            else
                _pack = {}
                _pack.name = obj.name
                _pack.package_type = icswAssetHelperFunctions.resolve("package_type", obj.package_type)
                moreFilteredPackageItems.push(_pack)

        return moreFilteredPackageItems

    $scope.assetchangesetar = ($event) ->
        ar1 = undefined
        ar2 = undefined

        for ar in $scope.struct.asset_runs
            if ar.$$selected && ar1 == undefined
                ar1 = ar
            else if ar.$$selected && ar2 == undefined
                ar2 = ar
                break

        console.log "ar1: ", ar1
        console.log "ar2: ", ar2

        if ar1 != undefined && ar2 != undefined
            icswSimpleAjaxCall({
                url: ICSW_URLS.ASSET_GET_ASSETRUN_DIFFS
                data:
                    pk1: ar1.idx
                    pk2: ar2.idx
                dataType: 'json'
            }
            ).then(
                (result) ->
                    $scope.struct.show_changeset = true
                    $scope.struct.added_changeset = result.added
                    $scope.struct.removed_changeset = result.removed
                (not_ok) ->
                    console.log not_ok
            )

        $scope.struct.num_selected_ar = (_run for _run in $scope.struct.asset_runs when _run.$$selected).length
        if $scope.struct.num_selected_ar > 2
            for _run in $scope.struct.asset_runs
                if _run.run_type == _type and _run.$$selected and _run.run_index != assetrun.run_index
                    _run.$$selected = false
                    $scope.struct.num_selected_ar--
                    break


    $scope.run_now = ($event, obj) ->
        $event.preventDefault()
        $event.stopPropagation()
        blockUI.start("Init AssetRun")
        obj.$$asset_run = true
        icswSimpleAjaxCall(
            {
                url: ICSW_URLS.ASSET_RUN_ASSETRUN_FOR_DEVICE_NOW
                data:
                    pk: obj.idx
                dataType: "json"
            }
        ).then(
            (ok) ->
                blockUI.stop()
                obj.$$asset_run = false
            (not_ok) ->
                blockUI.stop()
                obj.$$asset_run = false
        )


    $scope.select_asset = ($event, device, assetrun) ->
        assetrun.$$selected = !assetrun.$$selected
        if assetrun.$$selected
            # ensure only assetrun with same type are selected
            _type = assetrun.run_type
            for _run in device.assetrun_set
                if _run.run_type !=_type and _run.$$selected
                    _run.$$selected = false
        $scope.struct.num_selected = (_run for _run in device.assetrun_set when _run.$$selected).length
        if $scope.struct.num_selected > 2
            # remove selected asset run
            for _run in device.assetrun_set
                if _run.run_type == _type and _run.$$selected and _run.run_index != assetrun.run_index
                    _run.$$selected = false
                    $scope.struct.num_selected--
                    break
            

    $scope.assetchangeset = (device) ->
        ar1 = undefined
        ar2 = undefined

        for ar in device.assetrun_set
            if ar.$$selected && ar1 == undefined
                ar1 = ar
            else if ar.$$selected && ar2 == undefined
                ar2 = ar
                break

        console.log "ar1: ", ar1
        console.log "ar2: ", ar2
        if ar1 != undefined && ar2 != undefined
            icswSimpleAjaxCall({
                url: ICSW_URLS.ASSET_GET_ASSETRUN_DIFFS
                data:
                    pk1: ar1.idx
                    pk2: ar2.idx
                dataType: 'json'
            }
            ).then(
                (result) ->
                    device.show_changeset = true
                    device.added_changeset = result.added
                    device.removed_changeset = result.removed
                (not_ok) ->
                    console.log not_ok
            )

    $scope.select_devices = (obj) ->
        icswSimpleAjaxCall({
            url: ICSW_URLS.ASSET_GET_DEVICES_FOR_ASSET
            data:
                pk: obj[0]
            dataType: 'json'
        }
        ).then(
            (result) ->
                new_devs = []
                pks_s = ''
                devidx_dev_dict = {}

                for dev in $scope.struct.device_tree.all_list
                    for pk in result.devices
                        if dev.idx == pk
                            dev.assetrun_set = []
                            new_devs.push(dev)
                            pks_s = pks_s.concat(dev.idx + ",")
                            devidx_dev_dict[dev.idx] = dev

                icswSimpleAjaxCall({
                    url: ICSW_URLS.ASSET_GET_ASSETRUNS_FOR_DEVICES
                    data:
                        pks: pks_s
                    dataType: 'json'
                }).then(
                    (result) ->
                        console.log "result: ", result
                        for obj in result.asset_runs
                            asset_run = $scope.createAssetRunFromObj(obj)
                            devidx_dev_dict[asset_run.device_pk].assetrun_set.push(asset_run)
                    (not_ok) ->
                        console.log not_ok
                )

                $scope.struct.devices.length = 0
                for dev in new_devs
                    $scope.struct.devices.push dev
            (not_ok) ->
                console.log not_ok
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
        restrict: "E"
        template: $templateCache.get("icsw.asset.scheduled.runs.table")
    }
]).directive("icswAssetAssetRunsTable",
[
    "$q", "$templateCache",
(
    $q, $templateCache,
) ->
    return {
        restrict: "E"
        template: $templateCache.get("icsw.asset.asset.runs.table")
        scope: {
            asset_run_list: "=icswAssetRunList"
        }
        controller: "icswAssetAssetRunsTableCtrl"
    }
]).controller("icswAssetAssetRunsTableCtrl",
[
    "$scope", "$q", "ICSW_URLS", "blockUI", "Restangular", "icswAssetPackageTreeService", "icswSimpleAjaxCall", "$window"
(
    $scope, $q, ICSW_URLS, blockUI, Restangular, icswAssetPackageTreeService, icswSimpleAjaxCall, $window
) ->
    $scope.struct = {
        selected_assetrun: undefined
    }

    $scope.downloadCsv = ->
        console.log($scope.struct.selected_assetrun)
        if $scope.struct.selected_assetrun != undefined
            icswSimpleAjaxCall({
                url: ICSW_URLS.ASSET_EXPORT_ASSETRUNS_TO_CSV
                data:
                    pk: $scope.struct.selected_assetrun.idx
                dataType: 'json'
            }
            ).then(
                (result) ->
                    uri = 'data:text/csv;charset=utf-8,' + result.csv
                    downloadLink = document.createElement("a")
                    downloadLink.href = uri
                    downloadLink.download = "assetrun" + $scope.struct.selected_assetrun.idx + ".csv"

                    document.body.appendChild(downloadLink)
                    downloadLink.click()
                    document.body.removeChild(downloadLink)
                (not_ok) ->
                    console.log not_ok
            )

    $scope.select_assetrun = ($event, assetrun) ->
        assetrun.$$selected = !assetrun.$$selected
        if assetrun.$$selected
            $scope.struct.selected_assetrun = assetrun
            # ensure only assetrun with same type are selected
            _type = assetrun.run_type
            for _run in $scope.asset_run_list
                if _run.run_type !=_type and _run.$$selected
                    _run.$$selected = false

    # resolve functions
    resolve_package_assets = (tree, vers_list) ->
        _res = _.orderBy(
            (tree.version_lut[idx] for idx in vers_list)
            ["$$package.name"]
            ["asc"]
        )
        return _res

    resolve_hardware_assets = (in_list) ->
        # todo: create structured tree
        for entry in in_list
            entry.$$attributes = angular.fromJson(entry.attributes)
            entry.$$info_list = angular.fromJson(entry.info_list)
            entry.$$attribute_info = ("#{key}=#{value}" for key, value of entry.$$attributes).join(", ")
            entry.$$info_info = ("#{key} (#{value.length})" for key, value of entry.$$info_list).join(", ")
            # console.log entry
        return in_list

    resolve_pending_updates = (in_list) ->
        return (entry for entry in in_list when not entry.installed)
        
        
    resolve_installed_updates = (in_list) ->
        return (entry for entry in in_list when entry.installed)
        
        
    $scope.expand_assetrun = ($event, assetrun) ->
        if !assetrun.$$expanded and not assetrun.$$assets_loaded
            blockUI.start("Fetching data from server...")
            Restangular.all(ICSW_URLS.ASSET_GET_ASSETS_FOR_ASSET_RUN.slice(1)).getList(
                {
                    pk: assetrun.idx
                }
            ).then(
                (data) ->
                    _done = $q.defer()
                    if assetrun.run_type == 1
                        icswAssetPackageTreeService.load($scope.$id).then(
                            (tree) ->
                                _done.resolve(resolve_package_assets(tree, data[0].packages))

                        )
                    else if assetrun.run_type == 2
                        _done.resolve(resolve_hardware_assets(data[0].assethardwareentry_set))
                    else if assetrun.run_type == 3
                        _done.resolve(data[0].assetlicenseentry_set)
                    else if assetrun.run_type == 4
                        _done.resolve(resolve_installed_updates(data[0].assetupdateentry_set))
                    else if assetrun.run_type == 7
                        _done.resolve(resolve_pending_updates(data[0].assetupdateentry_set))
                    else if assetrun.run_type == 6
                        _done.resolve(data[0].assetprocessentry_set)
                    else
                        _done.resolve([])
                    _done.promise.then(
                        (results) ->
                            assetrun.$$assets = results
                            assetrun.$$expanded = !assetrun.$$expanded
                            assetrun.$$assets_loaded = true
                            blockUI.stop()
                    )
            )
        else
            assetrun.$$expanded = !assetrun.$$expanded

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
            package_tree: "=icswAssetPackageTree"
        }
        controller: "icswAssetKnownPackagesCtrl"
    }
]).controller("icswAssetKnownPackagesCtrl",
[
    "$scope", "$q",
(
    $scope, $q,
) ->
    $scope.expand_package = ($event, pack) ->
        pack.$$expanded = !pack.$$expanded
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
            else if scope.asset_run.run_type == 6
                _not_av_el = $compile($templateCache.get("icsw.asset.details.process"))(scope)
            else if scope.asset_run.run_type == 7
                _not_av_el = $compile($templateCache.get("icsw.asset.details.pending.updates"))(scope)
            else
                _not_av_el = $compile($templateCache.get("icsw.asset.details.na"))(scope)
            element.append(_not_av_el)
    }
]).service("icswStaticAssetTemplateTree",
[
    "$q", "Restangular", "ICSW_URLS", "icswTools", "icswSimpleAjaxCall", "icswStaticAssetFunctions",
(
    $q, Restangular, ICSW_URLS, icswTools, icswSimpleAjaxCall, icswStaticAssetFunctions,
) ->
    class icswStaticAssetTemplateTree
        constructor: (list) ->
            @list = []
            @update(list)

        update: (list) =>
            @list.length = 0
            for entry in list
                @list.push(entry)
            @build_luts()

        build_luts: () =>
            @lut = _.keyBy(@list, "idx")
            @link()

        link: () =>
            # DT_FORM = "dd, D. MMM YYYY HH:mm:ss"
            # _cf = ["year", "month", "week", "day", "hour", "minute", "second"]
            # create fields for schedule_setting form handling
            for entry in @list
                entry.$$num_fields = entry.staticassettemplatefield_set.length
                entry.$$asset_type = icswStaticAssetFunctions.resolve("asset_type", entry.type)
                entry.$$created = moment(entry.date).format("YYYY-MM-DD HH:mm:ss")
                
        copy_template: (src_obj, new_obj, create_user) =>
            defer = $q.defer()
            icswSimpleAjaxCall(
                {
                    url: ICSW_URLS.ASSET_COPY_STATIC_TEMPLATE
                    data:
                        new_obj: angular.toJson(new_obj)
                        src_idx: src_obj.idx
                        user_idx: create_user.idx
                    dataType: "json"
                }
            ).then(
                (result) =>
                    console.log "Result", result
                    @list.push(result)
                    @build_luts()
                    defer.resolve("created")
                (error) ->
                    defer.reject("not created")
            )
            return defer.promise

        create_template: (new_obj) =>
            d = $q.defer()
            Restangular.all(ICSW_URLS.ASSET_CREATE_STATIC_ASSET_TEMPLATE.slice(1)).post(new_obj).then(
                (created) =>
                    @list.push(created)
                    @build_luts()
                    d.resolve(created)
                (not_cr) =>
                    d.reject("not created")
            )
            return d.promise

        delete_template: (del_obj) =>
            d = $q.defer()
            Restangular.restangularizeElement(null, del_obj, ICSW_URLS.REST_STATIC_ASSET_TEMPLATE_DETAIL.slice(1).slice(0, -2))
            del_obj.remove().then(
                (removed) =>
                    _.remove(@list, (entry) -> return entry.idx == del_obj.idx)
                    @build_luts()
                    d.resolve("deleted")
                (not_removed) ->
                    d.resolve("not deleted")
            )
            return d.promise

]).service("icswStaticAssetTemplateTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall", "icswTools",
    "icswStaticAssetTemplateTree", "$rootScope", "ICSW_SIGNALS",
(
    $q, Restangular, ICSW_URLS, $window, icswCachingCall, icswTools,
    icswStaticAssetTemplateTree, $rootScope, ICSW_SIGNALS,
) ->
    rest_map = [
        [
            # asset packages
            ICSW_URLS.ASSET_GET_STATIC_TEMPLATES
            {}
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
                if _result?
                    _result.update(data[0])
                else
                    console.log "*** AssetTemplatesTree loaded ***"
                    _result = new icswStaticAssetTemplateTree(data[0])
                _defer.resolve(_result)
                for client of _fetch_dict
                    # resolve clients
                    _fetch_dict[client].resolve(_result)
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
            # loads from server
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise
        "reload": (client) ->
            return load_data(client).promise
    }
])
