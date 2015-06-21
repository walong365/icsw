# Copyright (C) 2012-2015 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

class Sensor
    constructor: (@graph, @xml) ->
        @mvs_id = parseInt(@xml.attr("db_key").split(".")[0])
        @mvv_id = parseInt(@xml.attr("db_key").split(".")[1])
        @device_id = parseInt(@xml.attr("device"))
        @mv_key = @xml.attr("mv_key")
        @cfs = {}
        _value = 0.0
        for _cf in @xml.find("cfs cf")
            _cf = $(_cf)
            @cfs[_cf.attr("cf")] = _cf.text()
            _value += parseFloat(_cf.text())
        @cf_list = _.keys(@cfs).sort()
        _value = _value / @cf_list.length
        # create default threshold
        @thresholds = []
        _new_th = new Threshold(@)
        _new_th.value = _value
        @thresholds.push(_new_th)

class Threshold
    constructor: (@sensor) ->
        @hysteresis = 1.0
        @upper_limit = false

class DisplayGraph
    constructor: (@num, @xml, @sensor_action_list) ->
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
            @removed_keys.push(full_draw_key($(entry).attr("struct_key"), $(entry).attr("value_key")))
        # build list of values for which we can createa sensor (== full db_key needed)
        # number of (als possible) sensors
        @num_sensors = 0
        @sensors = []
        for gv in @xml.find("graph_values graph_value")
            if $(gv).attr("db_key").match(/\d+\.\d+/)
                @num_sensors++
                @sensors.push(new Sensor(@, $(gv)))
    get_sensor_info: () ->
        return "#{@num_sensors} sensor sources"
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
      
DT_FORM = "YYYY-MM-DD HH:mm ZZ"

full_draw_key = (s_key, v_key) ->
    _key = s_key
    if v_key
        _key = "#{_key}.#{v_key}"
    return _key

get_node_keys = (node) ->
    # mapping for graph.py
    return {
        "struct_key": node._key_pair[0]
        "value_key": node._key_pair[1]
        "build_info": if node.build_info? then node.build_info else "",
    }
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

angular.module(
    "icsw.rrd.graph",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular"
    ]
).controller("icswGraphOverviewCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource",
        "$q", "$modal", "$timeout", "ICSW_URLS", "icswRRDGraphTreeService", "icswCallAjaxService", "icswParseXMLResponseService", "toaster",
        "icswCachingCall",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, $q, $modal, $timeout, ICSW_URLS, icswRRDGraphTreeService, icswCallAjaxService, icswParseXMLResponseService, toaster, icswCachingCall) ->
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
        $scope.scale_modes = ["level", "none", "to100"]
        $scope.scale_mode  = $scope.scale_modes[0]
        $scope.merge_devices = false
        $scope.merge_graphs = false
        $scope.show_tree = true
        $scope.g_tree = new icswRRDGraphTreeService($scope)
        $q.all([icswCachingCall.fetch($scope.$id, ICSW_URLS.REST_SENSOR_ACTION_LIST, {}, [])]).then((data) ->
            $scope.sensor_action_list = data[0]
        )
        $scope.$watch("from_date_mom", (new_val) ->
            if $scope.change_dt_to
                $timeout.cancel($scope.change_dt_to)
            $scope.change_dt_to = $timeout($scope.update_dt, 2000)
        )
        $scope.$watch("to_date_mom", (new_val) ->
            if $scope.change_dt_to
                $timeout.cancel($scope.change_dt_to)
            $scope.change_dt_to = $timeout($scope.update_dt, 2000)
        )
        $scope.set_job_mode = (new_jm) ->
            $scope.job_mode = new_jm
        $scope.set_scale_mode = (new_sm) ->
            $scope.scale_mode = new_sm
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
                    toaster.pop("warning", "", "exchanged from with to date")
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
            # clear graphs
            $scope.graph_list = []
            $scope.devsel_list = _dev_sel
            $scope.reload()

        $scope.toggle_merge_cd = () ->
            $scope.merge_cd = !$scope.merge_cd
            if $scope.merge_cd and not $scope.cds_already_merged
                $scope.cds_already_merged = true
                icswCallAjaxService
                    url  : ICSW_URLS.RRD_MERGE_CDS
                    data : {
                        "pks" : $scope.devsel_list
                    }
                    dataType: "json"
                    success : (json) =>
                        $scope.feed_rrd_json(json)

        $scope.reload = () ->
            $scope.vector_valid = false
            icswCallAjaxService
                url  : ICSW_URLS.RRD_DEVICE_RRDS
                data : {
                    "pks" : $scope.devsel_list
                }
                dataType: "json"
                success : (json) =>
                    $scope.feed_rrd_json(json)
        
        $scope.feed_rrd_json = (json) ->
            if "error" of json
                toaster.pop("error", "", json["error"])
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
                for dev in json
                    if dev.struct? and dev.struct.length
                        $scope.add_machine_vector(root_node, dev.pk, dev.struct)
                        #if dev._nodes.length > 1
                        #    # compound
                        #    $scope.add_machine_vector(root_node, dev.pk, dev._nodes[1])
                        $scope.num_devices++
                $scope.g_tree.recalc()
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
            parts = entry.key.split(".")
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
                else
                    # override name if display_name is set and this is the structural entry at the bottom
                    # structural
                    cur_node = $scope.g_tree.new_node(
                        {
                            folder : true,
                            expand : false
                            _display_name: _part
                            _mult : 1
                            _dev_pks : [$scope.mv_dev_pk]
                            _node_type : "s"
                            _show_select: false
                            build_info: ""
                            # marker: this is not an mve entry
                            _is_mve: false
                        }
                    )
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
            for _var in g_key.split(".")
                _num++
                info = info.replace("$#{_num}", _var)
            return info
            
        $scope._add_value_entry = (entry, lut, parent, top) =>
            # top is the parent node from the value entry (== mvstructentry)
            if entry.key
                g_key = "#{top.key}.#{entry.key}"
            else
                g_key = top.key
            if $scope.cur_selected.length
                _sel = g_key in $scope.cur_selected
            else if $scope.auto_select_re
                _sel = $scope.auto_select_re.test(g_key)
            else
                _sel = false
            if g_key of lut
                # rewrite structural entry as mve
                cur_node = lut[g_key]
                if not cur_node._is_mve
                    # change marker
                    cur_node._is_mve = true
                    cur_node._dev_pks = []
                    $scope.num_struct--
                    $scope.num_mve++
            else
                cur_node = $scope.g_tree.new_node(
                    {
                        expand : false
                        selected: _sel
                        _dev_pks: []
                        _is_mve: true
                    }
                )
                $scope.num_mve++
                lut[g_key] = cur_node
                parent.add_child(cur_node, $scope._child_sort)
            cur_node._key_pair = [top.key, entry.key]
            cur_node._display_name = $scope._expand_info(entry.info, g_key)
            if $scope.mv_dev_pk not in cur_node._dev_pks
                cur_node._dev_pks.push($scope.mv_dev_pk)
            cur_node._node_type = "e"
            cur_node.build_info = entry.build_info
            cur_node.folder = false
            cur_node._show_select = true
            cur_node._g_key = g_key
            cur_node.node = entry
            cur_node.selected = _sel

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
            for entry in mv
                _struct = $scope._add_structural_entry(entry, lut, root_node)
                for _sub in entry.mvvs
                    $scope._add_value_entry(_sub, lut, _struct, entry)

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
                        entry.set_selected(if (entry._display_name.match(cur_re) or entry._g_key.match(cur_re)) then true else false)
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
        $scope.$on("cropSet", (event, graph) ->
            event.stopPropagation()
            if graph.crop_width > 600
                $scope.from_date_mom = graph.cts_start_mom
                $scope.to_date_mom = graph.cts_end_mom
                $scope.draw_graph()
            else
                _mins = parseInt(graph.crop_width / 60)
                toaster.pop("warning", "", "selected timeframe is too narrow (#{_mins} < 10 min)")
        )
        $scope.draw_graph = () =>
            if !$scope.is_drawing
                $scope.is_drawing = true
                icswCallAjaxService
                    url  : ICSW_URLS.RRD_GRAPH_RRDS
                    data : {
                        "keys"       : angular.toJson((get_node_keys($scope.lut[key]) for key in $scope.cur_selected))
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
                        "scale_mode"    : $scope.scale_mode
                        "merge_devices" : $scope.merge_devices
                        "merge_graphs"  : $scope.merge_graphs
                        "timeshift"     : if $scope.active_ts then $scope.active_ts.seconds else 0
                    }
                    success : (xml) =>
                        $scope.is_drawing = false
                        graph_list = []
                        # graph matrix
                        graph_mat = {}
                        if icswParseXMLResponseService(xml)
                            num_graph = 0
                            for graph in $(xml).find("graph_list > graph")
                                graph = $(graph)
                                graph_key = graph.attr("fmt_graph_key")
                                dev_key = graph.attr("fmt_device_key")
                                if !(graph_key of graph_mat)
                                    graph_mat[graph_key] = {}
                                num_graph++
                                cur_graph = new DisplayGraph(num_graph, graph, $scope.sensor_action_list)
                                graph_mat[graph_key][dev_key] = cur_graph
                                graph_list.push(cur_graph)
                        $scope.$apply(
                            $scope.graph_mat = graph_mat
                            $scope.graph_list = graph_list
                        )
        $scope.$on("$destroy", () ->
            #console.log "dest"
        )                
]).directive("icswRrdGraph", ["$templateCache", ($templateCache) ->
    return {
        scope: true
        restrict : "EA"
        template : $templateCache.get("icsw.rrd.graph.overview")
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
        controller: "icswGraphOverviewCtrl"
    }
]).service("icswRRDGraphTreeService", () ->
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

).directive("icswRrdGraphList", ["$templateCache", "$compile", ($templateCache, $compile) ->
    return {
        restrict: "E"
        replace: true
        scope: {
            graphList: "="
            graphMatrix: "="
        }
        link: (scope, element, attr) ->
            scope.$watch("graphList", (new_val) ->
                element.children().remove()
                if new_val.length
                    element.append($compile($templateCache.get("icsw.rrd.graph.list.header"))(scope))
            )
            scope.get_graph_keys = () ->
                return (key for key of scope.graphMatrix)
    }
]).directive("icswRrdGraphThreshold", ["$templateCache", ($templateCache) ->
    return {
        restrict: "E"
        template: $templateCache.get("icsw.rrd.graph.threshold.create")

    }
]).service("icswRrdSensorDialogService", ["$q", "$compile", "$templateCache", ($q, $compile, $templateCache) ->
    return (scope, graph) ->
        sub_scope = scope.$new()
        sub_scope.hello = () ->
            return "hello"
        sub_scope.graph = graph
        sens_div = $compile($templateCache.get("icsw.rrd.graph.sensor"))(sub_scope)
        d = $q.defer()
        BootstrapDialog.show
            message: sens_div
            draggable: true
            title: "Modify / Create Sensors (" + graph.get_sensor_info() + ")"
            size: BootstrapDialog.SIZE_WIDE
            cssClass: "modal-tall"
            buttons: [
                {
                    icon: "glyphicon glyphicon-ok"
                    label: "OK"
                    cssClass: "btn-success"
                    action: (dialog) ->
                        dialog.close()
                        sub_scope.$destroy()
                        d.resolve()
                },
            ]
        return d.promise
]).directive("icswRrdGraphListGraph", ["$templateCache", "$compile", "icswRrdSensorDialogService", ($templateCache, $compile, icswRrdSensorDialogService) ->
    return {
        restrict: "E"
        replace: true
        scope: {
            graph: "="
        }
        # template: $templateCache.get("icsw.rrd.graph.list.graph")
        link: (scope, element, attr) ->
            graph_error = () ->
                element.children().remove()
                element.append(angular.element("<h4 class='text-danger'>Error loading graph (#{_graph.num})</h4>"))
            element.children().remove()
            _graph = scope.graph
            if not _graph.error
                element.append($compile($templateCache.get("icsw.rrd.graph.list.graph.header"))(scope))
            if _graph.removed_keys.length
                _rem_keys = _graph.get_removed_keys()
                element.append(angular.element("<h4>#{_graph.removed_keys.length} keys not shown (zero data) <span class='glyphicon glyphicon-info-sign' title=\"#{_rem_keys}\"></span></h4>"))
            if _graph.error
                graph_error()
            # element.append($compile($templateCache.get("icsw.rrd.graph.list.graph"))(scope))
            if not _graph.src
                element.append(angular.element("<div><span class='text-warning'>no graph created</span></div>"))
            else if not _graph.error
                _graph.error = false
                clear = () ->
                    if scope.img
                        scope.img.next().remove()
                        scope.img.remove()
                        scope.img = undefined
                clear()
                if _graph.src
                    crop_span = angular.element("<span><span></span><input type='button' class='btn btn-xs btn-warning' value='apply'/></span>")
                    if _graph.num_sensors
                        sens_el = angular.element("<input type='button' class='btn btn-primary btn-xs' value='Sensors'></input>")
                        sens_el.on("click", () ->
                            icswRrdSensorDialogService(scope, _graph).then(
                                () ->
                                    console.log "done"
                            )
                            #console.log "c"
                        )
                        element.after(sens_el)
                        sens_el.after(crop_span)
                    else
                        element.after(crop_span)
                    crop_span.find("input").on("click", () ->
                        scope.$apply(
                            scope.$emit("cropSet", _graph)
                        )
                    )
                    crop_span.hide()
                    myImg = angular.element("<img/>")
                    crop_span.after(myImg)
                    scope.img = myImg
                    myImg.attr("src", _graph.src)
                    $(myImg).Jcrop({
                        trackDocument: true
                        onSelect: (sel) ->
                            scope.$apply(() ->
                                if not _graph.cropped
                                    crop_span.show()
                                _graph.set_crop(sel)
                                crop_span.find("span").text(
                                    "cropped timerange: " +
                                    _graph.get_tv(_graph.cts_start_mom) +
                                    " to " +
                                    _graph.get_tv(_graph.cts_end_mom)
                                )
                            )
                        onRelease: () ->
                            scope.$apply(() ->
                                if _graph.cropped
                                    crop_span.hide()
                                _graph.clear_crop()
                            )
                    }, () ->
                        # not needed ?
                        bounds = this.getBounds()
                    )
                    myImg.bind("error", (event) ->
                        scope.$apply(() ->
                            _graph.error = true
                            graph_error()
                        )
                    )
                scope.$on("$destroy", clear)
                scope.$watch("graph.active", (new_val) ->
                    # true means hide and false means show ? strange but it works
                    if crop_span?
                        if _graph.cropped
                            if new_val
                                crop_span.show()
                            else
                                crop_span.hide()
                        if new_val
                            myImg.hide()
                        else
                            myImg.show()
                )
            element.on("$destroy", () ->
                # console.log "destr"
            )
    }
    # console.log "S", $scope.graph
])
