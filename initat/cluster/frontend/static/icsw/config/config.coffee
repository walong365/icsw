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
config_module = angular.module(
    "icsw.config.config",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.codemirror", "angularFileUpload", "ui.select", "icsw.tools.button",
    ]
).service("icswConfigMonCategoryTreeService", ["icswTreeConfig", (icswTreeConfig) ->
    class cat_tree extends icswTreeConfig
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
            @scope.$digest()
]).service("icswConfigRestService", ["$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall", "icswTools", ($q, Restangular, ICSW_URLS, $window, icswCachingCall, icswTools) ->
    rest_map = [
        [
            ICSW_URLS.REST_CONFIG_LIST,
        ],
        [
            ICSW_URLS.REST_MON_SERVICE_TEMPL_LIST,
        ],
        [
            ICSW_URLS.REST_CATEGORY_LIST,
        ],
        [
            ICSW_URLS.REST_CONFIG_CATALOG_LIST,
        ],
        [
            ICSW_URLS.REST_CONFIG_HINT_LIST,
        ],
        [
            ICSW_URLS.REST_MON_CHECK_COMMAND_SPECIAL_LIST,
        ],
        [
            ICSW_URLS.REST_MON_CHECK_COMMAND_LIST,
        ]
    ]
    _fetch_dict = {}
    _result = []
    # load called
    load_called = false
    load_data = (client) ->
        load_called = true
        _wait_list = (icswCachingCall.fetch(client, _entry[0], _entry[1], []) for _entry in rest_map)
        _defer = $q.defer()
        $q.all(_wait_list).then((data) ->
            _result = data
            _defer.resolve(_result)
            for client of _fetch_dict
                # resolve clients
                _fetch_dict[client].resolve(_result)
            # reset fetch_dict
            _fetch_dict = {}
        )
        return _defer
    fetch_data = (client) ->
        if client not of _fetch_dict
            # register client
            _defer = $q.defer()
            _fetch_dict[client] = _defer
        if _result.length
            # resolve immediately
            _fetch_dict[client].resolve(_result)
        return _fetch_dict[client]
    # number of selected configs
    num_selected_configs = 0
    return {
        "load": (client) ->
            # loads from server
            return load_data(client).promise
        "get_num_selected_configs": () ->
            return num_selected_configs
        "get_selected_configs": () ->
            return (entry for entry in _result[0] when entry.isSelected)
        "set_num_selected_configs": (num) ->
            num_selected_configs = num
        "fetch": (client) ->
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise
        "create_catalog": (new_cat) ->
            _d = $q.defer()
            Restangular.all(rest_map[3][0].slice(1)).post(new_cat).then(
                (new_obj) ->
                    _result[3].push(new_obj)
                    _d.resolve(new_obj)
            )
            return _d.promise
        "create_config": (new_config) ->
            _d = $q.defer()
            Restangular.all(rest_map[0][0].slice(1)).post(new_config).then(
                (new_obj) ->
                    _result[0].push(new_obj)
                    _d.resolve(new_obj)
            )
            return _d.promise
        "create_var": (config, v_type, new_var) ->
            _d = $q.defer()
            rest_url = {
                "str" : ICSW_URLS.REST_CONFIG_STR_LIST
                "int" : ICSW_URLS.REST_CONFIG_INT_LIST
                "bool" : ICSW_URLS.REST_CONFIG_BOOL_LIST
             }[v_type].slice(1)
            new_var.config = config.idx
            Restangular.all(rest_url).post(new_var).then(
                (new_var) ->
                    config["config_#{v_type}_set"].push(new_var)
                    _d.resolve(new_var)
                () ->
                    _d.reject()
            )
            return _d.promise
        "create_script": (config, new_script) ->
            _d = $q.defer()
            rest_url = ICSW_URLS.REST_CONFIG_SCRIPT_LIST.slice(1)
            new_script.config = config.idx
            Restangular.all(rest_url).post(new_script).then(
                (new_script) ->
                    config["config_script_set"].push(new_script)
                    _d.resolve(new_script)
                () ->
                    _d.reject()
            )
            return _d.promise
        "create_mon_check_command": (config, new_moncc) ->
            _d = $q.defer()
            rest_url = ICSW_URLS.REST_MON_CHECK_COMMAND_LIST.slice(1)
            new_moncc.config = config.idx
            Restangular.all(rest_url).post(new_moncc).then(
                (new_moncc) ->
                    config["mon_check_command_set"].push(new_moncc)
                    _d.resolve(new_moncc)
                () ->
                    _d.reject()
            )
            return _d.promise
    }
]).service("icswConfigHintService", ["icswConfigRestService", "$q", "icswTools", "ICSW_URLS", (icswConfigRestService, $q, icswTools, ICSW_URLS) ->
    _def = icswConfigRestService.fetch("icsw_config_catalog_list_service")
    hints = []
    _hints_loaded = false
    config_hints = {}
    soft_config_hints = []
    _def.then((data) ->
        hints = data[4]
        _hints_loaded = true
        for entry in hints
            config_hints[entry.config_name] = entry
            if not entry.exact_match
                soft_config_hints.push(entry)
            entry.var_lut = {}
            for vh in entry.config_var_hint_set
                entry.var_lut[vh.var_name] = vh
    )
    # config hint resolvers
    # configs found (positive cache)
    _resolved_config_hints = {}
    # configs not found (negative cache)
    _no_config_hints = {}
    config_has_info = (config) ->
        if not _hints_loaded
            return false
        if config.name of _resolved_config_hints
            return true
        else if config.name of _no_config_hints
            return false
        else if config.name of config_hints
            _resolved_config_hints[config.name] = config_hints[config.name]
            return true
        else
            # soft match
            found_names = _.sortBy((entry.config_name for entry in soft_config_hints when new RegExp(entry.config_name).test(config.name)), (_str) -> return -_str.length)
            if found_names.length
                found_name = found_names[0]
                _resolved_config_hints[config.name] = config_hints[found_name]
                return true
            else
                _no_config_hints[config.name] = true
                return false
    return {
        "get_config_help": (name) ->
            if name of config_hints
                return config_hints[name].help_text_html
            else
                return ""
        "get_all_config_hint_names": () ->
            return _.keys(config_hints)
        "config_selected_vt": (item, edit_obj) ->
            if item of config_hints
                # set description
                if not edit_obj.description
                    edit_obj.description = config_hints[item].config_description
        "config_has_info": (config) ->
            return config_has_info(config)
        "get_config_help_text": (config) ->
            if config_has_info(config)
                return _resolved_config_hints[config.name].help_text_short or "no short help"
            else
                return ""
        "var_has_info": (config, c_var) ->
            if config.name of _resolved_config_hints
                return c_var.name of _resolved_config_hints[config.name].var_lut
            else
                return false
        "show_config_var_help": (config, c_var) ->
            if config.name of config_hints
                ch = config_hints[config.name]
                if c_var.name of ch.var_lut
                    return ch.var_lut[c_var.name].help_text_html or ""
                else
                    return ""
            else
                return ""
        "get_config_var_hints": (config) ->
            if config and config.name of config_hints
                return (entry for entry of config_hints[config.name].var_lut)
            else
                return []
    }
]).service('icswConfigCatalogListService', ["icswConfigRestService", "$q", "icswTools", "ICSW_URLS", "$window", (icswConfigRestService, $q, icswTools, ICSW_URLS, $window) ->
    _def = icswConfigRestService.fetch("icsw_config_catalog_list_service")
    _config = $q.defer()
    configs = []
    catalogs = []
    _def.then((data) ->
        configs = data[0]
        catalogs = data[3]
        _config.resolve(catalogs)
    )
    return {
        edit_template: "config.catalog.form"
        load_promise: _config.promise
        delete_confirm_str: (obj) ->
            return "Really delete config catalog '#{obj.name}' ?"
        new_object: () ->
            new_obj = {
                "name" : "new catalog", "author" : $window.CURRENT_USER.login, "url" : "http://localhost/",
            }
            return new_obj
        save_defer: (new_obj) ->
            _cd = $q.defer()
            icswConfigRestService.create_catalog(new_obj).then(
                (new_cat) ->
                    _cd.resolve(new_cat)
            )
            return _cd.promise
        init_fn: (scope) ->
            scope.get_num_configs = (cat) ->
                return (entry for entry in configs when entry.config_catalog == cat.idx).length
    }
]).service('icswConfigListService', ["icswConfigRestService", "$q", "icswTools", "ICSW_URLS", "icswConfigHintService", (icswConfigRestService, $q, icswTools, ICSW_URLS, icswConfigHintService) ->
    _def = icswConfigRestService.fetch("icsw_config_list_service")
    _config = $q.defer()
    _configs = []
    _catalogs = []
    _def.then((data) ->
        _configs = data[0]
        (create_extra_fields(entry) for entry in _configs)
        _catalogs = data[3]
        _config.resolve(data[0])
        update_filter_field()
    )
    create_extra_fields = (entry) ->
        entry._cef = true
        entry.script_sel = 0
        entry.script_num = entry.config_script_set.length
        entry.var_sel = 0
        entry.var_num = entry.config_str_set.length + entry.config_int_set.length + entry.config_bool_set.length + entry.config_blob_set.length
        entry.mon_sel = 0
        entry.mon_num = entry.mon_check_command_set.length
        if not entry._cef
            entry.script_expanded = false
            entry.var_expanded = false
            entry.mon_expanded = false
        else
            for _type in ["var", "script", "mon"]
                if not entry["#{_type}_num"]
                    entry["#{_type}_expanded"] = false
    update_filter_field = () ->
        for entry in _configs
            update_filter_field_config(entry)
    update_filter_field_config = (config) ->
        # set the search field according to the filter settings
        s = []
        if _filter_settings.name
            s.push(config.name)
        # TODO, to be improved
        if _filter_settings.script
            for scr in config.config_script_set
                for attr_name in ["name", "description"]
                    s.push(scr[attr_name])
        if _filter_settings.var
            for vart in ["str", "int", "blob", "bool"]
                for cvar in config["config_#{vart}_set"]
                    for attr_name in ["name", "description"]
                        s.push(cvar[attr_name])
        if _filter_settings.mon
            for moncc in config.mon_check_command_set
                for attr_name in ["name", "description"]
                    s.push(moncc[attr_name])
        config.search_str = s.join(" ")
    _filter_settings = {
        "name" : true
        "script" : false
        "var" : false
        "mon" : false
    }
    return {
        edit_template: "config.form"
        load_promise: _config.promise
        save_defer: (new_obj) ->
            _cd = $q.defer()
            icswConfigRestService.create_config(new_obj).then(
                (new_conf) ->
                    create_extra_fields(new_conf)
                    update_filter_field_config(entry)
                    _cd.resolve(new_conf)
            )
            return _cd.promise
        delete_confirm_str: (obj) ->
            return "Really delete config '#{obj.name}' ?"
        new_object: () ->
            new_obj = {
                "name" : "new config", "description" : "", "priority" : 0, "mon_check_command_set" : [], "config_script_set" : [],
                "config_str_set" : [], "config_int_set" : [], "config_blob_set" : [], "config_bool_set" : [], "enabled" : true,
                "categories" : [],
                "config_catalog" : (entry.idx for entry in _catalogs)[0]
            }
            return new_obj
        update_config: (config) ->
            create_extra_fields(config)
        init_fn: (scope) ->
            scope.$watch("selected_configs", (new_val) ->
                icswConfigRestService.set_num_selected_configs(new_val)
            )
            scope.get_config_catalog_name = (conf) ->
                _cats = (entry for entry in _catalogs when entry.idx == conf.config_catalog)
                if _cats.length
                    return _cats[0].name
                else
                    return "???"
            scope.select = (obj) ->
                obj.isSelected = !obj.isSelected
            scope.get_all_config_hint_names = () ->
                return icswConfigHintService.get_all_config_hint_names()
            scope.show_config_help = (obj) ->
                return icswConfigHintService.get_config_help(obj.name)
            scope.config_selected_vt = (item, model, label, edit_obj) ->
                icswConfigHintService.config_selected_vt(item, edit_obj)
            scope.config_has_info = (config) ->
                return icswConfigHintService.config_has_info(config)
            scope.get_config_help_text = (config) ->
                return icswConfigHintService.get_config_help_text(config)
            scope.get_label_class = (entry, s_type) ->
                num = entry["#{s_type}_num"]
                sel = entry["#{s_type}_sel"]
                if sel and false # $scope.pagSettings.conf.filter_settings.filter_str
                    return "label label-success"
                else if num
                    return "label label-primary"
                else
                    return ""
            scope.get_expand_class = (config, _type) ->
                if config["#{_type}_num"]
                    if config["#{_type}_expanded"]
                        return "glyphicon glyphicon-chevron-down"
                    else
                        return "glyphicon glyphicon-chevron-right"
                else
                    return "glyphicon"
            scope.toggle_expand = (config, _type) ->
                if config["#{_type}_num"]
                    config["#{_type}_expanded"] = not config["#{_type}_expanded"]
            scope.get_num_cats = (config) ->
                return if config.categories.length then "#{config.categories.length}" else "-"
            scope.get_config_row_class = (config) ->
                return if config.enabled then "" else "danger"
            scope.get_all_catalogs = () ->
                return _catalogs
            scope.get_filter_class = (name) ->
                if _filter_settings[name]
                    return "btn btn-xs btn-success"
                else
                    return "btn btn-xs"
            scope.change_filter_setting = (name) ->
                _filter_settings[name] = ! _filter_settings[name]
                if not _.some(_filter_settings)
                    _filter_settings["name"] = true
                update_filter_field()
    }
]).directive("icswConfigUploader", ["$templateCache", "icswConfigRestService", ($templateCache, icswConfigRestService) ->
]).controller("icswConfigConfigCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "restDataSource", "$q", "$modal", "FileUploader", "$http", "blockUI", "icswTools", "ICSW_URLS", "$window", "icswToolsButtonConfigService", "icswCallAjaxService", "icswParseXMLResponseService", "msgbus", "icswConfigVarListService", "icswConfigRestService", "icswConfigListService", "icswConfigHintService", "icswConfigMonCheckCommandHelpService", "icswSimpleAjaxCall",
    ($scope, $compile, $filter, $templateCache, Restangular, restDataSource, $q, $modal, FileUploader, $http, blockUI, icswTools, ICSW_URLS, $window, icswToolsButtonConfigService, icswCallAjaxService, icswParseXMLResponseService, msgbus, icswConfigVarListService, icswConfigRestService, icswConfigListService, icswConfigHintService, icswConfigMonCheckCommandHelpService, icswSimpleAjaxCall) ->
        $scope.icswToolsButtonConfigService = icswToolsButtonConfigService
        # $scope.pagSettings = paginatorSettings.get_paginator("config_list", $scope)
        $scope.selected_configs = 0
        $scope.$watch(
            icswConfigRestService.get_num_selected_configs
            (new_val) ->
                $scope.selected_configs = new_val
        )
        $scope.download_selected = () ->
            hash = angular.toJson((entry.idx for entry in icswConfigRestService.get_selected_configs()))
            window.location = ICSW_URLS.CONFIG_DOWNLOAD_CONFIGS.slice(0, -1) + hash

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
        $scope.entries = []
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
                # $scope.mon_service_templ = data[1]
                # $scope.categories = data[2]
                # ($scope._set_fields(entry, true) for entry in data[0])
                # $scope.entries = data[0]
                # $scope.mccs_list = data[5]
                # $scope.check_commands = data[6]
                # catalog for uploads, TODO, FIXME
                # $scope.catalog = $scope.config_catalogs[0].idx
                # $scope.config_edit.create_list = $scope.entries
                # $scope.config_edit.delete_list = $scope.entries
                # $scope.config_hints = {}
                # $scope.soft_config_hints = []
                # configs found (positive cache)
                # $scope.resolved_config_hints = {}
                # configs not found (negative cache)
                # $scope.no_config_hints = {}
                #for entry in data[4]
                #    $scope.config_hints[entry.config_name] = entry
                #    if not entry.exact_match
                #        $scope.soft_config_hints.push(entry)
                #    entry.var_lut = {}
                #    for vh in entry.config_var_hint_set
                #        entry.var_lut[vh.var_name] = vh
                $scope.reload_upload()
            )
        $scope.reload_upload = () ->
            icswSimpleAjaxCall(
                {
                    url: ICSW_URLS.CONFIG_GET_CACHED_UPLOADS
                    dataType: "json"
                }
            ).then((json) ->
                $scope.cached_uploads = angular.fromJson(json)
            )
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

        $scope.create_var = (config, v_type, event) ->
            sub_scope = $scope.$new()
            _templ = "config.#{v_type}.form"
            sub_scope.config = config
            sub_scope.modify = () ->
                icswConfigRestService.create_var(config, v_type, sub_scope.edit_obj).then(
                    (new_var) ->
                        icswConfigListService.update_config(config)
                        sub_scope.modal.close()
                )
            sub_scope.show_config_var_help = () ->
                return icswConfigHintService.show_config_var_help(sub_scope.config, sub_scope.edit_obj)
            sub_scope.get_config_var_hints = () ->
                return icswConfigHintService.get_config_var_hints(sub_scope.config)
            sub_scope.edit_obj = {
                "config" : config.idx
                "name" : "new #{v_type} var"
                "description" : "new variable (type #{v_type})"
                "value" : {"str" : "", "int" : 0, "bool" : 1}[v_type]
            }
            edit_div = $compile($templateCache.get(_templ))(sub_scope)
            my_modal = BootstrapDialog.show
                message: edit_div
                draggable: true
                title: "Create new #{v_type} variable"
                size: BootstrapDialog.SIZE_WIDE
                closable: true
                closeByBackdrop: false
                cssClass: "modal-tall"
                onshow: (modal) =>
                    height = $(window).height() - 100
                    modal.getModal().find(".modal-body").css("max-height", height)
                onhide: (modal) =>
                    sub_scope.$destroy()
            sub_scope.modal = my_modal

        $scope.create_script = (config, event) ->
            sub_scope = $scope.$new()
            _templ = "config.script.form"
            sub_scope.config = config
            sub_scope.edit_obj = {
                "config"   : config.idx
                "name"     : "new script"
                "priority" : 0
                "enabled"  : true
                "description" : "new config script"
                "edit_value"  : "# config script (" + moment().format() + ")\n#\n"
            }
            sub_scope.editorOptions = {
                lineWrapping : false
                lineNumbers: true
                mode:
                    name : "python"
                    version : 2
                matchBrackets: true
                styleActiveLine: true
                indentUnit : 4
            }
            sub_scope.modify = () ->
                icswConfigRestService.create_script(config, sub_scope.edit_obj).then(
                    (new_script) ->
                        icswConfigListService.update_config(config)
                        sub_scope.modal.close()
                )
            edit_div = $compile($templateCache.get(_templ))(sub_scope)
            my_modal = BootstrapDialog.show
                message: edit_div
                draggable: true
                title: "Create new script"
                size: BootstrapDialog.SIZE_WIDE
                closable: true
                closeByBackdrop: false
                cssClass: "modal-tall"
                onshow: (modal) =>
                    height = $(window).height() - 100
                    modal.getModal().find(".modal-body").css("max-height", height)
                onhide: (modal) =>
                    sub_scope.$destroy()
            sub_scope.modal = my_modal

        $scope.create_mon = (config, event) ->
            sub_scope = $scope.$new()
            _templ = "mon.check.command.form"
            c_name = "cc_#{config.name}"
            c_idx = 1
            cc_names = (cc.name for cc in config.mon_check_command_set)
            while true
                if "#{c_name}_#{c_idx}" in cc_names
                    c_idx++
                else
                    break
            c_name = "#{c_name}_#{c_idx}"
            sub_scope.config = config
            sub_scope.edit_obj = {
                "config" : config.idx
                "name" : c_name
                "is_active": true
                "description" : "Check command"
                "command_line" : "$USER2$ -m $HOSTADDRESS$ uptime"
                "categories" : []
                "arg_name" : "argument"
                "arg_value" : "80"
            }
            angular.extend(sub_scope, icswConfigMonCheckCommandHelpService)
            sub_scope.modify = () ->
                icswConfigRestService.create_mon_check_command(config, sub_scope.edit_obj).then(
                    (new_moncc) ->
                        icswConfigListService.update_config(config)
                        sub_scope.modal.close()
                )
            edit_div = $compile($templateCache.get(_templ))(sub_scope)
            my_modal = BootstrapDialog.show
                message: edit_div
                draggable: true
                title: "Create new MonCheckCommand"
                size: BootstrapDialog.SIZE_WIDE
                closable: true
                closeByBackdrop: false
                cssClass: "modal-tall"
                onshow: (modal) =>
                    height = $(window).height() - 100
                    modal.getModal().find(".modal-body").css("max-height", height)
                onhide: (modal) =>
                    sub_scope.$destroy()
            sub_scope.modal = my_modal

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
        link: (scope, el, attr) ->
            scope.select = (obj) ->
                obj.isSelected = !obj.isSelected
    }
]).directive("icswConfigLine", ["$templateCache", ($templateCache) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.config.line")
    }
]).service('icswConfigVarListService', ["icswConfigListService", "$q", "icswTools", "ICSW_URLS", "icswConfigHintService", "Restangular", (icswConfigListService, $q, icswTools, ICSW_URLS, icswConfigHintService, Restangular) ->
    return {
        delete_confirm_str: (obj) ->
            return "Really delete var '#{obj.name}' ?"
        edit_template: (obj) -> return "config.#{obj.v_type}.form"
        save_defer: (new_obj) ->
        init_fn: (scope) ->
            config = scope.config
            r_val = []
            for v_type in ["str", "int", "bool", "blob"]
                for entry in config["config_#{v_type}_set"]
                    entry.v_type = v_type
                    r_val.push(entry)
                    Restangular.restangularizeElement(
                        null
                        entry
                        {
                            "str" : ICSW_URLS.REST_CONFIG_STR_DETAIL
                            "int" : ICSW_URLS.REST_CONFIG_INT_DETAIL
                            "bool" : ICSW_URLS.REST_CONFIG_BOOL_DETAIL
                            "blob" : ICSW_URLS.REST_CONFIG_BLOB_DETAIL
                        }[v_type].slice(1).slice(0, -2)
                    )
            r_val.sort((_a, _b) ->
                if _a.name > _b.name
                    return 1
                else if _a.name < _b.name
                    return -1
                else
                    return 0
            )
            scope.vars = []
            scope.data_received(r_val)
            scope.select = (obj) ->
                obj.isSelected = !obj.isSelected
            scope.var_has_info = (config, cvar) ->
                return icswConfigHintService.var_has_info(config, cvar)
            scope.get_var_help_text = (config, cvar) ->
                return icswConfigHintService.show_config_var_help(config, cvar)
            scope.get_config_var_hints = (config) ->
                return icswConfigHintService.get_config_var_hints(config)
        post_delete: (scope, obj) ->
            # remove from config_var list
            _list_name = "config_#{obj.v_type}_set"
            config = scope.config
            config[_list_name] = (entry for entry in config[_list_name] when entry.idx != obj.idx)
            icswConfigListService.update_config(config)
    }
]).directive("icswConfigVarTable", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.var.table")
        scope:
            config: "="
        link : (scope, el, attrs) ->
            scope.get_value = (obj) ->
                if obj.v_type == "bool"
                    return if obj.value then "true" else "false"
                else
                    return obj.value
    }
]).service('icswConfigScriptListService', ["icswConfigListService", "$q", "icswTools", "ICSW_URLS", "icswConfigHintService", "Restangular", (icswConfigListService, $q, icswTools, ICSW_URLS, icswConfigHintService, Restangular) ->
    return {
        delete_confirm_str: (obj) ->
            return "Really delete script '#{obj.name}' ?"
        edit_template: "config.script.form"
        save_defer: (new_obj) ->
        init_fn: (scope) ->
            scope.scripts = []
            for entry in scope.config.config_script_set
                Restangular.restangularizeElement(
                    null
                    entry
                    ICSW_URLS.REST_CONFIG_SCRIPT_DETAIL.slice(1).slice(0, -2)
                )
            scope.data_received(scope.config.config_script_set)
            scope.select = (obj) ->
                obj.isSelected = !obj.isSelected
            scope.editorOptions = {
                lineWrapping : false
                lineNumbers: true
                mode:
                    name : "python"
                    version : 2
                matchBrackets: true
                styleActiveLine: true
                indentUnit : 4
            }
            scope.on_script_revert = (obj, get_change_list) ->
                # script is called edit_value in edit_obj
                rename = (key) ->
                    return if key == "value" then "value" else key
                # apply all changes in order of their initial application (i.e. all diffs)
                for changes in get_change_list()
                    if changes.full_dump
                        # we get full obj, on initial, created, deleted
                        for k, v of changes.full_dump
                            obj[rename(k)] = v
                    else
                        # we get a dict {new_data: dat, ...} for each key
                        for k, v of changes
                            obj[rename(k)] = v.new_data
        post_delete: (scope, obj) ->
            # remove from config_script list
            _list_name = "config_script_set"
            config = scope.config
            config[_list_name] = (entry for entry in config[_list_name] when entry.idx != obj.idx)
            icswConfigListService.update_config(config)
    }
]).directive("icswConfigScriptTable", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.script.table")
        scope:
            config: "="
    }
]).service('icswConfigMonCheckCommandHelpService', ["icswConfigRestService", "icswConfigListService", "$q", "icswTools", "ICSW_URLS", "icswConfigHintService", "Restangular", (icswConfigRestService, icswConfigListService, $q, icswTools, ICSW_URLS, icswConfigHintService, Restangular) ->
    _def = icswConfigRestService.fetch("icsw_config_mcc_help_service")
    _configs = []
    _categories = []
    mccs_lut = {}
    mccs_list = []
    _def.then((data) ->
        _configs = data[0]
        _categories = data[2]
        mccs_list = data[5]
        mccs_lut = icswTools.build_lut(mccs_list)
    )
    return {
        "get_mccs_already_used_warning": (edit_obj) ->
            cur_mccs = edit_obj.mon_check_command_special
            warning = ""
            if cur_mccs?
                problem_list = []
                for config in _configs
                    for mcc in config.mon_check_command_set
                        if mcc.idx != edit_obj.idx and mcc.mon_check_command_special == cur_mccs
                            problem_list.push(mcc.name)
                if problem_list.length
                    warning += ""
                    warning += "This special check command is already used in " + problem_list.join(",") + "."
                    warning += "Multiple assignments of special check commands to check commands are not supported and may result in undefined behavior."
            return warning
        "get_mccs_list": () ->
            return mccs_list
        "get_mccs_info": (edit_obj) ->
            cur_mccs = edit_obj.mon_check_command_special
            if cur_mccs
                return mccs_lut[cur_mccs].description
            else
                return ""
        "get_mccs_cmdline": (edit_obj) ->
            cur_mccs = edit_obj.mon_check_command_special
            if cur_mccs
                if mccs_lut[cur_mccs].is_active
                    return mccs_lut[cur_mccs].command_line
                else
                    return "passive check"
            else
                return ""
        "get_mon_command_line": (obj) ->
            if obj.mon_check_command_special
                return mccs_lut[obj.mon_check_command_special].command_line
            else
                return obj.command_line
        "get_moncc_info": (edit_obj) ->
            cur_cl = edit_obj.command_line
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
        "add_argument": (edit_obj) ->
            cur_cl = edit_obj.command_line
            max_argn = 0
            match_list = cur_cl.match(/arg(\d+)/ig)
            if match_list?
                for cur_match in match_list
                    max_argn = Math.max(max_argn, parseInt(cur_match.substring(3)))
            max_argn++
            if edit_obj.arg_name?
                if edit_obj.arg_value?
                    edit_obj.command_line = "#{cur_cl} ${ARG#{max_argn}:#{edit_obj.arg_name.toUpperCase()}:#{edit_obj.arg_value}}"
                else
                    edit_obj.command_line = "#{cur_cl} ${ARG#{max_argn}:#{edit_obj.arg_name.toUpperCase()}}"
            else
                edit_obj.command_line = "#{cur_cl} ${ARG#{max_argn}}"
        "get_event_handler": (ev_idx) ->
            if ev_idx
                # not fast but working
                ev_config = (entry for entry in _configs when ev_idx in (mcc.idx for mcc in entry.mon_check_command_set))
                if ev_config.length
                    return (entry for entry in ev_config[0].mon_check_command_set when entry.idx == ev_idx)[0].name
                else
                    return "???"
            else
                return "---"
        "get_event_handlers": (edit_obj) ->
            ev_handlers = []
            for entry in _configs
                for cc in entry.mon_check_command_set
                    if cc.is_event_handler and cc.idx != edit_obj.idx
                        ev_handlers.push(cc)
            return ev_handlers
    }
]).service('icswConfigMonCheckCommandListService', ["icswSimpleAjaxCall", "icswConfigMonCheckCommandHelpService", "icswConfigListService", "icswTools", "icswConfigHintService", "Restangular", "ICSW_URLS", (icswSimpleAjaxCall, icswConfigMonCheckCommandHelpService, icswConfigListService, icswTools, icswConfigHintService, Restangular, ICSW_URLS) ->
    return {
        delete_confirm_str: (obj) ->
            return "Really delete MonCheckCommand '#{obj.name}' ?"
        edit_template: "mon.check.command.form"
        save_defer: (new_obj) ->
        init_fn: (scope) ->
            angular.extend(scope, icswConfigMonCheckCommandHelpService)
            # Restangularize all elements
            for entry in scope.config.mon_check_command_set
                Restangular.restangularizeElement(
                    null
                    entry
                    ICSW_URLS.REST_MON_CHECK_COMMAND_DETAIL.slice(1).slice(0, -2)
                )
            scope.data_received(scope.config.mon_check_command_set)
            scope.select = (obj) ->
                obj.isSelected = !obj.isSelected
            scope.duplicate = (config, obj, event) ->
                icswSimpleAjaxCall(
                    {
                        url: ICSW_URLS.CONFIG_COPY_MON
                        data:
                            "config": config.idx
                            "mon": obj.idx
                    }
                ).then((xml) ->
                    new_moncc = angular.fromJson($(xml).find("value[name='mon_cc']").text())
                    config.mon_check_command_set.push(new_moncc)
                    Restangular.restangularizeElement(
                        null
                        new_moncc
                        ICSW_URLS.REST_MON_CHECK_COMMAND_DETAIL.slice(1).slice(0, -2)
                    )
                    icswConfigListService.update_config(config)
                )
        post_delete: (scope, obj) ->
            # remove from config_script list
            _list_name = "mon_check_command_set"
            config = scope.config
            config[_list_name] = (entry for entry in config[_list_name] when entry.idx != obj.idx)
            icswConfigListService.update_config(config)
    }
]).directive("icswConfigMonTable", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.mon.table")
    }
]).directive("icswConfigCategoryChoice", ["$templateCache", "icswConfigMonCategoryTreeService", "icswConfigRestService", "$q", ($templateCache, icswConfigMonCategoryTreeService, icswConfigRestService, $q) ->
    return {
        restrict : "EA"
        template : "<tree treeconfig='cat_tree'></tree>"
        scope:
            editObj: "="
        link : (scope, el, attrs) ->
            # start at -1 because we dont count the Top level category
            scope.num_cats = -1
            scope.cat_tree = new icswConfigMonCategoryTreeService(scope)
            update = (cats) ->
                scope.cat_tree.clear_root_nodes()
                cat_tree_lut = {}
                if attrs["mode"] == "conf"
                    sel_cat = scope.editObj.categories
                    top_cat_re = new RegExp(/^\/config/)
                else if attrs["mode"] == "mon"
                    # mon
                    sel_cat = scope.editObj.categories
                    top_cat_re = new RegExp(/^\/mon/)
                for entry in cats
                    if entry.full_name.match(top_cat_re)
                        scope.num_cats++
                        t_entry = scope.cat_tree.new_node(
                            folder: false
                            obj: entry
                            expand: entry.depth < 2
                            selected: entry.idx in sel_cat
                        )
                        cat_tree_lut[entry.idx] = t_entry
                        if entry.parent and entry.parent of cat_tree_lut
                            cat_tree_lut[entry.parent].add_child(t_entry)
                        else
                            # hide selection from root nodes
                            t_entry._show_select = false
                            scope.cat_tree.add_root_node(t_entry)

                scope.cat_tree_lut = cat_tree_lut
                scope.cat_tree.show_selected(true)
            _def = icswConfigRestService.fetch("icsw_config_cat_choice")
            _def.then((data) ->
                cats = data[2]
                update(cats)
            )
            scope.new_selection = (new_sel) ->
                scope.editObj.categories = new_sel
                scope.$digest()
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
