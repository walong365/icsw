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

<div ng-repeat="device in devicepks">
    <devicestatushistory device="{{device}}" timerange="timerange" startdate="startdate" />
</div>
"""

device_status_history_template = """
<h3>{{device_rest.name }}</h3>

<table class="table table-condensed table-hover table-striped">
    <thead>
        <tr>
            <th>State</th>
            <th>State type</th>
            <th>Ratio of state</th>
        </tr>
    </thead>
    <tbody>
        <tr ng-repeat="state in host_data">
            <td> {{ state.state }} </td>
            <td> {{ state.state_type }} </td>
            <td> {{ state.value }} </td>
        </tr>
    </tbody>
</table>

<div id="{{device_chart_id}}" style="width: 200px; height: 200px;" class="chart"></div>

<h4>Services</h4>
<table class="table table-condensed table-hover table-striped">
    <thead>
        <tr>
            <th>Service</th>
            <th>Ok</th>
            <th>Warning</th>
            <th>Critical</th>
            <th>Unknown</th>
            <th>Undetermined</th>
        </tr>
    </thead>
    <tbody>
        <tr ng-repeat="(serv_key, serv_state) in service_data">
            <td> {{ extract_service_name(serv_key) }} </td>
            <td> {{ extract_service_value(serv_state, "ok") }} </td>
            <td> {{ extract_service_value(serv_state, "warning") }} </td>
            <td> {{ extract_service_value(serv_state, "critical") }} </td>
            <td> {{ extract_service_value(serv_state, "unknown") }} </td>
            <td> {{ extract_service_value(serv_state, "undetermined") }} </td>
        </tr>
    </tbody>
</table>
"""
{% endverbatim %}


# don't know who needs restangular here, but there are strange errors if removed
status_history_module = angular.module("icsw.device.status_history", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "ui.bootstrap.datetimepicker"])

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
            scope.$watch('timerange', (unused) ->
                scope.update()
            )
            scope.$watch('startdate', (unused) ->
                scope.update()
            )
            scope.float_format = (n) -> return (n*100).toFixed(0) + "%"
            scope.extract_service_value = (service, key) ->
                entries = _.filter(service, (e) -> e.state == key)
                ret = 0
                for entry in entries
                    ret += entry.value
                return scope.float_format(ret)
            scope.extract_service_name = (service_key) ->
                check_command_name = service_key.split(",", 2)[0]
                description =  service_key.split(",", 2)[1]
                return check_command_name + ": " + description

            
            scope.update = () ->
                dev_cont = (new_data) ->
                    for d in new_data
                        d['value'] = scope.float_format(d['value'])
                    scope.host_data = new_data

                status_history_utils.get_device_data($resource, scope.device_id, scope.startdate, scope.timerange, dev_cont)
                
                serv_cont = (new_data) ->
                    scope.service_data = new_data

                status_history_utils.get_service_data($resource, scope.device_id, scope.startdate, scope.timerange, serv_cont)

                # 66dd66
                
                # this is the opposite of angular-style, but it's just this one location
                elem = $("#"+scope.device_chart_id)
                elem.html('')
                elem.drawPieChart([
                   { title: "A",         value : 220,  color: "#FFD300" },
                   { title: "B",         value : 120,  color: "#00FF00" },
                ]);

            scope.update()

}).directive("statushistory", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("status_history_template.html")
        link : (scope, el, attrs) ->
            scope.devicepks = attrs["devicepks"].split(',')
            #scope.startdate = moment().startOf("day")
            scope.startdate = moment('Mon Jan 05 2015 00:00:00 GMT+0100 (CET)')
            scope.timerange = 'day'

            scope.set_timerange = (tr) ->
                scope.timerange = tr
}).run(($templateCache) ->
    $templateCache.put("status_history_template.html", status_history_template)
    $templateCache.put("device_status_history_template.html", device_status_history_template)
)



status_history_utils = {
    get_device_data: ($resource, device_id, start_date, timerange, cont) ->
        res = $resource("{% url 'mon:get_hist_device_data' %}", {})
        query_data = {
            'device_id': device_id,
            'date': moment(start_date).unix()  # ask server in utc
            'duration_type': timerange,
        }
        res.query(query_data, (new_data) ->
            cont(new_data)
        )
    get_service_data: ($resource, device_id, start_date, timerange, cont) ->
        res = $resource("{% url 'mon:get_hist_service_data' %}", {}, {'query': {method: 'GET', isArray: false}})
        query_data = {
            'device_id': device_id,
            'date': moment(start_date).unix()  # ask server in utc
            'duration_type': timerange,
        }
        res.query(query_data, (new_data) ->
            cont(new_data)
        )
}

{% endinlinecoffeescript %}

</script>


