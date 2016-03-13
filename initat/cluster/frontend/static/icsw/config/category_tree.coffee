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
            @lut = {}
        get_name : (t_entry) ->
            cat = t_entry.obj
            is_loc = @location_re.test(cat.full_name)
            if cat.depth > 1
                # r_info = "#{cat.full_name} (#{cat.name})"
                r_info = "#{cat.name}"
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
                @scope.create_or_edit(event, false, cat)
            else if cat.depth == 1
                @scope.create_or_edit(event, true, cat)
            @scope.$digest()

]).service("icswCategoryTree",
[
    "icswTools", "ICSW_URLS", "$q", "Restangular", "$rootScope",
(
    icswTools, ICSW_URLS, $q, Restangular, $rootScope
) ->
    class icswCategoryTree
        constructor: (@list) ->
            @build_luts()

        build_luts: () =>
            # create lookupTables
            @lut = icswTools.build_lut(@list)
            @reorder()

        reorder: () =>
            # sort
            @link()

        link: () =>
            # create links
            # clear all child entries
            set_name = (cat, full_name, depth) =>
                cat.full_name = "#{full_name}/#{cat.name}"
                cat.depth = depth + 1
                (set_name(@lut[child], cat.full_name, depth + 1) for child in cat.children)
            for entry in @list
                entry.children = []
            for entry in @list
                if entry.parent
                    @lut[entry.parent].children.push(entry.idx)
                else
                    entry.full_name = entry.name
            for entry in @list
                if entry.depth == 1
                    (set_name(@lut[child], entry.full_name, 1) for child in entry.children)
            @reorder_full_name()

        reorder_full_name: () =>
            @list = _.orderBy(
                @list
                ["full_name"]
                ["asc"]
            )
        # catalog create / delete category entries
        create_category_entry: (new_ce) =>
            # create new peer
            defer = $q.defer()
            Restangular.all(ICSW_URLS.REST_CATEGORY_LIST.slice(1)).post(new_ce).then(
                (new_obj) =>
                    @_fetch_category_entry(new_obj.idx, defer, "created category entry")
                (not_ok) ->
                    defer.reject("category entry not created")
            )
            return defer.promise

        delete_category_entry: (del_ce) =>
            # ensure REST hooks
            Restangular.restangularizeElement(null, del_ce, ICSW_URLS.REST_CATEGORY_DETAIL.slice(1).slice(0, -2))
            defer = $q.defer()
            del_ce.remove().then(
                (ok) =>
                    _.remove(@list, (entry) -> return entry.idx == del_ce.idx)
                    @build_luts()
                    defer.resolve("deleted")
                (error) ->
                    defer.reject("not deleted")
            )
            return defer.promise

        _fetch_category_entry: (pk, defer, msg) =>
            Restangular.one(ICSW_URLS.REST_CATEGORY_LIST.slice(1)).get({"idx": pk}).then(
                (new_ce) =>
                    new_ce = new_ce[0]
                    console.log "NEW", new_ce
                    @list.push(new_ce)
                    @build_luts()
                    defer.resolve(msg)
            )

]).service("icswCategoryTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall", "icswTools",
    "icswCategoryTree", "$rootScope", "ICSW_SIGNALS",
(
    $q, Restangular, ICSW_URLS, $window, icswCachingCall, icswTools,
    icswCategoryTree, $rootScope, ICSW_SIGNALS
) ->
    rest_map = [
        [
            ICSW_URLS.REST_CATEGORY_LIST
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
        $q.all(_wait_list).then(
            (data) ->
                console.log "*** category tree loaded ***"
                _result = new icswCategoryTree(data[0])
                _defer.resolve(_result)
                for client of _fetch_dict
                    # resolve clients
                    _fetch_dict[client].resolve(_result)
                $rootScope.$emit(ICSW_SIGNALS("ICSW_CATEGORY_TREE_LOADED"), _result)
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
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise
        "reload": (client) ->
            # to be implemented
        "current": () ->
            return _result
    }
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
]).directive("icswConfigCategoryTreeEdit", ["$compile", "$templateCache", ($compile, $templateCache) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.config.category.tree")
        # important: create new scope
        scope: true
        controller: "icswConfigCategoryTreeCtrl"
        link : (scope, element, attrs) ->
            scope.mode = attrs.mode
            scope.mode_display = if scope.mode == 'mon' then 'monitoring' else scope.mode
            console.assert(
                scope.mode in [
                    'mon', 'config', 'device', 'location'
                ],
                "invalid mode '#{scope.mode}' in category tree"
            )
    }
]).controller("icswConfigCategoryTreeCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular", "$timeout",
    "$q", "$uibModal", "icswAcessLevelService", "blockUI", "icswTools", "ICSW_URLS", "icswConfigCategoryTreeService", "msgbus",
    "icswSimpleAjaxCall", "toaster", "icswConfigCategoryTreeMapService", "icswConfigCategoryTreeFetchService",
    "icswToolsSimpleModalService", "icswCategoryTreeService", "icswComplexModalService",
    "icswCategoryBackup",
(
    $scope, $compile, $filter, $templateCache, Restangular, $timeout, $q, $uibModal, icswAcessLevelService,
    blockUI, icswTools, ICSW_URLS, icswConfigCategoryTreeService, msgbus, icswSimpleAjaxCall, toaster,
    icswConfigCategoryTreeMapService, icswConfigCategoryTreeFetchService, icswToolsSimpleModalService,
    icswCategoryTreeService, icswComplexModalService, icswCategoryBackup
) ->
    # $scope.entries = []
    $scope.mode_entries = []
    # mixins
    # edit mixin for cateogries
    #$scope.edit_mixin = new angular_edit_mixin($scope, $templateCache, $compile, Restangular, $q, "cat")
    #$scope.edit_mixin.use_modal = false
    #$scope.edit_mixin.use_promise = true
    #$scope.edit_mixin.new_object = (scope) -> return scope.new_object()
    #$scope.edit_mixin.delete_confirm_str = (obj) -> return "Really delete category node '#{obj.name}' ?"
    #$scope.edit_mixin.modify_rest_url = ICSW_URLS.REST_CATEGORY_DETAIL.slice(1).slice(0, -2)
    #$scope.edit_mixin.create_rest_url = Restangular.all(ICSW_URLS.REST_CATEGORY_LIST.slice(1))
    #$scope.edit_mixin.edit_template = "category.form"
    #$scope.form = {}

    $scope.tree = new icswConfigCategoryTreeService($scope, {})
    $scope.reload = () ->
        icswCategoryTreeService.load($scope.$id).then(
            (data) ->
                $scope.category_tree = data
                # for entry in $scope.entries
                #    entry.open = false
                # $scope.dml_list = data[2]
                # $scope.edit_mixin.create_list = $scope.entries
                # $scope.edit_mixin.delete_list = $scope.entries
                $scope.rebuild_tree()
    )
    msgbus.receive(msgbus.event_types.CATEGORY_CHANGED, $scope, $scope.reload)
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
            msgbus.emit(msgbus.event_types.CATEGORY_CHANGED)
        )
    $scope.delete_obj = (obj) ->
        $scope.edit_mixin.delete_obj(obj).then((data) ->
            if data
                $scope.rebuild_cat()
                $scope.cat.clear_active()
                msgbus.emit("icsw.config.locations.changed.tree")
                msgbus.emit(msgbus.event_types.CATEGORY_CHANGED)
        )
    $scope.rebuild_tree = () ->
        $scope.mode_entries = (entry for entry in $scope.category_tree.list when entry.depth < 1 or entry.full_name.split("/")[1] == $scope.mode)
        # check location gfx refs
        $scope.tree.lut = {}
        $scope.tree.clear_root_nodes()
        # only use mode_entries (for historic reasons, different category types are still mixed elsewhere here)
        for entry in $scope.mode_entries
            t_entry = $scope.tree.new_node(
                {
                    folder: false
                    obj: entry
                    expand: entry.depth < 2
                    selected: entry.immutable
                }
            )
            $scope.tree.lut[entry.idx] = t_entry
            if entry.parent
                $scope.tree.lut[entry.parent].add_child(t_entry)
            else
                $scope.tree.add_root_node(t_entry)

    $scope.create_or_edit = (event, create, obj_or_parent) ->
        console.log obj_or_parent.name
        top_level = obj_or_parent.full_name.split("/")[1]
        if create
            _parent = (value for value in $scope.mode_entries when value.depth == 1 and value.full_name.split("/")[1] == top_level)[0]
            _name = "new_#{top_level}_cat"
            r_struct = {
                name: _name
                parent: _parent.idx
                depth: 2
                full_name: "/#{top_level}/#{_name}"
            }
            if top_level == "location"
                r_struct["latitude"] = 48.1
                r_struct["longitude"] = 16.3
            obj_or_parent = r_struct
        else
            dbu = new icswCategoryBackup()
            dbu.create_backup(obj_or_parent)
        sub_scope = $scope.$new(false)
        sub_scope.edit_obj = obj_or_parent

        sub_scope.get_valid_parents = (obj) ->
            # called from form code
            if obj.idx
                # object already saved, do not move between top categories
                top_cat = new RegExp("^/" + obj.full_name.split("/")[1])
                p_list = (value for value in $scope.mode_entries when value.depth and top_cat.test(value.full_name))
                # remove all nodes below myself
                r_list = []
                add_list = [$scope.edit_obj.idx]
                while add_list.length
                    r_list = r_list.concat(add_list)
                    add_list = (value.idx for value in p_list when (value.parent in r_list and value.idx not in r_list))
                p_list = (value for value in p_list when value.idx not in r_list)
            else
                # new object, allow all values
                p_list = (value for value in $scope.mode_entries when value.depth)
            return p_list

        sub_scope.is_location = (obj) ->
            # called from formular code
            # full_name.match leads to infinite digest cycles
            return (obj.depth > 1) and top_level == "location"

        ok_label = if create then "Create" else "Modify"
        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.category.form"))(sub_scope)
                title: "#{ok_label} Category entry '#{obj_or_parent.name}"
                css_class: "modal-wide"
                ok_label: ok_label
                closable: true
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "", 0)
                        d.reject("form not valid")
                    else
                        if create
                            $scope.category_tree.create_category_entry(sub_scope.edit_obj).then(
                                (ok) ->
                                    d.resolve("created")
                                (notok) ->
                                    d.reject("not created")
                            )
                        else
                            sub_scope.edit_obj.put().then(
                                (ok) ->
                                    $scope.category_tree.reorder()
                                    d.resolve("updated")
                                (not_ok) ->
                                    d.reject("not updated")
                            )
                    return d.promise
                cancel_callback: (modal) ->
                    if not create
                        dbu.restore_backup(obj_or_parent)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                console.log "finish"
                $scope.rebuild_tree()
                sub_scope.$destroy()
        )

    $scope.prune_tree = () ->
        $scope.cat.clear_active()
        $scope.close_modal()
        icswToolsSimpleModalService("Really prune tree (delete empty elements) ?").then(() ->
            blockUI.start()
            icswSimpleAjaxCall(
                url     : ICSW_URLS.BASE_PRUNE_CATEGORIES
                data:
                    mode : $scope.mode
            ).then(
                (xml) ->
                    $scope.reload()
                    msgbus.emit(msgbus.event_types.CATEGORY_CHANGED)
                    blockUI.stop()
                (xml) ->
                    $scope.reload()
                    msgbus.emit(msgbus.event_types.CATEGORY_CHANGED)
                    blockUI.stop()
            )
        )
    $scope.reload()

]).directive("icswConfigCategoryContentsViewer", ["Restangular", "ICSW_URLS", "msgbus", (Restangular, ICSW_URLS, msgbus) ->
    return {
        restrict: "EA"
        templateUrl: "icsw.config.category.contents_viewer"
        scope:
            categoryPk: '='
            categoryName: '='
        link : (scope, elements, attrs) ->
            update = () ->
                scope.data_ready = false
                scope.enabled = scope.categoryPk?
                if scope.enabled
                    Restangular.all(ICSW_URLS.BASE_CATEGORY_CONTENTS.slice(1)).getList({category_pk: scope.categoryPk}).then((new_data) ->
                        scope.data_ready = true
                        scope.category_contents = new_data
                    )
            msgbus.receive(msgbus.event_types.CATEGORY_CHANGED, scope, update)
            scope.$watch('categoryPk', update)
    }
])