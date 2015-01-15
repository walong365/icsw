{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

monitoring_overview_module = angular.module("icsw.monitoring_overview", 
        ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "ui.bootstrap.datetimepicker", "smart-table", "smart_table_utils", "status_utils"])

angular_module_setup([monitoring_overview_module])

monitoring_overview_module.controller("monitoring_overview_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "access_level_service", "$timeout",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, access_level_service, $timeout) ->
        $scope.filter_settings = {"str_filter": ""}

        $scope.filter_predicate = (entry) ->
            try
                str_re = new RegExp($scope.filter_settings.str_filter, "gi")
            catch err
                str_re = new RegExp("^$", "gi")

            # string filter
            sf_flag = entry.name.match(str_re)

            return sf_flag

        wait_list = restDataSource.add_sources([
            ["{% url 'rest:device_list' %}", {}],
        ])
        $q.all(wait_list).then( (data) ->
            $scope.device_list = data[0]
            $scope.update_data()
        )

        $scope.yesterday = moment().subtract(1, "days")
        $scope.last_week = moment().subtract(1, "weeks")

        $scope.entries = []
        $scope.$watch(
                () -> [$scope.entries, $scope.filter_settings]
                () ->
                    $scope.entries_filtered = (entry for entry in $scope.entries when $scope.filter_predicate(entry))
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
        templateUrl: "monitoring_overview_template.html"
        link : (scope, el, attrs) ->
}).run(($templateCache) ->
)

{% endinlinecoffeescript %}

</script>
