{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

{% verbatim %}

rrd_graph_template = """
<div>
    <p class="text-danger">{{ error_string }}</p>
    <h3 ng-show="vector_valid">
        Vector info:
        <span class="label label-primary" title="structural entries">{{ num_struct }}<span ng-show="num_devices > 1" title="number of devices"> / {{ num_devices }}</span></span> /
        <span class="label label-primary" title="entries">{{ num_mve }}<span ng-show="num_mve_sel" title="selected entries"> / {{ num_mve_sel }}</span></span>, 
        <input type="button" ng-class="show_options && 'btn btn-sm btn-primary' || 'btn btn-sm'" value="options" ng-click="show_options=!show_options"></input>
    </h3>
    <div class="input-group" ng-show="show_options">
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
        <div class="input-group-btn">
            <input type="button" ng-class="hide_zero && 'btn btn-sm btn-success' || 'btn btn-sm'" value="hide zero" ng-click="hide_zero=!hide_zero"></input>
        </div>
                <div class="input-group-btn">
                    <button type="button" ng-class="merge_cd && 'btn btn-xs btn-warning' || 'btn btn-xs'" ng-click="toggle_merge_cd()" title="Merge RRDs from controlling devices">
                        <span class="glyphicon glyphicon-off"></span>
                    </button>
                </div>

        <div class="input-group-btn">
            <input type="button" ng-class="merge_devices && 'btn btn-sm btn-success' || 'btn btn-sm'" value="merge devices" ng-click="merge_devices=!merge_devices"></input>
        </div>
        <div class="input-group-btn">
            <div class="btn-group">
                <button type="button" class="btn btn-sm btn-primary dropdown-toggle" data-toggle="dropdown">
                    timeshift <span ng-show="active_ts">({{ active_ts.name }})</span><span class="caret"></span>
                </button>
                <ul class="dropdown-menu">
                    <li ng-repeat="ts in all_timeshifts" ng-click="set_active_ts(ts)"><a href="#">{{ ts.name }}</a></li>
                </ul>
            </div>
        </div>
        <div class="input-group">
            <span class="input-group-addon">
                 from
            </span>
            <input type="text" class="form-control" ng-model="from_date_mom">
            </input>
            <span class="dropdown-toggle input-group-addon">
                <div class="dropdown">
                    <button class="btn dropdown-toggle btn-xs">
                         <i class="glyphicon glyphicon-calendar"></i>
                    </button>
                    <ul class="dropdown-menu" role="menu">
                        <datetimepicker ng-model="from_date_mom" data-datetimepicker-config="{ dropdownSelector: '#dropdownfrom' }"/>
                    </ul>
                </div>
            </span>
        </div>
        <div class="input-group">
            <span class="input-group-addon">
                 to
            </span>
            <input type="text" class="form-control" ng-model="to_date_mom">
            </input>
            <span class="dropdown-toggle input-group-addon">
                <div class="dropdown">
                    <button class="btn dropdown-toggle btn-xs">
                         <i class="glyphicon glyphicon-calendar"></i>
                    </button>
                    <ul class="dropdown-menu" role="menu">
                        <datetimepicker ng-model="to_date_mom" data-datetimepicker-config="{ dropdownSelector: '#dropdownfrom' }"/>
                    </ul>
                </div>
            </span>
        </div>
    </div>
    <div class="row">
        <div class="col-md-3">  
            <div class="input-group">
                <input type="text" class="form-control" ng-disabled="is_loading" ng-model="searchstr" placeholder="search ..." ng-change="update_search()"></input>
                <span class="input-group-btn">
                    <button class="btn btn-success" ng-show="cur_selected.length && dt_valid" type="button" ng-click="draw_graph()"><span title="draw graph(s)" class="glyphicon glyphicon-pencil"></span></button>
                    <button class="btn btn-danger" type="button" ng-click="clear_selection()"><span title="clear selection" class="glyphicon glyphicon-ban-circle"></span></button>
                </span>
            </div>
            <tree treeconfig="g_tree"></tree>
        </div>
        <div class="col-md-9" ng-show="graph_list.length">
            <h4>{{ graph_list.length }} graphs, {{ graph_list[0].get_tv(graph_list[0].ts_start_mom) }} to {{ graph_list[0].get_tv(graph_list[0].ts_end_mom) }}</h4>
            <table class="table-condensed">
                <tr ng-repeat="gkey in get_graph_keys()">
                    <td ng-repeat="(dkey, graph) in graph_mat[gkey]">
                        <h4  ng-show="!graph.error">
                            <span class="label label-default" ng-click="graph.toggle_expand()">
                                <span ng-class="graph.get_expand_class()"></span>
                                {{ graph.num }}
                            </span>
                        </h4>
                        <h4 ng-show="graph.removed_keys.length">
                            {{ graph.removed_keys.length }} keys not shown (zero data) <span class="glyphicon glyphicon-info-sign" title="{{ graph.get_removed_keys() }}"></span>
                        </h4>
                        <h4 class="text-danger" ng-show="graph.error">Error loading graph ({{ graph.num }})</h4>
                        <span ng-show="graph.cropped && graph.active">cropped timerange: {{ graph.get_tv(graph.cts_start_mom) }} to {{ graph.get_tv(graph.cts_end_mom) }}
                            <input type="button" class="btn btn-xs btn-warning" value="apply" ng-click="use_crop(graph)"></input>
                        </span>
                        <div ng-show="graph.active && !graph.error">
                            <img-cropped ng-src="{{ graph.src }}" graph="graph">
                            </img-cropped>
                        </div>
                    </td>
                </tr>
            </table>
        </div>
    </div>
</div>
"""

{% endverbatim %}

class d_graph
    constructor: (@num, @xml) ->
        @active = true
        @error = false
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
            if t_entry.node.attr("devices")?
                return t_entry._name + " (" + t_entry.node.attr("devices") + ")"
            else
                return t_entry._name
        else
            if t_entry.node.attr("devices")?
                return t_entry._name + " (" + t_entry.node.attr("devices") + ")"
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

class pd_timeshift
    constructor: (@name, @seconds) ->

add_rrd_directive = (mod) ->
    mod.controller("rrd_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "$timeout"
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
            $scope.all_timeshifts = [
                new pd_timeshift("none", 0)
                new pd_timeshift("1 hour", 60 * 60)
                new pd_timeshift("1 day", 24 * 60 * 60)
                new pd_timeshift("1 week", 7 * 24 * 60 * 60)
                new pd_timeshift("1 month (31 days)", 31 * 24 * 60 * 60)
                new pd_timeshift("1 year (365 days)", 365 * 24 * 60 * 60)
            ]
            moment().utc()
            $scope.dt_valid = true
            $scope.vector_valid = false
            $scope.to_date_mom = moment()
            $scope.from_date_mom = moment().subtract("days", 1)
            $scope.cur_dim = $scope.all_dims[1]
            $scope.error_string = ""
            $scope.searchstr = ""
            $scope.is_loading = true
            $scope.cur_selected = []
            $scope.active_ts = undefined
            # to be set by directive
            $scope.auto_select_keys = []
            $scope.draw_on_init = false
            $scope.graph_list = {}
            $scope.graph_list = []
            $scope.hide_zero = false
            $scope.merge_devices = true
            $scope.show_options = false
            $scope.merge_cd = false
            $scope.g_tree = new rrd_tree($scope)
            $scope.$watch("from_date_mom", (new_val) ->
                $scope.update_dt() 
            )
            $scope.$watch("to_date_mom", (new_val) ->
                $scope.update_dt() 
            )
            $scope.update_dt = () ->
                # force moment
                from_date = moment($scope.from_date_mom)
                to_date = moment($scope.to_date_mom)
                $scope.dt_valid = from_date.isValid() and to_date.isValid()
                if $scope.dt_valid
                    diff = to_date - from_date 
                    if diff < 0
                        noty
                            text : "exchanged from with to date"
                            type : "warning"
                        $scope.to_date_mom = from_date
                        $scope.from_date_mom = to_date
                    else if diff < 60000
                        $scope.dt_valid = false
            $scope.set_active_tr = (new_tr) ->
                $scope.from_date_mom = new_tr.get_from()
                $scope.to_date_mom   = new_tr.get_to()
                $scope.update_dt()
            $scope.set_active_ts = (new_ts) ->
                if new_ts.seconds
                    $scope.active_ts = new_ts
                else
                    $scope.active_ts = undefined
            $scope.set_active_dim = (cur_dim) ->
                $scope.cur_dim = cur_dim
            $scope.new_devsel = (_dev_sel, _devg_sel) ->
                $scope.devsel_list = _dev_sel
                $scope.reload()
            $scope.toggle_merge_cd = () ->
                $scope.merge_cd = !$scope.merge_cd
                if $scope.merge_cd and not $scope.cds_already_merged
                    $scope.cds_already_merged = true
                    call_ajax
                        url  : "{% url 'rrd:merge_cds' %}"
                        data : {
                            "pks" : $scope.devsel_list
                        }
                        dataType: "json"
                        success : (json) =>
                            $scope.feed_rrd_json(json)
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
                                # node_result
                                num_devs = parseInt($(xml).find("node_result").attr("devices") ? "1")
                                if $scope.auto_select_keys.length
                                    $scope.auto_select_re = new RegExp($scope.auto_select_keys.join("|"))
                                else
                                    $scope.auto_select_re = null
                                $scope.add_nodes(undefined, $scope.vector)
                                $scope.is_loading = false
                                $scope.$apply(
                                    $scope.vector_valid = true
                                    $scope.num_struct = $scope.vector.find("entry").length
                                    $scope.num_devices = num_devs
                                    $scope.num_mve = $scope.vector.find("mve").length
                                    $scope.num_mve_sel = 0
                                    if $scope.auto_select_re
                                        # recalc tree when an autoselect_re is present
                                        $scope.g_tree.show_selected(false)
                                        $scope.selection_changed()
                                        if $scope.draw_on_init and $scope.num_mve_sel
                                            $scope.draw_graph()
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
                            node   : xml_node
                            _name  : xml_node.attr("part")
                            _node_type : "s"
                        })
                        cur_node._show_select = false
                    else
                        if $scope.auto_select_re
                            _sel = $scope.auto_select_re.test(xml_node.attr("name"))
                        else
                            _sel = false
                        # value
                        cur_node = $scope.g_tree.new_node({
                            folder : false
                            expand : false
                            selected : _sel
                            node   : xml_node
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
                $scope.draw_graph()
            $scope.draw_graph = () =>
                call_ajax
                    url  : "{% url 'rrd:graph_rrds' %}"
                    data : {
                        "keys"       : angular.toJson($scope.cur_selected)
                        "pks"        : angular.toJson($scope.devsel_list)
                        "start_time" : moment($scope.from_date_mom).format(DT_FORM)
                        "end_time"   : moment($scope.to_date_mom).format(DT_FORM)
                        "size"       : $scope.cur_dim
                        "hide_zero"     : $scope.hide_zero
                        "merge_devices" : $scope.merge_devices
                        "timeshift"     : if $scope.active_ts then $scope.active_ts.seconds else 0
                    }
                    success : (xml) =>
                        graph_list = []
                        # graph matrix
                        graph_mat = {}
                        if parse_xml_response(xml)
                            num_graph = 0
                            for graph in $(xml).find("graph_list > graph")
                                graph = $(graph)
                                graph_key = graph.attr("fmt_graph_key")
                                dev_key = graph.attr("fmt_device_key")
                                if !(graph_key of graph_mat)
                                    graph_mat[graph_key] = {}
                                num_graph++
                                cur_graph = new d_graph(num_graph, graph)
                                graph_mat[graph_key][dev_key] = cur_graph
                                graph_list.push(cur_graph)
                        $scope.$apply(
                            $scope.graph_mat = graph_mat
                            $scope.graph_list = graph_list
                        )
            $scope.get_graph_keys = () ->
                return (key for key of $scope.graph_mat)
            $scope.$on("$destroy", () ->
                #console.log "dest"
            )                
    ]).directive("rrdgraph", ($templateCache) ->
        return {
            restrict : "EA"
            template : $templateCache.get("rrd_graph_template.html")
            link : (scope, el, attrs) ->
                if attrs["selectkeys"]?
                    scope.auto_select_keys = attrs["selectkeys"].split(",")
                if attrs["mergedevices"]?
                    scope.merge_devices = if parseInt(attrs["mergedevices"]) then true else false
                if attrs["graphsize"]?
                    scope.all_dims.push(attrs["graphsize"])
                    scope.cur_dim = attrs["graphsize"]
                scope.draw_on_init = attrs["draw"] ? false
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
                # clear error
                scope.graph.error = false
                clear = () ->
                    if scope.img
                        scope.img.next().remove()
                        scope.img.remove()
                        scope.img = undefined
                scope.$watch("src", (nv) ->
                    clear()
                    if nv
                        element.after("<img />")
                        myImg = element.next()
                        scope.img = myImg
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
                        myImg.bind("error", () ->
                            scope.$apply(() ->
                                scope.graph.error = true
                            )
                        )
                )
                scope.$on("$destroy", clear)
        }
    )

    add_tree_directive(mod)

root.add_rrd_directive = add_rrd_directive

{% endinlinecoffeescript %}

</script>
