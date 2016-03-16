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

]).service("icswCachedConfigRestService", ["$q", "Restangular", "ICSW_URLS", "icswCachingCall", "icswTools", "icswSimpleAjaxCall", ($q, Restangular, ICSW_URLS, icswCachingCall, icswTools, icswSimpleAjaxCall) ->
    cached_uploads = undefined
    # number of cached uploads
    num_cached_uploads = 0
    load_data = (client) ->
        if client
            _defer = $q.defer()
        icswSimpleAjaxCall(
            {
                url: ICSW_URLS.CONFIG_GET_CACHED_UPLOADS
                dataType: "json"
            }
        ).then((json) ->
            _data = angular.fromJson(json)
            if cached_uploads is undefined
                cached_uploads = _data
            else
                cached_uploads.length = 0
                for entry in _data
                    cached_uploads.push(entry)
            num_cached_uploads = cached_uploads.length
            if client
                _defer.resolve(cached_uploads)
        )
        if client
           return _defer.promise
    trigger_reload = () ->
        load_data(null)
    return {
        "trigger_reload": () ->
            trigger_reload()
        "load": (client) ->
            return load_data(client)
        "set_num_cached_uploads": (num) ->
            num_cached_uploads = num
        "get_num_cached_uploads": () ->
            return num_cached_uploads
    }
]).service("icswConfigTree",
[
    "icswTools", "ICSW_URLS", "$q", "Restangular", "$rootScope",
(
    icswTools, ICSW_URLS, $q, Restangular, $rootScope
) ->
    class icswConfigTree
        constructor: (@list, @catalog_list, @hint_list, @cat_tree) ->
            @build_luts()

        build_luts: () =>
            # new entries added
            @lut = _.keyBy(@list, "idx")
            @catalog_lut = _.keyBy(@catalog_list, "idx")
            @hint_lut = _.keyBy(@hint_list, "idx")
            @resolve_hints()
            @reorder()
            @update_category_tree()

        resolve_hints: () =>
            soft_hint_list = []
            @config_hint_name_lut = {}
            for config in @list
                config.$hint = null
            for entry in @hint_list
                @config_hint_name_lut[entry.config_name] = entry
                if not entry.exact_match
                    soft_hint_list.push(entry)
                    entry.$cur_re = new RegExp(entry.config_name)
                entry.var_lut = _.keyBy(entry.config_var_hint_set, "var_name")
            # make soft matches
            for config in @list
                if config.name of @config_hint_name_lut
                    config.$hint = @config_hint_name_lut[config.name]
                else
                    found_names = _.sortBy(
                        (entry.config_name for entry in soft_hint_list when entry.$cur_re.test(config.name))
                        (_str) -> return -_str.length
                    )
                    if found_names.length
                        config.$hint = hint_config_name_lut[found_names[0]]
                    else
                        config.$hint = null

        reorder: () =>
            # sort
            icswTools.order_in_place(
                @catalog_list
                ["name"]
                ["asc"]
            )
            icswTools.order_in_place(
                @list
                ["name", "priority"]
                ["asc", "desc"]
            )
            @link()

        link: () =>
            # hints
            # create links between elements
            for cat in @catalog_list
                if cat.configs?
                    cat.configs.length = 0
                else
                    cat.configs = []
            for config in @list
                if config.config_catalog
                    @catalog_lut[config.config_catalog].configs.push(config.idx)
                else
                    # hm, config has no catalog ...
                    console.log "*** Config #{config.name} has no valid config_catalog"
                # populate helper fields
                config.script_sel = 0
                config.var_sel = 0
                config.mon_sel = 0
                if config.var_list?
                    config.var_list.length = 0
                else
                    config.var_list = []
                for vt in ["str", "int", "bool", "blob"]
                    for el in config["config_#{vt}_set"]
                        el.$var_type = vt
                        config.var_list.push(el)
                icswTools.order_in_place(
                    config.var_list
                    ["name"]
                    ["desc"]
                )
                config.var_num = config.var_list.length
                config.script_num = config.config_script_set.length
                config.mon_num = config.mon_check_command_set.length
                config.mon_check_command_lut = _.keyBy(config.mon_check_command_set, "idx")

        update_category_tree: () =>
            @cat_tree.feed_config_tree(@)

        # config catalog create / delete catalogs
        create_config_catalog: (new_cc) =>
            defer = $q.defer()
            Restangular.all(ICSW_URLS.REST_CONFIG_CATALOG_LIST.slice(1)).post(new_cc).then(
                (new_obj) =>
                    @_fetch_config_catalog(new_obj.idx, defer, "created config_catalog")
                (not_ok) ->
                    defer.reject("config catalog not created")
            )
            return defer.promise

        delete_config_catalog: (del_cc) =>
            # ensure REST hooks
            Restangular.restangularizeElement(null, del_cc, ICSW_URLS.REST_CONFIG_CATALOG_DETAIL.slice(1).slice(0, -2))
            defer = $q.defer()
            del_cc.remove().then(
                (ok) =>
                    _.remove(@catalog_list, (entry) -> return entry.idx == del_cc.idx)
                    @build_luts()
                    defer.resolve("deleted")
                (error) ->
                    defer.reject("not deleted")
            )
            return defer.promise

        _fetch_config_catalog: (pk, defer, msg) =>
            Restangular.one(ICSW_URLS.REST_CONFIG_CATALOG_LIST.slice(1)).get({"idx": pk}).then(
                (new_cc) =>
                    new_cc = new_cc[0]
                    @catalog_list.push(new_cc)
                    @build_luts()
                    defer.resolve(msg)
            )

        # config create / delete catalogs
        create_config: (new_conf) =>
            defer = $q.defer()
            Restangular.all(ICSW_URLS.REST_CONFIG_LIST.slice(1)).post(new_conf).then(
                (new_obj) =>
                    @_fetch_config(new_obj.idx, defer, "created config")
                (not_ok) ->
                    defer.reject("config not created")
            )
            return defer.promise

        delete_config: (del_conf) =>
            # ensure REST hooks
            Restangular.restangularizeElement(null, del_conf, ICSW_URLS.REST_CONFIG_DETAIL.slice(1).slice(0, -2))
            defer = $q.defer()
            del_conf.remove().then(
                (ok) =>
                    _.remove(@list, (entry) -> return entry.idx == del_conf.idx)
                    @build_luts()
                    defer.resolve("deleted")
                (error) ->
                    defer.reject("not deleted")
            )
            return defer.promise

        _fetch_config: (pk, defer, msg) =>
            Restangular.one(ICSW_URLS.REST_CONFIG_LIST.slice(1)).get({"idx": pk}).then(
                (new_conf) =>
                    new_conf = new_conf[0]
                    @list.push(new_conf)
                    @build_luts()
                    defer.resolve(new_conf)
            )

        # config create / delete mon_check_commands
        create_mon_check_command: (config, new_mcc) =>
            defer = $q.defer()
            Restangular.all(ICSW_URLS.REST_MON_CHECK_COMMAND_LIST.slice(1)).post(new_mcc).then(
                (new_obj) =>
                    @_fetch_mon_check_command(config, new_obj.idx, defer, "created mcc")
                (not_ok) ->
                    defer.reject("mcc not created")
            )
            return defer.promise

        delete_mon_check_command: (config, del_mcc) =>
            # ensure REST hooks
            Restangular.restangularizeElement(null, del_mcc, ICSW_URLS.REST_MON_CHECK_COMMAND_DETAIL.slice(1).slice(0, -2))
            defer = $q.defer()
            del_mcc.remove().then(
                (ok) =>
                    _.remove(config.mon_check_command_set, (entry) -> return entry.idx == del_mcc.idx)
                    @build_luts()
                    defer.resolve("deleted")
                (error) ->
                    defer.reject("not deleted")
            )
            return defer.promise

        _fetch_mon_check_command: (config, pk, defer, msg) =>
            Restangular.one(ICSW_URLS.REST_MON_CHECK_COMMAND_LIST.slice(1)).get({"idx": pk}).then(
                (new_mcc) =>
                    new_mcc = new_mcc[0]
                    config.mon_check_command_set.push(new_mcc)
                    @build_luts()
                    defer.resolve(new_mcc)
            )


        # config create / delete config_vars
        create_config_var: (config, new_var) =>
            defer = $q.defer()
            VT = _.toUpper(new_var.$var_type)
            _URL = ICSW_URLS["REST_CONFIG_#{VT}_LIST"]
            Restangular.all(_URL.slice(1)).post(new_var).then(
                (new_obj) =>
                    @_fetch_config_var(config, _URL, new_var.$var_type, new_obj.idx, defer, "created var")
                (not_ok) ->
                    defer.reject("var not created")
            )
            return defer.promise

        delete_config_var: (config, del_var) =>
            # ensure REST hooks
            VT = _.toUpper(del_var.$var_type)
            _URL = ICSW_URLS["REST_CONFIG_#{VT}_DETAIL"]
            Restangular.restangularizeElement(null, del_mcc, _URL.slice(1).slice(0, -2))
            defer = $q.defer()
            del_var.remove().then(
                (ok) =>
                    _.remove(config["config_#{del_var.$var_type}_set"], (entry) -> return entry.idx == del_var.idx)
                    @build_luts()
                    defer.resolve("deleted")
                (error) ->
                    defer.reject("not deleted")
            )
            return defer.promise

        _fetch_config_var: (config, url, var_type, pk, defer, msg) =>
            Restangular.one(url.slice(1)).get({"idx": pk}).then(
                (new_var) =>
                    new_var = new_var[0]
                    config["config_#{var_type}_set"].push(new_var)
                    @build_luts()
                    defer.resolve(new_var)
            )


]).service("icswConfigTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "icswCachingCall", "icswTools", "icswConfigTree",
    "$rootScope", "ICSW_SIGNALS", "icswCategoryTreeService",
(
    $q, Restangular, ICSW_URLS, icswCachingCall, icswTools, icswConfigTree,
    $rootScope, ICSW_SIGNALS, icswCategoryTreeService
) ->
    rest_map = [
        [
            ICSW_URLS.REST_CONFIG_LIST,
        ],
        [
            ICSW_URLS.REST_CONFIG_CATALOG_LIST,
        ],
        [
            ICSW_URLS.REST_CONFIG_HINT_LIST,
        ],
    ]
    _fetch_dict = {}
    _result = undefined
    # load called
    load_called = false

    load_data = (client) ->
        load_called = true
        _wait_list = (icswCachingCall.fetch(client, _entry[0], _entry[1], []) for _entry in rest_map)
        _wait_list.push(icswCategoryTreeService.load(client))
        _defer = $q.defer()
        $q.all(_wait_list).then(
            (data) ->
                console.log "*** config tree loaded ***"
                _result = new icswConfigTree(data[0], data[1], data[2], data[3])
                _defer.resolve(_result)
                for client of _fetch_dict
                    # resolve clients
                    _fetch_dict[client].resolve(_result)
                $rootScope.$emit(ICSW_SIGNALS("ICSW_CONFIG_TREE_LOADED"), _result)
                # reset fetch_dict
                _fetch_dict = {}
        )
        if client
            return _defer

    fetch_data = (client) ->
        if client not of _fetch_dict
            # register client
            _defer = $q.defer()
            _fetch_dict[client] = _defer
        if _result
            # resolve immediately
            _fetch_dict[client].resolve(_result)
        return _fetch_dict[client]

    # number of selected configs
    num_selected_configs = 0
    return {
        "load": (client) ->
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise

        "get_num_selected_configs": () ->
            return num_selected_configs
        "set_num_selected_configs": (num) ->
            num_selected_configs = num
        "load_single_config": (pk) ->
            _d = $q.defer()
            Restangular.all(rest_map[0][0].slice(1)).get(pk).then(
                (new_obj) ->
                    _result[0].push(new_obj)
                    _d.resolve(new_obj)
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
    }
]).service("icswConfigHintService", ["icswConfigTreeService", "$q", "icswTools", "ICSW_URLS", (icswConfigTreeService, $q, icswTools, ICSW_URLS) ->
    return {
        "get_config_var_hints": (config) ->
            if config and config.name of config_hints
                return (entry for entry of config_hints[config.name].var_lut)
            else
                return []
    }
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
    "icswConfigTreeService", "$q", "icswTools", "ICSW_URLS", "icswConfigHintService", "$compile",
    "icswComplexModalService", "icswToolsSimpleModalService", "$templateCache", "icswConfigBackup",
(
    icswConfigTreeService, $q, icswTools, ICSW_URLS, icswConfigHintService,
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
        if not config.$selected?
            config.$selected = false
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

        selected_configs: () ->
            if config_tree
                return (entry for entry in config_tree.list when entry.$selected).length
            else
                return 0
        select: (config) ->
            config.$selected = !config.$selected

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
]).directive("icswConfigDownload",
[
    "$templateCache", "icswConfigTreeService", "ICSW_URLS",
(
    $templateCache, icswConfigTreeService, ICSW_URLS,
) ->
    return {
        restrict: "E"
        scope: {
            configService: "="
        }
        template: $templateCache.get("icsw.config.download")
        link: (scope, el, attr) ->

            scope.download_selected = () ->
                icswConfigTreeService.load(scope.$id).then(
                    (tree) ->
                        hash = angular.toJson((entry.idx for entry in tree.list when entry.$selected))
                        window.location = ICSW_URLS.CONFIG_DOWNLOAD_CONFIGS.slice(0, -1) + hash
                )
    }
]).controller("icswConfigUploaderCtrl",
[
    "$scope", "FileUploader", "blockUI", "ICSW_URLS", "icswCSRFService",
(
    $scope, FileUploader, blockUI, ICSW_URLS, icswCSRFService
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
        blockUI.stop()
        $scope.uploader.clearQueue()
        # trigger reload
        # icswCachedConfigRestService.trigger_reload()
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
    "$templateCache", "icswConfigTreeService", "icswCachedConfigRestService", "ICSW_URLS",
    "icswTools", "icswSimpleAjaxCall",
(
    $templateCache, icswConfigTreeService, icswCachedConfigRestService, ICSW_URLS,
    icswTtools, icswSimpleAjaxCall
) ->
    return {
        restrict: "E"
        scope: {}
        template: $templateCache.get("icsw.config.uploaded")
        replace: true
        link: (scope, el, attr) ->
            scope.cached_uploads = []
            icswCachedConfigRestService.load(scope.$id).then((data) ->
                scope.cached_uploads = data
            )
            scope.config_catalogs = []
            scope.use_catalog = 0
            # fixme, todo
            #icswConfigRestService.fetch(scope.$id).then((data) ->
            #    scope.config_catalogs = data[3]
            #    scope.use_catalog = scope.config_catalogs[0].idx
            #)
    }
]).controller("icswConfigConfigCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular", "restDataSource",
    "$q", "$uibModal", "FileUploader", "$http", "blockUI", "icswTools", "ICSW_URLS",
    "icswToolsButtonConfigService", "msgbus", "icswConfigTreeService", "icswConfigListService",
    "icswConfigHintService", "icswSimpleAjaxCall", "icswMonitoringTreeService",
    "icswCachedConfigRestService", "icswConfigMonCheckCommandListService", "icswConfigVarListService",
(
    $scope, $compile, $filter, $templateCache, Restangular, restDataSource,
    $q, $uibModal, FileUploader, $http, blockUI, icswTools, ICSW_URLS,
    icswToolsButtonConfigService, msgbus, icswConfigTreeService, icswConfigListService,
    icswConfigHintService, icswSimpleAjaxCall, icswMonitoringTreeService,
    icswCachedConfigRestService, icswConfigMonCheckCommandListService, icswConfigVarListService
) ->
    config_tree = undefined
    mon_tree = undefined
    ensure_config_tree = () ->
        defer = $q.defer()
        if config_tree
            defer.resolve(config_tree)
        else
            $q.all(
                [
                    icswConfigTreeService.load($scope.$id)
                    icswMonitoringTreeService.load($scope.$id)
                ]
            ).then(
                (data) ->
                    config_tree = data[0]
                    mon_tree = data[1]
                    defer.resolve("loaded")
            )
        return defer.promise

    $scope.selected_objects = []
    $scope.num_cached_uploads = 0
    $scope.$watch(
        () ->
            icswCachedConfigRestService.get_num_cached_uploads()
        (new_val) ->
            $scope.num_cached_uploads = new_val
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

    # hint functions
    $scope.re_compare = (_array, _input) ->
        console.log _array, _input, $scope.config_hints[_array].exact_match
        return true
        cur_pat = new RegExp(_array, "i")
        console.log cur_pat, _input
        return cur_pat.test(_input)

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

    $scope.create_mon_check_command = (event, config) ->
        ensure_config_tree().then(
            (data) ->
                icswConfigMonCheckCommandListService.create_or_edit($scope, event, true, config, config_tree, mon_tree)
        )

    $scope.create_var = (event, config, var_type) ->
        ensure_config_tree().then(
            (data) ->
                icswConfigVarListService.create_or_edit($scope, event, true, config, config_tree, var_type)
        )

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
        sub_scope.mon_service_templ = []
        icswConfigRestService.fetch(sub_scope.$id).then((data) ->
            sub_scope.mon_service_templ = data[1]
        )
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
        if sel and false # $scope.pagSettings.conf.filter_settings.filter_str
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
    "icswConfigListService", "$q", "icswTools", "ICSW_URLS", "icswConfigHintService", "Restangular", "$compile",
    "icswComplexModalService", "icswToolsSimpleModalService", "$templateCache", "icswConfigVarBackup", "toaster",
(
    icswConfigListService, $q, icswTools, ICSW_URLS, icswConfigHintService, Restangular, $compile,
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
            sub_scope.edit_obj = obj_or_parent

            # config hint names

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
                    scope.config_tree.delete_config_var(cvar).then(
                        () ->
                            console.log "confvar deleted"
                    )
            )


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
            configTree: "="
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
                    scope.config_tree.delete_mon_check_command(mon).then(
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
]).directive("icswConfigCachedConfig",
[
    "$templateCache", "$compile", "blockUI", "$uibModal", "Restangular", "ICSW_URLS",
    "icswConfigTreeService", "icswCachedConfigRestService", "icswSimpleAjaxCall",
    "icswConfigListService",
(
    $templateCache, $compile, blockUI, $uibModal, Restangular, ICSW_URLS,
    icswConfigTreeService, icswCachedConfigRestService, icswSimpleAjaxCall,
    icswConfigListService
) ->
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
                blockUI.start()
                icswSimpleAjaxCall(
                    {
                        url     : ICSW_URLS.CONFIG_HANDLE_CACHED_CONFIG
                        data    : {
                            "upload_key" : scope.upload.upload_key
                            "name"       : scope.config.name
                            "catalog"    : scope.catalog
                            "mode"       : "take"
                        }
                    }
                ).then(
                    (xml) ->
                        blockUI.stop()
                        icswCachedConfigRestService.trigger_reload()
                        icswConfigRestService.load_single_config($(xml).find("value[name='new_pk']").text()).then(
                            (new_conf) ->
                                icswConfigListService.enrich_config(new_conf)
                        )
                    (error) ->
                        blockUI.stop()
                )
            scope.delete_config = () ->
                blockUI.start()
                icswSimpleAjaxCall(
                    {
                        url     : ICSW_URLS.CONFIG_HANDLE_CACHED_CONFIG
                        data    : {
                            "upload_key" : scope.upload.upload_key
                            "name"       : scope.config.name
                            "mode"       : "delete"
                        }
                    }
                ).then(
                    (xml) ->
                        blockUI.stop()
                        icswCachedConfigRestService.trigger_reload()
                    (error) ->
                        blockUI.stop()
                )
    }
])
