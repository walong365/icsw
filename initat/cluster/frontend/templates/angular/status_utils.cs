{% load coffeescript staticfiles %}

<script type="text/javascript">

{% inlinecoffeescript %}

{% verbatim %}

device_hist_status_template = """
<div ng-if="show_table"> <!-- use full layout -->
    <div class="row">
        <div class="col-md-4"> <!-- style="margin-top: -8px;"> -->
            <div style="float: right">
                <ngpiechart width="120" height="120" data="pie_data"></ngpiechart>
            </div>
        </div>
        <div class="col-md-8">
            <table class="table table-condensed table-hover table-striped">
                <!--
                <thead>
                    <tr>
                        <th>State</th>
                        <th>Ratio of state</th>
                    </tr>
                </thead>
                -->
                <tbody>
                    <tr ng-repeat="state in host_data">
                        <td> {{ state.state }} </td>
                        <td class="text-right"> {{ state.value }} </td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</div>
<div ng-if="!show_table"> <!-- only chart -->
    <ngpiechart width="40" height="40" data="pie_data"></ngpiechart>
</div>
"""

service_hist_status_template = """
<ngpiechart width="40" height="40" data="pie_data"></ngpiechart>
"""

{% endverbatim %}

root = exports ? this


angular.module(
    "status_utils", []
).directive('deviceHistStatusOverview', ($templateCache, $resource, $parse, status_utils_functions) ->
    # shows piechart and possibly table of historic device status
    return {
        restrict: 'EA',
        scope: {
            deviceid: "="
            startdate: "="
            timerange: "="
        },
        template: $templateCache.get("device_hist_status.html")
        link: (scope, element, attrs) ->
            scope.show_table = scope.$eval(attrs.showTable)

            # TODO: make this into a filter, then remove also from serviceHist*
            scope.float_format = (n) -> return (n*100).toFixed(2) + "%"

            scope.pie_data = []

            scope.update = () ->
                cont = (new_data) ->
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

                    [scope.host_data, scope.pie_data] = status_utils_functions.preprocess_state_data(new_data, weights, colors, scope.float_format)

                status_history_utils.get_device_data($resource, scope.deviceid, scope.startdate, scope.timerange, cont)
            scope.$watchGroup(['deviceid', 'startdate', 'timerange'], (unused) -> scope.update())

}).directive('serviceHistStatusOverview', ($templateCache, $resource, $parse, status_utils_functions) ->
    # shows piechart of state of service. shows how many service are in which state at a given time frame
    return {
        restrict: 'EA',
        scope: {
            deviceid: "="
            startdate: "="
            timerange: "="
        },
        template: $templateCache.get("service_hist_status.html")
        link: (scope, element, attrs) ->

            # TODO: see above
            scope.float_format = (n) -> return (n*100).toFixed(2) + "%"

            scope.pie_data = []

            scope.update = () ->
                cont = (new_data) ->
                    [scope.service_data, scope.pie_data] = status_utils_functions.preprocess_service_state_data(new_data)

                status_history_utils.get_service_data($resource, scope.deviceid, scope.startdate, scope.timerange, cont, merge_services=true)
            scope.$watchGroup(['deviceid', 'startdate', 'timerange'], (unused) -> scope.update())
}).directive("ngpiechart", () ->
    return {
        restrict : "E"
        scope:
            data: "=data"
            width: "=width"
            height: "=height"
        template: """
{% verbatim %}
<div class="chart"></div>
{% endverbatim %}
"""
        link : (scope, el, attrs) ->
            scope.$watchGroup(["data", "width", "height"], (new_data) ->
                el.html ''

                if scope.data
                    el.drawPieChart(scope.data, scope.width, scope.height, {animation: false, lightPiesOffset: 0, edgeOffset: 0, baseOffset: 0, baseColor: "#fff"});
            )
}).service('status_utils_functions', () ->
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

    return {
        float_format: float_format
        preprocess_state_data: preprocess_state_data
        preprocess_service_state_data: (new_data, float_format) ->
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
    }
).run(($templateCache) ->
    $templateCache.put("device_hist_status.html", device_hist_status_template)
    $templateCache.put("service_hist_status.html", service_hist_status_template)
)


# TODO: make into service?
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
    get_service_data: ($resource, device_id, start_date, timerange, cont, merge_services=false) ->
        expect_array = merge_services
        res = $resource("{% url 'mon:get_hist_service_data' %}", {}, {'query': {method: 'GET', isArray: expect_array}})
        query_data = {
            'device_id': device_id,
            'date': moment(start_date).unix()  # ask server in utc
            'duration_type': timerange,
            'merge_services': merge_services,
        }
        res.query(query_data, (new_data) ->
            cont(new_data)
        )

}


{% endinlinecoffeescript %}

</script>
