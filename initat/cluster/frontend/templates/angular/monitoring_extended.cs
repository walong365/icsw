{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

monitoring_extended_module = angular.module("icsw.monitoring_extended", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular", "ui.select"])

angular_module_setup([monitoring_extended_module])

angular_add_simple_list_controller(
    monitoring_extended_module,
    "mon_host_cluster_base",
    {
        rest_url            : "{% url 'rest:mon_host_cluster_list' %}"
        edit_template       : "mon_host_cluster.html"
        rest_map            : [
            {"short" : "device"            , "url" : "{% url 'rest:device_tree_list' %}", "options" : {"ignore_meta_devices" : true, "ignore_selection" : true}}
            {"short" : "mon_service_templ" , "url" : "{% url 'rest:mon_service_templ_list' %}"}
        ]
        delete_confirm_str  : (obj) -> return "Really delete host cluster '#{obj.name}' ?"
        template_cache_list : ["mon_host_cluster_row.html", "mon_host_cluster_head.html"]
        new_object          : ($scope) ->
            return {
                "name" : ""
                "description" : "new host cluster"
                "mon_service_templ" : (entry.idx for entry in $scope.rest_data.mon_service_templ)[0]
                "warn_value" : 1
                "error_value" : 2
            }
        object_created  : (new_obj) -> new_obj.name = ""
        fn:
            rest_data_present : ($scope) ->
                ok = true
                for t_field in ["device", "mon_service_templ"]
                    if not $scope.rest_data[t_field].length
                        ok = false
                return ok
    }
)

monitoring_extended_module.controller("mon_host_cluster", ["$scope", "$compile", "$templateCache", "Restangular",
    ($scope, $compile, $templateCache, Restangular) ->
        $scope.delete_ok = (obj) ->
            return true
])

angular_add_simple_list_controller(
    monitoring_extended_module,
    "mon_service_cluster_base",
    {
        rest_url            : "{% url 'rest:mon_service_cluster_list' %}"
        edit_template       : "mon_service_cluster.html"
        rest_map            : [
            {"short" : "device"            , "url" : "{% url 'rest:device_tree_list' %}", "options" : {"ignore_meta_devices" : true, "ignore_selection" : true}}
            {"short" : "mon_service_templ" , "url" : "{% url 'rest:mon_service_templ_list' %}"}
            {"short" : "mon_check_command" , "url" : "{% url 'rest:mon_check_command_list' %}"}
        ]
        delete_confirm_str  : (obj) -> return "Really delete service cluster '#{obj.name}' ?"
        template_cache_list : ["mon_service_cluster_row.html", "mon_service_cluster_head.html"]
        new_object          : ($scope) ->
            return {
                "name" : ""
                "description" : "new service cluster"
                "mon_service_templ" : (entry.idx for entry in $scope.rest_data.mon_service_templ)[0]
                "mon_check_command" : (entry.idx for entry in $scope.rest_data.mon_check_command)[0]
                "warn_value" : 1
                "error_value" : 2
            }
        object_created  : (new_obj) -> new_obj.name = ""
        fn:
            rest_data_present : ($scope) ->
                ok = true
                for t_field in ["device", "mon_service_templ", "mon_check_command"]
                    if not $scope.rest_data[t_field].length
                        ok = false
                return ok
    }
)

monitoring_extended_module.controller("mon_service_cluster", ["$scope", "$compile", "$templateCache", "Restangular",
    ($scope, $compile, $templateCache, Restangular) ->
        $scope.delete_ok = (obj) ->
            return true
])

angular_add_simple_list_controller(
    monitoring_extended_module,
    "mon_host_dependency_templ_base",
    {
        rest_url            : "{% url 'rest:mon_host_dependency_templ_list' %}"
        edit_template       : "mon_host_dependency_templ.html"
        rest_map            : [
            {"short" : "mon_period"        , "url" : "{% url 'rest:mon_period_list' %}"}
        ]
        delete_confirm_str  : (obj) -> return "Really delete Host dependency template '#{obj.name}' ?"
        template_cache_list : ["mon_host_dependency_templ_row.html", "mon_host_dependency_templ_head.html"]
        new_object          : ($scope) ->
            return {
                "name" : ""
                "priority" : 0
                "dependency_period" : (entry.idx for entry in $scope.rest_data.mon_period)[0]
                "efc_up" : true
                "efc_down" : true
                "nfc_up" : true
                "nfc_down" : true
            }
        object_created  : (new_obj) -> new_obj.name = ""
        fn:
            rest_data_present : ($scope) ->
                ok = true
                for t_field in ["mon_period"]
                    if not $scope.rest_data[t_field].length
                        ok = false
                return ok
    }
)

monitoring_extended_module.controller("mon_host_dependency_templ", ["$scope", "$compile", "$templateCache", "Restangular",
    ($scope, $compile, $templateCache, Restangular) ->
        $scope.delete_ok = (obj) ->
            return true
])

angular_add_simple_list_controller(
    monitoring_extended_module,
    "mon_service_dependency_templ_base",
    {
        rest_url            : "{% url 'rest:mon_service_dependency_templ_list' %}"
        edit_template       : "mon_service_dependency_templ.html"
        rest_map            : [
            {"short" : "mon_period"        , "url" : "{% url 'rest:mon_period_list' %}"}
        ]
        delete_confirm_str  : (obj) -> return "Really delete Service dependency template '#{obj.name}' ?"
        template_cache_list : ["mon_service_dependency_templ_row.html", "mon_service_dependency_templ_head.html"]
        new_object          : ($scope) ->
            return {
                "name" : ""
                "priority" : 0
                "dependency_period" : (entry.idx for entry in $scope.rest_data.mon_period)[0]
                "efc_ok" : true
                "efc_warn" : true
                "nfc_ok" : true
                "nfc_warn" : true
            }
        object_created  : (new_obj) -> new_obj.name = ""
        fn:
            rest_data_present : ($scope) ->
                ok = true
                for t_field in ["mon_period"]
                    if not $scope.rest_data[t_field].length
                        ok = false
                return ok
    }
)

monitoring_extended_module.controller("mon_service_dependency_templ", ["$scope", "$compile", "$templateCache", "Restangular",
    ($scope, $compile, $templateCache, Restangular) ->
        $scope.delete_ok = (obj) ->
            return true
])

angular_add_simple_list_controller(
    monitoring_extended_module,
    "mon_service_esc_templ_base",
    {
        rest_url            : "{% url 'rest:mon_service_esc_templ_list' %}"
        edit_template       : "mon_service_esc_templ.html"
        rest_map            : [
            {"short" : "mon_period"        , "url" : "{% url 'rest:mon_period_list' %}"}
        ]
        delete_confirm_str  : (obj) -> return "Really delete Service escalation template '#{obj.name}' ?"
        template_cache_list : ["mon_service_esc_templ_row.html", "mon_service_esc_templ_head.html"]
        new_object          : ($scope) ->
            return {
                "name" : ""
                "first_notification" : 1
                "last_notification" : 2
                "esc_period" : (entry.idx for entry in $scope.rest_data.mon_period)[0]
                "ninterval" : 2
                "nrecovery" : true
                "ncritical" : true
            }
        object_created  : (new_obj) -> new_obj.name = ""
        fn:
            rest_data_present : ($scope) ->
                ok = true
                for t_field in ["mon_period"]
                    if not $scope.rest_data[t_field].length
                        ok = false
                return ok
    }
)

monitoring_extended_module.controller("mon_service_esc_templ", ["$scope", "$compile", "$templateCache", "Restangular",
    ($scope, $compile, $templateCache, Restangular) ->
        $scope.delete_ok = (obj) ->
            return true
])

angular_add_simple_list_controller(
    monitoring_extended_module,
    "mon_device_esc_templ_base",
    {
        rest_url            : "{% url 'rest:mon_device_esc_templ_list' %}"
        edit_template       : "mon_device_esc_templ.html"
        rest_map            : [
            {"short" : "mon_period"           , "url" : "{% url 'rest:mon_period_list' %}"}
            {"short" : "mon_service_esc_templ", "url" : "{% url 'rest:mon_service_esc_templ_list' %}"}
        ]
        delete_confirm_str  : (obj) -> return "Really delete Device escalation template '#{obj.name}' ?"
        template_cache_list : ["mon_device_esc_templ_row.html", "mon_device_esc_templ_head.html"]
        new_object          : ($scope) ->
            return {
                "name" : ""
                "first_notification" : 1
                "last_notification" : 2
                "esc_period" : (entry.idx for entry in $scope.rest_data.mon_period)[0]
                "mon_service_esc_templ" : (entry.idx for entry in $scope.rest_data.mon_service_esc_templ)[0]
                "ninterval" : 2
                "nrecovery" : true
                "ndown" : true
            }
        object_created  : (new_obj) -> new_obj.name = ""
        fn:
            rest_data_present : ($scope) ->
                ok = true
                for t_field in ["mon_period", "mon_service_esc_templ"]
                    if not $scope.rest_data[t_field].length
                        ok = false
                return ok
    }
)

monitoring_extended_module.controller("mon_device_esc_templ", ["$scope", "$compile", "$templateCache", "Restangular",
    ($scope, $compile, $templateCache, Restangular) ->
        $scope.delete_ok = (obj) ->
            return true
])

angular_add_simple_list_controller(
    monitoring_extended_module,
    "mon_host_dependency_base",
    {
        rest_url            : "{% url 'rest:mon_host_dependency_list' %}"
        edit_template       : "mon_host_dependency.html"
        rest_map            : [
            {"short" : "device"            , "url" : "{% url 'rest:device_tree_list' %}", "options" : {"ignore_meta_devices" : true, "ignore_selection" : true}}
            {"short" : "mon_host_dependency_templ", "url" : "{% url 'rest:mon_host_dependency_templ_list' %}"}
            {"short" : "mon_host_cluster", "url" : "{% url 'rest:mon_host_cluster_list' %}"}
        ]
        delete_confirm_str  : (obj) -> return "Really delete Host-dependency ?"
        template_cache_list : ["mon_host_dependency_row.html", "mon_host_dependency_head.html"]
        new_object          : {}
        object_created  : (new_obj) ->
        fn:
            rest_data_present : ($scope) ->
                ok = true
                for t_field in ["device", "mon_host_dependency_templ"]
                    if not $scope.rest_data[t_field].length
                        ok = false
                return ok
    }
)

monitoring_extended_module.controller("mon_host_dependency", ["$scope", "$compile", "$templateCache", "Restangular",
    ($scope, $compile, $templateCache, Restangular) ->
        $scope.delete_ok = (obj) ->
            return true
])

angular_add_simple_list_controller(
    monitoring_extended_module,
    "mon_service_dependency_base",
    {
        rest_url            : "{% url 'rest:mon_service_dependency_list' %}"
        edit_template       : "mon_service_dependency.html"
        rest_map            : [
            {"short" : "device"            , "url" : "{% url 'rest:device_tree_list' %}", "options" : {"ignore_meta_devices" : true, "ignore_selection" : true}}
            {"short" : "mon_service_dependency_templ", "url" : "{% url 'rest:mon_service_dependency_templ_list' %}"}
            {"short" : "mon_check_command"  , "url" : "{% url 'rest:mon_check_command_list' %}"}
            {"short" : "mon_service_cluster", "url" : "{% url 'rest:mon_service_cluster_list' %}"}
        ]
        delete_confirm_str  : (obj) -> return "Really delete Service-dependency ?"
        template_cache_list : ["mon_service_dependency_row.html", "mon_service_dependency_head.html"]
        new_object          : {}
        object_created  : (new_obj) ->
        fn:
            rest_data_present : ($scope) ->
                ok = true
                for t_field in ["device", "mon_service_dependency_templ", "mon_check_command"]
                    if not $scope.rest_data[t_field].length
                        ok = false
                return ok
    }
)

monitoring_extended_module.controller("mon_service_dependency", ["$scope", "$compile", "$templateCache", "Restangular",
    ($scope, $compile, $templateCache, Restangular) ->
        $scope.delete_ok = (obj) ->
            return true
])

{% endinlinecoffeescript %}

</script>

