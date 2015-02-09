
status_history_module = angular.module("icsw.device.status_history",
        ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "ui.bootstrap.datetimepicker", "icsw.tools.status_history_utils"])

status_history_module.controller("icswDeviceStatusHistoryCtrl", ["$scope", "$compile", "$filter", "restDataSource", "sharedDataSource", "$q", "$modal", "$timeout", "msgbus",
    ($scope, $compile, $filter, restDataSource, sharedDataSource, $q, $modal, $timeout, msgbus) ->

        $scope.device_pks = []

        msgbus.emit("devselreceiver")
        msgbus.receive("devicelist", $scope, (name, args) ->
            $scope.devicepks = args[1]
        )
]).directive("icswDeviceStatusHistoryDevice", ["status_utils_functions", "Restangular", "ICSW_URLS", (status_utils_functions, Restangular, ICSW_URLS) ->
    return {
        restrict : "EA"
        templateUrl : "icsw.device.status_history_device"
        scope : {
            timerange: '='
            startdate: '='
        }
        link : (scope, el, attrs) ->
            scope.device_id = attrs.device
            scope.device_chart_id = "device_chart_" + scope.device_id
            scope.device_rest = undefined
            Restangular.one(ICSW_URLS.REST_DEVICE_LIST.slice(1)).get({'idx': scope.device_id}).then((new_data)->
                scope.device_rest = new_data[0]
            )
            scope.$watch('timerange', (unused) -> scope.update())
            scope.$watch('startdate', (unused) -> scope.update())
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
                        serv_name = check_command_name + ": " + description
                    else
                        serv_name = check_command_name
                else  # legacy data, only have some kind of id string to show
                    serv_name = description
                return serv_name
            scope.float_format = (n) -> return (n*100).toFixed(2) + "%"

            scope.calc_pie_data = (name, service_data) ->
                [unused, pie_data] = status_utils_functions.preprocess_service_state_data(service_data)
                return pie_data
            scope.update = () ->
                serv_cont = (new_data) ->
                    new_data = new_data[Object.keys(new_data)[0]]  # there is only one device
                    # new_data is dict, but we want it as list to be able to sort it
                    data = ([key, val, scope.calc_pie_data(key, val)] for key, val of new_data)
                    scope.service_data = _.sortBy(data, (entry) -> return scope.extract_service_name(entry[0]))

                status_utils_functions.get_service_data([scope.device_id], scope.startdate, scope.timerange, serv_cont)

            scope.update()
    }
]).directive("icswDeviceStatusHistoryOverview", ["status_utils_functions", (status_utils_functions) ->
    return {
        restrict : "EA"
        templateUrl : "icsw.device.status_history_overview"
        scope : {
            devicepks: '='
        }
        link : (scope, el, attrs) ->
            scope.devicepks = []
            scope.startdate = moment().startOf("day").subtract(1, "days")
            #scope.startdate = moment('Wed Jan 07 2015 00:00:00 GMT+0100 (CET)')
            scope.timerange = 'day'

            scope.set_timerange = (tr) ->
                scope.timerange = tr

            scope.update = () ->
                cont = (new_data) ->
                    scope.timespan_error = ""
                    scope.timespan_from = ""
                    scope.timespan_to = ""
                    if new_data.length > 0
                        timespan = new_data[0]
                        scope.timespan_from = moment.utc(timespan[0]).format("DD.MM.YYYY HH:mm")
                        scope.timespan_to = moment.utc(timespan[1]).format("DD.MM.YYYY HH:mm")
                    else
                        scope.timespan_error = "No data available for this time span"

                status_utils_functions.get_timespan(scope.startdate, scope.timerange, cont)

            scope.$watch('timerange', (unused) -> scope.update())
            scope.$watch('startdate', (unused) -> scope.update())
            scope.$watch(attrs["devicepks"], (new_val) ->
                if new_val and new_val.length
                    scope.devicepks = new_val
                    scope.update()
            )
            scope.update()
    }
])
