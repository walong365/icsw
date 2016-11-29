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
    "icswTools", "icswSimpleAjaxCall", "ICSW_URLS", "$timeout", "icswWebSocketService",
(
    $scope, $compile, $filter, $templateCache, $q, $uibModal, blockUI, DeviceOverviewService
    icswTools, icswSimpleAjaxCall, ICSW_URLS, $timeout, icswWebsocketService,
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

    info_available_class = "alert-success"
    info_warning_class = "alert-warning"

    $scope.struct.websocket = icswWebsocketService.register_ws("device_log_entries")

    $scope.struct.websocket.onmessage = (data) ->
        json_dict = JSON.parse(data.data)
        if $scope.struct.device_lut[json_dict.device]? and not $scope.struct.log_lut[json_dict.idx]?
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
        if $scope.struct.websocket?
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
    "$q", "Restangular", "ICSW_URLS", "$scope", "icswUserGroupRoleTreeService", "$timeout", "icswSimpleAjaxCall"
(
    $q, Restangular, ICSW_URLS, $scope, icswUserGroupRoleTreeService, $timeout, icswSimpleAjaxCall
) ->

    $scope.struct = {
        data_loaded: false
        user_tree: undefined
        websocket: undefined

        user_names: ['All Users']
        selected_username: undefined

        sources: ['All Sources']
        selected_source: undefined

        levels: ['All Levels']
        selected_level: undefined

        device_log_entries: []
        device_log_entries_lut: {}

        reload_timer: undefined
    }

    $scope.on_selected_user = (username) ->
        if username == 'All Users'
            $scope.struct.selected_username = undefined

    $scope.on_selected_source = (source) ->
        if source == 'All Sources'
            $scope.struct.selected_source = undefined

    $scope.on_selected_level = (level) ->
        if level == 'All Levels'
            $scope.struct.selected_level = undefined


    $scope.is_excluded_obj = (obj) ->
        excluded = false

        if $scope.struct.selected_username != undefined && $scope.struct.selected_username != obj.user_resolved
            excluded = true

        if $scope.struct.selected_source != undefined && $scope.struct.selected_source != obj.source.identifier
            excluded = true

        if $scope.struct.selected_level != undefined && $scope.struct.selected_level != obj.level.name
            excluded = true

        return excluded

    update_filter_lists = (device_log_entry) ->
        if !(device_log_entry.user_resolved in $scope.struct.user_names)
            $scope.struct.user_names.push(device_log_entry.user_resolved)
        if !(device_log_entry.source.identifier in $scope.struct.sources)
            $scope.struct.sources.push(device_log_entry.source.identifier)
        if !(device_log_entry.level.name in $scope.struct.levels)
            $scope.struct.levels.push(device_log_entry.level.name)


    device = $scope.device

    handle_log_entry = (log_entry) ->
        if log_entry.device == device.idx && $scope.struct.device_log_entries_lut[log_entry.idx] == undefined
            log_entry.pretty_date = moment(log_entry.date).format("YYYY-MM-DD HH:mm:ss")
            log_entry.user_resolved = "N/A"
            if log_entry.user != null
                log_entry.user_resolved = result[1].user_lut[log_entry.user].$$long_name

            $scope.struct.device_log_entries.push(log_entry)
            $scope.struct.device_log_entries_lut[log_entry.idx] = log_entry

            update_filter_lists(log_entry)

    reload_data = () ->
        icswSimpleAjaxCall(
            {
                url: ICSW_URLS.DEVICE_DEVICE_LOG_ENTRY_LOADER
                data:
                    device_pk: device.idx
                    excluded_device_log_entry_pks: (entry.idx for entry in $scope.struct.device_log_entries)
                dataType: "json"
            }
        ).then(
            (result) ->
                for log_entry in result
                    handle_log_entry(log_entry)
                start_timer()
        )

    start_timer = () ->
        stop_timer()
        $scope.struct.reload_timer = $timeout(
            () ->
                reload_data()
            15000
        )

    stop_timer = () ->
        # check if present and stop timer
        if $scope.struct.reload_timer?
            $timeout.cancel($scope.struct.reload_timer)
            $scope.struct.reload_timer = undefined

    icswUserGroupRoleTreeService.load($scope.$id).then((result) ->
        $scope.struct.user_tree = result

        icswSimpleAjaxCall(
            {
                url: ICSW_URLS.DEVICE_DEVICE_LOG_ENTRY_LOADER
                data:
                    device_pk: device.idx
                    excluded_device_log_entry_pks: []
                dataType: "json"
        }).then((result) ->
            for log_entry in result
                handle_log_entry(log_entry)

            $scope.struct.data_loaded = true

            start_timer()

            $scope.struct.websocket = new WebSocket("ws://" + window.location.host + "/icsw/ws/device_log_entries/")
            $scope.struct.websocket.onmessage = (data) ->
                json_dict = JSON.parse(data.data)
                if json_dict.device == device.idx && $scope.struct.device_log_entries_lut[json_dict.idx] == undefined
                    new_log_entry = {}

                    new_log_entry.device = json_dict.device
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

                    $scope.struct.device_log_entries_lut[new_log_entry.idx] = new_log_entry

                    $timeout(
                        () ->
                            $scope.struct.device_log_entries.push(new_log_entry)
                            update_filter_lists(new_log_entry)
                        0
                    )

        )
    )

    $scope.$on("$destroy", () ->
        if $scope.struct.websocket?
            $scope.struct.websocket.close()
            $scope.struct.websocket = undefined
        stop_timer()
    )
])
