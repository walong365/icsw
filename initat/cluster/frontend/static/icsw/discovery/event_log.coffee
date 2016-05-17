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
    "icsw.discovery.event_log",
    [
    ]
).config(["$stateProvider", ($stateProvider) ->
    $stateProvider.state(
        "main.eventlog", {
            url: "/eventlog"
            template: '<icsw-discovery-event-log icsw-sel-man="0" icsw-sel-man-mode="d"></icsw-discovery-event-log>'
            icswData:
                pageTitle: "Syslog, WMI- und IPMI-Event logs"
                licenses: ["discovery_server"]
                rights: ["device.discovery_server"]
                menuHeader:
                    key: "stat"
                    name: "Status"
                    icon: "fa-line-chart"
                    ordering: 50
                menuEntry:
                    menukey: "stat"
                    name: "Syslog, WMI- and IPMI-Event logs"
                    icon: "fa-list-alt"
                    ordering: 100
        }
    )
]).controller("icswDiscoveryEventCtrl",
[
    "$scope", 'Restangular', 'ICSW_URLS', '$timeout', '$q', 'icswSimpleAjaxCall', 'toaster',
(
    $scope, Restangular, ICSW_URLS, $timeout, $q, icswSimpleAjaxCall, toaster
) ->
    # this special pk is translated to mean all devices

    ALL_DEVICES_PK = -2

    # show hide column in output
    $scope.show_column = {}

    # TODO: if the table is in an ng-if, reinserting it into the dom when the condition becomes true seems to trigger pipe
    _last_table_state = {}

    # misc query parameters which partly depend on mode, hence are not general for all queries
    $scope.tab_query_parameters = {}

    _schedule_reload_timeout_promise = undefined
    $scope.query_parameter_changed = () ->
        if _schedule_reload_timeout_promise?
            $timeout.cancel(_schedule_reload_timeout_promise)

        init_reload = () ->
            if _last_table_state[$scope.cur_device_pk]?
                # rest start since we usually get totally different pages
                _last_table_state[$scope.cur_device_pk].pagination.start = 0
            $scope.reload_current_tab()

        _schedule_reload_timeout_promise = $timeout(init_reload, 350)

    $scope.$watch('tab_query_parameters', $scope.query_parameter_changed, true)
    $scope.$watch('struct.timeframe', $scope.query_parameter_changed, true)

    $scope.struct = {
        # loading
        loading: false
        # devices selected
        devices: []
        # device list ready
        device_list_ready: false
        # error
        error: ""
        # devices rest
        devices_rest: {}
        # current mode for each device, e.g. {4: 'ipmi', 55: 'wmi'}
        device_mode: {}
        # device pks ordered
        device_pks_ordered: []
        # all pks
        all_pks_ordered: []
        # active device tabs
        device_tab_active: {}
        # pipe() function for each tab
        server_pagination_pipe: {}
        # entries related stuff
        entries: []
        entries_is_loading: false
        entries_reload_observable: 0
        # timeframe from rrd-graph-timeframe
        timeframe: undefined
    }

    $scope.new_devsel = (sel) ->
        $scope.struct.loading = true
        $scope.struct.devices.length = 0
        for entry in sel
            if not sel.is_meta_device
                $scope.struct.devices.push(entry)

        # find data related to devices
        Restangular.one(ICSW_URLS.DISCOVERY_GET_EVENT_LOG_DEVICE_INFO.slice(1)).get(
            {
                device_pks: angular.toJson(dev.idx for dev in $scope.struct.devices)
            }
        ).then(
            (new_data) ->
                $scope.struct.device_list_ready = true
                if new_data.error?  # only error response
                    toaster.pop("error", "", new_data.error)
                    $scope.struct.error = new_data.error
                else
                    $scope.struct.devices_rest = new_data
                    disabled_devs = []
                    enabled_devs = []

                    first_dev_pk_with_logs = undefined
                    all_occurring_capabilities = []
                    for pk, dev_entry of $scope.struct.devices_rest.plain()
                        if dev_entry.capabilities.length > 0
                            desc = dev_entry.capabilities.join(", ")
                            enabled_devs.push(pk)
                            $scope.struct.device_mode[pk] = dev_entry.capabilities[0]
                            all_occurring_capabilities = _.union(all_occurring_capabilities, dev_entry.capabilities)
                            first_dev_pk_with_logs = first_dev_pk_with_logs || pk
                        else
                            desc = "N/A"
                            disabled_devs.push(pk)
                        dev_entry.capabilities_description = desc

                    $scope.struct.device_pks_ordered = enabled_devs.concat(disabled_devs)
                    $scope.struct.all_pks_ordered = [ALL_DEVICES_PK].concat($scope.struct.device_pks_ordered)

                    $scope.struct.devices_rest[ALL_DEVICES_PK] = {
                        name: "All selected devices"
                        full_name: "All selected devices"
                        capabilities: all_occurring_capabilities
                        capabilities_description: all_occurring_capabilities.join(", ")
                    }

                    if all_occurring_capabilities.length > 0
                        $scope.struct.device_mode[ALL_DEVICES_PK] = all_occurring_capabilities[0]
                    $scope.no_device_with_logs_selected = all_occurring_capabilities.length == 0
                    if $scope.no_device_with_logs_selected
                        $scope.struct.device_tab_active['no_device_tab'] = true
                    else
                        $scope.struct.device_tab_active[ALL_DEVICES_PK] = true
                $scope.struct.loading = false
        )

        # need pipe functions for each tab since they must remember the table state
        # in order to be able to get updated
        for device_pk in (dev.idx for dev in $scope.struct.devices).concat([ALL_DEVICES_PK])
            do (device_pk) ->
                $scope.struct.server_pagination_pipe[device_pk] = (table_state) ->
                    if $scope.cur_device_pk?
                        #console.log 'called w ts', table_state
                        if !table_state?
                            table_state = _last_table_state[device_pk]
                        _last_table_state[device_pk] = table_state
                        #console.log 'got ok', device_pk, 'table state', table_state
                        if table_state?
                            pagination = table_state.pagination

                            query_parameters = $scope.tab_query_parameters[$scope.cur_device_pk]
                            if !query_parameters?
                                query_parameters = {}

                            console.log 'pag ', pagination
                            console.log 'query params ', query_parameters
                            promise = $scope.get_event_log_promise($scope.cur_device_pk, pagination.start, pagination.number, query_parameters)
                            # promise may be zero for unneeded queries
                            do (table_state) ->
                                promise.then(
                                    (obj) ->
                                        console.log 'got obj', obj

                                        old_reload_observable = $scope.struct.entries_reload_observable
                                        old_grouping_keys = $scope.struct.entries.grouping_keys

                                        $scope.struct.entries = obj.entries
                                        $scope.struct.entries_reload_observable = old_reload_observable + 1
                                        $scope.struct.entries.keys = obj.keys_ordered
                                        $scope.struct.entries.total_num = obj.total_num
                                        $scope.struct.entries.grouping_keys = if obj.grouping_keys? then obj.grouping_keys else old_grouping_keys
                                        $scope.struct.entries.mode_specific_parameters = obj.mode_specific_parameters
                                        $scope.struct.entries_is_loading = false

                                        table_state.pagination.numberOfPages = Math.ceil(obj.total_num / pagination.number)
                                    (rej) ->
                                        console.log 'no query, disregarding'
                                )

    $scope.set_active = (device_pk) ->
        $scope.cur_device_pk = parseInt(device_pk)
        $scope.struct.device_tab_active[$scope.cur_device_pk] = true
        $scope.reload_current_tab(true)  # force

    _last_query_parameters = undefined
    $scope.reload_current_tab = (force) ->
        if force
            _last_query_parameters = undefined
        if $scope.cur_device_pk?
            $scope.struct.server_pagination_pipe[$scope.cur_device_pk]()

    xhr = {}
    # actually contact server
    $scope.get_event_log_promise = (device_pk, skip, limit, query_parameters) ->
        # copy from / to 
        query_parameters.from_date = $scope.struct.timeframe.from_date
        query_parameters.to_date = $scope.struct.timeframe.to_date
        query_parameters = angular.copy(query_parameters)
        for key in Object.keys(query_parameters)
            if query_parameters[key] == ""
                # empty means no restriction
                delete query_parameters[key]

        if parseInt(device_pk) == ALL_DEVICES_PK
            device_pks_request = angular.toJson((parseInt(pk) for pk in $scope.struct.device_pks_ordered))
        else
            device_pks_request = angular.toJson([parseInt(device_pk)])

        rest_params = {
            device_pks: device_pks_request
            query_parameters: JSON.stringify(query_parameters)
            mode: $scope.struct.device_mode[device_pk]
            pagination_skip: skip
            pagination_limit: limit
        }

        console.log 'cmp', _last_query_parameters, rest_params
        defer = $q.defer()
        if !_.isEqual(_last_query_parameters, rest_params)
            _last_query_parameters = angular.copy(rest_params)
            $scope.struct.entries_is_loading = true
            console.log 'really doing query', rest_params
            # if xhr.cur_request?
            #     xhr.cur_request.abort()
            icswSimpleAjaxCall(
                url: ICSW_URLS.DISCOVERY_GET_EVENT_LOG
                data: rest_params
                dataType: 'json'
            ).then(
                (json) ->
                    defer.resolve(json)
            )
        else
            defer.reject("no update needed")
        return defer.promise
]).directive("icswDiscoveryEventLog",
[
    'Restangular', 'ICSW_URLS', '$timeout', '$q', 'icswSimpleAjaxCall', 'toaster',
(
    Restangular, ICSW_URLS, $timeout, $q, icswSimpleAjaxCall, toaster
) ->
    return  {
        restrict: 'EA'
        templateUrl: 'icsw.discovery.event_log'
        controller: "icswDiscoveryEventCtrl"
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
        reload: "=reload"
        show_column: '='
    link: (scope, el, attrs) ->
        rebuild = () ->
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

        scope.$watch("reload", rebuild)
        scope.$watch("columnToggleDict", rebuild, true)
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
