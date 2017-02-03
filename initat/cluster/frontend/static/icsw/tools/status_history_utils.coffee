# Copyright (C) 2012-2017 init.at
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
                    value: _.round(d.value * 100, 3)
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
]).service("icswToolsHistLineGraphReact",
[
    "$q", "icswStatusHistorySettings", "icswTooltipTools",
(
    $q, icswStatusHistorySettings, icswTooltipTools,
) ->
    MAX_DATA = 1000
    {svg, g, div, path, span, rect, text} = React.DOM
    marker_fact = React.createFactory(
        React.createClass(
            propTypes: {
                data: React.PropTypes.array
                width: React.PropTypes.number
                height: React.PropTypes.number
                sideMargin: React.PropTypes.number
            }

            displayName: "HistLineGraphMarker"

            render: () ->
                el_list = []
                draw_width = @props.width - 2 * @props.sideMargin
                time_marker = icswStatusHistorySettings.get_time_marker()
                i = 0
                for marker, index in time_marker.data
                    if time_marker.time_points
                        # time is exactly at certain points
                        pos_x = @props.sideMargin + index * draw_width / (time_marker.data.length-1)
                    else
                        # pos should be in the middle of the durations, such as week days, month
                        unit_size = draw_width / time_marker.data.length
                        start_of_unit = @props.sideMargin + (index * unit_size)
                        pos_x = start_of_unit + (unit_size / 2)

                    # if steps is set, only draw every steps'th entry
                    if !time_marker.steps or i % time_marker.steps == 0
                        el_list.push(
                            text(
                                {
                                    key: "marker#{i}"
                                    x: pos_x
                                    y: @props.height
                                    className: "default-text"
                                    textAnchor: "middle"
                                    alignmentBaseline: "baseline"
                                }
                                marker
                            )
                        )
                    i++
                return g(
                    {
                        key: "top"
                    }
                    el_list
                )

        )
    )
    return React.createClass(
        propTypes: {
            width: React.PropTypes.number
            height: React.PropTypes.number
            baseHeight: React.PropTypes.number
            data: React.PropTypes.array
            fontSize: React.PropTypes.number
            sideMargin: React.PropTypes.number
            timeFrame: React.PropTypes.object
            # tooltip
            tooltip: React.PropTypes.object
            # for host or service
            forHost: React.PropTypes.bool
        }

        displayName: "HistLineGraph"

        render: () ->
            div_els = []
            if @props.data.length > MAX_DATA
                div_els.push(
                    span(
                        {
                            key: "warn"
                            className: "label label-danger"
                        }
                        "Too much data to display (#{@props.data.length} > #{MAX_DATA})"
                    )
                )
            else
                g_elements = [
                    marker_fact(
                        {
                            key: "markers"
                            data: @props.data
                            sideMargin: @props.sideMargin
                            width: @props.width
                            height: @props.height
                        }
                    )
                ]
                # calculate data to show
                # total duration of requested timeframe
                tf_duration = {
                    day: 24 * 3600
                    week: 7 * 24 * 3600
                    month: @props.timeFrame.start.daysInMonth() * 24 * 3600
                    year: 365 * 24 * 3600
                    decade: 10 * 365 * 24 * 3600
                }[@props.timeFrame.duration_type] * 1000

                pos_x = @props.sideMargin
                last_date = @props.timeFrame.start

                data_for_iteration = @props.data
                if @props.data.length > 0
                    has_last_event_after_time_frame_end = moment.utc(@props.data[@props.data.length-1].date).isAfter(@props.timeFrame.end)
                    if ! has_last_event_after_time_frame_end
                        # add dummy element for nice iteration below
                        data_for_iteration = data_for_iteration.concat('last')

                for entry, index in data_for_iteration
                    if entry == 'last'
                        cur_date = @props.timeFrame.end
                        display_end = moment()
                    else
                        cur_date = moment.utc(entry.date)
                        if cur_date.isBefore(@props.timeFrame.start)
                            # first event is before current time, but we must not draw that
                            cur_date = @props.timeFrame.start
                        display_end = cur_date

                    duration = cur_date.diff(last_date)
                    draw_width = @props.width - 2 * @props.sideMargin
                    entry_width = draw_width * duration / tf_duration

                    if index != 0

                        last_entry = data_for_iteration[index-1]

                        label_height = 13

                        entry_height = last_entry.$$data.height
                        entry_height /= (@props.baseHeight)
                        #pos_y = ((2/3)-entry_height ) * scope.height  # such that bar ends
                        entry_height *= (@props.height - label_height)

                        pos_y = @props.height - entry_height - label_height

                        # entry_height and pos_x are correct values, but we sometimes want some 'emphasis'
                        # these values are only used for display below
                        display_entry_width = entry_width
                        display_pos_x = pos_x
                        if entry_width <= 2
                            if entry_width <= 1
                                display_pos_x -= 1
                            display_entry_width += 1

                        last_entry.display_end = display_end
                        g_elements.push(
                            rect(
                                {
                                    key: "el#{index}"
                                    width: display_entry_width
                                    height: entry_height
                                    x: display_pos_x
                                    y: pos_y
                                    rx: 1
                                    ry: 1
                                    className: last_entry.$$data.svgClassName
                                    data: index - 1
                                    onMouseEnter: (event) =>
                                        _idx = event.target.getAttribute("data")
                                        entry = data_for_iteration[_idx]
                                        node = {
                                            node_type: if @props.forHost then "histline.device" else "histline.service"
                                            data: entry
                                        }
                                        entry.$$start = moment.utc(entry.date).format("DD.MM.YYYY HH:mm")
                                        entry.$$end = entry.display_end.format("DD.MM.YYYY HH:mm")
                                        icswTooltipTools.show(@props.tooltip, node)
                                    onMouseMove: (event) =>
                                        icswTooltipTools.position(@props.tooltip, event)
                                    onMouseLeave: (event) =>
                                        icswTooltipTools.hide(@props.tooltip)
                                }
                            )
                        )
                    pos_x += entry_width
                    last_date = cur_date
                div_els.push(
                    svg(
                        {
                            key: "top"
                            width: @props.width
                            height: @props.height
                        }
                        g(
                            {
                                key: "topg"
                            }
                            rect(
                                {
                                    key: "topr"
                                    width: @props.width
                                    height: @props.height
                                    x: 0
                                    y: 0
                                    fill: "rgba(0, 0, 0, 0.0)"
                                }
                            )
                            g_elements
                        )
                    )
                )
            tl_div = div(
                {
                    key: "top"
                    className: "icsw-chart"
                    style: {
                        width: "#{@props.width}px"
                        height: "#{@props.height}px"
                        # ???
                        marginBottom: "7px"
                    }
                }
                div_els
            )
            return tl_div
    )
]).directive("icswToolsHistLineGraph",
[
    "status_utils_functions", "$timeout", "icswStatusHistorySettings", "icswTooltipTools",
    "icswToolsHistLineGraphReact",
(
    status_utils_functions, $timeout, icswStatusHistorySettings, icswTooltipTools,
    icswToolsHistLineGraphReact,
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
            scope.height = scope.heightAttr() or base_height

            scope.update = () ->
                $timeout(scope.actual_update)

            scope.actual_update = () ->

                struct = icswTooltipTools.create_struct(element)
                time_frame = icswStatusHistorySettings.get_time_frame()

                # calculate data to show
                if time_frame? and scope.data?
                    _el = ReactDOM.render(
                        React.createElement(
                            icswToolsHistLineGraphReact
                            {
                                data: scope.data
                                width: scope.width
                                height: scope.height
                                baseHeight: base_height
                                fontSize: 10
                                sideMargin: 10
                                timeFrame: time_frame
                                tooltip: struct
                                forHost: scope.forHost()
                            }
                        )
                        element[0]
                    )

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
