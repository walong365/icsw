{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

{% verbatim %}

livestatus_templ = """
<!-- <d3test data="testData"></d3test>
<arctest data="testData"></arctest> -->
<table class="table table-condensed table-hover table-striped" style="font-size:100%;">
    <thead>
        <tr>
            <th colspan="99">
                Number of hosts / checks : {{ host_entries.length }} / {{ entries.length }}
            </th>
        </tr>
        <tr>
            <td colspan="99">
                <div class="row">
                    <div class="col-md-6">
                        <tree treeconfig="cat_tree" ng-mouseenter="show_cat_tree()" ng-mouseleave="hide_cat_tree()"></tree>
                    </div>
                </div>
                <div class="row">
                    <div class="col-md-6">
                        <bursttest data="burstData" active-service="activeService" focus-service="focusService" trigger-redraw="redrawSunburst"></bursttest>
                    </div> 
                    <div class="col-md-6">
                        <serviceinfo type="service_type" service="current_service"></serviceinfo>
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
                        title="{{ entry[3] }}"
                    >
                    </input>
                </div>
                <div class="btn-group">
                    <input ng-repeat="entry in sh_states" type="button"
                        ng-class="get_shs_class(entry[0])"
                        ng-value="entry[1]"
                        ng-click="toggle_shs(entry[0])"
                        title="{{ entry[3] }}"
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

serviceinfo_templ = """
    <h3 ng-show="type">Type: {{ type }}</h3>
    <div ng-switch="type">
        <div ng-switch-when="system">
           <ul class="list-group">
               <li class="list-group-item">System</li>
           </ul>
        </div>
        <div ng-switch-when="group">
           <ul class="list-group">
               <li class="list-group-item">Devicegroup<span class="pull-right">{{ service.group_name }}</span></li>
               <li class="list-group-item">State<span ng-class="get_state_class(service)">{{ get_state_string(service) }}</span></li>
           </ul>
        </div>
        <div ng-switch-when="host">
            <ul class="list-group">
                <li class="list-group-item">Devicegroup<span class="pull-right">{{ service.group_name }}</span></li>
                <li class="list-group-item">Device<span class="pull-right">{{ service.host_name }} ({{ service.address }})</span></li>
                <li class="list-group-item">Output<span class="pull-right">{{ service.plugin_output }}</span></li>
                <li class="list-group-item">State<span ng-class="get_state_class(service)">{{ get_state_string(service) }}</span></li>
                <li class="list-group-item">State type<span class="pull-right">{{ get_state_type(service) }}</span></li>
                <li class="list-group-item">Check type<span class="pull-right">{{ get_check_type(service) }}</span></li>
                <li class="list-group-item">attempts<span class="badge pull-right">{{ get_attempt_info(service) }}</span></li>
            </ul>
        </div>
        <div ng-switch-when="service">
            <ul class="list-group">
                <li class="list-group-item">Device<span class="pull-right">{{ service.host_name }}</span></li>
                <li class="list-group-item">Description<span class="pull-right">{{ service.description }}</span></li>
                <li class="list-group-item">Output<span class="pull-right">{{ service.plugin_output }}</span></li>
                <li class="list-group-item">State<span ng-class="get_state_class(service)">{{ get_state_string(service) }}</span></li>
                <li class="list-group-item">State type<span class="pull-right">{{ get_state_type(service) }}</span></li>
                <li class="list-group-item">Check type<span class="pull-right">{{ get_check_type(service) }}</span></li>
                <li class="list-group-item">attempts<span class="badge pull-right">{{ get_attempt_info(service) }}</span></li>
            </ul>
        </div>
    </div>
"""

{% endverbatim %}

device_livestatus_module = angular.module("icsw.device.livestatus", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular", "icsw.d3"])

angular_module_setup([device_livestatus_module])

add_tree_directive(device_livestatus_module)

get_state_string = (entry) ->
    return {
        0 : "OK"
        1 : "Warning"
        2 : "Critical"
        3 : "Unknown"
    }[entry.state]

get_state_class = (entry) ->
    return {
        0 : "success"
        1 : "warning"
        2 : "danger"
        3 : "danger"
    }[entry.state]

show_attempt_info = (entry) ->
    try
        if parseInt(entry.current_attempt) == 1
            return false
        else
            return true
    catch error
       return true

get_attempt_info = (entry, force=false) ->
    if entry.max_check_attempts == null
        return "N/A"
    try
        max = parseInt(entry.max_check_attempts)
        cur = parseInt(entry.current_attempt)
        if cur == 1 and not force
            return ""
        else
            if cur == max
                return "#{cur}"
            else
                return "#{cur} / #{max}"
    catch error
        return "e"

get_state_type = (entry) ->
    return {
        null : "???"
        0 : "soft"
        1 : "hard"
    }[entry.state_type]

get_check_type = (entry) ->
    return {
        null : "???"
        0 : "active"
        1 : "passive"
    }[entry.check_type]

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
        $scope.host_entries = []
        $scope.entries = []
        $scope.order_name = "host_name"
        $scope.order_dir = true
        $scope.md_filter_str = ""
        # not needed
        #$scope.cur_timeout = undefined
        $scope.activeService = null
        $scope.focusService = null
        $scope.redrawSunburst = 0
        # which devices to show
        $scope.show_devs = []
        # which service to show
        $scope.show_service = null
        $scope.$watch("activeService", (as) ->
            _parsed = $scope.parse_service(as)
            $scope.service_type = _parsed[0]
            $scope.current_service = _parsed[1]
        )
        $scope.$watch("focusService", (nf) ->
            _parsed = $scope.parse_service(nf)
            _type = _parsed[0]
            _service = _parsed[1]
            $scope.show_service = null
            switch _type
                when "system"
                    # show all
                    show_devs = []
                when "group"
                    show_devs = (entry.check.idx for entry in $scope.devg_lut[_service.group_name].children)
                when "host"
                    show_devs = [_service.idx]
                when "service"
                    show_devs = [_service.custom_variables.device_pk]
                    $scope.show_service = _service
                else
                    # default (equal to system)
                    show_devs = []
            $scope.show_devs = show_devs
            $scope.md_filter_changed()
        )
        $scope.parse_service = (srv) ->
            # parse compacted service identifier
            if srv
                _type = srv.split("_")[0]
                _idx = parseInt(srv.split("_")[1])
                switch _type
                    when "system"
                        _service = {"system"}
                    when "group"
                        _service = $scope.devg_lut[_idx].check
                    when "host"
                        _service = $scope.dev_tree_lut[_idx].sunburst.check
                    when "service"
                        _service = $scope.srv_lut[_idx]  
            else
                _type = ""
                _service = null
            return [_type, _service]
        # paginator settings
        $scope.pagSettings = paginatorSettings.get_paginator("device_tree_base", $scope)
        # category tree
        $scope.cat_tree = new category_tree($scope, {})
        # selected categories
        $scope.selected_mcs = []
        $scope.master_cat_pk = 0
        $scope.show_unspec_cat = true
        $scope.testData = []
        $scope.burstData = {"name" : "empty", "children" : []}
        $scope.show_options = [
            # 1 ... option local name
            # 2 ... option display name
            # 3 ... default value
            # 4 ... enable sort
            ["host_name"    , "node name", true, true],
            ["state"        , "state", true, true],
            ["description"  , "description", true, true],
            ["cats"         , "categories", false, false],
            ["state_type"   , "state type", false, false],
            ["last_check"   , "last check", true, false],
            ["last_change"  , "last change", false, false],
            ["plugin_output", "result", true, true],
        ]
        # int_state, str_state, default
        $scope.md_states = [
            [0, "O", true, "show OK states"]
            [1, "W", true, "show warning states"]
            [2, "C", true, "show critcal states"]
            [3, "U", true, "show unknown states"]
        ]
        $scope.sh_states = [
            [0, "S", true, "show soft states"]
            [1, "H", true, "show hard states"]
        ]
        $scope.so_enabled = {}
        for entry in $scope.show_options
            $scope.so_enabled[entry[0]] = entry[2]
        $scope.mds_enabled = {}
        for entry in $scope.md_states
            $scope.mds_enabled[entry[0]] = entry[2]
        $scope.shs_enabled = {}
        for entry in $scope.sh_states
            $scope.shs_enabled[entry[0]] = entry[2]
        $scope.get_so_class = (short) ->
            return if $scope.so_enabled[short] then "btn btn-xs btn-success" else "btn btn-xs"
        $scope.toggle_so = (short) ->
            $scope.so_enabled[short] = !$scope.so_enabled[short]
        $scope.get_mds_class = (int_state) ->
            return if $scope.mds_enabled[int_state] then "btn btn-xs " + {0 : "btn-success", 1 : "btn-warning", 2 : "btn-danger", 3 : "btn-danger"}[int_state] else "btn btn-xs"
        $scope.get_shs_class = (int_state) ->
            return if $scope.shs_enabled[int_state] then "btn btn-xs btn-success" else "btn btn-xs"
        $scope.toggle_mds = (int_state) ->
            $scope.mds_enabled[int_state] = !$scope.mds_enabled[int_state]
            $scope.md_filter_changed()
        $scope.toggle_shs = (int_state) ->
            $scope.shs_enabled[int_state] = !$scope.shs_enabled[int_state]
            $scope.md_filter_changed()
        $scope.new_devsel = (_dev_sel, _devg_sel) ->
            #pre_sel = (dev.idx for dev in $scope.devices when dev.expanded)
            #restDataSource.reset()
            $scope.devsel_list = _dev_sel
            $scope.load_static_data()
        $scope.show_cat_tree = () ->
            $scope.cat_tree.toggle_expand_tree(1, false)
        $scope.hide_cat_tree = () ->
            $scope.cat_tree.toggle_expand_tree(-1, false)
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
                restDataSource.reload(["{% url 'rest:device_tree_list' %}", {"with_meta_devices" : false, "ignore_cdg" : true}])
            ]
            $q.all(wait_list).then((data) ->
                cat_tree_lut = {}
                $scope.cat_tree.clear_root_nodes()
                $scope.selected_mcs = []
                for entry in data[0]
                    if entry.full_name.match(/^\/mon/)
                        entry.short_name = entry.full_name.substring(5)
                        t_entry = $scope.cat_tree.new_node({folder:false, obj:entry, expand:entry.depth < 1, selected: true})
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
                $scope.dev_tree_lut = build_lut(data[1])
                $scope.load_data()
            )
        $scope.load_data = () ->
            $scope.cur_timeout = $timeout($scope.load_data, 20000)#20000)
            $scope.cur_xhr = call_ajax
                url  : "{% url 'mon:get_node_status' %}"
                data : {
                    "pk_list" : angular.toJson($scope.devsel_list)
                },
                success : (xml) =>
                    if parse_xml_response(xml)
                        service_entries = []
                        $(xml).find("value[name='service_result']").each (idx, node) =>
                            service_entries = service_entries.concat(angular.fromJson($(node).text()))
                        host_entries = []
                        $(xml).find("value[name='host_result']").each (idx, node) =>
                            host_entries = host_entries.concat(angular.fromJson($(node).text()))
                        $scope.$apply(
                            used_cats = []
                            $scope.entries = service_entries
                            $scope.host_entries = host_entries
                            $scope.host_lut = {}
                            for entry in host_entries
                                # sanitize entries
                                $scope._sanitize_entries(entry)
                                entry.custom_variables = $scope.parse_custom_variables(entry.custom_variables)
                                $scope.host_lut[entry.host_name] = entry
                            for entry in service_entries
                                # sanitize entries
                                $scope._sanitize_entries(entry)
                                entry.custom_variables = $scope.parse_custom_variables(entry.custom_variables)
                                if entry.custom_variables and entry.custom_variables.cat_pks?
                                    used_cats = _.union(used_cats, entry.custom_variables.cat_pks)
                            for pk of $scope.cat_tree_lut
                                entry = $scope.cat_tree_lut[pk]
                                if parseInt(pk) in used_cats
                                    entry._show_select = true 
                                else
                                    entry.selected = false
                                    entry._show_select = false 
                            $scope.md_filter_changed()
                            $scope.testData = [
                                {name : "services", count : service_entries.length, color : "red"}
                                {name : "hosts", count : host_entries.length, color : "blue"}
                                {name : "test", count : 14, color : "green"}
                            ]
                            $scope.build_sunburst()
                        )
        $scope.build_sunburst = () ->
            # build burst data
            _bdat = {
                "name" : "System"
                "children" : []
                "check" : {"state" : 0, "type" : "system", "idx" : 0}
            }
            _devg_lut = {}
            srv_lut = {}
            _idx = 0
            for entry in $scope.host_entries
                if entry.custom_variables.device_pk of $scope.dev_tree_lut
                    _dev = $scope.dev_tree_lut[entry.custom_variables.device_pk]
                    entry.idx = _dev.idx
                    entry.type = "host" 
                    if _dev.device_group_name not of _devg_lut
                        # we use the same index for devicegroups and services ...
                        _idx++
                        _devg = {
                            "name" : _dev.device_group_name,
                            "children" : [],
                            "check" : {
                                "state" : 0,
                                "type"  : "group",
                                "idx"   : _idx,
                                "group_name" : _dev.device_group_name
                            }
                        }
                        _devg_lut[_devg.name] = _devg
                        _devg_lut[_idx] = _devg
                        _bdat.children.push(_devg)
                    else
                        _devg = _devg_lut[_dev.device_group_name]
                    # sunburst struct for device
                    entry.group_name = _dev.device_group_name
                    _dev_sbs = {"name" : _dev.full_name, "children" : [], "check" : entry}
                    _devg.children.push(_dev_sbs)
                    # set devicegroup state
                    _devg.check.state = Math.max(_devg.check.state, _dev_sbs.check.state)
                    # set system state
                    _bdat.check.state = Math.max(_bdat.check.state, _devg.check.state)
                    _dev.sunburst = _dev_sbs
            for entry in $scope.entries
                _idx++
                entry.idx = _idx
                entry.type = "service"
                srv_lut[_idx] = entry
                # sanitize entries
                if entry.custom_variables.device_pk of $scope.dev_tree_lut
                    _dev = $scope.dev_tree_lut[entry.custom_variables.device_pk]
                    _dev.sunburst.children.push({
                        "name" : entry.description,
                        "children" : [],
                        "check" : entry,
                        "value" : if entry._show then 1 else 0
                    })
            # set device_group lut
            $scope.devg_lut = _devg_lut
            # set service lut
            $scope.srv_lut = srv_lut
            # remove empty devices
            for _devg in _bdat.children
                _devg.children = (entry for entry in _devg.children when entry.children.length)
            _bdat.children = (entry for entry in _bdat.children when entry.children.length)
            $scope.burstData = _bdat
        $scope.update_sunburst = () ->
            if ($scope.burstData.children ? []).length
                for _sb_devg in $scope.burstData.children
                    for _sb_dev in _sb_devg.children
                        for _sb_srv in _sb_dev.children
                            _sb_srv._show = $scope.srv_lut[_sb_srv.check.idx]._show
                            _sb_srv.value = if _sb_srv._show then 1 else 0
                $scope.redrawSunburst++
        $scope._sanitize_entries = (entry) ->
            entry.state = parseInt(entry.state)
            if entry.state_type in ["0", "1"]
                entry.state_type = parseInt(entry.state_type)
            else
                entry.state_type = null
            if entry.check_type in ["0", "1"]
                entry.check_type = parseInt(entry.check_type)
            else
                entry.check_type = null
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
                for single_key in ["check_command_pk", "device_pk"]
                    if single_key of _cv
                        _cv[single_key] = parseInt(_cv[single_key][0])
                for int_mkey in ["cat_pks"]
                    if int_mkey of _cv
                        _cv[int_mkey] = (parseInt(_sv) for _sv in _cv[int_mkey])
            return _cv
        $scope.md_filter_changed = () ->
            # called when new entries are set or a filter rule has changes
            ($scope.check_filter(entry) for entry in @entries)
            $scope.update_sunburst()
            $scope.pagSettings.set_entries(@entries)
        $scope.check_filter = (entry) ->
            show = true
            if not $scope.mds_enabled[entry.state]
                show = false
            if not $scope.shs_enabled[entry.state_type]
                show = false
            if $scope.md_filter_str
                if not $filter("filter")([entry], $scope.md_filter_str).length
                    show = false
            if show
                if not $scope.selected_mcs.length
                   show = false
                else
                    if entry.custom_variables and entry.custom_variables.cat_pks?
                        # only show if there is an intersection
                        show = if _.intersection($scope.selected_mcs, entry.custom_variables.cat_pks).length then true else false
                    else
                        # show entries with unset / empty category
                        show = $scope.show_unspec_cat
                    if show and $scope.show_devs.length 
                        show = entry.custom_variables.device_pk in $scope.show_devs
            entry._show = show
        $scope.filter_mdr = (entry, scope) ->
            return entry._show
        $scope.$on("$destroy", () ->
            if $scope.cur_timeout?
                $timeout.cancel($scope.cur_timeout)
            if $scope.cur_xhr?
                $scope.cur_xhr.abort()
        )
]).directive("serviceinfo", ["$templateCache", ($templateCache) ->
    return {
        restrict : "E"
        template : $templateCache.get("serviceinfo_template.html")
        scope : {
            type : "=type"
            service : "=service"
        }
        link : (scope, element) ->
            scope.get_state_string = (entry) ->
                return get_state_string(entry)
            scope.get_state_class = (entry) ->
                return "label label-#{get_state_class(entry)} pull-right"
            scope.get_attempt_info = (entry) ->
                return get_attempt_info(entry, true)
            scope.get_state_type = (entry) ->
                return get_state_type(entry)
            scope.get_check_type = (entry) ->
                return get_check_type(entry)
    }
]).directive("bursttest", ["d3_service", "$compile", (d3_service, $compile) ->
    get_color = (d) ->
        if d.check?
            return {
                0 : "#66dd66"
                1 : "#dddd88"
                2 : "#ff7777"
                3 : "#ff0000"
            }[d.check.state]
        else
            return "#dddddd"
    return {
        restrict : "E"
        scope: {
            data          : "=data"
            activeService : "=activeService"
            focusService  : "=focusService"
            triggerRedraw : "=triggerRedraw"
        }
        link: (scope, element) ->
            width = 600
            height = 320
            d3_service.d3().then((d3) ->
                radius = Math.min(width, height) / 2 - 40
                top_el = d3.select(element[0]).append("svg")
                    .attr("width", width)
                    .attr("height", height)
                    .attr("font-family", "'Open-Sans', sans-serif")
                    .attr("font-size", "10pt")
                svg = top_el.append("g").attr("class", "sunburst")
                    .attr("transform", "translate(#{width / 2},#{height / 2})")
                partition = d3.layout.partition()
                    .sort(null)
                    .size([2 * Math.PI, radius * radius])
                    .value((d) ->
                        return if d.value? then d.value else 1
                    )
                arc = d3.svg.arc()
                    .startAngle((d) ->
                         return d.x
                    )
                    .endAngle((d) -> return d.x + d.dx)
                    .innerRadius((d) -> return Math.sqrt(d.y))
                    .outerRadius((d) -> return Math.sqrt(d.y + d.dy))
                outer_arc = d3.svg.arc()
                    .innerRadius(140)
                    .outerRadius(140)
                    .startAngle((d) -> return d.x)
                    .endAngle((d) -> return d.x + d.dx)
                scope.unhide = (_v) ->
                    _v.value = 1
                    if _v.children?
                        (scope.unhide(_entry) for _entry in _v.children)
                scope.hide = (_v) ->
                    _v.value = 0
                    if _v.children?
                        (scope.hide(_entry) for _entry in _v.children)
                scope.render = (data) ->
                    # remove previous labels and lines
                    svg.select(".slices").remove()
                    svg.select(".labels").remove()
                    svg.select(".lines").remove()
                    svg.append("g")
                        .attr("class", "slices")
                    svg.append("g")
                        .attr("class", "labels")
                    svg.append("g")
                        .attr("class", "lines")
                    #scope.render_path()
                    lines = svg.select(".slices").datum(data).selectAll("g")
                        .data(partition.nodes)
                        .enter().append("g")
                        #.attr("display", (d) -> return if d.depth then null else "none" )
                        .on("mouseover", (d) ->
                            cur_d = d
                            path = []
                            if cur_d.check?
                                if cur_d.check.plugin_output?
                                    path.unshift(cur_d.check.plugin_output)
                            while cur_d
                                path.unshift(cur_d.name)
                                p_path = d3.select("path[_gid='#{cur_d._gid}']")
                                p_path.style("fill", d3.rgb(p_path.style("fill")).brighter())
                                #p_path.style("stroke-width", "2px")
                                cur_d = cur_d.parent ? null
                            scope.cur_path = path
                            d3.selectAll("g.labels g").attr("display", "none")
                            if d.children?
                                for _child in d.children
                                    if _child.value
                                        d3.select("g.labels g[_gid='#{_child._gid}']").attr("display", null)
                            else
                                # no children, show label
                                d3.select("g.labels g[_gid='#{d._gid}']").attr("display", null)
                            scope.$apply(() ->
                                if d? and d.check?
                                    scope.activeService = "#{d.check.type}_#{d.check.idx}"
                            )
                        ).on("mouseout", (d) ->
                            cur_d = d
                            while cur_d
                                p_path = d3.select("path[_gid='#{cur_d._gid}']")
                                p_path.style("fill", get_color(cur_d))
                                cur_d = cur_d.parent ? null
                        ).on("click", (d) ->
                            if d.parent?
                                # hide everything
                                scope.hide(scope.data)
                                # unhide local node
                                scope.unhide(d)
                                _p = d.parent
                                while _p?
                                    _p.value = 1
                                    _p = _p.parent
                            else
                                scope.unhide(scope.data)
                            scope.$apply(() ->
                                scope.focusService = "#{d.check.type}_#{d.check.idx}"
                            )
                            scope.render(scope.data)
                        )
                    _gid = 0
                    lines.append("path")
                        .attr("d", arc)
                        .style("stroke", "#000000").style("stroke-width", "0.5")
                        .attr("_gid", (d) ->
                            _gid++
                            d._gid = _gid
                            return _gid
                        )
                        .style("fill", (d) ->
                            return get_color(d)
                        )
                        #.style("fill-rule", "evenodd")
                    cur_sel = svg.select(".labels").datum(data).selectAll("g").data(partition.nodes).enter()
                        .append("g")
                        .attr("_gid", (d) ->
                            return d._gid
                        )
                        .attr("display", "none")
                    cur_sel.append("text")
                        .attr("x", (d) ->
                            return if outer_arc.centroid(d)[0] < 0 then -170 else 170
                        )
                        .attr("y", (d) ->
                            return outer_arc.centroid(d)[1]
                        )
                        .attr("text-anchor", (d) ->
                            return if outer_arc.centroid(d)[0] < 0 then "end" else "start"
                        )
                        .attr("alignment-baseline", "middle")
                        .text((d) ->
                            return d.name
                        )
                    cur_sel.append("polyline")
                        .attr("points", (d) ->
                            _koord = arc.centroid(d)
                            _nkoord = outer_arc.centroid(d)
                            if _koord[0] < 0
                                return [[-170, _nkoord[1]], _nkoord, _koord]
                            else
                                return [[170, _nkoord[1]], _nkoord, _koord]
                        ).attr("stroke", "#333333").attr("opacity", "0.4").attr("fill", "none")
                scope.$watch('data', () ->
                    scope.render(scope.data)
                    true
                )
                scope.$watch('triggerRedraw', () ->
                    scope.render(scope.data)
                )
            )
    } 
]).directive("arctest", ["d3_service", (d3_service) ->
    return {
        restrict : "E"
        scope: {
            data: "="
        }
        link: (scope, element) ->
            width = 280
            height = 160
            d3_service.d3().then((d3) ->
                radius = Math.min(width, height) / 2
                arc = d3.svg.arc().outerRadius(radius - 10).innerRadius(radius - 50)
                pie = d3.layout.pie()
                    .sort(null)
                    .value((d) ->
                        return d.count
                    )

                svg = d3.select(element[0]).append("svg")
                    .attr("width", width)
                    .attr("height", height)
                    .append("g")
                    .attr("transform", "translate(#{width / 2},#{height / 2})")
                scope.render = (data) ->
                    g = svg.selectAll(".arc")
                        .data(pie(data))
                        .enter().append("g")
                        .attr("class", "arc")
                    g.append("path")
                        .attr("d", arc)
                        .style("fill", (d) ->
                            return d.data.color
                        ).attr("stroke", "#dddddd").attr("stroke-width", "0.6px")
                    g.append("text")
                        .attr("transform", (d) ->
                            return "translate(#{arc.centroid(d)})"
                        )
                        .attr("dy", ".35em")
                        .style("text-anchor", "middle")
                        .text((d) ->
                            return d.data.color
                        )
                scope.$watch('data', () ->
                    scope.render(scope.data)
                    true
                )
            )  
    }
]).directive("d3test", ["d3_service", (d3_service) ->
    return {
        restrict : "E"
        scope: {
            data: "="
        }
        link: (scope, element) ->
            margin = {
                top: 20
                right: 20
                bottom: 20
                left: 40
            }
            width = 280 - margin.left - margin.right
            height = 160 - margin.top - margin.bottom
            d3_service.d3().then((d3) ->
                svg = d3.select(element[0])
                    .append("svg")
                    .attr("width", width + margin.left + margin.right)
                    .attr("height", height + margin.top + margin.bottom)
                    .append("g")
                    .attr("transform", "translate(#{margin.left},#{margin.top})")
                x = d3.scale.ordinal().rangeRoundBands([0, width], .1)
                y = d3.scale.linear().range([height, 0])
                xAxis = d3.svg.axis().scale(x).orient("bottom").tickSize([1])
                yAxis = d3.svg.axis().scale(y).orient("left").ticks(10).tickSize([1])
                scope.render = (data) ->
                    x.domain(data.map(
                        (d) -> 
                            return d.name
                    ))
                    y.domain([0, d3.max(data, (d) ->
                        return d.count
                    )])
                    # Redraw the axes
                    svg.selectAll("g.axis").remove()
                    # X axis
                    svg.append("g")
                        .attr("class", "x axis")
                        .attr("transform", "translate(0,#{height})")
                        .call(xAxis)
                    # Y axis
                    svg.append("g")
                        .attr("class", "y axis")
                        .call(yAxis)
                        .append("text")
                        .attr("transform", "rotate(-90)")
                        .attr("y", -30)
                        .attr("x", -40)
                        .style("text-anchor", "end")
                        .text("Count")
                    svg.selectAll(".bar").remove()
                    bars = svg.selectAll(".bar").data(data)
                    bars.enter()
                        .append("rect")
                        .attr("class", "bar")
                        .attr("x", (d) -> 
                            return x(d.name)
                         )
                        .attr("width", (d) ->
                            return x.rangeBand()
                        )
                        .attr('height', (d) ->
                            return height - y(d.count)
                        )
                        .attr("y", (d) ->
                            return y(d.count)
                        )
                        .attr("fill", (d) ->
                            return d.color
                        )
                scope.$watch('data', () ->
                    scope.render(scope.data)
                    true
                )
            )  
    }
]).directive("livestatus", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("livestatus_template.html")
        link : (scope, el, attrs) ->
            if attrs.devicepk?
                scope.new_devsel((parseInt(entry) for entry in attrs["devicepk"].split(",")), [])
            else
                install_devsel_link(scope.new_devsel, false)
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
            scope.get_categories = (entry) ->
                if entry.custom_variables
                    if entry.custom_variables.cat_pks?
                        return (scope.cat_tree_lut[_pk].obj.short_name for _pk in entry.custom_variables.cat_pks).join(", ")
                    else
                        return "---"
                else
                    return "N/A"
            scope.get_state_type = (entry) ->
                return get_state_type(entry)
            scope.get_check_type = (entry) ->
                return get_check_type(entry)
            scope.host_is_passive_checked = (entry) ->
                if entry.host_name of scope.host_lut
                    return if scope.host_lut[entry.host_name].check_type then true else false 
                else
                    return false                  
            scope.is_passive_check = (entry) ->
                return if entry.check_type then true else false 
            scope.get_host_class = (entry) ->
                if entry.host_name of scope.host_lut
                    h_state = scope.host_lut[entry.host_name].state
                    h_state_str = {
                        0 : "success"
                        1 : "danger"
                        2 : "danger"
                    }[h_state]
                else
                    h_state_str = "warning"
                return "#{h_state_str} nowrap"
            scope.get_state_string = (entry) -> 
                return get_state_string(entry)
            scope.get_state_class = (entry) -> 
                return get_state_class(entry) + " nowrap"
            scope.show_host_attempt_info = (srv_entry) ->
                return scope.show_attempt_info(scope.host_lut[srv_entry.host_name])
            scope.show_attempt_info = (entry) ->
                return show_attempt_info(entry)
            scope.get_host_attempt_info = (srv_entry) ->
                return scope.get_attempt_info(scope.host_lut[srv_entry.host_name])
            scope.get_attempt_info = (entry) ->
                return get_attempt_info(entry)
    }
).run(($templateCache) ->
    $templateCache.put("livestatus_template.html", livestatus_templ)
    $templateCache.put("serviceinfo_template.html", serviceinfo_templ)
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
            $scope.cur_timeout = $timeout($scope.load_data, 20000)
            $scope.reload_pending = true
            $scope.cur_xhr = call_ajax
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
        $scope.$on("$destroy", () ->
            if $scope.cur_timeout?
                $timeout.cancel($scope.cur_timeout)
            if $scope.cur_xhr?
                $scope.cur_xhr.abort()
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
