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

# livestatus elements (curcle info)

angular.module(
    "icsw.livestatus.comp.elements",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.router",
    ]
).factory("icswLivestatusCircleInfoReact",
[
    "$q", "icswDeviceLivestatusFunctions",
(
    $q, icswDeviceLivestatusFunctions,
) ->
    {div, svg, g, rect, path, span, title, text} = React.DOM
    return React.createClass(
        propTypes: {
            size: React.PropTypes.number
            # list of (size, className, info) tuples
            data: React.PropTypes.array
            # title, optional
            title: React.PropTypes.string
            # titleSize, optional
            titleSize: React.PropTypes.number
            # text for center, optional
            text: React.PropTypes.string
            # focus mode, one of
            # none ..... no focus mode
            # simple ... other mode
            focusMode: React.PropTypes.string
        }

        handle_mouse_enter: (event, focus_mode) ->
            # console.log "me", event, focus_mode

        render: () ->
            _w = @props.size
            _d = @props.data
            if _d.length == 0
                return div(
                    {
                        key: "top"
                    }
                    "No data"
                )

            # check FocusMode

            if @props.focusMode?
                _fm = @props.focusMode
            else
                _fm = "none"
            _total = _.sum((_el[0] for _el in _d))
            _idx = 0
            _end_arc = - Math.PI * 0.5
            _cur_size = 0
            _p_list = []
            if _d[0].length == 3
                # no detailed info
                _outer = _w / 2.0 * 0.95
            else
                # detailed info present, draw extra arcs
                _outer = _w / 2.0 * 0.80
                _outer_detail = _w / 2.0 * 0.95
            _inner = _w / 2.0 * 0.5
            for [d_size, className, _info, _detail] in _d
                _idx++
                if d_size
                    _cur_size += d_size
                    _start_arc = _end_arc
                    _end_arc = Math.PI * 2.0 * _cur_size / _total - Math.PI * 0.5
                    if d_size == _total
                        _call = icswDeviceLivestatusFunctions.ring_path
                    else
                        _call = icswDeviceLivestatusFunctions.ring_segment_path
                    if _info? and _info
                        _title_el = title(
                            {
                                key: "title.#{_idx}"
                            }
                            _info
                        )
                    else
                        _title_el = null
                    _p_list.push(
                        path(
                            {
                                key: "sge.#{_idx}"
                                d: _call(_inner, _outer, _start_arc, _end_arc)
                                className: "sb_lines #{className}"
                                onMouseEnter: (event) =>
                                    if _fm != "none"
                                        @handle_mouse_enter(event, _fm)
                            }
                            _title_el
                        )
                    )
                    if _detail
                        _sub_sum = _.sum((_value for _key, _value of _detail))
                        if _sub_sum
                            _sub_idx = 0
                            _sub_end_arc = _start_arc
                            _cur_sum = 0
                            for _key, _value of _detail
                                _sub_idx++
                                _cur_sum += _value
                                _sub_start_arc = _sub_end_arc
                                _sub_end_arc = _start_arc + (_end_arc - _start_arc) * _cur_sum / _sub_sum
                                _p_list.push(
                                    path(
                                        {
                                            key: "sge.#{_idx}.#{_sub_idx}"
                                            d: _call(_outer, _outer_detail, _sub_start_arc, _sub_end_arc)
                                            className : "sb_lines svg_inactive"
                                        }
                                    )
                                )
                        else
                            # detail is empty (no categories used)
                            _p_list.push(
                                path(
                                    {
                                        key: "sge.#{_idx}.none"
                                        d: _call(_outer, _outer_detail, _start_arc, _end_arc)
                                        className: "sb_lines svg_white"
                                    }
                                )
                            )

            if @props.title?
                _text_height = if @props.titleSize? then @props.titleSize else 10
                _title_el = text(
                    {
                        x: "#{_w/2}px"
                        y: "#{_text_height/2 + 4}px"
                        key: "svg.title"
                        textAnchor: "middle"
                        fontSize: "#{_text_height}px"
                        className: "svg_txt_color"
                        alignmentBaseline: "middle"

                    }
                    @props.title
                )
            else
                _text_height = 0
                _title_el = null
            if @props.text?
                _text_el = text(
                    {
                        x: 0
                        y: 4
                        key: "svg.text"
                        textAnchor: "middle"
                        alignmentBaseline: "middle"
                        paintOrder: "stroke"
                        className: "svg_stroke default_text"
                    }
                    @props.text
                )
            else
                _text_el = null
            return span(
                {
                    key: "div.top"

                }
                svg(
                    {
                        key: "svg.top"
                        width: "#{_w}px"
                        height: "#{_w + _text_height}px"
                    }
                    g(
                        {
                            key: "main"
                        }
                        _title_el
                        g(
                            {
                                key: "content"
                                transform: "translate(#{_w/2}, #{_w/2 + _text_height})"
                            }
                            _p_list
                            _text_el
                        )
                    )
                )
            )
    )
]).directive("icswLivestatusServiceCircleInfo",
[
    "$templateCache", "icswLivestatusCircleInfoReact",
(
    $templateCache, icswLivestatusCircleInfoReact,
) ->
    return {
        restrict: "EA"
        scope:
            mon_data: "=icswMonitoringData"
        link: (scope, element, attrs) ->
            _render = () ->
                scope.mon_data.build_luts()
                ReactDOM.render(
                    React.createElement(
                        icswLivestatusCircleInfoReact
                        {
                            size: 26
                            data: scope.mon_data.service_circle_data
                            title: "Services"
                            titleSize: 5
                        }
                    )
                    element[0]
                )
            _render()
            scope.mon_data.result_notifier.promise.then(
                (resolved) ->
                (reject) ->
                (info) ->
                    _render()
            )
    }
]).directive("icswLivestatusDeviceCircleInfo",
[
    "$templateCache", "icswLivestatusCircleInfoReact",
(
    $templateCache, icswLivestatusCircleInfoReact,
) ->
    return {
        restrict: "EA"
        scope:
            mon_data: "=icswMonitoringData"
        link: (scope, element, attrs) ->
            _render = () ->
                scope.mon_data.build_luts()
                ReactDOM.render(
                    React.createElement(
                        icswLivestatusCircleInfoReact
                        {
                            size: 26
                            data: scope.mon_data.device_circle_data
                            title: "Devices"
                            titleSize: 5
                        }
                    )
                    element[0]
                )
            _render()
            scope.mon_data.result_notifier.promise.then(
                (resolved) ->
                (reject) ->
                (info) ->
                    _render()
            )
    }
])
