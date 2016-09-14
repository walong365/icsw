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

# variable related module

device_variable_module = angular.module(
    "icsw.device.variables",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select"
    ]
).config(["icswRouteExtensionProvider", (icswRouteExtensionProvider) ->
    icswRouteExtensionProvider.add_route("main.devvars")
]).controller("icswConfigVarsCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular", "$q",
    "$uibModal", "ICSW_URLS", "icswDeviceConfigurationConfigVarTreeService",
    "icswSimpleAjaxCall",
(
    $scope, $compile, $filter, $templateCache, Restangular, $q,
    $uibModal, ICSW_URLS, icswDeviceConfigurationConfigVarTreeService,
    icswSimpleAjaxCall
) ->
    $scope.devvar_tree = new icswDeviceConfigurationConfigVarTreeService(
        $scope
        {
            show_selection_buttons: false
            show_select: false
            show_descendants: false
        }
    )
    $scope.var_filter = ""
    $scope.loaded = false
    $scope.struct = {
        # devices
        devsel_list: []
    }

    $scope.new_devsel = (_dev_sel) ->
        $scope.struct.devsel_list.length = 0
        for entry in _dev_sel
            if not entry.is_meta_device
                $scope.struct.devsel_list.push(entry)

    $scope.load_vars = () ->
        if not $scope.loaded
            $scope.loaded = true
            icswSimpleAjaxCall(
                url: ICSW_URLS.CONFIG_GET_DEVICE_CVARS
                data:
                    keys: angular.toJson((dev.idx for dev in $scope.struct.devsel_list))
            ).then(
                (xml) ->
                    $scope.set_tree_content($(xml).find("devices"))
            )

    $scope.set_tree_content = (in_xml) ->
        # console.log "in_xml=", in_xml[0]
        for dev_xml in in_xml.find("device")
            dev_xml = $(dev_xml)
            dev_entry = $scope.devvar_tree.create_node({folder: true, expand:true, obj:{"name" : dev_xml.attr("name"), "info_str": dev_xml.attr("info_str"), "state_level" : parseInt(dev_xml.attr("state_level"))}, _node_type:"d"})
            $scope.devvar_tree.add_root_node(dev_entry)
            for _xml in dev_xml.find("var_tuple_list").children()
                _xml = $(_xml)
                t_entry = $scope.devvar_tree.create_node(
                    folder: true
                    obj:
                        "key": _xml.attr("key")
                        "value": _xml.attr("value")
                    _node_type: "c"
                )
                dev_entry.add_child(t_entry)
                _xml.children().each (idx, _sv) ->
                    _sv = $(_sv)
                    t_entry.add_child(
                        $scope.devvar_tree.create_node(
                            folder: false
                            obj:
                                key: _sv.attr("key")
                                value: _sv.attr("value")
                            _node_type: "v"
                        )
                    )
        $scope.$digest()

    $scope.$watch("var_filter", (new_val) -> $scope.new_filter_set(new_val, true))

    $scope.new_filter_set = (new_val) ->
        if new_val
            try
                filter_re = new RegExp(new_val, "gi")
            catch
                filter_re = new RegExp("^$", "gi")
        else
            filter_re = new RegExp("^$", "gi")
        $scope.devvar_tree.iter(
            (entry, filter_re) ->
                cmp_name = if entry._node_type == "d" then entry.obj.name else entry.obj.key
                entry.set_selected(if cmp_name.match(filter_re) then true else false)
            filter_re
        )
        $scope.devvar_tree.show_selected(false)
]).directive("icswDeviceConfigurationVarOverview",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        scope: true
        restrict : "EA"
        template : $templateCache.get("icsw.device.configuration.var.overview")
        controller: "icswConfigVarsCtrl"
    }
]).service("icswDeviceConfigurationConfigVarTreeService",
[
    "icswReactTreeConfig",
(
    icswReactTreeConfig
) ->
    class device_config_var_tree extends icswReactTreeConfig
        constructor: (@scope, args) ->
            super(args)

        get_name_class: (t_entry) =>
            # override
            obj = t_entry.obj
            if obj.state_level?
                if obj.state_level == 40
                    return "text-danger"
                else if obj.state_level == 20
                    return "text-success"
                else
                    return "text-warning"
            else
                return ""

        get_name : (t_entry) ->
            obj = t_entry.obj
            if t_entry._node_type == "d"
                return "#{obj.name} (#{obj.info_str})"
            else
                if obj.value?
                    return "#{obj.key} = #{obj.value}"
                else
                    return obj.key
]).service("icswDeviceVariableListService",
[
    "$q", "Restangular", "icswCachingCall", "icswSimpleAjaxCall",
    "ICSW_URLS", "icswDeviceTreeService", "icswToolsSimpleModalService", "icswComplexModalService",
    "$compile", "$templateCache", "icswDeviceVariableBackup", "toaster", "blockUI",
(
    $q, Restangular, icswCachingCall, icswSimpleAjaxCall,
    ICSW_URLS, icswDeviceTreeService, icswToolsSimpleModalService, icswComplexModalService,
    $compile, $templateCache, icswDeviceVariableBackup, toaster, blockUI,
) ->
    create_or_edit = (scope, event, create, obj_or_parent) ->
        _dvst = scope.device_variable_scope_tree
        if create
            single_create = true
            if obj_or_parent
                device = obj_or_parent
                nv_idx = 0
                var_pf = "new_variable"
                var_name = var_pf
                while (true for entry in device.device_variable_set when entry.name == var_name).length > 0
                    nv_idx++
                    var_name = "#{var_pf}_#{nv_idx}"
                obj_or_parent = {
                    device: device.idx
                    name: var_name
                    var_type: "s"
                    _mon_var: null
                    inherit: true
                    device_variable_scope: _dvst.lut_by_name["normal"].idx
                }
            else
                single_create = false
                obj_or_parent = {
                    device: 0
                    name: "new_variable"
                    var_type: "s"
                    _mon_var: null
                    inherit: true
                    device_variable_scope: _dvst.lut_by_name["normal"].idx
                }
        else
            single_create = false
            dbu = new icswDeviceVariableBackup()
            dbu.create_backup(obj_or_parent)
        sub_scope = scope.$new(true)
        sub_scope.create = create
        sub_scope.device_variable_scope_tree = _dvst
        sub_scope.single_create = single_create
        sub_scope.mon_vars = []
        if single_create
            # fetch mon_vars
            icswSimpleAjaxCall(
                url: ICSW_URLS.MON_GET_MON_VARS
                data: {
                    device_pk: device.idx
                }
                dataType: "json"
            ).then(
                (json) ->
                    # add selections delayed
                    for entry in json
                        sub_scope.mon_vars.push(entry)
            )
            # install take_mon_var command
            sub_scope.take_mon_var = () ->
                if sub_scope.edit_obj._mon_var?
                    # copy monitoring var
                    _mon_var = sub_scope.edit_obj._mon_var
                    sub_scope.edit_obj.var_type = _mon_var.type
                    sub_scope.edit_obj.name = _mon_var.name
                    sub_scope.edit_obj.device_variable_scope = _dvst.lut_by_name["normal"].idx
                    sub_scope.edit_obj.inherit = false
                    if _mon_var.type == "i"
                        sub_scope.edit_obj.val_int = parseInt(_mon_var.value)
                    else
                        sub_scope.edit_obj.val_str = _mon_var.value
        # functions
        sub_scope.change_scope = () ->
            cur_scope = _dvst.lut[sub_scope.edit_obj.device_variable_scope]
            if cur_scope.dvs_allowed_name_set.length
                sub_scope.$$discrete_names = true
                sub_scope.$$possible_names = (entry.name for entry in cur_scope.dvs_allowed_name_set)
                sub_scope.edit_obj.name = sub_scope.$$possible_names[0]
            else 
                sub_scope.$$discrete_names = false
                sub_scope.$$possible_names = []

        sub_scope.change_name = () ->
            cur_scope = _dvst.lut[sub_scope.edit_obj.device_variable_scope]
            cur_var = (entry for entry in cur_scope.dvs_allowed_name_set when entry.name == sub_scope.edit_obj.name)
            if cur_var.length
                cur_var = cur_var[0]
                if cur_var.forced_type in ["i", "s"]
                    sub_scope.edit_obj.var_type = cur_var.forced_type

        sub_scope.edit_obj = obj_or_parent

        sub_scope.valid_var_types = [
            {short: "i", long: "integer"},
            {short: "s", long: "string"},
        ]
        # init fields
        sub_scope.change_scope()

        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.device.variable.form"))(sub_scope)
                title: "Device Variable"
                # css_class: "modal-wide"
                ok_label: if create then "Create" else "Modify"
                closable: true
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "")
                        d.reject("form not valid")
                    else
                        if create
                            if single_create
                                # single creation
                                scope.device_tree.create_device_variable(sub_scope.edit_obj, scope.helper).then(
                                    (new_conf) ->
                                        d.resolve("created")
                                    (notok) ->
                                        d.reject("not created")
                                )
                            else
                                # multi-var creation
                                wait_list = []
                                for dev in scope.devices
                                    local_var = angular.copy(sub_scope.edit_obj)
                                    local_var.device = dev.idx
                                    wait_list.push(scope.device_tree.create_device_variable(local_var, scope.helper))
                                $q.allSettled(wait_list).then(
                                    (result) ->
                                        d.resolve("created")
                                )
                        else
                            scope.device_tree.update_device_variable(sub_scope.edit_obj, scope.helper).then(
                                (new_var) ->
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
                sub_scope.$destroy()
        )

    return {
        fetch: (scope) ->
            # copy device list and references from icsw_config_object

            scope.helper = scope.icsw_config_object.helper
            scope.devices = scope.icsw_config_object.devices
            scope.device_tree = scope.icsw_config_object.device_tree
            scope.device_variable_scope_tree = scope.icsw_config_object.device_variable_scope_tree

            _list_defer = $q.defer()
            _list_defer.resolve(scope.devices)
            return _list_defer.promise

        toggle_expand: (obj) ->
            obj.$vars_expanded = not obj.$vars_expanded

        get_expand_class: (obj) ->
            if obj.$vars_expanded
                return "glyphicon glyphicon-chevron-down"
            else
                return "glyphicon glyphicon-chevron-right"

        # variable related calls
        variable_edit_ok: (d_var, device) ->
            return d_var.device == device.idx and d_var.is_public

        variable_delete_ok: (d_var, device) ->
            return d_var.device == device.idx and !d_var.protected

        variable_local_copy_ok: (d_var, device) ->
            return d_var.device != device.idx and d_var.local_copy_ok

        get_source: (d_var, device) ->
            if d_var.device == device.idx
                return "direct"
            else if d_var.$source == "m"
                return "group"
            else
                return "cluster"

        create_or_edit: (scope, event, create, obj_or_parent) ->
            create_or_edit(scope, event, create, obj_or_parent)

        delete: (scope, event, d_var) ->
            icswToolsSimpleModalService("Really delete Device Variable '#{d_var.name}' ?").then(
                () =>
                    blockUI.start()
                    scope.device_tree.delete_device_variable(d_var).then(
                        () ->
                            scope.helper.filter_device_variables()
                            blockUI.stop()
                        (error) ->
                            blockUI.stop()
                    )
            )

        special_fn: (scope, event, fn_name, d_var, device) ->
            if fn_name == "local_copy"
                new_var = angular.copy(d_var)
                new_var.device = device.idx
                blockUI.start()
                scope.device_tree.create_device_variable(new_var, scope.helper).then(
                    (new_conf) ->
                        blockUI.stop()
                    (notok) ->
                        blockUI.stop()
                )
            else if fn_name == "create_for_all"
                create_or_edit(scope, event, true, null)

    }
]).controller("icswDeviceVariableCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "$q", "$uibModal", "blockUI",
    "icswTools", "icswDeviceVariableListService", "icswDeviceVariableScopeTreeService",
    "icswDeviceTreeService", "icswDeviceTreeHelperService",
(
    $scope, $compile, $filter, $templateCache, $q, $uibModal, blockUI,
    icswTools, icswDeviceVariableListService, icswDeviceVariableScopeTreeService,
    icswDeviceTreeService, icswDeviceTreeHelperService,
) ->
    $scope.vars = {
        name_filter: ""
    }
    # struct to hand over to VarCtrl
    $scope.struct = {
        # devices
        devices: []
        # device tree
        device_tree: undefined
        # device variable scope tree
        device_variable_scope_tree: undefined
    }
    $scope.dataLoaded = false

    $scope.new_devsel = (devs) ->
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
                icswDeviceVariableScopeTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                device_tree = data[0]
                $scope.struct.device_variable_scope_tree = data[1]
                trace_devices =  device_tree.get_device_trace(devs)
                hs = icswDeviceTreeHelperService.create(device_tree, trace_devices)
                device_tree.enrich_devices(hs, ["variable_info"]).then(
                    (_done) ->
                        $scope.struct.devices.length = 0
                        for entry in devs
                            $scope.struct.devices.push(entry)
                        $scope.struct.device_tree = device_tree
                        $scope.struct.helper = hs
                        # console.log "****", $scope.devices
                        $scope.dataLoaded = true
                )
        )

    $scope.get_tr_class = (obj) ->
        if obj.is_cluster_device_group
            return "danger"
        else if obj.is_meta_device
            return "success"
        else
            return ""

    $scope.get_name = (obj) ->
        if obj.is_cluster_device_group
            return obj.full_name.slice(8) + " [ClusterGroup]"
        else if obj.is_meta_device
            return obj.full_name.slice(8) + " [Group]"
        else
            return obj.full_name

    $scope.new_filter_set = () ->
        $scope.struct.helper.set_var_filter($scope.vars.name_filter)

]).directive("icswDeviceVariableOverview",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.variable.overview")
        controller: "icswDeviceVariableCtrl"
    }
]).directive("icswDeviceVariableTable",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.variable.table")
        link : (scope, el, attrs) ->
            scope.device = scope.$eval(attrs["device"])
    }
]).directive("icswDeviceVariableHead",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.variable.head")
    }
]).directive("icswDeviceVariableRow",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.variable.row")
    }
]).directive("icswDeviceFixedScopeVarsOverview",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.fixed.scope.vars.overview")
        controller: "icswDeviceFixedScopeVarsOverviewCtrl"
        scope: {
            device: "=icswDevice"
        }
    }
]).controller("icswDeviceFixedScopeVarsOverviewCtrl",
[
    "$scope", "icswDeviceVariableScopeTreeService", "icswDeviceTreeService", "$q",
    "icswDeviceTreeHelperService", "icswComplexModalService", "$compile", "$templateCache",
(
    $scope, icswDeviceVariableScopeTreeService, icswDeviceTreeService, $q,
    icswDeviceTreeHelperService, icswComplexModalService, $compile, $templateCache,
) ->
    $scope.struct = {
        # device tree
        device_tree: undefined
        # helper object
        helper: undefined
        # devvarscope_tree
        dvs_tree: undefined
        # fixed variable helper
        fixed_var_helper: undefined
        # toggle: show / hide
        shown: false
    }

    _build_struct = (device) ->
        # device local vars
        if not $scope.struct.fixed_var_helper?
            $scope.struct.fixed_var_helper = $scope.struct.dvs_tree.build_fixed_variable_helper(device)
        else
            # only update
            $scope.struct.fixed_var_helper.update()

    icswDeviceTreeService.load($scope.id).then(
        (data) ->
            $scope.struct.device_tree = data
            trace_devices =  $scope.struct.device_tree.get_device_trace([$scope.device])
            $scope.struct.helper = icswDeviceTreeHelperService.create($scope.struct.device_tree, trace_devices)
            $q.all(
                [
                    icswDeviceVariableScopeTreeService.load($scope.$id)
                    $scope.struct.device_tree.enrich_devices(
                        $scope.struct.helper
                        [
                            "variable_info",
                        ]
                    )
                ]
            ).then(
                (data) ->
                    $scope.struct.dvs_tree = data[0]
                    _build_struct($scope.device)
            )
    )

    $scope.modify_fixed_scope = ($event, scope) ->
        sub_scope = $scope.$new(true)
        _struct = $scope.struct.fixed_var_helper.scope_struct_lut[scope.idx]
        # salt structure
        _slist = []
        for _struct in _struct.list
            if _struct.set
                _value = _struct.var.$var_value
            else
                _value = ""
            if _struct.def.forced_type == "i"
                _vt = "number"
            else if _struct.def.forced_type == "D"
                _vt = "date"
                if _struct.set
                    _value = moment(_struct.var.val_date).toDate()
            else
                _vt = "text"
            _struct.$$vt = _vt
            _struct.$$value = _value
            _struct.$$prev_value = _value
            _slist.push(_struct)
        sub_scope.var_struct = _slist

        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.device.inventory.modify"))(sub_scope)
                title: "Modify #{scope.name} vars"
                # css_class: "modal-wide"
                ok_label: "Modify"
                closable: true
                ok_callback: (modal) ->
                    d = $q.defer()
                    c_list = []
                    for entry in sub_scope.var_struct
                        if not entry.set
                            if !entry.$$prev_value and !entry.$$value
                                # not set, ignore
                                true
                            else
                                if entry.def.forced_type
                                    _type = entry.def.forced_type
                                else
                                    _type = "s"
                                # create new var
                                _new_var = {
                                    device: $scope.device.idx
                                    name: entry.def.name
                                    var_type: _type
                                    device_variable_scope: scope.idx
                                }
                                if _type == "s"
                                    _new_var.val_str = entry.$$value
                                else if _type == "i"
                                    _new_var.val_int = entry.$$value
                                else if _type == "D"
                                    _new_var.val_date = entry.$$value
                                c_list.push(
                                    $scope.struct.device_tree.create_device_variable(
                                        _new_var
                                        $scope.struct.helper
                                    )
                                )
                        else
                            if entry.var.var_type == "i"
                                entry.var.val_int = parseInt(entry.$$value)
                            else if entry.var.var_type == "D"
                                entry.var.val_date = entry.$$value
                            else
                                entry.var.val_str = entry.$$value
                            c_list.push(
                                $scope.struct.device_tree.update_device_variable(entry.var, $scope.struct.helper)
                            )
                    $q.allSettled(c_list).then(
                        (result) ->
                            if _.some(result, (entry) -> return entry.state == "rejected")
                                d.reject("not updated")
                            else
                                d.resolve("updated")
                    )
                    return d.promise
                cancel_callback: (modal) ->
                    # dbu.restore_backup($scope.edit_obj)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                sub_scope.$destroy()
                # recreate structure
                _build_struct($scope.device)
        )
]).directive("icswDeviceStaticAssetOverview",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.static.asset.overview")
        controller: "icswDeviceStaticAssetOverviewCtrl"
        scope: {
            device: "=icswDevice"
        }
    }
]).service("icswStaticAssetObject",
[
    "$q",
(
    $q,
) ->
    class icswStaticAssetObject
        constructor: (device) ->
            @device = device
            # console.log "d", @device
]).controller("icswDeviceStaticAssetOverviewCtrl",
[
    "$scope", "icswDeviceVariableScopeTreeService", "icswDeviceTreeService", "$q",
    "icswDeviceTreeHelperService", "icswComplexModalService", "$compile", "$templateCache",
    "icswStaticAssetTemplateTreeService", "blockUI", "ICSW_URLS", "Restangular",
    "icswUserService", "icswToolsSimpleModalService", "icswSimpleAjaxCall",
(
    $scope, icswDeviceVariableScopeTreeService, icswDeviceTreeService, $q,
    icswDeviceTreeHelperService, icswComplexModalService, $compile, $templateCache,
    icswStaticAssetTemplateTreeService, blockUI, ICSW_URLS, Restangular,
    icswUserService, icswToolsSimpleModalService, icswSimpleAjaxCall,
) ->
    $scope.struct = {
        # device tree
        device_tree: undefined
        # helper object
        helper: undefined
        # asset tree
        asset_tree: undefined
        # devvarscope_tree
        dvs_tree: undefined
        # device to work on
        device: undefined
        # device local asset struct tree
        asset_struct: undefined
        # user
        user: undefined
        # available assets (not set and enabled)
        num_available: 0
        # flag: shown or not
        shown: false
    }

    _reload_assets = () ->
        defer = $q.defer()
        $q.all(
            [
                icswDeviceVariableScopeTreeService.load($scope.$id)
                $scope.struct.device_tree.enrich_devices(
                    $scope.struct.helper
                    [
                        "variable_info",
                        "static_asset_info",
                    ]
                    true
                )
            ]
        ).then(
            (data) ->
                $scope.struct.dvs_tree = data[0]
                # build lut, template_idx -> device_asset
                $scope.struct.asset_struct = $scope.struct.asset_tree.build_asset_struct($scope.struct.device)
                defer.resolve("done")
        )
        return defer.promise

    $q.all(
        [
            icswDeviceTreeService.load($scope.id)
            icswStaticAssetTemplateTreeService.load($scope.$id)
            icswUserService.load($scope.$id)
        ]
    ).then(
        (data) ->
            $scope.struct.device = $scope.device
            $scope.struct.device_tree = data[0]
            $scope.struct.asset_tree = data[1]
            $scope.struct.user = data[2]

            trace_devices =  $scope.struct.device_tree.get_device_trace([$scope.struct.device])
            $scope.struct.helper = icswDeviceTreeHelperService.create($scope.struct.device_tree, trace_devices)
            _reload_assets()
    )

    $scope.delete_asset = ($event, asset) ->
        icswToolsSimpleModalService("Really delete static asset #{asset.$$static_asset_template.name} ?").then(
            (ok) ->
                blockUI.start()
                Restangular.restangularizeElement(null, asset, ICSW_URLS.ASSET_DEVICE_ASSET_DETAIL.slice(1).slice(0, -2))
                asset.remove().then(
                    (del) ->
                        _reload_assets().then(
                            (ok) ->
                                blockUI.stop()
                        )
                    (error) ->
                        blockUI.stop()
                )
        )

    $scope.add_assets = ($event) ->
        sub_scope = $scope.$new(true)
        sub_scope.asset_tree = $scope.struct.asset_tree
        unused_list = []

        for _us in $scope.struct.asset_struct.unused
            if _us.enabled
                unused_list.push(_us)
                # set create flag to false
                _us.$$create = false
        sub_scope.unused_list = _.orderBy(unused_list, ["name"], ["asc"])

        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.device.static.asset.add"))(sub_scope)
                title: "Add static templates"
                ok_label: "Add"
                closable: true
                ok_callback: (modal) ->
                    d = $q.defer()
                    _to_add = []
                    for _us in sub_scope.unused_list
                        if _us.$$create
                            _to_add.push(_us)
                    if _to_add.length
                        $q.all(
                            (
                                Restangular.all(ICSW_URLS.ASSET_DEVICE_ASSET_CALL.slice(1)).post(
                                    {
                                        device: $scope.struct.device.idx
                                        static_asset_template: _us.idx
                                        create_user: $scope.struct.user.user.idx
                                    }
                                )
                            ) for _us in _to_add
                        ).then(
                            (new_assets) ->
                                _reload_assets().then(
                                    (ok) ->
                                        blockUI.stop()
                                        d.resolve("done")
                                )
                        )
                    else
                        d.resolve("nothing to do")
                    return d.promise
                cancel_callback: (modal) ->
                    # dbu.restore_backup($scope.edit_obj)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                sub_scope.$destroy()
        )

    $scope.add_unused_fields = ($event, asset) ->
        sub_scope = $scope.$new(true)
        sub_scope.unused_fields = asset.$$unused_fields
        for _uf in sub_scope.unused_fields
            _uf.$$add = false
        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.device.static.asset.add.unused"))(sub_scope)
                title: "Add unused fields"
                ok_label: "Add"
                closable: true
                ok_callback: (modal) ->
                    d = $q.defer()
                    _to_add = []
                    for _fs in sub_scope.unused_fields
                        if _uf.$$add
                            _to_add.push(_uf.idx)
                    if _to_add.length
                        blockUI.start("adding unused fields")
                        Restangular.all(ICSW_URLS.ASSET_DEVICE_ASSET_ADD_UNUSED.slice(1)).post(
                            {
                                asset: asset.idx
                                fields: _to_add
                            }
                        ).then(
                            (new_assets) ->
                                _reload_assets().then(
                                    (ok) ->
                                        blockUI.stop()
                                        d.resolve("done")
                                )
                        )
                    else
                        d.resolve("nothing to do")
                    return d.promise
                cancel_callback: (modal) ->
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                sub_scope.$destroy()
        )


    $scope.modify_asset = ($event, asset) ->
        sub_scope = $scope.$new(true)
        sub_scope.asset = asset

        sub_scope.open_picker = ($event, picker_idx) ->
            sub_scope.datepicker_options.open[picker_idx] = true

        sub_scope.button_bar = {
            show: true
            now: {
                show: true
                text: 'Now'
            },
            today: {
                show: true
                text: 'Today'
            },
            close: {
                show: true
                text: 'Close'
            }
        }
        sub_scope.datepicker_options = {
            date_options: {
                format: "dd.MM.yyyy"
                formatYear: "yyyy"
                minDate: new Date(2000, 1, 1)
                startingDay: 1
                minMode: "day"
                datepickerMode: "day"
            }
            time_options: {
                showMeridian: false
            }
            open: {}
        }

        sub_scope.remove_field = ($event, field) ->
            icswToolsSimpleModalService("Really delete field '#{field.$$field.name}' ?").then(
                (ok) ->
                    blockUI.start()
                    $scope.struct.asset_tree.remove_device_asset_field(asset, field).then(
                        (done) ->
                            blockUI.stop()
                    )
            )
        # create backup values
        _bu_f = {}
        for _f in asset.staticassetfieldvalue_set
            _bu_f[_f.idx] = {
                "i": _f.value_int
                "s": _f.value_str
                "d": _f.value_date
                "t": _f.value_text
            }
            _f.$$default_date = moment(_f.value_date).toDate()
            sub_scope.datepicker_options.open[_f.idx] = false
        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.device.static.asset.modify"))(sub_scope)
                title: "Modify static template '#{asset.$$static_asset_template.name}'"
                ok_label: "modify"
                closable: true
                ok_callback: (modal) ->
                    d = $q.defer()
                    post_params = []
                    for _f in asset.staticassetfieldvalue_set
                        # cast back to string
                        _f.value_date = moment(_f.$$default_date).format("DD.MM.YYYY")
                        post_params.push(
                            {
                                "idx": _f.idx
                                "int": _f.value_int
                                "str": _f.value_str
                                "date": _f.value_date
                                "text": _f.value_text
                            }
                        )
                    icswSimpleAjaxCall(
                        {
                            url: ICSW_URLS.ASSET_DEVICE_ASSET_POST
                            data:
                                asset_data: angular.toJson(post_params)
                        }
                    ).then(
                        (res) ->
                            _reload_assets().then(
                                (ok) ->
                                    d.resolve("done")
                            )
                        (error) ->
                            d.reject("not ok")
                    )
                    return d.promise
                cancel_callback: (modal) ->
                    for _f in asset.staticassetfieldvalue_set
                        _f.value_int = _bu_f[_f.idx].i
                        _f.value_str = _bu_f[_f.idx].s
                        _f.value_date = _bu_f[_f.idx].d
                        _f.value_text = _bu_f[_f.idx].t
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                sub_scope.$destroy()
        )

])
