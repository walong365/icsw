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
    "icsw.config.category_tree",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "ui.select", "restangular", "uiGmapgoogle-maps", "angularFileUpload",
    ]
).service("icswConfigCategoryTreeFetchService", ["icswCachingCall", "$q", "ICSW_URLS", (icswCachingCall, $q, ICSW_URLS) ->
    _fetch = (id, pk_list) ->
        defer =$q.defer()
        _wait = [
            icswCachingCall.fetch(id, ICSW_URLS.REST_CATEGORY_LIST, {}, []),
            icswCachingCall.fetch(id, ICSW_URLS.REST_LOCATION_GFX_LIST, {"device_mon_location__device__in": "<PKS>", "_distinct": true}, pk_list),
            icswCachingCall.fetch(id, ICSW_URLS.REST_DEVICE_MON_LOCATION_LIST, {"device__in": "<PKS>"}, pk_list)
            icswCachingCall.fetch(id, ICSW_URLS.DEVICE_GET_DEVICE_LOCATION, {"devices": "<PKS>"}, pk_list)
        ]
        $q.all(_wait).then((data) ->
            defer.resolve(data)
        )
        return defer.promise
    return {
        "fetch": (id, pk_list) ->
            return _fetch(id, pk_list)
    }
]).controller("icswConfigCategoryTreeCtrl", [
    "$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "$window", "$timeout",
    "$q", "$modal", "access_level_service", "blockUI", "icswTools", "ICSW_URLS", "icswConfigCategoryTreeService", "msgbus",
    "icswCallAjaxService", "icswParseXMLResponseService", "toaster", "icswConfigCategoryTreeMapService", "icswConfigCategoryTreeFetchService",
    "icswToolsSimpleModalService",
   ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, $window, $timeout, $q, $modal, access_level_service,
    blockUI, icswTools, ICSW_URLS, icswConfigCategoryTreeService, msgbus, icswCallAjaxService, icswParseXMLResponseService, toaster,
    icswConfigCategoryTreeMapService, icswConfigCategoryTreeFetchService, icswToolsSimpleModalService) ->
        $scope.cat = new icswConfigCategoryTreeService($scope, {})
        $scope.pagSettings = paginatorSettings.get_paginator("cat_base", $scope)
        $scope.entries = []
        $scope.mode_entries = []
        # mixins
        # edit mixin for cateogries
        $scope.edit_mixin = new angular_edit_mixin($scope, $templateCache, $compile, Restangular, $q, "cat")
        $scope.edit_mixin.use_modal = false
        $scope.edit_mixin.use_promise = true
        $scope.edit_mixin.new_object = (scope) -> return scope.new_object()
        $scope.edit_mixin.delete_confirm_str = (obj) -> return "Really delete category node '#{obj.name}' ?"
        $scope.edit_mixin.modify_rest_url = ICSW_URLS.REST_CATEGORY_DETAIL.slice(1).slice(0, -2)
        $scope.edit_mixin.create_rest_url = Restangular.all(ICSW_URLS.REST_CATEGORY_LIST.slice(1))
        $scope.edit_mixin.edit_template = "category.form"
        $scope.form = {}
        msgbus.receive("icsw.config.locations.changed.map", $scope, () ->
            # receiver for global changes from map
            $scope.reload()
        )
        $scope.is_mode_entry = (entry) ->
            # contains top node
            return entry.depth < 1 or entry.full_name.split("/")[1] == $scope.mode
        $scope.reload = () ->
            icswConfigCategoryTreeFetchService.fetch($scope.$id, null).then((data) ->
                # (for historic reasons, different category types are still mixed elsewhere here)
                $scope.entries = data[0]
                # these contain only the ones which are relevant to this view
                $scope.mode_entries = (entry for entry in $scope.entries.plain() when $scope.is_mode_entry(entry))

                for entry in $scope.entries
                    entry.open = false
                $scope.dml_list = data[2]
                $scope.edit_mixin.create_list = $scope.entries
                $scope.edit_mixin.delete_list = $scope.entries
                $scope.rebuild_cat()
        )
        $scope.edit_obj = (cat, event) ->
            $scope.create_mode = false
            $scope.cat.clear_active()
            $scope.cat_lut[cat.idx].active = true
            $scope.cat.show_active()
            pre_parent = cat.parent
            $scope.edit_mixin.edit(cat, event).then((data) ->
                if data.parent == pre_parent
                    $scope.cat.iter(
                        (entry) ->
                            if entry.parent and entry.parent.obj.name
                                entry.obj.full_name = "#{entry.parent.obj.full_name}/#{entry.obj.name}"
                            else
                                entry.obj.full_name = "/#{entry.obj.name}"
                    )
                else
                    $scope.reload()
                msgbus.emit("icsw.config.locations.changed.tree")
            )
        $scope.delete_obj = (obj) ->
            $scope.edit_mixin.delete_obj(obj).then((data) ->
                if data
                    $scope.rebuild_cat()
                    $scope.cat.clear_active()
                    msgbus.emit("icsw.config.locations.changed.tree")
            )
        $scope.rebuild_cat = () ->
            # check location gfx refs
            cat_lut = {}
            $scope.cat.clear_root_nodes()
            # only use mode_entries (for historic reasons, different category types are still mixed elsewhere here)
            for entry in $scope.mode_entries
                t_entry = $scope.cat.new_node({folder:false, obj:entry, expand:entry.depth < 2, selected: entry.immutable})
                cat_lut[entry.idx] = t_entry
                if entry.parent
                    cat_lut[entry.parent].add_child(t_entry)
                else
                    $scope.cat.add_root_node(t_entry)
            $scope.cat_lut = cat_lut
        $scope.new_object = () ->
            if $scope.new_top_level
                _parent = (value for value in $scope.entries when value.depth == 1 and value.name == $scope.new_top_level)[0]
                _name = "new_#{_parent.name}"
                r_struct = {"name" : _name, "parent" : _parent.idx, "depth" : 2, "full_name" : "/#{$scope.new_top_level}/#{_name}"}
                if $scope.new_top_level == "location"
                    r_struct["latitude"] = 48.1
                    r_struct["longitude"] = 16.3
                return r_struct
            else
                return {"name" : "new_cat", "depth" : 2, "full_name" : ""}
        $scope.create_new = ($event, top_level) ->
            $scope.create_mode = true
            $scope.new_top_level = top_level
            $scope.cat.clear_active()
            $scope.edit_mixin.create($event).then((data) ->
                $scope.reload()
                msgbus.emit("icsw.config.locations.changed.tree")
            )
        $scope.get_valid_parents = (obj) ->
            # called from form code
            if obj.idx
                # object already saved, do not move between top categories
                top_cat = new RegExp("^/" + obj.full_name.split("/")[1])
                p_list = (value for value in $scope.mode_entries when value.depth and top_cat.test(value.full_name))
                # remove all nodes below myself
                r_list = []
                add_list = [$scope._edit_obj.idx]
                while add_list.length
                    r_list = r_list.concat(add_list)
                    add_list = (value.idx for value in p_list when (value.parent in r_list and value.idx not in r_list))
                p_list = (value for value in p_list when value.idx not in r_list)
            else
                # new object, allow all values
                p_list = (value for value in $scope.mode_entries when value.depth)
            return p_list
        $scope.is_location = (obj) ->
            # called from formular code
            # full_name.match leads to infinite digest cycles
            return (obj.depth > 1) and obj.full_name.split("/")[1] == "location"
        $scope.close_modal = () ->
            $scope.cat.clear_active()
            if $scope.cur_edit
                $scope.cur_edit.close_modal()
        $scope.prune_tree = () ->
            $scope.cat.clear_active()
            $scope.close_modal()
            icswToolsSimpleModalService("Really prune tree (delete empty elements) ?").then(() ->
                blockUI.start()
                icswCallAjaxService
                    url     : ICSW_URLS.BASE_PRUNE_CATEGORIES
                    data:
                        mode : $scope.mode
                    success : (xml) ->
                        icswParseXMLResponseService(xml)
                        $scope.reload()
                        blockUI.stop()
            )
        $scope.reload()
]).service("icswConfigCategoryTreeService", ["icswTreeConfig", (icswTreeConfig) ->
    class category_tree_edit extends icswTreeConfig
        constructor: (@scope, args) ->
            super(args)
            @show_selection_buttons = false
            @show_icons = false
            @show_select = false
            @show_descendants = true
            @show_childs = false
            @location_re = new RegExp("^/location/.*$")
        get_name : (t_entry) ->
            cat = t_entry.obj
            is_loc = @location_re.test(cat.full_name)
            if cat.depth > 1
                r_info = "#{cat.full_name} (#{cat.name})"
                if cat.num_refs
                    r_info = "#{r_info} (refs=#{cat.num_refs})"
                if is_loc
                    if cat.physical
                        r_info = "#{r_info}, physical"
                    else
                        r_info = "#{r_info}, structural"
                    if cat.locked
                        r_info = "#{r_info}, locked"
            else if cat.depth
                r_info = cat.full_name
            else
                r_info = "TOP"
            return r_info
        handle_click: (entry, event) =>
            @clear_active()
            cat = entry.obj
            if cat.depth > 1
                @scope.edit_obj(cat, event)
            else if cat.depth == 1
                @scope.create_new(event, cat.full_name.split("/")[1])
            @scope.$digest()

]).directive("icswConfigCategoryTreeHead", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.category.tree.head")
    }
]).directive("icswConfigCategoryTreeRow", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.category.tree.row")
        link : (scope, el, attrs) ->
            scope.get_tr_class = (obj) ->
                return if obj.depth > 1 then "" else "success"
            scope.get_space = (depth) ->
                return ("&nbsp;&nbsp;" for idx in [0..depth]).join("")
    }
]).directive("icswConfigCategoryTreeEditTemplate", ["$compile", "$templateCache", ($compile, $templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("category.form")
        link : (scope, element, attrs) ->
            scope.form_error = (field_name) ->
                if scope.form[field_name].$valid
                    return ""
                else
                    return "has-error"
    }
]).directive("icswConfigCategoryTree", ["$compile", "$templateCache", ($compile, $templateCache) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.config.category.tree")
        link : (scope, element, attrs) ->
            scope.mode = attrs.mode
            scope.mode_display = if scope.mode == 'mon' then 'monitoring' else scope.mode
            console.assert(scope.mode in ['mon', 'config', 'device', 'location'], "invalid mode in category tree")
    }
]).directive("icswConfigCategoryContentsViewer", ["Restangular", "ICSW_URLS", (Restangular, ICSW_URLS) ->
    return {
        restrict: "EA"
        templateUrl: "icsw.config.category.contents_viewer"
        scope:
            categoryPk: '='
            categoryName: '='
        link : (scope, elements, attrs) ->
            scope.$watch('categoryPk', () ->
                scope.enabled = scope.categoryPk?
                if scope.enabled
                    scope.data_ready = false
                    Restangular.all(ICSW_URLS.BASE_CATEGORY_CONTENTS.slice(1)).getList({category_pk: scope.categoryPk}).then((new_data) ->
                        scope.data_ready = true
                        scope.category_contents = new_data
                    )
            )
    }
])
