{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

{% verbatim %}

rrd_graph_template = """
    <div>
        <p class="text-danger">{{ error_string }}</p>
        <div class="input-group">
            <input type="text" class="form-control" ng-disabled="is_loading" ng-model="searchstr" placeholder="search ..." ng-change="update_search()"></input>
            <span class="input-group-btn">
                <button class="btn btn-success" ng-show="cur_selected" type="button" ng-click="draw_graph()"><span title="draw graph(s)" class="glyphicon glyphicon-pencil"></span></button>
                <button class="btn btn-danger" type="button" ng-click="clear_selection()"><span title="clear selection" class="glyphicon glyphicon-ban-circle"></span></button>
            </span>
        </div>
        <div class="row">
            <div class="col-md-4">  
                <tree treeconfig="g_tree"></tree>
            </div>
            <div class="col-md-8">
                <h4>{{ graph_list.length }} graphs</h4>
                <div ng-repeat="graph in graph_list">
                    {{ graph }}
                    <img ng-src="{{ graph }}"></img>
                </div>
            </div>
        </div>
    </div>
"""

{% endverbatim %}

class rrd_tree extends tree_config
    constructor: (@scope, args) ->
        super(args)
        @show_selection_buttons = true
        @show_icons = false
        @show_select = true
        @show_descendants = false
        @show_childs = false
    get_name : (t_entry) ->
        if t_entry._node_type == "h"
            return "vector"
        else if t_entry._node_type == "s"
            return t_entry._name
        else
            return t_entry._name
    handle_click: (entry, event) =>
        if entry._node_type == "s"
            entry.expand = ! entry.expand
    selection_changed: () =>
        @scope.selection_changed()
            
device_rrd_module = angular.module("icsw.device.rrd", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular"])

angular_module_setup([device_rrd_module])

device_rrd_module.controller("rrd_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "$timeout"
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, $timeout) ->
        $scope.error_string = ""
        $scope.searchstr = ""
        $scope.is_loading = true
        $scope.cur_selected = []
        $scope.graph_list = []
        $scope.g_tree = new rrd_tree($scope)
        $scope.new_devsel = (_dev_sel, _devg_sel) ->
            $scope.devsel_list = _dev_sel
            $scope.reload()
        $scope.reload = () ->
            $.ajax
                url  : "{% url 'rrd:device_rrds' %}"
                data : {
                    "pks" : angular.toJson($scope.devsel_list)
                }
                success : (xml) =>
                    if parse_xml_response(xml)
                        @vector = $(xml).find("machine_vector")
                        if @vector.length
                            # we only get one vector at most (due to merge_results=1 in rrd_views.py)
                            @add_nodes(undefined, @vector)
                            $scope.is_loading = false
                            $scope.$digest()
                        else
                            $scope.$apply(
                                $scope.error_string = "No graphs found"
                            )
        $scope.add_nodes = (p_node, xml_node) =>
            if p_node == undefined
                cur_node = $scope.g_tree.new_node({folder:true, _node_type:"h", expand:true})
                cur_node._show_select = false
                $scope.g_tree.add_root_node(cur_node)
            else
                if xml_node.prop("tagName") == "entry"
                    # structural
                    cur_node = $scope.g_tree.new_node({folder:true, _node_type:"s", expand:false, _name:xml_node.attr("part")})
                    cur_node._show_select = false
                else
                    # value
                    #console.log xml_node[0]
                    cur_node = $scope.g_tree.new_node({
                        folder :false,
                        _node_type :"e",
                        expand :false
                        _g_key : xml_node.attr("name")
                        _name  :xml_node.attr("info")
                    })
                p_node.add_child(cur_node)
            for sub_node in xml_node.children()
                $scope.add_nodes(cur_node, $(sub_node))
        $scope.update_search = () ->
            if $scope.cur_search_to
                $timeout.cancel($scope.cur_search_to)
            $scope.cur_search_to = $timeout($scope.set_search_filter, 500)
        $scope.clear_selection = () =>
            $scope.searchstr = ""
            $scope.set_search_filter()
        $scope.set_search_filter = () =>
            if $scope.searchstr
                try
                    cur_re = new RegExp($scope.searchstr, "gi")
                catch
                    cur_re = new RegExp("^$", "gi")
            else
                cur_re = new RegExp("^$", "gi")
            $scope.g_tree.toggle_tree_state(undefined, -1, false)
            $scope.g_tree.iter(
                (entry, cur_re) ->
                    if entry._node_type in ["e"]
                        entry.set_selected(if (entry._name.match(cur_re) or entry._g_key.match(cur_re)) then true else false)
                cur_re
            )
            $scope.g_tree.show_selected(false)
            $scope.selection_changed()
        $scope.selection_changed = () =>
            $scope.cur_selected = $scope.g_tree.get_selected(
                (entry) ->
                    if entry._node_type == "e" and entry.selected
                        return [entry._g_key]
                    else
                        return []
            )
        $scope.draw_graph = () =>
            $.ajax
                url  : "{% url 'rrd:graph_rrds' %}"
                data : {
                    "keys"       : angular.toJson($scope.cur_selected)
                    "pks"        : angular.toJson($scope.devsel_list)
                    "start_time" : "2014-01-01 00:00"
                    "end_time"   : "2014-01-21 00:00"
                    "size"       : "640x480"
                }
                success : (xml) =>
                    graph_list = []
                    if parse_xml_response(xml)
                        for graph in $(xml).find("graph_list > graph")
                            graph = $(graph)
                            graph_list.push(graph.attr("href"))
                    $scope.$apply(
                        $scope.graph_list = graph_list
                    )
            
]).directive("rrdgraph", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("rrd_graph_template.html")
        link : (scope, el, attrs) ->
            scope.new_devsel((parseInt(entry) for entry in attrs["devicepk"].split(",")), [])
    }
).run(($templateCache) ->
    $templateCache.put("rrd_graph_template.html", rrd_graph_template)
)

add_tree_directive(device_rrd_module)

{% endinlinecoffeescript %}

</script>
