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
    "icswTools", "icswSimpleAjaxCall", "ICSW_URLS", "Restangular", "icswDeviceTreeService"
(
    $scope, $compile, $filter, $templateCache, $q, $uibModal, blockUI, DeviceOverviewService
    icswTools, icswSimpleAjaxCall, ICSW_URLS, Restangular, icswDeviceTreeService
) ->
    $scope.struct = {
        data_loaded: false

        log_entries: []

        devices: []

        tabs: []
    }

    info_not_available_class = "alert-danger"
    info_available_class = "alert-success"
    info_warning_class = "alert-warning"

    $scope.new_devsel = (devs) ->
        $q.all(
            [
                Restangular.all(ICSW_URLS.DEVICE_DEVICE_LOG_ENTRY_LIST.slice(1)).getList(
                    {
                        device_pks: angular.toJson((dev.idx for dev in devs))
                    }
                )
                icswDeviceTreeService.load($scope.$id)
            ]
        ).then((result) ->
            $scope.struct.devices.length = 0
            $scope.struct.log_entries.length = 0

            dev_lut = {}

            for dev in devs
                if dev.$$device_log_entries_list != undefined
                    dev.$$device_log_entries_list.length = 0
                else
                    dev.$$device_log_entries_list = []

                dev_lut[dev.idx] = dev

            log_entries_per_device = {}

            for log_entry in result[0]
                if log_entries_per_device[log_entry.device] == undefined
                    log_entries_per_device[log_entry.device] = 0
                log_entries_per_device[log_entry.device] += 1

                dev_lut[log_entry.device].$$device_log_entries_list.push(log_entry)

            for dev in devs
                if !dev.is_meta_device
                    $scope.struct.devices.push(dev)
                    dev.$$device_log_entries_count = 0
                    dev.$$device_log_entries_bg_color_class = info_warning_class
                    if log_entries_per_device[dev.idx] != undefined
                        dev.$$device_log_entries_count = log_entries_per_device[dev.idx]
                        dev.$$device_log_entries_bg_color_class = info_available_class

            $scope.struct.data_loaded = true
        )

    $scope.show_device = ($event, dev) ->
        DeviceOverviewService($event, [dev])

    $scope.open_in_new_tab = (device) ->
        if device.$$device_log_entries_count == 0
            return

        o = {
            name: device.full_name
        }

        for tab in $scope.struct.tabs
            if tab.name == o.name
                return

        $scope.struct.tabs.push(o)
])