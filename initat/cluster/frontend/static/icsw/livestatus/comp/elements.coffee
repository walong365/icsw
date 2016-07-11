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
    {div, svg, g, rect, path} = React.DOM
    return React.createClass(
        propTypes: {
            size: React.PropTypes.number
            # list of (size, color) tuples
            data: React.PropTypes.array
        }
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
            _total = _.sum((_el[0] for _el in _d))
            _idx = 0
            _end_arc = - Math.PI * 0.5
            _cur_size = 0
            _p_list = []
            _outer = _w / 2.0 * 0.95
            _inner = _w / 2.0 * 0.5
            for [d_size, color] in _d
                _idx++
                if d_size
                    _cur_size += d_size
                    _start_arc = _end_arc
                    _end_arc = Math.PI * 2.0 * _cur_size / _total - Math.PI * 0.5
                    if d_size == _total
                        _call = icswDeviceLivestatusFunctions.ring_path
                    else
                        _call = icswDeviceLivestatusFunctions.ring_segment_path
                    _p_list.push(
                        path(
                            {
                                key: "sge.#{_idx}"
                                d: _call(_inner, _outer, _start_arc, _end_arc)
                                fill: color
                                style: {stroke: "#000000", strokeWidth: "0.5px"}
                            }
                        )
                    )
            return svg(
                {
                    key: "svg.top"
                    width: "#{_w}px"
                    height: "#{_w}px"
                }
                g(
                    {
                        key: "main"
                    }
                    g(
                        {
                            key: "content"
                            transform: "translate(#{_w/2}, #{_w/2})"
                        }
                        _p_list
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
                            size: 24
                            data: scope.mon_data.service_circle_data
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
                            size: 24
                            data: scope.mon_data.device_circle_data
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
