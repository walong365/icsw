{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

{% verbatim %}

config_table_template = """
    <h2>{{ entries.length }} configurations, shown: {{ pagSettings.conf.filtered_len }}, <input type="button" class="btn btn-sm btn-success" value="create new config" ng-click="config_edit.create($event)"></input></h2>
    <table class="table table-condensed table-hover table-bordered" style="width:auto;">
        <thead>
            <tr>
                <td colspan="11">
                    <div class="row" style="width:900px;">
                        <div class="col-sm-4">
                            <div class="input-group">
                                <input ng-model="pagSettings.conf.filter_settings.filter_str" class="form-control" placeholder="filter">
                                </input>
                                <span class="input-group-btn">
                                    <button class="btn btn-danger" type="button" ng-click="clear_filter()"><span title="clear selection" class="glyphicon glyphicon-ban-circle"></span></button>
                                </span>
                            </div>
                        </div>
                        <div class="col-sm-3">
                            <div class="input-group">
                            name: <input type="checkbox" ng-model="pagSettings.conf.filter_settings.filter_name"></input>
                            script: <input type="checkbox" ng-model="pagSettings.conf.filter_settings.filter_script"></input>
                            var: <input type="checkbox" ng-model="pagSettings.conf.filter_settings.filter_var"></input>
                            mon: <input type="checkbox" ng-model="pagSettings.conf.filter_settings.filter_mon"></input>
                            </div>
                        </div>
                        <div class="col-sm-5" paginator entries="entries" pag_settings="pagSettings" per_page="15" paginator_filter="func" paginator_filter_func="filter_conf">
                        </div>
                    </div>
                </td>
            </tr>
            <tr>
                <th>Name</th>
                <th>Pri</th>
                <th>enabled</th>
                <th>Description</th>
                <th>parent</th>
                <th>script</th>
                <th>var</th>
                <th>mon</th>
                <th>cats</th>
                <th colspan="2">action</th>
            </tr>
        </thead>
        <tbody>
            <tr ng-repeat="config in pagSettings.filtered_list.slice(pagSettings.conf.start_idx, pagSettings.conf.end_idx + 1)" ng-class="get_config_row_class(config)">
                <td>{{ config.name }}</td>
                <td class="text-right">{{ config.priority }}</td>
                <td class="text-center">{{ config.enabled | yesno1 }}</td>
                <td>{{ config.description }}</td>
                <td>{{ show_parent_config(config) }}</td>
                <td class="text-center"><span ng-class="get_label_class(config, 'script')">{{ config.script_num }}</span></td>
                <td class="text-center"><span ng-class="get_label_class(config, 'var')">{{ config.var_num }}</span></td>
                <td class="text-center"><span ng-class="get_label_class(config, 'mon')">{{ config.mon_num }}</span></td>
                <td class="text-center">{{ get_num_cats(config) }}</td>
                <td class="text-center">
                    <span ng-if="config.usecount" class="text-warning">
                        refs: {{ config.usecount }}
                    </span>
                    <span ng-if="!config.usecount">
                        <input type="button" class="btn btn-sm btn-danger" value="delete" ng-click="config_edit.delete_obj(config)"></input>
                    </span>
                </td>
                <td>
                    <input type="button" class="btn btn-sm btn-success" value="modify" ng-click="config_edit.edit(config, $event)"></input>
                </td>
            </tr>
        </tbody>
    </table>
"""

{% endverbatim %}

config_module = angular.module("icsw.config", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular"])

angular_module_setup([config_module])

config_ctrl = config_module.controller("config_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal) ->
        $scope.pagSettings = paginatorSettings.get_paginator("config_list", $scope)
        $scope.pagSettings.conf.filter_settings = {
            "filter_str" : ""
            "filter_name" : true
            "filter_script" : false
            "filter_var" : false
            "filter_mon" : false
        }
        $scope.pagSettings.conf.filter_changed = (ps) ->
            cf = $scope.pagSettings.conf.filter_settings
            f_val = cf.filter_str 
            if  f_val == ""
                $scope.filter_re = new RegExp("", "gi")
            else
                try
                    $scope.filter_re = new RegExp(f_val, "gi")
                catch
                    $scope.filter_re = new RegExp("^$", "gi")
            if not cf.filter_name and not cf.filter_script and not cf.filter_var and not cf.filter_mon
                cf.filter_name = true
            #console.log "fc"
        $scope.entries = []
        $scope.config_edit = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular)
        $scope.config_edit.create_template = "config_template.html"
        $scope.config_edit.edit_template = "config_template.html"
        $scope.config_edit.create_rest_url = Restangular.all("{% url 'rest:config_list'%}".slice(1))
        $scope.config_edit.modify_rest_url = "{% url 'rest:config_detail' 1 %}".slice(1).slice(0, -2)
        $scope.config_edit.create_list = $scope.entries
        $scope.config_edit.new_object_at_tail = false
        $scope.config_edit.change_signal = "icsw.new_config"
        $scope.config_edit.new_object = (scope) ->
            new_obj = {
                "name" : "new config", "description" : "", "priority" : 0, "mon_check_command_set" : [], "config_script_set" : [],
                "config_str_set" : [], "config_int_set" : [], "config_blob_set" : [], "config_bool_set" : [], "enabled" : true,
                "parent_config" : undefined, "categories" : [],
            }
            return new_obj
        $scope.reload = () ->
            restDataSource.reload(["{% url 'rest:config_list' %}", {}]).then((data) ->
                #console.log data
                ($scope._set_fields(entry) for entry in data)
                $scope.entries = data
                $scope.config_edit.create_list = $scope.entries
                $scope.config_edit.delete_list = $scope.entries
            )
        $scope._set_fields = (entry) ->
            entry.script_sel = 0
            entry.script_num = entry.config_script_set.length
            entry.var_sel = 0
            entry.var_num = entry.config_str_set.length + entry.config_int_set.length + entry.config_bool_set.length + entry.config_blob_set.length
            entry.mon_sel = 0
            entry.mon_num = entry.mon_check_command_set.length
        $scope.filter_conf = (entry, scope) ->
            show = false
            scope._set_fields(entry)
            cf = scope.pagSettings.conf.filter_settings
            f_re = scope.filter_re
            if cf.filter_name
                if entry.name.match(f_re) or entry.description.match(f_re)
                    show = true
            if cf.filter_script
                entry.script_sel = (true for _scr in entry.config_script_set when _scr.name.match(f_re) or _scr.description.match(f_re) or _scr.value.match(f_re)).length
                if entry.script_sel
                    show = true
            if cf.filter_mon
                entry.mon_sel = (true for _mon in entry.mon_check_command_set when _mon.name.match(f_re) or _mon.command_line.match(f_re) or _mon.description.match(f_re)).length
                if entry.mon_sel
                    show = true
            if cf.filter_var
                for var_type in ["str", "int", "bool", "blob"]
                    sub_set = entry["config_#{var_type}_set"]
                    entry.var_sel += (true for _var in sub_set when _var.name.match(f_re) or _var.description.match(f_re) or String(_var.value).match(f_re)).length
                if entry.var_sel
                    show = true
            return show
        $scope.clear_filter = () ->
            $scope.pagSettings.conf.filter_settings.filter_str = ""
        $scope.get_label_class = (entry, s_type) ->
            num = entry["#{s_type}_num"]
            sel = entry["#{s_type}_sel"]
            if sel and $scope.pagSettings.conf.filter_settings.filter_str
                return "label label-success"
            else if num
                return "label label-primary"
            else
                return "label label-default"
        $scope.get_num_cats = (config) ->
            return if config.categories.length then "#{config.categories.length}" else "-"
        $scope.get_valid_parents = () ->
            return (entry for entry in $scope.entries when entry.enabled)
        $scope.$on("icsw.new_config", (args) ->
            $scope.pagSettings.set_entries($scope.entries)
        )
        $scope.show_parent_config = (config) ->
            if config.parent_config
                return (entry.name for entry in $scope.entries when entry.idx == config.parent_config)[0]
            else
                return ""
        $scope.get_config_row_class = (config) ->
            return if config.enabled then "" else "danger"
        $scope.reload()
]).directive("configtable", ($templateCache, $compile, $modal, Restangular) ->
    return {
        restrict : "EA"
        template : $templateCache.get("config_table.html")
        link : (scope, el, attrs) ->
            #scope.new_devsel((parseInt(entry) for entry in attrs["devicepk"].split(",")), [])
    }
).directive("category", ($templateCache, $compile, $modal, Restangular, restDataSource) ->
    return {
        restrict : "EA"
        template : "<tree treeconfig='cat_tree'></tree></div>"
        link : (scope, el, attrs) ->
            scope.cat_tree = new device_cat_tree(scope)
            restDataSource.reload(["{% url 'rest:category_list' %}", {}]).then((data) ->
                cat_tree_lut = {}
                sel_cat = scope._edit_obj.categories
                for entry in data
                    if entry.full_name.match(/^\/config/)
                        t_entry = scope.cat_tree.new_node({folder:false, obj:entry, expand:entry.depth < 2, selected: entry.idx in sel_cat})
                        cat_tree_lut[entry.idx] = t_entry
                        if entry.parent and entry.parent of cat_tree_lut
                            cat_tree_lut[entry.parent].add_child(t_entry)
                        else
                            # hide selection from root nodes
                            t_entry._show_select = false
                            scope.cat_tree.add_root_node(t_entry)
                scope.cat_tree_lut = cat_tree_lut
                scope.cat_tree.show_selected(true)
            )
            scope.new_selection = (new_sel) ->
                scope._edit_obj.categories = new_sel
    }
).run(($templateCache) ->
    $templateCache.put("simple_confirm.html", simple_modal_template)
    $templateCache.put("config_table.html", config_table_template)
)

class device_cat_tree extends tree_config
    constructor: (@scope, args) ->
        super(args)
        @show_selection_buttons = false
        @show_icons = false
        @show_select = true
        @show_descendants = false
        @show_childs = false
    get_name : (t_entry) ->
        obj = t_entry.obj
        if obj.comment
            return "#{obj.name} (#{obj.comment})"
        else
            return obj.name 
    selection_changed: () =>
        sel_list = @get_selected((node) ->
            if node.selected
                return [node.obj.idx]
            else
                return []
        )
        @scope.new_selection(sel_list)

add_tree_directive(config_ctrl)

{% endinlinecoffeescript %}

</script>
