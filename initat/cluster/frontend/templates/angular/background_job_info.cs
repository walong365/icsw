{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

{% verbatim %}
my_pag_code = """
<div class="ng-cloak ng-table-pager">
    <div ng-if="params.settings().counts.length" class="ng-table-counts btn-group pull-right">
        <button ng-repeat="count in params.settings().counts" type="button" ng-class="{\'active\':params.count()==count}" ng-click="params.count(count)" class="btn btn-default">
            <span ng-bind="count"></span>a
        </button>
    </div>
    <ul class="pagination pagination-sm ng-table-pagination">
        <li ng-class="{\'disabled\': !page.active}" ng-repeat="page in pages" ng-switch="page.type">
            <a ng-switch-when="prev" ng-click="params.page(page.number)" href="">&laquo;</a>
            <a ng-switch-when="first" ng-click="params.page(page.number)" href="">
                <span ng-bind="page.number"></span>
            </a>
            <a ng-switch-when="page" ng-click="params.page(page.number)" href="">
                <span ng-bind="page.number"></span>
            </a>
            <a ng-switch-when="more" ng-click="params.page(page.number)" href="">&#8230;</a>
            <a ng-switch-when="last" ng-click="params.page(page.number)" href="">
                <span ng-bind="page.number"></span>
            </a> 
            <a ng-switch-when="next" ng-click="params.page(page.number)" href="">&raquo;</a>
        </li>
    </ul>
</div>
"""
{% endverbatim %}

root = exports ? this

background_job_info_module = angular.module("icsw.background_job_info", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular", "ngTable"])

angular_module_setup([background_job_info_module])

DT_FORM = "dd, D. MMM YYYY HH:mm:ss"

background_job_info_module.controller("info_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "access_level_service", "$timeout", "ngTableParams",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, access_level_service, $timeout, ngTableParams) ->
        access_level_service.install($scope)
        $scope.pagSettings = paginatorSettings.get_paginator("jobs", $scope)
        $scope.table = new ngTableParams(
            {
                page : 1,
                count : 10,
                sorting : {
                   "idx" : "desc",
                }
            },
            {
                counts : [10, 25, 50],
                total : 0
                getData : ($defer, params) ->
                    restDataSource.reset()
                    wait_list = restDataSource.add_sources([
                        ["{% url 'rest:background_job_list' %}", {}]
                    ])
                    $q.all(wait_list).then((data) ->
                        _data = data[0]
                        params.total(_data.length)
                        _data = if params.sorting() then $filter("orderBy")(_data, params.orderBy()) else _data
                        _data = _data.slice((params.page() - 1) * params.count(), params.page() * params.count())
                        $defer.resolve(_data)
                    )
            }
        )
        # not working right now
        #$timeout($scope.table.reload, 1000)
        $scope.jobs = []
        $scope.reload = () ->
            # force reload
            restDataSource.reset()
            wait_list = restDataSource.add_sources([
                ["{% url 'rest:background_job_list' %}", {}]
            ])
            $q.all(wait_list).then((data) ->
                $scope.jobs = data[0]
            )
        $scope.get_diff_time = (dt) ->
            if dt
                return moment(dt).fromNow()
            else
                return "???"
        $scope.get_time = (dt) ->
            if dt
                return moment(dt).format(DT_FORM)
            else
                return "---"
        $scope._runtime = (diff) ->
            if diff
                # seconds
                return diff + "s"
            else
                return "< 1s"
        $scope.get_line_class = (job) ->
            return ""
        $scope.reload()
]).run(($templateCache) ->
    $templateCache.put("ng-table/pager.html", my_pag_code)
)

{% endinlinecoffeescript %}

</script>

