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
            icswData:
                pageTitle: "Database history"
                rights: ["user.snapshots"]
                menuEntry:
                    menukey: "sys"
                    name: "History"
                    icon: "fa-history"
                    ordering: 10
        }
    )
]).directive("icswHistoryOverview",
[
    'icswHistoryDataService',
(
    icswHistoryDataService
) ->
    return  {
        restrict: 'EA'
        templateUrl: 'icsw.history.overview'
        link: (scope, el, attrs) ->
            scope.struct = {
                loading: true
                models_with_history_sorted: []
                selected_model: "device"
            }
            icswHistoryDataService.get_models_with_history().then(
                (data) ->
                    _list = []
                    for key, value of data.plain()
                        _list.push([value, key])
                    _list.sort()
                    scope.struct.models_with_history_sorted = _list
                    scope.struct.loading = false
            )
    }
]).service("icswHistoryDataService",
[
    "Restangular", "ICSW_URLS", "$rootScope", "$q",
(
    Restangular, ICSW_URLS, $rootScope, $q
) ->
    get_historic_data = (model_name, object_id) ->
        params = {
            model: model_name,
            object_id: object_id,
        }
        return Restangular.all(ICSW_URLS.SYSTEM_GET_HISTORICAL_DATA.slice(1)).getList(params)

    get_models_with_history = () ->
        defer = $q.defer()
        Restangular.all(ICSW_URLS.SYSTEM_GET_MODELS_WITH_HISTORY.slice(1)).customGET().then(
            (data) ->
                defer.resolve(data)
        )
        return defer.promise

    return {
        get_historic_data: get_historic_data
        get_models_with_history: () ->
            return get_models_with_history()
    }
]).directive("icswHistoryModelHistory",
[
    "icswHistoryDataService", "icswUserGroupTreeService",
(
    icswHistoryDataService, icswUserGroupTreeService,
) ->
    return {
        restrict: 'EA'
        templateUrl: 'icsw.history.model_history'
        scope: {
            icsw_model: '=icswModel'
            object_id: '=icswObjectId'
            onRevert: '&'
            style: '@'  # 'config', 'history'
        }
        link: (scope, el, attrs) ->
            scope.struct = {
                loading: false
                entries: []
                num_entries: 0
                # user and group tree
                user_group_tree: undefined
            }
            icswUserGroupTreeService.load(scope.$id).then(
                (tree) ->
                    scope.struct.user_group_tree = tree
            )
            scope.on_revert_defined = attrs.onRevert
            scope.models_with_history = []
            icswHistoryDataService.get_models_with_history().then(
                (data) ->
                    scope.models_with_history = data
            )
            _load_model = () ->
                scope.struct.loading = true
                _model_to_load = scope.icsw_model
                icswHistoryDataService.get_historic_data(_model_to_load, scope.object_id).then(
                    (new_data) ->
                        # loading takes a while, check if the user has changed the selection meanwhile
                        if _model_to_load == scope.icsw_model
                            # don't show empty changes
                            scope.struct.entries.length = 0
                            for entry in new_data
                                if entry.meta.type != "modified" or Object.keys(entry.changes).length > 0
                                    scope.struct.entries.push(entry)
                            scope.struct.num_entries = scope.struct.entries.length
                            scope.struct.loading = false
                        else
                            _load_model()
                )

            scope.$watch("icsw_model", (new_val) ->
                if new_val?
                    if not scope.struct.loading
                        _load_model()
                else
                    scope.struct.entries.length = 0
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
                    for entry in scope.struct.entries
                        changes.push(entry.changes)
                        if entry == limit_entry
                            break
                    return changes
    }
])
