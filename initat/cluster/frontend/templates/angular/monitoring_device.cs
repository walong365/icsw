{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

monitoring_device_module = angular.module("icsw.monitoring_device", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular", "ui.select"])

angular_module_setup([monitoring_device_module])

angular_add_simple_list_controller(
    monitoring_device_module,
    "mon_device_base",
    {
        rest_url            : "{% url 'rest:device_tree_list' %}"
        rest_options        : {"ignore_meta_devices" : true, "olp" : "backbone.device.change_monitoring"}
        edit_template       : "monitoring_device.html"
        rest_map            : [
            {"short" : "mon_device_templ", "url" : "{% url 'rest:mon_device_templ_list' %}"}
            {"short" : "mon_ext_host"    , "url" : "{% url 'rest:mon_ext_host_list' %}"}
            {"short" : "mon_server"      , "url" : "{% url 'rest:device_tree_list' %}", "options" : {"monitor_server_type" : true}}
        ]
        template_cache_list : ["mon_device_head.html"]
        md_cache_modes : [
            {"idx" : 1, "name" : "automatic (server)"} 
            {"idx" : 2, "name" : "never use cache"} 
            {"idx" : 3, "name" : "once (until successfull)"} 
        ]
        init_fn: ($scope, $timeout) ->
            install_devsel_link($scope.reload, false)
        fn:
            fetch : (edit_obj) ->
                $.blockUI()
                call_ajax
                    url     : "{% url 'mon:fetch_partition' %}"
                    data    : {
                        "pk" : edit_obj.idx
                    }
                    success : (xml) ->
                        $.unblockUI()
                        parse_xml_response(xml)   
    }
)

monitoring_device_module.directive("mondevicerow", ($templateCache, $compile) ->
    return {
        restrict : "EA"
        link : (scope, element, attrs) ->
            if scope.obj.is_meta_device
                new_el = $compile($templateCache.get("mon_meta_device_row.html"))
            else
                new_el = $compile($templateCache.get("mon_device_row.html"))
            element.append(new_el(scope))
    }
)

{% endinlinecoffeescript %}

</script>

