{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

device_module = angular.module("icsw.device", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular"])

angular_module_setup([device_module])

angular_add_simple_list_controller(
    device_module,
    "device_base",
    {
        rest_url            : "{% url 'rest:device_list' %}"
        delete_confirm_str  : (obj) -> return "Really delete Device '#{obj.name}' ?"
        template_cache_list : ["device_row.html", "device_head.html"]
    }
)

angular_add_simple_list_controller(
    device_module,
    "device_sel_base",
    {
        rest_url            : "{% url 'rest:device_tree_list' %}"
        delete_confirm_str  : (obj) -> return "Really delete Device '#{obj.name}' ?"
        template_cache_list : ["device_sel_row.html", "device_sel_head.html"]
    }
)

angular_add_simple_list_controller(
    device_module,
    "device_tree_base",
    {
        rest_url            : "{% url 'rest:device_tree_list' %}"
        rest_options        : {"all_devices" : true, "ignore_cdg" : false}
        rest_map            : [
            {"short" : "device_group", "url" : "{% url 'rest:device_group_list' %}"}
            {"short" : "device_type", "url" : "{% url 'rest:device_type_list' %}"}
            {"short" : "mother_server", "url" : "{% url 'rest:device_tree_list' %}", "options" : {"all_mother_servers" : true}}
            {"short" : "monitor_server", "url" : "{% url 'rest:device_tree_list' %}", "options" : {"all_monitoring_servers" : true}}
            {"short" : "domain_tree_node", "url" : "{% url 'rest:domain_tree_node_list' %}"}
        ]
        delete_confirm_str  : (obj) -> return "Really delete Device '#{obj.name}' ?"
        template_cache_list : ["device_tree_head.html"]
        md : true
        filter_settings: {"md" : "a"}
        fn:
            rest_data_set: ($scope) ->
                $scope.device_lut = build_lut($scope.entries)
                $scope.device_group_lut = build_lut($scope.rest_data.device_group)
            get_tr_class: (obj) ->
                return if obj.is_meta_device then "success" else ""
            filter: (entry, a) ->
                md_list = {
                    "a" : [true, false]
                    "d" : [false]
                    "g" : [true]
                }[a.pagSettings.conf.filter_settings.md]
                return entry.is_meta_device in md_list
    }
)

device_module.directive("devicetreerow", ($templateCache, $compile) ->
    return {
        restrict : "EA"
        link : (scope, element, attrs) ->
            scope.device_group = scope.device_group_lut[scope.obj.device_group]
            if scope.obj.is_meta_device
                scope.device_group.num_devices = (entry for entry in scope.entries when entry.device_group == scope.obj.device_group).length - 1
                new_el = $compile($templateCache.get("device_tree_meta_row.html"))
            else
                new_el = $compile($templateCache.get("device_tree_row.html"))
            element.append(new_el(scope))
    }
)

{% endinlinecoffeescript %}

</script>
