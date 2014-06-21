{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

background_job_info_module = angular.module("icsw.background_job_info", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular"])

angular_module_setup([background_job_info_module])

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
                #["{% url 'rest:mon_dist_slave_list' %}", {}]
            ])
            $q.all(wait_list).then((data) ->
                $timeout($scope.reload, 5000)
                $scope.jobs = data[0]
                #console.log $scope.jobs
                #$scope.servers = build_lut(data[1])
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
        $scope.get_run_time = (master) ->
            if master.build_start and master.build_end
                return $scope._runtime(moment(master.build_end).diff(moment(master.build_start), "seconds"))
            else
                return "---"
        $scope.get_sync_time = (slave) ->
            if slave
                if slave.sync_end and slave.sync_start
                    return $scope._runtime(moment(slave.sync_end).diff(moment(slave.sync_start), "seconds"))
                else
                    return "---"
            else
                return "---"
        $scope.get_conf_time = (obj) ->
            if obj
                if obj.config_build_end and obj.config_build_start
                    return $scope._runtime(moment(obj.config_build_end).diff(moment(obj.config_build_start), "seconds"))
                else
                    return "---"
            else
                return "---"
        $scope.get_line_class = (job) ->
            return ""
        $scope.reload()
])

{% endinlinecoffeescript %}

</script>

