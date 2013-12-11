{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

monitoring_extended_module = angular.module("icsw.monitoring_extended", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular"])

angular_module_setup([monitoring_extended_module])

angular_add_simple_list_controller(
    monitoring_extended_module,
    "mon_host_cluster_base",
    {
        rest_url            : "{% url 'rest:mon_host_cluster_list' %}"
        edit_template       : "mon_host_cluster.html"
        rest_map            : [
            {"short" : "device"            , "url" : "{% url 'rest:device_list' %}"}
            {"short" : "mon_service_templ" , "url" : "{% url 'rest:mon_service_templ_list' %}"}
        ]
        delete_confirm_str  : (obj) -> return "Really delete host cluster '#{obj.name}' ?"
        template_cache_list : ["mon_host_cluster_row.html", "mon_host_cluster_head.html"]
        new_object          : {"name" : "", "description" : "new host cluster"},
        new_object_created  : (new_obj) -> new_obj.name = ""
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
            {"short" : "device"            , "url" : "{% url 'rest:device_list' %}"}
            {"short" : "mon_service_templ" , "url" : "{% url 'rest:mon_service_templ_list' %}"}
            {"short" : "mon_check_command" , "url" : "{% url 'rest:mon_check_command_list' %}"}
        ]
        delete_confirm_str  : (obj) -> return "Really delete service cluster '#{obj.name}' ?"
        template_cache_list : ["mon_service_cluster_row.html", "mon_service_cluster_head.html"]
        new_object          : {"name" : "", "description" : "new service cluster"},
        new_object_created  : (new_obj) -> new_obj.name = ""
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
        new_object          : {"name" : "", "priority" : 0}
        new_object_created  : (new_obj) -> new_obj.name = ""
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
        new_object          : {"name" : "", "priority" : 0}
        new_object_created  : (new_obj) -> new_obj.name = ""
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
        new_object          : {"name" : ""}
        new_object_created  : (new_obj) -> new_obj.name = ""
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
        new_object          : {"name" : ""}
        new_object_created  : (new_obj) -> new_obj.name = ""
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
            {"short" : "device"            , "url" : "{% url 'rest:device_list' %}"}
            {"short" : "mon_host_dependency_templ", "url" : "{% url 'rest:mon_host_dependency_templ_list' %}"}
            {"short" : "mon_host_cluster", "url" : "{% url 'rest:mon_host_cluster_list' %}"}
        ]
        delete_confirm_str  : (obj) -> return "Really delete Host-dependency ?"
        template_cache_list : ["mon_host_dependency_row.html", "mon_host_dependency_head.html"]
        new_object          : {}
        new_object_created  : (new_obj) ->
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
            {"short" : "device"             , "url" : "{% url 'rest:device_list' %}"}
            {"short" : "mon_service_dependency_templ", "url" : "{% url 'rest:mon_service_dependency_templ_list' %}"}
            {"short" : "mon_check_command"  , "url" : "{% url 'rest:mon_check_command_list' %}"}
            {"short" : "mon_service_cluster", "url" : "{% url 'rest:mon_service_cluster_list' %}"}
        ]
        delete_confirm_str  : (obj) -> return "Really delete Service-dependency ?"
        template_cache_list : ["mon_service_dependency_row.html", "mon_service_dependency_head.html"]
        new_object          : {}
        new_object_created  : (new_obj) ->
    }
)

monitoring_extended_module.controller("mon_service_dependency", ["$scope", "$compile", "$templateCache", "Restangular",
    ($scope, $compile, $templateCache, Restangular) ->
        $scope.delete_ok = (obj) ->
            return true
])

{% endinlinecoffeescript %}

</script>

