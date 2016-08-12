# Copyright (C) 2012-2016 init.at
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

    # device tree handling (including device enrichment)

    "icsw.backend.variable",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap",
        "init.csw.filters", "restangular", "noVNC", "ui.select", "icsw.tools",
        "icsw.device.info", "icsw.user",
    ]
).service("icswDeviceVariableScopeTree",
[
    "icswDeviceVariableFunctions", "$q", "Restangular", "ICSW_URLS",
(
    icswDeviceVariableFunctions, $q, Restangular, ICSW_URLS,
) ->
    class icswDeviceVariableScopeTree
        constructor: (list) ->
            @list = []
            @update(list)
            
        update: (list) =>
            @list.length = 0 
            for entry in list
                @salt_scope(entry)
                @list.push(entry)
            @$$fixed_list = (entry for entry in @list when entry.$$fixed)
            @$$num_fixed_scopes =  @$$fixed_list.length
            @build_luts()
            
        build_luts: () =>
            @lut = _.keyBy(@list, "idx")
            @lut_by_name= _.keyBy(@list, "name")
            @_inv_lut = _.keyBy(@lut_by_name["inventory"].dvs_allowed_name_set, "name")

        salt_scope: (entry) =>
            if entry.dvs_allowed_name_set.length
                entry.$$fixed = true
                (@salt_allowed_name(_dve) for _dve in entry.dvs_allowed_name_set)
            else
                entry.$$fixed = false
            
        get_inventory_var_names: () =>
            return _.orderBy(entry.name for entry in @lut_by_name["inventory"].dvs_allowed_name_set)
            
        get_inventory_var: (name) =>
            return @_inv_lut[name]

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
                    defer.reject("variable not created")
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
