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
]).controller("icswDeviceVariableEditCtrl",
[
    "$scope", "device_variable_scope_tree", "create", "obj_or_parent",
    "icswDeviceVariableBackup", "icswSimpleAjaxCall", "ICSW_URLS", "icswComplexModalService",
    "toaster", "$q", "struct", "$compile", "$templateCache", "blockUI",
(
    $scope, device_variable_scope_tree, create, obj_or_parent,
    icswDeviceVariableBackup, icswSimpleAjaxCall, ICSW_URLS, icswComplexModalService,
    toaster, $q, struct, $compile, $templateCache, blockUI,
) ->
    $scope.device_variable_scope_tree = device_variable_scope_tree
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
                device_variable_scope: device_variable_scope_tree.lut_by_name["normal"].idx
            }
        else
            single_create = false
            obj_or_parent = {
                device: 0
                name: "new_variable"
                var_type: "s"
                _mon_var: null
                inherit: true
                device_variable_scope: device_variable_scope_tree.lut_by_name["normal"].idx
            }
    else
        single_create = false
        dbu = new icswDeviceVariableBackup()
        dbu.create_backup(obj_or_parent)

    $scope.valid_var_types = [
        {short: "i", long: "integer"},
        {short: "s", long: "string"},
    ]
    $scope.edit_obj = obj_or_parent
    $scope.create = create
    $scope.single_create = single_create
    $scope.mon_vars = []
    # init monitoring vars when single_create is True
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
                    $scope.mon_vars.push(entry)
        )
        # install take_mon_var command
        $scope.take_mon_var = () ->
            if $scope.edit_obj._mon_var?
                # copy monitoring var
                _mon_var = $scope.edit_obj._mon_var
                $scope.edit_obj.var_type = _mon_var.type
                $scope.edit_obj.name = _mon_var.name
                $scope.edit_obj.device_variable_scope = device_variable_scope_tree.lut_by_name["normal"].idx
                $scope.edit_obj.inherit = false
                if _mon_var.type == "i"
                    $scope.edit_obj.val_int = parseInt(_mon_var.value)
                else
                    $scope.edit_obj.val_str = _mon_var.value

    # functions

    $scope.change_scope = () ->
        cur_scope = device_variable_scope_tree.lut[$scope.edit_obj.device_variable_scope]
        if cur_scope.dvs_allowed_name_set.length
            $scope.$$discrete_names = true
            $scope.$$possible_names = (entry.name for entry in cur_scope.dvs_allowed_name_set)
            if $scope.edit_obj.name not in $scope.$$possible_names
                $scope.edit_obj.name = $scope.$$possible_names[0]
        else
            $scope.$$discrete_names = false
            $scope.$$possible_names = []

    $scope.change_name = () ->
        cur_scope = device_variable_scope_tree.lut[$scope.edit_obj.device_variable_scope]
        cur_var = (entry for entry in cur_scope.dvs_allowed_name_set when entry.name == $scope.edit_obj.name)
        if cur_var.length
            cur_var = cur_var[0]
            if cur_var.forced_type in ["i", "s"]
                $scope.edit_obj.var_type = cur_var.forced_type

    # init fields
    $scope.change_scope()

    icswComplexModalService(
        {
            message: $compile($templateCache.get("icsw.device.variable.form"))($scope)
            title: "Device Variable"
            # css_class: "modal-wide"
            ok_label: if create then "Create" else "Modify"
            closable: true
            ok_callback: (modal) ->
                d = $q.defer()
                if $scope.form_data.$invalid
                    toaster.pop("warning", "form validation problem", "")
                    d.reject("form not valid")
                else
                    save_defer = $q.defer()
                    blockUI.start("saving ...")
                    if create
                        if single_create
                            # single creation
                            struct.device_tree.create_device_variable($scope.edit_obj, struct.helper).then(
                                (new_conf) ->
                                    save_defer.resolve("created")
                                (notok) ->
                                    save_defer.reject("not created")
                            )
                        else
                            # multi-var creation
                            wait_list = []
                            for dev in struct.devices
                                local_var = angular.copy($scope.edit_obj)
                                local_var.device = dev.idx
                                wait_list.push(struct.device_tree.create_device_variable(local_var, struct.helper))
                            $q.allSettled(wait_list).then(
                                (result) ->
                                    save_defer.resolve("created")
                            )
                    else
                        struct.device_tree.update_device_variable($scope.edit_obj, struct.helper).then(
                            (new_var) ->
                                save_defer.resolve("updated")
                            (not_ok) ->
                                save_defer.reject("not updated")
                        )
                    save_defer.promise.then(
                        (ok) ->
                            blockUI.stop()
                            d.resolve(ok)
                        (notok) ->
                            blockUI.stop()
                            d.reject(notok)
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
            $scope.$destroy()
    )
]).controller("icswDeviceVariableCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "$q", "$uibModal", "blockUI",
    "icswTools", "icswDeviceVariableScopeTreeService", "icswTableFilterService",
    "icswDeviceTreeService", "icswDeviceTreeHelperService", "icswDeviceVariableBackup",
    "toaster", "icswComplexModalService", "icswSimpleAjaxCall", "ICSW_URLS", "$controller",
    "icswToolsSimpleModalService",
(
    $scope, $compile, $filter, $templateCache, $q, $uibModal, blockUI,
    icswTools, icswDeviceVariableScopeTreeService, icswTableFilterService,
    icswDeviceTreeService, icswDeviceTreeHelperService, icswDeviceVariableBackup,
    toaster, icswComplexModalService, icswSimpleAjaxCall, ICSW_URLS, $controller,
    icswToolsSimpleModalService,
) ->
    $scope.show_column = {}
    # struct to hand over to VarCtrl
    $scope.struct = {
        # devices
        devices: []
        # device tree
        device_tree: undefined
        # helper
        helper: undefined
        # device variable scope tree
        device_variable_scope_tree: undefined
        # data loaded
        data_loaded: false
        # filter instance
        filter: icswTableFilterService.get_instance()
        # variables to display
        var_list: []
    }

    $scope.struct.filter.add(
        "devices"
        "Select device"
        (entry, choice) ->
            if not choice.id
                return true
            else
                return entry.device == choice.value
    ).add_choice(0, "All Devices", null, true)
    $scope.struct.filter.add(
        "sources"
        "Select Source"
        (entry, choice) ->
            if not choice.id
                return true
            else
                return entry.$$source == choice.value
    ).add_choice(
        0, "All Sources", null, true
    ).add_choice(
        1, "Direct", "direct", false
    ).add_choice(
        2, "Group", "group", false
    ).add_choice(
        3, "System", "system", false
    )

    $scope.struct.filter.add(
        "scopes"
        "Select Scope"
        (entry, choice) ->
            if not choice.id
                return true
            else
                return entry.$$scope_name == choice.value
    ).add_choice(
        0, "All Scopes", null, true
    )
    $scope.struct.filter.add(
        "types"
        "Select Tyoe"
        (entry, choice) ->
            if not choice.id
                return true
            else
                return entry.$var_type == choice.value
    ).add_choice(
        0, "All Types", null, true
    )
    $scope.struct.filter.add(
        "creation"
        "Select creation"
        (entry, choice) ->
            if not choice.id
                return true
            else
                return entry.$$created_mom.isAfter(choice.value)
    ).add_choice(
        0, "All times", null, true
    ).add_choice(
        1, "1 month ago", moment.duration(1, "months"), false
    ).add_choice(
        2, "1 day ago", moment.duration(1, "days"), false
    ).add_choice(
        3, "1 hour ago", moment.duration(1, "hours"), false
    ).add_choice(
        4, "10 minutes ago", moment.duration(10, "minutes"), false
    )
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
                    (done) ->
                        $scope.struct.devices.length = 0
                        for entry in devs
                            $scope.struct.devices.push(entry)

                        $scope.struct.device_tree = device_tree
                        $scope.struct.helper = hs
                        # console.log "****", $scope.devices
                        $scope.struct.data_loaded = true
                        _build_var_list()
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

    _build_var_list = () ->
        _dnf = $scope.struct.filter.get("devices")
        _dnf.clear_choices()
        _dvsf = $scope.struct.filter.get("scopes")
        _dvsf.clear_choices()
        _dvtf = $scope.struct.filter.get("types")
        _dvtf.clear_choices()
        $scope.struct.var_list.length = 0
        for entry in $scope.struct.devices
            _dnf.add_choice(entry.idx, entry.$$print_name, entry.idx, false)
            for d_var in entry.device_variables
                $scope.struct.var_list.push(d_var)
                _dvsf.add_choice(d_var.device_variable_scope, d_var.$$scope_name, d_var.$$scope_name, false)
                _dvtf.add_choice(d_var.$var_type, d_var.$var_type, d_var.$var_type, false)
        _update_filter()


    _update_filter = () ->
        $scope.struct.filter.filter($scope.struct.var_list)

    $scope.struct.filter.notifier.promise.then(
        () ->
        () ->
        () ->
            _update_filter()
    )
    $scope.toggle_expand = ($event, obj) ->
        obj.$vars_expanded = not obj.$vars_expanded

    $scope.create_or_edit = ($event, create, obj_or_parent) ->
        _dvst = $scope.struct.device_variable_scope_tree
        sub_scope = $scope.$new(true)
        $controller(
            "icswDeviceVariableEditCtrl"
            {
                $scope: sub_scope
                device_variable_scope_tree: $scope.struct.device_variable_scope_tree
                create: create
                obj_or_parent: obj_or_parent
                struct: $scope.struct
            }
        )
        sub_scope.$on("$destroy", () ->
            _build_var_list()
        )

    $scope.$on("$destroy", () ->
        $scope.struct.filter.close()
    )

    $scope.delete = ($event, d_var) ->
        device = d_var.$$device
        icswToolsSimpleModalService("Really delete Device Variable '#{d_var.name}' on device '#{device.$$print_name}' ?").then(
            () =>
                blockUI.start()
                $scope.struct.device_tree.delete_device_variable(d_var, $scope.struct.helper).then(
                    () ->
                        _build_var_list()
                        blockUI.stop()
                    (error) ->
                        _build_var_list()
                        blockUI.stop()
                )
        )

    $scope.local_copy = ($event, d_var) ->
        device = d_var.$$device
        new_var = angular.copy(d_var)
        new_var.device = device.idx
        new_var.uuid = ""
        blockUI.start()
        $scope.struct.device_tree.create_device_variable(new_var, $scope.struct.helper).then(
            (new_conf) ->
                _build_var_list()
                blockUI.stop()
            (notok) ->
                _build_var_list()
                blockUI.stop()
        )

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

    $scope.toggle_only_set = ($event, var_scope) ->
        _build_struct($scope.device)

    $scope.modify_fixed_scope = ($event, scope) ->
        sub_scope = $scope.$new(true)
        _struct = $scope.struct.fixed_var_helper.var_scope_struct_lut[scope.idx]
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
        # flag: shown or not, no longer needed
        # shown: false
        # asset helper struct
        asset_struct: {}
    }

    load_assets = (reload) ->
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
                    reload
                )
            ]
        ).then(
            (data) ->
                $scope.struct.dvs_tree = data[0]
                $scope.struct.asset_tree.build_asset_struct($scope.struct.device, $scope.struct.asset_struct)
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
            load_assets(false)
    )

    $scope.delete_asset = ($event, asset) ->
        icswToolsSimpleModalService(
            "Really delete static asset '#{asset.$$static_asset_template.name}' from '#{$scope.struct.device.full_name}' ?"
        ).then(
            (ok) ->
                blockUI.start()
                Restangular.restangularizeElement(null, asset, ICSW_URLS.ASSET_DEVICE_ASSET_DETAIL.slice(1).slice(0, -2))
                asset.remove().then(
                    (del) ->
                        load_assets(true).then(
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

        unused_single_list = []
        for _us in $scope.struct.asset_struct.to_add_single
            unused_single_list.push(_us)
            # set create flag to false
            _us.$$create = false
        sub_scope.unused_single_list = _.orderBy(unused_single_list, ["name"], ["asc"])

        unused_multi_list = []
        for _us in $scope.struct.asset_struct.to_add_multi
            unused_multi_list.push(_us)
            # set create flag to false
            _us.$$create = false
            _us.$$count = 1
        sub_scope.unused_multi_list = _.orderBy(unused_multi_list, ["name"], ["asc"])

        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.device.static.asset.add"))(sub_scope)
                title: "Add static templates"
                ok_label: "Add"
                closable: true
                ok_callback: (modal) ->
                    d = $q.defer()
                    _to_add = []
                    for _us in sub_scope.unused_single_list
                        if _us.$$create
                            _to_add.push(_us)
                    for _us in sub_scope.unused_multi_list
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
                                        count: _us.$$count
                                    }
                                )
                            ) for _us in _to_add
                        ).then(
                            (new_assets) ->
                                load_assets(true).then(
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
                                load_assets(true).then(
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
                            load_assets(true).then(
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

]).directive("icswDeviceFixedVariableScopeOverview",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.fixed.variable.scope.overview")
        controller: "icswDeviceFixedVariableScopeOverviewCtrl"
        scope: true
    }
]).controller("icswDeviceFixedVariableScopeOverviewCtrl",
[
    "$scope", "$q", "icswDeviceTreeService", "icswDeviceTreeHelperService",
    "icswDeviceVariableScopeTreeService", "icswDeviceFixedVariableHelper",
(
    $scope, $q, icswDeviceTreeService, icswDeviceTreeHelperService,
    icswDeviceVariableScopeTreeService, icswDeviceFixedVariableHelper,
) ->
    $scope.struct = {
        # device tree
        device_tree: undefined
        # devvarscope_tree
        dvs_tree: undefined
        # helper object
        helper: undefined
        # device helpers
        helpers: []
        # fixed variable helper
        # fixed_var_helper: undefined
        # data loaded: show / hide
        data_loaded: false
        # devices
        devices: []
    }

    load_data = () ->
        $scope.struct.data_loaded = false
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
                icswDeviceVariableScopeTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.device_tree = data[0]
                $scope.struct.dvs_tree = data[1]
                trace_devices =  $scope.struct.device_tree.get_device_trace($scope.struct.devices)
                helper =  icswDeviceTreeHelperService.create($scope.struct.device_tree, trace_devices)
                $scope.struct.device_tree.enrich_devices(helper, ["variable_info"]).then(
                    (_done) ->
                        # console.log "****", $scope.devices
                        $scope.struct.helper = helper
                        for dev in $scope.struct.devices
                            $scope.struct.helpers.push(
                                new icswDeviceFixedVariableHelper($scope.struct.dvs_tree, dev)
                            )
                        $scope.struct.data_loaded = true
                )
        )
    $scope.new_devsel = (devs) ->
        $scope.struct.devices.length = 0
        $scope.struct.helpers.length = 0
        for entry in devs
            if not entry.is_meta_device
                $scope.struct.devices.push(entry)
        load_data()
]).directive("icswDeviceFixedVariableScopeTable",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.fixed.variable.scope.table")
        controller: "icswDeviceFixedVariableScopeTableCtrl"
        scope: {
            helpers: "=icswDeviceHelpers"
            var_scope: "=icswVariableScope"
        }
        link: (scope, element, attrs) ->
            scope.link()
    }
]).controller("icswDeviceFixedVariableScopeTableCtrl",
[
    "$scope", "$q",
(
    $scope, $q,
) ->
    $scope.struct = {
        structs: []
    }

    $scope.link = () ->
        $scope.struct.structs.length = 0
        for entry in $scope.helpers
            $scope.struct.structs.push(
                {
                    helper: entry
                    scope: entry.var_scope_struct_lut[$scope.var_scope.idx]
                }
            )
])
