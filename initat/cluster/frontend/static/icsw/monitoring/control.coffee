# Copyright (C) 2012-2016 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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
    "icsw.monitoring.control",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular"
    ]
).service("icswMonitoringSysInfoTree",
[
    "$q",
(
    $q,
) ->
    class icswMonitoringSysInfoTree
        constructor: (in_list) ->
            @master = null
            @slaves = []
            @num_builds = 0
            # master build entry
            @master_list = []
            # list of slaves, not used right now
            # @slave_list = []
            @update(in_list)

        update: (in_list) =>
            @slaves.length = 0
            in_struct = in_list[0]
            if in_struct.master?
                # console.log "update", in_struct
                for entry in in_struct.slaves
                    @slaves.push(entry)
                @master = in_struct.master
            @num_builds = in_struct.num_builds
            @salt()

        salt: () =>
            # console.log "salt"
            if @master
                @salt_node(@master)
            (@salt_node(_slave) for _slave in @slaves)

        salt_node: (node) =>
            if node.sysinfo.start_process?
                node.$$sysinfo_ok = true
            else
                node.$$sysinfo_ok = false
            if node.latest_contact? and node.latest_contact
                node.$$latest_contact = moment.unix(node.latest_contact).fromNow()
            else
                node.$$latest_contact = "never"

        feed_builds: (in_list) =>
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

            _runtime = (diff) ->
                if diff
                    # seconds
                    return "#{diff}s"
                else
                    return "< 1s"

            _get_run_time = (master) ->
                if master.build_start and master.build_end
                    return _runtime(moment(master.build_end).diff(moment(master.build_start), "seconds"))
                else
                    return "---"

            _get_conf_time = (obj) ->
                if obj
                    if obj.config_build_end and obj.config_build_start
                        return _runtime(moment(obj.config_build_end).diff(moment(obj.config_build_start), "seconds"))
                    else
                        return "---"
                else
                    return "---"

            _get_time = (dt) ->
                if dt?
                    return moment(dt).format(DT_FORM)
                else
                    return "---"

            _get_sync_time = (slave) ->
                if slave
                    if slave.sync_end and slave.sync_start
                        return _runtime(moment(slave.sync_end).diff(moment(slave.sync_start), "seconds"))
                    else
                        return "---"
                else
                    return "---"
            @master_list.length = 0
            # @slave_list.length = 0
            slave_list = []
            for entry in in_list
                entry.$$line_class = _get_line_class(entry)
                @master_list.push(entry)
                for slave in entry.mon_dist_slave_set
                    # if slave.device not in @slave_list
                    #    @slave_list.push(slave.device)
                    slave.$$sync_diff_time = _get_diff_time(slave.sync_start)
                    slave.$$sync_start = _get_time(slave.sync_start)
                    slave.$$build_conf_time = _get_conf_time(entry)
                    slave.$$sync_time = _get_sync_time(slave)
                    slave.$$build_type = if slave.full_build then "full" else "partial"
                # console.log entry.mon_dist_slave_set
                # entry.$$slaves = ($scope.struct.device_tree.all_lut[slave])
                entry.$$build_time = _get_time(entry.build_start)
                entry.$$build_conf_time = _get_conf_time(entry)
                entry.$$build_run_time = _get_run_time(entry)
                entry.$$build_diff_time = _get_diff_time(entry.build_start)
                entry.$$build_type = if entry.full_build then "full" else "partial"
            # console.log @master_list
            # console.log @slave_list


]).service("icswMonitoringSysInfoTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "icswTreeBase",
    "icswTools", "icswMonitoringSysInfoTree",
(
    $q, Restangular, ICSW_URLS, icswTreeBase,
    icswTools, icswMonitoringSysInfoTree,
) ->
    rest_map = [
        ICSW_URLS.MON_GET_MON_SYS_INFO
    ]
    return new icswTreeBase(
        "MonitoringSysInfoTree"
        icswMonitoringSysInfoTree
        rest_map
        ""
    )
]).controller("icswMonitoringControlInfoCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular", "$window", "ICSW_SIGNALS",
    "$q", "$uibModal", "icswAccessLevelService", "$timeout", "icswTools", "ICSW_URLS", "icswDeviceTreeService",
    "icswMonitoringSysInfoTreeService", "blockUI", "icswSimpleAjaxCall",
(
    $scope, $compile, $filter, $templateCache, Restangular, $window, ICSW_SIGNALS,
    $q, $uibModal, icswAccessLevelService, $timeout, icswTools, ICSW_URLS, icswDeviceTreeService,
    icswMonitoringSysInfoTreeService, blockUI, icswSimpleAjaxCall,
) ->
    icswAccessLevelService.install($scope)

    $scope.struct = {
        # infostruct
        sys_info: undefined
        # loading flag
        loading: false
        # device tree
        device_tree: undefined
        # reload timer
        reload_to: undefined
        # system accordion open
        sys_open: true
        # overview open
        overview_open: false
    }

    $scope.load = (initial) ->
        $scope.struct.loading = true
        if $scope.struct.reload_to?
            $timeout.cancel($scope.struct.reload_to)
        $scope.struct.reload_to = undefined
        if initial
            _wait_list = [
                icswMonitoringSysInfoTreeService.load($scope.$id)
            ]
        else
            _wait_list = [
                icswMonitoringSysInfoTreeService.reload($scope.$id)
            ]
        _wait_list.push(
            Restangular.all(ICSW_URLS.MON_GET_MON_BUILD_INFO.slice(1)).getList({"count": 100})
        )
        if initial
            _wait_list.push(
                icswDeviceTreeService.load($scope.$id)
            )
        $q.all(
            _wait_list
        ).then(
            (data) ->
                if initial
                    $scope.struct.device_tree = data[2]
                    $scope.struct.sys_info = data[0]
                $scope.struct.sys_info.feed_builds(data[1])
                $scope.struct.loading = false
                $scope.struct.reload_to = $timeout(
                    () ->
                        $scope.load(false)
                    10000
                )
            (error) ->
                $scope.struct.loading = false
                $scope.struct.reload_to = $timeout(
                    () ->
                        $scope.load(false)
                    10000
                )
        )

    $scope.$on(ICSW_SIGNALS("_ICSW_FETCH_MON_BUILD_INFO"), () ->
        $scope.load()
    )

    $scope.$on("$destroy", () ->
        if $scope.struct.reload_to
            $timeout.cancel($scope.struct.reload_to)
    )
    $scope.load(true)

    $scope.go_to_icinga = ($event) ->
        icswSimpleAjaxCall(
            url: ICSW_URLS.MON_CALL_ICINGA
            dataType: "json"
        ).then(
            (json) ->
                url = json["url"]
                $window.open(url, "_blank")
        )

    $scope.create_config = ($event) ->
        blockUI.start()
        icswSimpleAjaxCall(
            url: ICSW_URLS.MON_CREATE_CONFIG
            title: "create config"
        ).then(
            (data) ->
                blockUI.stop()
            (error) ->
                blockUI.stop()
        )

    $scope.fetch_dyn_config = ($event) ->
        blockUI.start()
        icswSimpleAjaxCall(
            url: ICSW_URLS.MON_FETCH_DYN_CONFIG
            title: "starting dynamic config fetch"
        ).then(
            (data) ->
                blockUI.stop()
            (error) ->
                blockUI.stop()
        )

]).directive("icswMonitoringSysInfoNode",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "E"
        templateUrl: "icsw.monitoring.sys.info.node"
        controller: "icswMonitoringSysInfoNodeCtrl"
        scope:
            master: "=icswMaster"
            slaves: "=icswSlaves"
    }
]).controller("icswMonitoringSysInfoNodeCtrl",
[
    "$scope", "icswSimpleAjaxCall", "ICSW_URLS", "blockUI", "icswAccessLevelService",
    "ICSW_SIGNALS",
(
    $scope, icswSimpleAjaxCall, ICSW_URLS, blockUI, icswAccessLevelService,
    ICSW_SIGNALS,
) ->
    icswAccessLevelService.install($scope)
    $scope.struct = {
        # list of all nodes
        nodes: []
        # target flags
        start_process: null
        ignore_process: null
        # flagchange pending
        change_pending: false
    }

    _update_master = () ->
        $scope.struct.nodes.length = 0
        $scope.master.name = "master"
        # copy current flags
        _sinfo = $scope.master.sysinfo
        for _fl in ["start_process", "ignore_process"]
            $scope.struct[_fl] = _sinfo[_fl]
        $scope.struct.change_pending = false
        $scope.struct.nodes.push($scope.master)
        for entry in $scope.slaves
            $scope.struct.nodes.push(entry)

    if $scope.master?
        _update_master()

    #$scope.$watch("master", (new_val) ->
    #    if new_val
    #        _update_master()
    #)

    $scope.toggle_flag = ($event, flag_name) ->
        blockUI.start()
        $scope.struct[flag_name] = !$scope.struct[flag_name]
        $scope.struct.change_pending = true
        icswSimpleAjaxCall(
            {
                url: ICSW_URLS.MON_TOGGLE_SYS_FLAG
                data:
                    json: angular.toJson(
                        {
                            name: flag_name
                            current_state: $scope.master.sysinfo[flag_name]
                        }
                    )
            }
        ).then(
            (result) ->
                $scope.$emit(ICSW_SIGNALS("_ICSW_FETCH_MON_BUILD_INFO"))
                blockUI.stop()
        )
])
