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
        "icsw.backend.devicetree",
    ]
).service("icswActiveSelectionService",
[
    "$q", "Restangular", "$rootScope", "ICSW_URLS", "icswSelection",  "ICSW_SIGNALS",
(
    $q, Restangular, $rootScope, ICSW_URLS, icswSelection, ICSW_SIGNALS
) ->
    # used by menu.coffee (menu_base)
    _receivers = 0
    # for testing
    cur_selection = new icswSelection([], [], [666, 3, 5, 16, 21], [3, 5, 16, 21, 666])
    # cur_selection = new icswSelection([], [], [3, 5], [3, 5])
    # cur_selection = new icswSelection([], [], [3], [3])
    # windowstest
    # cur_selection = new icswSelection([], [], [13], [13])
    # cur_selection = new icswSelection([], [], [16], [16]) # only firewall
    # cur_selection = new icswSelection([], [], [], [])

    $rootScope.$on(ICSW_SIGNALS("ICSW_DEVICE_TREE_LOADED"), (event) ->
        # tree loaded, re-emit selection
        send_selection()
    )

    register_receiver = () ->
        _receivers += 1
        # console.log "registered receiver"
        $rootScope.$emit(ICSW_SIGNALS("ICSW_DSR_REGISTERED"))

    sync_selection = (new_sel) ->
        cur_selection.update(new_sel.categories, new_sel.device_groups, new_sel.devices, [])
        cur_selection.sync_with_db(new_sel)

    unsync_selection = () ->
        cur_selection.sync_with_db(undefined)

    send_selection = () ->
        # console.log "emit current device selection"
        $rootScope.$emit(ICSW_SIGNALS("ICSW_OVERVIEW_EMIT_SELECTION"))

    return {
        "num_receivers": () ->
            return _receivers
        current: () ->
            return cur_selection
        "get_selection": () ->
            return cur_selection
        "sync_selection": (new_sel) ->
            # synchronizes cur_selection with new_sel
            sync_selection(new_sel)
        "unsync_selection": () ->
            # remove synchronization with saved (==DB-selection)
            unsync_selection()
        "send_selection": () ->
            send_selection()

        register_receiver: () ->
            # register devsel receiver
            register_receiver()
    }
]).service("icswSelection",
[
    "icswDeviceTreeService", "$q", "icswSimpleAjaxCall", "ICSW_URLS", "$rootScope",
    "Restangular", "icswSavedSelectionService", "ICSW_SIGNALS",
(
    icswDeviceTreeService, $q, icswSimpleAjaxCall, ICSW_URLS, $rootScope,
    Restangular, icswSavedSelectionService, ICSW_SIGNALS
) ->

    class icswSelection
        # only instantiated once (for now), also handles saved selections
        constructor: (@cat_sel, @devg_sel, @dev_sel, @tot_dev_sel) ->
            $rootScope.$on(ICSW_SIGNALS("ICSW_DEVICE_TREE_LOADED"), (event, tree) =>
                @tree = tree
                # console.log "tree set for icswSelection", @tree
            )
            @tree = undefined
            @sync_with_db(undefined)

        update: (@cat_sel, @devg_sel, @dev_sel, @tot_dev_sel) ->

        sync_with_db: (@db_obj=undefined) =>
            if @db_obj
                @db_idx = @db_obj.idx
                @cat_sel_db = angular.copy(@cat_sel)
                @devg_sel_db = angular.copy(@devg_sel)
                @dev_sel_db = angular.copy(@dev_sel)
                # selection has changed
                @changed = false
                @compare_with_db()
            else
                # unsync
                @db_idx = 0
                delete @cat_sel_db
                delete @devg_sel_db
                delete @dev_sel_db
                @db_obj = {
                    "info": ""
                    "name": "New selection"
                }
                # is disabled on the drop-down selection list
                # selection has changed, dummy flag, should never be used
                @changed = true

        compare_with_db: () =>
            @changed = false
            # compare current selection with _db instances
            for _entry in ["cat_sel", "devg_sel", "dev_sel"]
                _db_entry = "#{_entry}_db"
                if _.sum(@[_entry]) != _.sum(@[_db_entry]) or @[_entry].length != @[_db_entry].length
                    @changed = true
            @create_info()

        create_info: () =>
            icswSavedSelectionService.enrich_selection(@db_obj)
            if @changed
                @db_obj.info = "(*) #{@db_obj.info}"

        toggle_selection: (obj) =>
            # toggle selection of object
            _selected = obj.idx in @dev_sel
            if _selected
                @remove_selection(obj)
            else
                @add_selection(obj)

        add_selection: (obj) =>
            # add selection
            if obj.idx not in @dev_sel
                @dev_sel.push(obj.idx)
                @tot_dev_sel.push(obj.idx)

        remove_selection: (obj) =>
            # remove selection
            if obj.idx in @dev_sel
                _.pull(@dev_sel, obj.idx)
                _.pull(@tot_dev_sel, obj.idx)

        device_is_selected: (obj) =>
            # only works for devices
            return obj.idx in @dev_sel

        deselect_all_devices: (obj) =>
            @dev_sel = []
            @tot_dev_sel = []

        selection_saved: () =>
            # database object saved
            # console.log "resync", @db_obj
            @sync_with_db(@db_obj)

        is_synced: () =>
            return if @db_idx then true else false

        any_selected: () ->
            return if @cat_sel.length + @devg_sel.length + @dev_sel.length + @tot_dev_sel.length then true else false

        any_lazy_selected: () ->
            return if @cat_sel.length + @devg_sel.length then true else false

        resolve_lazy_selection: () ->
            # categories
            for _cat in @cat_sel
                for _cs in @tree.cat_tree.lut[_cat].reference_dict.device
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
                _list = (@tree.group_lut[_dg].name.substring(8) for _dg in @devg_sel)
                _list.sort()
                return _list.join(", ")
            else
                return "---"

        resolve_categories: () ->
            if @cat_sel.length
                _list = ((@tree.cat_tree.lut[_cs].full_name for _cs in @cat_sel))
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
        save_db_obj: () =>
            if @db_obj
                # console.log @db_obj
                # console.log @dev_sel
                @db_obj.categories = (entry for entry in @cat_sel)
                @db_obj.device_groups = (entry for entry in @devg_sel)
                @db_obj.devices = (entry for entry in @dev_sel)
                # console.log @db_obj
                @db_obj.put().then(
                    (old_obj) =>
                        @selection_saved()
                )
        create_saved_selection: (user) =>
            defer = $q.defer()
            _sel = {
                "name": @db_obj.name
                "user": user.idx
                "devices": @dev_sel
                "categories": @cat_sel
                "device_groups": @devg_sel
            }
            # console.log "save", _sel
            Restangular.all(ICSW_URLS.REST_DEVICE_SELECTION_LIST.slice(1)).post(_sel).then(
                (data) =>
                    # enrich_selection(data)
                    @sync_with_db(data)
                    defer.resolve(data)
            )
            return defer.promise

        delete_saved_selection: () =>
            defer = $q.defer()
            @db_obj.remove().then(
                () =>
                    @sync_with_db(undefined)
                    defer.resolve(true)
            )
            return defer.promise

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

]).service("icswSavedSelectionService",
[
    "Restangular", "$q", "ICSW_URLS", "icswUserService",
(
    Restangular, $q, ICSW_URLS, icswUserService
) ->
    enrich_selection = (entry) ->
        _created = moment(entry.date)
        info = [entry.name]
        if entry.devices.length
            info.push("#{entry.devices.length} devs")
        if entry.device_groups.length
            info.push("#{entry.device_groups.length} groups")
        if entry.categories.length
            info.push("#{entry.categories.length} cats")
        info = info.join(", ")
        info = "#{info} (#{_created.format('YYYY-MM-DD HH:mm')})"
        entry.info = info

    _list = []

    load_selections = () ->
        defer = $q.defer()
        icswUserService.load().then(
            (user) ->
                Restangular.all(ICSW_URLS.REST_DEVICE_SELECTION_LIST.slice(1)).getList(
                    {
                        user: user.idx
                    }
                ).then(
                    (data) ->
                        (enrich_selection(entry) for entry in data)
                        _list = data
                        defer.resolve(_list)
                )
        )
        return defer.promise

    save_selection = (user, sel) ->
        defer = $q.defer()
        sel.create_saved_selection(user).then(
            (data) ->
                enrich_selection(data)
                _list.push(data)
                defer.resolve(data)
        )
        return defer.promise

    delete_selection = (sel) ->
        defer = $q.defer()
        del_id = sel.db_idx
        sel.delete_saved_selection().then(
            (done) ->
                console.log del_id, (entry.idx for entry in _list)
                _.remove(_list, (entry) -> return entry.idx == del_id)
                defer.resolve(_list)
        )
        return defer.promise

    return {
        "load_selections": () ->
            return load_selections()
        "save_selection": (user, sel) ->
            return save_selection(user, sel)
        "delete_selection": (sel) ->
            return delete_selection(sel)
        "enrich_selection": (obj) ->
            enrich_selection(obj)
    }
]).controller("icswLayoutSelectionController",
[
    "$scope", "icswLayoutSelectionTreeService", "$timeout", "icswDeviceTreeService", "ICSW_SIGNALS",
    "icswSelection", "icswActiveSelectionService", "$q", "icswSavedSelectionService", "icswToolsSimpleModalService",
    "DeviceOverviewService", "ICSW_URLS", 'icswSimpleAjaxCall', "blockUI", "$rootScope", "icswUserService",
    "DeviceOverviewSelection", "hotkeys",
(
    $scope, icswLayoutSelectionTreeService, $timeout, icswDeviceTreeService, ICSW_SIGNALS,
    icswSelection, icswActiveSelectionService, $q, icswSavedSelectionService, icswToolsSimpleModalService,
    DeviceOverviewService, ICSW_URLS, icswSimpleAjaxCall, blockUI, $rootScope, icswUserService,
    DeviceOverviewSelection, hotkeys,
) ->
    console.log "keys"
    hotkeys.bindTo($scope).add(
        combo: "g"
        description: "Group selection"
        callback: () ->
            console.log "g pressed"
    )
    # search settings
    $scope.search_ok = true
    $scope.is_loading = true
    $scope.active_tab = "d"
    $scope.show_selection = false
    $scope.saved_selections = []
    $scope.devsel_receivers = icswActiveSelectionService.num_receivers()
    $scope.selection_valid = false
    $scope.synced = false
    # for saved selections
    $scope.vars = {
        search_str: ""
        selection_for_dropdown: undefined
    }
    # console.log "new ctrl", $scope.$id
    # notifier queue
    notifier_queue = $q.defer()
    notifier_queue.promise.then(
        (ok) ->
        (error) ->
        (info) ->
            console.log "info"
    )
    # treeconfig for devices
    $scope.tc_devices = new icswLayoutSelectionTreeService($scope, notifier_queue, {show_tree_expand_buttons: false, show_descendants: true})
    # treeconfig for groups
    $scope.tc_groups = new icswLayoutSelectionTreeService($scope, notifier_queue, {show_tree_expand_buttons: false, show_descendants: true})
    # treeconfig for categories
    $scope.tc_categories = new icswLayoutSelectionTreeService($scope, notifier_queue, {show_selection_buttons: true, show_descendants: true})
    $scope.selection_dict = {
        d: 0
        g: 0
        c: 0
    }
    $scope.tree = undefined
    # console.log "start"
    # list of receivers
    stop_listen = []
    stop_listen.push(
        $rootScope.$on(ICSW_SIGNALS("ICSW_DSR_REGISTERED"), (event) ->
            $scope.devsel_receivers = icswActiveSelectionService.num_receivers()
            console.log "****", $scope.devsel_receivers, $scope
        )
    )
    stop_listen.push(
        $rootScope.$on(ICSW_SIGNALS("ICSW_USER_CHANGED"), (event, new_user) ->
            console.log "new user", new_user
            if new_user and new_user.idx
                icswDeviceTreeService.load($scope.$id).then(
                    (new_tree) ->
                        $scope.got_rest_data(new_tree, icswActiveSelectionService.get_selection())
                )
        )
    )
    stop_listen.push(
        $rootScope.$on(ICSW_SIGNALS("ICSW_SELECTOR_SHOW"), (event, cur_state) ->
            # call when the requester is shown
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
            notifier_queue.reject("exit")
            (stop_func() for stop_func in stop_listen)
        )
    )
    # get current devsel_receivers
    $scope.got_rest_data = (tree, selection) ->
        $scope.tc_devices.clear_root_nodes()
        $scope.tc_groups.clear_root_nodes()
        $scope.tc_categories.clear_root_nodes()
        $scope.selection = selection
        $scope.selection_valid = true
        console.log "got_rest_data (selection)"
        # build category tree
        # tree category lut
        # id -> category entry from tree (with devices)
        t_cat_lut = {}
        # store tree
        $scope.tree = tree
        console.log tree
        for entry in tree.cat_tree.list
            t_entry = $scope.tc_categories.create_node(
                {
                    folder: true
                    obj: entry.idx
                    show_select: entry.depth > 1
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
                g_entry = $scope.tc_groups.create_node(
                    {
                        obj: entry.device_group
                        folder: true
                        _node_type: "g"
                        selected: $scope.selection.device_group_selected(entry.device_group)
                    }
                )
                $scope.tc_groups.add_root_node(g_entry)
                d_entry = $scope.tc_devices.create_node(
                    {
                        obj: entry.idx
                        folder: true
                        selected: $scope.selection.device_selected(entry.idx)
                        _node_type: "d"
                    }
                )
                $scope.tc_devices.add_root_node(d_entry)
                dg_lut[entry.device_group] = d_entry
        # build devices tree
        for entry in tree.enabled_list
            if ! entry.is_meta_device
                # copy selection state to device selection (the selection state of the meta devices is keeped in sync with the selection states of the devicegroups )
                d_entry = $scope.tc_devices.create_node(
                    {
                        obj: entry.idx
                        folder: false
                        selected: $scope.selection.device_selected(entry.idx)
                        _node_type: "d"
                    }
                )
                dg_lut[entry.device_group].add_child(d_entry)
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
            _with_slash = false
            try
                cur_re = new RegExp($scope.vars.search_str, "gi")
                if $scope.vars.search_str.match(/\//)
                    _with_slash = true
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
                        # console.log $scope.tree.cat_tree.lut[entry.obj]
                        if _with_slash
                            _sel = if $scope.tree.cat_tree.lut[entry.obj].full_name.match(cur_re) then true else false
                        else
                            _sel = if $scope.tree.cat_tree.lut[entry.obj].name.match(cur_re) then true else false
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
            for _cat_dev in $scope.tree.get_category(_cs).reference_dict.device
                tot_dev_sel.push(_cat_dev)
        $scope.selection.update(cat_sel_nodes, devg_sel, dev_sel, _.uniq(tot_dev_sel))
        if $scope.selection.is_synced()
            # current selection is in sync with a saved one
            $scope.synced = true
            console.log "sync"
            $scope.selection.compare_with_db()
        else
            console.log "unsync"
            $scope.synced = false

    $scope.call_devsel_func = () ->
        icswActiveSelectionService.send_selection($scope.selection)
        $scope.modal.close()

    $scope.enable_saved_selections = () ->
        if not $scope.saved_selections.length
            icswSavedSelectionService.load_selections().then(
                (data) ->
                    $scope.saved_selections = data
            )

    $scope.update_selection = () ->
        $scope.selection.save_db_obj()

    $scope.create_selection = () ->
        _names = (sel.name for sel in $scope.saved_selections)
        # make name unique
        if $scope.selection.name in _names
            if $scope.selection.name.match(/.* \d+$/)
                _parts = $scope.selection.name.split(" ")
                _idx = parseInt(_parts.pop())
                $scope.selection.name = _parts.join(" ")
            else
                _idx = 1
            while true
                _name = $scope.selection.name + " #{_idx}"
                if _name not in _names
                    break
                else
                    _idx++
            $scope.selection.name = _name
        icswSavedSelectionService.save_selection(
            icswUserService.get(),
            $scope.selection
        ).then(
            (new_sel) ->
                $scope.vars.selection_for_dropdown = $scope.selection.db_obj
                $scope.synced = true
        )

    $scope.unselect = () ->
        console.log "unselect"
        $scope.synced = false
        icswActiveSelectionService.unsync_selection()
        $scope.vars.selection_for_dropdown = undefined

    $scope.use_selection = (new_sel, b) ->
        console.log "use_selection"
        $scope.vars.selection_for_dropdown = new_sel
        icswActiveSelectionService.sync_selection(new_sel)
        (cur_tc.clear_selected() for cur_tc in [$scope.tc_devices, $scope.tc_groups, $scope.tc_categories])
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
        if $scope.synced
            icswToolsSimpleModalService("Delete Selection #{$scope.selection.name} ?").then(
                () ->
                    icswSavedSelectionService.delete_selection($scope.selection).then(
                        (new_list) ->
                            $scope.vars.selection_for_dropdown = undefined
                            $scope.synced = false
                            icswActiveSelectionService.unsync_selection()
                            $scope.saved_selections = new_list
                    )
            )

    $scope.show_current_selection_in_overlay = () ->
        devsel_list = $scope.selection.get_devsel_list()
        selected_devices = ($scope.tree.all_lut[_pk] for _pk in devsel_list[0])
        DeviceOverviewSelection.set_selection(selected_devices)
        DeviceOverviewService(event, selected_devices)
        console.log "show_current_selection"

    $scope.select_parents = () ->
        blockUI.start("Selecting parents...")
        $scope.selection.select_parent().then(
            () ->
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
]).service("icswLayoutSelectionDialogService",
[
    "$q", "$compile", "$templateCache", "$state", "icswToolsSimpleModalService",
    "$rootScope", "ICSW_SIGNALS",
(
    $q, $compile, $templateCache, $state, icswToolsSimpleModalService,
    $rootScope, ICSW_SIGNALS
) ->
    # dialog_div =
    prev_left = undefined
    prev_top = undefined
    _active = false
    quick_dialog = () ->
        if !_active
            _active = true
            state_name = $state.current.name
            sel_scope = $rootScope.$new()
            dialog_div = $compile($templateCache.get("icsw.layout.selection.modify"))(sel_scope)
            console.log "SelectionDialog", state_name
            # signal controller
            $rootScope.$emit(ICSW_SIGNALS("ICSW_SELECTOR_SHOW"), state_name)
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
                    _active = false
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
        "quick_dialog": () ->
            return quick_dialog()
    }
]).service("icswLayoutSelectionTreeService",
[
    "DeviceOverviewService", "icswReactTreeConfig", "icswDeviceTreeService",
    "DeviceOverviewSelection",
(
    DeviceOverviewService, icswReactTreeConfig, icswDeviceTreeService,
    DeviceOverviewSelection
) ->
    class icswLayoutSelectionTree extends icswReactTreeConfig
        constructor: (@scope, @notifier, args) ->
            # args.debug_mode = true
            super(args)
            @current = undefined

        ensure_current: () =>
            if not @current
                @current = icswDeviceTreeService.current()

        handle_click: (event, entry) =>
            @ensure_current()
            if entry._node_type == "d"
                dev = @current.all_lut[entry.obj]
                DeviceOverviewSelection.set_selection([dev])
                DeviceOverviewService(event)
                @notifier.notify("go")
            else
                entry.set_selected(not entry.selected)
                @notifier.notify("go")
            # need $apply() here, $digest is not enough

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
                    cat = @current.cat_tree.lut[t_entry.obj]
                    if cat.reference_dict.device.length
                        _res = "#{_res} (#{cat.reference_dict.device.length} devices)"
                else
                    _res = "[TOP]"
                return _res
            else if t_entry._node_type == "g"
                _res = entry.name
                group = @current.group_lut[t_entry.obj]
                # ignore meta device
                if group.num_devices
                    _res = "#{_res} (#{group.num_devices} devices)"
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
                return @scope.tree.cat_tree.lut[t_entry.obj]
            else
                return @scope.tree.all_lut[t_entry.obj]
        selection_changed: () =>
            @scope.selection_changed()
            @notifier.notify("go")
])
