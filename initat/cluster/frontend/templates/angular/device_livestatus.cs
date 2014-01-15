{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

{% verbatim %}

livestatus_templ = """
    <table class="table table-condensed table-hover table-bordered" style="width:auto;">
        <thead>
            <tr>
                <td colspan="4" paginator entries="entries" pag_settings="pagSettings" per_page="20" paginator_filter="simple" paginator-epp="10,20,50,100,1000"></td>
            </tr>
            <tr>
                <th ng-click="toggle_order('name')"><span ng-class="get_order_glyph('name')"></span>Node</th>
                <th ng-click="toggle_order('descr')"><span ng-class="get_order_glyph('descr')"></span>Check</th>
                <th>last check</th>
                <th ng-click="toggle_order('result')"><span ng-class="get_order_glyph('result')"></span>result</th>
            </tr>
        </thead>
        <tbody>
            <tr ng-repeat="entry in entries | orderBy:get_order() | paginator2:this.pagSettings" ng-class="get_tr_class(entry)">
                <td>{{ entry.name }}</td>
                <td>{{ entry.descr }}</td>
                <td>{{ get_last_check(entry) }}</td>
                <td>{{ entry.result }}</td>
            </tr>
        </tbody>
    </table>
"""

{% endverbatim %}

device_livestatus_module = angular.module("icsw.device.livestatus", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular"])

angular_module_setup([device_livestatus_module])

device_livestatus_module.controller("livestatus_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "$timeout"
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, $timeout) ->
        $scope.entries = []
        $scope.order_name = "name"
        $scope.order_dir = true
        $scope.pagSettings = paginatorSettings.get_paginator("device_tree_base", $scope)
        $scope.new_devsel = (_dev_sel, _devg_sel) ->
            #pre_sel = (dev.idx for dev in $scope.devices when dev.expanded)
            #restDataSource.reset()
            $scope.devsel_list = _dev_sel
            $scope.load_data()
        $scope.toggle_order = (name) ->
            if $scope.order_name == name
                $scope.order_dir = not $scope.order_dir
            else
                $scope.order_name = name
                $scope.order_dir = true
        $scope.get_order = () ->
            return (if $scope.order_dir then "" else "-") + $scope.order_name
        $scope.get_order_glyph = (name) ->
            if $scope.order_name == name
                if $scope.order_dir 
                    _class = "glyphicon glyphicon-chevron-down"
                else
                    _class = "glyphicon glyphicon-chevron-up"
            else
                _class = "glyphicon glyphicon-chevron-right"
            return _class
        $scope.load_data = () ->
            $timeout($scope.load_data, 20000)
            $.ajax
                url  : "{% url 'mon:get_node_status' %}"
                data : {
                    "pk_list" : angular.toJson($scope.devsel_list)
                },
                success : (xml) =>
                    if parse_xml_response(xml)
                        entries = []
                        $(xml).find("node_results node_result").each (idx, node) =>
                            node = $(node)
                            node_name = node.attr("name")
                            node.find("result").each (_idx, res) =>
                                res = $(res)
                                entries.push({
                                    "name" : node_name
                                    "state" : parseInt(res.attr("state"))
                                    "descr" : res.attr("description")
                                    "last_check" : parseInt(res.attr("last_check"))
                                    "result" : res.text()
                                })
                        $scope.$apply(
                            $scope.entries = entries
                        )
]).directive("livestatus", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("livestatus_template.html")
        link : (scope, el, attrs) ->
            scope.new_devsel((parseInt(entry) for entry in attrs["devicepk"].split(",")), [])
            scope.get_tr_class = (entry) ->
                if entry.state > 2
                    return "danger"
                else if entry.state == 1
                    return "warning"
                else
                    return ""
            scope.get_last_check = (entry) ->
                return moment.unix(entry.last_check).fromNow(true)              
    }
).run(($templateCache) ->
    $templateCache.put("livestatus_template.html", livestatus_templ)
)

{% endinlinecoffeescript %}

</script>
