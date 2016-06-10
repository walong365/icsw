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

# livestatus sources and filter functions
angular.module(
    "icsw.livestatus.comp.sources",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.router",
    ]
).service("icswLivestatusFilterService",
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
])
