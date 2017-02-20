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

# network graphing tool, topology components

angular.module(
    "icsw.livestatus.comp.topology",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "icsw.d3", "ui.select",
        "angular-ladda", "icsw.dragging", "monospaced.mousewheel", "icsw.svg_tools", "icsw.tools", "icsw.tools.table",
        "icsw.livestatus.comp.functions", "icsw.panel_tools",
    ]
).config(["icswLivestatusPipeRegisterProvider", (icswLivestatusPipeRegisterProvider) ->
    icswLivestatusPipeRegisterProvider.add("icswLivestatusTopologySelector", true)
    icswLivestatusPipeRegisterProvider.add("icswLivestatusNetworkTopology", true)
]).factory("icswDeviceLivestatusReactBurst",
[
    "$q", "icswDeviceLivestatusFunctions", "icswBurstDrawParameters",
(
    $q, icswDeviceLivestatusFunctions, icswBurstDrawParameters,
) ->

    react_dom = ReactDOM
    {div, g, text, circle, path} = React.DOM

    return React.createClass(
        propTypes: {
            # required types
            node: React.PropTypes.object
            monitoring_data: React.PropTypes.object
            draw_parameters: React.PropTypes.object
        }
        
        componentDidMount: () ->
            el = react_dom.findDOMNode(@)
            # d3js hack
            el.__data__ = @props.node

        render: () ->
            node = @props.node
            # hack, set special attribute
            @props.draw_parameters.device_idx_filter = node.id
            # should be optmized
            root_node = icswDeviceLivestatusFunctions.build_structured_burst(
                @props.monitoring_data
                @props.draw_parameters
            )

            @props.draw_parameters.device_idx_filter = undefined
            tooltip_obj = @props.draw_parameters.tooltip
            return g(
                {
                    key: "node.#{node.id}"
                    className: "d3-livestatus"
                    id: "#{node.id}"
                    transform: "translate(#{node.x}, #{node.y})"
                }
                (
                    for _path in root_node.element_list
                        path(gen_path_dict(_path, tooltip_obj))
                )
            )

        gen_path_dict = (_path, tooltip_obj) ->
            path_data = _.pickBy(_path, (value, key) -> return not key.match(/\$/))
            path_data.onMouseEnter = (e) ->
                tooltip_obj.show(_path.$$burstNode)
            path_data.onMouseMove = tooltip_obj.pos
            path_data.onMouseLeave = (event) -> tooltip_obj.hide()
            path_data

    )
]).service("icswD3DeviceLivestatiReactBurst",
[
    "svg_tools", "icswDeviceLivestatusReactBurst", "icswBurstDrawParameters",
(
    svg_tools, icswDeviceLivestatusReactBurst, icswBurstDrawParameters,
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

        render: () ->
            _draw_params = new icswBurstDrawParameters(
                inner_radius: 20
                outer_radius: 30
                tooltip: @props.tooltip
            )
            _bursts = []
            if @props.show_livestatus
                idx = 0
                for node in @props.nodes
                    idx++
                    _bursts.push(
                        React.createElement(
                            icswDeviceLivestatusReactBurst
                            {
                                key: "burst.#{idx}"
                                node: node
                                monitoring_data: @props.monitoring_data
                                draw_parameters: _draw_params
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
            .attr("class", "svg-d3circle")
            .attr("cursor", "crosshair")
            _g.append("text")
            .attr("class", "svg-d3text")
            .text(
                (d) ->
                    return d.$$device.full_name
            )
            # <text text-anchor="middle" alignment-baseline="middle" cursor="crosshair">{{ node.name }}</text>
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
            .attr("class", "d3-link svg-d3link")
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
            @device_gen = new icswD3Device(@)
            @link_gen = new icswD3Link(@)
            # pipe for graph commands
            @graph_command_pipe = undefined
            # autoscale during initial force run
            @do_autoscale = false
            # monitoring active (data retained from livestatusdataservice)
            @monitoring_active = false

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
                    .attr("preserveAspectRatio", "xMidYMid slice")
                    .attr("version", "1.1")
                    .attr("onStart", @_drag_start)
                    .attr("pointer-events", "all")
                    .attr("width", "100%")
                    .attr("height", "100%") #$(window).height()-140)
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
                                            # fixed positions
                                            node.fx = cur_point.x
                                            node.fy = cur_point.y
                                            # the velocity-components are important for moving (dragging) nodes
                                            node.vx = 0.0
                                            node.vy = 0.0
                                            @tick()
                                            @reheat_simulation()
                                        dragEnded: (a, b, c, d) =>
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
                    .attr("style", "fill-opacity:0;")
                    _top_g = svg.append("g").attr("id", "top")
                    _top_g.append('g').attr('class', 'd3-links')
                    _top_g.append('g').attr('class', 'd3-livestati')
                    _top_g.append('g').attr('class', 'd3-points')

                    # force settings

                    force = undefined
                    if draw_settings.force? and draw_settings.force.enabled?
                        force = d3.forceSimulation().force(
                            "charge", d3.forceManyBody().strength(-220)
                        ).on("tick", () =>
                            @tick()
                        )
                    @update(element, state)
                    if draw_settings.force? and draw_settings.force.enabled?
                        if state.graph.nodes.length
                            force.nodes(state.graph.nodes).force("link", d3.forceLink(state.graph.links).distance(100))
                            @reheat_simulation()
                    @do_autoscale = true
                    @_draw_points()
                    @_draw_links()
                    @force = force
                    # for correct initial handling of livestatus display
                    @set_livestatus_state(props.with_livestatus)

            )
            # start reacting on monitoring_data changes
            @props.monitoring_data.result_notifier.promise.then(
                (resolve) ->
                    console.log "res", resolve
                (reject) ->
                    console.log "recj", reject
                (gen) =>
                    # force redraw of graph
                    # console.log "gen", gen
                    @_draw_livestatus()
            )

        reheat_simulation: () ->
            if @force?
                @force.alpha(0.2)
                @force.restart()

        set_fixed: (dom_node, device, flag) ->
            device.fixed = flag
            cssclass = if flag then "svg-d3circle-selected" else "svg-d3circle"
            $(dom_node).find("circle").attr("class", cssclass)
            device.vx = 0.0
            device.vy = 0.0
            if device.fixed
                # clear fixed coordinates
                device.fx = device.x
                device.fy = device.y
            else
                device.fx = null
                device.fy = null
                @reheat_simulation()

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
            # console.log x, y, z
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
            g = @d3_element.select(".d3-livestati").nodes()

            ReactDOM.render(
                React.createElement(
                    icswD3DeviceLivestatiReactBurst
                    {
                        nodes: @state.graph.nodes
                        show_livestatus: @livestatus_state
                        monitoring_data: @props.monitoring_data
                        tooltip: @props.tooltip
                    }
                )
                g[0]
            )

        destroy: (element) =>
            if @force?
                @force.stop()
            @stop_livestatus()

        graph_cmd_scale: () =>
            _n = @state.graph.nodes
            if not _n.length
                return
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

            _vbox = _.map(
                $(@element).find("svg")[0].getAttribute("viewBox").split(" "),
                (elem) ->
                    return parseInt(elem)
            )
            _width = parseInt(_vbox[2])
            _height = parseInt(_vbox[3])

            if _size_x == 0 or _size_y == 0
                # catch DivByZero
                _fact_x = 6.0
                _fact_y = 6.0
            else
                _fact_x = _width / (_max_x - _min_x) * 0.9
                _fact_y = _height / (_max_y - _min_y) * 0.9
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
            if @monitoring_active
                # icswDeviceLivestatusDataService.stop(@id)
                @monitoring_active = false

        start_livestatus: () =>
            @monitoring_active = true
            @_draw_livestatus()

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
            graph_command_cb: React.PropTypes.func
            monitoring_data: React.PropTypes.object
        }
        getInitialState: () ->
            return {
                iteration: 0
            }

        componentDidMount: () ->
            @draw_service = new icswNetworkTopologyDrawService()
            el = ReactDOM.findDOMNode(@)
            @draw_service.create(
                el
                {
                    width: @props.settings.size.width
                    height: @props.settings.size.height
                    update_scale_cb: @update_scale
                    with_livestatus: @props.with_livestatus
                    graph_command_cb: @props.graph_command_cb
                    monitoring_data: @props.monitoring_data
                    tooltip: @props.tooltip
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
            # console.log "main_umount"
            el = react_dom.findDOMNode(@)
            @draw_service.destroy(el)

        componentDidUpdate: () ->
            # called when the props have changed
            @draw_service.set_livestatus_state(@props.with_livestatus)

        render: () ->
            return div({key: "div"})
    )
]).factory("icswNetworkTopologyReactContainer",
[
    "$q", "ICSW_URLS", "icswSimpleAjaxCall", "icswNetworkTopologyReactSVGContainer",
(
    $q, ICSW_URLS, icswSimpleAjaxCall, icswNetworkTopologyReactSVGContainer,
) ->
    # Network topology container, including selection and redraw button
    react_dom = ReactDOM
    {div, h4, select, option, p, input, span, button} = React.DOM

    return React.createClass(
        propTypes: {
            # required types
            device_tree: React.PropTypes.object
            monitoring_data: React.PropTypes.object
        }

        getInitialState: () ->
            return {
                loading: false
                with_livestatus: true
                data_present: false
                graph: undefined
                settings: undefined
                graph_id: 0
                redraw_trigger: 0
            }

        componentWillMount: () ->
            @current_dev_pks = []

        componentWillUnmount: () ->
            # console.log "TopCont umount"
            if @graph_command?
                @graph_command.reject("exit")
            el = react_dom.findDOMNode(@)

        render: () ->
            _load_data = () =>
                @setState({loading: true})
                @load_data()

            _list = [
                h4(
                    {
                        key: "heading"
                        className: "pull-left"
                    }
                    "Network Topology"
                )
                button(
                    {
                        key: "b.redraw"
                        type: "button"
                        className: "btn btn-warning btn-sm fa fa-pencil pull-right"
                        onClick: (event) =>
                            _load_data()
                    }
                    " "
                    "Redraw"
                )
            ]
            if @state.data_present
                _list.push(
                    button(
                        {
                            key: "b.scale"
                            type: "button"
                            className: "btn btn-success btn-sm fa fa-arrows-alt pull-right"
                            onClick: (event) =>
                                @graph_command.notify("scale")
                        }
                        " "
                        "Scale"
                    )
                )
                _list.push(
                    button(
                        {
                            key: "b.livestatus"
                            type: "button"
                            className: "btn btn-sm fa fa-bar-chart pull-right " +
                                if @state.with_livestatus then "btn-success" else " btn-default"
                            onClick: (event) =>
                                @setState({with_livestatus: not @state.with_livestatus})
                        }
                        " "
                        "Livestatus"
                    )
                )
                if false
                    # disabled (too much disturbing details)
                    _top_list.push(
                        h4(
                            {key: "header"}
                            "Settings: #{_.round(@state.settings.offset.x, 3)} / #{_.round(@state.settings.offset.y, 3)} @ #{_.round(@state.settings.zoom.factor, 3)}"
                        )
                    )
            if @state.loading
                _list.push(
                    span(
                        {
                            className: "text-danger"
                            key: "infospan"
                        }
                        " Fetching Data from Server ..."
                    )
                )
            _top_list = [
                div(
                    {key: "div0", className: "form-group form-inline", style: {marginBottom: 0}}
                    _list
                )
            ]

            if @state.data_present
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
                            graph_command_cb: @graph_command_cb
                            monitoring_data: @props.monitoring_data
                            tooltip: @props.tooltip
                        }
                    )
                )
            return div(
                {key: "top"}
                _top_list
            )

        graph_command_cb: (defer) ->
            @graph_command = defer

        scale_changed: () ->
            @setState({redraw_trigger: @state.redraw_trigger + 1})

        new_monitoring_data: () ->
            # data received, check for any changes
            @current_dev_pks = _.sortBy((dev.$$icswDevice.idx for dev in @props.monitoring_data.hosts))
            @load_data()

        load_data: () ->
            # fetch the network again because we receive no network
            # connection info from the parent pipe element, to be
            # improved, FIXME, ToDo
            # store previous coordinates
            xy_dict = {}
            if @state.graph
                for node in @state.graph.nodes
                    xy_dict[node.$$device.idx] = {
                        x: node.x
                        y: node.y
                    }
            icswSimpleAjaxCall(
                url: ICSW_URLS.NETWORK_JSON_NETWORK
                data:
                    graph_sel: "sel"
                    devices: angular.toJson(@current_dev_pks)
                dataType: "json"
            ).then(
                (json) =>
                    @setState(
                        {
                            loading: false
                            data_present: true
                            graph_id: @state.graph_id + 1
                            graph: @props.device_tree.seed_network_graph(json.nodes, json.links, xy_dict)
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
                                size: {
                                    width: "95%"
                                    height: "600px"
                                }
                            }
                        }
                    )
            )
    )
]).service("icswLivestatusNetworkTopology",
[
    "$q", "$rootScope", "icswMonLivestatusPipeBase",
(
    $q, $rootScope, icswMonLivestatusPipeBase,
) ->
    class icswLivestatusNetworkTopology extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusNetworkTopology", true, false)
            @set_template(
                '<icsw-device-network-topology icsw-connect-element="con_element" icsw-sub-max-height></icsw-device-network-topology>'
                "Network Topology"
                10
                8
                true  # no_y_scrolling
            )

            @__dp_notify_only_on_devchange = true
            @new_data_notifier = $q.defer()

        new_data_received: (data) ->
            @new_data_notifier.notify(data)

        pipeline_reject_called: (reject) ->
            @new_data_notifier.reject("stop")

]).directive("icswDeviceNetworkTopology",
[
    "ICSW_URLS", "icswDeviceTreeService", "icswNetworkTopologyReactContainer", "$rootScope", "ICSW_SIGNALS",
    "icswTooltipTools",
(
    ICSW_URLS, icswDeviceTreeService, icswNetworkTopologyReactContainer, $rootScope, ICSW_SIGNALS,
    icswTooltipTools,
) ->
    return {
        restrict: "EA"
        replace: true
        scope:
            con_element: "=icswConnectElement"
        link: (scope, element, attrs) ->
            struct = {
                # react element
                react_element: undefined
                # monitoring data
                mon_data: undefined
                # device tree
                device_tree: undefined
            }
            _create_element = () ->
                if not struct.react_element?
                    if struct.mon_data? and struct.device_tree?
                        struct.react_element = ReactDOM.render(
                            React.createElement(
                                icswNetworkTopologyReactContainer
                                {
                                    device_tree: struct.device_tree
                                    monitoring_data: struct.mon_data
                                    tooltip: icswTooltipTools.get_global_struct()
                                }
                            )
                            element[0]
                        )
                        scope.$on("$destroy", () ->
                            ReactDOM.unmountComponentAtNode(element[0])
                        )
            icswDeviceTreeService.load(scope.$id).then(
                (tree) ->
                    struct.device_tree = tree
                    _create_element()
            )
            scope.con_element.new_data_notifier.promise.then(
                (resolved) ->
                (rejected) ->
                    # stop
                (data) ->
                    if not struct.mon_data?
                        struct.mon_data = data
                        _create_element()
                    struct.react_element.new_monitoring_data()
                    $rootScope.$emit(ICSW_SIGNALS("ICSW_SVG_FULLSIZELAYOUT_SETUP"))
            )

    }
]).service("icswLivestatusTopologySelector",
[
    "$q", "$rootScope", "icswMonLivestatusPipeBase",
(
    $q, $rootScope, icswMonLivestatusPipeBase
) ->
    class icswLivestatusTopologySelector extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusTopologySelector", true, true)
            @set_template(
                '<icsw-device-topology-selector icsw-connect-element="con_element"></icsw-device-topology-selector>'
                "Topology Selector"
                3
                1
            )

            # @__dp_notify_only_on_devchange = true
            @__dp_async_emit = true
            @new_data_notifier = $q.defer()

        new_data_received: (data) ->
            @new_data_notifier.notify(data)

        pipeline_reject_called: (reject) ->
            @new_data_notifier.reject("stop")

]).factory("icswDeviceTopologyReactContainer",
[
    "$q", "ICSW_URLS", "icswSimpleAjaxCall", "icswDeviceLivestatusDataService",
    "$timeout", "icswTools", "$rootScope", "ICSW_SIGNALS", "icswActiveSelectionService",
(
    $q, ICSW_URLS, icswSimpleAjaxCall, icswDeviceLivestatusDataService,
    $timeout, icswTools, $rootScope, ICSW_SIGNALS, icswActiveSelectionService,
) ->
    # Network topology container, including selection and redraw button
    react_dom = ReactDOM
    {div, h4, select, option, p, input, span, button} = React.DOM

    return React.createClass(
        propTypes: {
            # required types
            device_tree: React.PropTypes.object
            monitoring_data: React.PropTypes.object
            export_data: React.PropTypes.object
        }

        getInitialState: () ->
            return {
                draw_type: "sel"
                loading: false
                data_present: false
            }

        componentWillMount: () ->
            @struct = {
                # local id, created for every call to start()
                local_id: undefined
                # current fetch pks
                current_json_pks: []
                # data fetch timeout
                fetch_timeout: undefined
                # monitoring_data: undefined
                monitoring_data: undefined
            }

        componentWillUnmount: () ->
            @stop_update()

        render: () ->
            _load_data = () =>
                @setState({loading: true})
                @load_data()

            _draw_options = [
                ["none", "None"]
                ["all_with_peers", "All Peered"]
                ["all", "All Devices"]
                ["sel", "selected Devices"]
                ["selp1", "selected Devices + 1 (next ring)"]
                ["selp2", "selected Devices + 2"]
                ["selp3", "selected Devices + 3"]
                ["inp", "source Devices"]
                ["inpp1", "source Devices + 1 (next ring)"]
                ["inpp2", "source Devices + 2"]
                ["inpp3", "source Devices + 3"]
                ["core", "Core Network"]
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
                "Show Network Topology for "
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
            ]
            if @state.loading
                _list.push(
                    span(
                        {className: "text-danger", key: "infospan"}
                        " Fetching Data from Server ..."
                    )
                )
            return div(
                {key: "div0", className: "form-group form-inline"}
                _list
            )

        scale_changed: () ->
            @setState({redraw_trigger: @state.redraw_trigger + 1})

        new_monitoring_data: () ->
            # data received, check for any changes
            # console.log "nd"
            @load_data()

        stop_update: () ->
            if @struct.fetch_timeout
                $timeout.cancel(@struct.fetch_timeout)
                @struct.fetch_timeout = undefined
            if @struct.monitoring_data?
                @struct.monitoring_data.stop_receive()
                # destroy current fetcher
                icswDeviceLivestatusDataService.destroy(@struct.local_id)

        start_update: () ->
            @stop_update()
            @struct.local_id = icswTools.get_unique_id()
            wait_list = [
                icswDeviceLivestatusDataService.retain(
                    @struct.local_id
                    (@props.device_tree.all_lut[_idx] for _idx in @struct.current_json_pks)
                )
            ]
            $q.all(
                wait_list
            ).then(
                (data) =>
                    @struct.monitoring_data = data[0]
                    @setState({loading: false})
                    @struct.monitoring_data.result_notifier.promise.then(
                        (resolved) ->
                            console.log "Res"
                        (rejected) ->
                            console.log "Rej"
                        (gen) =>
                            @props.export_data.copy_from(@struct.monitoring_data)
                    )
            )
            
        load_data: () ->
            draw_type = @state.draw_type
            # devices currently selected
            if @state.draw_type.match(/sel/)
                # devices from global selection
                _cur_sel = icswActiveSelectionService.get_selection().dev_sel
            else if @state.draw_type.match(/inp/)
                # devices from input
                _cur_sel = (dev.$$icswDevice.idx for dev in @props.monitoring_data.hosts)
                draw_type = _.replace(draw_type, "inp", "sel")
            else
                # something else, no current selection
                _cur_sel = []
            # devices in current monitoring data
            icswSimpleAjaxCall(
                url: ICSW_URLS.NETWORK_JSON_NETWORK
                data:
                    graph_sel: draw_type
                    devices: angular.toJson(_cur_sel)
                dataType: "json"
            ).then(
                (json) =>
                    json_pks = _.sortBy((node.id for node in json.nodes))
                    # console.log "json", json_pks.length
                    if angular.toJson(json_pks) != angular.toJson(@struct.current_json_pks)
                        @struct.current_json_pks = (_id for _id in json_pks)
                        @start_update()
                    else
                        @setState({loading: false})

                    # icswDeviceLivestatusDataService.retain(@struct.local_id, @struct.devices)
                    # console.log "got", json
            )
    )
]).directive("icswDeviceTopologySelector",
[
    "ICSW_URLS", "icswDeviceTreeService", "icswDeviceTopologyReactContainer",
    "icswMonitoringResult",
(
    ICSW_URLS, icswDeviceTreeService, icswDeviceTopologyReactContainer,
    icswMonitoringResult,
) ->
    return {
        restrict: "EA"
        replace: true
        scope:
            con_element: "=icswConnectElement"
        link: (scope, element, attrs) ->
            struct = {
                # react element
                react_element: undefined
                # monitoring data
                mon_data: undefined
                # export data
                export_data: new icswMonitoringResult()
                # device tree
                device_tree: undefined
            }
            _create_element = () ->
                if not struct.react_element?
                    if struct.mon_data? and struct.device_tree?
                        struct.react_element = ReactDOM.render(
                            React.createElement(
                                icswDeviceTopologyReactContainer
                                {
                                    device_tree: struct.device_tree
                                    monitoring_data: struct.mon_data
                                    export_data: struct.export_data
                                }
                            )
                            element[0]
                        )
                        scope.$on("$destroy", () ->
                            ReactDOM.unmountComponentAtNode(element[0])
                        )
            icswDeviceTreeService.load(scope.$id).then(
                (tree) ->
                    struct.device_tree = tree
                    _create_element()
            )
            scope.con_element.new_data_notifier.promise.then(
                (resolved) ->
                (rejected) ->
                    # stop
                (data) =>
                    # console.log "d", data
                    if not struct.mon_data?
                        struct.mon_data = data
                        _create_element()
                        scope.con_element.set_async_emit_data(struct.export_data)
                    struct.react_element.new_monitoring_data()
            )

    }
])
