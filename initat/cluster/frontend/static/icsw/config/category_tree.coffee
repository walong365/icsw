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

        clear_tree: () =>
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
            # r_info = "#{r_info}"
            return r_info

        add_extra_span: (entry) =>
            cat = entry.obj
            #if cat.depth > 0
            #    return angular.element("<span></span>")
            #else
            return null

        update_extra_span: (entry, span) =>
            span.empty()
            cat = entry.obj
            if cat.depth > 0
                # span.append(angular.element("<input type='button' value='bla'></input>"))
                true

        handle_click: (entry, event) =>
            if not entry.active
                # i am not the active node, clear others
                @clear_active()
            cat = entry.obj
            if cat.depth > 1
                if entry.active
                    @scope.create_or_edit(event, false, cat)
                else
                    entry.active = true
                    @show_active()
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

        update: (new_list) ->
            # update with new data from server
            @list.length = 0
            for entry in new_list
                @list.push(entry)
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
                if _result?
                    _result.update(data[0])
                else
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
            return load_data(client).promise
        "current": () ->
            return _result
    }
]).directive("icswConfigCategoryTreeHead", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.category.tree.head")
        controller: "icswConfigCategoryRowCtrl"
    }
]).directive("icswConfigCategoryTreeRow", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.category.tree.row")
        controller: "icswConfigCategoryRowCtrl"
    }
]).controller("icswConfigCategoryRowCtrl",
[
    "$scope",
(
    $scope
) ->
    $scope.is_location = (obj) ->
        # called from formular code
        # full_name.match leads to infinite digest cycles
        return (obj.depth > 1) and $scope.mode == "location"

    $scope.get_tr_class = (obj) ->
        if $scope.tree.lut[obj.idx].active
            return "danger"
        else
            return if obj.depth > 1 then "" else "success"

    $scope.get_space = (depth) ->
        return ("&nbsp;&nbsp;" for idx in [0..depth]).join("")

    $scope.click_row = (obj) ->
        $scope.tree.clear_active()
        $scope.tree.lut[obj.idx].active = true
        $scope.tree.show_active()

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
    "icswCategoryBackup", "icswInfoModalService",
(
    $scope, $compile, $filter, $templateCache, Restangular, $timeout, $q, $uibModal, icswAcessLevelService,
    blockUI, icswTools, ICSW_URLS, icswConfigCategoryTreeService, msgbus, icswSimpleAjaxCall, toaster,
    icswConfigCategoryTreeMapService, icswConfigCategoryTreeFetchService, icswToolsSimpleModalService,
    icswCategoryTreeService, icswComplexModalService, icswCategoryBackup, icswInfoModalService
) ->
    $scope.mode_entries = []

    $scope.tree = new icswConfigCategoryTreeService($scope, {})
    $scope.load = () ->
        $scope.mode_is_location = if $scope.mode == "location" then true else false
        icswCategoryTreeService.load($scope.$id).then(
            (data) ->
                $scope.category_tree = data
                $scope.rebuild_tree()
    )
    $scope.reload = () ->
        icswCategoryTreeService.reload($scope.$id).then(
            (data) ->
                $scope.rebuild_tree()
    )

    $scope.rebuild_tree = () ->
        $scope.mode_entries = (entry for entry in $scope.category_tree.list when entry.depth < 1 or entry.full_name.split("/")[1] == $scope.mode)
        # save previous active nodes
        active = (entry.obj.idx for entry in $scope.tree.get_active())
        $scope.tree.clear_root_nodes()
        $scope.tree.clear_tree()
        # only use mode_entries (for historic reasons, different category types are still mixed elsewhere here)
        for entry in $scope.mode_entries
            t_entry = $scope.tree.new_node(
                {
                    folder: false
                    obj: entry
                    expand: entry.depth < 2
                    selected: false # entry.immutable
                }
            )
            $scope.tree.lut[entry.idx] = t_entry
            if entry.parent
                $scope.tree.lut[entry.parent].add_child(t_entry)
            else
                $scope.tree.add_root_node(t_entry)
        # activate nodes
        $scope.tree.iter(
            (entry) ->
                if entry.obj.idx in active
                    entry.active = true
        )
        $scope.tree.show_active()

    $scope.create_or_edit = (event, create, obj_or_parent) ->
        if obj_or_parent?
            top_level = obj_or_parent.full_name.split("/")[1]
        else
            # for top-level creation
            top_level = $scope.mode
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
                add_list = [sub_scope.edit_obj.idx]
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
                delete_ask: true

                delete_callback: (modal) ->
                    d = $q.defer()
                    $scope.category_tree.delete_category_entry(sub_scope.edit_obj).then(
                        (ok) ->
                            d.resolve("deleted")
                        (notok) ->
                            d.reject("not deleted")
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

    $scope.delete_obj = (event, obj) ->
        icswToolsSimpleModalService("Really delete Category ?").then(
            (ok) ->
                $scope.category_tree.delete_category_entry(obj).then(
                    (ok) ->
                        $scope.rebuild_tree()
                )
        )
    $scope.prune_tree = () ->
        blockUI.start()
        icswSimpleAjaxCall(
            url: ICSW_URLS.BASE_PRUNE_CATEGORY_TREE
            data:
                mode: $scope.mode
                doit: 0
        ).then(
            (xml) ->
                blockUI.stop()
                to_delete = parseInt($(xml).find("value[name='nodes']").text())
                info_str = $(xml).find("value[name='info']").text()
                if to_delete
                    icswToolsSimpleModalService(info_str).then(
                        (doit) ->
                            blockUI.start()
                            icswSimpleAjaxCall(
                                url: ICSW_URLS.BASE_PRUNE_CATEGORY_TREE
                                data:
                                    mode: $scope.mode
                                    doit: 1
                            ).then(
                                (xml) ->
                                    $scope.reload()
                                    blockUI.stop()
                                (xml) ->
                                    blockUI.stop()
                            )
                    )
                else
                    icswInfoModalService(info_str)
            (xml) ->
                blockUI.stop()
        )
    $scope.load()

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