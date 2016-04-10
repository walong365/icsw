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
    "icsw.monitoring.device",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "icsw.tools.table", "icsw.tools.button"
    ]
).config(["$stateProvider",
(
    $stateProvider
) ->
    $stateProvider.state(
        "main.monitordevice", {
            url: "/monitordevice"
            template: "<icsw-monitoring-device icsw-sel-man='0'></icsw-monitoring-device>"
            data:
                pageTitle: "Monitoring Device settings"
                rights: ["mon_check_command.setup_monitoring", "device.change_monitoring"]
                menuEntry:
                    menukey: "mon"
                    name: "Device settings"
                    icon: "fa-laptop"
                    ordering: 10
        }
    )
]).directive('icswMonitoringDevice',
[
    "ICSW_URLS", "Restangular",
(
    ICSW_URLS, Restangular
) ->
    return {
        restrict: "EA"
        templateUrl: "icsw.monitoring.device"
        controller: "icswMonitoringDeviceCtrl"
    }
]).controller("icswMonitoringDeviceCtrl",
[
    "$scope", "icswDeviceTreeService", "$q", "icswMonitoringBasicTreeService", "icswComplexModalService",
    "$templateCache", "$compile", "icswDeviceMonitoringBackup", "toaster", "blockUI", "Restangular",
    "ICSW_URLS", "icswConfigTreeService",
(
    $scope, icswDeviceTreeService, $q, icswMonitoringBasicTreeService, icswComplexModalService,
    $templateCache, $compile, icswDeviceMonitoringBackup, toaster, blockUI, Restangular,
    ICSW_URLS, icswConfigTreeService,
) ->
    $scope.struct = {
        # loading
        loading: false
        # device_tree
        device_tree: undefined
        # base monitoring tree
        base_tree: undefined
        # devices
        devices: []
        # monitor servers
        monitor_servers: []
    }
    $scope.md_cache_modes = [
        {idx: 1, name: "automatic (server)"}
        {idx: 2, name: "never use cache"}
        {idx: 3, name: "once (until successful)"}
    ]
    $scope.md_cache_lut = _.keyBy($scope.md_cache_modes, "idx")

    $scope.new_devsel = (devs) ->
        $scope.struct.loading = true
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
                icswMonitoringBasicTreeService.load($scope.$id)
                icswConfigTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.device_tree = data[0]
                $scope.struct.base_tree = data[1]
                config_tree = data[2]
                # get monitoring masters and slaves
                _mon_list = []
                for config in config_tree.list
                    if config.name in ["monitor_server", "monitor_slave"]
                        for _dc in config.device_config_set
                            if _dc.device not in _mon_list
                                _mon_list.push(_dc.device)
                $scope.struct.monitor_servers = ($scope.struct.device_tree.all_lut[_dev] for _dev in _mon_list)
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
