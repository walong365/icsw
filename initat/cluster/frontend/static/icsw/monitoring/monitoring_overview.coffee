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

monitoring_overview_module = angular.module(
    "icsw.monitoring.overview",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "ui.bootstrap.datetimepicker", "smart-table",
        "icsw.tools.table", "icsw.tools.status_history_utils", "icsw.device.livestatus"
    ]
).config(["$stateProvider", ($stateProvider) ->
    $stateProvider.state(
        "main.monitorov", {
            url: "/monitorov"
            template: "<icsw-monitoring-list-overview icsw-sel-man='0'></icsw-monitoring-list-overview>"
            data:
                pageTitle: "Monitoring List"
                rights: ["mon_check_command.setup_monitoring"]
                menuEntry:
                    menukey: "mon"
                    name: "Monitoring list"
                    icon: "fa-list"
                    ordering: 0
        }
    )
]).directive("icswMonitoringListOverview",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict : "EA"
        template: $templateCache.get("icsw.monitoring.list.overview")
        controller: "icswMonitoringOverviewCtrl"
    }
]).controller("icswMonitoringOverviewCtrl",
[
    "$scope", "$compile", "$filter", "Restangular", "$q", "icswDeviceTreeService",
    "icswAcessLevelService", "$timeout", "status_utils_functions", "ICSW_URLS",
(
    $scope, $compile, $filter, Restangular, $q, icswDeviceTreeService,
    icswAcessLevelService, $timeout, status_utils_functions, ICSW_URLS,
) ->
    $scope.struct = {
        # filter settings
        str_filter: ""
        # device tree
        device_tree: undefined
        # loading flag
        loading: false
        # devices
        devices: []
        # devices filetered
        devices_filtered: []
    }

    _filter_predicate = (entry, str_re) ->
        # string filter
        sf_flag = entry.full_name.match(str_re)

        return sf_flag

    _update_filter = () ->
        try
            str_re = new RegExp($scope.struct.str_filter, "gi")
        catch err
            str_re = new RegExp("^$", "gi")
        $scope.struct.devices_filtered.length = 0

        for entry in $scope.struct.devices
            if _filter_predicate(entry, str_re)
                $scope.struct.devices_filtered.push(entry)

    $scope.new_devsel = (devs) ->
        $scope.struct.loading = true
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.device_tree = data[0]
                $scope.struct.devices.length = 0
                for entry in devs
                    if not entry.is_meta_device
                        $scope.struct.devices.push(entry)
                _update_filter()
                $scope.struct.loading = false
                $scope.load_monitoring_overview_data()
        )

    _filter_to = undefined
    $scope.$watch(
        "struct.str_filter"
        () ->
            if _filter_to
                $timeout.cancel(_filter_to)

            _filter_to = $timeout(
                _update_filter
                200
            )
    )

    #() -> [$scope.entries, $scope.filter_settings]
    #    () ->
    #        $scope.entries_filtered = (entry for entry in $scope.entries when $scope.filter_predicate(entry))
    #            $scope.load_monitoring_overview_data($scope.entries_filtered)
    #        true)

    #$scope.device_list = []
    #$q.all(wait_list).then( (data) ->
    #    $scope.device_list = data[0]
    #    $scope.update_device_list()
    #)

    $scope.get_selected_entries = () ->
        return (entry for entry in $scope.entries when entry.selected)

    $scope.yesterday = moment().subtract(1, "days")
    $scope.last_week = moment().subtract(1, "weeks")
    $scope.last_month = moment().subtract(1, "month")

    $scope.load_monitoring_overview_data = (new_entries) ->
        $scope.struct.loading = true
        if $scope.struct.devices.length
            _lut = $scope.struct.device_tree.all_lut
            # historic
            historic_cont = (entry_property_name, new_data) ->
                for device_id, data of new_data
                    device_id = parseInt(device_id)  # fuck javascript (OMG)
                    if device_id of _lut
                        _lut[device_id][entry_property_name] = data
                    else
                        console.warn 'failed to find device with id #{device_id} in list'


            _devs = $scope.struct.devices
            $q.all(
                [
                    status_utils_functions.get_device_data(_devs, $scope.yesterday, 'day')
                    status_utils_functions.get_device_data(_devs, $scope.last_week, 'week')
                    status_utils_functions.get_device_data(_devs, $scope.last_month, 'month')
                    status_utils_functions.get_service_data(_devs, $scope.yesterday, 'day', merge_services=1)  #, historic_cont("service_data_yesterday"), merge_services=1)
                    status_utils_functions.get_service_data(_devs, $scope.last_week, 'week', merge_services=1)  #, historic_cont("service_data_last_week"), merge_services=1)
                    status_utils_functions.get_service_data(_devs, $scope.last_month, 'month', merge_services=1)  #, historic_cont("service_data_last_week"), merge_services=1)
                ]
            ).then(
                (data) ->
                    historic_cont("$$device_data_yesterday", data[0][0].plain())
                    historic_cont("$$device_data_last_week", data[1][0].plain())
                    historic_cont("$$device_data_last_month", data[2][0].plain())
                    historic_cont("$$service_data_yesterday", data[3][0].plain())
                    historic_cont("$$service_data_last_week", data[4][0].plain())
                    historic_cont("$$service_data_last_month", data[5][0].plain())
                    $scope.struct.loading = false
            )
])
