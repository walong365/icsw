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

angular.module(
    "icsw.tools.status_history_utils",
    [
        "icsw.tools.piechart", "restangular"
    ]
).directive('icswToolsDeviceHistStatusOverview',
[
    "$parse", "status_utils_functions", "icswStatusHistorySettings", "$q",
(
    $parse, status_utils_functions, icswStatusHistorySettings, $q,
) ->
    # shows piechart and possibly table of historic device status
    # used in status history page and monitoring overview
    return {
        restrict: 'E'
        scope: {
            # if data is passed right through here, the other attributes are discarded
            # data must be defined if we are not below the status history ctrl
            data: "="
            device: "=icswDevice"
        }
        require: '?^icswDeviceStatusHistoryOverview'
        templateUrl: "icsw.tools.device_hist_status"
        link: (scope, element, attrs) ->
            scope.detailed_view = scope.$eval(attrs.detailedView)
            scope.struct = {
                # loading flag
                loading: false
            }

            # TODO: make this into a filter, then remove also from serviceHist*
            scope.float_format = (n) -> return (n*100).toFixed(3) + "%"

            scope.host_data = []
            scope.pie_data = []
            scope.line_graph_data = []

            scope.update_from_server = () ->
                # TODO: this loading should probably be refactored into status_history.coffee, such that these directives
                #       here only get the direct data. then we can centralise the loading there.
                #       NOTE: keep consistent with service below
                if icswStatusHistorySettings.get_time_frame()?
                    scope.struct.loading = true
                    time_frame = icswStatusHistorySettings.get_time_frame()
                    $q.all(
                        [
                            status_utils_functions.get_device_data([scope.device], time_frame.date_gui, time_frame.duration_type, time_frame.db_ids)
                            status_utils_functions.get_device_data([scope.device], time_frame.date_gui, time_frame.duration_type, time_frame.db_ids, true)
                        ]
                    ).then(
                        (new_data) ->
                            srv_data = new_data[0]
                            if _.keys(srv_data).length
                                srv_data = srv_data[_.keys(srv_data)[0]]
                                [scope.host_data, scope.pie_data] = status_utils_functions.preprocess_device_state_data(
                                    srv_data
                                )
                            else
                                [scope.host_data, scope.pie_data] = [[], []]
                            line_data = new_data[1]
                            line_data = line_data[_.keys(line_data)[0]]
                            if line_data?
                                scope.line_graph_data = line_data
                            else
                                scope.line_graph_data = []
                            scope.struct.loading = false
                    )
                else
                    scope.host_data = []
                    scope.pie_data = []

            scope.update_from_local_data = () ->
                if scope.data?
                    [scope.host_data, scope.pie_data] = status_utils_functions.preprocess_device_state_data(
                        scope.data
                    )

            if attrs.data?
                scope.$watch('data', (unused) -> scope.update_from_local_data())
            else
                scope.$watchGroup(
                    [
                        "deviceid"
                        () ->
                            return icswStatusHistorySettings.get_time_frame()
                    ]
                    (unused) ->
                        if scope.device?
                            scope.update_from_server()
                )
    }
]).directive('icswToolsServiceHistStatusOverview',
[
    "$parse", "status_utils_functions",
(
    $parse, status_utils_functions
) ->
    # shows piechart of state of service. shows how many service are in which state at a given time frame
    # currently only used in monitoring_overview
    return {
        restrict: 'E'
        scope: {
            # if data is passed right through here, the other attributes are discarded
            # data must be defined if we are not below the status history ctrl
            data: "="
            device: "=icswDevice"
        }
        templateUrl: "icsw.tools.service_hist_status"
        require: '?^icswDeviceStatusHistoryCtrl'
        link: (scope, element, attrs, status_history_ctrl) ->

            # TODO: see above
            scope.float_format = (n) -> return (n*100).toFixed(3) + "%"

            scope.pie_data = []

            scope.update_from_server = () ->
                if status_history_ctrl.time_frame?
                    cont = (new_data) ->
                        new_data = new_data[Object.keys(new_data)[0]]  # there is only one device
                        new_data = new_data['main']  # only main data here
                        [scope.service_data, scope.pie_data] = status_utils_functions.preprocess_service_state_data(new_data)

                    status_utils_functions.get_service_data(
                        [scope.deviceid]
                        status_history_ctrl.time_frame.date_gui
                        status_history_ctrl.time_frame.time_range
                        []
                        cont
                        merge_services=1
                    )

            scope.update_from_local_data = () ->
                if scope.data?
                    [scope.service_data, scope.pie_data] = status_utils_functions.preprocess_service_state_data(scope.data)

            if attrs.data?
                scope.$watch('data', (unused) ->
                    scope.update_from_local_data()
                )
            else
                scope.$watchGroup(
                    ['deviceid', () -> return status_history_ctrl.time_frame]
                    (unused) ->
                        if scope.deviceid?
                            scope.update_from_server())
    }
]).service('status_utils_functions',
[
    "Restangular", "ICSW_URLS", "$q", "icswSaltMonitoringResultService",
(
    Restangular, ICSW_URLS, $q, icswSaltMonitoringResultService,
) ->
    service_states = [
        "Ok", "Warning", "Critical", "Unknown", "Undetermined", "Planned down", "Flapping",
    ]
    get_device_data = (devices, start_date, timerange, db_ids, line_graph_data=false) ->
        query_data = {
            device_ids: angular.toJson((_dev.idx for _dev in devices))
            date: moment(start_date).unix()  # ask server in utc
            duration_type: timerange
        }
        if db_ids.length
            query_data.db_ids = angular.toJson(db_ids)
        if line_graph_data
            base = Restangular.all(ICSW_URLS.MON_GET_HIST_DEVICE_LINE_GRAPH_DATA.slice(1))
        else
            base = Restangular.all(ICSW_URLS.MON_GET_HIST_DEVICE_DATA.slice(1))
        defer = $q.defer()
        base.getList(query_data).then(
            (data) ->
                data = data.plain()
                defer.resolve(icswSaltMonitoringResultService.salt_hist_device_data(data[0]))
        )
        return defer.promise

    get_service_data = (devices, start_date, timerange, db_ids, merge_services=0, line_graph_data=false) ->
        # merge_services: boolean as int
        # line_graph_data: boolean as int, get only line graph data
        query_data = {
            device_ids: angular.toJson((_dev.idx for _dev in devices))
            date: moment(start_date).unix()  # ask server in utc
            duration_type: timerange
            merge_services: merge_services
        }
        if db_ids.length
            query_data.db_ids = angular.toJson(db_ids)
        if line_graph_data
            base = Restangular.all(ICSW_URLS.MON_GET_HIST_SERVICE_LINE_GRAPH_DATA.slice(1))
        else
            base = Restangular.all(ICSW_URLS.MON_GET_HIST_SERVICE_DATA.slice(1))
        # we always return a list for easier REST handling
        defer = $q.defer()
        base.getList(query_data).then(
            (data) ->
                data = data.plain()
                _salted =
                defer.resolve(
                    icswSaltMonitoringResultService.salt_hist_service_data(data[0], merge_services)
                )
        )
        return defer.promise
        # return base.getList(query_data)

    get_timespan = (start_date, timerange) ->
        query_data = {
            "date": moment(start_date).unix()  # ask server in utc
            "duration_type": timerange,
        }
        return Restangular.all(ICSW_URLS.MON_GET_HIST_TIMESPAN.slice(1)).customGET("", query_data)

    float_format = (n) ->
        return "#{_.round(n * 100, 3)}%"

    _preprocess_state_data = (in_data, order_lut) ->
        # formatted_data = _.cloneDeep(new_data)
        new_data = []
        for entry in in_data
            new_data.push(
                {
                    state: entry.state
                    $$data: entry.$$data
                    value: entry.value
                }
            )
        for orderint, struct of order_lut
            if not _.some(in_data, (d) -> return d['state'] == struct.pycode)
                new_data.push(
                    {
                        state: struct.pycode
                        value: 0
                        $$data: struct
                    }
                )
        for d in new_data
            d['$$value'] = float_format(d['value'])
        new_data = _.sortBy(new_data, (d) -> return d.$$data.orderint)

        pie_data = []
        for d in new_data
            if d['state'] != "Flapping"  # can't display flapping in pie
                pie_data.push {
                    "$$data": d.$$data
                    value: Math.round(d['value'] * 10000) / 100
                }
        return [new_data, pie_data]

    preprocess_device_state_data = (new_data) ->
        return _preprocess_state_data(new_data, icswSaltMonitoringResultService.get_struct().ordering_device_lut)

    preprocess_service_state_data = (new_data) ->
        return _preprocess_state_data(new_data, icswSaltMonitoringResultService.get_struct().ordering_service_lut)

    return {
        float_format: float_format
        get_device_data: get_device_data
        get_service_data: get_service_data
        get_service_states: () ->
            return service_states
        get_timespan: get_timespan
        preprocess_device_state_data: preprocess_device_state_data
        preprocess_service_state_data: preprocess_service_state_data

        # kpi states and service states currently coincide even though kpis also have host data

        preprocess_kpi_state_data: preprocess_service_state_data

    }
]).directive("icswToolsHistLineGraph",
[
    "status_utils_functions", "$timeout", "icswStatusHistorySettings", "createSVGElement",
(
    status_utils_functions, $timeout, icswStatusHistorySettings, createSVGElement,
) ->
    return {
        restrict: 'E'
        scope   : {
            data: '='
            forHost: '&'
            widthAttr: '&width'
            heightAttr: '&height'
            clickAttr: '&click'
        }
        require : "^icswDeviceStatusHistoryOverview"
        link: (scope, element, attrs) ->

            base_height = 30

            scope.entry_clicked = (entry) ->
                scope.clickAttr()
                # TODO possibly pass entry outside along the lines of  scope.clickAttr()({entry: entry)) and setting click just to handle_click (not handle_click())

            scope.width = scope.widthAttr() or 400
            # console.log scope.width
            scope.height = scope.heightAttr() or base_height

            scope.fontSize = 10

            scope.side_margin = 15
            scope.draw_width = scope.width - 2 * scope.side_margin

            scope.update = () ->
                $timeout(scope.actual_update)

            scope.actual_update = () ->

                time_frame = icswStatusHistorySettings.get_time_frame()

                element.empty()

                # calculate data to show
                if time_frame? and scope.data?
                    _div = angular.element("<div class='icsw-chart'></div>")
                    _div.css("width", "#{scope.width}px").css("height", "#{scope.height}px").css("margin-bottom", "7px")
                    if scope.data.length > 5000
                        _div.text("Too much data to display (#{scope.data.length})")
                    else
                        _svg = createSVGElement("svg", {"width": scope.width, "height": scope.height})
                        _g = createSVGElement("g")
                        _rect = createSVGElement("rect", {"width": scope.width, "height": scope.height, "x": 0, "y": 0, "fill": "rgba(0, 0, 0, 0.0)"})
                        _g.append(_rect)
                        _div.append(_svg)
                        _svg.append(_g)
                        # set time marker
                        time_marker = icswStatusHistorySettings.get_time_marker()
                        i = 0
                        for marker, index in time_marker.data
                            if time_marker.time_points
                                # time is exactly at certain points
                                pos_x = scope.side_margin + index * scope.draw_width / (time_marker.data.length-1)
                            else
                                # pos should be in the middle of the durations, such as week days, month
                                unit_size = scope.draw_width / time_marker.data.length
                                start_of_unit = scope.side_margin + (index * unit_size)
                                pos_x = start_of_unit + (unit_size / 2)

                            # if steps is set, only draw every steps'th entry
                            if !time_marker.steps or i % time_marker.steps == 0
                                _marker = createSVGElement(
                                    "text"
                                    {
                                        x: pos_x
                                        y: scope.height
                                        class: "default-text"
                                        # style: "font-size": "#{scope.fontSize}px"
                                        textAnchor: "middle"
                                        alignmentBaseline: "baseline"
                                    }
                                )
                                _marker.text(marker)
                                _g.append(_marker)

                            i += 1

                        # tooltip
                        _tooltip = angular.element("<div/>")

                        _tooltip.addClass("icsw-tooltip").css("min-width", "400px").css("max-width", "350px")
                        _tooltip.hide()
                        _div.append(_tooltip)
                        # calculate data to show
                        # total duration of data in milliseconds
                        total_duration = time_frame.end.diff(time_frame.start)
                        # total duration of requested timeframe
                        tf_duration = {
                            day: 24 * 3600
                            week: 7 * 24 * 3600
                            month: time_frame.start.daysInMonth() * 24 * 3600
                            year: 365 * 24 * 3600
                            decade: 10 * 365 * 24 * 3600
                        }[time_frame.duration_type] * 1000

                        pos_x = scope.side_margin
                        last_date = time_frame.start

                        data_for_iteration = scope.data

                        if scope.data.length > 0
                            has_last_event_after_time_frame_end = moment.utc(scope.data[scope.data.length-1].date).isAfter(time_frame.end)
                            if ! has_last_event_after_time_frame_end
                                # add dummy element for nice iteration below
                                data_for_iteration = data_for_iteration.concat('last')

                        _mousemove = (event) ->
                            entry = event.data

                            _pos_x = event.clientX - _tooltip.width() / 2
                            _pos_y = event.clientY - _tooltip.height() - 10

                            if _pos_x < 0
                                _pos_x = 0

                            _tooltip.css("position", "fixed")
                            _tooltip.css("left", "#{_pos_x}px")
                            _tooltip.css("top", "#{_pos_y}px")

                        for entry, index in data_for_iteration
                            if entry == 'last'
                                cur_date = time_frame.end
                                display_end = moment()
                            else
                                cur_date = moment.utc(entry.date)
                                if cur_date.isBefore(time_frame.start)
                                    # first event is before current time, but we must not draw that
                                    cur_date = time_frame.start
                                display_end = cur_date

                            duration = cur_date.diff(last_date)
                            entry_width = scope.draw_width * duration / tf_duration

                            if index != 0

                                last_entry = data_for_iteration[index-1]
                                entry_height = last_entry.$$data.height
                                cssclass = last_entry.$$data.svgClassName
                                label_height = 13

                                entry_height /= (base_height)
                                #pos_y = ((2/3)-entry_height ) * scope.height  # such that bar ends
                                entry_height *= (scope.height - label_height)

                                pos_y = scope.height - entry_height - label_height

                                # entry_height and pos_x are correct values, but we sometimes want some 'emphasis'
                                # these values are only used for display below
                                display_entry_width = entry_width
                                display_pos_x = pos_x
                                if entry_width <= 2
                                    if entry_width <= 1
                                        display_pos_x -= 1
                                    display_entry_width += 1

                                last_entry.display_end = display_end
                                _rect = createSVGElement(
                                    "rect"
                                    {
                                        width: display_entry_width
                                        height: entry_height
                                        x: display_pos_x
                                        y: pos_y
                                        rx: 1
                                        ry: 1
                                        class: cssclass
                                    }
                                )
                                _rect.bind("mouseenter", last_entry, (event) ->
                                    last_entry = event.data
                                    _tooltip.html(
                                        "State: " + last_entry.state +
                                        "<br/>Start: " + moment.utc(last_entry.date).format("DD.MM.YYYY HH:mm") +
                                        "<br/>End: " + last_entry.display_end.format("DD.MM.YYYY HH:mm") +
                                        "<br/>" + if last_entry.msg then last_entry.msg else ""
                                    )
                                    _mousemove(event)
                                    _tooltip.show()
                                ).bind("mouseleave", (event) ->
                                    _tooltip.hide()
                                ).bind("mousemove", last_entry, (event) ->
                                    _mousemove(event)
                                )
                                _g.append(_rect)

                            pos_x += entry_width
                            last_date = cur_date
                element.append(_div)


            scope.$watchGroup(
                [
                    "data"
                    () ->
                        return icswStatusHistorySettings.get_time_frame()
                ]
                (unused) ->
                    scope.update()
            )
    }
]).directive("icswToolsHistLogViewer", ["status_utils_functions", (status_utils_functions) ->
    return {
        restrict: 'E'
        scope: {
            data: '&'  # takes same data as line graph
            enabled: '&'
        }
        templateUrl: "icsw.tools.hist_log_viewer"
        link: (scope, element, attrs) ->
            scope.view_mode = 'new'
            scope.$watchGroup(
                ['enabled()', 'view_mode']
                () ->
                    scope.actual_data = []
                    if scope.enabled()
                        if scope.view_mode == 'all'
                            scope.actual_data = scope.data()

                        else if scope.view_mode == 'new'
                            last_line = {
                                msg: undefined
                            }
                            for line in scope.data()
                                if line.msg != last_line.msg
                                    scope.actual_data.push(line)
                                last_line = line

                        else if scope.view_mode == 'state_change'
                            last_line = {
                                state: undefined
                            }
                            for line in scope.data()
                                if line.state != last_line.state
                                    scope.actual_data.push(line)
                                last_line = line
            )
    }
])
