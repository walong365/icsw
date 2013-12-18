{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

device_module = angular.module("icsw.device", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular"])

angular_module_setup([device_module])

angular_add_simple_list_controller(
    device_module,
    "device_base",
    {
        rest_url            : "{% url 'rest:device_list' %}"
        delete_confirm_str  : (obj) -> return "Really delete Device '#{obj.name}' ?"
        template_cache_list : ["device_row.html", "device_head.html"]
    }
)

angular_add_simple_list_controller(
    device_module,
    "device_sel_base",
    {
        rest_url            : "{% url 'rest:device_tree_list' %}"
        delete_confirm_str  : (obj) -> return "Really delete Device '#{obj.name}' ?"
        template_cache_list : ["device_sel_row.html", "device_sel_head.html"]
    }
)

device_tree_base = device_module.controller("device_tree_base", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$timeout", 
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $timeout) ->
        # init pagSettings /w. filter
        $scope.settings = {}
        $scope.settings.filter_settings = {"dg_filter" : "b", "en_filter" : "b", "sel_filter" : "b"}
        $scope.pagSettings = paginatorSettings.get_paginator("device_tree_base", $scope)
        $scope.rest_data = {}
        $scope.rest_map = [
            {"short" : "device", "url" : "{% url 'rest:device_tree_list' %}", "options" : {"all_devices" : true, "ignore_cdg" : false, "tree_mode" : true}} 
            {"short" : "device_group", "url" : "{% url 'rest:device_group_list' %}"}
            {"short" : "device_type", "url" : "{% url 'rest:device_type_list' %}"}
            {"short" : "mother_server", "url" : "{% url 'rest:device_tree_list' %}", "options" : {"all_mother_servers" : true}}
            {"short" : "monitor_server", "url" : "{% url 'rest:device_tree_list' %}", "options" : {"all_monitoring_servers" : true}}
            {"short" : "domain_tree_node", "url" : "{% url 'rest:domain_tree_node_list' %}"}
        ]
        $scope.edit_map = {
            "device"       : "device_tree.html",
            "device_group" : "device_group_tree.html",
        }
        $scope.modal_active = false
        $scope.entries = []
        $scope.reload = () ->
            wait_list = []
            for value, idx in $scope.rest_map
                $scope.rest_data[value.short] = restDataSource.reload([value.url, value.options])
                wait_list.push($scope.rest_data[value.short])
            $q.all(wait_list).then((data) ->
                for value, idx in data
                    if idx == 0
                        $scope.entries = value
                    $scope.rest_data[$scope.rest_map[idx].short] = value
                $scope.rest_data_set()
            )
        $scope.reload()
        $scope.modify = () ->
            rest_entry = (entry for entry in $scope.rest_map when entry.short == $scope._array_name)[0]
            if not $scope.form.$invalid
                if $scope.create_mode
                    $scope.rest.post($scope.new_obj).then((new_data) ->
                        if $scope._array_name == "device"
                            $scope.entries.push(new_data)
                            if $scope.pagSettings.conf.init
                                $scope.pagSettings.set_entries($scope.entries)
                        else
                            $scope.rest_data[$scope._array_name].push(new_data)
                        #if $scope.settings.object_created
                        #    $scope.settings.object_created($scope.new_obj, new_data)
                    )
                else
                    $scope.edit_obj.put(rest_entry.options).then(
                        (data) -> 
                            $.simplemodal.close()
                            if $scope._array_name == "device"
                                cur_f = $scope.entries
                            else
                                cur_f = $scope.rest_data[$scope._array_name]
                            handle_reset(data, cur_f, $scope.edit_obj.idx)
                            $scope.object_modified(data)
                        (resp) -> handle_reset(resp.data, cur_f, $scope.edit_obj.idx)
                    )
        $scope.form_error = (field_name) ->
            if $scope.form[field_name].$valid
                return ""
            else
                return "has-error"
        $scope.create = (a_name, event) ->
            $scope._array_name = a_name
            #if typeof($scope.settings.new_object) == "function"
            #    $scope.new_obj = $scope.settings.new_object($scope)
            #else
            #    $scope.new_obj = $scope.settings.new_object
            $scope.create_or_edit(event, true, $scope.new_obj)
        $scope.edit = (a_name, event, obj) ->
            $scope._array_name = a_name
            $scope.pre_edit_obj = angular.copy(obj)
            $scope.create_or_edit(event, false, obj)
        $scope.create_or_edit = (event, create_or_edit, obj) ->
            $scope.edit_obj = obj
            console.log obj
            $scope.create_mode = create_or_edit
            console.log $scope._array_name, $scope.edit_map[$scope._array_name]
            $scope.edit_div = $compile($templateCache.get($scope.edit_map[$scope._array_name]))($scope)
            $scope.edit_div.simplemodal
                #opacity      : 50
                position     : [event.pageY, event.pageX]
                #autoResize   : true
                #autoPosition : true
                onShow: (dialog) => 
                    dialog.container.draggable()
                    $("#simplemodal-container").css("height", "auto")
                    $scope.modal_active = true
                onClose: (dialog) =>
                    $.simplemodal.close()
                    $scope.modal_active = false
        $scope.get_action_string = () ->
            return if $scope.create_mode then "Create" else "Modify"
        $scope.delete = (obj) ->
            if confirm($scope.settings.delete_confirm_str(obj))
                obj.remove().then((resp) ->
                    noty
                        text : "deleted instance"
                    remove_by_idx($scope.entries, obj.idx)
                    if $scope.pagSettings.conf.init
                        $scope.pagSettings.set_entries($scope.entries)
                    if $scope.settings.post_delete
                        $scope.settings.post_delete($scope, obj)
                )

        $scope.rest_data_set = () ->
            $scope.device_lut = build_lut($scope.entries)
            $scope.device_group_lut = build_lut($scope.rest_data.device_group)
            for entry in $scope.entries
                entry.selected = false
                entry.device_group_obj = $scope.device_group_lut[entry.device_group]
        $scope.get_tr_class = (obj) ->
            return if obj.is_meta_device then "success" else ""
        $scope.ignore_md = (entry) ->
            return entry.identifier != "MD"
        $scope.ignore_cdg = (entry) ->
            return not entry.cluster_device_group
        $scope.filter_pag = (entry, scope) ->
            aft_dict = {
                "b" : [true, false]
                "f" : [false]
                "t" : [true]
            } 
            # meta device selection list
            md_list = aft_dict[scope.pagSettings.conf.filter_settings.dg_filter]
            # enabled selection list
            en_list = aft_dict[scope.pagSettings.conf.filter_settings.en_filter]
            # selected list
            sel_list = aft_dict[scope.pagSettings.conf.filter_settings.sel_filter]
            # check enabled flag
            if en_list.length == 2
                # show all, no check
                en_flag = true
            else if en_list[0] == true
                if entry.is_meta_device
                    en_flag = entry.device_group_obj.enabled
                else
                    # show enabled (device AND device_group)
                    en_flag = entry.enabled and scope.device_group_lut[entry.device_group].enabled
            else
                if entry.is_meta_device
                    en_flag = entry.device_group_obj.enabled
                else
                    # show disabled (device OR device_group)
                    en_flag = not entry.enabled or (not scope.device_group_lut[entry.device_group].enabled)
            # selected
            sel_flag = entry.selected in sel_list
            return entry.is_meta_device in md_list and en_flag and sel_flag
        $scope.object_modified = (new_obj) ->
            console.log "mod", $scope._array_name
            new_obj.selected = $scope.pre_edit_obj.selected
            new_obj.device_group_obj = $scope.device_group_lut[new_obj.device_group]
            if new_obj.device_group != $scope.pre_edit_obj.device_group
                # device group has changed, reload to fix all dependencies
                $scope.reload()
])

device_module.directive("devicetreerow", ($templateCache, $compile) ->
    return {
        restrict : "EA"
        link : (scope, element, attrs) ->
            if scope.obj.is_meta_device
                scope.obj.device_group_obj.num_devices = (entry for entry in scope.entries when entry.device_group == scope.obj.device_group).length - 1
                new_el = $compile($templateCache.get("device_tree_meta_row.html"))
            else
                new_el = $compile($templateCache.get("device_tree_row.html"))
            scope.change_dg_sel = (flag) ->
                for entry in scope.entries
                    if entry.device_group == scope.obj.device_group
                        if flag == 1
                            entry.selected = true
                        else if flag == -1
                            entry.selected = false
                        else
                            entry.selected = not entry.selected
            element.append(new_el(scope))
    }
).directive("devicetreehead", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("device_tree_head.html")
    }
)

{% endinlinecoffeescript %}

</script>
