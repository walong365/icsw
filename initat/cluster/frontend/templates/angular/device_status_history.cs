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
            device_resource = $resource("{% url 'rest:device_list' %}/:id", {});
            scope.device_rest = device_resource.get({'id': scope.device_id})
            scope.$watch('timerange', (unused) ->
                scope.update()
            )
            scope.$watch('startdate', (unused) ->
                scope.update()
            )
            scope.update = () ->
                cont = (new_data) ->
                    console.log new_data
                status_history_utils.get_device_data($resource, scope.device_id, scope.startdate, scope.timerange, cont)


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
}

{% endinlinecoffeescript %}

</script>
