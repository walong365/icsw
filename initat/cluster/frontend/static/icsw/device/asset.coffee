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

    resolve_asset_type_reverse = (_t) ->
        items = ["package", "hardware", "license", "update", "software version", "process", "pending update"]
        item_idx = {
            "package": 1
            "hardware": 2
            "license": 3
            "update": 4
            "software version": 5
            "process": 6
            "pending update": 7
        }

        for item in items
            if item.indexOf(_t.toLowerCase()) > -1
                return item_idx[item]
        return -1

    resolve_package_type = (_t) ->
        return {
            1: "Windows"
            2: "Linux"
        }[_t]

    resolve_package_type_reverse = (_t) ->
        items = ["windows", "linux"]

        item_idx = {
            "windows": 1
            "linux": 2
        }

        for item in items
            if item.indexOf(_t.toLowerCase()) > -1
                return item_idx[item]
        return -1

    resolve_run_status = (_t) ->
        return {
            1: "Pending"
            2: "Running"
            3: "Finished"
            4: "Failed"
        }[_t]

    resolve_run_status_reverse = (_t) ->
        items = ["pending", "running", "finished", "failed"]
        item_idx = {
            "pending": 1
            "running": 2
            "finished": 3
            "failed": 4
        }

        for item in items
            if item.indexOf(_t.toLowerCase()) > -1
                return item_idx[item]
        return -1
        
    SCHED_SOURCE_LUT = {
        # see models/dispatch.py
        1: "SNMP"
        2: "ASU"
        3: "IPMI"
        4: "Package"
        5: "Hardware"
        6: "License"
        7: "Update"
        8: "Software Version"
        9: "Process"
        10: "Pending update"
    }
    resolve_schedule_source = (_s) ->
        return SCHED_SOURCE_LUT[_s]
        
    return {
        resolve_asset_type: resolve_asset_type
        resolve_asset_type_reverse: resolve_asset_type_reverse
        resolve_package_type: resolve_package_type
        resolve_package_type_reverse: resolve_package_type_reverse
        resolve_run_status: resolve_run_status
        resolve_run_status_reverse: resolve_run_status_reverse
        resolve_schedule_source: resolve_schedule_source
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
            _moment = moment(obj[3])

            asset_run.run_start_day = _moment.format("YYYY-MM-DD")
            asset_run.run_start_hour = _moment.format("HH:mm:ss")
        else
            asset_run.run_start_day = ""
            asset_run.run_start_hour = ""
            
        if obj[4]!= null && obj[4].length > 0
            _moment = moment(obj[4])

            asset_run.run_end_day = _moment.format("YYYY-MM-DD")
            asset_run.run_end_hour = _moment.format("HH:mm:ss")
        else
            asset_run.run_end_day = ""
            asset_run.run_end_hour = ""

        asset_run.run_end_time = obj[4]
        asset_run.total_run_time = parseFloat(obj[5]).toFixed(2)
        asset_run.device_name = obj[6]
        asset_run.device_pk = obj[7]
        asset_run.run_status = obj[8]
        asset_run.assets = []

        return asset_run

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
                    asset_run.run_type = icswAssetHelperFunctions.resolve_asset_type(obj.run_type)
                    asset_run.run_start_time = obj.run_start_time
                    asset_run.run_end_time = obj.run_end_time
                    if obj.hasOwnProperty("device_name")
                        asset_run.device_name = obj.device_name
                    asset_run.asset = asset
                    moreFilteredARItems.push(asset_run)
            else
                asset_run = {}
                asset_run.run_type = icswAssetHelperFunctions.resolve_asset_type(obj.run_type)
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
                    _pack.package_type = icswAssetHelperFunctions.resolve_package_type(obj.package_type)
                    _pack.version = version[1]
                    _pack.release = version[2]
                    _pack.size = version[3]
                    moreFilteredPackageItems.push(_pack)
            else
                _pack = {}
                _pack.name = obj.name
                _pack.package_type = icswAssetHelperFunctions.resolve_package_type(obj.package_type)
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
                url: ICSW_URLS.ASSET_RUN_ASSETRUN_FOR_DEVICE_NOW
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

    $scope.resolve_package_type = (a_t) ->
        return icswAssetHelperFunctions.resolve_package_type(a_t)

    $scope.resolve_run_status = (a_t) ->
        return icswAssetHelperFunctions.resolve_run_status(a_t)

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

    $scope.expand_assetrun = ($event, assetrun) ->
        if !assetrun.expanded
            icswSimpleAjaxCall({
                url: ICSW_URLS.ASSET_GET_ASSETS_FOR_ASSET_RUN
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
                url: ICSW_URLS.ASSET_GET_VERSIONS_FOR_PACKAGE
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

    icswSimpleAjaxCall({
        url: ICSW_URLS.ASSET_GET_ASSET_LIST
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
                pks_s = ''
                devidx_dev_dict = {}
                for dev in devs
                    # filter out metadevices
                    if not dev.is_meta_device
                        dev.assetrun_set = []
                        pks_s = pks_s.concat(dev.idx + ",")
                        devidx_dev_dict[dev.idx] = dev
                        $scope.struct.devices.push(dev)

                $scope.struct.data_loaded = true
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
                            $scope.struct.asset_runs.push($scope.createAssetRunFromObj(obj))

                    (not_ok) ->
                        console.log not_ok
                )
                
                $scope.struct.data_loaded = true

                icswSimpleAjaxCall({
                    url: ICSW_URLS.ASSET_GET_SCHEDULE_LIST
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
                                sched_item.planned_time_moment = moment(obj[2])
                                sched_item.planned_time = sched_item.planned_time_moment.format("YYYY-MM-DD HH:mm:ss")
                                sched_item.ds_name = obj[3]
                                $scope.struct.schedule_items.push(sched_item)
                )

        )
]).filter('assetRunFilter'
[
    "$filter", "icswAssetHelperFunctions"
(
    $filter, icswAssetHelperFunctions
) ->
    return (input, predicate) ->
        console.log "input:", input
        console.log "predicate:" , predicate

        new_predicate = {}
        strict = true

        if (predicate.hasOwnProperty("run_type"))
            run_type = icswAssetHelperFunctions.resolve_asset_type_reverse(predicate.run_type)
            console.log "run_type: ", run_type
            new_predicate.run_type = run_type
            strict = false
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
        if (predicate.hasOwnProperty("run_status"))
            run_status = icswAssetHelperFunctions.resolve_run_status_reverse(predicate.run_status)
            new_predicate.run_status = run_status
            strict = false

        return $filter('filter')(input, new_predicate, strict)
]).filter('packageFilter'
[
    "$filter", "icswAssetHelperFunctions"
(
    $filter, icswAssetHelperFunctions
) ->
    return (input, predicate) ->
        console.log "input:", input
        console.log "predicate:" , predicate

        new_predicate = {}
        strict = false

        if (predicate.hasOwnProperty("name"))
            new_predicate.name = predicate.name

        if (predicate.hasOwnProperty("package_type"))
            package_type = icswAssetHelperFunctions.resolve_package_type_reverse(predicate.package_type)
            console.log "package_type: ", package_type
            new_predicate.package_type = package_type

        return $filter('filter')(input, new_predicate, strict)
]).filter('baseAssetFilter'
[
    "$filter", "icswAssetHelperFunctions"
(
    $filter, icswAssetHelperFunctions
) ->
    return (input, predicate) ->
        console.log "input:", input
        console.log "predicate:" , predicate


        return $filter('filter')(input, predicate, false)
])