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
]).directive('icswMonitoringCluster', () ->
    return {
        restrict     : "EA"
        templateUrl  : "icsw.monitoring.cluster"
    }
).config(["$stateProvider", ($stateProvider) ->
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
]).service('icswMonitoringClusterRestService', ["ICSW_URLS", "Restangular", (ICSW_URLS, Restangular) ->
    get_rest = (url, opts={}) -> return Restangular.all(url).getList(opts).$object
    data = {
        device              : get_rest(ICSW_URLS.REST_DEVICE_TREE_LIST.slice(1), {"ignore_meta_devices" : true, "ignore_selection" : true})
        mon_service_templ   : get_rest(ICSW_URLS.REST_MON_SERVICE_TEMPL_LIST.slice(1))
        mon_check_command   : get_rest(ICSW_URLS.REST_MON_CHECK_COMMAND_LIST.slice(1))
        # mon_period          : get_rest(ICSW_URLS.REST_MON_PERIOD_LIST.slice(1))
        mon_host_cluster    : get_rest(ICSW_URLS.REST_MON_HOST_CLUSTER_LIST.slice(1))
        mon_check_command   : get_rest(ICSW_URLS.REST_MON_CHECK_COMMAND_LIST.slice(1))
        mon_service_cluster : get_rest(ICSW_URLS.REST_MON_SERVICE_CLUSTER_LIST.slice(1))
        mon_host_dependency : get_rest(ICSW_URLS.REST_MON_HOST_DEPENDENCY_LIST.slice(1))
        mon_service_dependency        : get_rest(ICSW_URLS.REST_MON_SERVICE_DEPENDENCY_LIST.slice(1))
        mon_host_dependency_templ     : get_rest(ICSW_URLS.REST_MON_HOST_DEPENDENCY_TEMPL_LIST.slice(1))
        mon_service_dependency_templ  : get_rest(ICSW_URLS.REST_MON_SERVICE_DEPENDENCY_TEMPL_LIST.slice(1))
    }
    return data
]).service('icswMonitoringHostClusterService', ["ICSW_URLS", "icswMonitoringClusterRestService", "icswMonitoringUtilService", (ICSW_URLS, icswMonitoringClusterRestService, icswMonitoringUtilService) ->
    ret = {
        rest_handle        : icswMonitoringClusterRestService.mon_host_cluster
        edit_template      : "mon.host.cluster.form"
        delete_confirm_str : (obj) ->
            return "Really delete host cluster '#{obj.name}' ?"
        new_object         : () ->
            return {
            "name": ""
            "description": "new host cluster"
            "mon_service_templ": (entry.idx for entry in icswMonitoringClusterRestService.mon_service_templ)[0]
            "warn_value": 1
            "error_value": 2
            }
        object_created     : (new_obj) -> new_obj.name = ""

        get_data_incomplete_error: () ->
            return icswMonitoringUtilService.get_data_incomplete_error(icswMonitoringClusterRestService,
                [["device", "device"], ["mon_service_templ", "service template"]])
    }
    for k, v of icswMonitoringClusterRestService
        ret[k] = v
    return ret
]).service('icswMonitoringServiceClusterService', ["ICSW_URLS", "icswMonitoringClusterRestService", "icswMonitoringUtilService", (ICSW_URLS, icswMonitoringClusterRestService, icswMonitoringUtilService) ->
    ret =  {
        rest_handle         : icswMonitoringClusterRestService.mon_service_cluster
        edit_template       : "mon.service.cluster.form"
        delete_confirm_str  : (obj) ->
            return "Really delete service cluster '#{obj.name}' ?"
        new_object          : () ->
            return {
                "name" : ""
                "description" : "new service cluster"
                "mon_service_templ" : (entry.idx for entry in icswMonitoringClusterRestService.mon_service_templ)[0]
                "mon_check_command" : (entry.idx for entry in icswMonitoringClusterRestService.mon_check_command)[0]
                "warn_value" : 1
                "error_value" : 2
            }
        object_created  : (new_obj) -> new_obj.name = ""
        get_data_incomplete_error: () ->
            return icswMonitoringUtilService.get_data_incomplete_error(icswMonitoringClusterRestService,
                [["device", "device"], ["mon_service_templ", "service template"], ["mon_check_command", "check command"]])
    }
    for k, v of icswMonitoringClusterRestService
        ret[k] = v
    return ret
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
