
monitoring_cluster_module = angular.module("icsw.monitoring.escalation",
        ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "icsw.tools.table", "icsw.tools.button"])


monitoring_cluster_module.directive('icswMonitoringEscalation', () ->
    return {
        restrict     : "EA"
        templateUrl  : "icsw.monitoring.escalation"
    }
).service('icswMonitoringServiceEscalationService', ["ICSW_URLS", "Restangular", (ICSW_URLS, Restangular) ->
    get_rest = (url) -> return Restangular.all(url).getList().$object
    mon_period  = get_rest(ICSW_URLS.REST_MON_PERIOD_LIST.slice(1))

    return {
        rest_url            : ICSW_URLS.REST_MON_SERVICE_ESC_TEMPL_LIST
        edit_template       : "mon.service.esc.templ.form"
        mon_period          : mon_period
        delete_confirm_str  : (obj) ->
            return "Really delete Service escalation template '#{obj.name}' ?"
        new_object          : () ->
            return {
                "name" : ""
                "first_notification" : 1
                "last_notification" : 2
                "esc_period" : (entry.idx for entry in mon_period)[0]
                "ninterval" : 2
                "nrecovery" : true
                "ncritical" : true
            }
        object_created  : (new_obj) -> new_obj.name = ""
        rest_data_present : () ->
            ok = true
            for table in [mon_period]
                if not table.length
                    ok = false
            return ok
    }
]).service('icswMonitoringDeviceEscalationService', ["ICSW_URLS", "Restangular", (ICSW_URLS, Restangular) ->
    get_rest = (url) -> return Restangular.all(url).getList().$object
    mon_period            = get_rest(ICSW_URLS.REST_MON_PERIOD_LIST.slice(1))
    mon_service_esc_templ = get_rest(ICSW_URLS.REST_MON_SERVICE_ESC_TEMPL_LIST.slice(1))
    return  {
        rest_url              : ICSW_URLS.REST_MON_DEVICE_ESC_TEMPL_LIST
        edit_template         : "mon.device.esc.templ.form"
        mon_period            : mon_period
        mon_service_esc_templ : mon_service_esc_templ
        delete_confirm_str    : (obj) ->
            return "Really delete Device escalation template '#{obj.name}' ?"
        new_object          : () ->
            return {
                "name" : ""
                "first_notification" : 1
                "last_notification" : 2
                "esc_period" : (entry.idx for entry in mon_period)[0]
                "mon_service_esc_templ" : (entry.idx for entry in mon_service_esc_templ)[0]
                "ninterval" : 2
                "nrecovery" : true
                "ndown" : true
            }
        object_created  : (new_obj) -> new_obj.name = ""
        rest_data_present : ($scope) ->
            ok = true
            for table in [mon_period, mon_service_esc_templ]
                if not table.length
                    ok = false
            return ok
    }
])
