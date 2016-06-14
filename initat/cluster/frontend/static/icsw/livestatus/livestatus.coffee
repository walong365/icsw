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
    "icswDeviceTreeService", "icswMonLivestatusConnector",
(
    $scope, $compile, $templateCache, Restangular,
    $q, $timeout, icswTools, ICSW_URLS, icswSimpleAjaxCall,
    icswDeviceLivestatusDataService, icswCachingCall, icswLivestatusFilterService,
    icswDeviceTreeService, icswMonLivestatusConnector,
) ->
    # top level controller of monitoring dashboard

    $scope.struct = {
        # filter
        filter: new icswLivestatusFilterService()
        # selected devices
        devices: []
        # data fetch timeout
        fetch_timeout: undefined
        # updating flag
        updating: false
        # device tree, really needed here ?
        device_tree: undefined
        # monitoring data
        monitoring_data: undefined
        # connector
        # connector: new icswMonLivestatusConnector("test", angular.toJson({"icswLivestatusDataSource": [{"icswLivestatusFilterService": [{"icswLivestatusCategoryFilter": [{"icswLivestatusFullBurst": []}]}]}]}))
        # connector: new icswMonLivestatusConnector("test", angular.toJson({"icswLivestatusDataSource": [{"icswLivestatusFullBurst": []}]}))
        connector: new icswMonLivestatusConnector(
            "test"
            angular.toJson(
                {
                    "icswLivestatusDataSource": [
                        {
                            "icswLivestatusFilterService": [
                                {
                                    "icswLivestatusFullBurst": []
                                }
                                {
                                    "icswLivestatusCategoryFilter": [
                                        {
                                            "icswLivestatusFullBurst": []
                                        }
                                    ]
                                }
                                {
                                    "icswLivestatusFilterService": [
                                        {
                                            "icswLivestatusFullBurst": []
                                        }
                                    ]
                                }
                            ]
                        }
                        {
                            "icswLivestatusFullBurst": []
                        }
                    ]
                }
            )
        )
    }

    # $scope.ls_devsel = new icswLivestatusDevSelFactory()

    #$scope.$watch(
    #    $scope.ls_filter.changed
    #    (new_filter) ->
    #        $scope.apply_filter()
    #)

    # selected categories

    # $scope.filter_changed = () ->
    #    if $scope.struct.filter?
    #        $scope.struct.filter.set_monitoring_data($scope.struct.monitoring_data)

    $scope.new_devsel = (_dev_sel) ->
        @struct.connector.new_devsel(_dev_sel)
        return
        # only called when new devices are selected, not on every monitoring data update
        $scope.struct.updating = true

        if $scope.struct.fetch_timeout
            $timeout.cancel($scope.struct.fetch_timeout)
            $scope.struct.fetch_timeout = undefined

        $scope.struct.devices.length = 0
        for entry in _dev_sel
            if not entry.is_meta_device
                $scope.struct.devices.push(entry)

        #pre_sel = (dev.idx for dev in $scope.devices when dev.expanded)
        wait_list = [
            icswDeviceTreeService.load($scope.$id)
            icswDeviceLivestatusDataService.retain($scope.$id, $scope.struct.devices)
        ]
        $q.all(wait_list).then(
            (data) ->
                $scope.struct.device_tree = data[0]
                # $scope.new_data(data[1])
                # console.log "gen", data[1][4]
                # console.log "watch for", data[1]
                $scope.struct.updating = false
                $scope.struct.monitoring_data = data[1]
                console.log "start loop"
                $scope.struct.monitoring_data.result_notifier.promise.then(
                    (ok) ->
                        console.log "dr ok"
                    (not_ok) ->
                        console.log "dr error"
                    (generation) ->
                        console.log "new data here"
                        $scope.filter_changed()
                )
        )

    $scope.$on("$destroy", () ->
        icswDeviceLivestatusDataService.destroy($scope.$id)
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

        componentDidMount: () ->
            @burst_element = $(react_dom.findDOMNode(@)).parents("react-burst")
            # console.log @burst_element, @burst_element[0]

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

]).directive("reactBurst",
[
    "ICSW_URLS",
(
    ICSW_URLS,
) ->
    return {
        restrict: "EA"
        replace: true
        controller: "icswDeviceLivestatusBurstReactContainerCtrl"
        scope:
            filter: "=icswLivestatusFilter"
            data: "=icswMonitoringData"
            draw_params: "=icswDrawParameters"
        link: (scope, element, attrs) ->
            _mounted = false

            scope.$watch("data", (new_val) ->
                scope.struct.monitoring_data = new_val
                if scope.start_loop(element[0])
                    _mounted = true
            )

            scope.$watch("filter", (new_val) ->
                scope.struct.filter = new_val
                if scope.start_loop(element[0])
                    _mounted = true
            )

            scope.$on("$destroy", () ->
                if _mounted
                    ReactDOM.unmountComponentAtNode(element[0])
                    scope.struct.react_element = undefined
            )

    }
]).controller("icswDeviceLivestatusBurstReactContainerCtrl",
[
    "$scope", "icswDeviceTreeService", "$q",
    "icswDeviceLivestatusFunctions", "icswDeviceLivestatusBurstReactContainer",
    "icswBurstDrawParameters",
(
    $scope, icswDeviceTreeService, $q,
    icswDeviceLivestatusFunctions, icswDeviceLivestatusBurstReactContainer,
    icswBurstDrawParameters,
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
                console.log "ok"
            (not_ok) ->
                console.log "notok"
            (new_data) ->
                if not _mounted
                    _mounted = true
                    _mount_burst(element, new_data, draw_params)
                else
                    $scope.struct.react_element.new_monitoring_data_result()
                console.log "new data"
        )

]).directive("icswDeviceLivestatus",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict : "EA"
        # template : $templateCache.get("icsw.livestatus.livestatus.overview")
        template : $templateCache.get("icsw.livestatus.connect.overview")
        controller: "icswDeviceLiveStatusCtrl"
    }
]).directive("icswDeviceLivestatusBrief",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.livestatus.brief")
        controller: "icswDeviceLiveStatusBriefCtrl"
        scope:
             device: "=icswDevice"
        link : (scope, element, attrs) ->
            scope.new_devsel([scope.device])
    }
]).controller("icswDeviceLiveStatusBriefCtrl",
[
    "$scope", "$compile", "$templateCache", "Restangular",
    "$q", "$timeout", "icswTools", "ICSW_URLS", "icswSimpleAjaxCall",
    "icswDeviceLivestatusDataService", "icswCachingCall", "icswLivestatusFilterService",
    "icswBurstDrawParameters",
(
    $scope, $compile, $templateCache, Restangular,
    $q, $timeout, icswTools, ICSW_URLS, icswSimpleAjaxCall,
    icswDeviceLivestatusDataService, icswCachingCall, icswLivestatusFilterService,
    icswBurstDrawParameters,
) ->
    $scope.struct = {
        # filter
        filter: new icswLivestatusFilterService()
        # monitoring data
        monitoring_data: undefined
        # draw parameters
        draw_parameters: new icswBurstDrawParameters(
            {
                inner_radius: 0
                outer_radius: 20
                start_ring: 2
            }
        )
    }

    # layout functions

    $scope.filter_changed = () ->
        if $scope.struct.filter?
            $scope.struct.filter.set_monitoring_data($scope.struct.monitoring_data)

    $scope.new_devsel = (_dev_sel) ->
        # console.log "DS", _dev_sel

        #pre_sel = (dev.idx for dev in $scope.devices when dev.expanded)
        wait_list = [
            icswDeviceLivestatusDataService.retain($scope.$id, _dev_sel)
        ]
        $q.all(wait_list).then(
            (data) ->
                $scope.struct.monitoring_data = data[0]
                $scope.struct.monitoring_data.result_notifier.promise.then(
                    (ok) ->
                        console.log "dr ok"
                    (not_ok) ->
                        console.log "dr error"
                    (generation) ->
                        # console.log "data here", $scope.struct.monitoring_data
                        $scope.filter_changed()
                )
        )
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
                filter: "=icswLivestatusFilter"
                data: "=icswMonitoringData"
            }
            link: (scope, element, attrs) ->
                scope.$watch("data", (new_val) ->
                    scope.struct.monitoring_data = new_val
                )
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
        # filter
        filter: undefined
        # monitoring data
        monitoring_data: undefined
    }
    $scope.struct.filter = $scope.filter
    # console.log "struct=", $scope.struct

]).service('icswLivestatusFullBurst',
[
    "$q", "icswMonLivestatusPipeBase",
(
    $q, icswMonLivestatusPipeBase,
) ->
    class icswLivestatusFullBurst extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusFullBurst", true, false)
            @set_template('<icsw-device-livestatus-fullburst icsw-element-size="size" icsw-connect-element="con_element"></icsw-device-livestatus-fullburst>', "BurstGraph")
            @new_data_notifier = $q.defer()

        new_data_received: (new_data) ->
            @new_data_notifier.notify(new_data)

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
            console.log "+++", scope.con_element
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
                console.log "DESTROY FullBurst"
                if _mounted
                    ReactDOM.unmountComponentAtNode(element[0])
                    scope.struct.react_element = undefined
            )
    }

]).directive("icswDeviceLivestatusMaplist",
[
    "$compile", "$templateCache", "icswCachingCall", "$q", "ICSW_URLS", "$timeout",
(
    $compile, $templateCache, icswCachingCall, $q, ICSW_URLS, $timeout,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.livestatus.maplist")
        scope: {
            devices: "=icswDevices"
            data: "=icswMonitoringData"
            filter: "=icswLivestatusFilter"
        }
        link: (scope, element, attrs) ->
            scope.$watch("data", (new_val) ->
                scope.struct.monitoring_data = new_val
            )
            scope.$watch(
                "devices"
                (new_val) ->
                    scope.new_devsel(new_val)
                true
            )
        controller: "icswDeviceLivestatusMaplistCtrl"
    }
]).controller("icswDeviceLivestatusMaplistCtrl",
[
    "$scope", "icswCategoryTreeService", "$q", "$timeout", "$compile", "$templateCache",
    "icswComplexModalService", "toaster",
(
    $scope, icswCategoryTreeService, $q, $timeout, $compile, $templateCache,
    icswComplexModalService, toaster,
) ->

    $scope.struct = {
        # data valid
        data_valid: false
        # category tree
        cat_tree: undefined
        # gfx sizes
        gfx_sizes: ["1024x768", "1280x1024", "1920x1200", "800x600", "640x400"]
        # cur gfx
        cur_gfx_size: undefined
        # any maps present
        maps_present: false
        # monitoring data
        monitoring_data: undefined
        # devices
        devices: []
        # location list
        loc_gfx_list: []
        # autorotate
        autorotate: false
        # page idx for autorotate
        page_idx: 0
        # page idx set by uib-tab
        cur_page_idx: 0
        # filter
        filter: undefined
    }
    $scope.struct.cur_gfx_size = $scope.struct.gfx_sizes[0]
    console.log "F", $scope.filter
    $scope.struct.filter = $scope.filter

    load = () ->
        $scope.struct.data_valid = false
        $scope.struct.maps_present = false
        $q.all(
            [
                icswCategoryTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.cat_tree = data[0]
                $scope.struct.data_valid = true
                if $scope.struct.devices.length
                    check_for_maps()
        )

    check_for_maps = () ->
        # check for valid maps for current device selection
        $scope.struct.loc_gfx_list.length = 0
        $scope.struct.page_idx = 0
        _deactivate_rotation()
        loc_idx_used = []
        dev_idx = (dev.idx for dev in $scope.struct.devices)
        for gfx in $scope.struct.cat_tree.gfx_list
            gfx.$$filtered_dml_list = []
            for dml in gfx.$dml_list
                if dml.device in dev_idx and dml.location_gfx not in loc_idx_used
                    loc_idx_used.push(gfx.idx)
                    $scope.struct.loc_gfx_list.push(gfx)
                    gfx.$$filtered_dml_list.push(dml)
                    gfx.$$page_idx = $scope.struct.loc_gfx_list.length
        $scope.struct.maps_present = $scope.struct.loc_gfx_list.length > 0
                    
    $scope.new_devsel = (devs) ->
        $scope.struct.devices.length = 0
        for dev in devs
            $scope.struct.devices.push(dev)
        if $scope.struct.data_valid
            check_for_maps()

    load()

    # rotation functions

    _activate_rotation = () ->
        _pi = $scope.struct.page_idx
        _pi++
        if _pi < 1
            _pi = 1
        if _pi > $scope.struct.loc_gfx_list.length
            _pi = 1
        $scope.struct.page_idx = _pi
        $scope.struct.autorotate_timeout = $timeout(_activate_rotation, 8000)

    _deactivate_rotation = () ->
        $scope.struct.autorotate = false
        if $scope.struct.autorotate_timeout
            $timeout.cancel($scope.struct.autorotate_timeout)
            $scope.struct.autorotate_timeout = undefined

    $scope.toggle_autorotate = () ->
        $scope.struct.autorotate = !$scope.struct.autorotate
        if $scope.struct.autorotate
            _activate_rotation()
        else
            _deactivate_rotation()

    $scope.set_page_idx = (loc_gfx) ->
        $scope.struct.cur_page_idx = loc_gfx.$$page_idx

    $scope.show_settings = () ->
        sub_scope = $scope.$new(false)
        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.device.livestatus.maplist.settings"))(sub_scope)
                title: "Map settings"
                # css_class: "modal-wide"
                ok_label: "close"
                closable: true
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "", 0)
                        d.reject("form not valid")
                    else
                        d.resolve("updated")
                    return d.promise
            }
        ).then(
            (fin) ->
                sub_scope.$destroy()
        )

]).factory("icswDeviceLivestatusLocationMapReact",
[
    "$q", "icswDeviceLivestatusReactBurst",
(
    $q, icswDeviceLivestatusReactBurst,
) ->
    {div, h4, g, image, svg, polyline} = React.DOM

    return React.createClass(
        propTypes: {
            location_gfx: React.PropTypes.object
            monitoring_data: React.PropTypes.object
            draw_parameters: React.PropTypes.object
            device_tree: React.PropTypes.object
            livestatus_filter: React.PropTypes.object
        }

        getInitialState: () ->
            return {
                width: 640
                height: 400
                counter: 0
            }

        set_size: (size_str) ->
            [_width, _height] = size_str.split("x")
            @setState(
                {
                    width: parseInt(_width)
                    height: parseInt(_height)
                }
            )

        componentWillMount: () ->
            # @umount_defer = $q.defer()
            @props.livestatus_filter.change_notifier.promise.then(
                () ->
                () ->
                    # will get called when the component unmounts
                (c) =>
                    @force_redraw()
            )

        componentWillUnmount: () ->
            @umount_defer.reject("stop")

        force_redraw: () ->
            @setState(
                {counter: @state.counter + 1}
            )

        render: () ->
            _gfx = @props.location_gfx
            {width, height} = @state
            _header = _gfx.name
            if _gfx.comment
                _header = "#{_header} (#{_gfx.comment})"

            _dml_list = [
                image(
                    {
                        key: "bgimage"
                        width: width
                        height: height
                        href: _gfx.image_url
                    }
                )
                polyline(
                    {
                        key: "imageborder"
                        style: {fill:"none", stroke:"black", strokeWidth:"3"}
                        points: "0,0 #{width},0 #{width},#{height} 0,#{height} 0 0"
                    }
                )
            ]
            # console.log @props
            for dml in _gfx.$$filtered_dml_list
                # build node
                node = {
                    id: dml.device
                    x: dml.pos_x
                    y: dml.pos_y
                }
                _dml_list.push(
                    React.createElement(
                        icswDeviceLivestatusReactBurst
                        {
                            node: node
                            key: "dml_node_#{dml.device}"
                            monitoring_data: @props.monitoring_data
                            draw_parameters: @props.draw_parameters
                        }
                    )
                )
            return div(
                {
                    key: "top"
                }
                [
                    h4(
                        {
                            key: "header"
                        }
                        _header
                    )
                    svg(
                        {
                            key: "svgouter"
                            width: width
                            height: height
                            preserveAspectRatio: "xMidYMid meet"
                            viewBox: "0 0 #{width} #{height}"
                        }
                        [
                            g(
                                {
                                    key: "gouter"
                                }
                                _dml_list
                            )
                        ]
                    )

                ]
            )
    )
]).directive("icswDeviceLivestatusLocationMap",
[
    "$templateCache", "$compile", "Restangular", "icswDeviceLivestatusLocationMapReact",
    "icswBurstDrawParameters", "icswDeviceTreeService", "$q",
(
    $templateCache, $compile, Restangular, icswDeviceLivestatusLocationMapReact,
    icswBurstDrawParameters, icswDeviceTreeService, $q,
) ->
    return {
        restrict: "EA"
        scope:
            loc_gfx: "=icswLocationGfx"
            monitoring_data: "=icswMonitoringData"
            filter: "=icswLivestatusFilter"
            gfx_size: "=icswGfxSize"
        link : (scope, element, attrs) ->
            draw_params = new icswBurstDrawParameters(
                {
                    inner_radius: 0
                    outer_radius: 90
                }
            )
            $q.all(
                [
                    icswDeviceTreeService.load(scope.$id)
                ]
            ).then(
                (data) ->
                    device_tree = data[0]
                    # console.log scope.monitoring_data, scope.filter
                    react_el = ReactDOM.render(
                        React.createElement(
                            icswDeviceLivestatusLocationMapReact
                            {
                                livestatus_filter: scope.filter
                                location_gfx: scope.loc_gfx
                                monitoring_data: scope.monitoring_data
                                draw_parameters: draw_params
                                device_tree: device_tree
                            }
                        )
                        element[0]
                    )
                    scope.monitoring_data.result_notifier.promise.then(
                        () ->
                        () ->
                        (generation) =>
                            # console.log "gen", @props.livestatus_filter, @monitoring_data
                            console.log "new_gen", generation
                            react_el.force_redraw()
                    )
                    scope.$watch("gfx_size", (new_val) ->
                        react_el.set_size(new_val)
                    )
            )
    }
])
