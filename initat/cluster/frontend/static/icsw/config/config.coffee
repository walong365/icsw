config_module = angular.module(
    "icsw.config.config",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.codemirror", "angularFileUpload", "ui.select", "icsw.tools.button",
    ]
).service("icswConfigMonCategoryTreeService", () ->
    class cat_tree extends tree_config
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
).controller("icswConfigConfigCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "$q", "$modal", "FileUploader", "$http", "blockUI", "icswTools", "ICSW_URLS", "$window", "icswToolsButtonConfigService", "icswCallAjaxService", "icswParseXMLResponseService",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, $q, $modal, FileUploader, $http, blockUI, icswTools, ICSW_URLS, $window, icswToolsButtonConfigService, icswCallAjaxService, icswParseXMLResponseService) ->
        $scope.icswToolsButtonConfigService = icswToolsButtonConfigService
        $scope.pagSettings = paginatorSettings.get_paginator("config_list", $scope)
        $scope.selected_objects = []
        $scope.cached_uploads = []
        $scope.catalog = 0
        $scope.uploader = new FileUploader(
            scope : $scope
            url : ICSW_URLS.CONFIG_UPLOAD_CONFIG
            queueLimit : 1
            alias : "config"
            formData : [
                 "csrfmiddlewaretoken" : $window.CSRF_TOKEN
            ]
            removeAfterUpload : true
        )
        $scope.upload_list = []
        $scope.uploader.onBeforeUploadItem = () ->
            blockUI.start()
        $scope.uploader.onCompleteAll = () ->
            blockUI.stop()
            $scope.uploader.clearQueue()
            $scope.reload_upload()
        $scope.$on("icsw.reload_upload", () ->
            $scope.reload_upload()
        )
        $scope.$on("icsw.reload_all", () ->
            $scope.reload()
        )
        $scope.pagSettings.conf.filter_settings = {
            "filter_str" : ""
            "filter_name" : true
            "filter_script" : false
            "filter_var" : false 
            "filter_mon" : false
        }
        $scope.editorOptions = {
            lineWrapping : false
            lineNumbers: true
            mode: 
                name : "python"
                version : 2
            matchBrackets: true
            styleActiveLine: true
            indentUnit : 4
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
        $scope.entries = []
        $scope.config_catalogs = []
        $scope.get_filter_class = (name) ->
            if $scope.pagSettings.conf.filter_settings["filter_#{name}"]
                return "btn btn-sm btn-success"
            else
                return "btn btn-sm"
        $scope.change_filter_setting = (name) ->
            $scope.pagSettings.conf.filter_settings["filter_#{name}"] = ! $scope.pagSettings.conf.filter_settings["filter_#{name}"]
        # config edit
        $scope.config_edit = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular)
        $scope.config_edit.create_template = "config.form"
        $scope.config_edit.edit_template = "config.form"
        $scope.config_edit.create_rest_url = Restangular.all(ICSW_URLS.REST_CONFIG_LIST.slice(1))
        $scope.config_edit.modify_rest_url = ICSW_URLS.REST_CONFIG_DETAIL.slice(1).slice(0, -2)
        $scope.config_edit.create_list = $scope.entries
        $scope.config_edit.new_object_at_tail = false
        $scope.config_edit.change_signal = "icsw.new_config"
        $scope.config_edit.new_object = (scope) ->
            new_obj = {
                "name" : "new config", "description" : "", "priority" : 0, "mon_check_command_set" : [], "config_script_set" : [],
                "config_str_set" : [], "config_int_set" : [], "config_blob_set" : [], "config_bool_set" : [], "enabled" : true,
                "parent_config" : undefined, "categories" : [],
                "config_catalog" : (entry.idx for entry in scope.config_catalogs)[0]
            }
            return new_obj
        # catalog edit
        $scope.catalog_edit = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular, $q)
        $scope.catalog_edit.create_template = "config.catalog.form"
        $scope.catalog_edit.edit_template = "config.catalog.form"
        $scope.catalog_edit.create_rest_url = Restangular.all(ICSW_URLS.REST_CONFIG_CATALOG_LIST.slice(1))
        $scope.catalog_edit.modify_rest_url = ICSW_URLS.REST_CONFIG_CATALOG_DETAIL.slice(1).slice(0, -2)
        $scope.catalog_edit.create_list = $scope.config_catalogs
        $scope.catalog_edit.new_object_at_tail = false
        $scope.catalog_edit.use_promise = true
        $scope.catalog_edit.new_object = (scope) ->
            new_obj = {
                "name" : "new catalog", "author" : $window.CURRENT_USER.login, "url" : "http://localhost/",
            }
            return new_obj
        $scope.var_edit = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular, $q)
        $scope.var_edit.use_promise = true
        $scope.var_edit.new_object_at_tail = false
        $scope.script_edit = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular, $q)
        $scope.script_edit.create_template = "config.script.form"
        $scope.script_edit.edit_template = "config.script.form"
        $scope.script_edit.create_rest_url = Restangular.all(ICSW_URLS.REST_CONFIG_SCRIPT_LIST.slice(1))
        $scope.script_edit.modify_rest_url = ICSW_URLS.REST_CONFIG_SCRIPT_DETAIL.slice(1).slice(0, -2)
        $scope.script_edit.use_promise = true
        $scope.script_edit.new_object_at_tail = false
        $scope.script_edit.min_width = "1000px"
        $scope.mon_edit = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular, $q)
        $scope.mon_edit.create_template = "mon.check.command.form"
        $scope.mon_edit.edit_template = "mon.check.command.form"
        $scope.mon_edit.create_rest_url = Restangular.all(ICSW_URLS.REST_MON_CHECK_COMMAND_LIST.slice(1))
        $scope.mon_edit.modify_rest_url = ICSW_URLS.REST_MON_CHECK_COMMAND_DETAIL.slice(1).slice(0, -2)
        $scope.mon_edit.use_promise = true
        $scope.mon_edit.new_object_at_tail = false
        $scope.mon_edit.min_width = "820px"
        $scope.reload = () ->
            wait_list = [
                restDataSource.reload([ICSW_URLS.REST_CONFIG_LIST, {}]),
                restDataSource.reload([ICSW_URLS.REST_MON_SERVICE_TEMPL_LIST, {}]),
                restDataSource.reload([ICSW_URLS.REST_CATEGORY_LIST, {}]),
                restDataSource.reload([ICSW_URLS.REST_CONFIG_CATALOG_LIST, {}]),
                restDataSource.reload([ICSW_URLS.REST_CONFIG_HINT_LIST, {}]),
                restDataSource.reload([ICSW_URLS.REST_MON_CHECK_COMMAND_SPECIAL_LIST, {}]),
                restDataSource.reload([ICSW_URLS.REST_MON_CHECK_COMMAND_LIST, {}]),
            ]
            $q.all(wait_list).then((data) ->
                $scope.mon_service_templ = data[1]
                $scope.categories = data[2]
                ($scope._set_fields(entry, true) for entry in data[0])
                $scope.entries = data[0]
                $scope.config_catalogs = data[3]
                $scope.mccs_list = data[5]
                $scope.mccs_lut = icswTools.build_lut(data[5])
                $scope.check_commands = data[6]
                # catalog for uploads
                $scope.catalog = $scope.config_catalogs[0].idx
                $scope.config_edit.create_list = $scope.entries
                $scope.config_edit.delete_list = $scope.entries
                $scope.catalog_edit.create_list = $scope.config_catalogs
                $scope.catalog_edit.delete_list = $scope.config_catalogs
                $scope.config_hints = {}
                $scope.soft_config_hints = []
                # configs found (positive cache)
                $scope.resolved_config_hints = {}
                # configs not found (negative cache)
                $scope.no_config_hints = {}
                for entry in data[4]
                    $scope.config_hints[entry.config_name] = entry
                    if not entry.exact_match
                        $scope.soft_config_hints.push(entry)
                    entry.var_lut = {}
                    for vh in entry.config_var_hint_set
                        entry.var_lut[vh.var_name] = vh
                $scope.reload_upload()
            )
        $scope.reload_upload = () ->
            icswCallAjaxService
                url     : ICSW_URLS.CONFIG_GET_CACHED_UPLOADS
                dataType : "json"
                success : (json) ->
                    $scope.$apply(() ->
                        $scope.cached_uploads = angular.fromJson(json)
                    )
        $scope._set_fields = (entry, init=false) ->
            entry.script_sel = 0
            entry.script_num = entry.config_script_set.length
            entry.var_sel = 0
            entry.var_num = entry.config_str_set.length + entry.config_int_set.length + entry.config_bool_set.length + entry.config_blob_set.length
            entry.mon_sel = 0
            entry.mon_num = entry.mon_check_command_set.length
            if init
                entry.script_expanded = false
                entry.var_expanded = false
                entry.mon_expanded = false
            else
                for _type in ["var", "script", "mon"]
                    if not entry["#{_type}_num"]
                        entry["#{_type}_expanded"] = false
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
        $scope.delete_selected_objects = () ->
            if confirm("really delete #{$scope.selected_objects.length} objects ?")
                blockUI.start()
                for obj in $scope.selected_objects
                    conf = (entry for entry in $scope.entries when entry.idx == obj.config)[0]
                    if obj.object_type == "mon"
                        ref_f = conf.mon_check_command_set
                    else
                        ref_f = conf["config_#{obj.object_type}_set"]
                    ref_f = (_rv for _rv in ref_f when _rv.idx != obj.idx)
                    if obj.object_type == "mon"
                        conf.mon_check_command_set = ref_f
                    else
                        conf["config_#{obj.object_type}_set"] = ref_f
                    $scope._set_fields(conf)
                icswCallAjaxService
                    url     : ICSW_URLS.CONFIG_DELETE_OBJECTS
                    data    :
                        "obj_list" : angular.toJson(([entry.object_type, entry.idx] for entry in $scope.selected_objects))
                    success : (xml) =>
                        icswParseXMLResponseService(xml)
                        blockUI.stop()
                $scope.selected_objects = []
        $scope.unselect_objects = () ->
            # unselect all selected objects
            idx = 0
            while $scope.selected_objects.length
                prev_len = $scope.selected_objects.length
                idx++
                entry = $scope.selected_objects[0]
                $scope.unselect_object($scope.selected_objects[0])
                # unable to unselect, exit loop
                if $scope.selected_objects.length == prev_len
                    console.log "problem unselect..."
                    break
        $scope.unselect_object = (obj) ->
            obj._selected = false
            $scope.selected_objects = (entry for entry in $scope.selected_objects when entry != obj)
        $scope.select_object = (obj) ->
            if obj._selected
                $scope.unselect_object(obj)
            else
                obj._selected = true
                $scope.selected_objects.push(obj)
        # hint functions
        $scope.re_compare = (_array, _input) ->
            console.log _array, _input, $scope.config_hints[_array].exact_match
            return true
            cur_pat = new RegExp(_array, "i")
            console.log cur_pat, _input
            return cur_pat.test(_input)
        $scope.get_config_hints = () ->
            return (entry for entry of $scope.config_hints)
        $scope.config_selected_vt = (item, model, label) ->
            if item of $scope.config_hints
                # set description
                if not $scope._edit_obj.description
                    $scope._edit_obj.description = $scope.config_hints[item].config_description
        $scope.get_config_var_hints = (config) ->
            if config and config.name of $scope.config_hints
                return (entry for entry of $scope.config_hints[config.name].var_lut)
            else
                return []
        $scope.config_has_info = (config) ->
            if config.name of $scope.resolved_config_hints
                return true
            else if config.name of $scope.no_config_hints
                return false 
            else if config.name of $scope.config_hints
                $scope.resolved_config_hints[config.name] = $scope.config_hints[config.name]
                return true
            else
                # soft match
                found_names = _.sortBy((entry.config_name for entry in $scope.soft_config_hints when new RegExp(entry.config_name).test(config.name)), (_str) -> return -_str.length)
                if found_names.length
                    found_name = found_names[0]
                    $scope.resolved_config_hints[config.name] = $scope.config_hints[found_name]
                    return true
                else
                    $scope.no_config_hints[config.name] = true
                    return false
        $scope.get_config_help_text = (config) ->
            if $scope.config_has_info(config) 
                return $scope.resolved_config_hints[config.name].help_text_short or "no short help"
            else
                return ""
        $scope.var_has_info = (config, cvar) ->
            if config.name of $scope.resolved_config_hints
                return cvar.name of $scope.resolved_config_hints[config.name].var_lut
            else
                return false
        $scope.get_var_help_text = (config, cvar) ->
            if $scope.var_has_info(config, cvar)
                return $scope.resolved_config_hints[config.name].var_lut[cvar.name].help_text_short or "no short help"
            else
                return ""
        $scope.show_config_help = () ->
            if $scope._edit_obj.name of $scope.config_hints
                return $scope.config_hints[$scope._edit_obj.name].help_text_html
            else
                return ""
        $scope.show_config_var_help = () ->
            if $scope._edit_obj.config and $scope._config.name of $scope.config_hints
                ch = $scope.config_hints[$scope._config.name]
                if $scope._edit_obj.name of ch.var_lut
                    return ch.var_lut[$scope._edit_obj.name].help_text_html or ""
                else
                    return ""
            else
                return ""
        $scope.get_label_class = (entry, s_type) ->
            num = entry["#{s_type}_num"]
            sel = entry["#{s_type}_sel"]
            if sel and $scope.pagSettings.conf.filter_settings.filter_str
                return "label label-success"
            else if num
                return "label label-primary"
            else
                return "label label-default"
        $scope.get_expand_class = (config, _type) ->
            if config["#{_type}_num"]
                if config["#{_type}_expanded"]
                    return "glyphicon glyphicon-chevron-down"
                else
                    return "glyphicon glyphicon-chevron-right"
            else
                return "glyphicon"
        $scope.toggle_expand = (config, _type) ->
            if config["#{_type}_num"]
                config["#{_type}_expanded"] = not config["#{_type}_expanded"]
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
                return "-"
        $scope.get_config_row_class = (config) ->
            return if config.enabled then "" else "danger"
        $scope.get_config_vars = (config) ->
            r_val = []
            for v_type in ["str", "int", "bool", "blob"]
                for entry in config["config_#{v_type}_set"]
                    entry.v_type = v_type
                    r_val.push(entry)
            r_val.sort((_a, _b) ->
                if _a.name > _b.name
                    return 1
                else if _a.name < _b.name
                    return -1
                else
                    return 0 
            )
            return r_val
        $scope.delete_var = (config, _var) ->
            v_type = _var.v_type
            $scope.var_edit.delete_list = config["config_#{v_type}_set"]
            $scope.var_edit.modify_rest_url = {
                "str" : ICSW_URLS.REST_CONFIG_STR_DETAIL
                "int" : ICSW_URLS.REST_CONFIG_INT_DETAIL
                "bool" : ICSW_URLS.REST_CONFIG_BOOL_DETAIL
                "blob" : ICSW_URLS.REST_CONFIG_BLOB_DETAIL
            }[v_type].slice(1).slice(0, -2)
            $scope.var_edit.delete_obj(_var).then((res) ->
                if res
                    $scope.unselect_object(_var)
                    $scope.filter_conf(config, $scope)
            )
        $scope.edit_var = (config, obj, event) ->
            v_type = obj.v_type
            $scope._config = config
            if ! obj.description
                obj.description = "descr"
            $scope.var_edit.edit_template = "config.#{v_type}.form"
            $scope.var_edit.modify_rest_url = {
                "str" : ICSW_URLS.REST_CONFIG_STR_DETAIL
                "int" : ICSW_URLS.REST_CONFIG_INT_DETAIL
                "bool" : ICSW_URLS.REST_CONFIG_BOOL_DETAIL
            }[v_type].slice(1).slice(0, -2)
            $scope.var_edit.create_list = config["config_#{v_type}_set"]
            $scope.var_edit.edit(obj, event).then(
                (mod_obj) ->
                    if mod_obj != false
                        $scope.filter_conf(config, $scope)
            )
        $scope.create_var = (config, v_type, event) ->
            $scope._config = config
            $scope.var_edit.create_template = "config.#{v_type}.form"
            $scope.var_edit.create_rest_url = Restangular.all({
                "str" : ICSW_URLS.REST_CONFIG_STR_LIST
                "int" : ICSW_URLS.REST_CONFIG_INT_LIST
                "bool" : ICSW_URLS.REST_CONFIG_BOOL_LIST
            }[v_type].slice(1))
            $scope.var_edit.create_list = config["config_#{v_type}_set"]
            $scope.var_edit.new_object = (scope) ->
                return {
                    "config" : config.idx
                    "name" : "new #{v_type} var"
                    "description" : "new variable (type #{v_type})"
                    "value" : {"str" : "", "int" : 0, "bool" : 1}[v_type]
                }
            $scope.var_edit.create(event).then(
                (new_obj) ->
                    if new_obj != false
                        $scope.filter_conf(config, $scope)
            ) 
        $scope.delete_script = (config, _script) ->
            $scope.script_edit.delete_list = config.config_script_set
            $scope.script_edit.delete_obj(_script).then((res) ->
                if res
                    $scope.unselect_object(_script)
                    $scope.filter_conf(config, $scope)
            )
        $scope.edit_script = (config, obj, event) ->
            $scope.script_edit.create_list = config.config_script_set
            obj.edit_value = obj.value
            $scope.$watch(
                () -> 
                    return obj.edit_value
                (new_val) ->
                    if typeof(new_val) == "string" and new_val.length
                        obj.value = new_val
            )
            $scope.script_edit.edit(obj, event).then(
                (mod_obj) ->
                    if mod_obj != false
                        $scope.filter_conf(config, $scope)
            )
        $scope.create_script = (config, event) ->
            $scope.script_edit.create_list = config.config_script_set
            $scope.script_edit.new_object = (scope) ->
                return {
                    "config"   : config.idx
                    "name"     : "new script"
                    "priority" : 0
                    "enabled"  : true
                    "description" : "new config script"
                    "edit_value"  : "# config script (" + moment().format() + ")\n#\n"
                }
            $scope.$watch(
                () -> 
                    return $scope._edit_obj.edit_value
                (new_val) ->
                    if typeof(new_val) == "string" and new_val.length
                        $scope._edit_obj.value = new_val
            )
            $scope.script_edit.create(event).then(
                (new_obj) ->
                    if new_obj != false
                        $scope.filter_conf(config, $scope)
            ) 
        $scope.delete_mon = (config, _mon) ->
            $scope.mon_edit.delete_list = config.mon_check_command_set
            $scope.mon_edit.delete_obj(_mon).then((res) ->
                #$scope.check_commands = (entry for entry in $scope.check_commands when entry.idx != _mon.idx)
                if res
                    $scope.unselect_object(_mon)
                    $scope.filter_conf(config, $scope)
            )
        $scope.edit_mon = (config, obj, event) ->
            $scope.mon_edit.create_list = config.mon_check_command_set
            obj.arg_name = "argument"
            obj.arg_value = "80"
            $scope.mon_edit.edit(obj, event).then(
                (mod_obj) ->
                    if mod_obj != false
                        $scope.filter_conf(config, $scope)
            )
        $scope.get_mon_command_line = (obj) ->
            if obj.mon_check_command_special
                return $scope.mccs_lut[obj.mon_check_command_special].command_line
            else
                return obj.command_line 
        $scope.copy_mon = (config, obj, event) ->
            icswCallAjaxService
                url     : ICSW_URLS.CONFIG_COPY_MON
                data    :
                    "config" : config.idx
                    "mon"    : obj.idx
                success : (xml) =>
                    if icswParseXMLResponseService(xml)
                        new_moncc = angular.fromJson($(xml).find("value[name='mon_cc']").text())
                        config.mon_check_command_set.push(new_moncc)
                        $scope.$apply(() ->
                            $scope._set_fields(config)
                        )
        $scope.create_mon = (config, event) ->
            $scope.mon_edit.create_list = config.mon_check_command_set
            $scope.mon_edit.new_object = (scope) ->
                c_name = "cc_#{config.name}"
                c_idx = 1
                cc_names = (cc.name for cc in config.mon_check_command_set)
                while true
                    if "#{c_name}_#{c_idx}" in cc_names
                        c_idx++
                    else
                        break
                c_name = "#{c_name}_#{c_idx}"
                return {
                    "config" : config.idx
                    "name" : c_name
                    "is_active": true
                    "description" : "Check command"
                    "command_line" : "$USER2$ -m $HOSTADDRESS$ uptime"
                    "categories" : []
                    "arg_name" : "argument"
                    "arg_value" : "80"
                }
            $scope.mon_edit.create(event).then(
                (new_obj) ->
                    if new_obj != false
                        $scope.filter_conf(config, $scope)
            ) 
        $scope.get_event_handler = (ev_idx) ->
            if ev_idx
                # not fast but working
                ev_config = (entry for entry in $scope.entries when ev_idx in (mcc.idx for mcc in entry.mon_check_command_set))
                if ev_config.length
                    return (entry for entry in ev_config[0].mon_check_command_set when entry.idx == ev_idx)[0].name
                else
                    return "???"
            else
                return "---"
        $scope.get_event_handlers = (edit_obj) ->
            ev_handlers = []
            for entry in $scope.entries
                for cc in entry.mon_check_command_set
                    if cc.is_event_handler and cc.idx != edit_obj.idx
                        ev_handlers.push(cc)
            return ev_handlers
        $scope.download_selected = () ->
            hash = angular.toJson((entry.idx for entry in $scope.pagSettings.filtered_list))
            window.location = ICSW_URLS.CONFIG_DOWNLOAD_CONFIGS.slice(0, -1) + hash
        $scope.get_num_configs = (cat) ->
            return (entry for entry in $scope.entries when entry.config_catalog == cat.idx).length 
        $scope.edit_catalog = (cat, event) ->
            $scope.catalog_edit.edit(cat, event).then(
                (mod_obj) ->
            )
        $scope.delete_catalog = (cat) ->
            $scope.catalog_edit.delete_obj(cat).then((res) ->
            )
        $scope.get_mccs_already_used_warning = (edit_obj) ->
            cur_mccs = edit_obj.mon_check_command_special
            warning = ""
            if cur_mccs?
                problem_list = []
                for config in $scope.entries
                    for mcc in config.mon_check_command_set
                        if mcc.idx != edit_obj.idx and mcc.mon_check_command_special == cur_mccs
                            problem_list.push(mcc.name)
                if problem_list.length
                    warning += ""
                    warning += "This special check command is already used in " + problem_list.join(",") + "."
                    warning += "Multiple assignments of special check commands to check commands are not supported and may result in undefined behavior."
            return warning
        $scope.get_mccs_info = () ->
            cur_mccs = $scope._edit_obj.mon_check_command_special
            if cur_mccs
                return $scope.mccs_lut[cur_mccs].description
            else
                return ""
        $scope.get_mccs_cmdline = () ->
            cur_mccs = $scope._edit_obj.mon_check_command_special
            if cur_mccs
                if $scope.mccs_lut[cur_mccs].is_active
                    return $scope.mccs_lut[cur_mccs].command_line
                else
                    return "passive check"
            else
                return ""
        $scope.add_argument = () ->
            cur_cl = $scope._edit_obj.command_line
            max_argn = 0
            match_list = cur_cl.match(/arg(\d+)/ig)
            if match_list?
                for cur_match in match_list 
                    max_argn = Math.max(max_argn, parseInt(cur_match.substring(3)))
            max_argn++
            $scope._edit_obj.command_line = "#{cur_cl} ${ARG#{max_argn}:#{$scope._edit_obj.arg_name.toUpperCase()}:#{$scope._edit_obj.arg_value}}"
        $scope.get_moncc_info = () ->
            cur_cl = $scope._edit_obj.command_line
            complex_re = new RegExp("\\$\\{arg(\\d+):([^\\}^:]+):*(\\S+)*\\}\\$*|\\$\\arg(\\d+)\\$", "ig")
            if cur_cl
                simple_list = []
                default_list = []
                complex_list = []
                while cur_m = complex_re.exec(cur_cl)
                    if cur_m[4]
                        # simple $ARG##$
                        simple_list.push([parseInt(cur_m[4])])
                    else if cur_m[3]
                        # complex ${ARG##:NAME:DEFAULT}
                        complex_list.push([parseInt(cur_m[1]), cur_m[2], cur_m[3]])
                    else
                        # form with default #{ARG##:DEFAULT}
                        default_list.push([parseInt(cur_m[1]), cur_m[2]])
                info_field = ["#{simple_list.length} simple args, #{default_list.length} args with default and #{complex_list.length} complex args"]
                for entry in simple_list
                    info_field.push("simple argument $ARG#{entry[0]}$")
                for entry in default_list
                    info_field.push("argument $ARG#{entry[0]}$ with default value #{entry[1]}")
                for entry in complex_list
                    info_field.push("argument $ARG#{entry[0]}$ from DeviceVar '#{entry[1]}' (default value #{entry[2]})")
                return info_field
            else
                return ["no args parsed"]
        $scope.reload()
]).directive("icswConfigConfigOverview", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.overview")
        controller: "icswConfigConfigCtrl"
    }
]).directive("icswConfigCatalogTable", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.catalog.table")
    }
]).directive("icswConfigConfigTable", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.config.table")
    }
]).directive("icswConfigVarTable", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.var.table")
        link : (scope, el, attrs) ->
            scope.get_value = (obj) ->
                if obj.v_type == "bool"
                    return if obj.value then "true" else "false"
                else
                    return obj.value
    }
]).directive("icswConfigScriptTable", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.script.table")
    }
]).directive("icswConfigMonTable", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.mon.table")
    }
]).directive("icswConfigCategoryChoice", ["$templateCache", "icswConfigMonCategoryTreeService", ($templateCache, icswConfigMonCategoryTreeService) ->
    return {
        restrict : "EA"
        template : "<tree treeconfig='cat_tree'></tree>"
        link : (scope, el, attrs) ->
            # start at -1 because we dont count the Top level category
            scope.num_cats = -1
            scope.cat_tree = new icswConfigMonCategoryTreeService(scope)
            cat_tree_lut = {}
            if attrs["mode"] == "conf"
                sel_cat = scope._edit_obj.categories
                top_cat_re = new RegExp(/^\/config/)
            else if attrs["mode"] == "mon"
                # mon
                sel_cat = scope._edit_obj.categories
                top_cat_re = new RegExp(/^\/mon/)
            for entry in scope.categories
                if entry.full_name.match(top_cat_re)
                    scope.num_cats++
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
            scope.new_selection = (new_sel) ->
                scope._edit_obj.categories = new_sel
    }
]).directive("icswConfigUploadInfo", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.cached.upload.info")
        scope : {
            "upload"  : "="
            "catalog" : "="
        }
        replace : true
    }
]).directive("icswConfigCachedConfig", ["$templateCache", "$compile", "$modal", "Restangular", "ICSW_URLS", "icswCallAjaxService", "icswParseXMLResponseService", ($templateCache, $compile, $modal, Restangular, ICSW_URLS, icswCallAjaxService, icswParseXMLResponseService) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.cached.upload")
        scope : {
            "config"  : "="
            "upload"  : "="
            "catalog" : "="
        }
        replace : false
        link : (scope, el, attrs) ->
            scope.get_num_vars = () ->
                num = 0
                for _en in ["config_blob_set", "config_bool_set", "config_int_set", "config_str_set"]
                    if scope.config[_en]
                        num += scope.config[_en].length
                return num
            scope.get_num_scripts = () ->
                if scope.config.config_script_set
                    return scope.config.config_script_set.length
                else
                    return 0
            scope.get_num_check_commands = () ->
                if scope.config.mon_check_command_set
                    return scope.config.mon_check_command_set.length
                else
                    return 0
            scope.take_config = () ->
                # $.blockUI
                icswCallAjaxService
                    url     : ICSW_URLS.CONFIG_HANDLE_CACHED_CONFIG
                    data    : {
                        "upload_key" : scope.upload.upload_key
                        "name"       : scope.config.name
                        "catalog"    : scope.catalog
                        "mode"       : "take"
                    }
                    success : (xml) ->
                        # $.unblockUI
                        icswParseXMLResponseService(xml)
                        scope.$emit("icsw.reload_all")
            scope.delete_config = () ->
                # $.blockUI
                icswCallAjaxService
                    url     : ICSW_URLS.CONFIG_HANDLE_CACHED_CONFIG
                    data    : {
                        "upload_key" : scope.upload.upload_key
                        "name"       : scope.config.name
                        "mode"       : "delete"
                    }
                    success : (xml) ->
                        # $.unblockUI
                        icswParseXMLResponseService(xml)
                        scope.$emit("icsw.reload_upload")
    }
])

