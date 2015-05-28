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
            icswDiscoveryDataService.add_to_scope(scope)
    }
]).service("icswDiscoveryDataService", ["Restangular", "ICSW_URLS", "$rootScope", (Restangular, ICSW_URLS, $rootScope) ->
    #get_historic_data = (model_name, object_id) ->
    #    params = {
    #        model: model_name,
    #        object_id: object_id,
    #    }
    #    return Restangular.all(ICSW_URLS.SYSTEM_GET_HISTORICAL_DATA.slice(1)).getList(params)

    #user = Restangular.all(ICSW_URLS.REST_USER_LIST.slice(1)).getList().$object
    #models_with_history = Restangular.all(ICSW_URLS.SYSTEM_GET_MODELS_WITH_HISTORY.slice(1)).customGET().$object
    #get_user_by_idx = (idx) -> return _.find(user, (elem) -> return elem.idx == idx)

    #return {
    #    get_historic_data: get_historic_data
    #    models_with_history: models_with_history
    #    user:  user
    #    get_user_by_idx: get_user_by_idx
    #    add_to_scope: (scope) ->
    #        scope.user = user
    #        scope.models_with_history = models_with_history
    #        scope.get_user_by_idx = get_user_by_idx
    #}
])
