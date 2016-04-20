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
    "icsw.monitoring.cluster",
[
    "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select",
    "icsw.tools.table", "icsw.tools.button", "icsw.monitoring.monitoring_basic"
]).directive('icswMonitoringCluster',
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.monitoring.cluster")
        controller: "icswMonitoringClusterCtrl",
    }
]).config(["$stateProvider", ($stateProvider) ->
    $stateProvider.state(
        "main.monitorcluster", {
            url: "/monitorcluster"
            template: "<icsw-monitoring-cluster></icsw-monitoring-cluster>"
            data:
                pageTitle: "Monitoring Cluster / Dependency setup"
                rights: ["mon_check_command.setup_monitoring"]
                menuEntry:
                    menukey: "mon"
                    name: "Cluster / Dependency setup"
                    icon: "fa-chain"
                    ordering: 20
        }
    )
]).service("icswMonitoringClusterTree",
[
    "$q", "Restangular", "ICSW_URLS", "ICSW_SIGNALS", "icswTools",
(
    $q, Restangular, ICSW_URLS, ICSW_SIGNALS, icswTools
) ->
    ELIST = [
        "mon_host_cluster", "mon_service_cluster",
        "mon_host_dependency", "mon_service_dependency",
        "mon_host_dependency_templ", "mon_service_dependency_templ",
    ]
    class icswMonitoringClusterTree
        constructor: (@basic_tree, args...) ->
            for entry in ELIST
                @["#{entry}_list"] = []
            @update(args...)
            @missing_info = {
                "mon_contact": [
                    ["mon_period", "period"]
                ]
                "mon_service_templ": [
                    ["mon_period", "period"]
                ]
                "mon_device_templ": [
                    ["mon_period", "period"]
                    ["mon_service_templ", "service template"]
                    ["host_check_command", "host check command"]
                ]
            }
            # mon_host_cluster: [["device", "device"], ["mon_service_templ", "service template"]])
            # mon_service_cluster: [["device", "device"], ["mon_service_templ", "service template"], ["mon_check_command", "check command"]])
            # mon_host/service_dep_templ: [["mon_period", "period"]])
            # mon_host_dependency: [["device", "device"], ["mon_host_dependency_templ", "host dependency template"]])
            # mon_service_dependency: [["device", "device"], ["mon_service_dependency_templ", "service dependency template"], ["mon_check_command", "check command"]])

        update: (args...) =>
            for [entry, _list] in _.zip(ELIST, args)
                @["#{entry}_list"].length = 0
                for _el in _list
                    @["#{entry}_list"].push(_el)
            @build_luts()

        build_luts: () =>
            for entry in ELIST
                @["#{entry}_lut"] = _.keyBy(@["#{entry}_list"], "idx")


]).service("icswMonitoringClusterTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "icswCachingCall", "icswTools", "$rootScope",
    "ICSW_SIGNALS", "icswMonitoringBasicTreeService", "icswMonitoringClusterTree",
(
    $q, Restangular, ICSW_URLS, icswCachingCall, icswTools, $rootScope,
    ICSW_SIGNALS, icswMonitoringBasicTreeService, icswMonitoringClusterTree,
) ->
    # loads the monitoring tree
    rest_map = [
        [
            ICSW_URLS.REST_MON_HOST_CLUSTER_LIST, {}
        ]
        [
            ICSW_URLS.REST_MON_SERVICE_CLUSTER_LIST, {}
        ]
        [
            ICSW_URLS.REST_MON_HOST_DEPENDENCY_LIST, {}
        ]
        [
            ICSW_URLS.REST_MON_SERVICE_DEPENDENCY_LIST, {}
        ]
        [
            ICSW_URLS.REST_MON_HOST_DEPENDENCY_TEMPL_LIST, {}
        ]
        [
            ICSW_URLS.REST_MON_SERVICE_DEPENDENCY_TEMPL_LIST, {}
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
                console.log "*** basic monitoring tree loaded ***"
                _result = new icswMonitoringClusterTree(data[6], data[0], data[1], data[2], data[3], data[4], data[5])
                _defer.resolve(_result)
                for client of _fetch_dict
                    # resolve clients
                    _fetch_dict[client].resolve(_result)
                $rootScope.$emit(ICSW_SIGNALS("ICSW_MON_TREE_LOADED"), _result)
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
]).controller("icswMonitoringClusterCtrl",
[
    "$scope", "$q", "icswMonitoringClusterTreeService",
(
    $scope, $q, icswMonitoringClusterTreeService
) ->
    $scope.struct = {
        # tree valid
        tree_valid: false
        # basic tree
        cluster_tree: undefined
    }
    $scope.reload = () ->
        icswMonitoringClusterTreeService.load($scope.$id).then(
            (data) ->
                $scope.struct.cluster_tree = data
                $scope.struct.tree_valid = true
                # console.log $scope.struct
        )
    $scope.reload()
]).service("icswMonitoringClusterRestService", [() ->
]).service("icswMonitoringHostClusterService",
[
    "ICSW_URLS", "icswMonitoringClusterTreeService", "$q", "Restangular",
    "icswToolsSimpleModalService", "icswMonPeriodBackup", "icswMonitoringUtilService",
    "icswDeviceTreeService",
(
    ICSW_URLS, icswMonitoringClusterTreeService, $q, Restangular,
    icswToolsSimpleModalService, icswMonPeriodBackup, icswMonitoringUtilService,
    icswDeviceTreeService,
) ->
    cluster_tree = undefined
    return {
        fetch: (scope) ->
            defer = $q.defer()
            $q.all(
                [
                    icswMonitoringClusterTreeService.load(scope.$id)
                    icswDeviceTreeService.load(scope.$id)
                ]
            ).then(
                (data) ->
                    cluster_tree = data[0]
                    scope.cluster_tree = cluster_tree
                    scope.device_tree = data[1]
                    defer.resolve(cluster_tree.mon_host_cluster_list)
            )
            return defer.promise

        create_or_edit: (scope, $event, create, obj) ->
            if create
                obj = {
                    name: ""
                    description: "new host cluster"
                    mon_service_templ: cluster_tree.basic_tree.mon_service_templ_list[0].idx
                    warn_value: 1
                    error_value: 2
                }
            return icswMonitoringUtilService.create_or_edit(
                cluster_tree
                scope
                create
                obj
                "mon_host_cluster"
                icswMonPeriodBackup
                "icsw.mon.host.cluster.form"
                "Monitoring HostCluster"
            )

        delete: (scope, $event, obj) ->
            icswToolsSimpleModalService("Really delete MonitoringHostCluster '#{obj.name}' ?").then(
                () =>
                    cluster_tree.delete_mon_host_cluster(obj).then(
                        () ->
                            console.log "mon_host_cluster deleted"
                    )
            )

        get_data_incomplete_error: () ->
            return icswMonitoringUtilService.get_data_incomplete_error(cluster_tree, "mon_host_cluster")
    }
]).service("icswMonitoringServiceClusterService",
[
    "ICSW_URLS", "icswMonitoringClusterTreeService", "$q", "Restangular",
    "icswToolsSimpleModalService", "icswMonPeriodBackup", "icswMonitoringUtilService",
    "icswDeviceTreeService",
(
    ICSW_URLS, icswMonitoringClusterTreeService, $q, Restangular,
    icswToolsSimpleModalService, icswMonPeriodBackup, icswMonitoringUtilService,
    icswDeviceTreeService,
) ->
    cluster_tree = undefined
    return {
        fetch: (scope) ->
            defer = $q.defer()
            $q.all(
                [
                    icswMonitoringClusterTreeService.load(scope.$id)
                    icswDeviceTreeService.load(scope.$id)
                ]
            ).then(
                (data) ->
                    cluster_tree = data[0]
                    scope.cluster_tree = cluster_tree
                    scope.device_tree = data[1]
                    defer.resolve(cluster_tree.mon_service_cluster_list)
            )
            return defer.promise

        create_or_edit: (scope, $event, create, obj) ->
            if create
                obj = {
                    name: ""
                    description: "new service cluster"
                    mon_service_templ: cluster_tree.basic_tree.mon_service_templ_list[0].idx
                    mon_check_command: cluster_tree.basic_tree.mon_check_command_list[0].idx
                    warn_value: 1
                    error_value: 2
                }
            return icswMonitoringUtilService.create_or_edit(
                cluster_tree
                scope
                create
                obj
                "mon_service_cluster"
                icswMonPeriodBackup
                "icsw.mon.service.cluster.form"
                "Monitoring ServiceCluster"
            )

        delete: (scope, $event, obj) ->
            icswToolsSimpleModalService("Really delete MonitoringServiceCluster '#{obj.name}' ?").then(
                () =>
                    cluster_tree.delete_mon_service_cluster(obj).then(
                        () ->
                            console.log "mon_service_cluster deleted"
                    )
            )

        get_data_incomplete_error: () ->
            return icswMonitoringUtilService.get_data_incomplete_error(cluster_tree, "mon_service_cluster")
    }
]).service('icswMonitoringHostDependencyTemplateService', ["ICSW_URLS", "icswMonitoringClusterRestService", "icswMonitoringUtilService", (ICSW_URLS, icswMonitoringClusterRestService, icswMonitoringUtilService) ->
    ret = {
        rest_handle         : icswMonitoringClusterRestService.mon_host_dependency_templ
        edit_template       : "mon.host.dependency.templ.form"
        delete_confirm_str  : (obj) ->
            return "Really delete Host dependency template '#{obj.name}' ?"
        new_object          : () ->
            return {
                "name" : ""
                "priority" : 0
                "dependency_period" : (entry.idx for entry in icswMonitoringClusterRestService.mon_period)[0]
                "efc_up" : true
                "efc_down" : true
                "nfc_up" : true
                "nfc_down" : true
            }
        object_created  : (new_obj) -> new_obj.name = ""
        get_data_incomplete_error: () ->
            return icswMonitoringUtilService.get_data_incomplete_error(icswMonitoringClusterRestService,
                [["mon_period", "period"]])
    }

    for k, v of icswMonitoringClusterRestService
        ret[k] = v
    return ret
]).service('icswMonitoringServiceDependencyTemplateService', ["ICSW_URLS", "icswMonitoringClusterRestService", "icswMonitoringUtilService", (ICSW_URLS, icswMonitoringClusterRestService, icswMonitoringUtilService) ->
    ret =  {
        rest_handle         : icswMonitoringClusterRestService.mon_service_dependency_templ
        edit_template       : "mon.service.dependency.templ.form"
        delete_confirm_str  : (obj) ->
            return "Really delete Service dependency template '#{obj.name}' ?"
        new_object          : () ->
            return {
                "name" : ""
                "priority" : 0
                "dependency_period" : (entry.idx for entry in icswMonitoringClusterRestService.mon_period)[0]
                "efc_ok" : true
                "efc_warn" : true
                "nfc_ok" : true
                "nfc_warn" : true
            }
        object_created  : (new_obj) -> new_obj.name = ""
        get_data_incomplete_error: () ->
            return icswMonitoringUtilService.get_data_incomplete_error(icswMonitoringClusterRestService,
                [["mon_period", "period"]])
    }
    for k, v of icswMonitoringClusterRestService
        ret[k] = v
    return ret
]).service('icswMonitoringHostDependencyService', ["ICSW_URLS", "icswMonitoringClusterRestService", "icswMonitoringUtilService", (ICSW_URLS, icswMonitoringClusterRestService, icswMonitoringUtilService) ->
    ret =  {
        rest_handle         : icswMonitoringClusterRestService.mon_host_dependency
        edit_template       : "mon.host.dependency.form"
        delete_confirm_str  : (obj) ->
            return "Really delete host dependency ?"
        new_object          : {}
        object_created  : (new_obj) ->
        get_data_incomplete_error: () ->
            return icswMonitoringUtilService.get_data_incomplete_error(icswMonitoringClusterRestService,
                [["device", "device"], ["mon_host_dependency_templ", "host dependency template"]])
    }
    for k, v of icswMonitoringClusterRestService
        ret[k] = v
    return ret
]).service('icswMonitoringServiceDependencyService', ["ICSW_URLS", "icswMonitoringClusterRestService", "icswMonitoringUtilService", (ICSW_URLS, icswMonitoringClusterRestService, icswMonitoringUtilService) ->
    ret =  {
        rest_handle         : icswMonitoringClusterRestService.mon_service_dependency
        edit_template       : "mon.service.dependency.form"
        delete_confirm_str  : (obj) ->
            return "Really delete service dependency ?"
        new_object          : {}
        object_created  : (new_obj) ->

        get_data_incomplete_error: () ->
            return icswMonitoringUtilService.get_data_incomplete_error(icswMonitoringClusterRestService,
                [["device", "device"], ["mon_service_dependency_templ", "service dependency template"], ["mon_check_command", "check command"]])
    }
    for k, v of icswMonitoringClusterRestService
        ret[k] = v
    return ret
])
