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
    "icsw.tools.piechart", ["icsw.tools"]
).directive("icswToolsPiechart",
[
    "createSVGElement",
(
    createSVGElement,
) ->
    return {
        restrict: "E"
        scope:
            data: "=data"  # [{value: 0.34, title: "foo", color: "#ff0000"}]
            diameter: "=diameter"
        link : (scope, element, attrs) ->

            _build_pie = (data) ->

                element.empty()

                diameter = scope.diameter
                center_x = diameter/2
                center_y = diameter/2
                radius = diameter/2

                _div = angular.element("<div class='icsw-chart'></div>")
                _div.css("width", "#{diameter}px").css("height", "#{diameter}px")
                _svg = createSVGElement("svg", {width: diameter, height: diameter, viewBox: "-1 -1 #{diameter + 2} #{diameter + 2}"})
                _div.append(_svg)
                _g = createSVGElement("g", {opacity: 1})
                _svg.append(_g)

                _tooltip = angular.element("<div/>")
                _tooltip.addClass("icsw-tooltip")
                _tooltip.hide()
                _div.append(_tooltip)

                _mousemove = (event) ->
                    entry = event.data
                    _pos_x = event.offsetX - _tooltip.width() / 2
                    _pos_y = event.offsetY - _tooltip.height() - 10
                    _tooltip.css("left", "#{_pos_x}px")
                    _tooltip.css("top", "#{_pos_y}px")

                value_total = 0

                for entry in data
                    value_total += entry.value

                # calculations based on value_total (cant do these in loop above)

                start_angle = -Math.PI/2
                i = 0
                for entry in data
                    # calc general properties (currently only used in calc_path)
                    part = entry.value / value_total
                    part_angle = part * (Math.PI*2)

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
                    # new_entry.tooltip_visible = false

                    _part_g = createSVGElement(
                        "g"
                        {
                            "data-active": 1
                            class: "pieSegmentGroup"
                            "data-order": i
                        }
                    )
                    _path = createSVGElement(
                        "path"
                        {
                            class: "pieSegment #{entry.cssclass}"
                            d: cmd.join(" ")
                        }
                    )
                    _part_g.append(_path)
                    _g.append(_part_g)
                    _part_g.bind("mouseenter", entry, (event) ->
                        entry = event.data
                        _tooltip.html("#{entry.title}: #{entry.value}%")
                        _mousemove(event)
                        _tooltip.show()
                    ).bind("mouseleave", (event) ->
                        _tooltip.hide()
                    ).bind("mousemove", entry, (event) ->
                        _mousemove(event)
                    )
                    start_angle = end_angle
                    i++

                element.append(_div)

            scope.$watchGroup(
                ["data", "diameter"],
                (new_data) ->
                    if scope.data?
                        _build_pie(scope.data)
                )
    }
])

