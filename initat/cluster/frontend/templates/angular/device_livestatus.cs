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

monconfig_templ = """
    <div class="row">
        <tabset ng-show="!reload_pending">
            <tab heading="action">
                <div class="well">
                    <input type="button" class="btn btn-success" value="reload" ng-show="!reload_pending" ng-click="load_data()"></input>
                </div>
            </tab>
            <tab ng-repeat="(key, value) in mc_tables" heading="{{ value.short_name }} ({{ value.entries.length }})">
                <h3>{{ value.entries.length }} entries for {{ value.short_name }}</h3> 
                <table class="table table-condensed table-hover table-bordered" style="width:auto;">
                    <thead>
                        <tr>
                            <td colspan="{{ value.attr_list.length }}" paginator entries="value.entries" pag_settings="value.pagSettings" per_page="20" paginator_filter="simple" paginator-epp="10,20,50,100,1000"></td>
                        </tr>
                        <tr>
                            <th ng-repeat="attr in value.attr_list" title="{{ get_long_attr_name(attr) }}" ng-click="value.toggle_order(attr)">
                                <span ng-class="value.get_order_glyph(attr)"></span>
                                {{ get_short_attr_name(attr) }}
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr ng-repeat="entry in value.entries | orderBy:value.get_order() | paginator2:value.pagSettings">
                            <td ng-repeat="attr in value.attr_list">
                                {{ entry[attr] }}
                            </td>
                        </tr>
                    </tbody>
                </table>
            </tab>
        </tabset>
    </div>
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

class mc_table
    constructor : (@xml, paginatorSettings) ->
        @name = xml.prop("tagName")
        @short_name = @name.replace(/_/g, "").replace(/list$/, "")
        @attr_list = new Array()
        @entries = []
        @xml.children().each (idx, entry) =>
            for attr in entry.attributes
                if attr.name not in @attr_list
                    @attr_list.push(attr.name)
            @entries.push(@_to_json($(entry)))
        @pagSettings = paginatorSettings.get_paginator("device_tree_base")
        @order_name = "name"
        @order_dir = true
    _to_json : (entry) =>
        _ret = new Object()
        for attr_name in @attr_list
            _ret[attr_name] = entry.attr(attr_name)
        return _ret
    toggle_order : (name) =>
        if @order_name == name
            @order_dir = not @order_dir
        else
            @order_name = name
            @order_dir = true
    get_order : () =>
        return (if @order_dir then "" else "-") + @order_name
    get_order_glyph : (name) =>
        if @order_name == name
            if @order_dir 
                _class = "glyphicon glyphicon-chevron-down"
            else
                _class = "glyphicon glyphicon-chevron-up"
        else
            _class = "glyphicon"
        return _class
        
device_livestatus_module.controller("monconfig_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "$timeout"
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, $timeout) ->
        $scope.reload_pending = false
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
        $scope.get_long_attr_name = (name) ->
            return name.replace(/_/g, " ")
        $scope.get_short_attr_name = (name) ->
            _parts = name.split("_")
            return (_str.slice(0, 1) for _str in _parts).join("").toUpperCase() 
        $scope.load_data = () ->
            #$timeout($scope.load_data, 20000)
            $scope.reload_pending = true
            $.ajax
                url  : "{% url 'mon:get_node_config' %}"
                data : {
                    "pk_list" : angular.toJson($scope.devsel_list)
                },
                success : (xml) =>
                    if parse_xml_response(xml)
                        mc_tables = {}
                        $(xml).find("config > *").each (idx, node) => 
                            new_table = new mc_table($(node), paginatorSettings)
                            mc_tables[new_table.name] = new_table
                        $scope.$apply(
                            $scope.mc_tables = mc_tables
                            $scope.reload_pending = false
                        )
]).directive("monconfig", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("monconfig_template.html")
        link : (scope, el, attrs) ->
            scope.new_devsel((parseInt(entry) for entry in attrs["devicepk"].split(",")), [])
    }
).run(($templateCache) ->
    $templateCache.put("monconfig_template.html", monconfig_templ)
)

{% endinlinecoffeescript %}

</script>
