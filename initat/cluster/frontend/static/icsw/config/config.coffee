# Copyright (C) 2012-2017 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters",
        "restangular", "angularFileUpload", "ui.select", "icsw.tools.button",
    ]
).config(["icswRouteExtensionProvider", (icswRouteExtensionProvider) ->
    icswRouteExtensionProvider.add_route("main.configoverview")
    icswRouteExtensionProvider.add_route("main.moncheckoverview")
]).directive("icswConfigConfigOverview",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.config.overview")
        # controller: "icswConfigConfigCtrl"
        scope: true
    }
]).directive("icswConfigMoncheckOverview",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.moncheck.overview")
        scope: true
        # controller: "icswConfigConfigCtrl"
    }
]).directive("icswConfigCatalogTable",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.catalog.table")
        scope: true
        controller: "icswConfigCatalogTableCtrl"
    }
]).controller("icswConfigCatalogTableCtrl",
[
    "icswConfigTreeService", "$q", "icswTools", "ICSW_URLS", "icswUserService",
    "icswComplexModalService", "icswConfigCatalogBackup", "$compile", "$templateCache",
    "icswToolsSimpleModalService", "$scope", "blockUI",
(
    icswConfigTreeService, $q, icswTools, ICSW_URLS, icswUserService,
    icswComplexModalService, icswConfigCatalogBackup, $compile, $templateCache,
    icswToolsSimpleModalService, $scope, blockUI,
) ->
    $scope.struct = {
        # data present
        data_present: false
        # config tree
        config_tree: undefined
    }

    _load = () ->
        icswConfigTreeService.load($scope.$id).then(
            (tree) ->
                $scope.struct.config_tree = tree
                $scope.struct.data_present = true
        )

    _load()

    $scope.create_or_edit = (event, create, obj_or_parent) ->
        if create
            obj_or_parent = {
                name: "new catalog"
                url: "http://localhost"
                author: icswUserService.get().user.login
            }
        else
            dbu = new icswConfigCatalogBackup()
            dbu.create_backup(obj_or_parent)
        sub_scope = $scope.$new(true)
        sub_scope.edit_obj = obj_or_parent
        icswComplexModalService(
            {
                message: $compile($templateCache.get("config.catalog.form"))(sub_scope)
                title: "Configure Catalog"
                css_class: "modal-wide modal-form"
                ok_label: if create then "Create" else "Modify"
                closable: true
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "")
                        d.reject("form not valid")
                    else
                        if create
                            $scope.struct.config_tree.create_config_catalog(sub_scope.edit_obj).then(
                                (ok) ->
                                    d.resolve("created")
                                (notok) ->
                                    d.reject("not created")
                            )
                        else
                            sub_scope.edit_obj.put().then(
                                (ok) ->
                                    $scope.struct.config_tree.reorder()
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

    $scope.delete = ($event, cc) ->
        icswToolsSimpleModalService("Really delete ConfigCatalog #{cc.name} ?").then(
            () =>
                blockUI.start()
                $scope.struct.config_tree.delete_config_catalog(cc).then(
                    () ->
                        blockUI.stop()
                        console.log "cc deleted"
                    () ->
                        # error
                        blockUI.stop()
                )
        )
]).directive("icswConfigConfigTable",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.config.table")
        scope: true
        controller: "icswConfigConfigTableCtrl"
        link: (scope, el, attr) ->
            scope.select = (obj) ->
                obj.isSelected = !obj.isSelected
    }
]).controller("icswConfigConfigTableCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular",
    "$q", "$uibModal", "FileUploader", "$http", "blockUI", "icswTools", "ICSW_URLS",
    "icswToolsButtonConfigService", "icswConfigTreeService", "icswConfigMonTableService",
    "icswSimpleAjaxCall", "icswMonitoringBasicTreeService", "$rootScope",
    "ICSW_SIGNALS", "icswToolsSimpleModalService", "icswConfigBackup",
    "icswComplexModalService", "icswBackupTools", "$timeout",
(
    $scope, $compile, $filter, $templateCache, Restangular,
    $q, $uibModal, FileUploader, $http, blockUI, icswTools, ICSW_URLS,
    icswToolsButtonConfigService, icswConfigTreeService, icswConfigMonTableService,
    icswSimpleAjaxCall, icswMonitoringBasicTreeService, $rootScope,
    ICSW_SIGNALS, icswToolsSimpleModalService, icswConfigBackup,
    icswComplexModalService, icswBackupTools, $timeout,
) ->

    # used for config and monitoring check setup
    $scope.struct = {
        # data valid
        data_valid: undefined
        # config tree
        config_tree: undefined
        # monitoring tree
        mon_tree: undefined
        # selected objects
        selected_objects: []
        # search string
        search_str: ""
        # open configs
        open_configs: []
        # active tab
        activetab: 0
        tabmaxid: 0
        # show server configs
        with_server: 0
        # show service configs
        with_service: 0
    }

    # filter related functions

    $scope.update_search = () ->
        if $scope.struct.config_tree?
            $scope.struct.config_tree.update_filtered_list(
                $scope.struct.search_str
                $scope.struct.with_server
                $scope.struct.with_service
            )

    _update_filter_settings = () ->
        if $scope.struct.config_tree?
            $scope.update_search()

    $scope.change_boolean_filters = (attr, value) ->
        $scope.struct[attr] = value
        _update_filter_settings()

    _update_filter_settings()

    _fetch = () ->
        $scope.struct.open_configs.length = 0
        $q.all(
            [
                icswConfigTreeService.load($scope.$id)
                icswMonitoringBasicTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.data_valid = true
                $scope.struct.config_tree = data[0]
                $scope.struct.mon_tree = data[1]
                # set filter fields
                _update_filter_settings()
        )

    _fetch()

    $scope.modify_config = ($event, config, prevent_jump) =>
        $event.stopPropagation()
        _used_idxs = (entry.idx for entry in $scope.struct.open_configs)
        if config.idx not in _used_idxs
            _add = true
        else
            _add = false
        if _add
            bu_obj = new icswConfigBackup()
            bu_obj.create_backup(config)
            config.$$_shown_in_tabs = true
            $scope.struct.tabmaxid += 1
            config.tabindex = $scope.struct.tabmaxid + 1
            $scope.struct.open_configs.push(config)
            if !$event.ctrlKey and !prevent_jump
                $timeout(
                    () ->
                        $scope.struct.activetab = config.tabindex
                    0
                )

    $scope.create_config = ($event) =>
        new_config = {
            $$changed: true
            name: "New Configuration"
            description: ""
            priority: 0
            mcc_rel: []
            config_script_set: []
            config_str_set: []
            config_int_set: []
            config_blob_set: []
            config_bool_set: []
            enabled: true
            server_config: false
            system_config: false
            categories: []
            config_catalog: (entry.idx for entry in $scope.struct.config_tree.catalog_list)[0]
        }
        $scope.modify_config($event, new_config, false)

    $scope.delete_config = ($event, conf) ->
        $event.stopPropagation()
        icswToolsSimpleModalService("Really delete Config #{conf.name} ?").then(
            () =>
                blockUI.start("deleting config")
                $scope.struct.config_tree.delete_config(conf).then(
                    () ->
                        if conf.$$_shown_in_tabs
                            # remove vom tabs
                            conf.$$ignore_changes = true
                            $scope.close_config($event, conf)
                        blockUI.stop()
                        console.log "conf deleted"
                    () ->
                        blockUI.stop()
                )
        )

    $scope.clear_selection = ($event) =>
        for entry in $scope.struct.config_tree.list
            entry.$selected = false
        $scope.struct.config_tree.link()

    $scope.toggle_config_select = ($event, config) ->
        config.$selected = !config.$selected
        $scope.struct.config_tree.link()

    $scope.modify_selection = ($event, config) ->
        editlist = []
        for config in $scope.struct.config_tree.list when config.$selected
            editlist.push(config)
        for config in editlist
            $scope.modify_config($event, config, editlist.length > 1)

    $scope.delete_selected_objects = () ->
        if confirm("really delete #{$scope.struct.selected_objects.length} objects ?")
            blockUI.start()
            for obj in $scope.struct.selected_objects
                conf = (entry for entry in $scope.entries when entry.idx == obj.config)[0]
                if obj.object_type == "mon"
                    ref_f = conf.$$res_mcc_rel
                else
                    ref_f = conf["config_#{obj.object_type}_set"]
                ref_f = (_rv for _rv in ref_f when _rv.idx != obj.idx)
                if obj.object_type == "mon"
                    conf.$$res_mcc_rel = ref_f
                else
                    conf["config_#{obj.object_type}_set"] = ref_f
                $scope._set_fields(conf)
            icswSimpleAjaxCall(
                url: ICSW_URLS.CONFIG_DELETE_OBJECTS
                data:
                    obj_list: angular.toJson(([entry.object_type, entry.idx] for entry in $scope.tsruct.selected_objects))
            ).then(
                (xml) ->
                    blockUI.stop()
                (xml) ->
                    blockUI.stop()
            )
            $scope.struct.selected_objects.length = 0

    $scope.unselect_objects = () ->
        # unselect all selected objects
        idx = 0
        while $scope.struct.selected_objects.length
            prev_len = $scope.struct.selected_objects.length
            idx++
            entry = $scope.struct.selected_objects[0]
            $scope.unselect_object($scope.struct.selected_objects[0])
            # unable to unselect, exit loop
            if $scope.struct.selected_objects.length == prev_len
                console.error "problem unselect..."
                break

    $scope.unselect_object = (obj) ->
        obj._selected = false
        $scope.struct.selected_objects = (entry for entry in $scope.struct.selected_objects when entry != obj)

    $scope.select_object = (obj) ->
        if obj._selected
            $scope.unselect_object(obj)
        else
            obj._selected = true
            $scope.struct.selected_objects.push(obj)

    $scope.$on(ICSW_SIGNALS("_ICSW_CLOSE_CONFIG"), ($event, config) ->
        $scope.close_config($event, config)
    )

    $scope.$on(ICSW_SIGNALS("_ICSW_DELETE_CONFIG"), ($event, config) ->
        $scope.delete_config($event, config)
    )

    $scope.close_config = ($event, config) ->
        defer = $q.defer()
        if icswBackupTools.changed(config)
            icswToolsSimpleModalService("Really close config ?").then(
                (ok) ->
                    defer.resolve("close")
                (not_ok) ->
                    defer.reject("not closed")
            )
        else
            defer.resolve("not changed")
        defer.promise.then(
            (close) ->
                $timeout(
                    () ->
                        _removed = _.remove($scope.struct.open_configs, (entry) -> return config.idx == entry.idx)
                        if not _removed.length
                            # not found, must have been new config (entry.idx == undefined)
                            config.$$_shown_in_tabs = false
                            _removed = _.remove($scope.struct.open_configs, (entry) -> return not entry.idx?)
                    100
                )
        )

    # get changed flag
    $scope.changed = (object) ->
        return icswBackupTools.changed(object)

]).directive("icswConfigModify",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.config.modify.form")
        scope:
            config_tree: "=icswConfigTree"
            config: "=icswConfig"
        controller: "icswConfigModifyCtrl"
        link: (scope, element, attrs) ->
            scope.start_edit()
    }
]).controller("icswConfigModifyCtrl",
[
    "$q", "$scope", "icswBackupTools", "ICSW_SIGNALS", "blockUI",
    "icswConfigScriptListService", "icswConfigVarListService",
    "icswMonitoringBasicTreeService", "icswConfigMonTableService",
(
    $q, $scope, icswBackupTools, ICSW_SIGNALS, blockUI,
    icswConfigScriptListService, icswConfigVarListService,
    icswMonitoringBasicTreeService, icswConfigMonTableService,
) ->
    _set_object_from_src = () ->
        $scope.edit_obj = $scope.config.$$_ICSW_backup_data

    $scope.struct = {
        # data is there
        data_ready: false
        # monitoring tree
        mon_tree: undefined
    }

    $scope.data_ready = false

    $scope.start_edit = () ->
        $scope.struct.data_ready = true
        if $scope.config.idx?
            $scope.create_mode = false
        else
            $scope.create_mode = true
        _set_object_from_src()
        icswMonitoringBasicTreeService.load($scope.$id).then(
            (data) ->
                $scope.struct.mon_tree = data
        )
        # console.log $scope.edit_obj
        # console.log "S", $scope.edit_obj

    $scope.changed = () ->
        return icswBackupTools.changed($scope.config)

    $scope.close_config = () ->
        $scope.$emit(ICSW_SIGNALS("_ICSW_CLOSE_CONFIG"), $scope.config)

    $scope.delete_config = () ->
        $scope.$emit(ICSW_SIGNALS("_ICSW_DELETE_CONFIG"), $scope.config)

    $scope.modify = () ->
        # copy data to original object
        bu_def = $scope.config.$$_ICSW_backup_def

        # restore backup
        bu_def.restore_backup($scope.config)

        blockUI.start("updating config")
        defer = $q.defer()

        if $scope.create_mode
            # create new object
            $scope.config_tree.create_config($scope.config).then(
                (created) ->
                    $scope.config = created
                    defer.resolve("created")
                (not_saved) ->
                    defer.reject("not created")
            )
        else
            $scope.config_tree.modify_config($scope.config).then(
                (saved) ->
                    defer.resolve("saved")
                (not_saved) ->
                    defer.reject("not saved")
            )
        defer.promise.then(
            (ok) ->
                # create new backup
                bu_def.create_backup($scope.config)
                _set_object_from_src()
                if $scope.create_mode
                    # close current tab
                    $scope.config.$$ignore_changes = true
                    $scope.$emit(ICSW_SIGNALS("_ICSW_CLOSE_CONFIG"), $scope.config)
                blockUI.stop()
            (not_ok) ->
                console.log "not saved"
                # create new backup
                bu_def.create_backup($scope.config)
                _set_object_from_src()
                blockUI.stop()
        )

    $scope.create_mon_check_command = (event, config) ->
        icswConfigMonTableService.create_or_edit($scope, event, true, config, true)

    $scope.create_var = (event, config, var_type) ->
        icswConfigVarListService.create_or_edit($scope, event, true, config, $scope.config_tree, var_type)

    $scope.create_script = (event, config) ->
        icswConfigScriptListService.create_or_edit($scope, event, true, config, $scope.config_tree)

]).directive("icswMonCheckCommandLine",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.mon.check.command.line")
    }
]).directive("icswMonCheckCommandHeader",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.mon.check.command.header")
    }
]).directive("icswConfigLine",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.config.line")
    }
]).service('icswConfigVarListService',
[
    "$q", "icswTools", "ICSW_URLS", "Restangular", "$compile",
    "icswComplexModalService", "icswToolsSimpleModalService", "$templateCache", "icswConfigVarBackup", "toaster",
(
    $q, icswTools, ICSW_URLS, Restangular, $compile,
    icswComplexModalService, icswToolsSimpleModalService, $templateCache, icswConfigVarBackup, toaster
) ->
    # do NOT use local vars here because this is a service
    get_var_help_text = (config, c_var) ->
        if config.$hint
            if c_var.name of config.$hint.var_lut
                return config.$hint.var_lut[c_var.name].help_text_short or ""
            else
                return ""
        else
            return ""

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
            return get_var_help_text(config, c_var)

        select: (obj) ->
            obj.$selected = !obj.$selected
            obj.$$config_tree.link()

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
                # console.log "tree=", config_tree
                dbu = new icswConfigVarBackup()
                dbu.create_backup(obj_or_parent)
            sub_scope = scope.$new(false)
            sub_scope.create = create
            sub_scope.edit_obj = obj_or_parent
            sub_scope.var_type = var_type
            sub_scope.model_name = "config_#{var_type}"
            sub_scope.long_var_type_name = {
                int: "Integer"
                str: "String"
                bool: "Boolean"
            }[var_type]

            # config hint names
            if scope.config.$hint
                sub_scope.config_var_hints = (entry for entry of scope.config.$hint.var_lut)
            else
                sub_scope.config_var_hints = []

            sub_scope.edit_obj.$$var_help_html = get_var_help_text(scope.config, sub_scope.edit_obj)

            # hint functions
            sub_scope.var_selected = ($item, $model, $label) ->
                sub_scope.edit_obj.$$var_help_html = get_var_help_text(scope.config, sub_scope.edit_obj)

            name_blur = () ->
                sub_scope.edit_obj.$$var_help_html = get_var_help_text(scope.config, sub_scope.edit_obj)

            icswComplexModalService(
                {
                    message: $compile($templateCache.get("icsw.config.strintbool.form"))(sub_scope)
                    title: "ConfigVariable (#{var_type})"
                    css_class: "modal-wide modal-form"
                    ok_label: if create then "Create" else "Modify"
                    closable: true
                    ok_callback: (modal) ->
                        d = $q.defer()
                        if sub_scope.form_data.$invalid
                            toaster.pop("warning", "form validation problem", "")
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
    "$q", "icswTools", "ICSW_URLS", "Restangular", "$compile",
    "icswComplexModalService", "icswToolsSimpleModalService", "$templateCache", "icswConfigScriptBackup", "toaster",
(
    $q, icswTools, ICSW_URLS, Restangular, $compile,
    icswComplexModalService, icswToolsSimpleModalService, $templateCache, icswConfigScriptBackup, toaster
) ->
    return {
        fetch: (scope) ->
            defer = $q.defer()
            defer.resolve(scope.config.config_script_set)
            return defer.promise

        select: (obj) ->
            obj.$selected = !obj.$selected
            obj.$$config_tree.link()

        create_or_edit: (scope, event, create, obj_or_parent, ext_config_tree) ->
            if create
                config_tree = ext_config_tree
                scope.config = obj_or_parent
                obj_or_parent = {
                    config: scope.config.idx
                    priority: 0
                    name: "new script"
                    description: "New Script"
                    enabled: true
                    value: "# config script (" + moment().format() + ")\n#\n"
                }
            else
                config_tree = scope.configTree
                dbu = new icswConfigScriptBackup()
                dbu.create_backup(obj_or_parent)
            sub_scope = scope.$new(false)
            sub_scope.create = create
            sub_scope.edit_obj = obj_or_parent
            sub_scope.ace_options = {
                uswWrapMode: false
                showGutter: true
                mode: "python"
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
                            toaster.pop("warning", "form validation problem", "")
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
            config: "=config"
            configTree: "=configTree"
    }
]).directive("icswConfigMonTable",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.mon.table")
        scope: {
            config: "=icswConfig"
            config_tree: "=icswConfigTree"
        }
        controller: "icswConfigMonTableCtrl"
    }
]).service("icswConfigMonTableService",
[
    "icswSimpleAjaxCall", "icswToolsSimpleModalService", "toaster",
    "icswTools", "Restangular", "ICSW_URLS",  "$q", "blockUI", "icswFormTools",
    "icswConfigTreeService", "icswMonitoringBasicTreeService", "icswMonCheckCommandBackup",
    "icswComplexModalService", "$compile", "$templateCache",
(
    icswSimpleAjaxCall, icswToolsSimpleModalService, toaster,
    icswTools, Restangular, ICSW_URLS, $q, blockUI, icswFormTools,
    icswConfigTreeService, icswMonitoringBasicTreeService, icswMonCheckCommandBackup,
    icswComplexModalService, $compile, $templateCache
) ->
    create_or_edit = (scope, event, create, obj_or_parent, fixed_config) ->
        # may also be called from assign config checks, scope is then the $rootScope
        r_defer = $q.defer()
        sub_scope = scope.$new(true)
        sub_scope.fixed_config = fixed_config
        # console.log "*", ext_config_tree, ext_mon_tree
        if create
            if obj_or_parent.$$config_tree?
                config = obj_or_parent
                config_idx = config.idx
                config_tree = config.$$config_tree
            else
                # config not set, use first one
                config_tree = obj_or_parent
                if fixed_config
                    config = config_tree.list[0]
                    config_idx = config.idx
                else
                    config = null
                    config_idx = null

            if config
                c_name = "cc_#{config.name}"
            else
                c_name = "cc_new"
            cc_names = (cc.name for cc in config_tree.mon_basic_tree.mon_check_command_list)
            c_idx = 1
            while true
                if "#{c_name}_#{c_idx}" in cc_names
                    c_idx++
                else
                    break
            c_name = "#{c_name}_#{c_idx}"
            obj_or_parent = {
                name: c_name
                is_active: true
                enabled: true
                config_rel: if config then [config_idx] else []
                $$res_config_rel: if config then [config] else []
                description: "Check command"
                command_line: "$USER2$ -m $HOSTADDRESS$ uptime"
                categories: []
                arg_name: "argument"
                arg_value: "80"
            }
        else
            config_tree = obj_or_parent.$$config_tree
            dbu = new icswMonCheckCommandBackup()
            dbu.create_backup(obj_or_parent)
        mon_tree = config_tree.mon_basic_tree
        sub_scope.config_tree = config_tree
        sub_scope.create = create
        sub_scope.edit_obj = obj_or_parent
        sub_scope.template_list = mon_tree.mon_service_templ_list

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
                for cc in entry.$$res_mcc_rel
                    if cc.is_event_handler and cc.idx != edit_obj.idx
                        ev_handlers.push(cc)
            return ev_handlers

        cur_config = config_tree.lut[sub_scope.edit_obj.config]
        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.mon.check.command.form"))(sub_scope)
                title: "MonitorCheck Command"
                # css_class: "modal-wide"
                ok_label: if create then "Create" else "Modify"
                closable: true
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        icswFormTools.show_form_error(sub_scope.form_data)
                        d.reject("form not valid")
                    else
                        if create
                            config_tree.create_mon_check_command(sub_scope.edit_obj).then(
                                (ok) ->
                                    d.resolve("created")
                                (notok) ->
                                    d.reject("not created")
                            )
                        else
                            config_tree.modify_mon_check_command(sub_scope.edit_obj).then(
                                (ok) ->
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
                r_defer.resolve("done")
        )
        return r_defer.promise

    delete_entry = (scope, event, mon) ->
        icswToolsSimpleModalService("Really delete MonCheckCommand #{mon.name} ?").then(
            () =>
                blockUI.start()
                mon.$$config_tree.delete_mon_check_command(mon).then(
                    () ->
                        blockUI.stop()
                        console.log "mon deleted"
                    () ->
                        blockUI.stop()
                )
        )

    return {
        create_or_edit: create_or_edit
        delete: delete_entry
    }

]).controller("icswConfigMonTableCtrl",
[
    "$scope", "icswSimpleAjaxCall", "icswToolsSimpleModalService", "toaster",
    "icswTools", "Restangular", "ICSW_URLS",  "$q", "blockUI", "icswFormTools",
    "icswConfigTreeService", "icswMonitoringBasicTreeService", "icswMonCheckCommandBackup",
    "icswComplexModalService", "$compile", "$templateCache", "icswConfigMonTableService",
    "icswTableFilterService",
(
    $scope, icswSimpleAjaxCall, icswToolsSimpleModalService, toaster,
    icswTools, Restangular, ICSW_URLS, $q, blockUI, icswFormTools,
    icswConfigTreeService, icswMonitoringBasicTreeService, icswMonCheckCommandBackup,
    icswComplexModalService, $compile, $templateCache, icswConfigMonTableService,
    icswTableFilterService,
) ->
    $scope.struct = {
        # mode, subtable true or false
        is_sub_table: true
        # data loaded
        data_loaded: false
        # config tree
        config_tree: undefined
        # config
        config: undefined
        # monccs list, to be set on init
        monccs_list: undefined
        # table redraw
        redraw_table: 0
        # filter
        filter: icswTableFilterService.get_instance()
    }
    # init filter
    $scope.struct.filter.add_tri_state(
        "volatile"
        "Volatile"
        "volatile"
    ).end().add_tri_state(
        "perfdata"
        "PerfData"
        "enable_perfdata"
    ).end().add_tri_state(
        "isevh",
        "IsEventHandler"
        "is_event_handler"
    ).end().add_tri_state(
        "evhen",
        "EventHEnabled"
        "event_handler_enabled"
    ).end().add_tri_state(
        "evhen",
        "EventHEnabled"
        "event_handler_enabled"
    ).end().add_tri_state(
        "system"
        "System"
        "system_command"
        2
    ).end().add_tri_state(
        "special"
        "Special"
        "is_special_command"
    ).end().add_tri_state(
        "enabled"
        "Enabled"
        "enabled"
    )

    _update_filter = () ->
        $scope.struct.filter.filter($scope.struct.monccs_list)

    $scope.struct.filter.notifier.promise.then(
        () ->
        () ->
        () ->
            _update_filter()
    )

    $scope.show_columns = {}

    _load = () ->
        $q.all(
            [
                icswConfigTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.config_tree = data[0]
                $scope.struct.monccs_list = $scope.struct.config_tree.filtered_mcc_list
                $scope.struct.data_loaded = true
                _update_filter()

        )

    if $scope.config_tree?
        # is subtable
        $scope.struct.is_sub_table = true
        $scope.struct.data_loaded = true
        $scope.struct.config_tree = $scope.config_tree
        $scope.struct.config = $scope.config
        $scope.struct.monccs_list = $scope.struct.config.$$res_mcc_rel
        _update_filter()

    else
        $scope.struct.is_sub_table = false
        $scope.struct.data_loaded = false
        _load()

    $scope.select = ($event, obj) ->
        obj.$selected = !obj.$selected
        obj.$$config_tree.link()

    $scope.edit = ($event, obj) ->
        if $scope.struct.config?
            _fixed = true
        else
            _fixed = false
        icswConfigMonTableService.create_or_edit($scope, $event, false, obj, _fixed).then(
            (fin) ->
                $scope.struct.redraw_table++
        )

    $scope.delete = ($event, obj) ->
        icswConfigMonTableService.delete($scope, $event, obj)

    $scope.create_mon_check = ($event) =>
        icswConfigMonTableService.create_or_edit($scope, $event, true, $scope.struct.config_tree, false)

    $scope.$on("$destroy", () ->
        $scope.struct.filter.close()
    )

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
        scope: $scope
        url: ICSW_URLS.CONFIG_UPLOAD_CONFIG
        queueLimit: 1
        alias: "config"
        formData: []
        removeAfterUpload: true
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
                if config.$$res_mcc_rel
                    return config.$$res_mcc_rel.length
                else
                    return 0

            scope.take_config = (config) ->
                blockUI.start()
                icswSimpleAjaxCall(
                    {
                        url: ICSW_URLS.CONFIG_HANDLE_CACHED_CONFIG
                        data: {
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
