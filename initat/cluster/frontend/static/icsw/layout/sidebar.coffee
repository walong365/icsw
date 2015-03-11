angular.module(
    "icsw.layout.sidebar",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "noVNC", "ui.select", "icsw.tools", "icsw.device.info",
    ]
).service("icswDeviceTreeService", ["$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall", "icswTools", ($q, Restangular, ICSW_URLS, $window, icswCachingCall, icswTools) ->
    rest_map = [
        [
            ICSW_URLS.REST_DEVICE_TREE_LIST,
            {
                "ignore_cdg" : false
                "tree_mode" : true
                "all_devices" : true
                "with_categories" : true
                "olp" : $window.DEVICE_OBJECT_LEVEL_PERMISSION
            }
        ]
        [ICSW_URLS.REST_DOMAIN_TREE_NODE_LIST, {}]
        [ICSW_URLS.REST_CATEGORY_LIST, {}]
        [ICSW_URLS.REST_DEVICE_SELECTION_LIST, {}]
    ]
    _fetch_dict = {}
    _result = []
    load_data = (client) ->
        _wait_list = (icswCachingCall.fetch(client, _entry[0], _entry[1], []) for _entry in rest_map)
        _defer = $q.defer()
        $q.all(_wait_list).then((data) ->
            _result = data
            # build luts
            _result.push(icswTools.build_lut(data[0]))
            _defer.resolve(_result)
            for client of _fetch_dict
                # resolve clients
                _fetch_dict[client].resolve(_result)
            # reset fetch_dict
            _fetch_dict = {}
        )
        return _defer
    fetch_data = (client) ->
        if client not of _fetch_dict
            # register client
            _defer = $q.defer()
            _fetch_dict[client] = _defer
        if _result.length
            # resolve immediately
            _fetch_dict[client].resolve(_result)
        return _fetch_dict[client]
    return {
        "load": (client) ->
            # loads from server
            return load_data(client).promise
        "fetch": (client) ->
            # fetch when data is present (after sidebar)
            return fetch_data(client).promise
    }
    console.log rest_map

]).controller("icswSidebarCtrl", ["$scope", "$compile", "restDataSource", "$q", "$timeout", "Restangular", "$window", "msgbus", "DeviceOverviewService", "ICSW_URLS", "icswLayoutSidebarTreeService", "icswCallAjaxService", "icswParseXMLResponseService", "icswDeviceTreeService",
    ($scope, $compile, restDataSource, $q, $timeout, Restangular, $window, msgbus, DeviceOverviewService, ICSW_URLS, icswLayoutSidebarTreeService, icswCallAjaxService, icswParseXMLResponseService, icswDeviceTreeService) ->
        $scope.index_view = $window.INDEX_VIEW
        $scope.DeviceOverviewService = DeviceOverviewService
        $scope.msgbus = msgbus
        $scope.is_authenticated = $window.IS_AUTHENTICATED
        $scope.searchstr = ""
        $scope.search_ok = true
        $scope.is_loading = true
        # active tab, (g)roups, (f)qdn, (c)ategories
        $scope.hidden_tabs = {"g" : true, "f" : true, "c" : true}
        $scope.devsel_func = []
        $scope.devsel_receiver = 0
        $scope.call_devsel_func = () ->
            # list of devices
            dev_pk_list = []
            # list of devices without meta device list
            dev_pk_nmd_list = []
            # list of device groups
            devg_pk_list = []
            # list of metadevices
            dev_pk_md_list = []
            for idx in $scope.cur_sel
                if idx of $scope.dev_lut
                    # in case dev_lut is not valid
                    if $scope.dev_lut[idx].device_type_identifier == "MD"
                        devg_pk_list.push($scope.dev_lut[idx].device_group)
                        dev_pk_md_list.push(idx)
                    else
                        dev_pk_nmd_list.push(idx)
                    dev_pk_list.push(idx)
            # console.log "send devicelist"
            msgbus.emit("devicelist", [dev_pk_list, dev_pk_nmd_list, devg_pk_list, dev_pk_md_list])
            #for entry in $scope.devsel_func
            #    if called_after_load and not entry.fire_when_loaded
            #        true
            #    else
            #        # build device, device_group list
            #        if entry.with_meta_devices
            #            entry.func(dev_pk_list, devg_pk_list, dev_pk_md_list)
            #        else
            #            entry.func(dev_pk_nmd_list, devg_pk_list, dev_pk_md_list)
        $scope.resolve_device_keys = (key_list) =>
            list_len = key_list.length
            ret_list = list_len + (if list_len == 1 then " device" else " devices")
            if list_len
                if typeof(key_list[0]) == "int"
                    ret_list = "#{ret_list}: " + ($scope.dev_lut[key.split("__")[1]].full_name for key in key_list).join(", ")
                else
                    ret_list = "#{ret_list}: " + ($scope.dev_lut[key].full_name for key in key_list).join(", ")
            return ret_list
        $scope.update_search = () ->
            if $scope.cur_search_to
                $timeout.cancel($scope.cur_search_to)
            $scope.cur_search_to = $timeout($scope.set_search_filter, 500)
        $scope.set_search_filter = () ->
            try
                cur_re = new RegExp($scope.searchstr, "gi")
            catch exc
                cur_re = new RegExp("^$", "gi")
            cur_tree = $scope.get_tc($scope.active_tab) 
            cur_tree.toggle_tree_state(undefined, -1, false)
            num_found = 0
            cur_tree.iter(
                (entry, cur_re) ->
                    if entry._node_type == "d"
                        _sel = if $scope.dev_lut[entry.obj].full_name.match(cur_re) then true else false
                        entry.set_selected(_sel)
                        if _sel
                            num_found++
                cur_re
            )
            $scope.search_ok = if num_found > 0 then true else false
            cur_tree.show_selected(false)
            $scope.selection_changed()
        # current device selection
        $scope.cur_sel = []            
        $scope.active_tab = $window.SIDEBAR_MODE.slice(0, 1)
        $scope.tabs = {}
        for tab_short in ["g", "f", "c"]
            $scope.tabs[tab_short] = tab_short == $scope.active_tab
        # olp is the object level permission
        $scope.reload = (pk_list) ->
            if pk_list?
                # only reload the given devices
                # build list of current values
                prev_list = ([$scope.dev_lut[pk].domain_tree_node, (_entry for _entry in $scope.dev_lut[pk].categories)] for pk in pk_list)
                Restangular.all(ICSW_URLS.REST_DEVICE_TREE_LIST.slice(1)).getList({"pks" : angular.toJson(pk_list), "ignore_cdg" : false, "tree_mode" : true, "with_categories" : true, "olp" : $window.DEVICE_OBJECT_LEVEL_PERMISSION}).then((data) ->
                    $scope.update_device(data, prev_list)
                )
            else
                icswDeviceTreeService.load($scope.$id).then((data) ->
                    $scope.rest_data = {
                        "device_tree" : data[0]
                        "domain_tree_node": data[1]
                        "category": data[2]
                        "device_sel": data[3]
                    }
                    $scope.rest_data_set()
                )
        # load from server
        if $scope.is_authenticated
            $scope.reload()
        $scope.get_tc = (short) ->
            return {"g" : $scope.tc_devices, "f" : $scope.tc_fqdns, "c" : $scope.tc_categories}[short]
        $scope.set_active_selection = (t_type, new_sel) ->
            return $scope.get_tc(t_type).set_selected(
                (entry, new_sel) ->
                    if entry._node_type == "d"
                        return entry.obj in new_sel
                    else
                        # unknown node, return null
                        return null
                new_sel
            )
        $scope.get_active_selection = (t_type) ->
            return $scope.get_tc(t_type).get_selected(
                (entry) ->
                    if entry._node_type == "d" and entry.selected
                        return [entry.obj]
                    else
                        return []
            )
        $scope.clear_selection = () ->
            $scope.get_tc($scope.active_tab).clear_selected()
            $scope.search_ok = true
            $scope.selection_changed()
            $scope.call_devsel_func()
        $scope.activate_tab = (t_type) ->
            if $scope.is_authenticated
                if $scope.hidden_tabs[t_type]
                    $scope.hidden_tabs[t_type] = false
                    switch t_type
                        when "g"
                            $scope.s_tc_devices = $scope.tc_devices
                        when "f"
                            $scope.s_tc_fqdns = $scope.tc_fqdns
                        when "c"
                            $scope.s_tc_categories = $scope.tc_categories
                cur_sel = $scope.get_active_selection($scope.active_tab)
                $scope.set_active_selection(t_type, cur_sel)
                $scope.active_tab = t_type
                icswCallAjaxService
                    url  : ICSW_URLS.USER_SET_USER_VAR
                    data : 
                        key   : "sidebar_mode"
                        value : {"c" : "category", "f" : "fqdn", "g" : "group"}[$scope.active_tab]
                        type  : "str"
        $scope.selection_changed = () ->
            cur_sel = $scope.get_active_selection($scope.active_tab)
            # cast to string to compare the arrays
            if String(cur_sel) != String($scope.cur_sel)
                $scope.cur_sel = cur_sel
                icswCallAjaxService
                    url     : ICSW_URLS.DEVICE_SET_SELECTION
                    data    : {
                        "angular_sel" : angular.toJson(cur_sel)
                    }
                    success : (xml) ->
                        icswParseXMLResponseService(xml)
        # treeconfig for devices
        $scope.tc_devices = new icswLayoutSidebarTreeService($scope, {show_tree_expand_buttons : false, show_descendants : true})
        # treeconfig for FQDN
        $scope.tc_fqdns = new icswLayoutSidebarTreeService($scope, {show_childs : true})
        # treeconfig for categories
        $scope.tc_categories = new icswLayoutSidebarTreeService($scope, {show_selection_buttons : true, show_descendants : true})
        $scope.update_device = (new_devs, prev_list) ->#prev_dtn, prev_cats) ->
            for info_tuple in _.zip(new_devs, prev_list)
                new_dev = info_tuple[0]
                prev_dtn = info_tuple[1][0]
                prev_cats = info_tuple[1][1]
                $scope.dev_lut[new_dev.idx] = new_dev
                prev_node = $scope.t_fqdn_lut[prev_dtn]
                # get previous node
                del_c = (entry for entry in prev_node.children when entry.obj == new_dev.idx)[0]
                # remove it
                prev_node.remove_child(del_c)
                # add new node
                $scope.t_fqdn_lut[new_dev.domain_tree_node].add_child($scope.tc_fqdns.new_node({obj : new_dev.idx, _node_type : "d", selected:new_dev.idx in $scope.cur_sel}))
                # migrate categories
                for prev_cat in prev_cats
                    prev_node = $scope.t_cat_lut[prev_cat]
                    del_c = (entry for entry in prev_node.children when entry.obj == new_dev.idx)[0]
                    prev_node.remove_child(del_c)
                cat_list = []
                for new_cat in new_dev.categories
                    cat_entry = $scope.tc_categories.new_node({obj:new_dev.idx, _node_type:"d", selected:new_dev.idx in $scope.cur_sel})
                    $scope.t_cat_lut[new_cat].add_child(cat_entry)
                    cat_list.push(cat_entry)
                if cat_list.length > 1
                    for cat_entry in cat_list
                        cat_entry.linklist = cat_list
            for cur_tc in [$scope.tc_devices, $scope.tc_fqdns, $scope.tc_categories]
                cur_tc.prune(
                    (entry) ->
                        return entry._node_type == "d"
                )
                cur_tc.recalc()
                cur_tc.show_selected()
        $scope.rest_data_set = () ->
            # clear root nodes
            $scope.tc_devices.clear_root_nodes()
            $scope.tc_fqdns.clear_root_nodes()
            $scope.tc_categories.clear_root_nodes()
            # build FQDNs tree
            $scope.fqdn_lut = {}
            # tree FQDN lut
            $scope.t_fqdn_lut = {}
            for entry in $scope.rest_data["domain_tree_node"]
                $scope.fqdn_lut[entry.idx] = entry
                t_entry = $scope.tc_fqdns.new_node({folder : true, obj:entry.idx, _node_type : "f", expand:entry.depth == 0})
                $scope.t_fqdn_lut[entry.idx] = t_entry
                if entry.parent
                    $scope.t_fqdn_lut[entry.parent].add_child(t_entry)
                else
                    $scope.tc_fqdns.add_root_node(t_entry)
            # build category tree
            $scope.cat_lut = {}
            # tree category lut
            $scope.t_cat_lut = {}
            for entry in $scope.rest_data["category"]
                $scope.cat_lut[entry.idx] = entry
                t_entry = $scope.tc_categories.new_node({folder : true, obj:entry.idx, _node_type : "c", expand:entry.depth == 0})
                $scope.t_cat_lut[entry.idx] = t_entry
                if entry.parent
                    $scope.t_cat_lut[entry.parent].add_child(t_entry)
                else
                    $scope.tc_categories.add_root_node(t_entry)
            # build devices tree
            $scope.dev_lut = {}
            cur_dg = undefined
            dsel_list = (entry.idx for entry in $scope.rest_data["device_sel"] when entry.sel_type == "d")
            $scope.cur_sel = dsel_list
            # we dont need the group selection
            # gsel_list = (entry.idx for entry in $scope.rest_data["device_sel"] when entry.sel_type == "g")
            for entry in $scope.rest_data["device_tree"]
                $scope.dev_lut[entry.idx] = entry
                # copy selection state to device selection (the selection state of the meta devices is keeped in sync with the selection states of the devicegroups )
                t_entry = $scope.tc_devices.new_node({obj:entry.idx, folder:entry.is_meta_device, _node_type:"d", selected:entry.idx in dsel_list})
                $scope.t_fqdn_lut[entry.domain_tree_node].add_child($scope.tc_fqdns.new_node({obj:entry.idx, _node_type:"d", selected:entry.idx in dsel_list}))
                if entry.categories
                    cat_list = []
                    for t_cat in entry.categories
                        cat_entry = $scope.tc_categories.new_node({obj:entry.idx, _node_type:"d", selected:entry.idx in dsel_list})
                        cat_list.push(cat_entry)
                        $scope.t_cat_lut[t_cat].add_child(cat_entry)
                    if cat_list.length > 1
                        for cat_entry in cat_list
                            cat_entry.linklist = cat_list
                if entry.is_meta_device
                    cur_dg = t_entry
                    $scope.tc_devices.add_root_node(cur_dg)
                else
                    cur_dg.add_child(t_entry)
            for cur_tc in [$scope.tc_devices, $scope.tc_fqdns, $scope.tc_categories]
                cur_tc.prune(
                    (entry) ->
                        return entry._node_type == "d"
                )
                cur_tc.recalc()
                cur_tc.show_selected()
            $scope.is_loading = false
            $scope.call_devsel_func()
        msgbus.receive("devselreceiver", $scope, (name, args) ->
            # args is an optional sender name to find errors
            # console.log "register", args
            $scope.devsel_receiver++
        )
]).service("icswLayoutSidebarTreeService", () ->
    class sidebar_tree extends tree_config
        constructor: (@scope, args) ->
            super(args)
        handle_click: (entry, event) =>
            if entry._node_type == "d"
                dev = @scope.dev_lut[entry.obj]
                if dev.device_type_identifier != "MDX"
                    # create modal or use main view
                    if @scope.index_view
                        # replace index
                        @scope.DeviceOverviewService.NewSingleSelection(dev)
                    else
                        # modal
                        @scope.DeviceOverviewService.NewOverview(event, dev)
        get_name: (t_entry) ->
            entry = @get_dev_entry(t_entry)
            if t_entry._node_type == "f"
                if entry.parent
                    return "#{entry.name} (*.#{entry.full_name})"
                else
                    return "[TLN]"
            else if t_entry._node_type == "c"
                return if entry.depth then entry.name else "[TOP]"
            else
                info_f = []
                if entry.is_meta_device
                    d_name = entry.full_name.slice(8)
                else
                    d_name = entry.full_name
                    info_f.push(entry.device_type_identifier)
                if entry.comment
                    info_f.push(entry.comment)
                if info_f.length
                    d_name = "#{d_name} (" + info_f.join(", ") + ")"
                return d_name
        get_icon_class: (t_entry) =>
            if t_entry._node_type == "d"
                entry = @get_dev_entry(t_entry)
                if entry.is_meta_device
                    if entry.has_active_rrds
                        return "fa fa-line-chart"
                    else
                        return "dynatree-icon"
                else
                    if entry.has_active_rrds
                        return "fa fa-line-chart"
                    else
                        return ""
            else
                return "dynatree-icon"
        get_dev_entry: (t_entry) =>
            if t_entry._node_type == "f"
                return @scope.fqdn_lut[t_entry.obj]
            else if t_entry._node_type == "c"
                return @scope.cat_lut[t_entry.obj]
            else
                return @scope.dev_lut[t_entry.obj]
        selection_changed: () =>
            @scope.selection_changed()
).controller("icswSidebarSeparatorCtrl", ["$scope", "$window", "ICSW_URLS", "icswCallAjaxService", "icswParseXMLResponseService",
    ($scope, $window, ICSW_URLS, icswCallAjaxService, icswParseXMLResponseService) ->
        # init display of sidebar
        $scope.is_authenticated = $window.IS_AUTHENTICATED
        # 2 ... fully open
        $scope.sidebar_state = 2
        if $scope.is_authenticated
            if "sidebar_state" of $window.USER_VARS
                $scope.sidebar_state = parseInt($window.USER_VARS["sidebar_state"])
        else
            # closed sidebar when on login page
            $scope.sidebar_state = 0
        $scope.set_sidebar = () ->
            max_width = 350
            if $scope.sidebar_state == 2
                width = max_width
            else if $scope.sidebar_state == 1
                width = max_width * 0.6
            else
                width = 0
            # console.log $scope.sidebar_state, width, max_width - width
            $("div#icsw-wrapper").css("padding-left", width)
            $("div#icsw-sidebar-sep").css("left", width)
            $("div#icsw-sidebar-wrapper").css("width", width).css("left", width).css("margin-left", -width)
        $scope.set_sidebar()
        $scope.sep_click = () ->
            $scope.sidebar_state--
            if $scope.sidebar_state < 0
                $scope.sidebar_state = 2
            $scope.set_sidebar()
            icswCallAjaxService
                url: ICSW_URLS.USER_SET_USER_VAR
                data:
                    key: "sidebar_state"
                    value : $scope.sidebar_state
                    type: "int"
            return false
]).directive("icswLayoutSidebar", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.layout.sidebar")
    }
])
