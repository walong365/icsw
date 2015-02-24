

angular.module(
    "icsw.tools.status_history_utils", ["icsw.tools.piechart", "restangular"]
).directive('icswToolsDeviceHistStatusOverview', ["$parse", "status_utils_functions", ($parse, status_utils_functions) ->
    # shows piechart and possibly table of historic device status
    # used in status history page and monitoring overview
    return {
        restrict: 'E',
        scope: {
            data: "="  # if data is passed right through here, the other attributes are discarded
                       # data must be defined if we are not below the status history ctrl
            deviceid: "="
        },
        require: '?^icswDeviceStatusHistoryOverview'
        templateUrl: "icsw.tools.device_hist_status"
        link: (scope, element, attrs, status_history_ctrl) ->
            scope.detailed_view = scope.$eval(attrs.detailedView)

            # TODO: make this into a filter, then remove also from serviceHist*
            scope.float_format = (n) -> return (n*100).toFixed(2) + "%"

            scope.pie_data = []
            weights = {
                "Up": -10
                "Down": -8
                "Unreachable": -6
                "Undetermined": -4
            }

            scope.host_data = []
            scope.pie_data = []
            scope.line_graph_data = []

            scope.update_from_server = () ->
                # TODO: this loading should probably be refactored into status_history.coffee, such that these directives
                #       here only get the direct data. then we can centralise the loading there.
                #       NOTE: keep consistent with service below
                if status_history_ctrl.time_frame?
                    cont = (new_data) ->
                        new_data = new_data[Object.keys(new_data)[0]]  # there is only one device
                        [scope.host_data, scope.pie_data] =
                            status_utils_functions.preprocess_state_data(new_data, weights, status_utils_functions.host_colors, scope.float_format)

                    line_graph_cont = (new_data) ->
                        new_data = new_data[Object.keys(new_data)[0]]  # there is only one device
                        if new_data?
                            scope.line_graph_data = new_data
                        else
                            scope.line_graph_data = []

                    time_frame = status_history_ctrl.time_frame
                    status_utils_functions.get_device_data([scope.deviceid], time_frame.date_gui, time_frame.duration_type, cont)
                    status_utils_functions.get_device_data([scope.deviceid], time_frame.date_gui, time_frame.duration_type, line_graph_cont, true)
                else
                    scope.host_data = []
                    scope.pie_data = []

            scope.update_from_local_data = () ->
                if scope.data?
                    [scope.host_data, scope.pie_data] =
                        status_utils_functions.preprocess_state_data(scope.data, weights, status_utils_functions.host_colors, scope.float_format)

            if attrs.data?
                scope.$watch('data', (unused) -> scope.update_from_local_data())
            else
                scope.$watchGroup(
                    ['deviceid', () -> return status_history_ctrl.time_frame]
                    (unused) -> scope.update_from_server())
    }
]).directive('icswToolsServiceHistStatusOverview', ["$parse", "status_utils_functions", ($parse, status_utils_functions) ->
    # shows piechart of state of service. shows how many service are in which state at a given time frame
    # currently only used in monitoring_overview
    return {
        restrict: 'E',
        scope: {
            data: "="  # if data is passed right through here, the other attributes are discarded
                       # data must be defined if we are not below the status history ctrl
            deviceid: "="
        },
        templateUrl: "icsw.tools.service_hist_status"
        require: '?^icswDeviceStatusHistoryCtrl'
        link: (scope, element, attrs, status_history_ctrl) ->

            # TODO: see above
            scope.float_format = (n) -> return (n*100).toFixed(2) + "%"

            scope.pie_data = []

            scope.update_from_server = () ->
                if status_history_ctrl.time_frame?
                    cont = (new_data) ->
                        new_data = new_data[Object.keys(new_data)[0]]  # there is only one device
                        new_data = new_data['main']  # only main data here
                        [scope.service_data, scope.pie_data] = status_utils_functions.preprocess_service_state_data(new_data)

                    status_utils_functions.get_service_data(
                        [scope.deviceid],
                        status_history_ctrl.time_frame.date_gui,
                        status_history_ctrl.time_frame.time_range,
                        cont,
                        merge_services=1)

            scope.update_from_local_data = () ->
                if scope.data?
                    [scope.service_data, scope.pie_data] = status_utils_functions.preprocess_service_state_data(scope.data)

            if attrs.data?
                scope.$watch('data', (unused) -> scope.update_from_local_data())
            else
                scope.$watchGroup(
                    ['deviceid', () -> return status_history_ctrl.time_frame]
                    (unused) -> scope.update_from_server())
    }
]).service('status_utils_functions', ["Restangular", "ICSW_URLS", (Restangular, ICSW_URLS) ->
    service_colors = {
            "Ok": "#66dd66"
            "Warning": "#f0ad4e"
            "Critical": "#ff7777"
            "Unknown": "#c7c7c7"
            "Undetermined": "#c7c7c7"
        }
    host_colors = {
        "Up": "#66dd66"
        "Down": "#ff7777"
        "Unreachable": "#f0ad4e"
        "Undetermined": "#c7c7c7"
    }

    get_device_data = (device_ids, start_date, timerange, cont, line_graph_data=false) ->
        query_data = {
            'device_ids': device_ids.join(),
            'date': moment(start_date).unix()  # ask server in utc
            'duration_type': timerange,
        }
        if line_graph_data
            base = Restangular.all(ICSW_URLS.MON_GET_HIST_DEVICE_LINE_GRAPH_DATA.slice(1))
        else
            base = Restangular.all(ICSW_URLS.MON_GET_HIST_DEVICE_DATA.slice(1))
        base.getList(query_data).then((new_data) ->
            # customGET fucks up the query data, so just fake lists
            obj = new_data.plain()[0]
            cont(obj)
        )
    get_service_data = (device_ids, start_date, timerange, cont, merge_services=0, line_graph_data=false) ->
        # merge_services: boolean as int
        # line_graph_data: boolean as int, get only line graph data
        query_data = {
            'device_ids': device_ids.join(),
            'date': moment(start_date).unix()  # ask server in utc
            'duration_type': timerange,
            'merge_services': merge_services,
        }
        if line_graph_data
            base = Restangular.all(ICSW_URLS.MON_GET_HIST_SERVICE_LINE_GRAPH_DATA.slice(1))
        else
            base = Restangular.all(ICSW_URLS.MON_GET_HIST_SERVICE_DATA.slice(1))
        # we always return a list for easier REST handling
        base.getList(query_data).then((data_pseudo_list) ->
            # need plain() to get rid of restangular stuff
            cont(data_pseudo_list.plain()[0])
        )
    get_timespan = (start_date, timerange, cont) ->
        query_data = {
            'date': moment(start_date).unix()  # ask server in utc
            'duration_type': timerange,
        }
        base = Restangular.all(ICSW_URLS.MON_GET_HIST_TIMESPAN.slice(1))
        base.customGET("", query_data).then(cont)
    float_format = (n) -> return (n*100).toFixed(2) + "%"
    preprocess_state_data = (new_data, weights, colors) ->
        formatted_data = _.cloneDeep(new_data)
        for key of weights
            if not _.any(new_data, (d) -> return d['state'] == key)
                formatted_data.push({'state': key, 'value': 0})

        for d in formatted_data
            d['value'] = float_format(d['value'])
        final_data = _.sortBy(formatted_data, (d) -> return weights[d['state']])

        new_data = _.sortBy(new_data, (d) -> return weights[d['state']])

        pie_data = []
        for d in new_data
            if d['state'] != "Flapping"  # can't display flapping in pie
                pie_data.push {
                    'title': d['state']
                    'value': Math.round(d['value']*10000) / 100
                    'color': colors[d['state']]
                }
        return [final_data, pie_data]
    preprocess_service_state_data = (new_data, float_format) ->
        weights = {
            "Ok": -10
            "Warning": -9
            "Critical": -8
            "Unknown": -5
            "Undetermined": -4
        }
        return preprocess_state_data(new_data, weights, service_colors, float_format)
    return {
        float_format: float_format
        get_device_data: get_device_data
        get_service_data: get_service_data
        get_timespan: get_timespan
        preprocess_state_data: preprocess_state_data
        preprocess_service_state_data: preprocess_service_state_data
        service_colors: service_colors
        host_colors: host_colors
    }
]).directive("icswToolsHistLineGraph", ["status_utils_functions", "$timeout", (status_utils_functions, $timeout) ->
    return {
        restrict: 'E'
        scope   : {
            'data' : '='
            'forHost' : '&'
            'widthAttr' : '&width'
            'heightAttr' : '&height'
            'clickAttr' : '&click'
        }
        require : "^icswDeviceStatusHistoryOverview"
        template: """
<div class="icsw-chart" ng-attr-style="width: {{width}}px; height: {{height}}px;"> <!-- this must be same size as svg for tooltip positioning to work -->
    <svg ng-attr-width="{{width}}" ng-attr-height="{{height}}" >
        <g ng-show="!error">

            <rect ng-attr-width="{{width}}" ng-attr-height="{{height}}" x="0" y="0" fill="rgba(0, 0, 0, 0.0)"
            ng-click="entry_clicked(undefined)"></rect>
            <rect ng-repeat="entry in data_display" ng-attr-x="{{entry.pos_x}}" ng-attr-y="{{entry.pos_y}}"
                  ng-attr-width="{{entry.width}}" ng-attr-height="{{entry.height}}" rx="1" ry="1"
                  ng-attr-style="fill:{{entry.color}};stroke-width:0;stroke:rgb(0,0,0)"
                  ng-mouseenter="mouse_enter(entry)"
                  ng-mouseleave="mouse_leave(entry)"
                  ng-mousemove="mouse_move(entry, $event)"
                  ng-click="entry_clicked(entry)"></rect>
        </g>
        <g ng-show="!error">
            <text ng-repeat="marker in timemarker_display" ng-attr-x="{{marker.pos_x}}" ng-attr-y="{{height}}"  ng-attr-style="fill:black;" font-size="{{fontSize}}px" text-anchor="middle" alignment-baseline="baseline">{{marker.text}}</text>
        </g>
        <g ng-show="error">
            <text x="1" y="25"  font-size="12px" fill="red">{{error}}</text>
        </g>
    </svg>
    <div class="icsw-tooltip" ng-show="tooltip_entry" ng-attr-style="top: {{tooltipY}}px; left: {{tooltipX}}px; min-width: 350px; max-width: 350px;">
        State: {{tooltip_entry.state}}<br/>
        Start: {{tooltip_entry.start}}<br/>
        End: {{tooltip_entry.end}}<br/>
        <span ng-show="tooltip_entry.msg">{{tooltip_entry.msg}} <br /></span>
    </div>
</div>
"""
        link: (scope, element, attrs, status_history_ctrl) ->
            scope.mouse_enter = (entry) ->
                scope.tooltip_entry = entry
            scope.mouse_leave = (entry) ->
                scope.tooltip_entry = undefined
            scope.mouse_move = (entry, event) ->
                # not very elegant
                tooltip = element[0].children[0].children[1]
                scope.tooltipX = event.offsetX - (tooltip.clientWidth/2)
                scope.tooltipY = event.offsetY - (tooltip.clientHeight) - 10
            scope.entry_clicked = (entry) ->
                console.log 'clicked'
                scope.clickAttr()
                # TODO possibly pass entry outside along the lines of  scope.clickAttr()({entry: entry)) and setting click just to handle_click (not hande_click())

            scope.width = scope.widthAttr() or 300
            base_height = 30
            scope.height = scope.heightAttr() or base_height

            scope.fontSize = 10

            scope.side_margin = 15
            scope.draw_width = scope.width - 2 * scope.side_margin

            scope.update = () ->
                $timeout(scope.actual_update)
            scope.actual_update = () ->

                time_frame = status_history_ctrl.time_frame

                # cleanup
                scope.data_display = []
                scope.timemarker_display = []
                scope.error = ""

                # calculate data to show
                if time_frame?

                    if scope.data.length > 5000
                        scope.error = "Too much data to display"
                    else if time_frame.duration_type == "year" and !scope.forHost()
                        # no error, but also display nothing
                    else
                        # set time marker
                        time_marker = status_history_ctrl.get_time_marker()
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
                                scope.timemarker_display.push({
                                        text: marker
                                        pos_x: pos_x
                                })

                            i += 1


                        # calculate data to show
                        total_duration = time_frame.end.diff(time_frame.start)

                        pos_x = scope.side_margin
                        last_date = time_frame.start

                        data_for_iteration = scope.data

                        if scope.data.length > 0
                            has_last_event_after_time_frame_end = moment.utc(scope.data[scope.data.length-1].date).isAfter(time_frame.end)
                            if ! has_last_event_after_time_frame_end
                                # add dummy element for nice iteration below
                                data_for_iteration = data_for_iteration.concat('last')

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
                                entry_width = scope.draw_width * duration / total_duration

                                if index != 0

                                    last_entry = data_for_iteration[index-1]

                                    # these heights are for a total height of 30
                                    if scope.forHost()
                                        entry_height = switch last_entry.state
                                            when "Up" then 15
                                            when "Down" then 30
                                            when "Unreachable" then 22
                                            when "Undetermined" then 18
                                        color = status_utils_functions.host_colors[last_entry.state]
                                    else
                                        entry_height = switch last_entry.state
                                            when "Ok" then 15
                                            when "Warning" then 22
                                            when "Critical" then 30
                                            when "Unknown" then 18
                                            when "Undetermined" then 18
                                        color = status_utils_functions.service_colors[last_entry.state]

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

                                    scope.data_display.push(
                                        {
                                            pos_x : display_pos_x
                                            pos_y : pos_y
                                            height: entry_height
                                            width : display_entry_width
                                            color : color
                                            msg   : last_entry.msg
                                            state : last_entry.state
                                            # use actual start, not nice start with is always higher than time frame start
                                            start : moment.utc(last_entry.date).format("DD.MM.YYYY HH:mm")
                                            end   : display_end.format("DD.MM.YYYY HH:mm")
                                        }
                                    )

                                pos_x += entry_width
                                last_date = cur_date


            scope.$watchGroup(['data', () -> return status_history_ctrl.time_frame], (unused) -> scope.update() )
    }
]).directive("icswToolsHistLogViewer", ["status_utils_functions", (status_utils_functions) ->
    return {
        restrict: 'E'
        scope   : {
            'data' : '&'  # takes same data as line graph
            'enabled' : '&'
        }
        template: """
<table class="table table-condensed table-striped" ng-show="actual_data.length > 0">
    <thead>
        <tr>
            <th>Date</th>
            <th>State</th>
            <th>Message</th>
        </tr>
    </thead>
    <tbody>
        <tr ng-repeat="entry in actual_data" class="text-left">
            <td ng-bind="entry.date | datetime_concise"></td>
            <td ng-bind="entry.state | limit_text_no_dots:3"></td>
            <td ng-bind="entry.msg"></td>
        </tr>
    </tbody>
</table>
"""
        link: (scope, element, attrs) ->
            scope.$watch('enabled()', () ->
                if scope.enabled()
                    scope.actual_data = scope.data()
                else
                    scope.actual_data = []
            )
    }
])
