# Copyright (C) 2012-2015 init.at
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
        @iter_childs((obj) -> obj.show = false)
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
).factory("icswLivestatusDevSelFactory", [() ->
    return () ->
        _dev_sel = []
        _changed = 0
        return {
            "set": (sel) ->
                _dev_sel = sel
                _changed++
            "get": () ->
                return _dev_sel
            "changed": () ->
                return _changed
        }
]).factory("icswLivestatusFilterFactory", [() ->
    _filter_id = 0
    return () ->
        _filter_id++
        _local_id = _filter_id
        # categories
        _categories = []
        # all categories used
        _used_cats = []
        _cat_name_lut = {}
        _cat_defined = false
        _num_defined = false
        _num_maps = 0
        _iter = 0
        _num_hosts = 0
        _num_services = 0
        _num_filtered_hosts = 0
        _num_filtered_services = 0
        _filter_funcs = []
        return {
            register_filter_func: (nf) ->
                if nf not in _filter_funcs
                    _filter_funcs.push(nf)
                    _iter++
            filter_id: () -> return _local_id
            trigger: () ->
                _iter++
            changed: () -> return _iter
            cat_defined: () -> return _cat_defined
            get_categories: () -> return _categories
            set_categories: (vals, lut) ->
                _cat_defined = true
                _categories = vals
                if lut?
                    # ignore if not set
                    _cat_name_lut = lut
                _iter++
            get_cat_name: (key) ->
                return _cat_name_lut[key]
            set_used_cats: (vals) ->
                _used_cats = vals
            get_used_cats: () ->
                return _used_cats
            set_num_maps: (val) ->
                _num_maps = val
            get_num_maps: () ->
                return _num_maps
            num_defined: () ->
                return _num_defined
            set_total_num: (h, s) ->
                _num_defined = true
                _num_hosts = h
                _num_services = s
            get_total_num: () ->
                return [_num_hosts, _num_services]
            set_filtered_num: (h, s) ->
                _num_filtered_hosts = h
                _num_filtered_services = s
            get_filtered_num: () ->
                return [_num_filtered_hosts, _num_filtered_services]
            apply_filter: (check, show) ->
                for _ff in _filter_funcs
                    if show
                        show = _ff(check)
                    else
                        break
                check._show = show
                return check._show
        }
]).service("icswInterpretMonitoringCheckResult", [() ->
    get_diff_time = (ts) ->
        if parseInt(ts)
            return moment.unix(ts).fromNow(true)
        else
            return "never"
    _get_attempt_info = (entry, force=false) ->
        if entry.max_check_attempts == null
            return "N/A"
        try
            max = parseInt(entry.max_check_attempts)
            cur = parseInt(entry.current_attempt)
            if max == cur
                return "#{cur}"
            else
                return "#{cur} / #{max}"
        catch error
            return "e"
    _get_attempt_class = (entry, prefix="", force=false) ->
        if entry.max_check_attempts == null
            _r_str ="default"
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
        if prefix?
            _r_str = "#{prefix}#{_r_str}"
        return _r_str
    _get_host_state_class = (entry, prefix) ->
        _r_str = {
            0: "success"
            1: "danger"
            2: "danger"
        }[entry.state]
        if prefix?
            _r_str = "#{prefix}#{_r_str}"
        return _r_str
    return {
        get_last_check: (entry) ->
            return get_diff_time(entry.last_check)
        get_last_change: (entry) ->
            return get_diff_time(entry.last_state_change)
        get_host_last_check: (entry) ->
            return get_diff_time(entry.host.last_check)
        get_host_last_change: (entry) ->
            return get_diff_time(entry.host.last_state_change)
        host_is_passive_checked: (entry) ->
            return if entry.host.check_type then true else false
        get_host_class: (entry) ->
            return _get_host_state_class(entry.host)
        get_host_attempt_info: (entry, force=false) ->
            return _get_attempt_info(entry.host, force)
        get_host_attempt_class: (entry, prefix="", force=false) ->
            return _get_attempt_class(entry.host, prefix, force)
        get_check_type: (entry) ->
            return {
                null: "???"
                0: "active"
                1: "passive"
            }[entry.check_type]
        is_passive_check: (entry) ->
            return if entry.check_type then true else false
        get_state_type: (entry) ->
            return {
                null: "???"
                0: "soft"
                1: "hard"
            }[entry.state_type]
        get_host_state_string: (entry) ->
            return {
                0: "OK"
                1: "Critical"
                2: "Unreachable"
            }[entry.state]

        get_service_state_string: (entry) ->
            return {
                0: "OK"
                1: "Warning"
                2: "Critical"
                3: "Unknown"
            }[entry.state]
        get_service_state_class: (entry, prefix) ->
            _r_str = {
                0: "success"
                1: "warning"
                2: "danger"
                3: "danger"
            }[entry.state]
            if prefix?
                _r_str = "#{prefix}#{_r_str}"
            return _r_str
        get_host_state_class: (entry, prefix) ->
            return _get_host_state_class(entry, prefix)
        get_attempt_info: (entry, force=false) ->
            return _get_attempt_info(entry, force)
        get_attempt_class: (entry, prefix="", force=false) ->
            return _get_attempt_class(entry, prefix, force)
        show_attempt_info: (entry) ->
            try
                if parseInt(entry.current_attempt) == 1
                    return true
                else
                    return true
            catch error
               return true
        }
]).controller("icswDeviceLiveStatusCtrl",
    ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "restDataSource", "$q", "$modal", "$timeout",
     "icswTools", "ICSW_URLS", "icswCallAjaxService", "icswParseXMLResponseService", "icswDeviceLivestatusDataService",
     "icswCachingCall", "icswLivestatusFilterFactory", "icswDeviceTreeService", "icswLivestatusDevSelFactory", "$state",
    ($scope, $compile, $filter, $templateCache, Restangular, restDataSource,
     $q, $modal, $timeout, icswTools, ICSW_URLS, icswCallAjaxService, icswParseXMLResponseService, icswDeviceLivestatusDataService,
     icswCachingCall, icswLivestatusFilterFactory, icswDeviceTreeService, icswLivestatusDevSelFactory, $state) ->
        $scope.host_entries = []
        $scope.service_entries = []
        $scope.filtered_entries = []
        $scope.layouts = ["simple1", "simple2"]
        if not $scope.ls_filter?
            # init ls_filter if not set
            $scope.ls_filter = new icswLivestatusFilterFactory("lsc")
        $scope.ls_devsel = new icswLivestatusDevSelFactory()
        $scope.activate_layout = (name) ->
            $scope.cur_layout = name
            $state.go($scope.cur_layout)
        $scope.activate_layout($scope.layouts[0])
        $scope.$watch(
            $scope.ls_filter.changed
            (new_filter) ->
                $scope.apply_filter()
        )
        # selected categories
        $scope.new_devsel = (_dev_sel, _devg_sel) ->
            #pre_sel = (dev.idx for dev in $scope.devices when dev.expanded)
            #restDataSource.reset()
            wait_list = [
                icswDeviceTreeService.fetch($scope.$id)
                icswDeviceLivestatusDataService.retain($scope.$id, _dev_sel)
            ]
            $q.all(wait_list).then((data) ->
                $scope.ls_devsel.set(_dev_sel)
                $scope.dev_tree_lut = icswTools.build_lut(data[0][0])
                host_entries = data[1][0]
                service_entries = data[1][1]
                used_cats = data[1][3]
                $scope.host_entries = host_entries
                $scope.service_entries = service_entries
                $scope.ls_filter.set_total_num(host_entries.length, service_entries.length)
                $scope.ls_filter.set_used_cats(used_cats)
                $scope.apply_filter()
            )
        $scope.apply_filter = () ->
            # filter entries for table
            $scope.filtered_entries = _.filter($scope.service_entries, (_v) -> return $scope.ls_filter.apply_filter(_v, true))
            $scope.ls_filter.set_filtered_num($scope.host_entries.length, $scope.filtered_entries.length)

        $scope.$on("$destroy", () ->
            icswDeviceLivestatusDataService.destroy($scope.$id)
        )
]).service("icswCachingCall", ["$interval", "$timeout", "$q", "Restangular", ($inteval, $timeout, $q, Restangular) ->
    class LoadInfo
        constructor: (@key, @url, @options) ->
            @client_dict = {}
            # initial value is null (== no filtering)
            @pk_list = null
        add_pk_list: (client, pk_list) =>
            if pk_list != null
                # got a non-null pk_list
                if @pk_list == null
                    # init pk_list if the list was still null
                    @pk_list = []
                @pk_list = @pk_list.concat(pk_list)
            _defer = $q.defer()
            @client_dict[client] = _defer
            return _defer
        load: () =>
            opts = {}
            for key, value of @options
                if value == "<PKS>"
                    if @pk_list != null
                        # only set options when pk_list was not null
                        opts[key] = angular.toJson(@pk_list)
                else
                    opts[key] = value
            Restangular.all(@url.slice(1)).getList(opts).then(
                (result) =>
                    for c_id, _defer of @client_dict
                        _defer.resolve(result)
                    @client_dict = {}
                    @pk_list = null
            )
    start_timeout = {}
    load_info = {}
    schedule_load = (key) ->
        # called when new listeners register
        # don't update immediately, wait until more controllers have registered
        if start_timeout[key]?
            $timeout.cancel(start_timeout[key])
            delete start_timeout[key]
        if not start_timeout[key]?
            start_timeout[key] = $timeout(
                () ->
                    load_info[key].load()
                1
            )
    add_client = (client, url, options, pk_list) ->
        url_key = _key(url, options, pk_list)
        if url_key not of load_info
            load_info[url_key] = new LoadInfo(url_key, url, options)
        return load_info[url_key].add_pk_list(client, pk_list)
    _key = (url, options, pk_list) ->
        url_key = url
        for key, value of options
            url_key = "#{url_key},#{key}=#{value}"
        if pk_list == null
            # distinguish calls with pk_list == null (all devices required)
            url_key = "#{url_key}Z"
        return url_key
    return {
        "fetch" : (client, url, options, pk_list) ->
            _defer = add_client(client, url, options, pk_list)
            schedule_load(_key(url, options, pk_list))
            return _defer.promise
    }
]).directive('icswDeviceLivestatusFullburst', ["$templateCache", ($templateCache) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.livestatus.fullburst")
        scope: {
            data: "=data"
            redrawBurst: "=redraw"
            serviceFocus: "=serviceFocus"
            ls_filter: "=lsFilter"
            ls_devsel: "=lsDevsel"
            size: "=icswElementSize"
        }
        link: (scope, element, attrs) ->
            # omitted segments
            scope.width = parseInt(attrs["initialWidth"] ? "600")
            scope.omittedSegments = 0
            scope.$watch(
                "size",
                (new_val) ->
                    if new_val
                        _w = new_val.width / 2
                        if _w != scope.width
                            svg_el = element.find("svg")[0]
                            g_el = element.find("svg > g")[0]
                            scope.width = _w
                            svg_el.setAttribute("width", _w)
                            g_el.setAttribute("transform", "translate(#{_w / 2}, 160)")
            )
    }
]).directive('icswDeviceLivestatusFilter', ["$templateCache", ($templateCache) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.livestatus.filter")
        scope: {
            ls_filter: "=lsFilter"
        }
        link: (scope, elem, attrs) ->
            angular.extend(scope, scope.ls_filter)
            scope.md_states = [
                [0, "O", true, "show OK states"]
                [1, "W", true, "show warning states"]
                [2, "C", true, "show critical states"]
                [3, "U", true, "show unknown states"]
            ]
            scope.sh_states = [
                [0, "S", true, "show soft states"]
                [1, "H", true, "show hard states"]
            ]
            _srvs = {}
            for entry in scope.md_states
                _srvs[entry[0]] = entry[2]
            _shs = {}
            for entry in scope.sh_states
                _shs[entry[0]] = entry[2]
            scope.toggle_srv = (key) ->
                _srvs[key] = !_srvs[key]
                scope.ls_filter.trigger()
            scope.toggle_sh = (key) ->
                _shs[key] = !_shs[key]
                scope.ls_filter.trigger()
            scope.get_mds_class = (int_state) ->
                return if _srvs[int_state] then "btn btn-xs " + {0 : "btn-success", 1 : "btn-warning", 2 : "btn-danger", 3 : "btn-danger"}[int_state] else "btn btn-xs"
            scope.get_shs_class = (int_state) ->
                return if _shs[int_state] then "btn btn-xs btn-primary" else "btn btn-xs"
            scope._filter = (entry) ->
                if not _srvs[entry.state]
                    return false
                if not _shs[entry.state_type]
                    return false
                return true
            scope.ls_filter.register_filter_func(scope._filter)
    }
]).service('icswDeviceLivestatusTableService', ["ICSW_URLS", (ICSW_URLS) ->
    return {
        edit_template: "network.type.form"
    }
]).service("icswDeviceLivestatusDataService", ["ICSW_URLS", "$interval", "$timeout", "icswCallAjaxService", "icswParseXMLResponseService", "$q", "icswDeviceTreeService", (ICSW_URLS, $interval, $timeout, icswCallAjaxService, icswParseXMLResponseService, $q, icswDeviceTreeService) ->
    watch_list = {}
    defer_list = {}
    _host_lut = {}
    destroyed_list = []
    cur_interval = undefined
    cur_xhr = undefined
    schedule_start_timeout = undefined

    _sanitize_entries = (entry) ->
        entry.state = parseInt(entry.state)
        if entry.state_type in ["0", "1"]
            entry.state_type = parseInt(entry.state_type)
        else
            entry.state_type = null
        if entry.check_type in ["0", "1"]
            entry.check_type = parseInt(entry.check_type)
        else
            entry.check_type = null

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

    watchers_present = () ->
        # whether any watchers are present
        return _.keys(defer_list).length > 0

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
        cur_interval = $interval(load_data, 20000)#20000)

    stop_interval = () ->
        # stop regular update
        if cur_interval?
            $interval.cancel(cur_interval)
        if cur_xhr?
            cur_xhr.abort()


    load_data = () ->
        if schedule_start_timeout?
            $timeout.cancel(schedule_start_timeout)
            schedule_start_timeout = undefined

        # only continue if anyone is actually watching
        if watchers_present()

            watched_devs = []
            for dev of watch_list
                if watch_list[dev].length > 0
                    watched_devs.push(dev)

            cur_xhr = icswCallAjaxService
                url  : ICSW_URLS.MON_GET_NODE_STATUS
                data : {
                    "pk_list" : angular.toJson(watched_devs)
                },
                success : (xml) =>
                    if icswParseXMLResponseService(xml)
                        icswDeviceTreeService.fetch("bla").then((data) ->
                            dev_tree_lut = data[4]
                            service_entries = []
                            $(xml).find("value[name='service_result']").each (idx, node) =>
                                service_entries = service_entries.concat(angular.fromJson($(node).text()))
                            host_entries = []
                            $(xml).find("value[name='host_result']").each (idx, node) =>
                                host_entries = host_entries.concat(angular.fromJson($(node).text()))
                            host_lut = {}
                            used_cats = []
                            host_id = 0
                            for entry in host_entries
                                host_id++
                                # sanitize entries
                                _sanitize_entries(entry)
                                # list of checks for host
                                entry.checks = []
                                entry.ct = "host"
                                # dummy link
                                entry.host = entry
                                entry.custom_variables = _parse_custom_variables(entry.custom_variables)
                                entry._srv_id = "host#{host_id}"
                                if entry.custom_variables.device_pk of dev_tree_lut
                                    _dev = dev_tree_lut[entry.custom_variables.device_pk]
                                    entry.group_name = _dev.device_group_name
                                host_lut[entry.host_name] = entry
                                host_lut[entry.custom_variables.device_pk] = entry
                            srv_id = 0
                            for entry in service_entries
                                entry.search_str = "#{entry.plugin_output} #{entry.display_name}"
                                srv_id++
                                # sanitize entries
                                _sanitize_entries(entry)
                                entry.custom_variables = _parse_custom_variables(entry.custom_variables)
                                entry.description = entry.display_name  # this is also what icinga displays
                                entry.ct = "service"
                                entry._srv_id = "srvc#{srv_id}"
                                # populate list of checks
                                host_lut[entry.custom_variables.device_pk].checks.push(entry)
                                entry.host = host_lut[entry.custom_variables.device_pk]
                                entry.group_name = host_lut[entry.host_name].group_name
                                if entry.custom_variables and entry.custom_variables.cat_pks?
                                    used_cats = _.union(used_cats, entry.custom_variables.cat_pks)
                                else
                                    used_cats = _.union(used_cats, [0])
                            _host_lut = host_lut

                            for client, _defer of defer_list
                                hosts_client = []
                                services_client = []
                                host_lut_client = {}
                                for dev, watchers of watch_list
                                    if client in watchers and dev of host_lut  # sometimes we don't get data for a device
                                        entry = host_lut[dev]
                                        hosts_client.push(entry)
                                        for check in entry.checks
                                            services_client.push(check)
                                        host_lut_client[dev] = entry
                                        host_lut_client[entry.host_name] = entry
                                _defer.resolve([hosts_client, services_client, host_lut_client, used_cats])
                        )

    remove_watchers_by_client = (client) ->
        client = client.toString()
        for dev, watchers of watch_list
            _.remove(watchers, (elem) -> return elem == client)
        delete defer_list[client]

    return {
        resolve_host: (name) ->
            return _host_lut[name]
        retain: (client, dev_list) ->
            _defer = $q.defer()
            # get data for devices of dev_list for client (same client instance must be passed to cancel())

            # remove watchers in case of updates
            remove_watchers_by_client(client)

            client = client.toString()
            if client not in destroyed_list  # when client get the destroy event, they may still execute data, so we need to catch this here
                if not watchers_present()
                    # if no watchers have been present, there also was no regular update
                    start_interval()

                if dev_list.length
                    for dev in dev_list
                        if not watch_list[dev]?
                            watch_list[dev] = []

                        if not _.some(watch_list[dev], (elem) -> return elem == dev)
                            watch_list[dev].push(client)

                        defer_list[client] = _defer
                else
                    # resolve to empty list(s) if no devices are required
                    _defer.resolve([[], [], [], []])

                schedule_load()
            return _defer.promise


        destroy: (client) ->
            client = client.toString()
            destroyed_list.push(client)
            # don't watch for client anymore
            remove_watchers_by_client(client)

            if not watchers_present()
                stop_interval()
    }
]).service("icswDeviceLivestatusCategoryTreeService", () ->
    class category_tree extends tree_config
        constructor: (@scope, args) ->
            super(args)
            #@show_selection_buttons = false
            @show_icons = false
            @show_select = true
            @show_descendants = false
            @show_childs = false
        selection_changed: () =>
            sel_list = @get_selected((node) ->
                if node.selected
                    return [node.obj.idx]
                else
                    return []
            )
            @scope.new_cat_selection(sel_list)
        get_name : (t_entry) ->
            cat = t_entry.obj
            if cat.depth > 1
                r_info = "#{cat.full_name} (#{cat.name})"
                #if cat.num_refs
                #    r_info = "#{r_info} (refs=#{cat.num_refs})"
                return r_info # + "#{cat.idx}"
            else if cat.depth
                return cat.full_name
            else
                return "TOP"
).directive("icswDeviceLivestatusServiceInfo", ["$templateCache", "icswInterpretMonitoringCheckResult", ($templateCache, icswInterpretMonitoringCheckResult) ->
    return {
        restrict : "E"
        template : $templateCache.get("icsw.device.livestatus.serviceinfo")
        scope : {
            type: "=type"
            service: "=service"
            ls_filter: "=lsFilter"
        }
        link : (scope, element, attrs) ->
            angular.extend(scope, icswInterpretMonitoringCheckResult)
            scope.get_categories = (entry) ->
                if entry.custom_variables
                    if entry.custom_variables.cat_pks? and scope.ls_filter.cat_defined()
                        return (scope.ls_filter.get_cat_name(_pk) for _pk in entry.custom_variables.cat_pks).join(", ")
                    else
                        return "---"
                else
                    return "N/A"
    }
]).directive("icswDeviceLivestatusCheckService", ["$templateCache", "icswInterpretMonitoringCheckResult", ($templateCache, icswInterpretMonitoringCheckResult) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.livestatus.check.service")
        scope : {
            service: "=service"
            ls_filter: "=lsFilter"
            show_column: "=showColumn"
        }
        link: (scope, element) ->
            angular.extend(scope, icswInterpretMonitoringCheckResult)
            scope.get_categories = (entry) ->
                if entry.custom_variables
                    if entry.custom_variables.cat_pks? and scope.ls_filter.cat_defined()
                        return (scope.ls_filter.get_cat_name(_pk) for _pk in entry.custom_variables.cat_pks).join(", ")
                    else
                        return "---"
                else
                    return "N/A"
    }
]).controller("icswDeviceLivestatusBurstCtrl", ["$scope", "icswDeviceTreeService", "icswDeviceLivestatusDataService", "$q", "icswTools", ($scope, icswDeviceTreeService, icswDeviceLivestatusDataService, $q, icswTools) ->
    $scope.host_entries = []
    $scope.service_entries = []
    $scope._burst_data = null
    filter_propagated = false
    filter_list = []
    ignore_filter = false
    $scope.burst_sel = (_dev_list, single_selection) ->
        $scope.single_selection = single_selection
        $scope._burst_sel = _dev_list
        wait_list = [
            icswDeviceTreeService.fetch($scope.$id)
            icswDeviceLivestatusDataService.retain($scope.$id, _dev_list)
        ]
        $q.all(wait_list).then((data) ->
            $scope.dev_tree_lut = data[0][4]
            $scope.host_entries = data[1][0]
            $scope.service_entries = data[1][1]
            $scope.host_lut = data[1][2]
            $scope.burst_data = $scope.build_sunburst($scope.host_entries, $scope.service_entries)
            $scope.md_filter_changed()
        )
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
                    (_check_filter(_v) for _v in $scope.burst_data.get_childs((node) -> return node.filter))
                    if $scope.single_selection
                        $scope.set_data($scope.burst_data, $scope.dev_tree_lut[$scope._burst_sel[0]].full_name)
                    else
                        $scope.set_data($scope.burst_data, "")

        $scope.build_sunburst = (host_entries, service_entries) ->
            # build burst data
            _bdat = new hs_node(
                "System"
                {"state": 0, "idx" : 0, "ct": "system"}
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

]).directive("newburst", ["$compile", "$templateCache", "msgbus", ($compile, $templateCache, msgbus) ->
    return {
        restrict : "E"
        replace: true
        templateNamespace: "svg"
        template: $templateCache.get("icsw.device.livestatus.network_graph")
        controller: "icswDeviceLivestatusBurstCtrl"
        scope:
            device_pk: "=devicePk"
            serviceFocus: "=serviceFocus"
            omittedSegments: "=omittedSegments"
            ls_filter: "=lsFilter"
            ls_devsel: "=lsDevsel"
            is_drawn: "=isDrawn"
        link: (scope, element, attrs) ->
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
            if not attrs["devicePk"]
                scope.$watch(
                    scope.ls_devsel.changed
                    (changed) ->
                        scope.burst_sel(scope.ls_devsel.get(), false)
                )
            scope.$watch("device_pk", (new_val) ->
                if new_val
                    if angular.isString(new_val)
                        data = (parseInt(_v) for _v in new_val.split(","))
                    else
                        data = [new_val]
                    scope.burst_sel(data, true)
            )
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
                    if part.check.ct == "host"
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
]).directive("icswDeviceLivestatus", ["$templateCache", "msgbus", ($templateCache, msgbus) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.livestatus.overview")
        controller: "icswDeviceLiveStatusCtrl"
        link : (scope, el, attrs) ->
    }
]).directive("icswDeviceLivestatusBrief", ["icswLivestatusFilterFactory", "$templateCache", (icswLivestatusFilterFactory, $templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.livestatus.brief")
        controller: "icswDeviceLiveStatusCtrl"
        scope:
             devicepk: "=devicepk"
        replace: true
        link : (scope, element, attrs) ->
            scope.ls_filter = new icswLivestatusFilterFactory()
            scope.$watch("devicepk", (data) ->
                if data
                    scope.new_devsel([data], [])
            )
    }
]).directive("icswDeviceLivestatusMap", ["icswLivestatusFilterFactory", "$templateCache", (icswLivestatusFilterFactory, $templateCache) ->
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
    ["$templateCache", "icswDeviceLivestatusCategoryTreeService", "icswCachingCall", "$q", "ICSW_URLS",
    ($templateCache, icswDeviceLivestatusCategoryTreeService, icswCachingCall, $q, ICSW_URLS) ->
        return {
            restrict: "EA"
            template: $templateCache.get("icsw.device.livestatus.table.view")
            scope: {
                ls_filter: "=lsFilter"
                ls_devsel: "=lsDevsel"
                filtered_entries: "=filteredEntries"
            }
            link: (scope, elem, attrs) ->
        }
]).directive("icswDeviceLivestatusCatTree",
    ["$templateCache", "icswDeviceLivestatusCategoryTreeService", "icswCachingCall", "$q", "ICSW_URLS",
    ($templateCache, icswDeviceLivestatusCategoryTreeService, icswCachingCall, $q, ICSW_URLS) ->
        return {
            restrict: "EA"
            template: $templateCache.get("icsw.device.livestatus.cat.tree")
            scope: {
                ls_filter: "=lsFilter"
            }
            link: (scope, elem, attrs) ->
                # category tree
                scope.cat_tree = new icswDeviceLivestatusCategoryTreeService(scope, {})
                # add categories to filter
                $q.all([icswCachingCall.fetch(scope.$id, ICSW_URLS.REST_CATEGORY_LIST, {}, [])]).then((data) ->
                    cat_tree_lut = {}
                    scope.cat_tree.clear_root_nodes()
                    # list of all pks
                    selected_mcs = []
                    # name lut
                    name_lut = {}
                    # add dummy entry
                    for entry in data[0]
                        if entry.full_name.match(/^\/mon/)
                            entry.short_name = entry.full_name.substring(5)
                            entry.count = 0
                            t_entry = scope.cat_tree.new_node({folder:false, obj:entry, expand:entry.depth < 1, selected: true})
                            t_entry._show_select = false
                            cat_tree_lut[entry.idx] = t_entry
                            name_lut[entry.idx] = entry.short_name
                            if entry.parent and entry.parent of cat_tree_lut
                                cat_tree_lut[entry.parent].add_child(t_entry)
                            else
                                # hide selection from root nodes
                                _mc_pk = entry.idx
                                scope.cat_tree.add_root_node(t_entry)
                                # dummy entry for unspecified
                                entry = {idx:0, short_name:"unspecified", full_name:"/unspecified", depth:1}
                                entry.count = 0
                                d_entry = scope.cat_tree.new_node({folder:false, obj:entry, expand:false, selected:true})
                                d_entry._show_select = false
                                cat_tree_lut[0] = d_entry
                                cat_tree_lut[_mc_pk].add_child(d_entry)
                            selected_mcs.push(entry.idx)
                    selected_mcs.push(entry.idx)
                    scope.cat_tree_lut = cat_tree_lut
                    scope.cat_tree.show_selected(false)
                    scope.categories = selected_mcs
                    scope.ls_filter.set_categories(selected_mcs, name_lut)
                    scope.ls_filter.register_filter_func(scope.filter)
                    # check for active categories
                    scope.$watch(
                        scope.ls_filter.get_used_cats
                        (uc) ->
                            if uc.length
                                for pk of scope.cat_tree_lut
                                    entry = scope.cat_tree_lut[pk]
                                    if parseInt(pk) in uc
                                        entry._show_select = true
                                    else
                                        entry.selected = false
                                        entry._show_select = false
                    )
                )
                scope.filter = (entry) ->
                    if not scope.categories.length
                        return false
                    if entry.custom_variables and entry.custom_variables.cat_pks?
                        # only show if there is an intersection
                        return if _.intersection(scope.categories, entry.custom_variables.cat_pks).length then true else false
                    else
                        # show entries with unset / empty category
                        return 0 in scope.categories
                    return true
                scope.new_cat_selection = (new_sel) ->
                    scope.categories = new_sel
                    scope.ls_filter.set_categories(new_sel)
                    scope.ls_filter.trigger()
        }
]).directive("icswDeviceLivestatusLocationMap", ["$templateCache", "$compile", "$modal", "Restangular", ($templateCache, $compile, $modal, Restangular) ->
    return {
        restrict : "EA"
        template: $templateCache.get("icsw.device.livestatus.location.map")
        scope:
            loc_gfx : "=gfx"
            ls_filter: "=lsFilter"
            gfx_size: "=gfxSize"
        link : (scope, element, attrs) ->
            scope.$watch("gfx_size", (new_val) ->
                scope.width = parseInt(new_val.split("x")[0])
                scope.height = parseInt(new_val.split("x")[1])
            )
    }
]).directive("icswSvgSetViewbox", [() ->
    return {
        restrict: "A"
        link: (scope, element, attrs) ->
            scope.$watch(attrs["icswSvgSetViewbox"], (new_val) ->
                if new_val
                    element[0].setAttribute("viewBox", "0 0 #{new_val.width} #{new_val.height}")
            )
    }
]).directive("icswSvgBorderpoints", [() ->
    return {
        restrict: "A"
        link: (scope, element, attrs) ->
            scope.$watch(attrs["icswSvgBorderpoints"], (new_val) ->
                if new_val
                    _w = new_val.width
                    _h = new_val.height
                    element[0].setAttribute("points", "0,0 #{_w},0 #{_w},#{_h} 0,#{_h} 0 0")
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
]).directive(
    "icswDeviceLivestatusMaplist",
    ["$compile", "$templateCache", "icswCachingCall", "$q", "ICSW_URLS", "$timeout", "icswConfigCategoryTreeFetchService", (
        $compile, $templateCache, icswCachingCall, $q, ICSW_URLS, $timeout, icswConfigCategoryTreeFetchService
    ) ->
        return {
            restrict: "EA"
            template: $templateCache.get("icsw.device.livestatus.maplist")
            scope: {
                ls_filter: "=lsFilter"
                ls_devsel: "=lsDevsel"
            }
            link: (scope, element, attrs) ->
                # location gfx list
                scope.gfx_sizes = ["1024x768", "1280x1024", "1920x1200", "800x600", "640x400"]
                scope.gfx = {"size" : scope.gfx_sizes[0]}
                scope.autorotate = false
                scope.location_gfx_list = []
                scope.devsel_list = []
                scope.cur_page = -1
                # flag for enclosing div
                scope.show_maps = false
                scope.$watch(
                    scope.ls_devsel.changed
                    (changed) ->
                        _dev_sel = scope.ls_devsel.get()
                        scope.devsel_list = _dev_sel
                        icswConfigCategoryTreeFetchService.fetch(scope.$id, scope.devsel_list).then((data) ->
                            scope.location_gfx_list = data[1]
                            if scope.location_gfx_list.length
                                scope.show_maps = true
                            else
                                scope.show_maps = false
                            scope.ls_filter.set_num_maps(scope.location_gfx_list.length)
                            gfx_lut = {}
                            for entry in scope.location_gfx_list
                                entry.active = false
                                gfx_lut[entry.idx] = entry
                                entry.dml_list = []
                            # lut: device_idx -> list of dml_entries
                            dev_gfx_lut = {}
                            for entry in data[2]
                                if entry.device not of dev_gfx_lut
                                    dev_gfx_lut[entry.device] = []
                                dev_gfx_lut[entry.device].push(entry)
                                entry.redraw = 0
                                gfx_lut[entry.location_gfx].dml_list.push(entry)
                            scope.dev_gfx_lut = dev_gfx_lut
                        )
                )
                rte = null
                _activate_rotation = () ->
                    if scope.cur_page >= 0
                        scope.location_gfx_list[scope.cur_page].active = false
                    scope.cur_page++
                    if scope.cur_page >= scope.location_gfx_list.length
                        scope.cur_page = 0
                    scope.location_gfx_list[scope.cur_page].active = true
                    rte = $timeout(_activate_rotation, 4000)
                _deactivate_rotation = () ->
                    if rte
                        $timeout.cancel(rte)
                scope.toggle_autorotate = () ->
                    scope.autorotate = !scope.autorotate
                    if scope.autorotate
                        _activate_rotation()
                    else
                        _deactivate_rotation()
                scope.select_settings = () ->
                    scope.autorotate = false
                    _deactivate_rotation()
        }
])
