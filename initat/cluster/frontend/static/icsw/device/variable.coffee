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
).config(["$stateProvider", "icswRouteExtensionProvider", ($stateProvider, icswRouteExtensionProvider) ->
    $stateProvider.state(
        "main.devvars", {
            url: "/variables"
            template: '<icsw-device-variable-overview icsw-sel-man="0"></icsw-device-variable-overview>'
            icswData: icswRouteExtensionProvider.create
                pageTitle: "Device variables"
                rights: ["device.change_variables"]
                menuEntry:
                    menukey: "dev"
                    icon: "fa-code"
                    ordering: 30
        }
    )
]).controller("icswConfigVarsCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "$q", "$uibModal", "ICSW_URLS", "icswDeviceConfigurationConfigVarTreeService", "icswSimpleAjaxCall",
    ($scope, $compile, $filter, $templateCache, Restangular, $q, $uibModal, ICSW_URLS, icswDeviceConfigurationConfigVarTreeService, icswSimpleAjaxCall) ->
        $scope.devvar_tree = new icswDeviceConfigurationConfigVarTreeService($scope)
        $scope.var_filter = ""
        $scope.loaded = false
        $scope.new_devsel = (_dev_sel) ->
            console.log "icswConfigVarsCtrl", _dev_sel
            # $scope.devsel_list = _dev_sel
        $scope.load_vars = () ->
            if not $scope.loaded
                $scope.loaded = true
                icswSimpleAjaxCall(
                    url     : ICSW_URLS.CONFIG_GET_DEVICE_CVARS
                    data    :
                        "keys" : angular.toJson($scope.devsel_list)
                ).then((xml) ->
                    $scope.set_tree_content($(xml).find("devices"))
                )
        $scope.set_tree_content = (in_xml) ->
            for dev_xml in in_xml.find("device")
                dev_xml = $(dev_xml)
                dev_entry = $scope.devvar_tree.new_node({folder: true, expand:true, obj:{"name" : dev_xml.attr("name"), "info_str": dev_xml.attr("info_str"), "state_level" : parseInt(dev_xml.attr("state_level"))}, _node_type:"d"})
                $scope.devvar_tree.add_root_node(dev_entry)
                for _xml in dev_xml.find("var_tuple_list").children()
                    _xml = $(_xml)
                    t_entry = $scope.devvar_tree.new_node(
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
                            $scope.devvar_tree.new_node(
                                folder: false
                                obj:
                                    "key": _sv.attr("key")
                                    "value": _sv.attr("value")
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
]).service("icswDeviceConfigurationConfigVarTreeService", ["icswTreeConfig", (icswTreeConfig) ->
    class device_config_var_tree extends icswTreeConfig
        constructor: (@scope, args) ->
            super(args)
            @show_selection_buttons = false
            @show_icons = true
            @show_select = false
            @show_descendants = false
            @show_childs = false
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
                }
            else
                single_create = false
                obj_or_parent = {
                    device: 0
                    name: "new_variable"
                    var_type: "s"
                    _mon_var: null
                    inherit: true
                }
        else
            single_create = false
            dbu = new icswDeviceVariableBackup()
            dbu.create_backup(obj_or_parent)
        sub_scope = scope.$new(false)
        sub_scope.create = create
        sub_scope.single_create = single_create
        sub_scope.mon_vars = []
        if single_create
            # fetch mon_vars
            icswSimpleAjaxCall(
                url : ICSW_URLS.MON_GET_MON_VARS
                data : {
                    device_pk : device.idx
                }
                dataType : "json"
            ).then(
                (json) ->
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
                    sub_scope.edit_obj.inherit = false
                    if _mon_var.type == "i"
                        sub_scope.edit_obj.val_int = parseInt(_mon_var.value)
                    else
                        sub_scope.edit_obj.val_str = _mon_var.value

        sub_scope.edit_obj = obj_or_parent

        sub_scope.valid_var_types = [
            {"short" : "i", "long" : "integer"},
            {"short" : "s", "long" : "string"},
        ]

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
                        toaster.pop("warning", "form validation problem", "", 0)
                        d.reject("form not valid")
                    else
                        if create
                            if single_create
                                # single creation
                                scope.device_tree.create_device_variable(sub_scope.edit_obj).then(
                                    (new_conf) ->
                                        scope.helper.filter_device_variables()
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
                                    wait_list.push(scope.device_tree.create_device_variable(local_var))
                                $q.allSettled(wait_list).then(
                                    (result) ->
                                        # todo: check result
                                        scope.helper.filter_device_variables()
                                        d.resolve("created")
                                )
                        else
                            Restangular.restangularizeElement(
                                null
                                sub_scope.edit_obj
                                ICSW_URLS.REST_DEVICE_VARIABLE_DETAIL.slice(1).slice(0, -2)
                            )
                            sub_scope.edit_obj.put().then(
                                (ok) ->
                                    scope.helper.filter_device_variables()
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
            icswToolsSimpleModalService("Really delete DeviceVariable #{d_var.name} ?").then(
                () =>
                    scope.device_tree.delete_device_variable(d_var).then(
                        () ->
                            scope.helper.filter_device_variables()
                            console.log "DevVar deleted"
                    )
            )

        special_fn: (scope, event, fn_name, d_var, device) ->
            if fn_name == "local_copy"
                new_var = angular.copy(d_var)
                new_var.device = device.idx
                blockUI.start()
                scope.device_tree.create_device_variable(new_var).then(
                    (new_conf) ->
                        scope.helper.filter_device_variables()
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
    "icswTools", "icswDeviceVariableListService",
    "icswDeviceTreeService", "icswDeviceTreeHelperService",
(
    $scope, $compile, $filter, $templateCache, $q, $uibModal, blockUI,
    icswTools, icswDeviceVariableListService,
    icswDeviceTreeService, icswDeviceTreeHelperService,
) ->
    $scope.vars = {
        name_filter: ""
    }
    # struct to hand over to VarCtrl
    $scope.struct = {}
    $scope.dataLoaded = false

    $scope.new_devsel = (devs) ->
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                device_tree = data[0]
                trace_devices =  device_tree.get_device_trace(devs)
                hs = icswDeviceTreeHelperService.create(device_tree, trace_devices)
                device_tree.enrich_devices(hs, ["variable_info"]).then(
                    (_done) ->
                        $scope.struct.devices = devs
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
    "$templateCache", "$compile", "$q", "Restangular", "ICSW_URLS",
(
    $templateCache, $compile, $q, Restangular, ICSW_URLS,
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
])
