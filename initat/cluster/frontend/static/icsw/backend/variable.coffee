# Copyright (C) 2012-2016 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
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

angular.module(

    # device tree handling (including device enrichment)

    "icsw.backend.variable",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap",
        "init.csw.filters", "restangular", "noVNC", "ui.select", "icsw.tools",
        "icsw.device.info", "icsw.user",
    ]
).service("icswDeviceFixedVariableHelper",
[
    "$q",
(
    $q,
) ->
    class icswDeviceFixedVariableHelper
        constructor: (dvs_tree, device) ->
            @dvs_tree = dvs_tree
            @device = device
            @init()

        init: () =>
            @scope_structs = []
            @scope_struct_lut = {}
            @update()

        update: () =>
            @num_total_vars = 0
            @num_used_vars = 0
            _inv_var_lut = {}
            _fixed_scope_idxs = (entry.idx for entry in @dvs_tree.$$fixed_list)
            for _var in @device.device_variable_set
                if _var.device_variable_scope in _fixed_scope_idxs
                    _inv_var_lut[_var.name] = _var
            # create inventory_vars struct
            for _fixed_scope in @dvs_tree.$$fixed_list
                _local_list = []
                for entry in _fixed_scope.dvs_allowed_name_set
                    # get dev var
                    _struct = {
                        def: entry
                    }
                    if entry.name of _inv_var_lut
                        _struct.set = true
                        _struct.var = _inv_var_lut[entry.name]
                    else
                        _struct.set = false
                        _struct.var = null
                    _local_list.push(_struct)
                @add_fixed_scope(_fixed_scope, _local_list)

        add_fixed_scope: (scope, local_list) =>
            total_local = local_list.length
            local_set = (entry for entry in local_list when entry.set).length
            # check for existing
            if scope.idx of @scope_struct_lut
                _struct = @scope_struct_lut[scope.idx]
                _struct.list.length = 0
                for _entry in local_list
                    _struct.list.push(_entry)
            else
                _struct = {
                    scope: scope
                    list: local_list
                }
                @scope_structs.push(_struct)
                @scope_struct_lut[scope.idx] = _struct
            _struct.num_total = total_local
            _struct.num_set = local_set
            @num_total_vars += total_local
            @num_used_vars += local_set


]).service("icswDeviceVariableScopeTree",
[
    "icswDeviceVariableFunctions", "$q", "Restangular", "ICSW_URLS", "icswTools",
    "icswDeviceFixedVariableHelper",
(
    icswDeviceVariableFunctions, $q, Restangular, ICSW_URLS, icswTools,
    icswDeviceFixedVariableHelper,
) ->
    class icswDeviceVariableScopeTree
        constructor: (list) ->
            @list = []
            @update(list)
            
        update: (list) =>
            @list.length = 0 
            for entry in list
                @list.push(entry)
            @build_luts()
            
        build_luts: () =>
            (@salt_scope(entry) for entry in @list)
            icswTools.order_in_place(@list, ["priority"], ["desc"])
            @$$fixed_list = (entry for entry in @list when entry.fixed)
            @$$num_fixed_scopes =  @$$fixed_list.length
            # info strings
            @$$all_info_str = (entry.$$info_str for entry in @list).join("<br/>")
            @$$fixed_info_str = (entry.$$info_str for entry in @$$fixed_list).join("<br/>")
            @lut = _.keyBy(@list, "idx")
            @lut_by_name= _.keyBy(@list, "name")

        salt_scope: (entry) =>
            if entry.fixed
                (@salt_allowed_name(_dve) for _dve in entry.dvs_allowed_name_set)
                icswTools.order_in_place(entry.dvs_allowed_name_set, ["name"], ["asc"])
            _info = entry.name
            _info_f = []
            if entry.fixed
                _info_f.push("fixed")
            if entry.system_scope
                _info_f.push("system")
            if entry.description
                _info_f.push(entry.description)
            if _info_f.length
                _info = "#{_info} (#{_info_f.join(', ')})"
            entry.$$info_str = _info

        # return a new device_fixed_variable_helper
        build_fixed_variable_helper: (device) =>
            fvh = new icswDeviceFixedVariableHelper(@, device)
            return fvh

        salt_allowed_name: (entry) =>
            entry.$$forced_type_str = icswDeviceVariableFunctions.resolve("var_type", entry.forced_type)

        delete_dvs_an: (entry) =>
            defer = $q.defer()
            _scope = @lut[entry.device_variable_scope]
            Restangular.restangularizeElement(null, entry, ICSW_URLS.DEVICE_DEVICE_VARIABLE_SCOPE_ENTRY_DETAIL.slice(1).slice(0, -2))
            entry.remove().then(
                (ok) ->
                    _.remove(_scope.dvs_allowed_name_set, (_entry) => return _entry.idx == entry.idx)
                    defer.resolve("ok")
                (notok) ->
                    defer.resolve("not ok")
            )
            return defer.promise

        create_variable_scope: (var_scope) =>
            defer = $q.defer()
            Restangular.all(ICSW_URLS.DEVICE_DEVICE_VARIABLE_SCOPE_LIST.slice(1)).post(var_scope).then(
                (new_obj) =>
                    @list.push(new_obj)
                    @build_luts()
                    defer.resolve("created")
                (not_ok) ->
                    defer.reject("variable scope not created")
            )
            return defer.promise

        update_variable_scope: (var_scope) =>
            defer = $q.defer()
            Restangular.restangularizeElement(null, var_scope, ICSW_URLS.DEVICE_DEVICE_VARIABLE_SCOPE_DETAIL.slice(1).slice(0, -2))
            var_scope.put().then(
                (new_obj) =>
                    _.remove(@list, (_vs) => return _vs.idx == var_scope.idx)
                    @list.push(new_obj)
                    @build_luts()
                    defer.resolve("created")
                (not_ok) ->
                    defer.reject("variable scope not updated")
            )
            return defer.promise

        create_dvs_an: (var_scope, entry) =>
            defer = $q.defer()
            Restangular.all(ICSW_URLS.DEVICE_DEVICE_VARIABLE_SCOPE_ENTRY_LIST.slice(1)).post(entry).then(
                (new_obj) =>
                    var_scope.dvs_allowed_name_set.push(new_obj)
                    @salt_scope(var_scope)
                    defer.resolve("created")
                (not_ok) ->
                    defer.reject("variable not created")
            )
            return defer.promise

        update_dvs_an: (var_scope, entry) =>
            defer = $q.defer()
            Restangular.restangularizeElement(null, entry, ICSW_URLS.DEVICE_DEVICE_VARIABLE_SCOPE_ENTRY_DETAIL.slice(1).slice(0, -2))
            entry.put().then(
                (new_obj) =>
                    _.remove(var_scope.dvs_allowed_name_set, (_dvs) => return _dvs.idx == entry.idx)
                    var_scope.dvs_allowed_name_set.push(new_obj)
                    @salt_scope(var_scope)
                    defer.resolve("created")
                (not_ok) ->
                    defer.reject("variable not updated")
            )
            return defer.promise

]).service("icswDeviceVariableFunctions",
[
    "$q",
(
    $q,
) ->
    info_dict = {
        var_type: [
            ["", "ignore", ""]
            ["i", "Integer", ""]
            ["s", "String", ""]
            ["d", "DateTime", ""]
            ["D", "Date", ""]
            ["t", "Time", ""]
            ["b", "Blob", ""]
        ]
    }
    # list of dicts for forms
    form_dict = {}
    # create forward and backward resolves
    res_dict = {}
    for name, _list of info_dict
        res_dict[name] = {}
        form_dict[name] = []
        for [_idx, _str, _class] in _list
            # forward resolve
            res_dict[name][_idx] = [_str, _class]
            # backward resolve
            res_dict[name][_str] = [_idx, _class]
            res_dict[name][_.lowerCase(_str)] = [_idx, _class]
            # form dict
            form_dict[name].push({idx: _idx, name: _str})

    _resolve = (name, key, idx) ->
        if name of res_dict
            if key of res_dict[name]
                return res_dict[name][key][idx]
            else
                console.error "unknown key #{key} for name #{name} in resolve"
                return "???"
        else
            console.error "unknown name #{name} in resolve"
            return "????"

    return {
        resolve: (name, key) ->
            return _resolve(name, key, 0)

        get_class: (name, key) ->
            return _resolve(name, key, 1)

        get_form_dict: (name) ->
            return form_dict[name]
    }

]).service("icswDeviceVariableScopeTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "icswCachingCall", "icswTreeBase",
    "icswTools", "icswDeviceVariableScopeTree", "$rootScope", "ICSW_SIGNALS",
(
    $q, Restangular, ICSW_URLS, icswCachingCall, icswTreeBase,
    icswTools, icswDeviceVariableScopeTree, $rootScope, ICSW_SIGNALS,
) ->
    rest_map = [
        ICSW_URLS.DEVICE_DEVICE_VARIABLE_SCOPE_LIST
    ]
    return new icswTreeBase(
        "DeviceVariableScopeTree"
        icswDeviceVariableScopeTree
        rest_map
        ""
    )
])
