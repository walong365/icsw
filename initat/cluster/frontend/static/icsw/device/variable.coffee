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
device_variable_module = angular.module(
    "icsw.device.variables",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select"
    ]
).directive("icswDeviceVariableHead", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.variable.head")
    }
]).service("icswDeviceVariableRestService", ["$q", "Restangular", "icswCachingCall", "ICSW_URLS", "icswTools", ($q, Restangular, icswCachingCall, ICSW_URLS, icswTools) ->
    vstruct = {}
    _data_loaded = false
    _load_in_progress = false
    fetch_waiters = []
    # fingerprint of loaded pks
    _loaded_pks = "*"
    filter_string = ""
    filter_re = undefined
    hide_empty = false
    pk_fingerprint = (pks) ->
        return (val.toString() for val in pks).join(":")
    salt_data = (entries, pks) ->
        # all entries (including parent meta devices and CDG)
        vstruct.cdg = (entry for entry in entries when entry.is_cluster_device_group)[0]
        vstruct.deep_entries = icswTools.build_lut(entries)
        vstruct.group_dev_lut = {}
        for entry in entries
            if entry.is_meta_device
                vstruct.group_dev_lut[entry.device_group] = entry.idx
        _entries = (entry for entry in entries when entry.idx in pks)
        for entry in _entries
            entry.expanded = false
        if vstruct.entries_unfiltered
            vstruct.entries_unfiltered.length = 0
            for entry in _entries
                vstruct.entries_unfiltered.push(entry)
            vstruct.entries.length = 0
        else
            vstruct.entries_unfiltered = _entries
            vstruct.entries = []
        filter_data(false)
        return vstruct
    filter_data = (change_expand_state) ->
        # check all devs
        for entry in vstruct.entries_unfiltered
            if filter_string
                entry.num_filtered = (true for _var in entry.device_variable_set when _var.name.match(filter_re)).length
                entry.filter_active = true
            else
                entry.num_filtered = entry.device_variable_set.length
                entry.filter_active = false
            if change_expand_state
                if entry.num_filtered and filter_string
                    entry.expanded = true
                else
                    entry.expanded = false
        # check for hide_empty flag
        vstruct.entries.length = 0
        # always keep first entry
        first = true
        for entry in vstruct.entries_unfiltered
            if entry.num_filtered or not hide_empty or first
                vstruct.entries.push(entry)
            first = false

    fetch_data = (client) ->
        _defer = $q.defer()
        if _data_loaded and not _load_in_progress
            _defer.resolve(vstruct)
        else
            fetch_waiters.push(_defer)
        return _defer
    load_data = (client, pks) ->
        _defer = $q.defer()
        if _data_loaded and pk_fingerprint(pks) == _loaded_pks
            _defer.resolve(vstruct)
        else
            _load_in_progress = true
            _wait_list = [
                icswCachingCall.fetch(
                    client
                    ICSW_URLS.REST_DEVICE_TREE_LIST
                    {
                        "pks" : angular.toJson(pks)
                        "with_variables" : true
                        "with_meta_devices" : true
                        "ignore_cdg" : false
                        "olp" : "backbone.device.change_variables"
                    }
                    []
                )
            ]
            $q.all(_wait_list).then((data) ->
                salt_data(data[0], pks)
                _defer.resolve(vstruct)
                _data_loaded = true
                _loaded_pks = pk_fingerprint(_.sortBy(pks))
                _load_in_progress = false
                (entry.resolve(vstruct) for entry in fetch_waiters)
                fetch_waiters = []
            )
        return _defer
    create_variable = (new_obj) ->
        _defer = $q.defer()
        Restangular.all(ICSW_URLS.REST_DEVICE_VARIABLE_LIST.slice(1)).post(new_obj).then(
            (new_obj) ->
                vstruct.deep_entries[new_obj.device].device_variable_set.push(new_obj)
                _defer.resolve(new_obj)
            (error) ->
                _defer.reject("")
        )
        return _defer
    create_many_variables = (new_obj, pks) ->
        _defer = $q.defer()
        _wait_list = []
        for _pk in pks
            new_var = angular.copy(new_obj)
            new_var.device = _pk
            _wait_list.push(Restangular.all(ICSW_URLS.REST_DEVICE_VARIABLE_LIST.slice(1)).post(new_var))
        $q.allSettled(_wait_list).then(
            (result) ->
                rv = {"ok": 0, "error": 0}
                for ret_val in result
                    if ret_val.state == "fulfilled"
                        new_val = ret_val.value
                        vstruct.deep_entries[new_val.device].device_variable_set.push(new_val)
                        rv.ok++
                    else
                        rv.error++
                _defer.resolve(rv)
        )
        return _defer
    set_filter_string = (new_filter, change_expand_state) ->
        try
            filter_re = new RegExp(new_filter, "gi")
            filter_string = new_filter
        catch exc
            filter_re = new RegExp("^$", "gi")
            filter_string = ""
        filter_data(change_expand_state)
    delete_variable = (dvar) ->
        dev = vstruct.deep_entries[dvar.device]
        dev.device_variable_set = (entry for entry in dev.device_variable_set when entry.idx != dvar.idx)
        Restangular.restangularizeElement(null, dvar, ICSW_URLS.REST_DEVICE_VARIABLE_DETAIL.slice(1).slice(0, -2))
        dvar.remove().then((del) ->
        )
        filter_data(false)
    set_hidden_flag = (flag) ->
        hide_empty = flag
        if vstruct.entries?
            filter_data(false)
    return {
        # load data, when pks have changed reload data
        "load": (client, pks) ->
            return load_data(client, pks).promise
        # return loaded data, wait for load when load is in progress
        "fetch": (client) ->
            return fetch_data(client).promise
        "create_variable": (new_obj) ->
            return create_variable(new_obj).promise
        "create_many_variables": (new_var, pks) ->
            return create_many_variables(new_var, pks).promise
        "set_filter_string": (new_fs, change_expand_state) ->
            set_filter_string(new_fs, change_expand_state)
        "delete_variable": (dvar) ->
            return delete_variable(dvar)
        "filter_vars": (vars) ->
            if filter_string
                return (entry for entry in vars when entry.name.match(filter_re))
            else
                return vars
        "set_hidden_flag": (flag) ->
            set_hidden_flag(flag)
    }

]).service("icswDeviceVariableListService", ["$q", "Restangular", "icswCachingCall", "icswDeviceVariableRestService", "icswSimpleAjaxCall", "ICSW_URLS", ($q, Restangular, icswCachingCall, icswDeviceVariableRestService, icswSimpleAjaxCall, ICSW_URLS) ->
    load_vars = (pks) ->
        lines = $q.defer()
        icswDeviceVariableRestService.load("vars", pks).then((data) ->
            lines.resolve(data.entries)
        )
        return lines.promise
    set_hide_empty = (flag) ->
        icswDeviceVariableRestService.set_hidden_flag(flag)
    _scope = undefined
    _dev_pks = []
    set_pks = (pks) ->
        _dev_pks = pks
        icswDeviceVariableRestService.load("vars", pks).then((data) ->
        )
    return {
        "load_promise": () ->
            return load_vars(_dev_pks)
        "set_pks": (pks) ->
            return set_pks(pks)
        "set_hide_empty": (flag) ->
            set_hide_empty(flag)
        "init_fn": (scope) ->
            _scope = scope
            scope.take_mon_var = () ->
                if scope.edit_obj._mon_copy
                    _mon_var = (entry for entry in scope.mon_vars when entry.idx == scope.edit_obj._mon_copy)[0]
                    scope.edit_obj.var_type = _mon_var.type
                    scope.edit_obj.name = _mon_var.name
                    scope.edit_obj.inherit = false
                    if _mon_var.type == "i"
                        scope.edit_obj.val_int = parseInt(_mon_var.value)
                    else
                        scope.edit_obj.val_str = _mon_var.value
        create_template: "device.variable.new.form"
        edit_template: "device.variable.new.form"
        delete_confirm_str: (dvar) ->
            return "Really delete variable #{dvar.name} ?"
        delete: (scope, dvar) ->
            icswDeviceVariableRestService.delete_variable(dvar)
        new_object: (device) ->
            _scope.mon_vars = []
            nv_idx = 0
            if device?
                icswSimpleAjaxCall(
                    url : ICSW_URLS.MON_GET_MON_VARS
                    data : {
                        device_pk : device.idx
                    }
                    dataType : "json"
                ).then((json) ->
                    _scope.mon_vars = json
                )
                while true
                    var_name = if nv_idx then "new variable #{nv_idx}" else "new variable"
                    if (true for entry in device.device_variable_set when entry.name == var_name).length == 0
                        break
                    nv_idx++
            else
                var_name = "new variable"
            return {
                "device": if device? then device.idx else 0
                "name": var_name
                "var_type": "s"
                "_mon_copy": 0
                "inherit": true
            }
        save_defer: (new_obj) ->
            return icswDeviceVariableRestService.create_variable(new_obj)
        get_pks: () ->
            return _dev_pks
    }
]).directive("icswDeviceVariableRow", ["$templateCache", "icswDeviceVariableRestService", ($templateCache, icswDeviceVariableRestService) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.variable.row")
        link : (scope) ->
            scope.vstruct = undefined
            icswDeviceVariableRestService.fetch().then((vstruct) ->
                scope.vstruct = vstruct
            )
            scope.num_parent_vars = (obj) ->
                if scope.vstruct
                    my_names = (entry.name for entry in obj.device_variable_set)
                    num_meta = 0
                    if not obj.is_cluster_device_group
                        if not obj.is_meta_device
                            meta_server = scope.vstruct.deep_entries[scope.vstruct.group_dev_lut[obj.device_group]]
                            meta_names = (entry.name for entry in meta_server.device_variable_set when entry.inherit)
                            num_meta += (entry for entry in meta_names when entry not in my_names).length
                        else
                            meta_names = []
                        num_meta += (entry for entry in scope.vstruct.cdg.device_variable_set when entry.name not in my_names and entry.name not in meta_names and entry.inherit).length
                    return num_meta
                else
                    return 0
            scope.num_vars = (obj) ->
                return scope.num_parent_vars(obj) + obj.device_variable_set.length
            scope.parent_vars_defined = (obj) ->
                return if scope.num_parent_vars(obj) then true else false
            scope.num_shadowed_vars = (obj) ->
                if scope.vstruct
                    my_names = (entry.name for entry in obj.device_variable_set)
                    num_shadow = 0
                    if not obj.is_cluster_device_group
                        if not obj.is_meta_device
                            meta_server = scope.vstruct.deep_entries[scope.vstruct.group_dev_lut[obj.device_group]]
                            meta_names = (entry.name for entry in meta_server.device_variable_set)
                            num_shadow += (entry for entry in meta_names when entry in my_names).length
                        else
                            meta_names = []
                        num_shadow += (entry for entry in scope.vstruct.cdg.device_variable_set when entry.name in my_names and entry.name not in meta_names).length
                    return num_shadow
                else
                    return 0
            scope.any_shadowed_vars = (obj) ->
                return if scope.num_shadowed_vars(obj) then true else false
    }
]).filter("filter_dv_name",  ["icswDeviceVariableRestService", (icswDeviceVariableRestService) ->
    return (arr) ->
        return icswDeviceVariableRestService.filter_vars(arr)
]).directive("icswDeviceVariableTable", ["$templateCache", "$compile", "$q", "Restangular", "ICSW_URLS", "icswDeviceVariableRestService", ($templateCache, $compile, $q, Restangular, ICSW_URLS, icswDeviceVariableRestService) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.variable.table")
        link : (scope, el, attrs) ->
            scope.vstruct = undefined
            icswDeviceVariableRestService.fetch().then((vstruct) ->
                scope.vstruct = vstruct
            )
            scope.device = scope.$eval(attrs["device"])
            # scope.$watch(attrs.filtervalue, (new_val) ->
            #     scope.filtervalue = new_val
            # )
            scope.get_value = (obj) ->
                if obj.var_type == "s"
                    return obj.val_str
                else if obj.var_type == "i"
                    return obj.val_int
                else if obj.var_type == "b"
                    return obj.val_blob.length + " bytes"
                else if obj.var_type == "t"
                    return obj.val_time
                else if obj.var_type == "d"
                    return moment(obj.val_date).format("dd, D. MMM YYYY HH:mm:ss")
                else
                    return "unknown type #{obj.var_type}"
            scope.get_var_type = (obj) ->
                if obj.var_type == "s"
                    return "string"
                else if obj.var_type == "i"
                    return "integer"
                else if obj.var_type == "b"
                    return "blob"
                else if obj.var_type == "t"
                    return "time"
                else if obj.var_type == "d"
                    return "datetime"
                else
                    return obj.var_type
            scope.get_parent_vars = (obj, src) ->
                if scope.vstruct
                    my_names = (entry.name for entry in obj.device_variable_set)
                    parents = []
                    if not obj.is_cluster_device_group
                        if not obj.is_meta_device and src == "g"
                            # device, inherited from group
                            meta_group = scope.vstruct.deep_entries[scope.vstruct.group_dev_lut[obj.device_group]]
                            parents = (entry for entry in meta_group.device_variable_set when entry.inherit)
                        else if src == "c"
                            if obj.is_meta_device
                                # group, inherited from cluster
                                parents = (entry for entry in scope.vstruct.cdg.device_variable_set when entry.inherit)
                            else
                                # device, inherited from cluster
                                meta_group = scope.vstruct.deep_entries[scope.vstruct.group_dev_lut[obj.device_group]]
                                meta_names = (_entry.name for _entry in meta_group.device_variable_set)
                                parents = (entry for entry in scope.vstruct.cdg.device_variable_set when entry.name not in meta_names and entry.inherit)
                        parents = (entry for entry in parents when entry.name not in my_names)
                    return parents
                else
                    return []
            scope.local_copy = (d_var, src) ->
                new_var = angular.copy(d_var)
                new_var.device = scope.obj.idx
                Restangular.all(ICSW_URLS.REST_DEVICE_VARIABLE_LIST.slice(1)).post(new_var).then((data) ->
                    scope.obj.device_variable_set.push(data)
                )
    }
]).controller("icswDeviceVariableCtrl", ["$scope", "$compile", "$filter", "$templateCache", "$q", "$modal", "blockUI", "icswTools", "icswDeviceVariableListService", "icswDeviceVariableRestService",
    ($scope, $compile, $filter, $templateCache, $q, $modal, blockUI, icswTools, icswDeviceVariableListService, icswDeviceVariableRestService) ->
        $scope.vars = {
            name_filter: ""
            hide_empty: false
        }
        $scope.entries = []
        $scope.vstruct = {}
        $scope.dataLoaded = false
        $scope.valid_var_types = [
            {"short" : "i", "long" : "integer"},
            {"short" : "s", "long" : "string"},
        ]
        $scope.$watch(
            () ->
                return $scope.vars.hide_empty
            (new_val) ->
                icswDeviceVariableListService.set_hide_empty(new_val)
        )
        $scope.new_devsel = (dev_pks, group_pks) ->
            icswDeviceVariableListService.set_pks(dev_pks)
            $scope.entries = dev_pks
            icswDeviceVariableRestService.load("ctrl", dev_pks).then((vstruct) ->
                $scope.entries = vstruct.entries
                $scope.vstruct = vstruct
                $scope.dataLoaded = true
            )
        $scope.get_tr_class = (obj) ->
            if obj.is_cluster_device_group
                return "danger"
            else if obj.is_meta_device
                return "success"
            else
                return ""
        $scope.get_name = (obj) ->
            if obj.is_meta_device
                if obj.is_cluster_device_group
                    return obj.full_name.slice(8) + " [ClusterGroup]"
                else
                    return obj.full_name.slice(8) + " [Group]"
            else
                return obj.full_name
        $scope.expand_vt = (obj) ->
            obj.expanded = not obj.expanded
        $scope.get_expand_class = (obj) ->
            if obj.expanded
                return "glyphicon glyphicon-chevron-down"
            else
                return "glyphicon glyphicon-chevron-right"
        $scope.new_filter_set = (change_expand_state) ->
            ces = change_expand_state?
            icswDeviceVariableRestService.set_filter_string($scope.vars.name_filter, ces)
        $scope.create_for_all = (event) ->
            new_obj = icswDeviceVariableListService.new_object()
            # copy to scope, fixme
            $scope.edit_obj = new_obj
            $scope.form = {}
            $scope.action_string = "create for all"
            cv_mixin = new angular_modal_mixin($scope, $templateCache, $compile, $q, "New variable for selected devices")
            cv_mixin.cssClass = "modal-tall"
            cv_mixin.template = "device.variable.new.form"
            $scope.cv_mixin = cv_mixin
            cv_mixin.edit(new_obj).then((new_var) ->
                blockUI.start()
                icswDeviceVariableRestService.create_many_variables(new_var, icswDeviceVariableListService.get_pks()).then((result) ->
                    blockUI.stop()
                    cv_mixin.close_modal()
                )
            )
        $scope.modify = () ->
            # hack, redirect to
            $scope.cv_mixin.modify()
        $scope.$on("icsw.dv.changed", (args) ->
            # trigger redisplay of vars
            $scope.new_filter_set($scope.var_filter, false)
        )
]).directive("icswDeviceVariableOverview", ["$templateCache", "msgbus", ($templateCache, msgbus) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.variable.overview")
        controller: "icswDeviceVariableCtrl"
    }
])
