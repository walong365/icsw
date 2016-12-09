# Copyright (C) 2012-2016 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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
    "icsw.livestatus.comp.tabular",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.router",
    ]
).config(["icswLivestatusPipeRegisterProvider", (icswLivestatusPipeRegisterProvider) ->
    icswLivestatusPipeRegisterProvider.add("icswLivestatusMonTabularDisplay", true)
    icswLivestatusPipeRegisterProvider.add("icswLivestatusDeviceTabularDisplay", true)
]).service('icswLivestatusMonTabularDisplay',
[
    "$q", "icswMonLivestatusPipeBase", "icswMonitoringResult",
(
    $q, icswMonLivestatusPipeBase, icswMonitoringResult,
) ->
    class icswLivestatusMonTabularDisplay extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusMonTabularDisplay", true, false)
            @set_template(
                '<icsw-livestatus-mon-table-view icsw-connect-element="con_element"></icsw-livestatus-mon-table-view>'
                "Service Tabular Display"
                10
                8
            )
            @new_data_notifier = $q.defer()

        new_data_received: (data) ->
            @new_data_notifier.notify(data)

        pipeline_reject_called: (reject) ->
            @new_data_notifier.reject("end")

        restore_settings: (settings) ->
            # store settings
            @_settings = settings

]).directive("icswLivestatusMonTableView",
[
    "$templateCache",
(
    $templateCache,
) ->
        return {
            restrict: "EA"
            template: $templateCache.get("icsw.livestatus.mon.table.view")
            controller: "icswLivestatusDeviceMonTableCtrl"
            scope: {
                # connect element for pipelining
                con_element: "=icswConnectElement"
            }
            link: (scope, element, attrs) ->
                scope.link(scope.con_element, scope.con_element.new_data_notifier, "services")
        }
]).directive("icswLivestatusMonTableRow",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.livestatus.mon.table.row")
    }
]).service('icswLivestatusDeviceTabularDisplay',
[
    "$q", "icswMonLivestatusPipeBase", "icswMonitoringResult",
(
    $q, icswMonLivestatusPipeBase, icswMonitoringResult,
) ->
    class icswLivestatusDeviceTabularDisplay extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusDeviceTabularDisplay", true, false)
            @set_template(
                '<icsw-livestatus-device-table-view icsw-connect-element="con_element"></icsw-livestatus-device-table-view>'
                "Device Tabular Display"
                10
                8
            )
            @new_data_notifier = $q.defer()

        new_data_received: (data) ->
            @new_data_notifier.notify(data)

        pipeline_reject_called: (reject) ->
            @new_data_notifier.reject("end")

        restore_settings: (settings) ->
            # store settings
            @_settings = settings

]).directive("icswLivestatusDeviceTableView",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.livestatus.device.table.view")
        controller: "icswLivestatusDeviceMonTableCtrl"
        scope: {
            # connect element for pipelining
            con_element: "=icswConnectElement"
        }
        link: (scope, element, attrs) ->
            scope.link(scope.con_element, scope.con_element.new_data_notifier, "hosts")
    }
]).directive("icswLivestatusDeviceTableRow",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.livestatus.device.table.row")
    }
]).service("icswIcingaCmdTools",
[
    "$q", "icswMonitoringBasicTreeService", "$rootScope", "$templateCache", "$compile",
    "icswSimpleAjaxCall", "blockUI", "icswComplexModalService", "icswUserService",
    "ICSW_URLS", "toaster",
(
    $q, icswMonitoringBasicTreeService, $rootScope, $templateCache, $compile,
    icswSimpleAjaxCall, blockUI, icswComplexModalService, icswUserService,
    ICSW_URLS, toaster,
) ->
    _struct = {
        basic_tree: null
    }

    load_tree = () ->
        defer = $q.defer()
        if _struct.basic_tree
            defer.resolve(_struct.basic_tree)
        else
            blockUI.start("loading commands...")
            icswMonitoringBasicTreeService.load("icswIcingaCmdTools").then(
                (tree) ->
                    blockUI.stop()
                    _struct.basic_tree = tree
                    defer.resolve(_struct.basic_tree)
            )
        return defer.promise

    icinga_cmd = (obj_type, obj_list) ->
        load_tree().then(
            (tree) ->
                sub_scope = $rootScope.$new(true)
                sub_scope.obj_type = obj_type
                sub_scope.obj_list = obj_list
                sub_scope.user = icswUserService.get()
                # action

                _actions = []
                for entry in tree.icinga_command_list
                    if not entry.$$private
                        if obj_type == "host"
                            # for host actions this must be a host-only action
                            if entry.for_host and not entry.for_service
                                _actions.push(entry)
                        else if obj_type == "service"
                            # for service actions this must be a service action (!)
                            if entry.for_service
                                _actions.push(entry)

                sub_scope.valid_actions = _.orderBy(
                    _actions
                    ["name"]
                    ["asc"]
                )
                sub_scope.edit_obj = {
                    action: sub_scope.valid_actions[0]
                    args: {}
                }
                sub_scope.dt_picker = {
                    date_options: {
                        format: "dd.MM.yyyy"
                        formatYear: "yyyy"
                        maxDate: new Date()
                        minDate: new Date(2000, 1, 1)
                        startingDay: 1
                        minMode: "day"
                        datepickerMode: "day"
                    }
                    time_options: {
                        showMeridian: false
                    }
                    open: false
                }

                sub_scope.open_calendar = ($event, arg_name) ->
                    sub_scope.open_calendars[arg_name] = true

                sub_scope.set_duration = ($event, arg_name, hours) ->
                    sub_scope.edit_obj.args[arg_name] = moment().add(hours, "hours").toDate()
                    # console.log "SD", arg_name, hours

                sub_scope.arguments = []

                sub_scope.action_changed = ($event) ->
                    _act = sub_scope.edit_obj.action
                    sub_scope.arguments.length = 0
                    sub_scope.edit_obj.args = {}
                    sub_scope.open_calendars = {}
                    for arg in _act.args
                        if arg.name not in ["host_name", "service_description"]
                            sub_scope.arguments.push(arg)
                            if arg.is_boolean
                                _default = true
                            else if arg.is_timestamp
                                _default = moment().add(24, "hours").toDate()
                                sub_scope.open_calendars[arg.name] = false
                            else
                                _default = ""
                            sub_scope.edit_obj.args[arg.name] = _default
                        else
                            sub_scope.edit_obj.args[arg.name] = ""

                sub_scope.action_changed()
                icswComplexModalService(
                    {
                        message: $compile($templateCache.get("icsw.livestatus.modify.entries"))(sub_scope)
                        title: "Submit Icinga command"
                        ok_label: "Submit"
                        closable: true
                        ok_callback: (modal) ->
                            d = $q.defer()
                            if sub_scope.form_data.$invalid
                                toaster.pop("warning", "form validation problem", "")
                                d.reject("formerror")
                            else
                                blockUI.start()
                                if obj_type == "host"
                                    # build key list for hosts
                                    key_list = ({host_idx: entry.$$icswDevice.idx} for entry in obj_list)
                                else
                                    # build key list for services
                                    key_list = ({host_idx: entry.$$host_mon_result.$$icswDevice.idx, service_description: entry.description} for entry in obj_list)
                                icswSimpleAjaxCall(
                                    {
                                        url: ICSW_URLS.MON_SEND_MON_COMMAND
                                        data:
                                            json: angular.toJson(
                                                action: sub_scope.edit_obj.action.name
                                                type: obj_type
                                                key_list: key_list
                                                arguments: sub_scope.edit_obj.args
                                            )
                                    }
                                ).then(
                                    (res) ->
                                        # console.log "r=", res
                                        blockUI.stop()
                                        d.resolve("close")
                                    (error) ->
                                        blockUI.stop()
                                        d.reject(error)
                                )
                            return d.promise
                        cancel_callback: () ->
                            d = $q.defer()
                            d.resolve("close")
                            return d.promise
                    }
                ).then(
                    (fin) ->
                        sub_scope.$destroy()
                )


        )
    return {
        icinga_cmd: (obj_type, obj_list) ->
            return icinga_cmd(obj_type, obj_list)
    }
]).directive("icswLivestatusMonTableSelHeader",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.livestatus.mon.table.sel.header")
    }
]).controller("icswLivestatusDeviceMonTableCtrl",
[
    "$scope", "DeviceOverviewService", "$q", "icswSimpleAjaxCall", "ICSW_URLS",
    "ICSW_SIGNALS", "icswComplexModalService", "$templateCache", "$compile", "blockUI",
    "icswIcingaCmdTools", "$rootScope", "$timeout",
(
    $scope, DeviceOverviewService, $q, icswSimpleAjaxCall, ICSW_URLS,
    ICSW_SIGNALS, icswComplexModalService, $templateCache, $compile, $blockUI,
    icswIcingaCmdTools, $rootScope, $timeout,
) ->
    $scope.struct = {
        # monitoring data
        monitoring_data: undefined
        # connection element
        con_element: undefined
        # settings
        settings: {
            "pag": {}
            "columns": {}
        }
        # selected
        selected: 0
        # selectable (unselected)
        selectable: 0
        # display type
        d_type: undefined
        # value for modify button
        modify_value: "N/A"
        # external notifier
        external_notifier: $q.defer()
        # focus device (for service overview)
        focus_device: 0
        # source list
        source_list: []
        # current page (saved for focus)
        saved_page: 0
    }

    # pagination control
    $scope.pag_control = {counter: 0}

    _copy_to_source_list = () ->
        $scope.struct.source_list.length = 0
        if $scope.struct.focus_device
            _f_idx = $scope.struct.focus_device
            if $scope.struct.d_type == "services"
                for entry in $scope.struct.monitoring_data[$scope.struct.d_type]
                    entry.$$hasFocus = entry.$$host_mon_result.$$icswDevice.idx == _f_idx
                    if entry.$$hasFocus
                        $scope.struct.source_list.push(entry)
            else
                for entry in $scope.struct.monitoring_data[$scope.struct.d_type]
                    entry.$$hasFocus = entry.$$icswDevice.idx == _f_idx
                    $scope.struct.source_list.push(entry)
        else
            for entry in $scope.struct.monitoring_data[$scope.struct.d_type]
                entry.$$hasFocus = false
                $scope.struct.source_list.push(entry)
            if $scope.struct.d_type == "services" and $scope.struct.saved_page
                _restore = $scope.struct.saved_page
                $scope.struct.saved_page = 0
                $timeout(
                    () ->
                        # console.log "restore", _restore
                        # trigger watcher
                        $scope.pag_control.counter++
                        $scope.pag_control.current_page = _restore
                    0
                )

    $scope.link = (con_element, notifier, d_type) ->
        $scope.struct.d_type = d_type
        # console.log $scope.struct.d_type
        $scope.struct.con_element = con_element
        if $scope.struct.con_element._settings?
            $scope.struct.settings = angular.fromJson($scope.struct.con_element._settings)
            if "pag" of $scope.struct.settings
                _pag_settings = $scope.struct.settings.pag
                $scope.pag_control.$id = $scope.$id
                if "items_by_page" of _pag_settings
                    $scope.pag_control.items_by_page = _pag_settings.items_by_page
                if "sort" of _pag_settings
                    $scope.pag_control.sort = _pag_settings.sort
                # trigger reload
                $scope.pag_control.counter++
                # console.log $scope.struct.settings["pag"]
            if "columns" of $scope.struct.settings
                $scope.columns_from_settings = $scope.struct.settings["columns"]
        notifier.promise.then(
            (resolve) ->
            (rejected) ->
            (data) ->
                $scope.struct.monitoring_data = data
                _copy_to_source_list()
                $scope.struct.external_notifier.notify("new")
                _update_selected()
        )

    unreg_func = []

    unreg_func.push(
        $rootScope.$on(
            ICSW_SIGNALS("ICSW_LIVESTATUS_DEVICE_FOCUS")
            (event, c_id, t_type, dev_idx) ->
                if c_id == $scope.struct.con_element.__dp_connector.connector_id
                    if $scope.struct.focus_device == dev_idx
                        $scope.struct.focus_device = 0
                    else
                        $scope.struct.focus_device = dev_idx
                    _copy_to_source_list()
                    _update_selected()
        )
    )
    $scope.$on("$destroy", () ->
        $scope.struct.external_notifier.reject()
        (_func() for _func in unreg_func)
    )

    $scope.focus_device = ($event, dev_check) ->
        $event.stopPropagation()
        $event.preventDefault()
        $rootScope.$emit(
            ICSW_SIGNALS("ICSW_LIVESTATUS_DEVICE_FOCUS")
            $scope.struct.con_element.__dp_connector.connector_id
            $scope.struct.d_type
            dev_check.$$icswDevice.idx
        )

    $scope.show_device = ($event, dev_check) ->
        $event.stopPropagation()
        $event.preventDefault()
        DeviceOverviewService($event, [dev_check.$$icswDevice])

    $scope.pagination_changed = (pag) ->
        if not $scope.struct.focus_device
            # console.log "pag=", pag
            $scope.struct.settings["pag"] = pag
            $scope.struct.con_element.pipeline_settings_changed(angular.toJson($scope.struct.settings))
            $scope.struct.saved_page = pag.current_page

    $scope.columns_changed = (col_setup) ->
        $scope.struct.settings["columns"] = col_setup
        $scope.struct.con_element.pipeline_settings_changed(angular.toJson($scope.struct.settings))

    _update_selected = () ->
        $scope.struct.selected = (entry for entry in $scope.struct.source_list when entry.$$selected).length
        $scope.struct.selectable = $scope.struct.source_list.length - $scope.struct.selected
        if $scope.struct.selected
            $scope.struct.modify_value = "modify #{$scope.struct.selected} #{$scope.struct.d_type}"
        else
            $scope.struct.modify_value = "N/A"

    $scope.clear_selection = ($event) ->
        for entry in $scope.struct.source_list
            entry.$$selected = false
        $scope.struct.selected.length = 0
        $scope.struct.selectable = $scope.struct.source_list.length
        _update_selected()

    $scope.select_all = ($event) ->
        for entry in $scope.struct.source_list
            entry.$$selected = true
        _update_selected()

    $scope.toggle_selection = ($event, element) ->
        element.$$selected = !element.$$selected
        _update_selected()

    $scope.modify_entries = ($event) ->
        if $scope.struct.d_type == "hosts"
            obj_type = "host"
        else
            obj_type = "service"
        obj_list = (entry for entry in $scope.struct.source_list when entry.$$selected)
        icswIcingaCmdTools.icinga_cmd(
            obj_type
            obj_list
        )
]).service("icswLivestatusDeviceServiceOverviewReact",
[
    "$q",
(
    $q,
) ->
    # display of livestatus filter
    {span, rect, title, span, svg, path, g, text, div} = React.DOM

    return React.createClass(
        displayName: "DeviceServiceOverview"
        propTypes: {
            mon_device: React.PropTypes.object
        }
        getInitialState: () ->
            return {}
        render: () ->
            dev = @props.mon_device
            if not dev.$$service_list.length
                return div(
                    {}
                    "N/A"
                )
            # state lut
            state_lut = {}
            # calculate total width and build lut
            num = 0
            for srv in dev.$$service_list
                if srv.state not of state_lut
                    state_lut[srv.state] = _.clone(srv.$$data)
                    state_lut[srv.state].num = 0
                state_lut[srv.state].num++
                num++
            _w = 86
            _h = 16
            _rect_list = []
            idx = 0
            state_idxs = _.keys(state_lut)
            state_idxs.sort()
            title_str = ["w=#{dev.$$serviceWeight}"]
            # rect list and title string
            for state_idx in state_idxs
                state = state_lut[state_idx]
                _rect_list.push(
                    rect(
                        {
                            key: "service.#{state_idx}"
                            x: parseInt(_w * idx / num)
                            y: 0
                            width: parseInt(_w * (idx + state.num) / num)
                            height: _h
                            className: state.svgClassName
                        }
                    )
                )
                title_str.push("#{state.num} #{state.info}")
                idx += state.num
            # border
            _rect_list.push(
                rect(
                    {
                        key: "service.border"
                        x: 0
                        y: 0
                        width: "#{_w}px"
                        height: "#{_h}px"
                        style: {fill: "none", strokeWidth: "1px", stroke: "black"}
                    }
                )
            )
            return div(
                {
                    key: "top"
                    title: title_str.join(", ")
                }
                svg(
                    {
                        width: "#{_w}px"
                        height: "#{_h}px"
                    }
                    _rect_list
                )
            )
    )
]).directive("icswLivestatusDeviceServiceOverview",
[
    "$q", "icswLivestatusDeviceServiceOverviewReact",
(
    $q, icswLivestatusDeviceServiceOverviewReact,
) ->
    return {
        restrict: "E"
        scope: false
        link: (scope, element, attrs) ->
            new_rel = ReactDOM.render(
                React.createElement(
                    icswLivestatusDeviceServiceOverviewReact
                    {
                        mon_device: scope.$eval(attrs.monDevice)
                    }
                )
                $(element)[0]
            )

    }
])
