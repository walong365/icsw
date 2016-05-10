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
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select"
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
        
    return {
        resolve_asset_type: resolve_asset_type
    }
]).controller("icswDeviceAssetCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "$q", "$uibModal", "blockUI",
    "icswTools", "icswSimpleAjaxCall", "ICSW_URLS", "$http", "icswAssetHelperFunctions",
    "icswDeviceTreeService", "icswDeviceTreeHelperService", "$rootScope", "$timeout"
(
    $scope, $compile, $filter, $templateCache, $q, $uibModal, blockUI,
    icswTools, icswSimpleAjaxCall, ICSW_URLS, $http, icswAssetHelperFunctions,
    icswDeviceTreeService, icswDeviceTreeHelperService, $rootScope, $timeout
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
    }

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
            $http({
                method: 'POST',
                url: '/icsw/api/v2/mon/get_assetrun_diffs'
                data: "pk1="+ar1.idx+"&pk2="+ar2.idx
                headers: {'Content-Type': 'application/x-www-form-urlencoded'}
            }).then(
              (result) ->
                  console.log "assetchangeset ", result
            )

    $scope.refresh = ->
        hs = icswDeviceTreeHelperService.create($scope.struct.device_tree, $scope.struct.devices)
        $scope.struct.device_tree.enrich_devices(hs, ["asset_info"]).then(
            (data) ->
                for dev in $scope.struct.devices
                    dev.assetrun_set_sf_src = []
                    for ar in dev.assetrun_set
                        dev.assetrun_set_sf_src.push(ar)
                $scope.struct.data_loaded = true
        )



        console.log "refresh"

    $scope.select_devices = (obj) ->
        $http({
            method: 'POST',
            url: '/icsw/api/v2/mon/get_devices_for_asset'
            data: "pk=" + obj[0]
            headers: {'Content-Type': 'application/x-www-form-urlencoded'}
        }).then(
          (result) ->
              new_devs = []

              for dev in $scope.struct.device_tree.all_list
                  for pk in result.data.devices
                      if dev.idx == pk
                          new_devs.push dev

              $scope.struct.devices = new_devs
              hs = icswDeviceTreeHelperService.create($scope.struct.device_tree, $scope.struct.devices)
              $scope.struct.device_tree.enrich_devices(hs, ["asset_info"]).then(
                  (data) ->
                        for dev in $scope.struct.devices
                            dev.$$asset_run = false
                            dev.assetrun_set_sf_src = []
                            for ar in dev.assetrun_set
                                dev.assetrun_set_sf_src.push(ar)
                        $scope.struct.data_loaded = true
                )
        )

    $rootScope.assets = []
    $rootScope.assets_sf = []

    $http.get('/icsw/api/v2/mon/get_asset_list').then(
        (result) ->
            $rootScope.assets = []
            $rootScope.assets_sf = []

            angular.forEach result.data.assets, (item) ->
                _pack = {
                    name: undefined
                    version: undefined
                    release: undefined
                }
                _pack.pk = item[0]
                _pack.name = item[1]
                _pack.version = item[2]
                _pack.release = item[3]
                $rootScope.assets.push _pack
                $rootScope.assets_sf.push _pack
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
                for entry in devs
                    $scope.struct.devices.push(entry)

                hs = icswDeviceTreeHelperService.create($scope.struct.device_tree, $scope.struct.devices)
                $scope.struct.device_tree.enrich_devices(hs, ["asset_info"]).then(
                    (data) ->
                        for dev in $scope.struct.devices
                            dev.assetrun_set_sf_src = []
                            for ar in dev.assetrun_set
                                dev.assetrun_set_sf_src.push(ar)
                        $scope.struct.data_loaded = true
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
        if (predicate.hasOwnProperty("$"))
            new_predicate = predicate
            strict = false

        return $filter('filter')(input, new_predicate, strict);

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
])