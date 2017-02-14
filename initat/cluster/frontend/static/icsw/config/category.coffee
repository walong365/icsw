# Copyright (C) 2012-2017 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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

# category functions (without location)

angular.module(
    "icsw.config.category",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters",
        "ui.select", "restangular", "uiGmapgoogle-maps", "angularFileUpload",
        "icsw.backend.category",
    ]
).service("icswConfigCategoryDisplayTree",
[
    "icswReactTreeConfig",
(
    icswReactTreeConfig
) ->
    {span} = React.DOM
    class icswConfigCategoryDisplayTree extends icswReactTreeConfig
        constructor: (@scope, args) ->
            super(args)
            @mode_entries = []
            @location_re = new RegExp("^/location/.*$")
            # link to config-service of a list controller
            # @config_service = undefined
            # @config_object = undefined

        create_mode_entries: (mode, cat_tree) =>
            @mode_entries.length = []
            for entry in cat_tree.list
                if entry.depth < 1 or entry.full_name.split("/")[1] == mode
                    @mode_entries.push(entry)

        clear_tree: () =>
            @lut = {}

        get_name: (t_entry) ->
            cat = t_entry.obj
            is_loc = @location_re.test(cat.full_name)
            if cat.depth > 1
                # r_info = "#{cat.full_name} (#{cat.name})"
                r_info = "#{cat.name}"
            else if cat.depth
                r_info = cat.full_name
            else
                r_info = "TOP"
            return r_info

        get_post_view_element: (t_entry) ->
            _r_obj = []
            obj = t_entry.obj
            is_loc = @location_re.test(obj.full_name)
            if obj.depth > 1
                if is_loc
                    if obj.locked
                        _r_obj.push(" ")
                        _r_obj.push(
                            span(
                                {
                                    key: "lock"
                                    className: "fa fa-lock"
                                    title: "is locked"
                                }
                            )
                        )
                        _r_obj.push(" ")
                        _r_obj.push(
                            span(
                                {
                                    key: "_type"
                                    className: if obj.physical then "glyphicon glyphicon-globe" else "glyphicon glyphicon-th-list"
                                    title: if obj.pyhiscal then "Physical entry" else "Structural entry"
                                }
                            )
                        )
                        _r_obj.push(" ")
                if obj.num_refs
                    _r_obj.push(
                        span(
                            {
                                key: "num.refs"
                                className: "label label-success"
                            }
                            "#{obj.num_refs} refs"
                        )
                    )
            return _r_obj

        handle_context_menu: (event, entry) =>
            cat = entry.obj
            if cat.depth
                @config_service.create_or_edit(@config_object.scope, event, false, cat)
            event.preventDefault()

        toggle_active_obj: (obj) =>
            node = @lut[obj.idx]
            if node.obj
                node.set_active(!node.active)
                if node.active
                    @scope.selected_category = node.obj
                else
                    @scope.selected_category = null
                @show_active()
                @scope.update_active()

        handle_click: (event, entry) =>
            @toggle_active_obj(entry.obj)
            @scope.$digest()

]).service("icswConfigCategoryListService",
[
    "icswTools", "icswDomainTreeService", "$q", "$compile", "$templateCache",
    "icswComplexModalService", "toaster", "icswCategoryBackup", "Restangular";
    "icswToolsSimpleModalService", "ICSW_SIGNALS", "$rootScope", "ICSW_URLS",
(
    icswTools, icswDomainTreeService, $q, $compile, $templateCache,
    icswComplexModalService, toaster, icswCategoryBackup, Restangular,
    icswToolsSimpleModalService, ICSW_SIGNALS, $rootScope, ICSW_URLS,
) ->
    return {
        fetch: (scope) ->
            defer = $q.defer()
            # set scope for dn_tree
            scope.icsw_config_object.scope = scope
            scope.tree = scope.icsw_config_object.tree
            scope.dn_tree = scope.icsw_config_object.dn_tree
            scope.mode = scope.icsw_config_object.mode
            scope.mode_is_location = scope.mode == "location"
            scope.mode_is_device = scope.mode == "device"
            # links, a little hacky...
            scope.dn_tree.config_object = scope.icsw_config_object
            scope.dn_tree.config_service = @
            defer.resolve(scope.dn_tree.mode_entries)
            return defer.promise

        create_or_edit: (scope, event, create, obj_or_parent) ->
            if obj_or_parent?
                top_level = obj_or_parent.full_name.split("/")[1]
            else
                # for top-level creation
                top_level = scope.mode
            # console.log "***", top_level, obj_or_parent
            if create
                # if obj_or_parent?
                #     console.log "***", obj_or_parent
                #     _parent = obj_or_parent
                # else
                _parent = (value for value in scope.dn_tree.mode_entries when value.depth == 1 and value.full_name.split("/")[1] == top_level)[0]
                _name = "new_#{top_level}_cat"
                useable: true
                was_unuseable: false
                r_struct = {
                    name: _name
                    parent: _parent.idx
                    depth: 2
                    full_name: "/#{top_level}/#{_name}"
                    physical: false
                }
                if top_level == "location"
                    r_struct["latitude"] = 48.1
                    r_struct["longitude"] = 16.3
                obj_or_parent = r_struct
            else
                obj_or_parent.was_unuseable = not obj_or_parent.useable
                dbu = new icswCategoryBackup()
                dbu.create_backup(obj_or_parent)
            sub_scope = scope.$new(false)
            sub_scope.edit_obj = obj_or_parent

            if sub_scope.edit_obj.idx
                # object already saved, do not move between top categories
                if sub_scope.edit_obj.depth == 1
                    console.log "*"
                    p_list = (value for value in scope.dn_tree.mode_entries when value.depth == 0)
                    console.log p_list
                else
                    top_cat = new RegExp("^/" + sub_scope.edit_obj.full_name.split("/")[1])
                    p_list = (value for value in scope.dn_tree.mode_entries when value.depth and top_cat.test(value.full_name))
                    # remove all nodes below myself
                    r_list = []
                    add_list = [sub_scope.edit_obj.idx]
                    while add_list.length
                        r_list = r_list.concat(add_list)
                        add_list = (value.idx for value in p_list when (value.parent in r_list and value.idx not in r_list))
                    p_list = (value for value in p_list when value.idx not in r_list)
            else
                # new object, allow all values
                p_list = (value for value in scope.dn_tree.mode_entries when value.depth)

            # console.log p_list
            sub_scope.valid_parents = p_list

            sub_scope.is_location = (obj) ->
                # called from formular code
                # full_name.match leads to infinite digest cycles
                return (obj.depth > 1) and top_level == "location"

            sub_scope.is_device = (obj) ->
                # called from formular code
                # full_name.match leads to infinite digest cycles
                return (obj.depth > 1) and top_level == "device"

            ok_label = if create then "Create" else "Modify"

            complex_modal_service_dict =
            {
                message: $compile($templateCache.get("icsw.category.form"))(sub_scope)
                title: "#{ok_label} Category entry '#{obj_or_parent.name}"
                # css_class: "modal-wide"
                ok_label: ok_label
                closable: true
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "")
                        d.reject("form not valid")
                    else
                        if create
                            scope.tree.create_category_entry(sub_scope.edit_obj).then(
                                (ok) ->
                                    d.resolve("created")
                                (notok) ->
                                    d.reject("not created")
                            )
                        else
                            Restangular.restangularizeElement(null, sub_scope.edit_obj, ICSW_URLS.REST_CATEGORY_DETAIL.slice(1).slice(0, -2))
                            sub_scope.edit_obj.put().then(
                                (ok) ->
                                    scope.tree.reorder()
                                    d.resolve("updated")
                                (not_ok) ->
                                    d.reject("not updated")
                            )
                    return d.promise
                delete_ask: true

                cancel_callback: (modal) ->
                    if not create
                        dbu.restore_backup(obj_or_parent)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }

            if !create
                complex_modal_service_dict['delete_callback'] =
                    (modal) ->
                        d = $q.defer()
                        scope.tree.delete_category_entry(sub_scope.edit_obj).then(
                            (ok) ->
                                # sync with tree
                                $rootScope.$emit(ICSW_SIGNALS("ICSW_CATEGORY_TREE_CHANGED"), scope.tree)
                                d.resolve("deleted")
                            (notok) ->
                                d.reject("not deleted")
                        )
                        return d.promise



            icswComplexModalService(complex_modal_service_dict).then(
                (fin) ->
                    console.log "finish"
                    $rootScope.$emit(ICSW_SIGNALS("ICSW_CATEGORY_TREE_CHANGED"), scope.tree)
                    sub_scope.$destroy()
            )

        delete: (scope, event, obj) ->
            icswToolsSimpleModalService("Really delete Category #{obj.name} ?").then(
                (ok) ->
                    scope.tree.delete_category_entry(obj).then(
                        (ok) ->
                            $rootScope.$emit(ICSW_SIGNALS("ICSW_CATEGORY_TREE_CHANGED"), scope.tree)
                    )
            )

        special_fn: (scope, event, fn_name, obj) ->
            if fn_name == "delete_many"
                active = scope.dn_tree.get_active()

                # safeguard against deleting the /location category
                for obj in active
                    if obj.obj.full_name == "/location"
                        toaster.pop("error", "", "Deletion of '/location' category not allowed")
                        return

                icswToolsSimpleModalService("Really delete #{active.length} Categories ?").then(
                    (doit) ->
                        $q.allSettled(
                            (scope.tree.delete_category_entry(entry.obj) for entry in active)
                        ).then(
                            (result) ->
                                console.log result
                                $rootScope.$emit(ICSW_SIGNALS("ICSW_CATEGORY_TREE_CHANGED"), scope.tree)
                                console.log "many cats deleted"
                        )
                )
            else if fn_name == "clear_selection"
                scope.icsw_config_object.ctrl_scope.clear_active()

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
        return $scope.mode == "location"

    $scope.is_device = (obj) ->
        # called from formular code
        # full_name.match leads to infinite digest cycles
        return $scope.mode == "device"

    $scope.get_tr_class = (obj) ->
        if $scope.dn_tree.lut[obj.idx].active
            return "danger"
        else
            return if obj.depth > 1 then "" else "success"

    $scope.get_space = (depth) ->
        return ("&nbsp;&nbsp;" for idx in [0..depth]).join("")

    $scope.click_row = (obj) ->
        $scope.dn_tree.toggle_active_obj(obj)

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
    "$scope", "$compile", "$filter", "$templateCache", "Restangular", "$timeout", "$rootScope",
    "$q", "icswAccessLevelService", "blockUI", "icswTools", "ICSW_URLS", "icswConfigCategoryDisplayTree",
    "icswSimpleAjaxCall", "toaster",
    "icswToolsSimpleModalService", "icswCategoryTreeService", "icswComplexModalService",
    "icswCategoryBackup", "icswInfoModalService", "ICSW_SIGNALS",
(
    $scope, $compile, $filter, $templateCache, Restangular, $timeout, $rootScope,
    $q, icswAccessLevelService, blockUI, icswTools, ICSW_URLS, icswConfigCategoryDisplayTree,
    icswSimpleAjaxCall, toaster,
    icswToolsSimpleModalService,icswCategoryTreeService, icswComplexModalService,
    icswCategoryBackup, icswInfoModalService, ICSW_SIGNALS
) ->
    $scope.location_or_tln_selected = () ->
        tln_or_location_selected = false
        for selected in $scope.dn_tree.get_active()
            if selected.obj.full_name == "" || selected.obj.full_name == "/location"
                tln_or_location_selected = true

        return tln_or_location_selected

    $scope.struct = {}
    $scope.reload = () ->
        $scope.dn_tree = new icswConfigCategoryDisplayTree(
            $scope
            {
                show_selection_buttons: false
                show_select: false
                show_descendants: true
            }
        )
        icswCategoryTreeService.load($scope.$id).then(
            (tree) ->
                $scope.tree = tree
                # init struct for list-service
                $scope.struct.num_active = 0
                $scope.struct.dn_tree = $scope.dn_tree
                $scope.struct.tree = $scope.tree
                $scope.struct.mode = $scope.mode
                # create ctrl_scope entry
                $scope.struct.ctrl_scope = $scope
                $scope.rebuild_dnt()
    )

    $rootScope.$on(ICSW_SIGNALS("ICSW_CATEGORY_TREE_CHANGED"), (event) ->
        $scope.rebuild_dnt()
    )

    $scope.clear_active = () ->
        $scope.dn_tree.clear_active()
        $scope.update_active()

    $scope.update_active = ()->
        $scope.struct.num_active = $scope.dn_tree.get_active().length
        $scope.dn_tree.show_active()

    $scope.rebuild_dnt = () ->
        $scope.dn_tree.create_mode_entries($scope.mode, $scope.tree)
        # save previous active nodes
        active = (entry.obj.idx for entry in $scope.dn_tree.get_active())
        $scope.dn_tree.clear_root_nodes()
        $scope.dn_tree.clear_tree()
        # only use mode_entries (for historic reasons, different category types are still mixed elsewhere here)
        for entry in $scope.dn_tree.mode_entries
            t_entry = $scope.dn_tree.create_node(
                {
                    folder: false
                    obj: entry
                    expand: entry.depth < 2
                    selected: false # entry.immutable
                }
            )
            $scope.dn_tree.lut[entry.idx] = t_entry
            if entry.parent
                $scope.dn_tree.lut[entry.parent].add_child(t_entry)
            else
                $scope.dn_tree.add_root_node(t_entry)
        # activate nodes
        $scope.dn_tree.iter(
            (entry) ->
                if entry.obj.idx in active
                    entry.active = true
        )
        $scope.update_active()
        $scope.dn_tree.show_active()

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
                                (xml) =>
                                    $(xml).find("categories > category").each (idx, el) =>
                                        del_idx = parseInt($(el).attr("pk"))
                                        $scope.struct.tree.delete_category_by_pk(del_idx)
                                    $scope.struct.tree.build_luts()
                                    $rootScope.$emit(ICSW_SIGNALS("ICSW_CATEGORY_TREE_CHANGED"), $scope.struct.tree)
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
    $scope.reload()

]).directive("icswConfigCategoryContentsViewer",
[
    "Restangular",
(
    Restangular,
) ->
    return {
        restrict: "EA"
        templateUrl: "icsw.config.category.contents_viewer"
        controller: "icswConfigCategoryContentsViewerCtrl"
        scope:
            icsw_category: '=icswCategory'
    }
]).service("icswConfigCategoryModifyCall",
[
    "$q", "ICSW_URLS", "icswSimpleAjaxCall", "icswDeviceTreeService", "icswConfigTreeService",
    "icswCategoryTreeService", "icswTools", "ICSW_SIGNALS", "$rootScope",
(
    $q, ICSW_URLS, icswSimpleAjaxCall, icswDeviceTreeService, icswConfigTreeService,
    icswCategoryTreeService, icswTools, ICSW_SIGNALS, $rootScope,
) ->
    return (obj_pks, cat_objs, add) ->
        load_id = icswTools.get_unique_id()
        defer = $q.defer()
        icswSimpleAjaxCall(
            url: ICSW_URLS.BASE_CHANGE_CATEGORY
            data:
                obj_pks: angular.toJson(obj_pks)
                cat_pks: angular.toJson((cat.idx for cat in cat_objs))
                set: if add then "1" else "0"
        ).then(
            (xml) ->
                # see code in location.coffee
                change_dict = angular.fromJson($(xml).find("value[name='changes']").text())
                # console.log "cd=", change_dict
                # build dict
                cat_dict = {}
                for entry in cat_objs
                    _type = entry.full_name.split("/")[1]
                    if _type not of cat_dict
                        cat_dict[_type] = []
                    cat_dict[_type].push(entry.idx)
                    cat_dict[entry.idx] = _type
                # console.log "D=", cat_dict
                if "location" of cat_dict
                    console.error "location not supported in icswConfigCategoryModifyCalL"
                # console.log "**", cat_objs
                $q.all(
                    [
                        icswDeviceTreeService.load(load_id)
                        icswCategoryTreeService.load(load_id)
                        icswConfigTreeService.load(load_id)
                    ]
                ).then(
                    (data) ->
                        device_tree = data[0]
                        cat_tree = data[1]
                        config_tree = data[2]
                        # device or location
                        sync_pks = []
                        for [obj_idx, cat_idx] in change_dict.added
                            _ct = cat_dict[cat_idx]
                            if _ct == "config"
                                config_tree.add_category_to_config_by_pk(obj_idx, cat_idx)
                            else if _ct == "mon"
                                config_tree.add_category_to_mcc_by_pk(obj_idx, cat_idx)
                            else
                                device_tree.add_category_to_device_by_pk(obj_idx, cat_idx)
                                if obj_idx not in sync_pks
                                    sync_pks.push(obj_idx)
                        for [obj_idx, cat_idx] in change_dict.removed
                            _ct = cat_dict[cat_idx]
                            if _ct == "config"
                                config_tree.remove_category_from_config_by_pk(obj_idx, cat_idx)
                            else if _ct == "mon"
                                config_tree.remove_category_from_mcc_by_pk(obj_idx, cat_idx)
                            else
                                device_tree.remove_category_from_device_by_pk(obj_idx, cat_idx)
                                if obj_idx not in sync_pks
                                    sync_pks.push(obj_idx)
                        if sync_pks.length
                            cat_tree.sync_devices((device_tree.all_lut[_pk] for _pk in sync_pks))
                        $rootScope.$emit(ICSW_SIGNALS("ICSW_CATEGORY_TREE_CHANGED"))
                        defer.resolve("done")
                )
        )
        return defer.promise
]).controller("icswConfigCategoryContentsViewerCtrl",
[
    "$scope", "$q", "icswConfigTreeService", "icswDeviceTreeService",
    "icswMonitoringBasicTreeService", "$timeout", "blockUI", "ICSW_URLS",
    "icswSimpleAjaxCall", "icswConfigCategoryModifyCall", "icswToolsSimpleModalService",
(
    $scope, $q, icswConfigTreeService, icswDeviceTreeService,
    icswMonitoringBasicTreeService, $timeout, blockUI, ICSW_URLS,
    icswSimpleAjaxCall, icswConfigCategoryModifyCall, icswToolsSimpleModalService,
) ->
    $scope.struct = {
        # is enabled
        enabled: false
        # data is ready
        data_ready: false
        # contents of list
        contents: []
        # number selected
        selected: 0
        # selection supported (not for location due to missing DML handling code)
        selection_supported: false
    }

    update = () ->
        $scope.struct.data_ready = false
        $scope.struct.selected = 0
        _cat = $scope.icsw_category
        _wait_list = []
        _ref_list = []
        # todo: add deviceselection
        _lut = {
            config: icswConfigTreeService
            device: icswDeviceTreeService
            mon_check_command: icswMonitoringBasicTreeService
            deviceselection: null
        }
        for key, refs of _cat.reference_dict
            if refs.length
                _ext_call = _lut[key]
                if _ext_call
                    _wait_list.push(_ext_call.load($scope.$id))
                    _ref_list.push(key)
                else
                    console.error "cannot handle references to #{key}"
        res_list = []
        defer = $q.defer()
        if _wait_list.length
            $q.all(
                _wait_list
            ).then(
                (data) ->
                    for [key, res_obj] in _.zip(_ref_list, data)
                        # key, res_obj = res_tuple
                        pk_list = _cat.reference_dict[key]
                        for pk in pk_list
                            [subtype, info, type] = ["", "", key]
                            if key == "device"
                                _dev = res_obj.all_lut[pk]
                                name = _dev.full_name
                                if _dev.is_meta_device
                                    type = "Group"
                                    name = name.substr(8)
                                else
                                    info = "DeviceGroup " + res_obj.group_lut[_dev.device_group].name
                            else if key == "config"
                                _conf = res_obj.lut[pk]
                                name = _conf.name
                                info = "Coniguration"
                            else if key == "mon_check_command"
                                _mcc = res_obj.mon_check_command_lut[pk]
                                name = _mcc.name
                            res_list.push(
                                idx: pk
                                type: type
                                name: name
                                info: info
                                selected: false
                            )
                    defer.resolve(res_list)
            )
        else
            defer.resolve(res_list)
        defer.promise.then(
            (res_list) ->
                $scope.struct.data_ready = true
                $scope.struct.selection_supported = $scope.icsw_category.full_name.split("/")[1] != "location"
                $scope.struct.contents.length = 0
                for entry in _.orderBy(res_list, ["type", "name"], ["asc", "asc"])
                    $scope.struct.contents.push(entry)
        )

    _update_selected = () ->
        $scope.struct.selected = (entry for entry in $scope.struct.contents when entry.selected).length

    $scope.clear_selection = ($event) ->
        for entry in $scope.struct.contents
            entry.selected = false
        _update_selected()

    $scope.remove_selection= ($event) ->
        _sel_idx = (entry.idx for entry in $scope.struct.contents when entry.selected)
        if _sel_idx.length > 1
            _sel_str = "#{_sel_idx.length} selected objects"
        else
            _sel_str = "selected object"
        icswToolsSimpleModalService(
            "Really remote #{_sel_str} from category #{$scope.icsw_category.full_name} ?"
        ).then(
            (ok) ->
                blockUI.start()
                icswConfigCategoryModifyCall(
                    _sel_idx
                    [$scope.icsw_category]
                    false
                ).then(
                    (res) ->
                        blockUI.stop()
                )
        )

    $scope.change_selection = ($event) ->
        $timeout(
            () ->
                _update_selected()
            0
        )

    # watcher for current category
    $scope.$watch(
        "icsw_category",
        (new_val) ->
            if new_val
                $scope.struct.enabled = true
                update()
            else
                $scope.struct.enabled = false
                $scope.struct.data_ready = false
        # hm, to be improved...
        true
    )
]).service("icswCatSelectionTreeService",
[
    "icswReactTreeConfig",
(
    icswReactTreeConfig
) ->

    {span} = React.DOM
    class icswCatSelectionTree extends icswReactTreeConfig
        constructor: (@scope, args) ->
            @mode = args.mode
            if @mode == "obj"
                @num_objects = args.object_list.length
            else
                @num_objects = 0
            delete args.mode
            delete args.object_list
            super(args)
            # valid entries for the selected subtree
            @mode_entries = []
            @subtree = ""
            @clear_tree()

        clear_tree: () =>
            @lut = {}

        create_mode_entries: (mode, cat_tree) =>
            @subtree = mode
            @mode_entries.length = []
            for entry in cat_tree.list
                if entry.depth < 1 or entry.full_name.split("/")[1] == mode
                    @mode_entries.push(entry)

        hide_unused_entries: (useable_idxs, cat_tree) =>
            _full_list = (entry.idx for entry in @mode_entries when entry.depth < 2)
            # mark all used up to parent
            for _idx in useable_idxs
                # speedup
                if _idx not in _full_list
                    _full_list.push(_idx)
                    _p = cat_tree.lut[_idx]
                    while _p.parent
                        _p = cat_tree.lut[_p.parent]
                        _full_list.push(_p.idx)
            # make unique
            _full_list = _.uniq(_full_list)
            # filter mode entries
            @mode_entries = (entry for entry in @mode_entries when entry.idx in _full_list)

        get_name : (t_entry) =>
            obj = t_entry.obj
            if obj.depth
                if obj.comment
                    r_info = "#{obj.name} (#{obj.comment})"
                else
                    r_info = obj.name
                if @mode == "obj"
                    num_sel = t_entry.$match_pks.length
                    # console.log num_sel, @num_objects
                    if num_sel and @num_objects > 1
                        r_info = "#{r_info}, #{num_sel} of #{@num_objects}"
                    # if obj.num_refs
                    #    r_info = "#{r_info}, total references=#{obj.num_refs}"
            else
                r_info = "TOP"
            return r_info

        node_search: (t_entry, s_re) =>
            return s_re.test(t_entry.obj.name)

        get_selected_cat_pks: () =>
            return @get_selected(
                (node) ->
                    if node.selected
                        return [node.obj.idx]
                    else
                        return []
            )

        get_post_view_element: (t_entry) ->
            obj = t_entry.obj
            _r_obj = []
            if @mode == "obj" and obj.depth > 0
                num_sel = t_entry.$match_pks.length
                if num_sel
                    _r_obj.push(
                        span(
                            {
                                key: "num.refs"
                                className: "label label-success"
                            }
                            "#{num_sel} refs"
                        )
                    )
                if obj.num_refs
                    _r_obj.push(
                        span(
                            {
                                key: "num.refst"
                                className: "label label-danger"
                            }
                            "#{obj.num_refs} total"
                        )
                    )
            return _r_obj

        get_pre_view_element: (entry) =>
            _r_list = []
            if @subtree == "device" and entry.obj.asset
                _r_list.push(
                    span(
                        {
                            key: "is_asset"
                            className: "label label-info"
                            title: "Is an Asset category"
                        }
                        "Asset"
                    )
                )
                _r_list.push(" ")
            if entry._element_count
                _r_list.push(
                    span(
                        {
                            key: "_pve"
                            className: "label label-default"
                            title: "Devices selected"
                        }
                        "#{entry._element_count}"
                    )
                )
            return _r_list

        selection_changed: (entry) =>
            # console.log "SC"
            sel_list = @get_selected_cat_pks()
            @scope.new_selection(entry, sel_list)
            
        selection_changed_by_search: () =>
            sel_list = @get_selected_cat_pks()
            @scope.new_selection(undefined, sel_list)
            
        handle_click: ($event, entry) =>
            @clear_active()
            entry.set_active(!entry.active)
            if entry.obj.depth > 0
                @scope.click_category(entry.obj)

]).directive("icswConfigCategoryTreeSelect",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.config.category.tree.select")
        scope:
            # undefined, single object or list of objects (device, config or mon_check_command)
            edit_obj: "=editObj"
            # subtree, config, category, ...
            sub_tree: "=icswSubTree"
            # connect element for pipelining
            con_element: "=icswConnectElement"
            # filter: "=icswLivestatusFilter"
            # monitoring data for pipelining
            mon_data: "=icswMonitoringData"
            # to signal selected category, callback function
            selected_cat: "&icswSelectedCategory"
            # mode
            mode: "@icswMode"
            # optional assetfilter
            icsw_asset_filter: "=icswAssetFilter"
        controller: "icswConfigCategoryTreeSelectCtrl"
        link : (scope, el, attrs) ->
            if attrs.icswAssetFilter?
                _as_filter = scope.icsw_asset_filter
            else
                _as_filter = false
            scope.set_mode_and_tree_and_filter(scope.mode, scope.sub_tree, _as_filter)
    }
]).controller("icswConfigCategoryTreeSelectCtrl",
[
    "$scope", "$templateCache", "icswCatSelectionTreeService", "icswConfigTreeService", "$q",
    "icswCategoryTreeService", "icswAccessLevelService", "blockUI", "icswSimpleAjaxCall",
    "ICSW_URLS", "icswDeviceTreeService", "$rootScope", "ICSW_SIGNALS", "icswBaseCategoryTree",
    "icswConfigCategoryModifyCall",
(
    $scope, $templateCache, icswCatSelectionTreeService, icswConfigTreeService, $q,
    icswCategoryTreeService, icswAccessLevelService, blockUI, icswSimpleAjaxCall,
    ICSW_URLS, icswDeviceTreeService, $rootScope, ICSW_SIGNALS, icswBaseCategoryTree,
    icswConfigCategoryModifyCall,
) ->
    $scope.struct = {
        # object list
        objects: []
        # mode, one of
        # obj ...... set categories for one or more objects
        # filter ... work as filter for livestatus
        mode: undefined
        # asset filter, allow only asset device categories
        asset_filter: false
        # categore tree (display)
        disp_cat_tree: undefined
        # tree is ready
        tree_ready: false
        # category tree (data)
        cat_tree: undefined
        # monitoring data for filter mode
        mon_data: undefined
        # current selection
        current_selection: null
        # new (== target) selection
        new_selection: null
        # selection changed
        sel_changed: false
    }

    # selected category, used in directive
    # $scope.selected_cat = null

    # deregister list
    dereg_list = []

    $scope.click_category = (entry) ->
        $scope.$apply(
            # console.log "CS"
            # console.log "x", entry
            $scope.selected_cat({entry: entry}) #  = entry
        )

    $scope.set_mode_and_tree_and_filter = (mode, sub_tree, asset_filter) ->
        # set modes and init structure
        $scope.struct.mode = mode
        $scope.struct.sub_tree = sub_tree
        $scope.struct.asset_filter = asset_filter
        console.assert(
            $scope.struct.sub_tree in [
                "mon", "config", "device", "location"
            ],
            "invalid sub_tree '#{$scope.struct.sub_tree}' in category tree"
        )
        console.assert(
            $scope.struct.mode in [
                "obj", "filter"
            ],
            "invalid mode '#{$scope.struct.mode}' in category tree"
        )
        # init objects
        if $scope.struct.mode == "obj"
            if not angular.isArray($scope.edit_obj)
                $scope.struct.objects = [$scope.edit_obj]
            else
                $scope.struct.objects = $scope.edit_obj
        else
            $scope.struct.objects = null

        icswCategoryTreeService.load($scope.$id).then(
            (tree) ->
                $scope.struct.cat_tree = tree
                init_tree()

        )

    init_tree = () ->
        # init tree after structures are loaded
        $scope.struct.disp_cat_tree = new icswCatSelectionTreeService(
            $scope
            {
                show_selection_buttons: $scope.struct.mode == "filter"
                # search field enabled
                search_field: $scope.struct.mode == "filter"
                # show_icons: false
                show_select: true
                show_descendants: true
                # show_childs: false
                name: "Category Select Tree"
                # mode
                mode: $scope.struct.mode
                # objects list
                object_list: $scope.struct.objects
            }
        )

        if $scope.struct.mode == "obj"
            # check rights
            _ct = $scope.struct.disp_cat_tree
            _ct.change_select = true
            # iterate
            for _dev in $scope.struct.objects
                if not icswAccessLevelService.acl_all(_dev, "backbone.device.change_category", 7)
                    _ct.change_select = false
                    break
            $scope.$watch(
                () ->
                    return $scope.edit_obj.idx
                (new_val) ->
                    if new_val? and $scope.struct.cat_tree?
                        build_tree()
                true
            )

        else if $scope.struct.mode == "filter"
            if $scope.sub_tree in ["mon", "device"]
                $scope.count_dict_name = "#{$scope.sub_tree}_cat_counters"
                $scope.cat_name = "used_#{$scope.sub_tree}_cats"
            else
                assert "Invalid sub_tree '#{$scope.sub_tree}' for filter mode"
            # available cats, used to automatically select new cats (from mon-data reload)
            $scope.$$available_cats = []
            $scope.con_element.new_data_notifier.promise.then(
                () ->
                () ->
                (new_data) =>
                    # console.log "cnrb"
                    $scope.struct.mon_data = new_data
                    build_tree()
            )

        console.log "SelTree init, mode is #{$scope.struct.mode}, subtree is #{$scope.struct.sub_tree}"
        $scope.struct.tree_ready = true
        # install change handler
        dereg_list.push(
            $rootScope.$on(ICSW_SIGNALS("ICSW_CATEGORY_TREE_CHANGED"), (event) ->
                build_tree()
            )
        )

        build_tree()

    $scope.$on("$destroy", () ->
        (_entry() for _entry in dereg_list)
    )

    send_selection_to_filter = (sel_cat) ->
        if $scope.$$previous_filter?
            if angular.toJson($scope.$$previous_filter) == angular.toJson(sel_cat)
                return
        $scope.$$previous_filter = sel_cat
        $scope.con_element.set_category_filter(sel_cat)

    build_tree = () ->
        # build tree, called when something changes

        # list of useable categories
        _dct = $scope.struct.disp_cat_tree

        _dct.create_mode_entries($scope.struct.sub_tree, $scope.struct.cat_tree)

        _useable_idxs = (entry.idx for entry in _dct.mode_entries when entry.useable)
        # console.log "u", _useable_idxs

        if $scope.struct.mode == "obj"
            # obj mode, modify categories of given object
            if $scope.edit_obj?
                # dictionary of cat_idx -> [dev_idx, ...] list
                sel_cat = {}
                for _obj in $scope.struct.objects
                    for _cat in _obj.categories
                        if _cat not of sel_cat
                            sel_cat[_cat] = []
                        sel_cat[_cat].push(_obj.idx)
                        sel_cat[_cat].sort()
            else
                sel_cat = {}
            $scope.struct.current_selection = _.cloneDeep(sel_cat)
            $scope.struct.new_selection = _.cloneDeep(sel_cat)
            $scope.struct.sel_changed = false
        else
            # icswLivestatusFilter set, only some categories selectable und those are preselected
            if $scope.$$previous_filter?
                if $scope.struct.mon_data?
                    _new_cats = _.difference($scope.struct.mon_data[$scope.cat_name], $scope.$$available_cats)
                    # store
                    $scope.$$available_cats = (entry for entry in $scope.struct.mon_data[$scope.cat_name])
                    if _new_cats.length
                        # autoselect new categories and send to filter
                        # send to filter list
                        _stf_list = _.uniq(_.union($scope.$$previous_filter, _new_cats))
                        if $scope.$$removed_by_stored_filter?
                            _stf_list = _.difference(_stf_list, $scope.$$removed_by_stored_filter)
                            $scope.$$removed_by_stored_filter = undefined
                        send_selection_to_filter(_stf_list)
                sel_cat = $scope.$$previous_filter
            else
                if $scope.struct.mon_data?
                    # not set, fetch filter data from con_element
                    sel_cat = $scope.struct.mon_data[$scope.cat_name].concat([0])
                    _stored_filter = $scope.con_element.get_category_filter()
                    if _stored_filter?
                        # apply stored filter
                        $scope.$$removed_by_stored_filter = _.difference(sel_cat, _stored_filter)
                        sel_cat = _.intersection(_stored_filter, sel_cat)
                    # push category selection list
                    send_selection_to_filter(sel_cat)
                else
                    # mon_data no loaded
                    sel_cat = []
            # useable are only the categories present in the current dataset
            if $scope.struct.mon_data?
                _useable_idxs = _.intersection(_useable_idxs, $scope.struct.mon_data[$scope.cat_name])
                # further reduce mode entries by filtering non-useable entries
                _dct.hide_unused_entries(_useable_idxs, $scope.struct.cat_tree)

        if _dct.root_nodes.length
            _to_expand = []
            _dct.iter(
                (node) ->
                    if node.expand
                        _to_expand.push(node.obj.idx)
            )
        else
            _to_expand = (entry.idx for entry in $scope.struct.cat_tree.list when entry.depth < 2)

        _dct.clear_root_nodes()
        _dct.clear_tree()
        if $scope.struct.mode == "filter"
            # add uncategorized entry
            if false
                dummy_entry = _dct.create_node(
                    folder: false
                    obj: {
                        idx: 0
                        depth: 1
                        comment: "entries without category"
                        name: "N/A"
                        full_name: "N/A"
                    }
                    selected: 0 in sel_cat
                    show_select: true
                    _element_count: 0
                )
            dummy_entry = {
                idx: 0
                depth: 1
                comment: "entries without category"
                name: "N/A"
                full_name: "N/A"
            }
            # _dct.lut[dummy_entry.obj.idx] = dummy_entry
            # init
            _obj_pks = []
        else
            dummy_entry = undefined
            _obj_pks = (_obj.idx for _obj in $scope.struct.objects)

        # step 1: build list of tree
        helper_tree = new icswBaseCategoryTree("idx", "parent")
        for entry in _dct.mode_entries
            # number of element in related counter dict
            _num_el = 0
            if $scope.struct.mode == "filter"
                _sel = entry.idx in sel_cat
                # list of matching device pks, empty for filter mode
                _match_pks = []
                if $scope.struct.mon_data? and entry.idx of $scope.struct.mon_data[$scope.count_dict_name]
                    _num_el = $scope.struct.mon_data[$scope.count_dict_name][entry.idx]
            else
                if entry.idx of sel_cat
                    # only selected when all devices are selected
                    _sel = sel_cat[entry.idx].length == $scope.struct.objects.length
                else
                    _sel = false
                # list of matching device pks, not empty for obj (object) mode
                _match_pks = (_val for _val in entry.reference_dict.device when _val in _obj_pks)
                _match_pks.sort()
            # show selection button ?
            _show_select = entry.idx in _useable_idxs and entry.depth > 1
            if $scope.struct.asset_filter and $scope.struct.mode == "obj" and $scope.struct.sub_tree == "device" and not entry.asset
                _show_select = false

            #t_entry = _dct.create_node(
            #    folder: false
            #    obj: entry
            #    expand: entry.idx in _to_expand
            #    selected: _sel
            #    show_select: _show_select
            #    _element_count: _num_el
            #)
            # copy matching pks to tree entry (NOT entry because entry is global)
            # t_entry.$match_pks = (_v for _v in _match_pks)
            ms = helper_tree.feed(
                entry
                {
                    expand: entry.idx in _to_expand
                    selected: _sel
                    show_select: _show_select
                    _element_count: _num_el
                    $match_pks: (_v for _v in _match_pks)
                }
            )
            if ms.root_node
                ms.flags.show_select = false
                if dummy_entry?
                    helper_tree.add_to_parent(ms, helper_tree.get_meta_struct(dummy_entry, {selected: 0 in sel_cat, show_select: true, _element_count: 0, $match_pks: []}))
            #_dct.lut[entry.idx] = t_entry
            #if entry.parent and entry.parent of _dct.lut
            #    _dct.lut[entry.parent].add_child(t_entry)
            #else
            #    # hide selection from root nodes
            #    t_entry.show_select = false
            #    _dct.add_root_node(t_entry)
            #    if dummy_entry?
            #        # add dummy at first (if defined)
            #        _dct.lut[entry.idx].add_child(dummy_entry)
        if $scope.struct.mode == "obj" and $scope.struct.sub_tree == "device" and $scope.struct.asset_filter
            helper_tree.remove_nodes(
                (entry) ->
                    return not entry.struct.asset
            )
        for _node in helper_tree.get_nodes()
            t_entry = _dct.create_node(
                folder: false
                obj: _node.struct
                expand: _node.struct.idx in _to_expand
                selected: _node.flags.selected
                show_select: _node.flags.show_select
                _element_count: _node.flags._element_count
                $match_pks: _node.flags.$match_pks
            )
            _dct.lut[_node.struct.idx] = t_entry
            if _node.root_node
                _dct.add_root_node(t_entry)
            else
                _dct.lut[_node.parent.struct.idx].add_child(t_entry)
        _dct.show_selected(true)

    $scope.cancel_it = ($event) ->
        # cancel selection, reset to original one
        sel_cat = $scope.struct.current_selection
        for _obj in $scope.struct.objects
            _obj.categories.length = 0
            for _cat_idx, _obj_idxs of sel_cat
                if _obj.idx in _obj_idxs
                    _obj.categories.push(_cat_idx)
        $scope.struct.sel_changed = false
        build_tree()

    $scope.modify_it = ($event) ->
        # save selection to server
        # build change list
        change_list = []
        for cat_idx, _new_sel of $scope.struct.new_selection
            if cat_idx of $scope.struct.current_selection
                _prev_sel = $scope.struct.current_selection[cat_idx]
            else
                _prev_sel = []
            if not _.isEqual(_prev_sel, _new_sel)
                _cat = $scope.struct.cat_tree.lut[cat_idx]
                _to_add = (_idx for _idx in _new_sel when _idx not in _prev_sel)
                _to_remove = (_idx for _idx in _prev_sel when _idx not in _new_sel)
                if _to_add.length
                    change_list.push([true, _cat, _to_add])
                if _to_remove.length
                    change_list.push([false, _cat, _to_remove])
        if change_list.length
            blockUI.start()
            $q.all(
                (
                    icswConfigCategoryModifyCall(
                        c_entry[2]
                        [c_entry[1]]
                        c_entry[0]
                    ) for c_entry in change_list
                )
            ).then(
                (done) ->
                    blockUI.stop()
                    # build_tree is called via $rootScope signal

            )

    $scope.new_selection = (t_entry, new_sel) ->
        # console.log "S", t_entry, new_sel
        if $scope.struct.mode == "obj"
            # console.log "C", $scope.struct.current_selection, $scope.struct.new_selection
            # console.log _.isEqual($scope.struct.current_selection, $scope.struct.new_selection)
            if t_entry.obj.idx not of $scope.struct.new_selection
                $scope.struct.new_selection[t_entry.obj.idx] = []
            _sel_s = $scope.struct.new_selection[t_entry.obj.idx]
            for _obj in $scope.struct.objects
                if t_entry.selected
                    # add
                    if _obj.idx not in _sel_s
                        _sel_s.push(_obj.idx)
                else
                    # remove
                    _.remove(_sel_s, (entry) => return entry == _obj.idx)
            _sel_s.sort()
            $scope.struct.sel_changed = not _.isEqual($scope.struct.current_selection, $scope.struct.new_selection)
            # now handled by modify_it call
            # blockUI.start()
            # icswConfigCategoryModifyCall(
            #     (_entry.idx for _entry in $scope.struct.objects)
            #     [t_entry.obj]
            #     t_entry.selected
            # ).then(
            #     (res) ->
            #         blockUI.stop()
            #         # build_tree is called via $rootScope signal
            # )
        else
            send_selection_to_filter(new_sel)
])
