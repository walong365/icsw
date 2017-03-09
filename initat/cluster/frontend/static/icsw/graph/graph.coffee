# Copyright (C) 2012-2017 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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
DT_FORM_DISPLAY = "dd, D. MMM YYYY HH:mm:ss"

angular.module(
    "icsw.graph",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters",
        "restangular", "icsw.graphsetting",
    ]
).config(["icswRouteExtensionProvider", (icswRouteExtensionProvider) ->
    icswRouteExtensionProvider.add_route("main.graph")
]).service("icswGraphTools",
[
    "$q", "icswDeviceTreeHelperService", "icswReactTreeConfig",
    "icswDeviceTreeService", "icswTools", "icswSimpleAjaxCall", "ICSW_URLS",
    "toaster", "$timeout", "icswGraphBasicSetting", "icswTimeFrameService",
    "icswGraphUserSettingService", "icswParseXMLResponseService",
    "icswUserGroupRoleTreeService", "icswSavedSelectionService",
    "icswWebSocketService", "ICSW_ENUMS",
(
    $q, icswDeviceTreeHelperService, icswReactTreeConfig,
    icswDeviceTreeService, icswTools, icswSimpleAjaxCall, ICSW_URLS,
    toaster, $timeout, icswGraphBasicSetting, icswTimeFrameService,
    icswGraphUserSettingService, icswParseXMLResponseService,
    icswUserGroupRoleTreeService, icswSavedSelectionService,
    icswWebSocketService, ICSW_ENUMS,

) ->
    {span} = React.DOM
    _get_empty_vector_data = () ->
        return {
            num_struct: 0
            num_mve: 0
            num_devices: 0
            num_mve_sel: 0
            num_sensors: 0
        }

    _get_node_keys = (node) ->
        # mapping for graph.py
        return {
            "struct_key": node._key_pair[0]
            "value_key": node._key_pair[1]
            "build_info": node.build_info
        }

    _expand_info = (info, g_key) ->
        _num = 0
        for _var in g_key.split(".")
            _num++
            info = info.replace("$#{_num}", _var)
        return info

    _child_sort = (list, new_node) ->
        _idx = 0
        for _entry in list
            if _entry._display_name > new_node._display_name
                break
            _idx++
        return _idx

    class icswSensor
        constructor: (@graph, @json, sth_dict) ->
            @mvs_id = parseInt(@json.db_key.split(".")[0])
            @mvv_id = parseInt(@json.db_key.split(".")[1])
            @device_id = @json.device
            @mv_key = @json.mv_key
            @cfs = {}
            _value = 0.0
            _num_value = 0
            if not @json.nan
                for _cf in @json.cfs
                    @cfs[_cf.cf] = _cf.value
                    if _cf.cf != "TOTAL"
                        _value += parseFloat(_cf.value)
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

    class icswDisplayGraph
        constructor: (@num, @xml, @graph_result) ->
            #@user_settings, @user_group_role_tree, @selection_list, @device_tree) ->
            # state, has the values
            # i ... waiting for data
            # r ... result set
            # e ... something went wrong
            @state = "i"
            @name = @xml.attr("name")
            @loaded = false
            @cropped = false
            @removed_keys = []
            @draw_iter = 0
            @change_notifier = $q.defer()
            if false
                @value_min = parseFloat(@xml.attr("value_min"))
                @value_max = parseFloat(@xml.attr("value_max"))
                # complete graphic
                @img_width = parseInt(@xml.attr("image_width"))
                @img_height = parseInt(@xml.attr("image_height"))
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

            # build list of values for which we can createa sensor (== full db_key needed)
            # number of (als possible) sensors
            @num_sensors = 0
            @sensors = []

        update_source: (xml) =>
            # for graph reload
            @xml = xml
            @name = @xml.attr("name")
            @cropped = false
            @removed_keys = []
            @num_sensor = 0
            @sensors = []
            @change_notifier.notify("update_source")

        close: () =>
            @change_notifier.reject("stop")

        feed_result: (json) =>
            @state = "r"
            @json = json
            @draw_iter++
            @ts_start_mom = moment.unix(@json.graph_start)
            @ts_end_mom = moment.unix(@json.graph_end)
            @device_names = (entry.name for entry in @json.devices)
            @removed_keys.length = 0
            full_draw_key = (s_key, v_key) ->
                _key = s_key
                if v_key
                    _key = "#{_key}.#{v_key}"
                return _key

            for entry in @json.removed.removed_keys
                @removed_keys.push(full_draw_key(entry.struct_key, entry.value_key))

            @sensors.length = 0
            if @json.values?
                for value in @json.values
                    if value.db_key.match(/\d+\.\d+/)
                        # only a valid sensor when the db-idx has a device (no compound displays)
                        @num_sensors++
                        @sensors.push(new icswSensor(@, value, @graph_result.tree.user_settings.threshold_lut_by_mvv_id))
            @sensors = _.sortBy(@sensors, (sensor) -> return sensor.mv_key)
            @num_sensors = @sensors.length
            @change_notifier.notify("feed_result")

        get_sensor_info: () ->
            return "#{@num_sensors} sensor sources"

        get_threshold_info: () ->
            _num_th = 0
            for _sensor in @sensors
                _num_th += _sensor.thresholds.length
            return "#{_num_th} Thresholds"

        get_tv: (val) ->
            if val
                return val.format(DT_FORM_DISPLAY)
            else
                return "???"

        get_time_range_str: () =>
            if @ts_start_mom? and @ts_start_mom.isValid()
                return "#{@get_tv(@ts_start_mom)} to #{@get_tv(@ts_end_mom)}"
            else
                return null

        set_crop: (sel) ->
            @cropped = true
            ts_range = @json.graph_end - @json.graph_start
            new_start = @json.graph_start + parseInt((sel.x - @json.graph_left) * ts_range / @json.graph_width)
            new_end = @json.graph_start + parseInt((sel.x + sel.width - @json.graph_left) * ts_range / @json.graph_width)
            @crop_width = parseInt((sel.width) * ts_range / @json.graph_width)
            @cts_start_mom = moment.unix(new_start)
            @cts_end_mom = moment.unix(new_end)

        clear_crop: () ->
            @cropped = false

        crop: (event) =>
            event.stopPropagation()
            if @crop_width > 600
                @graph_result.tree.timeframe.set_from_to_mom(@cts_start_mom, @cts_end_mom)
                @graph_result.tree.draw_graphs(false, @graph_result)
            else
                _mins = parseInt(@crop_width / 60)
                toaster.pop("warning", "", "selected timeframe is too narrow (#{_mins} < 10 min)")

    class icswGraphResult
        # holds all resulting graphs
        constructor: (@tree) ->
            @list = []
            @clear()
            @generation = 0
            @stream_id = undefined
            @time_range_str = ""
            @tree.link_result(@)
            @auto_select_re = null

        set_auto_select_re: (auto_re) =>
            @auto_select_re = new RegExp(auto_re)

        filter_keys: (in_list) =>
            if @auto_select_re
                new_list = []
                for entry in in_list
                    if entry.match(@auto_select_re)
                        new_list.push(entry)
                return new_list
            return in_list

        close_ws: () =>
            # close websocket
            if @stream_id? and @stream_id
                icswWebSocketService.remove_stream(@stream_id).then(
                    (done) =>
                        @stream_id = undefined
                )

        close: () =>
            @close_ws()
            @clear()

        clear: () =>
            (entry.close() for entry in @list)
            @list.length = 0
            @name_lut = {}
            @num = 0
            # numer of outstanding requests
            @num_pending = 0
            # graph matrix
            @matrix = {}
            # full key lut
            @fk_lut = {}
            # time range string
            @time_range_str = ""

        clear_for_redraw: () =>
            # redraw all graphs
            @name_lut = {}
            # (entry.close() for entry in @list)
            @num = 0
            # numer of outstanding requests
            @num_pending = 0
            @time_range_str = ""

        start_feed: () =>
            # set feed flag, while we are feeding
            # the results from the graphing may be arriving
            # faster than we are to process the draw request
            @__feeding = true
            @__cache = []
            # start websocket
            @close_ws()
            _q = $q.defer()
            icswWebSocketService.add_stream(
                ICSW_ENUMS.WSStreamEnum.rrd_graph
                @feed_result
            ).then(
                (stream_id) =>
                    @stream_id = stream_id
                    console.log "gi", @stream_id
                    _q.resolve("go")
            )
            return _q.promise

        end_feed: () =>
            @__feeding = false
            (@feed_result(entry) for entry in @__cache)
            @__cache.length = 0

        feed_graph: (graph, add_new) =>
            @num_pending++
            @generation++
            graph_key = graph.attr("fmt_graph_key")
            dev_key = graph.attr("fmt_device_key")
            _full_key = "#{graph_key}::#{dev_key}"
            if add_new
                @num++
                if graph_key not of @matrix
                    @matrix[graph_key] = {}
                cur_graph = new icswDisplayGraph(
                    @num
                    graph
                    @
                )
                @fk_lut[_full_key] = cur_graph
                @name_lut[cur_graph.name] = cur_graph
                @matrix[graph_key][dev_key] = cur_graph
                @list.push(cur_graph)
            else
                cur_graph = @fk_lut[_full_key]
                if cur_graph?
                    cur_graph.update_source(graph)
                    @name_lut[cur_graph.name] = cur_graph
                else
                    console.error "Unknown graph with full_key '#{_full_key}"

        feed_result: (json) =>
            if @__feeding
                @__cache.push(json)
            else
                for graph in json.list
                    if graph.name of @name_lut
                        @name_lut[graph.name].feed_result(graph)
                        if not @time_range_str
                            @time_range_str = @name_lut[graph.name].get_time_range_str()
                            # successfull set ?
                            if @time_range_str
                                $timeout(
                                    () =>
                                    0
                                )
                        @num_pending--
                        if not @num_pending
                            @close_ws()
                    else
                        # in case of more than one GraphResult awaiting data
                        console.error "unknown graph with name '#{graph.name}'"
                        for _name, _value of @name_lut
                            console.warn " - #{_name}"

    class icswGraphReactTree extends icswReactTreeConfig
        constructor: (@_refresh_call, @_selection_changed, args) ->
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

        handle_click: ($event, entry) =>
            if entry._node_type == "s"
                entry.set_expand(!entry.expand)
            else if entry._node_type == "e"
                # trigger checkbox
                @toggle_checkbox_node(entry).then(
                    (ok) =>
                        # force redraw
                        @new_generation()
                )

        selection_changed: () =>
            # call outside
            @_selection_changed()
            @_refresh_call()

        get_pre_view_element: (entry) ->
            _rv = []
            if entry._node_type == "e" and entry.num_sensors
                _rv.push(
                    span(
                        {
                            key: "arrow"
                            className: "fa fa-arrows-v"
                        }
                    )
                )
                if entry.build_info.length > 1
                    if entry.entries_with_sensors != entry.build_info.length
                        _str = "#{entry.entries_with_sensors} / #{entry.build_info.length}"
                    else
                        _str = entry.build_info.length
                    _rv.push(
                        span(
                            {
                                key: "batch"
                                className: "badge"
                            }
                            _str
                        )
                    )
            return _rv

    class icswGraphTree
        # holds all data for graphing
        constructor: () ->
            @id = icswTools.get_unique_id("GraphTree")
            @base_setting = new icswGraphBasicSetting()
            @custom_setting = undefined
            @timeframe = new icswTimeFrameService()
            # created graphs, could be more than one
            @graph_results = []
            # currently drawing
            @num_drawing = 0
            # selected entries
            @cur_selected = []
            @tree = new icswGraphReactTree(
                @refresh
                @selection_changed
                {
                    show_selection_buttons: true
                    expand_on_selection: true
                    show_select: true
                    show_descendants: true
                    show_total_descendants: false
                    extra_args: ["build_info"]
                }
            )
            # vector is valid
            @_set_error("waiting for devices")
            @devices = []
            @vector_data = _get_empty_vector_data()

        link_result: (result) =>
            @graph_results.push(result)

        _set_error: (info) =>
            # vector (==treeView) valid
            @vector_valid = false
            @error_string = info

        _set_drawing: () =>
            # vector (==treeView) valid
            if @num_drawing
                @error_string = "Drawing Graphs (#{@num_drawing})"
            else
                @error_string = ""

        set_custom_setting: (setting) =>
            @custom_setting = setting

        set_base_setting: (setting) =>
            @base_setting = setting

        close: () =>
            # tear down all substructres
            (_result.close() for _result in @graph_results)
            # console.log "close GraphTree #{@id}"

        refresh: () =>
            $timeout(
                () ->
                0
            )

        set_devices: (dev_list) =>
            _defer = $q.defer()
            # clear graphing list
            # sets the new device list and loads the tree
            @devices.length = 0
            @_set_error("Loading Structures")
            $q.all(
                [
                    icswDeviceTreeService.load(@id)
                    # needed for graphs
                    icswGraphUserSettingService.load(@id)
                    icswUserGroupRoleTreeService.load(@id)
                    icswSavedSelectionService.load_selections(@id)
                ]
            ).then(
                (data) =>
                    @device_tree = data[0]
                    # user settings (GraphUserSetting)
                    @user_settings = data[1]
                    # user / group / role tree
                    @user_group_role_tree = data[2]
                    # saved device selections
                    @device_selection_list = data[3]
                    for entry in dev_list
                        @devices.push(entry)
                    hs = icswDeviceTreeHelperService.create(@device_tree, @devices)
                    @_set_error("Adding Sensor Info")
                    @device_tree.enrich_devices(hs, ["sensor_threshold_info"]).then(
                        (done) =>
                            if @devices.length
                                @_set_error("Loading VectorTree")
                                @vector_data = _get_empty_vector_data()
                                icswSimpleAjaxCall(
                                    url: ICSW_URLS.RRD_DEVICE_RRDS
                                    data: {
                                        pks: (dev.idx for dev in @devices)
                                    }
                                    dataType: "json"
                                ).then(
                                    (json) =>
                                        @_feed_rrd_json(json)
                                        _defer.resolve("done")
                                    (error) =>
                                        @_set_error("Error loading tree")
                                        _defer.reject("error loading tree")
                                )
                            else
                                @_set_error("No Devices selected")
                                _defer.reject("no devices")
                    )
            )
            return _defer.promise

        _feed_rrd_json: (json) =>
            if "error" of json
                toaster.pop("error", "", json["error"])
                @_set_error("Error loading Tree")
            else
                @base_setting.set_auto_select_re()
                # to machine vector
                root_node = @_init_machine_vector()
                for dev in json
                    if dev.struct? and dev.struct.length
                        @_add_machine_vector(root_node, dev.pk, dev.struct)
                        #if dev._nodes.length > 1
                        #    # compound
                        #    $scope.add_machine_vector(root_node, dev.pk, dev._nodes[1])
                        @vector_data.num_devices++
                @tree.recalc()
                @vector_valid = if @vector_data.num_struct then true else false
                if @vector_valid
                    @error_string = ""
                    if @base_setting.auto_select_re or @cur_selected.length
                        # recalc tree when an autoselect_re is present
                        @tree.show_selected(false)
                        @selection_changed()
                        if @base_setting.draw_on_init and @vector_data.num_mve_sel and @graph_results.length
                            @draw_graphs(true, @graph_results[0])
                else
                    @_set_error("No vector found")

        _init_machine_vector: () =>
            @_lut = {}
            @tree.clear_root_nodes()
            root_node = @tree.create_node(
                {
                    folder: true
                    expand: true
                    _node_type: "h"
                    show_select: true
                }
            )
            root_node.build_info = []
            @tree.add_root_node(root_node)
            return root_node

        _add_machine_vector: (root_node, dev_pk, mv) =>
            @_mv_dev_pk = dev_pk
            lut = @_lut
            for entry in mv
                _struct = @_add_structural_entry(entry, lut, root_node)
                for _sub in entry.mvvs
                    @_add_value_entry(_sub, lut, _struct, entry)

        _add_structural_entry: (entry, lut, parent) =>
            parts = entry.key.split(".")
            pn = ""
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
                    if @_mv_dev_pk not in cur_node._dev_pks
                        cur_node._dev_pks.push(@_mv_dev_pk)
                else
                    # override name if display_name is set and this is the structural entry at the bottom
                    # structural
                    cur_node = @tree.create_node(
                        {
                            folder: true,
                            expand: false
                            _display_name: if (entry.ti and _last) then entry.ti else _part
                            _mult: 1
                            _dev_pks: [@_mv_dev_pk]
                            _node_type: "s"
                            show_select: false
                            build_info: []
                            # marker: this is not an mve entry
                            _is_mve: false
                        }
                    )
                    @vector_data.num_struct++
                    # create lut entry
                    lut[pn] = cur_node
                    parent.add_child(cur_node, _child_sort)
                parent = cur_node
            return parent

        _add_value_entry: (entry, lut, parent, top) =>
            _vd = @vector_data
            # debg ?
            # _vd.a = "ddd"
            # top is the parent node from the value entry (== mvstructentry)
            if entry.key
                g_key = "#{top.key}.#{entry.key}"
            else
                g_key = top.key
            if @cur_selected.length
                _sel = g_key in @cur_selected
            else if @base_setting.auto_select_re
                _sel = @base_setting.auto_select_re.test(g_key)
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
                    # init number of sensors and mve with sensors defined
                    cur_node.num_sensors = 0
                    cur_node.entries_with_sensors = 0
                    # console.log "trans", cur_node.build_info, cur_node.num_sensors
            else
                cur_node = @tree.create_node(
                    {
                        expand : false
                        selected: _sel
                        _dev_pks: []
                        _is_mve: true
                    }
                )
                cur_node.build_info = []
                # init number of sensors
                # console.log "*", cur_node.num_sensors
                cur_node.num_sensors = 0
                cur_node.entries_with_sensors = 0
                _vd.num_mve++
                lut[g_key] = cur_node
                parent.add_child(cur_node, _child_sort)
            cur_node._key_pair = [top.key, entry.key]
            cur_node._display_name = _expand_info(entry.info, g_key)
            if @_mv_dev_pk not in cur_node._dev_pks
                cur_node._dev_pks.push(@_mv_dev_pk)
            cur_node._node_type = "e"
            cur_node.build_info.push(entry.build_info)
            cur_node.num_sensors += entry.num_sensors
            if entry.num_sensors
                cur_node.entries_with_sensors++
            @vector_data.num_sensors += entry.num_sensors
            cur_node.folder = false
            cur_node.show_select = true
            cur_node._g_key = g_key
            cur_node.node = entry
            cur_node.selected = _sel

        selection_changed: () =>
            @cur_selected = @tree.get_selected(
                (entry) ->
                    if entry._node_type == "e" and entry.selected
                        return [entry._g_key]
                    else
                        return []
            )
            @vector_data.num_mve_sel = @cur_selected.length

        set_search_filter: () =>
            cur_re = @base_setting.get_search_re()
            # console.log "*", cur_re
            @tree.toggle_tree_state(undefined, -1, false)
            @tree.iter(
                (entry, cur_re) ->
                    if entry._node_type in ["e"]
                        entry.set_selected(if (entry._display_name.match(cur_re) or entry._g_key.match(cur_re)) then true else false)
                cur_re
            )
            @tree.show_selected(false)
            @selection_changed()

        clear_selection: () =>
            @base_setting.clear_search_string()
            @set_search_filter()

        select_with_sensor: () =>
            @tree.toggle_tree_state(undefined, -1, false)
            @tree.iter(
                (entry) ->
                    if entry._node_type in ["e"]
                        entry.set_selected(if entry.num_sensors then true else false)
            )
            @tree.show_selected(false)
            @selection_changed()

        # graph calls
        draw_graphs: (clear_current, graph_result) =>
            defer = $q.defer()
            @num_drawing++
            @_set_drawing()
            if @custom_setting?
                _setting = @custom_setting
            else
                _setting = @user_settings.get_active()
            if clear_current
                graph_result.clear()
            else
                graph_result.clear_for_redraw()
            # open websocket
            graph_result.start_feed().then(
                (done) =>
                    console.log "start"
                    # ws init, start drawing
                    # get keys
                    _keys = graph_result.filter_keys((_key for _key in @cur_selected))
                    $q.allSettled(
                        [
                            icswSimpleAjaxCall(
                                url: ICSW_URLS.RRD_GRAPH_RRDS
                                data: {
                                    keys: angular.toJson((_get_node_keys(@_lut[key]) for key in _keys))
                                    pks: angular.toJson((dev.idx for dev in @devices))
                                    start_time: moment(@timeframe.from_date_mom).format(DT_FORM)
                                    end_time: moment(@timeframe.to_date_mom).format(DT_FORM)
                                    # job_mode: $scope.struct.job_mode.short
                                    # selected_job: $scope.selected_job
                                    ordering: @base_setting.ordering
                                    graph_setting: angular.toJson(@user_settings.resolve(_setting))
                                }
                                parse_response: false
                            )
                        ]
                    ).then(
                        (result) =>
                            $timeout(
                                () =>
                                    xml = result[0].value
                                    # reorder sensor threshold entries

                                    @num_drawing--
                                    @_set_drawing()
                                    if icswParseXMLResponseService(xml, 40, false, true)
                                        # num_graph = 0
                                        for graph in $(xml).find("graph_list > graph")
                                            graph = $(graph)
                                            graph_result.feed_graph(graph, clear_current)
                                        graph_result.end_feed()
                                    else
                                        graph_result.clear()
                                        graph_result.close_ws()
                                    defer.resolve("drawn")
                                0
                            )
                    )
                (error) =>
                    # ws not established
                    graph_result.clear()
                    graph_result.close_ws()
                    defer.reject("nothing drawn")
            )
            return defer.promise

    return {
        create_tree: () =>
            return new icswGraphTree()
        create_result: (tree) =>
            return new icswGraphResult(tree)
    }
]).controller("icswGraphOverviewCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular",
    "$q", "$uibModal", "$timeout", "ICSW_URLS", "icswSimpleAjaxCall",
    "icswParseXMLResponseService", "toaster", "icswUserService", "icswGraphTools",
(
    $scope, $compile, $filter, $templateCache, Restangular,
    $q, $uibModal, $timeout, ICSW_URLS, icswSimpleAjaxCall,
    icswParseXMLResponseService, toaster, icswUserService, icswGraphTools,
) ->
        # none, all or selected
        $scope.job_modes = [
            {short: "none", long: "No jobs"}
            {short: "all", long: "All Jobs"}
            {short: "selected", long: "Only selected"}
        ]
        $scope.job_mode = $scope.job_modes[0]

        # helper functions
        $scope.selected_job = 0
        $scope.struct = {
            # job mode
            job_mode: $scope.job_modes[0]
        }

        # graph tree
        $scope.graph_tree = icswGraphTools.create_tree()
        $scope.graph_result = icswGraphTools.create_result($scope.graph_tree)

        $scope.new_devsel = (dev_list) ->
            $scope.graph_tree.set_devices(dev_list)

        # $scope.set_job_mode = (new_jm) ->
        #     $scope.job_mode = new_jm

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

        $scope.$on("$destroy", () ->
            $scope.graph_tree.close()
        )
]).directive("icswGraphNormal",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.graph.overview")
        controller: "icswGraphOverviewCtrl"
    }
]).directive("icswGraphRemote",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.graph.overview")
        controller: "icswGraphOverviewCtrl"
        scope: {
            icsw_graph_setting: "=icswGraphSetting"
            icsw_base_setting: "=icswBaseSetting"
            devices: "=icswDeviceList"
            to_date: "=icswToDate"
            from_date: "=icswFromDate"
        }
        link: (scope, el, attrs) ->
            #if attrs["jobmode"]?
            #    scope.job_mode = attrs["jobmode"]
            #if attrs["selectedjob"]?
            #    scope.selected_job = attrs["selectedjob"]
            if scope.icsw_graph_setting?
                scope.graph_tree.set_custom_setting(scope.icsw_graph_setting)
            if scope.icsw_base_setting?
                scope.graph_tree.set_base_setting(scope.icsw_base_setting)
            if scope.devices?
                scope.new_devsel(scope.devices)
            if scope.from_date?
                scope.graph_tree.timeframe.set_from_to_mom(scope.from_date, scope.to_date)
    }
]).directive("icswGraphResult",
[
    "$templateCache", "$compile",
(
    $templateCache, $compile
) ->
    return {
        restrict: "E"
        replace: true
        scope: {
            graph_result: "=icswGraphResult"
        }
        template: $templateCache.get("icsw.graph.list.header")
        link: (scope, element, attr) ->
            scope.$$graph_keys = []
            scope.$watch(
                "graph_result.generation"
                (new_val) ->
                    if scope.graph_result.list.length
                        scope.$$graph_keys.length = 0
                        for entry in _.keys(scope.graph_result.matrix)
                            scope.$$graph_keys.push(entry)
            )
    }
]).service("icswGraphDisplayReact",
[
    "$q", "icswSensorDialogService", "ICSW_SIGNALS", "$window", "ICSW_URLS",
(
    $q, icswSensorDialogService, ICSW_SIGNALS, $window, ICSW_URLS,
) ->
    {div, text, h4, span, button, img, br} = React.DOM
    return React.createClass(
        propTypes: {
            # graph object
            graph: React.PropTypes.object
        }
        getInitialState: () ->
            return {
                open: true
                loadError: false
                # cropped: false
                draw_counter: 0
            }

        force_redraw: () ->
            @setState({draw_counter: @state.draw_counter++})

        render: () ->
            _graph = @props.graph
            if _graph.state == "e"
                return span(
                    {
                        key: "top"
                        className: "label label-danger"
                    }
                    "Error loading Graph (#{_graph.num})"
                )
            else if _graph.state == "i"
                return span(
                    {
                        key: "top"
                        className: "label label-warning"
                    }
                    "Awaiting data"
                )
            else
                _head1_list = [
                    span(
                        {
                            key: "info"
                            className: "label label-default"
                            title: _graph.name
                            onClick: (event) =>
                                _graph.clear_crop()
                                @setState({open: !@state.open, draw_counter: @state.draw_counter + 1})
                        }
                        [
                            span(
                                {
                                    key: "oc.span"
                                    className:  if @state.open then "glyphicon glyphicon-chevron-down" else "glyphicon glyphicon-chevron-right"
                                }
                            )
                            " graph ##{_graph.num}"
                        ]
                    )
                ]
                if _graph.json.href
                    _head1_list.push(
                        button(
                            {
                                key: "download"
                                type: "button"
                                className: "btn btn-xs btn-success"
                                onClick: (event) =>
                                    $window.location = ICSW_URLS.RRD_DOWNLOAD_RRD.slice(0, -1) + angular.toJson({path: _graph.json.abssrc})
                                    # event.preventDefault()
                            }
                            [
                                span(
                                    {
                                        key: "span"
                                        className:  "glyphicon glyphicon-download-alt"
                                    }
                                )
                                " download"
                            ]
                        )
                    )
                if _graph.json.href and _graph.num_sensors
                    _head1_list.push(
                        " "
                        button(
                            {
                                key: "sensor.button"
                                type: "button"
                                className: "btn btn-xs btn-primary"
                                onClick: (event) =>
                                    icswSensorDialogService(_graph).then(
                                        () ->
                                    )
                            }
                            "Sensors"
                        )
                    )
                if _graph.removed_keys.length
                    _rem_keys = _graph.removed_keys.join(", ")
                    _head1_list.push(
                        span(
                            {
                                key: "removed.keys"
                            }
                            " #{_graph.removed_keys.length} keys not shown (zero data) "
                            span(
                                {
                                    key: "removed.info"
                                    className: "glyphicon glyphicon-info-sign"
                                    title: _rem_keys
                                }
                            )
                        )
                    )
                _crop_list = []
                _img = null
                if _graph.cropped
                    _crop_list = [
                        span(
                            {
                                key: "crop.ts"
                            }
                            "cropped timerange: "
                            _graph.get_tv(_graph.cts_start_mom)
                            " to "
                            _graph.get_tv(_graph.cts_end_mom)
                        )
                        " "
                        button(
                            {
                                key: "crop.apply"
                                className: "btn btn-xs btn-success"
                                onClick: (event) =>
                                    @props.graph.crop(event)
                            }
                            "Apply"
                        )
                        " "
                        button(
                            {
                                key: "crop.clear"
                                className: "btn btn-xs btn-warning"
                                onClick: (event) =>
                                    if @image?
                                        $(@image).cropper("clear")
                                        _graph.cropped = false
                                        @force_redraw()
                            }
                            "Clear"
                        )
                    ]
                if _graph.json.href
                    if @state.open
                        _graph_list = [
                            div(
                                {
                                    key: "graph.div.#{_graph.draw_iter}"
                                }
                                img(
                                    {
                                        key: "graph.img"
                                        src: _graph.json.href
                                        onError: (event) =>
                                            _graph.state = "e"
                                            @setState({load_error: true})
                                        onLoad: (event) =>
                                            if not _graph.graph_result.tree.base_setting.allow_crop
                                                return
                                            _img = event.currentTarget
                                            @image = _img
                                            $(_img).cropper(
                                                {
                                                    # set MinContainer to fixed values in case of hidden load
                                                    minContainerWidth: _graph.json.image_width
                                                    minContainerHeight: _graph.json.image_height
                                                    autoCrop: false
                                                    movable: false
                                                    rotatable: false
                                                    zoomable: false
                                                    guides: true
                                                    cropend: (event) =>
                                                        _graph.set_crop($(_img).cropper("getData"))
                                                        @force_redraw()
                                                }
                                            )
                                    }
                                )
                            )
                        ]
                    else
                        _graph_list = []
                else
                    _graph_list = [
                        span(
                            {
                                key: "graph.nosrc"
                                className: "label label-warning"
                            }
                            "no graph created"
                        )
                    ]
                return div(
                    {
                        key: "top"
                    }
                    h4(
                        {
                            key: "head1"
                        }
                        _head1_list
                    )
                    span(
                        {
                            key: "info"
                        }
                        if _graph.device_names.length == 1 then " 1 device: " else " #{_graph.device_names.length} devices: "
                        _graph.device_names.join(", ")
                        br()
                    )
                    span(
                        {
                            key: "cropline"
                        }
                        _crop_list
                    )
                    _graph_list
                )
    )
]).directive("icswGraphListGraph",
[
    "$templateCache", "$compile", "icswGraphDisplayReact",
(
    $templateCache, $compile, icswGraphDisplayReact,
) ->
    return {
        restrict: "E"
        replace: true
        scope: {
            graph: "=icswGraph"
        }
        # template: $templateCache.get("icsw.graph.list.graph")
        link: (scope, element, attr) ->
            _el = ReactDOM.render(
                React.createElement(
                    icswGraphDisplayReact
                    {
                        graph: scope.graph
                    }
                )
                element[0]
            )
            scope.graph.change_notifier.promise.then(
                (ok) ->
                (error) ->
                (notify) ->
                    _el.force_redraw()
            )
            scope.$on(
                "$destroy"
                () ->
                    ReactDOM.unmountComponentAtNode(element[0])
            )
    }
    # console.log "S", $scope.graph
]).directive("icswGraphThreshold",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "AE"
        template: $templateCache.get("icsw.graph.threshold.overview")
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
                    return scope.sensor.graph.graph_result.tree.user_settings.base.sensor_action_lut[_act].name
                else
                    return "---"

            scope.resolve_user = () ->
                if scope.threshold.create_user
                    return scope.sensor.graph.graph_result.tree.user_group_role_tree.user_lut[scope.threshold.create_user].login
                else
                    return "---"

            scope.get_email = (type) ->
                return if scope.threshold["#{type}_mail"] then "send email" else "no email"

            scope.get_device_selection_info = () ->
                if scope.threshold.device_selection
                    return (entry.info for entry in scope.sensor.graph.graph_result.tree.device_selection_list when entry.idx == scope.threshold.device_selection)[0]
                else
                    return "---"

    }
]).service("icswSensorDialogService",
[
    "$q", "$compile", "$templateCache", "Restangular", "ICSW_URLS",
    "icswToolsSimpleModalService", "$timeout", "icswSimpleAjaxCall",
    "icswComplexModalService", "icswThresholdDialogService",
    "$rootScope",
(
    $q, $compile, $templateCache, Restangular, ICSW_URLS,
    icswToolsSimpleModalService, $timeout, icswSimpleAjaxCall,
    icswComplexModalService, icswThresholdDialogService,
    $rootScope,
) ->
    return (graph) ->
        sub_scope = $rootScope.$new()

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
            icswThresholdDialogService(false, sub_scope, sensor, threshold)

        sub_scope.create_new_threshold = (sensor) ->
            threshold = sensor.graph.graph_result.tree.user_settings.get_new_threshold(sensor)
            icswThresholdDialogService(true, sub_scope, sensor, threshold)

        sub_scope.graph = graph

        def = $q.defer()
        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.graph.sensor"))(sub_scope)
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
]).service("icswThresholdDialogService",
[
    "$q", "$compile", "$templateCache", "Restangular", "ICSW_URLS",
    "icswToolsSimpleModalService", "$timeout", "icswSimpleAjaxCall",
    "icswComplexModalService",
(
    $q, $compile, $templateCache, Restangular, ICSW_URLS,
    icswToolsSimpleModalService, $timeout, icswSimpleAjaxCall,
    icswComplexModalService,
) ->
    return (create, scope, sensor, threshold) ->
        user_settings = sensor.graph.graph_result.tree.user_settings
        th_scope = scope.$new()
        th_scope.sensor = sensor
        th_scope.threshold = threshold

        if !create
            th_scope.threshold.notify_users_obj = threshold.notify_users

            for device_selection in sensor.graph.graph_result.tree.device_selection_list
                if threshold.device_selection == device_selection.idx
                    th_scope.threshold.device_selection_obj = device_selection

        # console.log "args:", create, sensor, threshold
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
                message: $compile($templateCache.get("icsw.graph.threshold.form"))(th_scope)
                title: title
                ok_label: if create then "Create" else "Modify"
                ok_callback: (modal) ->
                    d = $q.defer()
                    th_scope.threshold.notify_users = threshold.notify_users_obj
                    if threshold.device_selection_obj
                        th_scope.threshold.device_selection = threshold.device_selection_obj.idx
                    else
                        th_scope.threshold.device_selection = null
                    user_settings.create_threshold_entry(sensor, th_scope.threshold).then(
                        (created) ->
                            if !create
                                user_settings.remove_threshold_entry(sensor, th_scope.threshold).then(
                                    (ok) ->
                                        d.resolve("done")
                                    (not_ok) ->
                                        d.reject("no")
                                )

                            else
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
    "icswVectorInfoFactory"
    [() ->
        return React.createClass(
            {
                propTypes: {
                    num_struct: React.PropTypes.number.isRequired
                    num_devices: React.PropTypes.number.isRequired
                    num_mve: React.PropTypes.number.isRequired
                    num_mve_sel: React.PropTypes.number.isRequired
                    num_sensors: React.PropTypes.number.isRequired
                }
                render: () ->
                    {div, span, strong} = React.DOM
                    _show_list = []
                    if @props.num_devices
                        _show_list.push("Devices: #{@props.num_devices}")
                    if @props.num_struct
                        _show_list.push("Structural: #{@props.num_struct}")
                    if @props.num_mve
                        _show_list.push("Data: #{@props.num_mve}")
                    if @props.num_mve_sel
                        _show_list.push("Selected: #{@props.num_mve_sel}")
                    if @props.num_sensors
                        _show_list.push("Sensors: #{@props.num_sensors}")
                    return strong(
                        {key: "k0", className: "form-group"},
                        _show_list.join(" / ")
                    )
            }
        )
    ]
).directive("icswVectorInfo",
[
    "icswVectorInfoFactory",
(
    icswVectorInfoFactory
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
                        React.createElement(icswVectorInfoFactory, new_val)
                        el[0]
                    )
                true
            )
    }
])

