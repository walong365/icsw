# Copyright (C) 2012-2016 init.at
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
    []
).config(["$stateProvider", ($stateProvider) ->
    $stateProvider.state(
        "main.history", {
            url: "/history"
            template: "<icsw-history-overview></icsw-history-overview>"
            data:
                pageTitle: "Database history"
                rights: ["user.snapshots"]
                menuEntry:
                    menukey: "sys"
                    name: "History"
                    icon: "fa-history"
                    ordering: 10
        }
    )
]).directive("icswHistoryOverview", ['icswHistoryDataService', (icswHistoryDataService) ->
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
]).directive("icswHistoryModelHistory", ["icswHistoryDataService", (icswHistoryDataService) ->
    return {
        restrict: 'EA'
        templateUrl: 'icsw.history.model_history'
        scope: {
            model: '&'
            objectId: '&'
            onRevert: '&'
            style: '@'  # 'config', 'history'
        }
        link: (scope, el, attrs) ->
            scope.on_revert_defined = attrs.onRevert
            icswHistoryDataService.add_to_scope(scope)
            scope.$watch(
                () -> [scope.model(), scope.objectId]
                () ->
                    if scope.model()?
                        model_for_callback = scope.model()
                        icswHistoryDataService.get_historic_data(scope.model(), scope.objectId()).then((new_data) ->
                            # loading takes a while, check if the user has changed the selection meanwhile
                            if model_for_callback == scope.model()
                                # don't show empty changes
                                scope.entries = (entry for entry in new_data when entry.meta.type != 'modified' || Object.keys(entry.changes).length > 0)
                                # NOTE: entries must be in chronological, earliest first
                    )
                true
            )
            scope.format_value = (val) ->
                if angular.isArray(val)
                    if val.length > 0
                        return val.join(", ")
                    else
                        return "no entries"
                else
                    return val
            scope.get_get_change_list = (limit_entry) ->
                # pass as function such that we don't need to generate everything
                return () ->
                    # return in order of original application
                    changes = []
                    for entry in scope.entries
                        changes.push(entry.changes)
                        if entry == limit_entry
                            break
                    return changes
    }
]).service("icswHistoryDataService", ["Restangular", "ICSW_URLS", "$rootScope", (Restangular, ICSW_URLS, $rootScope) ->
    get_historic_data = (model_name, object_id) ->
        params = {
            model: model_name,
            object_id: object_id,
        }
        return Restangular.all(ICSW_URLS.SYSTEM_GET_HISTORICAL_DATA.slice(1)).getList(params)

    user = Restangular.all(ICSW_URLS.REST_USER_LIST.slice(1)).getList().$object
    models_with_history = Restangular.all(ICSW_URLS.SYSTEM_GET_MODELS_WITH_HISTORY.slice(1)).customGET().$object
    get_user_by_idx = (idx) -> return _.find(user, (elem) -> return elem.idx == idx)

    return {
        get_historic_data: get_historic_data
        models_with_history: models_with_history
        user:  user
        get_user_by_idx: get_user_by_idx
        add_to_scope: (scope) ->
            scope.user = user
            scope.models_with_history = models_with_history
            scope.get_user_by_idx = get_user_by_idx
    }
])
