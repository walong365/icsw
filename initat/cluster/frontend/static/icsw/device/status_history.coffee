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
    "icsw.device.status_history",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "ui.bootstrap.datetimepicker", "icsw.tools.status_history_utils"
    ]
).config(["$stateProvider", ($stateProvider) ->
    $stateProvider.state(
        "main.statushistory", {
            url: "/statushistory"
            templateUrl: "icsw/main/status_history.html"
            data:
                pageTitle: "Status History"
                licenses: ["reporting"]
                rights: ["backbone.device.show_status_history"]
                menuEntry:
                    menukey: "stat"
                    icon: "fa-pie-chart"
                    ordering: 60
        }
    )
]).service("icswStatusHistorySettings", [() ->
    _time_frame = undefined
    _allowed_durations = [
        "day", "week", "month", "year", "decade";
    ]
    
    _set_time_frame = (date_gui, duration_type, start, end) ->
        if date_gui?
            _time_frame = {
                date_gui: date_gui
                duration_type: duration_type
                start: start
                end: end
                start_str: start.format("DD.MM.YYYY HH:mm")
                end_str: end.format("DD.MM.YYYY HH:mm")
            }
        else
            _time_frame = undefined

    _get_time_marker = () ->

        if _time_frame?
            days_of_month = _time_frame.end.subtract(1, 'seconds').date()
            return switch _time_frame.duration_type
                when "day" then {
                    data: ["0:00", "6:00", "12:00", "18:00", "24:00"]
                    time_points: true
                }
                when "week" then {
                    data: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                    time_points: false
                }
                when "month" then {
                    data: ("#{x}." for x in [1..days_of_month])
                    time_points: true
                    steps: 3
                }
                when "year" then {
                    data: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Sep", "Oct", "Nov", "Dec" ]
                    time_points: false
                }
                when "decade" then {
                    # TODO, Fixme
                    data: [_time_frame.start.year()]
                    time_points: false
                }
        else
            return []

    _get_time_frame = () ->
        return _time_frame

    _set_time_frame()

    return {
        set_time_frame: _set_time_frame
        get_time_frame: _get_time_frame
        get_time_marker: _get_time_marker
        get_allowed_durations: () ->
            return _allowed_durations
    }

]).controller("icswDeviceStatusHistoryCtrl",
[
    "$scope", "icswDeviceTreeService", "$q", "icswStatusHistorySettings", "status_utils_functions",
(
    $scope, icswDeviceTreeService, $q, icswStatusHistorySettings, status_utils_functions,
) ->
    # controller takes care of setting the time frame.
    # watch this to get updates
    # setting of time frame is done by outer directive icswDeviceStatusHistoryOverview
    $scope.struct = {
        # loading flag
        loading: false
        # devices
        devices: []
        # device tree
        device_tree: undefined
        # timespan error
        timespan_error: ""
        # timespan info
        timespan_info: ""
        # start date
        startdate: undefined
        # start date for datepicker
        startdate_dp: undefined
        # duration type
        duration_type: undefined
        # enabled devices
        enabled_device_lut: {}
    }

    # datepicker options
    $scope.date_options = {
        format: "dd.MM.yyyy"
        formatYear: "yyyy"
        maxDate: new Date()
        minDate: new Date(2000, 1, 1)
        startingDay: 1
        minMode: "day"
        datepickerMode: "day"
        $$opened: false
    }

    $scope.open_popup = () ->
        $scope.date_options.$$opened = true

    $scope.set_duration_type = (d) ->
        $scope.struct.duration_type = d
        _mode = {
            day: "day"
            week: "day"
            month: "month"
            year: "year"
            decade: "year"
        }[d]
        $scope.date_options.minMode = _mode
        $scope.date_options.datepickerMode = _mode

    if false  # debug
        $scope.struct.startdate = moment('Wed Jul 01 2015 00:00:00 GMT+0100 (CET)')
        $scope.set_duration_type("month")
    else
        # defaults
        $scope.struct.startdate = moment().startOf("day").subtract(1, "days")
        $scope.set_duration_type("day")

    # convert to datepicker date
    $scope.struct.startdate_dp = $scope.struct.startdate.toDate()

    $scope.new_devsel = (devs) ->
        $scope.struct.loading = true
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.devices = (dev for dev in devs when not dev.is_meta_device)
                $scope.struct.device_tree = data[0]
                $scope.struct.loading = false
        )

    $scope.get_time_frame = () ->
        return icswStatusHistorySettings.get_time_frame()
        
    $scope.get_allowed_durations = () ->
        return icswStatusHistorySettings.get_allowed_durations()

    update_time_frame = (new_values, old_values) ->
        duration_type_change = new_values[0] != old_values[0] and new_values[1] == old_values[1]

        $scope.struct.startdate = moment($scope.struct.startdate_dp)
        if moment($scope.struct.startdate).isValid()
            $scope.struct.timespan_info = "Fetching timespan data"
            status_utils_functions.get_timespan($scope.struct.startdate, $scope.struct.duration_type).then(
                (new_data) ->
                    $scope.struct.timespan_error = ""
                    $scope.struct.timespan_info = ""
                    if new_data.status == "found"

                        start = moment.utc(new_data.start)
                        end = moment.utc(new_data.end)

                        icswStatusHistorySettings.set_time_frame($scope.struct.startdate, $scope.struct.duration_type, start, end)

                    else if new_data.status == "found earlier" and duration_type_change
                        # does not exist for this time span. This usually happens when you select a timeframe which hasn't finished.

                        start = moment.utc(new_data.start)
                        end = moment.utc(new_data.end)

                        $scope.startdate = moment.utc(new_data.start)  # also set gui

                        icswStatusHistorySettings.set_time_frame($scope.struct.startdate, $scope.struct.duration_type, start, end)

                    else
                        $scope.struct.timespan_error = "No data available for this time span"
                        icswStatusHistorySettings.set_time_frame()
            )

    $scope.$watchGroup(
        ["struct.duration_type", "struct.startdate_dp"]
        (new_values, old_values) ->
            update_time_frame(new_values, old_values)
    )

]).directive("icswDeviceStatusHistoryDevice",
[
    "status_utils_functions", "Restangular", "ICSW_URLS", "$q", "icswStatusHistorySettings",
(
    status_utils_functions, Restangular, ICSW_URLS, $q, icswStatusHistorySettings,
) ->
    return {
        restrict : "EA"
        templateUrl : "icsw.device.status_history_device"
        require: '^icswDeviceStatusHistoryOverview'
        scope: {
            "device": "=icswDevice"
        }
        link : (scope, el, attrs, status_history_ctrl) ->

            scope.struct = {
                # loading flag
                loading: false
                # service cache, service -> key -> value
                service_cache: {}
            }

            _extract_service_name = (service_key) ->
                check_command_name = service_key.split(",", 2)[0]
                description =  service_key.split(",", 2)[1]
                if check_command_name
                    if description
                        # serv_name = check_command_name + ": " + description
                        # changed 20150223: only description as it's usually similar to check command name
                        serv_name = description
                    else
                        serv_name = check_command_name
                else  # legacy data, only have some kind of id string to show
                    serv_name = description
                return serv_name

            scope.float_format = (n) ->
                return status_utils_functions.float_format(n)

            scope.get_time_frame = () ->
                return icswStatusHistorySettings.get_time_frame()

            scope.calc_pie_data = (name, service_data) ->
                [unused, pie_data] = status_utils_functions.preprocess_service_state_data(service_data)
                return pie_data

            scope.update = () ->
                if icswStatusHistorySettings.get_time_frame()?
                    scope.struct.loading = true
                    time_frame = icswStatusHistorySettings.get_time_frame()
                    $q.all(
                        [
                            status_utils_functions.get_service_data(
                                [scope.device.idx]
                                time_frame.date_gui
                                time_frame.duration_type
                            )
                            # also query for year currently
                            status_utils_functions.get_service_data(
                                [scope.device.idx]
                                time_frame.date_gui
                                time_frame.duration_type
                                0
                                true
                            )
                        ]
                    ).then(
                        (new_data) ->
                            service_data = new_data[0].plain()[0]
                            service_data = service_data[_.keys(service_data)[0]]  # there is only one device
                            # line data
                            line_data = new_data[1].plain()[0]
                            line_data = line_data[_.keys(line_data)[0]]
                            # new_data is dict, but we want it as list to be able to sort it

                            # new_data is undefined if there are no services in this time frame
                            # (usually pathological configuration)
                            if service_data?
                                processed_data = (
                                    {
                                        key: key
                                        name: _extract_service_name(key)
                                        main_data: val
                                        line_graph_data: if line_data? and key of line_data then line_data[key] else []
                                        pie_data: scope.calc_pie_data(key, val)
                                    } for key, val of service_data
                                )
                            else
                                processed_data = []

                            scope.service_data = _.sortBy(processed_data, (entry) -> return entry.name)
                            scope.struct.service_cache = {}
                            # create service caches
                            for entry in scope.service_data
                                scope.struct.service_cache[entry.name] = {}
                                for key in status_utils_functions.get_service_states()
                                    scope.struct.service_cache[entry.name][key] = status_utils_functions.float_format(
                                        _.sum((_entry.value for _entry in _.filter(entry.main_data, (e) -> e.state == key)))
                                    )
                            scope.struct.loading = false
                        (error) ->
                            scope.struct.loading = false
                    )
                else
                    scope.service_data = []

            scope.$watchGroup(
                [
                    "device"
                    () ->
                        return icswStatusHistorySettings.get_time_frame()
                ]
                (unused) ->
                    if scope.device?
                        scope.update()
            )
    }
]).directive("icswDeviceStatusHistoryOverview",
[() ->
    return {
        restrict: "EA"
        templateUrl: "icsw.device.status_history_overview"
        controller: 'icswDeviceStatusHistoryCtrl'
    }
])
