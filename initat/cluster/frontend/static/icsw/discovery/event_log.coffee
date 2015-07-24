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
    "icsw.discovery.event_log",
    [
    ]
).directive("icswDiscoveryEventLog",
    ['msgbus', 'Restangular', 'ICSW_URLS', '$timeout', '$q', 'icswCallAjaxService', 'toaster',
     (msgbus, Restangular, ICSW_URLS, $timeout, $q, icswCallAjaxService, toaster) ->
        return  {
            restrict: 'EA'
            templateUrl: 'icsw.discovery.event_log'
            link: (scope, el, attrs) ->
                # this special pk is translated to mean all devices
                scope.ALL_DEVICES_PK = -2

                scope.set_active = (device_pk) ->
                    scope.cur_device_pk = parseInt(device_pk)
                    scope.reload_current_tab(true)  # force

                scope.devices_rest = {}
                scope.device_pks_ordered = []
                scope.device_list_ready = false

                # current mode for each device, e.g. {4: 'ipmi', 55: 'wmi'}
                scope.device_mode = {}

                # show hide column in output
                scope.show_column = {}

                # TODO: if the table is in an ng-if, reinserting it into the dom when the condition becomes try seems to trigger pipe
                _last_table_state = {}

                # misc query parameters which partly depend on mode, hence are not general for all queries
                scope.tab_query_parameters = {}

                _schedule_reload_timeout_promise = undefined
                scope.query_parameter_changed = () ->
                    if _schedule_reload_timeout_promise?
                        $timeout.cancel(_schedule_reload_timeout_promise)

                    init_reload = () ->
                        if _last_table_state[scope.cur_device_pk]?
                            # rest start since we usually get totally different pages
                            _last_table_state[scope.cur_device_pk].pagination.start = 0
                        scope.reload_current_tab()

                    _schedule_reload_timeout_promise = $timeout(init_reload, 350)

                scope.$watch('tab_query_parameters', scope.query_parameter_changed, true)

                scope.new_devsel = (sel) ->
                    scope.device_pks = sel

                    scope.device_tab_active = {}

                    # find data related to devices
                    Restangular.one(ICSW_URLS.DISCOVERY_GET_EVENT_LOG_DEVICE_INFO.slice(1)).get({device_pks: JSON.stringify(scope.device_pks)}).then((new_data)->
                        scope.device_list_ready = true

                        if new_data.error?  # only error response
                            toaster.pop("error", "", new_data.error)
                            scope.error = new_data.error
                        else
                            scope.devices_rest = new_data
                            disabled_devs = []
                            enabled_devs = []

                            first_dev_pk_with_logs = undefined
                            all_occurring_capabilities = []
                            for pk, dev_entry of scope.devices_rest.plain()
                                if dev_entry.capabilities.length > 0
                                    desc = dev_entry.capabilities.join(", ")
                                    enabled_devs.push(pk)
                                    scope.device_mode[pk] = dev_entry.capabilities[0]
                                    all_occurring_capabilities = _.union(all_occurring_capabilities, dev_entry.capabilities)
                                    first_dev_pk_with_logs = first_dev_pk_with_logs || pk
                                else
                                    desc = "N/A"
                                    disabled_devs.push(pk)
                                dev_entry.capabilities_description = desc

                            scope.device_pks_ordered = enabled_devs.concat(disabled_devs)

                            scope.devices_rest[scope.ALL_DEVICES_PK] = {
                                name: "All selected devices"
                                full_name: "All selected devices"
                                capabilities: all_occurring_capabilities
                                capabilities_description: all_occurring_capabilities.join(", ")
                            }

                            if all_occurring_capabilities.length > 0
                                scope.device_mode[scope.ALL_DEVICES_PK] = all_occurring_capabilities[0]
                            scope.no_device_with_logs_selected = all_occurring_capabilities.length == 0
                            if scope.no_device_with_logs_selected
                                scope.device_tab_active['no_device_tab'] = true
                            else
                                scope.device_tab_active[scope.ALL_DEVICES_PK] = true
                    )

                    # pipe() function for each tab
                    scope.server_pagination_pipe = {}

                    # need pipe functions for each tab since they must remember the table state
                    # in order to be able to get updated
                    for device_pk in scope.device_pks.concat([scope.ALL_DEVICES_PK])
                        do (device_pk) ->
                            scope.server_pagination_pipe[device_pk] = (table_state) ->
                                if scope.cur_device_pk?
                                    #console.log 'called w ts', table_state
                                    if !table_state?
                                        table_state = _last_table_state[device_pk]
                                    _last_table_state[device_pk] = table_state
                                    #console.log 'got ok', device_pk, 'table state', table_state
                                    if table_state?
                                        pagination = table_state.pagination

                                        query_parameters = scope.tab_query_parameters[scope.cur_device_pk]
                                        if !query_parameters?
                                            query_parameters = {}

                                        console.log 'pag ', pagination
                                        console.log 'query params ', query_parameters
                                        promise = scope.get_event_log_promise(scope.cur_device_pk, pagination.start, pagination.number, query_parameters)
                                        if promise
                                            do (table_state) ->
                                                promise.then((obj) ->
                                                    console.log 'got obj', obj

                                                    old_reload_observable = scope.entries.reload_observable
                                                    old_grouping_keys = scope.entries.grouping_keys

                                                    scope.entries = obj.entries
                                                    scope.entries.reload_observable = old_reload_observable + 1
                                                    scope.entries.keys = obj.keys_ordered
                                                    scope.entries.total_num = obj.total_num
                                                    scope.entries.grouping_keys = if obj.grouping_keys? then obj.grouping_keys else old_grouping_keys
                                                    scope.entries.mode_specific_parameters = obj.mode_specific_parameters
                                                    scope.entries.is_loading = false

                                                    table_state.pagination.numberOfPages = Math.ceil(obj.total_num / pagination.number)
                                                )

                _last_query_parameters = undefined
                scope.reload_current_tab = (force) ->
                    if force
                        _last_query_parameters = undefined
                    if scope.cur_device_pk?
                        scope.server_pagination_pipe[scope.cur_device_pk]()

                xhr = {}
                # actually contact server
                scope.get_event_log_promise = (device_pk, skip, limit, query_parameters) ->
                    query_parameters = angular.copy(query_parameters)
                    for key in Object.keys(query_parameters)
                        if query_parameters[key] == ""
                            # empty means no restriction
                            delete query_parameters[key]

                    if parseInt(device_pk) == scope.ALL_DEVICES_PK
                        device_pks_request = JSON.stringify(parseInt(pk) for pk in scope.device_pks_ordered)
                    else
                        device_pks_request = JSON.stringify([parseInt(device_pk)])

                    rest_params = {
                        device_pks: device_pks_request
                        query_parameters: JSON.stringify(query_parameters)
                        mode: scope.device_mode[device_pk]
                        pagination_skip: skip
                        pagination_limit: limit
                    }

                    console.log 'cmp', _last_query_parameters, rest_params
                    if !_.isEqual(_last_query_parameters, rest_params)
                        _last_query_parameters = angular.copy(rest_params)
                        scope.entries.is_loading = true
                        console.log 'really doing query'
                        defer = $q.defer()
                        if xhr.cur_request?
                            xhr.cur_request.abort()
                        xhr.cur_request = icswCallAjaxService
                            url  : ICSW_URLS.DISCOVERY_GET_EVENT_LOG
                            data : rest_params
                            dataType  : 'json'
                            success   : (json) ->
                                defer.resolve(json)
                        return defer.promise
                    else
                        console.log 'no query, disregarding'
                        return null

                scope.entries = []
                scope.entries.is_loading = false
                scope.entries.reload_observable = 0
        }
]).directive("icswDiscoveryEventLogFilters", [() ->
    restrict: 'E'
    templateUrl: 'icsw.discovery.event_log.filters'
    scope: false  # currently writes to tab_query_parameters[device_pk] and may reads some values
]).directive("icswDiscoveryEventLogTableBody", [() ->
    restrict: 'A'
    scope:
        keys: '='
        entries: '='
        columnToggleDict: '='
        show_column: '='
    link: (scope, el, attrs) ->
        rebuild = (new_reload_observable) ->
            el.empty()

            for entry in scope.entries
                tr = angular.element("<tr/>")

                for key in scope.keys
                    if !scope.columnToggleDict? or scope.columnToggleDict[key]
                        if entry[key]?
                            if angular.isArray(entry[key])
                                td = angular.element("<td>#{entry[key].join("<br />")}</td>")
                            else
                                td = angular.element("<td>#{entry[key]}</td>")
                        else
                            td = angular.element("<td />")
                        tr.append(td)

                el.append(tr)

        scope.$watch('entries.reload_observable', rebuild)
        scope.$watch('columnToggleDict', rebuild, true)
])

###
.service("icswDiscoveryEventLogDataService", ["Restangular", "ICSW_URLS", "$rootScope", "$q", (Restangular, ICSW_URLS, $rootScope, $q) ->
    rest_map = {
    }
    data = {
        reload_observable: 0
    }

    # TODO: create general service with this pattern

    promises = []
    for name, url of rest_map
        data[name] = []

        defer = $q.defer()
        promises.push defer.promise
        do (name, defer) ->
            Restangular.all(url).getList().then((new_data) ->
                defer.resolve([name, new_data])
            )

    $q.all(promises).then((all_new_data) ->
        for entry in all_new_data
            [name, new_data] = entry
            data[name] = new_data

        data.reload_observable += 1
    )

    return data
])
###
