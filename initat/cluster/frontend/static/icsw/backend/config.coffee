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
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular",
        "angularFileUpload", "ui.select", "icsw.tools.button",
    ]
).service("icswConfigTree",
[
    "icswTools", "ICSW_URLS", "$q", "Restangular", "$rootScope", "icswSimpleAjaxCall", "ICSW_SIGNALS",
(
    icswTools, ICSW_URLS, $q, Restangular, $rootScope, icswSimpleAjaxCall, ICSW_SIGNALS,
) ->
    class icswConfigTree
        constructor: (@list, @cse_list, @catalog_list, @hint_list, @cat_tree) ->
            @uploaded_configs = []
            @filtered_list = []
            @build_luts()

        build_luts: () =>
            _start = new Date().getTime()
            # new entries added
            @lut = _.keyBy(@list, "idx")
            @cse_lut = _.keyBy(@cse_list, "idx")
            @catalog_lut = _.keyBy(@catalog_list, "idx")
            @hint_lut = _.keyBy(@hint_list, "idx")
            @mcc_to_config_lut = {}
            @mcc_lut = {}
            for config in @list
                for mcc in config.mon_check_command_set
                    @mcc_to_config_lut[mcc.idx] = config.idx
                    @mcc_lut[mcc.idx] = mcc
            @resolve_hints()
            @reorder()
            @update_filtered_list()
            @update_category_tree()
            _end = new Date().getTime()
            console.log("ConfigTree.build_luts() took " + icswTools.get_diff_time_ms(_end - _start))

        resolve_hints: () =>
            @soft_hint_list = []
            @config_hint_name_lut = {}
            @config_hint_names = []
            for config in @list
                config.$hint = null
            for entry in @hint_list
                @config_hint_name_lut[entry.config_name] = entry
                @config_hint_names.push(entry.config_name)
                if not entry.exact_match
                    @soft_hint_list.push(entry)
                    entry.$cur_re = new RegExp(entry.config_name)
                entry.var_lut = _.keyBy(entry.config_var_hint_set, "var_name")
            # make soft matches
            for config in @list
                @_check_config_hint(config)

        _check_config_hint: (config) =>
            if config.name of @config_hint_name_lut
                config.$hint = @config_hint_name_lut[config.name]
            else
                found_names = _.sortBy(
                    (entry.config_name for entry in @soft_hint_list when entry.$cur_re.test(config.name))
                    (_str) -> return -_str.length
                )
                if found_names.length
                    config.$hint = @config_hint_name_lut[found_names[0]]
                else
                    config.$hint = null
            @_set_config_line_fields(config)

        # typeahead match
        config_selected_vt: ($item, $model, $label, config) =>
            if $item of @config_hint_name_lut
                # set hint
                config.$hint = @config_hint_name_lut[$item]
                # update fiels
                @_set_config_line_fields(config)

        check_config_hint: (config) =>
            console.log config.name
            @_check_config_hint(config)

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

        _init_expansion_fields: (config) =>
            if not config.$$script_expanded?
                # expansion flags
                config.$$script_expanded = false
                config.$$var_expanded = false
                config.$$mon_expanded = false
                for _type in ["script", "var", "mon"]
                    config["$$#{_type}_expanded"] = false
                    @_set_config_expansion_class(config, _type)

        _set_config_class: (config, type) =>
            _num = config["$$num_#{type}"]
            _sel= config["$$num_#{type}_found"]
            if not _sel?
                # may be undefined during first run
                _sel = 0
            if _num
                # if config["$$#{type}_expanded"]
                #     config["$$#{type}_expansion_class"] = "glyphicon glyphicon-chevron-down"
                # else
                #     config["$$#{type}_expansion_class"] = "glyphicon glyphicon-chevron-right"
                if _sel
                    config["$$#{type}_label_class"] = "label label-success"
                else
                    config["$$#{type}_label_class"] = "label label-primary"
            else
                # config["$$#{type}_expansion_class"] = "glyphicon"
                config["$$#{type}_label_class"] = ""
            if _sel
                if _sel == _num
                    config["$$#{type}_span_str"] = "all #{_num}"
                else
                    config["$$#{type}_span_str"] = "#{_sel} of #{_num}"
            else
                config["$$#{type}_span_str"] = "#{_num}"

        toggle_expand: (config, type) =>
            _num = config["$$num_#{type}"]
            if _num
                config["$$#{type}_expanded"] = !config["$$#{type}_expanded"]
            else
                config["$$#{type}_expanded"] = false
            @_set_config_class(config, type)

        _set_config_line_fields: (config) =>
            config.$$config_line_class = if config.$selected then "info" else ""
            if config.config_catalog of @catalog_lut
                config.$$catalog_name = @catalog_lut[config.config_catalog].name
            else
                config.$$catalog_name = "???"
            # console.log "C", config
            if config.categories.length
                config.$$cat_info_str = "#{config.categories.length}"
            else
                config.$$cat_info_str = "-"
            if config.$hint
                config.$$config_help_text = config.$hint.help_text_short or "no short help"
                config.$$config_help_html = config.$hint.help_text_html or "<p/>"
            else
                config.$$config_help_text = "---"
                config.$$config_help_html = "<span>No help text</span>"

        _enrich_config: (config) =>
            # console.log @cse_lut
            @_set_config_line_fields(config)
            if not config.$selected?
                config.$selected = false
            if config.config_service_enum
                # link to config service enum
                config.$$cse = @cse_lut[config.config_service_enum]
            else
                config.$$cse = null
            if config.config_catalog
                @catalog_lut[config.config_catalog].configs.push(config.idx)
            else
                # hm, config has no catalog ...
                if not config.$$config_error_reported?
                    config.$$config_error_reported = true
                    console.error "*** Config #{config.name} has no valid config_catalog"
            # device config set
            config.$$usecount = config.device_config_set.length
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
            config.$$num_var = config.var_list.length
            config.var_sel = (true for entry in config.var_list when entry.$selected).length
            config.$$num_script = config.config_script_set.length
            config.script_sel = (true for entry in config.config_script_set when entry.$selected).length
            config.$$num_mon = config.mon_check_command_set.length
            config.mon_sel = (true for entry in config.mon_check_command_set when entry.$selected).length
            config.mon_check_command_lut = _.keyBy(config.mon_check_command_set, "idx")
            # build info strings for device-config
            if @_multi_name_dict[config.name] > 1
                _name = "#{config.name} [" + @catalog_lut[config.config_catalog].name + "]"
                # flag, can be used in frontend
                config.$mulitple_names = true
            else
                _name = "#{config.name}"
                config.$mulitple_names = false
            # @_init_expansion_fields(config)
            config.$$info_str = "#{_name} (#{config.$$num_var}, #{config.$$num_script}, #{config.$$num_mon})"
            r_v = []
            if config.server_config
                r_v.push("S")
            if config.$$cse
                r_v.push("R")
            # if config.system_config
            #     r_v.push("Y")
            config.$$config_type_str = r_v.join(", ")

        link: () =>
            # hints
            # add root service info to sce
            for entry in @cse_list
                info_str = entry.name
                if entry.root_service
                    info_str = "#{info_str} (Root service)"
                entry.$$info_str = info_str
            # create links between elements
            # how often a config name is used
            @_multi_name_dict = _.countBy((config.name for config in @list))
            for cat in @catalog_list
                if cat.configs?
                    cat.configs.length = 0
                else
                    cat.configs = []
            for config in @list
                @_enrich_config(config)
            @_populate_filter_fields()
            @$selected = (entry for entry in @list when entry.$selected).length

        # filter functions
        _populate_filter_fields: () =>
            for entry in @list
                entry.$$filter_set = true
                s = []
                for scr in entry.config_script_set
                    _local_s = []
                    for attr_name in ["name", "description", "value"]
                        _local_s.push(scr[attr_name])
                    scr.$$filter_string = _local_s.join(" ")
                    s.push(scr.$$filter_string)
                for vart in ["str", "int", "blob", "bool"]
                    for cvar in entry["config_#{vart}_set"]
                        _local_s = []
                        for attr_name in ["name", "description", "value"]
                            _local_s.push(cvar[attr_name])
                        cvar.$$filter_string = _local_s.join(" ")
                        s.push(cvar.$$filter_string)
                for moncc in entry.mon_check_command_set
                    _local_s = []
                    for attr_name in ["name", "description", "check_command"]
                        _local_s.push(moncc[attr_name])
                    moncc.$$filter_string = _local_s.join(" ")
                    s.push(moncc.$$filter_string)
                # config search field
                _local_s = []
                for attr_name in ["name", "description"]
                    _local_s.push(entry[attr_name])
                entry.$$filter_string = _local_s.join(" ")
                s.push(entry.$$filter_string)
                # needed ?
                entry.$$global_filter_string = s.join(" ")

        update_filtered_list: (search_str, filter_settings) =>
            if not search_str?
                search_str = ""
            # console.log "f", search_str, filter_settings
            try
                search_re = new RegExp(search_str)
            catch error
                search_re = new RegExp("")
            if search_str == ""
                # default for empty search string
                filter_settings = {config: true, mon: false, script: false, var: false}
            @filtered_list.length = 0
            for entry in @list
                if entry.$$filter_set?
                    # search_str defined due some filtering
                    [_num_script_found, _num_mon_found, _num_var_found] = [0, 0, 0]
                    for scr in entry.config_script_set
                        if filter_settings.script
                            scr.$$filter_match = if scr.$$filter_string.match(search_re) then true else false
                            if scr.$$filter_match
                                _num_script_found++
                        else
                            scr.$$filter_match = false
                    for mon in entry.mon_check_command_set
                        if filter_settings.mon
                            mon.$$filter_match = if mon.$$filter_string.match(search_re) then true else false
                            if mon.$$filter_match
                                _num_mon_found++
                        else
                            mon.$$filter_match = false
                    for vart in ["str", "int", "blob", "bool"]
                        for cvar in entry["config_#{vart}_set"]
                            if filter_settings.var
                                cvar.$$filter_match = if cvar.$$filter_string.match(search_re) then true else false
                                if cvar.$$filter_match
                                    _num_var_found++
                            else
                                cvar.$$filter_match = false
                    entry.$$num_script_found = _num_script_found
                    entry.$$num_var_found = _num_var_found
                    entry.$$num_mon_found = _num_mon_found
                    if filter_settings.config
                        entry.$$filter_match = if entry.$$filter_string.match(search_re) then true else false
                    else
                        entry.$$filter_match = false
                    _sub_found = if _num_script_found + _num_var_found + _num_mon_found > 0 then true else false
                    # console.log _sub_found, entry.$$filter_match
                    entry.$$global_filter_match = _sub_found or entry.$$filter_match
                    #if entry.$$global_filter_match
                    #    console.log entry.$$filter_match, _num_script_found, _num_mon_found, _num_var_found
                else
                    entry.$$filter_match = true
                    entry.$$global_filter_match = true
                    entry.$$num_script_found = 0
                    entry.$$num_var_found = 0
                    entry.$$num_mon_found = 0
                for _type in ["script", "mon", "var"]
                    @_set_config_class(entry, _type)
                if entry.$$global_filter_match
                    @filtered_list.push(entry)

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

        modify_config: (config) ->
            defer = $q.defer()
            _modify_url = ICSW_URLS.REST_CONFIG_DETAIL.slice(1).slice(0, -2)
            Restangular.restangularizeElement(null, config, _modify_url)
            config.put().then(
                (saved_config) =>
                    console.log "ok"
                    @build_luts()
                    defer.resolve("saved")
                (not_ok) =>
                    console.log "nok"
                    defer.reject("not saved")
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

        # category functions
        add_category_to_config_by_pk: (conf_idx, cat_idx) =>
            @add_category_to_config(@lut[conf_idx], cat_idx)
            
        add_category_to_config: (conf, cat_idx) =>
            conf.categories.push(cat_idx)

        remove_category_from_config_by_pk: (conf_idx, cat_idx) =>
            @remove_category_from_config(@lut[conf_idx], cat_idx)
            
        remove_category_from_config: (conf, cat_idx) =>
            _.remove(conf.categories, (entry) -> return entry == cat_idx)

        add_category_to_mcc_by_pk: (mcc_idx, cat_idx) =>
            @add_category_to_mcc(@mcc_lut[mcc_idx], cat_idx)
            
        add_category_to_mcc: (mcc, cat_idx) =>
            mcc.categories.push(cat_idx)

        remove_category_from_mcc_by_pk: (mcc_idx, cat_idx) =>
            @remove_category_from_mcc(@mcc_lut[mcc_idx], cat_idx)
            
        remove_category_from_mcc: (mcc, cat_idx) =>
            _.remove(mcc.categories, (entry) -> return entry == cat_idx)

]).service("icswConfigTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "icswCachingCall", "icswTools", "icswConfigTree",
    "$rootScope", "ICSW_SIGNALS", "icswCategoryTreeService", "icswTreeBase",
(
    $q, Restangular, ICSW_URLS, icswCachingCall, icswTools, icswConfigTree,
    $rootScope, ICSW_SIGNALS, icswCategoryTreeService, icswTreeBase,
) ->
    rest_map = [
        ICSW_URLS.REST_CONFIG_LIST,
        ICSW_URLS.REST_CONFIG_SERVICE_ENUM_LIST,
        ICSW_URLS.REST_CONFIG_CATALOG_LIST,
        ICSW_URLS.REST_CONFIG_HINT_LIST,
    ]
    class icswConfigTreeService extends icswTreeBase
        extra_calls: (client) =>
            return [
                icswCategoryTreeService.load(client)
            ]

    return new icswConfigTreeService(
        "icswConfigTree"
        icswConfigTree
        rest_map
        "ICSW_CONFIG_TREE_LOADED"
    )
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
