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

angular.module(
    "icsw.device.category",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "icsw.d3", "icsw.tools.button"
    ]
).config(["$stateProvider", ($stateProvider) ->
    $stateProvider.state(
        "main.categorytree",
            {
                url: "/categorytree"
                templateUrl: "icsw/main/category/tree.html"
                data:
                    pageTitle: "Category tree"
                    rights: ["user.modify_category_tree"]
                    menuEntry:
                        menukey: "dev"
                        name: "Device category"
                        icon: "fa-table"
                        ordering: 14
            }
    )
]).service("icswDeviceCategoryTreeService",
[
    "icswTreeConfig",
(
    icswTreeConfig
) ->
    class category_tree extends icswTreeConfig
        constructor: (@scope, args) ->
            super(args)
            @show_selection_buttons = false
            @show_icons = false
            @show_select = true
            @show_descendants = false
            @show_childs = false
            @mode_entries = []
            @clear_tree()

        clear_tree: () =>
            @lut = {}

        create_mode_entries: (mode, cat_tree) =>
            @mode_entries.length = []
            for entry in cat_tree.list
                if entry.depth < 1 or entry.full_name.split("/")[1] == mode
                    @mode_entries.push(entry)

        get_selected_cat_pks: () =>
            return @get_selected(
                (node) ->
                    if node.selected
                        return [node.obj.idx]
                    else
                        return []
            )

        selection_changed: (entry) =>
            @scope.new_selection(entry, @get_selected_cat_pks())

        get_name : (t_entry) ->
            cat = t_entry.obj
            if cat.depth > 1
                r_info = "#{cat.name}"
                # number of selected entries (from local selection)
                num_sel = t_entry.$match_pks.length
                if num_sel and @$num_devs > 1
                    r_info = "#{r_info}, #{num_sel} of #{@$num_devs}"
                if cat.num_refs
                    r_info = "#{r_info}, total references=#{cat.num_refs}"
                return r_info
            else if cat.depth
                return cat.full_name
            else
                return "TOP"

        handle_click: (entry, event) =>
            if entry.obj.depth > 0
                @scope.selected_category = entry.obj
                @scope.$digest()

]).controller("icswDeviceCategoryCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular", "restDataSource", "$q",
    "icswAcessLevelService", "ICSW_URLS", "icswDeviceCategoryTreeService", "icswSimpleAjaxCall",
    "icswDeviceTreeService", "icswCategoryTreeService", "blockUI", "$rootScope", "ICSW_SIGNALS",
(
    $scope, $compile, $filter, $templateCache, Restangular, restDataSource, $q,
    icswAcessLevelService, ICSW_URLS, icswDeviceCategoryTreeService, icswSimpleAjaxCall,
    icswDeviceTreeService, icswCategoryTreeService, blockUI, $rootScope, ICSW_SIGNALS,
) ->
    icswAcessLevelService.install($scope)
    $scope.struct = {
        device_list_ready: false
        multi_device_mode: false
        cat_tree: new icswDeviceCategoryTreeService($scope, {})
    }

    $scope.$on("$destroy", () ->
        $scope.struct.device_list_ready = false
    )

    $scope.new_devsel = (devs) ->
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
                icswCategoryTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                device_tree = data[0]
                $scope.struct.device_list_ready = true
                $scope.struct.tree = data[1]
                $scope.struct.multi_device_mode = if devs.length > 1 then true else false
                $scope.struct.devices = devs
                $scope.struct.device_tree = device_tree
                $scope.rebuild_dnt()
        )

    $rootScope.$on(ICSW_SIGNALS("ICSW_CATEGORY_TREE_CHANGED"), (event) ->
        $scope.rebuild_dnt()
    )
    $scope.rebuild_dnt = () ->
        _ct = $scope.struct.cat_tree
        _ct.change_select = true
        for dev in $scope.struct.devices
            # check all devices and disable change button when not all devices are in allowed list
            if not $scope.acl_all(dev, "backbone.device.change_category", 7)
                _ct.change_select = false
                break
        if _ct.$pre_sel?
            _cur_sel = _ct.$pre_sel
        else
            _cur_sel = []
        _ct.clear_tree()
        _ct.clear_root_nodes()
        _ct.create_mode_entries("device", $scope.struct.tree)

        _ct.$num_devs = $scope.struct.devices.length
        _num_devs = $scope.struct.devices.length
        _dev_pks = (dev.idx for dev in $scope.struct.devices)
        _dev_pks.sort()

        for entry in _ct.mode_entries
            # console.log entry.reference_dict.device, _num_devs
            # get pks of devices in current selection which have the category entry set
            _match_pks = (_val for _val in entry.reference_dict.device when _val in _dev_pks)
            _match_pks.sort()
            # console.log entry.idx, _match_pks, entry.idx in _cur_sel
            # console.log _match_pks, _dev_pks
            t_entry = _ct.new_node(
                {
                    folder: false
                    obj: entry
                    expand: (entry.depth < 2) or (entry.idx in _cur_sel) or _match_pks.length
                    selected: _match_pks.length == _num_devs
                    _show_select: entry.useable
                }
            )
            # copy matching pks to tree entry (NOT entry because entry is global)
            t_entry.$match_pks = (_v for _v in _match_pks)
            _ct.lut[entry.idx] = t_entry
            if entry.parent and entry.parent of _ct.lut
                _ct.lut[entry.parent].add_child(t_entry)
                if t_entry.expand
                    # propagate expand level upwards
                    _t_entry = t_entry
                    while _t_entry.parent
                        _t_entry.expand = true
                        _t_entry = _t_entry.parent
            else
                # hide selection from root nodes
                t_entry._show_select = false
                _ct.add_root_node(t_entry)
        _ct.$pre_sel = _ct.get_selected_cat_pks()
        # _ct.show_selected(false)

    $scope.new_selection = (t_entry, sel_list) =>
        blockUI.start()
        cat = t_entry.obj
        icswSimpleAjaxCall(
            url: ICSW_URLS.BASE_CHANGE_CATEGORY
            data:
                "dev_pks": angular.toJson((_entry.idx for _entry in $scope.struct.devices))
                "cat_pks": angular.toJson([cat.idx])
                "set": if t_entry.selected then "1" else "0"
        ).then(
            (xml) ->
                # see code in location.coffee
                change_dict = angular.fromJson($(xml).find("value[name='changes']").text())
                sync_pks = []
                for add_b in change_dict.added
                    $scope.struct.device_tree.add_category_to_device_by_pk(add_b[0], add_b[1])
                    if add_b[0] not in sync_pks
                        sync_pks.push(add_b[0])
                for sub_b in change_dict.removed
                    $scope.struct.device_tree.remove_category_from_device_by_pk(sub_b[0], sub_b[1])
                    if sub_b[0] not in sync_pks
                        sync_pks.push(sub_b[0])
                if sync_pks.length
                    $scope.struct.tree.sync_devices(($scope.struct.device_tree.all_lut[_pk] for _pk in sync_pks))
                $scope.rebuild_dnt()
                blockUI.stop()
        )
]).directive("icswDeviceCategoryOverview", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        controller: "icswDeviceCategoryCtrl"
        template: $templateCache.get("icsw.device.category.overview")
    }
])
