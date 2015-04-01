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
).directive("icswHistoryOverview", [() ->
    return  {
        restrict: 'EA'
        templateUrl: 'icsw.history.overview'
    }
]).directive("icswHistoryModelHistory", ["$injector", "icswHistoryDataService", ($injector,icswHistoryDataService) ->
    return {
        restrict: 'EA'
        templateUrl: 'icsw.history.model_history'
        scope: {
            model: '@'
        }
        link: (scope, el, attrs) ->
            scope.$watch('model',  () ->
                if scope.model?
                    icswHistoryDataService.get_historic_data(scope.model).then((new_data) ->
                        scope.entries = []
                        scope.column_visible = {}
                        for raw_entry in new_data.plain()
                            meta_obj = {}

                            meta_obj['id'] = raw_entry['history_id']
                            meta_obj['date'] = raw_entry['history_date']
                            meta_obj['type'] = switch raw_entry['history_type']
                                when "+" then "created"
                                when "-" then "deleted"
                                when "~" then "changed"
                            changer = icswHistoryDataService.user[raw_entry['history_user']]
                            meta_obj['user'] = changer.login if changer?

                            for key in ['history_id', 'history_date', 'history_type', 'history_user']
                                delete raw_entry[key]

                            data_obj = raw_entry

                            entry = {meta: meta_obj, data: data_obj}
                            scope.entries.push(entry)
                    )
            )
            scope.get_last_entry_before = (idx, position) ->
                if position > 0
                    for i in [(position-1)..0]
                        if scope.entries[i].data.idx == idx
                            return scope.entries[i]
                return undefined
            scope.last_entry_different = (idx, position, key) ->
                last_entry = scope.get_last_entry_before(idx, position)
                if last_entry?
                    different =  last_entry.data[key] != scope.entries[position].data[key]
                    if different
                        scope.column_visible[key] = true
                    return different
                else
                    return false
    }
]).service("icswHistoryDataService", ["Restangular", "ICSW_URLS", (Restangular, ICSW_URLS) ->
    get_historic_data = (model_name) ->
        return Restangular.all(ICSW_URLS.SYSTEM_GET_HISTORICAL_DATA.slice(1)).getList({'model': model_name})

    user = Restangular.all(ICSW_URLS.REST_USER_LIST.slice(1)).getList().$object

    return {
        get_historic_data:  get_historic_data
        user:  user
    }
])
