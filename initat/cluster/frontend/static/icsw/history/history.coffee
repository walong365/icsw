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
    "icsw.history",
    [
    ]
).directive("icswHistoryOverview", ['icswHistoryDataService', (icswHistoryDataService) ->
    return  {
        restrict: 'EA'
        templateUrl: 'icsw.history.overview'
        link: (scope, el, attrs) ->
            icswHistoryDataService.add_to_scope(scope)
            scope.selected_model = 'device'
            scope.$watch(
                () -> Object.keys(icswHistoryDataService.models_with_history).length
                () ->
                    l = []
                    if icswHistoryDataService.models_with_history? and icswHistoryDataService.models_with_history.plain?
                        for k, v of icswHistoryDataService.models_with_history.plain()
                            l.push([v, k])
                    l.sort()
                    scope.models_with_history_sorted = l
            )
    }
]).directive("icswHistoryModelHistory", ["$injector", "icswHistoryDataService", ($injector,icswHistoryDataService) ->
    return {
        restrict: 'EA'
        templateUrl: 'icsw.history.model_history'
        scope: {
            model: '&'
        }
        link: (scope, el, attrs) ->
            icswHistoryDataService.add_to_scope(scope)
            scope.$watch(
                () -> scope.model(),
                (new_val) ->
                    if scope.model()?
                        icswHistoryDataService.get_historic_data(scope.model()).then((new_data) ->
                            scope.entries = new_data
                            scope.column_visible = {}
                    )
            )
            scope.format_value = (val) ->
                if angular.isArray(val)
                    return val.join(", ")
                else
                    return val

            #scope.get_last_entry_before = (idx, position) ->
            #    if position > 0
            #        for i in [(position-1)..0]
            #            if scope.entries[i].data.pk == idx
            #                return scope.entries[i]
            #    return undefined
            #scope.last_entry_different = (idx, position, key) ->
            #    last_entry = scope.get_last_entry_before(idx, position)
            #    if last_entry?
            #        # angular.equals supports comparing lists as python would
            #        different = !angular.equals(last_entry.data[key], scope.entries[position].data[key])
            #        if different
            #            scope.column_visible[key] = true
            #        return different
            #    else
            #        return false
    }
]).service("icswHistoryDataService", ["Restangular", "ICSW_URLS", "$rootScope", (Restangular, ICSW_URLS, $rootScope) ->
    get_historic_data = (model_name) ->
        return Restangular.all(ICSW_URLS.SYSTEM_GET_HISTORICAL_DATA.slice(1)).getList({'model': model_name})

    user = Restangular.all(ICSW_URLS.REST_USER_LIST.slice(1)).getList().$object
    models_with_history = Restangular.all(ICSW_URLS.SYSTEM_GET_MODELS_WITH_HISTORY.slice(1)).customGET().$object
    get_user_by_idx = (idx) -> return _.find(user, (elem) -> return elem.idx == idx)

    return {
        get_historic_data:  get_historic_data
        models_with_history:  models_with_history
        user:  user
        get_user_by_idx: get_user_by_idx
        add_to_scope: (scope) ->
            scope.user = user
            scope.models_with_history = models_with_history
            scope.get_user_by_idx = get_user_by_idx
    }
])
