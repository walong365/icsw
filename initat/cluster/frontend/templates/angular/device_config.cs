{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

{% verbatim %}

dc_row_template = """
<td>
    <button class="btn btn-primary btn-xs" ng-click="expand_vt(obj)">
        <span ng_class="get_expand_class(obj)">
        </span> {{ obj.device_variable_set.length }}
        <span ng-if="var_filter.length"> / {{ obj.num_filtered }} shown<span>
    </button>
</td>
<td>{{ get_name(obj) }}</td>
<td>{{ obj.device_group_name }}</td>
<td>{{ obj.comment }}</td>
<td>local: {{ obj.local_selected.length }}<span ng-show="obj.device_type_identifier != 'MD'">, meta: {{ meta_devices[devg_md_lut[obj.device_group]].local_selected.length }}</span></td>
"""

devconftable_template = """
<table ng-show="active_configs.length" class="table table-condensed table-hover table-bordered" style="width:auto;">
    <tbody>
        <tr ng-repeat="sub_list in line_list">
            <td ng-repeat="conf_idx in sub_list" ng-class="get_td_class(conf_idx)" ng-click="click(conf_idx)">
                <div ng-show="show_config(conf_idx)">
                    <span ng-class="get_td_class_icon(conf_idx)"></span>&nbsp;{{ get_config_info(conf_idx) }}&nbsp;<span class="pull-right badge" ng-bind-html="get_config_type(conf_idx)"></span>
                </div>
                <span ng-show="!show_config(conf_idx) && config_exists(conf_idx)">---</span>
            </td>
        </tr>
    </tbody>
</table>
"""

device_location_template = """
<h2>Device location for <ng-pluralize count="device_pks.length" when="{'one':'1 device', 'other':'{} devices'}"></ng-pluralize></h2>
<div class="row">
    <div class="col-md-6">
        <h3>Tree</h3>
        <tree treeconfig="loc_tree"></tree>
    </div>
    <div class="col-md-6" ng-show="gfx_cat">
        <locationlist></locationlist>
    </div>
    <div class="row" ng-show="gfx_cat && active_loc_gfx">
        <locationmap></locationmap>
    </div>
</div>
"""

location_map_template = """
<div class="col-md-12">
    <image ng-src="{{ active_loc_gfx.image_url }}" width="1024" height="768"></image>
</div>
"""

location_list_template = """
<h3>Location maps for {{ gfx_cat.full_name }} ({{ gfx_cat.location_gfxs.length }})</h3>
<ul class="list-group">
    <li class="list-group-item" ng-repeat="loc_gfx in get_location_gfxs(gfx_cat)">
        <input type="button" ng-class="loc_gfx.idx == active_loc_gfx.idx && 'btn btn-sm btn-success' || 'btn btn-sm btn-default'" value="show" ng-click="activate_loc_gfx(loc_gfx)"></input>
        {{ loc_gfx.name }}<span ng-show="loc_gfx.comment"> ({{ loc_gfx.comment }})</span>
        , {{ loc_gfx.image_name }} {{ loc_gfx.width }} x {{ loc_gfx.height }} ({{ loc_gfx.content_type }})
        <image ng-src="{{ loc_gfx.icon_url }}" width="24" height="24"></image>
    </li>
</ul>
"""

device_config_template = """
<h2>
    Device config ({{ devices.length }} devices), {{ configs.length }} configurations ({{ active_configs.length }} shown)
</h2>
<div class="form-inline">
    <input class="form-control" ng-model="name_filter" placeholder="filter"></input>,
    <input
        type="button"
        ng-class="only_selected && 'btn btn-sm btn-success' || 'btn btn-sm'"
        ng-click="only_selected = !only_selected"
        value="only selected"
        title="show only configs selected anywhere in the current selection"
    ></input>
    <div class="form-group" ng-show="acl_create(null, 'backbone.config.modify_config') && config_catalogs.length > 0">
        <input placeholder="new config" ng-model="new_config_name" class="form-control input-sm"></input>
        <div class="btn-group" ng-show="new_config_name">
            <button type="button" class="btn btn-sm btn-success dropdown-toggle" data-toggle="dropdown">
                Create in catalog <span class="caret"></span>
            </button>
            <ul class="dropdown-menu">
                <li ng-repeat="entry in config_catalogs" ng-click="create_config(entry.idx)"><a href="#">{{ entry.name }}</a></li>
            </ul>
        </div>
    </div>
</div>
<table ng-show="devices.length" class="table table-condensed table-hover" style="width:auto;">
    <thead>
        <tr>
            <th></th>
            <th>Device</th>
            <th>Group</th>
            <th>Comment</th>
            <th>Info</th>
        </tr>
    </thead>
    <tbody>
        <tr dcrow ng-repeat-start="obj in devices" ng-class="get_tr_class(obj)"></tr>
        <tr ng-repeat-end ng-if="obj.expanded">
            <td colspan="9"><deviceconfigtable></deviceconfigtable></td>
        </tr>
    </tbody>
</table>
"""

devconf_vars_template = """
<h2>Config variables for {{ devsel_list.length }} devices, <input type="button" class="btn btn-xs btn-primary" value="show vars" ng-click="load_vars()"></input></h2>
<div class="row">
    <div class="col-sm-5 form-inline" ng-show="loaded">
        <div class="form-group">
            <input class="form-control" ng-model="var_filter" placeholder="filter"></input>
        </div>
    </div>
</div>
<div ng-show="loaded">
    <tree treeconfig="devvar_tree"></tree>
</div>
"""

partinfo_template = """
<div>
    <tabset>
        <tab ng-repeat="dev in entries" heading="{{ dev.full_name }}" active="dev.tab_active">
            <div ng-show="dev.act_partition_table">
                <h4>
                    Partition table '{{ dev.act_partition_table.name}}',
                    <input type="button" class="btn btn-sm btn-warning" value="fetch partition info" ng-click="fetch(dev.idx)"></input>
                    <input type="button" class="btn btn-sm btn-danger" value="clear" ng-click="clear(dev.idx)" ng-show="dev.act_partition_table"></input>
                    <input type="button" class="btn btn-sm btn-success" value="use {{ dev.partition_table.name }}" ng-click="use(dev.idx)" ng-show="dev.partition_table"></input>
                </h4>
                <table class="table table-condensed table-hover table-bordered" style="width:auto;">
                    <tbody>
                        <tr ng-repeat-start="disk in dev.act_partition_table.partition_disc_set">
                            <th colspan="2">Disk {{ disk.disc }}, {{ disk.partition_set.length }} partitions</th>
                            <th>Size</th>
                            <th>warn</th>
                            <th>crit</th>
                        </tr>
                        <tr ng-repeat-end ng-repeat="part in disk.partition_set" ng-show="part.mountpoint">
                            <td>{{ disk.disc }}{{ part.pnum || '' }}</td>
                            <td>{{ part.mountpoint }}</td>
                            <td class="text-right">{{ part.size | get_size:1000000:1000 }}</td>
                            <td class="text-center">{{ part.warn_threshold }} %</td>
                            <td class="text-center">{{ part.crit_threshold }} %</td>
                        </tr>
                        <tr>
                            <th colspan="2">Logical Volumes</th>
                            <th>Size</th>
                            <th>warn</th>
                            <th>crit</th>
                        </tr>
                        <tr ng-repeat="lvm in dev.act_partition_table.lvm_lv_set | orderBy:'name'">
                            <td>/dev/{{ get_vg(dev, lvm.lvm_vg).name }}/{{ lvm.name }}</td>
                            <td>{{ lvm.mountpoint }}</td>
                            <td class="text-right">{{ lvm.size | get_size:1:1000 }}</td>
                            <td class="text-center">{{ lvm.warn_threshold }} %</td>
                            <td class="text-center">{{ lvm.crit_threshold }} %</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            <div ng-show="!dev.act_partition_table">
                <h4>
                    <span class="text-danger">No partition table defined</span>, 
                    <input type="button" class="btn btn-sm btn-warning" value="fetch partition info" ng-click="fetch(dev.idx)"></input>
                    <input type="button" class="btn btn-sm btn-success" value="use {{ dev.partition_table.name }}" ng-click="use(dev.idx)" ng-show="dev.partition_table"></input>
                </h4>
            </div>
        </tab> 
    </tabset>
</div>
"""

{% endverbatim %}

device_config_module = angular.module("icsw.device.config", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "localytics.directives"])

angular_module_setup([device_config_module])

class device_config_var_tree extends tree_config
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

device_config_module.controller("config_vars_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal) ->
        $scope.devvar_tree = new device_config_var_tree($scope)
        $scope.var_filter = ""
        $scope.loaded = false
        $scope.set_devsel = (_dev_sel, _devg_sel) ->
            $scope.devsel_list = _dev_sel
        $scope.load_vars = () ->
            if not $scope.loaded
                $scope.loaded = true
                call_ajax
                    url     : "{% url 'config:get_device_cvars' %}"
                    data    :
                        "keys" : angular.toJson($scope.devsel_list)
                    success : (xml) =>
                        parse_xml_response(xml)
                        $scope.set_tree_content($(xml).find("devices"))
        $scope.set_tree_content = (in_xml) ->
            for dev_xml in in_xml.find("device")
                dev_xml = $(dev_xml)
                dev_entry = $scope.devvar_tree.new_node({folder: true, expand:true, obj:{"name" : dev_xml.attr("name"), "info_str": dev_xml.attr("info_str"), "state_level" : parseInt(dev_xml.attr("state_level"))}, _node_type:"d"})
                $scope.devvar_tree.add_root_node(dev_entry)
                for _xml in dev_xml.find("var_tuple_list").children()
                    _xml = $(_xml)
                    t_entry = $scope.devvar_tree.new_node({folder : true, obj:{"key" : _xml.attr("key"), "value" : _xml.attr("value")}, _node_type : "c"})
                    dev_entry.add_child(t_entry)
                    _xml.children().each (idx, _sv) ->
                        _sv = $(_sv)
                        t_entry.add_child($scope.devvar_tree.new_node({folder : false, obj:{"key" : _sv.attr("key"), "value" : _sv.attr("value")}, _node_type : "v"}))
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
]).directive("deviceconfigvars", ($templateCache, $compile, $modal, Restangular) ->
    return {
        restrict : "EA"
        template : $templateCache.get("devconfvars.html")
        link : (scope, el, attrs) ->
            scope.set_devsel((parseInt(entry) for entry in attrs["devicepk"].split(",")), [])
    }
).run(($templateCache) ->
    $templateCache.put("devconfvars.html", devconf_vars_template)
)

device_config_module.controller("config_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "access_level_service",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, access_level_service) ->
        access_level_service.install($scope)
        $scope.devices = []
        $scope.configs = []
        $scope.config_catalogs = []
        $scope.active_configs = []
        $scope.name_filter = ""
        $scope.new_config_name = ""
        $scope.only_selected = false
        $scope.new_devsel = (_dev_sel, _devg_sel) ->
            $scope.devsel_list = _dev_sel
            $scope.reload()
        $scope.reload = () ->
            pre_sel = (dev.idx for dev in $scope.devices when dev.expanded)
            restDataSource.reset()
            wait_list = restDataSource.add_sources([
                ["{% url 'rest:device_tree_list' %}", {"with_device_configs" : true, "with_meta_devices" : true, "pks" : angular.toJson($scope.devsel_list), "olp" : "backbone.device.change_config"}],
                ["{% url 'rest:config_list' %}", {}]
                ["{% url 'rest:config_catalog_list' %}", {}]
            ])
            $q.all(wait_list).then((data) ->
                $scope.devices = []
                $scope.all_devices = []
                $scope.device_lut = {}
                $scope.meta_devices = {}
                $scope.devg_md_lut = {}
                # multiple name count (for names in config catalogs)
                mn_dict = {}
                for entry in data[1]
                    if entry.name not of mn_dict
                        mn_dict[entry.name] = 0
                    mn_dict[entry.name]++
                $scope.config_mn_dict = mn_dict
                for entry in data[0]
                    if entry.idx in $scope.devsel_list
                        $scope.devices.push(entry)
                        $scope.device_lut[entry.idx] = entry
                    if entry.device_type_identifier == "MD"
                        $scope.meta_devices[entry.idx] = entry
                        $scope.devg_md_lut[entry.device_group] = entry.idx
                    $scope.all_devices.push(entry)
                $scope.configs = data[1]
                $scope.config_catalogs = data[2]
                $scope.cc_lut = build_lut(data[2])
                $scope.init_devices(pre_sel)
                $scope.new_filter_set($scope.name_filter, false)
            )
        $scope.create_config = (cur_cat) ->
            new_obj = {
                "name" : $scope.new_config_name
                "config_catalog" : cur_cat
            }
            Restangular.all("{% url 'rest:config_list' %}".slice(1)).post(new_obj).then((new_data) ->
                $scope.new_config_name = ""
                $scope.reload()
            )
        $scope.get_tr_class = (obj) ->
            if obj.device_type_identifier == "MD"
                return "success"
            else
                return ""
        $scope.get_name = (obj) ->
            if obj.device_type_identifier == "MD"
                return obj.full_name.slice(8) + " [Group]"
            else
                return obj.full_name
        $scope.init_devices = (pre_sel) ->
            # called after load
            for entry in $scope.devices
                entry.local_selected = (_dc.config for _dc in entry.device_config_set)
            for idx, entry of $scope.meta_devices
                entry.local_selected = (_dc.config for _dc in entry.device_config_set)
            for entry in $scope.devices
                entry.expanded = if entry.idx in pre_sel then true else false
            $scope.configs_lut = {}
            for entry in $scope.configs
                num_vars = entry.config_str_set.length + entry.config_int_set.length + entry.config_bool_set.length + entry.config_blob_set.length
                num_ccs = entry.mon_check_command_set.length
                num_scripts = entry.config_script_set.length
                if $scope.config_mn_dict[entry.name] > 1
                    entry.info_str = "#{entry.name}[#{$scope.cc_lut[entry.config_catalog].name}] (#{num_vars}, #{num_scripts}, #{num_ccs})"
                else
                    entry.info_str = "#{entry.name} (#{num_vars}, #{num_scripts}, #{num_ccs})"
                $scope.configs_lut[entry.idx] = entry
        $scope.set_line_list = () ->
            PER_LINE = 6
            tot_len = $scope.active_configs.length
            if tot_len
                num_lines = parseInt((tot_len + PER_LINE - 1) / PER_LINE)
            else
                num_lines = 0
            cor_len = num_lines * PER_LINE
            if num_lines
                # number of empty cells
                empty_cells = cor_len - tot_len
                while empty_cells >= num_lines
                    # reduce PER_LINE to avoid empty rows
                    PER_LINE--
                    cor_len = num_lines * PER_LINE
                    empty_cells = cor_len - tot_len
            cur_idx = 0
            cur_list = []
            line_list = []
            for _idx in [0...cor_len]
                line_list.push(if cur_idx < tot_len then $scope.active_configs[cur_idx].idx else null)
                cur_idx += num_lines
                if cur_idx >= cor_len
                    cur_list.push(line_list)
                    cur_idx -= (PER_LINE * num_lines) - 1
                    line_list = []
            $scope.line_list = cur_list
        $scope.expand_vt = (obj) ->
            obj.expanded = not obj.expanded
        $scope.get_expand_class = (obj) ->
            if obj.expanded
                return "glyphicon glyphicon-chevron-down"
            else
                return "glyphicon glyphicon-chevron-right"
        $scope.$watch("name_filter", (new_val) -> $scope.new_filter_set(new_val, true))
        $scope.$watch("only_selected", (new_val) -> $scope.new_filter_set($scope.name_filter, true))
        $scope.new_filter_set = (new_val, change_expand_state) ->
            # called after filter settings have changed
            try
                cur_re = new RegExp($scope.name_filter, "gi")
            catch exc
                cur_re = new RegExp("^$", "gi")
            $scope.active_configs = []
            for entry in $scope.configs
                entry.show = if entry.name.match(cur_re) then true else false
                if $scope.only_selected and entry.show
                    sel = false
                    for cur_dev in $scope.all_devices
                        if entry.idx in cur_dev.local_selected
                            sel = true
                    entry.show = sel
                if entry.show
                    $scope.active_configs.push(entry)
            if change_expand_state
                active_ids = (_c.idx for _c in $scope.active_configs)
                # check expansion state of meta devices
                for idx, dev of $scope.meta_devices
                    dev.expanded = if (true for _loc_c in dev.local_selected when _loc_c in active_ids).length then true else false
                for dev in $scope.devices
                    dev.expanded = if (true for _loc_c in dev.local_selected when _loc_c in active_ids).length then true else false
                    if not dev.expanded and dev.device_type_identifier != "MD"
                        dev.expanded = $scope.meta_devices[$scope.devg_md_lut[dev.device_group]].expanded
            $scope.set_line_list()
        install_devsel_link($scope.new_devsel, true)
]).directive("dcrow", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("dc_row.html")
    }
).directive("deviceconfig", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("device_config_template.html")
        link : (scope, el, attrs) ->
            if attrs["devicepk"]?
                scope.new_devsel((parseInt(entry) for entry in attrs["devicepk"].split(",")), [])
    }
).directive("deviceconfigtable", ($templateCache, $compile, $modal, Restangular) ->
    return {
        restrict : "EA"
        template : $templateCache.get("devconftable.html")
        link : (scope) ->
            scope.get_td_class = (conf_idx) ->
                _cls = ""
                is_meta_dev = scope.obj.device_type_identifier == "MD"
                meta_dev = scope.meta_devices[scope.devg_md_lut[scope.obj.device_group]]
                if conf_idx != null
                    if conf_idx in scope.obj.local_selected
                        _cls = "success"
                    if conf_idx in meta_dev.local_selected and not is_meta_dev
                        _cls = "warn"
                return _cls
            scope.get_config_info = (conf_idx) ->
                if conf_idx != null
                    cur_conf = scope.configs_lut[conf_idx]
                    return cur_conf.info_str
            scope.config_exists = (conf_idx) ->
                return if conf_idx != null then true else false
            scope.show_config = (conf_idx) ->
                if conf_idx != null
                    cur_conf = scope.configs_lut[conf_idx]
                    if scope.obj.device_type_identifier == "MD" and cur_conf.server_config
                        return false
                    else
                        return true
                else
                    return false
            scope.get_config_type = (conf_idx) ->
                if conf_idx != null
                    r_v = []
                    cur_conf = scope.configs_lut[conf_idx]
                    if cur_conf.server_config
                        r_v.push("S")
                    if cur_conf.system_config
                        r_v.push("Y")
                    return r_v.join("/")
                else
                    return ""
            scope.get_td_class_icon = (conf_idx) ->
                _cls = "glyphicon"
                is_meta_dev = scope.obj.device_type_identifier == "MD"
                meta_dev = scope.meta_devices[scope.devg_md_lut[scope.obj.device_group]]
                if conf_idx != null
                    if conf_idx in scope.obj.local_selected
                        _cls = "glyphicon glyphicon-ok"
                    if conf_idx in meta_dev.local_selected and not is_meta_dev
                        _cls = "glyphicon glyphicon-ok-circle"
                return _cls
            scope.click = (conf_idx) ->
                if conf_idx != null and scope.acl_create(scope.obj, 'backbone.device.change_config') and scope.show_config(conf_idx)
                    meta_dev = scope.meta_devices[scope.devg_md_lut[scope.obj.device_group]]
                    value = 1
                    if conf_idx in scope.obj.local_selected
                        value = 0
                    if conf_idx in meta_dev.local_selected
                        value = 0
                    call_ajax
                        url  : "{% url 'config:alter_config_cb' %}"
                        data : {
                            "conf_pk" : conf_idx
                            "dev_pk"  : scope.obj.idx
                            "value"   : value
                        },
                        success : (xml) =>
                            # interpret response
                            parse_xml_response(xml)
                            # at first remove all selections
                            for entry in scope.devices
                                if entry.device_group == scope.obj.device_group
                                    if conf_idx in entry.local_selected
                                        entry.local_selected = (_v for _v in entry.local_selected when _v != conf_idx) 
                            for idx, entry of scope.meta_devices
                                if entry.device_group == scope.obj.device_group
                                    if conf_idx in entry.local_selected
                                        entry.local_selected = (_v for _v in entry.local_selected when _v != conf_idx)
                            # set selection where needed 
                            $(xml).find("device_configs device_config").each (idx, cur_dc) =>
                                cur_dc = $(cur_dc)
                                dev_pk = parseInt(cur_dc.attr("device"))
                                if dev_pk of scope.meta_devices
                                    scope.meta_devices[dev_pk].local_selected.push(conf_idx)
                                else if dev_pk of scope.device_lut
                                    if not parseInt(cur_dc.attr("meta"))
                                        # only set if meta is not 1
                                        scope.device_lut[dev_pk].local_selected.push(conf_idx)
                            # force redraw
                            scope.$apply()
    }
).run(($templateCache) ->
    $templateCache.put("dc_row.html", dc_row_template)
    $templateCache.put("devconftable.html", devconftable_template)
    $templateCache.put("device_config_template.html", device_config_template)
)

class category_tree extends tree_config
    constructor: (@scope, args) ->
        super(args)
        @show_selection_buttons = false
        @show_icons = false
        @show_select = true
        @show_descendants = false
        @show_childs = false
    selection_changed: (entry) =>
        if @scope.multi_device_mode
            @scope.new_md_selection(entry)
        else
            sel_list = @get_selected((node) ->
                if node.selected
                    return [node.obj.idx]
                else
                    return []
            )
            @scope.new_selection(sel_list)
    get_name : (t_entry) ->
        cat = t_entry.obj
        if cat.depth > 1
            r_info = "#{cat.full_name} (#{cat.name})"
            num_sel = @scope.sel_dict[cat.idx].length
            if num_sel and num_sel < @scope.num_devices
                r_info = "#{r_info}, #{num_sel} of #{@scope.num_devices}"
            if cat.num_refs
                r_info = "#{r_info} (refs=#{cat.num_refs})"
            return r_info
        else if cat.depth
            return cat.full_name
        else
            return "TOP"

cat_ctrl = device_config_module.controller("category_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "access_level_service",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, access_level_service) ->
        access_level_service.install($scope)
        $scope.cat_tree = new category_tree($scope, {})            
        $scope.reload = (pk_str) ->
            if pk_str.match(/,/)
                $scope.multi_device_mode = true
                $scope.device_pks = (parseInt(_val) for _val in pk_str.split(","))
            else
                $scope.multi_device_mode = false
                $scope.device_pks = [parseInt(pk_str)]
            wait_list = [
                restDataSource.reload(["{% url 'rest:category_list' %}", {}])
                restDataSource.reload(["{% url 'rest:device_tree_list' %}", {"pks" : angular.toJson($scope.device_pks), "with_categories" : true}])
            ]
            $q.all(wait_list).then((data) ->
                $scope.devices = data[1]
                $scope.num_devices = $scope.devices.length
                $scope.cat_tree.change_select = true
                for dev in $scope.devices
                    # check all devices and disable change button when not all devices are in allowed list
                    if not $scope.acl_all(dev, "backbone.device.change_category", 7)
                        $scope.cat_tree.change_select = false
                cat_tree_lut = {}
                $scope.cat_tree.clear_root_nodes()
                # selection dict
                sel_dict = {}
                for entry in data[0]
                    if entry.full_name.match(/^\/device/)
                        sel_dict[entry.idx] = []
                for dev in $scope.devices
                    for _sel in dev.categories
                        if _sel of sel_dict
                            sel_dict[_sel].push(entry.idx)
                $scope.sel_dict = sel_dict
                for entry in data[0]
                    if entry.full_name.match(/^\/device/)
                        t_entry = $scope.cat_tree.new_node({folder:false, obj:entry, expand:entry.depth < 2, selected: sel_dict[entry.idx].length == $scope.num_devices})
                        cat_tree_lut[entry.idx] = t_entry
                        if entry.parent and entry.parent of cat_tree_lut
                            cat_tree_lut[entry.parent].add_child(t_entry)
                        else
                            # hide selection from root nodes
                            t_entry._show_select = false
                            $scope.cat_tree.add_root_node(t_entry)
                $scope.cat_tree_lut = cat_tree_lut
                $scope.cat_tree.show_selected(false)
            )
        $scope.new_md_selection = (entry) ->
            # for multi-device selection
            cat = entry.obj
            call_ajax
                url     : "{% url 'base:change_category' %}"
                data    :
                    "obj_type" : "device"
                    "multi"    : "1"
                    "obj_pks"  : angular.toJson((_entry.idx for _entry in $scope.devices))
                    "set"      : if entry.selected then "1" else "0"
                    "cat_pk"   : cat.idx
                success : (xml) =>
                    parse_xml_response(xml)
                    $scope.$apply(
                        if entry.selected
                            $scope.sel_dict[cat.idx] = (_entry.idx for _entry in $scope.devices)
                        else
                            $scope.sel_dict[cat.idx] = []
                        reload_sidebar_tree((_dev.idx for _dev in $scope.devices))
                    )
        $scope.new_selection = (sel_list) =>
            # only for single-device mode
            call_ajax
                url     : "{% url 'base:change_category' %}"
                data    :
                    "obj_type" : "device"
                    "obj_pk"   : $scope.devices[0].idx
                    "subtree"  : "/device"
                    "cur_sel"  : angular.toJson(sel_list)
                success : (xml) =>
                    parse_xml_response(xml)
                    # selectively reload sidebar tree
                    reload_sidebar_tree([$scope.devices[0].idx])
]).directive("devicecategory", ($templateCache, $compile, $modal, Restangular) ->
    return {
        restrict : "EA"
        link : (scope, el, attrs) ->
            if attrs["devicepk"]?
                scope.reload(attrs["devicepk"])
    }
)

class location_tree extends tree_config
    constructor: (@scope, args) ->
        super(args)
        @show_selection_buttons = false
        @show_icons = false
        @show_select = true
        @show_descendants = false
        @show_childs = false
        @single_select = true
    selection_changed: (entry) =>
        if @scope.multi_device_mode
            @scope.new_md_selection(entry)
        else
            sel_list = @get_selected((node) ->
                if node.selected
                    return [node.obj.idx]
                else
                    return []
            )
            @scope.new_selection(sel_list)
    get_name : (t_entry) ->
        cat = t_entry.obj
        if cat.depth > 1
            r_info = "#{cat.full_name} (#{cat.name})"
            num_sel = @scope.sel_dict[cat.idx].length
            if num_sel and num_sel < @scope.num_devices
                r_info = "#{r_info}, #{num_sel} of #{@scope.num_devices}"
            if cat.num_refs
                r_info = "#{r_info} (refs=#{cat.num_refs})"
            num_locs = cat.location_gfxs.length
            if num_locs
                r_info = "#{r_info}, #{num_locs} location gfx"
            return r_info
        else if cat.depth
            return cat.full_name
        else
            return "TOP"
    handle_click: (t_entry) ->
        cat = t_entry.obj
        @clear_active()
        if cat.depth > 1 and cat.location_gfxs.length
            if cat != @scope.gfx_cat    
                @scope.active_loc_gfx = undefined
            @scope.gfx_cat = cat
            t_entry.active = true
        else
            @scope.active_loc_gfx = undefined
            @scope.gfx_cat = undefined    
        @show_active()

loc_ctrl = device_config_module.controller("location_ctrl", ["$scope", "restDataSource", "$q", "access_level_service",
    ($scope, restDataSource, $q, access_level_service) ->
        access_level_service.install($scope)
        $scope.loc_tree = new location_tree($scope, {})
        # category with gfx 
        $scope.gfx_cat = undefined
        $scope.active_loc_gfx = undefined
        $scope.reload = (pk_str) ->
            if pk_str.match(/,/)
                $scope.multi_device_mode = true
                $scope.device_pks = (parseInt(_val) for _val in pk_str.split(","))
            else
                $scope.multi_device_mode = false
                $scope.device_pks = [parseInt(pk_str)]
            wait_list = [
                restDataSource.reload(["{% url 'rest:category_list' %}", {}])
                restDataSource.reload(["{% url 'rest:device_tree_list' %}", {"pks" : angular.toJson($scope.device_pks), "with_categories" : true}])
                restDataSource.reload(["{% url 'rest:location_gfx_list' %}", {}])
            ]
            $q.all(wait_list).then((data) ->
                $scope.devices = data[1]
                $scope.location_gfxs = data[2]
                $scope.num_devices = $scope.devices.length
                $scope.loc_tree.change_select = true
                for dev in $scope.devices
                    # check all devices and disable change button when not all devices are in allowed list
                    if not $scope.acl_all(dev, "backbone.device.change_location", 7)
                        $scope.loc_tree.change_select = false
                loc_tree_lut = {}
                $scope.loc_tree.clear_root_nodes()
                # selection dict
                sel_dict = {}
                for entry in data[0]
                    if entry.full_name.match(/^\/location/)
                        sel_dict[entry.idx] = []
                        entry.location_gfxs = (loc_gfx.idx for loc_gfx in $scope.location_gfxs when loc_gfx.location == entry.idx)
                for dev in $scope.devices
                    for _sel in dev.categories
                        if _sel of sel_dict
                            sel_dict[_sel].push(dev.idx)
                $scope.sel_dict = sel_dict     
                for entry in data[0]
                    if entry.full_name.match(/^\/location/)
                        t_entry = $scope.loc_tree.new_node({folder:false, obj:entry, expand:entry.depth < 2, selected: sel_dict[entry.idx].length == $scope.num_devices})
                        loc_tree_lut[entry.idx] = t_entry
                        if entry.parent and entry.parent of loc_tree_lut
                            loc_tree_lut[entry.parent].add_child(t_entry)
                        else
                            # hide selection from root nodes
                            t_entry._show_select = false
                            $scope.loc_tree.add_root_node(t_entry)
                $scope.loc_tree_lut = loc_tree_lut
                $scope.loc_tree.show_selected(false)
            )
        $scope.new_md_selection = (entry) ->
            # for multi-device selection
            cat = entry.obj
            call_ajax
                url     : "{% url 'base:change_category' %}"
                data    :
                    "obj_type" : "device"
                    "multi"    : "1"
                    "obj_pks"  : angular.toJson((_entry.idx for _entry in $scope.devices))
                    "set"      : if entry.selected then "1" else "0"
                    "cat_pk"   : cat.idx
                success : (xml) =>
                    parse_xml_response(xml)
                    $scope.$apply(
                        $scope.update_tree(angular.fromJson($(xml).find("value[name='changes']").text()))
                        reload_sidebar_tree((_dev.idx for _dev in $scope.devices))
                    )
        $scope.new_selection = (sel_list) =>
            call_ajax
                url     : "{% url 'base:change_category' %}"
                data    :
                    "obj_type" : "device"
                    "obj_pk"   : $scope.device_pks[0]
                    "subtree"  : "/location"
                    "cur_sel"  : angular.toJson(sel_list)
                success : (xml) =>
                    parse_xml_response(xml)
                    # selectively reload sidebar tree
                    $scope.$apply(
                        $scope.update_tree(angular.fromJson($(xml).find("value[name='changes']").text()))
                        reload_sidebar_tree([$scope.devices[0].idx])
                   )
        $scope.update_tree = (changes) ->
            for add in changes.added
                _dev = add[0]
                _cat = add[1]
                $scope.sel_dict[_cat].push(_dev)
                $scope.loc_tree_lut[_cat].obj.num_refs++
            for rem in changes.removed
                _dev = rem[0]
                _cat = rem[1]
                _.remove($scope.sel_dict[_cat], (num) -> return num == _dev)
                $scope.loc_tree_lut[_cat].obj.num_refs--
        $scope.get_location_gfxs = (cat) ->
            if cat
                return (entry for entry in $scope.location_gfxs when entry.idx in cat.location_gfxs and entry.image_stored)
            else
                return []
]).run(($templateCache) ->
    $templateCache.put("device_location.html", device_location_template)
    $templateCache.put("location_list.html", location_list_template)
    $templateCache.put("location_map.html", location_map_template)
).directive("devicelocation", ($templateCache, $compile, $modal, Restangular) ->
    return {
        restrict : "EA"
        template: $templateCache.get("device_location.html")
        link : (scope, el, attrs) ->
            if attrs["devicepk"]?
                scope.reload(attrs["devicepk"])
    }
).directive("locationlist", ($templateCache, $compile, $modal, Restangular) ->
    return {
        restrict : "EA"
        template: $templateCache.get("location_list.html")
        link : (scope, el, attrs) ->
            scope.activate_loc_gfx = (loc_gfx) ->
                scope.active_loc_gfx = loc_gfx
    }
).directive("locationmap", ($templateCache, $compile, $modal, Restangular) ->
    return {
        restrict : "EA"
        template: $templateCache.get("location_map.html")
        link : (scope, el, attrs) ->
    }
)

device_config_module.controller("partinfo_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal) ->
        $scope.entries = []
        $scope.active_dev = undefined
        $scope.new_devsel = (_dev_sel, _devg_sel) ->
            $scope.devsel_list = _dev_sel
            $scope.reload()
        $scope.reload = () ->
            active_tab = (dev for dev in $scope.entries when dev.tab_active)
            restDataSource.reload(["{% url 'rest:device_tree_list' %}", {"with_disk_info" : true, "with_meta_devices" : false, "pks" : angular.toJson($scope.devsel_list), "olp" : "backbone.device.change_monitoring"}]).then((data) ->
                $scope.entries = (dev for dev in data)
                if active_tab.length
                    for dev in $scope.entries
                        if dev.idx == active_tab[0].idx
                            dev.tab_active = true
            )
        $scope.get_vg = (dev, vg_idx) ->
            return (cur_vg for cur_vg in dev.act_partition_table.lvm_vg_set when cur_vg.idx == vg_idx)[0]
        $scope.clear = (pk) ->
            if pk?
                $.blockUI()
                call_ajax
                    url     : "{% url 'mon:clear_partition' %}"
                    data    : {
                        "pk" : pk
                    }
                    success : (xml) ->
                        $.unblockUI()
                        parse_xml_response(xml)
                        $scope.reload()
        $scope.fetch = (pk) ->
            if pk?
                $.blockUI()
                call_ajax
                    url     : "{% url 'mon:fetch_partition' %}"
                    data    : {
                        "pk" : pk
                    }
                    success : (xml) ->
                        $.unblockUI()
                        parse_xml_response(xml)
                        $scope.reload()
        $scope.use = (pk) ->
            if pk?
                $.blockUI()
                call_ajax
                    url     : "{% url 'mon:use_partition' %}"
                    data    : {
                        "pk" : pk
                    }
                    success : (xml) ->
                        $.unblockUI()
                        parse_xml_response(xml)
                        $scope.reload()
]).directive("partinfo", ($templateCache, $compile, $modal, Restangular) ->
    return {
        restrict : "EA"
        template : $templateCache.get("partinfo.html")
        link : (scope, el, attrs) ->
            scope.new_devsel((parseInt(entry) for entry in attrs["devicepk"].split(",")), [])
    }
).run(($templateCache) ->
    $templateCache.put("partinfo.html", partinfo_template)
)

info_ctrl = device_config_module.controller("deviceinfo_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "access_level_service",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, access_level_service) ->
        access_level_service.install($scope)
        $scope.show_uuid = false
        $scope.image_url = ""
        $scope.get_image_src = () ->
            img_url = ""
            if $scope._edit_obj.mon_ext_host
                for entry in $scope.mon_ext_host_list
                    if entry.idx == $scope._edit_obj.mon_ext_host
                        img_url = entry.data_image
            return img_url
        $scope.toggle_uuid = () ->
            $scope.show_uuid = !$scope.show_uuid
        $scope.modify = () ->
            if not $scope.form.$invalid
                if $scope.acl_modify($scope._edit_obj, "backbone.device.change_basic")
                    if $scope._edit_obj.device_type_identifier == "MD"
                        $scope._edit_obj.name = "METADEV_" + $scope._edit_obj.name
                    $scope._edit_obj.put().then(() ->
                        if $scope._edit_obj.device_type_identifier == "MD"
                            $scope._edit_obj.name = $scope._edit_obj.name.substr(8)
                        # selectively reload sidebar tree
                        reload_sidebar_tree([$scope._edit_obj.idx])
                    )
            else
                noty
                    text : "form validation problem"
                    type : "warning"
]).directive("deviceinfo", ($templateCache, $compile, $modal, Restangular, restDataSource, $q) ->
    return {
        restrict : "EA"
        # bugfix for ui-select2, not working ...
        priority : 2
        link : (scope, element, attrs) ->
            scope._edit_obj = null
            if attrs["devicepk"]?
                scope.device_pk = parseInt(attrs["devicepk"])
                wait_list = [
                    restDataSource.reload(["{% url 'rest:fetch_forms' %}", {"forms" : angular.toJson(["device_info_form"])}])
                    restDataSource.reload(["{% url 'rest:domain_tree_node_list' %}", {}])
                    restDataSource.reload(["{% url 'rest:mon_device_templ_list' %}", {}])
                    restDataSource.reload(["{% url 'rest:mon_ext_host_list' %}", {}])
                    restDataSource.reload(["{% url 'rest:device_tree_list' %}", {"with_network" : true, "with_monitoring_hint" : true, "with_disk_info" : true, "pks" : angular.toJson([scope.device_pk]), "ignore_cdg" : false}])
                ]
                $q.all(wait_list).then((data) ->
                    form = data[0][0].form
                    scope.domain_tree_node = data[1]
                    scope.mon_device_templ_list = data[2]
                    scope.mon_ext_host_list = data[3]
                    scope._edit_obj = data[4][0]
                    if scope._edit_obj.device_type_identifier == "MD"
                        scope._edit_obj.name = scope._edit_obj.name.substr(8)
                    element.append($compile(form)(scope))
                )
            else
                scope.device_pk = null
            scope.is_device = () ->
                return if scope._edit_obj.device_type_identifier in ["MD"] then false else true
            scope.get_monitoring_hint_info = () ->
                if scope._edit_obj.monitoring_hint_set.length
                    mhs = scope._edit_obj.monitoring_hint_set
                    return "#{mhs.length} (#{(entry for entry in mhs when entry.check_created).length} used for service checks)"
                else
                    return "---"
            scope.get_ip_info = () ->
                if scope._edit_obj?
                    ip_list = []
                    for _nd in scope._edit_obj.netdevice_set
                        for _ip in _nd.net_ip_set
                            ip_list.push(_ip.ip)
                    if ip_list.length
                        return ip_list.join(", ")
                    else
                        return "none"
                else
                    return "---"
    }
)

{% verbatim %}

mh_devrow_template = """
<td>
    <button class="btn btn-primary btn-xs" ng-click="expand_vt(obj)">
        <span ng_class="get_expand_class(obj)">
        </span> {{ obj.device_variable_set.length }}
        <span ng-if="var_filter.length"> / {{ obj.num_filtered }} shown<span>
    </button>
</td>
<td>{{ obj.full_name }}</td>
<td>{{ obj.device_group_name }}</td>
<td>{{ obj.comment }}</td>
<td>hints : {{ obj.monitoring_hint_set.length }}</td>
"""

mh_row_template = """
<td title="from run {{ hint.call_idx }}">{{ hint.m_type }}</td>
<td>{{ hint.key }}</td>
<td>{{ hint.persistent | yesno1 }}</td>
<td>{{ hint.datasource }}</td>
<td>{{ get_v_type() }}</td>
<td class="text-right" ng-class="get_td_class('lower_crit')">{{ get_limit('lower_crit') }}</td>
<td class="text-right" ng-class="get_td_class('lower_warn')">{{ get_limit('lower_warn') }}</td>
<td class="text-right" ng-class="get_td_class('upper_warn')">{{ get_limit('upper_warn') }}</td>
<td class="text-right" ng-class="get_td_class('upper_crit')">{{ get_limit('upper_crit') }}</td>
<td class="text-center"><input ng-show="hint.datasource != 'p'" type="button" class="btn btn-xs btn-danger" value="delete" ng-click="delete_hint()"></input></td>
<td class="text-right success">{{ get_value() }}</td>>
<td>{{ hint.info }}</td>
"""

mh_table_template = """
<table class="table table-condensed table-hover table-bordered" style="width:auto;">
    <thead>
        <tr>
            <th>Source</th>
            <th>key</th>
            <th title="entry is persistent">pers</th>
            <th title="datasource">ds</th>
            <th>Type</th>
            <th>lower crit</th>
            <th>lower warn</th>
            <th>upper warn</th>
            <th>upper crit</th>
            <th>value</th>
            <th>action</th>
            <th>info</th>
        </tr>
    </thead>
    <tbody>
        <tr mhrow ng-repeat="hint in obj.monitoring_hint_set"></tr>
    </tbody>
</table>
"""

mh_template = """
<h2>
    Monitoring hint ({{ devices.length }} devices)
</h2>
<table ng-show="devices.length" class="table table-condensed table-hover" style="width:auto;">
    <thead>
        <tr>
            <th></th>
            <th>Device</th>
            <th>Group</th>
            <th>Comment</th>
            <th>Info</th>
        </tr>
    </thead>
    <tbody>
        <tr mhdevrow ng-repeat-start="obj in devices" ng-class="get_tr_class(obj)"></tr>
        <tr ng-repeat-end ng-if="obj.expanded" ng-show="obj.monitoring_hint_set.length">
            <td colspan="9"><monitoringhinttable></monitoringhinttable></td>
        </tr>
    </tbody>
</table>
"""

{% endverbatim %}

# monitoring hint controller
device_config_module.controller("monitoring_hint_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "access_level_service",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, access_level_service) ->
        access_level_service.install($scope)
        $scope.devices = []
        $scope.configs = []
        $scope.new_devsel = (_dev_sel, _devg_sel) ->
            $scope.devsel_list = _dev_sel
            $scope.reload()
        $scope.reload = () ->
            pre_sel = (dev.idx for dev in $scope.devices when dev.expanded)
            restDataSource.reset()
            wait_list = restDataSource.add_sources([
                ["{% url 'rest:device_tree_list' %}", {"with_monitoring_hint" : true, "pks" : angular.toJson($scope.devsel_list), "olp" : "backbone.device.change_monitoring"}],
            ])
            $q.all(wait_list).then((data) ->
                $scope.devices = []
                $scope.device_lut = {}
                for entry in data[0]
                    entry.expanded = true
                    $scope.devices.push(entry)
                    $scope.device_lut[entry.idx] = entry
                #$scope.init_devices(pre_sel)
                #$scope.new_filter_set($scope.name_filter, false)
            )
        $scope.get_tr_class = (obj) ->
            if obj.device_type_identifier == "MD"
                return "success"
            else
                return ""
        $scope.expand_vt = (obj) ->
            obj.expanded = not obj.expanded
        $scope.get_expand_class = (obj) ->
            if obj.expanded
                return "glyphicon glyphicon-chevron-down"
            else
                return "glyphicon glyphicon-chevron-right"
        $scope.remove_hint = (hint) ->
            _.remove($scope.device_lut[hint.device].monitoring_hint_set, (entry) -> return entry.idx == hint.idx)
            call_ajax
                url     : "{% url 'mon:delete_hint' %}"
                data    :
                    hint_pk : hint.idx
        install_devsel_link($scope.new_devsel, false)
]).directive("mhdevrow", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("mhdevrow.html")
    }
).directive("mhrow", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("mhrow.html")
        link : (scope) ->
            scope.get_v_type = () ->
                return {"f" : "float", "i" : "int", "s" : "string"}[scope.hint.v_type]
            scope.get_value = () ->
                return scope.hint["value_" + scope.get_v_type()]
            scope.get_td_class = (name) ->
                v_type = scope.get_v_type()
                key = "#{name}_#{v_type}"
                skey = "#{key}_source"
                if scope.hint[skey] == "n"
                    return ""
                else if scope.hint[skey] == "s"
                    return "warning"
                else if scope.hint[skey] == "u"
                    return "success"
            scope.get_limit = (name) ->
                v_type = scope.get_v_type()
                key = "#{name}_#{v_type}"
                skey = "#{key}_source"
                if scope.hint[skey] == "s" or scope.hint[skey] == "u"
                    return scope.hint[key]
                else
                    return "---"
            scope.delete_hint = () ->
                scope.remove_hint(scope.hint)
    }
).directive("monitoringhint", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("mh.html")
        link : (scope, el, attrs) ->
            if attrs["devicepk"]?
                scope.new_devsel((parseInt(entry) for entry in attrs["devicepk"].split(",")), [])
    }
).directive("monitoringhinttable", ($templateCache, $compile, $modal, Restangular) ->
    return {
        restrict : "EA"
        template : $templateCache.get("mhtable.html")
        link : (scope) ->
    }
).run(($templateCache) ->
    $templateCache.put("mhdevrow.html", mh_devrow_template)
    $templateCache.put("mhrow.html", mh_row_template)
    $templateCache.put("mh.html", mh_template)
    $templateCache.put("mhtable.html", mh_table_template)
)

add_tree_directive(cat_ctrl)

{% endinlinecoffeescript %}

</script>
