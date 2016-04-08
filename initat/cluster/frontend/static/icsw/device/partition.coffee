# Copyright (C) 2012-2015 init.at
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
            data:
                pageTitle: "Partition overview"
                rights: ["partition_fs.modify_partitions"]
                licenses: ["netboot"]
                menuEntry:
                    menukey: "cluster"
                    icon: "fa-database"
                    ordering: 35
        }
    )
    $stateProvider.state(
        "main.monitordisk", {
            url: "/monitordisk"
            template: '<icsw-device-partition-overview icsw-sel-man="0" icsw-sel-man-sel-mode="d"></icsw-device-partition-overview>
'
            data:
                pageTitle: "Disk"
                rights: ["mon_check_command.setup_monitoring"]
                menuEntry:
                    menukey: "mon"
                    icon: "fa-hdd-o"
                    ordering: 50
        }
    )
]).controller("icswDevicePartitionOverviewCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular",
    "restDataSource", "$q", "$uibModal", "blockUI", "ICSW_URLS",
    "icswSimpleAjaxCall",
(
    $scope, $compile, $filter, $templateCache, Restangular,
    restDataSource, $q, $uibModal, blockUI, ICSW_URLS,
    icswSimpleAjaxCall
) ->
    $scope.entries = []
    $scope.active_dev = undefined
    $scope.devsel_list = []
    $scope.new_devsel = (_dev_sel, _devg_sel) ->
        $scope.devsel_list = _dev_sel
        $scope.reload()
    $scope.reload = () ->
        active_tab = (dev for dev in $scope.entries when dev.tab_active)
        restDataSource.reload([ICSW_URLS.REST_DEVICE_TREE_LIST, {"with_disk_info" : true, "with_meta_devices" : false, "pks" : angular.toJson($scope.devsel_list), "olp" : "backbone.device.change_monitoring"}]).then((data) ->
            $scope.entries = (dev for dev in data)
            if active_tab.length
                for dev in $scope.entries
                    if dev.idx == active_tab[0].idx
                        dev.tab_active = true
        )
    $scope.get_vg = (dev, vg_idx) ->
        return (cur_vg for cur_vg in dev.act_partition_table.lvm_vg_set when cur_vg.idx == vg_idx)[0]
    $scope.clear = (pk) ->
        if pk?
            blockUI.start()
            icswSimpleAjaxCall(
                url     : ICSW_URLS.MON_CLEAR_PARTITION
                data    : {
                    "pk" : pk
                }
            ).then(
                (xml) ->
                    blockUI.stop()
                    $scope.reload()
                (xml) ->
                    blockUI.stop()
                    $scope.reload()
            )
    $scope.fetch = (pk) ->
        if pk?
            blockUI.start()
            icswSimpleAjaxCall(
                url     : ICSW_URLS.MON_FETCH_PARTITION
                data    : {
                    "pk" : pk
                }
            ).then(
                (xml) ->
                    blockUI.stop()
                    $scope.reload()
                (xml) ->
                    blockUI.stop()
                    $scope.reload()
            )
    $scope.use = (pk) ->
        if pk?
            blockUI.start()
            icswSimpleAjaxCall(
                url     : ICSW_URLS.MON_USE_PARTITION
                data    : {
                    "pk" : pk
                }
            ).then(
                (xml) ->
                    blockUI.stop()
                    $scope.reload()
                (xml) ->
                    blockUI.stop()
                    $scope.reload()
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
])
