# Copyright (C) 2012-2016 init.at
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

DT_FORM = "YYYY-MM-DD HH:mm ZZ"

angular.module(
    "icsw.rrd.graph",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters",
        "restangular", "icsw.rrd.graphsetting",
    ]
).config(["$stateProvider", ($stateProvider) ->
    $stateProvider.state(
        "main.graph", {
            url: "/graph"
            templateUrl: "icsw.rrd.graph"
            icswData:
                pageTitle: "Graph"
                licenses: ["graphing"]
                rights: ["backbone.device.show_graphs"]
                menuEntry:
                    menukey: "stat"
                    icon: "fa-line-chart"
                    ordering: 40
        }
    )
]).service("icswRRDSensor", [()->

    class icswRRDSensor
        constructor: (@graph, @xml, sth_dict) ->
            @mvs_id = parseInt(@xml.attr("db_key").split(".")[0])
            @mvv_id = parseInt(@xml.attr("db_key").split(".")[1])
            @device_id = parseInt(@xml.attr("device"))
            @mv_key = @xml.attr("mv_key")
            @cfs = {}
            _value = 0.0
            _num_value = 0
            if not parseInt(@xml.attr("nan"))
                for _cf in @xml.find("cfs cf")
                    _cf = $(_cf)
                    @cfs[_cf.attr("cf")] = _cf.text()
                    if _cf.attr("cf") != "TOTAL"
                        _value += parseFloat(_cf.text())
                        _num_value++
            @cf_list = _.keys(@cfs).sort()
            if _num_value
                @mean_value = _value / _num_value
            else
                @mean_value = 0.0
            # create default threshold
            @thresholds = []
            if @mvv_id of sth_dict
                for _entry in sth_dict[@mvv_id]
                    @thresholds.push(_entry)

]).service("icswRRDDisplayGraph",
[
    "icswRRDSensor",
(
    icswRRDSensor,
) ->

    class icswRRDDisplayGraph
        constructor: (@num, @xml, @user_settings, @user_group_tree, @selection_list, @device_tree) ->
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

            full_draw_key = (s_key, v_key) ->
                _key = s_key
                if v_key
                    _key = "#{_key}.#{v_key}"
                return _key

            for entry in @xml.find("removed_keys removed_key")
                @removed_keys.push(full_draw_key($(entry).attr("struct_key"), $(entry).attr("value_key")))

            # build list of values for which we can createa sensor (== full db_key needed)
            # number of (als possible) sensors
            @num_sensors = 0
            @sensors = []
            for gv in @xml.find("graph_values graph_value")
                if $(gv).attr("db_key").match(/\d+\.\d+/)
                    # only a valid sensor when the db-idx has a device (no compound displays)
                    @num_sensors++
                    @sensors.push(new icswRRDSensor(@, $(gv), @user_settings.threshold_lut_by_mvv_id))
                    console.log @sensors, gv
            @sensors = _.sortBy(@sensors, (sensor) -> return sensor.mv_key)

        get_sensor_info: () ->
            return "#{@num_sensors} sensor sources"

        get_threshold_info: () ->
            _num_th = 0
            for _sensor in @sensors
                _num_th += _sensor.thresholds.length
            return "#{_num_th} Thresholds"

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

]).controller("icswGraphOverviewCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular",
    "$q", "$uibModal", "$timeout", "ICSW_URLS", "icswRRDGraphTree", "icswSimpleAjaxCall",
    "icswParseXMLResponseService", "toaster", "icswCachingCall", "icswUserService",
    "icswSavedSelectionService", "icswRRDGraphUserSettingService", "icswDeviceTreeService",
    "icswUserGroupTreeService", "icswDeviceTreeHelperService", "icswRRDDisplayGraph",
(
    $scope, $compile, $filter, $templateCache, Restangular,
    $q, $uibModal, $timeout, ICSW_URLS, icswRRDGraphTree, icswSimpleAjaxCall,
    icswParseXMLResponseService, toaster, icswCachingCall, icswUserService,
    icswSavedSelectionService, icswRRDGraphUserSettingService, icswDeviceTreeService,
    icswUserGroupTreeService,  icswDeviceTreeHelperService, icswRRDDisplayGraph,
) ->
        moment().utc()
        $scope.timeframe = undefined
        $scope.cur_selected = []
        # to be set by directive
        $scope.auto_select_keys = []
        $scope.graph_list = []
        # none, all or selected
        $scope.job_modes = ["none", "all", "selected"]
        $scope.job_mode = $scope.job_modes[0]
        $scope.selected_job = 0
        $scope.struct = {
            # draw when called
            draw_on_init: false
            # search string
            searchstr: ""
            # is drawing
            is_drawing: false
            # show tree
            show_tree: true
            # user
            user: undefined
            # selected devices
            devices: []
            # device tree
            device_tree: undefined
            # helper server
            dt_helper: undefined
            # draw tree
            g_tree: new icswRRDGraphTree(
                $scope
                {
                    show_selection_buttons: true
                    show_icons: false
                    expand_on_selection: true
                    show_select: true
                    show_descendants: true
                    show_total_descendants: false
                    show_childs: false
                    extra_args: ["build_info"]
                }
            )
            # user / group tree
            user_group_tree: undefined
            # user settings (RRDGraphUserSetting)
            user_settings: undefined
            # selections
            selection_list: undefined
            # vector (==treeView) valid
            vector_valid: false
            # vector data
            vectordata: {
                num_struct: 0
                num_mve: 0
                num_devices: 0
                num_mve_sel: 0
            }
            # error string, if not empty show as top-level warning-div
            error_string: "Init structures"
        }
        $scope.new_devsel = (dev_list) ->
            # clear graphs
            $scope.graph_list = []
            $scope.struct.error_string = "Loading structures"
            $scope.struct.vector_valid = false
            $q.all(
                [
                    icswUserService.load($scope.$id)
                    icswDeviceTreeService.load($scope.$id)
                    icswUserGroupTreeService.load($scope.$id),
                    icswSavedSelectionService.load_selections($scope.$id),
                    icswRRDGraphUserSettingService.load($scope.$id),
                ]
            ).then(
                (data) ->
                    $scope.struct.user = data[0]
                    $scope.struct.device_tree = data[1]
                    $scope.struct.user_group_tree = data[2]
                    $scope.struct.selection_list = data[3]
                    $scope.struct.user_settings = data[4]
                    $scope.struct.devices.length = 0
                    for entry in dev_list
                        if not entry.is_meta_device
                            $scope.struct.devices.push(entry)
                    hs = icswDeviceTreeHelperService.create($scope.struct.device_tree, $scope.struct.devices)
                    $scope.struct.error_string = "Adding sensor info"
                    $scope.struct.device_tree.enrich_devices(hs, ["sensor_threshold_info"]).then(
                        (done) ->
                            console.log $scope.struct
                            if $scope.struct.devices.length
                                $scope.load_tree()
                            else
                                $scope.struct.error_string = "No devices selected"
                    )
            )

        $scope.load_tree = () ->
            $scope.struct.error_string = "Loading VectorTree"
            $scope.struct.vectordata = {
                num_struct: 0
                num_mve: 0
                num_devices: 0
                num_mve_sel: 0
            }
            icswSimpleAjaxCall(
                url: ICSW_URLS.RRD_DEVICE_RRDS
                data: {
                    pks: (dev.idx for dev in $scope.struct.devices)
                }
                dataType: "json"
            ).then(
                (json) ->
                    $scope.feed_rrd_json(json)
                (error) ->
                    $scope.struct.error_string = "Error loading tree"
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

        $scope.feed_rrd_json = (json) ->
            if "error" of json
                toaster.pop("error", "", json["error"])
            else
                if $scope.auto_select_keys.length
                    $scope.auto_select_re = new RegExp($scope.auto_select_keys.join("|"))
                else
                    $scope.auto_select_re = null
                # to machine vector
                root_node = $scope.init_machine_vector()
                for dev in json
                    if dev.struct? and dev.struct.length
                        $scope.add_machine_vector(root_node, dev.pk, dev.struct)
                        #if dev._nodes.length > 1
                        #    # compound
                        #    $scope.add_machine_vector(root_node, dev.pk, dev._nodes[1])
                        $scope.struct.vectordata.num_devices++
                $scope.struct.g_tree.recalc()
                $scope.struct.vector_valid = if $scope.struct.vectordata.num_struct then true else false
                if $scope.struct.vector_valid
                    $scope.struct.error_string = ""
                    if $scope.auto_select_re or $scope.cur_selected.length
                        # recalc tree when an autoselect_re is present
                        $scope.struct.g_tree.show_selected(false)
                        $scope.selection_changed()
                        if $scope.struct.draw_on_init and $scope.struct.vectordata.num_mve_sel
                            $scope.draw_graph()
                else
                    $scope.struct.error_string = "No vector found"

        _child_sort = (list, new_node) ->
            _idx = 0
            for _entry in list
                if _entry._display_name > new_node._display_name
                    break
                _idx++
            return _idx
            
        $scope._add_structural_entry = (entry, lut, parent) =>
            parts = entry.key.split(".")
            _pn = ""
            _idx = 0
            for _part in parts
                _idx++
                _last = _idx == parts.length
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
                    cur_node = $scope.struct.g_tree.create_node(
                        {
                            folder : true,
                            expand : false
                            _display_name: if (entry.ti and _last) then entry.ti else _part
                            _mult : 1
                            _dev_pks : [$scope.mv_dev_pk]
                            _node_type : "s"
                            _show_select: false
                            build_info: []
                            # marker: this is not an mve entry
                            _is_mve: false
                        }
                    )
                    $scope.struct.vectordata.num_struct++
                    lut[pn] = cur_node
                    parent.add_child(cur_node, _child_sort)
                parent = cur_node
            return parent
        
        $scope._expand_info = (info, g_key) =>
            _num = 0
            for _var in g_key.split(".")
                _num++
                info = info.replace("$#{_num}", _var)
            return info
            
        $scope._add_value_entry = (entry, lut, parent, top) =>
            _vd = $scope.struct.vectordata
            # debg ?
            _vd.a = "ddd"
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
                    _vd.num_struct--
                    _vd.num_mve++
            else
                cur_node = $scope.struct.g_tree.create_node(
                    {
                        expand : false
                        selected: _sel
                        _dev_pks: []
                        _is_mve: true
                    }
                )
                cur_node.build_info = []
                _vd.num_mve++
                lut[g_key] = cur_node
                parent.add_child(cur_node, _child_sort)
            cur_node._key_pair = [top.key, entry.key]
            cur_node._display_name = $scope._expand_info(entry.info, g_key)
            if $scope.mv_dev_pk not in cur_node._dev_pks
                cur_node._dev_pks.push($scope.mv_dev_pk)
            cur_node._node_type = "e"
            cur_node.build_info.push(entry.build_info)
            cur_node.num_sensors = entry.num_sensors
            cur_node.folder = false
            cur_node._show_select = true
            cur_node._g_key = g_key
            cur_node.node = entry
            cur_node.selected = _sel

        $scope.init_machine_vector = () =>
            $scope.lut = {}
            $scope.struct.g_tree.clear_root_nodes()
            root_node = $scope.struct.g_tree.create_node(
                {
                    folder: true
                    expand: true
                    _node_type: "h"
                    _show_select: false
                }
            )
            root_node.build_info = []
            $scope.struct.g_tree.add_root_node(root_node)
            return root_node

        $scope.add_machine_vector = (root_node, dev_pk, mv) =>
            $scope.mv_dev_pk = dev_pk
            lut = $scope.lut
            for entry in mv
                _struct = $scope._add_structural_entry(entry, lut, root_node)
                for _sub in entry.mvvs
                    $scope._add_value_entry(_sub, lut, _struct, entry)

        $scope.update_search = () ->
            if $scope.cur_search_to?
                $timeout.cancel($scope.cur_search_to)
            $scope.cur_search_to = $timeout($scope.set_search_filter, 500)

        $scope.clear_selection = () =>
            $scope.struct.searchstr = ""
            $scope.set_search_filter()

        $scope.select_with_sensor = () =>
            $scope.struct.g_tree.toggle_tree_state(undefined, -1, false)
            $scope.struct.g_tree.iter(
                (entry) ->
                    if entry._node_type in ["e"]
                        entry.set_selected(if entry.num_sensors then true else false)
            )
            $scope.struct.g_tree.show_selected(false)
            $scope.selection_changed()

        $scope.set_search_filter = () =>
            if $scope.struct.searchstr
                try
                    cur_re = new RegExp($scope.struct.searchstr, "gi")
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
            $scope.cur_selected = $scope.struct.g_tree.get_selected(
                (entry) ->
                    if entry._node_type == "e" and entry.selected
                        return [entry._g_key]
                    else
                        return []
            )
            $scope.struct.vectordata.num_mve_sel = $scope.cur_selected.length

        $scope.$on("cropSet", (event, graph) ->
            event.stopPropagation()
            if graph.crop_width > 600
                $scope.timeframe.from_date_mom = graph.cts_start_mom
                $scope.timeframe.to_date_mom = graph.cts_end_mom
                $scope.draw_graph()
            else
                _mins = parseInt(graph.crop_width / 60)
                toaster.pop("warning", "", "selected timeframe is too narrow (#{_mins} < 10 min)")
        )

        $scope.draw_graph = () =>
            get_node_keys = (node) ->
                # mapping for graph.py
                return {
                    "struct_key": node._key_pair[0]
                    "value_key": node._key_pair[1]
                    "build_info": node.build_info
                }

            if !$scope.struct.is_drawing
                $scope.struct.is_drawing = true
                $scope.struct.error_string = "Drawing graphs"
                gfx = $q.defer()
                icswSimpleAjaxCall(
                    url  : ICSW_URLS.RRD_GRAPH_RRDS
                    data : {
                        "keys": angular.toJson((get_node_keys($scope.lut[key]) for key in $scope.cur_selected))
                        "pks": angular.toJson((dev.idx for dev in $scope.struct.devices))
                        "start_time": moment($scope.timeframe.from_date_mom).format(DT_FORM)
                        "end_time": moment($scope.timeframe.to_date_mom).format(DT_FORM)
                        "job_mode": $scope.job_mode
                        "selected_job": $scope.selected_job
                        "graph_setting": $scope.struct.user_settings.get_active().idx
                    }
                ).then(
                    (xml) ->
                        gfx.resolve(xml)
                    (xml) ->
                        gfx.resolve(xml)
                )
                gfx.promise.then(
                    (result) ->
                        xml = result
                        # reorder sensor threshold entries

                        $scope.struct.is_drawing = false
                        $scope.struct.error_string = ""
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
                                cur_graph = new icswRRDDisplayGraph(
                                    num_graph
                                    graph
                                    $scope.struct.user_settings,
                                    $scope.struct.user_group_tree
                                    $scope.struct.selection_list
                                    $scope.struct.device_tree
                                )
                                graph_mat[graph_key][dev_key] = cur_graph
                                graph_list.push(cur_graph)
                        $scope.graph_mat = graph_mat
                        $scope.graph_list = graph_list
                )
        $scope.$on("$destroy", () ->
            #console.log "dest"
        )                
]).directive("icswRrdGraph",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        scope: true
        restrict: "EA"
        template: $templateCache.get("icsw.rrd.graph.overview")
        link: (scope, el, attrs) ->
            # to be improved
            # console.log attrs
            if attrs["icswSelectKeys"]?
                scope.auto_select_keys = attrs["icswSelectKeys"].split(",")
            if attrs["fromdt"]? and parseInt(attrs["fromdt"])
                scope.from_date_mom = moment.unix(parseInt(attrs["fromdt"]))
            if attrs["todt"]? and parseInt(attrs["todt"])
                scope.to_date_mom = moment.unix(parseInt(attrs["todt"]))
            if attrs["jobmode"]?
                scope.job_mode = attrs["jobmode"]
            if attrs["selectedjob"]?
                scope.selected_job = attrs["selectedjob"]
            scope.struct.draw_on_init = attrs["draw"] ? false
        controller: "icswGraphOverviewCtrl"
    }
]).service("icswRRDGraphTree",
[
    "icswReactTreeConfig",
(
    icswReactTreeConfig
) ->
    {span} = React.DOM
    class icswRRDGraphTree extends icswReactTreeConfig
        constructor: (@scope, args) ->
            super(args)

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
                @_jq_toggle_checkbox_node(entry)
            @scope.$digest()

        selection_changed: () =>
            @scope.selection_changed()
            @scope.$digest()

        get_pre_view_element: (entry) ->
            if entry._node_type == "e" and entry.num_sensors
                return span(
                    {
                        key: "arrow"
                        className: "fa fa-arrows-v"
                    }
                )
            else
                return null
            if entry.num_sensors
                span.addClass("fa fa-arrows-v")

]).directive("icswRrdGraphList",
[
    "$templateCache", "$compile",
(
    $templateCache, $compile
) ->
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
                    # console.log "id=", scope.$id
                    element.append($compile($templateCache.get("icsw.rrd.graph.list.header"))(scope))
            )
            scope.get_graph_keys = () ->
                return (key for key of scope.graphMatrix)
    }
]).directive("icswRrdGraphListGraph",
[
    "$templateCache", "$compile", "icswRRDSensorDialogService",
(
    $templateCache, $compile, icswRRDSensorDialogService
) ->
    return {
        restrict: "E"
        replace: true
        scope: {
            graph: "="
        }
        # template: $templateCache.get("icsw.rrd.graph.list.graph")
        link: (scope, element, attr) ->
            # console.log "it=", scope.$id
            graph_error = () ->
                element.children().remove()
                element.append(angular.element("<h4 class='text-danger'>Error loading graph (#{_graph.num})</h4>"))
            scope.modify_sensors = () ->
                icswRRDSensorDialogService(scope, _graph).then(
                    () ->
                        # console.log "done"
                )
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
                    element.after(crop_span)
                    crop_span.find("input").on("click", () ->
                        scope.$emit("cropSet", _graph)
                    )
                    crop_span.hide()
                    img_div = angular.element("<div/>")
                    crop_span.after(img_div)
                    myImg = angular.element("<img/>")
                    img_div.append(myImg)
                    myImg.attr("src", _graph.src)
                    $(myImg).Jcrop({
                        trackDocument: true
                        onSelect: (sel) ->
                            if not _graph.cropped
                                crop_span.show()
                            _graph.set_crop(sel)
                            crop_span.find("span").text(
                                "cropped timerange: " +
                                _graph.get_tv(_graph.cts_start_mom) +
                                " to " +
                                _graph.get_tv(_graph.cts_end_mom)
                            )
                            scope.$digest()
                        onRelease: () ->
                            if _graph.cropped
                                crop_span.hide()
                            _graph.clear_crop()
                            scope.$digest()
                    }, () ->
                        # not needed ?
                        bounds = this.getBounds()
                    )
                    myImg.bind("error", (event) ->
                        _graph.error = true
                        graph_error()
                        scope.$digest()
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
                            img_div.show()
                        else
                            img_div.hide()
                )
            element.on("$destroy", () ->
                # console.log "destr"
            )
    }
    # console.log "S", $scope.graph
]).directive("icswRrdGraphThreshold",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "AE"
        template: $templateCache.get("icsw.rrd.graph.threshold.overview")
        link: (scope, el, attr) ->
            scope.toggle_enabled = (type) ->
                scope.threshold["#{type}_enabled"] = !scope.threshold["#{type}_enabled"]
                scope.threshold.save()

            scope.toggle_mail = (type) ->
                scope.threshold["#{type}_mail"] = !scope.threshold["#{type}_mail"]
                scope.threshold.save()

            scope.get_enabled = (type) ->
                return if scope.threshold["#{type}_enabled"] then "enabled" else "disabled"

            scope.get_sensor_action_name = (type) ->
                _act = scope.threshold["#{type}_sensor_action"]
                if _act?
                    return scope.sensor.graph.user_settings.base.sensor_action_lut[_act].name
                else
                    return "---"

            scope.resolve_user = () ->
                if scope.threshold.create_user
                    return scope.sensor.graph.user_group_tree.user_lut[scope.threshold.create_user].login
                else
                    return "---"

            scope.get_email = (type) ->
                return if scope.threshold["#{type}_mail"] then "send email" else "no email"

            scope.get_device_selection_info = () ->
                if scope.threshold.device_selection
                    return (entry.info for entry in scope.sensor.graph.selection_list when entry.idx == scope.threshold.device_selection)[0]
                else
                    return "---"

    }
]).service("icswRRDSensorDialogService",
[
    "$q", "$compile", "$templateCache", "Restangular", "ICSW_URLS",
    "icswToolsSimpleModalService", "$timeout", "icswUserService", "icswSimpleAjaxCall",
    "icswComplexModalService", "icswRRDThresholdDialogService",
(
    $q, $compile, $templateCache, Restangular, ICSW_URLS,
    icswToolsSimpleModalService, $timeout, icswUserService, icswSimpleAjaxCall,
    icswComplexModalService, icswRRDThresholdDialogService,
) ->
    return (scope, graph) ->
        sub_scope = scope.$new()

        sub_scope.delete_threshold = (sensor, th) ->
            icswToolsSimpleModalService("Really delete Threshold '#{th.name}' ?").then(
                (res) ->
                    sensor.graph.user_settings.remove_threshold_entry(sensor, th).then(
                        (done) ->
                    )
            )

        sub_scope.trigger_threshold = (sensor, th, lu_switch) ->
            act_str = "trigger"
            info_str = "action will be triggered"
            icswToolsSimpleModalService("Really #{act_str} Threshold (#{info_str}) ?").then(
                (res) ->
                    icswSimpleAjaxCall(
                        {
                            url: ICSW_URLS.RRD_TRIGGER_SENSOR_THRESHOLD
                            data:
                                pk: th.idx
                                # lower or upper
                                type: lu_switch
                        }
                    ).then(
                        (ok) ->
                        (error) ->
                    )
            )

        sub_scope.modify_threshold = (sensor, threshold) ->
            icswRRDThresholdDialogService(false, sub_scope, sensor, threshold)

        sub_scope.create_new_threshold = (sensor) ->
            threshold = sensor.graph.user_settings.get_new_threshold(sensor)
            icswRRDThresholdDialogService(true, sub_scope, sensor, threshold)

        sub_scope.graph = graph

        def = $q.defer()
        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.rrd.graph.sensor"))(sub_scope)
                title: "Modify / Create Sensors (" + graph.get_sensor_info() + ", " + graph.get_threshold_info() + ")"
                css_class: "modal-wide"
                ok_label: "Close"
                ok_callback: (modal) ->
                    d = $q.defer()
                    d.resolve("done")
                    return d.promise
            }
        ).then(
            (fin) ->
                sub_scope.$destroy()
                def.resolve("closed")
        )
        return def.promise
]).service("icswRRDThresholdDialogService",
[
    "$q", "$compile", "$templateCache", "Restangular", "ICSW_URLS",
    "icswToolsSimpleModalService", "$timeout", "icswUserService", "icswSimpleAjaxCall",
    "icswComplexModalService",
(
    $q, $compile, $templateCache, Restangular, ICSW_URLS,
    icswToolsSimpleModalService, $timeout, icswUserService, icswSimpleAjaxCall,
    icswComplexModalService,
) ->
    return (create, scope, sensor, threshold) ->
        user_settings = sensor.graph.user_settings
        th_scope = scope.$new()
        th_scope.sensor = sensor
        th_scope.threshold = threshold
        console.log "args:", create, sensor, threshold
        if create
            title = "Create new Threshold"
        else
            title = "Modify Threshold"
        th_scope.check_upper_lower = () ->
            if th_scope.change_cu_to
                $timeout.cancel(th_scope.change_cu_to)
            th_scope.change_cu_to = $timeout(
                () ->
                    if th_scope.threshold.lower_value > th_scope.threshold.upper_value
                        _val = th_scope.threshold.lower_value
                        th_scope.threshold.lower_value = th_scope.threshold.upper_value
                        th_scope.threshold.upper_value = _val
                2000
            )
        th_scope.lookup_action = (idx) ->
            console.log "la", idx
        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.rrd.graph.threshold.form"))(th_scope)
                title: title
                ok_label: if create then "Create" else "Modify"
                ok_callback: (modal) ->
                    d = $q.defer()
                    if create
                        user_settings.create_threshold_entry(sensor, th_scope.threshold).then(
                            (created) ->
                                d.resolve("done")
                            (error) ->
                                d.reject("no")
                        )
                    return d.promise
                cancel_callback: (modal) ->
                    d = $q.defer()
                    d.resolve("done")
                    return d.promise
            }
        ).then(
            (fin) ->
                th_scope.$destroy()
        )
]).factory(
    "icswRRDVectorInfoFactory"
    [() ->
        return React.createClass(
            {
                propTypes: {
                    num_struct : React.PropTypes.number.isRequired
                    num_devices : React.PropTypes.number.isRequired
                    num_mve : React.PropTypes.number.isRequired
                    num_mve_sel : React.PropTypes.number.isRequired
                }
                render: () ->
                    {div, span} = React.DOM
                    div(
                        {key: "k0", className: "form-group"},
                        [
                            "Vector info: "
                            span(
                                {key: "se", className: "label label-primary", title: "structural entries"},
                                [
                                    @props.num_struct
                                    if @props.num_devices
                                        span(
                                            {key: "nd", title: "number of devices"}
                                            " / " + @props.num_devices
                                        )
                                ]
                            )
                            " / "
                            span(
                                {key: "de", className: "label label-primary", title: "data entries"},
                                [
                                    @props.num_mve
                                    if @props.num_mve_sel
                                        span(
                                            {key: "des", title: "selected entries"}
                                            " / " + @props.num_mve_sel
                                        )
                                ]
                            )
                        ]
                    )
            }
        )
    ]
).directive("icswRrdVectorInfo",
[
    "icswRRDVectorInfoFactory",
(
    icswRRDVectorInfoFactory
) ->
    return {
        restrict: "EA"
        replace: true
        scope:
            vectorInfo: "="
        link: (scope, el, attrs) ->
            scope.$watch(
                "vectorInfo",
                (new_val) ->
                    ReactDOM.render(
                        React.createElement(icswRRDVectorInfoFactory, new_val)
                        el[0]
                    )
                true
            )
    }
])

