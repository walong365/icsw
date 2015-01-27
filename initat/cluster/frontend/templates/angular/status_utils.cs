{% load coffeescript staticfiles %}

<script type="text/javascript">

{% inlinecoffeescript %}

{% verbatim %}

device_hist_status_template = """
<div ng-if="show_table"> <!-- use full layout -->
    <div class="row">
        <div class="col-md-4"> <!-- style="margin-top: -8px;"> -->
            <div style="float: right">
                <icsw-piechart diameter="120" data="pie_data"></icsw-piechart>
            </div>
        </div>
        <div class="col-md-4">
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
    <icsw-piechart diameter="40" data="pie_data"></icsw-piechart>
</div>
"""

service_hist_status_template = """
<icsw-piechart diameter="40" data="pie_data"></icsw-piechart>
"""

{% endverbatim %}

root = exports ? this


angular.module(
    "status_utils", ["angular-piechart"]
).directive('deviceHistStatusOverview', ($templateCache, $parse, status_utils_functions) ->
    # shows piechart and possibly table of historic device status
    return {
        restrict: 'E',
        scope: {
            data: "="  # if data is passed right through here, the other attributes are discarded
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

}).directive('serviceHistStatusOverview', ($templateCache, $parse, status_utils_functions) ->
    # shows piechart of state of service. shows how many service are in which state at a given time frame
    return {
        restrict: 'E',
        scope: {
            data: "="  # if data is passed right through here, the other attributes are discarded
            deviceid: "="
            startdate: "="
            timerange: "="
        },
        template: $templateCache.get("service_hist_status.html")
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
}).service('status_utils_functions', (Restangular) ->
    get_device_data = (device_ids, start_date, timerange, cont) ->
        query_data = {
            'device_ids': device_ids.join(),
            'date': moment(start_date).unix()  # ask server in utc
            'duration_type': timerange,
        }
        base = Restangular.all("{% url 'mon:get_hist_device_data' %}".slice(1))
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
        base = Restangular.all("{% url 'mon:get_hist_service_data' %}".slice(1))
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
        base = Restangular.all("{% url 'mon:get_hist_timespan' %}".slice(1))
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
).run(($templateCache) ->
    $templateCache.put("device_hist_status.html", device_hist_status_template)
    $templateCache.put("service_hist_status.html", service_hist_status_template)
)


{% endinlinecoffeescript %}

</script>
