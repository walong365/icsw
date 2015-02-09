
monitoring_basic_module = angular.module("icsw.monitoring.monitoring_basic",
        ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "icsw.tools.table", "icsw.tools.button"])

monitoring_basic_module.directive("icswMonitoringBasic", () ->
    return {
        restrict:"EA"
        templateUrl: "icsw.monitoring.basic"
    }
).service('icswMonitoringBasicService', ["ICSW_URLS", (ICSW_URLS) ->
    get_use_count =  (obj) ->
            return obj.service_check_period.length# + obj.mon_device_templ_set.length
    return {
        rest_url           : ICSW_URLS.REST_MON_PERIOD_LIST
        delete_confirm_str : (obj) ->
            return "Really delete monitoring period '#{obj.name}' ?"
        edit_template      : "mon_period.html"
        new_object         : {
            "alias" : "new period", "mon_range" : "00:00-24:00", "tue_range" : "00:00-24:00", "sun_range" : "00:00-24:00",
            "wed_range" : "00:00-24:00", "thu_range" : "00:00-24:00", "fri_range" : "00:00-24:00", "sat_range" : "00:00-24:00"
        }
        object_created     : (new_obj) -> new_obj.name = ""
        get_use_count      : get_use_count
        delete_ok          : (obj) ->
            return get_use_count(obj) == 0
    }
]).service('icswMonitoringNotificationService', ["ICSW_URLS", (ICSW_URLS) ->
    return {
        rest_url            : ICSW_URLS.REST_MON_NOTIFICATION_LIST
        edit_template       : "mon_notification.html"
        delete_confirm_str  : (obj) ->
            return "Really delete monitoring notification '#{obj.name}' ?"
        new_object          : {"name" : "", "channel" : "mail", "not_type" : "service"}
        object_created      : (new_obj) -> new_obj.name = ""
    }
]).service('icswMonitoringContactService', ["ICSW_URLS", "Restangular", (ICSW_URLS, Restangular) ->
     get_rest = (url) -> return Restangular.all(url).getList().$object

     mon_period = get_rest(ICSW_URLS.REST_MON_PERIOD_LIST.slice(1))
     user = get_rest(ICSW_URLS.REST_USER_LIST.slice(1))
     mon_notification = get_rest(ICSW_URLS.REST_MON_NOTIFICATION_LIST.slice(1))

     return {
         rest_url            : ICSW_URLS.REST_MON_CONTACT_LIST
         edit_template       : "mon_contact.html"
         delete_confirm_str  : (obj) ->
             return "Really delete monitoring contact '#{obj.user}' ?"
         new_object          : () ->
             return {
                 "user" : (entry.idx for entry in user)[0]
                 "snperiod" : (entry.idx for entry in mon_period)[0]
                 "hnperiod" : (entry.idx for entry in mon_period)[0]
                 "snrecovery" : true
                 "sncritical" : true
                 "hnrecovery" : true
                 "hndown" : true
             }
         object_created    : (new_obj) -> new_obj.user = null
         mon_period        : mon_period
         user              : user
         mon_notification  : mon_notification
         rest_data_present : () ->
             ok = true
             for table in [mon_period, user]
                 if not table.length
                     ok = false
             return ok
    }
]).service('icswMonitoringServiceTemplateService', ["ICSW_URLS", "Restangular", (ICSW_URLS, Restangular) ->

    mon_period = Restangular.all(ICSW_URLS.REST_MON_PERIOD_LIST.slice(1)).getList().$object

    return {
        rest_url            : ICSW_URLS.REST_MON_SERVICE_TEMPL_LIST
        edit_template       : "mon_service_templ.html"
        delete_confirm_str  : (obj) ->
            return "Really delete service template '#{obj.name}' ?"
        new_object          : () ->
            return {
                "nsn_period" : (entry.idx for entry in mon_period)[0]
                "nsc_period" : (entry.idx for entry in mon_period)[0]
                "max_attempts" : 1
                "ninterval" : 2
                "check_interval" : 2
                "retry_interval" : 2
                "nrecovery" : true
                "ncritical" : true
                "low_flap_threshold" : 20
                "high_flap_threshold" : 80
                "freshness_threshold" : 60
            }
        object_created    : (new_obj) -> new_obj.name = null
        mon_period        : mon_period
        rest_data_present : () ->
            ok = true
            for table in [mon_period]
                if not table.length
                    ok = false
            return ok
    }
])
