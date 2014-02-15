{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

monitoring_build_info_module = angular.module("icsw.monitoring_build_info", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular"])

angular_module_setup([monitoring_build_info_module])

DT_FORM = "dd, D. MMM YYYY HH:mm:ss"

monitoring_build_info_module.controller("info_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "access_level_service",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, access_level_service) ->
        access_level_service.install($scope)
        $scope.pagSettings = paginatorSettings.get_paginator("masters", $scope)
        $scope.masters = []
        $scope.slaves = []
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
        $scope.get_runtime = (master) ->
            if master.build_start and master.build_end
                diff = moment(master.build_end).diff(moment(master.build_start), "seconds")
                if diff
                    # seconds
                    return diff
                else
                    return "< 1"
            else
                return "---"
        $scope.reload = () ->
            wait_list = restDataSource.add_sources([
                ["{% url 'rest:mon_dist_master_list' %}", {}]
                #["{% url 'rest:mon_dist_slave_list' %}", {}]
                ["{% url 'rest:device_tree_list' %}", {"all_monitoring_servers" : true}]
            ])
            $q.all(wait_list).then((data) ->
                $scope.masters = data[0]
                for master in $scope.masters
                    console.log master.mon_dist_slave_set
                #$scope.slaves = data[1]
                $scope.servers = build_lut(data[1])
                console.log $scope.servers
            )
        $scope.reload()
])

{% endinlinecoffeescript %}

</script>

