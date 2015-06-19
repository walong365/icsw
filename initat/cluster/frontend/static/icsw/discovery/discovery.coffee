# Copyright (C) 2012-2015 init.at
#
# Send feedback to: <mallinger@init.at>
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
    "icsw.discovery",
    [
    ]
).directive("icswDiscoveryOverview", ['icswDiscoveryDataService', (icswDiscoveryDataService) ->
    return  {
        restrict: 'EA'
        templateUrl: 'icsw.discovery.overview'
        link: (scope, el, attrs) ->
            scope.data = icswDiscoveryDataService
    }
]).service("icswDiscoveryDataService", ["Restangular", "ICSW_URLS", "$rootScope", (Restangular, ICSW_URLS, $rootScope) ->
    rest_map = {
        dispatch_setting: ICSW_URLS.REST_DISCOVERY_DISPATCH_SETTING_LIST.slice(1)
        device: ICSW_URLS.REST_DEVICE_LIST.slice(1)
    }
    data = {}

    for k, url of rest_map
        data[k] = Restangular.all(url).getList().$object
    return data
])

