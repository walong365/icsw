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
                <button class="btn btn-success" ng-show="cur_selected.length && dt_valid" type="button" ng-click="draw_graph()"><span title="draw graph(s)" class="glyphicon glyphicon-pencil"></span></button>
                <button class="btn btn-danger" type="button" ng-click="clear_selection()"><span title="clear selection" class="glyphicon glyphicon-ban-circle"></span></button>
            </span>
            <input type="text" class="form-control input-sm" ng-model="from_date"></input>
            <span class="input-group-btn">
                <button type="button" class="btn btn-sm dropdown-toggle btn-primary" data-toggle="dropdown">
                   <span class="glyphicon glyphicon-calendar"></span>
                </button>
                <ul class="dropdown-menu" role="menu">
                    <datetimepicker ng-model="from_date" 
                                    datetimepicker-config="{ dropdownSelector: '.my-toggle-select' }">
                    </datetimepicker>
                </ul>
            </span>
            <input type="text" class="form-control input-sm" ng-model="to_date"></input>
            <span class="input-group-btn">
                <button type="button" class="btn btn-sm dropdown-toggle btn-primary" data-toggle="dropdown">
                   <span class="glyphicon glyphicon-calendar"></span>
                </button>
                <ul class="dropdown-menu" role="menu">
                    <datetimepicker ng-model="to_date"
                                    datetimepicker-config="{ dropdownSelector: '.my-toggle-select' }">
                    </datetimepicker>
                </ul>
            </span>
            <div class="input-group-btn">
                <button type="button" class="btn btn-sm dropdown-toggle" data-toggle="dropdown">
                    {{ cur_dim }} <span class="caret"></span>
                </button>
                <ul class="dropdown-menu">
                  <li ng-repeat="dim in all_dims" ng-click="set_active_dim(dim)"><a href="#">{{ dim }}</a></li>
                </ul>
            </div>
        </div>
        <div class="row">
            <h4>{{ graph_info_str }}</h4>
            <div class="col-md-4">  
                <tree treeconfig="g_tree"></tree>
            </div>
            <div class="col-md-8">
                <h4>{{ graph_list.length }} graphs</h4>
                <div ng-repeat="graph in graph_list">
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
            
device_rrd_module = angular.module("icsw.device.rrd", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular", "ui.bootstrap.datetimepicker"])

angular_module_setup([device_rrd_module])

DT_FORM = "YYYY-MM-DD HH:mm"

device_rrd_module.controller("rrd_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "$timeout"
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, $timeout) ->
        # possible dimensions
        $scope.all_dims = ["420x200", "640x300", "800x350", "1024x400", "1280x450"]
        $scope.dt_valid = true
        $scope.to_date_mom = moment()
        $scope.from_date_mom = moment().subtract("days", 1)
        $scope.from_date = $scope.from_date_mom.format(DT_FORM)
        $scope.to_date = $scope.to_date_mom.format(DT_FORM)
        $scope.cur_dim = $scope.all_dims[1]
        $scope.error_string = ""
        $scope.searchstr = ""
        $scope.is_loading = true
        $scope.cur_selected = []
        $scope.graph_list = []
        $scope.g_tree = new rrd_tree($scope)
        $scope.$watch("from_date", (new_val) ->
            $scope.from_date_mom = moment(new_val)
            $scope.update_dt() 
        )
        $scope.$watch("to_date", (new_val) ->
            $scope.to_date_mom = moment(new_val)
            $scope.update_dt() 
        )
        $scope.update_dt = () ->
            $scope.dt_valid = $scope.from_date_mom.isValid() and $scope.to_date_mom.isValid()
            if $scope.dt_valid
                diff = $scope.to_date_mom - $scope.from_date_mom 
                if diff < 0
                    $scope.from_date = $scope.to_date_mom.format(DT_FORM)
                    $scope.to_date = $scope.from_date_mom.format(DT_FORM)
                    noty
                        text : "exchanged from with to date"
                        type : "warning"
                else if diff < 60
                    $scope.dt_valid = false
        $scope.set_active_dim = (cur_dim) ->
            $scope.cur_dim = cur_dim
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
                        $scope.vector = $(xml).find("machine_vector")
                        if $scope.vector.length
                            # we only get one vector at most (due to merge_results=1 in rrd_views.py)
                            $scope.add_nodes(undefined, $scope.vector)
                            $scope.is_loading = false
                            $scope.$apply(
                                num_struct = $scope.vector.find("entry").length
                                num_mve = $scope.vector.find("mve").length
                                $scope.graph_info_str = "Vector info: #{num_struct} / #{num_mve}"
                            ) 
                        else
                            $scope.$apply(
                                $scope.error_string = "No vector found"
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
                    "start_time" : $scope.from_date_mom.format(DT_FORM)
                    "end_time"   : $scope.to_date_mom.format(DT_FORM)
                    "size"       : $scope.cur_dim
                }
                success : (xml) =>
                    graph_list = []
                    if parse_xml_response(xml)
                        for graph in $(xml).find("graph_list > graph")
                            graph = $(graph)
                            #console.log graph[0]
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
