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

# network graphing tool, topology components

angular.module(
    "icsw.livestatus.comp.maps",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "icsw.d3", "ui.select",
        "angular-ladda", "icsw.dragging", "monospaced.mousewheel", "icsw.svg_tools", "icsw.tools", "icsw.tools.table",
        "icsw.livestatus.comp.functions", "icsw.panel_tools",
    ]
).config(["icswLivestatusPipeRegisterProvider", (icswLivestatusPipeRegisterProvider) ->
    icswLivestatusPipeRegisterProvider.add("icswLivestatusLocationMap", true)
    icswLivestatusPipeRegisterProvider.add("icswLivestatusGeoLocationDisplay", true)
]).service("icswLivestatusLocationMap",
[
    "$q", "$rootScope", "icswMonLivestatusPipeBase",
(
    $q, $rootScope, icswMonLivestatusPipeBase,
) ->
    class icswLivestatusLocationMap extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusLocationMap", true, false)
            @set_template(
                '<icsw-livestatus-tooltip icsw-connect-element="con_element"></icsw-livestatus-tooltip>
                <icsw-show-livestatus-location-map icsw-connect-element="con_element"></icsw-show-livestatus-location-map>'
                "Location Images"
                10
                8
            )
            @new_data_notifier = $q.defer()
            #  @new_data_notifier = $q.defer()

        new_data_received: (data) ->
            @new_data_notifier.notify(data)

        pipeline_reject_called: (reject) ->
            @new_data_notifier.reject("stop")
]).directive("icswShowLivestatusLocationMap",
[
    "ICSW_URLS", "icswDeviceTreeService", "icswNetworkTopologyReactContainer", "$templateCache",
(
    ICSW_URLS, icswDeviceTreeService, icswNetworkTopologyReactContainer, $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.livestatus.maplist")
        scope:
            con_element: "=icswConnectElement"
        controller: "icswDeviceLivestatusMaplistCtrl"
        link: (scope, element, attrs) ->
            scope.link(scope.con_element.new_data_notifier)
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
        # location list
        loc_gfx_list: []
        # autorotate
        autorotate: false
        # page idx for autorotate
        page_idx: 1
        # page idx set by uib-tab
        cur_page_idx: 1
        # notifier for maps
        notifier: $q.defer()
        # current device idxs
        device_idxs: []
    }
    $scope.struct.cur_gfx_size = $scope.struct.gfx_sizes[0]

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
                check_for_maps()
        )

    check_for_maps = () ->
        dev_idxs = (dev.$$icswDevice.idx for dev in $scope.struct.monitoring_data.hosts)
        if not _.isEqual(dev_idxs.sort(), $scope.struct.device_idxs.sort())
            $scope.struct.device_idxs = dev_idxs
            # check for valid maps for current device selection
            $scope.struct.loc_gfx_list.length = 0
            $scope.struct.page_idx = 1
            _rotate = _deactivate_rotation()
            loc_idx_used = []
            for gfx in $scope.struct.cat_tree.gfx_list
                if gfx.$$filtered_dml_list?
                    gfx.$$filtered_dml_list.length = 0
                else
                    gfx.$$filtered_dml_list = []
                for dml in gfx.$dml_list
                    if dml.device in dev_idxs
                        if dml.location_gfx not in loc_idx_used
                            loc_idx_used.push(gfx.idx)
                            $scope.struct.loc_gfx_list.push(gfx)
                            gfx.$$page_idx = $scope.struct.loc_gfx_list.length
                        gfx.$$filtered_dml_list.push(dml)
                gfx.$$filtered_dml_info = "#{gfx.$$filtered_dml_list.length} devices"
            if _rotate
                $scope.struct.autorotate = _rotate
                _activate_rotation()
            $scope.struct.maps_present = $scope.struct.loc_gfx_list.length > 0
        $scope.struct.notifier.notify()

    $scope.link = (notifier) ->
        load_called = false
        notifier.promise.then(
            (resolved) ->
            (rejected) ->
                # rejected, done
                $scope.struct.notifier.reject("stop")
            (data) ->
                if not load_called
                    load_called = true
                    $scope.struct.monitoring_data = data
                    load()
                else if $scope.struct.data_valid
                    check_for_maps()
        )

    # rotation functions

    _activate_rotation = () ->
        _pi = $scope.struct.page_idx
        _pi++
        if _pi < 1
            _pi = 1
        if _pi > $scope.struct.loc_gfx_list.length
            _pi = 1
        # console.log _pi, $scope.struct.loc_gfx_list.length
        $scope.struct.page_idx = _pi
        $scope.struct.autorotate_timeout = $timeout(_activate_rotation, 8000)

    _deactivate_rotation = () ->
        _cur_rotation = $scope.struct.autorotate
        $scope.struct.autorotate = false
        if $scope.struct.autorotate_timeout
            $timeout.cancel($scope.struct.autorotate_timeout)
            $scope.struct.autorotate_timeout = undefined
        return _cur_rotation

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
                        toaster.pop("warning", "form validation problem", "")
                        d.reject("form not valid")
                    else
                        d.resolve("updated")
                    return d.promise
            }
        ).then(
            (fin) ->
                sub_scope.$destroy()
        )

]).service("icswLivestatusGeoLocationDisplay",
[
    "$q", "icswMonLivestatusPipeBase", "icswMonitoringResult",
(
    $q, icswMonLivestatusPipeBase, icswMonitoringResult,
) ->
    class icswLivestatusGeoLocationDisplay extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusGeoLocationDisplay", true, false)
            @set_template(
                '<icsw-device-livestatus-geo-location-display icsw-connect-element="con_element"></icsw-device-livestatus-geo-location-display>'
                "Geo Location"
                10
                8
            )
            @new_data_notifier = $q.defer()
            #  @new_data_notifier = $q.defer()

        new_data_received: (data) ->
            @new_data_notifier.notify(data)

        pipeline_reject_called: (reject) ->
            @new_data_notifier.reject("stop")

]).directive("icswDeviceLivestatusGeoLocationDisplay",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.config.category.location.show")
        scope: {
            con_element: "=icswConnectElement"
        }
        controller: "icswConfigCategoryLocationCtrl"
        link: (scope, element, attrs) ->
            scope.set_mode("show")
    }
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
            notifier: React.PropTypes.object
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
            @props.notifier.promise.then(
                () ->
                () ->
                    # will get called when the pipeline shuts down
                (c) =>
                    @force_redraw()
            )

        force_redraw: () ->
            @setState(
                {counter: @state.counter + 1}
            )

        render: () ->
            _gfx = @props.location_gfx
            # target width and height
            {width, height} = @state
            # gfx width and height
            _gfx_width = _gfx.width
            _gfx_height = _gfx.height
            # scale
            _scale_x = width / _gfx_width
            _scale_y = height / _gfx_height
            _scale = _.min([_scale_x, _scale_y])
            # console.log _scale_x, _scale_y, _scale
            _header = _gfx.name
            if _gfx.comment
                _header = "#{_header} (#{_gfx.comment})"
            _header = "#{_header} (#{_gfx_width} x #{_gfx_height}) * scale (#{_.round(_scale, 3)}) = (#{_.round(_gfx_width * _scale, 3)} x #{_.round(_gfx_height * _scale, 3)})"
            _header = "#{_header}, #{_gfx.$$filtered_dml_list.length} Devices"

            _dml_list = [
                image(
                    {
                        key: "bgimage"
                        width: _gfx_width
                        height: _gfx_height
                        xlinkHref: _gfx.image_url
                        preserveAspectRatio: "none"
                    }
                )
                polyline(
                    {
                        key: "imageborder"
                        style: {fill:"none", stroke:"black", strokeWidth:"3"}
                        points: "0,0 #{_gfx_width - 1},0 #{_gfx_width - 1},#{_gfx_height - 1} 0,#{_gfx_height - 1} 0 0"
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
            # console.log width, height, _gfx_width, _gfx_height
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
                            width: "100%"  # width
                            height: "100%"  # height
                            preserveAspectRatio: "xMidYMid meet"
                            viewBox: "0 0 #{_gfx_width} #{_gfx_height}"
                        }
                        [
                            g(
                                {
                                    key: "gouter"
                                    # scale not needed because of viewbox
                                    # transform: "scale(#{_scale})"
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
            gfx_size: "=icswGfxSize"
            # to notify when the data changes
            notifier: "=icswNotifier"
            con_element: "=icswConnectElement"
        link : (scope, element, attrs) ->
            draw_params = new icswBurstDrawParameters(
                {
                    inner_radius: 0
                    outer_radius: 90
                    tooltip: scope.con_element.tooltip
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
                                location_gfx: scope.loc_gfx
                                monitoring_data: scope.monitoring_data
                                draw_parameters: draw_params
                                device_tree: device_tree
                                notifier: scope.notifier
                            }
                        )
                        element[0]
                    )
                    scope.monitoring_data.result_notifier.promise.then(
                        () ->
                        () ->
                        (generation) =>
                            # console.log "gen", @props.livestatus_filter, @monitoring_data
                            react_el.force_redraw()
                    )
                    scope.$watch("gfx_size", (new_val) ->
                        react_el.set_size(new_val)
                    )
            )
    }
])
