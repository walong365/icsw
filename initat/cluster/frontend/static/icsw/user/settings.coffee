# Copyright (C) 2012-2015 init.at
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
    "icsw.user.settings",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular"
    ]
).controller("icswUserSettingsCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "$q", "$timeout", "$modal", "$window", "ICSW_URLS",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, $q, $timeout, $modal, $window, ICSW_URLS) ->
        $scope.licenses = []
        wait_list = restDataSource.add_sources([
            [ICSW_URLS.REST_CLUSTER_LICENSE_LIST, {}]
        ])
        $q.all(wait_list).then(
            (data) ->
                $scope.licenses = data[0]
                $scope.lic_lut = _.transform(
                    $scope.licenses
                    (memo, val) ->
                        memo[val.name] = val
                    {}
                )
        )
        $scope.get_lic_class = (lic) ->
            if lic.enabled
                return "btn btn-xs btn-success"
            else
                return "btn btn-xs"
        $scope.get_services = (lic) ->
            # console.log lic, $scope.licenses, lic of $scope.licenses
            if lic of $window.CLUSTER_LICENSE
                return $window.CLUSTER_LICENSE[lic].services
            else
                return []
        $scope.get_service_state = (srv) ->
            if $window.SERVICE_TYPES[srv] ? false
                return "success"
            else
                return "danger"
        $scope.get_lic_value = (lic) ->
            return if lic.enabled then "enabled" else "disabled"
        $scope.change_lic = (lic) ->
            # Restangular.restangularizeElement(null, lic, ICSW_URLS.REST_CLUSTER_LICENSE_DETAIL.slice(1).slice(0, -2))
            lic.enabled = !lic.enabled
            lic.put()
]).directive("icswUserSettingsOverview", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.user.settings.overview")
    }
])
