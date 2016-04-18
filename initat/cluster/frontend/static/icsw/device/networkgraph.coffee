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

# network graphing tool

angular.module(
    "icsw.svg_tools",
    []
).factory("svg_tools", () ->
    return {
        has_class_svg: (obj, has) ->
            classes = obj.attr("class")
            if !classes
                return false
            return if classes.search(has) == -1 then false else true

        get_abs_coordinate : (svg_el, x, y) ->
            screen_ctm = svg_el.getScreenCTM()
            svg_point = svg_el.createSVGPoint()
            svg_point.x = x
            svg_point.y = y
            first = svg_point.matrixTransform(screen_ctm.inverse())
            return first
    }
)

angular.module(
    "icsw.mouseCapture",
    []
).factory('mouseCaptureFactory', [() ->
    # mouseCaptureFactory for ReactJS, no $rootScope.$digest Cycles are triggered
    $element = document
    mouse_capture_config = null
    mouse_move = (event) ->
        if mouse_capture_config and mouse_capture_config.mouse_move
            mouse_capture_config.mouse_move(event)
    mouse_up = (event) ->
        if mouse_capture_config and mouse_capture_config.mouse_up
            mouse_capture_config.mouse_up(event)
    return {
        register_element: (element) ->
            $element = $(element)
        acquire: (event, config) ->
            this.release()
            mouse_capture_config = config
            $element.bind("mousemove", mouse_move)
            $element.bind("mouseup", mouse_up)
        release: () ->
            if mouse_capture_config
                if mouse_capture_config.released
                    mouse_capture_config.released()
                mouse_capture_config = null;
                $element.unbind("mousemove", mouse_move)
                $element.unbind("mouseup", mouse_up)
    }
])
# no longer needed, handled via ReactJS
# .directive('icswMouseCapture', () ->
#    return {
#        restrict: "A"
#        controller: ["$scope", "$element", "mouseCaptureFactory", ($scope, $element, mouseCaptureFactory) ->
#            mouseCaptureFactory.register_element($element)
#        ]
#    }
#)

angular.module(
    "icsw.dragging",
    [
        "icsw.mouseCapture"
    ]
).factory("dragging", ["mouseCaptureFactory", (mouseCaptureFactory) ->
    return {
        start_drag: (event, threshold, config) ->
            dragging = false
            x = event.clientX
            y = event.clientY
            mouse_move = (event) ->
                if !dragging
                    if Math.abs(event.clientX - x) > threshold or Math.abs(event.clientY - y) > threshold
                        dragging = true;
                        if config.dragStarted
                            config.dragStarted(x, y, event)
                        if config.dragging
                            config.dragging(event.clientX, event.clientY, event)
                else 
                    if config.dragging
                        config.dragging(event.clientX, event.clientY, event);
                    x = event.clientX
                    y = event.clientY
            released = () ->
                if dragging
                    if config.dragEnded
                        config.dragEnded()
                else 
                    if config.clicked
                        config.clicked()
            mouse_up = (event) ->
                mouseCaptureFactory.release()
                event.stopPropagation()
                event.preventDefault()
            mouseCaptureFactory.acquire(event, {
                mouse_move: mouse_move
                mouse_up: mouse_up
                released: released
            })
            event.stopPropagation()
            event.preventDefault()
    }
])

angular.module(
    "icsw.device.network.graph",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "icsw.d3", "ui.select",
        "angular-ladda", "icsw.dragging", "monospaced.mousewheel", "icsw.svg_tools", "icsw.tools", "icsw.tools.table",
    ]
).directive("icswDeviceNetworkTopology", ["$templateCache", ($templateCache) ->
    return {
        restrict: "E"
        template: $templateCache.get("icsw.device.network.topology")
        controller: "icswDeviceNetworkGraphCtrl"
    }
]).controller("icswDeviceNetworkGraphCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular", "$q", "icswAcessLevelService", "icswLivestatusFilterFactory",
    "ICSW_SIGNALS", "$rootScope",
(
    $scope, $compile, $filter, $templateCache, Restangular, $q, icswAcessLevelService, icswLivestatusFilterFactory,
    ICSW_SIGNALS, $rootScope
) ->
    icswAcessLevelService.install($scope)
    $scope.settings = {
    #    "draw_mode": "sel"
    #    "show_livestatus": false
        "devices": []
    #    "size": {
    #        width: 1200
    #        height: 800
    #    }
    #    "zoom": {
    #        factor: 1.0
    #    }
    #    "offset": {
    #        x: 0
    #        y: 0
    #    }
    }
    $scope.raw_draw_selections = [
        {"value": "none", "info": "None", "dr": false}
        {"value": "all_with_peers", "info": "all peered", "dr": false}
        {"value": "all", "info": "All devices", "dr": false}
        {"value": "sel", "info": "selected", "dr": true}
        {"value": "selp1", "info": "selected + 1 (next ring)", "dr": true}
        {"value": "selp2", "info": "selected + 2", "dr": true}
        {"value": "selp3", "info": "selected + 3", "dr": true}
        {"value": "core", info: "Core network", "dr": false}
    ]
    #update_draw_selections = () ->
    #    sles = []
    #    for entry in $scope.raw_draw_selections
    #        _add = true
    #        if entry.dr and not $scope.settings.devices.length
    #            _add = false
    #        if _add
    #            sles.push(entry)
    #    $scope.draw_selections = sles

    $scope.new_devsel = (_dev_sel) ->
        $scope.settings.devices = _dev_sel

    # update_draw_selections()

    # $scope.ls_filter = new icswLivestatusFilterFactory()
]).service("icswDeviceLivestatusFunctions",
[
    "$q",
(
    $q,
) ->
    get_fill_color = (res) ->
        if res.$$ct == "service"
            color = {
                0: "#66dd66"
                1: "#dddd88"
                2: "#ff7777"
                3: "#ff0000"
            }[res.state]
        else if res.$$ct == "host"
            color = {
                0: "#66dd66"
                1: "#ff7777"
                2: "#ff0000"
            }[res.state]
        else
            color = "000000"
        return color

    build_burst_ring = (inner, outer, key_prefix, r_data) ->
        end_arc = 0
        end_num = 0
        _len = r_data.length
        _result = []
        if _len
            _idx = 0
            for srvc in r_data
                _idx++
                start_arc = end_arc
                end_num += 1
                end_arc = 2 * Math.PI * end_num / _len
                start_sin = Math.sin(start_arc)
                start_cos = Math.cos(start_arc)
                end_sin = Math.sin(end_arc)
                end_cos = Math.cos(end_arc)
                if end_arc > start_arc + Math.PI
                    _large_arc_flag = 1
                else
                    _large_arc_flag = 0
                _path = "M#{start_cos * inner},#{start_sin * inner} L#{start_cos * outer},#{start_sin * outer} " + \
                    "A#{outer},#{outer} 0 #{_large_arc_flag} 1 #{end_cos * outer},#{end_sin * outer} " + \
                    "L#{end_cos * inner},#{end_sin * inner} " + \
                    "A#{inner},#{inner} 0 #{_large_arc_flag} 0 #{start_cos * inner},#{start_sin * inner} " + \
                    "Z"
                _result.push(
                    {
                        key: "path.#{key_prefix}.#{_idx}"
                        d: _path
                        fill: get_fill_color(srvc)
                        stroke: "black"
                        # hm, stroke-width seems to be ignored
                        strokeWidth: "0.5"
                    }
                )
        else
            _path = "M#{outer},0 " + \
            "A#{outer},#{outer} 0 1,1 #{-outer},0 " + \
            "A#{outer},#{outer} 0 1,1 #{outer},0 " + \
            "L#{outer},0 " + \
            "M#{inner},0 " + \
            "A#{inner},#{inner} 0 1,0 #{-inner},0 " + \
            "A#{inner},#{inner} 0 1,0 #{inner},0 " + \
            "L#{inner},0 " + \
            "Z"

            # draw an empty (== grey) ring
            _result.push(
                {
                    key: "path.#{key_prefix}.empty"
                    d: _path
                    fill: "#dddddd"
                    stroke: "black"
                    strokeWidth: "0.3"
                }
            )
        return _result

    build_single_device_burst = (h_data, s_data) ->
        _result = []
        if h_data?
            _result = _.concat(_result, build_burst_ring(10, 20, "host", [h_data]))
        else
            _result = _.concat(_result, build_burst_ring(10, 20, "host", []))
        _result = _.concat(_result, build_burst_ring(20, 30, "srvc", s_data))
        return _result


    return {
        build_single_device_burst: (host_data, srvc_data) ->
            return build_single_device_burst(host_data, srvc_data)
    }

]).factory("icswDeviceLivestatusReactBurst",
[
    "$q", "icswDeviceLivestatusFunctions",
(
    $q, icswDeviceLivestatusFunctions,
) ->

    react_dom = ReactDOM
    {div, g, text, circle, path} = React.DOM

    return React.createClass(
        propTypes: {
            # required types
            node: React.PropTypes.object
            monitoring_data: React.PropTypes.object
        }
        componentDidMount: () ->
            el = react_dom.findDOMNode(@)
            # d3js hack
            el.__data__ = @props.node

        render: () ->
            node = @props.node
            if node.id of @props.monitoring_data.host_lut
                host_data = @props.monitoring_data.host_lut[node.id]
                if not host_data.$$show
                    host_data = undefined
            else
                host_data = undefined
            # should be optmized
            srvc_data = (entry for entry in @props.monitoring_data.filtered_services when entry.host.host_name  == node.$$device.full_name)

            # console.log host_data, srvc_data
            # if host_data and srvc_data.length
            _pathes = icswDeviceLivestatusFunctions.build_single_device_burst(host_data, srvc_data)
            # else
            #    _pathes = []

            return g(
                {
                    key: "node.#{node.id}"
                    className: "d3-livestatus"
                    id: "#{node.id}"
                    transform: "translate(#{node.x}, #{node.y})"
                }
                (
                    path(_path) for _path in _pathes
                )
            )
    )
]).service("icswD3DeviceLivestatiReactBurst",
[
    "svg_tools", "icswDeviceLivestatusReactBurst",
(
    svg_tools, icswDeviceLivestatusReactBurst,
) ->
    # container for all device bursts
    react_dom = ReactDOM
    {div, g, text} = React.DOM

    return React.createClass(
        propTypes: {
            # required types
            nodes: React.PropTypes.array
            show_livestatus: React.PropTypes.bool
            monitoring_data: React.PropTypes.object
        }
        #shouldComponentUpdate: (next_props, next_state) ->
        #    console.log "*", next_props, @props
        #    return _redraw

        render: () ->
            _bursts = []
            if @props.show_livestatus
                for node in @props.nodes
                    _bursts.push(
                        React.createElement(
                            icswDeviceLivestatusReactBurst
                            {
                                node: node
                                monitoring_data: @props.monitoring_data
                            }
                        )
                    )
            return g(
                {
                    key: "top.stati"
                    className: "d3-livestati"
                }
                _bursts
            )
    )
]).service("icswD3Device",
[
    "svg_tools",
(
    svg_tools
) ->
    class icswD3Device
        constructor: (@container) ->

        create: (selector, graph) ->
            # console.log "data=", graph.nodes
            # not working, TODO
            # selector.data([]).exit().remove()
            ds = selector.data(graph.nodes, (d) -> return d.id)
            _g = ds.enter().append("g")
            _g.attr("class", "d3-point draggable")
            .attr("id", (d) -> return graph.node_to_dom_id(d))
            .attr("transform", (d) -> return "translate(#{d.x}, #{d.y})")
            _g.append("circle")
            # <circle r="18" fill="{{ fill_color }}" stroke-width="{{ stroke_width }}" stroke="{{ stroke_color }}" cursor="crosshair"></circle>
            .attr('r', (d) -> return d.radius)
            .attr("stroke-width", "2")
            .attr("stroke", "grey")
            .attr("fill", "white")
            .attr("cursor", "crosshair")
            _g.append("text")
            .attr("stroke-width", "2")
            .attr("stroke", "white")
            .attr("paint-order", "stroke")
            .text(
                (d) ->
                    return d.$$device.full_name
            )
            # <text text-anchor="middle" alignment-baseline="middle" cursor="crosshair">{{ node.name }}</text>
            .attr("text-anchor", "middle")
            .attr("alignment-baseline", "middle")
            .attr("cursor", "crosshair")
            # mouse handling
            that = @
            _g.on("click", (node) ->
                # important to use thin arrows here
                that.container.click(this, node)
            )
            ds.exit().remove()

]).service("icswD3Link",
[
    "svg_tools",
(
    svg_tools
) ->
    class icswD3Link
        constructor: (@container) ->
        create: (selector, graph) ->
            # console.log "link=", graph.links
            ds = selector.data(graph.links, (l) -> return graph.link_to_dom_id(l))
            ds.enter().append("line")
            .attr("class", "d3-link")
            .attr("stroke", "#ff7788")
            .attr("stroke-width", "4")
            .attr("opacity", "1")
            ds.exit().remove()

]).service("icswNetworkTopologyDrawService",
[
    "$templateCache", "d3_service", "svg_tools", "dragging", "mouseCaptureFactory",
    "icswTools", "icswD3Device", "icswD3Link", "$q", "icswDeviceLivestatusDataService",
    "$timeout", "icswD3DeviceLivestatiReactBurst",
(
    $templateCache, d3_service, svg_tools, dragging, mouseCaptureFactory,
    icswTools, icswD3Device, icswD3Link, $q, icswDeviceLivestatusDataService,
    $timeout, icswD3DeviceLivestatiReactBurst,
) ->

    # acts as a helper class for drawing Networks as SVG-graphs
    class icswNetworkTopologyDrawService

        constructor: () ->
            @id = icswTools.get_unique_id()
            @status_timeout = undefined
            @livestatus_state = false
            @filter_state_str = ""
            @device_gen = new icswD3Device(@)
            @link_gen = new icswD3Link(@)
            # pipe for graph commands
            @graph_command_pipe = undefined
            # current monitoring data
            @monitoring_data = undefined
            # autoscale during initial force run
            @do_autoscale = false

        create: (element, props, state) =>
            @element = element
            @props = props
            @state = state
            @graph_command_pipe = $q.defer()
            if @props.graph_command_cb?
                @props.graph_command_cb(@graph_command_pipe)
                @graph_command_pipe.promise.then(
                    () ->
                    (exit) ->
                        console.log "exit"
                    (cmd) =>
                        if cmd == "scale"
                            @graph_cmd_scale()
                        else
                            console.error "unknown graph command '#{cmd}'"
                )
            draw_settings = state.settings
            $q.all(
                [
                    d3_service.d3()
                ]
            ).then(
                (result) =>
                    d3 = result[0]
                    # base settings
                    @d3 = d3
                    @d3_element = d3.select(@element)
                    _find_element = (s_target) ->
                        # iterative search
                        if svg_tools.has_class_svg(s_target, "draggable")
                            return s_target
                        s_target = s_target.parent()
                        if s_target.length
                            return _find_element(s_target)
                        else
                            return null
                    svg = @d3_element.append("svg")
                    .attr('class', 'draggable')
                    # viewBox not viewbox
                    .attr("viewBox", "0 0 1200 760")
                    .attr("preserveAspectRatio", "xMidYMin slice")
                    .attr("version", "1.1")
                    .attr("onStart", @_drag_start)
                    .attr("pointer-events", "all")
                    $(element).on("mouseclick", (event) =>
                        drag_el = _find_element($(event.target))
                        # console.log "DRAG_EL=", drag_el
                        if drag_el? and drag_el.length
                            drag_el = $(drag_el[0])
                            # console.log "d=", drag_el
                    )
                    $(element).mousedown(
                        (event) =>
                            mouseCaptureFactory.register_element(element)
                            drag_el = _find_element($(event.target))
                            if drag_el? and drag_el.length
                                drag_el = $(drag_el[0])
                                drag_el_tag = drag_el.prop("tagName")
                                # disable autoscale
                                svg = $(element).find("svg")[0]
                                @do_autoscale = false
                                if drag_el_tag == "svg"
                                    _sx = 0
                                    _sy = 0
                                    start_drag_point = undefined
                                    dragging.start_drag(event, 1, {
                                        dragStarted: (x, y, event) =>
                                            start_drag_point = svg_tools.get_abs_coordinate(svg, x, y)
                                            _sx = draw_settings.offset.x
                                            _sy = draw_settings.offset.y
                                        dragging: (x, y) =>
                                            cur_point = svg_tools.get_abs_coordinate(svg, x, y)
                                            draw_settings.offset = {
                                                x: _sx + cur_point.x - start_drag_point.x
                                                y: _sy + cur_point.y - start_drag_point.y
                                            }
                                            @_update_transform(element, draw_settings, props.update_scale_cb)
                                        dragEnded: () =>
                                    })
                                else
                                    drag_node = drag_el[0]
                                    drag_dev = state.graph.dom_id_to_node($(drag_node).attr("id"))
                                    dragging.start_drag(event, 1, {
                                        dragStarted: (x, y, event) =>
                                            @set_fixed(drag_node, drag_dev, true)
                                        dragging: (x, y) =>
                                            cur_point = @_rescale(
                                                svg_tools.get_abs_coordinate(svg, x, y)
                                                draw_settings
                                            )
                                            node = drag_dev
                                            node.x = cur_point.x
                                            node.y = cur_point.y
                                            # the p-coordiantes are important for moving (dragging) nodes
                                            node.px = cur_point.x
                                            node.py = cur_point.y
                                            @tick()
                                            if @force?
                                                # restart moving
                                                @force.start()
                                        dragEnded: () =>
                                            @set_fixed(drag_node, drag_dev, false)
                                    })
                    )
                    Hamster(element).wheel(
                        (event, delta, dx, dy) =>
                            # console.log "msd", delta, dx, dy
                            svg = $(element).find("svg")[0]
                            scale_point = @_rescale(
                                svg_tools.get_abs_coordinate(svg, event.originalEvent.clientX, event.originalEvent.clientY)
                                draw_settings
                            )
                            prev_factor = draw_settings.zoom.factor
                            if delta > 0
                                draw_settings.zoom.factor *= 1.05
                            else
                                draw_settings.zoom.factor /= 1.05
                            draw_settings.offset.x += scale_point.x * (prev_factor - draw_settings.zoom.factor)
                            draw_settings.offset.y += scale_point.y * (prev_factor - draw_settings.zoom.factor)
                            @_update_transform(element, draw_settings, props.update_scale_cb)
                            event.stopPropagation()
                            event.preventDefault()
                    )
                    # enclosing rectangular and top-level g
                    svg.append("rect")
                    .attr("x", "0")
                    .attr("y", "0")
                    .attr("width", "100%")
                    .attr("height", "100%")
                    .attr("style", "stroke:black; stroke-width:2px; fill-opacity:0;")
                    _top_g = svg.append("g").attr("id", "top")
                    _top_g.append('g').attr('class', 'd3-links')
                    _top_g.append('g').attr('class', 'd3-livestati')
                    _top_g.append('g').attr('class', 'd3-points')

                    # force settings

                    force = undefined
                    if draw_settings.force? and draw_settings.force.enabled?
                        force = d3.layout.force().charge(-220).gravity(0.01).linkDistance(100).size(
                            [
                                400
                                400
                            ]
                        ).linkDistance(
                            (d) ->
                                return 100
                        ).on("tick", () =>
                            @tick()
                        )
                    @update(element, state)
                    if draw_settings.force? and draw_settings.force.enabled?
                        force.stop()
                        force.nodes(state.graph.nodes).links(state.graph.links)
                        force.start()
                    @do_autoscale = true
                    @_draw_points()
                    @_draw_links()
                    @force = force
                    # for correct initial handling of livestatus display
                    @set_livestatus_state(props.with_livestatus)

            )

        set_fixed: (dom_node, device, flag) ->
            device.fixed = flag
            fill_color = if flag then "red" else "white"
            $(dom_node).find("circle").attr("fill", fill_color)

        tick: () =>
            # updates all coordinates, attention: not very effective for dragging
            # update
            @d3_element.selectAll(".d3-point")
            .attr("transform", (d) -> return "translate(#{d.x}, #{d.y})")
            @d3_element.selectAll(".d3-livestatus")
            .attr("transform", (d) -> return "translate(#{d.x}, #{d.y})")
            @d3_element.selectAll(".d3-link")
            .attr("x1", (d) -> return d.source.x)
            .attr("y1", (d) -> return d.source.y)
            .attr("x2", (d) -> return d.target.x)
            .attr("y2", (d) -> return d.target.y)
            @d3_element.selectAll(".d3-point")
            if @do_autoscale
                @graph_cmd_scale()

        click: (dom_node, drag_dev) =>
            @set_fixed(dom_node, drag_dev, !drag_dev.fixed)

        _drag_start: (event, ui) ->
            # console.log "ds", event, ui
            true

        _rescale: (point, settings) =>
            point.x -= settings.offset.x
            point.y -= settings.offset.y
            point.x /= settings.zoom.factor
            point.y /= settings.zoom.factor
            return point

        update: () =>
            # scales are not needed
            # scales = @_scales(@element, @state.settings.domain)
            @_update_transform(@element, @state.settings, @props.update_scale_cb)
            @tick()

        _scales: (element, domain) =>
            # hm, to be improved ...
            jq_el = $(element).find("svg")
            width = jq_el.width()
            height = jq_el.height()
            # console.log "domain=", domain
            x = @d3.scale.linear().range([0, width]).domain(domain.x)
            y = @d3.scale.linear().range([height, 0]).domain(domain.y)
            z = @d3.scale.linear().range([5, 20]).domain([1, 10])
            console.log x, y, z
            return {x: x, y: y, z: z}

        _update_transform: (element, settings, update_scale_cb) =>
            g = $(element).find("g#top")
            _t_str = "translate(#{settings.offset.x}, #{settings.offset.y}) scale(#{settings.zoom.factor})"
            g.attr("transform", _t_str)
            update_scale_cb()

        _draw_points: () =>
            # select g
            g = @d3_element.selectAll(".d3-points")

            @device_gen.create(g.selectAll(".d3-point"), @state.graph)

        _draw_links: () =>
            # select g
            g = @d3_element.selectAll(".d3-links")

            @link_gen.create(g.selectAll(".d3-link"), @state.graph)

        _draw_livestatus: () =>
            # select g
            g = @d3_element.select(".d3-livestati")
            ReactDOM.render(
                React.createElement(
                    icswD3DeviceLivestatiReactBurst
                    {
                        nodes: @state.graph.nodes
                        show_livestatus: @livestatus_state
                        monitoring_data: @monitoring_data
                    }
                )
                g[0][0]
            )

        destroy: (element) =>
            console.log "destroy"
            if @force?
                @force.stop()
            icswDeviceLivestatusDataService.destroy(@id)

        graph_cmd_scale: () =>
            _n = @state.graph.nodes
            _xs = (d.x for d in _n)
            _ys = (d.y for d in _n)
            [_min_x, _max_x] = [_.min(_xs), _.max(_xs)]
            [_min_y, _max_y] = [_.min(_ys), _.max(_ys)]

            # add boundaries

            _size_x = _max_x - _min_x
            _size_y = _max_y - _min_y
            _min_x -= _size_x / 20
            _max_x += _size_x / 20
            _min_y -= _size_y / 20
            _max_y += _size_y / 20

            # parse current viewBox settings

            _vbox = _.map($(@element).find("svg")[0].getAttribute("viewBox").split(" "), (elem) -> return parseInt(elem))
            _width = parseInt(_vbox[2])
            _height = parseInt(_vbox[3])

            _fact_x = _width / (_max_x - _min_x)
            _fact_y = _height / (_max_y - _min_y)
            if _fact_x < _fact_y
                # x domain is wider than y domain
                @state.settings.zoom.factor = _fact_x
                @state.settings.offset = {
                    x: -_min_x * _fact_x
                    y: (_height - (_max_y + _min_y) * _fact_x) / 2
                }
            else
                @state.settings.zoom.factor = _fact_y
                @state.settings.offset = {
                    x: (_width - (_max_x + _min_x) * _fact_y) / 2
                    y: -_min_y * _fact_y
                }
            @_update_transform(@element, @state.settings, @props.update_scale_cb)

        set_livestatus_filter: (filter) =>
            state_str = filter.get_filter_state_str()
            if state_str != @filter_state_str
                @filter_state_str = state_str
                if @monitoring_data
                    @props.livestatus_filter.set_monitoring_data(@monitoring_data)
                    @_draw_livestatus()

        set_livestatus_state: (new_state) =>
            # set state of livestatus display
            if new_state != @livestatus_state
                # console.log "set state of livestatus to #{new_state}"
                @livestatus_state = new_state
                if @livestatus_state
                    @start_livestatus()
                else
                    @stop_livestatus()
                    @_draw_livestatus()

        stop_livestatus: () =>
            icswDeviceLivestatusDataService.stop(@id)
            @monitoring_data = undefined

        start_livestatus: () =>
            icswDeviceLivestatusDataService.retain(@id, @state.graph.device_list).then(
                (result) =>
                    result.notifier.promise.then(
                        () ->
                        () ->
                        (generation) =>
                            @monitoring_data = result
                            # console.log "gen", @props.livestatus_filter, @monitoring_data
                            @props.livestatus_filter.set_monitoring_data(@monitoring_data)
                            @_draw_livestatus()
                    )
            )

]).factory("icswNetworkTopologyReactSVGContainer",
[
    "icswNetworkTopologyDrawService",
(
    icswNetworkTopologyDrawService
) ->

    react_dom = ReactDOM
    {div} = React.DOM

    return React.createClass(
        propTypes: {
            # required types
            graph: React.PropTypes.object
            settings: React.PropTypes.object
            scale_changed_cb: React.PropTypes.func
            with_livestatus: React.PropTypes.bool
            livestatus_filter: React.PropTypes.object
            graph_command_cb: React.PropTypes.func
        }
        getInitialState: () ->
            return {
                iteration: 0
            }

        componentDidMount: () ->
            @draw_service = new icswNetworkTopologyDrawService()
            console.log "mount"
            el = ReactDOM.findDOMNode(@)
            @draw_service.create(
                el
                {
                    width: @props.settings.size.width
                    height: @props.settings.size.height
                    update_scale_cb: @update_scale
                    with_livestatus: @props.with_livestatus
                    livestatus_filter: @props.livestatus_filter
                    graph_command_cb: @props.graph_command_cb
                }
                {
                    graph: @props.graph
                    settings: @props.settings
                }
            )

        update_scale: () ->
            @setState({iteration: @state.iteration + 1})
            @props.scale_changed_cb()

        componentWillUnmount: () ->
            console.log "main_umount"
            el = react_dom.findDOMNode(@)
            @draw_service.destroy(el)

        componentDidUpdate: () ->
            # called when the props have changed
            @draw_service.set_livestatus_state(@props.with_livestatus)
            @draw_service.set_livestatus_filter(@props.livestatus_filter)

        render: () ->
            return div({key: "div"})
    )
]).factory("icswLivestatusFilterReactDisplay",
[
    "$q",
(
    $q
) ->
    # display of livestatus filter
    react_dom = ReactDOM
    {div, h4, select, option, p, input, span} = React.DOM

    return React.createClass(
        propTypes: {
            livestatus_filter: React.PropTypes.object
            filter_changed_cb: React.PropTypes.func
        }
        getInitialState: () ->
            return {
                filter_state_str: @props.livestatus_filter.get_filter_state_str()
                display_iter: 0
            }

        componentWillMount: () ->
            @umount_defer = $q.defer()
            @props.livestatus_filter.change_notifier.promise.then(
                () ->
                () ->
                    # will get called when the component unmounts
                (c) =>
                    @setState({display_iter: @state.display_iter + 1})
            )

        componentWillUnmount: () ->
            @props.livestatus_filter.stop_notifying()

        shouldComponentUpdate: (next_props, next_state) ->
            _redraw = false
            if next_state.display_iter != @state.display_iter
                _redraw = true
            else if next_state.filter_state_str != @state.filter_state_str
                _redraw = true
            return _redraw

        render: () ->

            _filter_changed = () =>
                if @props.filter_changed_cb?
                    @props.filter_changed_cb()

            # console.log "r", @props.livestatus_filter
            _lf = @props.livestatus_filter
            _list = []
            _list.push(
                span(
                    {key: "hco"}
                    "# of hosts / services: #{_lf.f_hosts} or #{_lf.n_hosts} / #{_lf.f_services} of #{_lf.n_services}"
                )
                ", filter options: "
            )
            _service_buttons = []
            for entry in _lf.service_state_list
                _service_buttons.push(
                    input(
                        {
                            key: "srvc.#{entry[1]}"
                            type: "button"
                            className: "btn btn-xs " + if _lf.service_states[entry[0]] then entry[4] else "btn-default"
                            value: entry[1]
                            title: entry[3]
                            onClick: (event) =>
                                # _lf.toggle_md(event.target_value)
                                _lf.toggle_service_state(event.target.value)
                                # force redraw
                                @setState({filter_state_str: _lf.get_filter_state_str()})
                                _filter_changed()
                        }
                    )
                )
            _host_buttons = []
            for entry in _lf.host_state_list
                _host_buttons.push(
                    input(
                        {
                            key: "host.#{entry[1]}"
                            type: "button"
                            className: "btn btn-xs " + if _lf.host_states[entry[0]] then entry[4] else "btn-default"
                            value: entry[1]
                            title: entry[3]
                            onClick: (event) =>
                                _lf.toggle_host_state(event.target.value)
                                # force redraw
                                @setState({filter_state_str: _lf.get_filter_state_str()})
                                _filter_changed()
                        }
                    )
                )
            _type_buttons = []
            for entry in _lf.service_type_list
                _type_buttons.push(
                    input(
                        {
                            key: "stype.#{entry[1]}"
                            type: "button"
                            className: "btn btn-xs " + if _lf.service_types[entry[0]] then entry[4] else "btn-default"
                            value: entry[1]
                            title: entry[3]
                            onClick: (event) =>
                                _lf.toggle_service_type(event.target.value)
                                # force redraw
                                @setState({filter_state_str: _lf.get_filter_state_str()})
                                _filter_changed()
                        }
                    )
                )
            _list.push(
                div(
                    {
                        key: "srvc.buttons"
                        className: "btn-group"
                    }
                    _service_buttons
                )
            )
            _list.push(" ")
            _list.push(
                div(
                    {
                        key: "host.buttons"
                        className: "btn-group"
                    }
                    _host_buttons
                )
            )
            _list.push(" ")
            _list.push(
                div(
                    {
                        key: "type.buttons"
                        className: "btn-group"
                    }
                    _type_buttons
                )
            )
            return span(
                {key: "top"}
                _list
            )
    )
]).factory("icswNetworkTopologyReactContainer",
[
    "$q", "ICSW_URLS", "icswSimpleAjaxCall", "icswNetworkTopologyReactSVGContainer",
    "icswLivestatusFilterService", "icswLivestatusFilterReactDisplay",
(
    $q, ICSW_URLS, icswSimpleAjaxCall, icswNetworkTopologyReactSVGContainer,
    icswLivestatusFilterService, icswLivestatusFilterReactDisplay,
) ->
    # Network topology container, including selection and redraw button
    react_dom = ReactDOM
    {div, h4, select, option, p, input, span, button} = React.DOM

    return React.createClass(
        propTypes: {
            # required types
            device_tree: React.PropTypes.object
        }

        getInitialState: () ->
            return {
                draw_type: "all_with_peers"
                loading: false
                with_livestatus: false
                data_present: false
                graph: undefined
                settings: undefined
                graph_id: 0
                redraw_trigger: 0
                livestatus_filter: new icswLivestatusFilterService()
            }

        componentWillUnmount: () ->
            console.log "TopCont umount"
            if @graph_command?
                @graph_command.reject("exit")
            el = react_dom.findDOMNode(@)

        render: () ->
            _load_data = () =>
                @setState({loading: true})
                @load_data()

            _draw_options = [
                ["none", "None"]
                ["all_with_peers", "All peered"]
                ["all", "All devices"]
                ["sel", "selected devices"]
                ["selp1", "selected devices + 1 (next ring)"]
                ["selp2", "selected devices + 2"]
                ["selp3", "selected devices + 3"]
                ["core", "Core network"]
            ]
            _opts = (
                option(
                    {
                        key: "sel_#{key}"
                        value: key
                    }
                    info
                ) for [key, info] in _draw_options
            )
            _list = [
                "Show network topology for "
                select(
                    {
                        key: "inpsel"
                        className: "form-control"
                        defaultValue: "#{@state.draw_type}"
                        style: {width: "200px"}
                        onChange: (event) =>
                            _cur_dt = @state.draw_type
                            _new_dt = event.target.value
                            @setState({draw_type: event.target.value}, () =>
                                if _cur_dt != _new_dt
                                    _load_data()
                            )

                    }
                    _opts
                )
                ", "
                button(
                    {
                        key: "b.redraw"
                        type: "button"
                        className: "btn btn-warning btn-sm fa fa-pencil"
                        onClick: (event) =>
                            _load_data()
                    }
                    " Redraw"
                )
            ]
            _top_list = [
                div(
                    {key: "div0", className: "form-group form-inline"}
                    _list
                )
            ]
            if @state.data_present
                _list.push(
                    button(
                        {
                            key: "b.scale"
                            type: "button"
                            className: "btn btn-success btn-sm fa fa-arrows-alt"
                            onClick: (event) =>
                                @graph_command.notify("scale")
                        }
                        " Scale"
                    )
                )
                _list.push(
                    button(
                        {
                            key: "b.livestatus"
                            type: "button"
                            className: if @state.with_livestatus then "btn btn-success btn-sm fa fa-bar-chart" else "btn btn-default btn-sm fa fa-bar-chart"
                            onClick: (event) =>
                                @setState({with_livestatus: not @state.with_livestatus})
                        }
                        " Livestatus"
                    )
                )
                if false
                    # no longer needed, too much details
                    _top_list.push(
                        h4(
                            {key: "header"}
                            "Settings: #{_.round(@state.settings.offset.x, 3)} / #{_.round(@state.settings.offset.y, 3)} @ #{_.round(@state.settings.zoom.factor, 3)}"
                        )
                    )
                graph_id = @state.graph_id
                _top_list.push(
                    React.createElement(
                        icswNetworkTopologyReactSVGContainer
                        {
                            key: "graph#{graph_id}"
                            graph: @state.graph
                            settings: @state.settings
                            scale_changed_cb: @scale_changed
                            with_livestatus: @state.with_livestatus
                            livestatus_filter: @state.livestatus_filter
                            graph_command_cb: @graph_command_cb
                        }
                    )
                )
            if @state.with_livestatus
                _list.push(
                    React.createElement(
                        icswLivestatusFilterReactDisplay
                        {
                            livestatus_filter: @state.livestatus_filter
                            filter_changed_cb: @filter_changed
                        }
                    )
                )
            if @state.loading
                _list.push(
                    span(
                        {className: "text-danger", key: "infospan"}
                        " Fetching data from server..."
                    )
                )
            return div(
                {key: "top"}
                _top_list
            )

        graph_command_cb: (defer) ->
            @graph_command = defer

        filter_changed: () ->
            @setState({redraw_trigger: @state.redraw_trigger + 1})

        scale_changed: () ->
            @setState({redraw_trigger: @state.redraw_trigger + 1})

        load_data: () ->
            icswSimpleAjaxCall(
                url: ICSW_URLS.NETWORK_JSON_NETWORK
                data:
                    graph_sel: @state.draw_type
                    devices: angular.toJson([])
                dataType: "json"
            ).then(
                (json) =>
                    console.log json
                    @setState(
                        {
                            loading: false
                            data_present: true
                            graph_id: @state.graph_id + 1
                            graph: @props.device_tree.seed_network_graph(json.nodes, json.links)
                            settings: {
                                offset: {
                                    x: 0
                                    y: 0
                                }
                                zoom: {
                                    factor: 1.0
                                }
                                force: {
                                    enabled: true
                                }
                                # domain: {
                                #     x: [0, 10]
                                #     y: [0, 20]
                                # }
                                size: {
                                    width: "95%"
                                    height: "600px"
                                }
                            }
                        }
                    )
            )
)

]).directive("icswTestG",
[
    "ICSW_URLS", "icswDeviceTreeService", "icswNetworkTopologyReactContainer",
(
    ICSW_URLS, icswDeviceTreeService, icswNetworkTopologyReactContainer,
) ->
    return {
        restrict: "EA"
        replace: true
        link: (scope, element, attr) ->
            scope.size = undefined
            scope.$watch("size", (new_val) ->
                # hm, not working
                console.log "new size", new_val
            )
            icswDeviceTreeService.load(scope.$id).then(
                (tree) ->
                    _load_graph(tree)
            )
            _load_graph = (tree) ->
                ReactDOM.render(
                    React.createElement(
                        icswNetworkTopologyReactContainer
                        {
                            device_tree: tree
                        }
                    )
                    element[0]
                )
                scope.$on("$destroy", (d) ->
                    ReactDOM.unmountComponentAtNode(element[0])
                )

    }
])
