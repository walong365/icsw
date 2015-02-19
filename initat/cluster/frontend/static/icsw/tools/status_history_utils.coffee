

angular.module(
    "icsw.tools.status_history_utils", ["icsw.tools.piechart", "restangular"]
).directive('icswToolsDeviceHistStatusOverview', ["$parse", "status_utils_functions", ($parse, status_utils_functions) ->
    # shows piechart and possibly table of historic device status
    return {
        restrict: 'E',
        scope: {
            data: "="  # if data is passed right through here, the other attributes are discarded
            deviceid: "="
            startdate: "="
            timerange: "="
        },
        templateUrl: "icsw.tools.device_hist_status"
        link: (scope, element, attrs) ->
            scope.show_table = scope.$eval(attrs.showTable)

            # TODO: make this into a filter, then remove also from serviceHist*
            scope.float_format = (n) -> return (n*100).toFixed(2) + "%"

            scope.pie_data = []
            weights = {
                "Up": -10
                "Down": -8
                "Unreachable": -6
                "Undetermined": -4
            }

            colors = {
                "Up": "#66dd66"
                "Down": "#ff7777"
                "Unreachable": "#f0ad4e"
                "Undetermined": "#c7c7c7"
            }

            scope.update_from_server = () ->
                cont = (new_data) ->
                    new_data = new_data[Object.keys(new_data)[0]]  # there is only one device
                    [scope.host_data, scope.pie_data] = status_utils_functions.preprocess_state_data(new_data, weights, colors, scope.float_format)

                status_utils_functions.get_device_data([scope.deviceid], scope.startdate, scope.timerange, cont)

            scope.update_from_local_data = () ->
                if scope.data?
                    [scope.host_data, scope.pie_data] = status_utils_functions.preprocess_state_data(scope.data, weights, colors, scope.float_format)

            if attrs.data?
                scope.$watch('data', (unused) -> scope.update_from_local_data())
            else
                scope.$watchGroup(['deviceid', 'startdate', 'timerange'], (unused) -> scope.update_from_server())
    }
]).directive('icswToolsServiceHistStatusOverview', ["$parse", "status_utils_functions", ($parse, status_utils_functions) ->
    # shows piechart of state of service. shows how many service are in which state at a given time frame
    return {
        restrict: 'E',
        scope: {
            data: "="  # if data is passed right through here, the other attributes are discarded
            deviceid: "="
            startdate: "="
            timerange: "="
        },
        templateUrl: "icsw.tools.service_hist_status"
        link: (scope, element, attrs) ->

            # TODO: see above
            scope.float_format = (n) -> return (n*100).toFixed(2) + "%"

            scope.pie_data = []

            scope.update_from_server = () ->
                cont = (new_data) ->
                    new_data = new_data[Object.keys(new_data)[0]]  # there is only one device
                    [scope.service_data, scope.pie_data] = status_utils_functions.preprocess_service_state_data(new_data)

                status_utils_functions.get_service_data([scope.deviceid], scope.startdate, scope.timerange, cont, merge_services=1)

            scope.update_from_local_data = () ->
                if scope.data?
                    [scope.service_data, scope.pie_data] = status_utils_functions.preprocess_service_state_data(scope.data)

            if attrs.data?
                scope.$watch('data', (unused) -> scope.update_from_local_data())
            else
                scope.$watchGroup(['deviceid', 'startdate', 'timerange'], (unused) -> scope.update_from_server())
    }
]).service('status_utils_functions', ["Restangular", "ICSW_URLS", (Restangular, ICSW_URLS) ->
    get_device_data = (device_ids, start_date, timerange, cont) ->
        query_data = {
            'device_ids': device_ids.join(),
            'date': moment(start_date).unix()  # ask server in utc
            'duration_type': timerange,
        }
        base = Restangular.all(ICSW_URLS.MON_GET_HIST_DEVICE_DATA.slice(1))
        base.getList(query_data).then((new_data) ->
            # customGET fucks up the query data, so just fake lists
            obj = new_data.plain()[0]
            cont(obj)
        )
    get_service_data = (device_ids, start_date, timerange, cont, merge_services=0) ->
        # merge_services: boolean as int
        expect_array = merge_services != 0
        query_data = {
            'device_ids': device_ids.join(),
            'date': moment(start_date).unix()  # ask server in utc
            'duration_type': timerange,
            'merge_services': merge_services,
        }
        base = Restangular.all(ICSW_URLS.MON_GET_HIST_SERVICE_DATA.slice(1))
        # we always return a list for easier REST handling
        base.getList(query_data).then((data_pseudo_list) ->
            # need plain() to get rid of restangular stuff
            console.log 'serv', data_pseudo_list.plain()[0]
            cont(data_pseudo_list.plain()[0])
        )

        line_base = Restangular.all(ICSW_URLS.MON_GET_HIST_SERVICE_LINE_GRAPH_DATA.slice(1))
        line_base.getList(query_data).then((data) ->
            data = data.plain()
            console.log 'dat', data
        )
    get_timespan = (start_date, timerange, cont) ->
        query_data = {
            'date': moment(start_date).unix()  # ask server in utc
            'duration_type': timerange,
        }
        base = Restangular.all(ICSW_URLS.MON_GET_HIST_TIMESPAN.slice(1))
        base.getList(query_data).then(cont)
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

            colors = {
                "Ok": "#66dd66"
                "Warning": "#f0ad4e"
                "Critical": "#ff7777"
                "Unknown": "#c7c7c7"
                "Undetermined": "#c7c7c7"
            }

            return preprocess_state_data(new_data, weights, colors, float_format)

    return {
        float_format: float_format
        get_device_data: get_device_data
        get_service_data: get_service_data
        get_timespan: get_timespan
        preprocess_state_data: preprocess_state_data
        preprocess_service_state_data: preprocess_service_state_data
    }
])

