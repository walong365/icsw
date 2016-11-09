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

setup_progress = angular.module(
    "icsw.setup.progress",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select"
    ]
).config(["icswRouteExtensionProvider", (icswRouteExtensionProvider) ->
    icswRouteExtensionProvider.add_route("main.setupprogress")
]).directive("icswSetupProgress",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.setup.progress")
        controller: "icswSetupProgressCtrl"
        scope: true
    }
]).controller("icswSetupProgressCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "$q", "$uibModal", "blockUI",
    "icswTools", "icswSimpleAjaxCall", "ICSW_URLS", "icswAssetHelperFunctions",
    "icswDeviceTreeService", "$timeout", "DeviceOverviewService", "icswUserGroupRoleTreeService",
    "icswToolsSimpleModalService"
(
    $scope, $compile, $filter, $templateCache, $q, $uibModal, blockUI,
    icswTools, icswSimpleAjaxCall, ICSW_URLS, icswAssetHelperFunctions,
    icswDeviceTreeService, $timeout, DeviceOverviewService, icswUserGroupRoleTreeService,
    icswToolsSimpleModalService
) ->
    $scope.struct = {
        # selected devices
        devices: []
        # device tree
        device_tree: undefined
        ugr_tree: undefined
        data_loaded: false

        devices: []
        device_ids_needing_refresh: []

        tabs: []

        reload_timer: undefined

        active_tab_index: 0

        system_completion: 0
        devices_availability_class: "alert-danger"
        devices_availability_text: "Not Available"

        monitoring_checks_availability_class: "alert-danger"
        monitoring_checks_availability_text: "Not Available"

        users_availability_class: "alert-danger"
        users_availability_text: "Not Available"

        location_availability_class: "alert-danger"
        location_availability_text: "Not Available"

        show_extended_information_button_value: "Off"
        show_extended_information_button_class: "btn btn-default"
        show_extended_information_button_enabled: false
    }

    info_not_available_class = "alert-danger"
    info_not_available_text = "Not Available"
    info_available_class = "alert-success"
    info_available_text = "Available"
    info_warning_class = "alert-warning"
    info_warning_text = "In Progress..."

    start_timer = (refresh_time) ->
        stop_timer()
        $scope.struct.reload_timer = $timeout(
            () ->
                perform_refresh_for_device_status(true)
            refresh_time
        )

    stop_timer = () ->
        # check if present and stop timer
        if $scope.struct.reload_timer?
            $timeout.cancel($scope.struct.reload_timer)
            $scope.struct.reload_timer = undefined


    $scope.new_devsel = (devs) ->
        $scope.struct.devices.length = 0
        for entry in devs
            if not entry.is_meta_device
                $scope.struct.devices.push(entry)
        perform_refresh_for_device_status(false)
        perform_refresh_for_system_status()

    perform_refresh_for_device_status = (partial_refresh) ->
        console.log("performing_refresh:" + partial_refresh)
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
                icswUserGroupRoleTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.device_tree = data[0]
                $scope.struct.ugr_tree = data[1]

                if partial_refresh
                    device_id_list = (idx for idx in $scope.struct.device_ids_needing_refresh)
                else
                    device_id_list = (device.idx for device in $scope.struct.devices)

                if device_id_list.length > 0
                    icswSimpleAjaxCall(
                        {
                            url: ICSW_URLS.DEVICE_DEVICE_COMPLETION
                            data:
                                device_pks: device_id_list
                            dataType: "json"
                        }
                    ).then(
                        (data) ->
                            $scope.struct.device_ids_needing_refresh.length = 0

                            for device_id in device_id_list
                                device = $scope.struct.device_tree.all_lut[device_id]

                                salt_device(device, data[device.idx])

                            $scope.struct.data_loaded = true
                            if $scope.struct.device_ids_needing_refresh.length > 0
                                start_timer(15000)

                            console.log($scope.struct.device_ids_needing_refresh)
                            console.log("performing_refresh done")
                    )
                else
                    $scope.struct.data_loaded = true
        )

    perform_refresh_for_system_status = () ->
        icswSimpleAjaxCall(
            {
                url: ICSW_URLS.DEVICE_SYSTEM_COMPLETION
                dataType: "json"
            }
        ).then(
            (data) ->
                info_list_names = [
                    ["devices", 25],
                    ["monitoring_checks", 25]
                    ["users", 25]
                    ["locations", 25]
                ]

                $scope.struct.system_completion = 0

                for obj in info_list_names
                    info_list_name = obj[0]
                    weight = obj[1]

                    $scope.struct[info_list_name + "_availability_class"] = info_not_available_class
                    $scope.struct[info_list_name + "_availability_text"] = info_not_available_text


                    if data[info_list_name] > 0
                        $scope.struct[info_list_name + "_availability_class"] = info_available_class
                        $scope.struct[info_list_name + "_availability_text"] = data[info_list_name + "_text"]

                        $scope.struct.system_completion += weight


                console.log(data)
        )

    salt_device = (device, device_hints) ->
        device.$$date_created = moment(device.date).format("YYYY-MM-DD HH:mm:ss")
        if device.creator
            device.$$creator = $scope.struct.ugr_tree.user_lut[device.creator].$$long_name
        else
            device.$$creator = "N/A"

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

            needs_refresh = false

            device["$$" + info_list_name + "_availability_class"] = info_not_available_class
            device["$$" + info_list_name + "_availability_text"] = info_not_available_text
            device["$$" + info_list_name + "_availability_extended_text"] = info_not_available_text
            device["$$" + info_list_name + "_sort_hint"] = 0

            if device_hints[info_list_name] > 0
                device["$$" + info_list_name + "_availability_class"] = info_available_class
                device["$$" + info_list_name + "_availability_text"] = info_available_text
                device["$$" + info_list_name + "_availability_extended_text"] = info_available_text
                device["$$" + info_list_name + "_sort_hint"] = device_hints[info_list_name]

                device.$$overview_completion_percentage += weight

            if device_hints[info_list_name + "_warning"] == true
                device["$$" + info_list_name + "_availability_class"] = info_warning_class
                device["$$" + info_list_name + "_availability_text"] = info_warning_text
                device["$$" + info_list_name + "_availability_extended_text"] = info_available_text
                needs_refresh = true

            if device_hints[info_list_name + "_extended_text"] != undefined
                device["$$" + info_list_name + "_availability_extended_text"] = device_hints[info_list_name + "_extended_text"]

            if device_hints[info_list_name + "_age_in_seconds"] != undefined
                device["$$" + info_list_name + "_sort_hint"] = device_hints[info_list_name + "_age_in_seconds"]

                if device_hints[info_list_name + "_age_in_seconds"] > (60 * 60)
                    device["$$" + info_list_name + "_availability_class"] = info_warning_class
                    device["$$" + info_list_name + "_availability_text"] = "Stale data found..."
                    needs_refresh = true

            if needs_refresh
                $scope.struct.device_ids_needing_refresh.push(device.idx)


    $scope.open_in_new_tab_for_devices = (device, setup_type) ->
        if setup_type == 0
            heading = "Monitoring Checks"
        else if setup_type == 1
            heading = "Location Data"
        else if setup_type == 2
            heading = "Asset Data"
        else if setup_type == 3
            heading = "Graphing Data"

        o = {
            type: setup_type
            heading: heading + " (" + device.name + ")"
            device_id: device.idx
        }

        for tab in $scope.struct.tabs
            if tab.device_id == o.device_id && tab.heading == o.heading
                return

        $scope.struct.tabs.push(o)
        $timeout(
            () ->
                $scope.struct.active_tab_index = $scope.struct.tabs.length + 1
            0
        )


    $scope.open_in_new_tab_for_system = (setup_type) ->
        if setup_type == 4
            heading = "Device Tree"
            special_flag_name = "devices_available"
            special_flag_value = true

            if $scope.struct.devices_availability_class == "alert-danger"
                special_flag_value = false
                heading = "Create new Device"

        else if setup_type == 5
            heading = "Monitoring Checks"
        else if setup_type == 6
            heading = "Users"
        else if setup_type == 7
            heading = "Locations"



        o = {
            type: setup_type
            heading: heading
        }

        if special_flag_name != undefined
            o[special_flag_name] = special_flag_value

        for tab in $scope.struct.tabs
            if tab.heading == o.heading
                return

        $scope.struct.tabs.push(o)
        $timeout(
            () ->
                $scope.struct.active_tab_index = $scope.struct.tabs.length + 1
            0
        )

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
                    perform_refresh_for_device_status(true)
            0
        )


    $scope.mark_unfresh = (tab) ->
        if tab["device_id"] != undefined
            $scope.struct.device_ids_needing_refresh.push(tab.device_id)

    $scope.show_device = ($event, dev) ->
        DeviceOverviewService($event, [dev])

    $scope.setup_graphing = (dev) ->
        f = (_yes) ->
                blockUI.start("Please wait...")
                icswSimpleAjaxCall(
                    {
                        url: ICSW_URLS.DEVICE_SIMPLE_GRAPH_SETUP
                        data:
                            device_pk: dev.idx
                        dataType: "json"
                    }
                ).then(
                    (data) ->
                        $scope.struct.device_ids_needing_refresh.push(dev.idx)
                        perform_refresh_for_device_status(true)
                        blockUI.stop()
                )
        if dev.$$graphing_data_availability_class == "alert-danger"
            icswToolsSimpleModalService("Enable graphing for this device? [Requires installed host-monitoring]").then(
                f
                (_no) ->
                    console.log("no")
            )
        else if dev.$$graphing_data_availability_class == "alert-warning"
            icswToolsSimpleModalService("Re-enable graphing for this device? [Requires installed host-monitoring]").then(
                f
                (_no) ->
                    $scope.open_in_new_tab_for_devices(dev, 3)
            )
        else if dev.$$graphing_data_availability_class == "alert-success"
          $scope.open_in_new_tab_for_devices(dev, 3)

    $scope.system_overview_tab_clicked = () ->
        perform_refresh_for_system_status()

    $scope.device_overview_tab_clicked = () ->
        perform_refresh_for_device_status(true)

    $scope.show_extended_information_button_pressed = () ->
        $scope.struct.show_extended_information_button_enabled = !$scope.struct.show_extended_information_button_enabled

        if $scope.struct.show_extended_information_button_enabled
            $scope.struct.show_extended_information_button_value = "On"
            $scope.struct.show_extended_information_button_class = "btn btn-success"
        else
            $scope.struct.show_extended_information_button_value = "Off"
            $scope.struct.show_extended_information_button_class = "btn btn-default"


])