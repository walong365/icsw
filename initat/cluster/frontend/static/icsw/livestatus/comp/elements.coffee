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

# small livestatus elements (circle info) for table headings

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
            # showInfo, true or false
            showInfo: React.PropTypes.bool
            # showDetails, true or false
            showDetails: React.PropTypes.bool
        }

        #handle_mouse_enter: (event, focus_mode) ->
        #    console.log "me", event, focus_mode

        render: () ->
            # check flags
            _show_info = false
            if @props.showInfo?
                _show_info = @props.showInfo

            _show_details = false
            if @props.showDetails?
                _show_details = @props.showDetails

            # check FocusMode

            if @props.focusMode?
                _fm = @props.focusMode
            else
                _fm = "none"

            _w = 140  # @props.size  # not needed anymore due to viewBox
            _d = @props.data

            _total = _.sum((_el.value for _el in _d))
            _idx = 0
            _end_arc = - Math.PI * 0.5
            _cur_size = 0
            _p_list = []
            if _d.length and _d[0].detail? and _show_details
                # detailed info present, draw extra arcs
                _outer = _w / 2.0 * 0.80
                _outer_detail = _w / 2.0 * 0.95
            else
                # no detailed info
                _outer = _w / 2.0 * 0.95
            _inner = _w / 2.0 * 0.5
            _raw_text_list = []
            for _entry in _d
                _idx++
                if _entry.value
                    if _show_info
                        _raw_text_list.push("#{_entry.shortInfoStr}")
                    _cur_size += _entry.value
                    _start_arc = _end_arc
                    _end_arc = Math.PI * 2.0 * _cur_size / _total - Math.PI * 0.5
                    if _entry.value == _total
                        _call = icswDeviceLivestatusFunctions.ring_path
                    else
                        _call = icswDeviceLivestatusFunctions.ring_segment_path
                    if _entry.infoStr?
                        _title_el = title(
                            {
                                key: "title.#{_idx}"
                            }
                            _entry.infoStr
                        )
                    else
                        _title_el = null
                    _p_list.push(
                        path(
                            {
                                key: "sge.#{_idx}"
                                d: _call(_inner, _outer, _start_arc, _end_arc)
                                className: "sb-lines #{_entry.data.svgClassName}"
                                onMouseEnter: (event) =>
                                    if _fm != "none"
                                        @handle_mouse_enter(event, _fm)
                            }
                            _title_el
                        )
                    )
                    if _entry.detail? and _show_details
                        _sub_sum = _.sum((_value for _key, _value of _entry.detail))
                        if _sub_sum
                            _sub_idx = 0
                            _sub_end_arc = _start_arc
                            _cur_sum = 0
                            for _key, _value of _entry.detail
                                _sub_idx++
                                _cur_sum += _value
                                _sub_start_arc = _sub_end_arc
                                _sub_end_arc = _start_arc + (_end_arc - _start_arc) * _cur_sum / _sub_sum
                                _p_list.push(
                                    path(
                                        {
                                            key: "sge.#{_idx}.#{_sub_idx}"
                                            d: _call(_outer, _outer_detail, _sub_start_arc, _sub_end_arc)
                                            className : "svg-inactive svg-outline"
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
                                        className: "sb-lines svg-white"
                                    }
                                )
                            )

            if @props.title?
                _text_height = if @props.titleSize? then @props.titleSize else 10
                _title_el = text(
                    {
                        x: "#{_w/2}px"
                        y: "#{_text_height/2 + 3}px"
                        key: "svg.title"
                        textAnchor: "middle"
                        fontSize: "#{_text_height}px"
                        className: "svg-txt-color"
                        # alignmentBaseline: "middle"  # bad for browser/ os compat
                        fontWeight: "bold"
                    }
                    @props.title
                )
            else
                _text_height = 0
                _title_el = null
            if @props.text?
                _raw_text_list.push(@props.text)
            _text_list = []
            _idx = 0
            _len = _raw_text_list.length + 1
            # calculate text size
            _text_size = _.min([parseInt(@props.size / (1.6 * _len)), 12])
            for _text in _raw_text_list
                _idx++
                _text_list.push(
                    text(
                        {
                            x: 0
                            y: - _text_size / 2 * _len + _text_size * _idx
                            key: "svg.text.#{_idx}"
                            textAnchor: "middle"
                            fontSize: "#{_text_size}px"
                            # alignmentBaseline: "middle"  # bad for browser/ os compat
                            paintOrder: "stroke"
                            className: "svg-stroke default-text"
                        }
                        _text
                    )
                )
            _translate_y = if @props.title? and @props.titleSize? then 70 + @props.titleSize else 70
            _viewbox = if @props.title? then "3 -4 134 156" else "3 3 133 133"
            return div(
                {
                    key: "div.top"
                    className: @props.className
                }
                svg(
                    {
                        key: "svg.top"
                        width: "99%"  # browser crap
                        viewBox: _viewbox
                    }
                    g(
                        {
                            key: "main"
                        }
                        _title_el
                        g(
                            {
                                key: "content"
                                # transform: "translate(#{_w/2}, #{_w/2 + _text_height})"
                                transform: "translate(70, #{_translate_y})"
                            }
                            _p_list
                            _text_list
                        )
                    )
                )
            )
    )
]).directive("icswLivestatusCircleInfo",
[
    "$templateCache", "icswLivestatusCircleInfoReact",
(
    $templateCache, icswLivestatusCircleInfoReact,
) ->
    return {
        restrict: "EA"
        scope:
            mon_data: "=icswMonitoringData"
            notifier: "=icswNotifier"
            type: "@icswDisplayType"
        link: (scope, element, attrs) ->
            _render = () ->
                scope.mon_data.build_luts()
                ReactDOM.render(
                    React.createElement(
                        icswLivestatusCircleInfoReact
                        {
                            data: scope.mon_data["#{scope.type}_circle_data"]
                            showInfo: false
                        }
                    )
                    element[0]
                )
            _render()
            scope.notifier.promise.then(
                (resolved) ->
                (reject) ->
                (info) ->
                    _render()
            )
    }
]).directive("icswLivestatusTextInfo",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        scope:
            mon_data: "=icswMonitoringData"
            notifier: "=icswNotifier"
            type: "@icswDisplayType"
        template: $templateCache.get("icsw.livestatus.text.info")
        link: (scope, element, attrs) ->

            _render = () ->
                scope.mon_data.build_luts()
                _data = scope.mon_data["#{scope.type}_circle_data"]
                if _data.length
                    _info_str = (
                        "#{entry.value} #{entry.data.info}" for entry in _data
                    ).join(", ")
                else
                    _info_str = "N/A"
                scope.$$info_str = _info_str
            scope.$$info_str = "N/A"
            scope.notifier.promise.then(
                (resolved) ->
                (reject) ->
                (info) ->
                    _render()
            )
    }
])
