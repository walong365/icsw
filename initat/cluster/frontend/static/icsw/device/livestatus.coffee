# Copyright (C) 2012-2016 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
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

class hs_node
    # hierarchical structure node
    constructor: (@name, @check, @filter=false, @placeholder=false, @dummy=false) ->
        # name
        # check (may also be a dummy dict)
        @value = 1
        @root = @
        @children = []
        @show = true
        @depth = 0
        @clicked = false
    valid_device: () ->
        _r = false
        if @children.length == 1
            if @children[0].children.length == 1
                _r = true
        return _r
    reduce: () ->
        if @children.length
            return @children[0]
        else
            return @
    add_child: (entry) ->
        entry.root = @
        entry.depth = @depth + 1
        entry.parent = @
        @children.push(entry)
    iter_childs: (cb_f) ->
        cb_f(@)
        (_entry.iter_childs(cb_f) for _entry in @children)
    get_childs: (filter_f) ->
        _field = []
        if filter_f(@)
            _field.push(@)
        for _entry in @children
            _field = _field.concat(_entry.get_childs(filter_f))
        return _field
    clear_clicked: () ->
        # clear all clicked flags
        @clicked = false
        @show = true
        (_entry.clear_clicked() for _entry in @children)
    any_clicked: () ->
        res = @clicked
        if not res
            for _entry in @children
                res = res || _entry.any_clicked()
        return res
    handle_clicked: () ->
        # find clicked entry
        _clicked = @get_childs((obj) -> return obj.clicked)[0]
        @iter_childs(
            (obj) ->
                obj.show = false
        )
        parent = _clicked
        while parent?
            parent.show = true
            parent = parent.parent
        _clicked.iter_childs((obj) -> obj.show = true)
    
angular.module(
    "icsw.device.livestatus",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.router",
    ]
).config(["$stateProvider", "icswRouteExtensionProvider", ($stateProvider, icswRouteExtensionProvider) ->
    $stateProvider.state(
        "main.livestatus", {
            url: "/livestatus"
            template: '<icsw-device-livestatus icsw-sel-man="0" icsw-sel-man-mode="d"></icsw-device-livestatus>'
            icswData: icswRouteExtensionProvider.create
                pageTitle: "Monitoring dashboard"
                licenses: ["monitoring_dashboard"]
                rights: ["mon_check_command.show_monitoring_dashboard"]
                menuEntry:
                    menukey: "stat"
                    icon: "fa-dot-circle-o"
                    ordering: 20
        }
    ).state(
        "main.livestatus.Everything"
        {
            url: "/livestatus/lo1"
            templateUrl: "icsw.device.livestatus.everything"
            icswData: icswRouteExtensionProvider.create()
        }
    ).state(
        "main.livestatus.BurstTable"
        {
            url: "/livestatus/lo2"
            templateUrl: "icsw.device.livestatus.bursttable"
            icswData: icswRouteExtensionProvider.create()
        }
    ).state(
        "main.livestatus.OnlyTable"
        {
            url: "/livestatus/lo3"
            templateUrl: "icsw.device.livestatus.onlytable"
            icswData: icswRouteExtensionProvider.create()
        }
    ).state(
        "main.livestatus.MapWithBurst"
        {
            url: "/livestatus/lo4"
            templateUrl: "icsw.device.livestatus.mapwithburst"
            icswData: icswRouteExtensionProvider.create()
        }
    )
]).service("icswLivestatusFilterService",
[
    "$q", "$rootScope",
(
    $q, $rootScope,
) ->
    # ToDo: separate data / filtered data from filter
    running_id = 0
    class icswLivestatusFilter
        constructor: () ->
            running_id++
            @id = running_id
            # console.log "new LivestatusFilter with id #{@id}"
            @categories = []
            # number of entries
            @n_hosts = 0
            @n_services = 0
            # filtered entries
            @f_hosts = 0
            @f_services = 0
            # possible service states
            @service_state_list = [
                [0, "O", true, "show OK states", "btn-success"]
                [1, "W", true, "show warning states", "btn-warning"]
                [2, "C", true, "show critical states", "btn-danger"]
                [3, "U", true, "show unknown states", "btn-danger"]
            ]
            @service_state_lut = {}

            # possible host states
            @host_state_list = [
                [0, "U", true, "show Up states", "btn-success"]
                [1, "D", true, "show Down states", "btn-warning"]
                [2, "?", true, "show unreachable states", "btn-danger"]
            ]
            @host_state_lut = {}

            # possibel service type states
            @service_type_list = [
                [0, "S", true, "show soft states", "btn-primary"]
                [1, "H", true, "show hard states", "btn-primary"]
            ]
            @service_type_lut = {}
            
            # default values for service states
            @service_states = {}
            for entry in @service_state_list
                @service_state_lut[entry[0]] = entry
                @service_state_lut[entry[1]] = entry
                @service_states[entry[0]] = entry[2]

            # default values for host states
            @host_states = {}
            for entry in @host_state_list
                @host_state_lut[entry[0]] = entry
                @host_state_lut[entry[1]] = entry
                @host_states[entry[0]] = entry[2]
                
            # default values for service types
            @service_types = {}
            for entry in @service_type_list
                @service_type_lut[entry[0]] = entry
                @service_type_lut[entry[1]] = entry
                @service_types[entry[0]] = entry[2]

            @change_notifier = $q.defer()
            # category filter settings
            @cat_filter_installed = false

        install_category_filter: () =>
            @cat_filter_installed = true
            @cat_filter_list = undefined

        set_category_filter: (in_list) =>
            @cat_filter_list = in_list
            # console.log "cur_cat_filter=", in_list
            if @_latest_data?
                # a little hack but working
                @set_monitoring_data(@_latest_data)

        toggle_service_state: (code) =>
            _srvc_idx = @service_state_lut[code][0]
            @service_states[_srvc_idx] = !@service_states[_srvc_idx]
            # ensure that any service state is set, should be implemented as option
            # if not _.some(_.values(@service_states))
            #    @service_states[0] = true

        toggle_host_state: (code) =>
            _host_idx = @host_state_lut[code][0]
            @host_states[_host_idx] = !@host_states[_host_idx]
            # ensure that any host state is set, should be implemented as option
            # if not _.some(_.values(@host_states))
            #     @host_states[0] = true

        toggle_service_type: (code) =>
            _type_idx = @service_type_lut[code][0]
            @service_types[_type_idx] = !@service_types[_type_idx]
            # ensure that any service state is set, should be implemented as option
            # if not _.some(_.values(@service_types))
            #    @service_types[0] = true

        # get state strings for ReactJS, a little hack ...
        _get_service_state_str: () =>
            return (entry[1] for entry in @service_state_list when @service_states[entry[0]]).join(":")

        _get_host_state_str: () =>
            return (entry[1] for entry in @host_state_list when @host_states[entry[0]]).join(":")
            
        _get_service_type_str: () =>
            return (entry[1] for entry in @service_type_list when @service_types[entry[0]]).join(":")
            
        get_filter_state_str: () ->
            return [
                @_get_service_state_str()
                @_get_host_state_str()
                @_get_service_type_str()
            ].join(";")

        stop_notifying: () ->
            @change_notifier.reject("stop")
            
        set_monitoring_data: (data) ->
            @n_hosts = data.hosts.length
            @n_services = data.services.length
            @categories = data.categories
            @_latest_data = data
            data.filter(@)
            @f_hosts = data.filtered_hosts.length
            @f_services = data.filtered_services.length
            @change_notifier.notify()

]).factory("icswLivestatusFilterReactDisplay",
[
    "$q",
(
    $q
) ->
    # display of livestatus filter
    react_dom = ReactDOM
    {div, h4, select, option, p, input, span} = React.DOM

    return React.createClass(
        propTypes: {
            livestatus_filter: React.PropTypes.object
            filter_changed_cb: React.PropTypes.func
        }
        getInitialState: () ->
            return {
                filter_state_str: @props.livestatus_filter.get_filter_state_str()
                display_iter: 0
            }

        componentWillMount: () ->
            # @umount_defer = $q.defer()
            @props.livestatus_filter.change_notifier.promise.then(
                () ->
                () ->
                    # will get called when the component unmounts
                (c) =>
                    @setState({display_iter: @state.display_iter + 1})
            )

        componentWillUnmount: () ->
            @props.livestatus_filter.stop_notifying()

        shouldComponentUpdate: (next_props, next_state) ->
            _redraw = false
            if next_state.display_iter != @state.display_iter
                _redraw = true
            else if next_state.filter_state_str != @state.filter_state_str
                _redraw = true
            return _redraw

        render: () ->

            _filter_changed = () =>
                if @props.filter_changed_cb?
                    @props.filter_changed_cb()

            # console.log "r", @props.livestatus_filter
            _lf = @props.livestatus_filter
            _list = []
            _text_f = []
            _text_f.push(" hosts:")
            if _lf.f_hosts != _lf.n_hosts
                _text_f.push("#{_lf.f_hosts} of #{_lf.n_hosts}")
            else
                _text_f.push(" #{_lf.n_hosts}")
            _text_f.push("services:")
            if _lf.f_services != _lf.n_services
                _text_f.push("#{_lf.f_services} of #{_lf.n_services}")
            else
                _text_f.push(" #{_lf.n_services}")
            _list.push(
                "filter options: "
            )
            _service_buttons = []
            for entry in _lf.service_state_list
                _service_buttons.push(
                    input(
                        {
                            key: "srvc.#{entry[1]}"
                            type: "button"
                            className: "btn btn-xs " + if _lf.service_states[entry[0]] then entry[4] else "btn-default"
                            value: entry[1]
                            title: entry[3]
                            onClick: (event) =>
                                # _lf.toggle_md(event.target_value)
                                _lf.toggle_service_state(event.target.value)
                                # force redraw
                                @setState({filter_state_str: _lf.get_filter_state_str()})
                                _filter_changed()
                        }
                    )
                )
            _host_buttons = []
            for entry in _lf.host_state_list
                _host_buttons.push(
                    input(
                        {
                            key: "host.#{entry[1]}"
                            type: "button"
                            className: "btn btn-xs " + if _lf.host_states[entry[0]] then entry[4] else "btn-default"
                            value: entry[1]
                            title: entry[3]
                            onClick: (event) =>
                                _lf.toggle_host_state(event.target.value)
                                # force redraw
                                @setState({filter_state_str: _lf.get_filter_state_str()})
                                _filter_changed()
                        }
                    )
                )
            _type_buttons = []
            for entry in _lf.service_type_list
                _type_buttons.push(
                    input(
                        {
                            key: "stype.#{entry[1]}"
                            type: "button"
                            className: "btn btn-xs " + if _lf.service_types[entry[0]] then entry[4] else "btn-default"
                            value: entry[1]
                            title: entry[3]
                            onClick: (event) =>
                                _lf.toggle_service_type(event.target.value)
                                # force redraw
                                @setState({filter_state_str: _lf.get_filter_state_str()})
                                _filter_changed()
                        }
                    )
                )
            _list.push(
                div(
                    {
                        key: "srvc.buttons"
                        className: "btn-group"
                    }
                    _service_buttons
                )
            )
            _list.push(" ")
            _list.push(
                div(
                    {
                        key: "host.buttons"
                        className: "btn-group"
                    }
                    _host_buttons
                )
            )
            _list.push(" ")
            _list.push(
                div(
                    {
                        key: "type.buttons"
                        className: "btn-group"
                    }
                    _type_buttons
                )
            )
            _list.push(
                _text_f.join(" ")
            )
            return span(
                {key: "top"}
                _list
            )
    )
]).directive("icswLivestatusFilterDisplay",
[
    "$q", "icswLivestatusFilterReactDisplay",
(
    $q, icswLivestatusFilterReactDisplay,
) ->
    return  {
        restrict: "EA"
        replace: true
        scope:
            filter: "=icswLivestatusFilter"
            changed_cb: "=icswChangedCallback"
        link: (scope, element, attr) ->
            ReactDOM.render(
                React.createElement(
                    icswLivestatusFilterReactDisplay
                    {
                        livestatus_filter: scope.filter
                        filter_changed_cb: () ->
                            if scope.changed_cb?
                                scope.changed_cb()
                    }
                )
                element[0]
            )
    }

]).service("icswSaltMonitoringResultService", [() ->

    _parse_custom_variables = (cvs) ->
        _cv = {}
        if cvs
            first = true
            for _entry in cvs.split("|")
                if first
                    key = _entry.toLowerCase()
                    first = false
                else
                    parts = _entry.split(",")
                    _cv[key] = parts
                    key = parts.pop().toLowerCase()
            # append key of last '|'-split to latest parts
            parts.push(key)
            for single_key in ["check_command_pk", "device_pk"]
                if single_key of _cv
                    _cv[single_key] = parseInt(_cv[single_key][0])
            for int_mkey in ["cat_pks"]
                if int_mkey of _cv
                    _list = (parseInt(_sv) for _sv in _cv[int_mkey] when _sv != "-")
                    if _list.length
                        _cv[int_mkey] = _list
                    else
                        delete _cv[int_mkey]
        return _cv

    _get_diff_time = (ts) ->
        if parseInt(ts)
            return moment.unix(ts).fromNow(true)
        else
            return "never"

    _get_attempt_info = (entry) ->
        if entry.max_check_attempts == null
            return "N/A"
        else
            try
                max = parseInt(entry.max_check_attempts)
                cur = parseInt(entry.current_attempt)
                if max == cur
                    return "#{cur}"
                else
                    return "#{cur} / #{max}"
            catch error
                return "e"
            
    _get_attempt_class = (entry) ->
        if entry.max_check_attempts == null
            _r_str = "default"
        else
            try
                max = parseInt(entry.max_check_attempts)
                cur = parseInt(entry.current_attempt)
                if max == cur
                    _r_str = "info"
                else
                    _r_str = "success"
            catch error
                _r_str = "danger"
        return "label-#{_r_str}"
            
    _sanitize_entry = (entry) ->
        entry.$$dummy = false
        entry.state = parseInt(entry.state)
        if entry.state_type in ["0", "1"]
            entry.state_type = parseInt(entry.state_type)
        else
            entry.state_type = null
        if entry.check_type in ["0", "1"]
            entry.check_type = parseInt(entry.check_type)
        else
            entry.check_type = null
        entry.$$icswStateTypeString = {
            null: "???"
            0: "soft"
            1: "hard"
        }[entry.state_type]
        entry.$$icswCheckTypeString = {
            null: "???"
            0: "active"
            1: "passive"
        }[entry.check_type]
        entry.$$icswPassiveCheck = if entry.check_type then true else false
        entry.$$icswAttemptLabelClass = _get_attempt_class(entry)
        entry.$$icswAttemptInfo = _get_attempt_info(entry)
        try
            if parseInt(entry.current_attempt) == 1
                _si = true
            else
                _si = true
        catch error
           _si = true
        entry.$$icswShowAttemptInfo = _si
        entry.$$icswLastCheckString = _get_diff_time(entry.last_check)
        entry.$$icswLastStateChangeString = _get_diff_time(entry.last_state_change)

        # custom variables

        entry.custom_variables = _parse_custom_variables(entry.custom_variables)

    _get_dummy_entry = (display_name, ct) ->
        entry = {
            $$burst_fill_color: "#dddddd"
            display_name: display_name
            $$ct: ct
            $$dummy: false
        }
        return entry

    get_dummy_service_entry = (display_name) ->
        entry = _get_dummy_entry(display_name, "service")
        # is a dummy entry
        entry.$$dummy = true
        return entry

    get_device_group_entry = (display_name) ->
        entry = _get_dummy_entry(display_name, "devicegroup")
        return entry

    get_system_entry = (display_name) ->
        entry = _get_dummy_entry(display_name, "system")
        return entry
    
    salt_device_state = (entry) ->
        entry.$$burst_fill_color = {
            0: "#66dd66"
            1: "#ff7777"
            2: "#ff0000"
            # special state 
            3: "#dddddd"
        }[entry.state]
        _r_str = {
            0: "success"
            1: "danger"
            2: "danger"
            3: "warning"
        }[entry.state]
        entry.$$icswStateClass = _r_str
        entry.$$icswStateLabelClass = "label-#{_r_str}"
        entry.$$icswStateTextClass = "text-#{_r_str}"
        entry.$$icswStateString = {
            0: "OK"
            1: "Critical"
            2: "Unreachable"
            3: "Not set"
        }[entry.state]

    salt_service_state = (entry) ->
            _r_str = {
                0: "success"
                1: "warning"
                2: "danger"
                3: "danger"
            }[entry.state]
            entry.$$burst_fill_color = {
                0: "#66dd66"
                1: "#dddd88"
                2: "#ff7777"
                3: "#ff0000"
            }[entry.state]
            entry.$$icswStateLabelClass = "label-#{_r_str}"
            entry.$$icswStateTextClass = "text-#{_r_str}"
            entry.$$icswStateString = {
                0: "OK"
                1: "Warning"
                2: "Critical"
                3: "Unknown"
            }[entry.state]

    salt_host = (entry, device_tree) ->
        if not entry.$$icswSalted?
            entry.$$service_list = []
            entry.$$icswSalted = true
            # set default values
            entry.$$ct = "device"
            # sanitize entries
            _sanitize_entry(entry)
            # host state class
            salt_device_state(entry)
            entry.$$icswDevice = device_tree.all_lut[entry.custom_variables.device_pk]
            # for display
            entry.display_name = entry.$$icswDevice.full_name
            # link back, highly usefull
            entry.$$icswDevice.$$host_mon_result = entry
            entry.$$icswDeviceGroup = device_tree.group_lut[entry.$$icswDevice.device_group]
        return entry

    salt_service = (entry, cat_tree) ->
        if not entry.$$icswSalted?
            entry.$$icswSalted = true
            # set default values
            entry.$$ct = "service"
            # sanitize entries
            _sanitize_entry(entry)
            # service state class
            salt_service_state(entry)
            # resolve categories
            if entry.custom_variables.cat_pks?
                entry.$$icswCategories = (cat_tree.lut[_cat].name for _cat in entry.custom_variables.cat_pks).join(", ")
            else
                entry.$$icswCategories = "---"
        return entry

    return {
        get_dummy_service_entry: get_dummy_service_entry

        get_device_group_entry: get_device_group_entry

        get_system_entry: get_system_entry

        salt_device_state: salt_device_state

        salt_host: salt_host

        salt_service: salt_service
    }
]).controller("icswDeviceLiveStatusCtrl",
[
    "$scope", "$compile", "$templateCache", "Restangular",
    "$q", "$timeout", "icswTools", "ICSW_URLS", "icswSimpleAjaxCall",
    "icswDeviceLivestatusDataService", "icswCachingCall", "icswLivestatusFilterService",
    "icswDeviceTreeService", "$state",
(
    $scope, $compile, $templateCache, Restangular,
    $q, $timeout, icswTools, ICSW_URLS, icswSimpleAjaxCall,
    icswDeviceLivestatusDataService, icswCachingCall, icswLivestatusFilterService,
    icswDeviceTreeService, $state
) ->
    # top level controller of monitoring dashboard

    LS_KEY = "main.livestatus"

    $scope.struct = {
        # list of layouts
        layouts: []
        # current layout
        current_layout: undefined
        # filter
        filter: new icswLivestatusFilterService()
        # selected devices
        devices: []
        # data fetch timeout
        fetch_timeout: undefined
        # updating flag
        updating: false
        # device tree, really needed here ?
        device_tree: undefined
        # monitoring data
        monitoring_data: undefined
    }

    # layout functions

    $scope.activate_layout = (state) ->
        $scope.struct.current_layout = state
        $state.go(state)

    check_layouts = () ->
        $scope.struct.layouts.length = 0
        $scope.struct.current_layout = $state.current
        _change_state = true
        for state in $state.get()
            if state.name.match(LS_KEY) and state.name != LS_KEY
                state.icswData.short_name = state.name.slice(LS_KEY.length + 1)
                $scope.struct.layouts.push(state)
                if state.url == $scope.struct.current_layout.url
                    # url is in local states, no change
                    _change_state = false
        if _change_state
            $scope.activate_layout($scope.struct.layouts[0])

    check_layouts()

    # $scope.ls_devsel = new icswLivestatusDevSelFactory()

    #$scope.$watch(
    #    $scope.ls_filter.changed
    #    (new_filter) ->
    #        $scope.apply_filter()
    #)

    # selected categories

    $scope.filter_changed = () ->
        if $scope.struct.filter?
            $scope.struct.filter.set_monitoring_data($scope.struct.monitoring_data)

    $scope.new_devsel = (_dev_sel, _devg_sel) ->
        $scope.struct.updating = true

        if $scope.struct.fetch_timeout
            $timeout.cancel($scope.struct.fetch_timeout)
            $scope.struct.fetch_timeout = undefined

        $scope.struct.devices.length = 0
        for entry in _dev_sel
            if not entry.is_meta_device
                $scope.struct.devices.push(entry)

        #pre_sel = (dev.idx for dev in $scope.devices when dev.expanded)
        wait_list = [
            icswDeviceTreeService.load($scope.$id)
            icswDeviceLivestatusDataService.retain($scope.$id, $scope.struct.devices)
        ]
        $q.all(wait_list).then(
            (data) ->
                $scope.struct.device_tree = data[0]
                # $scope.new_data(data[1])
                #console.log "gen", data[1][4]
                # console.log "watch for", data[1]
                $scope.struct.updating = false
                $scope.struct.monitoring_data = data[1]
                $scope.struct.monitoring_data.result_notifier.promise.then(
                    (ok) ->
                        console.log "dr ok"
                    (not_ok) ->
                        console.log "dr error"
                    (generation) ->
                        # console.log "data here"
                        $scope.filter_changed()
                )
        )

    #$scope.new_data = (mres) ->
    #    host_entries = mres.hosts
    #    service_entries = mres.services
    #    used_cats = mres.used_cats
    #    $scope.host_entries = host_entries
    #    $scope.service_entries = service_entries
        # $scope.ls_filter.set_total_num(host_entries.length, service_entries.length)
        # $scope.ls_filter.set_used_cats(used_cats)
        # $scope.apply_filter()

    #$scope.apply_filter = () ->
        # filter entries for table
        # $scope.filtered_entries = _.filter($scope.service_entries, (_v) -> return $scope.ls_filter.apply_filter(_v, true))
        # $scope.ls_filter.set_filtered_num($scope.host_entries.length, $scope.filtered_entries.length)

    $scope.$on("$destroy", () ->
        icswDeviceLivestatusDataService.destroy($scope.$id)
    )

]).service("icswMonitoringResult",
[
    "$q",
(
    $q,
) ->
    class icswMonitoringResult
        constructor: () ->
            # console.log "new MonRes"
            # selection generation
            @sel_generation = 0
            # result generation
            @generation = 0
            # notifier for new data
            @result_notifier = $q.defer()
            # notifier for new devices
            @selection_notifier = $q.defer()
            @hosts = []
            @services = []
            @filtered_hosts = []
            @filtered_services = []
            @used_cats = []

        new_selection: () =>
            @sel_generation++
            @selection_notifier.notify(@sel_generation)

        update: (hosts, services, used_cats) =>
            @generation++
            # console.log "update", @generation
            @result_notifier.notify(@generation)
            @hosts.length = 0
            for entry in hosts
                @hosts.push(entry)
            @services.length = 0
            for entry in services
                @services.push(entry)
            @used_cats = used_cats

        filter: (filter) =>
            # apply livestatus filter

            @filtered_hosts.length = 0
            for entry in @hosts
                if filter.service_types[entry.state_type] and filter.host_states[entry.state]
                    entry.$$show = true
                    @filtered_hosts.push(entry)
                else
                    entry.$$show = false

            # category filtering ?
            _cf = if filter.cat_filter_installed and filter.cat_filter_list? then true else false
            if _cf
                # show uncategorized entries
                _zero_cf = 0 in filter.cat_filter_list

            @filtered_services.length = 0
            for entry in @services
                if filter.service_types[entry.state_type] and filter.service_states[entry.state]
                    entry.$$show = true
                    if _cf
                        if entry.custom_variables? and entry.custom_variables.cat_pks?
                            if not _.intersection(filter.cat_filter_list, entry.custom_variables.cat_pks).length
                                entry.$$show = false
                        else if not _zero_cf
                            entry.$$show = false
                    if entry.$$show
                        @filtered_services.push(entry)
                else
                    entry.$$show = false

            # bump generation counter
            @generation++

]).service("icswDeviceLivestatusDataService",
[
    "ICSW_URLS", "$interval", "$timeout", "icswSimpleAjaxCall", "$q", "icswDeviceTreeService",
    "icswMonitoringResult", "icswSaltMonitoringResultService", "icswCategoryTreeService",
(
    ICSW_URLS, $interval, $timeout, icswSimpleAjaxCall, $q, icswDeviceTreeService,
    icswMonitoringResult, icswSaltMonitoringResultService, icswCategoryTreeService,
) ->
    # dict: device.idx -> watcher ids
    watch_dict = {}

    # dict: watcher ids -> Monitoring result
    result_dict = {}

    destroyed_list = []
    cur_interval = undefined
    cur_xhr = undefined
    schedule_start_timeout = undefined

    # for lookup
    device_tree = undefined
    category_tree = undefined

    watchers_present = () ->
        # whether any watchers are present
        return _.keys(result_dict).length > 0

    schedule_load = () ->
        # called when new listeners register
        # don't update immediately, wait until more controllers have registered
        if not schedule_start_timeout?
            schedule_start_timeout = $timeout(load_data, 1)

    start_interval = () ->
        # start regular update
        # this is additional to schedule_load
        if cur_interval?
            $interval.cancel(cur_interval)
        cur_interval = $interval(load_data, 20000) #20000)

    stop_interval = () ->
        # stop regular update
        if cur_interval?
            $interval.cancel(cur_interval)
        if cur_xhr?
            cur_xhr.abort()

    remove_watchers_by_client = (client) ->
        remove_device_watchers_by_client(client)
        # remove from result list
        delete result_dict[client.toString()]

    remove_device_watchers_by_client = (client) ->
        client = client.toString()
        for dev, watchers of watch_dict
            _.remove(watchers, (elem) -> return elem == client)

    load_data = () ->
        if schedule_start_timeout?
            $timeout.cancel(schedule_start_timeout)
            schedule_start_timeout = undefined

        # only continue if anyone is actually watching
        if watchers_present()

            watched_devs = []
            for dev of watch_dict
                if watch_dict[dev].length > 0
                    watched_devs.push(dev)

            _waiters = [
                icswSimpleAjaxCall(
                    url: ICSW_URLS.MON_GET_NODE_STATUS
                    data: {
                        pk_list: angular.toJson(watched_devs)
                    }
                    show_error: false
                )
            ]
            if not device_tree?
                _load_device_tree = true
                _waiters.push(
                    icswDeviceTreeService.load("liveStatusDataService")
                )
                _waiters.push(
                    icswCategoryTreeService.load("liveStatusDataService")
                )
            else
                _load_device_tree = false
            $q.allSettled(
                _waiters
            ).then(
                (result) ->
                    if _load_device_tree
                        # DeviceTreeService was requested
                        device_tree = result[1].value
                        category_tree = result[2].value
                    service_entries = []
                    host_entries = []
                    used_cats = []
                    if result[0].state == "fulfilled"
                        # fill service and host_entries, used cats
                        xml = result[0].value
                        $(xml).find("value[name='service_result']").each (idx, node) =>
                            service_entries = service_entries.concat(angular.fromJson($(node).text()))
                        $(xml).find("value[name='host_result']").each (idx, node) =>
                            host_entries = host_entries.concat(angular.fromJson($(node).text()))
                        for entry in host_entries
                            icswSaltMonitoringResultService.salt_host(entry, device_tree)
                        srv_id = 0
                        for entry in service_entries
                            srv_id++
                            entry.$$idx = srv_id
                            icswSaltMonitoringResultService.salt_service(entry, category_tree)
                            # host mon result
                            h_m_result = device_tree.all_lut[entry.custom_variables.device_pk].$$host_mon_result
                            # link
                            h_m_result.$$service_list.push(entry)
                            entry.$$host_mon_result = h_m_result
                            if entry.custom_variables and entry.custom_variables.cat_pks?
                                used_cats = _.union(used_cats, entry.custom_variables.cat_pks)
                    else
                        # invalidate results
                        for dev_idx, watchers of watch_dict
                            if dev_idx of device_tree.all_lut
                                device_tree.all_lut[dev_idx].$$host_mon_result = undefined
                    for client, _result of result_dict
                        # signal clients even when no results were received
                        hosts_client = []
                        services_client = []
                        # host_lut_client = {}
                        for dev_idx, watchers of watch_dict
                            if client in watchers and dev_idx of device_tree.all_lut
                                dev = device_tree.all_lut[dev_idx]
                                if dev.$$host_mon_result?
                                    entry = dev.$$host_mon_result
                                    hosts_client.push(entry)
                                    for check in entry.$$service_list
                                        services_client.push(check)
                        _result.update(hosts_client, services_client, used_cats)
            )

    return {
        # not needed here
        # resolve_host: (name) ->
        #    return _host_lut[name]

        retain: (client, dev_list) ->
            _defer = $q.defer()
            # get data for devices of dev_list for client (same client instance must be passed to cancel())

            # remove watchers in case of updates
            remove_device_watchers_by_client(client)

            client = client.toString()
            if client not in destroyed_list  # when client get the destroy event, they may still execute data, so we need to catch this here
                if not watchers_present()
                    # if no watchers have been present, there also was no regular update
                    start_interval()

                if dev_list.length
                    # console.log "w", dev_list
                    for dev in dev_list
                        if not watch_dict[dev.idx]?
                            watch_dict[dev.idx] = []

                        if client not in watch_dict[dev.idx]
                            watch_dict[dev.idx].push(client)

                if client not of result_dict
                    # console.log "n", client
                    result_dict[client] = new icswMonitoringResult()
                else
                    # console.log "k", client
                    result_dict[client].new_selection()

                _defer.resolve(result_dict[client])

                schedule_load()
            else
                _defer.reject("client in destroyed list")
                console.warn "client #{client} in destroyed_list"
            # the promise resolves always immediately
            return _defer.promise

        destroy: (client) ->
            client = client.toString()
            destroyed_list.push(client)
            # don't watch for client anymore
            remove_watchers_by_client(client)

            if not watchers_present()
                stop_interval()

        stop: (client) ->
            client = client.toString()
            # don't watch for client anymore
            remove_watchers_by_client(client)

            if not watchers_present()
                stop_interval()
    }
]).factory("icswBurstServiceDetail",
[
    "$q",
(
    $q,
) ->
    {div, ul, li, h3, span} = React.DOM
    return React.createClass(
        propTypes: {
            service: React.PropTypes.object
        }

        render: () ->
            _srvc = @props.service
            if _srvc
                if _srvc.$$dummy
                    _div_list = h3(
                        {key: "header"}
                        "Dummy segment"
                    )
                else
                    _ul_list = []
                    if _srvc.$$ct in ["system", "devicegroup"]
                        if _srvc.$$ct == "system"
                            _obj_name = "System"
                        else
                            _obj_name = _.capitalize(_srvc.$$ct) + " " + _srvc.display_name
                        _ul_list.push(
                            li(
                                {key: "li.state", className: "list-group-item"}
                                [
                                    "State"
                                    span(
                                        {key: "state.span", className: "pull-right #{_srvc.$$icswStateTextClass}"}
                                        _srvc.$$icswStateString
                                    )
                                ]
                            )
                        )
                    if _srvc.$$ct in ["device", "service"]
                        if _srvc.$$ct == "service"
                            _host = _srvc.$$host_mon_result
                            _obj_name = _.capitalize(_srvc.$$ct) + " " + _srvc.display_name
                        else
                            _host = _srvc
                            _obj_name = _.capitalize(_srvc.$$ct) + " " + _host.$$icswDevice.full_name
                        _path_span = [
                            _host.$$icswDeviceGroup.name
                            " "
                            span(
                                {key: "path.span2", className: "fa fa-arrow-right"}
                            )
                            " "
                            _host.$$icswDevice.full_name
                        ]
                        if _srvc.$$ct == "service"
                            _path_span = _path_span.concat(
                                [
                                    " "
                                    span(
                                        {key: "path.span3", className: "fa fa-arrow-right"}
                                    )
                                    " "
                                    _srvc.display_name
                                ]
                            )
                        _ul_list.push(
                            li(
                                {key: "li.path", className: "list-group-item"}
                                [
                                    "Path"
                                    span(
                                        {key: "path.span", className: "pull-right"}
                                        _path_span
                                    )
                                ]
                            )
                        )
                        # state li
                        _ul_list.push(
                            li(
                                {key: "li.state2", className: "list-group-item"}
                                [
                                    "State"
                                    span(
                                        {key: "state.span", className: "pull-right"}
                                        "#{_srvc.$$icswStateTypeString} #{_srvc.$$icswCheckTypeString}, "
                                        span(
                                            {key: "state.span2", className: _srvc.$$icswStateTextClass}
                                            _srvc.$$icswStateString
                                        )
                                        ", "
                                        span(
                                            {key: "state.span3", className: "label #{_srvc.$$icswAttemptLabelClass}"}
                                            _srvc.$$icswAttemptInfo
                                        )
                                    )
                                ]
                            )
                        )
                        # last check / last change
                        _ul_list.push(
                            li(
                                {key: "li.lclc", className: "list-group-item"}
                                [
                                    "last check / last change"
                                    span(
                                        {key: "lclc.span", className: "pull-right"}
                                        "#{_srvc.$$icswLastCheckString } / #{_srvc.$$icswLastStateChangeString}"
                                    )
                                ]
                            )
                        )
                        if _srvc.$$ct == "service"
                            # categories
                            _ul_list.push(
                                li(
                                    {key: "li.cats", className: "list-group-item"}
                                    [
                                        "Categories"
                                        span(
                                            {key: "cats.span", className: "pull-right"}
                                            "#{_srvc.$$icswCategories}"
                                        )
                                    ]
                                )
                            )
                        # output
                        _ul_list.push(
                            li(
                                {key: "li.output", className: "list-group-item"}
                                [
                                    "Output"
                                    span(
                                        {key: "output.span", className: "pull-right"}
                                        _srvc.plugin_output or "N/A"
                                    )
                                ]
                            )
                        )
                    _div_list = [
                        h3(
                            {key: "header"}
                            _obj_name
                        )
                        ul(
                            {key: "ul", className: "list-group"}
                            _ul_list
                        )
                    ]
            else
                _div_list = h3(
                    {key: "header"}
                    "Nothing selected"
                )
            return div(
                {key: "top"}
                _div_list
            )
    )
]).factory("icswBurstReactSegment",
[
    "$q",
(
    $q,
) ->
    {div, g, text, circle, path, svg, polyline} = React.DOM
    return React.createClass(
        propTypes: {
            element: React.PropTypes.object
            draw_parameters: React.PropTypes.object
            set_focus: React.PropTypes.func
            clear_focus: React.PropTypes.func
        }

        render: () ->
            _path_el = @props.element
            _color = _path_el.fill
            # if @state.focus
            #    _color = "#445566"

            # focus element
            _g_list = []
            _segment = {
                key: _path_el.key
                d: _path_el.d
                fill: _color
                stroke: _path_el.stroke
                strokeWidth: _path_el.strokeWidth
                onMouseEnter: @on_mouse_enter
                onMouseLeave: @on_mouse_leave
            }
            return path(_segment)

        on_mouse_enter: (event) ->
            # console.log "me"
            if @props.element.$$segment?
                @props.set_focus(@props.element.$$segment)

        on_mouse_leave: (event) ->
            # @props.clear_focus()
            # console.log "ml"
            # @setState({focus: false})
    )
]).factory("icswBurstReactSegmentText",
[
    "$q",
(
    $q,
) ->
    {div, g, text, circle, path, svg, polyline} = React.DOM
    return React.createClass(
        propTypes: {
            element: React.PropTypes.object
            draw_parameters: React.PropTypes.object
        }

        render: () ->
            _path_el = @props.element

            # add info
            if _path_el.$$segment? and not _path_el.$$segment.placeholder
                _g_list = []
                {text_radius, text_width} = @props.draw_parameters
                _sx = _path_el.$$mean_radius * Math.cos(_path_el.$$mean_arc)
                _sy = _path_el.$$mean_radius * Math.sin(_path_el.$$mean_arc)
                _ex = text_radius * Math.cos(_path_el.$$mean_arc)
                _ey = text_radius * Math.sin(_path_el.$$mean_arc)
                if _ex > 0
                    _ex2 = text_width
                    _text_anchor = "start"
                else
                    _ex2 = -text_width
                    _text_anchor = "end"
                _g_list.push(
                    polyline(
                        {
                            key: "burst.legend.line"
                            points: "#{_sx},#{_sy} #{_ex},#{_ey} #{_ex2},#{_ey}"
                            stroke: "black"
                            strokeWidth: "1"
                            fill: "none"
                        }
                    )
                )
                _g_list.push(
                    text(
                        {
                            key: "burst.legend.text"
                            x: _ex2
                            y: _ey
                            textAnchor: _text_anchor
                            alignmentBaseline: "middle"
                        }
                        _path_el.$$service.display_name
                    )
                )

                return g(
                    {key: "segment"}
                    _g_list
                )
            else
                return null
    )
]).factory("icswDeviceLivestatusBurstReactContainer",
[
    "$q", "ICSW_URLS", "icswSimpleAjaxCall", "icswNetworkTopologyReactSVGContainer",
    "icswDeviceLivestatusFunctions", "icswBurstDrawParameters", "icswBurstReactSegment",
    "icswBurstServiceDetail", "icswBurstReactSegmentText",
(
    $q, ICSW_URLS, icswSimpleAjaxCall, icswNetworkTopologyReactSVGContainer,
    icswDeviceLivestatusFunctions, icswBurstDrawParameters, icswBurstReactSegment,
    icswBurstServiceDetail, icswBurstReactSegmentText,
) ->
    # Network topology container, including selection and redraw button
    react_dom = ReactDOM
    {div, g, text, line, polyline, path, svg, h3} = React.DOM
    return React.createClass(
        propTypes: {
            # required types
            monitoring_data: React.PropTypes.object
            draw_parameters: React.PropTypes.object
        }

        componentDidMount: () ->

        getInitialState: () ->
            return {
                # to trigger redraw
                draw_counter: 0
                focus_element: undefined
            }

        new_monitoring_data_selection: () ->
            @new_monitoring_data_result()

        new_monitoring_data_result: () ->
            # force recalc of burst, todo: incremental root_node update
            @root_node = undefined
            # not very elegant
            @clear_focus()
            @trigger_redraw()

        componentDidMount: () ->
            @burst_element = $(react_dom.findDOMNode(@)).parents("react-burst")
            # console.log @burst_element, @burst_element[0]

        trigger_redraw: () ->
            @setState(
                {
                    draw_counter: @state.draw_counter + 1
                }
            )

        set_focus: (ring_el) ->
            @clear_focus()
            ring_el.set_focus()
            @setState({focus_element: ring_el})

        clear_focus: () ->
            if @root_node?
                @root_node.clear_foci()
            @setState({focus_element: undefined})

        render: () ->
            [_outer_width, _outer_height] = [0, 0]
            if @burst_element? and @burst_element.width()
                [_outer_width, _outer_height] = [@burst_element.width(), @burst_element.height()]
            # check if burst is interactive
            _ia = @props.draw_parameters.is_interactive
            if not @root_node?
                # console.log "rnd"
                @root_node = icswDeviceLivestatusFunctions.build_structured_burst(@props.monitoring_data, @props.draw_parameters)
            # console.log _outer_width, _outer_height
            root_node = @root_node
            # if _outer_width
            #    _outer = _.min([_outer_width, _outer_height])
            # else
            @props.draw_parameters.do_layout()
            _outer = @props.draw_parameters.outer_radius
            # console.log _outer
            if _ia
                # interactive, pathes have mouseover and click handler
                _g_list = (
                    React.createElement(
                        icswBurstReactSegment,
                        {
                            element: _element
                            set_focus: @set_focus
                            clear_focus: @clear_focus
                            draw_parameters: @props.draw_parameters
                        }
                    ) for _element in root_node.element_list
                )
                for _element in root_node.element_list
                    if _element.$$segment?
                        _seg = _element.$$segment
                        if _seg.show_legend
                            _g_list.push(
                                React.createElement(
                                    icswBurstReactSegmentText,
                                    {
                                        element: _element
                                        draw_parameters: @props.draw_parameters
                                    }
                                )
                            )
            else
                # not interactive, simple list of graphs
                _g_list = (path(_element) for _element in root_node.element_list)

            _svg = svg(
                {
                    key: "svg.top"
                    width: "#{@props.draw_parameters.total_width}px"
                    height: "#{@props.draw_parameters.total_height}px"
                    "font-family": "'Open-Sans', sans-serif"
                    "font-size": "10pt"
                }
                [
                    g(
                        {
                            key: "main"
                            transform: "translate(#{@props.draw_parameters.total_width / 2}, #{@props.draw_parameters.total_height / 2})"
                        }
                        _g_list
                    )
                ]
            )
            if _ia
                # console.log _fe
                if @state.focus_element?
                    _fe = @state.focus_element.check
                else
                    _fe = undefined
                # graph has a focus component
                _graph = div(
                    {
                        key: "top.div"
                        className: "row"
                    }
                    [
                        div(
                            {
                                key: "svg.div"
                                className: "col-xs-6"
                            }
                            [
                                h3(
                                    {key: "graph.header"}
                                    "Burst graph (" + @props.draw_parameters.get_segment_info() + ")"
                                )
                                _svg
                            ]
                        )
                        div(
                            {
                                key: "detail.div"
                                className: "col-xs-6"
                            }
                            React.createElement(icswBurstServiceDetail, {service: _fe})
                        )
                    ]
                )
            else
                # graph consists only of svg
                _graph = _svg
            return _graph 
    )

]).directive("reactBurst",
[
    "ICSW_URLS",
(
    ICSW_URLS,
) ->
    return {
        restrict: "EA"
        replace: true
        controller: "icswDeviceLivestatusBurstReactContainerCtrl"
        scope:
            filter: "=icswLivestatusFilter"
            data: "=icswMonitoringData"
            draw_params: "=icswDrawParameters"
        link: (scope, element, attrs) ->
            _mounted = false

            scope.$watch("data", (new_val) ->
                scope.struct.monitoring_data = new_val
                if scope.start_loop(element[0])
                    _mounted = true
            )

            scope.$watch("filter", (new_val) ->
                scope.struct.filter = new_val
                if scope.start_loop(element[0])
                    _mounted = true
            )

            scope.$on("$destroy", () ->
                if _mounted
                    ReactDOM.unmountComponentAtNode(element[0])
                    scope.struct.react_element = undefined
            )

    }
]).controller("icswDeviceLivestatusBurstReactContainerCtrl",
[
    "$scope", "icswDeviceTreeService", "icswDeviceLivestatusDataService", "$q",
    "icswDeviceLivestatusFunctions", "icswDeviceLivestatusBurstReactContainer",
    "icswBurstDrawParameters",
(
    $scope, icswDeviceTreeService, icswDeviceLivestatusDataService, $q,
    icswDeviceLivestatusFunctions, icswDeviceLivestatusBurstReactContainer,
    icswBurstDrawParameters,
) ->
    # $scope.host_entries = []
    # $scope.service_entries = []
    $scope.struct = {
        # monitoring data
        monitoring_data: undefined
        # filter
        filter: undefined
        # loop started
        loop_started: false
        # draw parameters, copy from scope
        draw_parameters: $scope.draw_params
        # react element
        react_element: undefined
    }

    _mount_burst = (element) ->
        $scope.struct.react_element = ReactDOM.render(
            React.createElement(
                icswDeviceLivestatusBurstReactContainer
                {
                    monitoring_data: $scope.struct.monitoring_data
                    draw_parameters: $scope.struct.draw_parameters
                }
            )
            element
        )


    $scope.start_loop = (element) ->
        if $scope.struct.monitoring_data and $scope.struct.filter and not $scope.struct.loop_started
            $scope.struct.loop_started = true
            $scope.struct.filter.change_notifier.promise.then(
                (ok) ->
                (error) ->
                (gen) ->
                    if $scope.struct.react_element?
                        $scope.struct.react_element.new_monitoring_data_result()
            )
            $scope.struct.monitoring_data.selection_notifier.promise.then(
                (ok) ->
                (error) ->
                (gen) ->
                    if $scope.struct.react_element?
                        $scope.struct.react_element.new_monitoring_data_selection()
            )
            _mount_burst(element)
            return true
        else
            return false

]).directive("newburst",
[
    "$compile", "$templateCache",
(
    $compile, $templateCache,
) ->
    return {
        restrict : "E"
        replace: true
        templateNamespace: "svg"
        template: $templateCache.get("icsw.device.livestatus.network_graph")
        controller: "icswDeviceLivestatusBurstCtrl"
        scope:
            filter: "=icswLivestatusFilter"
            data: "=icswMonitoringData"
            # device: "=icswDevice"
            # serviceFocus: "=serviceFocus"
            omitted_segments: "=omittedSegments"
            #ls_filter: "=lsFilter"
            #ls_devsel: "=lsDevsel"
            #is_drawn: "=isDrawn"
        link: (scope, element, attrs) ->
            scope.$watch("data", (new_val) ->
                scope.struct.monitoring_data = new_val
            )
            scope.$watch("filter", (new_val) ->
                scope.struct.filter = new_val
                if new_val
                    scope.start_loop()
            )

            scope.nodes = []
            scope.inner = parseInt(attrs["innerradius"] or 20)
            scope.outer = parseInt(attrs["outerradius"] or 120)
            scope.zoom = parseInt(attrs["zoom"] or 0)
            scope.font_stroke = parseInt(attrs["fontstroke"] or 0)
            scope.show_name = parseInt(attrs["showname"] or 0)
            scope.zoom_level = attrs["zoomLevel"] ? "s"
            scope.noninteractive = attrs["noninteractive"]  # defaults to false
            scope.active_part = null
            scope.propagate_filter = if attrs["propagateFilter"] then true else false
            #if not attrs["devicePk"]
            #    scope.$watch(
            #        scope.ls_devsel.changed
            #        (changed) ->
            #            scope.burst_sel(scope.ls_devsel.get(), false)
            #    )
            #scope.$watch("device_pk", (new_val) ->
            #    if new_val
            #        if angular.isString(new_val)
            #            data = (parseInt(_v) for _v in new_val.split(","))
            #        else
            #            data = [new_val]
            #        scope.burst_sel(data, true)
            #)
            # scope.burst_sel([scope.device], true)
            if attrs["drawAll"]?
                scope.draw_all = true
            else
                scope.draw_all = false
            scope.create_node = (name, settings) ->
                ns = 'http://www.w3.org/2000/svg'
                node = document.createElementNS(ns, name)
                for attr of settings
                    value = settings[attr]
                    if value?
                        node.setAttribute(attr, value)
                return node
            scope.get_children = (node, depth, struct) ->
                _num = 0
                if node.children.length
                    for _child in node.children
                        _num += scope.get_children(_child, depth+1, struct)
                else
                    if node.value?
                        _num = node.value
                node.width = _num
                if not struct[depth]?
                    struct[depth] = []
                struct[depth].push(node)
                return _num
            scope.set_focus_service = (srvc) ->
                if "serviceFocus" of attrs
                    scope.serviceFocus = srvc
            scope.set_data = (data, name) ->
                scope.sunburst_data = data
                scope.name = name
                # struct: dict of concentric circles, beginning with the innermost
                struct = {}
                scope.get_children(scope.sunburst_data, 0, struct)
                scope.max_depth = (idx for idx of struct).length
                scope.nodes = []
                omitted_segments = 0
                for idx of struct
                    if struct[idx].length
                        omitted_segments += scope.add_circle(parseInt(idx), struct[idx])
                # console.log "nodes", scope.nodes
                if attrs["omittedSegments"]?
                    scope.omittedSegments = omitted_segments
                if attrs["isDrawn"]?
                    scope.is_drawn = 1
            scope.add_circle = (idx, nodes) ->
                _len = _.reduce(
                    nodes,
                    (sum, obj) ->
                        return sum + obj.width
                    0
                )
                omitted_segments = 0
                outer = scope.get_inner(idx)
                inner = scope.get_outer(idx)
                # no nodes defined or first node is a dummy node (== no devices / checks found)
                if not _len or nodes[0].dummy
                    # create a dummy part
                    dummy_part = {}
                    dummy_part.children = {}
                    dummy_part.path = "M#{outer},0 " + \
                        "A#{outer},#{outer} 0 1,1 #{-outer},0 " + \
                        "A#{outer},#{outer} 0 1,1 #{outer},0 " + \
                        "L#{outer},0 " + \
                        "M#{inner},0 " + \
                        "A#{inner},#{inner} 0 1,0 #{-inner},0 " + \
                        "A#{inner},#{inner} 0 1,0 #{inner},0 " + \
                        "L#{inner},0 " + \
                        "Z"
                    scope.nodes.push(dummy_part)
                else
                    end_arc = 0
                    end_num = 0
                    # legend radii
                    inner_legend = (outer + inner) / 2
                    outer_legend = scope.outer * 1.125
                    local_omitted = 0
                    for part in nodes
                        if part.width
                            start_arc = end_arc #+ 1 * Math.PI / 180
                            start_sin = Math.sin(start_arc)
                            start_cos = Math.cos(start_arc)
                            end_num += part.width
                            end_arc = 2 * Math.PI * end_num / _len
                            if (end_arc - start_arc) * outer < 3 and not scope.draw_all
                                # arc is too small, do not draw
                                omitted_segments++
                                local_omitted++
                            else if part.placeholder
                                true
                            else
                                # console.log end_arc - start_arc
                                mean_arc = (start_arc + end_arc) / 2
                                mean_sin = Math.sin(mean_arc)
                                mean_cos = Math.cos(mean_arc)
                                end_sin = Math.sin(end_arc)
                                end_cos = Math.cos(end_arc)
                                if end_arc > start_arc + Math.PI
                                    _large_arc_flag = 1
                                else
                                    _large_arc_flag = 0
                                if mean_cos < 0
                                    legend_x = -outer_legend * 1.2
                                    part.legend_anchor = "end"
                                else
                                    legend_x = outer_legend * 1.2
                                    part.legend_anchor = "start"
                                part.legend_x = legend_x
                                part.legend_y = mean_sin * outer_legend
                                part.legendpath = "#{mean_cos * inner_legend},#{mean_sin * inner_legend} #{mean_cos * outer_legend},#{mean_sin * outer_legend} " + \
                                    "#{legend_x},#{mean_sin * outer_legend}"
                                if part.width == _len
                                    # trick: draw 2 semicircles
                                    part.path = "M#{outer},0 " + \
                                        "A#{outer},#{outer} 0 1,1 #{-outer},0 " + \
                                        "A#{outer},#{outer} 0 1,1 #{outer},0 " + \
                                        "L#{outer},0 " + \
                                        "M#{inner},0 " + \
                                        "A#{inner},#{inner} 0 1,0 #{-inner},0 " + \
                                        "A#{inner},#{inner} 0 1,0 #{inner},0 " + \
                                        "L#{inner},0 " + \
                                        "Z"
                                else
                                    part.path = "M#{start_cos * inner},#{start_sin * inner} L#{start_cos * outer},#{start_sin * outer} " + \
                                        "A#{outer},#{outer} 0 #{_large_arc_flag} 1 #{end_cos * outer},#{end_sin * outer} " + \
                                        "L#{end_cos * inner},#{end_sin * inner} " + \
                                        "A#{inner},#{inner} 0 #{_large_arc_flag} 0 #{start_cos * inner},#{start_sin * inner} " + \
                                        "Z"
                                scope.nodes.push(part)
                    if local_omitted
                        # some segmens were omitted, draw a circle
                        dummy_part = {children: {}, omitted: true}
                        dummy_part.path = "M#{outer},0 " + \
                            "A#{outer},#{outer} 0 1,1 #{-outer},0 " + \
                            "A#{outer},#{outer} 0 1,1 #{outer},0 " + \
                            "L#{outer},0 " + \
                            "M#{inner},0 " + \
                            "A#{inner},#{inner} 0 1,0 #{-inner},0 " + \
                            "A#{inner},#{inner} 0 1,0 #{inner},0 " + \
                            "L#{inner},0 " + \
                            "Z"
                        scope.nodes.push(dummy_part)
                return omitted_segments
            scope.get_inner = (idx) ->
                _inner = scope.inner + (scope.outer - scope.inner) * idx / scope.max_depth
                return _inner
            scope.get_outer = (idx) ->
                _outer = scope.inner + (scope.outer - scope.inner) * (idx + 1) / scope.max_depth
                return _outer
            scope.get_fill_color = (part) ->
                if part.check?
                    if part.check.ct == "system"
                        color = {
                            0 : "#66dd66"
                            1 : "#ff7777"
                            2 : "#ff0000"
                            4 : "#eeeeee"
                        }[part.check.state]
                    else if part.check.ct == "host"
                        color = {
                            0 : "#66dd66"
                            1 : "#ff7777"
                            2 : "#ff0000"
                        }[part.check.state]
                    else
                        color = {
                            0 : "#66dd66"
                            1 : "#dddd88"
                            2 : "#ff7777"
                            3 : "#ff0000"
                        }[part.check.state]
                else if part.omitted?
                    color = "#ffffff"
                else
                    color = "#dddddd"
                return color
            scope.get_fill_opacity = (part) ->
                if part.mouseover? and part.mouseover
                    return 0.4
                else if part.omitted
                    return 0
                else
                    return 0.8
            scope.mouse_enter = (part) ->
                if !scope.noninteractive
                    # console.log "enter"
                    if scope.active_part
                        # console.log "leave"
                        scope._mouse_leave(scope.active_part)
                    scope.set_focus_service(part.check)
                    if part.children.length
                        for _entry in part.children
                            if _entry.value
                                _entry.legend_show = true
                    else
                        if part.value
                            part.legend_show = true
                    scope.active_part = part
                    scope.set_mouseover(part, true)
            scope.mouse_click = (part) ->
                if scope.zoom and !scope.noninteractive
                    scope.sunburst_data.clear_clicked()
                    part.clicked = true
                    scope.handle_section_click()
            scope.mouse_leave = (part) ->
            scope._mouse_leave = (part) ->
                if !scope.noninteractive
                    if part.children.length
                        for _entry in part.children
                            _entry.legend_show = false
                    else
                        part.legend_show = false
                    scope.set_mouseover(part, false)
            scope.set_mouseover = (part, flag) ->
                while true
                    part.mouseover = flag
                    if part.parent?
                        part = part.parent
                    else
                        break
    }
]).controller("icswDeviceLivestatusBurstCtrl",
[
    "$scope", "icswDeviceTreeService", "icswDeviceLivestatusDataService", "$q",
    "icswDeviceLivestatusFunctions",
(
    $scope, icswDeviceTreeService, icswDeviceLivestatusDataService, $q,
    icswDeviceLivestatusFunctions,
) ->
    # $scope.host_entries = []
    # $scope.service_entries = []
    $scope.struct = {
        # monitoring data
        monitoring_data: undefined
        # filter
        filter: undefined
    }

    $scope.start_loop = () ->
        # console.log "start loop"
        $scope.struct.filter.change_notifier.promise.then(
            (ok) ->
            (error) ->
            (gen) ->
                b_data = icswDeviceLivestatusFunctions.build_structured_burst($scope.struct.monitoring_data)
                # console.log b_data
                $scope.set_data(b_data, "bla")
        )
    $scope._burst_data = null
    filter_propagated = false
    filter_list = []
    ignore_filter = false
    $scope.burst_sel = (_dev_list, single_selection) ->
        $scope.single_selection = single_selection
        $scope._burst_sel = _dev_list
        wait_list = [
            icswDeviceTreeService.load($scope.$id)
            icswDeviceLivestatusDataService.retain($scope.$id, _dev_list)
        ]
        $q.all(wait_list).then(
            (data) ->
                $scope.dev_tree_lut = data[0].enabled_lut
                $scope.new_data(data[1])
                $scope.$watch(
                    () ->
                        return data[1].generation
                    () ->
                        $scope.new_data(data[1])
                )
        )
        $scope.new_data = (mres) ->
            $scope.host_entries = mres.hosts
            $scope.service_entries = mres.services
            $scope.burst_data = $scope.build_sunburst(
                $scope.host_entries
                $scope.service_entries
            )
            $scope.md_filter_changed()

        $scope.$watch("ls_filter", (new_val) ->
            if new_val
                # wait until ls_filter is set
                $scope.$watch(
                    new_val.changed
                    (new_filter) ->
                        $scope.md_filter_changed()

                )
        )
        $scope.apply_click_filter = (check) ->
            if filter_list.length and check._srv_id not in filter_list
                return false
            else
                return true

        $scope.handle_section_click = () ->
            # handle click on a defined section
            if $scope.burst_data? and $scope.dev_tree_lut?
                if $scope.burst_data.any_clicked()
                    $scope.burst_data.handle_clicked()
                if $scope.propagate_filter and not filter_propagated
                    filter_propagated = true
                    # register filter function
                    $scope.ls_filter.register_filter_func($scope.apply_click_filter)
                # create a list of all unique ids which are actually displayed
                filter_list = (entry.check._srv_id for entry in $scope.burst_data.get_childs((node) -> return node.show))
                # trigger filter change
                $scope.ls_filter.trigger()

        $scope.md_filter_changed = () ->
            # filter entries for table
            if $scope.ls_filter?
                # filter burstData
                if $scope.burst_data? and $scope.dev_tree_lut?
                    (_check_filter(_v) for _v in $scope.burst_data.get_childs(
                        (node) -> return node.filter)
                    )
                    if $scope.single_selection
                        $scope.set_data($scope.burst_data, $scope._burst_sel[0].full_name)
                    else
                        $scope.set_data($scope.burst_data, "")

        $scope.build_sunburst = (host_entries, service_entries) ->
            # build burst data
            _bdat = new hs_node(
                "System"
                # state 4: not set
                {"state": 4, "idx" : 0, "ct": "system"}
            )
            _devg_lut = {}
            # lut: dev idx to hs_nodes
            dev_hs_lut = {}
            for entry in host_entries
                if entry.custom_variables.device_pk of $scope.dev_tree_lut
                    _dev = $scope.dev_tree_lut[entry.custom_variables.device_pk]
                    if _dev.device_group_name not of _devg_lut
                        # we use the same index for devicegroups and services ...
                        _devg = new hs_node(
                            _dev.device_group_name
                            {
                                "ct"    : "group"
                                "state" : 0
                                "group_name" : _dev.device_group_name
                            }
                        )
                        _bdat.check.state = 0
                        _devg_lut[_devg.name] = _devg
                        _bdat.add_child(_devg)
                    else
                        _devg = _devg_lut[_dev.device_group_name]
                    # sunburst struct for device
                    entry.group_name = _dev.device_group_name
                    _dev_sbs = new hs_node(_dev.full_name, entry)
                    _devg.add_child(_dev_sbs)
                    # set devicegroup state
                    _devg.check.state = Math.max(_devg.check.state, _dev_sbs.check.state)
                    # set system state
                    _bdat.check.state = Math.max(_bdat.check.state, _devg.check.state)
                    dev_hs_lut[_dev.idx] = _dev_sbs
            for entry in service_entries
                # sanitize entries
                if entry.custom_variables.device_pk of $scope.dev_tree_lut
                    dev_hs_lut[entry.custom_variables.device_pk].add_child(new hs_node(entry.description, entry, true))
            for idx, dev of dev_hs_lut
                if not dev.children.length
                    # add placeholder for non-existing services
                    dev.add_child(new hs_node("", {}, true, true))
            if $scope.zoom_level == "d"
                if _bdat.valid_device()
                    # valid device substructure, add dummy
                    return _bdat.reduce().reduce()
                else
                    _dev = new hs_node("", {}, false, true, true)
                    return _dev
            else if $scope.zoom_level == "g"
                return _bdat.reduce()
            else
                return _bdat

        _check_filter = (entry) ->
            show = $scope.ls_filter.apply_filter(entry.check, entry.show)
            entry.value = if show then 1 else 0
            return show

        $scope.$on("$destroy", () ->
            icswDeviceLivestatusDataService.destroy($scope.$id)
        )

]).directive("icswDeviceLivestatus",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.livestatus.overview")
        controller: "icswDeviceLiveStatusCtrl"
    }
]).directive("icswDeviceLivestatusBrief",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.livestatus.brief")
        controller: "icswDeviceLiveStatusBriefCtrl"
        scope:
             device: "=icswDevice"
        link : (scope, element, attrs) ->
            scope.new_devsel([scope.device])
    }
]).controller("icswDeviceLiveStatusBriefCtrl",
[
    "$scope", "$compile", "$templateCache", "Restangular",
    "$q", "$timeout", "icswTools", "ICSW_URLS", "icswSimpleAjaxCall",
    "icswDeviceLivestatusDataService", "icswCachingCall", "icswLivestatusFilterService",
    "icswBurstDrawParameters",
(
    $scope, $compile, $templateCache, Restangular,
    $q, $timeout, icswTools, ICSW_URLS, icswSimpleAjaxCall,
    icswDeviceLivestatusDataService, icswCachingCall, icswLivestatusFilterService,
    icswBurstDrawParameters,
) ->
    $scope.struct = {
        # filter
        filter: new icswLivestatusFilterService()
        # monitoring data
        monitoring_data: undefined
        # draw parameters
        draw_parameters: new icswBurstDrawParameters(
            {
                inner_radius: 0
                outer_radius: 20
                start_ring: 2
            }
        )
    }

    # layout functions

    $scope.filter_changed = () ->
        if $scope.struct.filter?
            $scope.struct.filter.set_monitoring_data($scope.struct.monitoring_data)

    $scope.new_devsel = (_dev_sel) ->
        # console.log "DS", _dev_sel

        #pre_sel = (dev.idx for dev in $scope.devices when dev.expanded)
        wait_list = [
            icswDeviceLivestatusDataService.retain($scope.$id, _dev_sel)
        ]
        $q.all(wait_list).then(
            (data) ->
                $scope.struct.monitoring_data = data[0]
                $scope.struct.monitoring_data.result_notifier.promise.then(
                    (ok) ->
                        console.log "dr ok"
                    (not_ok) ->
                        console.log "dr error"
                    (generation) ->
                        # console.log "data here", $scope.struct.monitoring_data
                        $scope.filter_changed()
                )
        )
]).directive("icswDeviceLivestatusMap", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.livestatus.map")
        controller: "icswDeviceLiveStatusCtrl"
        scope:
             devicepk: "@devicepk"
             # flag when svg is finished
             is_drawn: "=isDrawn"
             # external filter
             ls_filter: "=lsFilter"
        replace: true
        link : (scope, element, attrs) ->
            scope.$watch("devicepk", (data) ->
                if data
                    data = (parseInt(_v) for _v in data.split(","))
                    scope.new_devsel(data, [])
            )
    }
]).directive("icswDeviceLivestatusTableView",
[
    "$templateCache",
(
    $templateCache,
) ->
        return {
            restrict: "EA"
            template: $templateCache.get("icsw.device.livestatus.table.view")
            controller: "icswDeviceLivestatusTableCtrl"
            scope: {
                filter: "=icswLivestatusFilter"
                data: "=icswMonitoringData"
            }
            link: (scope, element, attrs) ->
                scope.$watch("data", (new_val) ->
                    scope.struct.monitoring_data = new_val
                )
        }
]).directive("icswDeviceLivestatusTableRow",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.livestatus.table.row")
    }
]).controller("icswDeviceLivestatusTableCtrl",
[
    "$scope",
(
    $scope,
) ->
    $scope.struct = {
        # filter
        filter: undefined
        # monitoring data
        monitoring_data: undefined
    }
    $scope.struct.filter = $scope.filter
    # console.log "struct=", $scope.struct

]).directive('icswDeviceLivestatusFullburst',
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.livestatus.fullburst")
        scope: {
            filter: "=icswLivestatusFilter"
            data: "=icswMonitoringData"
            size: "=icswElementSize"
        }
        controller: "icswDeviceLivestatusFullburstCtrl"
        link: (scope, element, attrs) ->
            scope.$watch("data", (new_val) ->
                # console.log "FB data set", new_val
                scope.struct.monitoring_data = new_val
            )
            scope.$watch("filter", (new_val) ->
                scope.struct.filter = new_val
            )
            # omitted segments
            scope.width = parseInt(attrs["initialWidth"] or "600")
            # not working ...
            if false
                scope.$watch("size", (new_val) ->
                    if new_val
                        console.log "new_width=", new_val
                        _w = new_val.width / 2
                        if _w != scope.width
                            svg_el = element.find("svg")[0]
                            g_el = element.find("svg > g")[0]
                            scope.width = _w
                            svg_el.setAttribute("width", _w)
                            g_el.setAttribute("transform", "translate(#{_w / 2}, 160)")
                )
    }
]).controller("icswDeviceLivestatusFullburstCtrl", [
    "$scope", "icswBurstDrawParameters",
(
    $scope, icswBurstDrawParameters,
) ->
    $scope.struct = {
        # monitoring data
        monitoring_data: undefined
        # filter
        filter: undefined
        # draw parameters
        draw_parameters: new icswBurstDrawParameters(
            {
                inner_radius: 40
                outer_radius: 160
                start_ring: 0
                is_interactive: true
                omit_small_segments: true
            }
        )
    }
]).directive("icswDeviceLivestatusDeviceNode", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        replace: true
        template: $templateCache.get("icsw.device.livestatus.device.node")
        scope: {
            "dml": "=dml"
            "ls_filter": "=lsFilter"
        }
        link: (scope, element, attrs) ->
            # for network with connections
            dml = scope.dml
            scope.transform = "translate(#{dml.pos_x},#{dml.pos_y})"
    }
]).directive("icswDeviceLivestatusMaplist",
[
    "$compile", "$templateCache", "icswCachingCall", "$q", "ICSW_URLS", "$timeout",
(
    $compile, $templateCache, icswCachingCall, $q, ICSW_URLS, $timeout,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.livestatus.maplist")
        scope: {
            devices: "=icswDevices"
            data: "=icswMonitoringData"
            filter: "=icswLivestatusFilter"
        }
        link: (scope, element, attrs) ->
            scope.$watch("data", (new_val) ->
                scope.struct.monitoring_data = new_val
            )
            scope.$watch(
                "devices"
                (new_val) ->
                    scope.new_devsel(new_val)
                true
            )
        controller: "icswDeviceLivestatusMaplistCtrl"
    }
]).controller("icswDeviceLivestatusMaplistCtrl",
[
    "$scope", "icswCategoryTreeService", "$q", "$timeout", "$compile", "$templateCache",
    "icswComplexModalService", "toaster",
(
    $scope, icswCategoryTreeService, $q, $timeout, $compile, $templateCache,
    icswComplexModalService, toaster,
) ->

    $scope.struct = {
        # data valid
        data_valid: false
        # category tree
        cat_tree: undefined
        # gfx sizes
        gfx_sizes: ["1024x768", "1280x1024", "1920x1200", "800x600", "640x400"]
        # cur gfx
        cur_gfx_size: undefined
        # any maps present
        maps_present: false
        # monitoring data
        monitoring_data: undefined
        # devices
        devices: []
        # location list
        loc_gfx_list: []
        # autorotate
        autorotate: false
        # page idx for autorotate
        page_idx: 0
        # page idx set by uib-tab
        cur_page_idx: 0
        # filter
        filter: undefined
    }
    $scope.struct.cur_gfx_size = $scope.struct.gfx_sizes[0]
    console.log "F", $scope.filter
    $scope.struct.filter = $scope.filter

    load = () ->
        $scope.struct.data_valid = false
        $scope.struct.maps_present = false
        $q.all(
            [
                icswCategoryTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.cat_tree = data[0]
                $scope.struct.data_valid = true
                if $scope.struct.devices.length
                    check_for_maps()
        )

    check_for_maps = () ->
        # check for valid maps for current device selection
        $scope.struct.loc_gfx_list.length = 0
        $scope.struct.page_idx = 0
        _deactivate_rotation()
        loc_idx_used = []
        dev_idx = (dev.idx for dev in $scope.struct.devices)
        for gfx in $scope.struct.cat_tree.gfx_list
            gfx.$$filtered_dml_list = []
            for dml in gfx.$dml_list
                if dml.device in dev_idx and dml.location_gfx not in loc_idx_used
                    loc_idx_used.push(gfx.idx)
                    $scope.struct.loc_gfx_list.push(gfx)
                    gfx.$$filtered_dml_list.push(dml)
                    gfx.$$page_idx = $scope.struct.loc_gfx_list.length
        $scope.struct.maps_present = $scope.struct.loc_gfx_list.length > 0
                    
    $scope.new_devsel = (devs) ->
        $scope.struct.devices.length = 0
        for dev in devs
            $scope.struct.devices.push(dev)
        if $scope.struct.data_valid
            check_for_maps()

    load()

    # rotation functions

    _activate_rotation = () ->
        _pi = $scope.struct.page_idx
        _pi++
        if _pi < 1
            _pi = 1
        if _pi > $scope.struct.loc_gfx_list.length
            _pi = 1
        $scope.struct.page_idx = _pi
        $scope.struct.autorotate_timeout = $timeout(_activate_rotation, 8000)

    _deactivate_rotation = () ->
        $scope.struct.autorotate = false
        if $scope.struct.autorotate_timeout
            $timeout.cancel($scope.struct.autorotate_timeout)
            $scope.struct.autorotate_timeout = undefined

    $scope.toggle_autorotate = () ->
        $scope.struct.autorotate = !$scope.struct.autorotate
        if $scope.struct.autorotate
            _activate_rotation()
        else
            _deactivate_rotation()

    $scope.set_page_idx = (loc_gfx) ->
        $scope.struct.cur_page_idx = loc_gfx.$$page_idx

    $scope.show_settings = () ->
        sub_scope = $scope.$new(false)
        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.device.livestatus.maplist.settings"))(sub_scope)
                title: "Map settings"
                # css_class: "modal-wide"
                ok_label: "close"
                closable: true
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "", 0)
                        d.reject("form not valid")
                    else
                        d.resolve("updated")
                    return d.promise
            }
        ).then(
            (fin) ->
                sub_scope.$destroy()
        )

]).factory("icswDeviceLivestatusLocationMapReact",
[
    "$q", "icswDeviceLivestatusReactBurst",
(
    $q, icswDeviceLivestatusReactBurst,
) ->
    {div, h4, g, image, svg, polyline} = React.DOM

    return React.createClass(
        propTypes: {
            location_gfx: React.PropTypes.object
            monitoring_data: React.PropTypes.object
            draw_parameters: React.PropTypes.object
            device_tree: React.PropTypes.object
            livestatus_filter: React.PropTypes.object
        }

        getInitialState: () ->
            return {
                width: 640
                height: 400
                counter: 0
            }

        set_size: (size_str) ->
            [_width, _height] = size_str.split("x")
            @setState(
                {
                    width: parseInt(_width)
                    height: parseInt(_height)
                }
            )

        componentWillMount: () ->
            # @umount_defer = $q.defer()
            @props.livestatus_filter.change_notifier.promise.then(
                () ->
                () ->
                    # will get called when the component unmounts
                (c) =>
                    @force_redraw()
            )

        componentWillUnmount: () ->
            @umount_defer.reject("stop")

        force_redraw: () ->
            @setState(
                {counter: @state.counter + 1}
            )

        render: () ->
            _gfx = @props.location_gfx
            {width, height} = @state
            _header = _gfx.name
            if _gfx.comment
                _header = "#{_header} (#{_gfx.comment})"

            _dml_list = [
                image(
                    {
                        key: "bgimage"
                        width: width
                        height: height
                        href: _gfx.image_url
                    }
                )
                polyline(
                    {
                        key: "imageborder"
                        style: {fill:"none", stroke:"black", strokeWidth:"3"}
                        points: "0,0 #{width},0 #{width},#{height} 0,#{height} 0 0"
                    }
                )
            ]
            # console.log @props
            for dml in _gfx.$$filtered_dml_list
                # build node
                node = {
                    id: dml.device
                    x: dml.pos_x
                    y: dml.pos_y
                }
                _dml_list.push(
                    React.createElement(
                        icswDeviceLivestatusReactBurst
                        {
                            node: node
                            monitoring_data: @props.monitoring_data
                            draw_parameters: @props.draw_parameters
                        }
                    )
                )
            return div(
                {key: "top"}
                [
                    h4(
                        {key: "header"}
                        _header
                    )
                    svg(
                        {
                            key: "svgouter"
                            width: width
                            height: height
                            preserveAspectRatio: "xMidYMid meet"
                            viewBox: "0 0 #{width} #{height}"
                        }
                        [
                            g(
                                {
                                    key: "gouter"
                                }
                                _dml_list
                            )
                        ]
                    )

                ]
            )
    )
]).directive("icswDeviceLivestatusLocationMap",
[
    "$templateCache", "$compile", "Restangular", "icswDeviceLivestatusLocationMapReact",
    "icswBurstDrawParameters", "icswDeviceTreeService", "$q",
(
    $templateCache, $compile, Restangular, icswDeviceLivestatusLocationMapReact,
    icswBurstDrawParameters, icswDeviceTreeService, $q,
) ->
    return {
        restrict: "EA"
        # template: $templateCache.get("icsw.device.livestatus.location.map")
        scope:
            loc_gfx: "=icswLocationGfx"
            monitoring_data: "=icswMonitoringData"
            filter: "=icswLivestatusFilter"
            gfx_size: "=icswGfxSize"
        link : (scope, element, attrs) ->
            draw_params = new icswBurstDrawParameters(
                {
                    inner_radius: 0
                    outer_radius: 90
                }
            )
            $q.all(
                [
                    icswDeviceTreeService.load(scope.$id)
                ]
            ).then(
                (data) ->
                    device_tree = data[0]
                    # console.log scope.monitoring_data, scope.filter
                    react_el = ReactDOM.render(
                        React.createElement(
                            icswDeviceLivestatusLocationMapReact
                            {
                                livestatus_filter: scope.filter
                                location_gfx: scope.loc_gfx
                                monitoring_data: scope.monitoring_data
                                draw_parameters: draw_params
                                device_tree: device_tree
                            }
                        )
                        element[0]
                    )
                    scope.monitoring_data.result_notifier.promise.then(
                        () ->
                        () ->
                        (generation) =>
                            # console.log "gen", @props.livestatus_filter, @monitoring_data
                            console.log "new_gen", generation
                            react_el.force_redraw()
                    )
                    scope.$watch("gfx_size", (new_val) ->
                        react_el.set_size(new_val)
                    )
            )
    }
])
