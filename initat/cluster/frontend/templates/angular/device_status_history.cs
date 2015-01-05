{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

{% verbatim %}
status_history_template = """
<h2>Status History</h2>

<b>{{devicepks}}</b>"
"""
{% endverbatim %}


status_history_module = angular.module("icsw.device.status_history", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select"])

angular_module_setup([status_history_module])

status_history_module.controller("status_history_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal) ->
]).directive("statushistory", ($templateCache) ->
    return {
        restrict : "EA"
{% verbatim %}
        template : $templateCache.get("status_history_template.html")
{% endverbatim %}
        link : (scope, el, attrs) ->
            scope.devicepks = attrs["devicepks"].split(',')
    }
).run(($templateCache) -> 
    $templateCache.put("status_history_template.html", status_history_template)
)

{% endinlinecoffeescript %}

</script>
