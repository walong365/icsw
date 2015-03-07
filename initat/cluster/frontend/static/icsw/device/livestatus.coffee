get_service_state_string = (entry) ->
    return {
        0: "OK"
        1: "Warning"
        2: "Critical"
        3: "Unknown"
    }[entry.state]

get_host_state_string = (entry) ->
    return {
        0: "OK"
        1: "Critical"
        2: "Unreachable"
    }[entry.state]

get_service_state_class = (entry) ->
    return {
        0: "success"
        1: "warning"
        2: "danger"
        3: "danger"
    }[entry.state]

get_host_state_class = (entry) ->
    return {
        0: "success"
        1: "danger"
        2: "danger"
    }[entry.state]

show_attempt_info = (entry) ->
    try
        if parseInt(entry.current_attempt) == 1
            return true
        else
            return true
    catch error
       return true

get_attempt_info = (entry, force=false) ->
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

get_attempt_class = (entry, force=false) ->
    if entry.max_check_attempts == null
        return "label-default"
    try
        max = parseInt(entry.max_check_attempts)
        cur = parseInt(entry.current_attempt)
        if max == cur
            return "label-info"
        else
            return "label-success"
    catch error
        return "label-danger"

get_state_type = (entry) ->
    return {
        null : "???"
        0 : "soft"
        1 : "hard"
    }[entry.state_type]

get_check_type = (entry) ->
    return {
        null : "???"
        0 : "active"
        1 : "passive"
    }[entry.check_type]

class hs_node
    # hierarchical structure node
    constructor: (@name, @depth=0) ->
        @value = 1
        @root = @
        @children = []
        @show = true
        @clicked = false
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
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular"
    ]
).controller("icswDeviceLiveStatusCtrl",
    ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "restDataSource", "$q", "$modal", "$timeout",
     "icswTools", "ICSW_URLS", "icswDeviceLivestatusCategoryTreeService", "icswCallAjaxService", "icswParseXMLResponseService", "icswDeviceLivestatusDataService",
     "icswCachingCall",
    ($scope, $compile, $filter, $templateCache, Restangular, restDataSource,
     $q, $modal, $timeout, icswTools, ICSW_URLS, icswDeviceLivestatusCategoryTreeService, icswCallAjaxService, icswParseXMLResponseService, icswDeviceLivestatusDataService,
     icswCachingCall) ->
        $scope.host_entries = []
        $scope.entries = []
        $scope.filtered_entries = []
        $scope.order_name = "host_name"
        $scope.order_dir = true
        # not needed
        #$scope.cur_timeout = undefined
        # focused
        $scope.focusService = null
        # draw response
        $scope.burstResponse = null
        # flag to trigger redraw of sunburst
        $scope.redrawSunburst = 0
        # flag to trigger recalc of sunburst visibility
        $scope.recalcSunburst = 0
        $scope.cat_tree_show = false
        $scope.burst_show = true
        $scope.burstData = undefined
        $scope.map_show = true
        $scope.table_show = true
        # location gfx list
        $scope.location_gfx_list = []
        # omitted segments
        $scope.omitted_segments = 0
        $scope.$watch("focusService", (as) ->
            # link nested newburst
            $scope.focusService = as
        )
        $scope.$watch("burstResponse", (as) ->
            # link nested newburst
            $scope.burstResponse = as
            $scope.omitted_segments = as
        )
        $scope.$watch("recalcSunburst", (red) ->
            $scope.md_filter_changed()
        )
        # category tree
        $scope.cat_tree = new icswDeviceLivestatusCategoryTreeService($scope, {})
        # selected categories
        $scope.selected_mcs = []
        $scope.master_cat_pk = 0
        $scope.show_unspec_cat = true
        # int_state, str_state, default
        $scope.md_states = [
            [0, "O", true, "show OK states"]
            [1, "W", true, "show warning states"]
            [2, "C", true, "show critcal states"]
            [3, "U", true, "show unknown states"]
        ]
        $scope.sh_states = [
            [0, "S", true, "show soft states"]
            [1, "H", true, "show hard states"]
        ]
        $scope.mds_enabled = {}
        for entry in $scope.md_states
            $scope.mds_enabled[entry[0]] = entry[2]
        $scope.shs_enabled = {}
        for entry in $scope.sh_states
            $scope.shs_enabled[entry[0]] = entry[2]
        $scope.get_mds_class = (int_state) ->
            return if $scope.mds_enabled[int_state] then "btn btn-xs " + {0 : "btn-success", 1 : "btn-warning", 2 : "btn-danger", 3 : "btn-danger"}[int_state] else "btn btn-xs"
        $scope.get_shs_class = (int_state) ->
            return if $scope.shs_enabled[int_state] then "btn btn-xs btn-primary" else "btn btn-xs"
        $scope.toggle_mds = (int_state) ->
            $scope.mds_enabled[int_state] = !$scope.mds_enabled[int_state]
            $scope.md_filter_changed()
        $scope.toggle_shs = (int_state) ->
            $scope.shs_enabled[int_state] = !$scope.shs_enabled[int_state]
            $scope.md_filter_changed()
        $scope.new_devsel = (_dev_sel, _devg_sel) ->
            #pre_sel = (dev.idx for dev in $scope.devices when dev.expanded)
            #restDataSource.reset()
            $scope.devsel_list = _dev_sel
            $scope.load_static_data()
        $scope.toggle_order = (name) ->
            if $scope.order_name == name
                $scope.order_dir = not $scope.order_dir
            else
                $scope.order_name = name
                $scope.order_dir = true
        $scope.new_mc_selection = (new_sel) ->
            $scope.selected_mcs = new_sel
            $scope.show_unspec_cat = $scope.master_cat_pk in $scope.selected_mcs
            $scope.md_filter_changed()
        $scope.get_header_class = (entry) ->
            return "nowrap"
        $scope.get_order = () ->
            return (if $scope.order_dir then "" else "-") + $scope.order_name
        $scope.get_order_glyph = (name) ->
            if $scope.order_name == name
                if $scope.order_dir 
                    _class = "glyphicon glyphicon-chevron-down"
                else
                    _class = "glyphicon glyphicon-chevron-up"
            else
                _class = "glyphicon glyphicon-chevron-right"
            return _class
        $scope.load_static_data = () ->
            wait_list = [
                icswCachingCall.fetch($scope.$id, ICSW_URLS.REST_CATEGORY_LIST, {}, [])
                icswCachingCall.fetch($scope.$id, ICSW_URLS.REST_DEVICE_TREE_LIST, {"with_meta_devices" : false, "ignore_cdg" : true, "pks": "<PKS>"}, $scope.devsel_list)
                icswCachingCall.fetch($scope.$id, ICSW_URLS.REST_LOCATION_GFX_LIST, {"device_mon_location__device__in": "<PKS>", "_distinct": true}, $scope.devsel_list)
                icswCachingCall.fetch($scope.$id, ICSW_URLS.REST_DEVICE_MON_LOCATION_LIST, {"device__in": "<PKS>"}, $scope.devsel_list)
                icswDeviceLivestatusDataService.retain($scope.$id, $scope.devsel_list)
            ]
            $q.all(wait_list).then((data) ->
                $scope.location_gfx_list = data[2]
                gfx_lut = {}
                for entry in $scope.location_gfx_list
                    gfx_lut[entry.idx] = entry
                    entry.dml_list = []
                # lut: device_idx -> list of dml_entries
                dev_gfx_lut = {}
                for entry in data[3]
                    if entry.device not of dev_gfx_lut
                        dev_gfx_lut[entry.device] = []
                    dev_gfx_lut[entry.device].push(entry)
                    entry.redraw = 0
                    gfx_lut[entry.location_gfx].dml_list.push(entry)
                $scope.dev_gfx_lut = dev_gfx_lut
                cat_tree_lut = {}
                $scope.cat_tree.clear_root_nodes()
                $scope.selected_mcs = []
                for entry in data[0]
                    if entry.full_name.match(/^\/mon/)
                        entry.short_name = entry.full_name.substring(5)
                        t_entry = $scope.cat_tree.new_node({folder:false, obj:entry, expand:entry.depth < 1, selected: true})
                        cat_tree_lut[entry.idx] = t_entry
                        if entry.parent and entry.parent of cat_tree_lut
                            cat_tree_lut[entry.parent].add_child(t_entry)
                        else
                            # hide selection from root nodes
                            $scope.master_cat_pk = entry.idx
                            $scope.cat_tree.add_root_node(t_entry)
                        $scope.selected_mcs.push(entry.idx)
                $scope.cat_tree_lut = cat_tree_lut
                $scope.cat_tree.show_selected(false)
                $scope.dev_tree_lut = icswTools.build_lut(data[1])
                $scope.on_new_data(data[4][0], data[4][1], data[4][2])
            )
        $scope.on_new_data = (host_entries, service_entries, host_lut) ->
            $scope.host_entries = host_entries
            $scope.entries = service_entries
            $scope.host_lut = host_lut
            used_cats = []

            for entry in service_entries
                if entry.custom_variables and entry.custom_variables.cat_pks?
                    used_cats = _.union(used_cats, entry.custom_variables.cat_pks)

            for pk of $scope.cat_tree_lut
                entry = $scope.cat_tree_lut[pk]
                if parseInt(pk) in used_cats
                    entry._show_select = true
                else
                    entry.selected = false
                    entry._show_select = false
            $scope.build_sunburst()
            $scope.md_filter_changed()
        $scope.build_sunburst = () ->
            # build burst data
            _bdat = new hs_node("System")
            _bdat.check = {"state" : 0, "type" : "system", "idx" : 0, "ct": "system"}
            _devg_lut = {}
            # lut: dev idx to hs_nodes
            dev_hs_lut = {}
            for entry in $scope.host_entries
                if entry.custom_variables.device_pk of $scope.dev_tree_lut
                    _dev = $scope.dev_tree_lut[entry.custom_variables.device_pk]
                    if _dev.device_group_name not of _devg_lut
                        # we use the same index for devicegroups and services ...
                        _devg = new hs_node(_dev.device_group_name)
                        _devg.check = {
                            "ct"    : "group"
                            "state" : 0
                            "type"  : "group"
                            "group_name" : _dev.device_group_name
                        }
                        _devg_lut[_devg.name] = _devg
                        _bdat.add_child(_devg)
                    else
                        _devg = _devg_lut[_dev.device_group_name]
                    # sunburst struct for device
                    entry.group_name = _dev.device_group_name
                    _dev_sbs = new hs_node(_dev.full_name)
                    _dev_sbs.check = entry
                    _devg.add_child(_dev_sbs)
                    # set devicegroup state
                    _devg.check.state = Math.max(_devg.check.state, _dev_sbs.check.state)
                    # set system state
                    _bdat.check.state = Math.max(_bdat.check.state, _devg.check.state)
                    dev_hs_lut[_dev.idx] = [_dev_sbs]
                    # create sunburst for mon locations
                    if _dev.idx of $scope.dev_gfx_lut
                        for dml in $scope.dev_gfx_lut[_dev.idx]
                            dml_sb = new hs_node(_dev.full_name)
                            dml_sb.check = entry
                            dev_hs_lut[_dev.idx].push(dml_sb)
                            # link sunburst with dml
                            dml.sunburst = dml_sb
            for entry in $scope.entries
                # sanitize entries
                if entry.custom_variables.device_pk of $scope.dev_tree_lut
                    _srv_node = new hs_node(entry.description)
                    _srv_node.check = entry
                    for node in dev_hs_lut[entry.custom_variables.device_pk]
                        _srv_node = new hs_node(entry.description)
                        _srv_node.check = entry
                        node.add_child(_srv_node)
            # remove empty devices
            for _devg in _bdat.children
                _devg.children = (entry for entry in _devg.children when entry.children.length)
            _bdat.children = (entry for entry in _bdat.children when entry.children.length)
            $scope.burstData = _bdat
        $scope.md_filter_changed = () ->
            get_filter = (node) ->
               if node.check?
                   # filter for services
                   return node.check.ct == "service"
               else
                   return false
            if $scope.burstData?
                if $scope.burstData.any_clicked()
                    $scope.burstData.handle_clicked()
                srv_entries = $scope.burstData.get_childs(
                    (node) ->
                       if node.check?
                           return node.check.ct == "service"
                       else
                           return false
                )
                # called when new entries are set or a filter rule has changed
                ($scope._check_filter(entry) for entry in srv_entries)
                # filter dml
                for dev_idx of $scope.dev_gfx_lut
                    for dml in $scope.dev_gfx_lut[dev_idx]
                        if dml.sunburst?
                            ($scope._check_filter(entry) for entry in dml.sunburst.get_childs(get_filter))
                            dml.redraw++
                $scope.redrawSunburst++
            $scope.filtered_entries = (_v for _v in $scope.entries when _v._show)
        $scope._check_filter = (entry) ->
            show = entry.show
            _check = entry.check
            if not $scope.mds_enabled[_check.state]
                show = false
            if not $scope.shs_enabled[_check.state_type]
                show = false
            if show
                if not $scope.selected_mcs.length
                   show = false
                else
                    if _check.custom_variables and _check.custom_variables.cat_pks?
                        # only show if there is an intersection
                        show = if _.intersection($scope.selected_mcs, _check.custom_variables.cat_pks).length then true else false
                    else
                        # show entries with unset / empty category
                        show = $scope.show_unspec_cat
            _check._show = show
            entry.value = if show then 1 else 0
            return show
        $scope.filter_mdr = (entry, scope) ->
            return entry._show
        $scope.$on("$destroy", () ->
            icswDeviceLivestatusDataService.destroy($scope.$id)
        )
]).service("icswCachingCall", ["$interval", "$timeout", "$q", "Restangular", ($inteval, $timeout, $q, Restangular) ->
    class LoadInfo
        constructor: (@key, @url, @options) ->
            @client_dict = {}
            @pk_list = []
        add_pk_list: (client, pk_list) =>
            @pk_list = @pk_list.concat(pk_list)
            _defer = $q.defer()
            @client_dict[client] = _defer
            return _defer
        load: () =>
            opts = {}
            for key, value of @options
                if value == "<PKS>"
                    opts[key] = angular.toJson(@pk_list)
                else
                    opts[key] = value
            Restangular.all(@url.slice(1)).getList(opts).then(
                (result) =>
                    for c_id, _defer of @client_dict
                        # console.log "resolve client ", c_id, "for ", @key
                        _defer.resolve(result)
                    @client_dict = {}
                    @pk_list = []
            )
    start_timeout = {}
    load_info = {}
    schedule_load = (key) ->
        # called when new listeners register
        # don't update immediately, wait until more controllers have registered
        # console.log key, start_timeout[key]?
        if start_timeout[key]?
            $timeout.cancel(start_timeout[key])
            delete start_timeout[key]
        if not start_timeout[key]?
            start_timeout[key] = $timeout(
                () ->
                    # console.log "load", key
                    load_info[key].load()
                1
            )
    add_client = (client, url, options, pk_list) ->
        url_key = _key(url, options)
        if url_key not of load_info
            load_info[url_key] = new LoadInfo(url_key, url, options)
        # console.log "add client", client, "to", url_key
        return load_info[url_key].add_pk_list(client, pk_list)
    _key = (url, options) ->
        url_key = url
        for key, value of options
            url_key = "#{url_key},#{key}=#{value}"
        return url_key
    return {
        "fetch" : (client, url, options, pk_list) ->
            _defer = add_client(client, url, options, pk_list)
            schedule_load(_key(url, options))
            return _defer.promise
    }
]).service('icswDeviceLivestatusTableService', ["ICSW_URLS", (ICSW_URLS) ->
    return {
        edit_template       : "network.type.form"
    }
]).service("icswDeviceLivestatusDataService", ["ICSW_URLS", "$interval", "$timeout", "icswCallAjaxService", "icswParseXMLResponseService", "$q", (ICSW_URLS, $interval, $timeout, icswCallAjaxService, icswParseXMLResponseService, $q) ->
    watch_list = {}
    defer_list = {}
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
                    _cv[int_mkey] = (parseInt(_sv) for _sv in _cv[int_mkey])
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
                        service_entries = []
                        $(xml).find("value[name='service_result']").each (idx, node) =>
                            service_entries = service_entries.concat(angular.fromJson($(node).text()))
                        host_entries = []
                        $(xml).find("value[name='host_result']").each (idx, node) =>
                            host_entries = host_entries.concat(angular.fromJson($(node).text()))
                        host_lut = {}
                        for entry in host_entries
                            # sanitize entries
                            _sanitize_entries(entry)
                            # list of checks for host
                            entry.checks = []
                            entry.ct = "host"
                            entry.custom_variables = _parse_custom_variables(entry.custom_variables)
                            host_lut[entry.host_name] = entry
                            host_lut[entry.custom_variables.device_pk] = entry
                        for entry in service_entries
                            # sanitize entries
                            _sanitize_entries(entry)
                            entry.custom_variables = _parse_custom_variables(entry.custom_variables)
                            entry.description = entry.display_name  # this is also what icinga displays
                            entry.ct = "service"
                            # populate list of checks
                            host_lut[entry.custom_variables.device_pk].checks.push(entry)

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

                            _defer.resolve([hosts_client, services_client, host_lut_client])

    remove_watchers_by_client = (client) ->
        client = client.toString()
        for dev, watchers of watch_list
            _.remove(watchers, (elem) -> return elem == client)
        delete defer_list[client]

    return {
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

                for dev in dev_list
                    if not watch_list[dev]?
                        watch_list[dev] = []

                    if not _.some(watch_list[dev], (elem) -> return elem == dev)
                        watch_list[dev].push(client)

                    defer_list[client] = _defer

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
            @scope.new_mc_selection(sel_list)
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
).directive("icswDeviceLivestatusServiceInfo", ["$templateCache", ($templateCache) ->
    return {
        restrict : "E"
        template : $templateCache.get("icsw.device.livestatus.serviceinfo")
        scope : {
            type : "=type"
            service : "=service"
        }
        link : (scope, element) ->
            scope.get_service_state_string = (entry) ->
                return get_service_state_string(entry)
            scope.get_host_state_string = (entry) ->
                return get_host_state_string(entry)
            scope.get_host_state_class = (entry) ->
                return "label label-#{get_host_state_class(entry)} pull-right"
            scope.get_service_state_class = (entry) ->
                return "label label-#{get_service_state_class(entry)} pull-right"
            scope.get_attempt_info = (entry) ->
                return get_attempt_info(entry, true)
            scope.get_state_type = (entry) ->
                return get_state_type(entry)
            scope.get_check_type = (entry) ->
                return get_check_type(entry)
    }
]).directive("newburst", ["$compile", "$templateCache", ($compile, $templateCache) ->
    return {
        restrict : "E"
        replace: true
        templateNamespace: "svg"
        template: $templateCache.get("icsw.device.livestatus.network_graph")
        scope:
            data: "=data"
            redraw_burst: "=redraw"
            recalc_burst: "=recalc"
            serviceFocus: "=serviceFocus"
            burstResponse: "=burstResponse"
        link: (scope, element, attrs) ->
            scope.nodes = []
            scope.inner = parseInt(attrs["innerradius"] or 20)
            scope.outer = parseInt(attrs["outerradius"] or 120)
            scope.zoom = parseInt(attrs["zoom"] or 0)
            scope.font_stroke = parseInt(attrs["fontstroke"] or 0)
            scope.show_name = parseInt(attrs["showname"] or 0)
            scope.noninteractive = attrs["noninteractive"]  # defaults to false
            scope.hidegroup = attrs["hidegroup"]  # defaults to false
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
            scope.$watch("data", (data) ->
                if data?
                    data_ok = true
                    if scope.hidegroup
                        if data.children.length > 0  # if not proper livestatus is available, data does not have any children
                            # skip first two levels
                            data = data.children[0].children[0]
                        else
                            data_ok = false

                    if data_ok
                        scope.set_focus_service(null)
                        scope.sunburst_data = data
                        scope.name = scope.sunburst_data.name
                        scope.draw_data()
                )
            scope.$watch("redraw_burst", (data) ->
                if scope.sunburst_data?
                    scope.draw_data()
            )
            scope.set_focus_service = (srvc) ->
                if "serviceFocus" of attrs
                    scope.serviceFocus = srvc
            scope.force_recalc = () ->
                if "recalc" of attrs
                    scope.recalc_burst++
            scope.draw_data = () ->
                # struct: dict of concentric circles, beginning with the innermost
                struct = {}
                _size = scope.get_children(scope.sunburst_data, 0, struct)
                scope.max_depth = (idx for idx of struct).length
                scope.nodes = []
                omitted_segments = 0
                for idx of struct
                    if struct[idx].length
                        omitted_segments += scope.add_circle(parseInt(idx), struct[idx])
                if attrs["burstResponse"]
                    scope.burstResponse = omitted_segments
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
                if not _len
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
                    # console.log idx, _len, nodes.length
                    end_arc = 0
                    end_num = 0
                    # legend radii
                    inner_legend = (outer + inner) / 2
                    outer_legend = scope.outer * 1.125
                    for part in nodes
                        if part.width
                            start_arc = end_arc #+ 1 * Math.PI / 180
                            start_sin = Math.sin(start_arc)
                            start_cos = Math.cos(start_arc)
                            end_num += part.width
                            end_arc = 2 * Math.PI * end_num / _len
                            if (end_arc - start_arc) * outer < 3
                                # arc is too small, do not draw
                                omitted_segments++
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
                else
                    color = "#dddddd"
                return color
            scope.get_fill_opacity = (part) ->
                if part.mouseover? and part.mouseover
                    return 0.4
                else
                    return 0.8
            scope.mouse_enter = (part) ->
                if !scope.noninteractive
                    scope.set_focus_service(part.check)
                    if part.children.length
                        for _entry in part.children
                            if _entry.value
                                _entry.legend_show = true
                    else
                        if part.value
                            part.legend_show = true
                    scope.set_mouseover(part, true)
            scope.mouse_click = (part) ->
                if scope.zoom and !scope.noninteractive
                    scope.sunburst_data.clear_clicked()
                    part.clicked = true
                    scope.force_recalc()
            scope.mouse_leave = (part) ->
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
]).directive("livestatus", ["$templateCache", "msgbus", ($templateCache, msgbus) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.livestatus.overview")
        controller: "icswDeviceLiveStatusCtrl"
        link : (scope, el, attrs) ->
            scope.get_state_class = (entry) ->
                state_class = {
                    0 : "success"
                    1 : "warning"
                    2 : "danger"
                    3 : "danger"
                }[entry.state]
                return "#{state_class} nowrap"
            scope.get_last_check = (entry) ->
                return scope.get_diff_time(entry.last_check)
            scope.get_last_change = (entry) ->
                return scope.get_diff_time(entry.last_state_change)
            scope.get_diff_time = (ts) ->
                if parseInt(ts)
                    return moment.unix(ts).fromNow(true)
                else
                    return "never"
            scope.get_categories = (entry) ->
                if entry.custom_variables
                    if entry.custom_variables.cat_pks?
                        return (scope.cat_tree_lut[_pk].obj.short_name for _pk in entry.custom_variables.cat_pks).join(", ")
                    else
                        return "---"
                else
                    return "N/A"
            scope.get_state_type = (entry) ->
                return get_state_type(entry)
            scope.get_check_type = (entry) ->
                return get_check_type(entry)
            scope.host_is_passive_checked = (entry) ->
                if entry.host_name of scope.host_lut
                    return if scope.host_lut[entry.host_name].check_type then true else false 
                else
                    return false                  
            scope.is_passive_check = (entry) ->
                return if entry.check_type then true else false 
            scope.get_host_class = (entry) ->
                if entry.host_name of scope.host_lut
                    h_state = scope.host_lut[entry.host_name].state
                    h_state_str = {
                        0 : "success"
                        1 : "danger"
                        2 : "danger"
                    }[h_state]
                else
                    h_state_str = "warning"
                return "#{h_state_str} nowrap"
            scope.get_host_state_string = (entry) -> 
                return get_host_state_string(entry)
            scope.get_host_state_class = (entry) -> 
                return get_host_state_class(entry) + " nowrap"
            scope.get_service_state_string = (entry) -> 
                return get_service_state_string(entry)
            scope.get_service_state_class = (entry) -> 
                return get_service_state_class(entry) + " nowrap"
            scope.show_host_attempt_info = (srv_entry) ->
                return scope.show_attempt_info(scope.host_lut[srv_entry.host_name])
            scope.show_attempt_info = (entry) ->
                return show_attempt_info(entry)
            scope.get_host_attempt_info = (srv_entry) ->
                return scope.get_attempt_info(scope.host_lut[srv_entry.host_name])
            scope.get_host_attempt_class = (srv_entry) ->
                return scope.get_attempt_class(scope.host_lut[srv_entry.host_name])
            scope.get_attempt_info = (entry) ->
                return get_attempt_info(entry)
            scope.get_attempt_class = (entry) ->
                return get_attempt_class(entry)
    }
]).directive("livestatusBrief", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.livestatus.brief")
        controller: "icswDeviceLiveStatusCtrl"
        scope:
             devicepk: "=devicepk"
             redrawSunburst: "=redrawSunburst"
        replace: true
        link : (scope, element, attrs) ->
            scope.$watch("devicepk", (data) ->
                if data
                    scope.new_devsel([data], [])
            )
    }
]).directive("monmap", ["$templateCache", "$compile", "$modal", "Restangular", ($templateCache, $compile, $modal, Restangular) ->
    return {
        restrict : "EA"
        template: $templateCache.get("icsw.device.livestatus.map.overview")
        scope:
            gfx : "=gfx"
        link : (scope, element, attrs) ->
            scope.loc_gfx = undefined
            scope.$watch("gfx", (new_val) ->
                scope.loc_gfx = new_val
            )
    }
]).directive("devnode", ["$compile", "$templateCache", ($compile, $templateCache) ->
    return {
        restrict : "EA"
        replace: true
        template: $templateCache.get("icsw.device.livestatus.device.node")
        link: (scope, element, attrs) ->
            dml = scope.dml
            scope.data_source = ""
            scope.transform = "translate(#{dml.pos_x},#{dml.pos_y})"
            scope.$watch("dml.sunburst", (dml) ->
                if dml?
                    scope.data_source = "b"
            )
    }    
])
