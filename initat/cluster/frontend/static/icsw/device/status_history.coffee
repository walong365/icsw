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
    "icsw.device.status_history",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "ui.bootstrap.datetimepicker", "icsw.tools.status_history_utils"
    ]
).controller("icswDeviceStatusHistoryCtrl", ["$scope",
    ($scope) ->
        # controller takes care of setting the time frame.
        # watch this to get updates
        # setting of time frame is done by outer directive icswDeviceStatusHistoryOverview
        this.set_time_frame = (date_gui, duration_type, start, end) ->
            if date_gui?
                this.time_frame = {
                    'date_gui'   : date_gui
                    'duration_type' : duration_type
                    'start'      : start
                    'end'        : end
                    'start_str'  : start.format("DD.MM.YYYY HH:mm")
                    'end_str'    : end.format("DD.MM.YYYY HH:mm")
                }
            else
                this.time_frame = undefined
        this.set_time_frame()
        this.get_time_marker = () ->

            days_of_month = this.time_frame.end.subtract(1, 'seconds').date()

            if this.time_frame?
                return switch this.time_frame.duration_type
                    when 'day' then {'data': ["0:00", "6:00", "12:00", "18:00", "24:00"], 'time_points': true}
                    when 'week' then {'data': ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], 'time_points': false}
                    when 'month' then {'data': (x+"." for x in [1..days_of_month]) , 'time_points': true, 'steps': 3}
                    when 'year' then {'data': ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Sep", "Oct", "Nov", "Dec" ], 'time_points': false}
            else
                return []
]).directive("icswDeviceStatusHistoryDevice", ["status_utils_functions", "Restangular", "ICSW_URLS", "msgbus", "$q", (status_utils_functions, Restangular, ICSW_URLS, msgbus, $q) ->
    return {
        restrict : "EA"
        templateUrl : "icsw.device.status_history_device"
        require: '^icswDeviceStatusHistoryOverview'
        scope: {
            "deviceid" : "="
        }
        link : (scope, el, attrs, status_history_ctrl) ->
            scope.devicepks = []

            scope.extract_service_value = (service, key) ->
                entries = _.filter(service, (e) -> e.state == key)
                ret = 0
                for entry in entries
                    ret += entry.value
                return scope.float_format(ret)
            scope.extract_service_name = (service_key) ->
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
            scope.float_format = (n) -> return (n*100).toFixed(2) + "%"

            scope.get_time_frame = () ->
                return status_history_ctrl.time_frame

            scope.calc_pie_data = (name, service_data) ->
                [unused, pie_data] = status_utils_functions.preprocess_service_state_data(service_data)
                return pie_data
            scope.update = () ->

                Restangular.one(ICSW_URLS.REST_DEVICE_LIST.slice(1)).get({'idx': scope.deviceid}).then((new_data)->
                    scope.device_rest = new_data[0]
                )
                if status_history_ctrl.time_frame?
                    serv_cont_done = $q.defer()
                    serv_cont = (new_data) ->
                        new_data = new_data[Object.keys(new_data)[0]]  # there is only one device
                        # new_data is dict, but we want it as list to be able to sort it

                        # new_data is undefined if there are no services in this time frame
                        # (usually pathological configuration)
                        if new_data?
                            processed_data = ({
                                'key' : key
                                'name': scope.extract_service_name(key)
                                'main_data': val
                                'line_graph_data': [] # line graph data will be filled below
                                'pie_data': scope.calc_pie_data(key, val)} for key, val of new_data)
                        else
                            processed_data = []

                        scope.service_data = _.sortBy(processed_data, (entry) -> return entry.name)
                        serv_cont_done.resolve()

                    serv_line_graph_cont = (new_data) ->
                        # we need that the other query has finished
                        serv_cont_done.promise.then(() ->
                            new_data = new_data[Object.keys(new_data)[0]]  # there is only one device

                            if new_data?
                                for entry in scope.service_data
                                    entry.line_graph_data = new_data[entry.key]
                        )

                    time_frame = status_history_ctrl.time_frame
                    status_utils_functions.get_service_data([scope.deviceid], time_frame.date_gui, time_frame.duration_type, serv_cont)
                    # also query for year currently
                    status_utils_functions.get_service_data([scope.deviceid], time_frame.date_gui, time_frame.duration_type, serv_line_graph_cont, 0, true)
                else
                    scope.service_data = []

            scope.$watchGroup(
                ['deviceid', () -> return status_history_ctrl.time_frame]
                (unused) ->
                    if scope.deviceid?
                        scope.update()
            )
    }
]).directive("icswDeviceStatusHistoryOverview", ["status_utils_functions", "Restangular", "ICSW_URLS", (status_utils_functions, Restangular, ICSW_URLS) ->
    return {
        restrict : "EA"
        templateUrl : "icsw.device.status_history_overview"
        controller: 'icswDeviceStatusHistoryCtrl'
        link : (scope, el, attrs, status_history_ctrl) ->

            # this directive takes care of setting the time frame
            # and contains the other directives (this is not necessarily so)

            scope.devicepks = []
            scope.startdate = moment().startOf("day").subtract(1, "days")
            scope.duration_type = 'day'

            if false  # debug
                scope.duration_type = 'month'
                scope.startdate = moment('Tue Jun 17 2014 00:00:00 GMT+0100 (CET)')

            scope.set_duration_type = (d) ->
                scope.duration_type = d

            scope.get_time_frame = () ->
                return status_history_ctrl.time_frame

            scope.update_time_frame = (new_values, old_values) ->
                duration_type_change = new_values[0] != old_values[0] and new_values[1] == old_values[1]

                cont = (new_data) ->
                    scope.timespan_error = ""
                    if new_data.status == 'found'

                        start = moment.utc(new_data.start)
                        end = moment.utc(new_data.end)

                        status_history_ctrl.set_time_frame(scope.startdate, scope.duration_type, start, end)
                    else if new_data.status == 'found earlier' and duration_type_change
                        # does not exist for this time span. This usually happens when you select a timeframe which hasn't finished.

                        start = moment.utc(new_data.start)
                        end = moment.utc(new_data.end)

                        scope.startdate = moment.utc(new_data.start)  # also set gui

                        status_history_ctrl.set_time_frame(scope.startdate, scope.duration_type, start, end)
                    else
                        scope.timespan_error = "No data available for this time span"
                        status_history_ctrl.set_time_frame()

                if moment(scope.startdate).isValid()
                    status_utils_functions.get_timespan(scope.startdate, scope.duration_type, cont)

            # used only in template
            scope.enabled_device_lut = {}

            scope.devices_rest = {}
            scope.new_devsel = (new_val) ->
                scope.devicepks = new_val

                for devicepk in scope.devicepks
                    do (devicepk) ->
                        Restangular.one(ICSW_URLS.REST_DEVICE_LIST.slice(1)).get({'idx': devicepk}).then((new_data)->
                            scope.devices_rest[devicepk] = new_data[0]
                        )
            scope.$watchGroup(['duration_type', 'startdate'],  (new_values, old_values) -> scope.update_time_frame(new_values, old_values) )
    }
])