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

# livestatus sources and filter functions (components)

angular.module(
    "icsw.livestatus.comp.sources",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.router",
    ]
).config(["icswLivestatusPipeRegisterProvider", (icswLivestatusPipeRegisterProvider) ->
    icswLivestatusPipeRegisterProvider.add("icswLivestatusSelDevices", false)
    icswLivestatusPipeRegisterProvider.add("icswLivestatusDataSource", false)
]).service("icswSaltMonitoringResultService", [() ->

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
        if not entry.$$selected?
            entry.$$selected = false
        entry.$$dummy = false
        entry.state = parseInt(entry.state)
        entry.$$numComments = entry._comments.length
        # console.log entry.last_check, typeof(entry.last_check)
        if entry.last_check in ["0"] and entry.state != 4
            entry.state = 5
        #if entry.state_type in ["0", "1"]
        #    entry.state_type = parseInt(entry.state_type)
        #else
        #    entry.state_type = null
        #if entry.check_type in ["0", "1"]
        #    entry.check_type = parseInt(entry.check_type)
        #else
        #    entry.check_type = null
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
        # console.log entry.check_type, typeof(entry.check_type), entry.$$icswPassiveCheck  #, entry
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
        entry.$$icswLastCheckSortHint = entry.last_check
        entry.$$icswLastStateChangeString = _get_diff_time(entry.last_state_change)
        entry.$$icswLastStateChangeSortHint = entry.last_state_change

        # custom variables, already parsed

    _get_dummy_entry = (display_name, ct) ->
        entry = {
            display_name: display_name
            $$ct: ct
            $$dummy: false
            last_check: 0
            last_state_change: 0
            _comments: []
        }
        return entry

    get_dummy_service_entry = (display_name) ->
        entry = _get_dummy_entry(display_name, "service")
        # is a dummy entry
        entry.$$dummy = true
        entry.state = 4
        entry.state_type = 1
        entry.check_type = 0
        salt_service_state(entry)
        return entry

    get_device_group_entry = (display_name) ->
        entry = _get_dummy_entry(display_name, "devicegroup")
        return entry

    get_system_entry = (display_name) ->
        entry = _get_dummy_entry(display_name, "system")
        return entry

    get_unmonitored_device_entry = (dev) ->
        # dev ... device_tree device
        entry = _get_dummy_entry(dev.full_name, "device")
        entry.$$dummy = true
        # important: state type is 1 (== hard state) and check_type is 0 (== active)
        entry.state = 4
        entry.state_type = 1
        entry.check_type = 0
        # custom vars
        entry.custom_variables = {
            device_pk: dev.idx
            uuid: dev.uuid
        }
        return entry

    _state_lut = {
        0: {
            # soft state
            svgClassName: "svg-sh-type"
            info: "Soft state"
            iconCode: "\uf096"
            iconFaName: "fa-square-o"
        }
        1: {
            # hard state
            svgClassName: "svg-sh-type"
            info: "Hard state"
            iconCode: "\uf0c8"
            iconFaName: "fa-square"
        }
    }

    _device_lut = {
        0: {
            svgClassName: "svg-dev-up"
            info: "Up"
            iconCode: "\uf00c"
            iconFaName: "fa-check"
            StateString: "Up"
        }
        1: {
            svgClassName:  "svg-dev-down"
            info: "Down"
            iconCode: "\uf0e7"
            iconFaName: "fa-bolt"
            StateString: "Down"
        }
        2: {
            svgClassName: "svg-dev-unreach"
            info: "Unreachable"
            iconCode: "\uf071"
            iconFaName: "fa-warning"
            StateString: "Unreachable"
        }
        3: {
            svgClassName: "svg-dev-unknown"
            info: "Unknown"
            iconCode: "\uf29c"
            iconFaName: "fa-question-circle-o"
            StateString: "Not set"
        }
        4: {
            svgClassName: "svg-dev-notmonitored"
            info: "not monitored"
            iconCode: "\uf05e"
            iconFaName: "fa-ban"
            StateString: "Not Monitored"
        }
        5: {
            svgClassName: "svg-dev-pending"
            info: "pending"
            iconCode: "\uf10c"
            iconFaName: "fa-circle-o"
            StateString: "pending"
        }
    }

    _service_lut = {
        0: {
            svgClassName: "svg-srv-ok"
            info: "OK"
            iconCode: "\uf00c"
            iconFaName: "fa-check"
            StateString: "OK"
        }
        1: {
            svgClassName: "svg-srv-warn"
            info: "Warning"
            iconCode: "\uf071"
            iconFaName: "fa-warning"
            StateString: "Warning"
        }
        2: {
            svgClassName: "svg-srv-crit"
            info: "Critical"
            iconCode: "\uf0e7"
            iconFaName: "fa-bolt"
            StateString: "Critical"
        }
        3: {
            svgClassName: "svg-srv-unknown"
            info: "Unknown"
            iconCode: "\uf29c"
            iconFaName: "fa-question-circle-o"
            StateString: "Unknown"
        }
        4: {
            svgClassName: "svg-srv-notmonitored"
            info: "not monitored"
            iconCode: "\uf05e"
            iconFaName: "fa-ban"
            StateString: "unmon"
        }
        5: {
            svgClassName: "svg-srv-pending"
            info: "pending"
            iconCode: "\uf10c"
            iconFaName: "fa-circle-o"
            StateString: "pending"
        }
    }
    _struct = {
        device_lut: _device_lut
        service_lut: _service_lut
        device_states: [0, 1, 2, 3, 4, 5]
        service_states: [0, 1, 2, 3, 4, 5]
    }
    salt_device_state = (entry) ->
        entry.$$data = _device_lut[entry.state]
        #    0: "svg-dev-up"
        #    1: "svg-srv-warn"
        #    2: "svg-srv-crit"
        #    3: "svg-dev-unknown"
        #    4: "svg-dev-unknown"
        #    5: "svg-dev-unknown"
        # }[entry.state]
        _r_str = {
            0: "success"
            1: "danger"
            2: "danger"
            3: "warning"
            4: "default"
            5: "default"
        }[entry.state]
        entry.$$icswStateClass = _r_str
        # entry.$$icswStateLabelClass = "label-#{_r_str}"
        entry.$$icswStateTextClass = "text-#{_r_str}"
        entry.$$icswStateBtnClass = "btn-#{_r_str}"

    salt_service_state = (entry) ->
        _r_str = {
            0: "success"
            1: "warning"
            2: "danger"
            3: "danger"
            # special state: unmonitored
            4: "default"
            # special state: pending
            5: "default"
        }[entry.state]
        entry.$$data = _service_lut[entry.state]
        #    0: "svg-srv-ok"
        #    1: "svg-srv-warn"
        #    2: "svg-srv-crit"
        #    3: "svg-danger"
        #    4: "svg-srv-unknown"
        #    5: "svg-srv-unknown"
        # }[entry.state]
        entry.$$icswStateClass = _r_str
        # entry.$$icswStateLabelClass = "label-#{_r_str}"
        entry.$$icswStateTextClass = "text-#{_r_str}"
        entry.$$icswStateBtnClass = "btn-#{_r_str}"

    salt_host = (entry, device_tree, cat_tree, device_cat_pks) ->
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
            entry.$$device_categories = _.intersection(entry.$$icswDevice.categories, device_cat_pks)
            if entry.$$device_categories.length
                entry.$$icswCategories = (cat_tree.lut[_cat].name for _cat in entry.$$device_categories).join(", ")
            else
                entry.$$icswCategories = "---"
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
            entry.$$search_string = "#{entry.plugin_output} #{entry.description}" 
        return entry

    build_circle_info = (in_type, in_dict, detail_dict) ->
        # transform a device or service dict (state -> num) to an array
        # detail_dict: to add detailed info (categories, location, ...)
        # which is usable for device_circle_info
        _r_list = []
        _lut = _struct["#{in_type}_lut"]
        for _state in _struct["#{in_type}_states"]
            if _state of in_dict
                _count = in_dict[_state]
                _ps = if _count > 1 then "s" else ""
                _info = {
                    value: _count
                    data: _lut[_state]
                    shortInfoStr: "#{_count} #{_lut[_state].info}"
                }
                _info_str = "#{_count} #{in_type}#{_ps} #{_lut[_state].info}"
                if detail_dict?
                    _sub_keys = _.keys(detail_dict[_state])
                    _info_str = "#{_info_str}, #{_sub_keys.length} subelements"
                    _info.detail = detail_dict[_state]
                _info.infoStr = _info_str
                _r_list.push(_info)
        return _r_list

    return {
        get_luts: () ->
            return {
                dev: _device_lut
                srv: _service_lut
                state: _state_lut
            }

        get_unmonitored_device_entry: get_unmonitored_device_entry

        get_dummy_service_entry: get_dummy_service_entry

        get_device_group_entry: get_device_group_entry

        get_system_entry: get_system_entry

        salt_device_state: salt_device_state

        salt_host: salt_host

        salt_service: salt_service

        build_circle_info: build_circle_info
    }
]).service("icswMonitoringResult",
[
    "$q", "icswTools", "icswSaltMonitoringResultService",
(
    $q, icswTools, icswSaltMonitoringResultService,
) ->
    class icswMonitoringResult
        constructor: (monitoring=true) ->
            # used for monitoring
            @monitoring = monitoring
            @id = icswTools.get_unique_id("monres")
            # selection generation
            @sel_generation = 0
            # result generation
            @generation = 0
            # notifier for new data
            @result_notifier = $q.defer()
            # counter dicts
            @hosts = []
            @services = []
            @mon_cat_counters = {}
            @device_cat_counters = {}
            @_create_used_fields()
            @clear()

        clear: () =>
            @hosts.length = 0
            @services.length = 0
            @__luts_set = false

        new_selection: () =>
            # hm, not needed ... ?
            @sel_generation++

        stop_receive: () =>
            @result_notifier.reject("stop")

        copy_from: (src) =>
            # copy objects from src
            @update(src.hosts, src.services, src.mon_cat_counters, src.device_cat_counters)

        add_host: (host, allowed_srvc_list) =>
            @hosts.push(host)
            for srvc in host.$$service_list
                if srvc.$$idx in allowed_srvc_list
                    @services.push(srvc)
            # console.log "add", host

        update: (hosts, services, mon_cat_counters, device_cat_counters) =>
            @generation++
            @__luts_set = false
            #console.log @hosts, hosts
            if @monitoring
                # monitoring mode, check selection
                _sel_hosts = (entry.$$icswDevice.idx for entry in @hosts when entry.$$selected)
                _sel_services = (entry.description for entry in @services when entry.$$selected)
                @hosts.length = 0
                for entry in hosts
                    if entry.$$icswDevice.idx in _sel_hosts
                        entry.$$selected = true
                    @hosts.push(entry)
                @services.length = 0
                for entry in services
                    if entry.description in _sel_services
                        entry.$$selected = true
                    @services.push(entry)
            else
                # special device mode
                @hosts.length = 0
                for entry in hosts
                    @hosts.push(entry)
                @services.length = 0
                for entry in services
                    @services.push(entry)
            @mon_cat_counters = mon_cat_counters
            @device_cat_counters = device_cat_counters
            @_create_used_fields()
            # console.log "update", @generation
            @notify()

        notify: () =>
            @result_notifier.notify(@generation)

        # helper functions
        _copy_list: (attr_name, src_data) =>
            @[attr_name].length = 0
            for entry in src_data[attr_name]
                @[attr_name].push(entry)

        _copy_dict: (attr_name, src_data) =>
            @[attr_name] = _.cloneDeep(src_data[attr_name])

        _create_used_fields: () =>
            # used monitoring categories
            @used_mon_cats = (parseInt(_v) for _v in _.keys(@mon_cat_counters))
            # used device categories
            @used_device_cats = (parseInt(_v) for _v in _.keys(@device_cat_counters))

        apply_base_filter: (filter, src_data) =>
            # apply base livestatus filter
            @__luts_set = false
            # for linked mode
            _host_pks = []

            @hosts.length = 0
            device_cat_counters = {}
            # _device_cats = []
            for entry in src_data.hosts
                if filter.host_types[entry.state_type] and filter.host_states[entry.state]
                    @hosts.push(entry)
                    device_cat_counters = icswTools.merge_count_dict(device_cat_counters, _.countBy(entry.$$device_categories))
                    _host_pks.push(entry.$$icswDevice.idx)

            @services.length = 0
            mon_cat_counters = {}
            for entry in src_data.services
                if filter.linked and entry.$$host_mon_result.$$icswDevice.idx not in _host_pks
                    true
                else if filter.service_types[entry.state_type] and filter.service_states[entry.state]
                    @services.push(entry)
                    if entry.custom_variables? and entry.custom_variables.cat_pks?
                        mon_cat_counters = icswTools.merge_count_dict(mon_cat_counters, _.countBy(entry.custom_variables.cat_pks))

            # reduce mon and device cats
            @device_cat_counters = device_cat_counters
            @mon_cat_counters = mon_cat_counters
            @_create_used_fields()

            # bump generation counter
            @generation++

        apply_category_filter: (cat_list, src_data, filter_name) =>
            # filter name is mon or device
            @__luts_set = false
            # show uncategorized entries
            _zero_cf = 0 in cat_list
            if filter_name == "mon"
                # copy hosts
                @_copy_list("hosts", src_data)
                @_copy_dict("device_cat_counters", src_data)
                # filter services
                @services.length = 0
                mon_cat_counters = {}
                for entry in src_data.services
                    _add = true
                    if entry.custom_variables? and entry.custom_variables.cat_pks?
                        if not _.intersection(cat_list, entry.custom_variables.cat_pks).length
                            _add = false
                    else if not _zero_cf
                        _add = false
                    if _add
                        @services.push(entry)
                        mon_cat_counters = icswTools.merge_count_dict(mon_cat_counters, _.countBy(entry.custom_variables.cat_pks))
                @mon_cat_counters = mon_cat_counters
            else
                _host_pks = []
                # device filter
                @hosts.length = 0
                device_cat_counters = {}
                for entry in src_data.hosts
                    _add = true
                    if entry.$$device_categories.length
                        if not _.intersection(cat_list, entry.$$device_categories).length
                            _add = false
                    else if not _zero_cf
                        _add = false
                    if _add
                        @hosts.push(entry)
                        _host_pks.push(entry.$$icswDevice.idx)
                        device_cat_counters = icswTools.merge_count_dict(device_cat_counters, _.countBy(entry.$$device_categories))
                @device_cat_counters = device_cat_counters
                # only take services on a valid host
                @services.length = 0
                mon_cat_counters = {}
                for entry in src_data.services
                    if entry.$$host_mon_result.$$icswDevice.idx in _host_pks
                        @services.push(entry)
                        mon_cat_counters = icswTools.merge_count_dict(mon_cat_counters, _.countBy(entry.custom_variables.cat_pks))
                @mon_cat_counters = mon_cat_counters

            @_create_used_fields()
            # bump generation counter
            @generation++
            
        build_luts: () =>
            if @__luts_set
                return
            # lookup tables
            @__luts_set = true
            _srv_lut = {}
            # dict: [srv_state][category] -> number of entries
            _srv_cat_lut = {}
            for srv in @services
                if srv.state not of _srv_lut
                    _srv_lut[srv.state] = 0
                    _srv_cat_lut[srv.state] = {}
                _srv_lut[srv.state]++
                if srv.custom_variables? and srv.custom_variables.cat_pks?
                    _cats = srv.custom_variables.cat_pks
                else
                    # no category
                    _cats = [0]
                for _cat in _cats
                    if _cat not of _srv_cat_lut[srv.state]
                        _srv_cat_lut[srv.state][_cat] = 0
                    _srv_cat_lut[srv.state][_cat]++
            _host_lut = {}
            # dict: [dev_state][category] -> number of entries
            _host_cat_lut = {}
            for host in @hosts
                if host.state not of _host_lut
                    _host_lut[host.state] = 0
                    _host_cat_lut[host.state] = {}
                _host_lut[host.state]++
                for _cat in host.$$device_categories
                    if _cat not of _host_cat_lut[host.state]
                        _host_cat_lut[host.state][_cat] = 0
                    _host_cat_lut[host.state][_cat]++
            @service_circle_data = icswSaltMonitoringResultService.build_circle_info("service", _srv_lut, _srv_cat_lut)
            @device_circle_data = icswSaltMonitoringResultService.build_circle_info("device", _host_lut, _host_cat_lut)

]).service("icswDeviceLivestatusDataService",
[
    "ICSW_URLS", "$interval", "$timeout", "icswSimpleAjaxCall", "$q", "icswDeviceTreeService",
    "icswMonitoringResult", "icswSaltMonitoringResultService", "icswCategoryTreeService", "icswTools",
(
    ICSW_URLS, $interval, $timeout, icswSimpleAjaxCall, $q, icswDeviceTreeService,
    icswMonitoringResult, icswSaltMonitoringResultService, icswCategoryTreeService, icswTools,
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
        # console.log "RWBC", client.toString(), result_dict[client.toString()]
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
                    mon_cat_counters = {}
                    device_cat_counters = {}
                    # list of unknown hosts
                    _unknown_hosts = (parseInt(_idx) for _idx in watched_devs)
                    if result[0].state == "fulfilled"
                        # fill service and host_entries, used cats
                        xml = result[0].value
                        $(xml).find("value[name='service_result']").each (idx, node) =>
                            service_entries = service_entries.concat(angular.fromJson($(node).text()))
                        $(xml).find("value[name='host_result']").each (idx, node) =>
                            host_entries = host_entries.concat(angular.fromJson($(node).text()))
                        # get all device cats
                        _dev_cat_pks = (_entry.idx for _entry in category_tree.list when _entry.full_name.match(/\/device\//))
                        for entry in host_entries
                            icswSaltMonitoringResultService.salt_host(entry, device_tree, category_tree, _dev_cat_pks)
                            device_cat_counters = icswTools.merge_count_dict(device_cat_counters, _.countBy(entry.$$device_categories))
                            # for _dc in entry.$$
                            _.remove(_unknown_hosts, (_idx) -> return _idx == entry.$$icswDevice.idx)
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
                                mon_cat_counters = icswTools.merge_count_dict(mon_cat_counters, _.countBy(entry.custom_variables.cat_pks))
                    for _idx in _unknown_hosts
                        if _idx of device_tree.all_lut
                            dev = device_tree.all_lut[_idx]
                            _um_entry = icswSaltMonitoringResultService.get_unmonitored_device_entry(dev)
                            icswSaltMonitoringResultService.salt_host(_um_entry, device_tree, category_tree, _dev_cat_pks)
                            device_cat_counters = icswTools.merge_count_dict(device_cat_counters, _.countBy(_um_entry.$$device_categories))
                            host_entries.push(_um_entry)
                    # else
                    #    # invalidate results
                    #    for dev_idx, watchers of watch_dict
                    #        if dev_idx of device_tree.all_lut
                    #            device_tree.all_lut[dev_idx].$$host_mon_result = undefined
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
                        _result.update(hosts_client, services_client, mon_cat_counters, device_cat_counters)
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
                        if not angular.isObject(dev)
                            console.error "device #{dev} for retain() is not an object"
                        else
                            if not watch_dict[dev.idx]?
                                watch_dict[dev.idx] = []

                            if client not in watch_dict[dev.idx]
                                watch_dict[dev.idx].push(client)

                if client not of result_dict
                    console.log "new retain client #{client}"
                    result_dict[client] = new icswMonitoringResult()
                else
                    # console.log "k", client
                    # not really needed ?
                    result_dict[client].new_selection()

                _defer.resolve(result_dict[client])

                schedule_load()
            else
                _defer.reject("client in destroyed list")
                throw new Error("client #{client} in destroyed_list")
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
]).service("icswLivestatusSelDevices",
[
    "$q", "$rootScope", "icswMonLivestatusPipeBase", "$timeout", "ICSW_SIGNALS",
    "icswDeviceTreeService", "icswDeviceLivestatusDataService", "icswTools",
    "icswActiveSelectionService", "icswMonitoringResult",
(
    $q, $rootScope, icswMonLivestatusPipeBase, $timeout, ICSW_SIGNALS,
    icswDeviceTreeService, icswDeviceLivestatusDataService, icswTools,
    icswActiveSelectionService, icswMonitoringResult,
) ->
    class icswLivestatusSelDevices extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusSelDevices", false, true)
            # pipe flags
            @__dp_async_emit = true

            @struct = {
                # local id
                local_id: icswTools.get_unique_id()
                # device list to emit
                device_list: []
                # device tree
                device_tree: undefined
                # raw selection
                raw_selection: undefined
                # monresult to emit
                mon_result: new icswMonitoringResult(monitoring=false)
            }
            # todo: get the current selection after the pipe is fully initialised
            @dereg = $rootScope.$on(ICSW_SIGNALS("ICSW_OVERVIEW_EMIT_SELECTION_DTL"), (event) =>
                @get_selection()
            )
            icswActiveSelectionService.register_receiver()
            icswDeviceTreeService.load(@struct.local_id).then(
                (tree) =>
                    @struct.device_tree = tree
                    @check_raw_selection()
            )
            @get_selection()
            @set_async_emit_data(@struct.mon_result)

        get_selection: () =>
            @struct.raw_selection = icswActiveSelectionService.current().tot_dev_sel
            @check_raw_selection()

        check_raw_selection: () =>
            if @struct.device_tree? and @struct.raw_selection?
                @struct.device_list.length = 0
                for pk in @struct.raw_selection
                    if @struct.device_tree.all_lut[pk]?
                        _dev = @struct.device_tree.all_lut[pk]
                        if not _dev.is_meta_device
                            @struct.device_list.push(_dev)
                # we use MonitoringResult as a container to send the device selection down the pipe
                # console.log "EMIT"
                # here we go
                @struct.mon_result.update(@struct.device_list, [], [], [])

        pipeline_pre_close: () =>
            icswActiveSelectionService.unregister_receiver()
            # console.log "PPC"
            @dereg()

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
            super("icswLivestatusDataSource", true, true)
            @__dp_async_emit = true
            @struct = {
                # local id, created for every call to start()
                local_id: undefined
                # device list
                devices: []
                # is updating
                updating: false
                # data fetch timeout
                fetch_timeout: undefined
                # monitoring data
                is_running: true
                # monitoring_data: undefined
                monitoring_data: undefined
            }

        set_running_flag: (flag) =>
            @struct.is_running = flag

        new_data_received: (data) =>
            @struct.devices.length = 0
            for dev in data.hosts
                if not dev.is_meta_device
                    @struct.devices.push(dev)
            @start()
            # important because we are an asynchronous emitter
            return null

        stop_update: () =>
            if @struct.fetch_timeout
                $timeout.cancel(@struct.fetch_timeout)
                @struct.fetch_timeout = undefined
            if @struct.monitoring_data?
                @struct.monitoring_data.stop_receive()
                # destroy current fetcher
                icswDeviceLivestatusDataService.destroy(@struct.local_id)

        pipeline_pre_close: () =>
            if @struct.monitoring_data?
                icswDeviceLivestatusDataService.destroy(@struct.local_id)

        start: () =>
            @stop_update()
            @struct.updating = true
            @struct.local_id = icswTools.get_unique_id()
            wait_list = [
                icswDeviceLivestatusDataService.retain(@struct.local_id, @struct.devices)
            ]
            $q.all(wait_list).then(
                (data) =>
                    @struct.updating = false
                    @struct.monitoring_data = data[0]
                    @set_async_emit_data(@struct.monitoring_data)
            )
])
