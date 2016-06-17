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
    "icsw.livestatus.livestatus",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.router",
    ]
).config(["$stateProvider", "icswRouteExtensionProvider", ($stateProvider, icswRouteExtensionProvider) ->
    $stateProvider.state(
        "main.livestatus", {
            url: "/livestatus/all"
            template: '<icsw-device-livestatus icsw-sel-man="0"></icsw-device-livestatus>'
            icswData: icswRouteExtensionProvider.create
                pageTitle: "Monitoring dashboard"
                licenses: ["monitoring_dashboard"]
                rights: ["mon_check_command.show_monitoring_dashboard"]
                menuEntry:
                    menukey: "stat"
                    icon: "fa-dot-circle-o"
                    ordering: 20
                dashboardEntry:
                    size_x: 4
                    size_y: 4
        }
    )
]).controller("icswDeviceLiveStatusCtrl",
[
    "$scope", "$compile", "$templateCache", "Restangular",
    "$q", "$timeout", "icswTools", "ICSW_URLS", "icswSimpleAjaxCall",
    "icswDeviceLivestatusDataService", "icswCachingCall", "icswLivestatusFilterService",
    "icswDeviceTreeService", "icswMonLivestatusPipeConnector",
(
    $scope, $compile, $templateCache, Restangular,
    $q, $timeout, icswTools, ICSW_URLS, icswSimpleAjaxCall,
    icswDeviceLivestatusDataService, icswCachingCall, icswLivestatusFilterService,
    icswDeviceTreeService, icswMonLivestatusPipeConnector,
) ->
    # top level controller of monitoring dashboard

    $scope.struct = {
        # connector
        # connector: new icswMonLivestatusPipeConnector("test", angular.toJson({"icswLivestatusDataSource": [{"icswLivestatusFilterService": [{"icswLivestatusCategoryFilter": [{"icswLivestatusFullBurst": []}]}]}]}))
        # connector: new icswMonLivestatusPipeConnector("test", angular.toJson({"icswLivestatusDataSource": [{"icswLivestatusFullBurst": []}]}))
        connector: new icswMonLivestatusPipeConnector(
            "test"
            angular.toJson(
                {
                    "icswLivestatusDataSource": [
                        {
                            "icswLivestatusFilterService": [
                                {
                                    "icswLivestatusLocationDisplay": []
                                }
                                {
                                    "icswLivestatusCategoryFilter": [
                                        {
                                            "icswLivestatusMapDisplay": []
                                        }
                                    ]
                                }
                                {
                                    "icswLivestatusFilterService": [
                                        {
                                            "icswLivestatusTabularDisplay": []
                                        }
                                    ]
                                }
                            ]
                        }
                        {
                            "icswLivestatusFullBurst": [
                                {
                                    "icswLivestatusTabularDisplay": []
                                }
                            ]
                        }
                        {
                            "icswLivestatusFilterService": [
                                {
                                    "icswLivestatusLocationDisplay": []
                                }
                            ]
                        }
                    ]
                }
            )
        )
    }

    $scope.new_devsel = (_dev_sel) ->
        $scope.struct.connector.new_devsel(_dev_sel)

    $scope.$on("$destroy", () ->
        $scope.struct.connector.close()
    )

]).directive("icswDeviceLivestatus",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.livestatus.connect.overview")
        controller: "icswDeviceLiveStatusCtrl"
    }
]).service('icswLivestatusTabularDisplay',
[
    "$q", "icswMonLivestatusPipeBase", "icswMonitoringResult",
(
    $q, icswMonLivestatusPipeBase, icswMonitoringResult,
) ->
    class icswLivestatusTabularDisplay extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusTabularDisplay", true, false)
            @set_template(
                '<icsw-device-livestatus-table-view icsw-connect-element="con_element"></icsw-device-livestatus-table-view>'
                "TabularDisplay"
                6
                10
            )
            @new_data_notifier = $q.defer()

        new_data_received: (data) ->
            @new_data_notifier.notify(data)

        pipeline_reject_called: (reject) ->
            @new_data_notifier.reject("end")

]).directive("icswDeviceLivestatusTableView",
[
    "$templateCache",
(
    $templateCache,
) ->
        return {
            restrict: "EA"
            template: $templateCache.get("icsw.device.livestatus.table.view")
            controller: "icswDeviceLivestatusTableCtrl"
            scope: {
                # connect element for pipelining
                con_element: "=icswConnectElement"
            }
            link: (scope, element, attrs) ->
                scope.link(scope.con_element.new_data_notifier)
        }
]).directive("icswDeviceLivestatusTableRow",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.livestatus.table.row")
    }
]).controller("icswDeviceLivestatusTableCtrl",
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
])
