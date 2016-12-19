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
    "$timeout",
(
    $q, ICSW_URLS, icswSimpleAjaxCall, icswNetworkTopologyReactSVGContainer,
    icswDeviceLivestatusFunctions, icswBurstDrawParameters, icswBurstReactSegment,
    icswBurstReactSegmentText, icswMonitoringResult, icswCategoryTreeService,
    $timeout,
) ->
    # Network topology container, including selection and redraw button
    react_dom = ReactDOM
    {div, g, text, line, polyline, path, svg, h3, span, h4} = React.DOM
    react_id = 0
    return React.createClass(
        propTypes: {
            # required types
            monitoring_data: React.PropTypes.object
            draw_parameters: React.PropTypes.object
            return_data: React.PropTypes.object
            # subtree
            sub_tree: React.PropTypes.string
            # external trigger, changing this prop will result in a full recalc of the burst
            external_trigger: React.PropTypes.number
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
            @focus_name = ""
            @clicked_focus = ""
            # current trigger, for external trigger, NOT in state
            @current_trigger = @props.external_trigger
            return {
                # to trigger redraw
                draw_counter: 0
                focus_element: undefined
                cat_tree_defined: false
            }

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

        focus_cb: (action, ring_el) ->
            if action == "enter"
                if not @clicked_focus or @clicked_focus == ring_el.name
                    @_set_focus(ring_el)
            else if action == "leave"
                if @leave_timeout?
                    $timeout.cancel(@leave_timeout)
                if not @clicked_focus
                    _cur_focus = @focus_name
                    @leave_timeout = $timeout(
                        () =>
                            if _cur_focus == @focus_name
                                # focus_name not changed -> moved outside burst
                                @_clear_focus(true)
                                @clear_timeout()
                        2
                    )
            else if action == "click"
                if ring_el.clicked
                    ring_el.clear_clicked()
                    @clicked_focus = ""
                else
                    ring_el.set_clicked()
                    @clicked_focus = ring_el.name
                @_set_focus(ring_el)

        _set_focus: (ring_el) ->
            @_clear_focus(false)
            ring_el.set_focus()
            # store focus name
            @focus_name = ring_el.name
            @clear_timeout()
            # delay export by 200 milliseconds
            if @props.return_data?
                @export_timeout = $timeout(
                    () =>
                        # console.log "UPDATE"
                        _services = (el.check for el in ring_el.get_self_and_childs() when el.check.$$ct == "service")
                        _hosts = []
                        _host_idxs = []
                        for _service in _services
                            if not _service.$$dummy
                                if _service.$$host_mon_result.$$icswDevice.idx not in _host_idxs
                                    _host_idxs.push(_service.$$host_mon_result.$$icswDevice.idx)
                                    _hosts.push(_service.$$host_mon_result)
                        @props.return_data.update(_hosts, _services, [], [])
                    if @clicked_focus then 0 else 50
                )
            # console.log _services
            @setState({focus_element: ring_el})

        _clear_focus: (do_export) ->
            if @root_node?
                @root_node.clear_focus()
            @focus_name = ""
            if do_export and @props.return_data?
                @props.return_data.update([], [], [], [])
            @setState({focus_element: undefined})

        render: () ->
            if not @state.cat_tree_defined
                return div({}, "waiting for server data...")
            # console.log "ct=", @category_tree, @props.sub_tree
            # get all used cats (also parents)
            # not the most elegant way but working for now
            if @props.external_trigger?
                if @props.external_trigger != @current_trigger
                    # clear root node
                    @root_node = undefined
                    @current_trigger = @props.external_trigger
            [_outer_width, _outer_height] = [0, 0]
            if @burst_element? and @burst_element.width()
                [_outer_width, _outer_height] = [@burst_element.width(), @burst_element.height()]
            # check if burst is interactive
            _ia = @props.draw_parameters.is_interactive
            if not @root_node?
                @root_node = icswDeviceLivestatusFunctions.build_structured_category_burst(
                    @props.monitoring_data
                    @props.sub_tree
                    @category_tree
                    @props.draw_parameters
                )
                _focus_el = undefined
                if @clicked_focus
                    # persistent when new monitoring data arrives
                    @focus_name = @clicked_focus
                if @focus_name
                    @root_node.iter_childs(
                        (node) =>
                            if node.name == @focus_name
                                _focus_el = node
                    )
                    if @clicked_focus and _focus_el?
                        _focus_el.set_clicked()
                # delay to avoid React Error
                $timeout(
                    () =>
                        if _focus_el
                            @focus_cb("enter", _focus_el)
                        else
                            @_clear_focus(true)
                    0
                )
            # console.log _outer_width, _outer_height
            root_node = @root_node
            # if _outer_width
            #    _outer = _.min([_outer_width, _outer_height])
            # else
            @props.draw_parameters.do_layout()
            _outer = @props.draw_parameters.outer_radius
            # console.log _outer
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
                    if _element.$$segment?
                        _seg = _element.$$segment
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
                # if @clicked_focus
                #    console.log "*", @clicked_focus, root_node
            else
                # not interactive, simple list of graphs
                _g_list = (path(_.pickBy(_element, (value, key) -> return not key.match(/\$/))) for _element in root_node.element_list)
            # _g_list = []
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
                # console.log _fe
                if @state.focus_element?
                    _fe = @state.focus_element.check
                else
                    _fe = undefined
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
                            [
                                h4(
                                    {
                                        key: "graph.header"
                                        style: { }
                                    }
                                    "Burst Graph (" + @props.draw_parameters.get_segment_info()
                                    if @clicked_focus then span(
                                        {
                                            key: "sel.span"
                                            className: "text-warning"
                                        }
                                        ", clicked"
                                    ) else ""
                                    ")"
                                )
                                _svg
                            ]
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

    _mount_burst = (element, new_data, draw_params, sub_tree) ->
        $scope.struct.react_element = ReactDOM.render(
            React.createElement(
                icswLivestatusCategoryFilterBurstReact
                {
                    monitoring_data: new_data
                    draw_parameters: draw_params
                    return_data: $scope.struct.return_data
                    sub_tree: sub_tree
                }
            )
            element
        )


    $scope.set_notifier = (notify, element, draw_params, sub_tree) ->
        notify.promise.then(
            (ok) ->
                # console.log "ok"
            (reject) ->
                # stop processing
                # console.log "notok"
            (new_data) ->
                if not $scope.struct.mounted
                    $scope.struct.mounted = true
                    _mount_burst(element, new_data, draw_params, sub_tree)
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
                    inner_radius: 40
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
            @_emit_data = new icswMonitoringResult()
            @_cat_filter = undefined
            @_latest_data = undefined
            @new_data_notifier = $q.defer()
            #  @new_data_notifier = $q.defer()

        get_category_filter: () ->
            return @_cat_filter

        restore_settings: (f_list) ->
            @_cat_filter = f_list

        new_data_received: (data) ->
            @_latest_data = data
            # console.log @_latest_data
            # if @_cat_filter?
            #    @_emit_data.apply_category_filter(@_cat_filter, @_latest_data, "mon")
            @new_data_notifier.notify(data)
            return @_emit_data

        pipeline_reject_called: (reject) ->
            # ignore, stop processing
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
            @_emit_data = new icswMonitoringResult()
            @_cat_filter = undefined
            @_latest_data = undefined
            @new_data_notifier = $q.defer()
            #  @new_data_notifier = $q.defer()

        get_category_filter: () ->
            return @_cat_filter

        restore_settings: (f_list) ->
            @_cat_filter = f_list

        new_data_received: (data) ->
            @_latest_data = data
            # console.log @_latest_data
            # if @_cat_filter?
            #    @_emit_data.apply_category_filter(@_cat_filter, @_latest_data, "mon")
            @new_data_notifier.notify(data)
            return @_emit_data

        pipeline_reject_called: (reject) ->
            # ignore, stop processing
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
                @emit_data_downstream(@new_data_received(@_latest_data))

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
                "Device Category Filter"
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
                @emit_data_downstream(@new_data_received(@_latest_data))

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
