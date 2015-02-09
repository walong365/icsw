device_variable_module = angular.module(
    "icsw.device.variables",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select"
    ]
).controller("icswDeviceVariableCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "blockUI", "icswTools", "ICSW_URLS",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, blockUI, icswTools, ICSW_URLS) ->
        $scope.enable_modal = true
        $scope.base_edit = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular)
        $scope.base_edit.create_template = "device.variable.new.form"
        $scope.base_edit.create_rest_url = Restangular.all(ICSW_URLS.REST_DEVICE_VARIABLE_LIST.slice(1))
        $scope.base_edit.new_object = (scope) -> 
            return {"device" : scope._obj.idx, "var_type" : "s", "_mon_copy" : 0}
        $scope.base_edit.change_signal = "icsw.dv.changed"
        $scope.create = (obj, event) ->
            # copy for new_object callback
            $scope._obj = obj
            $scope.base_edit.create_list = obj.device_variable_set
            call_ajax
                url : ICSW_URLS.MON_GET_MON_VARS
                data : {
                    device_pk : obj.idx
                }
                dataType : "json"
                success : (json) ->
                    $scope.$apply(
                        $scope.mon_vars = json
                    )
            $scope.mon_vars = []#{"idx" : 0, "info" : "please wait, fetching data from server ..."}]
            $scope.base_edit.create(event)
        $scope.take_mon_var = () ->
            if $scope._edit_obj._mon_copy
                _mon_var = (entry for entry in $scope.mon_vars when entry.idx == $scope._edit_obj._mon_copy)[0]
                $scope._edit_obj.var_type = _mon_var.type
                $scope._edit_obj.name = _mon_var.name
                if _mon_var.type == "i"
                    $scope._edit_obj.val_int = parseInt(_mon_var.value)
                else
                    $scope._edit_obj.val_str = _mon_var.value
        $scope.var_filter = ""
        $scope.entries = []
        $scope.pagSettings = paginatorSettings.get_paginator("dv_base", $scope)
        $scope.pagSettings.conf.filter_mode = "func"
        $scope.valid_var_types = [
            {"short" : "i", "long" : "integer"},
            {"short" : "s", "long" : "string"},
        ]
        $scope.pagSettings.conf.filter_settings = {
            "hide_empty" : false
        }
        $scope.pagSettings.conf.filter_func = () ->
            return (entry) ->
                if $scope.pagSettings.conf.filter_settings.hide_empty and not entry.device_variable_set.length
                    return false
                else
                    return true
        $scope.get_hide_class = () ->
            if $scope.pagSettings.conf.filter_settings.hide_empty
                return "btn btn-sm btn-warning"
            else
                return "btn btn-sm"
        $scope.new_devsel = (dev_pks, group_pks) ->
            wait_list = [
                restDataSource.reload([ICSW_URLS.REST_DEVICE_TREE_LIST, {"pks" : angular.toJson(dev_pks), "with_variables" : true, "with_meta_devices" : true, "ignore_cdg" : false, "olp" : "backbone.device.change_variables"}])
            ]
            $q.all(wait_list).then((data) ->
                entries = data[0]
                $scope.base_edit.create_list = entries
                # all entries (including parent meta devices and CDG)
                $scope.cdg = (entry for entry in entries when entry.is_cluster_device_group)[0]
                $scope.deep_entries = icswTools.build_lut(entries)
                $scope.group_dev_lut = {}
                for entry in entries
                    if entry.device_type_identifier == "MD"
                        $scope.group_dev_lut[entry.device_group] = entry.idx
                $scope.entries = (entry for entry in entries when entry.idx in dev_pks)
                for entry in $scope.entries
                    entry.expanded = false
                    entry.num_filtered = entry.device_variable_set.length
            )
        $scope.get_tr_class = (obj) ->
            if obj.is_cluster_device_group
                return "danger"
            else if obj.device_type_identifier == "MD"
                return "success"
            else
                return ""
        $scope.get_name = (obj) ->
            if obj.device_type_identifier == "MD"
                if obj.is_cluster_device_group
                    return obj.full_name.slice(8) + " [ClusterGroup]"
                else
                    return obj.full_name.slice(8) + " [Group]"
            else
                return obj.full_name
        $scope.expand_vt = (obj) ->
            obj.expanded = not obj.expanded
        $scope.get_expand_class = (obj) ->
            if obj.expanded
                return "glyphicon glyphicon-chevron-down"
            else
                return "glyphicon glyphicon-chevron-right"
        $scope.new_filter_set = (new_val, change_expand_state) ->
            try
                cur_re = new RegExp($scope.var_filter, "gi")
            catch exc
                cur_re = new RegExp("^$", "gi")
            for entry in $scope.entries
                entry.num_filtered = (true for _var in entry.device_variable_set when _var.name.match(cur_re)).length
                if change_expand_state
                    if entry.num_filtered and new_val.length
                        entry.expanded = true
                    else
                        entry.expanded = false
            $scope.pagSettings.set_entries($scope.entries)
        $scope.$watch("var_filter", (new_val) -> $scope.new_filter_set(new_val, true))
        $scope.form_error = (field_name) =>
            if $scope.form?
                if $scope.form[field_name].$valid
                    return ""
                else
                    return "has-error"
            else
                return ""
        $scope.create_for_all = (event) ->
            new_obj = {"var_type" : "i", "name" : "var_name"}
            $scope._edit_obj = new_obj
            $scope.action_string = "create for all"
            $scope.edit_div = $compile($templateCache.get("device.variable.new.form"))($scope)
            $scope.edit_div.simplemodal
                position     : [event.pageY, event.pageX]
                #autoResize   : true
                #autoPosition : true
                onShow: (dialog) =>
                    $scope.cur_edit = $scope
                    dialog.container.draggable()
                    $("#simplemodal-container").css("height", "auto")
                onClose: (dialog) =>
                    $scope.close_modal()
        $scope.close_modal = () =>
            $.simplemodal.close()
        $scope.modify = () ->
            if not $scope.form.$invalid
                $scope.create_rest_url = Restangular.all(ICSW_URLS.REST_DEVICE_VARIABLE_LIST.slice(1))
                $scope.close_modal()
                blockUI.start()
                $scope.add_list = []
                for entry in $scope.entries
                    new_var = angular.copy($scope._edit_obj)
                    new_var.device = entry.idx
                    $scope.add_list.push(new_var)
                $scope.next_send()
        $scope.next_send_error = (error) ->
            $scope.next_send()
        $scope.next_send = (new_data) ->
            if new_data
                add_entry = (entry for entry in $scope.entries when entry.idx == new_data.device)[0]
                add_entry.device_variable_set.push(new_data)
            if $scope.add_list.length
                $scope.create_rest_url.post($scope.add_list.shift()).then($scope.next_send, $scope.next_send_error)
            else
                # trigger recalc of filter w. pagination settings
                $scope.new_filter_set($scope.var_filter, false)
                blockUI.stop()
        $scope.$on("icsw.dv.changed", (args) ->
            # trigger redisplay of vars
            $scope.new_filter_set($scope.var_filter, false)
        )
]).directive("icswDeviceVariableHead", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.variable.head")
    }
]).directive("icswDeviceVariableRow", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.variable.row")
        link : (scope) ->
            scope.num_parent_vars = (obj) ->
                my_names = (entry.name for entry in obj.device_variable_set)
                num_meta = 0
                if not obj.is_cluster_device_group
                    if obj.device_type_identifier != "MD"
                        meta_server = scope.deep_entries[scope.group_dev_lut[obj.device_group]]
                        meta_names = (entry.name for entry in meta_server.device_variable_set)
                        num_meta += (entry for entry in meta_names when entry not in my_names).length
                    else
                        meta_names = []
                    num_meta += (entry for entry in scope.cdg.device_variable_set when entry.name not in my_names and entry.name not in meta_names).length
                return num_meta
            scope.num_vars = (obj) ->
                return scope.num_parent_vars + obj.device_variable_set.length
            scope.parent_vars_defined = (obj) ->
                return if scope.num_parent_vars(obj) then true else false
            scope.num_shadowed_vars = (obj) ->
                my_names = (entry.name for entry in obj.device_variable_set)
                num_shadow = 0
                if not obj.is_cluster_device_group
                    if obj.device_type_identifier != "MD"
                        meta_server = scope.deep_entries[scope.group_dev_lut[obj.device_group]]
                        meta_names = (entry.name for entry in meta_server.device_variable_set)
                        num_shadow += (entry for entry in meta_names when entry in my_names).length
                    else
                        meta_names = []
                    num_shadow += (entry for entry in scope.cdg.device_variable_set when entry.name in my_names and entry.name not in meta_names).length
                return num_shadow
            scope.any_shadowed_vars = (obj) ->
                return if scope.num_shadowed_vars(obj) then true else false
    }
]).filter("filter_name", ["$filter", ($filter) ->
    return (arr, f_string) ->
        try
            cur_re = new RegExp(f_string, "gi")
        catch exc
            cur_re = new RegExp("^$", "gi")
        return (entry for entry in arr when entry.name.match(cur_re))
]).directive("icswDeviceVariableTable", ["$templateCache", "$compile", "$modal", "Restangular", "ICSW_URLS", ($templateCache, $compile, $modal, Restangular, ICSW_URLS) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.variable.table")
        link : (scope, el, attrs) ->
            scope.device = scope.$eval(attrs["device"])
            scope.filtervalue = scope.$eval(attrs["filtervalue"])
            scope.edit_mixin = new angular_edit_mixin(scope, $templateCache, $compile, $modal, Restangular)
            scope.edit_mixin.delete_confirm_str = (obj) -> "Really delete variable '#{obj.name}' ?"
            scope.edit_mixin.modify_rest_url = ICSW_URLS.REST_DEVICE_VARIABLE_DETAIL.slice(1).slice(0, -2)
            scope.edit_mixin.delete_list = scope.device.device_variable_set
            scope.edit_mixin.edit_template = "device.variable.form"
            scope.edit_mixin.change_signal = "icsw.dv.changed"
            scope.get_value = (obj) ->
                if obj.var_type == "s"
                    return obj.val_str
                else if obj.var_type == "i"
                    return obj.val_int
                else if obj.var_type == "b"
                    return obj.val_blob.length + " bytes"
                else if obj.var_type == "t"
                    return obj.val_time
                else if obj.var_type == "d"
                    return moment(obj.val_date).format("dd, D. MMM YYYY HH:mm:ss")
                else
                    return "unknown type #{obj.var_type}"
            scope.get_var_type = (obj) ->
                if obj.var_type == "s"
                    return "string"
                else if obj.var_type == "i"
                    return "integer"
                else if obj.var_type == "b"
                    return "blob"
                else if obj.var_type == "t"
                    return "time"
                else if obj.var_type == "d"
                    return "datetime"
                else
                    return obj.var_type
            scope.get_parent_vars = (obj, src) ->
                my_names = (entry.name for entry in obj.device_variable_set)
                parents = []                    
                if not obj.is_cluster_device_group
                    if obj.device_type_identifier != "MD" and src == "g"
                        # device, inherited from group
                        meta_group = scope.deep_entries[scope.group_dev_lut[obj.device_group]]
                        parents = meta_group.device_variable_set
                    else if src == "c"
                        if obj.device_type_identifier == "MD"
                            # group, inherited from cluster
                            parents = scope.cdg.device_variable_set
                        else
                            # device, inherited from cluster
                            meta_group = scope.deep_entries[scope.group_dev_lut[obj.device_group]]
                            meta_names = (_entry.name for _entry in meta_group.device_variable_set)
                            parents = (entry for entry in scope.cdg.device_variable_set when entry.name not in meta_names) 
                    parents = (entry for entry in parents when entry.name not in my_names)
                return parents
            scope.local_copy = (d_var, src) ->
                new_var = angular.copy(d_var)
                new_var.device = scope.obj.idx
                Restangular.all(ICSW_URLS.REST_DEVICE_VARIABLE_LIST.slice(1)).post(new_var).then((data) ->
                    scope.obj.device_variable_set.push(data)
                )
    }
]).directive("icswDeviceVariableOverview", ["$templateCache", "msgbus", ($templateCache, msgbus) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.variable.overview")
        link : (scope, el, attrs) ->
            if attrs["disablemodal"]?
                scope.enable_modal = if parseInt(attrs["disablemodal"]) then false else true
            scope.$watch(attrs["devicepk"], (new_val) ->
                if new_val and new_val.length
                    scope.new_devsel(new_val)
            )
            if not attrs["devicepk"]?
                msgbus.emit("devselreceiver")
                msgbus.receive("devicelist", scope, (name, args) ->
                    scope.new_devsel(args[0])                    
                )
    }
])
