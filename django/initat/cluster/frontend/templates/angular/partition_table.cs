{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

partition_table_module = angular.module("icsw.partition_table", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular"])

angular_module_setup([partition_table_module])

angular_add_simple_list_controller(
    partition_table_module,
    "partition_table_base",
    {
        rest_url            : "{% url 'rest:partition_table_list' %}"
        edit_template       : "partition_table.html"
        delete_confirm_str  : (obj) -> return "Really delete partition table '#{obj.name}' ?"
        template_cache_list : ["partition_table_row.html", "partition_table_head.html"]
    }
)

partition_table_module.controller("partition_table", ["$scope", "$compile", "$templateCache", "Restangular",
    ($scope, $compile, $templateCache, Restangular) ->
        $scope.delete_ok = (obj) ->
            num_refs = obj.act_partition_table.length + obj.new_partition_table.length
            return if num_refs == 0 then true else false
])

{% endinlinecoffeescript %}

</script>
