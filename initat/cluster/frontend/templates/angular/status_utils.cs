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

{% endverbatim %}

root = exports ? this


angular.module(
    "status_utils", []
).directive('deviceHistStatusOverview', ($templateCache, $resource, $parse) ->
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

            scope.float_format = (n) -> return (n*100).toFixed(2) + "%"

            scope.update = () ->
                cont = (new_data) ->
                    weigth = {
                        "Up": -10
                        "Down": -8
                        "Unreachable": -6
                        "Undetermined": -4
                    }
                    formatted_data = _.cloneDeep(new_data)
                    for key of weigth
                        if not _.any(new_data, (d) -> return d['state'] == key)
                            formatted_data.push({'state':key, 'value': 0})

                    for d in formatted_data
                        d['value'] = scope.float_format(d['value'])
                    scope.host_data = _.sortBy(formatted_data, (d) -> return weigth[d['state']])

                    new_data = _.sortBy(new_data, (d) -> return weigth[d['state']])

                    for d in new_data
                        d['value'] = Math.round(d['value']*10000) / 100

                    colors = {
                        "Up": "#66dd66"
                        "Down": "#ff7777"
                        "Unreachable": "#f0ad4e"
                        "Undetermined": "#b7b7b7"
                    }
                    pie_data = []
                    for d in new_data
                        pie_data.push {
                            'title': d['state']
                            'value': d['value']
                            'color': colors[d['state']]
                        }
                    scope.pie_data = pie_data

                status_history_utils.get_device_data($resource, scope.deviceid, scope.startdate, scope.timerange, cont)

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
}).run(($templateCache) ->
    $templateCache.put("device_hist_status.html", device_hist_status_template)
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
}


{% endinlinecoffeescript %}

</script>
