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

angular.module(
    "icsw.tools.piechart", ["icsw.tools"]
).service("icswToolsPiechartReact",
[
    "$q", "icswTooltipTools",
(
    $q, icswTooltipTools,
) ->
    {svg, g, div, path, circle} = React.DOM

    part_fact = React.createFactory(
        React.createClass(
            propTypes: {
                tooltip: React.PropTypes.object
                data: React.PropTypes.object
                idx: React.PropTypes.number
                commands: React.PropTypes.array
            }
            render: () ->
                entry = @props.data
                i = @props.idx
                if entry.$$data?
                    _path = path(
                        {
                            key: "path.idx#{i}"
                            className: "pie-segment #{entry.$$data.svgClassName}"
                            d: @props.commands.join(" ")
                        }
                    )
                else
                    _path = path(
                        {
                            key: "path.idx#{i}"
                            className: "pie-segment"
                            d: @props.commands.join(" ")
                            fill: entry.color
                        }
                    )
                return g(
                    {
                        key: "g.idx#{i}"
                        className: "pie-segment-group"
                        onMouseEnter: (event) =>
                            entry = @props.data
                            node = {
                                node_type: "simplepiechart"
                            }
                            if entry.$$data?
                                node.data = "#{entry.$$data.StateString}: #{entry.$$perc_value}%"
                            else
                                node.data = "#{entry.title}: #{entry.$$perc_value}%"
                            icswTooltipTools.show(@props.tooltip, node)
                        onMouseMove: (event) =>
                            icswTooltipTools.position(@props.tooltip, event)
                        onMouseLeave: (event) =>
                            icswTooltipTools.hide(@props.tooltip)
                    }
                    _path
                )
        )

    )
    return React.createClass(
        propTypes: {
            diameter: React.PropTypes.number
            data: React.PropTypes.array
            tooltip: React.PropTypes.object
        }

        displayName: "icswToolsPiechart"

        render: () ->
            diameter =@props.diameter
            center_x = diameter/2
            center_y = diameter/2
            radius = diameter/2

            value_total = 0

            for entry in @props.data
                value_total += entry.value

            # calculations based on value_total (cant do these in loop above)

            start_angle = -Math.PI/2
            i = 0
            _g_elements = []
            for entry in @props.data
                # calc general properties (currently only used in calc_path)
                part = entry.value / value_total
                part_angle = part * (Math.PI*2)
                perc_value = part * 100
                entry.$$perc_value = _.round(perc_value, 3)

                end_angle = start_angle + part_angle

                if part == 1.0  # full circle
                    cmd = [
                        'M', center_x, center_y,
                        'm', -radius, 0,
                        'a', radius, radius, 0, 1, 0, 2 * radius, 0,
                        'a', radius, radius, 0, 1, 0, -2 * radius, 0
                    ]
                else
                    startX = center_x + Math.cos(start_angle) * radius
                    startY = center_y + Math.sin(start_angle) * radius

                    endX = center_x + Math.cos(end_angle) * radius
                    endY = center_y + Math.sin(end_angle) * radius

                    largeArc = if ((end_angle - start_angle) % (Math.PI * 2)) > Math.PI then 1 else 0

                    cmd = [
                        'M', startX, startY,  # move
                        'A', radius, radius, 0, largeArc, 1, endX, endY,  # arc
                        'L', center_x, center_y,  #line to the center.
                        'Z'
                    ]
                _g_elements.push(
                    part_fact(
                        {
                            key: "pf#{i}"
                            idx: i
                            tooltip: @props.tooltip
                            data: entry
                            commands: cmd
                        }
                    )
                )
                start_angle = end_angle
                i++
            if diameter > 40
                # append a black circle
                _g_elements.push(
                    circle(
                        {
                            key: "olc"
                            fill: "none"
                            cx: center_x
                            cy: center_y
                            r: radius - 2
                            stroke: "#222222"
                            strokeWidth: if diameter > 30 then 2 else 1
                        }
                    )
                )
            return div(
                {
                    key: "top"
                    className: "icswChart"
                    style: {width: "#{diameter}px", height: "#{diameter}px"}
                }
                svg(
                    {
                        key: "svgtop"
                        style: {
                            width: "#{diameter}px"
                            height: "#{diameter}px"
                            viewBox: "-1 -1 #{diameter + 2} #{diameter + 2}"
                        }
                    }
                    g(
                        {
                            key: "gtop"
                            opacity: 1
                        }
                        _g_elements
                    )
                )
            )
    )
]).directive("icswToolsPiechart",
[
    "icswToolsPiechartReact", "icswTooltipTools",
(
    icswToolsPiechartReact, icswTooltipTools,
) ->
    return {
        restrict: "E"
        scope:
            data: "=data"  # [{value: 0.34, title: "foo", color: "#ff0000"}]
            diameter: "=diameter"
            trigger: "=icswTrigger"
        link : (scope, element, attrs) ->

            struct = icswTooltipTools.create_struct(element)
            render = () ->
                _el = ReactDOM.render(
                    React.createElement(
                        icswToolsPiechartReact
                        {
                            diameter: scope.diameter
                            data: scope.data
                            tooltip: struct
                        }
                    )
                    element[0]
                )
            scope.$on(
                "$destroy"
                () ->
                    icswTooltipTools.delete_struct(struct)
            )
            if attrs["icswTrigger"]?
                scope.$watch(
                    "trigger"
                    (new_val) ->
                        render()
                )
            else
                scope.$watchGroup(
                    ["data", "diameter"],
                    (new_data) ->
                        if scope.data?
                            render()
                    )
    }
])
