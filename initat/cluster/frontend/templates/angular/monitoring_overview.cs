{% load coffeescript %}

<script type="text/javascript">


{% inlinecoffeescript %}

{% verbatim %}

monitoring_overview_template = """

<div class="panel panel-default" style="width: auto">
    <div class="panel-body">
        <!-- entries_displayed is st-table interal -->
        <table st-table="entries_displayed" st-safe-src="entries_filtered" class="table table-hover table-condensed table-striped" style="width:auto;">
            <thead>
                <tr>
                    <td colspan="99">
                        <div icsw-pagination="" st-items-by-page="10" st-displayed-pages="11" possible-items-by-page="2,5,10,20,50,100,200,500,1000"></div>
                    </td>
                </tr>
                <tr>
                    <th st-sort='name'>Name</th>
                    <!-- todo: sort -->
                    <th>Now</th>
                    <th>Yesterday</th>
                    <th>Last Week</th>
                <tr>
            </thead>
            <tbody>
                <tr ng-repeat="entry in entries_displayed">
                    <td>{{entry.name}}
                    <td>TBD</td>
                    <td>
                        <div>
                            <device-hist-status-overview deviceid="entry.idx" startdate="yesterday" timerange="'day'" show-table="false"></device-hist-status-overview>
                        </div>
                    </td>
                    <td>
                        <div>
                            <device-hist-status-overview deviceid="entry.idx" startdate="last_week" timerange="'week'" show-table="false"></device-hist-status-overview>
                        </div>
                    </td>
                    <td>
                        {{entry}}
                    </td>
                </tr>
            </tbody>
        </table>
    </div>
</div>
"""

{% endverbatim %}

root = exports ? this

monitoring_overview_module = angular.module("icsw.monitoring_overview", 
        ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "ui.bootstrap.datetimepicker", "smart-table", "smart_table_utils", "status_utils"])

angular_module_setup([monitoring_overview_module])

monitoring_overview_module.controller("monitoring_overview_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "access_level_service", "$timeout",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, access_level_service, $timeout) ->
        wait_list = restDataSource.add_sources([
            ["{% url 'rest:device_list' %}", {}],
        ])
        $q.all(wait_list).then( (data) ->
            $scope.device_list = data[0]
            $scope.update_data()
        )

        $scope.yesterday = moment().subtract(1, 'days')
        $scope.last_week = moment().subtract(1, 'weeks')

        $scope.entries = []
        $scope.$watch(
                () -> $scope.entries
                () ->
                    $scope.entries_filtered = (entry for entry in $scope.entries when true)
                true)

        $scope.update_data = () ->

            new_entries = []
            for dev in $scope.device_list
                new_entries.push({
                    'idx': dev.idx
                    'name': dev.name
                })
            $scope.entries = new_entries

            call_ajax
                url  : "{% url 'mon:get_node_status' %}"
                data : {
                    "pk_list" : angular.toJson((dev.idx for dev in $scope.device_list))
                }
                success : (xml) =>
                    if parse_xml_response(xml)
                        service_entries = []
                        $(xml).find("value[name='service_result']").each (idx, node) =>
                            service_entries = service_entries.concat(angular.fromJson($(node).text()))
                        host_entries = []
                        $(xml).find("value[name='host_result']").each (idx, node) =>
                            host_entries = host_entries.concat(angular.fromJson($(node).text()))
                        console.log 'serv', service_entries
                        console.log 'host', host_entries

]).directive("monitoringoverview", ($templateCache, $timeout) ->
    return {
        restrict : "EA"
        template: $templateCache.get("monitoring_overview_template.html")
        link : (scope, el, attrs) ->

            
}).run(($templateCache) ->
    $templateCache.put("monitoring_overview_template.html", monitoring_overview_template)
)


{% endinlinecoffeescript %}

</script>

