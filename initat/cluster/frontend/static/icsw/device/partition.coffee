angular.module(
    "icsw.device.partition"
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "icsw.d3", "icsw.tools.button"
    ]
).controller("icswDevicePartitionCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "blockUI", "ICSW_URLS",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, blockUI, ICSW_URLS) ->
        $scope.entries = []
        $scope.active_dev = undefined
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
                call_ajax
                    url     : ICSW_URLS.MON_CLEAR_PARTITION
                    data    : {
                        "pk" : pk
                    }
                    success : (xml) ->
                        blockUI.stop()
                        parse_xml_response(xml)
                        $scope.reload()
        $scope.fetch = (pk) ->
            if pk?
                blockUI.start()
                call_ajax
                    url     : ICSW_URLS.MON_FETCH_PARTITION
                    data    : {
                        "pk" : pk
                    }
                    success : (xml) ->
                        blockUI.stop()
                        parse_xml_response(xml)
                        $scope.reload()
        $scope.use = (pk) ->
            if pk?
                blockUI.start()
                call_ajax
                    url     : ICSW_URLS.MON_USE_PARTITION
                    data    : {
                        "pk" : pk
                    }
                    success : (xml) ->
                        blockUI.stop()
                        parse_xml_response(xml)
                        $scope.reload()
]).directive("icswDevicePartitionOverview", ($templateCache, $compile, $modal, Restangular) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.partition.overview")
        link : (scope, el, attrs) ->
            scope.$watch(attrs["devicepk"], (new_val) ->
                if new_val and new_val.length
                    scope.new_devsel(new_val)
            )
    }
)
