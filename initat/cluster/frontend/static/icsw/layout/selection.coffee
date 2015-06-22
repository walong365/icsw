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

class Selection
    constructor: (@cat_sel, @devg_sel, @dev_sel, @tot_dev_sel) ->
    any_selected: () ->
        return if @cat_sel.length + @devg_sel.length + @dev_sel.length + @tot_dev_sel.length then true else false
    any_lazy_selected: () ->
        return if @cat_sel.length + @devg_sel.length then true else false
    resolve_lazy_selection: (dev_lut, devg_lut, cat_lut) ->
        # categories
        for _cat in @cat_sel
            for _cs in cat_lut[_cat].devices
                @tot_dev_sel.push(_cs)
        @cat_sel = []
        # groups
        for _group in @devg_sel
            for _gs in devg_lut[dev_lut[_group].device_group].devices
                @dev_sel.push(_gs)
                @tot_dev_sel.push(_gs)
        @devg_sel = []
        @tot_dev_sel = _.uniq(@tot_dev_sel)
        @dev_sel = _.uniq(@dev_sel)
    resolve_devices: (dev_lut) ->
        if @dev_sel.length
            _list = ((dev_lut[_ds].full_name for _ds in @dev_sel))
            _list.sort()
            return _list.join(", ")
        else
            return "---"
    resolve_total_devices: (dev_lut) ->
        if @tot_dev_sel.length
            _list = ((dev_lut[_ds].full_name for _ds in @tot_dev_sel))
            _list.sort()
            return _list.join(", ")
        else
            return "---"
    resolve_device_groups: (dev_lut) ->
        if @devg_sel.length
            _list = ((dev_lut[_dg].name.substring(8) for _dg in @devg_sel))
            _list.sort()
            return _list.join(", ")
        else
            return "---"
    resolve_categories: (cat_lut) ->
        if @cat_sel.length
            _list = ((cat_lut[_cs].full_name for _cs in @cat_sel))
            _list.sort()
            return _list.join(", ")
        else
            return "---"

angular.module(
    "icsw.layout.selection",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap",
        "init.csw.filters", "restangular", "noVNC", "ui.select", "icsw.tools",
        "icsw.device.info", "icsw.layout.sidebar",
    ]
).controller("icswLayoutSelectionController", ["$scope", "icswDeviceTreeService", "icswLayoutSelectionTreeService", "$timeout", "$window", ($scope, icswDeviceTreeService, icswLayoutSelectionTreeService, $timeout, $window) ->
    # search settings
    $scope.searchstr = ""
    $scope.search_ok = true
    $scope.is_loading = true
    $scope.active_tab = "d"
    $scope.show_selection = false
    $scope.selection = new Selection([], [], [], [])
    # treeconfig for devices
    $scope.tc_devices = new icswLayoutSelectionTreeService($scope, {show_tree_expand_buttons : false, show_descendants : true})
    # treeconfig for groups
    $scope.tc_groups = new icswLayoutSelectionTreeService($scope, {show_tree_expand_buttons : false, show_descendants : true})
    # treeconfig for categories
    $scope.tc_categories = new icswLayoutSelectionTreeService($scope, {show_selection_buttons : true, show_descendants : true})
    icswDeviceTreeService.fetch($scope.$id).then((data) ->
        $scope.rest_data = {
            "device_tree": data[0]
            "category": data[2]
            "device_sel": data[3]
        }
        $scope.tc_devices.clear_root_nodes()
        $scope.tc_groups.clear_root_nodes()
        $scope.tc_categories.clear_root_nodes()
        # build category tree
        # id -> category entry
        $scope.cat_lut = {}
        # tree category lut
        # id -> category entry from tree (with devices)
        $scope.t_cat_lut = {}
        for entry in $scope.rest_data["category"]
            $scope.cat_lut[entry.idx] = entry
            t_entry = $scope.tc_categories.new_node({folder : true, obj:entry.idx, _show_select: entry.depth > 1, _node_type : "c", expand:entry.depth == 0, devices:[]})
            $scope.t_cat_lut[entry.idx] = t_entry
            if entry.parent
                $scope.t_cat_lut[entry.parent].add_child(t_entry)
            else
                $scope.tc_categories.add_root_node(t_entry)
        # build devices tree
        # device id -> device entry
        $scope.dev_lut = {}
        # group_id -> device group entry from tree (with devices list)
        $scope.devg_lut = {}
        cur_dg = undefined
        dsel_list = (entry.idx for entry in $scope.rest_data["device_sel"] when entry.sel_type == "d")
        $scope.cur_sel = dsel_list
        # we dont need the group selection
        # gsel_list = (entry.idx for entry in $scope.rest_data["device_sel"] when entry.sel_type == "g")
        for entry in $scope.rest_data["device_tree"]
            $scope.dev_lut[entry.idx] = entry
            # copy selection state to device selection (the selection state of the meta devices is keeped in sync with the selection states of the devicegroups )
            t_entry = $scope.tc_devices.new_node({obj:entry.idx, folder:entry.is_meta_device, _node_type:"d", selected:entry.idx in dsel_list})
            if entry.categories
                cat_list = []
                for t_cat in entry.categories
                    $scope.t_cat_lut[t_cat].devices.push(entry.idx)
            if entry.is_meta_device
                g_entry = $scope.tc_groups.new_node({obj: entry.idx, folder:true, _node_type: "g", devices: []})
                $scope.tc_groups.add_root_node(g_entry)
                cur_dg = t_entry
                $scope.tc_devices.add_root_node(cur_dg)
                $scope.devg_lut[entry.device_group] = g_entry
            else
                cur_dg.add_child(t_entry)
                $scope.devg_lut[entry.device_group].devices.push(entry.idx)
        $scope.tc_devices.prune(
            (entry) ->
                return entry._node_type == "d"
        )
        for cur_tc in [$scope.tc_devices, $scope.tc_groups, $scope.tc_categories]
            cur_tc.recalc()
            cur_tc.show_selected()
        $scope.is_loading = false
        $scope.selection_changed()
    )
    $scope.toggle_show_selection = () ->
        $scope.show_selection = !$scope.show_selection
    $scope.tabs = {}
    for tab_short in ["d", "g", "c"]
        $scope.tabs[tab_short] = tab_short == $scope.active_tab
    $scope.activate_tab = (t_type) ->
        # cur_sel = $scope.get_active_selection($scope.active_tab)
        # $scope.set_active_selection(t_type, cur_sel)
        $scope.active_tab = t_type
        #icswCallAjaxService
        #    url  : ICSW_URLS.USER_SET_USER_VAR
        #    data :
        #        key   : "sidebar_mode"
        #        value : {"c" : "category", "f" : "fqdn", "g" : "group"}[$scope.active_tab]
        #        type  : "str"
    $scope.get_tc = (short) ->
        return {"d" : $scope.tc_devices, "g": $scope.tc_groups, "c" : $scope.tc_categories}[short]
    $scope.clear_selection = (tab_name) ->
        _tree = $scope.get_tc(tab_name)
        _tree.clear_selected()
        $scope.search_ok = true
        $scope.selection_changed()
        # $scope.call_devsel_func()
    $scope.clear_search = () ->
        if $scope.cur_search_to
            $timeout.cancel($scope.cur_search_to)
        $scope.searchstr = ""
        $scope.search_ok = true
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
                else if entry._node_type == "g"
                    _sel = if $scope.dev_lut[entry.obj].full_name.match(cur_re) then true else false
                    entry.set_selected(_sel)
                    if _sel
                        num_found++
                else if entry._node_type == "c"
                    _sel = if $scope.cat_lut[entry.obj].name.match(cur_re) then true else false
                    entry.set_selected(_sel)
                    if _sel
                        num_found++
            cur_re
        )
        $scope.search_ok = if num_found > 0 then true else false
        cur_tree.show_selected(false)
        $scope.selection_changed()
    $scope.resolve_devices = (sel) ->
        return sel.resolve_devices($scope.dev_lut)
    $scope.resolve_total_devices = (sel) ->
        return sel.resolve_total_devices($scope.dev_lut)
    $scope.resolve_device_groups = (sel) ->
        return sel.resolve_device_groups($scope.dev_lut)
    $scope.resolve_categories = (sel) ->
        return sel.resolve_categories($scope.cat_lut)
    $scope.resolve_lazy_selection = () ->
        # use t_cat_lut to get the devices right
        $scope.selection.resolve_lazy_selection($scope.dev_lut, $scope.devg_lut, $scope.t_cat_lut)
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
            for _group_dev in $scope.devg_lut[$scope.dev_lut[_gs].device_group].devices
                tot_dev_sel.push(_group_dev)
        for _cs in cat_sel_nodes
            for _cat_dev in $scope.t_cat_lut[_cs].devices
                tot_dev_sel.push(_cat_dev)
        $scope.selection = new Selection(cat_sel_nodes, devg_sel, dev_sel, _.uniq(tot_dev_sel))
]).service("icswLayoutSelectionDialogService", ["$q", "$compile", "$templateCache", "Restangular", "ICSW_URLS", "icswToolsSimpleModalService", ($q, $compile, $templateCache, Restangular, ICSW_URLS, icswToolsSimpleModalService) ->
    show_dialog = (scope) ->
        sel_scope = scope.$new()
        dialog_div = $compile($templateCache.get("icsw.layout.selection.modify"))(sel_scope)
        BootstrapDialog.show
            message: dialog_div
            draggable: true
            animate: true
            onhidden: () ->
                sel_scope.$destroy()
    quick_dialog = (scope) ->
        sel_scope = scope.$new()
        dialog_div = $compile($templateCache.get("icsw.layout.selection.modify"))(sel_scope)
        BootstrapDialog.show
            message: dialog_div
            cssClass: "modal-left"
            title: "Device Selection"
            draggable: true
            animate: false
            closable: true
            onhidden: () ->
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
        "show_dialog": show_dialog
        "quick_dialog": quick_dialog
    }
]).service("icswLayoutSelectionTreeService", () ->
    class selection_tree extends tree_config
        constructor: (@scope, args) ->
            super(args)
        handle_click: (entry, event) =>
            entry.set_selected(not entry.selected)
        get_name: (t_entry) ->
            entry = @get_dev_entry(t_entry)
            if t_entry._node_type == "f"
                if entry.parent
                    return "#{entry.name} (*.#{entry.full_name})"
                else
                    return "[TLN]"
            else if t_entry._node_type == "c"
                if entry.depth
                    _res = entry.name
                    if t_entry.devices.length
                        _res = "#{_res} (#{t_entry.devices.length} devices)"
                else
                    _res = "[TOP]"
                return _res
            else if t_entry._node_type == "g"
                _res = entry.name.slice(8)
                if t_entry.devices.length
                    _res = "#{_res} (#{t_entry.devices.length} devices)"
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
            if t_entry._node_type == "f"
                return @scope.fqdn_lut[t_entry.obj]
            else if t_entry._node_type == "c"
                return @scope.cat_lut[t_entry.obj]
            else
                return @scope.dev_lut[t_entry.obj]
        selection_changed: () =>
            @scope.selection_changed()
)
