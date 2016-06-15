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

angular.module(
    "icsw.livestatus.livestatus",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.router",
    ]
).config(["$stateProvider", "icswRouteExtensionProvider", ($stateProvider, icswRouteExtensionProvider) ->
    $stateProvider.state(
        "main.livestatus", {
            url: "/livestatus/all"
            template: '<icsw-device-livestatus icsw-sel-man="0"></icsw-device-livestatus>'
            icswData: icswRouteExtensionProvider.create
                pageTitle: "Monitoring dashboard"
                licenses: ["monitoring_dashboard"]
                rights: ["mon_check_command.show_monitoring_dashboard"]
                menuEntry:
                    menukey: "stat"
                    icon: "fa-dot-circle-o"
                    ordering: 20
                dashboardEntry:
                    size_x: 4
                    size_y: 4
        }
    )
]).controller("icswDeviceLiveStatusCtrl",
[
    "$scope", "$compile", "$templateCache", "Restangular",
    "$q", "$timeout", "icswTools", "ICSW_URLS", "icswSimpleAjaxCall",
    "icswDeviceLivestatusDataService", "icswCachingCall", "icswLivestatusFilterService",
    "icswDeviceTreeService", "icswMonLivestatusPipeConnector",
(
    $scope, $compile, $templateCache, Restangular,
    $q, $timeout, icswTools, ICSW_URLS, icswSimpleAjaxCall,
    icswDeviceLivestatusDataService, icswCachingCall, icswLivestatusFilterService,
    icswDeviceTreeService, icswMonLivestatusPipeConnector,
) ->
    # top level controller of monitoring dashboard

    $scope.struct = {
        # connector
        # connector: new icswMonLivestatusPipeConnector("test", angular.toJson({"icswLivestatusDataSource": [{"icswLivestatusFilterService": [{"icswLivestatusCategoryFilter": [{"icswLivestatusFullBurst": []}]}]}]}))
        # connector: new icswMonLivestatusPipeConnector("test", angular.toJson({"icswLivestatusDataSource": [{"icswLivestatusFullBurst": []}]}))
        connector: new icswMonLivestatusPipeConnector(
            "test"
            angular.toJson(
                {
                    "icswLivestatusDataSource": [
                        {
                            "icswLivestatusFilterService": [
                                {
                                    "icswLivestatusLocationDisplay": []
                                }
                                {
                                    "icswLivestatusCategoryFilter": [
                                        {
                                            "icswLivestatusMapDisplay": []
                                        }
                                    ]
                                }
                                {
                                    "icswLivestatusFilterService": [
                                        {
                                            "icswLivestatusTabularDisplay": []
                                        }
                                    ]
                                }
                            ]
                        }
                        {
                            "icswLivestatusFullBurst": []
                        }
                        {
                            "icswLivestatusFilterService": [
                                {
                                    "icswLivestatusLocationDisplay": []
                                }
                            ]
                        }
                    ]
                }
            )
        )
    }

    $scope.new_devsel = (_dev_sel) ->
        $scope.struct.connector.new_devsel(_dev_sel)

    $scope.$on("$destroy", () ->
        $scope.struct.connector.close()
    )

]).factory("icswBurstServiceDetail",
[
    "$q",
(
    $q,
) ->
    {div, ul, li, h3, span} = React.DOM
    return React.createClass(
        propTypes: {
            service: React.PropTypes.object
        }

        render: () ->
            _srvc = @props.service
            if _srvc
                if _srvc.$$dummy
                    _div_list = h3(
                        {key: "header"}
                        "Dummy segment"
                    )
                else
                    _ul_list = []
                    if _srvc.$$ct in ["system", "devicegroup"]
                        if _srvc.$$ct == "system"
                            _obj_name = "System"
                        else
                            _obj_name = _.capitalize(_srvc.$$ct) + " " + _srvc.display_name
                        _ul_list.push(
                            li(
                                {key: "li.state", className: "list-group-item"}
                                [
                                    "State"
                                    span(
                                        {key: "state.span", className: "pull-right #{_srvc.$$icswStateTextClass}"}
                                        _srvc.$$icswStateString
                                    )
                                ]
                            )
                        )
                    if _srvc.$$ct in ["device", "service"]
                        if _srvc.$$ct == "service"
                            _host = _srvc.$$host_mon_result
                            _obj_name = _.capitalize(_srvc.$$ct) + " " + _srvc.display_name
                        else
                            _host = _srvc
                            _obj_name = _.capitalize(_srvc.$$ct) + " " + _host.$$icswDevice.full_name
                        _path_span = [
                            _host.$$icswDeviceGroup.name
                            " "
                            span(
                                {key: "path.span2", className: "fa fa-arrow-right"}
                            )
                            " "
                            _host.$$icswDevice.full_name
                        ]
                        if _srvc.$$ct == "service"
                            _path_span = _path_span.concat(
                                [
                                    " "
                                    span(
                                        {key: "path.span3", className: "fa fa-arrow-right"}
                                    )
                                    " "
                                    _srvc.display_name
                                ]
                            )
                        _ul_list.push(
                            li(
                                {key: "li.path", className: "list-group-item"}
                                [
                                    "Path"
                                    span(
                                        {key: "path.span", className: "pull-right"}
                                        _path_span
                                    )
                                ]
                            )
                        )
                        # state li
                        _ul_list.push(
                            li(
                                {key: "li.state2", className: "list-group-item"}
                                [
                                    "State"
                                    span(
                                        {key: "state.span", className: "pull-right"}
                                        "#{_srvc.$$icswStateTypeString} #{_srvc.$$icswCheckTypeString}, "
                                        span(
                                            {key: "state.span2", className: _srvc.$$icswStateTextClass}
                                            _srvc.$$icswStateString
                                        )
                                        ", "
                                        span(
                                            {key: "state.span3", className: "label #{_srvc.$$icswAttemptLabelClass}"}
                                            _srvc.$$icswAttemptInfo
                                        )
                                    )
                                ]
                            )
                        )
                        # last check / last change
                        _ul_list.push(
                            li(
                                {key: "li.lclc", className: "list-group-item"}
                                [
                                    "last check / last change"
                                    span(
                                        {key: "lclc.span", className: "pull-right"}
                                        "#{_srvc.$$icswLastCheckString } / #{_srvc.$$icswLastStateChangeString}"
                                    )
                                ]
                            )
                        )
                        if _srvc.$$ct == "service"
                            # categories
                            _ul_list.push(
                                li(
                                    {key: "li.cats", className: "list-group-item"}
                                    [
                                        "Categories"
                                        span(
                                            {key: "cats.span", className: "pull-right"}
                                            "#{_srvc.$$icswCategories}"
                                        )
                                    ]
                                )
                            )
                        # output
                        _ul_list.push(
                            li(
                                {key: "li.output", className: "list-group-item"}
                                [
                                    "Output"
                                    span(
                                        {key: "output.span", className: "pull-right"}
                                        _srvc.plugin_output or "N/A"
                                    )
                                ]
                            )
                        )
                    _div_list = [
                        h3(
                            {key: "header"}
                            _obj_name
                        )
                        ul(
                            {key: "ul", className: "list-group"}
                            _ul_list
                        )
                    ]
            else
                _div_list = h3(
                    {key: "header"}
                    "Nothing selected"
                )
            return div(
                {key: "top"}
                _div_list
            )
    )
]).factory("icswBurstReactSegment",
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
            set_focus: React.PropTypes.func
            clear_focus: React.PropTypes.func
        }

        render: () ->
            _path_el = @props.element
            _color = _path_el.fill
            # if @state.focus
            #    _color = "#445566"

            # focus element
            _g_list = []
            _segment = {
                key: _path_el.key
                d: _path_el.d
                fill: _color
                stroke: _path_el.stroke
                strokeWidth: _path_el.strokeWidth
                onMouseEnter: @on_mouse_enter
                onMouseLeave: @on_mouse_leave
            }
            return path(_segment)

        on_mouse_enter: (event) ->
            # console.log "me"
            if @props.element.$$segment?
                @props.set_focus(@props.element.$$segment)

        on_mouse_leave: (event) ->
            # @props.clear_focus()
            # console.log "ml"
            # @setState({focus: false})
    )
]).factory("icswBurstReactSegmentText",
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
            if _path_el.$$segment? and not _path_el.$$segment.placeholder
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
]).factory("icswDeviceLivestatusBurstReactContainer",
[
    "$q", "ICSW_URLS", "icswSimpleAjaxCall", "icswNetworkTopologyReactSVGContainer",
    "icswDeviceLivestatusFunctions", "icswBurstDrawParameters", "icswBurstReactSegment",
    "icswBurstServiceDetail", "icswBurstReactSegmentText",
(
    $q, ICSW_URLS, icswSimpleAjaxCall, icswNetworkTopologyReactSVGContainer,
    icswDeviceLivestatusFunctions, icswBurstDrawParameters, icswBurstReactSegment,
    icswBurstServiceDetail, icswBurstReactSegmentText,
) ->
    # Network topology container, including selection and redraw button
    react_dom = ReactDOM
    {div, g, text, line, polyline, path, svg, h3} = React.DOM
    return React.createClass(
        propTypes: {
            # required types
            monitoring_data: React.PropTypes.object
            draw_parameters: React.PropTypes.object
        }

        componentDidMount: () ->

        getInitialState: () ->
            return {
                # to trigger redraw
                draw_counter: 0
                focus_element: undefined
            }

        new_monitoring_data_result: () ->
            # force recalc of burst, todo: incremental root_node update
            @root_node = undefined
            # not very elegant
            @clear_focus()
            @trigger_redraw()

        trigger_redraw: () ->
            @setState(
                {
                    draw_counter: @state.draw_counter + 1
                }
            )

        set_focus: (ring_el) ->
            @clear_focus()
            ring_el.set_focus()
            @setState({focus_element: ring_el})

        clear_focus: () ->
            if @root_node?
                @root_node.clear_foci()
            @setState({focus_element: undefined})

        render: () ->
            [_outer_width, _outer_height] = [0, 0]
            if @burst_element? and @burst_element.width()
                [_outer_width, _outer_height] = [@burst_element.width(), @burst_element.height()]
            # check if burst is interactive
            _ia = @props.draw_parameters.is_interactive
            if not @root_node?
                # console.log "rnd"
                @root_node = icswDeviceLivestatusFunctions.build_structured_burst(@props.monitoring_data, @props.draw_parameters)
            # console.log _outer_width, _outer_height
            root_node = @root_node
            # if _outer_width
            #    _outer = _.min([_outer_width, _outer_height])
            # else
            @props.draw_parameters.do_layout()
            _outer = @props.draw_parameters.outer_radius
            # console.log _outer
            if _ia
                # interactive, pathes have mouseover and click handler
                _g_list = (
                    React.createElement(
                        icswBurstReactSegment,
                        {
                            key: _element.key
                            element: _element
                            set_focus: @set_focus
                            clear_focus: @clear_focus
                            draw_parameters: @props.draw_parameters
                        }
                    ) for _element in root_node.element_list
                )
                for _element in root_node.element_list
                    if _element.$$segment?
                        _seg = _element.$$segment
                        if _seg.show_legend
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
                _g_list = (path(_element) for _element in root_node.element_list)
            # _g_list = []

            _svg = svg(
                {
                    key: "svg.top"
                    width: "#{@props.draw_parameters.total_width}px"
                    height: "#{@props.draw_parameters.total_height}px"
                    "font-family": "'Open-Sans', sans-serif"
                    "font-size": "10pt"
                }
                [
                    g(
                        {
                            key: "main"
                            transform: "translate(#{@props.draw_parameters.total_width / 2}, #{@props.draw_parameters.total_height / 2})"
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
                                className: "col-xs-6"
                            }
                            [
                                h3(
                                    {key: "graph.header"}
                                    "Burst graph (" + @props.draw_parameters.get_segment_info() + ")"
                                )
                                _svg
                            ]
                        )
                        div(
                            {
                                key: "detail.div"
                                className: "col-xs-6"
                            }
                            React.createElement(icswBurstServiceDetail, {service: _fe})
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
    "$scope", "icswDeviceTreeService", "$q",
    "icswDeviceLivestatusFunctions", "icswDeviceLivestatusBurstReactContainer",
(
    $scope, icswDeviceTreeService, $q,
    icswDeviceLivestatusFunctions, icswDeviceLivestatusBurstReactContainer,
) ->
    $scope.struct = {
        # loop started
        loop_started: false
        # react element
        react_element: undefined
    }

    _mount_burst = (element, new_data, draw_params) ->
        $scope.struct.react_element = ReactDOM.render(
            React.createElement(
                icswDeviceLivestatusBurstReactContainer
                {
                    monitoring_data: new_data
                    draw_parameters: draw_params
                }
            )
            element
        )


    _mounted = false
    $scope.set_notifier = (notify, element, draw_params) ->
        notify.promise.then(
            (ok) ->
                # console.log "ok"
            (reject) ->
                # stop processing
                # console.log "notok"
            (new_data) ->
                if not _mounted
                    _mounted = true
                    _mount_burst(element, new_data, draw_params)
                else
                    $scope.struct.react_element.new_monitoring_data_result()
        )

]).directive("icswDeviceLivestatus",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.livestatus.connect.overview")
        controller: "icswDeviceLiveStatusCtrl"
    }
]).service('icswLivestatusTabularDisplay',
[
    "$q", "icswMonLivestatusPipeBase", "icswMonitoringResult",
(
    $q, icswMonLivestatusPipeBase, icswMonitoringResult,
) ->
    class icswLivestatusTabularDisplay extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusTabularDisplay", true, false)
            @set_template(
                '<icsw-device-livestatus-table-view icsw-connect-element="con_element"></icsw-device-livestatus-table-view>'
                "TabularDisplay"
                6
                10
            )
            @new_data_notifier = $q.defer()

        new_data_received: (data) ->
            @new_data_notifier.notify(data)

        pipeline_reject_called: (reject) ->
            @new_data_notifier.reject("end")

]).directive("icswDeviceLivestatusTableView",
[
    "$templateCache",
(
    $templateCache,
) ->
        return {
            restrict: "EA"
            template: $templateCache.get("icsw.device.livestatus.table.view")
            controller: "icswDeviceLivestatusTableCtrl"
            scope: {
                # connect element for pipelining
                con_element: "=icswConnectElement"
            }
            link: (scope, element, attrs) ->
                scope.link(scope.con_element.new_data_notifier)
        }
]).directive("icswDeviceLivestatusTableRow",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.livestatus.table.row")
    }
]).controller("icswDeviceLivestatusTableCtrl",
[
    "$scope",
(
    $scope,
) ->
    $scope.struct = {
        # monitoring data
        monitoring_data: undefined
    }
    $scope.link = (notifier) ->
        notifier.promise.then(
            (resolve) ->
            (rejected) ->
            (data) ->
                $scope.struct.monitoring_data = data
        )

]).service('icswLivestatusFullBurst',
[
    "$q", "icswMonLivestatusPipeBase",
(
    $q, icswMonLivestatusPipeBase,
) ->
    class icswLivestatusFullBurst extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusFullBurst", true, false)
            @set_template(
                '<icsw-device-livestatus-fullburst icsw-element-size="size" icsw-connect-element="con_element"></icsw-device-livestatus-fullburst>'
                "BurstGraph"
                6
                10
            )
            @new_data_notifier = $q.defer()

        new_data_received: (new_data) ->
            @new_data_notifier.notify(new_data)

        pipeline_reject_called: (reject) ->
            @new_data_notifier.reject("stop")

]).directive('icswDeviceLivestatusFullburst',
[
    "$templateCache", "icswBurstDrawParameters",
(
    $templateCache, icswBurstDrawParameters,
) ->
    return {
        restrict: "EA"
        # template: $templateCache.get("icsw.device.livestatus.fullburst")
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
                }
            )
            scope.set_notifier(scope.con_element.new_data_notifier, element[0], draw_params)
            # console.log "+++", scope.con_element
            # omitted segments
            scope.width = parseInt(attrs["initialWidth"] or "600")
            # not working ...
            if false
                scope.$watch("size", (new_val) ->
                    if new_val
                        console.log "new_width=", new_val
                        _w = new_val.width / 2
                        if _w != scope.width
                            svg_el = element.find("svg")[0]
                            g_el = element.find("svg > g")[0]
                            scope.width = _w
                            svg_el.setAttribute("width", _w)
                            g_el.setAttribute("transform", "translate(#{_w / 2}, 160)")
                )
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
    "$templateCache", "icswBurstDrawParameters", "icswDeviceLivestatusDataService", "$q",
(
    $templateCache, icswBurstDrawParameters, icswDeviceLivestatusDataService, $q,
) ->
    return {
        restrict : "EA"
        controller: "icswDeviceLivestatusBurstReactContainerCtrl"
        scope:
             device: "=icswDevice"
        link : (scope, element, attrs) ->
            draw_params = new icswBurstDrawParameters(
                {
                    inner_radius: 0
                    outer_radius: 20
                    start_ring: 2
                }
            )
            scope.width = 60
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
            # scope.set_notifier(scope.con_element.new_data_notifier, element[0], draw_params)
    }

])
