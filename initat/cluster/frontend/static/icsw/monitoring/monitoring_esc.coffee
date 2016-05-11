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

monitoring_cluster_module = angular.module(
    "icsw.monitoring.escalation",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select",
        "icsw.tools.table", "icsw.tools.button", "icsw.monitoring.monitoring_basic"
    ]
).directive('icswMonitoringEscalation', () ->
    return {
        restrict: "EA"
        templateUrl: "icsw.monitoring.escalation"
        controller: "icswMonitoringEscalationCtrl",
    }
).config(["$stateProvider", ($stateProvider) ->
    $stateProvider.state(
        "main.monitoresc", {
            url: "/monitoresc"
            template: "<icsw-monitoring-escalation></icsw-monitoring-escalation>"
            icswData:
                pageTitle: "Monitoring Escalation setup"
                rights: ["mon_check_command.setup_monitoring"]
                menuEntry:
                    menukey: "mon"
                    name: "Escalation setup"
                    icon: "fa-bolt"
                    ordering: 30
        }
    )
]).service("icswMonitoringEscalationTree",
[
    "$q", "Restangular", "ICSW_URLS", "ICSW_SIGNALS", "icswTools",
(
    $q, Restangular, ICSW_URLS, ICSW_SIGNALS, icswTools
) ->
    ELIST = [
        "mon_device_esc_templ", "mon_service_esc_templ",
    ]
    class icswMonitoringEscalationTree
        constructor: (@basic_tree, args...) ->
            for entry in ELIST
                @["#{entry}_list"] = []
            @update(args...)
            @missing_info = {
                mon_device_esc_templ: [
                    ["basic_tree", "mon_period", "Period"]
                    ["mon_service_esc_templ", "ServiceEscalation Template"]
                ]
                mon_service_esc_templ: [
                    ["basic_tree", "mon_period", "Period"]
                ]
            }
        update: (args...) =>
            for [entry, _list] in _.zip(ELIST, args)
                @["#{entry}_list"].length = 0
                for _el in _list
                    @["#{entry}_list"].push(_el)
            @build_luts()

        build_luts: () =>
            for entry in ELIST
                @["#{entry}_lut"] = _.keyBy(@["#{entry}_list"], "idx")

        # create / delete mon_device_esc_templ

        create_mon_device_esc_templ: (new_obj) =>
            d = $q.defer()
            Restangular.all(ICSW_URLS.REST_MON_DEVICE_ESC_TEMPL_LIST.slice(1)).post(new_obj).then(
                (created) =>
                    @mon_device_esc_templ_list.push(created)
                    @build_luts()
                    d.resolve(created)
                (not_cr) =>
                    d.reject("not created")
            )
            return d.promise

        delete_mon_device_esc_templ: (del_obj) =>
            d = $q.defer()
            Restangular.restangularizeElement(null, del_obj, ICSW_URLS.REST_MON_DEVICE_ESC_TEMPL_DETAIL.slice(1).slice(0, -2))
            del_obj.remove().then(
                (removed) =>
                    _.remove(@mon_device_esc_templ_list, (entry) -> return entry.idx == del_obj.idx)
                    d.resolve("deleted")
                (not_removed) ->
                    d.resolve("not deleted")
            )
            return d.promise

        # create / delete mon_service_esc_templ

        create_mon_service_esc_templ: (new_obj) =>
            d = $q.defer()
            Restangular.all(ICSW_URLS.REST_MON_SERVICE_ESC_TEMPL_LIST.slice(1)).post(new_obj).then(
                (created) =>
                    @mon_service_esc_templ_list.push(created)
                    @build_luts()
                    d.resolve(created)
                (not_cr) =>
                    d.reject("not created")
            )
            return d.promise

        delete_mon_service_esc_templ: (del_obj) =>
            d = $q.defer()
            Restangular.restangularizeElement(null, del_obj, ICSW_URLS.REST_MON_SERVICE_ESC_TEMPL_DETAIL.slice(1).slice(0, -2))
            del_obj.remove().then(
                (removed) =>
                    _.remove(@mon_service_esc_templ_list, (entry) -> return entry.idx == del_obj.idx)
                    d.resolve("deleted")
                (not_removed) ->
                    d.resolve("not deleted")
            )
            return d.promise

]).service("icswMonitoringEscalationTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "icswCachingCall", "icswTools", "$rootScope",
    "ICSW_SIGNALS", "icswMonitoringBasicTreeService", "icswMonitoringEscalationTree",
(
    $q, Restangular, ICSW_URLS, icswCachingCall, icswTools, $rootScope,
    ICSW_SIGNALS, icswMonitoringBasicTreeService, icswMonitoringEscalationTree,
) ->
    # loads the monitoring tree
    rest_map = [
        [
            ICSW_URLS.REST_MON_DEVICE_ESC_TEMPL_LIST, {}
        ]
        [
            ICSW_URLS.REST_MON_SERVICE_ESC_TEMPL_LIST, {}
        ]
    ]
    _fetch_dict = {}
    _result = undefined
    # load called
    load_called = false

    load_data = (client) ->
        load_called = true
        _wait_list = (icswCachingCall.fetch(client, _entry[0], _entry[1], []) for _entry in rest_map)
        _wait_list.push(icswMonitoringBasicTreeService.load(client))
        _defer = $q.defer()
        $q.all(_wait_list).then(
            (data) ->
                console.log "*** escalation monitoring tree loaded ***"
                _result = new icswMonitoringEscalationTree(data[2], data[0], data[1])
                _defer.resolve(_result)
                for client of _fetch_dict
                    # resolve clients
                    _fetch_dict[client].resolve(_result)
                # $rootScope.$emit(ICSW_SIGNALS("ICSW_MON_TREE_LOADED"), _result)
                # reset fetch_dict
                _fetch_dict = {}
        )
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

    return {
        "load": (client) ->
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise
    }
]).controller("icswMonitoringEscalationCtrl",
[
    "$scope", "$q", "icswMonitoringEscalationTreeService",
(
    $scope, $q, icswMonitoringEscalationTreeService
) ->
    $scope.struct = {
        # tree valid
        tree_valid: false
        # basic tree
        esc_tree: undefined
    }
    $scope.reload = () ->
        icswMonitoringEscalationTreeService.load($scope.$id).then(
            (data) ->
                $scope.struct.esc_tree = data
                $scope.struct.tree_valid = true
        )
    $scope.reload()
]).service("icswMonitoringServiceEscalationTemplateService",
[
    "ICSW_URLS", "icswMonitoringEscalationTreeService", "$q", "Restangular",
    "icswToolsSimpleModalService", "icswMonServiceEscTemplBackup", "icswMonitoringUtilService",
    "icswDeviceTreeService",
(
    ICSW_URLS, icswMonitoringEscalationTreeService, $q, Restangular,
    icswToolsSimpleModalService, icswMonServiceEscTemplBackup, icswMonitoringUtilService,
    icswDeviceTreeService,
) ->
    esc_tree = undefined
    return {
        fetch: (scope) ->
            defer = $q.defer()
            $q.all(
                [
                    icswMonitoringEscalationTreeService.load(scope.$id)
                    icswDeviceTreeService.load(scope.$id)
                ]
            ).then(
                (data) ->
                    esc_tree = data[0]
                    scope.esc_tree = esc_tree
                    scope.basic_tree = scope.esc_tree.basic_tree
                    scope.device_tree = data[1]
                    defer.resolve(esc_tree.mon_service_esc_templ_list)
            )
            return defer.promise

        create_or_edit: (scope, $event, create, obj) ->
            if create
                obj = {
                    name: ""
                    first_notification: 1
                    last_notification: 2
                    esc_period: esc_tree.basic_tree.mon_period_list[0].idx
                    ninterval: 2
                    nrecovery: true
                    ncritical: true
                }
            return icswMonitoringUtilService.create_or_edit(
                esc_tree
                scope
                create
                obj
                "mon_service_esc_templ"
                icswMonServiceEscTemplBackup
                "icsw.mon.service.esc.templ.form"
                "Service Esclation Template"
            )

        delete: (scope, $event, obj) ->
            icswToolsSimpleModalService("Really delete ServiceEscalationTemplate '#{obj.name}' ?").then(
                () =>
                    esc_tree.delete_mon_service_esc_templ(obj).then(
                        () ->
                            console.log "mon_service_esc_templ deleted"
                    )
            )

        get_data_incomplete_error: () ->
            return icswMonitoringUtilService.get_data_incomplete_error(esc_tree, "mon_service_esc_templ")
    }
]).service("icswMonitoringDeviceEscalationTemplateService",
[
    "ICSW_URLS", "icswMonitoringEscalationTreeService", "$q", "Restangular",
    "icswToolsSimpleModalService", "icswMonDeviceEscTemplBackup", "icswMonitoringUtilService",
    "icswDeviceTreeService",
(
    ICSW_URLS, icswMonitoringEscalationTreeService, $q, Restangular,
    icswToolsSimpleModalService, icswMonDeviceEscTemplBackup, icswMonitoringUtilService,
    icswDeviceTreeService,
) ->
    esc_tree = undefined
    return {
        fetch: (scope) ->
            defer = $q.defer()
            $q.all(
                [
                    icswMonitoringEscalationTreeService.load(scope.$id)
                    icswDeviceTreeService.load(scope.$id)
                ]
            ).then(
                (data) ->
                    esc_tree = data[0]
                    scope.esc_tree = esc_tree
                    scope.basic_tree = scope.esc_tree.basic_tree
                    scope.device_tree = data[1]
                    defer.resolve(esc_tree.mon_device_esc_templ_list)
            )
            return defer.promise

        create_or_edit: (scope, $event, create, obj) ->
            if create
                obj = {
                    name: ""
                    first_notification: 1
                    last_notification: 2
                    esc_period: esc_tree.basic_tree.mon_period_list[0].idx
                    mon_service_esc_templ: esc_tree.mon_service_esc_templ_list[0].idx
                    ninterval: 2
                    nrecovery: true
                    ndown: true
                }
            return icswMonitoringUtilService.create_or_edit(
                esc_tree
                scope
                create
                obj
                "mon_device_esc_templ"
                icswMonDeviceEscTemplBackup
                "icsw.mon.device.esc.templ.form"
                "Device Esclation Template"
            )

        delete: (scope, $event, obj) ->
            icswToolsSimpleModalService("Really delete DeviceEscalationTemplate '#{obj.name}' ?").then(
                () =>
                    esc_tree.delete_mon_device_esc_templ(obj).then(
                        () ->
                            console.log "mon_device_esc_templ deleted"
                    )
            )

        get_data_incomplete_error: () ->
            return icswMonitoringUtilService.get_data_incomplete_error(esc_tree, "mon_device_esc_templ")
    }
])
