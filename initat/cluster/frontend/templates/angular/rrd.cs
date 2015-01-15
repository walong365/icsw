{% load coffeescript %} 

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

{% verbatim %}

rrd_graph_template = """
<div>
    <p class="text-danger">{{ error_string }}</p>
    <h4 ng-show="vector_valid">
        <div class="input-group form-inline">
            <div class="form-group">
                Vector info:
                <span class="label label-primary" title="structural entries">{{ num_struct }}<span ng-show="num_devices > 1" title="number of devices"> / {{ num_devices }}</span></span> /
                <span class="label label-primary" title="data entries">{{ num_mve }}<span ng-show="num_mve_sel" title="selected entries"> / {{ num_mve_sel }}</span></span>, 
            </div>
            <div class="form-group">
                <div class="input-group-btn">
                    <button type="button" ng-class="show_tree && 'btn btn-xs btn-primary' || 'btn btn-xs'" ng-click="show_tree=!show_tree">
                        <span class="glyphicon glyphicon-align-left"></span>
                        tree
                    </button>
                </div>
            </div>&nbsp;
            <div class="form-group">
                <div class="input-group-btn">
                    <button type="button" class="btn btn-xs btn-success" ladda="is_drawing" ng-show="cur_selected.length && dt_valid" ng-click="draw_graph()">
                        <span title="draw graph(s)" class="glyphicon glyphicon-pencil"></span>
                     </button>
                </div>
            </div>&nbsp;
            <div class="form-group">
                <div class="input-group-btn">
                    <div class="btn-group">
                        <button type="button" class="btn btn-xs btn-primary dropdown-toggle" data-toggle="dropdown">
                        <span class="glyphicon glyphicon-zoom-in"></span>
                            {{ cur_dim }} <span class="caret"></span>
                        </button>
                        <ul class="dropdown-menu">
                            <li ng-repeat="dim in all_dims" ng-click="set_active_dim(dim)"><a href="#">{{ dim }}</a></li>
                        </ul>
                    </div>
                </div>
            </div>&nbsp;
            <div class="form-group">
                <div class="input-group-btn">
                    <div class="btn-group">
                        <button type="button" class="btn btn-xs btn-primary dropdown-toggle" data-toggle="dropdown">
                            <span class="glyphicon glyphicon-time"></span>
                            timerange <span class="caret"></span>
                        </button>
                        <ul class="dropdown-menu">
                            <li ng-repeat="tr in all_timeranges" ng-click="set_active_tr(tr)"><a href="#">{{ tr.name }}</a></li>
                        </ul>
                    </div>
                </div>
            </div>&nbsp;
            <div class="form-group">
                <div class="input-group-btn">
                    <div class="btn-group">
                        <button type="button" class="btn btn-xs dropdown-toggle" ng-class="active_ts && 'btn-primary'" data-toggle="dropdown">
                            <span class="glyphicon glyphicon-dashboard"></span>
                            timeshift <span ng-show="active_ts">({{ active_ts.name }})</span><span class="caret"></span>
                        </button>
                        <ul class="dropdown-menu">
                            <li ng-repeat="ts in all_timeshifts" ng-click="set_active_ts(ts)"><a href="#">{{ ts.name }}</a></li>
                        </ul>
                    </div>
                </div>
            </div>&nbsp;
            <div class="form-group">
                <div class="input-group-btn">
                    <div class="btn-group">
                        <button type="button" class="btn btn-xs btn-success dropdown-toggle" data-toggle="dropdown" title="which jobs to show">
                            <span class="glyphicon glyphicon-tasks"></span>
                            {{ get_job_mode(job_mode) }}<span class="caret"></span>
                        </button>
                        <ul class="dropdown-menu">
                            <li ng-repeat="_jm in job_modes" ng-show="job_mode_allowed(_jm)" ng-click="set_job_mode(_jm)"><a href="#">{{ get_job_mode(_jm) }}</a></li>
                        </ul>
                    </div>
                </div>
            </div>&nbsp;
            <div class="form-group">
                <div class="input-group-btn">
                    <button type="button" class="btn btn-success btn-xs" ng-click="move_to_now()" title="move current timeframe to now">
                        <span class="glyphicon glyphicon-step-forward"></span>
                    </button>
                </div>
            </div>&nbsp;
            <div class="form-group">
                <div class="input-group-btn">
                    <button type="button" class="btn btn-success btn-xs" ng-click="set_to_now()" title="set endpoint to now">
                        <span class="glyphicon glyphicon-fast-forward"></span>
                    </button>
                </div>
            </div>&nbsp;
            <div class="form-group">
                <div class="input-group-btn">
                    <button type="button" ng-class="hide_empty && 'btn btn-xs btn-warning' || 'btn btn-xs'" ng-click="hide_empty=!hide_empty" title="hide empty (==always zero) graphs">
                        <span class="glyphicon glyphicon-ban-circle"></span>
                    </button>
                </div>
            </div>&nbsp;
            <div class="form-group">
                <div class="input-group-btn">
                    <button type="button" ng-class="include_zero && 'btn btn-xs btn-warning' || 'btn btn-xs'" ng-click="include_zero=!include_zero" title="scale graph to always include y=0">
                        <span class="glyphicon glyphicon-download"></span>
                    </button>
                </div>
            </div>&nbsp;
            <div class="form-group">
                <div class="input-group-btn">
                    <button type="button" ng-class="show_forecast && 'btn btn-xs btn-warning' || 'btn btn-xs'" ng-click="show_forecast=!show_forecast" title="show forecast">
                        <span class="glyphicon glyphicon-eye-open"></span>
                    </button>
                </div>
            </div>&nbsp;
            <div class="form-group">
                <div class="input-group-btn">
                    <button type="button" ng-class="show_values && 'btn btn-xs btn-warning' || 'btn btn-xs'" ng-click="show_values=!show_values" title="show numeric values">
                        <span class="glyphicon glyphicon-list"></span>
                    </button>
                </div>
            </div>&nbsp;
            <div class="form-group" ng-show="!merge_cd">
                <div class="input-group-btn">
                    <button type="button" ng-class="merge_cd && 'btn btn-xs btn-warning' || 'btn btn-xs'" ng-click="toggle_merge_cd()" title="Merge RRDs from controlling devices">
                        <span class="glyphicon glyphicon-off"></span>
                    </button>
                </div>
            </div>&nbsp;
            <div class="form-group" ng-show="devsel_list.length > 1">
                <div class="input-group-btn">
                    <button type="button" ng-class="scale_y && 'btn btn-xs btn-success' || 'btn btn-xs'" ng-click="scale_y=!scale_y" title="scale ordinate to be able to compare graphs">
                        <span class="glyphicon glyphicon-sort"></span>
                    </button>
                </div>
                <div class="input-group-btn">
                    <button type="button" ng-class="merge_devices && 'btn btn-xs btn-success' || 'btn btn-xs'" ng-click="merge_devices=!merge_devices" title="show data from all devices on one graph">
                        <span class="glyphicon glyphicon-th"></span>
                    </button>
                </div>
            </div>
            <div class="form-group">
                <div class="input-group">
                    <span class="input-group-addon">
                         from
                    </span>
                    <input type="text" class="form-control" ng-model="from_date_mom">
                    </input>
                    <span class="dropdown-toggle input-group-addon">
                        <div class="dropdown">
                            <button class="btn dropdown-toggle btn-xs" data-toggle="dropdown">
                                 <i class="glyphicon glyphicon-calendar"></i>
                            </button>
                            <ul class="dropdown-menu" role="menu">
                                <datetimepicker ng-model="from_date_mom" data-datetimepicker-config="{ dropdownSelector: '#dropdownfrom' }"/>
                            </ul>
                        </div>
                    </span>
                </div>
            </div>
            <div class="form-group">
                <div class="input-group">
                    <span class="input-group-addon">
                         to
                    </span>
                    <input type="text" class="form-control" ng-model="to_date_mom">
                    </input>
                    <span class="dropdown-toggle input-group-addon">
                        <div class="dropdown">
                            <button class="btn dropdown-toggle btn-xs" data-toggle="dropdown">
                                 <i class="glyphicon glyphicon-calendar"></i>
                            </button>
                            <ul class="dropdown-menu" role="menu">
                                <datetimepicker ng-model="to_date_mom" data-datetimepicker-config="{ dropdownSelector: '#dropdownfrom' }"/>
                            </ul>
                        </div>
                    </span>
                </div>
            </div>
        </div>
    </h4>
    <div class="row">
        <div class="col-md-3" ng-show="show_tree">  
            <div class="input-group">
                <input type="text" class="form-control" ng-disabled="is_loading" ng-model="searchstr" placeholder="search ..." ng-change="update_search()"></input>
                <span class="input-group-btn">
                    <button class="btn btn-success" ng-show="cur_selected.length && dt_valid" type="button" ladda="is_drawing" ng-click="draw_graph()"><span title="draw graph(s)" class="glyphicon glyphicon-pencil"></span></button>
                    <button class="btn btn-danger" type="button" ng-click="clear_selection()"><span title="clear selection" class="glyphicon glyphicon-ban-circle"></span></button>
                </span>
            </div>
            <tree treeconfig="g_tree"></tree>
        </div>
        <div ng-class="show_tree && 'col-md-9' || 'col-md-12'" ng-show="graph_list.length">
            <h4>{{ graph_list.length }} graphs, {{ graph_list[0].get_tv(graph_list[0].ts_start_mom) }} to {{ graph_list[0].get_tv(graph_list[0].ts_end_mom) }}</h4>
            <table class="table-condensed">
                <tr ng-repeat="gkey in get_graph_keys()">
                    <td ng-repeat="(dkey, graph) in graph_mat[gkey]" style="vertical-align:top;">
                        <h4 ng-show="!graph.error">
                            <span class="label label-default" ng-click="graph.toggle_expand()">
                                <span ng-class="graph.get_expand_class()"></span>
                                graph \#{{ graph.num }}
                            </span>&nbsp;
                            <ng-pluralize count="graph.num_devices" when="{'one' : '1 device', 'other' : '{} devices'}"></ng-pluralize>: {{ graph.get_devices() }}
                        </h4>
                        <h4 ng-show="graph.removed_keys.length">
                            {{ graph.removed_keys.length }} keys not shown (zero data) <span class="glyphicon glyphicon-info-sign" title="{{ graph.get_removed_keys() }}"></span>
                        </h4>
                        <h4 class="text-danger" ng-show="graph.error">Error loading graph ({{ graph.num }})</h4>
                        <span ng-show="graph.cropped && graph.active">cropped timerange: {{ graph.get_tv(graph.cts_start_mom) }} to {{ graph.get_tv(graph.cts_end_mom) }}
                            <input type="button" class="btn btn-xs btn-warning" value="apply" ng-click="use_crop(graph)"></input>
                        </span>
                        <div ng-show="graph.active && !graph.error && graph.src">
                            <img-cropped ng-src="{{ graph.src }}" graph="graph">
                            </img-cropped>
                        </div>
                        <div ng-show="!graph.src">
                            <span class="text-warning">no graph created</span>
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
        @src = @xml.attr("href") or ""
        @num_devices = @xml.find("devices device").length
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
    get_devices: () ->
        dev_names = ($(entry).text() for entry in @xml.find("devices device"))
        return dev_names.join(", ")
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
        @crop_width = parseInt((sel.x2 - sel.x) * ts_range / @gfx_width)
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
        @show_total_descendants = false
        @show_childs = false
    get_name : (t_entry) ->
        if t_entry._node_type == "h"
            return "vector"
        else
            node_name = t_entry._display_name
            if t_entry._dev_pks.length > 1
                return "#{node_name} (#{t_entry._dev_pks.length})"
            else
                return node_name
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
    get_from: (cur_from, cur_to) =>
        if @to
            # from and to set, return from
            return @from
        else
            # special format, no to set, from == moment() - @from hours
            return moment().subtract(@from, "hours")
    get_to: (cur_from, cur_to) =>
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
                new pd_timerange("last 24 hours", 24, undefined)
                new pd_timerange("last day", moment().subtract(1, "days").startOf("day"), moment().subtract(1, "days").endOf("day"))
                new pd_timerange("current week", moment().startOf("week"), moment().endOf("week"))
                new pd_timerange("last week", moment().subtract(1, "week").startOf("week"), moment().subtract(1, "week").endOf("week"))
                new pd_timerange("current month", moment().startOf("month"), moment().endOf("month"))
                new pd_timerange("last month", moment().subtract(1, "month").startOf("month"), moment().subtract(1, "month").endOf("month"))
                new pd_timerange("current year", moment().startOf("year"), moment().endOf("year"))
                new pd_timerange("last year", moment().subtract(1, "year").startOf("year"), moment().subtract(1, "year").endOf("year"))
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
            $scope.from_date_mom = moment().subtract(1, "days")
            $scope.cur_dim = $scope.all_dims[1]
            $scope.error_string = ""
            $scope.searchstr = ""
            $scope.is_loading = true
            $scope.is_drawing = false
            $scope.cur_selected = []
            $scope.active_ts = undefined
            # to be set by directive
            $scope.auto_select_keys = []
            $scope.draw_on_init = false
            $scope.graph_list = {}
            $scope.graph_list = []
            $scope.hide_empty = true
            # none, all or selected
            $scope.job_modes = ["none", "all", "selected"]
            $scope.job_mode = $scope.job_modes[0]
            $scope.selected_job = 0
            $scope.include_zero = true
            $scope.show_forecast = false
            $scope.show_values = true
            $scope.cds_already_merged = false
            $scope.merge_cd = false
            $scope.scale_y = true
            $scope.merge_devices = false
            $scope.show_tree = true
            $scope.g_tree = new rrd_tree($scope)
            $scope.$watch("from_date_mom", (new_val) ->
                $scope.update_dt() 
            )
            $scope.$watch("to_date_mom", (new_val) ->
                $scope.update_dt() 
            )
            $scope.set_job_mode = (new_jm) -> 
                $scope.job_mode = new_jm
            $scope.get_job_mode = (_jm) ->
                if _jm == "selected"
                    return "#{_jm} (#{$scope.selected_job})"
                else
                    return _jm    
            $scope.job_mode_allowed = (cur_jm) ->
                if cur_jm == "selected" and not $scope.selected_job
                    return false
                else
                    return true     
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
            $scope.move_to_now = () ->
                # shift timeframe
                _timeframe = moment.duration($scope.to_date_mom.unix() - $scope.from_date_mom.unix(), "seconds")
                $scope.from_date_mom = moment().subtract(_timeframe)
                $scope.to_date_mom = moment()
            $scope.set_to_now = () ->
                # set to_date to now
                $scope.to_date_mom = moment()
            $scope.set_active_tr = (new_tr) ->
                new_from = new_tr.get_from($scope.from_date_mom, $scope.to_date_mom)
                new_to   = new_tr.get_to($scope.from_date_mom, $scope.to_date_mom)
                $scope.from_date_mom = new_from
                $scope.to_date_mom   = new_to
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
                        "pks" : $scope.devsel_list
                    }
                    dataType: "json"
                    success : (json) =>
                        $scope.feed_rrd_json(json)
            
            $scope.feed_rrd_json = (json) ->
                if "error" of json
                    noty
                        text : json["error"]
                        type : "error"
                else
                    if $scope.auto_select_keys.length
                        $scope.auto_select_re = new RegExp($scope.auto_select_keys.join("|"))
                    else
                        $scope.auto_select_re = null
                    # to machine vector
                    $scope.num_devices = 0
                    root_node = $scope.init_machine_vector()
                    $scope.num_struct = 0
                    $scope.num_mve = 0
                    for dev in json._nodes
                        if dev._nodes?
                            mv = dev._nodes[0]
                            $scope.add_machine_vector(root_node, dev.pk, mv)
                            if dev._nodes.length > 1
                                # compound
                                $scope.add_machine_vector(root_node, dev.pk, dev._nodes[1])
                            $scope.num_devices++
                    $scope.is_loading = false
                    $scope.$apply(
                        $scope.vector_valid = if $scope.num_struct then true else false
                        if $scope.vector_valid
                            $scope.error_string = ""
                            $scope.num_mve_sel = 0
                            if $scope.auto_select_re or $scope.cur_selected.length
                                # recalc tree when an autoselect_re is present
                                $scope.g_tree.show_selected(false)
                                $scope.selection_changed()
                                if $scope.draw_on_init and $scope.num_mve_sel
                                    $scope.draw_graph()
                        else
                            $scope.error_string = "No vector found"
                    )

            $scope._add_structural_entry = (entry, lut, parent) =>
                _latest_is_entry = entry._tag in ["mve", "cve"]
                parts = entry.name.split(".")
                _pn = ""
                for _part in parts
                    if pn
                        pn = "#{pn}.#{_part}"
                    else
                        pn = _part
                    if pn of lut
                        cur_node = lut[pn]
                        if $scope.mv_dev_pk not in cur_node._dev_pks
                            cur_node._dev_pks.push($scope.mv_dev_pk)
                        if pn == entry.name and _latest_is_entry
                            true
                    else
                        if pn == entry.name and _latest_is_entry
                            # value entry
                            $scope._add_value_entry(entry, lut, parent)
                        else
                            # override name if display_name is set and this is the structural entry at the bottom
                            if entry.display_name? and pn == entry.name
                                display_name = entry.display_name
                            else
                                display_name = _part
                            # structural
                            cur_node = $scope.g_tree.new_node({
                                folder : true,
                                expand : false
                                _name  : _part
                                _display_name: display_name
                                _mult : 1
                                _dev_pks : [$scope.mv_dev_pk]
                                _node_type : "s"
                                _show_select: false
                            })
                            $scope.num_struct++
                            lut[pn] = cur_node
                            parent.add_child(cur_node, $scope._child_sort)
                    parent = cur_node
                return parent
            
            $scope._child_sort = (list, new_node) ->
                _idx = 0
                for _entry in list
                    if _entry._display_name > new_node._display_name
                        break
                    _idx++
                return _idx
                
            $scope._expand_info = (info, g_key) =>
                _num = 0
                for _var in g_key.split(":")[1].split(".")
                    _num++
                    info = info.replace("$#{_num}", _var)
                return info
                
            $scope._add_value_entry = (entry, lut, parent, top) =>
                # top is the parent node from the machine vector (or undefined)
                if top?
                    # pde or mvl, graph_key is top.name + local node name
                    g_key = "#{top._tag}:#{top.name}.#{entry.key}"
                else
                    # mve or cve, graph_key is entry.name
                    g_key = "#{entry._tag}:#{entry.name}"
                if $scope.cur_selected.length
                    _sel = g_key in $scope.cur_selected
                else if $scope.auto_select_re
                    _sel = $scope.auto_select_re.test(g_key)
                else
                    _sel = false
                if g_key of lut
                    cur_node = lut[g_key]
                else
                    cur_node = $scope.g_tree.new_node({
                        folder : false
                        expand : false
                        node   : entry
                        selected: _sel
                        _dev_pks: []
                        _name  : entry.info
                        _display_name: $scope._expand_info(entry.info, g_key)
                        _node_type : "e"
                        _show_select: true
                        _g_key : g_key
                    })
                    $scope.num_mve++
                    lut[g_key] = cur_node
                    parent.add_child(cur_node, $scope._child_sort)
                cur_node._dev_pks.push($scope.mv_dev_pk)
            
            $scope.init_machine_vector = () =>
                $scope.lut = {}
                $scope.g_tree.clear_root_nodes()
                root_node = $scope.g_tree.new_node({
                    folder : true
                    expand : true
                    _node_type : "h"
                    _show_select : false
                })
                $scope.g_tree.add_root_node(root_node)
                return root_node

            $scope.add_machine_vector = (root_node, dev_pk, mv) =>
                $scope.mv_dev_pk = dev_pk
                lut = $scope.lut
                for entry in mv._nodes
                    _tag = entry._tag
                    if _tag in ["mve", "cve"]
                        # add machine vector entry or compound data
                        $scope._add_structural_entry(entry, lut, root_node)
                    else if _tag in ["pde", "mvl"]
                        # add performance data header
                        if _tag == "mvl" and entry.info and entry.name.match(/\.snmp_/g)
                            # hack to beautify snmp network entries
                            entry.display_name = "[S] #{entry.info}"
                        _pde_mvl = $scope._add_structural_entry(entry, lut, root_node)
                        # add performance data values
                        for _sub in entry._nodes
                            $scope._add_value_entry(_sub, lut, _pde_mvl, entry)
                    else
                        # unhandled entry
                        true
                        console.log entry

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
                if graph.crop_width > 600
                    $scope.from_date_mom = graph.cts_start_mom
                    $scope.to_date_mom = graph.cts_end_mom
                    $scope.draw_graph()
                else
                    _mins = parseInt(graph.crop_width / 60)
                    noty
                        text : "selected timeframe is too narrow (#{_mins} < 10 min)"
                        type : "warning"
            $scope.draw_graph = () =>
                if !$scope.is_drawing
                    $scope.is_drawing = true
                    call_ajax
                        url  : "{% url 'rrd:graph_rrds' %}"
                        data : {
                            "keys"       : angular.toJson($scope.cur_selected)
                            "pks"        : angular.toJson($scope.devsel_list)
                            "start_time" : moment($scope.from_date_mom).format(DT_FORM)
                            "end_time"   : moment($scope.to_date_mom).format(DT_FORM)
                            "size"       : $scope.cur_dim
                            "hide_empty"    : $scope.hide_empty
                            "job_mode"      : $scope.job_mode
                            "selected_job"  : $scope.selected_job 
                            "include_zero"  : $scope.include_zero
                            "show_forecast" : $scope.show_forecast
                            "show_values"   : $scope.show_values
                            "merge_cd"      : $scope.merge_cd
                            # flag if the controlling devices are shown in the rrd tree
                            "cds_already_merged" : $scope.cds_already_merged
                            "scale_y"       : $scope.scale_y
                            "merge_devices" : $scope.merge_devices
                            "timeshift"     : if $scope.active_ts then $scope.active_ts.seconds else 0
                        }
                        success : (xml) =>
                            $scope.is_drawing = false
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
                if attrs["fromdt"]? and parseInt(attrs["fromdt"])
                    scope.from_date_mom = moment.unix(parseInt(attrs["fromdt"]))
                if attrs["todt"]? and parseInt(attrs["todt"])
                    scope.to_date_mom = moment.unix(parseInt(attrs["todt"]))
                if attrs["jobmode"]?
                    scope.job_mode = attrs["jobmode"]
                if attrs["selectedjob"]?
                    scope.selected_job = attrs["selectedjob"]
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
