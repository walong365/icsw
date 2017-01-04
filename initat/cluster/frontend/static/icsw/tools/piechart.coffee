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
    "$q", "icswTooltipTools", "icswDeviceLivestatusFunctions",
(
    $q, icswTooltipTools, icswDeviceLivestatusFunctions,
) ->
    {svg, g, div, path, circle} = React.DOM

    part_fact = React.createFactory(
        React.createClass(
            propTypes: {
                tooltip: React.PropTypes.object
                data: React.PropTypes.object
                idx: React.PropTypes.number
                commands: React.PropTypes.string
            }
            render: () ->
                entry = @props.data
                i = @props.idx
                if entry.$$data?
                    _path = path(
                        {
                            key: "path.idx#{i}"
                            className: "pie-segment #{entry.$$data.svgClassName}"
                            d: @props.commands
                        }
                    )
                else
                    _path = path(
                        {
                            key: "path.idx#{i}"
                            className: "pie-segment"
                            d: @props.commands
                            fill: entry.color
                        }
                    )
                return g(
                    {
                        key: "g.idx#{i}"
                        className: "pie-segment-group"
                        onMouseEnter: (event) =>
                            entry = @props.data
                            if entry.$$tooltipType?
                                node = {
                                    node_type: entry.$$tooltipType
                                    data: entry
                                }
                            else
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
            maxWidth: React.PropTypes.string
        }

        displayName: "icswToolsPiechart"

        render: () ->
            diameter =@props.diameter
            center_x = diameter / 2
            center_y = diameter / 2
            radius = diameter / 2

            # build rings
            # the ring with ring_id == 0 is outside
            rings = {}
            for entry in @props.data
                if entry.ring_id?
                    _ring_id = entry.ring_id
                else
                    _ring_id = 0
                if _ring_id not of rings
                    rings[_ring_id] = []
                rings[_ring_id].push(entry)

            ring_ids = _.sortBy((parseInt(_val) for _val in _.keys(rings)))

            _g_elements = []
            i = 0
            for ring_id in ring_ids
                ring_radius = radius * (ring_ids.length - ring_id) / ring_ids.length
                inner_radius = radius * (ring_ids.length - ring_id - 1) / ring_ids.length

                data_stream = rings[ring_id]

                value_total = 0
                for entry in data_stream
                    value_total += entry.value

                # calculations based on value_total (cant do these in loop above)

                if value_total > 0
                    # only draw ring if any segment has a value > 0
                    start_angle = -Math.PI/2
                    for entry in data_stream
                        # calc general properties (currently only used in calc_path)
                        part = entry.value / value_total
                        part_angle = part * (Math.PI*2)
                        perc_value = part * 100
                        entry.$$perc_value = _.round(perc_value, 3)

                        end_angle = start_angle + part_angle

                        if entry.value == value_total
                            cmd = icswDeviceLivestatusFunctions.ring_path(inner_radius, ring_radius)
                        else if entry.value > 0
                            cmd = icswDeviceLivestatusFunctions.ring_segment_path(inner_radius, ring_radius, start_angle, end_angle)
                        else
                            cmd = null
                        if cmd
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
                else
                    _g_elements.push(
                        circle(
                            {
                                key: "olc.ir#{ring_id}"
                                fill: "#cccccc"
                                cx: 0
                                cy: 0
                                r: ring_radius - 1
                            }
                        )
                    )
                # if diameter > 0
                # append a black circle
                if diameter > 40
                    _cr = 2
                else if diameter > 15
                    _cr = 1
                else
                    _cr = 0.5
                _g_elements.push(
                    circle(
                        {
                            key: "olc.or#{ring_id}"
                            fill: "none"
                            cx: 0
                            cy: 0
                            r: ring_radius - 1
                            stroke: "#222222"
                            strokeWidth: _cr
                        }
                    )
                )
            return svg(
                {
                    key: "svgtop"
                    width: "100%"
                    preserveAspectRatio: "xMidYMid meet"
                    style: {
                        maxWidth: if @props.maxWidth then "#{@props.maxWidth}px" else null
                    }
                    # style: {
                        # width: "#{diameter + 2}px"
                        # height: "#{diameter + 2}px"
                    viewBox: "-1 -1 #{diameter + 3} #{diameter + 3}"
                    # }
                }
                g(
                    {
                        key: "gtop"
                        opacity: 1
                        transform: "translate(#{center_x + 1},#{center_y + 1})"
                    }
                    _g_elements
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
            max_width: "@icswMaxWidth"
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
                            maxWidth: scope.max_width
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
