# Copyright (C) 2012-2016 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

DT_FORM = "dd, D. MMM YYYY HH:mm:ss"

monitoring_build_info_module = angular.module(
    "icsw.monitoring.build_info",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular"
    ]
).config([
    "$stateProvider", "icswRouteExtensionProvider",
(
    $stateProvider, icswRouteExtensionProvider,
) ->
    $stateProvider.state(
        "main.monitobuildinfo", {
            url: "/monitorbuildinfo"
            template: "<icsw-monitoring-build-info></icsw-monitoring-build-info>"
            icswData: icswRouteExtensionProvider.create
                pageTitle: "Monitoring build info"
                rights: ["mon_check_command.setup_monitoring"]
                menuEntry:
                    menukey: "mon"
                    name: "Build info"
                    icon: "fa-info-circle"
                    ordering: 60
        }
    )
]).controller("icswMonitoringBuildInfoCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular",
    "$q", "$uibModal", "icswAcessLevelService", "$timeout", "icswTools", "ICSW_URLS", "icswDeviceTreeService",
(
    $scope, $compile, $filter, $templateCache, Restangular,
    $q, $uibModal, icswAcessLevelService, $timeout, icswTools, ICSW_URLS, icswDeviceTreeService,
) ->
    icswAcessLevelService.install($scope)

    $scope.struct = {
        # loading flag
        loading: false
        # device tree
        device_tree: undefined
        # master build list
        masters: []
        # all slaves
        slaves: []
        # reload timer
        reload_to: undefined
    }

    $scope.reload = () ->
        $scope.struct.loading = true
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
                Restangular.all(ICSW_URLS.REST_MON_DIST_MASTER_LIST.slice(1)).getList()
            ]
        ).then(
            (data) ->
                $scope.struct.device_tree = data[0]
                $scope.build_list(data[1])
                $scope.struct.loading = false
                $scope.struct.reload_to = $timeout($scope.reload, 5000)
        )

    $scope.$on("$destroy", () ->
        if $scope.struct.reload_to
            console.log "C"
            $timeout.cancel($scope.struct.reload_to)
    )
    $scope.reload()

    $scope.build_list = (in_list) ->
        _get_line_class = (build) ->
            if build.build_start and build.build_end
                r_class = ""
            else
                r_class = "danger"
            for slave in build.mon_dist_slave_set
                if not slave.sync_start or not slave.sync_end
                    if not r_class
                        r_class = "warning"
            return r_class

        _get_diff_time = (dt) ->
            if dt?
                return moment(dt).fromNow()
            else
                return "???"

        _get_time = (dt) ->
            if dt?
                return moment(dt).format(DT_FORM)
            else
                return "---"

        $scope.struct.masters.length = 0
        slave_list = []
        for entry in in_list
            entry.$$line_class = _get_line_class(entry)
            $scope.struct.masters.push(entry)
            for slave in entry.mon_dist_slave_set
                if slave.device not in slave_list
                    slave_list.push(slave.device)
            # console.log entry.mon_dist_slave_set
            # entry.$$slaves = ($scope.struct.device_tree.all_lut[slave])
            entry.$$build_time = _get_time(entry.build_start)
            entry.$$build_diff_time = _get_diff_time(entry.build_start)
        $scope.struct.slaves = slave_list

    $scope.get_diff_time = (dt) ->
        if dt?
            return moment(dt).fromNow()
        else
            return "???"

    $scope.get_time = (dt) ->
        if dt?
            return moment(dt).format(DT_FORM)
        else
            return "---"

    $scope._runtime = (diff) ->
        if diff
            # seconds
            return "#{diff}s"
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

]).directive('icswMonitoringBuildInfo', () ->
    return {
        restrict: 'EA'
        templateUrl: 'icsw.monitoring.build_info'
        controller: "icswMonitoringBuildInfoCtrl"
    }
)
