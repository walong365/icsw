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
    "icsw.livestatus.comp.tabular",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.router",
    ]
).config(["icswLivestatusPipeRegisterProvider", (icswLivestatusPipeRegisterProvider) ->
    icswLivestatusPipeRegisterProvider.add("icswLivestatusMonTabularDisplay", true)
    icswLivestatusPipeRegisterProvider.add("icswLivestatusDeviceTabularDisplay", true)
]).service('icswLivestatusMonTabularDisplay',
[
    "$q", "icswMonLivestatusPipeBase", "icswMonitoringResult",
(
    $q, icswMonLivestatusPipeBase, icswMonitoringResult,
) ->
    class icswLivestatusMonTabularDisplay extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusMonTabularDisplay", true, false)
            @set_template(
                '<icsw-livestatus-mon-table-view icsw-connect-element="con_element"></icsw-livestatus-mon-table-view>'
                "Service Tabular Display"
                10
                8
            )
            @new_data_notifier = $q.defer()

        new_data_received: (data) ->
            @new_data_notifier.notify(data)

        pipeline_reject_called: (reject) ->
            @new_data_notifier.reject("end")

        restore_settings: (settings) ->
            # store settings
            @_settings = settings

]).directive("icswLivestatusMonTableView",
[
    "$templateCache",
(
    $templateCache,
) ->
        return {
            restrict: "EA"
            template: $templateCache.get("icsw.livestatus.mon.table.view")
            controller: "icswLivestatusDeviceMonTableCtrl"
            scope: {
                # connect element for pipelining
                con_element: "=icswConnectElement"
            }
            link: (scope, element, attrs) ->
                scope.link(scope.con_element, scope.con_element.new_data_notifier, "services")
        }
]).directive("icswLivestatusMonTableRow",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.livestatus.mon.table.row")
    }
]).service('icswLivestatusDeviceTabularDisplay',
[
    "$q", "icswMonLivestatusPipeBase", "icswMonitoringResult",
(
    $q, icswMonLivestatusPipeBase, icswMonitoringResult,
) ->
    class icswLivestatusDeviceTabularDisplay extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusDeviceTabularDisplay", true, false)
            @set_template(
                '<icsw-livestatus-device-table-view icsw-connect-element="con_element"></icsw-livestatus-device-table-view>'
                "Device Tabular Display"
                10
                8
            )
            @new_data_notifier = $q.defer()

        new_data_received: (data) ->
            @new_data_notifier.notify(data)

        pipeline_reject_called: (reject) ->
            @new_data_notifier.reject("end")

        restore_settings: (settings) ->
            # store settings
            @_settings = settings

]).directive("icswLivestatusDeviceTableView",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.livestatus.device.table.view")
        controller: "icswLivestatusDeviceMonTableCtrl"
        scope: {
            # connect element for pipelining
            con_element: "=icswConnectElement"
        }
        link: (scope, element, attrs) ->
            scope.link(scope.con_element, scope.con_element.new_data_notifier, "hosts")
    }
]).directive("icswLivestatusDeviceTableRow",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.livestatus.device.table.row")
    }
]).directive("icswLivestatusTableRowSel",
[
    "$q", "ICSW_SIGNALS",
(
    $q, ICSW_SIGNALS,
) ->
    return {
        restrict: "A"
        scope:
            element: "=icswLivestatusTableRowSel"
        link: (scope, element, attrs) ->
            if not scope.element.$$selected?
                scope.element.$$selected = false
            if scope.element.$$selected
                $(element).addClass("info")
            $(element).bind("click", () ->
                scope.element.$$selected = !scope.element.$$selected
                if scope.element.$$selected
                    scope.$emit(ICSW_SIGNALS("_ICSW_UPDATE_MON_SELECTION"), 1)
                    $(element).addClass("info")
                else
                    scope.$emit(ICSW_SIGNALS("_ICSW_UPDATE_MON_SELECTION"), -1)
                    $(element).removeClass("info")
            )
    }
]).service("icswIcingaCmdTools",
[
    "$q", "icswMonitoringBasicTreeService", "$rootScope", "$templateCache", "$compile",
    "icswSimpleAjaxCall", "blockUI", "icswComplexModalService", "icswUserService",
    "ICSW_URLS",
(
    $q, icswMonitoringBasicTreeService, $rootScope, $templateCache, $compile,
    icswSimpleAjaxCall, blockUI, icswComplexModalService, icswUserService,
    ISCW_URLS,
) ->
    _struct = {
        basic_tree: null
    }

    load_tree = () ->
        defer = $q.defer()
        if _struct.basic_tree
            defer.resolve(_struct.basic_tree)
        else
            blockUI.start("loading commands...")
            icswMonitoringBasicTreeService.load("icswIcingaCmdTools").then(
                (tree) ->
                    blockUI.stop()
                    _struct.basic_tree = tree
                    defer.resolve(_struct.basic_tree)
            )
        return defer.promise

    icinga_cmd = (obj_type, obj_key_list) ->
        load_tree().then(
            (tree) ->
                sub_scope = $rootScope.$new(true)
                sub_scope.obj_type = obj_type
                sub_scope.obj_key_list = obj_key_list
                sub_scope.user = icswUserService.get()
                # action

                _actions = []
                for entry in tree.icinga_command_list
                    if not entry.$$private
                        if obj_type == "host"
                            # for host actions this must be a host-only action
                            if entry.for_host and not entry.for_service
                                _actions.push(entry)
                        else if obj_type == "service"
                            # for service actions this must be a service action (!)
                            if entry.for_service
                                _actions.push(entry)

                sub_scope.valid_actions = _.orderBy(
                    _actions
                    ["name"]
                    ["asc"]
                )
                sub_scope.edit_obj = {
                    action: sub_scope.valid_actions[0]
                    args: {}
                }
                sub_scope.arguments = []

                sub_scope.action_changed = ($event) ->
                    _act = sub_scope.edit_obj.action
                    sub_scope.arguments.length = 0
                    sub_scope.edit_obj.args = {}
                    for arg in _act.args
                        if arg.name not in ["host_name", "service_description"]
                            sub_scope.arguments.push(arg)
                            if arg.is_boolean
                                _default = true
                            else
                                _default = ""
                            sub_scope.edit_obj.args[arg.name] = _default

                sub_scope.action_changed()
                icswComplexModalService(
                    {
                        message: $compile($templateCache.get("icsw.livestatus.modify.entries"))(sub_scope)
                        title: "Submit Icinga command"
                        ok_label: "Submit"
                        closable: true
                        ok_callback: (modal) ->
                            d = $q.defer()
                            blockUI.start()
                            icswSimpleAjaxCall(
                                {
                                    url: ICSW_URLS.MON_SEND_MON_COMMAND
                                    data:
                                        json: angular.toJson(
                                            action: sub_scope.edit_obj.action
                                            type: obj_type
                                            key_list: obj_key_list
                                        )
                                }
                            ).then(
                                (res) ->
                                    console.log "r=", res
                                    blockUI.stop()
                                    d.resolve("close")
                                (error) ->
                                    blockUI.stop()
                                    d.reject(error)
                            )
                            return d.promise
                        cancel_callback: () ->
                            d = $q.defer()
                            d.resolve("close")
                            return d.promise
                    }
                ).then(
                    (fin) ->
                        sub_scope.$destroy()
                )


        )
    return {
        icinga_cmd: (obj_type, obj_key_list) ->
            return icinga_cmd(obj_type, obj_key_list)
    }

]).controller("icswLivestatusDeviceMonTableCtrl",
[
    "$scope", "DeviceOverviewService", "$q", "icswSimpleAjaxCall", "ICSW_URLS",
    "ICSW_SIGNALS", "icswComplexModalService", "$templateCache", "$compile", "blockUI",
    "icswIcingaCmdTools",
(
    $scope, DeviceOverviewService, $q, icswSimpleAjaxCall, ICSW_URLS,
    ICSW_SIGNALS, icswComplexModalService, $templateCache, $compile, $blockUI,
    icswIcingaCmdTools,
) ->
    $scope.struct = {
        # monitoring data
        monitoring_data: undefined
        # connection element
        con_element: undefined
        # settings
        settings: {
            "pag": {}
            "columns": {}
        }
        # selected
        selected: 0
        # display type
        d_type: undefined
        # value for modify button
        modify_value: "N/A"
        # external notifier

        external_notifier: $q.defer()
    }
    $scope.link = (con_element, notifier, d_type) ->
        $scope.struct.d_type = d_type
        # console.log $scope.struct.d_type
        $scope.struct.con_element = con_element
        if $scope.struct.con_element._settings?
            $scope.struct.settings = angular.fromJson($scope.struct.con_element._settings)
            if "pag" of $scope.struct.settings
                $scope.pagination_settings = $scope.struct.settings["pag"]
            if "columns" of $scope.struct.settings
                $scope.columns_from_settings = $scope.struct.settings["columns"]
        notifier.promise.then(
            (resolve) ->
            (rejected) ->
            (data) ->
                $scope.struct.monitoring_data = data
                $scope.struct.external_notifier.notify("new")
                _update_selected()
        )

    $scope.$on("$destroy", () ->
        $scope.struct.external_notifier.reject()
    )

    $scope.show_device = ($event, dev_check) ->
        DeviceOverviewService($event, [dev_check.$$icswDevice])

    $scope.pagination_changed = (pag) ->
        if not pag?
            return $scope.struct.settings["pag"]
        else
            $scope.struct.settings["pag"] = pag
            $scope.struct.con_element.pipeline_settings_changed(angular.toJson($scope.struct.settings))

    $scope.columns_changed = (col_setup) ->
        $scope.struct.settings["columns"] = col_setup
        $scope.struct.con_element.pipeline_settings_changed(angular.toJson($scope.struct.settings))

    _update_selected = () ->
        $scope.struct.selected = (entry for entry in $scope.struct.monitoring_data[$scope.struct.d_type] when entry.$$selected).length
        if $scope.struct.selected
            $scope.struct.modify_value = "modify #{$scope.struct.selected} #{$scope.struct.d_type}"
        else
            $scope.struct.modify_value = "N/A"

    $scope.$on(ICSW_SIGNALS("_ICSW_UPDATE_MON_SELECTION"), (event, val) ->
        # handling of table-row clicks
        $scope.$apply(
            () ->
                _update_selected()
        )
    )

    $scope.modify_entries = ($event) ->
        if $scope.struct.d_type == "hosts"
            _obj_type = "host"
            key_list = (entry.$$icswDevice.idx for entry in $scope.struct.monitoring_data.hosts when entry.$$selected)
        else
            _obj_type = "service"
            key_list = (entry.description for entry in $scope.struct.monitoring_data.services when entry.$$selected)
        icswIcingaCmdTools.icinga_cmd(
            _obj_type
            key_list
        )
])
