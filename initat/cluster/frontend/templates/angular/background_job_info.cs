{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

background_job_info_module = angular.module("icsw.background_job_info", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular"])

DT_FORM = "dd, D. MMM YYYY HH:mm:ss"

background_job_info_module.controller("info_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "access_level_service", "$timeout",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, access_level_service, $timeout) ->
        access_level_service.install($scope)
        $scope.pagSettings = paginatorSettings.get_paginator("jobs", $scope)
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
        $timeout($scope.reload, 5000)
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
])

{% endinlinecoffeescript %}

</script>
