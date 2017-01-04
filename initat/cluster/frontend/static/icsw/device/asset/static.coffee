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

static_inventory_overview = angular.module(
    "icsw.device.asset.static",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select"
    ]
).config(["icswRouteExtensionProvider", (icswRouteExtensionProvider) ->
    icswRouteExtensionProvider.add_route("main.assetstaticoverview")
]).directive("icswDeviceAssetStaticOverview",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.asset.static.overview")
        controller: "icswDeviceAssetStaticOverviewCtrl"
        scope: true
    }
]).controller("icswDeviceAssetStaticOverviewCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "$q", "$uibModal", "blockUI",
    "icswTools", "icswSimpleAjaxCall", "ICSW_URLS", "icswAssetHelperFunctions",
    "icswDeviceTreeService", "icswDeviceTreeHelperService", "$timeout",
    "icswDispatcherSettingTreeService", "Restangular", "icswCategoryTreeService",
    "icswStaticAssetTemplateTreeService"
(
    $scope, $compile, $filter, $templateCache, $q, $uibModal, blockUI,
    icswTools, icswSimpleAjaxCall, ICSW_URLS, icswAssetHelperFunctions,
    icswDeviceTreeService, icswDeviceTreeHelperService, $timeout,
    icswDispatcherSettingTreeService, Restangular, icswCategoryTreeService,
    icswStaticAssetTemplateTreeService
) ->
    $scope.struct = {
        device_tree: undefined
        category_tree: undefined
        staticasset_tree: undefined
        data_loaded: false

        # easier to handle data structures
        categories: []

        static_asset_tabs: {}
    }

    $q.all(
        [
            icswDeviceTreeService.load($scope.$id)
            icswCategoryTreeService.load($scope.$id)
            icswStaticAssetTemplateTreeService.load($scope.$id)
        ]).then(
                (data) ->
                    $scope.struct.device_tree = data[0]
                    $scope.struct.category_tree = data[1]
                    $scope.struct.staticasset_tree = data[2]

                    console.log(data[0])
                    console.log(data[2])

                    $scope.struct.categories.length = 0



                    for category in $scope.struct.category_tree.asset_list
                        o = {
                            name: category.name
                            devices: []
                        }

                        for device_id in category.reference_dict.device
                            o.devices.push(data[0].all_lut[device_id])

                        $scope.struct.categories.push(o)

                    idx_list = []

                    for obj in $scope.struct.staticasset_tree.list
                        idx_list.push(obj.idx)

                    icswSimpleAjaxCall({
                        url: ICSW_URLS.ASSET_GET_FIELDVALUES_FOR_TEMPLATE
                        data:
                            idx_list: idx_list
                        dataType: 'json'
                    }).then(
                        (result) ->
                            static_assets = []

                            for obj in $scope.struct.staticasset_tree.list
                                static_assets.push(obj)
                                obj.$$show_devices_inventory_static_overview = false

                                if $scope.struct.static_asset_tabs[obj.type] == undefined
                                    $scope.struct.static_asset_tabs[obj.type] = []

                                $scope.struct.static_asset_tabs[obj.type].push(obj)


                            for static_asset in static_assets
                                static_asset.$$fields = result.data[static_asset.idx]
                                static_asset.$$devices = {}
                                static_asset.$$inventory_static_status = 0

                                for ordering_num in Object.getOwnPropertyNames(static_asset.$$fields)
                                    for field_value in static_asset.$$fields[ordering_num]["list"]
                                        if static_asset.$$fields[ordering_num].status > static_asset.$$inventory_static_status
                                            static_asset.$$inventory_static_status = static_asset.$$fields[ordering_num].status

                                        if field_value.device_idx > 0
                                            device = $scope.struct.device_tree.all_lut[field_value.device_idx]
                                            if device.$$static_field_values == undefined
                                                device.$$static_field_values = {}

                                            device.$$static_field_values[ordering_num] = field_value
                                            if !(field_value.device_idx in static_asset.$$devices)
                                                static_asset.$$devices[field_value.device_idx] = device

                                            field_value.$$device = $scope.struct.device_tree.all_lut[field_value.device_idx]

                                for ordering_num in Object.getOwnPropertyNames(static_asset.$$fields)
                                    for device_num in Object.getOwnPropertyNames(static_asset.$$devices)
                                        if static_asset.$$devices[device_num].$$static_field_values[ordering_num] == undefined
                                            o = {
                                                value: static_asset.$$fields[ordering_num].aggregate
                                            }

                                            static_asset.$$devices[device_num].$$static_field_values[ordering_num] = o

                                static_asset.$$expand_devices_button_disabled = true
                                for device_num in Object.getOwnPropertyNames(static_asset.$$devices)
                                    static_asset.$$expand_devices_button_disabled = false
                                    device = static_asset.$$devices[device_num]
                                    device.$$inventory_static_status = 0

                                    for ordering_num in Object.getOwnPropertyNames(device.$$static_field_values)
                                        if device.$$static_field_values[ordering_num].status > device.$$inventory_static_status
                                            device.$$inventory_static_status = device.$$static_field_values[ordering_num].status



                            $scope.struct.data_loaded = true

                        (not_ok) ->
                            console.log(not_ok)
                    )


        )

    $scope.show_devices = (obj) ->
        obj.$$show_devices_inventory_static_overview = !obj.$$show_devices_inventory_static_overview
])