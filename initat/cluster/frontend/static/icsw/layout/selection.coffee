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

angular.module(
    "icsw.layout.selection",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap",
        "init.csw.filters", "restangular", "noVNC", "ui.select", "icsw.tools",
        "icsw.device.info", "icsw.tools.tree", "icsw.user",
    ]
).service("icswDeviceTree", ["icswTools", (icswTools) ->
    class icswDeviceTree
        constructor: (full_list, cat_list, group_list) ->
            @all_list = []
            @enabled_list = []
            @cat_list = cat_list
            @group_list = group_list
            @disabled_list = []
            @enabled_lut = {}
            @disabled_lut = {}
            _enabled = []
            _disabled = []
            _disabled_groups = []
            for _entry in full_list
                @all_list.push(_entry)
                if not _entry.is_meta_device and _entry.device_group in _disabled_groups
                    @disabled_list.push(_entry)
                else if _entry.enabled
                    @enabled_list.push(_entry)
                else
                    if _entry.is_meta_device
                        _disabled_groups.push(_entry.device_group)
                    @disabled_list.push(_entry)
            @enabled_lut = icswTools.build_lut(@enabled_list)
            @disabled_lut = icswTools.build_lut(@disabled_list)
            @all_lut = icswTools.build_lut(@all_list)
            @group_lut = icswTools.build_lut(@group_list)
            @cat_lut = icswTools.build_lut(@cat_list)
            # console.log @enabled_list.length, @disabled_list.length, @all_list.length
            @link()
        link: () =>
            for group in @group_list
                group.devices = []
            for cat in @cat_list
                cat.devices = []
            for entry in @all_list
                @group_lut[entry.device_group].devices.push(entry.idx)
                for cat in entry.categories
                    @cat_lut[cat].devices.push(entry.idx)
            # create helper structures
            # console.log "link"
        get_meta_device: (dev) =>
            return @all_lut[@group_lut[dev.device_group].device]
        get_group: (dev) =>
            return @group_lut[dev.device_group]
        get_category: (cat) =>
            return @cat_lut[cat]
        get_num_devices: (group) =>
            # return all enabled devices in group
            return (entry for entry in @enabled_list when entry.device_group == group.idx).length - 1
]).service("icswDeviceTreeService", ["$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall", "icswTools", "icswDeviceTree", "$rootScope", ($q, Restangular, ICSW_URLS, $window, icswCachingCall, icswTools, icswDeviceTree, $rootScope) ->
    rest_map = [
        [
            ICSW_URLS.REST_DEVICE_TREE_LIST
            {
                "ignore_cdg" : false
                "tree_mode" : true
                "all_devices" : true
                "with_categories" : true
                "ignore_disabled": true
            }
        ]
        [
            ICSW_URLS.REST_CATEGORY_LIST
            {}
        ]
        [
            ICSW_URLS.REST_DEVICE_GROUP_LIST
            {}
        ]
    ]
    _fetch_dict = {}
    _result = undefined
    # load called
    load_called = false
    load_data = (client) ->
        load_called = true
        _wait_list = (icswCachingCall.fetch(client, _entry[0], _entry[1], []) for _entry in rest_map)
        _defer = $q.defer()
        $q.all(_wait_list).then((data) ->
            _result = new icswDeviceTree(data[0], data[1], data[2])
            _defer.resolve(_result)
            for client of _fetch_dict
                # resolve clients
                _fetch_dict[client].resolve(_result)
            $rootScope.$emit("icsw.tree.loaded", _result)
            # reset fetch_dict
            _fetch_dict = {}
        )
        return _defer
    fetch_data = (client) ->
        if client not of _fetch_dict
            # register client
            _defer = $q.defer()
            _fetch_dict[client] = _defer
        if _result
            # resolve immediately
            _fetch_dict[client].resolve(_result)
        return _fetch_dict[client]
    return {
        "load": (client) ->
            # loads from server
            return load_data(client).promise
        "fetch": (client) ->
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise
        "current": () ->
            return _result
    }
]).service("icswSelectionGetDeviceService", ["icswDeviceTreeService", "$q", (icswDeviceTreeService, $q) ->
    id = Math.random()
    return (dev_pk) ->
        defer = $q.defer()
        icswDeviceTreeService.fetch(id).then((new_data) ->
            if dev_pk of new_data.all_lut
                defer.resolve(new_data.all_lut[dev_pk])
            else
                defer.resolve(undefined)
        )
        return defer.promise
]).service("icswSelectionDeviceExists", ["icswDeviceTreeService", "$q", (icswDeviceTreeService, $q) ->
    id = Math.random()
    return (dev_pk) ->
        defer = $q.defer()
        icswDeviceTreeService.fetch(id).then((new_data) ->
            defer.resolve(dev_pk of new_data.all_lut)
        )
        return defer.promise
]).service("icswActiveSelectionService", ["$q", "Restangular", "msgbus", "$rootScope", "ICSW_URLS", "icswSelection",  ($q, Restangular, msgbus, $rootScope, ICSW_URLS, icswSelection) ->
    # used by menu.coffee (menu_base)
    _receivers = 0
    cur_selection = new icswSelection([], [], [], [])
    msgbus.receive("devselreceiver", $rootScope, (name, args) ->
        # args is an optional sender name to find errors
        _receivers += 1
        console.log "register dsr"
        $rootScope.$emit("icsw.dsr.registered")
        send_selection()
    )
    set_selection = (new_sel) ->
        # cur_selection.sync(new_sel)
        send_selection()
    send_selection = () ->
        msgbus.emit("devicelist", cur_selection.get_devsel_list())
    return {
        "num_receivers": () ->
            return _receivers
        "get_selection": () ->
            return cur_selection
        "set_selection": (new_sel) ->
            set_selection(new_sel)
    }
]).service("icswSelection", ["icswDeviceTreeService", "$q", "icswSimpleAjaxCall", "ICSW_URLS", "$rootScope", (icswDeviceTreeService, $q, icswSimpleAjaxCall, ICSW_URLS, $rootScope) ->
    class Selection
        constructor: (@cat_sel, @devg_sel, @dev_sel, @tot_dev_sel, @db_idx=0) ->
            @tree = undefined
            $rootScope.$on("icsw.tree.loaded", (event, tree) =>
                @tree = tree
                console.log "tree set", @tree
            )
        update: (@cat_sel, @devg_sel, @dev_sel, @tot_dev_sel) ->
        any_selected: () ->
            return if @cat_sel.length + @devg_sel.length + @dev_sel.length + @tot_dev_sel.length then true else false
        any_lazy_selected: () ->
            return if @cat_sel.length + @devg_sel.length then true else false
        resolve_lazy_selection: () ->
            # categories
            for _cat in @cat_sel
                for _cs in @tree.cat_lut[_cat].devices
                    @tot_dev_sel.push(_cs)
            @cat_sel = []
            # groups
            for _group in @devg_sel
                for _gs in @tree.group_lut[_group].devices
                    @dev_sel.push(_gs)
                    @tot_dev_sel.push(_gs)
            @devg_sel = []
            @tot_dev_sel = _.uniq(@tot_dev_sel)
            @dev_sel = _.uniq(@dev_sel)
        resolve_dev_name: (dev_idx) =>
            _dev = @tree.all_lut[dev_idx]
            if _dev.is_meta_device
                return "[M] " + _dev.full_name.substring(8)
            else
                return _dev.full_name
        resolve_devices: () =>
            if @dev_sel.length
                _list = ((@resolve_dev_name(_ds) for _ds in @dev_sel))
                _list.sort()
                return _list.join(", ")
            else
                return "---"
        resolve_total_devices: () =>
            if @tot_dev_sel.length
                _list = ((@resolve_dev_name(_ds) for _ds in @tot_dev_sel))
                _list.sort()
                return _list.join(", ")
            else
                return "---"
        resolve_device_groups: () =>
            if @devg_sel.length
                _list = ((@tree.group_lut[_dg].name.substring(8) for _dg in @devg_sel))
                _list.sort()
                return _list.join(", ")
            else
                return "---"
        resolve_categories: () ->
            if @cat_sel.length
                _list = ((@tree.cat_lut[_cs].full_name for _cs in @cat_sel))
                _list.sort()
                return _list.join(", ")
            else
                return "---"
        get_devsel_list: () =>
            # all device pks
            dev_pk_list = @tot_dev_sel
            # all non-meta device pks
            dev_pk_nmd_list = []
            # all device_group pks
            devg_pk_list = []
            # all meta device pks
            dev_pk_md_list = []
            for _pk in @tot_dev_sel
                _dev = @tree.all_lut[_pk]
                if _dev
                    if _dev.is_meta_device
                        devg_pk_list.push(_dev.device_group)
                        dev_pk_md_list.push(_pk)
                    else
                        dev_pk_nmd_list.push(_pk)
                else
                    console.log "device with pk #{_pk} is not resolvable"
            return [dev_pk_list, dev_pk_nmd_list, devg_pk_list, dev_pk_md_list]
        category_selected: (cat_idx) ->
            return cat_idx in @cat_sel
        device_group_selected: (devg_idx) ->
            return devg_idx in @devg_sel
        device_selected: (dev_idx) ->
            if dev_idx in @dev_sel or dev_idx in @tot_dev_sel
                return true
            else
                return false
        store_as_current: () ->
            icswSimpleAjaxCall(
                url     : ICSW_URLS.DEVICE_SET_SELECTION
                data    : {
                    "angular_sel" : angular.toJson(@tot_dev_sel)
                }
            ).then(
                (xml) ->
            )
        select_parent: () ->
            defer = $q.defer()
            icswSimpleAjaxCall(
                "url": ICSW_URLS.DEVICE_SELECT_PARENTS
                "data": {
                    "angular_sel" : angular.toJson(@tot_dev_sel)
                }
                dataType: "json"
            ).then(
                (data) =>
                    @tot_dev_sel = data["new_selection"]
                    defer.resolve(data)
            )
            return defer.promise
]).service("icswSavedSelectionService", ["Restangular", "$q", "ICSW_URLS", "icswUserService", (Restangular, $q, ICSW_URLS, icswUserService) ->
    enrich_selection = (entry) ->
        _created = moment(entry.date)
        info = [entry.name]
        entry.changed = false
        if entry.devices.length
            info.push("#{entry.devices.length} devs")
        if entry.device_groups.length
            info.push("#{entry.device_groups.length} groups")
        if entry.categories.length
            info.push("#{entry.categories.length} cats")
        info = info.join(", ")
        info = "#{info} (#{_created.format('YYYY-MM-DD HH:mm')})"
        entry.info = info
    sync_selection = (icsw_sel, json_sel) ->
        _changed = false
        if _.sum(json_sel.devices) != _.sum(icsw_sel.dev_sel) or json_sel.devices.length != icsw_sel.dev_sel.length
            _changed = true
            json_sel.devices = icsw_sel.dev_sel
        if _.sum(json_sel.device_groups) != _.sum(icsw_sel.devg_sel) or json_sel.device_groups.length != icsw_sel.devg_sel.length
            _changed = true
            json_sel.device_groups = icsw_sel.devg_sel
        if _.sum(json_sel.categories) != _.sum(icsw_sel.cat_sel) or json_sel.categories.length != icsw_sel.cat_sel.length
            _changed = true
            json_sel.categories = icsw_sel.cat_sel
        enrich_selection(json_sel)
        if _changed
            json_sel.changed = true
    load_selections = () ->
        defer = $q.defer()
        icswUserService.load().then(
            (user) ->
                Restangular.all(ICSW_URLS.REST_DEVICE_SELECTION_LIST.slice(1)).getList({"user": user.idx}).then(
                    (data) ->
                        (enrich_selection(entry) for entry in data)
                        defer.resolve(data)
                )
        )
        return defer.promise
    save_selection = (name, sel) ->
        defer = $q.defer()
        icswUserService.load().then((user) ->
            _sel = {
                "name": name
                "user": user.idx
                "devices": sel.dev_sel
                "categories": sel.cat_sel
                "device_groups": sel.devg_sel
            }
            # console.log "save", _sel
            Restangular.all(ICSW_URLS.REST_DEVICE_SELECTION_LIST.slice(1)).post(_sel).then(
                (data) ->
                    enrich_selection(data)
                    defer.resolve(data)
            )
        )
        return defer.promise
    return {
        "load_selections": () ->
            return load_selections()
        "save_selection": (name, sel) ->
            return save_selection(name, sel)
        "sync_selection": (icsw_sel, json_sel) ->
            sync_selection(icsw_sel, json_sel)
    }
]).controller("icswLayoutSelectionController",
[
    "$scope", "icswLayoutSelectionTreeService", "$timeout", "msgbus", "icswDeviceTreeService",
    "icswSelection", "icswActiveSelectionService", "$q", "icswSavedSelectionService", "icswToolsSimpleModalService",
    "DeviceOverviewService", "ICSW_URLS", 'icswSimpleAjaxCall', "blockUI", "$rootScope", "icswUserService",
(
    $scope, icswLayoutSelectionTreeService, $timeout, msgbus, icswDeviceTreeService
    icswSelection, icswActiveSelectionService, $q, icswSavedSelectionService, icswToolsSimpleModalService,
    DeviceOverviewService, ICSW_URLS, icswSimpleAjaxCall, blockUI, $rootScope, icswUserService,
) ->
    # search settings
    $scope.search_ok = true
    $scope.is_loading = true
    $scope.active_tab = "d"
    $scope.show_selection = false
    $scope.saved_selections = []
    $scope.devsel_receivers = 0
    $scope.selection_valid = false
    stop_listen = []
    stop_listen.push(
        $rootScope.$on("icsw.dsr.registered", (event) ->
            $scope.devsel_receivers = icswActiveSelectionService.num_receivers()
            console.log "****", $scope.devsel_receivers, $scope
        )
    )
    # for saved selections
    $scope.vars = {
        "name": "new selection"
        # JSON element from server, NOT icswSelection
        "current": {}
        "search_str": ""
    }
    console.log "new ctrl", $scope.$id
    # treeconfig for devices
    $scope.tc_devices = new icswLayoutSelectionTreeService($scope, {show_tree_expand_buttons : false, show_descendants : true})
    # treeconfig for groups
    $scope.tc_groups = new icswLayoutSelectionTreeService($scope, {show_tree_expand_buttons : false, show_descendants : true})
    # treeconfig for categories
    $scope.tc_categories = new icswLayoutSelectionTreeService($scope, {show_selection_buttons : true, show_descendants : true})
    $scope.selection_dict = {"d": 0, "g": 0, "c": 0}
    stop_listen.push(
        $rootScope.$on("icsw.user.changed", (event, new_user) ->
            console.log "new user", new_user
            if new_user and new_user.idx
                icswDeviceTreeService.load($scope.$id).then(
                    (new_tree) ->
                        $scope.got_rest_data(new_tree, icswActiveSelectionService.get_selection())
                )
        )
    )
    $scope.tree = undefined
    console.log "start"
    stop_listen.push(
        $rootScope.$on("icsw.devsel.show", (event, cur_state) ->
            console.log "show_devsel", event, cur_state, $scope
            if icswUserService.user_present()
                icswDeviceTreeService.load($scope.$id).then(
                    (new_tree) ->
                        $scope.got_rest_data(new_tree, icswActiveSelectionService.get_selection())
                )
            else
                console.log "No user user"
        )
    )
    stop_listen.push(
        $scope.$on("$destroy", (event) ->
            console.log "Destroy", stop_listen
            (stop_func() for stop_func in stop_listen)
        )
    )
    $scope.got_rest_data = (tree, selection) ->
        $scope.tc_devices.clear_root_nodes()
        $scope.tc_groups.clear_root_nodes()
        $scope.tc_categories.clear_root_nodes()
        $scope.selection = selection
        $scope.selection_valid = true
        console.log "sv"
        # build category tree
        # tree category lut
        # id -> category entry from tree (with devices)
        t_cat_lut = {}
        $scope.tree = tree
        console.log tree
        for entry in tree.cat_list
            t_entry = $scope.tc_categories.new_node(
                {
                    folder: true
                    obj: entry.idx
                    _show_select: entry.depth > 1
                    _node_type: "c"
                    expand: entry.depth == 0
                    selected: $scope.selection.category_selected(entry.idx)
                }
            )
            t_cat_lut[entry.idx] = t_entry
            if entry.parent
                t_cat_lut[entry.parent].add_child(t_entry)
            else
                $scope.tc_categories.add_root_node(t_entry)
        # build device group tree and top level of device tree
        dg_lut = {}
        for entry in tree.enabled_list
            if entry.is_meta_device
                g_entry = $scope.tc_groups.new_node(
                    {
                        obj: entry.device_group
                        folder: true
                        _node_type: "g"
                        selected: $scope.selection.device_group_selected(entry.device_group)
                    }
                )
                $scope.tc_groups.add_root_node(g_entry)
                d_entry = $scope.tc_devices.new_node(
                    {
                        obj: entry.idx
                        folder: true
                        _node_type: "d"
                        selected: $scope.selection.device_selected(entry.idx)
                    }
                )
                $scope.tc_devices.add_root_node(d_entry)
                dg_lut[entry.device_group] = d_entry
        # build devices tree
        for entry in tree.enabled_list
            if ! entry.is_meta_device
                # copy selection state to device selection (the selection state of the meta devices is keeped in sync with the selection states of the devicegroups )
                d_entry = $scope.tc_devices.new_node(
                    {
                        obj: entry.idx
                        folder: false
                        _node_type: "d"
                        selected: $scope.selection.device_selected(entry.idx)
                    }
                )
                dg_lut[entry.device_group].add_child(d_entry)
        $scope.tc_devices.prune(
            (entry) ->
                return entry._node_type == "d"
        )
        for cur_tc in [$scope.tc_devices, $scope.tc_groups, $scope.tc_categories]
            cur_tc.recalc()
            cur_tc.show_selected()
        $scope.is_loading = false
        $scope.selection_changed()
    $scope.toggle_show_selection = () ->
        $scope.show_selection = !$scope.show_selection
    $scope.activate_tab = (t_type) ->
        $scope.active_tab = t_type
        for tab_key in ["d", "g", "c"]
            $scope.tabs[tab_key] = tab_key == $scope.active_tab
    $scope.tabs = {}
    $scope.activate_tab($scope.active_tab)
    $scope.get_tc = (short) ->
        return {"d" : $scope.tc_devices, "g": $scope.tc_groups, "c" : $scope.tc_categories}[short]
    $scope.clear_selection = (tab_name) ->
        _tree = $scope.get_tc(tab_name)
        _tree.clear_selected()
        $scope.search_ok = true
        $scope.selection_changed()
    $scope.clear_search = () ->
        if $scope.cur_search_to
            $timeout.cancel($scope.cur_search_to)
        $scope.vars.search_str = ""
        $scope.search_ok = true
    $scope.update_search = () ->
        if $scope.cur_search_to
            $timeout.cancel($scope.cur_search_to)
        $scope.cur_search_to = $timeout($scope.set_search_filter, 500)
    $scope.set_search_filter = () ->
        if $scope.vars.search_str == ""
            return

        looks_like_ip_or_mac_start = (in_str) ->
            # accept "192.168." or "AB:AB:AB:
            return /^\d{1,3}\.\d{1,3}\./.test(in_str) || /^([0-9A-Fa-f]{2}[:-]){3}/.test(in_str)

        if looks_like_ip_or_mac_start($scope.vars.search_str)
            icswSimpleAjaxCall(
                url: ICSW_URLS.DEVICE_GET_MATCHING_DEVICES
                dataType: "json"
                data:
                    search_str: $scope.vars.search_str
            ).then(
                (matching_device_pks) ->
                    cur_tree = $scope.get_tc($scope.active_tab)
                    cur_tree.toggle_tree_state(undefined, -1, false)
                    num_found = 0
                    cur_tree.iter(
                        (entry) ->
                            if entry._node_type == "d"
                                _sel = $scope.tree.all_lut[entry.obj].idx in matching_device_pks
                                entry.set_selected(_sel)
                                if _sel
                                    num_found++
                    )
                    $scope.search_ok = num_found > 0
                    cur_tree.show_selected(false)
                    $scope.selection_changed()
            )

        else  # regular search
            try
                cur_re = new RegExp($scope.vars.search_str, "gi")
            catch exc
                cur_re = new RegExp("^$", "gi")
            cur_tree = $scope.get_tc($scope.active_tab)
            cur_tree.toggle_tree_state(undefined, -1, false)
            num_found = 0
            cur_tree.iter(
                (entry, cur_re) ->
                    if entry._node_type == "d"
                        _sel = if $scope.tree.all_lut[entry.obj].full_name.match(cur_re) then true else false
                        entry.set_selected(_sel)
                        if _sel
                            num_found++
                    else if entry._node_type == "g"
                        _sel = if $scope.tree.group_lut[entry.obj].full_name.match(cur_re) then true else false
                        entry.set_selected(_sel)
                        if _sel
                            num_found++
                    else if entry._node_type == "c"
                        _sel = if $scope.tree.cat_lut[entry.obj].name.match(cur_re) then true else false
                        entry.set_selected(_sel)
                        if _sel
                            num_found++
                cur_re
            )
            $scope.search_ok = if num_found > 0 then true else false
            cur_tree.show_selected(false)
            $scope.selection_changed()
    $scope.resolve_devices = (sel) ->
        return sel.resolve_devices()
    $scope.resolve_total_devices = (sel) ->
        return sel.resolve_total_devices()
    $scope.resolve_device_groups = (sel) ->
        return sel.resolve_device_groups()
    $scope.resolve_categories = (sel) ->
        return sel.resolve_categories()
    $scope.resolve_lazy_selection = () ->
        $scope.selection.resolve_lazy_selection()
        $scope.tc_groups.clear_selected()
        $scope.tc_categories.clear_selected()
        # select devices
        $scope.tc_devices.iter(
            (node, data) ->
                node.selected = node.obj in $scope.selection.tot_dev_sel
        )
        $scope.tc_devices.recalc()
        $scope.tc_groups.show_selected(false)
        $scope.tc_categories.show_selected(false)
        $scope.tc_devices.show_selected(false)
        $scope.selection_changed()
        $scope.activate_tab("d")
    $scope.selection_changed = () ->
        dev_sel_nodes = $scope.tc_devices.get_selected(
            (entry) ->
                if entry._node_type == "d" and entry.selected
                    return [entry.obj]
                else
                    return []
        )
        group_sel_nodes = $scope.tc_groups.get_selected(
            (entry) ->
                if entry._node_type == "g" and entry.selected
                    return [entry.obj]
                else
                    return []
        )
        cat_sel_nodes = $scope.tc_categories.get_selected(
            (entry) ->
                if entry._node_type == "c" and entry.selected
                    return [entry.obj]
                else
                    return []
        )
        $scope.selection_dict = {
            "d": dev_sel_nodes.length
            "g": group_sel_nodes.length
            "c": cat_sel_nodes.length
        }
        # direct selected devices
        dev_sel = []
        # total devices select
        tot_dev_sel = []
        # selected devicegroups (==lazy)
        devg_sel = []
        for _ds in dev_sel_nodes
            dev_sel.push(_ds)
            tot_dev_sel.push(_ds)
        for _gs in group_sel_nodes
            devg_sel.push(_gs)
            for _group_dev in $scope.tree.group_lut[_gs].devices
                tot_dev_sel.push(_group_dev)
        for _cs in cat_sel_nodes
            for _cat_dev in $scope.tree.get_category(_cs).devices
                tot_dev_sel.push(_cat_dev)
        $scope.selection.update(cat_sel_nodes, devg_sel, dev_sel, _.uniq(tot_dev_sel))
        if $scope.vars.current and $scope.vars.current.idx == $scope.selection.db_idx
            # current selection is in sync with a saved one
            $scope.synced = true
            icswSavedSelectionService.sync_selection($scope.selection, $scope.vars.current)
        else
            $scope.synced = false
    $scope.call_devsel_func = () ->
        $scope.selection.store_as_current()
        icswActiveSelectionService.set_selection($scope.selection)
        $scope.modal.close()
    $scope.enable_saved_selections = () ->
        if not $scope.saved_selections.length
            icswSavedSelectionService.load_selections().then((data) ->
                $scope.saved_selections = data
                $scope.selected_selection = undefined
            )
    $scope.update_selection = () ->
        $scope.vars.current.put().then((newd) -> console.log newd)
    $scope.create_selection = () ->
        _names = (sel.name for sel in $scope.saved_selections)
        if $scope.vars.name in _names
            if $scope.vars.name.match(/.* \d+/)
                _parts = $scope.vars.name.split(" ")
                _idx = parseInt(_parts.pop())
                $scope.vars.name = _parts.join(" ")
            else
                _idx = 1
            while true
                _name = $scope.vars.name + " #{_idx}"
                if _name not in _names
                    break
                else
                    _idx++
            $scope.vars.name = _name
        icswSavedSelectionService.save_selection($scope.vars.name, $scope.selection).then((new_sel) ->
            $scope.saved_selections.splice(0, 0, new_sel)
            $scope.vars.current = new_sel
        )
    $scope.use_selection = (new_sel, b) ->
        $scope.vars.current = new_sel
        console.log "use_selection"
        $scope.selection = new icswSelection(new_sel.categories, new_sel.device_groups, new_sel.devices, [], new_sel.idx)
        for cur_tc in [$scope.tc_devices, $scope.tc_groups, $scope.tc_categories]
            cur_tc.clear_selected()
        $scope.tc_devices.iter(
            (entry, bla) ->
                if entry._node_type == "d"
                    entry.set_selected($scope.selection.device_selected(entry.obj))
        )
        $scope.tc_groups.iter(
            (entry, bla) ->
                if entry._node_type == "g"
                    entry.set_selected($scope.selection.device_group_selected(entry.obj))
        )
        $scope.tc_categories.iter(
            (entry, bla) ->
                if entry._node_type == "c"
                    entry.set_selected($scope.selection.category_selected(entry.obj))
        )
        # apply new selection
        for cur_tc in [$scope.tc_devices, $scope.tc_groups, $scope.tc_categories]
            cur_tc.recalc()
            cur_tc.show_selected()
        $scope.selection_changed()
    $scope.delete_selection = () ->
        if $scope.vars.current
            icswToolsSimpleModalService("Delete Selection ?").then(() ->
                del_id = $scope.vars.current.idx
                $scope.vars.current.remove().then((del) ->
                    $scope.saved_selections = (entry for entry in $scope.saved_selections when entry.idx != del_id)
                    $scope.vars.current = undefined
                )
            )

    $scope.show_current_selection_in_overlay = () ->
        devsel_list = $scope.selection.get_devsel_list()
        selected_devices = ($scope.tree.all_lut[_pk] for _pk in devsel_list[0])
        DeviceOverviewService.NewOverview(event, selected_devices)
    $scope.select_parents = () ->
        blockUI.start()
        $scope.selection.select_parent().then(() ->
            $scope.tc_devices.iter(
                (node, data) ->
                    node.selected = node.obj in $scope.selection.tot_dev_sel
            )
            $scope.tc_devices.recalc()
            $scope.tc_groups.show_selected(false)
            $scope.tc_categories.show_selected(false)
            $scope.tc_devices.show_selected(false)
            $scope.selection_changed()
            $scope.activate_tab("d")
            blockUI.stop()
        )
]).service("icswLayoutSelectionDialogService", ["$q", "$compile", "$templateCache", "$state", "icswToolsSimpleModalService", "$rootScope", ($q, $compile, $templateCache, $state, icswToolsSimpleModalService, $rootScope) ->
    # dialog_div =
    prev_left = undefined
    prev_top = undefined
    quick_dialog = () ->
        state_name = $state.current.name
        sel_scope = $rootScope.$new()
        dialog_div = $compile($templateCache.get("icsw.layout.selection.modify"))(sel_scope)
        console.log "SelectionDialog", state_name
        # signal controller
        $rootScope.$emit("icsw.devsel.show", state_name)
        BootstrapDialog.show
            message: dialog_div
            title: "Device Selection"
            draggable: true
            animate: false
            closable: true
            onshown: (ref) ->
                # hack to position to the left
                _tw = ref.getModal().width()
                _diag = ref.getModalDialog()
                if prev_left?
                    $(_diag[0]).css("left", prev_left)
                    $(_diag[0]).css("top", prev_top)
                else
                    $(_diag[0]).css("left", - (_tw - 600)/2)
                sel_scope.modal = ref
            onhidden: (ref) ->
                _diag = ref.getModalDialog()
                prev_left = $(_diag[0]).css("left")
                prev_top = $(_diag[0]).css("top")
                sel_scope.$destroy()
            buttons: [
                {
                    icon: "glyphicon glyphicon-ok"
                    cssClass: "btn-warning"
                    label: "close"
                    action: (ref) ->
                        ref.close()
                }
            ]
    return {
        "quick_dialog": quick_dialog
    }
]).service("icswLayoutSelectionTreeService", ["DeviceOverviewService", "icswTreeConfig", "icswDeviceTreeService", (DeviceOverviewService, icswTreeConfig, icswDeviceTreeService) ->
    class selection_tree extends icswTreeConfig
        constructor: (@scope, args) ->
            super(args)
            @current = undefined
        ensure_current: () =>
            if not @current
                @current = icswDeviceTreeService.current()
        handle_click: (entry, event) =>
            @ensure_current()
            if entry._node_type == "d"
                dev = @current.all_lut[entry.obj]
                DeviceOverviewService.NewOverview(event, [dev])
            else
                entry.set_selected(not entry.selected)
            # need $apply() here, $digest is not enough
            @scope.$apply()
        get_name: (t_entry) =>
            @ensure_current()
            entry = @get_dev_entry(t_entry)
            if t_entry._node_type == "f"
                if entry.parent
                    return "#{entry.name} (*.#{entry.full_name})"
                else
                    return "[TLN]"
            else if t_entry._node_type == "c"
                if entry.depth
                    _res = entry.name
                    cat = @current.cat_lut[t_entry.obj]
                    if cat.devices.length
                        _res = "#{_res} (#{cat.devices.length} devices)"
                else
                    _res = "[TOP]"
                return _res
            else if t_entry._node_type == "g"
                _res = entry.name
                group = @current.group_lut[t_entry.obj]
                if group.devices.length
                    _res = "#{_res} (#{group.devices.length} devices)"
                return _res
            else
                info_f = []
                if entry.is_meta_device
                    d_name = entry.full_name.slice(8)
                else
                    d_name = entry.full_name
                if entry.comment
                    info_f.push(entry.comment)
                if info_f.length
                    d_name = "#{d_name} (" + info_f.join(", ") + ")"
                return d_name
        get_icon_class: (t_entry) =>
            if t_entry._node_type == "d"
                entry = @get_dev_entry(t_entry)
                if entry.is_meta_device
                    return "dynatree-icon"
                else
                    return ""
            else
                return "dynatree-icon"
        get_dev_entry: (t_entry) =>
            if t_entry._node_type == "g"
                return @scope.tree.group_lut[t_entry.obj]
            else if t_entry._node_type == "c"
                return @scope.tree.cat_lut[t_entry.obj]
            else
                return @scope.tree.all_lut[t_entry.obj]
        selection_changed: () =>
            @scope.selection_changed()
            @scope.$digest()
])
