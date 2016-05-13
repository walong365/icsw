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
]).service("icswAssetHelperFunctions",
[
    "$q",
(
    $q,
) ->
    resolve_asset_type = (_t) ->
        return {
            1: "Package"
            2: "Hardware"
            3: "License"
            4: "Update"
            5: "Software version"
            6: "Process"
            7: "Pending update"
        }[_t]

    resolve_package_type = (_t) ->
        return {
            1: "Windows"
            2: "Linux"
        }[_t]
        
    return {
        resolve_asset_type: resolve_asset_type,
        resolve_package_type: resolve_package_type
    }
]).controller("icswDeviceAssetCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "$q", "$uibModal", "blockUI",
    "icswTools", "icswSimpleAjaxCall", "ICSW_URLS", "icswAssetHelperFunctions",
    "icswDeviceTreeService", "icswDeviceTreeHelperService"
(
    $scope, $compile, $filter, $templateCache, $q, $uibModal, blockUI,
    icswTools, icswSimpleAjaxCall, ICSW_URLS, icswAssetHelperFunctions,
    icswDeviceTreeService, icswDeviceTreeHelperService
) ->
    # struct to hand over to VarCtrl
    $scope.struct = {
        # list of devices
        devices: []
        # device tree
        device_tree: undefined
        # data loaded
        data_loaded: false
        # num_selected
        num_selected: 0

        # AssetRun tab properties
        num_selected_ar: 0
        asset_runs: []
        show_changeset: false
        added_changeset: []
        removed_changeset: []

        #Scheduled Runs tab properties
        schedule_items: []
        
        #Known packages tab properties
        packages: []
    }

    $scope.createAssetRunFromObj = (obj) ->
        asset_run = {}
        asset_run.idx = obj[0]
        asset_run.pk = obj[0]
        asset_run.run_index = obj[1]
        asset_run.run_type = obj[2]
        asset_run.run_start_time = obj[3]
        if obj[3]!= null && obj[3].length > 0
            date_time_arr = obj[3].split("T")
            if date_time_arr.length < 2
                date_time_arr = obj[3].split(" ")

            asset_run.run_start_day = date_time_arr[0]
            asset_run.run_start_hour = date_time_arr[1].split(".")[0]
        else
            asset_run.run_start_day = ""
            asset_run.run_start_hour = ""
        if obj[4]!= null && obj[4].length > 0
            date_time_arr = obj[4].split("T")
            if date_time_arr.length < 2
                date_time_arr = obj[4].split(" ")
            asset_run.run_end_day = date_time_arr[0]
            asset_run.run_end_hour = date_time_arr[1].split(".")[0]
        else
            asset_run.run_end_day = ""
            asset_run.run_end_hour = ""

        asset_run.run_end_time = obj[4]
        asset_run.total_run_time = obj[5]
        asset_run.device_name = obj[6]
        asset_run.device_pk = obj[7]
        asset_run.assets = []

        return asset_run

    $scope.resolve_asset_type = (_t) ->
        return {
            1: "Package"
            2: "Hardware"
            3: "License"
            4: "Update"
            5: "Software version"
            6: "Process"
            7: "Pending update"
        }[_t]
        
    $scope.resolve_asset_type_reverse = (_t) ->
        return {
            "Package": 1
            "Hardware": 2
            "License": 3
            "Update": 4
            "Software version": 5
            "Process": 6
            "Pending update": 7
        }[_t]

    $scope.resolve_package_type = (_t) ->
        return {
            1: "Windows"
            2: "Linux"
        }[_t]

    $scope.resolve_package_type_reverse = (_t) ->
        return {
            "Windows": 1
            "Linux": 2
        }[_t]

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
                    asset_run.run_type = $scope.resolve_asset_type(obj.run_type)
                    asset_run.run_start_time = obj.run_start_time
                    asset_run.run_end_time = obj.run_end_time
                    if obj.hasOwnProperty("device_name")
                        asset_run.device_name = obj.device_name
                    asset_run.asset = asset
                    moreFilteredARItems.push(asset_run)
            else
                asset_run = {}
                asset_run.run_type = $scope.resolve_asset_type(obj.run_type)
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
                    _pack.package_type = $scope.resolve_package_type(obj.package_type)
                    _pack.version = version[1]
                    _pack.release = version[2]
                    _pack.size = version[3]
                    moreFilteredPackageItems.push(_pack)
            else
                _pack = {}
                _pack.name = obj.name
                _pack.package_type = $scope.resolve_package_type(obj.package_type)
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
                url: ICSW_URLS.MON_GET_ASSETRUN_DIFFS
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

    $scope.select_assetrun = ($event, assetrun) ->
        assetrun.$$selected = !assetrun.$$selected
        if assetrun.$$selected
            # ensure only assetrun with same type are selected
            _type = assetrun.run_type
            for _run in $scope.struct.asset_runs
                if _run.run_type !=_type and _run.$$selected
                    _run.$$selected = false

        $scope.struct.num_selected_ar = (_run for _run in $scope.struct.asset_runs when _run.$$selected).length
        if $scope.struct.num_selected_ar > 2
            for _run in $scope.struct.asset_runs
                if _run.run_type == _type and _run.$$selected and _run.run_index != assetrun.run_index
                    _run.$$selected = false
                    $scope.struct.num_selected_ar--
                    break

    $scope.run_now = ($event, obj) ->
        obj.$$asset_run = true
        icswSimpleAjaxCall(
            {
                url: ICSW_URLS.MON_RUN_ASSETS_NOW
                data:
                    pk: obj.idx
            }
        ).then(
            (ok) ->
                obj.$$asset_run = false
            (not_ok) ->
                obj.$$asset_run = false
        )


    $scope.resolve_asset_type = (a_t) ->
        return icswAssetHelperFunctions.resolve_asset_type(a_t)

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
                url: ICSW_URLS.MON_GET_ASSETRUN_DIFFS
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

    $scope.expand_assetrun = ($event, assetrun) ->
        if !assetrun.expanded
            icswSimpleAjaxCall({
                url: ICSW_URLS.MON_GET_ASSETS_FOR_ASSET_RUN
                data:
                    pk: assetrun.idx
                dataType: 'json'
            }
            ).then(
                (result) ->
                    assetrun.assets = result.assets
                    assetrun.expanded = !assetrun.expanded
                (not_ok) ->
                    console.log not_ok
            )
        else
            assetrun.assets = []
            assetrun.expanded = !assetrun.expanded

    $scope.expand_package = ($event, pack) ->
        if !pack.expanded
            icswSimpleAjaxCall({
                url: ICSW_URLS.MON_GET_VERSIONS_FOR_PACKAGE
                data:
                    pk: pack.pk
                dataType: 'json'
            }
            ).then(
                (result) ->
                    pack.versions = result.versions
                    pack.expanded = !pack.expanded
                (not_ok) ->
                    console.log not_ok
            )
        else
            pack.versions = []
            pack.expanded = !pack.expanded

    $scope.select_devices = (obj) ->
        icswSimpleAjaxCall({
            url: ICSW_URLS.MON_GET_DEVICES_FOR_ASSET
            data:
                pk: obj[0]
            dataType: 'json'
        }
        ).then(
            (result) ->
                new_devs = []

                for dev in $scope.struct.device_tree.all_list
                    for pk in result.devices
                        if dev.idx == pk
                            dev.assetrun_set = []
                            new_devs.push dev

                            icswSimpleAjaxCall({
                                url: ICSW_URLS.MON_GET_ASSETRUNS_FOR_DEVICE
                                data:
                                    pk: dev.idx
                                dataType: 'json'
                            }).then(
                                (result) ->
                                    console.log "result: ", result
                                    for obj in result.asset_runs
                                        dev.assetrun_set.push($scope.createAssetRunFromObj(obj))

                                (not_ok) ->
                                    console.log not_ok
                            )

                $scope.struct.devices.length = 0
                for dev in new_devs
                    $scope.struct.devices.push dev
#              hs = icswDeviceTreeHelperService.create($scope.struct.device_tree, $scope.struct.devices)
#              $scope.struct.device_tree.enrich_devices(hs, ["asset_info"]).then(
#                  (data) ->
#                        for dev in $scope.struct.devices
#                            dev.$$asset_run = false
#                            #dev.assetrun_set_sf_src = []
#                            #for ar in dev.assetrun_set
#                            #    dev.assetrun_set_sf_src.push(ar)
#                        $scope.struct.data_loaded = true
#                )
            (not_ok) ->
                console.log not_ok
        )


    icswSimpleAjaxCall({
        url: ICSW_URLS.MON_GET_ASSET_LIST
        type: "GET"
        dataType: 'json'
    }
    ).then(
        (result) ->
            $scope.struct.packages.length = 0

            for item in result.assets
                _pack = {
                    name: undefined
                    versions: undefined
                }
                _pack.pk = item[0]
                _pack.name = item[1]
                _pack.package_type = item[2]
                _pack.versions = []
                $scope.struct.packages.push(_pack)
        (not_ok) ->
            console.log not_ok
    )

    $scope.new_devsel = (devs) ->
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.device_tree = data[0]
                $scope.struct.devices.length = 0
                $scope.struct.asset_runs.length = 0
                for dev in devs
                    dev.assetrun_set = []
                    $scope.struct.devices.push(dev)

#                    icswSimpleAjaxCall({
#                            url: ICSW_URLS.MON_GET_ASSETRUNS_FOR_DEVICE
#                            data:
#                                pk: dev.idx
#                            dataType: 'json'
#                    }).then(
#                        (result) ->
#                            console.log "result: ", result
#
#                            for obj in result.asset_runs
#                                dev.assetrun_set.push($scope.createAssetRunFromObj(obj))
#                                $scope.struct.asset_runs.push($scope.createAssetRunFromObj(obj))
#
#                        (not_ok) ->
#                            console.log not_ok
#                    )

                $scope.struct.data_loaded = true

#                hs = icswDeviceTreeHelperService.create($scope.struct.device_tree, $scope.struct.devices)
#                $scope.struct.device_tree.enrich_devices(hs, ["asset_info"]).then(
#                    (data) ->
#                        for dev in $scope.struct.devices
#                            dev.$$asset_run = false
#                            #dev.assetrun_set_sf_src = []
#                            #for ar in dev.assetrun_set
#                            #    dev.assetrun_set_sf_src.push(ar)
#                                #$scope.struct.asset_runs.push(ar)
#                        $scope.struct.data_loaded = true
#                )

                icswSimpleAjaxCall({
                    url: ICSW_URLS.MON_GET_ASSETRUNS
                    type: "GET"
                    dataType: 'json'
                }).then(
                    (result) ->
                        console.log "get_assetruns: ", result
                        $scope.struct.asset_runs.length = 0
                        for obj in result.asset_runs
                            found = false
                            for dev in devs
                                if dev.idx == obj[7]
                                    found = true
                                    dev.assetrun_set.push($scope.createAssetRunFromObj(obj))

                            if found
                                $scope.struct.asset_runs.push($scope.createAssetRunFromObj(obj))
                )

                icswSimpleAjaxCall({
                    url: ICSW_URLS.MON_GET_SCHEDULE_LIST
                    type: "GET"
                    dataType: 'json'
                }).then(
                    (result) ->
                        $scope.struct.schedule_items.length = 0
                        for obj in result.schedules
                            found = false
                            for dev in devs
                                if dev.idx == obj[0]
                                    found = true

                            if found
                                sched_item = {}
                                sched_item.dev_pk = obj[0]
                                sched_item.dev_name = obj[1]
                                sched_item.planned_time = obj[2] #obj[2].split("T")[0] + " " +  (obj[2].split("T")[1])
                                sched_item.ds_name = obj[3]
                                $scope.struct.schedule_items.push(sched_item)
                )

        )
]).filter('strictFilter'
[
    "$filter",
(
    $filter
) ->
    return (input, predicate) ->
        console.log "input:", input
        console.log "predicate:" , predicate

        new_predicate = {}

        strict = true
        if (predicate.hasOwnProperty("name"))
            new_predicate.name = predicate.name
            strict = false
        if (predicate.hasOwnProperty("package_type"))
            package_type = undefined
            if predicate.package_type == "Windows"
                package_type = 1
            else if predicate.package_type == "Linux"
                package_type = 2
            new_predicate.package_type = package_type
        if (predicate.hasOwnProperty("run_index"))
            new_predicate.run_index = parseInt(predicate.run_index)
        if (predicate.hasOwnProperty("run_type"))
            run_type = undefined
            if predicate.run_type == "Package"
                run_type = 1
            else if predicate.run_type == "Hardware"
                run_type = 2
            else if predicate.run_type == "License"
                run_type = 3
            else if predicate.run_type == "Update"
                run_type = 4
            else if predicate.run_type == "Software version"
                run_type = 5
            else if predicate.run_type == "Process"
                run_type = 6
            else if predicate.run_type == "Pending update"
                run_type = 7
            new_predicate.run_type = run_type
        if (predicate.hasOwnProperty("run_start_time"))
            new_predicate.run_start_time = predicate.run_start_time
            strict = false
        if (predicate.hasOwnProperty("run_end_time"))
            new_predicate.run_end_time = predicate.run_end_time
            strict = false
        if (predicate.hasOwnProperty("device_name"))
            new_predicate.device_name = predicate.device_name
            strict = false
        if (predicate.hasOwnProperty("$"))
            new_predicate = predicate
            strict = false

        return $filter('filter')(input, new_predicate, strict)

]).filter('unique'
[
    "$filter",
(
    $filter
) ->
    return (arr, field) ->
        console.log "* arr:", arr
        console.log "* field:", field
        o = {}
        l = arr.length
        r = []

        for i in [0...l]
            o[arr[i][field]] = arr[i]


        for i in o
            r.push(o[i])

        console.log "*r: ", r

        return r
]).filter('assetRunFilter'
[
    "$filter",
(
    $filter
) ->
    return (input, predicate) ->
        console.log "input:", input
        console.log "predicate:" , predicate

        new_predicate = {}
        strict = true

        if (predicate.hasOwnProperty("run_type"))
            run_type = undefined
            if predicate.run_type == "Package"
                run_type = 1
            else if predicate.run_type == "Hardware"
                run_type = 2
            else if predicate.run_type == "License"
                run_type = 3
            else if predicate.run_type == "Update"
                run_type = 4
            else if predicate.run_type == "Software version"
                run_type = 5
            else if predicate.run_type == "Process"
                run_type = 6
            else if predicate.run_type == "Pending update"
                run_type = 7
            new_predicate.run_type = run_type
        if (predicate.hasOwnProperty("run_start_day"))
            new_predicate.run_start_day = predicate.run_start_day
            strict = false
        if (predicate.hasOwnProperty("run_start_hour"))
            new_predicate.run_start_hour = predicate.run_start_hour
            strict = false
        if (predicate.hasOwnProperty("run_end_day"))
            new_predicate.run_end_day = predicate.run_end_day
            strict = false
        if (predicate.hasOwnProperty("run_end_hour"))
            new_predicate.run_end_hour = predicate.run_end_hour
            strict = false
        if (predicate.hasOwnProperty("device_name"))
            new_predicate.device_name = predicate.device_name
            strict = false

        return $filter('filter')(input, new_predicate, strict)
])