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
    "icsw.backend.config",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.codemirror",
        "angularFileUpload", "ui.select", "icsw.tools.button",
    ]
).service("icswConfigTree",
[
    "icswTools", "ICSW_URLS", "$q", "Restangular", "$rootScope", "icswSimpleAjaxCall", "ICSW_SIGNALS",
(
    icswTools, ICSW_URLS, $q, Restangular, $rootScope, icswSimpleAjaxCall, ICSW_SIGNALS,
) ->
    class icswConfigTree
        constructor: (@list, @catalog_list, @hint_list, @cat_tree) ->
            @uploaded_configs = []
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
                        config.$hint = @config_hint_name_lut[found_names[0]]
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
            # how often a config name is used
            multi_name_dict = _.countBy((config.name for config in @list))
            for cat in @catalog_list
                if cat.configs?
                    cat.configs.length = 0
                else
                    cat.configs = []
            for config in @list
                if not config.$selected?
                    config.$selected = false
                if config.config_catalog
                    @catalog_lut[config.config_catalog].configs.push(config.idx)
                else
                    # hm, config has no catalog ...
                    console.error "*** Config #{config.name} has no valid config_catalog"
                # device config set
                config.usecount = config.device_config_set.length
                # populate helper fields
                config.script_sel = 0
                config.var_sel = 0
                config.mon_sel = 0
                if config.var_list?
                    config.var_list.length = 0
                else
                    config.var_list = []
                for script in config.config_script_set
                    script.$$tree = @
                    if not script.$selected?
                        script.$selected = false
                for mon in config.mon_check_command_set
                    mon.$$tree = @
                    if not mon.$selected?
                        mon.$selected = false
                for vt in ["str", "int", "bool", "blob"]
                    for el in config["config_#{vt}_set"]
                        el.$$tree = @
                        if not el.$selected?
                            el.$selected = false
                        el.$var_type = vt
                        config.var_list.push(el)
                icswTools.order_in_place(
                    config.var_list
                    ["name"]
                    ["desc"]
                )
                config.var_num = config.var_list.length
                config.var_sel = (true for entry in config.var_list when entry.$selected).length
                config.script_num = config.config_script_set.length
                config.script_sel = (true for entry in config.config_script_set when entry.$selected).length
                config.mon_num = config.mon_check_command_set.length
                config.mon_sel = (true for entry in config.mon_check_command_set when entry.$selected).length
                config.mon_check_command_lut = _.keyBy(config.mon_check_command_set, "idx")
                # build info strings for device-config
                if multi_name_dict[config.name] > 1
                    _name = "#{config.name} [" + @catalog_lut[config.config_catalog].name + "]"
                    # flag, can be used in frontend
                    config.$mulitple_names = true
                else
                    _name = "#{config.name}"
                    config.$mulitple_names = false
                config.info_str = "#{_name} (#{config.var_num}, #{config.script_num}, #{config.mon_num})"
                r_v = []
                if config.server_config
                    r_v.push("S")
                if config.system_config
                    r_v.push("Y")
                config.config_type_str = r_v.join("/")
            @$selected = (entry for entry in @list when entry.$selected).length

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
            Restangular.restangularizeElement(null, del_var, _URL.slice(1).slice(0, -2))
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

        # config script create / delete
        create_config_script: (config, new_script) =>
            defer = $q.defer()
            Restangular.all(ICSW_URLS.REST_CONFIG_SCRIPT_LIST.slice(1)).post(new_script).then(
                (new_obj) =>
                    @_fetch_config_script(config, new_obj.idx, defer, "created script")
                (not_ok) ->
                    defer.reject("script not created")
            )
            return defer.promise

        delete_config_script: (config, del_script) =>
            # ensure REST hooks
            Restangular.restangularizeElement(null, del_script, ICSW_URLS.REST_CONFIG_SCRIPT_DETAIL.slice(1).slice(0, -2))
            defer = $q.defer()
            del_script.remove().then(
                (ok) =>
                    _.remove(config.config_script_set, (entry) -> return entry.idx == del_mcc.idx)
                    @build_luts()
                    defer.resolve("deleted")
                (error) ->
                    defer.reject("not deleted")
            )
            return defer.promise

        _fetch_config_script: (config, pk, defer, msg) =>
            Restangular.one(ICSW_URLS.REST_CONFIG_SCRIPT_LIST.slice(1)).get({"idx": pk}).then(
                (new_script) =>
                    new_script = new_script[0]
                    config.config_script_set.push(new_script)
                    @build_luts()
                    defer.resolve(new_script)
            )

        # uploaded configs settings
        load_uploaded_configs: () =>
            defer = $q.defer()
            icswSimpleAjaxCall(
                {
                    url: ICSW_URLS.CONFIG_GET_CACHED_UPLOADS
                    dataType: "json"
                }
            ).then(
                (json) =>
                     _data = angular.fromJson(json)
                     @uploaded_configs.length = 0
                     for entry in _data
                         @uploaded_configs.push(entry)
                     $rootScope.$emit(ICSW_SIGNALS("ICSW_CONFIG_UPLOADED"))
                     defer.resolve("done")
            )
            return defer.promise

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
    # num_selected_configs = 0
    return {
        "load": (client) ->
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise
    }
])
