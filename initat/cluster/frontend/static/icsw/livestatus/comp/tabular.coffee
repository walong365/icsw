# Copyright (C) 2012-2016 init.at
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
    "icsw.livestatus.comp.tabular",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.router",
    ]
).config(["icswLivestatusPipeRegisterProvider", (icswLivestatusPipeRegsterProvider) ->
    icswLivestatusPipeRegsterProvider.add("icswLivestatusMonTabularDisplay", true)
    icswLivestatusPipeRegsterProvider.add("icswLivestatusDeviceTabularDisplay", true)
]).service('icswLivestatusMonTabularDisplay',
[
    "$q", "icswMonLivestatusPipeBase", "icswMonitoringResult",
(
    $q, icswMonLivestatusPipeBase, icswMonitoringResult,
) ->
    class icswLivestatusMonTabularDisplay extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusMonTabularDisplay", true, false)
            @set_template(
                '<icsw-livestatus-mon-table-view icsw-connect-element="con_element"></icsw-livestatus-mon-table-view>'
                "ServiceTabularDisplay"
                10
                10
            )
            @new_data_notifier = $q.defer()

        new_data_received: (data) ->
            @new_data_notifier.notify(data)

        pipeline_reject_called: (reject) ->
            @new_data_notifier.reject("end")

        restore_settings: (settings) ->
            # store settings
            @_settings = settings

]).directive("icswLivestatusMonTableView",
[
    "$templateCache",
(
    $templateCache,
) ->
        return {
            restrict: "EA"
            template: $templateCache.get("icsw.livestatus.mon.table.view")
            controller: "icswLivestatusDeviceMonTableCtrl"
            scope: {
                # connect element for pipelining
                con_element: "=icswConnectElement"
            }
            link: (scope, element, attrs) ->
                scope.link(scope.con_element, scope.con_element.new_data_notifier)
        }
]).controller("icswLivestatusDeviceMonTableCtrl",
[
    "$scope", "DeviceOverviewSelection", "DeviceOverviewService",
(
    $scope, DeviceOverviewSelection, DeviceOverviewService,
) ->
    $scope.struct = {
        # monitoring data
        monitoring_data: undefined
        # connection element
        con_element: undefined
        # settings
        settings: {
            "pag": {}
            "columns": {}
        }
    }
    $scope.link = (con_element, notifier) ->
        $scope.struct.con_element = con_element
        if $scope.struct.con_element._settings?
            $scope.struct.settings = angular.fromJson($scope.struct.con_element._settings)
            if "pag" of $scope.struct.settings
                $scope.pagination_settings = $scope.struct.settings["pag"]
            if "columns" of $scope.struct.settings
                $scope.columns_from_settings = $scope.struct.settings["columns"]
        notifier.promise.then(
            (resolve) ->
            (rejected) ->
            (data) ->
                $scope.struct.monitoring_data = data
        )
    
    $scope.show_device = ($event, dev_check) ->
        DeviceOverviewSelection.set_selection([dev_check.$$icswDevice])
        DeviceOverviewService($event)

    $scope.pagination_changed = (pag) ->
        if not pag?
            return $scope.struct.settings["pag"]
        else
            $scope.struct.settings["pag"] = pag
            $scope.struct.con_element.pipeline_settings_changed(angular.toJson($scope.struct.settings))

    $scope.columns_changed = (col_setup) ->
        $scope.struct.settings["columns"] = col_setup
        $scope.struct.con_element.pipeline_settings_changed(angular.toJson($scope.struct.settings))

]).directive("icswLivestatusMonTableRow",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.livestatus.mon.table.row")
    }
]).service('icswLivestatusDeviceTabularDisplay',
[
    "$q", "icswMonLivestatusPipeBase", "icswMonitoringResult",
(
    $q, icswMonLivestatusPipeBase, icswMonitoringResult,
) ->
    class icswLivestatusDeviceTabularDisplay extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusDeviceTabularDisplay", true, false)
            @set_template(
                '<icsw-livestatus-device-table-view icsw-connect-element="con_element"></icsw-livestatus-device-table-view>'
                "DeviceTabularDisplay"
                10
                10
            )
            @new_data_notifier = $q.defer()

        new_data_received: (data) ->
            @new_data_notifier.notify(data)

        pipeline_reject_called: (reject) ->
            @new_data_notifier.reject("end")

        restore_settings: (settings) ->
            # store settings
            @_settings = settings

]).directive("icswLivestatusDeviceTableView",
[
    "$templateCache",
(
    $templateCache,
) ->
        return {
            restrict: "EA"
            template: $templateCache.get("icsw.livestatus.device.table.view")
            controller: "icswLivestatusDeviceMonTableCtrl"
            scope: {
                # connect element for pipelining
                con_element: "=icswConnectElement"
            }
            link: (scope, element, attrs) ->
                scope.link(scope.con_element, scope.con_element.new_data_notifier)
        }
]).directive("icswLivestatusDeviceTableRow",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.livestatus.device.table.row")
    }
])
