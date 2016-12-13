# Copyright (C) 2015-2016 init.at
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
    "icsw.config.category.googlemaps",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters",
        "ui.select", "restangular", "uiGmapgoogle-maps", "angularFileUpload"
    ]
).service("reactMarkerEntry",
[
    "$q",
(
    $q,
) ->
    {svg, circle, div, g, text} = React.DOM
    return React.createClass(
        propTypes: {
            # required types
            location: React.PropTypes.object
        }

        render: () ->
            _offset = 50
            loc = @props.location
            _render = div(
                {
                    key: "container.#{loc.idx}"
                    style: {
                        position: "absolute"
                        left: "#{loc.$$gm_x - _offset}px"
                        top: "#{loc.$$gm_y - _offset}px"
                        width: "100px"
                        height: "100px"
                        border: "1px solid black"
                    }
                }
                [
                    svg(
                        {
                            key: "svg.top"
                            width: "100%"
                            height: "100%"
                        }
                        g(
                            {
                                key: "g"
                                transform: "translate(#{_offset}, #{_offset})"
                            }
                            [
                                circle(
                                    {
                                        key: "c"
                                        r: "15"
                                        fill: "#8888ee"
                                        opacity: 0.5
                                        stroke: "#000000"
                                        strokeWidth: "2px"
                                    }
                                )
                                text(
                                    {
                                        key: "c.text"
                                        alignmentBaseline: "middle"
                                        textAnchor: "middle"
                                        fontSize: "14px"
                                        fill: "#000000"
                                        stroke: "#ffffff"
                                        strokeWidth: "0.5px"
                                    }
                                    loc.full_name
                                )

                            ]
                        )
                    )
                ]
            )
            return _render
    )
]).service("reactMarkerList",
[
    "$q", "reactMarkerEntry",
(
    $q, reactMarkerEntry,
) ->
    {div, svg, rect} = React.DOM
    return React.createClass(
        propTypes: {
            # required types
            locations: React.PropTypes.array
        }

        getInitialState: () ->
            return {
                counter: 0
            }

        redraw: () ->
            @setState({counter: @state.counter + 1})

        render: () ->
            return div(
                {
                    key: "top"
                }
                (
                    React.createElement(
                        reactMarkerEntry
                        {
                            location: loc.location
                        }
                    ) for loc in @props.locations
                )
            )
    )
]).service("icswReactBurstGraphList",
[
    "$q", "icswDeviceLivestatusBurstReactContainer", "icswBurstDrawParameters",
(
    $q, icswDeviceLivestatusBurstReactContainer, icswBurstDrawParameters,
) ->
    OUTER_RAD = 80
    {div, svg, rect} = React.DOM
    return React.createClass(
        propTypes: {
            # required types
            locations: React.PropTypes.array
        }

        getInitialState: () ->
            @draw_params = new icswBurstDrawParameters(
                {
                    inner_radius: 10
                    outer_radius: OUTER_RAD
                    start_ring: 0
                    is_interactive: false
                    omit_small_segments: true
                }
            )
            return {
                counter: 0
                external_trigger: 0
            }

        redraw: () ->
            @setState({counter: @state.counter + 1})

        new_mon_data: () ->
            @setState({external_trigger: @state.external_trigger + 1})

        render: () ->
            # should be equal to outer radius
            _offset = OUTER_RAD
            _size = 2 * OUTER_RAD
            _el_list = []
            for loc_proxy in @props.locations
                loc = loc_proxy.location
                _el_list.push(
                    div(
                        {
                            key: "container.#{loc.idx}"
                            style: {
                                position: "absolute"
                                left: "#{loc.$$gm_x - _offset}px"
                                top: "#{loc.$$gm_y - _offset}px"
                                # should be equal to the total width / height
                                width: "#{_size}px"
                                height: "#{_size}px"
                                # border: "1px solid black"
                            }
                        }
                        React.createElement(
                            icswDeviceLivestatusBurstReactContainer
                            {
                                draw_parameters: @draw_params
                                monitoring_data: loc_proxy.monitoring_data
                                external_trigger: @state.external_trigger
                            }
                        )
                    )
                )
            return div(
                {
                    key: "top"
                }
                _el_list
            )
    )
]).service("icswGoogleMapsMarkerOverlay",
[
    "$q", "reactMarkerList", "icswReactBurstGraphList",
(
    $q, reactMarkerList, icswReactBurstGraphList,
) ->
    class icswGoogleMapsMarkerOverlay
        constructor: (@overlay, @google_maps, @locations) ->

        onAdd: () =>
            panes = @overlay.getPanes()
            @mydiv = angular.element("<div/>")[0]
            @mydiv.style.position = "absolute"
            panes.markerLayer.appendChild(@mydiv)
            @element = ReactDOM.render(
                React.createElement(
                    # reactMarkerList
                    icswReactBurstGraphList
                    {
                        locations: @locations
                    }
                )
                @mydiv
            )

        new_mon_data: (locations) =>
            if @element?
                @element.new_mon_data()

        draw: () =>
            _proj = @overlay.getProjection()
            for _loc_proxy in @locations
                _loc = _loc_proxy.location
                center = _proj.fromLatLngToDivPixel(new @google_maps.LatLng(_loc.latitude, _loc.longitude))
                _loc.$$gm_x = center.x
                _loc.$$gm_y = center.y
            @element.redraw()

]).service("icswGoogleMapsHelper",
[
    "$q",
(
    $q,
) ->
    # small helper to be used by gridster to avoid double-panning
    _is_panning = false
    _in_map = false
    return {
        start_panning: () ->
            _is_panning = true

        end_panning: () ->
            _is_panning = false

        enter_map: () ->
            _in_map = true

        leave_map: () ->
            _in_map = false

        is_panning: () ->
            return _is_panning

        in_map: () ->
            return _in_map
    }
]).directive("icswConfigCategoryTreeGoogleMap",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.config.category.tree.google.map")
        scope: {
            # locations are in fact proxylocations
            locations: "=locations"
            active_tab: "=activeTab"
            maps_control: "=icswGoogleMapsFn"
            maps_cb_fn: "=icswGoogleMapsCbFn"
        }
        controller: "icswConfigCategoryTreeGoogleMapCtrl"
        link: (scope, element, attrs) ->
            scope.set_map_mode(attrs["icswMapMode"])
            scope.$on("$destroy", () ->
                # console.log "gmd"
            )
    }
]).controller("icswConfigCategoryTreeGoogleMapCtrl",
[
    "$scope", "$templateCache", "$timeout", "$rootScope", "ICSW_SIGNALS", "icswGoogleMapConfig",
    "icswGoogleMapsMarkerOverlay", "uiGmapIsReady", "icswGoogleMapsHelper",
(
    $scope, $templateCache, $timeout, $rootScope, ICSW_SIGNALS, icswGoogleMapConfig,
    icswGoogleMapsMarkerOverlay, uiGmapIsReady, icswGoogleMapsHelper,
) ->

    $scope.struct = {
        # map mode
        map_mode: undefined
        # map active
        map_active: false
        # google maps ready
        maps_ready: false
        # google maps object
        google_maps: undefined
        # map options
        map_options: {
            center: {}
            zoom: 6
            control: {}
            options: {
                streetViewControl: false
                minZoom: 1
                maxZoom: 20
            }
            events: {
                dragstart: (args...) ->
                    icswGoogleMapsHelper.start_panning()
                dragend: (args...) ->
                    icswGoogleMapsHelper.end_panning()
                mouseover: (args...) ->
                    icswGoogleMapsHelper.enter_map()
                mouseout: (args...) ->
                    icswGoogleMapsHelper.leave_map()
            }
        }
        # marker overlay
        marker_overlay: undefined
    }
    $scope.set_map_mode = (mode) ->
        console.log "map_mode=", mode
        $scope.struct.map_mode = mode
        if $scope.struct.map_mode in ["show"]
            $scope.struct.map_active = true
        else
            # wait for activation
            $scope.struct.map_active = false

    $scope.marker_lut = {}
    $scope.marker_list = []

    $scope.event_dict = {
        dragend: (marker, event_name, args) ->
            _pos = marker.getPosition()
            _cat = $scope.marker_lut[marker.key]
            _cat.latitude = _pos.lat()
            _cat.longitude = _pos.lng()
            _cat.put()

        click: (marker, event_name, args) ->
            _loc = $scope.marker_lut[marker.key]
            for entry in $scope.locations
                entry.$$selected = false
            _loc.$$selected = !_loc.$$selected
            if $scope.maps_cb_fn?
                $scope.maps_cb_fn("marker_clicked", _loc)
        dblclick: (marker, event_name, args) ->
            console.log "DBL"

    }

    $scope.zoom_to_locations = () ->
        # center map around the locations
        _bounds = new $scope.struct.google_maps.LatLngBounds()
        for entry in $scope.locations
            _bounds.extend(new $scope.struct.google_maps.LatLng(entry.location.latitude, entry.location.longitude))
        if $scope.struct.map_options.control.getGMap?
            $scope.struct.map_options.control.getGMap().fitBounds(_bounds)
        else
            console.log "maps control not populated"

    $scope.get_center = () ->
        # center map around the locations
        _bounds = new $scope.struct.google_maps.LatLngBounds()
        for entry in $scope.locations
            _bounds.extend(new $scope.struct.google_maps.LatLng(entry.location.latitude, entry.location.longitude))
        $scope.struct.map_options.center = {latitude:_bounds.getCenter().lat(), longitude: _bounds.getCenter().lng()}

    # helper functions

    build_markers = () ->
        $scope.marker_list.length = 0
        marker_lut = {}
        if $scope.struct.marker_overlay
            # do not draw any google markers when a marker overlay is present
            return
        # console.log "init markers", $scope.locations.length

        for _proxy_entry in $scope.locations
            _entry = _proxy_entry.location
            comment = _entry.name
            if _entry.comment
                comment = "#{comment} (#{_entry.comment})"
            if _entry.$gfx_list.length
                comment = "#{comment}, #{_entry.$gfx_list.length} gfxs"
            # draggable flag
            if $scope.struct.map_mode in ["edit"]
                _draggable = not _entry.locked
            else
                _draggable = false
            $scope.marker_list.push(
                {
                    latitude: _entry.latitude
                    longitude: _entry.longitude
                    key: _entry.idx
                    comment: comment
                    options: {
                        draggable: _draggable
                        title: comment
                        opacity: if _entry.locked then 1.0 else 0.7
                    }
                    icon: if _entry.svg_url then _entry.svg_url else null
                }
            )
            marker_lut[_entry.idx] = _entry
            $scope.marker_lut = marker_lut

    $scope.maps_control = (fn_name, args) ->
        if $scope.struct.google_maps? and $scope.struct.map_options.control?
            if fn_name == "refresh"
                [lat, long] = args
                $scope.struct.map_options.control.refresh(
                    {
                        latitude: lat
                        longitude: long
                    }
                )
            else if fn_name == "zoom"
                $scope.struct.map_options.control.getGMap().setZoom(args)
            else if fn_name == "new_mon_data"
                if not $scope.struct.marker_overlay
                    # marker overlay
                    marker_overlay = new $scope.struct.google_maps.OverlayView()
                    angular.extend(marker_overlay, new icswGoogleMapsMarkerOverlay(marker_overlay, $scope.struct.google_maps, $scope.locations))
                    marker_overlay.setMap($scope.struct.map_options.control.getGMap())
                    $scope.struct.marker_overlay = marker_overlay
                    build_markers()
                $scope.struct.marker_overlay.new_mon_data(args)
            else
                console.warn "got unknown command #{fn_name} (#{args})"

    _update = () ->
        if $scope.struct.map_active and $scope.locations? and $scope.locations.length and not $scope.struct.maps_ready
            # console.log "Zoom"
            build_markers()
            icswGoogleMapConfig.init().then(
                (maps) ->
                    $scope.struct.maps_ready = true
                    $scope.struct.google_maps = maps
                    $scope.get_center()
                    # console.log "WFR"
                    uiGmapIsReady.promise(1).then(
                        (ok) ->
                            # console.log "GMR", ok
                            _map = $scope.struct.map_options
                            # zoom
                            $scope.zoom_to_locations()
                            # console.log _map.control
                            if _map.control? and _map.control.refresh?
                                _map.control.refresh(
                                    {
                                        latitude: _map.center.latitude
                                        longitude: _map.center.longitude
                                    }
                                )
                            if $scope.maps_cb_fn?
                                $scope.maps_cb_fn("map_init")
                    )
            )

    $rootScope.$on(ICSW_SIGNALS("ICSW_CATEGORY_TREE_CHANGED"), (event) ->
        _update()
    )

    $scope.$watch(
        "active_tab"
        (new_val) ->
            if new_val?
                if new_val == "conf"
                    $scope.struct.map_active = true
                    _update()
                else
                    $scope.struct.map_active = false
    )
    $scope.$watch(
        "locations",
        (new_val) ->
            _update()
            build_markers()
        true
    )

])
