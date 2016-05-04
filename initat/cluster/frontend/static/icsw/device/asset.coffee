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
]).controller("icswDeviceAssetCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "$q", "$uibModal", "blockUI",
    "icswTools",
    "icswDeviceTreeService", "icswDeviceTreeHelperService", "$rootScope"
(
    $scope, $compile, $filter, $templateCache, $q, $uibModal, blockUI,
    icswTools,
    icswDeviceTreeService, icswDeviceTreeHelperService, $rootScope,
) ->
    # struct to hand over to VarCtrl
    $scope.struct = {
        # list of devices
        devices: []
        # device tree
        device_tree: undefined
        # data loaded
        data_loaded: false
    }

    $scope.predicates = ['firstName', 'lastName', 'birthDate', 'balance', 'email'];
    $scope.selectedPredicate = $scope.predicates[0];

    $scope.addRandomItem = (id) ->
        console.log "ttttt", id

    a = $q.defer()
    b = $q.defer()
    c = $q.defer()
    a.promise.then(
        (bzwwez) ->
            console.log "ok", bzwwez
            b.resolve("ok")
    )
    c.promise.then(
        (ok) ->
        (error) ->
            console.log "notoK"
        (notify) ->
            console.log "cnot", notify
    )
    b.promise.then(
        (ok) ->
            console.log "q"
            c.reject("notok")
    )
    b.promise.then(
        (ok) ->
            console.log "second"
    )
    c.notify("1.")
    c.notify("2.")
    a.resolve("go")
    $scope.$on("$destroy", () ->
        console.log "asset destroyed"
    )

    $rootScope.assets = []
    $rootScope.assets_sf = []

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

                $rootScope.assets = []
                $rootScope.assets_sf = []
                console.log "reseting assets"

                hs = icswDeviceTreeHelperService.create($scope.struct.device_tree, $scope.struct.devices)
                $scope.struct.device_tree.enrich_devices(hs, ["asset_info"]).then(
                    (data) ->
                        console.log "len: ", $rootScope.assets.length

                        hm = {}


                        for dev in $scope.struct.devices
                            dev.assetrun_set_sf_src = []
                            for ar in dev.assetrun_set
                                dev.assetrun_set_sf_src.push(ar)
                                for pack in ar.packages
                                    hm[pack.idx] = pack

                        console.log "hm: ", hm
                        for k, v of hm
                            $rootScope.assets.push(v)
                            $rootScope.assets_sf.push(v)

                        console.log "lenAfter: ", $rootScope.assets.length
                        console.log "assets loaded"
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

        strict = true
        if (predicate.hasOwnProperty("run_index"))
            predicate.run_index = parseInt(predicate.run_index)
        if (predicate.hasOwnProperty("run_type"))
            predicate.run_type = parseInt(predicate.run_type)
        if (predicate.hasOwnProperty("$"))
            strict = false

        return $filter('filter')(input, predicate, strict);

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