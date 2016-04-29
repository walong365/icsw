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
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters",
        "ui.select", "restangular", "uiGmapgoogle-maps", "angularFileUpload",
        "icsw.backend.category_tree",
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
]).service("icswConfigCategoryTreeService",
[
    "icswTreeConfig",
(
    icswTreeConfig
) ->
    class icswConfigCategoryTreeService extends icswTreeConfig
        constructor: (@scope, args) ->
            super(args)
            @show_selection_buttons = false
            @show_icons = false
            @show_select = false
            @show_descendants = true
            @show_childs = false
            @mode_entries = []
            @location_re = new RegExp("^/location/.*$")
            # link to config-service of a list controller
            @config_service = undefined
            @config_object = undefined

        create_mode_entries: (mode, cat_tree) =>
            @mode_entries.length = []
            for entry in cat_tree.list
                if entry.depth < 1 or entry.full_name.split("/")[1] == mode
                    @mode_entries.push(entry)

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

        handle_dblclick: (entry, event) =>
            cat = entry.obj
            if cat.depth
                @config_service.create_or_edit(@config_object.scope, event, false, cat)

        toggle_active_obj: (obj) =>
            node = @lut[obj.idx]
            if node.obj
                node.active = !node.active
                if node.active
                    @scope.selected_category = node.obj
                else
                    @scope.selected_category = null
                @show_active()
                @scope.update_active()

        handle_click: (entry, event) =>
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
            scope.icswConfigObject.scope = scope
            scope.tree = scope.icswConfigObject.tree
            scope.dn_tree = scope.icswConfigObject.dn_tree
            scope.mode = scope.icswConfigObject.mode
            scope.mode_is_location = scope.mode == "location"
            defer.resolve(scope.dn_tree.mode_entries)
            return defer.promise

        create_or_edit: (scope, event, create, obj_or_parent) ->
            if obj_or_parent?
                top_level = obj_or_parent.full_name.split("/")[1]
            else
                # for top-level creation
                top_level = scope.mode
            console.log "***", top_level, obj_or_parent
            if create
                _parent = (value for value in scope.dn_tree.mode_entries when value.depth == 1 and value.full_name.split("/")[1] == top_level)[0]
                _name = "new_#{top_level}_cat"
                useable: true
                was_unuseable: false
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

            console.log p_list
            sub_scope.valid_parents = p_list

            sub_scope.is_location = (obj) ->
                # called from formular code
                # full_name.match leads to infinite digest cycles
                return (obj.depth > 1) and top_level == "location"

            ok_label = if create then "Create" else "Modify"
            icswComplexModalService(
                {
                    message: $compile($templateCache.get("icsw.category.form"))(sub_scope)
                    title: "#{ok_label} Category entry '#{obj_or_parent.name}"
                    # css_class: "modal-wide"
                    ok_label: ok_label
                    closable: true
                    ok_callback: (modal) ->
                        d = $q.defer()
                        if sub_scope.form_data.$invalid
                            toaster.pop("warning", "form validation problem", "", 0)
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

                    delete_callback: (modal) ->
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
                scope.icswConfigObject.ctrl_scope.clear_active()

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
    "$q", "icswAcessLevelService", "blockUI", "icswTools", "ICSW_URLS", "icswConfigCategoryTreeService",
    "icswSimpleAjaxCall", "toaster",
    "icswToolsSimpleModalService", "icswCategoryTreeService", "icswComplexModalService",
    "icswCategoryBackup", "icswInfoModalService", "ICSW_SIGNALS",
(
    $scope, $compile, $filter, $templateCache, Restangular, $timeout, $rootScope,
    $q, icswAcessLevelService, blockUI, icswTools, ICSW_URLS, icswConfigCategoryTreeService,
    icswSimpleAjaxCall, toaster,
    icswToolsSimpleModalService,icswCategoryTreeService, icswComplexModalService,
    icswCategoryBackup, icswInfoModalService, ICSW_SIGNALS
) ->
    $scope.struct = {}
    $scope.reload = () ->
        $scope.dn_tree = new icswConfigCategoryTreeService($scope, {})
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
            t_entry = $scope.dn_tree.new_node(
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
    "Restangular", "ICSW_URLS", "icswConfigTreeService", "icswDeviceTreeService", "$q",
    "icswMonitoringBasicTreeService",
(
    Restangular, ICSW_URLS, icswConfigTreeService, icswDeviceTreeService, $q,
    icswMonitoringBasicTreeService,
) ->
    return {
        restrict: "EA"
        templateUrl: "icsw.config.category.contents_viewer"
        scope:
            icsw_category: '=icswCategory'
            # categoryName: '='
        link : (scope, elements, attrs) ->
            scope.enabled = false
            scope.data_ready = false
            update = () ->
                scope.data_ready = false
                _cat = scope.icsw_category
                _wait_list = []
                _ref_list = []
                # todo: add deviceselection
                _lut = {
                    config: icswConfigTreeService
                    device: icswDeviceTreeService
                    mon_check_command: icswMonitoringBasicTreeService
                    deviceselectipon: null
                }
                for key, refs of _cat.reference_dict
                    if refs.length
                        _ext_call = _lut[key]
                        if _ext_call
                            _wait_list.push(_ext_call.load(scope.$id))
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
                                    [subtype, info] = ["", ""]
                                    if key == "device"
                                        _dev = res_obj.all_lut[pk]
                                        name = _dev.full_name
                                        if _dev.is_meta_device
                                            subtype = "Group"
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
                                        type: key
                                        subtype: subtype
                                        name: name
                                        info: info
                                    )
                            defer.resolve(res_list)
                    )
                else
                    defer.resolve(res_list)
                defer.promise.then(
                    (res_list) ->
                        scope.data_ready = true
                        scope.contents = res_list
                )
            scope.$watch("icsw_category", (new_val) ->
                if new_val
                    scope.enabled = true
                    update()
                else
                    scope.enabled = false
                    scope.data_ready = false
            )
    }
])
