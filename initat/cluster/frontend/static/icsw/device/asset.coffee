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

        # AssetBatch data
        asset_batch_list: []

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
                Restangular.all(ICSW_URLS.ASSET_GET_ASSETBATCH_LIST.slice(1)).getList(
                    {
                        device_pks: angular.toJson((dev.idx for dev in $scope.struct.devices))
                        simple: angular.toJson(1)
                    }
                )
                # todo, make faster
                # icswAssetPackageTreeService.reload($scope.$id)
            ]
        ).then(
            (result) ->
                set_schedule_items(result[0])

                set_asset_batch_list(result[1])

                $scope.struct.reloading = false

                for asset_batch in $scope.struct.asset_batch_list
                    if !asset_batch.is_finished_processing
                        start_timer()
                        break
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

    set_asset_batch_list = (asset_batch_list) ->
        $scope.struct.asset_batch_list.length = 0

        dev_lookup_table = {}

        for dev in $scope.struct.devices
            dev.asset_batch_list.length = 0
            dev_lookup_table[dev.idx] = dev

        for asset_batch in asset_batch_list
            $scope.struct.asset_batch_list.push(asset_batch)
            salt_asset_batch(asset_batch)
            dev_lookup_table[asset_batch.device].asset_batch_list.push(asset_batch)

    set_schedule_items = (sched_list) ->
        $scope.struct.schedule_items.length = 0

        for device in $scope.struct.devices
            device.schedule_items.length = 0

        for obj in sched_list
            $scope.struct.schedule_items.push(salt_schedule_item(obj))
            obj.$$device.schedule_items.push(obj)

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

                console.log(data[2])

                $scope.struct.devices.length = 0
                for dev in devs
                    # filter out metadevices
                    if not dev.is_meta_device
                        if not dev.assetrun_set?
                            dev.assetrun_set = []

                        if not dev.asset_batch_list?
                            dev.asset_batch_list = []
                        else
                            dev.asset_batch_list.length = 0

                        if not dev.info_tabs?
                            dev.info_tabs = []
                        else
                            dev.info_tabs.length = 0

                        if not dev.schedule_items?
                            dev.schedule_items = []
                        else
                            dev.schedule_items.length = 0

                        dev.$$scan_device_button_disabled = false

                        $scope.struct.devices.push(dev)

                $q.all(
                    [
                        Restangular.all(ICSW_URLS.ASSET_GET_SCHEDULE_LIST.slice(1)).getList(
                            {
                                pks: angular.toJson((dev.idx for dev in $scope.struct.devices))
                            }
                        )
                        Restangular.all(ICSW_URLS.ASSET_GET_ASSETBATCH_LIST.slice(1)).getList(
                            {
                                device_pks: angular.toJson((dev.idx for dev in $scope.struct.devices))
                                simple: angular.toJson(1)
                            }
                        )
                    ]
                ).then(
                    (result) ->
                        # schedule list
                        set_schedule_items(result[0])

                        set_asset_batch_list(result[1])

                        $scope.struct.data_loaded = true

                        for asset_batch in $scope.struct.asset_batch_list
                            if !asset_batch.is_finished_processing
                                start_timer()
                                break
                )
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
            "packages",
            "pending_updates",
            "installed_updates",
            "memory_modules",
            "cpus",
            "gpus",
            "network_devices",
            "partition_table",
        ]

        for info_list_name in info_list_names
            obj["$$" + info_list_name + "_availability_class"] = info_not_available_class
            obj["$$" + info_list_name + "_availability_text"] = info_not_available_text

            if obj[info_list_name + "_length"] > 0
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
        icswSimpleAjaxCall(
            {
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

                icswSimpleAjaxCall(
                    {
                        url: ICSW_URLS.ASSET_GET_ASSETRUNS_FOR_DEVICES
                        data:
                            pks: pks_s
                        dataType: 'json'
                    }
                ).then(
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
            package_tree: "=icswAssetPackageTree"
        }
        controller: "icswAssetKnownPackagesCtrl"
    }
]).controller("icswAssetKnownPackagesCtrl",
[
    "$scope", "$q", "ICSW_URLS", "icswSimpleAjaxCall"
(
    $scope, $q, ICSW_URLS, icswSimpleAjaxCall
) ->
    $scope.expand = ($event, obj) ->
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

    $scope.downloadCsv = ->
        icswSimpleAjaxCall(
            {
                url: ICSW_URLS.ASSET_EXPORT_PACKAGES_TO_CSV
                dataType: 'json'
            }
        ).then(
            (result) ->
                    uri = 'data:text/csv;charset=utf-8,' + encodeURIComponent(result.csv)
                    downloadLink = document.createElement("a")
                    downloadLink.href = uri
                    downloadLink.download = "packages.csv"

                    document.body.appendChild(downloadLink)
                    downloadLink.click()
                    document.body.removeChild(downloadLink)
            (not_ok) ->
                console.log not_ok
        )

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
    "icswTools"
(
    $scope, $q, ICSW_URLS, blockUI, Restangular, icswAssetPackageTreeService, icswSimpleAjaxCall, icswTools
) ->
    $scope.struct = {
        selected_assetrun: undefined
        package_tree: undefined
    }



    $scope.downloadPdf = ->
        if $scope.struct.selected_assetrun != undefined
            icswSimpleAjaxCall({
                url: ICSW_URLS.ASSET_EXPORT_ASSETBATCH_TO_PDF
                data:
                    pk: $scope.struct.selected_assetrun.asset_batch
                dataType: 'json'
            }
            ).then(
                (result) ->
                    console.log "result: ", result

                    uri = 'data:application/pdf;base64,' + result.pdf
                    downloadLink = document.createElement("a")
                    downloadLink.href = uri
                    downloadLink.download = "assetbatch" + $scope.struct.selected_assetrun.asset_batch + ".pdf"

                    document.body.appendChild(downloadLink)
                    downloadLink.click()
                    document.body.removeChild(downloadLink)
                (not_ok) ->
                    console.log not_ok
            )

    $scope.downloadXlsx = ->
        console.log($scope.struct.selected_assetrun)
        if $scope.struct.selected_assetrun != undefined
            icswSimpleAjaxCall({
                url: ICSW_URLS.ASSET_EXPORT_ASSETBATCH_TO_XLSX
                data:
                    pk: $scope.struct.selected_assetrun.asset_batch
                dataType: 'json'
            }
            ).then(
                (result) ->
                    console.log "result: ", result

                    uri = 'data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,' + result.xlsx
                    downloadLink = document.createElement("a")
                    downloadLink.href = uri
                    downloadLink.download = "assetbatch" + $scope.struct.selected_assetrun.asset_batch + ".xlsx"

                    document.body.appendChild(downloadLink)
                    downloadLink.click()
                    document.body.removeChild(downloadLink)
                (not_ok) ->
                    console.log not_ok
            )

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
                    uri = 'data:text/csv;charset=utf-8,' + encodeURIComponent(result.csv)
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
    resolve_package_assets = (tree, vers_list, package_install_times) ->
        _res = _.orderBy(
            (tree.version_lut[idx] for idx in vers_list)
            ["$$package.name"]
            ["asc"]
        )

        result_new = []

        # do some more salting of package objectss
        for vers in _res
            new_obj = {}

            if vers.release == ""
                new_obj.release = "N/A"
            else
                new_obj.release = vers.release

            new_obj.$$install_time = "N/A"
            new_obj.$$package = vers.$$package
            new_obj.version = vers.version
            new_obj.size = vers.size

            if vers.$$package.$$package_type == "Windows"
                if vers.size > 0
                    new_obj.$$size = Number((vers.size / 1024).toFixed(2)) + " MByte"
                else
                    new_obj.$$size = "N/A"

            if vers.$$package.$$package_type == "Linux"
                if vers.size > 0
                    if vers.size < (1024 * 1024)
                        new_obj.$$size = Number((vers.size / 1024).toFixed(2)) + " KByte"
                    else
                        new_obj.$$size = Number((vers.size / (1024 * 1024)).toFixed(2)) + " MByte"
                else
                    new_obj.$$size = "N/A"

            for package_install_time in package_install_times
                if vers.idx == package_install_time.package_version
                    new_obj.$$install_time = moment(package_install_time.install_time).format("YYYY-MM-DD HH:mm:ss")
                    break

            result_new.push(new_obj)

        return result_new

    $scope.expand_assetbatch = ($event, assetbatch) ->
        assetbatch.$$expanded = !assetbatch.$$expanded

    $scope.open_in_new_tab = (asset_batch) ->
        for tab in asset_batch.$$device.info_tabs
            if tab.asset_batch.idx == asset_batch.idx
                return

        blockUI.start("Please wait...")


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
                #console.log(result[0][0])
                tab = {}
                tab.asset_batch = result[0][0]
                tab.tab_heading_text = "Scan (ID:" + asset_batch.idx + ")"

                for memory_entry in tab.asset_batch.memory_modules
                    memory_entry.$$capacity = "N/A"
                    memory_entry.$$capacity = memory_entry.capacity / (1024.0 * 1024.0)

                tab.asset_batch.hdds = []

                if tab.asset_batch.partition_table
                    for disc in tab.asset_batch.partition_table.partition_disc_set
                        o = {
                            "identifier": "N/A"
                            "serialnumber": "N/A"
                            "size": "N/A"
                            "partitions": []
                        }

                        if disc.disc
                            o["identifier"] = disc.disc

                        if disc.serial
                            o["serialnumber"] = disc.serial

                        if disc.size
                            o["size"] = disc.size

                        for partition in disc.partition_set
                            new_partition_o = {
                                "mountpoint": "N/A"
                                "size": "N/A"
                            }

                            if partition.mountpoint
                                new_partition_o["mountpoint"] = partition.mountpoint
                            if partition.size
                                new_partition_o["size"] = icswTools.get_size_str(partition.size, 1024, "Byte")

                            o["partitions"].push(new_partition_o)

                        console.log(o)

                        tab.asset_batch.hdds.push(o)

                #console.log(tab)

                icswAssetPackageTreeService.load($scope.$id).then(
                    (tree) ->
                        tree_up_to_date = true
                        for package_idx in tab.asset_batch.packages
                            if tree.version_lut[package_idx] == undefined
                                tree_up_to_date = false
                                break

                        if !tree_up_to_date
                            console.log("not up to date package tree found, reloading")
                            icswAssetPackageTreeService.reload($scope.$id).then(
                                (tree) ->
                                    tab.packages = resolve_package_assets(tree, tab.asset_batch.packages, tab.asset_batch.packages_install_times)
                                    asset_batch.$$device.info_tabs.push(tab)
                                    blockUI.stop()
                            )
                        else
                            tab.packages = resolve_package_assets(tree, tab.asset_batch.packages, tab.asset_batch.packages_install_times)
                            asset_batch.$$device.info_tabs.push(tab)
                            blockUI.stop()
                )
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
])
