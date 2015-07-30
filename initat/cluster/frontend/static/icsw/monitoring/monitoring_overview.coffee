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
).controller("icswMonitoringOverviewCtrl",
    ["$scope", "$compile", "$filter", "Restangular", "paginatorSettings", "restDataSource", "$q", "$modal",
     "access_level_service", "$timeout", "msgbus", "status_utils_functions", "ICSW_URLS",
    ($scope, $compile, $filter, Restangular, paginatorSettings, restDataSource, $q, $modal, access_level_service,
     $timeout, msgbus, status_utils_functions, ICSW_URLS) ->
        $scope.filter_settings = {"str_filter": "", "only_selected": true}

        $scope.filter_predicate = (entry) ->
            selected = $scope.get_selected_entries()
            if !$scope.filter_settings.only_selected || selected.length == 0
                sel_flag = true
            else
                sel_flag = _.contains(selected, entry)
                    
            try
                str_re = new RegExp($scope.filter_settings.str_filter, "gi")
            catch err
                str_re = new RegExp("^$", "gi")

            # string filter
            sf_flag = entry.name.match(str_re)

            return sf_flag and sel_flag

        wait_list = restDataSource.add_sources([
            [ICSW_URLS.REST_DEVICE_LIST, {}],
        ])
        $scope.device_list = []
        $q.all(wait_list).then( (data) ->
            $scope.device_list = data[0]
            $scope.update_device_list()
        )

        $scope.get_selected_entries = () ->
            return (entry for entry in $scope.entries when entry.selected)

        $scope.yesterday = moment().subtract(1, "days")
        $scope.last_week = moment().subtract(1, "weeks")

        $scope.entries = []
        $scope.$watch(
                () -> [$scope.entries, $scope.filter_settings]
                () ->
                    $scope.entries_filtered = (entry for entry in $scope.entries when $scope.filter_predicate(entry))
                    $scope.load_monitoring_overview_data($scope.entries_filtered)
                true)

        $scope.update_device_list = () ->
            # currently only called on external selection change
            # if this is to be called more often, take care to not destroy selection
            
            if $scope.device_list
                set_initial_sel = $scope.initial_sel.length > 0

                new_entries = []
                for dev in $scope.device_list
                    if ! dev.is_meta_device
                        entry = {
                            'idx': dev.idx
                            'name': dev.name
                        }
                        if set_initial_sel
                            entry['selected'] = _.contains($scope.initial_sel, dev.idx)
                        new_entries.push(entry)
                $scope.entries = new_entries

                $scope.initial_sel = []

        $scope.load_monitoring_overview_data = (new_entries) ->
            if new_entries.length > 0
                # historic
                historic_cont = (entry_property_name) ->
                    (new_data) ->
                        for device_id, data of new_data
                            device_id = parseInt(device_id)  # fuck javascript
                            entry = _.find(new_entries, (entry) ->
                                return entry.idx == device_id)

                            if entry
                                entry[entry_property_name] = data
                            else
                                console.log 'failed to find device with id', device_id, 'in list', new_entries


                indexes = (entry.idx for entry in new_entries)
                status_utils_functions.get_device_data(indexes, $scope.yesterday, 'day', historic_cont("device_data_yesterday"))
                status_utils_functions.get_device_data(indexes, $scope.last_week, 'week', historic_cont("device_data_last_week"))

                status_utils_functions.get_service_data(indexes, $scope.yesterday, 'day', historic_cont("service_data_yesterday"), merge_services=1)
                status_utils_functions.get_service_data(indexes, $scope.last_week, 'week', historic_cont("service_data_last_week"), merge_services=1)


        $scope.initial_sel = []
        $scope.new_devsel = (_dev_sel, _devg_sel) ->
            $scope.initial_sel = _dev_sel
            $scope.update_device_list()
            $scope.entries = $scope.entries
            # TODO: since single-app move, this now seems to be executed from apply. Use whichever version works in final single-app version
            #$scope.$apply(  # if we do update_device_list() from this path, angular doesn't realise it
            #    $scope.entries = $scope.entries
            #)
         
        msgbus.emit("devselreceiver")
        msgbus.receive("devicelist", $scope, (name, args) ->
            $scope.new_devsel(args[1])
        )

]).directive("icswMonitoringOverview", () ->
    return {
        restrict : "EA"
        templateUrl: "monitoring_overview_template.html"
    }
)
