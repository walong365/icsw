{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

monitoring_basic_module = angular.module("icsw.monitoring_basic", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select"])

angular_add_simple_list_controller(
    monitoring_basic_module,
    "mon_period_base",
    {
        rest_url            : "{% url 'rest:mon_period_list' %}"
        edit_template       : "mon_period.html"
        delete_confirm_str  : (obj) -> return "Really delete monitoring period '#{obj.name}' ?"
        template_cache_list : ["mon_period_row.html", "mon_period_head.html"]
        new_object          : {
            "alias" : "new period", "mon_range" : "00:00-24:00", "tue_range" : "00:00-24:00", "sun_range" : "00:00-24:00",
            "wed_range" : "00:00-24:00", "thu_range" : "00:00-24:00", "fri_range" : "00:00-24:00", "sat_range" : "00:00-24:00"
        }
        object_created  : (new_obj) -> new_obj.name = ""
    }
)

monitoring_basic_module.controller("mon_period", ["$scope", "$compile", "$templateCache", "Restangular",
    ($scope, $compile, $templateCache, Restangular) ->
        $scope.get_usecount = (obj) ->
            return obj.service_check_period.length# + obj.mon_device_templ_set.length
        $scope.delete_ok = (obj) ->
            return if $scope.get_usecount(obj) == 0 then true else false
])

angular_add_simple_list_controller(
    monitoring_basic_module,
    "mon_notification_base",
    {
        rest_url            : "{% url 'rest:mon_notification_list' %}"
        edit_template       : "mon_notification.html"
        delete_confirm_str  : (obj) -> return "Really delete monitoring notification '#{obj.name}' ?"
        template_cache_list : ["mon_notification_row.html", "mon_notification_head.html"]
        new_object          : {"name" : "", "channel" : "mail", "not_type" : "service"}
        object_created  : (new_obj) -> new_obj.name = ""
    }
)

monitoring_basic_module.controller("mon_notification", ["$scope", "$compile", "$templateCache", "Restangular",
    ($scope, $compile, $templateCache, Restangular) ->
        $scope.delete_ok = (obj) ->
            return true
])


angular_add_simple_list_controller(
    monitoring_basic_module,
    "mon_contact_base",
    {
        rest_url            : "{% url 'rest:mon_contact_list' %}"
        edit_template       : "mon_contact.html"
        rest_map            : [
            {"short" : "mon_period"      , "url" : "{% url 'rest:mon_period_list' %}"}
            {"short" : "user"            , "url" : "{% url 'rest:user_list' %}"}
            {"short" : "mon_notification", "url" : "{% url 'rest:mon_notification_list' %}"}
        ]
        delete_confirm_str  : (obj) -> return "Really delete monitoring contact '#{obj.user}' ?"
        template_cache_list : ["mon_contact_row.html", "mon_contact_head.html"]
        new_object          : ($scope) ->
            return {
                "user" : (entry.idx for entry in $scope.rest_data.user)[0]
                "snperiod" : (entry.idx for entry in $scope.rest_data.mon_period)[0]
                "hnperiod" : (entry.idx for entry in $scope.rest_data.mon_period)[0]
                "snrecovery" : true
                "sncritical" : true
                "hnrecovery" : true
                "hndown" : true
            }
        object_created  : (new_obj) -> new_obj.user = null
        fn:
            rest_data_present : ($scope) ->
                ok = true
                for t_field in ["mon_period", "user"]
                    if not $scope.rest_data[t_field].length
                        ok = false
                return ok
    }
)

monitoring_basic_module.controller("mon_contact", ["$scope", "$compile", "$templateCache", "Restangular",
    ($scope, $compile, $templateCache, Restangular) ->
        $scope.delete_ok = (obj) ->
            return true
])

angular_add_simple_list_controller(
    monitoring_basic_module,
    "mon_service_templ_base",
    {
        rest_url            : "{% url 'rest:mon_service_templ_list' %}"
        edit_template       : "mon_service_templ.html"
        rest_map            : [
            {"short" : "mon_period", "url" : "{% url 'rest:mon_period_list' %}"}
        ]
        delete_confirm_str  : (obj) -> return "Really delete service template '#{obj.name}' ?"
        template_cache_list : ["mon_service_templ_row.html", "mon_service_templ_head.html"]
        new_object          : ($scope) ->
            return {
                "nsn_period" : (entry.idx for entry in $scope.rest_data.mon_period)[0]
                "nsc_period" : (entry.idx for entry in $scope.rest_data.mon_period)[0]
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
        object_created  : (new_obj) -> new_obj.name = null
        fn:
            rest_data_present : ($scope) ->
                ok = true
                for t_field in ["mon_period"]
                    if not $scope.rest_data[t_field].length
                        ok = false
                return ok
    }
)

monitoring_basic_module.controller("mon_service_templ", ["$scope", "$compile", "$templateCache", "Restangular",
    ($scope, $compile, $templateCache, Restangular) ->
        $scope.delete_ok = (obj) ->
            return true
])

angular_add_simple_list_controller(
    monitoring_basic_module,
    "host_check_command_base",
    {
        rest_url            : "{% url 'rest:host_check_command_list' %}"
        edit_template       : "host_check_command.html"
        delete_confirm_str  : (obj) -> return "Really delete host check command '#{obj.name}' ?"
        template_cache_list : ["host_check_command_row.html", "host_check_command_head.html"]
        new_object          : {"name" : ""}
        object_created  : (new_obj) -> new_obj.name = null
    }
)

monitoring_basic_module.controller("host_check_command", ["$scope", "$compile", "$templateCache", "Restangular",
    ($scope, $compile, $templateCache, Restangular) ->
        $scope.delete_ok = (obj) ->
            return true
])

angular_add_simple_list_controller(
    monitoring_basic_module,
    "mon_contactgroup_base",
    {
        rest_url            : "{% url 'rest:mon_contactgroup_list' %}"
        edit_template       : "mon_contactgroup.html"
        rest_map            : [
            {"short" : "mon_contact"      , "url" : "{% url 'rest:mon_contact_list' %}"}
            {"short" : "user"             , "url" : "{% url 'rest:user_list' %}"}
            {"short" : "device_group"     , "url" : "{% url 'rest:device_group_list' %}"}
            {"short" : "mon_service_templ", "url" : "{% url 'rest:mon_service_templ_list' %}"}
        ]
        delete_confirm_str  : (obj) -> return "Really delete Contactgroup '#{obj.name}' ?"
        template_cache_list : ["mon_contactgroup_row.html", "mon_contactgroup_head.html"]
        new_object          : {"name" : ""}
        object_created  : (new_obj) -> new_obj.name = null
    }
)

monitoring_basic_module.controller("mon_contactgroup", ["$scope", "$compile", "$templateCache", "Restangular",
    ($scope, $compile, $templateCache, Restangular) ->
        $scope.delete_ok = (obj) ->
            return true
])

angular_add_simple_list_controller(
    monitoring_basic_module,
    "mon_device_templ_base",
    {
        rest_url            : "{% url 'rest:mon_device_templ_list' %}"
        edit_template       : "mon_device_templ.html"
        rest_map            : [
            {"short" : "mon_period"        , "url" : "{% url 'rest:mon_period_list' %}"}
            {"short" : "mon_service_templ" , "url" : "{% url 'rest:mon_service_templ_list' %}"}
            {"short" : "host_check_command", "url" : "{% url 'rest:host_check_command_list' %}"}
        ]
        delete_confirm_str  : (obj) -> return "Really delete device template '#{obj.name}' ?"
        template_cache_list : ["mon_device_templ_row.html", "mon_device_templ_head.html"]
        new_object          : ($scope) ->
            return {
                "mon_service_templ" : (entry.idx for entry in $scope.rest_data.mon_service_templ)[0]
                "host_check_command" : (entry.idx for entry in $scope.rest_data.host_check_command)[0]
                "mon_period" : (entry.idx for entry in $scope.rest_data.mon_period)[0]
                "not_period" : (entry.idx for entry in $scope.rest_data.mon_period)[0]
                "max_attempts" : 1
                "ninterval" : 5
                "check_interval" : 2
                "retry_interval" : 2
                "nrecovery" : true
                "ndown"     : true
                "ncritical" : true
                "low_flap_threshold" : 20
                "high_flap_threshold" : 80
                "freshness_threshold" : 60
            }
        object_created  : (new_obj) -> new_obj.name = null
        fn:
            rest_data_present : ($scope) ->
                ok = true
                for t_field in ["mon_period", "mon_service_templ", "host_check_command"]
                    if not $scope.rest_data[t_field].length
                        ok = false
                return ok
    }
)

monitoring_basic_module.controller("mon_device_templ", ["$scope", "$compile", "$templateCache", "Restangular",
    ($scope, $compile, $templateCache, Restangular) ->
        $scope.delete_ok = (obj) ->
            return true
])

{% endinlinecoffeescript %}

</script>
