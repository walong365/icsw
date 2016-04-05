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

class mc_table
    constructor : (@xml, paginatorSettings) ->
        @name = @xml.prop("tagName")
        @short_name = @name.replace(/_/g, "").replace(/list$/, "")
        @attr_list = new Array()
        @entries = []
        @columns_enabled = {}
        @xml.children().each (idx, entry) =>
            for attr in entry.attributes
                if attr.name not in @attr_list
                    @attr_list.push(attr.name)
                    @columns_enabled[attr.name] = true
            @entries.push(@_to_json($(entry)))
        @pagSettings = paginatorSettings.get_paginator("device_tree_base")
        @order_name = "name"
        @order_dir = true
    toggle_column: (attr) ->
        @columns_enabled[attr] = !@columns_enabled[attr]
    _to_json : (entry) =>
        _ret = new Object()
        for attr_name in @attr_list
            _ret[attr_name] = entry.attr(attr_name)
        return _ret
    toggle_order : (name) =>
        if @order_name == name
            @order_dir = not @order_dir
        else
            @order_name = name
            @order_dir = true
    get_order : () =>
        return (if @order_dir then "" else "-") + @order_name
    get_order_glyph : (name) =>
        if @order_name == name
            if @order_dir
                _class = "glyphicon glyphicon-chevron-down"
            else
                _class = "glyphicon glyphicon-chevron-up"
        else
            _class = "glyphicon"
        return _class


angular.module(
    "icsw.device.monconfig",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular"
    ]
).config(["$stateProvider", ($stateProvider) ->
    $stateProvider.state(
        "main.monitorhint", {
            url: "/monitorhint"
            template: '<icsw-device-mon-config icsw-sel-man="0" icsw-sel-man-sel-mode="d"></icsw-device-mon-config>'
            data:
                pageTitle: "Monitoring hints"
                rights: ["mon_check_command.setup_monitoring"]
                menuEntry:
                    menukey: "mon"
                    icon: "fa-info"
                    ordering: 40
        }
    )
]).controller("icswDeviceMonConfigCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "$q", "$uibModal", "$timeout", "icswAcessLevelService", "ICSW_URLS", "icswSimpleAjaxCall", "toaster",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, $q, $uibModal, $timeout, icswAcessLevelService, ICSW_URLS, icswSimpleAjaxCall, toaster) ->
        icswAcessLevelService.install($scope)
        $scope.hint_edit = new angular_edit_mixin($scope, $templateCache, $compile, Restangular, $q, "nd")
        $scope.hint_edit.edit_template = "monitoring.hint.form"
        $scope.hint_edit.modify_rest_url = ICSW_URLS.REST_MONITORING_HINT_DETAIL.slice(1).slice(0, -2)
        $scope.hint_edit.modify_data_before_put = (hint) ->
            $scope.restore_values(hint, true)
        $scope.hint_edit.new_object_at_tail = false
        $scope.hint_edit.use_promise = true
        $scope.reload_pending = false
        $scope.monconfig_open = true
        $scope.monhint_open = true
        $scope.new_devsel = (_dev_sel) ->
            $scope.devsel_list = _dev_sel
            $scope.load_data("ALWAYS")
        $scope.toggle_order = (name) ->
            if $scope.order_name == name
                $scope.order_dir = not $scope.order_dir
            else
                $scope.order_name = name
                $scope.order_dir = true
        $scope.get_order = () ->
            return (if $scope.order_dir then "" else "-") + $scope.order_name
        $scope.get_order_glyph = (name) ->
            if $scope.order_name == name
                if $scope.order_dir
                    _class = "glyphicon glyphicon-chevron-down"
                else
                    _class = "glyphicon glyphicon-chevron-up"
            else
                _class = "glyphicon glyphicon-chevron-right"
            return _class
        $scope.get_long_attr_name = (name) ->
            return name.replace(/_/g, " ")
        $scope.get_short_attr_name = (name) ->
            _parts = name.split("_")
            return (_str.slice(0, 1) for _str in _parts).join("").toUpperCase()
        $scope.load_data = (mode) ->
            _reset_entries = () ->
                $scope.mc_tables = []
                $scope.reload_pending = false
            if $scope.devsel_list.length == 0
                _reset_entries()
            else
                $scope.reload_pending = true
                icswSimpleAjaxCall(
                    url  : ICSW_URLS.MON_GET_NODE_CONFIG
                    data : {
                        "pk_list" : angular.toJson($scope.devsel_list)
                        "mode"    : mode
                    },
                ).then(
                    (xml) ->
                        mc_tables = []
                        $(xml).find("config > *").each (idx, node) =>
                            new_table = new mc_table($(node), paginatorSettings)
                            mc_tables.push(new_table)
                        $scope.mc_tables = mc_tables
                        restDataSource.reset()
                        wait_list = restDataSource.add_sources([
                            [ICSW_URLS.REST_DEVICE_TREE_LIST, {"with_monitoring_hint" : true, "pks" : angular.toJson($scope.devsel_list), "olp" : "backbone.device.change_monitoring"}],
                        ])
                        $q.all(wait_list).then((data) ->
                            $scope.devices = []
                            $scope.device_lut = {}
                            for entry in data[0]
                                entry.expanded = true
                                $scope.devices.push(entry)
                                $scope.device_lut[entry.idx] = entry
                            $scope.reload_pending = false
                        )
                    (xml) ->
                        _reset_entries()
                )
        $scope.get_tr_class = (obj) ->
            if obj.is_meta_device
                return "success"
            else
                return ""
        $scope.expand_vt = (obj) ->
            obj.expanded = not obj.expanded
        $scope.get_expand_class = (obj) ->
            if obj.expanded
                return "glyphicon glyphicon-chevron-down"
            else
                return "glyphicon glyphicon-chevron-right"
        $scope.remove_hint = (hint) ->
            _.remove($scope.device_lut[hint.device].monitoring_hint_set, (entry) -> return entry.idx == hint.idx)
            icswSimpleAjaxCall(
                url     :ICSW_URLS.MON_DELETE_HINT
                data    :
                    hint_pk : hint.idx
            ).then((xml) ->
                toaster.pop("success", "", "removed hint")
            )
        $scope.save_hint = (hint) ->
            Restangular.restangularizeElement(null, hint, ICSW_URLS.REST_MONITORING_HINT_DETAIL.slice(1).slice(0, -2))
            hint.put()
        $scope.backup_values = (hint) ->
            if hint.v_type == "f"
                v_name = "float"
            else
                v_name = "int"
            for _a in ["lower", "upper"]
                for _b in ["crit", "warn"]
                    _var = "#{_a}_#{_b}_#{v_name}"
                    hint["#{_var}_saved"] = hint[_var]
                    hint["#{_var}_source_saved"] = hint["#{_var}_source"]
                    hint["#{_var}_source"] = "u"
        $scope.restore_values = (hint, intl) ->
            if hint.v_type == "f"
                v_name = "float"
            else
                v_name = "int"
            for _a in ["lower", "upper"]
                for _b in ["crit", "warn"]
                    _var = "#{_a}_#{_b}_#{v_name}"
                    if intl
                        if hint["#{_var}"] == hint["#{_var}_saved"]
                            hint["#{_var}"] = hint["#{_var}_saved"]
                            hint["#{_var}_source"] = hint["#{_var}_source_saved"]
                    else
                        hint["#{_var}"] = hint["#{_var}_saved"]
                        hint["#{_var}_source"] = hint["#{_var}_source_saved"]
        $scope.show_modify = (hint) ->
            return if hint.v_type in ["B"] then false else true
        $scope.modify_hint = (hint, event) ->
            event.stopPropagation()
            $scope.backup_values(hint)
            $scope.hint_edit.edit(hint, event).then(
                (mod_hint) ->
                    if mod_hint == false
                        $scope.restore_values(hint, false)
            )
        $scope.$on("$destroy", () ->
            #if $scope.cur_timeout?
            #    $timeout.cancel($scope.cur_timeout)
        )
]).directive("icswDeviceMonConfig", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.livestatus.monconfig")
        controller: "icswDeviceMonConfigCtrl"
    }
]).directive("mhdevrow", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.livestatus.device.row")
    }
]).directive("mhrow", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.livestatus.hint.row")
        link : (scope) ->
            scope.get_v_type = () ->
                return {"f" : "float", "i" : "int", "s" : "string", "B": "blob"}[scope.hint.v_type]
            scope.get_value = () ->
                if scope.hint.v_type == "B"
                    return scope.hint.value_blob.length + " bytes"
                else
                    return scope.hint["value_" + scope.get_v_type()]
            scope.from_now = (dt) ->
                return moment(dt).fromNow(true)
            scope.get_td_title = (name) ->
                v_type = scope.get_v_type()
                key = "#{name}_#{v_type}"
                skey = "#{key}_source"
                if scope.hint[skey] == "n"
                    return "not set"
                else if scope.hint[skey] == "s"
                    return "set by system"
                else if scope.hint[skey] == "u"
                    return "set by user"
                else
                    return "unknown source '#{scope.hint[skey]}'"
            scope.get_td_class = (name) ->
                v_type = scope.get_v_type()
                key = "#{name}_#{v_type}"
                skey = "#{key}_source"
                if scope.hint[skey] == "n"
                    return ""
                else if scope.hint[skey] == "s"
                    return "warning"
                else if scope.hint[skey] == "u"
                    return "success"
            scope.get_limit = (name) ->
                v_type = scope.get_v_type()
                key = "#{name}_#{v_type}"
                skey = "#{key}_source"
                if scope.hint[skey] == "s" or scope.hint[skey] == "u"
                    return scope.hint[key]
                else
                    return "---"
            scope.toggle_enabled = (hint, $event) ->
                $event.stopPropagation()
                hint.enabled = !hint.enabled
                scope.save_hint(hint)
    }
]).service('icswDeviceMonConfigTableService', ["ICSW_URLS", (ICSW_URLS) ->
    return {
        delete_confirm_str : (obj) ->
            return "Really delete hint '#{obj.m_type} / #{obj.key}' ?"
        delete: (scope, obj) ->
            scope.remove_hint(obj)
        many_delete: true
        edit_template      : "network.device.type.form"
    }
]).directive("monitoringhinttable", ["$templateCache", "$compile", "$uibModal", "Restangular", ($templateCache, $compile, $uibModal, Restangular) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.livestatus.hint.table")
        link : (scope) ->
    }
])
