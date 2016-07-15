# Copyright (C) 2012-2016 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
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
).service('icswLivestatusMonTabularDisplay',
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

]).directive("icswLivestatusMonTableView",
[
    "$templateCache",
(
    $templateCache,
) ->
        return {
            restrict: "EA"
            template: $templateCache.get("icsw.livestatus.mon.table.view")
            controller: "icswLivestatusMonTableCtrl"
            scope: {
                # connect element for pipelining
                con_element: "=icswConnectElement"
            }
            link: (scope, element, attrs) ->
                scope.link(scope.con_element.new_data_notifier)
        }
]).controller("icswLivestatusMonTableCtrl",
[
    "$scope",
(
    $scope,
) ->
    $scope.struct = {
        # monitoring data
        monitoring_data: undefined
    }
    $scope.link = (notifier) ->
        notifier.promise.then(
            (resolve) ->
            (rejected) ->
            (data) ->
                $scope.struct.monitoring_data = data
        )
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

]).directive("icswLivestatusDeviceTableView",
[
    "$templateCache",
(
    $templateCache,
) ->
        return {
            restrict: "EA"
            template: $templateCache.get("icsw.livestatus.device.table.view")
            controller: "icswLivestatusDeviceTableCtrl"
            scope: {
                # connect element for pipelining
                con_element: "=icswConnectElement"
            }
            link: (scope, element, attrs) ->
                scope.link(scope.con_element.new_data_notifier)
        }
]).controller("icswLivestatusDeviceTableCtrl",
[
    "$scope",
(
    $scope,
) ->
    $scope.struct = {
        # monitoring data
        monitoring_data: undefined
    }
    $scope.link = (notifier) ->
        notifier.promise.then(
            (resolve) ->
            (rejected) ->
            (data) ->
                $scope.struct.monitoring_data = data
        )
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
