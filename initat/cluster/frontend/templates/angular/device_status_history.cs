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
<h3>{{device_rest.name }}</h3>

<div style="width: 470px">
    <device-hist-status-overview deviceid="device_id" startdate="startdate" timerange="timerange" show-table="true"></device-hist-status-overview>
</div>

<div class="row" style="width: 600px">
    <div class="col-md-12">
        <table class="table table-condensed table-hover table-striped">
            <thead>
                <tr>
                    <th >Service</th>
                    <th style="width: 10%;" class="text-center">Ok</th>
                    <th style="width: 10%;" class="text-center">Warning</th>
                    <th style="width: 10%;" class="text-center">Critical</th>
                    <th style="width: 10%;" class="text-center">Unknown</th>
                    <th style="width: 10%;" class="text-center">Undetermined</th>
                    <th style="width: 10%;" class="text-center">Flapping</th>
                </tr>
            </thead>
            <tbody>
                <tr ng-repeat="entry in service_data">
                    <td> {{ extract_service_name(entry[0]) }} </td>
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


# don't know who needs restangular here, but there are strange errors if removed
status_history_module = angular.module("icsw.device.status_history", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "ui.bootstrap.datetimepicker", "status_utils"])

angular_module_setup([status_history_module])

status_history_module.controller("status_history_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "$timeout", "$resource",
    ($scope, $compile, $filter, $templateCache, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, $timeout, $resource) ->
]).directive("devicestatushistory", ($templateCache, $resource) ->
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
            device_resource = $resource("{% url 'rest:device_list' %}/:id", {});
            scope.device_rest = device_resource.get({'id': scope.device_id})
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

            scope.update = () ->
                serv_cont = (new_data) ->
                    # new_data is dict, but we want it as list to be able to sort it
                    data = ([key, val] for key, val of new_data)
                    scope.service_data = _.sortBy(data, (entry) -> return scope.extract_service_name(entry[0]))

                status_history_utils.get_service_data($resource, scope.device_id, scope.startdate, scope.timerange, serv_cont)

            scope.update()

}).directive("statushistory", ($templateCache, $resource) ->
    return {
        restrict : "EA"
        template : $templateCache.get("status_history_template.html")
        link : (scope, el, attrs) ->
            scope.devicepks = attrs["devicepks"].split(',')
            #scope.startdate = moment().startOf("day")
            scope.startdate = moment('Wed Jan 07 2015 00:00:00 GMT+0100 (CET)')
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
                        scope.timespan_from = moment(timespan[0]).format("DD.MM.YYYY HH:MM")
                        scope.timespan_to = moment(timespan[1]).format("DD.MM.YYYY HH:MM")
                    else
                        scope.timespan_error = "No data available for this time span"

                status_history_utils.get_timespan($resource, scope.startdate, scope.timerange, cont)

            scope.$watch('timerange', (unused) -> scope.update())
            scope.$watch('startdate', (unused) -> scope.update())
            scope.update()
}).run(($templateCache) ->
    $templateCache.put("status_history_template.html", status_history_template)
    $templateCache.put("device_status_history_template.html", device_status_history_template)
)



status_history_utils = {
    get_service_data: ($resource, device_id, start_date, timerange, cont) ->
        res = $resource("{% url 'mon:get_hist_service_data' %}", {}, {'query': {method: 'GET', isArray: false}})
        query_data = {
            'device_id': device_id,
            'date': moment(start_date).unix()  # ask server in utc
            'duration_type': timerange,
        }
        res.query(query_data, (new_data) ->
            cont(new_data.toJSON())  # toJSON gets rid of object properties of $resource, which would otherwise be iterated over
        )
    get_timespan: ($resource, start_date, timerange, cont) ->
        res = $resource("{% url 'mon:get_hist_timespan' %}", {})
        query_data = {
            'date': moment(start_date).unix()  # ask server in utc
            'duration_type': timerange,
        }
        res.query(query_data, (new_data) ->
            cont(new_data)
        )
}

{% endinlinecoffeescript %}

</script>


