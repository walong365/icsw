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
    "icswTools", "icswSimpleAjaxCall", "ICSW_URLS", "$timeout", "icswWebSocketService", "icswUserService",
    "ICSW_ENUMS",
(
    $scope, $compile, $filter, $templateCache, $q, $uibModal, blockUI, DeviceOverviewService
    icswTools, icswSimpleAjaxCall, ICSW_URLS, $timeout, icswWebSocketService, icswUserService,
    ICSW_ENUMS,
) ->
    $scope.struct = {
        data_loaded: false
        devs_present: false
        log_entries: []
        devices: []
        tabs: []
        activetab: 0
        device_lut: {}
        log_lut: {}
        # id of websocket stream callback
        stream_id: ""
    }

    info_available_class = "alert-success"
    info_warning_class = "alert-warning"

    icswUserService.load($scope.$id).then(
        (user) ->
            icswWebSocketService.add_stream(
                ICSW_ENUMS.WSStreamEnum.device_log_entries
                (json_dict) =>
                    if $scope.struct.device_lut[json_dict.device]? and not $scope.struct.log_lut[json_dict.idx]?
                        $scope.struct.log_lut[json_dict.idx] = true
                        $timeout(
                            () ->
                                $scope.struct.device_lut[json_dict.device].$$device_log_entries_count += 1
                                $scope.struct.device_lut[json_dict.device].$$device_log_entries_bg_color_class = info_available_class
                            0
                        )
            ).then(
                (stream_id) ->
                    $scope.struct.stream_id = stream_id
            )
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
                $scope.struct.devs_present = true
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
        if $scope.struct.stream_id
            icswWebSocketService.remove_stream($scope.struct.stream_id)
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
            max_days_per_device: "<icswMaxDaysPerDevice"
        }
    }
]).controller("icswDeviceLogTableCtrl",
[
    "$q", "Restangular", "ICSW_URLS", "$scope", "icswUserGroupRoleTreeService", "$timeout", "icswSimpleAjaxCall",
    "icswWebSocketService", "icswTableFilterService", "icswUserService", "ICSW_ENUMS",
(
    $q, Restangular, ICSW_URLS, $scope, icswUserGroupRoleTreeService, $timeout, icswSimpleAjaxCall,
    icswWebSocketService, icswTableFilterService, icswUserService, ICSW_ENUMS,
) ->

    $scope.struct = {
        # filter
        filter: icswTableFilterService.get_instance()
        # devices present
        devs_present: false
        # data loaded
        data_loaded: false
        user_tree: undefined

        device_log_entries: []
        device_log_entries_lut: {}

        reload_timer: undefined
        device_idxs: []
        device_lut: {}
        # fingerprint of dev idxs
        def_fp: ""
        # max logs per device or 0 for all
        max_days_per_device: 0
        # id of websocket stream callback
        stream_id: ""
    }
    if $scope.max_days_per_device?
        $scope.struct.max_days_per_device = $scope.max_days_per_device
    # init filter

    $scope.struct.filter.add(
        "devices"
        "Select Device"
        (entry, choice) ->
            if not choice.id
                return true
            else
                return entry.device == choice.value
    ).add_choice(0, "All Devices", null, true)

    $scope.struct.filter.add(
        "timeframes"
        "Select timeframe"
        (entry, choice) ->
            if not choice.id
                entry.$$date_from_now = entry.$$mom_date.fromNow(true)
                return true
            else
                _disp = entry.$$mom_date.isAfter(choice.$$compare_date)
                if _disp
                    # update date_from_now
                    entry.$$date_from_now = entry.$$mom_date.fromNow(true)
                return _disp
        (choice) ->
            choice.$$compare_date = moment().subtract(choice.value)
    ).add_choice(
        0, "All times", null, true
    ).add_choice(
        1, "1 day ago", moment.duration(1, "days"), false
    ).add_choice(
        2, "1 hour ago", moment.duration(1, "hours"), false
    ).add_choice(
        3, "30 minutes ago", moment.duration(30, "minutes"), false
    ).add_choice(
        4, "10 minutes ago", moment.duration(10, "minutes"), false
    )

    $scope.struct.filter.add_mult(
        "users"
        "Select User"
        (entry, idx_list) ->
            return entry.user in idx_list
    ).add_choice(0, "No user", null, true)

    $scope.struct.filter.add_mult(
        "sources"
        "Select Source"
        (entry, idx_list) ->
            return entry.source.idx in idx_list
    )

    $scope.struct.filter.add(
        "levels"
        "Select Level"
        (entry, choice) ->
            if not choice.id
                return true
            else
                return entry.level.idx == choice.value
    ).add_choice(0, "All Levels", null, true)

    $scope.struct.filter.notifier.promise.then(
        () ->
        () ->
        () ->
            _update_filter()
    )

    $scope.$watch(
        "device_list"
        (new_val) ->
            new_fp = ("#{dev.idx}" for dev in new_val).join("::")
            if new_fp != $scope.struct.def_fp
                $scope.struct.def_fp = new_fp
                ($scope.struct.filter.get(_en).clear_choices() for _en in ["users", "levels", "devices", "sources"])
                $scope.struct.device_lut = {}
                $scope.struct.device_idxs.length = 0
                for entry in $scope.device_list
                    $scope.struct.device_idxs.push(entry.idx)
                    $scope.struct.device_lut[entry.idx] = entry
                    $scope.struct.filter.get("devices").add_choice(entry.idx, entry.$$print_name, entry.idx, false)
                # filter all device log entries where device_idx is not in device_idxs
                $scope.struct.device_log_entries.length = 0
                if $scope.struct.device_idxs.length
                    $scope.struct.devs_present = true
                else
                    $scope.struct.devs_present = false
                reload()
        true
    )
    _update_filter = () ->
        $scope.struct.filter.filter($scope.struct.device_log_entries)

    update_filter_lists = (device_log_entry) ->
        # only used once
        if device_log_entry.user
            $scope.struct.filter.get("users").add_choice(device_log_entry.user, device_log_entry.user_resolved, device_log_entry.user, false)
        $scope.struct.filter.get("sources").add_choice(device_log_entry.source.idx, device_log_entry.source.identifier, device_log_entry.source.idx, true)
        $scope.struct.filter.get("levels").add_choice(device_log_entry.level.idx, device_log_entry.level.name, device_log_entry.level.idx, false)

    handle_log_entry = (log_entry) ->
        if log_entry.device in $scope.struct.device_idxs and $scope.struct.device_log_entries_lut[log_entry.idx] == undefined
            log_entry.$$mom_date = moment(log_entry.date)
            log_entry.$$pretty_date = log_entry.$$mom_date.format("YYYY-MM-DD HH:mm:ss")
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
                    max_days_per_device: $scope.struct.max_days_per_device
                dataType: "json"
            }
        ).then(
            (result) ->
                if result.length
                    (handle_log_entry(log_entry) for log_entry in result)
                    _update_filter()
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

    reload = () ->
        $q.all(
            [
                icswUserGroupRoleTreeService.load($scope.$id)
                icswSimpleAjaxCall(
                    {
                        url: ICSW_URLS.DEVICE_DEVICE_LOG_ENTRY_LOADER
                        data:
                            device_pks: angular.toJson($scope.struct.device_idxs)
                            excluded_device_log_entry_pks: []
                            max_days_per_device: $scope.struct.max_days_per_device
                        dataType: "json"
                    }
                )
            ]
        ).then(
            (data) ->
                $scope.struct.user_tree = data[0]
                (handle_log_entry(log_entry) for log_entry in data[1])
                # initial load, set default levels

                _update_filter()

                $scope.struct.data_loaded = true

                start_timer()

                icswWebSocketService.add_stream(
                    ICSW_ENUMS.WSStreamEnum.device_log_entries
                    (json_dict) =>
                        $timeout(
                            () ->
                                handle_log_entry(json_dict)
                                _update_filter()
                            0
                        )
                ).then(
                    (stream_id) ->
                        $scope.struct.stream_id = stream_id
                )
        )

    $scope.$on("$destroy", () ->
        if $scope.struct.stream_id
            icswWebSocketService.remove_stream($scope.struct.stream_id)
        stop_timer()
        $scope.struct.filter.close()
    )
])
