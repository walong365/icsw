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

device_properties_overview = angular.module(
    "icsw.device.properties.overview",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select"
    ]
).config(["icswRouteExtensionProvider", (icswRouteExtensionProvider) ->
    icswRouteExtensionProvider.add_route("main.devicepropertiesoverview")
]).directive("icswDevicePropertiesOverview",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.properties.overview")
        controller: "icswDevicePropertiesOverviewCtrl"
        scope: true
    }
]).controller("icswDevicePropertiesOverviewCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "$q", "$uibModal", "blockUI",
    "icswTools", "icswSimpleAjaxCall", "ICSW_URLS", "icswAssetHelperFunctions",
    "icswDeviceTreeService", "$timeout"
(
    $scope, $compile, $filter, $templateCache, $q, $uibModal, blockUI,
    icswTools, icswSimpleAjaxCall, ICSW_URLS, icswAssetHelperFunctions,
    icswDeviceTreeService, $timeout
) ->
    $scope.struct = {
        device_tree: undefined
        data_loaded: false

        devices: []
        device_ids_needing_refresh: []

        tabs: []
    }



    perform_refresh = (partial_refresh) ->
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.device_tree = data[0]
                $scope.struct.devices.length = 0

                for device in $scope.struct.device_tree.all_list
                    if !device.is_meta_device
                        $scope.struct.devices.push(device)


                if partial_refresh
                    device_id_list = $scope.struct.device_ids_needing_refresh
                else
                    device_id_list = (device.idx for device in $scope.struct.devices)

                console.log(device_id_list)

                icswSimpleAjaxCall(
                  {
                    url: ICSW_URLS.DEVICE_DEVICE_COMPLETION
                    data:
                        device_pks: device_id_list
                    dataType: "json"
                }).then(
                    (data) ->
                        for device_id in device_id_list
                            console.log(device_id)
                            device = $scope.struct.device_tree.all_lut[device_id]
                            console.log(device)

                            salt_device(device, data[device.idx])

                        $scope.struct.data_loaded = true
                        $scope.struct.device_ids_needing_refresh.length = 0
                )
        )

    perform_refresh(false)

    salt_device = (device, device_hints) ->
        device.$$date_created = moment(device.date).format("YYYY-MM-DD HH:mm:ss")

        info_not_available_class = "alert-danger"
        info_not_available_text = "Not Available"
        info_available_class = "alert-success"
        info_available_text = "Available"

        info_list_names = [
            ["monitoring_checks", 25],
            ["location_data", 25],
            ["asset_data", 25]
            ["graphing_data", 25]
        ]

        device.$$overview_completion_percentage = 0

        for obj in info_list_names
            info_list_name = obj[0]
            weight = obj[1]

            device["$$" + info_list_name + "_availability_class"] = info_not_available_class
            device["$$" + info_list_name + "_availability_text"] = info_not_available_text

            if device_hints[info_list_name] > 0
                device["$$" + info_list_name + "_availability_class"] = info_available_class
                device["$$" + info_list_name + "_availability_text"] = info_available_text

                device.$$overview_completion_percentage += weight

    $scope.open_in_new_tab = (device, setup_type) ->
        if setup_type == 0
            heading = "Monitoring Checks"
        else if setup_type == 1
            heading = "Location Data"
        else if setup_type == 2
            heading = "Asset Data"

        o = {
            type: setup_type
            heading: heading + " (" + device.name + ")"
            device_id: device.idx
        }

        for tab in $scope.struct.tabs
            if tab.device_id == o.device_id && tab.heading == o.heading
                return

        $scope.struct.tabs.push(o)

    $scope.close_tab = (to_be_closed_tab) ->
        $timeout(
            () ->
                tabs_tmp = []

                for tab in $scope.struct.tabs
                    if tab != to_be_closed_tab
                        tabs_tmp.push(tab)
                $scope.struct.tabs.length = 0
                for tab in tabs_tmp
                    $scope.struct.tabs.push(tab)

                if tabs_tmp.length == 0
                    $scope.perform_lazy_refresh()
            0
        )

    $scope.perform_lazy_refresh = () ->
        perform_refresh(true)

    $scope.mark_unfresh = (tab) ->
        $scope.struct.device_ids_needing_refresh.push(tab.device_id)

])