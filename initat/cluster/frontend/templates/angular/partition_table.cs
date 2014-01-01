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
        use_modal           : false
        template_cache_list : ["partition_table_row.html", "partition_table_head.html"]
        post_delete : ($scope) ->
            $scope.close_modal()
    }
)

partition_table_module.directive("layout", ($compile, $templateCache) ->
    return {
        restrict : "EA"
        scope :
            layout : "=layout"
        #template : $templateCache.get("layout.html")
        compile: (tElement, tAttrs) ->
            return (scope, element, attrs) ->
                element.replaceWith($compile($templateCache.get("layout.html"))(scope))
    }
)

partition_table_module.directive("partclean", ($compile, $templateCache) ->
    return {
        restrict : "EA"
        replace : true
        compile: (tElement, tAttrs) ->
            return (scope, element, attrs) ->
                # dirty but working
                element.parent().find("tr[class*='icsw_dyn']").remove()
    }
)

partition_table_module.directive("partdisc", ($compile, $templateCache) ->
    return {
        restrict : "EA"
        replace : true
        compile: (tElement, tAttrs) ->
            return (scope, element, attrs) ->
                element.replaceWith($compile($templateCache.get("part_disc.html"))(scope))
    }
)

partition_table_module.directive("part", ($compile, $templateCache) ->
    return {
        restrict : "EA"
        compile: (tElement, tAttrs) ->
            return (scope, element, attrs) ->
                # console.log scope, element, attrs, scope.layout
                element.replaceWith($compile($templateCache.get("part.html"))(scope))
    }
)

partition_table_module.directive("partsys", ($compile, $templateCache) ->
    return {
        restrict : "EA"
        compile: (tElement, tAttrs) ->
            return (scope, element, attrs) ->
                # console.log scope, element, attrs, scope.layout
                element.replaceWith($compile($templateCache.get("sys_part.html"))(scope))
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
