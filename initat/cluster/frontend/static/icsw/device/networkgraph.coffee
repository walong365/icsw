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
        "draw_mode": "sel"
        "show_livestatus": false
        "devices": []
        "size": {
            width: 1200
            height: 800
        }
        "zoom": {
            factor: 1.0
        }
        "offset": {
            x: 0
            y: 0
        }
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
    update_draw_selections = () ->
        sles = []
        for entry in $scope.raw_draw_selections
            _add = true
            if entry.dr and not $scope.settings.devices.length
                _add = false
            if _add
                sles.push(entry)
        $scope.draw_selections = sles

    $scope.new_devsel = (_dev_sel) ->
        $scope.settings.devices = _dev_sel
        update_draw_selections()
        $scope.redraw_graph()

    $scope.redraw_graph = () ->
        $rootScope.$emit(ICSW_SIGNALS("ICSW_NETWORK_REDRAW_TOPOLOGY"))

    update_draw_selections()

    $scope.ls_filter = new icswLivestatusFilterFactory()
]).directive("icswDeviceNetworkNodeTransform", ["$rootScope", "ICSW_SIGNALS", ($rootScope, ICSW_SIGNALS) ->
    return {
        restrict: "A"
        link: (scope, element, attrs) ->
            scope.$watch(attrs["icswDeviceNetworkNodeTransform"], (transform_node) ->
                $rootScope.$on(ICSW_SIGNALS("ICSW_NETWORK_REDRAW_D3_ELEMENT"), (event) ->
                    if transform_node.x?
                        element.attr("transform", "translate(#{transform_node.x},#{transform_node.y})")
                )
            )
    }
]).directive("icswDeviceNetworkNodeDblClick", ["DeviceOverviewService", (DeviceOverviewService) ->
    return {
        restrict: "A"
        link: (scope, element, attrs) ->
            scope.click_node = null
            scope.double_click = (event) ->
                # beef up node structure
                if scope.click_node?
                    scope.click_node.idx = scope.click_node.id
                    #scope.click_node.device_type_identifier = "D"
                    DeviceOverviewService.NewOverview(event, [scope.click_node])
            scope.$watch(attrs["icswDeviceNetworkNodeDblClick"], (click_node) ->
                scope.click_node = click_node
            )
    }
]).directive("icswDeviceNetworkHostLivestatus", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.network.host.livestatus")
        scope:
             devicepk: "=devicepk"
             ls_filter: "=lsFilter"
        replace: true
    }
]).directive("icswDeviceNetworkHostNode", ["dragging", "$templateCache", (dragging, $templateCache) ->
    return {
        restrict : "EA"
        templateNamespace: "svg"
        replace: true
        scope:
            node: "=node"
        template: $templateCache.get("icsw.device.network.host.node")
        link : (scope, element, attrs) ->
            scope.stroke_width = 1
            scope.focus = true
            scope.mousedown = false
            scope.$watch("node", (new_val) ->
                scope.node = new_val
                scope.fill_color = "white"
                scope.stroke_width = Math.max(Math.min(new_val.num_nds, 3), 1)
                scope.stroke_color = if new_val.num_nds then "grey" else "red"
            )
            scope.mouse_click = () ->
                if scope.node.ignore_click
                    scope.node.ignore_click = false
                else
                    scope.node.fixed = !scope.node.fixed
                    scope.fill_color = if scope.node.fixed then "red" else "white"
            scope.mouse_enter = () ->
                scope.focus = true
                scope.stroke_width++
            scope.mouse_leave = () ->
                scope.focus = false
                scope.mousedown = false
                scope.stroke_width--
    }
]).directive("icswDeviceNetworkHostLink", ["$templateCache", "$rootScope", "ICSW_SIGNALS", ($templateCache, $rootScope, ICSW_SIGNALS) ->
    return {
        restrict : "EA"
        templateNamespace: "svg"
        replace: true
        scope: 
            link: "=link"
        template: $templateCache.get("icsw.device.network.host.link")
        link : (scope, element, attrs) ->
            scope.$watch("link", (new_val) ->
                scope.link = new_val
                #scope.stroke_width = if new_val.num_nds then new_val.num_nds else 1
                #scope.stroke_color = if new_val.num_nds then "grey" else "red"
            )
            $rootScope.$on(ICSW_SIGNALS("ICSW_NETWORK_REDRAW_D3_ELEMENT"), (event) ->
                element.attr("x1", scope.link.x1c)
                element.attr("y1", scope.link.y1c)
                element.attr("x2", scope.link.x2c)
                element.attr("y2", scope.link.y2c)
            )
    }
]).directive("icswDeviceNetworkGraph", ["$templateCache", "msgbus", ($templateCache, msgbus) ->
    return {
        restrict : "EA"
        replace: true
        scope:
            ls_filter: "=lsFilter"
            draw_settings: "=drawSettings"
        template: $templateCache.get("icsw.device.network.graph")
        link: (scope, element, attrs) ->
            if not attrs["devicepk"]?
                msgbus.emit("devselreceiver")
                msgbus.receive("devicelist", scope, (name, args) ->
                    scope.new_devsel(args[1])
                )
            scope.prev_size = {width:100, height:100}
            scope.get_element_dimensions = () ->
                return {"h": element.height(), "w": element.width()}
            scope.$watch(
                scope.get_element_dimensions
                (new_val) ->
                    # needed ? why ?
                    scope.prev_size = {width: scope.draw_settings.size.width, height:scope.draw_settings.size.height}
                    #scope.size.width = new_val["w"]
                    #scope.size.height = new_val["h"]
                    #console.log scope.prev_size, scope.size
                true
            )
            element.bind("resize", () ->
                console.log "Resize NetworkGraph"
                scope.$apply()
            )
    }
]).directive("icswDeviceNetworkGraphInner",
[
    "d3_service", "dragging", "svg_tools", "blockUI", "ICSW_URLS", "$templateCache",
    "icswSimpleAjaxCall", "ICSW_SIGNALS", "$rootScope",
(
    d3_service, dragging, svg_tools, blockUI, ICSW_URLS, $templateCache,
    icswSimpleAjaxCall, ICSW_SIGNALS, $rootScope
) ->
    return {
        restrict : "EA"
        templateNamespace: "svg"
        replace: true
        template: $templateCache.get("icsw.device.network.graph.inner")
        scope:
            ls_filter: "=lsFilter"
            draw_settings: "=drawSettings"
        link : (scope, element, attrs) ->
            scope.cur_scale = 1.0
            scope.cur_trans = [0, 0]
            scope.nodes = []
            scope.links = []
            d3_service.d3().then(
                (d3) ->
                    scope.svg_el = element[0]
                    svg = d3.select(scope.svg_el)
                    #svg.attr("height", scope.size.height)
                    scope.force = d3.layout.force().charge(-220).gravity(0.02).linkDistance(150).size([scope.draw_settings.size.width, scope.draw_settings.size.height])
                      .linkDistance((d) -> return 100).on("tick", scope.tick)
                    # scope.fetch_data()
            )
            $rootScope.$on(ICSW_SIGNALS("ICSW_NETWORK_REDRAW_TOPOLOGY"), (event) ->
                blockUI.start(
                    "loading, please wait..."
                )
                console.log scope.draw_settings
                icswSimpleAjaxCall(
                    url: ICSW_URLS.NETWORK_JSON_NETWORK
                    data:
                        graph_sel: scope.draw_settings.draw_mode
                        devices: angular.toJson((dev.idx for dev in scope.draw_settings.devices))
                    dataType: "json"
                ).then(
                    (json) ->
                        blockUI.stop()
                        scope.json_data = json
                        scope.draw_graph()
                )
            )
            scope.draw_graph = () ->
                scope.force.nodes(scope.json_data.nodes).links(scope.json_data.links)
                scope.node_lut = {}
                scope.nodes = scope.json_data.nodes
                scope.links = scope.json_data.links
                for node in scope.nodes
                    node.fixed = false
                    node.dragging = false
                    node.ignore_click = false
                    scope.node_lut[node.id] = node
                $rootScope.$emit(ICSW_SIGNALS("ICSW_NETWORK_REDRAW_D3_ELEMENT"))
                scope.force.start()
            scope.find_element = (s_target) ->
                if svg_tools.has_class_svg(s_target, "draggable")
                    return s_target
                s_target = s_target.parent()
                if s_target.length
                    return scope.find_element(s_target)
                else
                    return null
            scope.mouse_down = (event) ->
                drag_el = scope.find_element($(event.target))
                if drag_el.length
                    el_scope = angular.element(drag_el[0]).scope()
                else
                    el_scope = null
                if el_scope
                    drag_el_tag = drag_el.prop("tagName")
                    if drag_el_tag == "svg"
                        dragging.start_drag(event, 0, {
                            dragStarted: (x, y, event) ->
                                scope.sx = x - scope.draw_settings.offset.x
                                scope.sy = y - scope.draw_settings.offset.y
                            dragging: (x, y) ->
                                scope.draw_settings.offset = {
                                   x: x - scope.sx
                                   y: y - scope.sy
                                }
                            dragEnded: () ->
                        })
                    else
                        drag_node = el_scope.node
                        scope.redraw_nodes++
                        dragging.start_drag(event, 1, {
                            dragStarted: (x, y, event) ->
                                drag_node.dragging = true
                                drag_node.fixed = true
                                drag_node.ignore_click = true
                                scope.start_drag_point = scope.rescale(
                                    svg_tools.get_abs_coordinate(scope.svg_el, x, y)
                                )
                                scope.force.start()
                            dragging: (x, y) ->
                                cur_point = scope.rescale(
                                    svg_tools.get_abs_coordinate(scope.svg_el, x, y)
                                )
                                drag_node.x = cur_point.x
                                drag_node.y = cur_point.y
                                drag_node.px = cur_point.x
                                drag_node.py = cur_point.y
                                scope.tick()
                            dragEnded: () ->
                                drag_node.dragging = false
                        })
            scope.rescale = (point) ->
                point.x -= scope.draw_settings.offset.x
                point.y -= scope.draw_settings.offset.y
                point.x /= scope.draw_settings.zoom.factor
                point.y /= scope.draw_settings.zoom.factor
                return point
            scope.mouse_wheel = (event, delta, deltax, deltay) ->
                scale_point = scope.rescale(
                    svg_tools.get_abs_coordinate(scope.svg_el, event.originalEvent.clientX, event.originalEvent.clientY)
                )
                prev_factor = scope.draw_settings.zoom.factor
                if delta > 0
                    scope.draw_settings.zoom.factor *= 1.05
                else
                    scope.draw_settings.zoom.factor /= 1.05
                scope.draw_settings.offset.x += scale_point.x * (prev_factor - scope.draw_settings.zoom.factor)
                scope.draw_settings.offset.y += scale_point.y * (prev_factor - scope.draw_settings.zoom.factor)
                event.stopPropagation()
                event.preventDefault()
            scope.tick = () ->
                #console.log "t"
                for node in scope.force.nodes()
                    t_node = scope.node_lut[node.id]
                    #if t_node.fixed
                        #console.log "*", t_node
                    #    t_node.x = node.x
                    #    t_node.y = node.y
                for link in scope.links
                    s_node = scope.node_lut[link.source.id]
                    d_node = scope.node_lut[link.target.id]
                    link.x1c = s_node.x
                    link.y1c = s_node.y
                    link.x2c = d_node.x
                    link.y2c = d_node.y
                $rootScope.$emit(ICSW_SIGNALS("ICSW_NETWORK_REDRAW_D3_ELEMENT"))
    }
]).service("icswD3Elementx", ["svg_tools", (svg_tools) ->
    class icswD3Elementx
        constructor: () ->
        create: (selector, data) ->
            ds = selector.data(data, (d) -> return d.id)
            ds.enter().append("circle").attr("class", "d3-point draggable")
            ds.attr('cx', (d) -> return d.x)
            .attr('cy', (d) -> return d.y)
            .attr('r', (d) -> return d.r)
            .attr("id", (d) -> return d.id)
            return ds
            # EXIT
            # point.exit().remove()


]).service("icswD3Element",
[
    "svg_tools",
(
    svg_tools
) ->
    class icswD3Element
        constructor: () ->
        create: (selector, data) ->
            console.log "data=", data
            ds = selector.data(data, (d) -> return d.id)
            ds.enter().append("circle").attr("class", "d3-point draggable")
            ds.attr('cx', (d) -> return d.x)
            .attr('cy', (d) -> return d.y)
            .attr('r', (d) -> return d.r)
            .attr("id", (d) -> return d.id)
            return ds
            # EXIT
            # point.exit().remove()

]).service("icswD3Link",
[
    "svg_tools",
(
    svg_tools
) ->
    class icswD3Link
        constructor: () ->
        create: (selector, link, points) ->
            console.log "link=", link
            _id = 0
            ds = selector.data(link, (d) ->
                _id++
                return _id
            )
            ds.enter().append("line")
            .attr("class", "d3-link")
            .attr("stroke", "#ff7788")
            .attr("stroke-width", "4")
            .attr("opacity", "1")
            #ds.attr('x1', (d) -> return points[d.source].x)
            #.attr('y1', (d) -> return points[d.source].y)
            #.attr('x2', (d) -> return points[d.target].x)
            #.attr("y2", (d) -> return points[d.target].y)
            #.attr("id", (d) -> return d.id)
            return ds
            # EXIT
            # point.exit().remove()

]).service("icswD3Test",
[
    "$templateCache", "d3_service", "svg_tools", "dragging", "mouseCaptureFactory",
    "icswTools", "icswD3Element", "icswD3Link",
(
    $templateCache, d3_service, svg_tools, dragging, mouseCaptureFactory,
    icswTools, icswD3Element, icswD3Link,
) ->
    class icswD3Test

        constructor: () ->

        create: (element, props, state, update_scale_fn) =>
            @element = element
            draw_settings = state.settings
            _lut = {}
            for node in state.data
                _lut[node.id] = node
            d3_service.d3().then(
                (d3) =>
                    @d3 = d3
                    svg = d3.select(element).append("svg")
                    .attr('class', 'draggable')
                    .attr('width', props.width)
                    .attr('height', props.height)
                    .attr("onStart", @_drag_start)
                    .attr("pointer-events", "all")
                    $(element).mousedown(
                        (event) =>
                            mouseCaptureFactory.register_element(element)
                            _find_element = (s_target) ->
                                # iterative search
                                if svg_tools.has_class_svg(s_target, "draggable")
                                    return s_target
                                s_target = s_target.parent()
                                if s_target.length
                                    return _find_element(s_target)
                                else
                                    return null
                            drag_el = _find_element($(event.target))
                            if drag_el? and drag_el.length
                                drag_el = $(drag_el[0])
                                drag_el_tag = drag_el.prop("tagName")
                                if drag_el_tag == "svg"
                                    _sx = 0
                                    _sy = 0
                                    dragging.start_drag(event, 0, {
                                        dragStarted: (x, y, event) =>
                                            _sx = x - draw_settings.offset.x
                                            _sy = y - draw_settings.offset.y
                                        dragging: (x, y) =>
                                            draw_settings.offset = {
                                               x: x - _sx
                                               y: y - _sy
                                            }
                                            @_update_transform(element, draw_settings, update_scale_fn)
                                        dragEnded: () =>
                                    })
                                else
                                    drag_node = drag_el[0]
                                    start_drag_point = undefined
                                    dragging.start_drag(event, 1, {
                                        dragStarted: (x, y, event) =>
                                            svg = $(element).find("svg")[0]
                                            start_drag_point = @_rescale(
                                                svg_tools.get_abs_coordinate(svg, x, y)
                                                draw_settings
                                            )
                                            console.log start_drag_point
                                        dragging: (x, y) =>
                                            svg = $(element).find("svg")[0]
                                            cur_point = @_rescale(
                                                svg_tools.get_abs_coordinate(svg, x, y)
                                                draw_settings
                                            )
                                            node = _lut[parseInt($(drag_node).attr("id"))]
                                            node.x = cur_point.x
                                            node.y = cur_point.y
                                            node.px = cur_point.x
                                            node.py = cur_point.y
                                            @tick()
                                        dragEnded: () =>
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
                            @_update_transform(element, draw_settings, update_scale_fn)
                            event.stopPropagation()
                            event.preventDefault()
                    )
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
                    # reactangle around drawing area
                    svg.append("rect")
                    .attr("x", "0")
                    .attr("y", "0")
                    .attr("width", "100%")
                    .attr("height", "100%")
                    .attr("style", "stroke:black; stroke-width:2px; fill-opacity:0;")
                    svg.append('g').attr('class', 'd3-points')
                    svg.append('g').attr('class', 'd3-links')
                    @update(element, state, update_scale_fn)
                    if draw_settings.force? and draw_settings.force.enabled?
                        force.stop()
                        force.nodes(state.data).links(state.links)
                        force.start()
            )

        tick: () =>
            # updates all coordinates, attention: not very effective for dragging
            # update
            @d3.select(@element).selectAll(".d3-point").attr(
                "cx", (d) -> return d.x
            ).attr(
                "cy", (d) -> return d.y
            )
            @d3.select(@element).selectAll(".d3-link")
            .attr("x1", (d) -> return d.source.x)
            .attr("y1", (d) -> return d.source.y)
            .attr("x2", (d) -> return d.target.x)
            .attr("y2", (d) -> return d.target.y)

        _drag_start: (event, ui) ->
            console.log "ds", event, ui

        _rescale: (point, settings) =>
            point.x -= settings.offset.x
            point.y -= settings.offset.y
            point.x /= settings.zoom.factor
            point.y /= settings.zoom.factor
            return point

        update: (element, state, update_scale_fn) =>
            console.log "up", element, state
            scales = @_scales(element, state.domain)
            @_draw_points(element, scales, state.data)
            @_draw_links(element, scales, state.links, state.data)
            @_update_transform(element, state.settings, update_scale_fn)

        _scales: (element, domain) =>
            # hm, to be improved ...
            jq_el = $(element).find("svg")
            width = jq_el.width()
            height = jq_el.height()
            x = @d3.scale.linear().range([0, width]).domain(domain.x)
            y = @d3.scale.linear().range([height, 0]).domain(domain.y)
            z = @d3.scale.linear().range([5, 20]).domain([1, 10])
            return {x: x, y: y, z: z}

        _update_transform: (element, settings, update_scale_fn) =>
            g = $(element).find("g")
            _t_str = "translate(#{settings.offset.x}, #{settings.offset.y}) scale(#{settings.zoom.factor})"
            g.attr("transform", _t_str)
            update_scale_fn()

        _draw_points: (element, scales, points) =>
            _pc = new icswD3Element()
            # select g
            g = @d3.select(element).selectAll(".d3-points")

            ds_sel = _pc.create(g.selectAll(".d3-point"), points)
            ds_sel.exit().remove()

        _draw_links: (element, scales, links, points) =>
            _pc = new icswD3Link()
            # select g
            g = @d3.select(element).selectAll(".d3-links")

            ds_sel = _pc.create(g.selectAll(".d3-link"), links, points)
            ds_sel.exit().remove()

        destroy: (element) =>
            console.log "destroy"
]).factory("icswD3T2", ["icswD3Test", (icswD3Test) ->
    my_test = new icswD3Test()
    react_dom = ReactDOM
    {div, h4} = React.DOM
    test = React.createClass(
        propTypes: {
            # required types
            data: React.PropTypes.array
            links: React.PropTypes.array
            domain: React.PropTypes.object
            settings: React.PropTypes.object
        }
        componentDidMount: () ->
            el = ReactDOM.findDOMNode(@)
            my_test.create(
                el
                {
                    width: "80%"
                    height: "300px"
                }
                @get_chart_state()
                @update_scale
            )
        componentDidUpdate: () ->
            console.log "comp update"
        update_scale: () ->
            @forceUpdate()
        get_chart_state: () ->
            return {
                data: @props.data
                links: @props.links
                domain: @props.domain
                settings: @props.settings
            }
        componentWillUnmount: () ->
            console.log "main_umount"
            el = react_dom.findDOMNode(@)
            my_test.destroy(el)
        render: () ->
            return div(
                {key: "top"}
                [
                    h4(
                        {key: "header"}
                        "Header #{@props.settings.zoom.factor} #{@props.settings.offset.x} / #{@props.settings.offset.y}"
                    )
                    div(
                        {key: "div", className: "chart"}
                    )
                ]
            )
    )
    return test
]).directive("icswTestG",
[
    "icswD3T2", "ICSW_URLS", "icswSimpleAjaxCall",
(
    icswD3T2, ICSW_URLS, icswSimpleAjaxCall
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
            icswSimpleAjaxCall(
                url: ICSW_URLS.NETWORK_JSON_NETWORK
                data:
                    graph_sel: "all"
                    devices: angular.toJson([])
                dataType: "json"
            ).then(
                (json) ->
                    idx = 0
                    idy = 0
                    for node in json.nodes
                        node.x = idx
                        node.y = idy
                        node.r = 10
                        idx += 10
                        idy += 25
                        if idy > 100
                            idy = 0
                        # console.log "node=", node
                    console.log "N=", json.nodes
                    console.log "L=", json.links
                    _settings = {
                        data: json.nodes
                        links: json.links
                        domain: {x: [0, 10], y: [0,20]}
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
                        }
                    }
                    _render = () ->
                        ReactDOM.render(
                            React.createElement(
                                icswD3T2
                                _settings
                            )
                            element[0]
                        )
                    _render()
            )
            scope.$on("$destroy", (d) ->
                ReactDOM.unmountComponentAtNode(element[0])
            )

    }
])
