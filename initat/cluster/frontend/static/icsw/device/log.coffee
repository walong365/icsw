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

device_logs = angular.module(
    "icsw.device.log",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select"
    ]
).config(["icswRouteExtensionProvider", (icswRouteExtensionProvider) ->
    icswRouteExtensionProvider.add_route("main.devicelog")
]).directive("icswDeviceLog",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.log")
        controller: "icswDeviceLogCtrl"
        scope: true
    }
]).controller("icswDeviceLogCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "$q", "$uibModal", "blockUI", "DeviceOverviewService"
    "icswTools", "icswSimpleAjaxCall", "ICSW_URLS", "$timeout"
(
    $scope, $compile, $filter, $templateCache, $q, $uibModal, blockUI, DeviceOverviewService
    icswTools, icswSimpleAjaxCall, ICSW_URLS, $timeout
) ->
    $scope.struct = {
        data_loaded: false
        log_entries: []
        devices: []
        tabs: []
        activetab: 0
        device_lut: {}
        log_lut: {}

        websocket: undefined
    }

    info_not_available_class = "alert-danger"
    info_available_class = "alert-success"
    info_warning_class = "alert-warning"

    $scope.struct.websocket = new WebSocket("ws://" + window.location.host.split(":")[0] + ":8443" + "/device_log_entries/")

    $scope.struct.websocket.onmessage = (data) ->
        console.log(data)
        json_dict = JSON.parse(data.data)
        if $scope.struct.device_lut[json_dict.device] != undefined && $scope.struct.log_lut[json_dict.idx] == undefined
            $scope.struct.log_lut[json_dict.idx] = true

            $timeout(
                () ->
                    $scope.struct.device_lut[json_dict.device].$$device_log_entries_count += 1
                    $scope.struct.device_lut[json_dict.device].$$device_log_entries_bg_color_class = info_available_class
                0
            )

    $scope.new_devsel = (devices) ->
        icswSimpleAjaxCall(
            {
                url: ICSW_URLS.DEVICE_DEVICE_LOG_ENTRY_COUNT
                data:
                    device_pks: (dev.idx for dev in devices)
                dataType: "json"
            }
        ).then((result) ->
            $scope.struct.devices.length = 0

            for device in devices
                if !device.is_meta_device
                    $scope.struct.device_lut[device.idx] = device

                    device.$$device_log_entries_count = 0
                    device.$$device_log_entries_bg_color_class = info_warning_class
                    if result[device.idx] != undefined && result[device.idx] > 0
                        device.$$device_log_entries_count = result[device.idx]
                        device.$$device_log_entries_bg_color_class = info_available_class

                    $scope.struct.devices.push(device)

            $scope.struct.data_loaded = true
        )

    $scope.show_device = ($event, dev) ->
        DeviceOverviewService($event, [dev])

    $scope.open_in_new_tab = (device, $event) ->
        if device.$$device_log_entries_count == 0
            return

        o = {
            device: device
            tabindex: device.idx
            }
        device_in_tablist = false
        for tab in $scope.struct.tabs when tab.device == o.device
            device_in_tablist = true
        if !device_in_tablist
            $scope.struct.tabs.push(o)
        if !$event.ctrlKey
            $timeout(
                () ->
                    $scope.struct.activetab = o.tabindex
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
            0
        )

    $scope.$on("$destroy", () ->
        $scope.struct.websocket.close()
        $scope.struct.websocket = undefined
    )

]).directive("icswDeviceLogTable",
[
    "$q", "$templateCache"
(
    $q, $templateCache
) ->
    return {
        restrict: "E"
        template: $templateCache.get("icsw.device.log.table")
        controller: "icswDeviceLogTableCtrl"
        scope: {
            device: "=icswDevice"
        }
    }
]).controller("icswDeviceLogTableCtrl",
[
    "$q", "Restangular", "ICSW_URLS", "$scope", "icswUserGroupRoleTreeService", "$timeout"
(
    $q, Restangular, ICSW_URLS, $scope, icswUserGroupRoleTreeService, $timeout
) ->

    $scope.struct = {
        user_tree: undefined
        websocket: undefined
    }

    device = $scope.device

    device.$$device_log_entries_list = []
    device.$$device_log_entries_lut = {}

    perform_refresh = () ->
        $q.all(
            [
                Restangular.all(ICSW_URLS.DEVICE_DEVICE_LOG_ENTRY_LIST.slice(1)).getList(
                    {
                        device_pks: angular.toJson([device.idx])
                        high_idx: 0
                    }
                )
                icswUserGroupRoleTreeService.load($scope.$id)
            ]
            ).then((result) ->
                $scope.struct.user_tree = result[1]
                for log_entry in result[0]
                    log_entry.pretty_date = moment(log_entry.date).format("YYYY-MM-DD HH:mm:ss")
                    log_entry.user_resolved = "N/A"
                    if log_entry.user != null
                        log_entry.user_resolved = result[1].user_lut[log_entry.user].$$long_name

                    device.$$device_log_entries_list.push(log_entry)
                    if log_entry.idx > high_idx
                        high_idx = log_entry.idx

                    device.$$device_log_entries_lut[log_entry.idx] = log_entry

                $scope.struct.websocket = new WebSocket("ws://" + window.location.host.split(":")[0] + ":8443" + "/device_log_entries/")

                $scope.struct.websocket.onmessage = (data) ->
                    json_dict = JSON.parse(data.data)
                    if json_dict.device == device.idx && device.$$device_log_entries_lut[json_dict.idx] == undefined
                        new_log_entry = {}

                        new_log_entry.idx = json_dict.idx
                        new_log_entry.pretty_date = moment(json_dict.date).format("YYYY-MM-DD HH:mm:ss")
                        new_log_entry.user_resolved = "N/A"
                        if json_dict.user != null
                            log_entry.user_resolved = $scope.struct.user_tree.user_lut[json_dict.user].$$long_name

                        new_log_entry.source = {}
                        new_log_entry.source.identifier = json_dict.source
                        new_log_entry.level = {}
                        new_log_entry.level.name = json_dict.level
                        new_log_entry.text = json_dict.text

                        device.$$device_log_entries_lut[new_log_entry.idx] = new_log_entry

                        $timeout(
                            () ->
                                device.$$device_log_entries_list.push(new_log_entry)
                            0
                        )
            )
    perform_refresh()

    $scope.$on("$destroy", () ->
        $scope.struct.websocket.close()
        $scope.struct.websocket = undefined
    )
])