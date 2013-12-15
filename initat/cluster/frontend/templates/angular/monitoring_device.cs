{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

monitoring_device_module = angular.module("icsw.monitoring_device", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular"])

angular_module_setup([monitoring_device_module])

angular_add_simple_list_controller(
    monitoring_device_module,
    "mon_device_base",
    {
        rest_url            : "{% url 'rest:device_tree_list' %}"
        edit_template       : "monitoring_device.html"
        rest_map            : [
            {"short" : "mon_device_templ", "url" : "{% url 'rest:mon_device_templ_list' %}"}
            {"short" : "mon_ext_host"    , "url" : "{% url 'rest:mon_ext_host_list' %}"}
        ]
        delete_confirm_str  : (obj) -> return "Really delete monitoring period '#{obj.name}' ?"
        template_cache_list : ["mon_device_row.html", "mon_device_head.html"]
        md_cache_modes : {
            1 : "automatic (server)"
            2 : "never use cache"
            3 : "once (until successfull)"
        }
        fn:
            fetch : (edit_obj) ->
                $.blockUI()
                $.ajax
                    url     : "{% url 'mon:fetch_partition' %}"
                    data    : {
                        "pk" : edit_obj.idx
                    }
                    success : (xml) ->
                        $.unblockUI()
                        parse_xml_response(xml)              
    }
)

{% endinlinecoffeescript %}

</script>

