# Copyright (C) 2012-2016 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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
).config(["$stateProvider", ($stateProvider) ->
    $stateProvider.state(
        "main.configoverview",
            {
                url: "/configoverview"
                # templateUrl: "icsw/main/device/config.html"
                templateUrl: "icsw/main/config/overview.html"
                data:
                    pageTitle: "Configuration Overview"
                    rights: ["device.change_config"]
                    menuEntry:
                        menukey: "dev"
                        name: "Configurations"
                        icon: "fa-check-square-o"
                        ordering: 10
                        preSpacer: true
            }
    )
    $stateProvider.state(
        "main.deviceconfig"
            {
                url: "/deviceconfig"
                templateUrl: "icsw/main/device/config.html"
                data:
                    pageTitle: "Configure Device"
                    rights: ["device.change_config"]
                    menuEntry:
                        menukey: "dev"
                        name: "Device Configurations"
                        icon: "fa-check-square"
                        ordering: 10
            }
    )
]).service("icswCatSelectionTreeService", ["icswTreeConfig", (icswTreeConfig) ->
    class icswCatSelectionTree extends icswTreeConfig
        constructor: (@scope, args) ->
            super(args)
            @show_selection_buttons = false
            @show_icons = false
            @show_select = true
            @show_descendants = false
            @show_childs = false
            @lut = {}

        get_name : (t_entry) ->
            obj = t_entry.obj
            if obj.comment
                return "#{obj.name} (#{obj.comment})"
            else
                return obj.name

        selection_changed: () =>
            sel_list = @get_selected(
                (node) ->
                    if node.selected
                        return [node.obj.idx]
                    else
                        return []
            )
            @scope.new_selection(sel_list)

]).service('icswConfigCatalogListService',
[
    "icswConfigTreeService", "$q", "icswTools", "ICSW_URLS", "icswUserService",
    "icswComplexModalService", "icswConfigCatalogBackup", "$compile", "$templateCache",
    "icswToolsSimpleModalService",
(
    icswConfigTreeService, $q, icswTools, ICSW_URLS, icswUserService,
    icswComplexModalService, icswConfigCatalogBackup, $compile, $templateCache,
    icswToolsSimpleModalService
) ->
    config_tree = undefined
    return {
        fetch: (scope) ->
            defer = $q.defer()
            icswConfigTreeService.load(scope.$id).then(
                (tree) ->
                    config_tree = tree
                    defer.resolve(tree.catalog_list)
            )
            return defer.promise

        create_or_edit: (scope, event, create, obj_or_parent) ->
            if create
                obj_or_parent = {
                    name: "new catalog"
                    url: "http://localhost"
                    author: icswUserService.get().login
                }
            else
                dbu = new icswConfigCatalogBackup()
                dbu.create_backup(obj_or_parent)
            sub_scope = scope.$new(false)
            sub_scope.edit_obj = obj_or_parent
            icswComplexModalService(
                {
                    message: $compile($templateCache.get("config.catalog.form"))(sub_scope)
                    title: "Config Catalog"
                    css_class: "modal-wide"
                    ok_label: if create then "Create" else "Modify"
                    closable: true
                    ok_callback: (modal) ->
                        d = $q.defer()
                        if sub_scope.form_data.$invalid
                            toaster.pop("warning", "form validation problem", "", 0)
                            d.reject("form not valid")
                        else
                            if create
                                config_tree.create_config_catalog(sub_scope.edit_obj).then(
                                    (ok) ->
                                        d.resolve("created")
                                    (notok) ->
                                        d.reject("not created")
                                )
                            else
                                sub_scope.edit_obj.put().then(
                                    (ok) ->
                                        config_tree.reorder()
                                        d.resolve("updated")
                                    (not_ok) ->
                                        d.reject("not updated")
                                )
                        return d.promise
                    cancel_callback: (modal) ->
                        if not create
                            dbu.restore_backup(obj_or_parent)
                        d = $q.defer()
                        d.resolve("cancel")
                        return d.promise
                }
            ).then(
                (fin) ->
                    console.log "finish"
                    sub_scope.$destroy()
            )

        delete: (scope, event, cc) ->
            icswToolsSimpleModalService("Really delete ConfigCatalog #{cc.name} ?").then(
                () =>
                    config_tree.delete_config_catalog(cc).then(
                        () ->
                            console.log "cc deleted"
                    )
            )

    }
]).service('icswConfigListService',
[
    "icswConfigTreeService", "$q", "icswTools", "ICSW_URLS", "$compile",
    "icswComplexModalService", "icswToolsSimpleModalService", "$templateCache", "icswConfigBackup",
(
    icswConfigTreeService, $q, icswTools, ICSW_URLS, $compile,
    icswComplexModalService, icswToolsSimpleModalService, $templateCache, icswConfigBackup
) ->
    config_tree = undefined

    g_create_extra_fields = () ->
        # add extra fields for display expansion
        for entry in config_tree.list
            create_extra_fields(entry)

    create_extra_fields = (config) ->
        config._cef = true
        if not config._cef
            config.script_expanded = false
            config.var_expanded = false
            config.mon_expanded = false
        else
            for _type in ["var", "script", "mon"]
                if not config["#{_type}_num"]
                    config["#{_type}_expanded"] = false

    g_update_filter_field = () ->
        for entry in config_tree.list
            update_filter_field(entry)

    update_filter_field = (config) ->
        # set the search field according to the filter settings
        s = []
        if _filter_settings.name
            s.push(config.name)
        # TODO, to be improved
        if _filter_settings.script
            for scr in config.config_script_set
                for attr_name in ["name", "description", "value"]
                    s.push(scr[attr_name])
        if _filter_settings.var
            for vart in ["str", "int", "blob", "bool"]
                for cvar in config["config_#{vart}_set"]
                    for attr_name in ["name", "description", "value"]
                        s.push(cvar[attr_name])
        if _filter_settings.mon
            for moncc in config.mon_check_command_set
                for attr_name in ["name", "description", "check_command"]
                    s.push(moncc[attr_name])
        # set search string
        config.search_str = s.join(" ")

    _filter_settings = {
        "name" : true
        "script" : false
        "var" : false
        "mon" : false
    }
    enrich_config = (config) ->
        create_extra_fields(config)
        update_filter_field(config)

    return {
        fetch: (scope) ->
            defer = $q.defer()
            icswConfigTreeService.load(scope.$id).then(
                (data) ->
                    config_tree = data
                    scope.config_tree = config_tree
                    g_create_extra_fields()
                    g_update_filter_field()
                    defer.resolve(config_tree.list)
            )
            return defer.promise

        create_or_edit: (scope, event, create, obj_or_parent) ->
            if create
                obj_or_parent = {
                    name: "new config"
                    description: ""
                    priority: 0
                    mon_check_command_set: []
                    config_script_set: []
                    config_str_set: []
                    config_int_set: []
                    config_blob_set: []
                    config_bool_set: []
                    enabled: true
                    categories: []
                    config_catalog: (entry.idx for entry in config_tree.catalog_list)[0]
                }
            else
                dbu = new icswConfigBackup()
                dbu.create_backup(obj_or_parent)
            sub_scope = scope.$new(false)
            sub_scope.edit_obj = obj_or_parent
            sub_scope.config_tree = config_tree
            # config hint names

            sub_scope.config_hint_names = _.keys(config_tree.config_hint_name_lut)

            sub_scope.config_selected_vt = (item, model, label, edit_obj) ->
                if item of config_tree.config_hint_name_lut
                    edit_opj.description = config_tree.config_hint_name_lut[item].config_description

            sub_scope.show_config_help = () ->
                if sub_scope.edit_obj.name of config_tree.config_hint_name_lut
                    return config_tree.config_hint_name_lut[sub_scope.edit_obj.name].help_text_html
                else
                    return ""

            icswComplexModalService(
                {
                    message: $compile($templateCache.get("icsw.config.form"))(sub_scope)
                    title: "Configuration"
                    css_class: "modal-wide"
                    ok_label: if create then "Create" else "Modify"
                    closable: true
                    ok_callback: (modal) ->
                        d = $q.defer()
                        if sub_scope.form_data.$invalid
                            toaster.pop("warning", "form validation problem", "", 0)
                            d.reject("form not valid")
                        else
                            if create
                                config_tree.create_config(sub_scope.edit_obj).then(
                                    (new_conf) ->
                                        enrich_config(new_conf)
                                        d.resolve("created")
                                    (notok) ->
                                        d.reject("not created")
                                )
                            else
                                sub_scope.edit_obj.put().then(
                                    (ok) ->
                                        config_tree.build_luts()
                                        d.resolve("updated")
                                    (not_ok) ->
                                        d.reject("not updated")
                                )
                        return d.promise
                    cancel_callback: (modal) ->
                        if not create
                            dbu.restore_backup(obj_or_parent)
                        d = $q.defer()
                        d.resolve("cancel")
                        return d.promise
                }
            ).then(
                (fin) ->
                    console.log "finish"
                    sub_scope.$destroy()
            )

        delete: (scope, event, conf) ->
            icswToolsSimpleModalService("Really delete Config #{conf.name} ?").then(
                () =>
                    config_tree.delete_config(conf).then(
                        () ->
                            console.log "conf deleted"
                    )
            )

        update_config: (config) ->
            create_extra_fields(config)

        select: (config) ->
            config.$selected = !config.$selected
            config_tree.link()

        get_filter_class: (name) ->
            if _filter_settings[name]
                return "btn btn-sm btn-success"
            else
                return "btn btn-sm"

        change_filter_setting: (name) ->
            _filter_settings[name] = ! _filter_settings[name]
            if not _.some(_filter_settings)
                _filter_settings["name"] = true
            g_update_filter_field()

        init_fn: (scope) ->
            scope.get_system_catalog = () ->
                return (cat for cat in _catalogs when cat.system_catalog)

    }
]).controller("icswConfigConfigCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular", "restDataSource",
    "$q", "$uibModal", "FileUploader", "$http", "blockUI", "icswTools", "ICSW_URLS",
    "icswToolsButtonConfigService", "msgbus", "icswConfigTreeService", "icswConfigListService",
    "icswSimpleAjaxCall", "icswMonitoringTreeService", "icswConfigScriptListService",
    "icswConfigMonCheckCommandListService", "icswConfigVarListService", "$rootScope",
    "ICSW_SIGNALS",
(
    $scope, $compile, $filter, $templateCache, Restangular, restDataSource,
    $q, $uibModal, FileUploader, $http, blockUI, icswTools, ICSW_URLS,
    icswToolsButtonConfigService, msgbus, icswConfigTreeService, icswConfigListService,
    icswSimpleAjaxCall, icswMonitoringTreeService, icswConfigScriptListService,
    icswConfigMonCheckCommandListService, icswConfigVarListService, $rootScope,
    ICSW_SIGNALS
) ->
    $scope.config_tree = undefined
    $scope.mon_tree = undefined
    ensure_config_tree = () ->
        defer = $q.defer()
        if $scope.config_tree? and $scope.mon_tree?
            defer.resolve("present")
        else
            $q.all(
                [
                    icswConfigTreeService.load($scope.$id)
                    icswMonitoringTreeService.load($scope.$id)
                ]
            ).then(
                (data) ->
                    $scope.config_tree = data[0]
                    $scope.mon_tree = data[1]
                    defer.resolve("loaded")
            )
        return defer.promise

    $rootScope.$on(ICSW_SIGNALS("ICSW_CONFIG_TREE_LOADED"), (event, tree) ->
        $scope.config_tree = tree
    )
    $scope.selected_objects = []

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
            icswSimpleAjaxCall(
                url     : ICSW_URLS.CONFIG_DELETE_OBJECTS
                data    :
                    "obj_list" : angular.toJson(([entry.object_type, entry.idx] for entry in $scope.selected_objects))
            ).then(
                (xml) ->
                    blockUI.stop()
                (xml) ->
                    blockUI.stop()
            )
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

    $scope.create_mon_check_command = (event, config) ->
        ensure_config_tree().then(
            (data) ->
                icswConfigMonCheckCommandListService.create_or_edit($scope, event, true, config, $scope.config_tree, $scope.mon_tree)
        )

    $scope.create_var = (event, config, var_type) ->
        ensure_config_tree().then(
            (data) ->
                icswConfigVarListService.create_or_edit($scope, event, true, config, $scope.config_tree, var_type)
        )

    $scope.create_script = (event, config) ->
        ensure_config_tree().then(
            (data) ->
                icswConfigScriptListService.create_or_edit($scope, event, true, config, $scope.config_tree)
        )

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
]).controller("icswConfigLineCtrl",
[
    "$scope",
(
    $scope,
) ->
    $scope.get_config_catalog_name = (conf) ->
        if conf.config_catalog of $scope.config_tree.catalog_lut
            return $scope.config_tree.catalog_lut[conf.config_catalog].name
        else
            return "???"

    $scope.get_expand_class = (config, _type) ->
        if config["#{_type}_num"]
            if config["#{_type}_expanded"]
                return "glyphicon glyphicon-chevron-down"
            else
                return "glyphicon glyphicon-chevron-right"
        else
            return "glyphicon"

    $scope.get_label_class = (entry, s_type) ->
        num = entry["#{s_type}_num"]
        sel = entry["#{s_type}_sel"]
        if sel
            return "label label-success"
        else if num
            return "label label-primary"
        else
            return ""

    $scope.toggle_expand = (config, _type) ->
        if config["#{_type}_num"]
            config["#{_type}_expanded"] = not config["#{_type}_expanded"]

    $scope.get_num_cats = (config) ->
        return if config.categories.length then "#{config.categories.length}" else "-"

    $scope.get_config_row_class = (config) ->
        return if config.enabled then "" else "danger"

    # hint related services
    $scope.get_config_help_text = (config) ->
        if config.$hint
            return config.$hint.help_text_short or "no short help"
        else
            return "---"

]).directive("icswConfigLine", ["$templateCache", ($templateCache) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.config.line")
    }
]).service('icswConfigVarListService',
[
    "icswConfigListService", "$q", "icswTools", "ICSW_URLS", "Restangular", "$compile",
    "icswComplexModalService", "icswToolsSimpleModalService", "$templateCache", "icswConfigVarBackup", "toaster",
(
    icswConfigListService, $q, icswTools, ICSW_URLS, Restangular, $compile,
    icswComplexModalService, icswToolsSimpleModalService, $templateCache, icswConfigVarBackup, toaster
) ->
    # do NOT use local vars here because this is a service
    return {
        fetch: (scope) ->
            defer = $q.defer()
            defer.resolve(scope.config.var_list)
            return defer.promise

        get_value: (obj) ->
            if obj.$var_type == "bool"
                return if obj.value then "true" else "false"
            else
                return obj.value

        var_has_info: (config, c_var) ->
            if config.$hint
                return c_var.name of config.$hint.var_lut
            else
                return false

        get_var_help_text: (config, c_var) ->
            if config.$hint
                if c_var.name of config.$hint.var_lut
                    return config.$hint.var_lut[c_var.name].help_text_short or ""
                else
                    return ""
            else
                return ""

        select: (obj) ->
            obj.$selected = !obj.$selected
            obj.$$tree.link()

        create_or_edit: (scope, event, create, obj_or_parent, ext_config_tree, var_type) ->
            if create
                config_tree = ext_config_tree
                scope.config = obj_or_parent
                obj_or_parent = {
                    config: scope.config.idx
                    $var_type: var_type
                    name: "new #{var_type} var"
                    description: "New variable (type #{var_type})"
                    value: {
                        str: ""
                        int: 0
                        bool: 1
                    }[var_type]
                }
            else
                var_type = obj_or_parent.$var_type
                config_tree = scope.configTree
                console.log "tree=", config_tree
                dbu = new icswConfigVarBackup()
                dbu.create_backup(obj_or_parent)
            sub_scope = scope.$new(false)
            sub_scope.create = create
            sub_scope.edit_obj = obj_or_parent

            # config hint names
            if scope.config.$hint
                sub_scope.config_var_hints = (entry for entry of scope.config.$hint.var_lut)
            else
                sub_scope.config_var_hints = []

            icswComplexModalService(
                {
                    message: $compile($templateCache.get("icsw.config.#{var_type}.form"))(sub_scope)
                    title: "ConfigVariable (#{var_type})"
                    css_class: "modal-wide"
                    ok_label: if create then "Create" else "Modify"
                    closable: true
                    ok_callback: (modal) ->
                        d = $q.defer()
                        if sub_scope.form_data.$invalid
                            toaster.pop("warning", "form validation problem", "", 0)
                            d.reject("form not valid")
                        else
                            if create
                                config_tree.create_config_var(scope.config, sub_scope.edit_obj).then(
                                    (new_conf) ->
                                        d.resolve("created")
                                    (notok) ->
                                        d.reject("not created")
                                )
                            else
                                VT = _.toUpper(sub_scope.edit_obj.$var_type)
                                _URL = ICSW_URLS["REST_CONFIG_#{VT}_DETAIL"]
                                Restangular.restangularizeElement(null, sub_scope.edit_obj, _URL.slice(1).slice(0, -2))
                                sub_scope.edit_obj.put().then(
                                    (ok) ->
                                        config_tree.build_luts()
                                        d.resolve("updated")
                                    (not_ok) ->
                                        d.reject("not updated")
                                )
                        return d.promise
                    cancel_callback: (modal) ->
                        if not create
                            dbu.restore_backup(obj_or_parent)
                        d = $q.defer()
                        d.resolve("cancel")
                        return d.promise
                }
            ).then(
                (fin) ->
                    console.log "finish"
                    sub_scope.$destroy()
            )

        delete: (scope, event, cvar) ->
            icswToolsSimpleModalService("Really delete ConfigVariable #{cvar.name} ?").then(
                () =>
                    scope.configTree.delete_config_var(scope.config, cvar).then(
                        () ->
                            console.log "confvar deleted"
                    )
            )
    }
]).directive("icswConfigVarTable", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.var.table")
        scope:
            config: "="
            configTree: "="
    }
]).service('icswConfigScriptListService',
[
    "icswConfigListService", "$q", "icswTools", "ICSW_URLS", "Restangular", "$compile",
    "icswComplexModalService", "icswToolsSimpleModalService", "$templateCache", "icswConfigScriptBackup", "toaster",
(
    icswConfigListService, $q, icswTools, ICSW_URLS, Restangular, $compile,
    icswComplexModalService, icswToolsSimpleModalService, $templateCache, icswConfigScriptBackup, toaster
) ->
    return {
        fetch: (scope) ->
            defer = $q.defer()
            defer.resolve(scope.config.config_script_set)
            return defer.promise

        select: (obj) ->
            obj.$selected = !obj.$selected
            obj.$$tree.link()

        create_or_edit: (scope, event, create, obj_or_parent, ext_config_tree) ->
            if create
                config_tree = ext_config_tree
                scope.config = obj_or_parent
                obj_or_parent = {
                    config: scope.config.idx
                    priority: 0
                    name: "new script"
                    description: "New Script"
                    value: "# config script (" + moment().format() + ")\n#\n"
                }
            else
                config_tree = scope.configTree
                dbu = new icswConfigScriptBackup()
                dbu.create_backup(obj_or_parent)
            sub_scope = scope.$new(false)
            sub_scope.create = create
            sub_scope.edit_obj = obj_or_parent
            sub_scope.editorOptions = {
                lineWrapping: false
                lineNumbers: true
                mode:
                    name: "python"
                    version: 2
                matchBrackets: true
                styleActiveLine: true
                indentUnit: 4
            }
            sub_scope.on_script_revert = (obj, get_change_list) ->
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


            icswComplexModalService(
                {
                    message: $compile($templateCache.get("icsw.config.script.form"))(sub_scope)
                    title: "ConfigScript"
                    css_class: "modal-wide"
                    ok_label: if create then "Create" else "Modify"
                    closable: true
                    ok_callback: (modal) ->
                        d = $q.defer()
                        if sub_scope.form_data.$invalid
                            toaster.pop("warning", "form validation problem", "", 0)
                            d.reject("form not valid")
                        else
                            if create
                                config_tree.create_config_script(scope.config, sub_scope.edit_obj).then(
                                    (new_conf) ->
                                        d.resolve("created")
                                    (notok) ->
                                        d.reject("not created")
                                )
                            else
                                Restangular.restangularizeElement(null, sub_scope.edit_obj, ICSW_URLS.REST_CONFIG_SCRIPT_DETAIL.slice(1).slice(0, -2))
                                sub_scope.edit_obj.put().then(
                                    (ok) ->
                                        config_tree.build_luts()
                                        d.resolve("updated")
                                    (not_ok) ->
                                        d.reject("not updated")
                                )
                        return d.promise
                    cancel_callback: (modal) ->
                        if not create
                            dbu.restore_backup(obj_or_parent)
                        d = $q.defer()
                        d.resolve("cancel")
                        return d.promise
                }
            ).then(
                (fin) ->
                    console.log "finish"
                    sub_scope.$destroy()
            )

        delete: (scope, event, cscript) ->
            icswToolsSimpleModalService("Really delete ConfigScript #{cscript.name} ?").then(
                () =>
                    scope.configTree.delete_config_script(scope.config, cscript).then(
                        () ->
                            console.log "confscript deleted"
                    )
            )
    }
]).directive("icswConfigScriptTable", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.script.table")
        scope:
            config: "="
            configTree: "="
    }
]).service('icswConfigMonCheckCommandListService',
[
    "icswSimpleAjaxCall", "icswConfigListService", "icswToolsSimpleModalService",
    "icswTools", "Restangular", "ICSW_URLS", "msgbus", "$q",
    "icswConfigTreeService", "icswMonitoringTreeService", "icswMonCheckCommandBackup",
    "icswComplexModalService", "$compile", "$templateCache",
(
    icswSimpleAjaxCall, icswConfigListService, icswToolsSimpleModalService,
    icswTools, Restangular, ICSW_URLS, msgbus, $q,
    icswConfigTreeService, icswMonitoringTreeService, icswMonCheckCommandBackup,
    icswComplexModalService, $compile, $templateCache
) ->
    config_tree = undefined
    mon_tree = undefined
    return {
        fetch: (scope) ->
            defer = $q.defer()
            $q.all(
                [
                    icswConfigTreeService.load(scope.$id)
                    icswMonitoringTreeService.load(scope.$id)
                ]
            )
            .then(
                (data) ->
                    config_tree = data[0]
                    mon_tree = data[1]
                    defer.resolve(scope.config.mon_check_command_set)
            )
            return defer.promise

        select: (obj) ->
            obj.$selected = !obj.$selected
            obj.$$tree.link()

        get_mon_command_line: (mon) ->
            if mon.mon_check_command_special
                return mon_tree.mon_check_command_special_lut[mon.mon_check_command_special].command_line
            else
                return mon.command_line

        get_event_handler: (ev_idx) ->
            if ev_idx
                # not fast but working
                ev_config = (entry for entry in config_tree.list when ev_idx of entry.mon_check_command_lut)
                if ev_config.length
                    return (entry for entry in ev_config[0].mon_check_command_set when entry.idx == ev_idx)[0].name
                else
                    return "???"
            else
                return "---"

        create_or_edit: (scope, event, create, obj_or_parent, ext_config_tree, ext_mon_tree) ->
            if create
                config_tree = ext_config_tree
                mon_tree = ext_mon_tree
                # config must be in the local scope
                scope.config = obj_or_parent
                c_name = "cc_#{scope.config.name}"
                c_idx = 1
                cc_names = (cc.name for cc in scope.config.mon_check_command_set)
                while true
                    if "#{c_name}_#{c_idx}" in cc_names
                        c_idx++
                    else
                        break
                c_name = "#{c_name}_#{c_idx}"
                obj_or_parent = {
                    config: scope.config.idx
                    name: c_name
                    is_active: true
                    description: "Check command"
                    command_line: "$USER2$ -m $HOSTADDRESS$ uptime"
                    categories: []
                    arg_name: "argument"
                    arg_value: "80"
                }
            else
                dbu = new icswMonCheckCommandBackup()
                dbu.create_backup(obj_or_parent)
            sub_scope = scope.$new(false)
            sub_scope.edit_obj = obj_or_parent
            sub_scope.mccs_list = mon_tree.mon_check_command_special_list
            sub_scope.get_mccs_info = (edit_obj) ->
                cur_mccs = edit_obj.mon_check_command_special
                if cur_mccs
                    return mon_tree.mon_check_command_special_lut[cur_mccs].description
                else
                    return ""
            sub_scope.get_mccs_cmdline = (edit_obj) ->
                cur_mccs = edit_obj.mon_check_command_special
                if cur_mccs
                    if mon_tree.mon_check_command_special_lut[cur_mccs].is_active
                        return mon_tree.mon_check_command_special_lut[cur_mccs].command_line
                    else
                        return "passive check"
                else
                    return ""

            sub_scope.get_mccs_already_used_warning=  (edit_obj) ->
                cur_mccs = edit_obj.mon_check_command_special
                warning = ""
                if cur_mccs?
                    problem_list = []
                    for config in config_tree.list
                        for mcc in config.mon_check_command_set
                            if mcc.idx != edit_obj.idx and mcc.mon_check_command_special == cur_mccs
                                problem_list.push(mcc.name)
                    if problem_list.length
                        warning += ""
                        warning += "This special check command is already used in " + problem_list.join(",") + "."
                        warning += "Multiple assignments of special check commands to check commands are not supported and may result in undefined behavior."
                return warning

            sub_scope.add_argument = (edit_obj) ->
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

            sub_scope.get_moncc_info = (edit_obj) ->
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

            sub_scope.get_event_handlers = (edit_obj) ->
                ev_handlers = []
                for entry in config_tree.list
                    for cc in entry.mon_check_command_set
                        if cc.is_event_handler and cc.idx != edit_obj.idx
                            ev_handlers.push(cc)
                return ev_handlers

            icswComplexModalService(
                {
                    message: $compile($templateCache.get("icsw.mon.check.command.form"))(sub_scope)
                    title: "MonitorCheck Command"
                    css_class: "modal-wide"
                    ok_label: if create then "Create" else "Modify"
                    closable: true
                    ok_callback: (modal) ->
                        d = $q.defer()
                        if sub_scope.form_data.$invalid
                            toaster.pop("warning", "form validation problem", "", 0)
                            d.reject("form not valid")
                        else
                            if create
                                config_tree.create_mon_check_command(scope.config, sub_scope.edit_obj).then(
                                    (ok) ->
                                        d.resolve("created")
                                    (notok) ->
                                        d.reject("not created")
                                )
                            else
                                Restangular.restangularizeElement(null, sub_scope.edit_obj, ICSW_URLS.REST_MON_CHECK_COMMAND_DETAIL.slice(1).slice(0, -2))
                                sub_scope.edit_obj.put().then(
                                    (ok) ->
                                        config_tree.build_luts()
                                        d.resolve("updated")
                                    (not_ok) ->
                                        d.reject("not updated")
                                )
                        return d.promise
                    cancel_callback: (modal) ->
                        if not create
                            dbu.restore_backup(obj_or_parent)
                        d = $q.defer()
                        d.resolve("cancel")
                        return d.promise
                }
            ).then(
                (fin) ->
                    console.log "finish"
                    sub_scope.$destroy()
            )

        delete: (scope, event, mon) ->
            icswToolsSimpleModalService("Really delete MonCheckCommand #{mon.name} ?").then(
                () =>
                    scope.configTree.delete_mon_check_command(scope.config, mon).then(
                        () ->
                            console.log "mon deleted"
                    )
            )

    }
]).directive("icswConfigMonTable", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.mon.table")
        scope: {
            config: "="
            configTree: "="
        }
    }
]).directive("icswCategoryTreeSelect",
[
    "$templateCache", "icswCatSelectionTreeService", "icswConfigTreeService", "$q",
    "icswCategoryTreeService",
(
    $templateCache, icswCatSelectionTreeService, icswConfigTreeService, $q,
    icswCategoryTreeService
) ->
    return {
        restrict : "EA"
        template : "<tree treeconfig='cat_tree'></tree>"
        scope:
            editObj: "="
            mode: "="
        link : (scope, el, attrs) ->
            scope.cat_tree = new icswCatSelectionTreeService(scope)
            icswCategoryTreeService.load(scope.$id).then(
                (tree) ->
                    scope.cat_tree.clear_root_nodes()
                    if scope.editObj?
                        sel_cat = scope.editObj.categories
                    else
                        sel_cat = []
                    top_cat_re = new RegExp("/#{scope.mode}")
                    for entry in tree.list
                        if entry.full_name.match(top_cat_re)
                            t_entry = scope.cat_tree.new_node(
                                folder: false
                                obj: entry
                                expand: entry.depth < 2
                                selected: entry.idx in sel_cat
                            )
                            scope.cat_tree.lut[entry.idx] = t_entry
                            if entry.parent and entry.parent of scope.cat_tree.lut
                                scope.cat_tree.lut[entry.parent].add_child(t_entry)
                            else
                                # hide selection from root nodes
                                t_entry._show_select = false
                                scope.cat_tree.add_root_node(t_entry)
                    scope.cat_tree.show_selected(true)
            )
            scope.new_selection = (new_sel) ->
                scope.editObj.categories = new_sel
    }
]).directive("icswConfigDownload",
[
    "$templateCache", "icswConfigTreeService", "ICSW_URLS",
(
    $templateCache, icswConfigTreeService, ICSW_URLS,
) ->
    return {
        restrict: "E"
        scope: {
            configTree: "="
        }
        template: $templateCache.get("icsw.config.download")
        link: (scope, el, attr) ->

            scope.download_selected = () ->
                hash = angular.toJson((entry.idx for entry in scope.configTree.list when entry.$selected))
                window.location = ICSW_URLS.CONFIG_DOWNLOAD_CONFIGS.slice(0, -1) + hash
    }
]).controller("icswConfigUploaderCtrl",
[
    "$scope", "FileUploader", "blockUI", "ICSW_URLS", "icswCSRFService", "icswConfigTreeService",
(
    $scope, FileUploader, blockUI, ICSW_URLS, icswCSRFService, icswConfigTreeService
) ->
    $scope.uploader = new FileUploader(
        scope : $scope
        url : ICSW_URLS.CONFIG_UPLOAD_CONFIG
        queueLimit : 1
        alias : "config"
        formData : []
        removeAfterUpload : true
    )

    # fetch CSRF-token from Service
    icswCSRFService.get_token().then(
        (token) ->
            $scope.uploader.formData.push({"csrfmiddlewaretoken": token})
    )

    $scope.uploader.onBeforeUploadItem = () ->
        blockUI.start()
        return null

    $scope.uploader.onCompleteAll = () ->
        $scope.uploader.clearQueue()
        icswConfigTreeService.load($scope.$id).then(
            (tree) ->
                tree.load_uploaded_configs().then(
                    (done) ->
                        blockUI.stop()
                )
        )
        return null

]).directive("icswConfigUploader",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "E"
        scope: {}
        template: $templateCache.get("icsw.config.uploader")
        controller: "icswConfigUploaderCtrl"
        replace: true
    }
]).directive("icswConfigUploaded",
[
    "$templateCache", "icswConfigTreeService", "ICSW_URLS",
    "icswTools", "icswSimpleAjaxCall", "$rootScope", "ICSW_SIGNALS",
(
    $templateCache, icswConfigTreeService, ICSW_URLS,
    icswTtools, icswSimpleAjaxCall, $rootScope, ICSW_SIGNALS,
) ->
    return {
        restrict: "E"
        scope: {}
        template: $templateCache.get("icsw.config.uploaded")
        replace: true
        link: (scope, el, attr) ->
            scope.config_tree = undefined
            scope.use_catalog = 0
            console.log $rootScope, ICSW_SIGNALS("ICSW_CONFIG_UPLOADED")
            _reload = () ->
                icswConfigTreeService.load(scope.$id).then(
                    (tree) ->
                        scope.config_tree = tree
                        scope.use_catalog = scope.config_tree.catalog_list[0].idx
            )
            $rootScope.$on(ICSW_SIGNALS("ICSW_CONFIG_UPLOADED"), (event) ->
                # react on all furhter config uploads
                _reload()
            )
            # this will be called when the directive is initially rendered
            _reload()
    }
]).directive("icswConfigUploadInfo",
[
    "$templateCache", "ICSW_URLS", "icswConfigTreeService", "blockUI", "icswSimpleAjaxCall",
(
    $templateCache, ICSW_URLS, icswConfigTreeService, blockUI, icswSimpleAjaxCall
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.cached.upload.info")
        scope : {
            upload: "="
            catalog: "="
            config_tree: "=configTree"
        }
        replace : true
        link : (scope, el, attrs) ->
            scope.get_num_vars = (config) ->
                num = 0
                for _en in ["config_blob_set", "config_bool_set", "config_int_set", "config_str_set"]
                    if config[_en]
                        num += config[_en].length
                return num

            scope.get_num_scripts = (config) ->
                if config.config_script_set
                    return config.config_script_set.length
                else
                    return 0

            scope.get_num_check_commands = (config) ->
                if config.mon_check_command_set
                    return config.mon_check_command_set.length
                else
                    return 0

            scope.take_config = (config) ->
                blockUI.start()
                icswSimpleAjaxCall(
                    {
                        url     : ICSW_URLS.CONFIG_HANDLE_CACHED_CONFIG
                        data    : {
                            upload_key: scope.upload.upload_key
                            catalog: scope.catalog
                            name: config.name
                            mode: "take"
                        }
                    }
                ).then(
                    (xml) ->
                        scope.config_tree.load_uploaded_configs().then(
                            (done) ->
                                blockUI.stop()
                        )
                    (error) ->
                        blockUI.stop()
                )
            scope.delete_config = (config) ->
                blockUI.start()
                icswSimpleAjaxCall(
                    {
                        url     : ICSW_URLS.CONFIG_HANDLE_CACHED_CONFIG
                        data    : {
                            upload_key: scope.upload.upload_key
                            name: config.name
                            mode: "delete"
                        }
                    }
                ).then(
                    (xml) ->
                        scope.config_tree.load_uploaded_configs().then(
                            (done) ->
                                blockUI.stop()
                        )
                    (error) ->
                        blockUI.stop()
                )
    }
])
