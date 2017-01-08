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
    icswTools, icswSimpleAjaxCall, ICSW_URLS, $timeout, icswWebSocketService,
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

    $scope.struct.websocket = icswWebSocketService.register_ws("device_log_entries")

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
        ).then(
            (result) ->
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
            device_list: "=icswDeviceList"
        }
    }
]).controller("icswDeviceLogTableCtrl",
[
    "$q", "Restangular", "ICSW_URLS", "$scope", "icswUserGroupRoleTreeService", "$timeout", "icswSimpleAjaxCall",
    "icswWebSocketService"
(
    $q, Restangular, ICSW_URLS, $scope, icswUserGroupRoleTreeService, $timeout, icswSimpleAjaxCall,
    icswWebSocketService
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

        device_names: ["All Devices"]
        selected_device_name: undefined

        time_frames: [
            {
                string: "All times"
                duration: null
            }
            {
                string: "1 day ago"
                duration: moment.duration(1, "days")
            }
            {
                string: "1 hour ago"
                duration: moment.duration(1, "hours")
            }
            {
                string: "10 minutes ago"
                duration: moment.duration(10, "minutes")
            }
        ]
        selected_time_frame: undefined

        device_log_entries: []
        filtered_device_log_entries: []
        device_log_entries_lut: {}

        reload_timer: undefined
        device_idxs: []
        device_lut: {}
    }

    for entry in $scope.device_list
        $scope.struct.device_idxs.push(entry.idx)
        $scope.struct.device_lut[entry.idx] = entry
        $scope.struct.device_names.push(entry.full_name)

    $scope.update_filter = ($event) ->
        $scope.struct.filtered_device_log_entries.length = 0
        _uname = $scope.struct.selected_username
        if _uname == "All Users"
            _uname = undefined
        _source = $scope.struct.selected_source
        if _source == "All Sources"
            _source = undefined
        _level = $scope.struct.selected_level
        if _level == "All Levels"
            _level = undefined
        _dname = $scope.struct.selected_device_name
        if _dname == "All Devices"
            _dname = undefined
        _duration = $scope.struct.selected_time_frame.duration
        if _duration
            _duration = moment().subtract(_duration)
        for entry in $scope.struct.device_log_entries
            _add = true
            if _uname? and entry.user_resolved != _uname
                _add = false
            if _source? and entry.source.identifier != _source
                _add = false
            if _level? and entry.level.name != _level
                _add = false
            if _dname? and entry.$$full_name != _dname
                _add = false
            if _duration and _add
                _add = entry.$$mom_date.isAfter(_duration)
            if _add
                $scope.struct.filtered_device_log_entries.push(entry)

    update_filter_lists = (device_log_entry) ->
        # only used onee
        if device_log_entry.user_resolved not in $scope.struct.user_names
            $scope.struct.user_names.push(device_log_entry.user_resolved)
        if device_log_entry.source.identifier not in $scope.struct.sources
            $scope.struct.sources.push(device_log_entry.source.identifier)
        if device_log_entry.level.name not in $scope.struct.levels
            $scope.struct.levels.push(device_log_entry.level.name)

    handle_log_entry = (log_entry) ->
        if log_entry.device in $scope.struct.device_idxs and $scope.struct.device_log_entries_lut[log_entry.idx] == undefined
            log_entry.$$mom_date = moment(log_entry.date)
            log_entry.$$pretty_date = log_entry.$$mom_date.format("YYYY-MM-DD HH:mm:ss")
            log_entry.$$date_from_now = log_entry.$$mom_date.fromNow(true)
            if log_entry.user != null
                log_entry.user_resolved = $scope.struct.user_tree.user_lut[log_entry.user].$$long_name
            else
                log_entry.user_resolved = "N/A"
            # salt level
            _lev = log_entry.level.name
            # see create icsw_fixtures, line 395ff
            if _lev == "ok"
                log_entry.$$level_class = "label label-success"
            else if _lev == "warning"
                log_entry.$$level_class = "label label-warn"
            else
                log_entry.$$level_class = "label label-danger"

            log_entry.$$full_name = $scope.struct.device_lut[log_entry.device].full_name

            $scope.struct.device_log_entries.push(log_entry)
            $scope.struct.device_log_entries_lut[log_entry.idx] = log_entry

            update_filter_lists(log_entry)

    reload_data = () ->
        icswSimpleAjaxCall(
            {
                url: ICSW_URLS.DEVICE_DEVICE_LOG_ENTRY_LOADER
                data:
                    device_pks: angular.toJson($scope.struct.device_idxs)
                    excluded_device_log_entry_pks: (entry.idx for entry in $scope.struct.device_log_entries)
                dataType: "json"
            }
        ).then(
            (result) ->
                if result.length
                    (handle_log_entry(log_entry) for log_entry in result)
                    $scope.update_filter()
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

    $q.all(
        [
            icswUserGroupRoleTreeService.load($scope.$id)
            icswSimpleAjaxCall(
                {
                    url: ICSW_URLS.DEVICE_DEVICE_LOG_ENTRY_LOADER
                    data:
                        device_pks: angular.toJson($scope.struct.device_idxs)
                        excluded_device_log_entry_pks: []
                    dataType: "json"
                }
            )
        ]
    ).then(
        (data) ->
            $scope.struct.user_tree = data[0]
            (handle_log_entry(log_entry) for log_entry in data[1])
            # initial load, set default levels
            $scope.struct.selected_username = $scope.struct.user_names[0]
            $scope.struct.selected_source = $scope.struct.sources[0]
            $scope.struct.selected_level = $scope.struct.levels[0]
            $scope.struct.selected_device_name = $scope.struct.device_names[0]
            $scope.struct.selected_time_frame = $scope.struct.time_frames[0]

            $scope.update_filter()

            $scope.struct.data_loaded = true

            start_timer()

            $scope.struct.websocket = icswWebSocketService.register_ws("device_log_entries")
            $scope.struct.websocket.onmessage = (data) ->
                json_dict = angular.fromJson(data.data)
                $timeout(
                    () ->
                        handle_log_entry(json_dict)
                        $scope.update_filter()
                    0
                )
    )

    $scope.$on("$destroy", () ->
        if $scope.struct.websocket?
            $scope.struct.websocket.close()
            $scope.struct.websocket = undefined
        stop_timer()
    )
])
