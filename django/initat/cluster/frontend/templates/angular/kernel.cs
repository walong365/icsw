{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

kernel_module = angular.module("icsw.kernel", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "ip_filters", "localytics.directives", "restangular"])

angular_module_setup([kernel_module])

angular_add_simple_list_controller(
    kernel_module,
    "kernel_base",
    {
        rest_url            : "{% url 'rest:kernel_list' %}"
        edit_template       : "kernel.html"
        delete_confirm_str  : (obj) -> return "Really delete kernel '#{obj.name}' ?"
        template_cache_list : ["kernel_row.html", "kernel_head.html"]
    }
)

kernel_module.controller("kernel", ["$scope", "$compile", "$templateCache", "Restangular",
    ($scope, $compile, $templateCache, restangular) ->
        $scope.delete_ok = (obj) ->
            num_refs = obj.act_kernel.length + obj.new_kernel.length
            return if num_refs == 0 then true else false
        $scope.scan_for_kernels = () =>
            $.blockUI()
            $.ajax
                url     : "{% url 'setup:rescan_kernels' %}"
                title   : "scanning for new kernels"
                success : (xml) =>
                    $.unblockUI()
                    $scope.reload()
])

{% endinlinecoffeescript %}

</script>
