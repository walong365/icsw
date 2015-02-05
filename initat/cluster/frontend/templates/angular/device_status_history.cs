{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

{% verbatim %}
status_history_template = """
<h2>Status History</h2>

<h4>
    <div class="form-inline">
        Timerange:
        <div class="form-group">
            <div class="input-group">
                <input type="text" class="form-control" ng-model="startdate"></input>
                <span class="dropdown-toggle input-group-addon">
                    <div class="dropdown">
                         <button class="btn dropdown-toggle btn-xs" data-toggle="dropdown">
                         <i class="glyphicon glyphicon-calendar"></i>
                         </button>
                         <ul class="dropdown-menu" role="menu">
                             <datetimepicker ng-model="startdate"
                                 data-datetimepicker-config="{ startView:'day', minView:'day' }" />
                         </ul>
                    </div>
                </span>
            </div>
            &nbsp;
            <div class="btn-group">
                <button type="button" class="btn btn-xs btn-primary dropdown-toggle" data-toggle="dropdown">
                    <span class="glyphicon glyphicon-time"></span>
                    {{timerange}} <span class="caret"></span>
                </button>
                <ul class="dropdown-menu">
                    <li ng-click="set_timerange('day')"><a href="#">day</a></li>
                    <li ng-click="set_timerange('week')"><a href="#">week</a></li>
                    <li ng-click="set_timerange('month')"><a href="#">month</a></li>
                    <li ng-click="set_timerange('year')"><a href="#">year</a></li>
                    <!-- values parsed by rest_views.py -->
                </ul>
            </div>
        </div>
    </div>
</h4>

<h4 ng-if="!timespan_error ">Showing data from {{timespan_from}} to {{timespan_to}}:</h4>
<h4 class="alert alert-danger" style="width: 300px" ng-if="timespan_error ">{{timespan_error}}</h4>

<div ng-repeat="device in devicepks">
    <devicestatushistory device="{{device}}" timerange="timerange" startdate="startdate" />
</div>
"""

device_status_history_template = """
<h3>{{device_rest.full_name}}</h3>

<div class="row" style="width: 650px">
    <div class="col-md-12">
        <div style="width: auto">
            <device-hist-status-overview deviceid="device_id" startdate="startdate" timerange="timerange" show-table="true"></device-hist-status-overview>
        </div>
    </div>

    <div class="col-md-12">
        <table class="table table-condensed table-hover table-striped">
            <thead>
                <tr>
                    <th >Service</th>
                    <th style="width: 10%;" class="text-center"><!-- chart --></th>
                    <th style="width: 50px;" class="text-center">Ok</th>
                    <th style="width: 50px;" class="text-center">Warning</th>
                    <th style="width: 50px;" class="text-center">Critical</th>
                    <th style="width: 50px;" class="text-center">Unknown</th>
                    <th style="width: 50px;" class="text-center">Undetermined</th>
                    <th style="width: 50px;" class="text-center">Flapping</th>
                </tr>
            </thead>
            <tbody>
                <tr ng-repeat="entry in service_data">
                    <td> {{ extract_service_name(entry[0]) }} </td>
                    <td class="text-right">
                        <icsw-piechart diameter="28" data="entry[2]"></icsw-piechart>
                    </td>
                    <td class="text-right"> {{ extract_service_value(entry[1], "Ok") }} </td>
                    <td class="text-right"> {{ extract_service_value(entry[1], "Warning") }} </td>
                    <td class="text-right"> {{ extract_service_value(entry[1], "Critical") }} </td>
                    <td class="text-right"> {{ extract_service_value(entry[1], "Unknown") }} </td>
                    <td class="text-right"> {{ extract_service_value(entry[1], "Undetermined") }} </td>
                    <td class="text-right"> {{ extract_service_value(entry[1], "Flapping") }} </td>
                </tr>
            </tbody>
        </table>
    </div>
</div>
"""
{% endverbatim %}


status_history_module = angular.module("icsw.device.status_history", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "ui.bootstrap.datetimepicker", "status_utils"])

status_history_module.controller("status_history_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "restDataSource", "sharedDataSource", "$q", "$modal", "$timeout", "msgbus",
    ($scope, $compile, $filter, $templateCache, restDataSource, sharedDataSource, $q, $modal, $timeout, msgbus) ->

        $scope.device_pks = []

        msgbus.emit("devselreceiver")
        msgbus.receive("devicelist", $scope, (name, args) ->
            $scope.devicepks = args[1]
        )
]).directive("devicestatushistory", ($templateCache, status_utils_functions, Restangular) ->
    return {
        restrict : "EA"
        template : $templateCache.get("device_status_history_template.html")
        scope : {
            timerange: '='
            startdate: '='
        }
        link : (scope, el, attrs) ->
            scope.device_id = attrs.device
            scope.device_chart_id = "device_chart_" + scope.device_id
            scope.device_rest = undefined
            Restangular.one("{% url 'rest:device_list' %}".slice(1)).get({'idx': scope.device_id}).then((new_data)->
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


}).directive("statushistory", ($templateCache, status_utils_functions) ->
    return {
        restrict : "EA"
        template : $templateCache.get("status_history_template.html")
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
}).run(($templateCache) ->
    $templateCache.put("status_history_template.html", status_history_template)
    $templateCache.put("device_status_history_template.html", device_status_history_template)
)


{% endinlinecoffeescript %}

</script>


