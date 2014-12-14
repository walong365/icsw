{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

monitoring_build_info_module = angular.module("icsw.monitoring_build_info", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular"])

angular_module_setup([monitoring_build_info_module])

DT_FORM = "dd, D. MMM YYYY HH:mm:ss"

monitoring_build_info_module.controller("info_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "access_level_service", "$timeout",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, access_level_service, $timeout) ->
        access_level_service.install($scope)
        $scope.pagSettings = paginatorSettings.get_paginator("masters", $scope)
        $scope.masters = []
        $scope.reload = () ->
            # force reload
            restDataSource.reset()
            wait_list = restDataSource.add_sources([
                ["{% url 'rest:mon_dist_master_list' %}", {}]
                #["{% url 'rest:mon_dist_slave_list' %}", {}]
                ["{% url 'rest:device_tree_list' %}", {"monitor_server_type" : true}]
            ])
            $q.all(wait_list).then((data) ->
                $timeout($scope.reload, 5000)
                $scope.masters = data[0]
                slave_list = []
                for master in $scope.masters
                    for slave in master.mon_dist_slave_set
                        if slave.device not in slave_list
                            slave_list.push(slave.device)
                $scope.all_slaves = slave_list
                $scope.servers = build_lut(data[1])
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
        $scope.get_slaves = (build) ->
            return ($scope.get_slave(build, slave.device) for slave in build.mon_dist_slave_set)
        $scope.get_slave = (build, idx) ->
            _list = (entry for entry in build.mon_dist_slave_set when entry.device == idx)
            return if _list.length then _list[0] else undefined 
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
        $scope.get_line_class = (build) ->
            if build.build_start and build.build_end
                r_class = ""
            else
                r_class = "danger"
            for slave in build.mon_dist_slave_set
                if not slave.sync_start or not slave.sync_end
                    if not r_class
                        r_class = "warning"
            return r_class
        $scope.reload()
])

{% endinlinecoffeescript %}

</script>

