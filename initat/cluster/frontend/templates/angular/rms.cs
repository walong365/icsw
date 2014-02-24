{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

{% verbatim %}

running_table = """
<table class="table table-condensed table-hover" style="width:auto;">
    <thead>
        <tr>
            <td colspan="20" paginator entries="run_list" pag_settings="pagRun" per_page="20" paginator_filter="simple" paginator-epp="10,20,50,100,1000"></td>
        </tr>
        <tr headers struct="running_struct"></tr>
    </thead>
    <tbody>
        <tr rmsline ng-repeat-start="data in run_list | paginator2:this.pagRun" struct="running_struct">
        </tr>
        <tr ng-repeat-end>
            <td colspan="10">{{ datax }}</td>
        </tr>
    </tbody>
    <tfoot>
        <tr headertoggle struct="running_struct"></tr>
    </tfoot>
</table>
"""

waiting_table = """
<table class="table table-condensed table-hover" style="width:auto;">
    <thead>
        <tr>
            <td colspan="20" paginator entries="wait_list" pag_settings="pagWait" per_page="20" paginator_filter="simple" paginator-epp="10,20,50,100,1000"></td>
        </tr>
        <tr headers struct="waiting_struct"></tr>
    </thead>
    <tbody>
        <tr rmsline ng-repeat="data in wait_list | paginator2:this.pagWait" struct="waiting_struct"></tr>
    </tbody>
    <tfoot>
        <tr headertoggle struct="waiting_struct"></tr>
    </tfoot>
</table>
"""

node_table = """
<table class="table table-condensed table-hover" style="width:auto;">
    <thead>
        <tr>
            <td colspan="20" paginator entries="node_list" pag_settings="pagNode" per_page="20" paginator_filter="simple" paginator-epp="10,20,50,100,1000"></td>
        </tr>
        <tr headers struct="node_struct"></tr>
    </thead>
    <tbody>
        <tr rmsline ng-repeat="data in node_list | paginator2:this.pagNode" struct="node_struct"></tr>
    </tbody>
    <tfoot>
        <tr headertoggle struct="node_struct"></tr>
    </tfoot>
</table>
"""

headers = """
<th ng-repeat="entry in struct.display_headers()">{{ entry }}</th>
"""

header_toggle = """
<th colspan="{{ struct.headers.length }}">
    <form class="inline">
        <input ng-repeat="entry in struct.headers" type="button" ng-class="struct.get_btn_class(entry)" value="{{ entry }}" ng-click="struct.change_entry(entry)">
        </input>
    </form>
</th>
"""

rmsline = """
<td ng-repeat="entry in get_display_data(data) track by $index" ng-bind-html="entry"></td>
"""

{% endverbatim %}

rms_module = angular.module("icsw.rms", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular"])

angular_module_setup([rms_module])

class header_struct
    constructor: (@headers) ->
        _dict = {}
        for entry in @headers
            _dict[entry] = true
        @toggle = _dict
        @build_cache()
    build_cache : () =>
        _c = []
        for entry in @headers
            if @toggle[entry]
                _c.push([true, entry])
            else
                _c.push([false, entry])
        @togglec = _c
    change_entry : (entry) =>
        @toggle[entry] = ! @toggle[entry]
        @build_cache()
    display_headers : () =>
        return (v[0] for v in _.zip.apply(null, [@headers, @togglec]) when v[1][0])
    display_data : (data) =>
        # get display list
        return ([v[1][1], v[0]] for v in _.zip.apply(null, [data, @togglec]) when v[1][0])
    get_btn_class : (entry) ->
        if @toggle[entry]
            return "btn btn-sm btn-success"
        else
            return "btn btn-sm"
        
rms_module.controller("rms_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "access_level_service", "$timeout", 
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, access_level_service, $timeout) ->
        access_level_service.install($scope)
        $scope.rms_headers = {{ RMS_HEADERS | safe }}
        $scope.pagRun = paginatorSettings.get_paginator("run", $scope)
        $scope.pagWait = paginatorSettings.get_paginator("wait", $scope)
        $scope.pagNode = paginatorSettings.get_paginator("node", $scope)
        $scope.run_list = []
        $scope.wait_list = []
        $scope.node_list = []
        $scope.running_struct = new header_struct($scope.rms_headers.running_headers)
        $scope.waiting_struct = new header_struct($scope.rms_headers.waiting_headers)
        $scope.node_struct = new header_struct($scope.rms_headers.node_headers)
        $scope.reload= () ->
            $scope.update_info_timeout = $timeout($scope.reload, 5000)
            $.ajax
                url      : "{% url 'rms:get_rms_json' %}"
                dataType : "json"
                data:
                    "angular" : true
                success  : (json) =>
                    $scope.$apply(() ->
                        $scope.run_list = json.run_table
                        $scope.wait_list = json.wait_table
                        $scope.node_list = json.node_table
                    )
        $scope.reload()
]).directive("running", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("running_table.html")
        link : (scope, el, attrs) ->
    }
).directive("waiting", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("waiting_table.html")
        link : (scope, el, attrs) ->
    }
).directive("node", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("node_table.html")
        link : (scope, el, attrs) ->
    }
).directive("headers", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("headers.html")
        scope:
            struct : "="
        link : (scope, el, attrs) ->
    }
).directive("rmsline", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("rmsline.html")
        link : (scope, el, attrs) ->
            scope.struct_name = attrs["struct"]
            scope.render_helper = {
                "host" : (name) ->
                    return "<b>#{name}</b>"
            }
            scope.get_display_data = (data) ->
                _list = []
                for entry in scope[scope.struct_name].display_data(data)
                    if entry[0] of scope.render_helper
                        _list.push(scope.render_helper[entry[0]](entry[1]))
                    else
                        _list.push(entry[1])
                return _list
    }
).directive("headertoggle", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("header_toggle.html")
        scope:
            struct : "="
        link : (scope, el, attrs) ->
    }
).run(($templateCache) ->
    $templateCache.put("running_table.html", running_table)
    $templateCache.put("waiting_table.html", waiting_table)
    $templateCache.put("node_table.html", node_table)
    $templateCache.put("headers.html", headers)
    $templateCache.put("rmsline.html", rmsline)
    $templateCache.put("header_toggle.html", header_toggle)
)

{% endinlinecoffeescript %}

</script>
