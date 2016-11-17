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
    "icsw.livestatus.livestatus",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.router",
        "icsw.panel_tools",
    ]
).config(["icswRouteExtensionProvider", (icswRouteExtensionProvider) ->
    icswRouteExtensionProvider.add_route("main.livestatus")
]).controller("icswDeviceLiveStatusCtrl",
[
    "$scope", "$compile", "$templateCache", "Restangular", "icswUserService",
    "$q", "$timeout", "icswTools", "ICSW_URLS", "icswSimpleAjaxCall",
    "icswDeviceLivestatusDataService", "icswCachingCall", "icswLivestatusFilterService",
    "icswDeviceTreeService", "icswMonLivestatusPipeConnector", "$rootScope", "ICSW_SIGNALS",
(
    $scope, $compile, $templateCache, Restangular, icswUserService,
    $q, $timeout, icswTools, ICSW_URLS, icswSimpleAjaxCall,
    icswDeviceLivestatusDataService, icswCachingCall, icswLivestatusFilterService,
    icswDeviceTreeService, icswMonLivestatusPipeConnector, $rootScope, ICSW_SIGNALS
) ->
    # top level controller of monitoring dashboard

    _cd = {
        "test": {
            "icswLivestatusSelDevices": [{
                "icswLivestatusDataSource": [{
                    "icswLivestatusFilterService": [{
                        "icswLivestatusMonCategoryFilter": [{
                            "icswLivestatusDeviceCategoryFilter": [{
                                "icswLivestatusMonTabularDisplay": []
                                # "icswLivestatusLocationMap": []
                            }
                            {
                                "icswLivestatusDeviceTabularDisplay": []
                                # "icswLivestatusGeoLocationDisplay": []
                            }
                            {
                                "icswLivestatusInfoDisplay": []
                            }]
                        }]
                    }]
                }]
            }]
        }
        "btest": {
            "icswLivestatusSelDevices": [{
                "icswLivestatusDataSource": [{
                    "icswLivestatusFilterService": [{
                        "icswLivestatusLocationDisplay": []
                    }
                    {
                        "icswLivestatusMonCategoryFilter": [{
                            "icswLivestatusMapDisplay": []
                        }]
                    }
                    {
                        "icswLivestatusFilterService": [{
                            "icswLivestatusMonTabularDisplay": []
                        }
                            {
                                "icswLivestatusMonTabularDisplay": []
                            }]
                    }]
                }
                {
                    "icswLivestatusFilterService": [{
                        "icswLivestatusFullBurst": [{
                            "icswLivestatusMonTabularDisplay": []
                        }
                            {
                                "icswLivestatusFullBurst": []
                            }]
                    }]
                }
                {
                    "icswLivestatusFilterService": [{
                        "icswLivestatusLocationDisplay": []
                    }]
                }]
            }]
        }
        "nettop": {
            "icswLivestatusSelDevices": [{
                "icswLivestatusDataSource": [{
                    "icswLivestatusFilterService": [{
                        "icswLivestatusTopologySelector": [{
                            "icswLivestatusFilterService": [{
                                "icswLivestatusNetworkTopology": []
                            }]
                        }
                        {
                            "icswLivestatusNetworkTopology": []
                        }]
                    }]
                }]
            }]
        }
        "location": {
            "icswLivestatusSelDevices": [{
                "icswLivestatusDataSource": [{
                    "icswLivestatusFilterService": [{
                        "icswLivestatusMonCategoryFilter": [{
                            "icswLivestatusDeviceCategoryFilter": [{
                                "icswLivestatusGeoLocationDisplay": []
                            }
                            {
                                "icswLivestatusLocationMap":  []
                            }]
                        }]
                    }]
                }]
            }]
        }
    }

    $scope.struct = {
        connector: null
        connector_set: false
    }

    $scope.unset_connector = () ->
        if $scope.struct.connector_set
            $scope.struct.connector.close()
            $scope.struct.connector_set = false

    $scope.set_connector = (c_name) ->
        $scope.unset_connector()
        icswUserService.load($scope.$id).then(
            (user) ->
                $scope.struct.connector = new icswMonLivestatusPipeConnector(c_name, user, angular.toJson(_cd[c_name]))
                $scope.struct.connector_set = true
        )
    $scope.toggle_gridster_lock = () ->
        $scope.struct.connector.toggle_global_display_state()
        is_unlocked = $scope.struct.connector.global_display_state == 1
        $scope.struct.connector.is_unlocked = is_unlocked
        $scope.struct.connector.gridsterOpts.resizable.enabled = is_unlocked
        $scope.struct.connector.gridsterOpts.draggable.enabled = is_unlocked
        $rootScope.$emit(ICSW_SIGNALS("ICSW_TRIGGER_PANEL_LAYOUTCHECK"))

    $scope.new_devsel = (_dev_sel) ->
        # console.log "nds"
        $scope.struct.connector.new_devsel(_dev_sel)

    $scope.$on("$destroy", () ->
        if $scope.struct.connector
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
        scope:
            active_view: "=icswLivestatusView"
        link: (scope, element, attrs) ->
            scope.$watch(
                "active_view"
                (new_val) ->
                    if new_val?
                        scope.set_connector(new_val)
                    else
                        scope.unset_connector()
            )
    }
])
