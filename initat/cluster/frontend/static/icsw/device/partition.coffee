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
angular.module(
    "icsw.device.partition"
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "icsw.d3", "icsw.tools.button"
    ]
).config(["$stateProvider", ($stateProvider) ->
    $stateProvider.state(
        "main.partition", {
            url: "/partition"
            templateUrl: "icsw/main/partition.html"
            icswData:
                pageTitle: "Partition overview"
                rights: ["partition_fs.modify_partitions"]
                licenses: ["netboot"]
                menuEntry:
                    menukey: "cluster"
                    icon: "fa-database"
                    ordering: 35
        }
    ).state(
        "main.monitordisk", {
            url: "/monitordisk"
            template: '<icsw-device-partition-overview icsw-sel-man="0" icsw-sel-man-sel-mode="d"></icsw-device-partition-overview>'
            icswData:
                pageTitle: "Disk"
                rights: ["mon_check_command.setup_monitoring"]
                menuEntry:
                    menukey: "mon"
                    icon: "fa-hdd-o"
                    ordering: 50
        }
    )
]).directive("icswDevicePartitionOverview",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.partition.overview")
        controller: "icswDevicePartitionOverviewCtrl"
    }
]).controller("icswDevicePartitionOverviewCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular",
    "$q", "blockUI", "ICSW_URLS",
    "icswSimpleAjaxCall", "icswDeviceTreeService", "icswDeviceTreeHelperService",
(
    $scope, $compile, $filter, $templateCache, Restangular,
    $q, blockUI, ICSW_URLS,
    icswSimpleAjaxCall, icswDeviceTreeService, icswDeviceTreeHelperService,
) ->
    $scope.struct = {
        # loading
        loading: false
        # device tree
        device_tree: undefined
        # devices
        devices: []
    }
    $scope.new_devsel = (dev_sel) ->
        $scope.struct.loading = true
        $scope.struct.devices.length = 0
        icswDeviceTreeService.load($scope.$id).then(
            (data) ->
                $scope.struct.device_tree = data
                for dev in dev_sel
                    if not dev.is_meta_device
                        $scope.struct.devices.push(dev)
                hs = icswDeviceTreeHelperService.create($scope.struct.device_tree, $scope.struct.devices)
                $scope.struct.device_tree.enrich_devices(hs, ["disk_info"]).then(
                    (data) ->
                        # console.log "*", data
                        $scope.struct.loading = false
                )
        )

    $scope.get_vg = (dev, vg_idx) ->
        return (cur_vg for cur_vg in dev.act_partition_table.lvm_vg_set when cur_vg.idx == vg_idx)[0]

    _call_server = ($event, device, url) ->
        $scope.struct.loading = true
        blockUI.start()
        icswSimpleAjaxCall(
            url: url
            data: {
                pk: device.idx
            }
        ).then(
            (xml) ->
                # reload partition set
                hs = icswDeviceTreeHelperService.create($scope.struct.device_tree, [device])
                $scope.struct.device_tree.enrich_devices(hs, ["disk_info"], true).then(
                    (data) ->
                        $scope.struct.loading = false
                        blockUI.stop()
                )

            (xml) ->
                $scope.struct.loading = false
                blockUI.stop()
        )

    $scope.clear = ($event, device) ->
        _call_server($event, device, ICSW_URLS.MON_CLEAR_PARTITION)

    $scope.fetch = ($event, device) ->
        _call_server($event, device, ICSW_URLS.MON_FETCH_PARTITION)

    $scope.use = ($event, device) ->
        _call_server($event, device, ICSW_URLS.MON_USE_PARTITION)

])
