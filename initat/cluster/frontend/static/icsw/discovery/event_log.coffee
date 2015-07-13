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
    ['msgbus', 'icswDiscoveryEventLogDataService', 'Restangular', 'ICSW_URLS', '$timeout'
     (msgbus, icswDiscoveryEventLogDataService, Restangular, ICSW_URLS, $timeout) ->
        return  {
            restrict: 'EA'
            templateUrl: 'icsw.discovery.event_log'
            link: (scope, el, attrs) ->
                scope.data = icswDiscoveryEventLogDataService

                reload_current_tab = () ->
                    console.log 'reload', scope.tab_query_parameters
                    if scope.cur_device_pk?
                        scope.server_pagination_pipe[scope.cur_device_pk]()

                scope.set_active = (device_pk) ->
                    scope.cur_device_pk = parseInt(device_pk)
                    reload_current_tab()

                scope.devices_rest = {}
                scope.device_pks_ordered = []
                scope.device_list_ready = false

                # current mode for each device, e.g. {4: 'ipmi', 55: 'wmi'}
                scope.device_mode = {}

                # show hide column in output
                scope.show_column = {}

                # need to remember last table state by device tab to be able to call pipe() again
                _last_table_state = {}

                # misc query parameters which partly depend on mode, hence are not general for all queries
                scope.tab_query_parameters = {}

                _schedule_reload_timeout_promise = undefined
                query_parameter_changed = () ->
                    if _schedule_reload_timeout_promise?
                        $timeout.cancel(_schedule_reload_timeout_promise)

                    init_reload = () ->
                        if _last_table_state[scope.cur_device_pk]?
                            _last_table_state[scope.cur_device_pk].pagination.start = 0
                        reload_current_tab()

                    _schedule_reload_timeout_promise = $timeout(init_reload, 350)

                scope.$watch('tab_query_parameters', query_parameter_changed, true)

                scope.new_devsel = (sel) ->
                    scope.device_pks = sel

                    scope.device_tab_active = {}

                    # find data related to devices
                    Restangular.one(ICSW_URLS.DISCOVERY_GET_EVENT_LOG_DEVICE_INFO.slice(1)).get({device_pks: JSON.stringify(scope.device_pks)}).then((new_data)->
                        scope.device_list_ready = true
                        scope.devices_rest = new_data
                        disabled_devs = []
                        enabled_devs = []

                        has_device_with_logs = false
                        first_dev_pk_with_logs = undefined
                        for pk, dev_entry of scope.devices_rest.plain()
                            if dev_entry.capabilities.length > 0
                                desc = dev_entry.capabilities.join(", ")
                                enabled_devs.push(pk)
                                scope.device_mode[pk] = dev_entry.capabilities[0]
                                has_device_with_logs = true
                                first_dev_pk_with_logs = first_dev_pk_with_logs || pk
                            else
                                desc = "N/A"
                                disabled_devs.push(pk)
                            dev_entry.capabilities_description = desc

                        scope.device_pks_ordered = enabled_devs.concat(disabled_devs)

                        scope.no_device_with_logs_selected = !has_device_with_logs
                        if scope.no_device_with_logs_selected
                            scope.device_tab_active['no_device_tab'] = true
                        else
                            scope.device_tab_active[first_dev_pk_with_logs] = true
                    )

                    # pipe() function for each tab
                    scope.server_pagination_pipe = {}


                    do (_last_table_state) ->
                        # need pipe functions for each tab since they must remember the table state
                        # in order to be able to get updated
                        for device_pk in scope.device_pks
                            do (device_pk) ->
                                scope.server_pagination_pipe[device_pk] = (table_state) ->
                                    if scope.cur_device_pk?
                                        console.log 'called w ts', table_state
                                        if !table_state?
                                            table_state = _last_table_state[device_pk]
                                        _last_table_state[device_pk] = table_state
                                        console.log 'got ok', device_pk, 'table state', table_state
                                        if table_state?
                                            pagination = table_state.pagination
                                            scope.entries.is_loading = true

                                            query_parameters = scope.tab_query_parameters[scope.cur_device_pk]
                                            if !query_parameters?
                                                query_parameters = {}

                                            promise = scope.get_event_log_promise(scope.cur_device_pk, pagination.start, pagination.number, query_parameters)
                                            if promise
                                                do (table_state) ->
                                                    promise.then(([total_num, keys, new_data]) ->
                                                        console.log 'result here'
                                                        scope.entries = new_data
                                                        scope.entries.keys = keys
                                                        scope.entries.total_num = total_num
                                                        scope.entries.is_loading = false

                                                        table_state.pagination.numberOfPages = Math.ceil(total_num / pagination.number)
                                                    )

                # actually contact server
                _last_query_parameters = undefined
                scope.get_event_log_promise = (device_pk, skip, limit, query_parameters) ->
                    query_params = {
                        device_pks: JSON.stringify([parseInt(device_pk)])
                        query_parameters: query_parameters
                        mode: scope.device_mode[device_pk]
                        pagination_skip: skip
                        pagination_limit: limit
                    }
                    if !_.isEqual(_last_query_parameters, query_params)
                        _last_query_parameters = angular.copy(query_params)
                        console.log 'really doing query'
                        return Restangular.all(ICSW_URLS.DISCOVERY_GET_EVENT_LOG.slice(1)).getList(query_params)
                    else
                        console.log 'no query, disregarding'
                        return null

                scope.entries = []
                scope.entries.is_loading = false


        }
]).service("icswDiscoveryEventLogDataService", ["Restangular", "ICSW_URLS", "$rootScope", "$q", (Restangular, ICSW_URLS, $rootScope, $q) ->
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
.directive("icswDiscoveryOverview", ['icswDiscoveryDataService', 'icswDiscoveryDialogService', 'msgbus', (icswDiscoveryDataService, icswDiscoveryDialogService, msgbus) ->
    return  {
        restrict: 'EA'
        templateUrl: 'icsw.discovery.overview'
        link: (scope, el, attrs) ->
            scope.data = icswDiscoveryDataService
            scope.dialog_service = icswDiscoveryDialogService

            scope.selected_device_pks = []
            scope.selected_devices = []
            scope.selected_dispatch_settings = []

            update_selected_devices = () ->
                scope.selected_devices = (dev for dev in icswDiscoveryDataService.device when dev.idx in scope.selected_device_pks)
                scope.selected_dispatch_settings = (ds for ds in icswDiscoveryDataService.dispatch_setting when ds.device in scope.selected_device_pks)
                device_pks_with_dispatch_settings = _.uniq(ds.device for ds in icswDiscoveryDataService.dispatch_setting)
                scope.selected_devices_without_dispatch_settings =
                    (dev for dev in scope.selected_devices when dev.idx not in device_pks_with_dispatch_settings)

            scope.$watch('data.reload_observable', update_selected_devices)
            scope.$watchCollection('selected_device_pks', update_selected_devices)

            scope.new_devsel = (_dev_sel, _devg_sel) ->
                scope.selected_device_pks = _dev_sel

            msgbus.emit("devselreceiver")
            msgbus.receive("devicelist", scope, (name, args) ->
                scope.new_devsel(args[1])
            )
    }
]).service("icswDiscoveryDialogService",
    ["Restangular", "ICSW_URLS", "$rootScope", "$q", "$compile", "$templateCache",
    (Restangular, ICSW_URLS, $rootScope, $q, $compile, $templateCache) ->
        CREATE_MODE = 1
        MODIFY_MODE = 1

        show_dialog = (mode, objs) ->
            child_scope = $rootScope.$new()
            child_scope.is_create_mode = mode == CREATE_MODE
            edit_div = $compile($templateCache.get("icsw.discovery.edit_dialog"))(child_scope)
            modal = BootstrapDialog.show
                title: if mode == CREATE_MODE then "Create dispatch setting" else "Edit dispatch setting"
                message: edit_div
                draggable: true
                closable: true
                closeByBackdrop: false
                closeByKeyboard: false,
                onshow: (modal) =>
                    height = $(window).height() - 100
                    modal.getModal().find(".modal-body").css("max-height", height)
            child_scope.modal = modal

        return {
            show_create_dispatch_setting: () ->
                show_dialog(CREATE_MODE)
            show_modify_dispatch_setting: () ->
                show_dialog(MODIFY_MODE)
        }
]).service("icswDiscoveryDataService", ["Restangular", "ICSW_URLS", "$rootScope", "$q", (Restangular, ICSW_URLS, $rootScope, $q) ->
    rest_map = {
        dispatch_setting: ICSW_URLS.REST_DISCOVERY_DISPATCH_SETTING_LIST.slice(1)
        device: ICSW_URLS.REST_DEVICE_LIST.slice(1)
    }
    data = {
        reload_observable: 0
    }

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
