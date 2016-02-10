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
]).service("icswDeviceCategoryTreeService", ["icswTreeConfig", "msgbus", (icswTreeConfig, msgbus) ->
    class category_tree extends icswTreeConfig
        constructor: (@scope, args) ->
            super(args)
            @show_selection_buttons = false
            @show_icons = false
            @show_select = true
            @show_descendants = false
            @show_childs = false
        selection_changed: (entry) =>
            # FIXME, TODO, slow update of the frontend (albeit the backbone already got the request)
            if @scope.multi_device_mode
                @scope.new_md_selection(entry)
            else
                sel_list = @get_selected((node) ->
                    if node.selected
                        return [node.obj.idx]
                    else
                        return []
                )
                @scope.new_selection(sel_list)
        get_name : (t_entry) ->
            cat = t_entry.obj
            if cat.depth > 1
                r_info = "#{cat.full_name} (#{cat.name})"
                num_sel = @scope.sel_dict[cat.idx].length
                if num_sel and num_sel < @scope.num_devices
                    r_info = "#{r_info}, #{num_sel} of #{@scope.num_devices}"
                if cat.num_refs
                    r_info = "#{r_info} (refs=#{cat.num_refs})"
                return r_info
            else if cat.depth
                return cat.full_name
            else
                return "TOP"
        handle_click: (entry, event) =>
            @scope.selected_category = entry.obj
            @scope.$digest()
]).controller("icswDeviceCategoryCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "restDataSource", "$q", "$uibModal", "icswAcessLevelService", "ICSW_URLS", "icswDeviceCategoryTreeService", "icswSimpleAjaxCall", "msgbus"
    ($scope, $compile, $filter, $templateCache, Restangular, restDataSource, $q, $uibModal, icswAcessLevelService, ICSW_URLS, icswDeviceCategoryTreeService, icswSimpleAjaxCall, msgbus) ->
        icswAcessLevelService.install($scope)
        $scope.device_pks = []
        $scope.device_list_ready = false
        $scope.cat_tree = new icswDeviceCategoryTreeService($scope, {})
        $scope.new_devsel = (pk_list) ->
            $scope.device_pks = pk_list
            $scope.multi_device_mode = if $scope.device_pks.length > 1 then true else false
            $scope.reload()
        msgbus.receive("icsw.config.locations.changed.tree", $scope, () ->
            $scope.reload()
        )
        $scope.reload = () ->
            wait_list = [
                restDataSource.reload([ICSW_URLS.REST_CATEGORY_LIST, {}])
                restDataSource.reload([ICSW_URLS.REST_DEVICE_TREE_LIST, {"pks" : angular.toJson($scope.device_pks), "with_categories" : true}])
            ]
            $q.all(wait_list).then((data) ->
                $scope.devices = data[1]
                $scope.device_list_ready = true
                $scope.num_devices = $scope.devices.length
                $scope.cat_tree.change_select = true
                for dev in $scope.devices
                    # check all devices and disable change button when not all devices are in allowed list
                    if not $scope.acl_all(dev, "backbone.device.change_category", 7)
                        $scope.cat_tree.change_select = false
                cat_tree_lut = {}
                $scope.cat_tree.clear_root_nodes()
                # selection dict
                sel_dict = {}
                for entry in data[0]
                    if entry.full_name.match(/^\/device/)
                        sel_dict[entry.idx] = []
                for dev in $scope.devices
                    for _sel in dev.categories
                        if _sel of sel_dict
                            sel_dict[_sel].push(entry.idx)
                $scope.sel_dict = sel_dict
                for entry in data[0]
                    if entry.full_name.match(/^\/device/)
                        t_entry = $scope.cat_tree.new_node({folder:false, obj:entry, expand:entry.depth < 2, selected: sel_dict[entry.idx].length == $scope.num_devices})
                        cat_tree_lut[entry.idx] = t_entry
                        if entry.parent and entry.parent of cat_tree_lut
                            cat_tree_lut[entry.parent].add_child(t_entry)
                        else
                            # hide selection from root nodes
                            t_entry._show_select = false
                            $scope.cat_tree.add_root_node(t_entry)
                $scope.cat_tree_lut = cat_tree_lut
                $scope.cat_tree.show_selected(false)
            )
        $scope.new_md_selection = (entry) ->
            # for multi-device selection
            cat = entry.obj
            icswSimpleAjaxCall(
                url     : ICSW_URLS.BASE_CHANGE_CATEGORY
                data    :
                    "obj_type" : "device"
                    "multi"    : "1"
                    "obj_pks"  : angular.toJson((_entry.idx for _entry in $scope.devices))
                    "set"      : if entry.selected then "1" else "0"
                    "cat_pk"   : cat.idx
            ).then((xml) ->
                if entry.selected
                    $scope.sel_dict[cat.idx] = (_entry.idx for _entry in $scope.devices)
                else
                    $scope.sel_dict[cat.idx] = []
                # FIXME, TODO
                # reload_sidebar_tree((_dev.idx for _dev in $scope.devices))

                msgbus.emit(msgbus.event_types.CATEGORY_CHANGED)  # category contents changed
            )
        $scope.new_selection = (sel_list) =>
            # only for single-device mode
            icswSimpleAjaxCall(
                url     : ICSW_URLS.BASE_CHANGE_CATEGORY
                data    :
                    "obj_type" : "device"
                    "obj_pk"   : $scope.devices[0].idx
                    "subtree"  : "/device"
                    "cur_sel"  : angular.toJson(sel_list)
            ).then((xml) ->
                msgbus.emit(msgbus.event_types.CATEGORY_CHANGED)  # category contents changed
            )
]).directive("icswDeviceCategoryOverview", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        controller: "icswDeviceCategoryCtrl"
        template: $templateCache.get("icsw.device.category.overview")
    }
])
