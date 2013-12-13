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


{% endinlinecoffeescript %}

</script>
