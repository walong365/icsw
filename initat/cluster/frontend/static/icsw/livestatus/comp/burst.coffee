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

angular.module(
    "icsw.livestatus.comp.burst",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.router",
    ]
).config(["icswLivestatusPipeRegisterProvider", (icswLivestatusPipeRegisterProvider) ->
    icswLivestatusPipeRegisterProvider.add("icswLivestatusFullBurst", true)
]).service("icswBurstReactSegment",
[
    "$q",
(
    $q,
) ->
    {div, g, text, circle, path, svg, polyline} = React.DOM
    return React.createClass(
        propTypes: {
            element: React.PropTypes.object
            draw_parameters: React.PropTypes.object
            focus_cb: React.PropTypes.func
        }

        displayName: "icswBurstReactSegment"

        render: () ->
            _path_el = @props.element
            # focus element
            _cls = "sb-lines #{_path_el.$$service.$$data.svgClassName}"
            if @props.element.$$burstNode?
                _bn = @props.element.$$burstNode
                # console.log "*", @props
                if _bn.sel_by_child or _bn.sel_by_parent
                    _cls = "#{_cls} svg-sel"
            _segment = {
                key: _path_el.key
                d: _path_el.d
                className: _cls
                onMouseEnter: @on_mouse_enter
                onMouseMove: @props.draw_parameters.tooltip.pos
                onMouseLeave: @on_mouse_leave
                onClick: (event) =>
                    if @props.element.$$burstNode
                        @props.focus_cb("click", @props.element.$$burstNode)
            }
            return path(_segment)

        on_mouse_enter: (event) ->
            if @props.element.$$burstNode?
                @props.draw_parameters.tooltip.show(@props.element.$$burstNode)
                @props.focus_cb("enter", @props.element.$$burstNode)

        on_mouse_leave: (event) ->
            if @props.element.$$burstNode?
                @props.draw_parameters.tooltip.hide()
                @props.focus_cb("leave", @props.element.$$burstNode)
            # @props.clear_focus()
            # console.log "ml"
            # @setState({focus: false})
    )
]).service("icswBurstReactFocusSegment",
[
    "$q",
(
    $q,
) ->
    {div, g, text, circle, path, svg, polyline} = React.DOM
    return React.createClass(
        propTypes: {
            element: React.PropTypes.object
            clicked: React.PropTypes.bool
        }

        displayName: "icswBurstReactFocusSegment"

        render: () ->
            _path_el = @props.element
            if @props.clicked
                _cls = [["o", "svg-clicked-outer"], ["i", "svg-clicked-inner"]]
            else
                _cls = [["o", "svg-hovered-outer"], ["i", "svg-hovered-inner"]]
            return g(
                {
                    key: _path_el.key
                }
                (
                    path(
                        {
                            key: _path_el.key + _pf
                            d: _path_el.d
                            className: _cl
                        }
                    ) for [_pf, _cl] in _cls
                )
            )
    )
]).service("icswBurstReactSegmentText",
[
    "$q",
(
    $q,
) ->
    {div, g, text, circle, path, svg, polyline} = React.DOM
    return React.createClass(
        propTypes: {
            element: React.PropTypes.object
            draw_parameters: React.PropTypes.object
        }

        render: () ->
            _path_el = @props.element

            # add info
            if _path_el.$$burstNode? and not _path_el.$$burstNode.placeholder
                _g_list = []
                {text_radius, text_width} = @props.draw_parameters
                _sx = _path_el.$$mean_radius * Math.cos(_path_el.$$mean_arc)
                _sy = _path_el.$$mean_radius * Math.sin(_path_el.$$mean_arc)
                _ex = text_radius * Math.cos(_path_el.$$mean_arc)
                _ey = text_radius * Math.sin(_path_el.$$mean_arc)
                if _ex > 0
                    _ex2 = text_width
                    _text_anchor = "start"
                else
                    _ex2 = -text_width
                    _text_anchor = "end"
                _g_list.push(
                    polyline(
                        {
                            key: "burst.legend.line"
                            points: "#{_sx},#{_sy} #{_ex},#{_ey} #{_ex2},#{_ey}"
                            stroke: "black"
                            strokeWidth: "1"
                            fill: "none"
                        }
                    )
                )
                _g_list.push(
                    text(
                        {
                            key: "burst.legend.text"
                            x: _ex2
                            y: _ey
                            textAnchor: _text_anchor
                            alignmentBaseline: "middle"
                        }
                        _path_el.$$service.display_name
                    )
                )

                return g(
                    {key: "segment"}
                    _g_list
                )
            else
                return null
    )
]).service("icswDeviceLivestatusBurstReactContainer",
[
    "$q", "ICSW_URLS", "icswSimpleAjaxCall", "icswNetworkTopologyReactSVGContainer",
    "icswDeviceLivestatusFunctions", "icswBurstDrawParameters", "icswBurstReactSegment",
    "icswBurstReactSegmentText", "icswMonitoringResult",
    "$timeout", "icswBurstReactFocusSegment",
(
    $q, ICSW_URLS, icswSimpleAjaxCall, icswNetworkTopologyReactSVGContainer,
    icswDeviceLivestatusFunctions, icswBurstDrawParameters, icswBurstReactSegment,
    icswBurstReactSegmentText, icswMonitoringResult,
    $timeout, icswBurstReactFocusSegment,
) ->
    # Network topology container, including selection and redraw button
    react_dom = ReactDOM
    {div, g, text, line, polyline, path, svg, h3, span, h4} = React.DOM
    return React.createClass(
        propTypes: {
            # required types
            monitoring_data: React.PropTypes.object
            draw_parameters: React.PropTypes.object
            return_data: React.PropTypes.object
            # external trigger, changing this prop will result in a full recalc of the burst
            external_trigger: React.PropTypes.number
            maxWidth: React.PropTypes.number
            minWidth: React.PropTypes.number
        }

        componentDidMount: () ->

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
            # not the most elegant way but working for now
            if @props.external_trigger?
                if @props.external_trigger != @current_trigger
                    # clear root node
                    @root_node = undefined
                    @current_trigger = @props.external_trigger
            # check if burst is interactive
            _ia = @props.draw_parameters.is_interactive
            if not @root_node?
                @root_node = icswDeviceLivestatusFunctions.build_structured_burst(@props.monitoring_data, @props.draw_parameters)
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
            @props.draw_parameters.do_layout()
            if _ia
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
                # if @clicked_focus
                #    console.log "*", @clicked_focus, root_node
            else
                # not interactive, simple list of graphs
                _g_list = (path(_.pickBy(_element, (value, key) -> return not key.match(/\$/))) for _element in root_node.element_list)
            if @state.focus_element
                _element = @state.focus_element.$$path
                _g_list.push(
                    React.createElement(
                        icswBurstReactFocusSegment
                        {
                            key: "foc.#{_element.key}"
                            element: _element
                            clicked: true
                        }
                    )
                )
            _svg = svg(
                {
                    key: "svg.top"
                    # width: "#{@props.draw_parameters.total_width}px"
                    width: "100%"
                    style: {
                        maxWidth: if @props.maxWidth then "#{@props.maxWidth}px" else null
                        minWidth: if @props.minWidth then "#{@props.minWidth}px" else null
                    }
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
                                        style: {}
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

]).controller("icswDeviceLivestatusBurstReactContainerCtrl",
[
    "$scope", "icswDeviceTreeService", "$q", "icswMonitoringResult",
    "icswDeviceLivestatusFunctions", "icswDeviceLivestatusBurstReactContainer",
(
    $scope, icswDeviceTreeService, $q, icswMonitoringResult,
    icswDeviceLivestatusFunctions, icswDeviceLivestatusBurstReactContainer,
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

    _mount_burst = (element, new_data, draw_params) ->
        $scope.struct.react_element = ReactDOM.render(
            React.createElement(
                icswDeviceLivestatusBurstReactContainer
                {
                    monitoring_data: new_data
                    draw_parameters: draw_params
                    return_data: $scope.struct.return_data
                    maxWidth: parseInt($scope.max_width)
                    minWidth: parseInt($scope.min_width)
                }
            )
            element
        )


    $scope.set_notifier = (notify, element, draw_params) ->
        notify.promise.then(
            (ok) ->
                # console.log "ok"
            (reject) ->
                # stop processing
                # console.log "notok"
            (new_data) ->
                # console.log "nd"
                if not $scope.struct.mounted
                    $scope.struct.mounted = true
                    _mount_burst(element, new_data, draw_params)
                else
                    $scope.struct.react_element.new_monitoring_data_result()
        )
        return $scope.struct.return_data

]).service('icswLivestatusFullBurst',
[
    "$q", "icswMonLivestatusPipeBase",
(
    $q, icswMonLivestatusPipeBase,
) ->
    class icswLivestatusFullBurst extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusFullBurst", true, true)
            @set_template(
                '<icsw-livestatus-tooltip icsw-connect-element="con_element"></icsw-livestatus-tooltip>
                <icsw-device-livestatus-fullburst icsw-element-size="size" icsw-connect-element="con_element"></icsw-device-livestatus-fullburst>'
                "Burst Graph"
                5
                5
            )
            @new_data_notifier = $q.defer()
            @__dp_async_emit = true

        new_data_received: (new_data) ->
            # this must return undefined
            @new_data_notifier.notify(new_data)

        pipeline_reject_called: (reject) ->
            @new_data_notifier.reject("stop")

]).directive('icswDeviceLivestatusFullburst',
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
        }
        controller: "icswDeviceLivestatusBurstReactContainerCtrl"
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
            scope.con_element.set_async_emit_data(scope.set_notifier(scope.con_element.new_data_notifier, element[0], draw_params))
            scope.width = parseInt(attrs["initialWidth"] or "600")
            _mounted = false

            scope.$on("$destroy", () ->
                # console.log "DESTROY FullBurst"
                if _mounted
                    ReactDOM.unmountComponentAtNode(element[0])
                    scope.struct.react_element = undefined
            )
    }

]).directive("icswDeviceLivestatusBrief",
[
    "icswBurstDrawParameters", "icswDeviceLivestatusDataService", "$q",
(
    icswBurstDrawParameters, icswDeviceLivestatusDataService, $q,
) ->
    return {
        restrict : "EA"
        controller: "icswDeviceLivestatusBurstReactContainerCtrl"
        scope:
             device: "=icswDevice"
             max_width: "@icswMaxWidth"
             min_width: "@icswMinWidth"
        link : (scope, element, attrs) ->
            if not scope.max_width?
                scope.max_width = "0"
            if not scope.min_width?
                scope.min_width = "0"
            draw_params = new icswBurstDrawParameters(
                {
                    inner_radius: 0
                    outer_radius: 160
                    start_ring: 2
                }
            )
            wait_list = [
                icswDeviceLivestatusDataService.retain(scope.$id, [scope.device])
            ]
            $q.all(wait_list).then(
                (data) ->
                    my_not = $q.defer()
                    scope.set_notifier(my_not, element[0], draw_params)
                    data[0].result_notifier.promise.then(
                        (ok) ->
                        (not_ok) ->
                        (new_data) ->
                            my_not.notify(data[0])
                    )
            )
    }
])
