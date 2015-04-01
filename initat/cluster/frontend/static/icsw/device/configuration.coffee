# Copyright (C) 2012-2015 init.at
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
angular.module(
    "icsw.device.configuration",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "icsw.d3", "icsw.tools.button"
    ]
).service("icswDeviceConfigurationConfigVarTreeService", () ->
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
).controller("icswConfigVarsCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "$q", "$modal", "ICSW_URLS", "icswDeviceConfigurationConfigVarTreeService", "icswCallAjaxService", "icswParseXMLResponseService",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, $q, $modal, ICSW_URLS, icswDeviceConfigurationConfigVarTreeService, icswCallAjaxService, icswParseXMLResponseService) ->
        $scope.devvar_tree = new icswDeviceConfigurationConfigVarTreeService($scope)
        $scope.var_filter = ""
        $scope.loaded = false
        $scope.new_devsel = (_dev_sel) ->
            $scope.devsel_list = _dev_sel
        $scope.load_vars = () ->
            if not $scope.loaded
                $scope.loaded = true
                icswCallAjaxService
                    url     : ICSW_URLS.CONFIG_GET_DEVICE_CVARS
                    data    :
                        "keys" : angular.toJson($scope.devsel_list)
                    success : (xml) =>
                        icswParseXMLResponseService(xml)
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
]).directive("icswDeviceConfigurationVarOverview", ["$templateCache", "$compile", "$modal", "Restangular", ($templateCache, $compile, $modal, Restangular) ->
    return {
        scope: true
        restrict : "EA"
        template : $templateCache.get("icsw.device.configuration.var.overview")
        controller: "icswConfigVarsCtrl"
    }
]).controller("icswDeviceConfigurationCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "$q", "$modal", "access_level_service", "msgbus", "icswTools", "ICSW_URLS",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, $q, $modal, access_level_service, msgbus, icswTools, ICSW_URLS) ->
        access_level_service.install($scope)
        $scope.devices = []
        $scope.configs = []
        $scope.config_catalogs = []
        $scope.active_configs = []
        $scope.name_filter = ""
        $scope.new_config_name = ""
        $scope.table_mode = true
        $scope.list_mode = false
        $scope.only_selected = false
        $scope.new_devsel = (_dev_sel) ->
            $scope.devsel_list = _dev_sel
            $scope.reload()
        $scope.reload = () ->
            pre_sel = (dev.idx for dev in $scope.devices when dev.expanded)
            restDataSource.reset()
            wait_list = restDataSource.add_sources([
                [ICSW_URLS.REST_DEVICE_TREE_LIST, {"with_device_configs" : true, "with_meta_devices" : true, "pks" : angular.toJson($scope.devsel_list), "olp" : "backbone.device.change_config"}],
                [ICSW_URLS.REST_CONFIG_LIST, {}]
                [ICSW_URLS.REST_CONFIG_CATALOG_LIST, {}]
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
                $scope.cc_lut = icswTools.build_lut(data[2])
                $scope.init_devices(pre_sel)
                $scope.new_filter_set($scope.name_filter, false)
            )
        $scope.create_config = (cur_cat) ->
            new_obj = {
                "name" : $scope.new_config_name
                "config_catalog" : cur_cat
            }
            Restangular.all(ICSW_URLS.REST_CONFIG_LIST.slice(1)).post(new_obj).then((new_data) ->
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
                entry.show = if (entry.enabled and entry.name.match(cur_re)) then true else false
                if $scope.only_selected and entry.show
                    sel = false
                    for cur_dev in $scope.all_devices
                        if entry.idx in cur_dev.local_selected
                            sel = true
                    entry.show = sel
                if entry.show
                    $scope.active_configs.push(entry)
            if change_expand_state
                num_show = $scope.active_configs.length
                active_ids = (_c.idx for _c in $scope.active_configs)
                # check expansion state of meta devices
                for idx, dev of $scope.meta_devices
                    #dev.expanded = if (true for _loc_c in dev.local_selected when _loc_c in active_ids).length then true else false
                    dev.expanded = if num_show > 0 then true else false
                for dev in $scope.devices
                    #dev.expanded = if (true for _loc_c in dev.local_selected when _loc_c in active_ids).length then true else false
                    dev.expanded = if num_show > 0 then true else false
                    if not dev.expanded and dev.device_type_identifier != "MD"
                        dev.expanded = $scope.meta_devices[$scope.devg_md_lut[dev.device_group]].expanded
            $scope.set_line_list()
        $scope.get_config_info = (conf_idx) ->
            if conf_idx != null
                cur_conf = $scope.configs_lut[conf_idx]
                return cur_conf.info_str
        $scope.get_config_type = (conf_idx) ->
            if conf_idx != null
                r_v = []
                cur_conf = $scope.configs_lut[conf_idx]
                if cur_conf.server_config
                    r_v.push("S")
                if cur_conf.system_config
                    r_v.push("Y")
                return r_v.join("/")
            else
                return ""
]).directive("icswDeviceConfigurationOverview", ["$templateCache", "msgbus", ($templateCache, msgbus) ->
    return {
        scope: true
        restrict : "EA"
        template : $templateCache.get("icsw.device.configuration.overview")
        controller: "icswDeviceConfigurationCtrl"
    }
]).directive("icswDeviceConfigurationHelper", ["Restangular", "ICSW_URLS", "icswCallAjaxService", "icswParseXMLResponseService", (Restangular, ICSW_URLS, icswCallAjaxService, icswParseXMLResponseService) ->
    return {
        restrict : "EA"
        link: (scope, el, attrs) ->
            scope.get_th_class = (dev) ->
                _cls = ""
                is_meta_dev = dev.device_type_identifier == "MD"
                if is_meta_dev
                    return "warning"
                else
                    return ""
            scope.get_td_class = (dev, conf_idx, single_line) ->
                _cls = ""
                is_meta_dev = dev.device_type_identifier == "MD"
                meta_dev = scope.meta_devices[scope.devg_md_lut[dev.device_group]]
                if single_line and not scope.show_config(dev, conf_idx) and scope.config_exists(conf_idx)
                    _cls = "danger"
                if conf_idx != null
                    if conf_idx in dev.local_selected
                        _cls = "success"
                    else if conf_idx in meta_dev.local_selected and not is_meta_dev
                        _cls = "warn"
                return _cls
            scope.show_config = (dev, conf_idx) ->
                if conf_idx != null
                    cur_conf = scope.configs_lut[conf_idx]
                    if dev.device_type_identifier == "MD" and cur_conf.server_config
                        return false
                    else
                        return true
                else
                    return false
            scope.click = (dev, conf_idx) ->
                if conf_idx != null and scope.acl_create(dev, 'backbone.device.change_config') and scope.show_config(dev, conf_idx)
                    meta_dev = scope.meta_devices[scope.devg_md_lut[dev.device_group]]
                    value = 1
                    if conf_idx in dev.local_selected
                        value = 0
                    if conf_idx in meta_dev.local_selected
                        value = 0
                    icswCallAjaxService
                        url  : ICSW_URLS.CONFIG_ALTER_CONFIG_CB
                        data : {
                            "conf_pk" : conf_idx
                            "dev_pk"  : dev.idx
                            "value"   : value
                        },
                        success : (xml) =>
                            # interpret response
                            icswParseXMLResponseService(xml)
                            # at first remove all selections
                            for entry in scope.devices
                                if entry.device_group == dev.device_group
                                    if conf_idx in entry.local_selected
                                        entry.local_selected = (_v for _v in entry.local_selected when _v != conf_idx) 
                            for idx, entry of scope.meta_devices
                                if entry.device_group == dev.device_group
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
            scope.get_config_class_icon = (dev, conf_idx, single_line) ->
                if single_line
                    _cls = "glyphicon glyphicon-minus"
                else
                    _cls = "glyphicon"
                is_meta_dev = dev.device_type_identifier == "MD"
                meta_dev = scope.meta_devices[scope.devg_md_lut[dev.device_group]]
                if conf_idx != null
                    if conf_idx in dev.local_selected
                        _cls = "glyphicon glyphicon-ok"
                    if conf_idx in meta_dev.local_selected and not is_meta_dev
                        _cls = "glyphicon glyphicon-ok-circle"
                return _cls
            scope.config_exists = (conf_idx) ->
                return if conf_idx != null then true else false
    }
]).directive("icswDeviceConfigurationRow", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.configuration.row")
    }
]).directive("icswDeviceConfigurationTable", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.configuration.table")
    }
]).directive("icswDeviceConfigurationSimpleRow", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.configuration.simplerow")
    }
])
