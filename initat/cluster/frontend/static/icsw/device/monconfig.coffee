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
            icswData:
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
            @attr_dict = {}
            @entries = []
            @columns_enabled = {}
            @xml.children().each (idx, entry) =>
                for attr in entry.attributes
                    if attr.name not in @attr_list
                        @add_attr_name(attr.name)
                @entries.push(@_to_json($(entry)))

        add_attr_name: (name) ->
            @attr_list.push(name)
            _parts = name.split("_")
            @attr_dict[name] = {
                long: name.replace(/_/g, " ")
                short: (_str.slice(0, 1) for _str in _parts).join("").toUpperCase()
            }
            @columns_enabled[name] = true

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
    "$timeout", "icswAcessLevelService", "ICSW_URLS", "blockUI",
    "icswSimpleAjaxCall", "toaster", "icswDeviceTreeService", "icswMonConfigTable",
    "icswDeviceTreeHelperService", "icswToolsSimpleModalService",
(
    $scope, $compile, $filter, $templateCache, Restangular, $q, $uibModal,
    $timeout, icswAcessLevelService, ICSW_URLS, blockUI,
    icswSimpleAjaxCall, toaster, icswDeviceTreeService, icswMonConfigTable,
    icswDeviceTreeHelperService, icswToolsSimpleModalService,
) ->

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
        # console.log "DS", _dev_sel
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


    $scope.load_data = (mode) ->
        fetch_mon_config(mode)

    $scope.get_tr_class = (obj) ->
        if obj.is_meta_device
            return "success"
        else
            return ""

    $scope.expand_vt = (device) ->
        device.$$hints_expanded = not device.$$hints_expanded

    $scope.delete_multiple_hints = ($event, device) ->
        _to_del = (entry for entry in device.monitoring_hint_set when entry.isSelected)
        if _to_del.length
            icswToolsSimpleModalService("Really delete #{_to_del.length} hints ?").then(
                (ok) ->
                    blockUI.start("deleting hints")
                    (
                        Restangular.restangularizeElement(null, hint, ICSW_URLS.REST_MONITORING_HINT_DETAIL.slice(1).slice(0, -2)) for hint in _to_del
                    )
                    $q.all(
                        (hint.remove() for hint in _to_del)
                    ).then(
                        (done) ->
                            _keys = (hint.key for hint in _to_del)
                            _.remove(device.monitoring_hint_set, (entry) -> return entry.key in _keys)
                            blockUI.stop()
                    )
            )

    $scope.get_expand_class = (device) ->
        if device.$$hints_expanded
            return "glyphicon glyphicon-chevron-down"
        else
            return "glyphicon glyphicon-chevron-right"

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
        controller: "icswMonitoringHintTableCtrl"
    }
]).controller("icswMonitoringHintTableCtrl",
[
    "$scope", "$q", "icswToolsSimpleModalService", "Restangular", "ICSW_URLS",
    "toaster", "$compile", "$templateCache", "blockUI", "icswComplexModalService",
    "icswMonitoringHintBackup",
(
    $scope, $q, icswToolsSimpleModalService, Restangular, ICSW_URLS,
    toaster, $compile, $templateCache, blockUI, icswComplexModalService,
    icswMonitoringHintBackup,
) ->
    _salt_hints = () ->
        for entry in $scope.device.monitoring_hint_set
            entry.$$v_type = {
                f: "float"
                i: "int"
                s: "string"
                B: "blob"
            }[entry.v_type]
            entry.$$from_now = moment(entry.date).fromNow(true)
            if entry.v_type == "B"
                entry.$$value = entry.value_blob.length + " Bytes"
            else
                entry.$$value = entry["value_#{entry.$$v_type}"]
            # entry.$$from_now = m
            for _name in ["lower_crit", "lower_warn", "upper_warn", "upper_crit"]
                s_key = "#{_name}_#{entry.$$v_type}"
                d_key = "$$#{s_key}"
                _source = entry["#{s_key}_source"]
                if _source == "n"
                    entry["$$#{_name}_title"] = "not set"
                    entry["$$#{_name}_class"] = ""
                    entry["$$#{_name}_limit"] = "---"
                else if _source == "s"
                    entry["$$#{_name}_title"] = "set by system"
                    entry["$$#{_name}_class"] = "warning"
                    entry["$$#{_name}_limit"] = entry[s_key]
                else if _source == "u"
                    entry["$$#{_name}_title"] = "not by user"
                    entry["$$#{_name}_class"] = "success"
                    entry["$$#{_name}_limit"] = entry[s_key]
                else
                    entry["$$#{_name}_title"] = "unknown source '#{_source}'"
                    entry["$$#{_name}_class"] = ""
                    entry["$$#{_name}_limit"] = "---"
            entry.$$show_modify = entry.v_type in ["f", "i"]
    _salt_hints()

    # modify functions

    $scope.delete_hint = ($event, hint) ->
        icswToolsSimpleModalService("Really delete hint #{hint.key} ?").then(
            (ok) ->
                Restangular.restangularizeElement(null, hint, ICSW_URLS.REST_MONITORING_HINT_DETAIL.slice(1).slice(0, -2))
                hint.remove().then(
                    (removed) ->
                        _.remove($scope.device.monitoring_hint_set, (entry) -> return entry.key == hint.key)
                        _salt_hints()
                        toaster.pop("success", "", "removed hint")
                )
        )

    $scope.toggle_enabled = ($event, hint) ->
        $event.stopPropagation()
        hint.enabled = !hint.enabled
        $scope.save_hint(hint)

    $scope.save_hint = (hint) ->
        Restangular.restangularizeElement(null, hint, ICSW_URLS.REST_MONITORING_HINT_DETAIL.slice(1).slice(0, -2))
        hint.put().then(
            (done) ->
        )

    $scope.edit_hint = ($event, hint) ->
        dbu = new icswMonitoringHintBackup()
        dbu.create_backup(hint)

        sub_scope = $scope.$new(false)
        sub_scope.edit_obj = hint
        # copy references

        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.monitoring.hint.form"))(sub_scope)
                title: "Modify monitoring hint"
                ok_label: "Modify"
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.invalid
                        toaster.pop("warning", "form validation problem", "", 0)
                        d.reject("form not valid")
                    else
                        blockUI.start("saving hint...")
                        # hm, maybe not working ...
                        Restangular.restangularizeElement(null, sub_scope.edit_obj, ICSW_URLS.REST_MONITORING_HINT_DETAIL.slice(1).slice(0, -2))
                        sub_scope.edit_obj.put().then(
                            (ok) ->
                                blockUI.stop()
                                d.resolve("saved")
                            (not_ok) ->
                                blockUI.stop()
                                d.reject("not saved")
                        )
                    return d.promise
                cancel_callback: (modal) ->
                    dbu.restore_backup(hint)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                sub_scope.$destroy()
                _salt_hints()
        )
])
