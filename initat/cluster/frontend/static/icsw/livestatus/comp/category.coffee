# Copyright (C) 2012-2016 init.at
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

# livestatus sources and filter functions (components)

angular.module(
    "icsw.livestatus.comp.category",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.router",
    ]
).config(["icswLivestatusPipeRegisterProvider", (icswLivestatusPipeRegisterProvider) ->
    icswLivestatusPipeRegisterProvider.add("icswLivestatusMonCategoryFilter", true)
    icswLivestatusPipeRegisterProvider.add("icswLivestatusDeviceCategoryFilter", true)
    icswLivestatusPipeRegisterProvider.add("icswLivestatusMonCategoryFilterBurst", true)
    icswLivestatusPipeRegisterProvider.add("icswLivestatusDeviceCategoryFilterBurst", true)
]).service("icswLivestatusCategoryFilterBurstReact",
[
    "$q", "ICSW_URLS", "icswSimpleAjaxCall", "icswNetworkTopologyReactSVGContainer",
    "icswDeviceLivestatusFunctions", "icswBurstDrawParameters", "icswBurstReactSegment",
    "icswBurstReactSegmentText", "icswMonitoringResult", "icswCategoryTreeService",
    "$timeout", "icswBurstReactFocusSegment",
(
    $q, ICSW_URLS, icswSimpleAjaxCall, icswNetworkTopologyReactSVGContainer,
    icswDeviceLivestatusFunctions, icswBurstDrawParameters, icswBurstReactSegment,
    icswBurstReactSegmentText, icswMonitoringResult, icswCategoryTreeService,
    $timeout, icswBurstReactFocusSegment,
) ->
    # Network topology container, including selection and redraw button
    react_dom = ReactDOM
    {div, g, button, path, svg, input, span, h4} = React.DOM
    react_id = 0
    return React.createClass(
        propTypes: {
            # required types
            monitoring_data: React.PropTypes.object
            draw_parameters: React.PropTypes.object
            return_data: React.PropTypes.object
            # subtree
            sub_tree: React.PropTypes.string
            # settings changed
            settings_changed: React.PropTypes.func
            # initial filter
            start_settings: React.PropTypes.object
        }
        displayName: "icswLivestatusCategoryFilterBurstReact"

        componentDidMount: () ->
            @category_tree = null
            react_id++
            @filter_id = react_id
            icswCategoryTreeService.load("lsfilterb.#{react_id}").then(
                (data) =>
                    @category_tree = data
                    @setState({cat_tree_defined: true})
            )

        getInitialState: () ->
            @export_timeout = undefined
            @leave_timeout = undefined
            # list of elements now in focus
            # structure of one element is
            # name: name of node
            # clicked: true if clicked or only hover (only one can be hovered)
            @focus_elements = []
            # currently exported filter list
            @settings = _.clone(@props.start_settings)
            @first_call = true
            if not @settings.sum_childs?
                @settings.sum_childs = false
            if not @settings.select_all?
                @settings.select_all = false
            # current trigger, for external trigger, NOT in state
            return {
                # to trigger redraw
                draw_counter: 0
                cat_tree_defined: false
                sum_childs: @settings.sum_childs
                select_all: @settings.select_all
            }

        new_click_list: (new_list) ->
            if not @settings.filter?
                @settings.filter = []
            if not _.isEqual(new_list, @settings.filter)
                @settings.filter.length = 0
                for entry in new_list
                    @settings.filter.push(entry)
                @props.settings_changed(@settings)

        new_monitoring_data_result: () ->
            # force recalc of burst, todo: incremental root_node update
            @root_node = undefined
            # not very elegant
            @trigger_redraw()

        trigger_redraw: () ->
            @setState(
                {
                    draw_counter: @state.draw_counter + 1
                }
            )

        # update timeout handling
        clear_timeout: () ->
            if @export_timeout?
                $timeout.cancel(@export_timeout)
                @export_timeout = undefined

        select_none: () ->
            @focus_elements.length = 0
            @setState({select_all: false})
            @update_filter_settings(true)

        select_all: (update) ->
            if @root_node?
                @focus_elements.length = 0
                for node in @root_node.get_self_and_childs()
                    if node.category
                        @focus_elements.push({name: node.name, clicked: true})
                @update_filter_settings(update)

        select_some: (filter_list, update) ->
            if @root_node?
                @focus_elements.length = 0
                for node in @root_node.get_self_and_childs()
                    if node.category and node.category.idx in filter_list
                        @focus_elements.push({name: node.name, clicked: true})
                @update_filter_settings(update)

        focus_cb: (action, ring_el) ->
            if action == "enter"
                # remove old hover
                _.remove(@focus_elements, (entry) -> return not entry.clicked)
                # if not _.some(@focus_elements, (entry) -> return entry.name == ring_el.name)
                @focus_elements.push({name: ring_el.name, clicked: false})
                @update_filter_settings(true)
            else if action == "leave"
                if @leave_timeout?
                    $timeout.cancel(@leave_timeout)
                _cur_focus = _.clone(@focus_elements)
                @leave_timeout = $timeout(
                    () =>
                        if _.isEqual(_cur_focus, @focus_elements)
                            # focus_elements not changed -> moved outside burst
                            # remove element
                            _.remove(@focus_elements, (entry) -> return not entry.clicked and entry.name == ring_el.name)
                            @clear_timeout()
                            @update_filter_settings(true)
                    2
                )
            else if action == "click"
                _current = (entry for entry in @focus_elements when entry.name == ring_el.name and entry.clicked)
                if _current.length
                    # _current = _current[0]
                    # if _current.clicked
                    # remove
                    _.remove(@focus_elements, (entry) -> return entry.name == ring_el.name and entry.clicked)
                    # deactvate select_all
                    @setState({select_all: false})
                    # else
                    #     # was hovered, now click
                    #     _current.clicked = true
                else
                    # not in list, add clicked verison
                    @focus_elements.push({name: ring_el.name, clicked: true})
                @update_filter_settings(true)

        update_filter_settings: (redraw) ->
            @clear_timeout()
            _click_list = []
            # delay export by 200 milliseconds
            _cats = []
            any_clicked = false
            for s_node in @focus_elements
                node = @root_node.name_lut[s_node.name]
                if node.category
                    _cats.push(node.category.idx)
                    if s_node.clicked
                        any_clicked = true
                        _click_list.push(node.category.idx)
            if @props.return_data?
                @export_timeout = $timeout(
                    () =>
                        # console.log "UPDATE", ring_el
                        @props.return_data.apply_category_filter(
                            _cats
                            @props.monitoring_data
                            @props.sub_tree
                        )
                        # send data downstream
                        @props.return_data.notify()
                    if any_clicked then 0 else 50
                )
            @new_click_list(_click_list)
            # console.log _services
            if redraw
                @trigger_redraw()

        _clear_focus: (do_export) ->
            if @root_node?
                @root_node.clear_focus()
            @focus_elements.length = 0
            if do_export and @props.return_data?
                console.log "clear"
                @props.return_data.update([], [], [], [])
            @trigger_redraw()

        render: () ->
            if not @state.cat_tree_defined
                return div({}, "waiting for server data...")
            # console.log "ct=", @category_tree, @props.sub_tree
            # get all used cats (also parents)
            # not the most elegant way but working for now
            # check if burst is interactive
            _ia = @props.draw_parameters.is_interactive
            _redraw = false
            if not @root_node?
                _redraw = true
            _settings_changed = false
            if @settings.sum_childs != @state.sum_childs
                @settings.sum_childs = @state.sum_childs
                _settings_changed = true
            if @settings.select_all != @state.select_all
                @settings.select_all = @state.select_all
                _settings_changed = true
                if @settings.select_all
                    # force redraw when select_all is set
                    _redraw = true
            if _settings_changed
                @props.settings_changed(@settings)
                _redraw = true
            if _redraw
                @root_node = icswDeviceLivestatusFunctions.build_structured_category_burst(
                    @props.monitoring_data
                    @props.sub_tree
                    @category_tree
                    @props.draw_parameters
                    @state.sum_childs
                )
                # remove no longer existing nodes from focus_elements
                _.remove(@focus_elements, (node) => return node.name not of @root_node.name_lut)
                if @settings.select_all
                    @select_all(false)
                else
                    if @first_call
                        @first_call = false
                        if not @props.start_settings.filter?
                            @select_all(false)
                        else
                            @select_some(@props.start_settings.filter, false)
                    else
                        @update_filter_settings(false)
            root_node = @root_node
            @props.draw_parameters.do_layout()
            if _ia
                # console.log "RN=", root_node
                # interactive, pathes have mouseover and click handler
                _g_list = (
                    React.createElement(
                        icswBurstReactSegment,
                        {
                            key: _element.key
                            element: _element
                            focus_cb: @focus_cb
                            draw_parameters: @props.draw_parameters
                        }
                    ) for _element in root_node.element_list
                )
                for _element in root_node.element_list
                    if _element.$$burstNode?
                        _seg = _element.$$burstNode
                        if _seg.show_legend and false
                            _g_list.push(
                                React.createElement(
                                    icswBurstReactSegmentText,
                                    {
                                        key: _element.key + "_leg"
                                        element: _element
                                        draw_parameters: @props.draw_parameters
                                    }
                                )
                            )
            else
                # not interactive, simple list of graphs
                _g_list = (
                    path(_.pickBy(_element, (value, key) -> return not key.match(/\$/))) for _element in root_node.element_list
                )
            for node in @focus_elements
                if node.clicked
                    _element = @root_node.name_lut[node.name].$$path
                    _g_list.push(
                        React.createElement(
                            icswBurstReactFocusSegment
                            {
                                key: "foc.#{_element.key}"
                                element: _element
                                clicked: node.clicked
                            }
                        )
                    )
            for node in @focus_elements
                if not node.clicked
                    _element = @root_node.name_lut[node.name].$$path
                    _g_list.push(
                        React.createElement(
                            icswBurstReactFocusSegment
                            {
                                key: "hov.#{_element.key}"
                                element: _element
                                clicked: node.clicked
                            }
                        )
                    )
            _svg = svg(
                {
                    key: "svg.top"
                    # width: "#{@props.draw_parameters.total_width}px"
                    width: "100%"
                    # height: "#{@props.draw_parameters.total_height}px"
                    fontFamily: "'Open-Sans', sans-serif"
                    fontSize: "10pt"
                    viewBox: "128 32 330 330"
                    preserveAspectRatio: "xMidYMid meet"
                }
                [
                    g(
                        {
                            key: "main"
                            # transform: "translate(#{@props.draw_parameters.total_width / 2}, #{@props.draw_parameters.total_width / 2})"
                            transform: "translate(292, 192)"
                        }
                        _g_list
                    )
                ]
            )
            if _ia
                num_clicked = (entry for entry in @focus_elements when entry.clicked).length
                _header = [
                    if @props.sub_tree == "mon" then "Service" else "Device"
                    " ("
                    @props.draw_parameters.get_segment_info()
                ]
                if num_clicked
                    _header.push(", #{num_clicked} selected")
                _header.push(")")
                _header = _header.join("")
                # graph has a focus component
                _graph = div(
                    {
                        key: "top.div"
                        className: "row"
                    }
                    [
                        div(
                            {
                                key: "svg.div"
                                className: "col-xs-12"
                            }
                            h4(
                                {
                                    key: "graph.header"
                                    style: { }
                                }
                                "all:"
                                input(
                                    {
                                        type: "checkbox"
                                        key: "selall"
                                        title: "keep all categories selected"
                                        checked: @settings.select_all
                                        # className: "btn btn-xs btn-primary"
                                        onClick: (event) =>
                                            @setState({select_all: !@state.select_all})
                                            # @select_all(true)
                                    }
                                )
                                button(
                                    {
                                        type: "button"
                                        key: "selnone"
                                        className: "btn btn-xs btn-warning"
                                        onClick: (event) =>
                                            @select_none()
                                    }
                                    "none"
                                )
                                "sum:"
                                input(
                                    {
                                        type: "checkbox"
                                        key: "parent"
                                        title: "Take info from childs"
                                        checked: @state.sum_childs
                                        onClick: (event) =>
                                            @setState({sum_childs: !@state.sum_childs})
                                    }
                                )
                                span(
                                    {
                                        key: "hs"
                                    }
                                    _header
                                )
                            )
                            _svg
                        )
                    ]
                )
            else
                # graph consists only of svg
                _graph = _svg
            return _graph
    )

]).controller("icswLivestatusCategoryFilterBurstCtrl",
[
    "$scope", "icswDeviceTreeService", "$q", "icswMonitoringResult",
    "icswLivestatusCategoryFilterBurstReact",
(
    $scope, icswDeviceTreeService, $q, icswMonitoringResult,
    icswLivestatusCategoryFilterBurstReact,
) ->
    $scope.struct = {
        # loop started
        loop_started: false
        # react element
        react_element: undefined
        # return data
        return_data: new icswMonitoringResult()
        # mounted
        mounted: false
    }

    _mount_burst = (element, new_data, draw_params, sub_tree, filter_changed, start_settings) ->
        $scope.struct.react_element = ReactDOM.render(
            React.createElement(
                icswLivestatusCategoryFilterBurstReact
                {
                    monitoring_data: new_data
                    draw_parameters: draw_params
                    return_data: $scope.struct.return_data
                    sub_tree: sub_tree
                    settings_changed: filter_changed
                    start_settings: start_settings
                }
            )
            element
        )


    $scope.set_notifier = (notify, element, draw_params, sub_tree, filter_changed, start_settings) ->
        notify.promise.then(
            (ok) ->
                # console.log "ok"
            (reject) ->
                # stop processing
                # console.log "notok"
            (new_data) ->
                if not $scope.struct.mounted
                    $scope.struct.mounted = true
                    _mount_burst(element, new_data, draw_params, sub_tree, filter_changed, start_settings)
                else
                    $scope.struct.react_element.new_monitoring_data_result()
        )
        return $scope.struct.return_data

]).directive("icswLivestatusCategoryFilterBurst",
[
    "icswBurstDrawParameters",
(
    icswBurstDrawParameters,
) ->
    return {
        restrict: "EA"
        scope: {
            size: "=icswElementSize"
            con_element: "=icswConnectElement"
            icsw_sub_tree: "=icswSubTree"
        }
        controller: "icswLivestatusCategoryFilterBurstCtrl",
        link: (scope, element, attrs) ->
            draw_params = new icswBurstDrawParameters(
                {
                    inner_radius: 0
                    outer_radius: 160
                    start_ring: 0
                    is_interactive: true
                    omit_small_segments: true
                    tooltip: scope.con_element.tooltip
                }
            )
            scope.con_element.set_async_emit_data(
                scope.set_notifier(
                    scope.con_element.new_data_notifier
                    element[0]
                    draw_params
                    scope.icsw_sub_tree
                    scope.con_element.filter_changed
                    scope.con_element.filter_settings
                )
            )
            # console.log "+++", scope.con_element
            # omitted segments
            _mounted = false

            scope.$on("$destroy", () ->
                # console.log "DESTROY FullBurst"
                if _mounted
                    ReactDOM.unmountComponentAtNode(element[0])
                    scope.struct.react_element = undefined
            )
    }

]).service('icswLivestatusMonCategoryFilterBurst',
[
    "$q", "icswMonLivestatusPipeBase", "icswMonitoringResult",
(
    $q, icswMonLivestatusPipeBase, icswMonitoringResult,
) ->
    class icswLivestatusMonCategoryFilterBurst extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusMonCategoryFilterBurst", true, true)
            @set_template(
                '<icsw-livestatus-tooltip icsw-connect-element="con_element"></icsw-livestatus-tooltip>
                <icsw-livestatus-category-filter-burst icsw-connect-element="con_element" icsw-sub-tree="\'mon\'"></icsw-livestatus-category-filter-burst>'
                "Monitoring Category Filter (Burst)"
                5
                4
            )
            @__dp_async_emit = true
            @new_data_notifier = $q.defer()
            # default for not set
            @filter_settings = {}

        restore_settings: (f_obj) ->
            @filter_settings = f_obj

        filter_changed: (f_obj) =>
            @pipeline_settings_changed(f_obj)

        new_data_received: (data) ->
            @new_data_notifier.notify(data)
            return null

        pipeline_reject_called: (reject) ->
            @new_data_notifier.reject("stop")

]).service('icswLivestatusDeviceCategoryFilterBurst',
[
    "$q", "icswMonLivestatusPipeBase", "icswMonitoringResult",
(
    $q, icswMonLivestatusPipeBase, icswMonitoringResult,
) ->
    class icswLivestatusDeviceCategoryFilterBurst extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusDeviceCategoryFilterBurst", true, true)
            @set_template(
                '<icsw-livestatus-tooltip icsw-connect-element="con_element"></icsw-livestatus-tooltip>
                <icsw-livestatus-category-filter-burst icsw-connect-element="con_element" icsw-sub-tree="\'device\'"></icsw-livestatus-category-filter-burst>'
                "Device Category Filter (Burst)"
                5
                4
            )
            @__dp_async_emit = true
            @new_data_notifier = $q.defer()
            # default for not set
            @filter_settings = {}

        restore_settings: (f_obj) ->
            @filter_settings = f_obj

        filter_changed: (f_obj) =>
            @pipeline_settings_changed(f_obj)

        new_data_received: (data) ->
            @new_data_notifier.notify(data)
            return null

        pipeline_reject_called: (reject) ->
            @new_data_notifier.reject("stop")

]).service('icswLivestatusMonCategoryFilter',
[
    "$q", "icswMonLivestatusPipeBase", "icswMonitoringResult",
(
    $q, icswMonLivestatusPipeBase, icswMonitoringResult,
) ->
    class icswLivestatusMonCategoryFilter extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusMonCategoryFilter", true, true)
            @set_template(
                '<h4>Monitoring Category Filter</h4>
                <icsw-config-category-tree-select icsw-mode="filter" icsw-sub-tree="\'mon\'" icsw-mode="filter" icsw-connect-element="con_element"></icsw-config-category-tree-select>'
                "Monitoring Category Filter (Tree)"
                5
                2
            )
            @_emit_data = new icswMonitoringResult()
            @_cat_filter = undefined
            @_latest_data = undefined
            @new_data_notifier = $q.defer()
            #  @new_data_notifier = $q.defer()

        set_category_filter: (sel_cat) ->
            @_cat_filter = sel_cat
            @pipeline_settings_changed(@_cat_filter)
            if @_latest_data?
                @emit_data_downstream(@new_data_received_cached(@_latest_data))

        get_category_filter: () ->
            return @_cat_filter

        restore_settings: (f_list) ->
            @_cat_filter = f_list

        new_data_received: (data) ->
            @_latest_data = data
            if @_cat_filter?
                @_emit_data.apply_category_filter(@_cat_filter, @_latest_data, "mon")
            @new_data_notifier.notify(data)
            return @_emit_data

        pipeline_reject_called: (reject) ->
            # ignore, stop processing
]).service('icswLivestatusDeviceCategoryFilter',
[
    "$q", "icswMonLivestatusPipeBase", "icswMonitoringResult",
(
    $q, icswMonLivestatusPipeBase, icswMonitoringResult,
) ->
    class icswLivestatusDeviceCategoryFilter extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusDeviceCategoryFilter", true, true)
            @set_template(
                '<h4>Device Category Filter</h4>
                <icsw-config-category-tree-select icsw-mode="filter" icsw-sub-tree="\'device\'" icsw-mode="filter" icsw-connect-element="con_element"></icsw-config-category-tree-select>'
                "Device Category Filter (Tree)"
                4
                2
            )
            @_emit_data = new icswMonitoringResult()
            @_cat_filter = undefined
            @_latest_data = undefined
            @new_data_notifier = $q.defer()
            #  @new_data_notifier = $q.defer()

        set_category_filter: (sel_cat) ->
            @_cat_filter = sel_cat
            @pipeline_settings_changed(@_cat_filter)
            if @_latest_data?
                @emit_data_downstream(@new_data_received_cached(@_latest_data))

        get_category_filter: () ->
            return @_cat_filter

        restore_settings: (f_list) ->
            @_cat_filter = f_list

        new_data_received: (data) ->
            @_latest_data = data
            if @_cat_filter?
                @_emit_data.apply_category_filter(@_cat_filter, @_latest_data, "device")
            @new_data_notifier.notify(data)
            return @_emit_data

        pipeline_reject_called: (reject) ->
            # ignore, stop processing
])
