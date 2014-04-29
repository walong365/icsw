{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

{% verbatim %}

livestatus_templ = """
<table class="table table-condensed table-hover table-striped" style="font-size:100%;">
    <thead>
        <tr>
            <th colspan="99">
                Number of checks : {{ entries.length }}
            </th>
        </tr>
        <tr>
            <td colspan="99">
                <div class="row">
                    <div class="col-md-6">
                        <span paginator entries="entries" paginator_filter="func" paginator_filter_func="filter_mdr" pag_settings="pagSettings" per_page="20" paginator_filter="simple" paginator-epp="10,20,50,100,1000"></span>
                    </div>
                    <div class="col-md-6">
                        <input placeholder="filter..." ng-model="md_filter_str" class="form-control input-sm" ng-change="md_filter_changed()">
                        </input>
                    </div>
                </div>
            </td>
        </tr>
        <tr>
            <th colspan="99">
                <div class="btn-group">
                    <input ng-repeat="entry in md_states" type="button"
                        ng-class="get_mds_class(entry[0])"
                        ng-value="entry[1]"
                        ng-click="toggle_mds(entry[0])"
                    >
                    </input>
                </div>
                <div class="btn-group">
                    <input ng-repeat="entry in show_options" type="button"
                        ng-class="get_so_class(entry[0])"
                        ng-value="entry[1]"
                        ng-click="toggle_so(entry[0])"
                    >
                    </input>
                </div>
            </th>

        </tr>
        <tr>
            <td colspan="99">
                <div class="row">
                    <div class="col-md-6">
                        <tree treeconfig="cat_tree"></tree>
                    </div>
                </div>
            </td>
        </tr>
        <tr>
            <th ng-repeat="entry in show_options"
                ng-show="so_enabled[entry[0]]"
                ng-click="entry[3] && toggle_order(entry[0])"
                ng-class="get_header_class(entry)"
            >
            <span ng-if="entry[3]" ng-class="get_order_glyph(entry[0])"></span>
            {{ entry[1] }}
            </th>
        </tr>
    </thead>
    <tbody>
        <tr ng-repeat="entry in entries | orderBy:get_order() | paginator2:this.pagSettings">
            <td ng-show="so_enabled['host_name']" ng-class="get_host_class(entry)">
                {{ entry.host_name }}
                <span ng-show="show_host_attempt_info(entry)" class="badge pull-right">{{ get_host_attempt_info(entry) }}</span>
                <span ng-show="host_is_passive_checked(entry)" title="host is passive checked" class="glyphicon glyphicon-download pull-right"></span>
            </td>
            <td ng-show="so_enabled['state']" ng-class="get_state_class(entry)">
                {{ get_state_string(entry) }}
                <span ng-show="show_attempt_info(entry)" class="badge pull-right">{{ get_attempt_info(entry) }}</span>
                <span ng-show="is_passive_check(entry)" title="service is passive checked" class="glyphicon glyphicon-download pull-right"></span>
            </td>
            <td class="nowrap" ng-show="so_enabled['description']">{{ entry.description }}</td>
            <td class="nowrap" ng-show="so_enabled['cats']">{{ get_categories(entry) }}</td>
            <td class="nowrap" ng-show="so_enabled['state_type']">{{ get_state_type(entry) }}</td>
            <td class="nowrap" ng-show="so_enabled['last_check']">{{ get_last_check(entry) }}</td>
            <td class="nowrap" ng-show="so_enabled['last_change']">{{ get_last_change(entry) }}</td>
            <td ng-show="so_enabled['plugin_output']">{{ entry.plugin_output }}</td>
        </tr>
    </tbody>
</table>
"""

monconfig_templ = """
<div class="panel panel-default">
    <input type="button" class="btn btn-success" value="reload" ng-show="!reload_pending" ng-click="load_data()"></input>
    <tabset ng-show="!reload_pending">
        <tab ng-repeat="(key, value) in mc_tables" heading="{{ value.short_name }} ({{ value.entries.length }})">
            <h3>{{ value.entries.length }} entries for {{ value.short_name }}</h3> 
            <table class="table table-condensed table-hover table-bordered" style="width:auto;">
                <thead>
                    <tr>
                        <td colspan="{{ value.attr_list.length }}" paginator entries="value.entries" pag_settings="value.pagSettings" per_page="20" paginator_filter="simple" paginator-epp="10,20,50,100,1000"></td>
                    </tr>
                    <tr>
                        <th ng-repeat="attr in value.attr_list" title="{{ get_long_attr_name(attr) }}" ng-click="value.toggle_order(attr)">
                            <span ng-class="value.get_order_glyph(attr)"></span>
                            {{ get_short_attr_name(attr) }}
                        </th>
                    </tr>
                </thead>
                <tbody>
                    <tr ng-repeat="entry in value.entries | orderBy:value.get_order() | paginator2:value.pagSettings">
                        <td ng-repeat="attr in value.attr_list">
                            {{ entry[attr] }}
                        </td>
                    </tr>
                </tbody>
            </table>
        </tab>
    </tabset>
</div>
"""
{% endverbatim %}

device_livestatus_module = angular.module("icsw.device.livestatus", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular"])

angular_module_setup([device_livestatus_module])

add_tree_directive(device_livestatus_module)

class category_tree extends tree_config
    constructor: (@scope, args) ->
        super(args)
        #@show_selection_buttons = false
        @show_icons = false
        @show_select = true
        @show_descendants = false
        @show_childs = false
    selection_changed: () =>
        sel_list = @get_selected((node) ->
            if node.selected
                return [node.obj.idx]
            else
                return []
        )
        @scope.new_mc_selection(sel_list)
    get_name : (t_entry) ->
        cat = t_entry.obj
        if cat.depth > 1
            r_info = "#{cat.full_name} (#{cat.name})"
            #if cat.num_refs
            #    r_info = "#{r_info} (refs=#{cat.num_refs})"
            return r_info# + "#{cat.idx}"
        else if cat.depth
            return cat.full_name
        else
            return "TOP"

device_livestatus_module.controller("livestatus_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "$timeout"
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, $timeout) ->
        $scope.entries = []
        $scope.order_name = "host_name"
        $scope.order_dir = true
        $scope.md_filter_str = ""
        $scope.cur_timeout = undefined
        # paginator settings
        $scope.pagSettings = paginatorSettings.get_paginator("device_tree_base", $scope)
        # category tree
        $scope.cat_tree = new category_tree($scope, {})
        # selected categories
        $scope.selected_mcs = []
        $scope.master_cat_pk = 0
        $scope.show_unspec_cat = true
        $scope.show_options = [
            # 1 ... option local name
            # 2 ... option display name
            # 3 ... default value
            # 4 ... enable sort
            ["host_name"    , "node name", true, true],
            ["state"        , "state", true, true],
            ["description"  , "description", true, true],
            ["cats"         , "cats", false, false],
            ["state_type"   , "state type", false, false],
            ["last_check"   , "last check", true, false],
            ["last_change"  , "last change", false, false],
            ["plugin_output", "result", true, true],
        ]
        # int_state, str_state, default
        $scope.md_states = [
            [0, "O", true]
            [1, "W", true]
            [2, "C", true]
            [3, "U", true]
        ]
        $scope.so_enabled = {}
        for entry in $scope.show_options
            $scope.so_enabled[entry[0]] = entry[2]
        $scope.mds_enabled = {}
        for entry in $scope.md_states
            $scope.mds_enabled[entry[0]] = entry[2]
        $scope.get_so_class = (short) ->
            return if $scope.so_enabled[short] then "btn btn-xs btn-success" else "btn btn-xs"
        $scope.toggle_so = (short) ->
            $scope.so_enabled[short] = !$scope.so_enabled[short]
        $scope.get_mds_class = (int_state) ->
            return if $scope.mds_enabled[int_state] then "btn btn-xs " + {0 : "btn-success", 1 : "btn-warning", 2 : "btn-danger", 3 : "btn-danger"}[int_state] else "btn btn-xs"
        $scope.toggle_mds = (int_state) ->
            $scope.mds_enabled[int_state] = !$scope.mds_enabled[int_state]
        $scope.new_devsel = (_dev_sel, _devg_sel) ->
            #pre_sel = (dev.idx for dev in $scope.devices when dev.expanded)
            #restDataSource.reset()
            $scope.devsel_list = _dev_sel
            $scope.load_data()
        $scope.toggle_order = (name) ->
            if $scope.order_name == name
                $scope.order_dir = not $scope.order_dir
            else
                $scope.order_name = name
                $scope.order_dir = true
        $scope.new_mc_selection = (new_sel) ->
            $scope.selected_mcs = new_sel
            $scope.show_unspec_cat = $scope.master_cat_pk in $scope.selected_mcs
            $scope.md_filter_changed()
        $scope.get_header_class = (entry) ->
            return "nowrap"
        $scope.get_order = () ->
            return (if $scope.order_dir then "" else "-") + $scope.order_name
        $scope.get_order_glyph = (name) ->
            if $scope.order_name == name
                if $scope.order_dir 
                    _class = "glyphicon glyphicon-chevron-down"
                else
                    _class = "glyphicon glyphicon-chevron-up"
            else
                _class = "glyphicon glyphicon-chevron-right"
            return _class
        $scope.load_static_data = () ->
            wait_list = [
                restDataSource.reload(["{% url 'rest:category_list' %}", {}])
            ]
            $q.all(wait_list).then((data) ->
                cat_tree_lut = {}
                $scope.cat_tree.clear_root_nodes()
                $scope.selected_mcs = []
                for entry in data[0]
                    if entry.full_name.match(/^\/mon/)
                        entry.short_name = entry.full_name.substring(5)
                        t_entry = $scope.cat_tree.new_node({folder:false, obj:entry, expand:entry.depth < 2, selected: true})
                        cat_tree_lut[entry.idx] = t_entry
                        if entry.parent and entry.parent of cat_tree_lut
                            cat_tree_lut[entry.parent].add_child(t_entry)
                        else
                            # hide selection from root nodes
                            #t_entry._show_select = false
                            $scope.master_cat_pk = entry.idx
                            $scope.cat_tree.add_root_node(t_entry)
                        $scope.selected_mcs.push(entry.idx)
                $scope.cat_tree_lut = cat_tree_lut
                $scope.cat_tree.show_selected(false)
            )
        $scope.load_data = () ->
            $scope.cur_timeout = $timeout($scope.load_data, 20000)
            call_ajax
                url  : "{% url 'mon:get_node_status' %}"
                data : {
                    "pk_list" : angular.toJson($scope.devsel_list)
                },
                success : (xml) =>
                    if parse_xml_response(xml)
                        service_entries = []
                        $(xml).find("value[name='service_result']").each (idx, node) =>
                            service_entries = service_entries.concat(angular.fromJson($(node).text()))
                            #console.log entries[0]
                        host_entries = []
                        $(xml).find("value[name='host_result']").each (idx, node) =>
                            host_entries = host_entries.concat(angular.fromJson($(node).text()))
                        $scope.$apply(
                            $scope.entries = service_entries
                            for entry in service_entries
                                entry.custom_variables = $scope.parse_custom_variables(entry.custom_variables)
                            $scope.host_entries = host_entries
                            $scope.host_lut = {}
                            for entry in host_entries
                                entry.custom_variables = $scope.parse_custom_variables(entry.custom_variables)
                                $scope.host_lut[entry.host_name] = entry
                        )
        $scope.parse_custom_variables = (cvs) ->
            _cv = {}
            if cvs
                first = true
                for _entry in cvs.split("|")
                    if first
                        key = _entry.toLowerCase()
                        first = false
                    else
                        parts = _entry.split(",")
                        _cv[key] = parts
                        key = parts.pop().toLowerCase()
                # append key of last '|'-split to latest parts
                parts.push(key)
                for single_key in ["check_command_pk"]
                    if single_key of _cv
                        _cv[single_key] = parseInt(_cv[single_key][0])
                for int_mkey in ["cat_pks"]
                    if int_mkey of _cv
                        _cv[int_mkey] = (parseInt(_sv) for _sv in _cv[int_mkey])
            return _cv
        $scope.md_filter_changed = () ->
            $scope.pagSettings.set_entries(@entries)
        $scope.filter_mdr = (entry, scope) ->
            show = true
            if not scope.mds_enabled[parseInt(entry.state)]
                show = false
            if scope.md_filter_str
                if not $filter("filter")([entry], scope.md_filter_str).length
                    show = false
            if show
                if not scope.selected_mcs.length
                   show = false
                else
                    if entry.custom_variables and entry.custom_variables.cat_pks?
                        # only show if there is an intersection
                        show = _.intersection(scope.selected_mcs, entry.custom_variables.cat_pks).length
                    else
                        # show entries with unset / empty category
                        show = scope.show_unspec_cat
            return show
        $scope.load_static_data()
        $scope.$on("$destroy", () ->
            if $scope.cur_timeout
                $timeout.cancel($scope.cur_timeout)
        )
]).directive("livestatus", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("livestatus_template.html")
        link : (scope, el, attrs) ->
            scope.new_devsel((parseInt(entry) for entry in attrs["devicepk"].split(",")), [])
            scope.get_state_class = (entry) ->
                state_class = {
                    0 : "success"
                    1 : "warning"
                    2 : "danger"
                    3 : "danger"
                }[entry.state]
                return "#{state_class} nowrap"
            scope.get_last_check = (entry) ->
                return scope.get_diff_time(entry.last_check)
            scope.get_last_change = (entry) ->
                return scope.get_diff_time(entry.last_state_change)
            scope.get_diff_time = (ts) ->
                if parseInt(ts)
                    return moment.unix(ts).fromNow(true)
                else
                    return "never"
            scope.get_state_string = (entry) ->
                return {
                    0 : "OK"
                    1 : "Warning"
                    2 : "Critical"
                    3 : "Unknown"
                }[entry.state]
            scope.get_categories = (entry) ->
                if entry.custom_variables
                    if entry.custom_variables.cat_pks?
                        return (scope.cat_tree_lut[_pk].obj.short_name for _pk in entry.custom_variables.cat_pks).join(", ")
                    else
                        return "---"
                else
                    return "N/A"
            scope.get_state_type = (entry) ->
                return {
                    ""  : "???"
                    null : "???"
                    "0" : "soft"
                    "1" : "hard"
                }[entry.state_type]
            scope.get_check_type = (entry) ->
                return {
                    ""  : "???"
                    null : "???"
                    "0" : "active"
                    "1" : "passive"
                }[entry.check_type]
            scope.host_is_passive_checked = (entry) ->
                if entry.host_name of scope.host_lut
                    return if parseInt(scope.host_lut[entry.host_name].check_type) then true else false 
                else
                    return false                  
            scope.is_passive_check = (entry) ->
                return if parseInt(entry.check_type) then true else false 
            scope.get_host_class = (entry) ->
                if entry.host_name of scope.host_lut
                    h_state = parseInt(scope.host_lut[entry.host_name].state)
                    h_state_str = {
                        0 : "success"
                        1 : "danger"
                        2 : "danger"
                    }[h_state]
                else
                    h_state_str = "warning"
                return "#{h_state_str} nowrap"
            scope.show_host_attempt_info = (srv_entry) ->
                return scope.show_attempt_info(scope.host_lut[srv_entry.host_name])
            scope.show_attempt_info = (entry) ->
                try
                    if parseInt(entry.current_attempt) == 1
                        return false
                    else
                        return true
                catch error
                    return true
            scope.get_host_attempt_info = (srv_entry) ->
                return scope.get_attempt_info(scope.host_lut[srv_entry.host_name])
            scope.get_attempt_info = (entry) ->
                if entry.max_check_attempts == null
                    return "N/A"
                try
                    max = parseInt(entry.max_check_attempts)
                    cur = parseInt(entry.current_attempt)
                    if cur == 1
                        return ""
                    else
                        if cur == max
                            return "#{cur}"
                        else
                            return "#{cur} / #{max}"
                catch error
                    return "e"
    }
).run(($templateCache) ->
    $templateCache.put("livestatus_template.html", livestatus_templ)
)

class mc_table
    constructor : (@xml, paginatorSettings) ->
        @name = xml.prop("tagName")
        @short_name = @name.replace(/_/g, "").replace(/list$/, "")
        @attr_list = new Array()
        @entries = []
        @xml.children().each (idx, entry) =>
            for attr in entry.attributes
                if attr.name not in @attr_list
                    @attr_list.push(attr.name)
            @entries.push(@_to_json($(entry)))
        @pagSettings = paginatorSettings.get_paginator("device_tree_base")
        @order_name = "name"
        @order_dir = true
    _to_json : (entry) =>
        _ret = new Object()
        for attr_name in @attr_list
            _ret[attr_name] = entry.attr(attr_name)
        return _ret
    toggle_order : (name) =>
        if @order_name == name
            @order_dir = not @order_dir
        else
            @order_name = name
            @order_dir = true
    get_order : () =>
        return (if @order_dir then "" else "-") + @order_name
    get_order_glyph : (name) =>
        if @order_name == name
            if @order_dir 
                _class = "glyphicon glyphicon-chevron-down"
            else
                _class = "glyphicon glyphicon-chevron-up"
        else
            _class = "glyphicon"
        return _class
        
device_livestatus_module.controller("monconfig_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "$timeout"
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, $timeout) ->
        $scope.reload_pending = false
        $scope.new_devsel = (_dev_sel, _devg_sel) ->
            #pre_sel = (dev.idx for dev in $scope.devices when dev.expanded)
            #restDataSource.reset()
            $scope.devsel_list = _dev_sel
            $scope.load_data()
        $scope.toggle_order = (name) ->
            if $scope.order_name == name
                $scope.order_dir = not $scope.order_dir
            else
                $scope.order_name = name
                $scope.order_dir = true
        $scope.get_order = () ->
            return (if $scope.order_dir then "" else "-") + $scope.order_name
        $scope.get_order_glyph = (name) ->
            if $scope.order_name == name
                if $scope.order_dir 
                    _class = "glyphicon glyphicon-chevron-down"
                else
                    _class = "glyphicon glyphicon-chevron-up"
            else
                _class = "glyphicon glyphicon-chevron-right"
            return _class
        $scope.get_long_attr_name = (name) ->
            return name.replace(/_/g, " ")
        $scope.get_short_attr_name = (name) ->
            _parts = name.split("_")
            return (_str.slice(0, 1) for _str in _parts).join("").toUpperCase() 
        $scope.load_data = () ->
            #$timeout($scope.load_data, 20000)
            $scope.reload_pending = true
            call_ajax
                url  : "{% url 'mon:get_node_config' %}"
                data : {
                    "pk_list" : angular.toJson($scope.devsel_list)
                },
                success : (xml) =>
                    if parse_xml_response(xml)
                        mc_tables = {}
                        $(xml).find("config > *").each (idx, node) => 
                            new_table = new mc_table($(node), paginatorSettings)
                            mc_tables[new_table.name] = new_table
                        $scope.$apply(
                            $scope.mc_tables = mc_tables
                            $scope.reload_pending = false
                        )
]).directive("monconfig", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("monconfig_template.html")
        link : (scope, el, attrs) ->
            scope.new_devsel((parseInt(entry) for entry in attrs["devicepk"].split(",")), [])
    }
).run(($templateCache) ->
    $templateCache.put("monconfig_template.html", monconfig_templ)
)

{% endinlinecoffeescript %}

</script>
