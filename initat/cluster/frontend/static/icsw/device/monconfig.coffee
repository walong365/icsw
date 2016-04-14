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
]).service("icswMonConfigTable",
[
    "$q",
(
    $q,
) ->

    # simple container for monitoring config(s)
        
    class icswMonConfigTable
        constructor : (@xml) ->
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

        toggle_column: (attr) ->
            @columns_enabled[attr] = !@columns_enabled[attr]

        _to_json : (entry) =>
            _ret = new Object()
            for attr_name in @attr_list
                _ret[attr_name] = entry.attr(attr_name)
            return _ret

]).controller("icswDeviceMonConfigCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular", "$q", "$uibModal",
    "$timeout", "icswAcessLevelService", "ICSW_URLS",
    "icswSimpleAjaxCall", "toaster", "icswDeviceTreeService", "icswMonConfigTable",
    "icswDeviceTreeHelperService",
(
    $scope, $compile, $filter, $templateCache, Restangular, $q, $uibModal,
    $timeout, icswAcessLevelService, ICSW_URLS,
    icswSimpleAjaxCall, toaster, icswDeviceTreeService, icswMonConfigTable,
    icswDeviceTreeHelperService,
) ->
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

    $scope.struct = {
        # loading flag (devices)
        loading: false
        # loading flag (monconfig)
        fetching: false
        # devices
        devices: []
        # device tree
        device_tree: undefined
        # config accordion
        monconfig_open: true
        # hint accordion
        monhint_open: true
        # monconfig tables
        mc_tables: []
    }

    fetch_mon_config = (mode) ->
        $scope.struct.fetching = true
        icswSimpleAjaxCall(
            url: ICSW_URLS.MON_GET_NODE_CONFIG
            data: {
                pk_list: angular.toJson((dev.idx for dev in $scope.struct.devices))
                mode: mode
            },
        ).then(
            (xml) ->
                $scope.struct.mc_tables.length = 0
                $(xml).find("config > *").each (idx, node) =>
                    new_table = new icswMonConfigTable($(node))
                    $scope.struct.mc_tables.push(new_table)
                # now (re)-enrich the devices
                hs = icswDeviceTreeHelperService.create($scope.struct.device_tree, $scope.struct.devices)
                $scope.struct.device_tree.enrich_devices(hs, ["monitoring_hint_info"], force=true).then(
                    (done) ->
                        console.log "done"
                        $scope.struct.fetching = false
                )
            (error) ->
                $scope.struct.mc_tables.length = 0
                $scope.struct.fetching = false
        )
    $scope.new_devsel = (_dev_sel) ->
        console.log "DS", _dev_sel
        $scope.struct.loading = true
        $scope.struct.mc_tables.length = 0
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.devices.length = 0
                for _dev in _dev_sel
                    if not _dev.is_meta_device
                        $scope.struct.devices.push(_dev)
                        if not _dev.$$hints_expanded?
                            _dev.$$hints_expanded = false
                $scope.struct.device_tree = data[0]
                $scope.struct.loading = false
                fetch_mon_config("ALWAYS")
        )

    $scope.get_long_attr_name = (name) ->
        return name.replace(/_/g, " ")
    $scope.get_short_attr_name = (name) ->
        _parts = name.split("_")
        return (_str.slice(0, 1) for _str in _parts).join("").toUpperCase()
    $scope.load_data = (mode) ->
        _reset_entries = () ->
            $scope.mc_tables = []
            $scope.reload_pending = false

    $scope.get_tr_class = (obj) ->
        if obj.is_meta_device
            return "success"
        else
            return ""

    $scope.expand_vt = (device) ->
        device.$$hints_expanded = not device.$$hints_expanded

    $scope.get_expand_class = (device) ->
        if device.$$hints_expanded
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
]).directive("icswDeviceMonConfig",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.livestatus.monconfig")
        controller: "icswDeviceMonConfigCtrl"
    }
]).directive("icswMonitoringHintDeviceRow",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.monitoring.hint.device.row")
    }
]).directive("icswMonitoringHintRow",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.monitoring.hint.row")
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
]).directive("icswMonitoringHintTable",
[
    "$templateCache", "$compile", "$uibModal", "Restangular",
(
    $templateCache, $compile, $uibModal, Restangular
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.monitoring.hint.table")
        scope: {
            device: "=icswDevice"
        }
        link : (scope, element, attrs) ->
            _salt_hints = () ->
                for entry in scope.device.monitoring_hint_set
                    console.log "hint=", entry
            console.log "dev=", scope.device
            _salt_hints()
    }
])
