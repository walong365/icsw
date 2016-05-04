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

monitoring_device_module = angular.module(
    "icsw.schedule.device",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "icsw.tools.table", "icsw.tools.button"
    ]
).config(["$stateProvider",
(
    $stateProvider
) ->
    $stateProvider.state(
        "main.scheddevice", {
            url: "/sched/device"
            template: "<icsw-schedule-device icsw-sel-man='0'></icsw-schedule-device>"
            icswData:
                pageTitle: "Set Device Schedules"
                # rights: ["mon_check_command.setup_monitoring", "device.change_monitoring"]
                menuHeader:
                    key: "sched"
                    name: "Scheduling"
                    icon: "fa-gears"
                    ordering: 70
                menuEntry:
                    menukey: "sched"
                    name: "Device settings"
                    icon: "fa-laptop"
                    ordering: 10
        }
    )
]).service("icswDispatcherSettingTree",
[
    "$q",
(
    $q,
) ->
    class icswDispatcherSettingTree
        constructor: (list, schedule_list) ->
            @list = []
            @schedule_list = []
            @update(list, schedule_list)

        update: (list, schedule_list) =>
            @list.length = 0
            for entry in list
                @list.push(entry)
            @schedule_list.length = 0
            for entry in schedule_list
                @schedule_list.push(entry)
            @lut = _.keyBy(@list, "idx")
            @schedule_lut = _.keyBy(@schedule_list, "idx")
            @link

        link: () =>
            # create some simple links
            for entry in @list
                entry.$$run_schedule = @schedule_lut[entry.run_schedule]

]).service("icswDispatcherSettingTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall", "icswTools",
    "icswDispatcherSettingTree", "$rootScope", "ICSW_SIGNALS",
(
    $q, Restangular, ICSW_URLS, $window, icswCachingCall, icswTools,
    icswDispatcherSettingTree, $rootScope, ICSW_SIGNALS
) ->
    rest_map = [
        [
            # setting list
            ICSW_URLS.REST_DISPATCHER_SETTING_LIST
            {}
        ]
        [
            # setting schedule list
            ICSW_URLS.REST_DISPATCHER_SETTING_SCHEDULE_LIST
            {}
        ]
    ]
    _fetch_dict = {}
    _result = undefined
    # load called
    load_called = false

    load_data = (client) ->
        load_called = true
        _wait_list = (icswCachingCall.fetch(client, _entry[0], _entry[1], []) for _entry in rest_map)
        _defer = $q.defer()
        $q.all(_wait_list).then(
            (data) ->
                console.log "*** dispatcher setting tree loaded ***"
                if _result?
                    _result.update(data[0], data[1])
                else
                    _result = new icswDispatcherSettingTree(data[0], data[1])
                _defer.resolve(_result)
                for client of _fetch_dict
                    # resolve clients
                    _fetch_dict[client].resolve(_result)
                # reset fetch_dict
                _fetch_dict = {}
        )
        return _defer

    fetch_data = (client) ->
        if client not of _fetch_dict
            # register client
            _defer = $q.defer()
            _fetch_dict[client] = _defer
        if _result
            # resolve immediately
            _fetch_dict[client].resolve(_result)
        return _fetch_dict[client]

    return {
        "load": (client) ->
            # loads from server
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise
        "reload": (client) ->
            return load_data(client).promise
    }
]).directive('icswScheduleDevice',
[
    "ICSW_URLS", "Restangular",
(
    ICSW_URLS, Restangular
) ->
    return {
        restrict: "EA"
        templateUrl: "icsw.schedule.device"
        controller: "icswScheduleDeviceCtrl"
    }
]).controller("icswScheduleDeviceCtrl",
[
    "$scope", "icswDeviceTreeService", "$q", "icswMonitoringBasicTreeService", "icswComplexModalService",
    "$templateCache", "$compile", "icswDeviceMonitoringBackup", "toaster", "blockUI", "Restangular",
    "ICSW_URLS", "icswConfigTreeService", "icswDispatcherSettingTreeService",
(
    $scope, icswDeviceTreeService, $q, icswMonitoringBasicTreeService, icswComplexModalService,
    $templateCache, $compile, icswDeviceMonitoringBackup, toaster, blockUI, Restangular,
    ICSW_URLS, icswConfigTreeService, icswDispatcherSettingTreeService,
) ->
    $scope.struct = {
        # loading
        loading: false
        # device_tree
        device_tree: undefined
        # base monitoring tree
        base_tree: undefined
        # dispatch tree
        dispatch_tree: undefined
        # devices
        devices: []
        # monitor servers
        monitor_servers: []
    }
    $scope.new_devsel = (devs) ->
        $scope.struct.loading = true
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
                icswMonitoringBasicTreeService.load($scope.$id)
                icswConfigTreeService.load($scope.$id)
                icswDispatcherSettingTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.device_tree = data[0]
                $scope.struct.base_tree = data[1]
                $scope.struct.dispatch_tree = data[3]
                config_tree = data[2]
                # get monitoring masters and slaves
                $scope.struct.loading = false
                $scope.struct.devices.length = 0
                for entry in devs
                    if not entry.is_meta_device
                        $scope.struct.devices.push(entry)
        )
    $scope.edit = ($event, obj) ->
        dbu = new icswDeviceMonitoringBackup()
        dbu.create_backup(obj)
        
        sub_scope = $scope.$new(false)
        sub_scope.edit_obj = obj
        # copy references
        sub_scope.md_cache_modes = $scope.md_cache_modes
        sub_scope.base_tree = $scope.struct.base_tree
        sub_scope.monitor_servers = $scope.struct.monitor_servers
        sub_scope.nagvis_list = (
            entry for entry in $scope.struct.device_tree.enabled_list when not entry.is_meta_device and entry.idx !=obj.idx and entry.automap_nagvis_root
        )
        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.device.monitoring.form"))(sub_scope)
                title: "Monitoring settings for #{sub_scope.edit_obj.full_name}"
                ok_label: "Modify"
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.invalid
                        toaster.pop("warning", "form validation problem", "", 0)
                        d.reject("form not valid")
                    else
                        blockUI.start("saving device...")
                        # hm, maybe not working ...
                        Restangular.restangularizeElement(null, sub_scope.edit_obj, ICSW_URLS.REST_DEVICE_DETAIL.slice(1).slice(0, -2))
                        sub_scope.edit_obj.put().then(
                            (ok) ->
                                blockUI.stop()
                                d.resolve("saved")
                            (not_ok) ->
                                blockUI.stop()
                                d.reject("not saved")
                        )
                    return d.promise
                cancel_callback: (modal) ->
                    dbu.restore_backup(obj)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                sub_scope.$destroy()
        )
])
