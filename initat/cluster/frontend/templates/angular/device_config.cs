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
                    <span ng-class="get_td_class_icon(conf_idx)"></span> {{ get_config_info(conf_idx) }}
                 </td>
            </tr>
        </tbody>
    </table>
"""

device_config_template = """
    <h2>
        Device config ({{ devices.length }} devices), {{ configs.length }} configurations ({{ active_configs.length }} shown)
    </h2>
    <div class="row">
        <div class="form-inline col-sm-3">
            <div class="form-group">
                <input class="form-control" ng-model="name_filter" placeholder="filter"></input>
            </div>,
            <span class="checkbox">
                <label>
                    only selected:
                    <input title="show only configs selected anywhere in the curren selection" type="checkbox" ng-model="only_selected"></input>
                </label>
            </span>
        </div>
        <div class="form-inline col-sm-4">
            <div class="form-group">
                <input placeholder="new config" ng-model="new_config_name" class="form-control input-sm"></input>
            </div>
            <div class="form-group">
                <input type="button" class="btn btn-success btn-sm" ng-show="new_config_name" ng-click="create_config()" value="create config"></input>
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
    <h2>Config variables for {{ devsel_list.length }} devices</h2>
    <div class="row">
        <div class="col-sm-5 form-inline">
            <div class="form-group">
                <input class="form-control" ng-model="var_filter" placeholder="filter"></input>
            </div>
        </div>
    </div>
    <div>
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
                                <td>{{ disk.disc }}{{ part.pnum }}</td>
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
                    </h4>
                </div>
            </tab> 
        </tabset>
    </div>
"""

{% endverbatim %}

device_config_module = angular.module("icsw.device.config", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular"])

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
        $scope.new_devsel = (_dev_sel, _devg_sel) ->
            $scope.devsel_list = _dev_sel
            $.ajax
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
            scope.new_devsel((parseInt(entry) for entry in attrs["devicepk"].split(",")), [])
    }
).run(($templateCache) ->
    $templateCache.put("devconfvars.html", devconf_vars_template)
)

device_config_module.controller("config_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal) ->
        $scope.devices = []
        $scope.configs = []
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
                ["{% url 'rest:device_tree_list' %}", {"with_device_configs" : true, "with_meta_devices" : true, "pks" : angular.toJson($scope.devsel_list)}],
                ["{% url 'rest:config_list' %}", {}]
            ])
            $q.all(wait_list).then((data) ->
                for value, idx in data
                    if idx == 0
                        $scope.devices = []
                        $scope.all_devices = []
                        $scope.device_lut = {}
                        $scope.meta_devices = {}
                        $scope.devg_md_lut = {}
                        for entry in value
                            if entry.idx in $scope.devsel_list
                                $scope.devices.push(entry)
                                $scope.device_lut[entry.idx] = entry
                            if entry.device_type_identifier == "MD"
                                $scope.meta_devices[entry.idx] = entry
                                $scope.devg_md_lut[entry.device_group] = entry.idx
                            $scope.all_devices.push(entry)
                    else if idx == 1
                        $scope.configs = value
                        $scope.new_filter_set($scope.name_filter, false)
                $scope.init_devices(pre_sel)
            )
        $scope.create_config = () ->
            new_obj = {
                "name" : $scope.new_config_name
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
        $scope.get_config_info = (conf_idx) ->
            if conf_idx != null
                cur_conf = $scope.configs_lut[conf_idx]
                return cur_conf.info_str
        install_devsel_link($scope.new_devsel, true, true)
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
                if conf_idx != null
                    meta_dev = scope.meta_devices[scope.devg_md_lut[scope.obj.device_group]]
                    value = 1
                    if conf_idx in scope.obj.local_selected
                        value = 0
                    if conf_idx in meta_dev.local_selected
                        value = 0
                    $.ajax
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
                                if conf_idx in entry.local_selected
                                    entry.local_selected = (_v for _v in entry.local_selected when _v != conf_idx) 
                            for idx, entry of scope.meta_devices
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
    selection_changed: () =>
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
            if cat.num_refs
                r_info = "#{r_info} (refs=#{cat.num_refs})"
            return r_info
        else if cat.depth
            return cat.full_name
        else
            return "TOP"

cat_ctrl = device_config_module.controller("category_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal) ->
        $scope.cat_tree = new category_tree($scope, {})            
        $scope.xml_to_json = (in_xml) ->
            entry = {
                "depth" : parseInt(in_xml.attr("depth"))
                "immutable" : if parseInt(in_xml.attr("immutable")) then true else false
                "parent" : parseInt(in_xml.attr("parent"))
                "name" : in_xml.attr("name")
                "idx"  : parseInt(in_xml.attr("pk"))
                "full_name" : in_xml.attr("full_name")
            }
            return entry
        $scope.set_xml_entries = (dev_pk, sel_list, in_xml, call_digest=false) ->
            $scope.device_pk = dev_pk
            cat_tree_lut = {}
            $scope.cat_tree.clear_root_nodes()
            # transform to json
            entries = []
            $(in_xml).each (idx, _xml) ->
                entries.push($scope.xml_to_json($(_xml)))
            for entry in entries
                t_entry = $scope.cat_tree.new_node({folder:false, obj:entry, expand:entry.depth < 2, selected: entry.idx in sel_list})
                cat_tree_lut[entry.idx] = t_entry
                if entry.parent and entry.parent of cat_tree_lut
                    cat_tree_lut[entry.parent].add_child(t_entry)
                else
                    # hide selection from root nodes
                    t_entry._show_select = false
                    $scope.cat_tree.add_root_node(t_entry)
            $scope.cat_tree_lut = cat_tree_lut
            $scope.cat_tree.show_selected(false)
            if call_digest
                # needed when called from jQuery 
                $scope.$digest()
        $scope.new_selection = (sel_list) =>
            $.ajax
                url     : "{% url 'base:change_category' %}"
                data    :
                    "obj_type" : "device"
                    "obj_pk"   : $scope.device_pk
                    "subtree"  : "/device"
                    "cur_sel"  : angular.toJson(sel_list)
                success : (xml) =>
                    parse_xml_response(xml)

])

class location_tree extends tree_config
    constructor: (@scope, args) ->
        super(args)
        @show_selection_buttons = false
        @show_icons = false
        @show_select = true
        @show_descendants = false
        @show_childs = false
        @single_select = true
    selection_changed: () =>
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
            if cat.num_refs
                r_info = "#{r_info} (refs=#{cat.num_refs})"
            return r_info
        else if cat.depth
            return cat.full_name
        else
            return "TOP"

loc_ctrl = device_config_module.controller("location_ctrl", ["$scope",
    ($scope) ->
        $scope.loc_tree = new location_tree($scope, {})            
        $scope.xml_to_json = (in_xml) ->
            entry = {
                "depth" : parseInt(in_xml.attr("depth"))
                "immutable" : if parseInt(in_xml.attr("immutable")) then true else false
                "parent" : parseInt(in_xml.attr("parent"))
                "name" : in_xml.attr("name")
                "idx"  : parseInt(in_xml.attr("pk"))
                "full_name" : in_xml.attr("full_name")
            }
            return entry
        $scope.set_xml_entries = (dev_pk, sel_list, in_xml, call_digest=false) ->
            $scope.device_pk = dev_pk
            loc_tree_lut = {}
            $scope.loc_tree.clear_root_nodes()
            # transform to json
            entries = []
            $(in_xml).each (idx, _xml) ->
                entries.push($scope.xml_to_json($(_xml)))
            for entry in entries
                t_entry = $scope.loc_tree.new_node({folder:false, obj:entry, expand:entry.depth < 2, selected: entry.idx in sel_list})
                loc_tree_lut[entry.idx] = t_entry
                if entry.parent and entry.parent of loc_tree_lut
                    loc_tree_lut[entry.parent].add_child(t_entry)
                else
                    # hide selection from root nodes
                    t_entry._show_select = false
                    $scope.loc_tree.add_root_node(t_entry)
            $scope.loc_tree_lut = loc_tree_lut
            $scope.loc_tree.show_selected(false)
            if call_digest
                # needed when called from jQuery 
                $scope.$digest()
        $scope.new_selection = (sel_list) =>
            $.ajax
                url     : "{% url 'base:change_category' %}"
                data    :
                    "obj_type" : "device"
                    "obj_pk"   : $scope.device_pk
                    "subtree"  : "/location"
                    "cur_sel"  : angular.toJson(sel_list)
                success : (xml) =>
                    parse_xml_response(xml)

])

device_config_module.controller("partinfo_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal) ->
        $scope.entries = []
        $scope.active_dev = undefined
        $scope.new_devsel = (_dev_sel, _devg_sel) ->
            $scope.devsel_list = _dev_sel
            $scope.reload()
        $scope.reload = () ->
            active_tab = (dev for dev in $scope.entries when dev.tab_active)
            restDataSource.reload(["{% url 'rest:device_tree_list' %}", {"with_disk_info" : true, "with_meta_devices" : false, "pks" : angular.toJson($scope.devsel_list)}]).then((data) ->
                $scope.entries = (dev for dev in data)
                if active_tab.length
                    for dev in $scope.entries
                        if dev.idx == active_tab[0].idx
                            dev.tab_active = true
            )
        $scope.get_vg = (dev, vg_idx) ->
            return (cur_vg for cur_vg in dev.act_partition_table.lvm_vg_set when cur_vg.idx == vg_idx)[0]
        $scope.fetch = (pk) ->
            if pk?
                $.blockUI()
                $.ajax
                    url     : "{% url 'mon:fetch_partition' %}"
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

add_tree_directive(cat_ctrl)

{% endinlinecoffeescript %}

</script>
