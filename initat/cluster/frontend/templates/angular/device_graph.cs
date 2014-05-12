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
                <div class="btn-group">
                    <button type="button" class="btn btn-sm dropdown-toggle btn-primary" data-toggle="dropdown">
                       <span class="glyphicon glyphicon-calendar"></span>
                    </button>
                    <ul class="dropdown-menu" role="menu">
                        <datetimepicker ng-model="from_date" datetimepicker-config="{ dropdownSelector: '.my-toggle-select' }">
                        </datetimepicker>
                    </ul>
                </div>
            </span>
            <input type="text" class="form-control input-sm" ng-model="to_date"></input>
            <span class="input-group-btn">
                <div class="btn-group">
                    <button type="button" class="btn btn-sm dropdown-toggle btn-primary" data-toggle="dropdown">
                       <span class="glyphicon glyphicon-calendar"></span>
                    </button>
                    <ul class="dropdown-menu" role="menu">
                        <datetimepicker ng-model="to_date" datetimepicker-config="{ dropdownSelector: '.my-toggle-select' }">
                        </datetimepicker>
                    </ul>
                </div>
            </span>
            <div class="input-group-btn">
                <div class="btn-group">
                    <button type="button" class="btn btn-sm btn-success dropdown-toggle" data-toggle="dropdown">
                        {{ cur_dim }} <span class="caret"></span>
                    </button>
                    <ul class="dropdown-menu">
                        <li ng-repeat="dim in all_dims" ng-click="set_active_dim(dim)"><a href="#">{{ dim }}</a></li>
                    </ul>
                </div>
            </div>&nbsp;
            <div class="input-group-btn">
                <div class="btn-group">
                    <button type="button" class="btn btn-sm btn-primary dropdown-toggle" data-toggle="dropdown">
                        timerange <span class="caret"></span>
                    </button>
                    <ul class="dropdown-menu">
                        <li ng-repeat="tr in all_timeranges" ng-click="set_active_tr(tr)"><a href="#">{{ tr.name }}</a></li>
                    </ul>
                </div>
            </div>
        </div>
        <div class="row">
            <h4 ng-show="vector_valid">
                Vector info:
                <span class="label label-primary">{{ num_struct }}</span> /
                <span class="label label-primary">{{ num_mve }}<span ng-show="num_mve_sel"> / {{ num_mve_sel }}</span></span>
            </h4>
            <div class="col-md-3">  
                <tree treeconfig="g_tree"></tree>
            </div>
            <div class="col-md-9" ng-show="graph_list.length">
                <h3>{{ graph_list.length }} graphs</h3>
                <div ng-repeat="graph in graph_list">
                    <h4>
                        <span class="label label-default" ng-click="graph.toggle_expand()">
                            <span ng-class="graph.get_expand_class()"></span>
                            {{ graph.num }}
                        </span>
                        &nbsp;from {{ graph.get_tv(graph.ts_start_mom) }} to {{ graph.get_tv(graph.ts_end_mom) }}
                    </h4>
                    <h4 ng-show="graph.removed_keys.length">
                        {{ graph.removed_keys.length }} keys not shown <span class="glyphicon glyphicon-info-sign" title="{{ graph.get_removed_keys() }}"></span>
                    </h4>
                    <span ng-show="graph.cropped && graph.active">cropped timerange: {{ graph.get_tv(graph.cts_start_mom) }} to {{ graph.get_tv(graph.cts_end_mom) }}
                        <input type="button" class="btn btn-xs btn-warning" value="apply" ng-click="use_crop(graph)"></input>
                    </span>
                    <div ng-show="graph.active">
                        <img-cropped ng-src="{{ graph.src }}" graph="graph">
                        </img-cropped>
                    </div>
                </div>
            </div>
        </div>
    </div>
"""

{% endverbatim %}

class d_graph
    constructor: (@num, @xml) ->
        @active = true
        @src = @xml.attr("href")
        #console.log @xml[0]
        @value_min = parseFloat(@xml.attr("value_min"))
        @value_max = parseFloat(@xml.attr("value_max"))
        # complete graphic
        @img_width = parseInt(@xml.attr("image_width"))
        @img_height = parseInt(@xml.attr("imageheight"))
        # relevant part, coordinates in pixel
        @gfx_width = parseInt(@xml.attr("graph_width"))
        @gfx_height = parseInt(@xml.attr("graph_height"))
        @gfx_left = parseInt(@xml.attr("graph_left"))
        @gfx_top = parseInt(@xml.attr("graph_top"))
        # timescale
        @ts_start = parseInt(@xml.attr("graph_start"))
        @ts_end = parseInt(@xml.attr("graph_end"))
        @ts_start_mom = moment.unix(@ts_start)
        @ts_end_mom = moment.unix(@ts_end)
        @cropped = false
        @removed_keys = []
        for entry in @xml.find("removed_keys removed_key")
            @removed_keys.push($(entry).text())
    get_tv: (val) ->
        if val
            return val.format(DT_FORM)
        else
            return "???"
    get_removed_keys: () ->
        return @removed_keys.join(", ")
    set_crop: (sel) ->
        @cropped = true
        ts_range = @ts_end - @ts_start
        new_start = @ts_start + parseInt((sel.x - @gfx_left) * ts_range / @gfx_width)
        new_end = @ts_start + parseInt((sel.x2 - @gfx_left) * ts_range / @gfx_width)
        @cts_start_mom = moment.unix(new_start)
        @cts_end_mom = moment.unix(new_end)
    clear_crop: () ->
        @cropped = false
    get_expand_class: () ->
        if @active
            return "glyphicon glyphicon-chevron-down"
        else
            return "glyphicon glyphicon-chevron-right"
    toggle_expand: () ->
        @active = !@active
      
class rrd_tree extends tree_config
    constructor: (@scope, args) ->
        super(args)
        @show_selection_buttons = true
        @show_icons = false
        @show_select = true
        @show_descendants = true
        @show_childs = false
    get_name : (t_entry) ->
        if t_entry._node_type == "h"
            return "vector"
        else if t_entry._node_type == "s"
            return t_entry._name
        else
            return t_entry._name
    get_title: (t_entry) ->
        if t_entry._node_type == "e"
            return t_entry._g_key
        else
            return ""
    handle_click: (entry, event) =>
        if entry._node_type == "s"
            entry.expand = ! entry.expand
        else if entry._node_type == "e"
            entry.set_selected(!entry.selected)
            @scope.selection_changed()
    selection_changed: () =>
        @scope.selection_changed()
            
device_rrd_module = angular.module("icsw.device.rrd", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular", "ui.bootstrap.datetimepicker"])

angular_module_setup([device_rrd_module])

DT_FORM = "YYYY-MM-DD HH:mm ZZ"

class pd_timerange
    constructor: (@name, @from, @to) ->
    get_from: () =>
        if @to
            return @from
        else
            return moment().subtract("days", 1)
    get_to: () =>
        if @to
            return @to
        else
            return moment()

device_rrd_module.controller("rrd_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "$timeout"
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, $timeout) ->
        # possible dimensions
        $scope.all_dims = ["420x200", "640x300", "800x350", "1024x400", "1280x450"]
        $scope.all_timeranges = [
            new pd_timerange("last 24 hours", "24:00", undefined)
            new pd_timerange("last day", moment().subtract("days", 1).startOf("day"), moment().subtract("days", 1).endOf("day"))
            new pd_timerange("current month", moment().startOf("month"), moment().endOf("month"))
            new pd_timerange("last month", moment().subtract("month", 1).startOf("month"), moment().subtract("month", 1).endOf("month"))
            new pd_timerange("current week", moment().startOf("week"), moment().endOf("week"))
            new pd_timerange("last week", moment().subtract("week", 1).startOf("week"), moment().subtract("week", 1).endOf("week"))
            new pd_timerange("current year", moment().startOf("year"), moment().endOf("year"))
            new pd_timerange("last year", moment().subtract("year", 1).startOf("year"), moment().subtract("year", 1).endOf("year"))
        ]
        moment().utc()
        $scope.dt_valid = true
        $scope.vector_valid = false
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
                else if diff < 60000
                    $scope.dt_valid = false
        $scope.set_active_tr = (new_tr) ->
            $scope.from_date_mom = new_tr.get_from()
            $scope.to_date_mom   = new_tr.get_to()
            $scope.from_date = $scope.from_date_mom.format(DT_FORM)
            $scope.to_date   = $scope.to_date_mom.format(DT_FORM)
            $scope.update_dt()
        $scope.set_active_dim = (cur_dim) ->
            $scope.cur_dim = cur_dim
        $scope.new_devsel = (_dev_sel, _devg_sel) ->
            $scope.devsel_list = _dev_sel
            $scope.reload()
        $scope.reload = () ->
            $scope.vector_valid = false
            call_ajax
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
                                $scope.vector_valid = true
                                $scope.num_struct = $scope.vector.find("entry").length
                                $scope.num_mve = $scope.vector.find("mve").length
                                $scope.num_mve_sel = 0
                            ) 
                        else
                            $scope.error_string = "No vector found"
                            $scope.$digest()
        $scope.add_nodes = (p_node, xml_node) =>
            if p_node == undefined
                cur_node = $scope.g_tree.new_node({
                    folder : true
                    expand : true
                    _node_type : "h"
                })
                cur_node._show_select = false
                $scope.g_tree.add_root_node(cur_node)
            else
                if xml_node.prop("tagName") == "entry"
                    # structural
                    cur_node = $scope.g_tree.new_node({
                        folder : true,
                        expand : false
                        _name  : xml_node.attr("part")
                        _node_type : "s"
                    })
                    cur_node._show_select = false
                else
                    # value
                    cur_node = $scope.g_tree.new_node({
                        folder : false
                        expand : false
                        _g_key : xml_node.attr("name")
                        _name  : xml_node.attr("info")
                        _node_type : "e"
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
            $scope.num_mve_sel = $scope.cur_selected.length
        $scope.use_crop = (graph) ->
            $scope.from_date_mom = graph.cts_start_mom
            $scope.to_date_mom = graph.cts_end_mom
            $scope.from_date = $scope.from_date_mom.format(DT_FORM)
            $scope.to_date = $scope.to_date_mom.format(DT_FORM)
            $scope.draw_graph()
        $scope.draw_graph = () =>
            call_ajax
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
                        num_graph = 0
                        for graph in $(xml).find("graph_list > graph")
                            num_graph++
                            graph_list.push(new d_graph(num_graph, $(graph)))
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
).directive("imgCropped", () ->
    return {
        restrict: "E"
        replace: true
        scope: {
            src: "@"
            graph: "="
            selected: "&"
        }
        link: (scope, element, attr) ->
            clear = () ->
                if myImg
                    myImg.next().remove()
                    myImg.remove()
                    myImg = undefined
            scope.$watch("src", (nv) ->
                clear()
                if nv
                    element.after("<img />")
                    myImg = element.next()
                    myImg.attr("src", nv)
                    $(myImg).Jcrop({
                        trackDocument: true
                        onSelect: (sel) ->
                            scope.$apply(() ->
                                scope.graph.set_crop(sel)
                            )
                        onRelease: () ->
                            scope.$apply(() ->
                                scope.graph.clear_crop()
                            )
                    }, () ->
                        bounds = this.getBounds()
                        boundx = bounds[0]
                        boundy = bounds[1]

                    )
            )
            scope.$on("$destroy", clear)
    }
)

add_tree_directive(device_rrd_module)

{% endinlinecoffeescript %}

</script>
