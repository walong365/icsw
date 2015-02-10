
monitoring_cluster_module = angular.module("icsw.monitoring.cluster",
        ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "icsw.tools.table", "icsw.tools.button"])


monitoring_cluster_module.directive('icswMonitoringCluster', () ->
    return {
        restrict     : "EA"
        templateUrl  : "icsw.monitoring.cluster"
    }
).service('icswMonitoringClusterRestService', ["ICSW_URLS", "Restangular", (ICSW_URLS, Restangular) ->
    get_rest = (url, opts={}) -> return Restangular.all(url).getList(opts).$object
    data = {
        device              : get_rest(ICSW_URLS.REST_DEVICE_TREE_LIST.slice(1), {"ignore_meta_devices" : true, "ignore_selection" : true})
        mon_service_templ   : get_rest(ICSW_URLS.REST_MON_SERVICE_TEMPL_LIST.slice(1))
        mon_check_command   : get_rest(ICSW_URLS.REST_MON_CHECK_COMMAND_LIST.slice(1))
        mon_period          : get_rest(ICSW_URLS.REST_MON_PERIOD_LIST.slice(1))
        mon_host_cluster    : get_rest(ICSW_URLS.REST_MON_HOST_CLUSTER_LIST.slice(1))
        mon_check_command   : get_rest(ICSW_URLS.REST_MON_CHECK_COMMAND_LIST.slice(1))
        mon_service_cluster : get_rest(ICSW_URLS.REST_MON_SERVICE_CLUSTER_LIST.slice(1))
        mon_host_dependency_templ     : get_rest(ICSW_URLS.REST_MON_HOST_DEPENDENCY_TEMPL_LIST.slice(1))
        mon_service_dependency_templ  : get_rest(ICSW_URLS.REST_MON_SERVICE_DEPENDENCY_TEMPL_LIST.slice(1))
    }
    _rest_data_present = (tables) ->
        ok = true
        for table in tables
            if not data[table].length
                ok = false
        return ok
    data['_rest_data_present'] = _rest_data_present
    return data
]).service('icswMonitoringHostClusterService', ["ICSW_URLS", "icswMonitoringClusterRestService", (ICSW_URLS, icswMonitoringClusterRestService) ->
    ret = {
        rest_url           : ICSW_URLS.REST_MON_HOST_CLUSTER_LIST
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
        rest_data_present  : () ->
            return icswMonitoringClusterRestService._rest_data_present(["device", "mon_service_templ"])
    }
    for k, v of icswMonitoringClusterRestService
        ret[k] = v
    return ret
]).service('icswMonitoringServiceClusterService', ["ICSW_URLS", "icswMonitoringClusterRestService", (ICSW_URLS, icswMonitoringClusterRestService) ->
    ret =  {
        rest_url            : ICSW_URLS.REST_MON_SERVICE_CLUSTER_LIST
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
        rest_data_present : () ->
            return icswMonitoringClusterRestService._rest_data_present(["device", "mon_service_templ", "mon_check_command"])
    }
    for k, v of icswMonitoringClusterRestService
        ret[k] = v
    return ret
]).service('icswMonitoringHostDependencyTemplateService', ["ICSW_URLS", "icswMonitoringClusterRestService", (ICSW_URLS, icswMonitoringClusterRestService) ->
    ret = {
        rest_url            : ICSW_URLS.REST_MON_HOST_DEPENDENCY_TEMPL_LIST
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
        rest_data_present : () ->
            return icswMonitoringClusterRestService._rest_data_present(["mon_period"])
    }

    for k, v of icswMonitoringClusterRestService
        ret[k] = v
    return ret
]).service('icswMonitoringServiceDependencyTemplateService', ["ICSW_URLS", "icswMonitoringClusterRestService", (ICSW_URLS, icswMonitoringClusterRestService) ->
    ret =  {
        rest_url            : ICSW_URLS.REST_MON_SERVICE_DEPENDENCY_TEMPL_LIST
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
        rest_data_present : () ->
            return icswMonitoringClusterRestService._rest_data_present(["mon_period"])
    }
    for k, v of icswMonitoringClusterRestService
        ret[k] = v
    return ret
]).service('icswMonitoringHostDependencyService', ["ICSW_URLS", "icswMonitoringClusterRestService", (ICSW_URLS, icswMonitoringClusterRestService) ->
    ret =  {
        rest_url            : ICSW_URLS.REST_MON_HOST_DEPENDENCY_LIST
        edit_template       : "mon.host.dependency.form"
        delete_confirm_str  : (obj) ->
            return "Really delete Host-dependency ?"
        new_object          : {}
        object_created  : (new_obj) ->
        rest_data_present : ($scope) ->
            return icswMonitoringClusterRestService._rest_data_present(["device", "mon_host_dependency_templ"])
    }
    for k, v of icswMonitoringClusterRestService
        ret[k] = v
    return ret
]).service('icswMonitoringServiceDependencyService', ["ICSW_URLS", "icswMonitoringClusterRestService", (ICSW_URLS, icswMonitoringClusterRestService) ->
    ret =  {
        rest_url            : ICSW_URLS.REST_MON_SERVICE_DEPENDENCY_LIST
        edit_template       : "mon.service.dependency.form"
        delete_confirm_str  : (obj) ->
            return "Really delete Service-dependency ?"
        new_object          : {}
        object_created  : (new_obj) ->
        rest_data_present : ($scope) ->
            return icswMonitoringClusterRestService._rest_data_present(["device", "mon_service_dependency_templ", "mon_check_command"])
    }
    for k, v of icswMonitoringClusterRestService
        ret[k] = v
    return ret
])
