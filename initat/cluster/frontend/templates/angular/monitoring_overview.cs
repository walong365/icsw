{% load coffeescript %}

<script type="text/javascript">


{% inlinecoffeescript %}

{% verbatim %}

monitoring_overview_template = """
here
"""

{% endverbatim %}

root = exports ? this

monitoring_overview_module = angular.module("icsw.monitoring_overview", 
        ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "ui.bootstrap.datetimepicker"])

angular_module_setup([monitoring_overview_module])

monitoring_overview_module.controller("monitoring_overview_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "access_level_service", "$timeout",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, access_level_service, $timeout) ->
]).directive("monitoringoverview", ($templateCache) ->
    return {
        restrict : "EA"
        template: $templateCache.get("monitoring_overview_template.html")
        link : (scope, el, attrs) ->
}).run(($templateCache) ->
    $templateCache.put("monitoring_overview_template.html", monitoring_overview_template)
)


{% endinlinecoffeescript %}

</script>

