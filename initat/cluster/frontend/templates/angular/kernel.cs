{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

kernel_module = angular.module("icsw.kernel", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular"])

DT_FORM = "YYYY-MM-DD HH:mm"

angular_add_simple_list_controller(
    kernel_module,
    "kernel_base",
    {
        rest_url            : "{% url 'rest:kernel_list' %}"
        edit_template       : "kernel.html"
        delete_confirm_str  : (obj) -> return "Really delete kernel '#{obj.name}' ?"
        template_cache_list : ["kernel_row.html", "kernel_head.html"]
        fn : 
            get_initrd_built : (kernel) ->
                if kernel.initrd_built
                    return moment(kernel.initrd_built).format(DT_FORM)
                else
                    return "N/A"
            get_flag_value : (kernel, flag_name) ->
                return if kernel[flag_name] then "yes" else "no"
    }
)

kernel_module.controller("kernel", ["$scope", "$compile", "$templateCache", "Restangular", "blockUI",
    ($scope, $compile, $templateCache, restangular, blockUI) ->
        $scope.delete_ok = (obj) ->
            num_refs = obj.act_kernel.length + obj.new_kernel.length
            return if num_refs == 0 then true else false
        $scope.scan_for_kernels = () =>
            blockUI.start()
            call_ajax
                url     : "{% url 'setup:rescan_kernels' %}"
                title   : "scanning for new kernels"
                success : (xml) =>
                    blockUI.stop()
                    $scope.reload()
])

{% endinlinecoffeescript %}

</script>
