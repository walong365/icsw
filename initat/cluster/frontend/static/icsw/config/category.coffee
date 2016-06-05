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
    "icswTreeConfig",
(
    icswTreeConfig
) ->
    class icswConfigCategoryDisplayTree extends icswTreeConfig
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
            scope.icsw_config_object.scope = scope
            scope.tree = scope.icsw_config_object.tree
            scope.dn_tree = scope.icsw_config_object.dn_tree
            scope.mode = scope.icsw_config_object.mode
            scope.mode_is_location = scope.mode == "location"
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
    "$q", "icswAcessLevelService", "blockUI", "icswTools", "ICSW_URLS", "icswConfigCategoryDisplayTree",
    "icswSimpleAjaxCall", "toaster",
    "icswToolsSimpleModalService", "icswCategoryTreeService", "icswComplexModalService",
    "icswCategoryBackup", "icswInfoModalService", "ICSW_SIGNALS",
(
    $scope, $compile, $filter, $templateCache, Restangular, $timeout, $rootScope,
    $q, icswAcessLevelService, blockUI, icswTools, ICSW_URLS, icswConfigCategoryDisplayTree,
    icswSimpleAjaxCall, toaster,
    icswToolsSimpleModalService,icswCategoryTreeService, icswComplexModalService,
    icswCategoryBackup, icswInfoModalService, ICSW_SIGNALS
) ->
    $scope.struct = {}
    $scope.reload = () ->
        $scope.dn_tree = new icswConfigCategoryDisplayTree($scope, {})
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
            scope.$watch(
                "icsw_category",
                (new_val) ->
                    if new_val
                        scope.enabled = true
                        update()
                    else
                        scope.enabled = false
                        scope.data_ready = false
                # hm, to be improved...
                true
            )
    }
]).service("icswCatSelectionTreeService",
[
    "icswReactTreeConfig",
(
    icswReactTreeConfig
) ->

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
            @clear_tree()

        clear_tree: () =>
            @lut = {}

        create_mode_entries: (mode, cat_tree) =>
            @mode_entries.length = []
            for entry in cat_tree.list
                if entry.depth < 1 or entry.full_name.split("/")[1] == mode
                    @mode_entries.push(entry)

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
                    if obj.num_refs
                        r_info = "#{r_info}, total references=#{obj.num_refs}"
            else
                r_info = "TOP"
            return r_info


        get_selected_cat_pks: () =>
            return @get_selected(
                (node) ->
                    if node.selected
                        return [node.obj.idx]
                    else
                        return []
            )

        selection_changed: (entry) =>
            console.log "SC"
            sel_list = @get_selected_cat_pks()
            @scope.new_selection(entry, sel_list)

        handle_click: ($event, entry) =>
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
        template: "<icsw-react-tree ng-if='struct.tree_ready' icsw-tree-config='struct.disp_cat_tree'></icsw-react-tree>"
        scope:
            # undefined, single object or list of objects (device, config or mon_check_command)
            edit_obj: "=editObj"
            # subtree, config, category, ...
            sub_tree: "=icswSubTree"
            # filter for pipelining
            filter: "=icswLivestatusFilter"
            # monitoring data for pipelining
            mon_data: "=icswMonitoringData"
            # to signal selected category, callback function
            selected_cat: "&icswSelectedCategory"
            # mode
            mode: "@icswMode"
        controller: "icswConfigCategoryTreeSelectCtrl"
        link : (scope, el, attrs) ->
            scope.set_mode_and_tree(scope.mode, scope.sub_tree)
    }
]).controller("icswConfigCategoryTreeSelectCtrl",
[
    "$scope", "$templateCache", "icswCatSelectionTreeService", "icswConfigTreeService", "$q",
    "icswCategoryTreeService", "icswAcessLevelService", "blockUI", "icswSimpleAjaxCall",
    "ICSW_URLS", "icswDeviceTreeService", "$rootScope", "ICSW_SIGNALS",
(
    $scope, $templateCache, icswCatSelectionTreeService, icswConfigTreeService, $q,
    icswCategoryTreeService, icswAcessLevelService, blockUI, icswSimpleAjaxCall,
    ICSW_URLS, icswDeviceTreeService, $rootScope, ICSW_SIGNALS,
) ->
    $scope.struct = {
        # object list
        objects: []
        # mode, one of
        # obj ...... set categories for one or more objects
        # filter ... work as filter for livestatus
        mode: undefined
        # categore tree (display)
        disp_cat_tree: undefined
        # tree is ready
        tree_ready: false
        # category tree (data)
        cat_tree: undefined
    }

    # selected category, used in directive
    # $scope.selected_cat = null

    # deregister list
    dereg_list = []

    $scope.click_category = (entry) ->
        $scope.$apply(
            # console.log "CS"
            console.log "x", entry
            $scope.selected_cat({entry: entry}) #  = entry
        )

    $scope.set_mode_and_tree = (mode, sub_tree) ->
        # set modes and init structure
        $scope.struct.mode = mode
        $scope.struct.sub_tree = sub_tree
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
                show_selection_buttons: false
                # show_icons: false
                show_select: true
                show_descendants: true
                # show_childs: false
                name: "CategorySelectTree"
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
                if not icswAcessLevelService.acl_all(_dev, "backbone.device.change_category", 7)
                    _ct.change_select = false
                    break
            $scope.$watch(
                "edit_obj"
                (new_val) ->
                    if new_val? and $scope.struct.cat_tree?
                        build_tree()
                true
            )

        else if $scope.struct.mode == "filter"
            # available cats, used to automatically select new cats (from mon-data reload)
            $scope.$$available_cats = []
            $scope.filter.install_category_filter()
            $scope.filter.change_notifier.promise.then(
                () ->
                () ->
                (notify) =>
                    console.log "cnrb"
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
            if $scope.$$previous_filter == sel_cat
                console.log "same filter"
                return
        $scope.$$previous_filter = sel_cat
        $scope.filter.set_category_filter(sel_cat)

    build_tree = () ->
        # build tree, called when something changes

        # list of useable categories

        $scope.struct.disp_cat_tree.create_mode_entries($scope.struct.sub_tree, $scope.struct.cat_tree)

        _useable_idxs = (entry.idx for entry in $scope.struct.disp_cat_tree.mode_entries when entry.useable)
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
            else
                sel_cat = {}
        else
            # icswLivestatusFilter set, only some categories selectable und those are preselected
            if $scope.$$previous_filter?
                if $scope.mon_data?
                    _new_cats = _.difference($scope.mon_data.used_cats, $scope.$$available_cats)
                    # store
                    $scope.$$available_cats = (entry for entry in $scope.mon_data.used_cats)
                    if _new_cats.length
                        # autoselect new categories and send to filter
                        send_selection_to_filter(_.uniq(_.union($scope.$$previous_filter, _new_cats)))
                sel_cat = $scope.$$previous_filter
            else
                if $scope.mon_data?
                    sel_cat = $scope.mon_data.used_cats.concat([0])
                    # push category selection list
                    send_selection_to_filter(sel_cat)
                else
                    # mon_data no loaded
                    sel_cat = []
            # useable are only the categories present in the current dataset
            if $scope.mon_data?
                _useable_idxs =  _.intersection(_useable_idxs, $scope.mon_data.used_cats)

        if $scope.struct.disp_cat_tree.root_nodes.length
            _to_expand = []
            $scope.struct.disp_cat_tree.iter(
                (node) ->
                    if node.expand
                        _to_expand.push(node.obj.idx)
            )
        else
            _to_expand = (entry.idx for entry in $scope.struct.cat_tree.list when entry.depth < 2)

        $scope.struct.disp_cat_tree.clear_root_nodes()
        $scope.struct.disp_cat_tree.clear_tree()
        if $scope.struct.mode == "filter"
            # add uncategorized entry
            dummy_entry = $scope.struct.disp_cat_tree.create_node(
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
            )
            $scope.struct.disp_cat_tree.lut[dummy_entry.obj.idx] = dummy_entry
            # init
            _obj_pks = []
        else
            dummy_entry = undefined
            _obj_pks = (_obj.idx for _obj in $scope.struct.objects)

        # console.log "pks=", _obj_pks
        for entry in $scope.struct.disp_cat_tree.mode_entries
            if $scope.struct.mode == "filter"
                _sel = entry.idx in sel_cat
                _match_pks = []
            else
                if entry.idx of sel_cat
                    # only selected when all devices are selected
                    _sel = sel_cat[entry.idx].length == $scope.struct.objects.length
                else
                    _sel = false
                _match_pks = (_val for _val in entry.reference_dict.device when _val in _obj_pks)
                _match_pks.sort()
            t_entry = $scope.struct.disp_cat_tree.create_node(
                folder: false
                obj: entry
                expand: entry.idx in _to_expand
                selected: _sel
                show_select: entry.idx in _useable_idxs and entry.depth > 1
            )
            # copy matching pks to tree entry (NOT entry because entry is global)
            t_entry.$match_pks = (_v for _v in _match_pks)
            $scope.struct.disp_cat_tree.lut[entry.idx] = t_entry
            if entry.parent and entry.parent of $scope.struct.disp_cat_tree.lut
                $scope.struct.disp_cat_tree.lut[entry.parent].add_child(t_entry)
            else
                # hide selection from root nodes
                t_entry.show_select = false
                $scope.struct.disp_cat_tree.add_root_node(t_entry)
                if dummy_entry?
                    # add dummy at first (if defined)
                    $scope.struct.disp_cat_tree.lut[entry.idx].add_child(dummy_entry)
        # console.log "*", $scope.cat_tree.lut
        $scope.struct.disp_cat_tree.show_selected(true)

    $scope.new_selection = (t_entry, new_sel) ->
        # console.log "S", t_entry, new_sel
        if $scope.struct.mode == "obj"
            blockUI.start()
            cat = t_entry.obj
            icswSimpleAjaxCall(
                url: ICSW_URLS.BASE_CHANGE_CATEGORY
                data:
                    obj_pks: angular.toJson((_entry.idx for _entry in $scope.struct.objects))
                    cat_pks: angular.toJson([cat.idx])
                    set: if t_entry.selected then "1" else "0"
            ).then(
                (xml) ->
                    # see code in location.coffee
                    change_dict = angular.fromJson($(xml).find("value[name='changes']").text())
                    _wait = $q.defer()
                    if $scope.sub_tree in ["config", "mon"]
                        icswConfigTreeService.load($scope.$id).then(
                            (config_tree) ->
                                if $scope.sub_tree == "config"
                                    for [obj_idx, cat_idx] in change_dict.added
                                        config_tree.add_category_to_config_by_pk(obj_idx, cat_idx)
                                    for [obj_idx, cat_idx] in change_dict.removed
                                        config_tree.remove_category_from_config_by_pk(obj_idx, cat_idx)
                                else
                                    for [obj_idx, cat_idx] in change_dict.added
                                        config_tree.add_category_to_mcc_by_pk(obj_idx, cat_idx)
                                    for [obj_idx, cat_idx] in change_dict.removed
                                        config_tree.remove_category_from_mcc_by_pk(obj_idx, cat_idx)
                                config_tree.update_category_tree()
                                _wait.resolve("done")
                        )
                    else
                        icswDeviceTreeService.load($scope.$id).then(
                            (device_tree) ->
                                # device or location
                                sync_pks = []
                                for [dev_idx, cat_idx] in change_dict.added
                                    device_tree.add_category_to_device_by_pk(dev_idx, cat_idx)
                                    if dev_idx not in sync_pks
                                        sync_pks.push(dev_idx)
                                for [dev_idx, cat_idx] in change_dict.removed
                                    device_tree.remove_category_from_device_by_pk(dev_idx, cat_idx)
                                    if dev_idx not in sync_pks
                                        sync_pks.push(dev_idx)
                                if sync_pks.length
                                    $scope.struct.cat_tree.sync_devices((device_tree.all_lut[_pk] for _pk in sync_pks))
                                _wait.resolve("done")
                        )
                    _wait.promise.then(
                        (done) ->
                            build_tree()
                            blockUI.stop()
                    )
            )
            # $scope.edit_obj.categories = new_sel
        else
            send_selection_to_filter(new_sel)
])
