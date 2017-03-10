# Copyright (C) 2012-2017 init.at
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

angular.module(
    "icsw.weathermap",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters",
        "restangular",
    ]
).config(["icswRouteExtensionProvider", (icswRouteExtensionProvider) ->
    icswRouteExtensionProvider.add_route("main.weathermap")
]).controller("icswWeathermapOverviewCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular",
    "$q", "$uibModal", "$timeout", "ICSW_URLS", "icswSimpleAjaxCall",
    "icswParseXMLResponseService", "toaster", "icswUserService", "icswGraphTools",
    "icswDeviceTreeHelperService", "icswDeviceTreeService",
(
    $scope, $compile, $filter, $templateCache, Restangular,
    $q, $uibModal, $timeout, ICSW_URLS, icswSimpleAjaxCall,
    icswParseXMLResponseService, toaster, icswUserService, icswGraphTools,
    icswDeviceTreeHelperService, icswDeviceTreeService,
) ->
    $scope.struct = {
        # device tree
        device_tree: undefined
        # loading
        loading: true
        # data valid
        data_valid: false
        # devices
        devices: []
    }
    $scope.new_devsel = (dev_list) ->
        $scope.struct.devices.length = 0
        for dev in dev_list
            if not dev.is_meta_device
                $scope.struct.devices.push(dev)
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.device_tree = data[0]
                hs = icswDeviceTreeHelperService.create($scope.struct.device_tree, $scope.struct.devices)
                $scope.struct.device_tree.enrich_devices(hs, ["network_info"]).then(
                    (done) ->
                        console.log "d"
                        icswSimpleAjaxCall(
                            url: ICSW_URLS.DEVICE_GET_WEATHERMAP_DATA
                            dataType: "json"
                            data:
                                device_idxs: angular.toJson((dev.idx for dev in $scope.struct.devices))
                        ).then(
                            (result) ->
                                console.log "*", result
                                $scope.struct.loading = false
                                $scope.struct.data_valid = true
                        )
                )
        )

    $scope.$on("$destroy", () ->
    )
]).directive("icswWeathermapOverview",
[
    "$templateCache", "$compile",
(
    $templateCache, $compile,
) ->
    return {
        restrict: "E"
        template: $templateCache.get("icsw.weathermap.overview")
        controller: "icswWeathermapOverviewCtrl"
    }
    # console.log "S", $scope.graph
])
