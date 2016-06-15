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

# livestatus sources and filter functions (components)

angular.module(
    "icsw.livestatus.comp.sources",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.router",
    ]
).service("icswLivestatusFilterService",
[
    "$q", "$rootScope", "icswMonLivestatusPipeBase", "icswMonitoringResult",
(
    $q, $rootScope, icswMonLivestatusPipeBase, icswMonitoringResult,
) ->
    # ToDo: separate data / filtered data from filter
    running_id = 0
    class icswLivestatusFilter extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusFilter", true, true)
            @set_template('<icsw-livestatus-filter-display icsw-livestatus-filter="con_element"></icsw-livestatus-filter-display>', "BaseFilter")
            running_id++
            @id = running_id
            @_latest_data = undefined
            # emit data
            @_emit_data = new icswMonitoringResult()
            @_local_init()

        filter_changed: () ->
            # callback from React
            if @_latest_data?
                @emit_data_downstream(@new_data_received(@_latest_data))

        new_data_received: (data) =>
            @_latest_data = data
            @n_hosts = data.hosts.length
            @n_services = data.services.length
            @categories = data.categories

            @_emit_data.apply_base_filter(@, @_latest_data)
            @f_hosts = @_emit_data.hosts.length
            @f_services = @_emit_data.services.length
            @react_notifier.notify()
            return @_emit_data
            # @change_notifier.notify()

        pipeline_reject_called: (reject) ->
            # ignore, stop processing

        _local_init: () =>
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

            @react_notifier = $q.defer()
            @change_notifier = $q.defer()
            # category filter settings
            @cat_filter_installed = false

        # install_category_filter: () =>
        #     @cat_filter_installed = true
        #     @cat_filter_list = undefined

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
            # filter_changed_cb: React.PropTypes.func
        }
        getInitialState: () ->
            return {
                filter_state_str: @props.livestatus_filter.get_filter_state_str()
                display_iter: 0
            }

        componentWillMount: () ->
            # @umount_defer = $q.defer()
            @props.livestatus_filter.react_notifier.promise.then(
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
                @props.livestatus_filter.filter_changed()

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
            return div(
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
        link: (scope, element, attr) ->
            ReactDOM.render(
                React.createElement(
                    icswLivestatusFilterReactDisplay
                    {
                        livestatus_filter: scope.filter
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
            @hosts = []
            @services = []
            @used_cats = []

        new_selection: () =>
            # hm, not needed ... ?
            @sel_generation++

        stop_receive: () =>
            @result_notifier.reject("stop")

        update: (hosts, services, used_cats) =>
            @generation++
            @hosts.length = 0
            for entry in hosts
                @hosts.push(entry)
            @services.length = 0
            for entry in services
                @services.push(entry)
            @used_cats = used_cats
            # console.log "update", @generation
            @result_notifier.notify(@generation)

        apply_base_filter: (filter, src_data) =>
            # apply base livestatus filter
            @hosts.length = 0
            for entry in src_data.hosts
                if filter.service_types[entry.state_type] and filter.host_states[entry.state]
                    @hosts.push(entry)

            # category filtering ?
            @services.length = 0
            for entry in src_data.services
                if filter.service_types[entry.state_type] and filter.service_states[entry.state]
                    @services.push(entry)
            # simply copy
            @used_cats.length = 0
            for entry in src_data.used_cats
                @used_cats.push(entry)

            # bump generation counter
            @generation++

        apply_category_filter: (cat_list, src_data) =>
            @hosts.length = 0
            for entry in src_data.hosts
                @hosts.push(entry)
            # show uncategorized entries
            _zero_cf = 0 in cat_list
            @services.length = 0
            for entry in src_data.services
                _add = true
                if entry.custom_variables? and entry.custom_variables.cat_pks?
                    if not _.intersection(cat_list, entry.custom_variables.cat_pks).length
                        _add = false
                else if not _zero_cf
                    _add = false
                if _add # entry.$$show
                    @services.push(entry)
            # simply copy
            @used_cats.length = 0
            for entry in src_data.used_cats
                if entry in cat_list
                    @used_cats.push(entry)
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
        console.log "RWBC", client.toString(), result_dict[client.toString()]
        result_dict[client.toString()].stop_receive()
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
                    # not really needed ?
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
]).service("icswLivestatusDataSource",
[
    "$q", "$rootScope", "icswMonLivestatusPipeBase", "$timeout",
    "icswDeviceTreeService", "icswDeviceLivestatusDataService", "icswTools",
(
    $q, $rootScope, icswMonLivestatusPipeBase, $timeout,
    icswDeviceTreeService, icswDeviceLivestatusDataService, icswTools,
) ->
    class icswLivestatusDataSource extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusDataSource", false, true)
            @_my_id = icswTools.get_unique_id()
            @struct = {
                # device list
                devices: []
                # is updating
                updating: false
                # data fetch timeout
                fetch_timeout: undefined
                # device tree, really needed here ?
                device_tree: undefined
                # monitoring data
                is_running: true
                # monitoring_data: undefined
            }

        set_running_flag: (flag) =>
            @struct.is_running = flag
            
        new_devsel: (devs) =>
            @struct.devices.length = 0
            for dev in devs
                if not dev.is_meta_device
                    @struct.devices.push(dev)
            @start()

        stop_update: () =>
            if @struct.fetch_timeout
                $timeout.cancel(@struct.fetch_timeout)
                @struct.fetch_timeout = undefined

        pipeline_pre_close: () =>
            icswDeviceLivestatusDataService.destroy(@_my_id)

        start: () =>
            @stop_update()
            @struct.updating = true
            wait_list = [
                icswDeviceTreeService.load(@_my_id)
                icswDeviceLivestatusDataService.retain(@_my_id, @struct.devices)
            ]
            $q.all(wait_list).then(
                (data) =>
                    @struct.device_tree = data[0]
                    @struct.updating = false
                    monitoring_data = data[1]
                    monitoring_data.result_notifier.promise.then(
                        (ok) ->
                            console.log "dr ok"
                        (not_ok) ->
                            # stop receiving
                            # console.log "dr error"
                        (generation) =>
                            if @struct.is_running
                                @feed_data(monitoring_data)
                            else
                                console.warn "is_running flag is false"
                    )
            )
]).service('icswLivestatusCategoryFilter',
[
    "$q", "icswMonLivestatusPipeBase", "icswMonitoringResult",
(
    $q, icswMonLivestatusPipeBase, icswMonitoringResult,
) ->
    class icswLivestatusCategoryFilter extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusCategoryFilter", true, true)
            @set_template(
                '<icsw-config-category-tree-select icsw-mode="filter" icsw-sub-tree="\'mon\'" icsw-mode="filter" icsw-connect-element="con_element"></icsw-config-category-tree-select>'
                "CategoryFilter"
            )
            @_emit_data = new icswMonitoringResult()
            @_cat_filter = undefined
            @_latest_data = undefined
            @new_data_notifier = $q.defer()
            #  @new_data_notifier = $q.defer()

        set_category_filter: (sel_cat) ->
            @_cat_filter = sel_cat
            if @_latest_data?
                @emit_data_downstream(@new_data_received(@_latest_data))

        new_data_received: (data) ->
            @_latest_data = data
            if @_cat_filter?
                @_emit_data.apply_category_filter(@_cat_filter, @_latest_data)
            @new_data_notifier.notify(data)
            return @_emit_data

        pipeline_reject_called: (reject) ->
            # ignore, stop processing
]).service("icswLivestatusLocationDisplay",
[
    "$q", "icswMonLivestatusPipeBase", "icswMonitoringResult",
(
    $q, icswMonLivestatusPipeBase, icswMonitoringResult,
) ->
    class icswLivestatusLocationDisplay extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusLocationDisplay", true, false)
            @set_template(
                '<icsw-livestatus-location-display icsw-connect-element="con_element"></icsw-livestatus-location-display>'
                "LocationDisplay"
                8
                8
            )
            @new_data_notifier = $q.defer()
            #  @new_data_notifier = $q.defer()

        new_data_received: (data) ->
            @new_data_notifier.notify(data)

        pipeline_reject_called: (reject) ->
            @new_data_notifier.reject("stop")
            
]).directive("icswLivestatusLocationDisplay",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.config.category.location.show")
        scope: {
            con_element: "=icswConnectElement"
        }
        controller: "icswConfigCategoryLocationCtrl"
        link: (scope, element, attrs) ->
            scope.set_mode("show")
    }
]).service("icswLivestatusMapDisplay",
[
    "$q", "icswMonLivestatusPipeBase", "icswMonitoringResult",
(
    $q, icswMonLivestatusPipeBase, icswMonitoringResult,
) ->
    class icswLivestatusMapDisplay extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusMapDisplay", true, false)
            @set_template(
                '<icsw-device-livestatus-maplist icsw-connect-element="con_element"></icsw-device-livestatus-maplist>'
                "LocationDisplay"
                8
                8
            )
            @new_data_notifier = $q.defer()
            #  @new_data_notifier = $q.defer()

        new_data_received: (data) ->
            @new_data_notifier.notify(data)

        pipeline_reject_called: (reject) ->
            @new_data_notifier.reject("stop")

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
            con_element: "=icswConnectElement"
        }
        controller: "icswDeviceLivestatusMaplistCtrl"
        link: (scope, element, attrs) ->
            scope.link(scope.con_element.new_data_notifier)
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
        # location list
        loc_gfx_list: []
        # autorotate
        autorotate: false
        # page idx for autorotate
        page_idx: 0
        # page idx set by uib-tab
        cur_page_idx: 0
        # notifier for maps
        notifier: $q.defer()
        # current device idxs
        device_idxs: []
    }
    $scope.struct.cur_gfx_size = $scope.struct.gfx_sizes[0]

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
                check_for_maps()
        )

    check_for_maps = () ->
        dev_idxs = (dev.$$icswDevice.idx for dev in $scope.struct.monitoring_data.hosts)
        if _.difference(dev_idxs, $scope.struct.device_idxs).length
            $scope.struct.device_idxs = dev_idxs
            # check for valid maps for current device selection
            $scope.struct.loc_gfx_list.length = 0
            $scope.struct.page_idx = 0
            _deactivate_rotation()
            loc_idx_used = []
            for gfx in $scope.struct.cat_tree.gfx_list
                gfx.$$filtered_dml_list = []
                for dml in gfx.$dml_list
                    if dml.device in dev_idxs and dml.location_gfx not in loc_idx_used
                        loc_idx_used.push(gfx.idx)
                        $scope.struct.loc_gfx_list.push(gfx)
                        gfx.$$filtered_dml_list.push(dml)
                        gfx.$$page_idx = $scope.struct.loc_gfx_list.length
            $scope.struct.maps_present = $scope.struct.loc_gfx_list.length > 0
        $scope.struct.notifier.notify()

    $scope.link = (notifier) ->
        load_called = false
        notifier.promise.then(
            (resolved) ->
            (rejected) ->
                # rejected, done
                $scope.struct.notifier.reject("stop")
            (data) ->
                if not load_called
                    load_called = true
                    $scope.struct.monitoring_data = data
                    load()
                else if $scope.struct.data_valid
                    check_for_maps()
        )

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
            notifier: React.PropTypes.object
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
            @props.notifier.promise.then(
                () ->
                () ->
                    # will get called when the pipeline shuts down
                (c) =>
                    @force_redraw()
            )

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
                            key: "dml_node_#{dml.device}"
                            monitoring_data: @props.monitoring_data
                            draw_parameters: @props.draw_parameters
                        }
                    )
                )
            return div(
                {
                    key: "top"
                }
                [
                    h4(
                        {
                            key: "header"
                        }
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
        scope:
            loc_gfx: "=icswLocationGfx"
            monitoring_data: "=icswMonitoringData"
            gfx_size: "=icswGfxSize"
            # to notify when the data changes
            notifier: "=icswNotifier"
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
                                location_gfx: scope.loc_gfx
                                monitoring_data: scope.monitoring_data
                                draw_parameters: draw_params
                                device_tree: device_tree
                                notifier: scope.notifier
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
