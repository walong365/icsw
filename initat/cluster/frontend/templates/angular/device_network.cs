{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

{% verbatim %}

dc_row_template = """
    <td>
        <button class="btn btn-primary btn-xs" ng-click="expand_vt(obj)">
            <span ng_class="get_expand_class(obj)">
            </span> {{ obj.device_variable_set.length }}
            <span ng-if="var_filter.length"> / {{ obj.num_filtered }} shown<span>
        </button>
    </td>
    <td>{{ get_name(obj) }}</td>
    <td>{{ obj.device_group_name }}</td>
    <td>{{ obj.comment }}</td>
    <td>local: {{ obj.local_selected.length }}<span ng-show="obj.device_type_identifier != 'MD'">, meta: {{ meta_devices[devg_md_lut[obj.device_group]].local_selected.length }}</span></td>
"""

{% endverbatim %}

device_network_module = angular.module("icsw.network.device", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular"])

angular_module_setup([device_network_module])

device_network_module.controller("network_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal) ->
        $scope.var_filter = ""
        $scope.devsel_list = []
        $scope.entries = []
        $scope.new_devsel = (_dev_sel, _devg_sel) ->
            $scope.devsel_list = _dev_sel
            wait_list = [
                restDataSource.reload(["{% url 'rest:device_tree_list' %}", {"with_network" : true, "pks" : angular.toJson($scope.devsel_list)}]),
                restDataSource.reload(["{% url 'rest:peer_information_list' %}", {}]),
            ]
            $q.all(wait_list).then((data) ->
                console.log data[1]
                $scope.entries = (dev for dev in data[0])
            )
        install_devsel_link($scope.new_devsel, true, true, false)
]).directive("devicenetwork", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("devconfvars.html")
        link : (scope, el, attrs) ->
            scope.new_devsel((parseInt(entry) for entry in attrs["devicepk"].split(",")), [])
    }
).run(($templateCache) ->
    #$templateCache.put("devconfvars.html", devconf_vars_template)
)

{% endinlinecoffeescript %}

</script>
