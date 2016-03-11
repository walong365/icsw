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
            glob_to_local = event.target.getTransformToElement(scope.svg_el)
            second = first.matrixTransform(glob_to_local.inverse())
            return second
    }
)

angular.module(
    "icsw.mouseCapture",
    []
).factory('mouseCaptureFactory', ["$rootScope", ($rootScope) ->
    $element = document
    mouse_capture_config = null
    mouse_move = (event) ->
        if mouse_capture_config and mouse_capture_config.mouse_move
            mouse_capture_config.mouse_move(event)
            $rootScope.$digest()
    mouse_up = (event) ->
        if mouse_capture_config and mouse_capture_config.mouse_up
            mouse_capture_config.mouse_up(event)
            $rootScope.$digest()
    return {
        register_element: (element) ->
            $element = element
        acquire: (event, config) ->
            this.release()
            mouse_capture_config = config
            $element.mousemove(mouse_move)
            $element.mouseup(mouse_up)
        release: () ->
            if mouse_capture_config
                if mouse_capture_config.released
                    mouse_capture_config.released()
                mouse_capture_config = null;
                $element.unbind("mousemove", mouse_move)
                $element.unbind("mouseup", mouse_up)
    }
]).directive('icswMouseCapture', () ->
    return {
        restrict: "A"
        controller: ["$scope", "$element", "mouseCaptureFactory", ($scope, $element, mouseCaptureFactory) ->
            mouseCaptureFactory.register_element($element)
        ]
    }
)

angular.module(
    "icsw.dragging",
    [
        "icsw.mouseCapture"
    ]
).factory("dragging", ["$rootScope", "mouseCaptureFactory", ($rootScope, mouseCaptureFactory) ->
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
            console.log "XXX", scope.ls_filter, scope.draw_settings
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
    "d3_service", "dragging", "svg_tools", "blockUI", "ICSW_URLS", "$templateCache", "icswSimpleAjaxCall", "ICSW_SIGNALS", "$rootScope",
(
    d3_service, dragging, svg_tools, blockUI, ICSW_URLS, $templateCache, icswSimpleAjaxCall, ICSW_SIGNALS, $rootScope
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
                    url      : ICSW_URLS.NETWORK_JSON_NETWORK
                    data     :
                        "graph_sel" : scope.draw_settings.draw_mode
                        "devices": angular.toJson((dev.idx for dev in scope.draw_settings.devices))
                    dataType : "json"
                ).then(
                    (json) ->
                        blockUI.stop()
                        scope.json_data = json
                        scope.draw_graph()
                )
            )
            scope.draw_graph = () ->
                scope.iter = 0
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
            scope.iter = 0
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
                scope.iter++
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
])
